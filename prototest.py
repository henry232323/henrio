from henrio import ConnectionBase, ServerBase, connect, create_server, get_default_loop


def run_client():
    class MyProto(ConnectionBase):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        async def data_received(self, data):
            print(data)

    loop = get_default_loop()
    loop.create_task(connect(MyProto, "irc.mindfang.org", 6667))
    loop.run_forever()


def run_serv():
    class MyProto(ServerBase):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        async def data_received(self, sock, data):
            print(sock, data)

        async def connection_made(self, socket):
            print(socket._socket.getpeername())

    loop = get_default_loop()
    loop.create_task(create_server(MyProto, "127.0.0.1", 8888))
    loop.run_forever()


run_serv()
