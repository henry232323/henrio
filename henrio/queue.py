from collections import deque
from heapq import heappush, heappop

from . import Future
from types import coroutine

__all__ = ["Queue", "HeapQueue", "QueueWouldBlock"]


class QueueWouldBlock(Exception):
    pass


class Queue:
    def __init__(self, size=0, lifo=False):
        """A generic queue with limited space. FIFO or LIFO."""
        self._lifo = lifo
        self.size = size
        self._getters = deque()
        self._putters = deque()
        self._queue = deque()

    def __len__(self):
        return len(self._queue)

    def __repr__(self):
        return "{3}({0}, lifo={1}, size={2})".format(repr(self._queue)[6:-1],
                                                     self._lifo, self.size,
                                                     self.__class__.__name__)

    def empty(self):
        """Check if the queue is empty"""
        return not self._queue

    def full(self):
        """Check if the queue is full"""
        return self.size and len(self._queue) == self.size

    async def get(self):
        """Wait to get an item from the queue, or immediately get one if one is available."""
        if not self.empty():
            result = self._pop()
            if self._putters:
                future, item = self._putters.popleft()
                while future.cancelled:
                    future, item = self._putters.popleft()
                self._append(item)
                future.set_result(None)
            return result

        future = Future()
        self._getters.append(future)
        return await future

    async def put(self, item):
        """Wait to append to the queue or immediately append to the queue if it is not full."""
        if not self.full():
            if self._getters:
                getter = self._getters.popleft()
                while getter.cancelled:
                    getter = self._getters.popleft()
                getter.set_result(item)
                return
            self._append(item)
            return

        future = Future()
        self._putters.append((future, item))
        return await future

    def get_nowait(self):
        """Try to get from the queue immediately, raises `QueueWouldBlock` on failure"""
        if self.empty():
            raise QueueWouldBlock("Queue is empty!")
        return self._pop()

    def put_nowait(self, item):
        """Try to append to the queue immediately, raises `QueueWouldBlock` on failure"""
        if self.full():
            raise QueueWouldBlock("Queue is full!")
        return self._append(item)

    def _pop(self):
        if self._lifo:
            return self._queue.pop()
        return self._queue.popleft()

    def _append(self, item):
        self._queue.append(item)

    def setlifo(self, bool: bool):
        """Set whether the queue is FIFO or LIFO"""
        self._lifo = bool

    async def __anext__(self):
        return await self.get()

    async def __aiter__(self):
        return self

    @coroutine
    def join(self):
        """Wait until the queue is empty"""
        while self._queue:
            yield


class HeapQueue(Queue):
    def __init__(self, size=0):
        """A Heap queue that gets and puts like the heapq module."""
        self.size = size
        self._getters = deque()
        self._putters = deque()
        self._queue = list()

    def __repr__(self):
        return "{2}({0}, size={1})".format(repr(self._queue), self.size, self.__class__.__name__)

    def _pop(self):
        return heappop(self._queue)

    def _append(self, item):
        return heappush(self._queue, item)

    @property
    def setlifo(self):
        raise AttributeError("HeapQueue doesn't implement LIFO!")
