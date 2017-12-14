import socket

from .workers import threadworker

__all__ = ["socket_connect", "socket_bind", "gethostbyname", "create_socketpair"]


async def socket_connect(socket, hostpair):
    socket.setblocking(True)
    await threadworker(socket.connect, hostpair)


async def socket_bind(socket, hostpair):
    socket.setblocking(False)
    try:
        resp = socket.bind(hostpair)
        socket.setblocking(True)
        return resp
    except BlockingIOError:
        socket.setblocking(True)
        return await threadworker(socket.bind, hostpair)


async def gethostbyname(name):
    return await threadworker(socket.gethostbyname, name)


async def create_socketpair(*args, **kwargs):
    reader, writer = socket.socketpair(*args, **kwargs)
    rr, rw = await create_socketpair(reader), await create_socketpair(writer)
    return rr, rw
