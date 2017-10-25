"""
Ignore this file, this is some test usages
"""

from henrio import *


async def sleeper(tim):
    a = await sleep(tim)
    print(a)
    return "Bon hommie"


async def sleeperator():
    return await sleeper(4)


async def duo():
    await sleeperator()


async def raser():
    raise IndexError("Oh no")


def run_readers():
    import socket
    loop = SelectorLoop()
    my_socket = socket.socket()
    my_socket.connect(("irc.mindfang.org", 1413))
    buffer = bytearray()

    async def reader():
        nonlocal buffer
        received = my_socket.recv(1024)
        if received:
            buffer.extend(received)
            pts = bytes(buffer).split(b"\r\n")
            buffer = pts.pop()
            for el in pts:
                print(el)
        else:
            loop.unregister_reader(my_socket)
            my_socket.close()

    loop.register_reader(my_socket, reader)
    loop.run_forever()


def run_stdreaders():
    import sys
    loop = IOCPLoop()
    file = sys.stdin
    print(file.fileno())
    wrapped = loop.wrap_file(file)

    async def do_thing():
        print(await wrapped.read(1024))

    loop.create_task(do_thing())
    loop.run_forever()


def run_files():
    loop = IOCPLoop()
    file = open("LICENSE", 'rb')
    print(file.fileno())
    wrapped = loop.wrap_file(file)

    async def do_thing():
        print(await wrapped.read(1024))

    loop.create_task(do_thing())
    loop.run_forever()


def run_socks():
    import socket
    loop = IOCPLoop()
    r, w = socket.socketpair()

    # w.send(b"Elle me dit ecris un chanson")
    async def do_thing():
        reader, writer = await wrap_socket(r), await wrap_socket(w)
        await writer.send(b"abcdefg")
        print(b'asd')
        await writer.send(b"dsa")
        print(b'dsa')
        f = await reader.recv(12)
        print(f, 1)
        await writer.send(b"1234")
        d = await reader.recv(1024)
        print(d, 2)

    loop.create_task(do_thing())
    loop.run_forever()


def run_socks2():
    import socket
    loop = IOCPLoop()
    rw = socket.socket()
    rw.connect(("irc.mindfang.org", 6667))

    # w.send(b"Elle me dit ecris un chanson")
    async def do_thing():
        sock = await wrap_socket(rw)
        await sock.send(b"abcdefg")
        print(b'asd')
        await sock.send(b"dsa")
        print(b'dsa')
        f = await sock.recv(1024)
        print(f, 1)
        await sock.send(b"1234")
        print(12321)
        d = await sock.recv(15)
        print(d, 2)

    loop.create_task(do_thing())
    loop.run_forever()


def run_stdio():
    import sys
    loop = SelectorLoop()
    reader, writer = loop.wrap_file(sys.stdin), loop.wrap_file(sys.stdout)
    loop.create_task(writer.write("asd"))
    resp = loop.run_until_complete(reader.read(10))
    print(resp)


def run_thing():
    l = BaseLoop()
    d = Future()

    async def s():
        await sleep(10)
        d.set_result(32)

    async def g():
        return await d

    print(l.run_until_complete(g()))


def bier():
    def asd():
        yield from sleep(4)
        yield
        print("dun")

    l = BaseLoop()
    l.run_until_complete(asd())


def working():
    async def asd():
        def b():
            import time
            a = time.monotonic()
            time.sleep(4)
            print(time.monotonic() - a)
            return 3

        d = await worker(b)
        print(d)

    l = BaseLoop()
    l.run_until_complete(asd())


def async_working():
    l = SelectorLoop()
    import socket
    r, w = socket.socketpair()
    reader, writer = l.wrap_socket(r), l.wrap_socket(w)

    async def do_thing():
        print('asd')
        await writer.send(b"Fuckeroni!")
        print("dsa")
        f = r.recv(5)
        print(f)
        return 3

    f = l.run_until_complete(async_worker(do_thing))
    print(f)


def get_looper():
    import types
    l = SelectorLoop()

    @types.coroutine
    def gl():
        l = yield ("loop",)
        return l

    print(l.run_until_complete(gl()))


def test_spawn():
    async def mf():
        print("asd")
        await spawn(f2())

    async def f2():
        await sleep(3)
        print(1)

    run(mf())


def ctask():
    async def pepe():
        return await current_task()

    l = SelectorLoop()
    f = l.run_until_complete(pepe())
    print(f, type(f), f.__name__)


def locktests():
    d = 0
    lock = Lock()

    async def pepe():
        nonlocal d
        async with lock:
            print(2)
            await sleep(4)
            print(5)
            d = 2

    async def pepo():
        nonlocal d
        async with lock:
            print(3)
            await sleep(7)
            print(4)
            d = 3

        print(lock._queue)

    l = SelectorLoop()
    l.create_task(pepo())
    l.create_task(pepe())
    f = l.run_forever()


def timeouts():
    async def myfunc():
        import time
        try:
            print(time.time())
            async with timeout(3):
                print("cake")
                print((await get_loop())._timers, 'afd')
                await sleep(10)
                print("nyet")
        except Exception as e:
            print(type(e), "asd")
            print(time.time())
        else:
            print(time.time())
            print("shit!")

    l = BaseLoop()
    l.create_task(myfunc())
    l.run_forever()


timeouts()
