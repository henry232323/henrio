from threading import Thread

from . import Future, SelectorLoop


def worker(func, *args):
    fut = Future()
    runner = lambda: fut.set_result(func(*args))
    thread = Thread(target=runner)
    thread.start()
    return fut


def async_worker(func, *args):
    fut = Future()
    def runner():
        coro = func(*args)
        l = SelectorLoop()
        try:
            fut.set_result(l.run_until_complete(coro))
        except Exception as e:
            fut.set_exception(e)
    thread = Thread(target=runner)
    thread.start()
    return fut