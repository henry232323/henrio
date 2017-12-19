from multio import _AsyncLib

import henrio


def open_connection(host, port,
                    timeout=None, *,
                    ssl=False,
                    source_addr=None,
                    server_hostname=None,
                    alpn_protocols=None):
    return henrio.open_connection((host, port),
                                  timeout=timeout,
                                  ssl=ssl,
                                  source_addr=source_addr,
                                  server_hostname=server_hostname,
                                  alpn_protocols=alpn_protocols)


def _henrio_init(lib: _AsyncLib):
    lib.aopen = henrio.aopen
    lib.open_connection = open_connection
    lib.sleep = henrio.sleep
    lib.task_manager = henrio.TaskGroup
    lib.timeout_after = henrio.timeout
    lib.sendall = henrio.AsyncSocket.sendall
    lib.recv = henrio.AsyncSocket.recv
    lib.sock_close = henrio.AsyncSocket.close
    lib.spawn = henrio.spawn

    lib.Lock = henrio.Lock
    lib.Semaphore = henrio.Semaphore
    lib.Queue = henrio.Queue
    lib.Event = henrio.Event
    lib.Cancelled = henrio.CancelledError
    lib.TaskTimeout = TimeoutError
