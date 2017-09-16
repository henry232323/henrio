from henrio import *


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
