from concurrent.futures import CancelledError
from .bases import AbstractLoop, BaseFile, BaseSocket
from .loop import BaseLoop
from .awaitables import Future, Task, sleep
from .selector import SelectorLoop, SelectorFile, SelectorSocket

import sys

if sys.platform == "win32":
    from .windows import IOCPLoop, IOCPFile, IOCPSocket


def get_default_loop():
    if sys.platform == "win32":
        return IOCPLoop()
    return SelectorLoop()
