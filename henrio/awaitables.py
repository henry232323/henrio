import typing
from types import coroutine

from . import CancelledError


@coroutine
def sleep(seconds: typing.Union[float, int]):
    if seconds == 0:
        yield
    else:
        yield ("sleep", seconds)


class Future:
    def __init__(self):
        self._data = None
        self._result = None
        self._error = None
        self.complete = False
        self.cancelled = False
        self._current = None
        self._running = False
        self._callback = None

    def __lt__(self, other):
        return False

    def running(self):
        return self._running

    def done(self):
        return self.complete

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
        if self._callback:
            self._callback()

    def set_exception(self, exception: typing.Union[Exception, typing.Callable[..., Exception]]):
        if self.complete or self._error is not None:
            raise RuntimeError("Future already completed")
        self._error = exception

    def cancel(self):
        if self.cancelled:
            return True
        if self.complete:
            return False
        if self.running:
            return False
        self.cancelled = True
        self.set_exception(CancelledError)

    def __iter__(self):
        while not self.complete and self._error is None:
            yield self
        return self.result()

    __await__ = __iter__

    def send(self, data):
        if not self.complete and self._error is None:
            return self
        return self.result()

    def add_done_callback(self, fn):
        self._callback = fn


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

    def __iter__(self):
        return self._task

    __await__ = __iter__

    def send(self, data):
        return self._task.send(data)

    def throw(self, exc):
        return self._task.throw(exc)
