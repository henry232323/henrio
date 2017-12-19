import selectors
import socket
from collections import deque

from . import BaseLoop
from .io import AsyncSocket

__all__ = ["SelectorLoop"]


class SelectorLoop(BaseLoop):
    """An event loop using the the OS's builtin Selector."""

    def __init__(self, selector=None):
        super().__init__()
        self.selector = selector if selector else selectors.DefaultSelector()

    def _poll(self):
        """Poll IO using the selector"""
        map = self.selector.get_map()  # Pray it doesn't block
        l = []
        for key in map.values():
            if key.fileobj.fileno() == -1:
                l.append(key)

        for item in l:
            self.selector.unregister(item.fileobj)

        if map:
            # We can block as long as we want if theres no tasks to process till we're done
            # We want our currently ready files
            if not (self._tasks or self._queue):
                if self._timers:
                    if not self._timers[0][0].cancelled and not self._timers[0][0].complete:
                        wait = max(0.0, self._timers[0][1] - self.time())
                    else:
                        wait = 0.0
                else:
                    wait = None
            else:
                wait = 0

            files = self.selector.select(wait)
            for file, events in files:
                if events & selectors.EVENT_READ == selectors.EVENT_READ:
                    queue = map[file.fileobj].data[0]
                    if queue:
                        queue.popleft().set_result(None)
                if events & selectors.EVENT_WRITE == selectors.EVENT_WRITE:
                    queue = map[file.fileobj].data[1]
                    if queue:
                        queue.popleft().set_result(None)

        else:
            if not self._tasks and self._timers:  # We can sleep as long as we want if theres nothing to do
                if not self._timers[0][0].cancelled and self._timers[0][0].complete:
                    self.sleep(max(0.0, self._timers[0][1] - self.time()))  # Don't loop if we don't need to

        return map

    def wrap_socket(self, socket: socket.socket) -> "SelectorSocket":
        """Wrap a file in an async socket API."""
        wrapped = AsyncSocket(socket)
        self.selector.register(socket, selectors.EVENT_READ | selectors.EVENT_WRITE,
                               data=(deque(), deque()))  # Get our R/W
        return wrapped

    def unwrap_socket(self, file):
        key = self.selector.get_key(file)
        for fut in key.data[0]:
            fut.cancel()

        for fut in key.data[1]:
            fut.cancel()

        self.selector.unregister(file)

    unwrap_file = unwrap_socket

    def _wait_read(self, file, fut):
        self.selector.get_key(file.fileno()).data[0].append(fut)

    def _wait_write(self, file, fut):
        self.selector.get_key(file.fileno()).data[1].append(fut)
