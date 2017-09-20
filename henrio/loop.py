import time
import typing
from collections import deque
from traceback import print_exc
from inspect import iscoroutine
from heapq import heappop, heappush

from .awaitables import Task, Future
from .bases import AbstractLoop


class BaseLoop(AbstractLoop):
    def __init__(self):
        self._queue = deque()
        self._tasks = deque()
        self._timers = list()
        self._readers = dict()
        self._writers = dict()
        self._files = dict()
        self.running = False

    def time(self):
        """Get the current loop time, relative and monotonic. Speed up the loop by increasing increments"""
        return time.monotonic()

    @staticmethod
    async def handle_callback(self, callback: typing.Callable[..., None], args: typing.Iterable[typing.Any]):
        """Asynchronously deploy a callback sync -> async"""
        await callback(*args)

    def run_until_complete(self, starting_task: typing.Union[typing.Generator, typing.Awaitable]):
        """Run an awaitable/generator until it is complete and return its value. Raise if the task raises"""
        try:
            if self.running:
                raise RuntimeError("Loop is already running!")
            else:
                self.running = True

            self._tasks.clear()
            if not isinstance(starting_task, Future):
                starting_task = Task(starting_task, None)  # Convert any coros to tasks
            if starting_task not in self._tasks:
                self._tasks.appendleft(starting_task)  # Make it priority over already queued tasks
            while self._tasks or self._timers:
                self._loop_once()  # Loop until we're out of tasks

            # Loop is done, return our result
            return starting_task.result()
        finally:
            self.running = False

    def run_forever(self):
        """Run the current tasks queue forever"""
        try:
            if self.running:
                raise RuntimeError("Loop is already running!")
            else:
                self.running = True
            self._tasks.clear()
            self._tasks.extend(self._queue)
            self._queue.clear()
            while self.running:
                self._loop_once()
        finally:
            self.running = False

    def _loop_once(self):
        """Check timers, IO, and run the queue once"""
        self._queue.extend(self._tasks)
        self._tasks.clear()
        if not self._tasks and self._timers:
            time.sleep(max(0.0, self._timers[0][0] - self.time()))

        while self._timers and self._timers[0][0] < self.time():
            _, task = heappop(self._timers)
            self._tasks.append(task)

        self._poll()

        while self._queue:
            task = self._queue.popleft()
            if not task.cancelled and not task.complete:
                try:
                    task._data = task.send(task._data)
                except StopIteration as err:
                    task.set_result(err.value)
                except Exception as err:
                    task.set_exception(err)
                    print_exc()
                else:
                    if isinstance(task._data, tuple) and task._data[0] == 'sleep':
                        heappush(self._timers, (self.time() + task._data[1], task))
                    else:
                        if iscoroutine(task._data):
                            self._tasks.append(task._data)
                        self._tasks.append(task)

    def _poll(self):
        """Poll IO once, base loop doesn't handle IO, thus nothing happens"""
        pass

    def create_task(self, task: typing.Union[typing.Generator, typing.Awaitable]) -> Task:
        """Add a task to the internal queue, will get called eventually. Returns the awaitable wrapped in a Task"""
        if not isinstance(task, Future):
            task = Task(task, None)
        if task not in self._queue:
            self._queue.append(task)
        return task

    def close(self):
        """Close the running event loop"""
        self.running = False
