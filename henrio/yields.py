import typing
from types import coroutine

__all__ = ["sleep", "get_loop", "unwrap_file", "create_reader", "create_writer", "remove_reader",
           "remove_writer", "spawn", "wrap_file", "wrap_socket", "current_task",
           "unwrap_socket", "postpone", "spawn_after", "gethostbyname"]


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
    return (yield ("create_task", awaitable))


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
