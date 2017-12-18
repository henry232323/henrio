import _overlapped
from _winapi import NULL, INFINITE, CloseHandle

from . import BaseLoop, Future
from .io import AsyncSocket

__all__ = ["IOCPLoop", "IOCPSocket", "IOCPInstance", "IOCPFile"]

ERROR_CONNECTION_REFUSED = 1225
ERROR_CONNECTION_ABORTED = 1236


class IOCPLoop(BaseLoop):
    def __init__(self, concurrency=INFINITE):
        super().__init__()
        self._port = _overlapped.CreateIoCompletionPort(_overlapped.INVALID_HANDLE_VALUE, NULL, 0, concurrency)
        self._current_iocp = dict()
        self._open_ports = list()

    def _poll(self):
        if self._current_iocp:
            if not self._tasks or self._queue:
                if self._timers:
                    ms = max(100, (self._timers[0][0] - self.time()) * 1000)
                else:
                    ms = 100
            else:
                ms = 100
            while True:
                status = _overlapped.GetQueuedCompletionStatus(self._port, ms)  # See if anything is ready (LIFO)
                if status is None:
                    break
                ms = 0

                err, transferred, key, address = status

                try:
                    future = self._current_iocp.pop(address)
                    if isinstance(future, AsyncSocket):
                        future._io_ready(address, transferred)
                    elif isinstance(future, Future):
                        future.set_result(transferred)
                except KeyError:
                    if key not in (0, _overlapped.INVALID_HANDLE_VALUE):
                        CloseHandle(key)  # If we get a handle that doesn't exist or got deleted: Close it
                    continue
        else:
            if self._timers:
                self.sleep(max(0, self._timers[0][0] - self.time()))

    def wrap_channel(self, wrapper, channel):
        wrapped = wrapper(channel, self)
        self._open_ports.append(channel.fileno())
        _overlapped.CreateIoCompletionPort(channel.fileno(), self._port, 0, 0)
        return wrapped

    def wrap_file(self, file) -> "IOCPFile":
        """Wrap a file in an async file API."""
        return self.wrap_channel(AsyncSocket, file)

    def wrap_socket(self, socket) -> "IOCPSocket":
        """Wrap a file in an async socket API."""
        return self.wrap_channel(AsyncSocket, socket)

    def unwrap_file(self, file):
        if file.fileno not in (0, _overlapped.INVALID_HANDLE_VALUE):
            CloseHandle(file.fileno())
        del self._current_iocp[file._overlap.overlap.address]
