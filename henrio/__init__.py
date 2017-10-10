from concurrent.futures import CancelledError
from .awaitables import (Future, Task, sleep, get_loop, unwrap_file,
                         create_reader, create_writer, remove_reader,
                         remove_writer, spawn, wrap_file, wrap_socket)
from .bases import AbstractLoop, BaseFile, BaseSocket
from .loop import BaseLoop
from .queue import Queue
from .selector import SelectorLoop, SelectorFile, SelectorSocket
from .workers import worker, async_worker

import sys

if sys.platform == "win32":
    from .windows import IOCPLoop, IOCPFile, IOCPSocket

del sys  # Not for export


def get_default_loop():
    return SelectorLoop()


def run(awaitable):
    loop = get_default_loop()
    return loop.run_until_complete(awaitable)
