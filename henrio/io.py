import socket
import errno
import ssl as _ssl
from types import coroutine

from .workers import threadworker
from .yields import wrap_socket
from . import timeout as _timeout

__all__ = ["threaded_connect", "threaded_bind", "gethostbyname", "create_socketpair", "async_connect",
           "ssl_do_handshake"]


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


@coroutine
def async_connect(socket, hostpair):
    socket.setblocking(False)
    socket.connect_ex(hostpair)
    while True:
        try:
            socket.getpeername()
            break
        except OSError as err:
            if err.errno == errno.ENOTCONN:
                yield
            else:
                raise
        finally:
            socket.setblocking(True)


async def gethostbyname(name):
    return await threadworker(socket.gethostbyname, name)


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
            await ssl_do_handshake(sock)
        return await wrap_socket(sock)
