import _overlapped
import typing
from collections import deque
import _winapi

from . import Loop, Future


NULL = 0
INFINITE = 0xffffffff
ERROR_CONNECTION_REFUSED = 1225
ERROR_CONNECTION_ABORTED = 1236

# Initial delay in seconds for connect_pipe() before retrying to connect
CONNECT_PIPE_INIT_DELAY = 0.001

# Maximum delay in seconds for connect_pipe() before retrying to connect
CONNECT_PIPE_MAX_DELAY = 0.100


class IOCPLoop(Loop):
    def __init__(self, concurrency=INFINITE):
        super().__init__()
        self._port = _overlapped.CreateIoCompletionPort(_overlapped.INVALID_HANDLE_VALUE, NULL, 0, concurrency)
        self._current_iocp = dict()

    def _poll(self):
        #ms = 1000
        ms = 100
        while True:
            status = _overlapped.GetQueuedCompletionStatus(self._port, ms)
            print(status)
            if status is None:
                break
            ms = 0

            err, transferred, key, address = status

            try:
                file = self._current_iocp.pop(address)
                file._io_ready(transferred)
            except KeyError:
                if key not in (0, _overlapped.INVALID_HANDLE_VALUE):
                    _winapi.CloseHandle(key)
                continue

    def register_reader(self, fileobj, callback: typing.Callable[..., None], *args):
        _overlapped.CreateIoCompletionPort(fileobj.fileno(), self._port, 0, 0)

    def wrap_file(self, file) -> "IOCPFile":
        """Wrap a file in an async file API."""
        overlap = _overlapped.Overlapped(NULL)
        wrapped = IOCPFile(file, overlap, loop=self)
        _overlapped.CreateIoCompletionPort(file.fileno(), self._port, 0, 0)
        self._current_iocp[overlap.address] = wrapped
        return wrapped

    def wrap_socket(self, socket) -> "IOCPSocket":
        """Wrap a file in an async socket API."""
        overlap = _overlapped.Overlapped(NULL)
        wrapped = IOCPSocket(socket, overlap, loop=self)
        _overlapped.CreateIoCompletionPort(socket.fileno(), self._port, 0, 0)
        self._current_iocp[overlap.address] = wrapped
        return wrapped


class IOCPFile:
    def __init__(self, file, overlap, loop=None):
        self.file = file
        self._loop = loop
        self._read_queue = deque()
        self._write_queue = deque()
        self._overlap = _overlapped.Overlapped(NULL)


class IOCPSocket:
    def __init__(self, socket, overlap, loop=None):
        self.file = socket
        self._loop = loop
        self._queue = deque()
        self._overlap = overlap

    def _io_ready(self, data):
        if self._queue:
            _type, fut, _data = self._queue.popleft()
            fut.set_result(data)

    def send(self, data, flags=0):
        self._overlap.WSASend(self.file.fileno(), data, flags)
        fut = Future()
        self._queue.append((0, fut, data))

        return fut

    def recv(self, nbytes, flags=0):
        self._overlap.WSARecv(self.file.fileno(), nbytes, flags)
        fut = Future()
        self._queue.append((1, fut, nbytes))

        return fut

    def cancel(self):
        self._overlap.cancel()
