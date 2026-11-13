"""Queue, retry and uncertain delivery fault tests using synchronous fake ports."""
import argparse
import ctypes as C
from pathlib import Path
import random
import unittest
from pad_native import load
from pad_native import Config
from test_pad_stream import Stream, Batch, bind as bind_stream, report
from midi_native import Output, PumpResult, Send, bind_output, batch_from_events, possible

class MidiTests(unittest.TestCase):
    def fresh(self):
        state = Output()
        self.assertEqual(LIB.mk1_midi_output_init(C.byref(state)), 1)
        return state

    def submit(self, state, events, expected=1, reset=0, generation=None):
        batch = batch_from_events(events, reset)
        self.assertEqual(LIB.mk1_midi_output_submit(C.byref(state), state.generation if generation is None
                                                   else generation, C.byref(batch)), expected)

    def pump(self, state, statuses=None, budget=64, delivered=None):
        statuses = iter(statuses or [])
        calls, violations = [], []
        @Send
        def backend(context, message):
            data = list(message[:3])
            calls.append(data)
            status = next(statuses, 1)
            if delivered is not None and status == 1:
                route = (data[0] & 15, data[1])
                if data[0] & 0xf0 == 0x90:
                    if route in delivered:
                        violations.append(route)
                    delivered.add(route)
                else:
                    delivered.discard(route)  # cleanup may safely repeat an off
            return status
        result = PumpResult()
        status = LIB.mk1_midi_output_pump(C.byref(state), backend, None, budget, C.byref(result))
        self.assertEqual(violations, [])
        return status, calls, result

    def test_exact_bytes_and_order_on_all_channels(self):
        state = self.fresh()
        self.submit(state, [(0, channel, 35+channel, 100) for channel in range(1, 17)])
        status, calls, result = self.pump(state)
        self.assertEqual((status, result.accepted, state.count), (1, 16, 0))
        self.assertEqual(calls, [[0x90+i, 36+i, 100] for i in range(16)])
        self.submit(state, [(1, channel, 35+channel, 0) for channel in range(1, 17)])
        _, calls, _ = self.pump(state)
        self.assertEqual(calls, [[0x80+i, 36+i, 0] for i in range(16)])
        self.assertFalse(possible(state))

    def test_retry_does_not_pop_or_duplicate_accepted_prefix(self):
        state = self.fresh()
        self.submit(state, [(0, 1, 36, 80), (1, 1, 36, 0)])
        status, calls, result = self.pump(state, [1, 2])
        self.assertEqual((status, result.attempted, result.accepted, state.count), (2, 2, 1, 1))
        self.assertEqual(calls, [[0x90, 36, 80], [0x80, 36, 0]])
        status, calls, result = self.pump(state)
        self.assertEqual((status, result.accepted), (1, 1))
        self.assertEqual(calls, [[0x80, 36, 0]])
        self.assertFalse(possible(state))

    def test_uncertain_on_blocks_and_recovers_only_with_note_off(self):
        state = self.fresh()
        old_generation = state.generation
        self.submit(state, [(0, 1, 36, 100), (1, 1, 36, 0)])
        status, calls, _ = self.pump(state, [3])
        self.assertEqual(status, 3)
        self.assertEqual(possible(state), {(0, 36)})
        self.assertEqual((state.blocked, state.recovering, state.count), (1, 1, 0))
        self.assertNotEqual(state.generation, old_generation)
        self.assertEqual(self.pump(state)[1], [])
        self.submit(state, [(0, 1, 37, 80)], expected=0)
        self.assertEqual(LIB.mk1_midi_output_resume(C.byref(state)), 1)
        status, calls, _ = self.pump(state)
        self.assertEqual((status, calls), (1, [[0x80, 36, 0]]))
        self.assertFalse(possible(state))
        self.submit(state, [(0, 1, 37, 80)], expected=0, generation=old_generation)
        self.submit(state, [(0, 1, 37, 80)])

    def test_uncertain_off_retries_cleanup_without_replaying_on(self):
        state = self.fresh()
        self.submit(state, [(0, 16, 127, 127), (1, 16, 127, 0)])
        self.assertEqual(self.pump(state, [1, 3])[0], 3)
        self.assertEqual(LIB.mk1_midi_output_resume(C.byref(state)), 1)
        self.assertEqual(self.pump(state, [2])[0], 2)
        self.assertEqual(possible(state), {(15, 127)})
        _, calls, _ = self.pump(state)
        self.assertEqual(calls, [[0x8f, 127, 0]])
        self.assertFalse(possible(state))

    def test_overflow_discards_unsent_onsets_but_keeps_cleanup(self):
        state = self.fresh()
        self.submit(state, [(0, 1, 36, 100)])
        self.pump(state)
        pair = [(0, 1, 40, 80), (1, 1, 40, 0)]
        self.submit(state, pair*16)
        self.submit(state, pair*16)
        self.assertEqual(state.count, 64)
        self.submit(state, pair, expected=4)
        self.assertEqual((state.count, state.recovering), (0, 1))
        _, calls, _ = self.pump(state)
        self.assertEqual(calls, [[0x80, 36, 0]])

    def test_stream_reset_cancels_queued_work_and_silences_sent_notes(self):
        state = self.fresh()
        self.submit(state, [(0, 1, 36, 100)])
        self.pump(state)
        self.submit(state, [(0, 1, 40, 100)])
        old = state.generation
        self.submit(state, [(1, 1, 36, 0), (1, 1, 40, 0)], expected=5, reset=16)
        self.assertNotEqual(state.generation, old)
        self.assertEqual(self.pump(state)[1], [[0x80, 36, 0]])
        self.assertEqual(state.count, 0)

    def test_invalid_batch_is_atomic(self):
        state = self.fresh()
        for events in ([(0, 0, 36, 100)], [(0, 17, 36, 100)], [(0, 1, 128, 100)],
                       [(0, 1, 36, 0)], [(1, 1, 36, 50)], [(2, 1, 36, 50)],
                       [(0, 1, 36, 100), (0, 1, 36, 100)], [(1, 1, 36, 0)]):
            before = bytes(state)
            self.submit(state, events, expected=0)
            self.assertEqual(bytes(state), before)

    def test_ring_wrap_and_bounded_pump(self):
        state = self.fresh()
        for _ in range(100):
            self.submit(state, [(0, 1, 36, 100), (1, 1, 36, 0)])
            status, calls, result = self.pump(state, budget=1)
            self.assertEqual((status, result.accepted, state.count), (1, 1, 1))
            self.pump(state, budget=1)
        self.assertFalse(possible(state))

    def test_unexpected_backend_status_fails_closed(self):
        state = self.fresh()
        self.submit(state, [(0, 1, 36, 80)])
        self.assertEqual(self.pump(state, [99])[0], 3)
        self.assertEqual((state.blocked, state.recovering), (1, 1))

    def test_randomized_retries_and_unknown_delivery(self):
        state, rng, delivered = self.fresh(), random.Random(123), set()
        violations = []
        for _ in range(2000):
            if state.blocked:
                LIB.mk1_midi_output_resume(C.byref(state))
            if not state.recovering:
                # Balanced pairs, including queued work across pump calls.
                self.submit(state, [(0, 1, 36, 100), (1, 1, 36, 0)])
            # Unknown delivery here may or may not reach the fake receiver.
            @Send
            def backend(context, message):
                data = list(message[:3])
                status = rng.choice((1, 1, 1, 2, 3))
                actual = status == 1 or (status == 3 and rng.randrange(2))
                if actual:
                    route = (data[0] & 15, data[1])
                    if data[0] & 0xf0 == 0x90:
                        if route in delivered:
                            violations.append(route)
                        delivered.add(route)
                    else:
                        delivered.discard(route)
                return status
            result = PumpResult()
            status = LIB.mk1_midi_output_pump(C.byref(state), backend, None, 2, C.byref(result))
            self.assertIn(status, (1, 2, 3))
            self.assertTrue(delivered.issubset(possible(state)))
            self.assertEqual(violations, [])
        LIB.mk1_midi_output_recover(C.byref(state))
        for _ in range(32):
            self.pump(state, delivered=delivered)
            if not state.recovering:
                break
        self.assertFalse(delivered)
        self.assertFalse(possible(state))

    def test_stream_watchdog_cancels_unsent_attacks_before_cleanup(self):
        stream, batch, output = Stream(), Batch(), self.fresh()
        configs = (Config*16)(*[Config(4, 3, 5, 100, 40, 1000, i+1, 1, 36+i) for i in range(16)])
        self.assertEqual(LIB.mk1_pad_stream_init(C.byref(stream), configs, 16, 50), 1)
        self.assertEqual(LIB.mk1_pad_stream_connect(C.byref(stream), 0, C.byref(batch)), 1)
        for sequence, tick, values in ((0, 0, [0]*16), (1, 1, [800]*16), (2, 5, [800]*16)):
            raw = report(values)
            self.assertEqual(LIB.mk1_pad_stream_frame(C.byref(stream), stream.generation, sequence, tick,
                                                     raw, 65, C.byref(batch)), 1)
            self.assertEqual(LIB.mk1_midi_output_submit(C.byref(output), output.generation, C.byref(batch)), 1)
        self.assertEqual(self.pump(output, budget=1)[1], [[0x90, 36, 99]])
        self.assertEqual(output.count, 15)
        self.assertEqual(LIB.mk1_pad_stream_poll(C.byref(stream), 56, C.byref(batch)), 1)
        self.assertEqual(batch.reset_flags, 16)
        self.assertEqual(LIB.mk1_midi_output_submit(C.byref(output), output.generation, C.byref(batch)), 5)
        self.assertEqual(self.pump(output)[1], [[0x80, 36, 0]])
        self.assertFalse(possible(output))
        self.assertEqual(output.count, 0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', required=True, type=Path)
    args = parser.parse_args()
    LIB = bind_output(bind_stream(args.library))
    unittest.main(argv=['test_midi_output'])
