from . import postpone, current_task
from concurrent.futures import CancelledError

__all__ = ["timeout"]

class timeout:
    def __init__(self, time):
        """A timeout that cancels the task once the timeout is reached. May act weirdly if no other tasks are running"""
        if time <= 0:
            raise ValueError("Timeout must be greater than 0!")
        self.timeout = time
        self.exited = False
        self.task = None

    def canceller(self):
        if self.exited:
            return
        self.task.cancel()

    async def __aenter__(self):
        self.task = await current_task()
        await postpone(self.canceller, self.timeout)

    async def __aexit__(self, exc_type, exc, tb):
        if exc:
            if exc_type is CancelledError:
                raise TimeoutError
            raise exc
        self.exited = True