import typing
from types import coroutine
from math import inf

from .futures import Future

__all__ = ["sleep", "get_loop", "unwrap_file", "create_reader", "create_writer", "remove_reader",
           "remove_writer", "spawn", "wrap_file", "wrap_socket", "current_task",
           "unwrap_socket", "postpone", "spawn_after", "gethostbyname", "wait_readable", "wait_writable",
           "sleepinf", "call_after", "schedule_after"]


@coroutine
def sleep(seconds: typing.Union[float, int]):
    if seconds == 0:
        yield
    elif seconds == inf:
        yield from sleepinf()
    else:
        yield ("sleep", seconds)


@coroutine
def sleepinf():
    try:
        while True:
            yield
    except:
        return


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
async def postpone(func, time):
    return await spawn(call_after(func, time))


@coroutine
async def spawn_after(coro, time):
    return await spawn(schedule_after(coro, time))


async def schedule_after(coro, time):
    await sleep(time)
    loop = await get_loop()
    return loop.create_task(coro)


async def call_after(func, time):
    await sleep(time)
    return func()


@coroutine
def wait_readable(socket):
    fut = Future()
    yield ("_wait_read", socket, fut)
    return (yield from fut)


@coroutine
def wait_writable(socket):
    fut = Future()
    yield ("_wait_write", socket, fut)
    return (yield from fut)


class TaskGroup:
    def __init__(self):
        self.tasks = []

    async def spawn(self, coro):
        task = await spawn(coro)
        self.tasks.append(task)

    async def join(self):
        for task in self.tasks:
            await task.wait()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.join()
        if exc_val:
            raise exc_val

    async def cancel_rest(self):
        for task in self.tasks:
            task.cancel()
