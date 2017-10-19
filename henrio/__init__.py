from .awaitables import (Future, Task, sleep, get_loop, unwrap_file, create_reader, create_writer, remove_reader,
                         remove_writer, spawn, wrap_file, wrap_socket, socket_connect, socket_bind, current_task)
from .bases import AbstractLoop, BaseFile, BaseSocket
from .loop import BaseLoop
from .protocols import ConnectionBase, connect, create_server, ServerBase, ssl_connect
from .queue import Queue
from .selector import SelectorLoop, SelectorFile, SelectorSocket
from .workers import worker, async_worker
from .locks import Lock

import concurrent.futures
CancelledError = concurrent.futures.CancelledError
del concurrent.futures

import sys

if sys.platform == "win32":
    from .windows import IOCPLoop, IOCPFile, IOCPSocket

del sys  # Not for export


def get_default_loop():
    return SelectorLoop()


def run(awaitable):
    loop = get_default_loop()
    return loop.run_until_complete(awaitable)
