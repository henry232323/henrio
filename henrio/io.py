import socket
import errno
import ssl as _ssl
from types import coroutine
import typing
import os

from .workers import threadworker
from .yields import wrap_socket, unwrap_file, wait_readable, wait_writable
from .bases import BaseSocket
from . import timeout as _timeout

__all__ = ["threaded_connect", "threaded_bind", "getaddrinfo", "create_socketpair", "async_connect",
           "ssl_do_handshake", "AsyncSocket"]


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


async def open_connection(hostpair: tuple, ssl=False, timeout=None):
    if timeout is not None:
        async with _timeout(timeout):
            return await open_connection(hostpair, ssl)
    else:
        sock = socket.socket()
        if ssl:
            ssl_context = _ssl.create_default_context()
            sock = ssl_context.wrap_socket(sock)
        addr, port = hostpair
        addr = await gethostbyname(addr)
        await async_connect(sock, (addr, port))
        if ssl:
            print(sock.getpeername())
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
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if exc_val:
            raise exc_val

    @property
    def fileno(self):
        return self.file.fileno()

    def close(self):
        self.file.close()
        return unwrap_file(self)
