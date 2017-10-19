import time
import typing
from collections import deque
from heapq import heappop, heappush
from inspect import iscoroutine, isawaitable
from traceback import print_exc
from concurrent.futures import CancelledError

from .awaitables import Task, Future
from .bases import AbstractLoop
from .workers import worker


class BaseLoop(AbstractLoop):
    def __init__(self):
        self._queue = deque()
        self._tasks = deque()
        self._timers = list()
        self._readers = dict()
        self._writers = dict()
        self.running = False

    def time(self):
        """Get the current loop time, relative and monotonic. Speed up the loop by increasing increments"""
        return time.monotonic()

    def sleep(self, time):
        """Sleep"""
        return time.sleep(time)

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
            while (self._queue or self._tasks or self._timers or self._readers, self._writers) and self.running:
                self._loop_once()  # As long as were 'running' and have stuff to do just keep spinning our loop
        finally:
            self.running = False

    def _loop_once(self):
        """Check timers, IO, and run the queue once"""
        self._queue.extend(self._tasks)
        self._tasks.clear()

        while self._timers and self._timers[0][0] < self.time():  # Check for overdue timers
            _, task = heappop(self._timers)  # Get the smallest timer
            self._tasks.append(task)

        self._poll()  # Poll for IO

        while self._queue:
            task = self._queue.popleft()  # Get next task (FIFO)
            if not task.cancelled and not task.complete:  # If the task isn't done, run it
                try:
                    task._data = task.send(task._data)  # Iterate, send it the new data
                except StopIteration as err:
                    task.set_result(err.value)  # Are we done iterating? Get the err value as the result
                except CancelledError as err:
                    task.cancelled = True
                    task.set_exception(err)
                except Exception as err:  # Did we error? Print the traceback then set as the task error
                    task.set_exception(err)
                    print_exc()
                else:  # If everything went alright, check if we're supposed to sleep. Sleep is in the form of
                    # A generator yielding us a tuple of `("sleep", time_in_seconds)`
                    if isinstance(task._data,
                                  tuple):  # These are all our 'commands' that can be yielded directly into the loop
                        command = task._data[0]  # Always ('command', *args) in the form of tuples
                        if command == 'sleep':
                            heappush(self._timers,
                                     (self.time() + task._data[1], task))  # Add our time to our list of timers
                        else:
                            if command == "loop":  # If we want the loop, give it to em
                                task._data = self
                            elif command == "time":
                                task._data = self.time()
                            elif command == "current_task":
                                task._data = task
                            else:
                                task._data = getattr(self, command)(*task._data[1:])
                                if iscoroutine(task._data):
                                    self._tasks.append(task._data)
                            self._tasks.append(task)
                    else:
                        if iscoroutine(task._data):  # If we received back a coroutine as data, queue it
                            self._tasks.append(task._data)
                        self._tasks.append(task)  # Queue the sub-coroutine first, then reschedule our task

    def _poll(self):
        """Poll IO once, base loop doesn't handle IO, thus nothing happens"""
        if not self._tasks and self._timers:  # We can sleep as long as we want if theres nothing to do
            time.sleep(max(0.0, self._timers[0][0] - self.time()))  # Don't loop if we don't need to
            # Make selector select with timeout instead of sleeping

    def create_task(self, task: typing.Union[typing.Generator, typing.Awaitable]) -> Task:
        """Add a task to the internal queue, will get called eventually. Returns the awaitable wrapped in a Task"""
        if not isawaitable(task):
            raise TypeError("Task must be awaitable!")
        if not isinstance(task, Future):
            task = Task(task, None)
        if task not in self._queue:
            self._queue.append(task)
        return task

    def close(self):
        """Close the running event loop"""
        self.running = False

    async def socket_connect(self, socket, hostpair):
        #socket.setblocking(False)
        #val = socket.connect_ex(hostpair)
        socket.setblocking(True)
        await worker(socket.connect, hostpair)

    async def socket_bind(self, socket, hostpair):
        socket.setblocking(False)
        try:
            resp = socket.bind(hostpair)
            socket.setblocking(True)
            return resp
        except BlockingIOError:
            socket.setblocking(True)
            return await worker(socket.bind, hostpair)
