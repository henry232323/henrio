from collections import deque

from . import Future

__all__ = ["Queue"]


class Queue:
    def __init__(self, size=0, lifo=False):
        self._lifo = lifo
        self.size = size
        self._getters = deque()
        self._putters = deque()
        self._queue = deque()

    def __len__(self):
        return len(self._queue)

    def __repr__(self):
        return "{3}({0}, lifo={1}, size={2})".format(self._queue.__repr__()[6:-1],
                                                     self._lifo, self.size,
                                                     self.__class__.__name__)

    def empty(self):
        return not self._queue

    def full(self):
        return self.size and len(self._queue) == self.size

    async def get(self):
        if not self.empty():
            result = self._pop()
            if self._putters:
                future, item = self._putters.popleft()
                self._queue.append(item)
                future.set_result(None)
            return result

        future = Future()
        self._getters.append(future)
        return await future

    async def put(self, item):
        if not self.full():
            if self._getters:
                self._getters.popleft().set_result(item)
                return
            self._queue.append(item)
            return

        future = Future()
        self._putters.append((future, item))
        return await future

    def _pop(self):
        if self._lifo:
            return self._queue.pop()
        return self._queue.popleft()

    def setlifo(self, bool: bool):
        self._lifo = bool

    async def __anext__(self):
        return await self.get()

    async def __aiter__(self):
        return self
