from collections import defaultdict, deque
from socket import AF_INET, SOCK_STREAM, socket, SO_REUSEADDR, SOL_SOCKET

from . import create_writer, create_reader, socket_connect, socket_bind, spawn, Future


class ConnectionBase:
    def __init__(self, socket, host, bufsize):
        self.socket = socket
        self.host = host
        self.addr, self.port = host
        self._bufsize = bufsize
        self._writequeue = deque()

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
        while self._writequeue:
            future, data = self._writequeue.popleft()
            ans = self.socket.send(data)
            future.set_result(ans)

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

    def send(self, data):
        future = Future()
        self._writequeue.append((future, data))
        return future

    def close(self):
        self.socket.close()


class ServerBase:
    def __init__(self, socket, host, bufsize):
        self.host = host
        self.address, self.port = host
        self.socket = socket
        self._bufsize = bufsize
        self._writequeue = defaultdict(deque)
        self.connections = list()

    async def _reader_callback(self):
        client, addr = self.socket.accept()
        wrapped = ServerSocket(self, client)
        self.connections.append(wrapped)
        await create_reader(wrapped, self._client_readable, wrapped)
        await create_writer(wrapped, self._client_writable, wrapped)
        await self.connection_made(wrapped)

    async def _writer_callback(self):
        while self._writequeue[self.socket]:
            future, data = self._writequeue[self.socket].popleft()
            ans = self.socket.send(data)
            future.set_result(ans)

    async def _client_writable(self, sock):
        while self._writequeue[sock]:
            future, data = self._writequeue[sock].popleft()
            ans = sock.send(data)
            future.set_result(ans)

    async def _client_readable(self, sock):
        received = sock.recv(self._bufsize)
        try:
            if received:
                await self.data_received(sock, received)
            else:
                await self.eof_received(sock)
                await self.connection_lost(sock, None)
        except OSError as e:
            sock.close()
            await self.connection_lost(sock, e)

    async def connection_made(self, socket):
        pass

    async def data_received(self, socket, data):
        pass

    async def connection_lost(self, socket, exc):
        pass

    async def eof_received(self, socket):
        pass

    def close(self):
        self.socket.close()
        del self._writequeue[self.socket]


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


async def create_server(protocol_factory, address, port, family=AF_INET,
                        type=SOCK_STREAM, proto=0, fileno=None,
                        bufsize=1024, sock=None, backlog=None):
    if sock is not None:
        if fileno is not None:
            raise ValueError("You cannot specify a fileno AND a socket!")
        bound = True
    else:
        sock = socket(family=family, type=type, proto=proto, fileno=fileno)
        bound = False

    connection = protocol_factory(socket=sock, host=(address, port), bufsize=bufsize)
    sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    await create_reader(sock, connection._reader_callback)
    await create_writer(sock, connection._writer_callback)

    if not bound:
        await socket_bind(sock, (address, port))
        sock.listen(backlog) if backlog is not None else sock.listen()

    return connection


class ServerSocket:
    def __init__(self, protocol, socket):
        self._protocol = protocol
        self._socket = socket

    def send(self, data):
        future = Future()
        self._protocol._writequeue[self].append((future, data))
        return future

    def close(self):
        self.close()
        del self._protocol._writequeue[self]

    def fileno(self):
        return self._socket.fileno()

    def recv(self, bufsize):
        return self._socket.recv(bufsize)
