from socket import AF_INET, SOCK_STREAM, socket

from . import create_writer, create_reader, socket_connect, spawn


class ConnectionBase:
    def __init__(self, socket, host, bufsize):
        self.socket = socket
        self.host = host
        self.addr, self.port = host
        self._bufsize = bufsize
        self._writebuffer = bytes()

    async def _reader_callback(self):
        received = self.socket.recv(self._bufsize)
        try:
            if received:
                await self.data_received(received)
            else:
                await self.eof_received()
                await self.connection_lost(None)
        except OSError as e:
            self.close()
            await self.connection_lost(e)

    async def _writer_callback(self):
        self._writebuffer, data = bytes(), self._writebuffer
        self.socket.send(data)

    async def _connect(self):
        await socket_connect(self.socket, self.host)
        await spawn(self.connection_made())

    async def connection_made(self):
        pass

    async def data_received(self, data):
        pass

    async def connection_lost(self, exc):
        pass

    async def eof_received(self):
        pass

    def close(self):
        self.socket.close()


async def connect(protocol_factory, address=None, port=None, family=AF_INET,
                  type=SOCK_STREAM, proto=0, fileno=None,
                  bufsize=1024, sock=None):
    if sock is not None:
        if fileno is not None:
            raise ValueError("You cannot specify a fileno AND a socket!")
        try:
            sock.getpeername()
            connected = False
        # We want to check if the sock is connected already
        except OSError:  # It'll raise an OSError if we try to getpeername of an unconnected sock
            if address is not None or port is not None:
                raise ValueError("You cannot specify both an address/port AND a connected socket!") from None
            connected = True
    else:
        sock = socket(family=family, type=type, proto=proto, fileno=fileno)
        connected = False

    connection = protocol_factory(socket=sock, host=(address, port), bufsize=bufsize)
    await create_reader(sock, connection._reader_callback)
    await create_writer(sock, connection._writer_callback)

    if not connected:
        await connection._connect()

    return connection
