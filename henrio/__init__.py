all = ["get_default_loop", "run", "run_forever", "CancelledError"]
from .futures import Future, Task, timeout, __all__
all.extend(__all__)

from .yields import (sleep, get_loop, unwrap_file, create_reader, create_writer, remove_reader,
                     remove_writer, spawn, wrap_file, wrap_socket, socket_connect, socket_bind, current_task,
                     unwrap_socket, postpone, spawn_after, __all__)
all.extend(__all__)

from .bases import AbstractLoop, BaseFile, BaseSocket, AbstractProtocol, IOBase, __all__
all.extend(__all__)
from .locks import Lock, ResourceLock, __all__
all.extend(__all__)
from .loop import BaseLoop, __all__
all.extend(__all__)
from .protocols import ConnectionBase, connect, create_server, ServerBase, ssl_connect, SSLServer, create_ssl_server, \
    ServerSocket, __all__
all.extend(__all__)
from .queue import Queue, __all__
all.extend(__all__)
from .selector import SelectorLoop, SelectorFile, SelectorSocket, __all__
all.extend(__all__)
from .workers import worker, async_worker, __all__
all.extend(__all__)

import concurrent.futures
CancelledError = concurrent.futures.CancelledError
del concurrent

import sys
if sys.platform == "win32":
    from .windows import IOCPLoop, IOCPFile, IOCPSocket, IOCPInstance, __all__
    all.extend(__all__)

del sys  # Not for export


def get_default_loop():
    return SelectorLoop()


def run(awaitable):
    loop = get_default_loop()
    return loop.run_until_complete(awaitable)


def run_forever(*awaitables):
    loop = get_default_loop()
    for awaitable in awaitables:
        loop.create_task(awaitable)
    return loop.run_forever()


__all__ = all
del all
