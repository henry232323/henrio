import time
import typing
from collections import deque
from concurrent.futures import CancelledError
from heapq import heappop, heappush
from inspect import iscoroutine, isawaitable
from traceback import print_exc

from .bases import AbstractLoop
from .futures import Task, Future
from .yields import sleep

__all__ = ["BaseLoop"]


class BaseLoop(AbstractLoop):
    def __init__(self):
        self._queue = deque()
        self._tasks = deque()
        self._futures = list()
        self._timers = list()
        self._readers = dict()
        self._writers = dict()
        self.running = 0
        self.threadpool = None
        self.processpool = None

    def time(self):
        """Get the current loop time, relative and monotonic. Speed up the loop by increasing increments"""
        return time.monotonic()

    def sleep(self, amount):
        """Sleep for when there is nothing to do to avoid spinning"""
        return time.sleep(amount)

    def run(self, func, *args, **kwargs):
        """Run a function with the given args"""
        return self.run_until_complete(func(*args, **kwargs))

    def run_until_complete(self, starting_task: typing.Union[typing.Generator, typing.Awaitable]):
        """Run an awaitable/generator until it is complete and return its value. Raise if the task raises"""
        try:
            # if self.running:
            #    raise RuntimeError("Loop is already running!")
            # else:
            #    self.running = True
            self.running += 1
            if not isinstance(starting_task, Future):
                starting_task = Task(starting_task, None)  # Convert any coros to tasks
            if starting_task not in self._tasks:
                self._queue.appendleft(starting_task)  # Make it priority over already queued tasks
            while not starting_task.complete and not starting_task.cancelled and not starting_task._error:
                self._loop_once()  # Loop until we're out of tasks

            # Loop is done, return our result
            return starting_task.result()
        finally:
            if self.running:
                self.running -= 1

    def run_forever(self):
        """Run the current tasks queue forever"""
        try:
            if self.running:
                raise RuntimeError("Loop is already running!")
            else:
                self.running += 1
            while (self._queue or self._tasks or self._timers or self._readers or self._writers) and self.running:
                self._loop_once()  # As long as were 'running' and have stuff to do just keep spinning our loop
        finally:
            if self.running:
                self.running -= 1

    def _loop_once(self):
        """Check timers, IO, and run the queue once"""
        self._queue.extend(self._tasks)
        self._tasks.clear()
        while self._timers:  # Check for overdue timers
            if self._timers[0][0].cancelled or self._timers[0][0].complete:
                task, _ = heappop(self._timers)  # Get the smallest timer
            elif self._timers[0][1] < self.time():
                task, _ = heappop(self._timers)  # Get the smallest timer
                self._tasks.append(task)
            else:
                break

        for future, task in self._futures.copy():
            if future.complete or future.cancelled:
                self._tasks.append(task)
                self._futures.remove((future, task))

        self._poll()  # Poll for IO

        while self._queue:
            task = self._queue.popleft()  # Get next task (FIFO)
            if not task.cancelled and not task.complete:  # If the task isn't done, run it
                try:
                    if task._throw_later:
                        task._data = task.throw(task._throw_later)
                    else:
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
                        command, *args = task._data  # Always ('command', *args) in the form of tuples
                        if command == 'sleep':
                            heappush(self._timers,
                                     (task, self.time() + task._data[1]))  # Add our time to our list of timers
                        else:
                            if command == "loop":  # If we want the loop, give it to em
                                task._data = self
                            elif command == "current_task":
                                task._data = task
                            else:
                                try:
                                    task._data = getattr(self, command)(*args)
                                except Exception as e:
                                    task._throw_later = e
                                if iscoroutine(task._data) and command != "create_task":
                                    self._tasks.append(task._data)
                            self._tasks.append(task)
                    elif task._data is None:
                        self._tasks.append(task)  # Queue the sub-coroutine first, then reschedule our task
                    elif isinstance(task._data, Future):
                        self._futures.append((task._data, task))
                    else:
                        raise RuntimeError("Invalid yield!")
            else:
                if task.cancelled:
                    task.close()

    def _poll(self):
        """Poll IO once, base loop doesn't handle IO, thus nothing happens"""
        if not self._tasks and self._timers:  # We can sleep as long as we want if theres nothing to do
            if not self._timers[0][0].cancelled and self._timers[0][0].complete:
                self.sleep(max(0.0, self._timers[0][1] - self.time()))  # Don't loop if we don't need to
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
        self.running = 0
