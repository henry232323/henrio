from types import coroutine
from collections import deque
from heapq import heappop, heappush
from traceback import print_exc
from inspect import iscoroutine
import time
import selectors


@coroutine
def ayield():
    yield


@coroutine
def sleep(seconds):
    yield ("sleep", time.monotonic() + seconds)


async def handle_callback(callback, args):
    return callback(*args)


class CancelledError(Exception):
    pass


class Future:
    def __init__(self):
        self._result = None
        self._error = None
        self.complete = False
        self.cancelled = False
        self._current = self.__await__()

    def result(self):
        if self._error is not None:
            raise self._error
        if not self.complete:
            raise RuntimeError("Result isn't ready!")
        return self._result

    def set_result(self, data):
        if self.complete or self._error is not None:
            raise RuntimeError("Future already completed")
        self.complete = True
        self._result = data

    def set_exception(self, exception):
        if self.complete or self._error is not None:
            raise RuntimeError("Future already completed")
        self._error = exception

    def cancel(self):
        if self.cancelled:
            return True
        if self.complete:
            return False
        self.cancelled = True
        self.set_exception(CancelledError)

    def __await__(self):
        if not self.complete and self._error is None:
            yield self
        return self.result()

    def send(self, data):
        self._current.send(data)


class Task(Future):
    def __init__(self, task, data):
        super().__init__()
        self._task = task
        self._data = data

    def send(self, data):
        self._task.send(data)

    def throw(self, exc):
        self._task.throw(exc)


class Loop:
    def __init__(self, selector=None):
        self._queue = deque()
        self.__tasks = deque()
        self._timers = list()
        self._readers = dict()
        self._writers = dict()
        self.running = False
        self.selector = selector if selector else selectors.DefaultSelector()

    def run_until_complete(self, starting_task):
        if self.running:
            raise RuntimeError("Loop is already running!")
        self.__tasks.clear()
        if not isinstance(starting_task, Future):
            starting_task = Task(starting_task, None)
        if starting_task not in self.__tasks:
            self.__tasks.append(starting_task)
        while self.__tasks or self._timers:
            self._queue.extend(self.__tasks)
            self.__tasks.clear()
            if not self.__tasks and self._timers:
                time.sleep(max(0.0, self._timers[0][0] - time.monotonic()))

            while self._timers and self._timers[0][0] < time.monotonic():
                _, task = heappop(self._timers)
                self.__tasks.append(task)

            if self.selector.get_map():
                for file, events in self._poll():
                    if events & 1:
                        self.__tasks.append(Task(handle_callback(*self._readers[file.fd]), None))
                    if events & 2:
                        self.__tasks.append(Task(handle_callback(*self._writers[file.fd]), None))

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
                                self.__tasks.append(task._data)
                            self.__tasks.append(task)

        return starting_task.result()

    def run_forever(self):
        self.__tasks.clear()
        self.__tasks.extend(self._queue)
        self._queue.clear()
        while self.running:
            self._queue.extend(self.__tasks)
            self.__tasks.clear()
            if not self.__tasks and self._timers:
                time.sleep(max(0.0, self._timers[0][0] - time.monotonic()))

            while self._timers and self._timers[0][0] < time.monotonic():
                _, task = heappop(self._timers)
                self.__tasks.append(task)

            if self.selector.get_map():
                for file, events in self._poll():
                    if events & 1:
                        self.__tasks.append(Task(handle_callback(*self._readers[file.fd]), None))
                    if events & 2:
                        self.__tasks.append(Task(handle_callback(*self._writers[file.fd]), None))

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
                                self.__tasks.append(task._data)
                            self.__tasks.append(task)

    def _poll(self):
        return self.selector.select(0 if self.__tasks or self._queue or self._timers else None)

    def create_task(self, task):
        if not isinstance(task, Future):
            task = Task(task, None)
        if task not in self._queue:
            self._queue.append(task)
        return task

    def close(self):
        self.running = False

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

if __name__ == "__main__":
    from testers import *
    loop = Loop()

    f = loop.run_until_complete(sleep(5))