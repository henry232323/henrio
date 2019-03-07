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

    def __repr__(self):
        fmt = "result={0}, error={1}, data={2}".format(self._result if self._data is not self else "self",
                                       self._error,
                                       self._data if self._data is not self else "self")
        if self.cancelled:
            return "<Cancelled {0} {1}>".format(self.__class__.__name__, fmt)
        else:
            return "<{0} complete={1} {2}>".format(self.__class__.__name__, self.complete, fmt)

    __lt__ = lambda *_: False  # We use this to make sure heapsort doesn't get mad at us, its arbitrary

    # And more importantly, an implementation detail

    def running(self):
        """Check if future is running"""
        return self._running

    def done(self):
        """Check if future is done"""
        return self.complete

    def result(self):
        """Get the result of the future. Will raise if it isnt ready or an error has been set."""
        if self._error is not None:
            raise self._error
        if not self.complete:
            raise RuntimeError("Result isn't ready!")
        return self._result

    def set_result(self, data: typing.Any):
        """Set the result of the future"""
        if self.complete or self._error is not None:
            raise RuntimeError("Future already completed")
        self.complete = True
        self._result = data
        for fut in self._joiners:
            fut.set_result(None)

    def set_exception(self, exception: BaseException):
        """Set the future's exception to raise when returning control"""
        if self.complete or self._error is not None:
            raise RuntimeError("Future already completed")
        self._error = exception
        for fut in self._joiners:
            fut.set_exception(exception)

    def cancel(self):
        """Try to cancel a coroutine. Will return True if successfully raised otherwise False"""
        if self.cancelled:
            return True
        if self.complete:
            return False
        if self.running():
            return False
        self.cancelled = True
        self.set_exception(CancelledError("Execution of this coro has been cancelled!"))
        return True

    def __iter__(self):
        """Wait for the Future to complete."""
        yield self
        return self.result()

    __await__ = __iter__

    def send(self, data):
        if not self.complete and self._error is None:
            return self
        raise StopIteration(self.result())

    def add_done_callback(self, fn, *args, **kwargs):
        """Add a callback to execute when the future finishes."""
        self._callback = partial(fn, args=args, kwargs=kwargs)

    def close(self):
        self._error = StopIteration("Closed!")

    async def wait(self):
        """Wait on this future to finish (different than awaiting, which should not be done except for the original caller)"""
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
        fmt = "result={0}, error={1}, data={2}, class={3}".format(self._result if self._data is not self else "self",
                                       self._error,
                                       self._data if self._data is not self else "self",
                                       self._task.__class__.__name__)#, self._task)
        if self.cancelled:
            return "<Cancelled {0} {1}>".format(self.__class__.__name__, fmt)
        else:
            return "<{0} complete={1} {2}>".format(self.__class__.__name__, self.complete, fmt)

    __lt__ = lambda *_: False

    def running(self):
        """Return if the Task is executing"""
        return self._running

    def done(self):
        """Check if the task is done."""
        return self.complete

    def result(self):
        """Returns the result of the task. Will raise if the result isnt ready or an exception has been set"""
        if self._error is not None:
            raise self._error
        if not self.complete:
            raise RuntimeError("Result isn't ready!")
        return self._result

    def set_result(self, data: typing.Any):
        """Sets the result of Task"""
        if self.complete or self._error is not None:
            raise RuntimeError("Future already completed")
        self.complete = True
        self._result = data
        for fut in self._joiners:
            fut.set_result(None)

    def set_exception(self, exception: BaseException):
        """Sets the exception that will be raised when control is returned"""
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
        """Returns whether or not the task has been successfully cancelled. """
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
            self.set_exception(CancelledError("Execution of this coro has been cancelled!"))
            return True
        except StopIteration as err:
            self.set_result(err.value)
            return False
        else:
            return False

    def close(self):
        self._task.close()

    async def wait(self):
        """Wait on this future to finish (different than awaiting, which should not be done except for the original caller)"""
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
        """Get the result of the conditional. If an error was set it will be raised"""
        if self._error is not None:
            raise self._error
        if not self.complete:
            raise RuntimeError("Result isn't ready!")
        return self._callback()


class Event:
    def __init__(self):
        """An event that can be waited on until set, then can be waited for again once cleared."""
        self._value = False
        self._waiters = 0

    @coroutine
    def wait(self):
        """Wait until the event is set."""
        self._waiters += 1
        while not self._value:
            yield
        self._waiters -= 1

    def set(self):
        """Toggle the event and wake all waiters"""
        self._value = True

    @coroutine
    def clear(self):
        """Waits until waiters are woken then resets the Event."""
        while self._waiters > 0:
            yield
        self._value = False
