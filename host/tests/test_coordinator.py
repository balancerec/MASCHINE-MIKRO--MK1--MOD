"""Native pipeline plus fake backend. No USB, services, FL or real MIDI."""
import argparse
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'host'))
from mk1_host.native import Config, NativeEngine, possible_count
from mk1_host.coordinator import Coordinator

def report(value=0):
    words = [(channel << 12) | (value if channel == 0 else 0)
             for _ in range(2) for channel in range(16)]
    return bytes([32]+[byte for word in words for byte in (word & 255, word >> 8)])

class Backend:
    ready = True
    identity = ('MIKRO MOD FL', 1)
    def __init__(self): self.messages, self.results = [], []
    def send(self, message):
        self.messages.append(message)
        return self.results.pop(0) if self.results else 1

class CoordinatorTests(unittest.TestCase):
    def fresh(self):
        configs = [Config(4, 3, 5, 100, 40, 1000, i+1, 1, 36+i) for i in range(16)]
        engine = NativeEngine(args.library, configs, 50)
        backend = Backend()
        coordinator = Coordinator(engine, backend, retry_timeout_us=20)
        return coordinator, backend

    def hit(self, controller):
        generation = controller.start(0)
        self.assertTrue(controller.feed(report(), 0, generation, 0))
        self.assertTrue(controller.feed(report(800), 1, generation, 1))
        self.assertTrue(controller.feed(report(800), 5, generation, 2))
        return generation

    def test_normal_hit_stop_and_explicit_restart(self):
        controller, backend = self.fresh()
        old = self.hit(controller)
        self.assertEqual(backend.messages, [[0x90, 36, 99]])
        self.assertTrue(controller.stop(6))
        self.assertEqual(backend.messages[-1], [0x80, 36, 0])
        self.assertEqual(controller.status()['possible_notes'], 0)
        current = controller.start(7)
        self.assertNotEqual(current, old)
        self.assertFalse(controller.feed(report(800), 8, old, 3))
        controller.feed(report(800), 8, current, 0)
        controller.feed(report(800), 12, current, 1)
        self.assertEqual(len(backend.messages), 2)  # quiet baseline still missing

    def test_watchdog_releases_and_pauses_without_automatic_restart(self):
        controller, backend = self.fresh()
        generation = self.hit(controller)
        controller.advance(56)
        self.assertEqual(controller.phase, 'stopped')
        self.assertEqual(backend.messages[-1], [0x80, 36, 0])
        self.assertFalse(controller.feed(report(800), 57, generation, 3))
        self.assertEqual(len(backend.messages), 2)

    def test_duplicate_frames_do_not_keep_notes_alive(self):
        controller, backend = self.fresh()
        generation = self.hit(controller)
        for tick in (20, 40, 56):
            self.assertFalse(controller.feed(report(800), tick, generation, 2))
        self.assertEqual(controller.phase, 'stopped')
        self.assertEqual(backend.messages[-1], [0x80, 36, 0])

    def test_sequence_gap_flushes_without_replaying_stale_attack(self):
        controller, backend = self.fresh()
        generation = self.hit(controller)
        controller.feed(report(800), 6, generation, 4)
        self.assertEqual(controller.phase, 'stopped')
        self.assertEqual(backend.messages, [[0x90, 36, 99], [0x80, 36, 0]])

    def test_uncertain_delivery_stops_input_and_requires_repair(self):
        controller, backend = self.fresh()
        backend.results = [3]
        generation = self.hit(controller)
        self.assertEqual(controller.phase, 'fault')
        self.assertTrue(controller.engine.output.blocked)
        controller.advance(10)
        self.assertEqual(len(backend.messages), 1)
        self.assertFalse(controller.feed(report(), 11, generation, 3))
        self.assertTrue(controller.repair(12))
        self.assertEqual(backend.messages, [[0x90, 36, 99], [0x80, 36, 0]])
        self.assertEqual(controller.phase, 'stopped')
        self.assertFalse(possible_count(controller.engine.output))

    def test_retry_deadline_stops_and_cancels_unsent_work(self):
        controller, backend = self.fresh()
        backend.results = [2]*10
        self.hit(controller)
        controller.advance(25)
        self.assertEqual(controller.phase, 'fault')
        self.assertEqual(controller.engine.output.count, 0)
        backend.results = []
        self.assertTrue(controller.repair(26))
        self.assertEqual(controller.phase, 'stopped')
        self.assertEqual(len(backend.messages), 2)  # two attempts, no late onset

    def test_endpoint_switch_cannot_receive_old_cleanup(self):
        controller, backend = self.fresh()
        self.hit(controller)
        original = backend.identity
        backend.identity = ('Another port', 2)
        controller.advance(6)
        self.assertEqual(controller.phase, 'fault')
        self.assertEqual(len(backend.messages), 1)
        with self.assertRaises(RuntimeError): controller.repair(7)
        backend.identity = original
        self.assertTrue(controller.repair(8))
        self.assertEqual(backend.messages[-1], [0x80, 36, 0])

    def test_large_clock_gap_uses_cleanup_not_ambiguous_native_poll(self):
        controller, backend = self.fresh()
        self.hit(controller)
        controller.advance(2**31+10)
        self.assertEqual(controller.phase, 'stopped')
        self.assertEqual(backend.messages[-1], [0x80, 36, 0])
        with self.assertRaises(ValueError): controller.advance(9)

    def test_backend_exception_is_latched_as_unknown_delivery(self):
        controller, backend = self.fresh()
        def failed(message): raise OSError('fake backend failure')
        backend.send = failed
        self.hit(controller)
        self.assertEqual(controller.phase, 'fault')
        self.assertTrue(controller.engine.output.blocked)
        self.assertIn('fake backend', controller.last_error)

    def test_native_abi_mismatch_is_rejected_before_state_calls(self):
        class Function:
            def __init__(self, result): self.result = result
            def __call__(self, *unused): return self.result
        class Library:
            pass
        for version, size, expected in ((99, 0, 'version'), (1, 0, 'layout')):
            fake = Library()
            fake.mk1_core_abi_version = Function(version)
            fake.mk1_core_layout_size = Function(size)
            with patch('mk1_host.native.C.CDLL', return_value=fake):
                with self.assertRaisesRegex(RuntimeError, expected):
                    NativeEngine(args.library, [Config() for _ in range(16)], 50)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, required=True)
    args = parser.parse_args()
    unittest.main(argv=['test_coordinator'])
