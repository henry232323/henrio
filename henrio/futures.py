import typing
from concurrent.futures import CancelledError
from functools import partial
from types import coroutine

__all__ = ["Future", "Task", "Conditional", "Event"]


class Future:
    def __init__(self):
        """An awaitable that will yield until an exception or result is set."""
        self._data = None
        self._result = None
        self._error = None
        self.complete = False
        self.cancelled = False
        self._running = False
        self._callback = None
        self._joiners = list()

    __lt__ = lambda *_: False  # We use this to make sure heapsort doesn't get mad at us, its arbitrary

    # And more importantly, an implementation detail

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
        for fut in self._joiners:
            fut.set_result(None)

    def set_exception(self, exception):
        if self.complete or self._error is not None:
            raise RuntimeError("Future already completed")
        self._error = exception
        for fut in self._joiners:
            fut.set_exception(exception)

    def cancel(self):
        if self.cancelled:
            return True
        if self.complete:
            return False
        if self.running():
            return False
        self.cancelled = True
        self.set_exception(CancelledError)
        return True

    def __iter__(self):
        yield self
        return self.result()

    __await__ = __iter__

    def send(self, data):
        if not self.complete and self._error is None:
            return self
        raise StopIteration(self.result())

    def add_done_callback(self, fn, *args, **kwargs):
        self._callback = partial(fn, args=args, kwargs=kwargs)

    def close(self):
        self._error = StopIteration("Closed!")

    async def wait(self):
        if self.complete or self.cancelled or self._error:
            return
        fut = Future()
        self._joiners.append(fut)
        await fut


class Task:
    def __init__(self, task: typing.Union[typing.Generator, typing.Awaitable], data: typing.Any):
        """A Future that wraps a coroutine or another future"""
        self._data = None
        self._result = None
        self._error = None
        self.complete = False
        self.cancelled = False
        self._running = False
        self._callback = None
        self._joiners = list()
        self._throw_later = None
        super().__init__()
        if hasattr(task, "__await__"):
            self._task = task.__await__()
        else:
            self._task = task
        self._data = data

    def __repr__(self):
        fmt = "{0} {1} {2} {3}".format(self._result if self._data is not self else "self",
                                       self._error,
                                       self._data if self._data is not self else "self",
                                       self._task.__class__.__name__)
        if self.cancelled:
            return "<Cancelled {0} {1}>".format(self.__class__.__name__, fmt)
        else:
            return "<{0} complete={1} {2}>".format(self.__class__.__name__, self.complete, fmt)

    __lt__ = lambda *_: False

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
        for fut in self._joiners:
            fut.set_result(None)

    def set_exception(self, exception: typing.Union[Exception, typing.Callable[..., Exception]]):
        if self.complete or self._error is not None:
            raise RuntimeError("Future already completed")
        self._error = exception
        for fut in self._joiners:
            fut.set_exception(exception)

    def __iter__(self):
        return self._task

    __await__ = __iter__

    def send(self, data):
        return self._task.send(data)

    def throw(self, exc):
        return self._task.throw(exc)

    def cancel(self):
        if self.cancelled:
            return True
        if self.complete:
            return False
        if self.running():
            return False
        try:
            self.throw(CancelledError)
        except CancelledError:
            self.cancelled = True
            self.set_exception(CancelledError)
            return True
        except StopIteration as err:
            self.set_result(err.value)
            return False
        else:
            return False

    def close(self):
        self._task.close()

    async def wait(self):
        fut = Future()
        self._joiners.append(fut)
        await fut


class Conditional(Future):
    def __init__(self, condition: typing.Callable[..., bool]):
        """An awaitable that waits until the condition becomes true. Returns whatever the done callback returns"""
        super().__init__()
        self.condition = condition

    def __iter__(self):
        while not self.condition():
            yield
        return self.result()

    __await__ = __init__  # These just keep yielding / passing until our condition is true.

    def send(self, data):
        if not self.condition():
            return
        raise StopIteration(self.result())

    def result(self):
        if self._error is not None:
            raise self._error
        if not self.complete:
            raise RuntimeError("Result isn't ready!")
        return self._callback()


class Event:
    def __init__(self):
        self._value = False
        self._waiters = 0

    @coroutine
    def wait(self):
        self._waiters += 1
        while not self.value:
            yield
        self._waiters -= 1

    def set(self):
        self.value = True

    async def clear(self):
        while self._waiters > 0:
            yield
        self.value = False
