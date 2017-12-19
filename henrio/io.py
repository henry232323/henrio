import socket
import errno
from types import coroutine
import typing
import os
from concurrent.futures import CancelledError

from .workers import threadworker
from .yields import wrap_socket, unwrap_file, wait_readable, wait_writable
from .bases import BaseSocket
from . import timeout as _timeout

try:
    import ssl as _ssl
    from ssl import SSLWantReadError, SSLWantWriteError

    WantRead = (BlockingIOError, InterruptedError, SSLWantReadError)
    WantWrite = (BlockingIOError, InterruptedError, SSLWantWriteError)
except ImportError:  # Borrowed from curio https://github.com/dabeaz/curio/blob/master/curio/io.py
    _ssl = None
    WantRead = (BlockingIOError, InterruptedError)
    WantWrite = (BlockingIOError, InterruptedError)

__all__ = ["threaded_connect", "threaded_bind", "getaddrinfo", "create_socketpair", "async_connect",
           "ssl_do_handshake", "AsyncSocket", "aopen", "AsyncFile", "open_connection"]


async def threaded_connect(socket, hostpair):
    socket.setblocking(True)
    await threadworker(socket.connect, hostpair)


async def threaded_bind(socket, hostpair):
    socket.setblocking(False)
    try:
        resp = socket.bind(hostpair)
        socket.setblocking(True)
        return resp
    except BlockingIOError:
        socket.setblocking(True)
        return await threadworker(socket.bind, hostpair)


yerrlist = [
    "EINPROGRESS",
    "WSAEINPROGRESS",
    "EWOULDBLOCK",
    "WSAEWOULDBLOCK",
    "EINVAL",
    "WSAEINVAL",
]
yerrors = {getattr(errno, name) for name in yerrlist if hasattr(errno, name)}


@coroutine
def _async_connect(sock, host):
    addr, port = host
    addr = (yield from getaddrinfo(addr, port))[0][-1][0]
    sock.setblocking(False)
    while True:
        err = sock.connect_ex((addr, port))
        if err in yerrors:
            yield
        elif err in (getattr(errno, "EISCONN"), getattr(errno, "WSAEISCONN")):
            break
        else:
            raise OSError(err, os.strerror(err))


async def async_connect(sock, host, timeout=None):
    if timeout is not None:
        async with _timeout(timeout):
            return await _async_connect(sock, host)
    return await _async_connect(sock, host)


async def getaddrinfo(name, port):
    return await threadworker(socket.getaddrinfo, name, port)


async def create_socketpair(*args, **kwargs):
    reader, writer = socket.socketpair(*args, **kwargs)
    rr, rw = await wrap_socket(reader), await wrap_socket(writer)
    return rr, rw


@coroutine
def ssl_do_handshake(socket, *args, **kwargs):
    while True:
        try:
            return socket.do_handshake()
        except (_ssl.SSLWantReadError, _ssl.SSLWantWriteError):
            yield


async def open_connection(hostpair: tuple, timeout=None, *,
                          ssl=False,
                          source_addr=None,
                          server_hostname=None,
                          alpn_protocols=None):
    if timeout is not None:
        async with _timeout(timeout):
            open_connection(hostpair, timeout, ssl=ssl, source_addr=source_addr, server_hostname=server_hostname,
                            alpn_protocols=alpn_protocols)
        return

    sock = socket.socket()
    if source_addr:
        await threaded_bind(sock, source_addr)
    addr, port = hostpair
    addr = (await getaddrinfo(addr, port))[0][-1][0]
    await async_connect(sock, (addr, port))

    if ssl and _ssl is None:
        raise RuntimeError("The SSL Module is missing! SSL connections cannot be made without it!")

    if ssl:
        if not isinstance(ssl, bool):
            ssl_context = ssl
        else:
            ssl_context = _ssl.create_default_context()
            if not server_hostname:
                ssl_context.check_hostname = False

            if alpn_protocols:
                ssl_context.set_alpn_protocols(alpn_protocols)

        sock = ssl_context.wrap_socket(sock, server_hostname=server_hostname, do_handshake_on_connect=False)

    if ssl:
        await ssl_do_handshake(sock)

    return await wrap_socket(sock)


class AsyncSocket(BaseSocket):
    def __init__(self, file: socket.socket):
        self.file = file

    async def recv(self, nbytes: int) -> bytes:
        await wait_readable(self.file)
        return self.file.recv(nbytes)

    async def read(self, nbytes: int):
        await wait_readable(self.file)
        return self.file.read(nbytes)

    async def send(self, data: bytes):
        await wait_writable(self.file)
        return self.file.send(data)

    async def sendall(self, data, flags=0):
        """Borrowed from curio https://github.com/dabeaz/curio/blob/master/curio/io.py"""
        buffer = memoryview(data).cast('b')
        total_sent = 0
        try:
            while buffer:
                try:
                    await wait_writable(self.file)
                    nsent = self.file.send(buffer, flags)
                    total_sent += nsent
                    buffer = buffer[nsent:]
                except WantWrite:
                    await wait_writable(self.file)
                except WantRead:  # pragma: no cover
                    await wait_readable(self.file)
        except CancelledError as e:
            e.bytes_sent = total_sent
            raise

    async def write(self, data: typing.Union[bytes, str]):
        await wait_writable(self.file)
        return self.file.write(data)

    async def sendto(self, data: bytes, address: tuple):
        await wait_writable(self.file)
        return self.file.sendto(data, address)

    async def accept(self):
        await wait_readable(self.file)
        sock, addr = self.accept()
        return AsyncSocket(sock), addr

    async def connect(self, hostpair):
        await async_connect(self.file, hostpair)

    async def bind(self, hostpair):
        await threaded_bind(self.file, hostpair)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if exc_val:
            raise exc_val

    @property
    def fileno(self):
        return self.file.fileno()

    async def close(self):
        await threadworker(self.file.close)
        return unwrap_file(self)


class AsyncFile(BaseSocket):
    def __init__(self, file, mode='r', *args, **kwargs):
        self.file = open(file, mode=mode, *args, **kwargs)

    @coroutine
    def read(self, *args, **kwargs):
        return threadworker(self.file.read, *args, **kwargs)

    @coroutine
    def readline(self, *args, **kwargs):
        return threadworker(self.file.readlines, *args, **kwargs)

    @coroutine
    def write(self, *args, **kwargs):
        return threadworker(self.file.writelines, *args, **kwargs)

    @coroutine
    def writelines(self, *args, **kwargs):
        return threadworker(self.file.writelines, *args, **kwargs)

    @coroutine
    def close(self):
        return threadworker(self.file.close)

    @coroutine
    def flush(self):
        return threadworker(self.file.flush)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        if exc_val:
            raise exc_val


aopen = AsyncFile
