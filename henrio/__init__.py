from concurrent.futures import CancelledError
from .bases import AbstractLoop, BaseFile, BaseSocket
from .loop import BaseLoop
from .awaitables import Future, Task, sleep
from .selector import SelectorLoop, SelectorFile, SelectorSocket
from .queue import Queue
from .workers import worker, async_worker

import sys

if sys.platform == "win32":
    from .windows import IOCPLoop, IOCPFile, IOCPSocket


def get_default_loop():
    return SelectorLoop()
