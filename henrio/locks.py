from collections import deque
from weakref import ref

from .futures import Future
from .yields import current_task

__all__ = ["Lock", "ResourceLock", "Semaphore"]


class Lock:
    def __init__(self):
        """A generic lock. Use like any other lock. Holder is decided by Task"""
        self._queue = deque()
        self._holder = None
        self._held = False

    @property
    def holder(self):
        """Gets the task that currently owns the lock"""
        if self._holder is not None:
            return self._holder()

    @holder.setter
    def holder(self, value):  # The idea here is that if the holder of a lock disappears we can assume its released
        if value is not None:
            self._holder = ref(value)
        else:
            self._holder = None

    @property
    def locked(self):
        return self._held

    async def acquire(self):
        """Waits to acquire the lock and registers the holder as the current task."""
        if not self._held:
            self._held = True
            ct = await current_task()
            self.holder = ct
        else:
            fut = Future()
            self._queue.append(fut)
            await fut
            self.holder = await current_task()

    async def release(self):
        """Release the lock and set the holder to None"""
        ct = await current_task()
        if self.holder == ct:
            if self._queue:
                self._held = True
                self._queue.popleft().set_result(None)
            else:
                self._held = False
                self.holder = None
        else:
            raise RuntimeError("You don't currently hold this lock!")

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.release()
        if exc_type:
            raise exc_value


class ResourceLock(Lock):
    """A lock that holds a resource"""
    def __init__(self, value):
        super().__init__()
        self._value = value

    async def acquire(self):
        """Acquire the lock and return the value"""
        await super().acquire()
        return self._value

    async def __aenter__(self):
        return await self.acquire()


class Semaphore(Lock):
    def __init__(self, maxholders=1):
        """A lock that can be held by up to `maxholders` tasks"""
        super().__init__()
        self.maxholders = maxholders
        self.holders = []

    @property
    def locked(self):
        return len(self.holders) == self.maxholders

    async def acquire(self):
        """Wait to acquire the lock"""
        if not self.locked:
            ct = await current_task()
            self.holders.append(ct)
        else:
            fut = Future()
            self._queue.append(fut)
            await fut
            self.holders.append(await current_task())

    async def release(self):
        """Release the lock"""
        ct = await current_task()
        if ct in self.holders:
            if self._queue:
                self._queue.popleft().set_result(None)
            else:
                self.holders.remove(ct)
        else:
            raise RuntimeError("You don't currently hold this lock!")


class ResourceManager:
    def __init__(self, lock_factory=Lock):
        """A class for managing multiple locks on arbitrary resources."""
        self.locks = {}
        self._lock_factory = lock_factory

    async def acquire(self, resource):
        if resource in self.locks:
            await self.locks[resource].acquire()
        else:
            lock = self.locks[resource] = self._lock_factory()
            await lock.acquire()

    async def release(self, resource):
        if resource in self.locks:
            lock = self.locks[resource]
            await lock.release()
            if lock.holder is None:
                del self.locks[resource]
        else:
            raise RuntimeError("This lock is not being held!")
