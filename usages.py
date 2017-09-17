from henrio import *
import time


async def sleeper(tim):
    await sleep(tim)
    print("banane")
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
    buffer = bytes()
    def reader():
        global buffer
        received = my_socket.recv(1024)
        if received:
            buffer += received
            pts = buffer.split(b"\r\n")
            buffer = pts.pop()
            for el in pts:
                print(el)
        else:
            loop.unregister_reader(my_socket)
            my_socket.close()

    loop.register_reader(my_socket, reader)
    loop.run_forever()


buffer = bytes()
def run_files():
    global buffer
    loop = SelectorLoop()
    file = open("LICENSE", 'rb')
    def reader():
        global buffer
        received = file.read(1024)
        if received:
            buffer += received
            pts = buffer.split(b"\r\n")
            buffer = pts.pop()
            for el in pts:
                print(el)
        else:
            loop.unregister_reader(file)
            file.close()

    loop.register_reader(file, reader)
    loop.run_forever()


def run_socks():
    import socket
    loop = SelectorLoop()
    r, w = socket.socketpair()
    reader, writer = loop.wrap_socket(r), loop.wrap_socket(w)
    w.send(b"Elle me dit ecris un chanson")
    d = loop.run_until_complete(reader.recv(1024))
    print(d)


def run_stdio():
    import sys
    loop = SelectorLoop()
    reader, writer = loop.wrap_file(sys.stdin), loop.wrap_file(sys.stdout)
    loop.create_task(writer.write("fuck"))
    resp = loop.run_until_complete(reader.read(10))
    print(resp)

run_readers()