from henrio import *
import unittest


class QueueTest(unittest.TestCase):
    def test_queue(self):
        try:

            l = get_default_loop()
            q = HeapQueue(50)

            print(q)

            async def d():
                return await q.get()

            async def a(i):
                await sleep(3)
                await q.put(i)

            for x in range(100):
                l.create_task(a(x))
                l.create_task(d())

            async def task():
                await sleep(5)
                print(len(l._queue), len(l._tasks))

            l.run_until_complete(task())

        finally:
            self.assertEqual(len(q), 0)
