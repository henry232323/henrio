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


class Task:
    def __init__(self, task, data):
        self._task = task
        self._data = data
        self._result = None
        self._error = None
        self.complete = False
        self.cancelled = False

    def result(self):
        if self._error is not None:
            raise self._error
        if not self.complete:
            raise RuntimeError("Result isn't ready!")
        return self._result

    def set_result(self, data):
        self.complete = True
        self._result = data

    def set_exception(self, exception):
        self._error = exception

    def cancel(self):
        if self.cancelled:
            return True
        if self.complete:
            return False
        self.cancelled = True
        self.set_exception(CancelledError)


class Loop:
    running = False

    def __init__(self, selector=None):
        self._queue = deque()
        self.__tasks = deque()
        self._timers = list()
        self._readers = dict()
        self._writers = dict()
        self.selector = selector if selector else selectors.DefaultSelector()

    def run_until_complete(self, task):
        self.__tasks.clear()
        self.__tasks.append(Task(task, None))
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
                        task._data = task._task.send(task._data)
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

        return task.result()

    def _poll(self):
        return self.selector.select(0 if self.__tasks or self._queue or self._timers else None)

    def create_task(self, task):
        new_task = Task(task, None)
        self._queue.append(new_task)
        return new_task

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

    def unregister_write(self, fileobj):
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
    loop.run_until_complete(duo())