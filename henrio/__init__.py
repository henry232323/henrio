from concurrent.futures import CancelledError
from .awaitables import Future, Task, sleep
from .loop import Loop
from .selector import SelectorLoop, SelectorFile, SelectorSocket

import sys

if sys.platform == "win32":
    from .windows import IOCPLoop, IOCPFile, IOCPSocket


