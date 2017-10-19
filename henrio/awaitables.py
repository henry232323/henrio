import typing
from concurrent.futures import CancelledError
from types import coroutine


@coroutine
def sleep(seconds: typing.Union[float, int]):
    if seconds == 0:
        yield
    else:
        yield ("sleep", seconds)


@coroutine
def get_loop():
    loop = yield ("loop",)
    return loop


@coroutine
def create_reader(fileobj, callback, *args):
    yield ("register_reader", fileobj, callback, *args)


@coroutine
def create_writer(fileobj, callback, *args):
    yield ("register_writer", fileobj, callback, *args)


@coroutine
def remove_writer(fileobj):
    yield ("unregister_writer", fileobj)


@coroutine
def remove_reader(fileobj):
    yield ("unregister_reader", fileobj)


@coroutine
def spawn(awaitable):
    task = yield ("create_task", awaitable)
    return task


@coroutine
def wrap_file(file):
    wrapped = yield ("wrap_file", file)
    return wrapped


@coroutine
def wrap_socket(socket):
    wrapped = yield ("wrap_socket", socket)
    return wrapped


@coroutine
def unwrap_file(file):
    yield ("unwrap_file", file)


unwrap_socket = unwrap_file


@coroutine
def socket_connect(socket, hostpair):
    return (yield ("socket_connect", socket, hostpair))


@coroutine
def socket_bind(socket, hostpair):
    return (yield ("socket_bind", socket, hostpair))


@coroutine
def current_task():
    return (yield ("current_task",))


class Future:
    def __init__(self):
        self.__name__ = __class__.__name__
        self._data = None
        self._result = None
        self._error = None
        self.complete = False
        self.cancelled = False
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
        self.__name__ = self._task.__name__

    def __repr__(self):
        fmt = "{0} {1} {2} {3}".format(self._result if self._data is not self else "self",
                                       self._error,
                                       self._data if self._data is not self else "self",
                                       self.__name__)
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

    def cancel(self):
        if self.cancelled:
            return True
        if self.complete:
            return False
        if self.running:
            return False
        try:
            self.throw(CancelledError)
        except CancelledError as err:
            self.cancelled = True
            self.set_exception(err)
