import time
import typing
import selectors
from types import coroutine
from collections import deque
from traceback import print_exc
from inspect import iscoroutine
from heapq import heappop, heappush

from .futures import Task, Future, File, Socket


class Loop:
    def __init__(self):
        self._queue = deque()
        self._tasks = deque()
        self._timers = list()
        self._readers = dict()
        self._writers = dict()
        self._files = dict()
        self.running = False

    @coroutine
    def handle_callback(self, callback: typing.Callable, args: typing.Iterable):
        """Asynchronously deploy a callback sync -> async"""
        yield callback(*args)

    def run_until_complete(self, starting_task: typing.Union[typing.Generator, typing.Awaitable]):
        """Run an awaitable/generator until it is complete and return its value. Raise if the task raises"""
        if self.running:
            raise RuntimeError("Loop is already running!")
        else:
            self.running = True

        self._tasks.clear()
        if not isinstance(starting_task, Future):
            starting_task = Task(starting_task, None)
        if starting_task not in self._tasks:
            self._tasks.append(starting_task)
        while self._tasks or self._timers:
            self._loop_once()

        self.running = False
        return starting_task.result()

    def run_forever(self):
        """Run the current tasks forever"""
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
                    if isinstance(task._data, tuple) and task._data[0] == 'sleep':
                        heappush(self._timers, (task._data[1], task))
                    else:
                        if iscoroutine(task._data):
                            self._tasks.append(task._data)
                        self._tasks.append(task)

    def _poll(self):
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


class SelectorLoop(Loop):
    """An event loop using the the OS's builtin Selector."""
    def __init__(self, selector=None):
        super().__init__()
        self.selector = selector if selector else selectors.DefaultSelector()

    def _poll(self):
        """Poll IO using the selector"""
        if self.selector.get_map():
            files = self.selector.select(0 if self._tasks or self._queue or self._timers else None)
            ready = dict()
            for file, events in files:
                if file.fd in self._readers or file.fd in self._writers:
                    if events & 1:
                        self._tasks.append(Task(self.handle_callback(*self._readers[file.fd]), None))
                    if events & 2:
                        self._tasks.append(Task(self.handle_callback(*self._writers[file.fd]), None))
                if file.fd in self._files:
                    ready[file.fd] = events

            for fileno, file in self._files.items():
                if fileno in ready:
                    event = ready[fileno]
                    if event & 1:
                        file._read_ready(True)
                    if event & 2:
                        file._write_ready(True)
                else:
                    file._read_ready(False)
                    file._write_ready(False)

    def register_reader(self, fileobj, callback: typing.Callable, *args):
        """Register a reader, the given callback will be called with the given args when the file is ready to read"""
        if fileobj.fileno() in self.selector.get_map() and self.selector.get_key(
                fileobj).events == selectors.EVENT_WRITE:
            self.selector.modify(fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE)
        else:
            self.selector.register(fileobj, selectors.EVENT_READ)
        self._readers[fileobj.fileno()] = (callback, args)

    def register_writer(self, fileobj, callback: typing.Callable, *args):
        """Register a writer, the given callback will be called with the given args when the file is ready to write"""
        if fileobj.fileno() in self.selector.get_map():
            if self.selector.get_key(fileobj).events == selectors.EVENT_READ:
                self.selector.modify(fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE)
        else:
            self.selector.register(fileobj, selectors.EVENT_WRITE)
        self._writers[fileobj.fileno()] = (callback, args)

    def unregister_reader(self, fileobj):
        """Disable and remove a reader"""
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
        """Disable and remove a writer"""
        if fileobj.fileno() in self.selector.get_map():
            if self.selector.get_key(fileobj) == selectors.EVENT_READ ^ selectors.EVENT_WRITE:
                self.selector.modify(fileobj, selectors.EVENT_READ)
            else:
                self.selector.unregister(fileobj)
            del self._writers[fileobj.fileno()]
            return True
        else:
            return False

    def wrap_file(self, file) -> File:
        """Wrap a file in an async file API."""
        wrapped = File(file, loop=self)
        self._files[file.fileno()] = wrapped
        self.selector.register(file, selectors.EVENT_READ | selectors.EVENT_WRITE)
        return wrapped

    def wrap_socket(self, socket) -> Socket:
        """Wrap a file in an async socket API."""
        wrapped = Socket(socket, loop=self)
        self._files[socket.fileno()] = wrapped
        self.selector.register(socket, selectors.EVENT_READ | selectors.EVENT_WRITE)
        return wrapped
