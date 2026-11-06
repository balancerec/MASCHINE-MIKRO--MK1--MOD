"""Spawn real workers around fake devices only; never opens HID or WinMM."""
from functools import partial
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mk1_host.hid_reader import SupervisedHID
from mk1_host.midi_worker import SupervisedMIDI
from mk1_host.winmm import PortKey

REPORT = bytes([32]+[byte for _ in range(2) for channel in range(16) for byte in (0, channel << 4)])

class FakeReader:
    def __init__(self, mode): self.mode, self.calls = mode, 0
    def read(self, size):
        self.calls += 1
        if self.calls == 1: return []  # startup drain
        if self.mode == 'hang': time.sleep(30)
        if self.mode == 'overflow': return REPORT
        if self.mode == 'malformed': return [32, 0]
        if self.calls == 2: return REPORT
        return []
    def close(self): pass

def fake_reader(mode):
    if mode == 'startup-hang': time.sleep(30)
    return FakeReader(mode)

class FakeMidi:
    def __init__(self, name, mode):
        self.mode = mode
        self.identity = PortKey(name, 1, 2, 3, 1)
    def send(self, message):
        if self.mode == 'hang': time.sleep(30)
        return 3 if self.mode == 'uncertain' else 2 if self.mode == 'retry' else 1
    def close(self): pass

def fake_midi(mode, name):
    if mode == 'startup-hang': time.sleep(30)
    return FakeMidi(name, mode)

class WorkerTests(unittest.TestCase):
    def reader(self, mode, capacity=128, startup_timeout=5):
        return SupervisedHID(capacity, startup_timeout, partial(fake_reader, mode))

    def midi(self, mode, call_timeout=.5, startup_timeout=5):
        return SupervisedMIDI('Test port', call_timeout, startup_timeout, partial(fake_midi, mode))

    def test_reader_reports_are_sequenced_and_close(self):
        reader = self.reader('one')
        try:
            reader.start()
            deadline, value = time.monotonic()+3, None
            while value is None and time.monotonic() < deadline:
                value = reader.read()
                time.sleep(.001)
            self.assertIsNotNone(value)
            sequence, stamp, data = value
            self.assertEqual((sequence, data), (0, REPORT))
            self.assertGreater(stamp, 0)
            self.assertIsNone(reader.status()['fault'])
        finally:
            self.assertTrue(reader.close())

    def test_reader_hung_call_does_not_block_parent_shutdown(self):
        reader = self.reader('hang')
        reader.start()
        start = time.monotonic()
        self.assertTrue(reader.close())
        self.assertLess(time.monotonic()-start, 3)

    def test_reader_overflow_and_malformed_fail_instead_of_overwrite(self):
        for mode in ('overflow', 'malformed'):
            reader = self.reader(mode, capacity=2)
            try:
                try:
                    reader.start()
                except RuntimeError:
                    continue  # child may detect fault before ready is observed
                deadline = time.monotonic()+3
                while reader.status()['fault'] is None and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertIsNotNone(reader.status()['fault'])
            finally:
                self.assertTrue(reader.close())

    def test_reader_startup_deadline(self):
        reader = self.reader('startup-hang', startup_timeout=.2)
        start = time.monotonic()
        with self.assertRaises(TimeoutError): reader.start()
        self.assertLess(time.monotonic()-start, 6)
        self.assertFalse(reader.process.is_alive())

    def test_midi_accept_retry_and_close(self):
        for mode, expected in (('ok', 1), ('retry', 2)):
            sender = self.midi(mode)
            try:
                sender.open()
                self.assertTrue(sender.ready)
                self.assertEqual(sender.send([0x90, 36, 100]), expected)
                self.assertEqual(sender.identity.name, 'Test port')
            finally:
                self.assertTrue(sender.close())

    def test_midi_hang_becomes_uncertain_and_old_worker_must_die(self):
        sender = self.midi('hang', call_timeout=.1)
        try:
            sender.open()
            start = time.monotonic()
            self.assertEqual(sender.send([0x90, 36, 100]), 3)
            self.assertLess(time.monotonic()-start, 3)
            self.assertFalse(sender.ready)
            self.assertFalse(sender.process.is_alive())
            sender.factory = partial(fake_midi, 'ok')
            sender.open()  # a fresh mailbox/worker, same verified identity
            self.assertEqual(sender.send([0x80, 36, 0]), 1)
        finally:
            self.assertTrue(sender.close())

    def test_midi_unknown_result_is_latched(self):
        sender = self.midi('uncertain')
        try:
            sender.open()
            self.assertEqual(sender.send([0x90, 36, 100]), 3)
            self.assertTrue(sender.faulted)
            self.assertEqual(sender.send([0x90, 37, 100]), 3)
        finally:
            self.assertTrue(sender.close())

    def test_midi_startup_deadline(self):
        sender = self.midi('startup-hang', startup_timeout=.2)
        with self.assertRaises(TimeoutError): sender.open()
        self.assertFalse(sender.process.is_alive())

    def test_bad_message_never_published(self):
        sender = self.midi('ok')
        for data in ([0x90, 36, 0], [0xb0, 1, 1], [0x90, 128, 10]):
            with self.assertRaises(ValueError): sender.send(data)
        self.assertIsNone(sender.process)

if __name__ == '__main__': unittest.main()
