import typing
from types import coroutine
from math import inf

from .futures import Future

__all__ = ["sleep", "get_loop", "unwrap_file", "spawn", "wrap_file", "wrap_socket", "current_task",
           "unwrap_socket", "postpone", "spawn_after", "wait_readable", "wait_writable",
           "sleepinf", "call_after", "schedule_after", "get_time"]


@coroutine
def sleep(seconds: typing.Union[float, int]):
    """Sleep a specified number of seconds. Pass `math.inf` for an endless sleep that returns when cancelled or thrown
    Pass 0 for an inline yield (allow the loop to process once)"""
    if seconds == 0:
        yield
    elif seconds == inf:
        yield from sleepinf()
    else:
        yield ("sleep", seconds)


@coroutine
def sleepinf():
    """Sleep forever, returns when an error is raised (Cancelling or manual throwing)"""
    try:
        while True:
            yield
    except:
        return


@coroutine
def get_loop():
    """Get the loop object that is executing the coroutine"""
    loop = yield ("loop",)
    return loop


@coroutine
def get_time():
    """Get the current loop internal time, good for measuring waits and timeouts."""
    loop = yield ("time",)
    return loop


@coroutine
def create_reader(fileobj, callback, *args):
    """Outdated."""
    yield ("register_reader", fileobj, callback, *args)


@coroutine
def create_writer(fileobj, callback, *args):
    """Outdated."""
    yield ("register_writer", fileobj, callback, *args)


@coroutine
def remove_writer(fileobj):
    """Outdated."""
    yield ("unregister_writer", fileobj)


@coroutine
def remove_reader(fileobj):
    """Outdated."""
    yield ("unregister_reader", fileobj)


@coroutine
def spawn(awaitable):
    """Start running a coroutine asynchronously. Returns the associated task."""
    return (yield ("create_task", awaitable))


@coroutine
def wrap_file(file):
    """Wrap a file/socket with the loop's file type. i.e. SelectorFile / IOCPFile depending on the loop."""
    wrapped = yield ("wrap_file", file)
    return wrapped


wrap_socket = wrap_file


@coroutine
def unwrap_file(file):
    """Unregisters the file/socket with the loop. Generally for when closing a file that has been wrapped."""
    yield ("unwrap_file", file)


unwrap_socket = unwrap_file


@coroutine
def current_task():
    """Get the task that is currently being executed."""
    return (yield ("current_task",))


@coroutine
async def postpone(func, time):
    """Spawns a function (not coroutine) after a certain amount of time. Returns the associated task"""
    return await spawn(call_after(func, time))


@coroutine
async def spawn_after(coro, time):
    """Spawns a coroutine after a given amount of time."""
    return await spawn(schedule_after(coro, time))


async def schedule_after(coro, time):
    """Schedule a coroutine to execute after a given amount of time"""
    await sleep(time)
    loop = await get_loop()
    return loop.create_task(coro)


async def call_after(func, time):
    """Call a function after the given amount of time"""
    await sleep(time)
    return func()


@coroutine
def wait_readable(socket):
    """Wait until a socket is readable"""
    fut = Future()
    yield ("_wait_read", socket, fut)
    return (yield from fut)


@coroutine
def wait_writable(socket):
    """Wait until a socket is writable"""
    fut = Future()
    yield ("_wait_write", socket, fut)
    return (yield from fut)


class TaskGroup:
    def __init__(self):
        """A group of tasks. Akin to curio's TaskGroup (necessary for multio)"""
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
