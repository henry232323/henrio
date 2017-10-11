from henrio import ConnectionBase, connect, get_default_loop


class MyProto(ConnectionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def data_received(self, data):
        print(data)

loop = get_default_loop()
loop.create_task(connect(MyProto, "irc.mindfang.org", 6667))
loop.run_forever()
