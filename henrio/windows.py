import _overlapped
from _winapi import NULL, INFINITE, CloseHandle
from collections import deque

from . import BaseLoop, Future, BaseFile, BaseSocket

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
                    if isinstance(future, IOCPInstance):
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
        return self.wrap_channel(IOCPFile, file)

    def wrap_socket(self, socket) -> "IOCPSocket":
        """Wrap a file in an async socket API."""
        return self.wrap_channel(IOCPSocket, socket)

    def unwrap_file(self, file):
        if file.fileno not in (0, _overlapped.INVALID_HANDLE_VALUE):
            CloseHandle(file.fileno())
        del self._current_iocp[file._overlap.overlap.address]

    """
    def register_reader(self, file, callback, *args):
        if file.fileno() not in self._open_ports:
            _overlapped.CreateIoCompletionPort(file.fileno(), self._port, 0, 0)
            self._open_ports.append(file.fileno())
        self._readers[file.fileno()] = callback
        self.create_task(self.reader_read(file, callback, args))

    async def reader_read(self, file, callback, args):
        while not file.fileno() == -1 and file.fileno() in self._readers:
            ov = _overlapped.Overlapped(NULL)
            if hasattr(file, "recv"):
                ov.WSARecv(file.fileno(), 1024, 0)
            else:
                ov.ReadFile(file.fileno(), 1024)
            fut = Future()
            self._current_iocp[ov.address] = fut
            await fut
            self.create_task(callback(*args))

    def unregister_reader(self, fileobj):
        if fileobj.fileno() != -1:
            del self._readers[fileobj.fileno()]
    """


class IOCPInstance:
    def __init__(self, file, loop):
        self.file = file
        self._readqueue = deque()
        self._writequeue = deque()
        self._loop = loop
        self._queue = dict()

    def _io_ready(self, key, data):  # When we're ready to process IO
        _type, fut, _data = self._queue.pop(key)
        fut.set_result(data)

    def close(self):
        try:
            # self._overlap.cancel()
            if self.file.fileno not in (0, _overlapped.INVALID_HANDLE_VALUE):
                CloseHandle(self.file.fileno())
        finally:
            self.file.close()

    @property
    def fileno(self):
        return self.file.fileno()


class IOCPFile(BaseFile, IOCPInstance):
    def write(self, data):
        ov = _overlapped.Overlapped(NULL)
        ov.WriteFile(self.file.fileno(), data)  # Write our file data
        fut = Future()
        self._queue[ov.address] = (0, fut, data)
        self._loop._current_iocp[ov.address] = self
        return fut

    async def read(self, nbytes):  # Read from file
        ov = _overlapped.Overlapped(NULL)
        ov.ReadFile(self.file.fileno(), nbytes)
        fut = Future()
        self._queue[ov.address] = (0, fut, nbytes)
        self._loop._current_iocp[ov.address] = self
        await fut  # Ok this one is weird, we actually wait to be told we can read, rather than delegating the reading
        return self.file.read(nbytes)  # Like we do with writing


class IOCPSocket(BaseSocket, IOCPInstance):  # Its literally all the same, except send and recv not write and read
    def send(self, data, flags=0):
        ov = _overlapped.Overlapped(NULL)
        ov.WSASend(self.file.fileno(), data, flags)
        fut = Future()
        self._queue[ov.address] = (0, fut, data)
        self._loop._current_iocp[ov.address] = self
        return fut

    async def recv(self, nbytes, flags=0):
        ov = _overlapped.Overlapped(NULL)
        ov.WSARecv(self.file.fileno(), nbytes, flags)
        fut = Future()
        self._queue[ov.address] = (1, fut, nbytes)
        self._loop._current_iocp[ov.address] = self
        await fut
        return self.file.recv(nbytes)
