import selectors
import time
from collections import deque
from heapq import heappop, heappush
from inspect import iscoroutine
from traceback import print_exc
from types import coroutine

from .futures import Task, Future


class Loop:
    def __init__(self):
        self._queue = deque()
        self._tasks = deque()
        self._timers = list()
        self._readers = dict()
        self._writers = dict()
        self.running = True

    @coroutine
    def handle_callback(self, callback, args):
        yield callback(*args)

    def run_until_complete(self, starting_task):
        if self.running:
            raise RuntimeError("Loop is already running!")
        self._tasks.clear()
        if not isinstance(starting_task, Future):
            starting_task = Task(starting_task, None)
        if starting_task not in self._tasks:
            self._tasks.append(starting_task)
        while self._tasks or self._timers:
            self._queue.extend(self._tasks)
            self._tasks.clear()
            if not self._tasks and self._timers:
                time.sleep(max(0.0, self._timers[0][0] - time.monotonic()))

            while self._timers and self._timers[0][0] < time.monotonic():
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
                        if task._data and task._data[0] == 'sleep':
                            heappush(self._timers, (task._data[1], task))
                        else:
                            if iscoroutine(task._data):
                                self._tasks.append(task._data)
                            self._tasks.append(task)

        return starting_task.result()

    def run_forever(self):
        self._tasks.clear()
        self._tasks.extend(self._queue)
        self._queue.clear()
        while self.running:
            self._queue.extend(self._tasks)
            self._tasks.clear()
            if not self._tasks and self._timers:
                time.sleep(max(0.0, self._timers[0][0] - time.monotonic()))

            while self._timers and self._timers[0][0] < time.monotonic():
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
                        if task._data and task._data[0] == 'sleep':
                            heappush(self._timers, (task._data[1], task))
                        else:
                            if iscoroutine(task._data):
                                self._tasks.append(task._data)
                            self._tasks.append(task)

    def _poll(self):
        pass

    def create_task(self, task):
        if not isinstance(task, Future):
            task = Task(task, None)
        if task not in self._queue:
            self._queue.append(task)
        return task

    def close(self):
        self.running = False


class SelectorLoop(Loop):
    def __init__(self, selector=None):
        super().__init__()
        self.selector = selector if selector else selectors.DefaultSelector()

    def _poll(self):
        if self.selector.get_map():
            files = self.selector.select(0 if self._tasks or self._queue or self._timers else None)
            for file, events in files:
                if events & 1:
                    self._tasks.append(Task(self.handle_callback(*self._readers[file.fd]), None))
                if events & 2:
                    self._tasks.append(Task(self.handle_callback(*self._writers[file.fd]), None))

    def register_reader(self, fileobj, callback, *args):
        if fileobj.fileno() in self.selector.get_map() and self.selector.get_key(
                fileobj).events == selectors.EVENT_WRITE:
            self.selector.modify(fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE)
        else:
            self.selector.register(fileobj, selectors.EVENT_READ)
        self._readers[fileobj.fileno()] = (callback, args)

    def register_writer(self, fileobj, callback, *args):
        if fileobj.fileno() in self.selector.get_map():
            if self.selector.get_key(fileobj).events == selectors.EVENT_READ:
                self.selector.modify(fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE)
        else:
            self.selector.register(fileobj, selectors.EVENT_WRITE)
        self._writers[fileobj.fileno()] = (callback, args)

    def unregister_reader(self, fileobj):
        if fileobj.fileno() in self.selector.get_map():
            if self.selector.get_key(fileobj) == selectors.EVENT_READ ^ selectors.EVENT_WRITE:
                self.selector.modify(fileobj, selectors.EVENT_WRITE)
            else:
                self.selector.unregister(fileobj)
            del self._readers[fileobj.fileno()]
            return True
        else:
            return False

    def unregister_writer(self, fileobj):
        if fileobj.fileno() in self.selector.get_map():
            if self.selector.get_key(fileobj) == selectors.EVENT_READ ^ selectors.EVENT_WRITE:
                self.selector.modify(fileobj, selectors.EVENT_READ)
            else:
                self.selector.unregister(fileobj)
            del self._writers[fileobj.fileno()]
            return True
        else:
            return False
