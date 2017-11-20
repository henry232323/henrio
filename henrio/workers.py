from multiprocessing import Pool as ProcessPool
from multiprocessing.dummy import Pool as ThreadPool
from types import coroutine
from functools import partial

from .yields import get_loop
from .locks import Semaphore
from . import Future

__all__ = ["threadworker", "async_threadworker", "processworker", "async_processworker", "AsyncFuture"]


@coroutine
def async_worker(pooltype, func, *args, **kwargs):
    fut = Future()
    loop = yield from get_loop()

    def runner():
        coro = func(*args, **kwargs)
        l = type(loop)()
        return l.run_until_complete(coro)

    pool = get_pool(pooltype, loop)

    pool.apply_async(runner, callback=fut.set_result, error_callback=fut.set_exception)

    res = yield from fut
    return res


@coroutine
def worker(pooltype, func, *args, **kwargs):
    fut = Future()
    loop = yield from get_loop()
    pool = get_pool(pooltype, loop)
    pool.apply_async(func, args=args, kwds=kwargs, callback=fut.set_result, error_callback=fut.set_exception)
    res = yield from fut
    return res


def get_pool(pooltype, loop):
    if pooltype:
        if loop.processpool:
            pool = loop.processpool
        else:
            pool = loop.processpool = ProcessPool()
    else:
        if loop.threadpool:
            pool = loop.threadpool
        else:
            pool = loop.threadpool = ThreadPool()
    return pool


threadworker = partial(worker, 0)
processworker = partial(worker, 1)
async_threadworker = partial(async_worker, 0)
async_processworker = partial(async_worker, 1)


class AsyncFuture:
    def __init__(self, async_result):
        self._async_result = async_result

    def __iter__(self):
        while not self._async_result.ready():
            yield self
        return self._async_result.get(0)

    __await__ = __iter__

    def send(self, data):
        if not self._async_result.ready():
            return self
        return self._async_result.get(0)


class Pool:
    def __init__(self, factory, workers):
        self.waiter = Semaphore(workers)
        self.factory = factory
        self.workers = [factory() for i in range(workers)]

    def shutdown(self):
        for worker in self.workers:
            worker.shutdown()
        self.workers = []

    async def acquire(self):
        await self.waiter.acquire()
        return self.workers.pop()

    async def release(self, worker):
        await self.waiter.release()
        self.workers.append(worker)
