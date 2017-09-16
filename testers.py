from loop import *

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
