import concurrent.futures

CancelledError = concurrent.futures.CancelledError
del concurrent  # Not for export

from .bases import AbstractLoop, BaseFile, BaseSocket, AbstractProtocol, IOBase
from .futures import Future, Task, Conditional, Event
from .locks import Lock, ResourceLock, Semaphore
from .loop import BaseLoop
from .queue import Queue, HeapQueue, QueueWouldBlock
from .workers import threadworker, async_threadworker, processworker, async_processworker, AsyncFuture
from .yields import (sleep, get_loop, unwrap_file, spawn, wrap_file, wrap_socket, current_task, sleepinf,
                     unwrap_socket, postpone, spawn_after, wait_readable, wait_writable, call_after,
                     schedule_after, TaskGroup, get_time)
from .selector import SelectorLoop
from .io import async_connect, threaded_bind, threaded_connect, getaddrinfo, create_socketpair, AsyncSocket, \
    open_connection, aopen, AsyncFile, ssl_do_handshake, ssl_wrap_socket
from .timeout import timeout
from . import universals
from . import dns

import sys

if sys.platform == "win32":
    from .windows import IOCPLoop, IOCPFile

    getaddrinfo_ex = getattr(dns, "getaddrinfo_ex", None)

getaddrinfo_a = getattr(dns, "getattrinfo_a", None)

del sys  # Not for export

import threading

_current_loops = threading.local()
_current_loops.value = []
del threading  # Not for export


def get_default_loop():
    if _current_loops.value:
        return _current_loops.value[0]
    else:
        _current_loops.value.append(SelectorLoop())
    return get_default_loop()


def run(func, *args, **kwargs):
    loop = get_default_loop()
    return loop.run_until_complete(func(*args, **kwargs))


def run_coro(coro):
    loop = get_default_loop()
    return loop.run_until_complete(coro)


def run_forever(*awaitables):
    loop = get_default_loop()
    for awaitable in awaitables:
        loop.create_task(awaitable)
    return loop.run_forever()


try:
    from multio import _AsyncLib, manager


    def _open_connection(host, port,
                         timeout=None, *,
                         ssl=False,
                         source_addr=None,
                         server_hostname=None,
                         alpn_protocols=None):
        return open_connection((host, port),
                               timeout=timeout,
                               ssl=ssl,
                               source_addr=source_addr,
                               server_hostname=server_hostname,
                               alpn_protocols=alpn_protocols)


    def _henrio_init(lib: _AsyncLib):
        lib.aopen = aopen
        lib.open_connection = open_connection
        lib.sleep = sleep
        lib.task_manager = TaskGroup
        lib.timeout_after = timeout
        lib.sendall = AsyncSocket.sendall
        lib.recv = AsyncSocket.recv
        lib.sock_close = AsyncSocket.close
        lib.spawn = spawn

        lib.Lock = Lock
        lib.Semaphore = Semaphore
        lib.Queue = Queue
        lib.Event = Event
        lib.Cancelled = CancelledError
        lib.TaskTimeout = TimeoutError

    manager.register("henrio", _henrio_init)
    del _AsyncLib
except ImportError:
    pass
