import _overlapped
from _winapi import NULL, INFINITE, CloseHandle
from types import coroutine

from . import BaseLoop, Future, BaseFile, BaseSocket

__all__ = ["IOCPLoop", "IOCPFile"]

ERROR_CONNECTION_REFUSED = 1225
ERROR_CONNECTION_ABORTED = 1236


class IOCPLoop(BaseLoop):
    def __init__(self, concurrency=INFINITE):
        """An event loop that runs using Windows IOCP instead of the default Selector"""
        super().__init__()
        self._port = _overlapped.CreateIoCompletionPort(_overlapped.INVALID_HANDLE_VALUE, NULL, 0, concurrency)
        self._current_iocp = dict()  # Registered IOCPs
        self._open_ports = list()

    def _poll(self):
        if self._current_iocp:
            if not self._tasks or self._queue:
                if self._timers:
                    ms = max(10, (self._timers[0][0] - self.time()) * 1000)
                else:
                    ms = 10  # Need a 100ms minimum timeout probably, this can be changed
            else:
                ms = 10
            while True:
                status = _overlapped.GetQueuedCompletionStatus(self._port, ms)  # See if anything is ready (LIFO)
                if status is None:  # While we have things to process, keep going
                    break
                ms = 0

                err, transferred, key, address = status

                try:
                    future = self._current_iocp.pop(address)
                    future.set_result(transferred)
                except KeyError:
                    if key not in (0, _overlapped.INVALID_HANDLE_VALUE):
                        CloseHandle(key)  # If we get a handle that doesn't exist or got deleted: Close it
                    continue
        else:
            if self._timers:
                self.sleep(max(0, self._timers[0][0] - self.time()))

    def wrap_socket(self, file):
        wrapped = IOCPFile(file)
        self._open_ports.append(file.fileno())
        _overlapped.CreateIoCompletionPort(file.fileno(), self._port, 0, 0)
        return wrapped

    wrap_file = wrap_socket

    def unwrap_file(self, file):
        if file.fileno not in (0, _overlapped.INVALID_HANDLE_VALUE):
            CloseHandle(file.fileno())
        del self._current_iocp[file._overlap.overlap.address]

    def _write_data(self, file, type, fut, data, flags=0):
        ov = _overlapped.Overlapped(NULL)
        if type:
            args = ()
            meth = ov.WriteFile
        else:
            args = (flags,)
            meth = ov.WSASend
        meth(file.fileno(), data, *args)
        self._current_iocp[ov.address] = fut

    def _read_data(self, file, type, fut, nbytes, flags=0):
        ov = _overlapped.Overlapped(NULL)
        if type:
            args = ()
            meth = ov.ReadFile
        else:
            args = (flags,)
            meth = ov.WSARecv
        meth(file.fileno(), nbytes, *args)
        self._current_iocp[ov.address] = fut


class IOCPFile(BaseFile, BaseSocket):
    def __init__(self, file):
        """A class wrapping file-likes. Uses IOCP to wait for events and registers the file descriptor with the loop"""
        self.file = file

    @coroutine
    def write(self, data, flags=0):
        fut = Future()
        yield ("_write_data", self.file, 1, fut, data)
        return (yield from fut)

    @coroutine
    def read(self, nbytes, flags=0):
        fut = Future()
        yield ("_read_data", self.file, 1, fut, nbytes)
        return (yield from fut)

    @coroutine
    def send(self, data, flags=0):
        fut = Future()
        yield ("_write_data", self.file, 0, fut, data)
        return (yield from fut)

    @coroutine
    def recv(self, nbytes, flags=0):
        fut = Future()
        yield ("_read_data", self.file, 0, fut, nbytes)
        return (yield from fut)

    def fileno(self):
        return self.file.fileno()

    def close(self):
        """Unregister the file descriptor with the loop and close the file."""
        try:
            # self._overlap.cancel()
            if self.file.fileno not in (0, _overlapped.INVALID_HANDLE_VALUE):
                CloseHandle(self.file.fileno())
        finally:
            self.file.close()
