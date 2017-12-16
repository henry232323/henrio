import socket
import errno

from .workers import threadworker

__all__ = ["threaded_connect", "threaded_bing", "gethostbyname", "create_socketpair", "async_connect"]


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


async def async_connect(socket, hostpair):
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

    socket.setblocking(True)


async def gethostbyname(name):
    return await threadworker(socket.gethostbyname, name)


async def create_socketpair(*args, **kwargs):
    reader, writer = socket.socketpair(*args, **kwargs)
    rr, rw = await create_socketpair(reader), await create_socketpair(writer)
    return rr, rw
