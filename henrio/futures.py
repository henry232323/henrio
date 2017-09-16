from time import monotonic
from types import coroutine


@coroutine
def ayield():
    yield


@coroutine
def sleep(seconds):
    if seconds == 0:
        yield
    else:
        yield ("sleep", monotonic() + seconds)


class CancelledError(Exception):
    pass


class Future:
    def __init__(self):
        self._result = None
        self._error = None
        self.complete = False
        self.cancelled = False
        self._current = self.__await__()

    def __repr__(self):
        fmt = "{0} {1} {2}".format(self._result, self._error, self._data)
        if self.cancelled:
            return "<Cancelled {0} {1}>".format(self.__class__.__name__, fmt)
        else:
            return "<{0} complete={1} {2}>".format(self.__class__.__name__, self.complete, fmt)

    def result(self):
        if self._error is not None:
            raise self._error
        if not self.complete:
            raise RuntimeError("Result isn't ready!")
        return self._result

    def set_result(self, data):
        if self.complete or self._error is not None:
            raise RuntimeError("Future already completed")
        self.complete = True
        self._result = data

    def set_exception(self, exception):
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
    def __init__(self, task, data):
        super().__init__()
        self._task = task
        self._data = data

    def send(self, data):
        return self._task.send(data)

    def throw(self, exc):
        return self._task.throw(exc)


class File:
    def __init__(self, file):
        pass
