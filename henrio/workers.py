from threading import Thread
from types import coroutine

from . import Future, get_loop


@coroutine
def worker(func, *args):
    fut = Future()

    def runner():
        try:
            fut.set_result(func(*args))
        except Exception as e:
            fut.set_exception(e)

    thread = Thread(target=runner)
    thread.start()
    result = yield from fut
    return result


@coroutine
def async_worker(func, *args):
    fut = Future()
    loop = yield from get_loop()

    def runner():
        coro = func(*args)
        l = type(loop)()
        try:
            fut.set_result(l.run_until_complete(coro))
        except Exception as e:
            fut.set_exception(e)

    thread = Thread(target=runner)
    thread.start()
    result = yield from fut
    return result
