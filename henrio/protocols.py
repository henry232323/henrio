from collections import defaultdict, deque
from socket import AF_INET, SOCK_STREAM, socket, SO_REUSEADDR, SOL_SOCKET

from . import create_writer, create_reader, socket_connect, socket_bind, spawn, Future, remove_writer, remove_reader, get_loop


class ConnectionBase:
    def __init__(self, socket, host, bufsize):
        self.socket = socket
        self.host = host
        self.addr, self.port = host  # Host to connect to
        self._bufsize = bufsize  # Max amount to read at a time
        self._writequeue = deque()  # Deque of (Future, message) to send

    async def _reader_callback(self):
        try:
            received = self.socket.recv(self._bufsize)  # Try to receive
            if received:  # Only fire if we received anything
                await self.data_received(received)
                return
            else:  # If we didn't we EOF'd
                await spawn(self.eof_received())
                await spawn(self.connection_lost(None))  # Subclass callback
        except OSError as e:  # Something errored trying to read
            await spawn(self.connection_lost(e))

        await self._connection_lost()  # Our callback

    async def _writer_callback(self):
        while self._writequeue:  # Write everything we can
            future, data = self._writequeue.popleft()  # FIFO
            ans = self.socket.send(data)
            future.set_result(ans)  # Length of content we sent, return barely matters just set future once its complete

    async def _connect(self):
        await socket_connect(self.socket, self.host)
        await spawn(self.connection_made())  # All callbacks are spawns, thus don't interfere with internals

    async def _connection_lost(self):
        await remove_reader(self.socket)  # Connection dropped, we don't need to listen any more
        await remove_writer(self.socket)
        self.socket.close()

    async def connection_made(self):
        pass

    async def data_received(self, data):
        pass

    async def connection_lost(self, exc):
        pass

    async def eof_received(self):
        pass

    def send(self, data):  # All we really do is add to the write queue
        future = Future()
        self._writequeue.append((future, data))
        return future  # Then wait for it to actually get sent

    async def close(self):
        await self._connection_lost()


class ServerBase:
    def __init__(self, socket, host, bufsize):
        self.host = host  # The host we're _serving_ on
        self.address, self.port = host
        self.socket = socket
        self._bufsize = bufsize  # Read buffer size
        self._writequeue = defaultdict(deque)  # We have a separate deque for every connection
        self.connections = list()  # All connected (wrapped) sockets

    async def _reader_callback(self):
        client, addr = self.socket.accept()  # If we're ready to read on a servery sock, then we're accepting
        wrapped = ServerSocket(self, client)  # Wrap in async methods
        self.connections.append(wrapped)
        await create_reader(wrapped, self._client_readable, wrapped)
        await create_writer(wrapped, self._client_writable, wrapped)
        await spawn(self.connection_made(wrapped))

    async def _client_writable(self, sock):
        while self._writequeue[sock]:  # This is all the same as `ConnectionBase` more or less
            future, data = self._writequeue[sock].popleft()
            ans = sock.send(data)
            future.set_result(ans)

    async def _client_readable(self, sock):
        error = None
        try:
            received = sock.recv(self._bufsize)
            if received:
                await self.data_received(sock, received)
                return
            else:
                await self.eof_received(sock)
        except OSError as e:
            error = e

        if sock in self.connections:  # This can get called multiple times before we actually stop reading
            await self._connection_lost(sock)  # So only do it once
            await spawn(self.connection_lost(sock, error))

    async def _connection_lost(self, sock):
        self.connections.remove(sock)
        await remove_reader(sock)
        await remove_writer(sock)
        sock.close()

    async def connection_made(self, socket):
        pass

    async def data_received(self, socket, data):
        pass

    async def connection_lost(self, socket, exc):
        pass

    async def eof_received(self, socket):
        pass

    async def close(self):
        await remove_reader(self.socket)
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

    connection = protocol_factory(socket=sock, host=(address, port), bufsize=bufsize)  # All protos need these args
    await create_reader(sock, connection._reader_callback)
    await create_writer(sock, connection._writer_callback)  # Create our reader and writer

    if not connected:
        await connection._connect()  # If the sock isn't connected, connect "asynchronously"

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

    if not bound:  # We need to bind the sock if it isn't already
        await socket_bind(sock, (address, port))
        sock.listen(backlog) if backlog is not None else sock.listen()
    # We assume we're already listening if we're using an already bound socket, maybe this needs to change?

    return connection


class ServerSocket:
    def __init__(self, protocol, socket):
        """Wraps a socket with async methods"""
        self._protocol = protocol
        self._socket = socket

    def send(self, data):  # Same send style as usual
        future = Future()
        self._protocol._writequeue[self].append((future, data))
        return future

    def close(self):
        self._socket.close()
        try:
            del self._protocol._writequeue[self]
        except:
            pass

    def fileno(self):  # These are the minimal number of methods we need to wrap realistically
        return self._socket.fileno()

    def recv(self, bufsize):
        return self._socket.recv(bufsize)
