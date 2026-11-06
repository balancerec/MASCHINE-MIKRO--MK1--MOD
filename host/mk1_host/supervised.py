"""Disposable shared-memory workers. Never reuse IPC after forced termination."""
import json
import multiprocessing as MP
import time

def context():
    return MP.get_context('spawn')

def stop_process(process, timeout=0.25):
    if process is None:
        return True
    if process.pid is None:
        return True
    process.join(timeout)
    if process.is_alive():
        process.terminate()
        process.join(timeout)
    return not process.is_alive()

class Mailbox:
    """No I/O under lock; the parent only attempts a nonblocking acquisition."""
    def __init__(self, ctx):
        self.lock = ctx.Lock()
        self.fields = ctx.RawArray('q', 8)  # state, request, operation, result, bytes...
        self.metadata = ctx.RawArray('B', 2048)

    def read(self):
        if not self.lock.acquire(False):
            return None
        try:
            return list(self.fields), bytes(self.metadata).split(b'\0', 1)[0]
        finally:
            self.lock.release()

    def update(self, fields, metadata=None):
        if not self.lock.acquire(False):
            return False
        try:
            for index, value in fields.items():
                self.fields[index] = value
            if metadata is not None:
                data = json.dumps(metadata).encode('utf-8')
                if len(data) >= len(self.metadata):
                    raise ValueError('Worker metadata too large')
                for index in range(len(self.metadata)):
                    self.metadata[index] = data[index] if index < len(data) else 0
            return True
        finally:
            self.lock.release()

def update_until(mailbox, fields, metadata=None):
    # Child side only; parent can terminate it if a lock holder disappeared.
    while not mailbox.update(fields, metadata):
        time.sleep(.001)

def wait_mailbox(mailbox, process, predicate, timeout):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        value = mailbox.read()
        if value is not None and predicate(value[0]):
            return value
        if not process.is_alive():
            raise RuntimeError('Worker exited before reply')
        time.sleep(.001)
    raise TimeoutError('Worker reply deadline exceeded')
