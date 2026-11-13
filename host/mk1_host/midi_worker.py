"""Deadline-limited parent facade; all WinMM calls live in a disposable child."""
from dataclasses import asdict
import json
import multiprocessing
import time
from .supervised import Mailbox, context, stop_process, update_until, wait_mailbox
from .winmm import PortKey, WinMMBackend

def open_winmm(name):
    backend = WinMMBackend()
    backend.open(name)
    return backend

def midi_worker(mailbox, name, factory, expected):
    backend = None
    try:
        backend = factory(name)
        if expected is not None and backend.identity != expected:
            raise RuntimeError('Replacement MIDI worker opened a different endpoint')
        update_until(mailbox, {0: 1}, asdict(backend.identity))  # idle/ready
        while True:
            parent = multiprocessing.parent_process()
            if parent is not None and not parent.is_alive():
                break
            value = mailbox.read()
            if value is None or value[0][0] != 2:
                time.sleep(.001)
                continue
            fields = value[0]
            request, operation = fields[1], fields[2]
            update_until(mailbox, {0: 3})  # busy; no lock during driver calls
            if operation == 1:
                result = backend.send(fields[4:7])
                update_until(mailbox, {0: 4, 1: request, 3: result})
            elif operation == 2:
                backend.close()
                update_until(mailbox, {0: 5, 1: request, 3: 1})
                break
            else:
                raise RuntimeError('Unknown worker operation')
    except Exception as error:
        update_until(mailbox, {0: 6}, {'error': str(error)})
    finally:
        if backend is not None:
            backend.close()

class SupervisedMIDI:
    def __init__(self, name, call_timeout=.1, startup_timeout=5.0, backend_factory=open_winmm):
        if not name or not 0 < call_timeout <= 5 or not 0 < startup_timeout <= 30:
            raise ValueError('An explicit endpoint and finite worker deadlines are required')
        self.name, self.call_timeout, self.startup_timeout = name, call_timeout, startup_timeout
        self.factory, self.ctx = backend_factory, context()
        self.identity, self.process, self.mailbox = None, None, None
        self.faulted, self.last_error, self.request = False, None, 0
        self.messages_attempted = self.messages_accepted = self.uncertain_deliveries = 0
        self.note_on_accepted = self.note_off_accepted = 0

    @property
    def ready(self):
        return self.process is not None and self.process.is_alive() and not self.faulted

    def open(self):
        if self.process is not None and self.process.is_alive():
            raise RuntimeError('Old worker must have exited before reopening the endpoint')
        self.mailbox = Mailbox(self.ctx)  # never reuse a possibly poisoned lock
        self.process = self.ctx.Process(target=midi_worker,
            args=(self.mailbox, self.name, self.factory, self.identity), daemon=True)
        self.process.start()
        try:
            fields, data = wait_mailbox(self.mailbox, self.process, lambda f: f[0] in (1, 6), self.startup_timeout)
            if fields[0] != 1:
                raise RuntimeError(data.decode())
            opened = PortKey(**json.loads(data))
            if self.identity is not None and opened != self.identity:
                raise RuntimeError('Endpoint changed')
            self.identity, self.faulted = opened, False
        except Exception:
            self.faulted = True
            stop_process(self.process)
            raise

    def _call(self, operation, message=None):
        self.request += 1
        fields = {0: 2, 1: self.request, 2: operation}
        if message is not None:
            fields.update({4+i: byte for i, byte in enumerate(message)})
        deadline, published = time.monotonic()+self.call_timeout, False
        try:
            while time.monotonic() < deadline:
                if self.mailbox.update(fields):
                    published = True
                    break
                time.sleep(.001)
            if not published:
                raise TimeoutError('Unable to publish worker request')
            remaining = max(.001, deadline-time.monotonic())
            reply, data = wait_mailbox(self.mailbox, self.process,
                lambda f: f[0] in (4, 5, 6), remaining)
            if reply[0] == 6 or reply[1] != self.request:
                raise RuntimeError(data.decode() or 'Mismatched worker reply')
            result = reply[3]
            if operation == 1 and result not in (1, 2):
                self.faulted = True
                self.last_error = 'Worker backend reported uncertain delivery'
                stop_process(self.process)
                return 3
            if operation == 1:
                cleared = False
                while time.monotonic() < deadline:
                    if self.mailbox.update({0: 1}):
                        cleared = True
                        break
                    time.sleep(.001)
                if not cleared:
                    # Known accepted result still matters; do not replay it.
                    self.faulted = True
                    self.last_error = 'Unable to clear worker reply'
            return result
        except Exception as error:
            self.last_error, self.faulted = str(error), True
            stop_process(self.process)
            return 3 if published else 2

    def send(self, message):
        if (len(message) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in message) or
            message[0] & 0xf0 not in (0x80, 0x90) or message[1] > 127 or message[2] > 127 or
            (message[0] & 0xf0 == 0x90 and message[2] == 0) or
            (message[0] & 0xf0 == 0x80 and message[2] != 0)):
            raise ValueError('Expected a complete MIDI note-on/off message')
        if not self.ready:
            return 3 if self.faulted else 2
        self.messages_attempted += 1
        result = self._call(1, message)
        self.messages_accepted += result == 1
        self.note_on_accepted += result == 1 and message[0] & 0xf0 == 0x90
        self.note_off_accepted += result == 1 and message[0] & 0xf0 == 0x80
        self.uncertain_deliveries += result == 3
        return result

    def close(self):
        if self.process is None:
            return True
        if self.ready:
            result = self._call(2)
            if result != 1:
                return False
        return stop_process(self.process)
