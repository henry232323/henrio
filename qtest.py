try:
    from henrio import *

    l = get_default_loop()
    q = Queue(50)
    q._queue.append(50)

    async def d(i):
        await q.put(i)
        await sleep(5)
        return await q.get()

    for x in range(1000):
        _ = l.create_task(d(x))

    l.run_forever()

finally:
    print(q._queue)