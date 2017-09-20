class AbstractLoop:
    def time(self):
        raise NotImplementedError

    def run_forever(self):
        raise NotImplementedError

    def run_until_complete(self, coro):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def create_task(self, coro):
        raise NotImplementedError

    def register_reader(self, file, callback, *args):
        raise NotImplementedError

    def register_writer(self, file, callback, *args):
        raise NotImplementedError

    def unregister_reader(self, fileobj):
        raise NotImplementedError

    def unregister_writer(self, fileobj):
        raise NotImplementedError

    def wrap_file(self, file):
        raise NotImplementedError

    def wrap_socket(self, socket):
        raise NotImplementedError

    def _poll(self):
        raise NotImplementedError


class IOBase:
    loop = None
    file = None

    def fileno(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class BaseFile(IOBase):
    async def read(self, nbytes):
        raise NotImplementedError

    async def write(self, nbytes):
        raise NotImplementedError


class BaseSocket(IOBase):
    async def recv(self, nbytes):
        raise NotImplementedError

    async def send(self, data):
        raise NotImplementedError
