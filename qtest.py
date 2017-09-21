try:
    from henrio import *

    l = get_default_loop()
    q = Queue(50, lifo=True)
    #q._queue.append(50)

    print(q)
    async def d(i):
        return await q.get()

    async def a():
        f = l.time()
        await sleep(5)
        print(l.time() - f)
        await q.put(5)
        print(l._queue, l._tasks)

    l.create_task(a())

    l.run_until_complete(d(5))

finally:
    print(q)