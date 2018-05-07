import warnings
import typing
from io import IOBase

__all__ = ["AbstractLoop", "AbstractProtocol", "IOBase", "BaseSocket", "BaseFile"]


class AbstractLoop:
    def time(self):
        """Get the current time for the loop, generally time.monotonic()"""
        raise NotImplementedError

    def sleep(self, time: float):
        """Sleep the system, generally time.sleep()"""
        raise NotImplementedError

    def run_forever(self):
        """Run the loop indefinitely (until there is nothing left to do)"""
        raise NotImplementedError

    def run_until_complete(self, coro: typing.Coroutine):
        """Run until the given coroutine completes"""
        raise NotImplementedError

    def close(self):
        """Close the loop, cease / pause execution"""
        raise NotImplementedError

    def create_task(self, coro: typing.Coroutine):
        """Add a new task to the queue, return the task object"""
        raise NotImplementedError

    def register_reader(self, file: typing.IO, callback: typing.Callable[..., typing.Any], *args):
        """Deprecated, use file wrappers instead"""
        warnings.warn("Call to deprecated function {}.".format(self.register_reader.__name__),
                      category=DeprecationWarning,
                      stacklevel=2)
        raise NotImplementedError

    def register_writer(self, file: typing.IO, callback, *args):
        """Deprecated, use file wrappers instead"""
        raise NotImplementedError

    def unregister_reader(self, fileobj: typing.IO):
        """Deprecated, use file wrappers instead"""
        raise NotImplementedError

    def unregister_writer(self, fileobj: typing.IO):
        """Deprecated, use file wrappers instead"""
        raise NotImplementedError

    def wrap_file(self, file: typing.IO) -> IOBase:
        """Wrap a standard sync file object with an async version."""
        raise NotImplementedError

    def wrap_socket(self, socket: typing.IO) -> IOBase:
        """Wrap a standard sync file object with an async version."""
        raise NotImplementedError

    def _poll(self):
        """Polls for I/O ready and processes anything that needs to happen with it"""
        raise NotImplementedError


class IOBase:
    file = None

    def fileno(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class BaseFile(IOBase):
    async def read(self, nbytes):
        raise NotImplementedError

    async def write(self, nbytes):
        raise NotImplementedError


class BaseSocket(IOBase):
    async def recv(self, nbytes):
        raise NotImplementedError

    async def send(self, data):
        raise NotImplementedError


class AbstractProtocol:
    async def data_received(self, data):
        raise NotImplementedError

    async def connection_lost(self, exc):
        raise NotImplementedError
