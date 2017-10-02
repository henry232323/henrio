import selectors
import typing
import socket
import time
from collections import deque

from . import Future, Task, BaseLoop, BaseSocket, BaseFile


class SelectorLoop(BaseLoop):
    """An event loop using the the OS's builtin Selector."""
    def __init__(self, selector=None):
        super().__init__()
        self.selector = selector if selector else selectors.DefaultSelector()
        self._files = dict()

    def _poll(self):
        """Poll IO using the selector"""
        if self.selector.get_map():  # Pray it doesn't block
            # We can block as long as we want if theres no tasks to process till we're done
            # We want our currently ready files
            if not self._tasks or self._queue:
                if self._timers:
                    wait = max(0.0, self._timers[0][0] - self.time())
                else:
                    wait = None
            else:
                wait = 0

            files = self.selector.select(wait)
            ready = dict()
            for file, events in files:
                if file.fd in self._readers or file.fd in self._writers:
                    if events & 1:  # If read ready
                        func, args = self._readers[file.fd]
                        self.create_task(func(*args))
                    if events & 2:  # If write ready, both will run if both are ready (events == 3)
                        func, args = self._writers[file.fd]
                        self.create_task(func(*args))
                if file.fd in self._files:
                    ready[file.fd] = events

            for fileno, file in self._files.items():
                if fileno in ready:  # Dispatch events to awaiting files
                    event = ready[fileno]
                    if event & 1:  # Same as before
                        file._read_ready(True)
                    if event & 2:  # Read while we're good to read
                        file._write_ready(True)
                else:
                    file._read_ready(False)  # If we're no longer good to read, stop it
                    file._write_ready(False)
        else:
            if not self._tasks and self._timers:  # We can sleep as long as we want if theres nothing to do
                time.sleep(max(0.0, self._timers[0][0] - self.time()))  # Don't loop if we don't need to

    def register_reader(self, fileobj, callback: typing.Callable[..., None], *args):
        """Register a reader, the given callback will be called with the given args when the file is ready to read"""
        if fileobj.fileno() in self.selector.get_map():
            if self.selector.get_key(fileobj).events == selectors.EVENT_WRITE:
                # If the item exists and is registered for just WRITE, listen for READ too
                self.selector.modify(fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE)
        else:  # If it isn't, make it just listen for read.
            self.selector.register(fileobj, selectors.EVENT_READ)
        self._readers[fileobj.fileno()] = (callback, args)  # Cache our callback, overwrites if one already exists

    def register_writer(self, fileobj, callback: typing.Callable, *args):
        """Register a writer, the given callback will be called with the given args when the file is ready to write"""
        if fileobj.fileno() in self.selector.get_map():
            if self.selector.get_key(fileobj).events == selectors.EVENT_READ:
                # If the item exists and is registered for just READ, listen for WRITE too
                self.selector.modify(fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE)
        else:  # If it isn't, make it just listen for WRITE.
            self.selector.register(fileobj, selectors.EVENT_WRITE)
        self._writers[fileobj.fileno()] = (callback, args)  # Cache our callback, overwrites if one already exists

    def unregister_reader(self, fileobj):
        """Disable and remove a reader. Returns whether or not successful"""
        if fileobj.fileno() in self.selector.get_map():  # If it exists as a WRITER and READER, make it just WRITER
            if self.selector.get_key(fileobj) == selectors.EVENT_READ ^ selectors.EVENT_WRITE:
                self.selector.modify(fileobj, selectors.EVENT_WRITE)
            else:
                self.selector.unregister(fileobj)
            del self._readers[fileobj.fileno()]
            return True
        else:
            return False

    def unregister_writer(self, fileobj):
        """Disable and remove a writer. Returns whether or not successful"""
        if fileobj.fileno() in self.selector.get_map():  # If it exists as a WRITER and READER, make it just READER
            if self.selector.get_key(fileobj) == selectors.EVENT_READ ^ selectors.EVENT_WRITE:
                self.selector.modify(fileobj, selectors.EVENT_READ)
            else:
                self.selector.unregister(fileobj)
            del self._writers[fileobj.fileno()]  # Remove from cache
            return True
        else:
            return False

    def wrap_file(self, file) -> "SelectorFile":
        """Wrap a file in an async file API."""
        wrapped = SelectorFile(file)
        self._files[file.fileno()] = wrapped  # Cache our file by file descriptor
        self.selector.register(file, selectors.EVENT_READ | selectors.EVENT_WRITE)  # Register for R/W just in case
        return wrapped

    def wrap_socket(self, socket) -> "SelectorSocket":
        """Wrap a file in an async socket API."""
        wrapped = SelectorSocket(socket)
        self._files[socket.fileno()] = wrapped  # Register just like a regular file, since no repeat fds
        self.selector.register(socket, selectors.EVENT_READ | selectors.EVENT_WRITE)  # Get our R/W
        return wrapped


class SelectorFile(BaseFile):
    """A file object wrapped with async"""
    def __init__(self, file: typing.IO[typing.AnyStr]):
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
        fut = Future()  # Just await a future that will eventually be handled when read is ready
        self._read_queue.append((fut, (0, nbytes)))  # We just delegate to the queue
        return await fut

    async def readline(self, nbytes: int=-1) -> typing.AnyStr:
        fut = Future()  # Same as above
        self._read_queue.append((fut, (1, nbytes)))
        return await fut

    async def write(self, data: typing.AnyStr):
        fut = Future()  # etc
        self._write_queue.append((fut, data))
        return await fut

    @property
    def fileno(self):
        """Get the file descriptor"""
        return self.file.fileno()

    def close(self):
        del self.loop._files[self.file.fileno()]
        self.loop.selector.unregister(self.file)
        self.file.close()


class SelectorSocket(BaseSocket):
    def __init__(self, file: socket.socket):
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