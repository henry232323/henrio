import typing
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


@coroutine
def postpone(func, time):
    loop = yield from get_loop()
    loop.create_task(loop.call_after(func, time))


@coroutine
def spawn_after(coro, time):
    loop = yield from get_loop()
    loop.create_task(loop.schedule_after(coro, time))
