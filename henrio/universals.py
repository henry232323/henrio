"""
These are all the functions and classes that will work perfectly fine outside of henrio. Each of these *should*
work with other libraries like asyncio or curio or trio (or really any other async library that uses a standard
method of operation)
"""

from . import Future, Task, Conditional
from . import Queue, HeapQueue
from . import sleepinf

from types import coroutine
import typing
from math import inf
from time import monotonic

__all__ = ["Future", "Task", "Conditional", "Queue", "HeapQueue", "sleepinf", "sleep"]


@coroutine
def sleep(seconds: typing.Union[float, int]):
    """Sleep for a specified amount of time. Will work with any library."""
    if seconds == 0:
        yield
    elif seconds == inf:
        yield from sleepinf()
    else:
        end = monotonic() + seconds
        while end >= monotonic():
            yield
