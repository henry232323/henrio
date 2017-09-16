from time import monotonic
from types import coroutine


@coroutine
def ayield():
    yield


@coroutine
def sleep(seconds):
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
        self._current.send(data)

    def throw(self, exc):
        self._current.send(exc)


class Task(Future):
    def __init__(self, task, data):
        super().__init__()
        self._task = task
        self._data = data

    def send(self, data):
        self._task.send(data)

    def throw(self, exc):
        self._task.throw(exc)


class File:
    def __init__(self):
        file
