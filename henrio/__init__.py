import concurrent.futures

from .bases import AbstractLoop, BaseFile, BaseSocket, AbstractProtocol, IOBase
from .futures import Future, Task, timeout
from .locks import Lock, ResourceLock
from .loop import BaseLoop
from .queue import Queue, HeapQueue
from .workers import worker, async_worker
from .yields import (sleep, get_loop, unwrap_file, create_reader, create_writer, remove_reader,
                     remove_writer, spawn, wrap_file, wrap_socket, current_task,
                     unwrap_socket, postpone, spawn_after)
from .selector import SelectorLoop, SelectorFile, SelectorSocket
from .protocols import ConnectionBase, connect, create_server, ServerBase, ssl_connect, SSLServer, create_ssl_server, \
    ServerSocket
from .io import socket_connect, socket_bind, gethostbyname, create_socketpair
from .lang import parse, execute, eval, load_hio, compile_hio, _hio_interpret_call, prep as prep_parsing

CancelledError = concurrent.futures.CancelledError
del concurrent

import sys
if sys.platform == "win32":
    from .windows import IOCPLoop, IOCPFile, IOCPSocket, IOCPInstance

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
