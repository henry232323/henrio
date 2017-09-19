from . import Future, Task, Loop

import selectors
import typing
import socket
from collections import deque


class SelectorLoop(Loop):
    """An event loop using the the OS's builtin Selector."""
    def __init__(self, selector=None):
        super().__init__()
        self.selector = selector if selector else selectors.DefaultSelector()

    def _poll(self):
        """Poll IO using the selector"""
        if self.selector.get_map():
            files = self.selector.select(0 if self._tasks or self._queue or self._timers else None)
            ready = dict()
            for file, events in files:
                if file.fd in self._readers or file.fd in self._writers:
                    if events & 1:
                        self._tasks.append(Task(self.handle_callback(*self._readers[file.fd]), None))
                    if events & 2:
                        self._tasks.append(Task(self.handle_callback(*self._writers[file.fd]), None))
                if file.fd in self._files:
                    ready[file.fd] = events

            for fileno, file in self._files.items():
                if fileno in ready:
                    event = ready[fileno]
                    if event & 1:
                        file._read_ready(True)
                    if event & 2:
                        file._write_ready(True)
                else:
                    file._read_ready(False)
                    file._write_ready(False)

    def register_reader(self, fileobj, callback: typing.Callable[..., None], *args):
        """Register a reader, the given callback will be called with the given args when the file is ready to read"""
        if fileobj.fileno() in self.selector.get_map() and self.selector.get_key(
                fileobj).events == selectors.EVENT_WRITE:
            self.selector.modify(fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE)
        else:
            self.selector.register(fileobj, selectors.EVENT_READ)
        self._readers[fileobj.fileno()] = (callback, args)

    def register_writer(self, fileobj, callback: typing.Callable, *args):
        """Register a writer, the given callback will be called with the given args when the file is ready to write"""
        if fileobj.fileno() in self.selector.get_map():
            if self.selector.get_key(fileobj).events == selectors.EVENT_READ:
                self.selector.modify(fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE)
        else:
            self.selector.register(fileobj, selectors.EVENT_WRITE)
        self._writers[fileobj.fileno()] = (callback, args)

    def unregister_reader(self, fileobj):
        """Disable and remove a reader"""
        if fileobj.fileno() in self.selector.get_map():
            if self.selector.get_key(fileobj) == selectors.EVENT_READ ^ selectors.EVENT_WRITE:
                self.selector.modify(fileobj, selectors.EVENT_WRITE)
            else:
                self.selector.unregister(fileobj)
            del self._readers[fileobj.fileno()]
            return True
        else:
            return False

    def unregister_writer(self, fileobj):
        """Disable and remove a writer"""
        if fileobj.fileno() in self.selector.get_map():
            if self.selector.get_key(fileobj) == selectors.EVENT_READ ^ selectors.EVENT_WRITE:
                self.selector.modify(fileobj, selectors.EVENT_READ)
            else:
                self.selector.unregister(fileobj)
            del self._writers[fileobj.fileno()]
            return True
        else:
            return False

    def wrap_file(self, file) -> "SelectorFile":
        """Wrap a file in an async file API."""
        wrapped = SelectorFile(file, loop=self)
        self._files[file.fileno()] = wrapped
        self.selector.register(file, selectors.EVENT_READ | selectors.EVENT_WRITE)
        return wrapped

    def wrap_socket(self, socket) -> "SelectorSocket":
        """Wrap a file in an async socket API."""
        wrapped = SelectorSocket(socket, loop=self)
        self._files[socket.fileno()] = wrapped
        self.selector.register(socket, selectors.EVENT_READ | selectors.EVENT_WRITE)
        return wrapped


class SelectorFile:
    def __init__(self, file: typing.IO[typing.AnyStr], loop=None):
        self.loop = loop
        self.file = file
        self._read_queue = deque()
        self._write_queue = deque()

    def _read_ready(self, value: bool):
        if value and self._read_queue:
            fut, (type, nbytes) = self._read_queue.popleft()
            if type == 0:
                fut.set_result(self.file.read(nbytes))
            elif type == 1:
                fut.set_result(self.file.readline(nbytes))

    def _write_ready(self, value: bool):
        if value and self._write_queue:
            fut, data = self._write_queue.popleft()
            fut.set_result(self.file.write(data))

    async def read(self, nbytes: int=-1) -> typing.AnyStr:
        fut = Future()
        self._read_queue.append((fut, (0, nbytes)))
        return await fut

    async def readline(self, nbytes: int=-1) -> typing.AnyStr:
        fut = Future()
        self._read_queue.append((fut, (1, nbytes)))
        return await fut

    async def write(self, data: typing.AnyStr):
        fut = Future()
        self._write_queue.append((fut, data))
        return await fut

    @property
    def fileno(self):
        return self.file.fileno()

    def close(self):
        del self.loop._files[self.file.fileno()]
        self.loop.selector.unregister(self.file)
        self.file.close()


class SelectorSocket:
    def __init__(self, file: socket.socket, loop=None):
        self.loop = loop
        self.file = file
        self._read_queue = deque()
        self._write_queue = deque()

    def _read_ready(self, value: bool):
        if value and self._read_queue:
            fut, nbytes = self._read_queue.popleft()
            fut.set_result(self.file.recv(nbytes))

    def _write_ready(self, value: bool):
        if value and self._write_queue:
            fut, data = self._write_queue.popleft()
            fut.set_result(self.file.send(data))

    async def recv(self, nbytes: int) -> bytes:
        fut = Future()
        self._read_queue.append((fut, nbytes))
        return await fut

    async def send(self, data: bytes):
        fut = Future()
        self._write_queue.append((fut, data))
        return await fut

    @property
    def fileno(self):
        return self.file.fileno()

    def close(self):
        del self.loop._files[self.file.fileno()]
        self.loop.selector.unregister(self.file)
        self.file.close()