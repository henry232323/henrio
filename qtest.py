try:
    from henrio import *

    l = get_default_loop()
    q = Queue(50, lifo=True)
    #q._queue.append(50)

    print(q)
    async def d():
        return await q.get()

    async def a(i):
        await sleep(3)
        await q.put(i)

    for x in range(100):
        _ = l.create_task(a(x))
        _ = l.create_task(d())

    async def task():
        await sleep(5)
        print(len(l._queue), len(l._tasks))

    l.run_until_complete(task())

finally:
    print(q)