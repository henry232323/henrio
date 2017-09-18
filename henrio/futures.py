import typing
import socket
from types import coroutine
from collections import deque

from . import CancelledError

@coroutine
def sleep(seconds: typing.Union[float, int]):
    if seconds == 0:
        yield
    else:
        yield ("sleep", seconds)


class Future:
    def __init__(self):
        self._result = None
        self._error = None
        self.complete = False
        self.cancelled = False
        self._current = self.__await__()

    def result(self):
        if self._error is not None:
            raise self._error
        if not self.complete:
            raise RuntimeError("Result isn't ready!")
        return self._result

    def set_result(self, data: typing.Any):
        if self.complete or self._error is not None:
            raise RuntimeError("Future already completed")
        self.complete = True
        self._result = data

    def set_exception(self, exception: typing.Union[Exception, typing.Callable[..., Exception]]):
        if self.complete or self._error is not None:
            raise RuntimeError("Future already completed")
        self._error = exception

    def cancel(self):
        if self.cancelled:
            return True
        if self.complete:
            return False
        self.cancelled = True
        self.set_exception(CancelledError)

    def __await__(self):
        if not self.complete and self._error is None:
            yield self
        return self.result()

    def send(self, data):
        return self._current.send(data)

    def throw(self, exc):
        return self._current.send(exc)


class Task(Future):
    def __init__(self, task: typing.Union[typing.Generator, typing.Awaitable], data: typing.Any):
        super().__init__()
        self._task = task
        self._data = data

    def __repr__(self):
        fmt = "{0} {1} {2}".format(self._result, self._error, self._data)
        if self.cancelled:
            return "<Cancelled {0} {1}>".format(self.__class__.__name__, fmt)
        else:
            return "<{0} complete={1} {2}>".format(self.__class__.__name__, self.complete, fmt)

    def send(self, data):
        return self._task.send(data)

    def throw(self, exc):
        return self._task.throw(exc)


class File:
    def __init__(self, file: typing.IO[typing.AnyStr], loop=None):
        self.loop = loop
        self.file = file
        self._read_queue = deque()
        self._write_queue = deque()

    def _read_ready(self, value: bool):
        if value and self._read_queue:
            fut, (type, nbytes) = self._read_queue.popleft()
            if type == 0:
                fut.set_result(self.file.read(nbytes))
            elif type == 1:
                fut.set_result(self.file.readline(nbytes))

    def _write_ready(self, value: bool):
        if value and self._write_queue:
            fut, data = self._write_queue.popleft()
            fut.set_result(self.file.write(data))

    async def read(self, nbytes: int=-1) -> typing.AnyStr:
        fut = Future()
        self._read_queue.append((fut, (0, nbytes)))
        return await fut

    async def readline(self, nbytes: int=-1) -> typing.AnyStr:
        fut = Future()
        self._read_queue.append((fut, (1, nbytes)))
        return await fut

    async def write(self, data: typing.AnyStr):
        fut = Future()
        self._write_queue.append((fut, data))
        return await fut

    @property
    def fileno(self):
        return self.file.fileno()

    def close(self):
        del self.loop._files[self.file.fileno()]
        self.loop.selector.unregister(self.file)
        self.file.close()


class Socket:
    def __init__(self, file: socket.socket, loop=None):
        self.loop = loop
        self.file = file
        self._read_queue = deque()
        self._write_queue = deque()

    def _read_ready(self, value: bool):
        if value and self._read_queue:
            fut, nbytes = self._read_queue.popleft()
            fut.set_result(self.file.recv(nbytes))

    def _write_ready(self, value: bool):
        if value and self._write_queue:
            fut, data = self._write_queue.popleft()
            fut.set_result(self.file.send(data))

    async def recv(self, nbytes: int) -> bytes:
        fut = Future()
        self._read_queue.append((fut, nbytes))
        return await fut

    async def send(self, data: bytes):
        fut = Future()
        self._write_queue.append((fut, data))
        return await fut

    @property
    def fileno(self):
        return self.file.fileno()

    def close(self):
        del self.loop._files[self.file.fileno()]
        self.loop.selector.unregister(self.file)
        self.file.close()
