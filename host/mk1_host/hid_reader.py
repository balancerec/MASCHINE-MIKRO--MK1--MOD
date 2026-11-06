"""Normal MK1 HID input in a supervised child; no output/feature reports."""
from pathlib import Path
import multiprocessing
import sys
import time
from .supervised import Mailbox, context, stop_process, update_until, wait_mailbox

def open_mk1():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'.deps'))
    import hid
    devices = hid.enumerate(0x17cc, 0x1110)
    if len(devices) != 1:
        raise RuntimeError('Expected exactly one normal MIKRO MK1 HID interface')
    device = hid.device()
    device.open_path(devices[0]['path'])
    device.set_nonblocking(1)
    return device

class Ring:
    def __init__(self, ctx, capacity):
        self.capacity = capacity
        self.lock = ctx.Lock()
        self.data = ctx.RawArray('B', capacity*65)
        self.sequence = ctx.RawArray('I', capacity)
        self.stamp = ctx.RawArray('Q', capacity)
        self.indices = ctx.RawArray('I', 3)  # head, count, stop

    def push(self, sequence, stamp, data):
        if not self.lock.acquire(False):
            return None
        try:
            head, count, stopped = self.indices
            if stopped:
                return False
            if count == self.capacity:
                return False
            index = (head+count) % self.capacity
            for offset, byte in enumerate(data):
                self.data[index*65+offset] = byte
            self.sequence[index], self.stamp[index] = sequence, stamp
            self.indices[1] = count+1
            return True
        finally:
            self.lock.release()

    def pop(self):
        if not self.lock.acquire(False):
            return None
        try:
            head, count, _ = self.indices
            if not count:
                return None
            item = (self.sequence[head], self.stamp[head], bytes(self.data[head*65:(head+1)*65]))
            self.indices[0] = (head+1) % self.capacity
            self.indices[1] = count-1
            return item
        finally:
            self.lock.release()

    def request_stop(self):
        if not self.lock.acquire(False):
            return False
        try:
            self.indices[2] = 1
            return True
        finally:
            self.lock.release()

def reader_worker(mailbox, ring, factory, drain_limit):
    device = None
    try:
        device = factory()
        for _ in range(drain_limit):
            if not device.read(1024):
                break
        else:
            raise RuntimeError('Input buffer did not drain before startup')
        update_until(mailbox, {0: 1})  # ready
        sequence = 0
        while True:
            parent = multiprocessing.parent_process()
            if parent is not None and not parent.is_alive():
                break
            snapshot = ring.indices[2]  # advisory only; locked enqueue also checks stop
            if snapshot:
                break
            data = bytes(device.read(1024))
            stamp = time.monotonic_ns()
            if not data:
                time.sleep(.001)
                continue
            if data[0] != 32:
                continue
            if len(data) < 65:
                raise RuntimeError('Malformed HID20 input')
            while True:
                pushed = ring.push(sequence, stamp, data[:65])
                if pushed is not None:
                    break
                time.sleep(.001)
            if not pushed:
                if ring.indices[2]:
                    break
                raise RuntimeError('Input backlog exceeded ring capacity')
            sequence = (sequence+1) & 0xffffffff
    except Exception as error:
        update_until(mailbox, {0: 3}, {'error': str(error)})
    finally:
        if device is not None:
            device.close()  # may itself block; supervisor owns the deadline
        value = mailbox.read()
        if value and value[0][0] != 3:
            update_until(mailbox, {0: 2})

class SupervisedHID:
    def __init__(self, capacity=128, startup_timeout=5.0, source_factory=open_mk1):
        if not 2 <= capacity <= 4096 or not 0 < startup_timeout <= 30:
            raise ValueError('Invalid input worker limits')
        self.ctx, self.capacity = context(), capacity
        self.startup_timeout, self.factory = startup_timeout, source_factory
        self.process = self.mailbox = self.ring = None

    def start(self):
        if self.process is not None:
            raise RuntimeError('A reader instance cannot be restarted or reuse its IPC')
        self.mailbox, self.ring = Mailbox(self.ctx), Ring(self.ctx, self.capacity)
        self.process = self.ctx.Process(target=reader_worker,
            args=(self.mailbox, self.ring, self.factory, 2048), daemon=True)
        self.process.start()
        try:
            value = wait_mailbox(self.mailbox, self.process, lambda fields: fields[0] in (1, 2, 3), self.startup_timeout)
            if value[0][0] != 1:
                raise RuntimeError(value[1].decode() or 'Input worker startup failed')
        except Exception:
            stop_process(self.process)
            raise

    def status(self):
        value = self.mailbox.read()
        if value and value[0][0] == 3:
            return {'fault': value[1].decode()}
        if not self.process.is_alive():
            return {'fault': 'Input worker exited'}
        return {'fault': None}

    def read(self):
        return self.ring.pop()

    def close(self):
        if self.process is None:
            return True
        self.ring.request_stop()
        return stop_process(self.process)
