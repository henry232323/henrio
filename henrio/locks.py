from collections import deque
from weakref import ref

from .futures import Future
from .yields import current_task

__all__ = ["Lock", "ResourceLock"]


class Lock:
    def __init__(self):
        self._queue = deque()
        self._holder = None
        self._held = False

    @property
    def holder(self):
        if self._holder is not None:
            return self._holder()

    @holder.setter
    def holder(self, value):
        if value is not None:
            self._holder = ref(value)
        else:
            self._holder = None

    @property
    def locked(self):
        return self._held

    async def release(self):
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

    async def acquire(self):
        if not self._held:
            self._held = True
            ct = await current_task()
            self.holder = ct
        else:
            fut = Future()
            self._queue.append(fut)
            await fut
            self.holder = await current_task()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.release()
        if exc_type:
            raise exc_value


class ResourceLock(Lock):
    def __init__(self, value):
        super().__init__()
        self._value = value

    async def __aenter__(self):
        await self.acquire()
        return self._value
