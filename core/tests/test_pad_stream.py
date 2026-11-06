"""Fault-injection tests of the compiled report-to-detector adapter, no hardware."""
import argparse
import ctypes as C
from pathlib import Path
import random
import unittest
from pad_native import Config, Detector, Event, load

class Stream(C.Structure):
    _fields_ = [('pads', Detector*16), ('generation', C.c_uint32), ('clock_tick', C.c_uint32),
                ('last_frame_tick', C.c_uint32), ('last_sequence', C.c_uint32),
                ('max_gap_ticks', C.c_uint32), ('connected', C.c_uint8), ('has_frame', C.c_uint8)]

class Batch(C.Structure):
    _fields_ = [('events', Event*32), ('count', C.c_uint8), ('reset_flags', C.c_uint8)]

def bind(library):
    lib = load(library)
    lib.mk1_pad_stream_init.argtypes = [C.POINTER(Stream), C.POINTER(Config), C.c_size_t, C.c_uint32]
    for name in ('connect', 'disconnect', 'poll'):
        getattr(lib, 'mk1_pad_stream_'+name).argtypes = [C.POINTER(Stream), C.c_uint32, C.POINTER(Batch)]
    lib.mk1_pad_stream_frame.argtypes = [C.POINTER(Stream), C.c_uint32, C.c_uint32, C.c_uint32,
                                        C.POINTER(C.c_uint8), C.c_size_t, C.POINTER(Batch)]
    for name in ('init', 'connect', 'disconnect', 'poll', 'frame'):
        getattr(lib, 'mk1_pad_stream_'+name).restype = C.c_int
    return lib

def report(values=None, second=None, shuffle=False):
    values = values or [0]*16
    second = values if second is None else second
    words = []
    for scan, data in enumerate((values, second)):
        channels = list(range(16))
        if shuffle:
            random.Random(scan+55).shuffle(channels)
        words += [(channel << 12) | data[channel] for channel in channels]
    raw = [32]+[byte for word in words for byte in (word & 255, word >> 8)]
    return (C.c_uint8*65)(*raw)

def get_events(batch):
    return [(e.kind, e.control, e.value) for e in list(batch.events)[:batch.count]]

class StreamTests(unittest.TestCase):
    def fresh(self, tick=0):
        state = Stream()
        configs = (Config*16)(*[Config(4, 3, 5, 100, 40, 1000, i+1, 1, 36+i) for i in range(16)])
        self.assertEqual(LIB.mk1_pad_stream_init(C.byref(state), configs, 16, 50), 1)
        batch = Batch()
        self.assertEqual(LIB.mk1_pad_stream_connect(C.byref(state), tick, C.byref(batch)), 1)
        self.assertEqual(batch.count, 0)
        return state

    def frame(self, state, sequence, tick, values=None, second=None, shuffle=False):
        batch, raw = Batch(), report(values, second, shuffle)
        self.assertEqual(LIB.mk1_pad_stream_frame(C.byref(state), state.generation, sequence, tick,
                                                 raw, 65, C.byref(batch)), 1)
        return batch

    def held(self):
        state = self.fresh()
        self.frame(state, 0, 0)
        values = [800]*16
        self.frame(state, 1, 1, values)
        batch = self.frame(state, 2, 5, values)
        self.assertEqual(batch.count, 16)
        self.assertTrue(all(kind == 0 for kind, _, _ in get_events(batch)))
        return state

    def call(self, name, state, tick):
        batch = Batch()
        self.assertEqual(getattr(LIB, 'mk1_pad_stream_'+name)(C.byref(state), tick, C.byref(batch)), 1)
        return batch

    def test_tag_routing_and_second_scan_maximum(self):
        state = self.fresh()
        self.frame(state, 0, 0)
        only_second = [0]*16
        only_second[12] = 1000
        self.frame(state, 1, 1, [0]*16, only_second, True)
        batch = self.frame(state, 2, 5, [0]*16, only_second, True)
        self.assertEqual(get_events(batch), [(0, 13, 127)])
        self.frame(state, 3, 6)
        self.assertEqual(get_events(self.frame(state, 4, 9)), [(1, 13, 0)])

    def test_maximum_batch_short_hits_all_channels(self):
        state = self.fresh()
        self.frame(state, 0, 0)
        self.frame(state, 1, 1, [1000]*16)
        self.frame(state, 2, 2)
        batch = self.frame(state, 3, 5)
        self.assertEqual(batch.count, 32)
        self.assertEqual([kind for kind, _, _ in get_events(batch)], [0, 1]*16)

    def test_duplicate_old_sequence_and_old_clock_do_not_mutate(self):
        state = self.held()
        original = bytes(state)
        raw, batch = report(), Batch()
        for sequence, tick in ((2, 6), (1, 6), (3, 4), (2+2**31, 6)):
            batch.count = 77
            self.assertEqual(LIB.mk1_pad_stream_frame(C.byref(state), state.generation, sequence, tick,
                                                     raw, 65, C.byref(batch)), 0)
            self.assertEqual(bytes(state), original)
            self.assertEqual(batch.count, 77)

    def test_sequence_gap_releases_once_and_requires_quiet(self):
        state = self.held()
        batch = self.frame(state, 4, 6, [800]*16)
        self.assertEqual(batch.reset_flags, 1)
        self.assertEqual([kind for kind, _, _ in get_events(batch)], [1]*16)
        self.assertEqual(self.frame(state, 5, 10, [800]*16).count, 0)
        self.frame(state, 6, 11)
        self.frame(state, 7, 12, [800]*16)
        self.assertEqual(self.frame(state, 8, 16, [800]*16).count, 16)

    def test_time_gap_and_combined_gap(self):
        for sequence, expected in ((3, 2), (8, 3)):
            state = self.held()
            batch = self.frame(state, sequence, 56, [800]*16)
            self.assertEqual(batch.reset_flags, expected)
            self.assertEqual(batch.count, 16)
            self.assertTrue(all(kind == 1 for kind, _, _ in get_events(batch)))
            self.assertEqual(self.frame(state, sequence+1, 57, [800]*16).count, 0)

    def test_watchdog_without_frame_and_with_held_notes(self):
        state = self.fresh()
        self.assertEqual(self.call('poll', state, 50).reset_flags, 0)
        self.assertEqual(self.call('poll', state, 51).reset_flags, 16)
        self.assertEqual(state.connected, 0)
        state = self.held()
        self.assertEqual(self.call('poll', state, 55).count, 0)
        batch = self.call('poll', state, 56)
        self.assertEqual((batch.reset_flags, batch.count), (16, 16))
        self.assertEqual(self.call('poll', state, 57).count, 0)
        self.assertEqual(state.connected, 0)

    def test_reconnect_releases_and_rejects_old_generation(self):
        state = self.held()
        generation = state.generation
        batch = self.call('connect', state, 6)
        self.assertEqual((batch.reset_flags, batch.count), (32, 16))
        self.assertEqual(state.generation, generation+1)
        raw, batch = report(), Batch()
        original = bytes(state)
        self.assertEqual(LIB.mk1_pad_stream_frame(C.byref(state), generation, 9, 7,
                                                 raw, 65, C.byref(batch)), 0)
        self.assertEqual(bytes(state), original)
        self.assertEqual(self.frame(state, 0, 7, [800]*16).count, 0)
        self.assertEqual(self.frame(state, 1, 11, [800]*16).count, 0)
        self.assertEqual(self.call('disconnect', state, 12).count, 0)
        self.assertEqual(self.call('disconnect', state, 13).reset_flags, 0)

    def test_malformed_report_disconnects_but_unrelated_id_does_not(self):
        for corruption in ('short', 'tag'):
            state = self.held()
            raw, batch = report(), Batch()
            if corruption == 'tag':
                raw[4] = 0
            self.assertEqual(LIB.mk1_pad_stream_frame(C.byref(state), state.generation, 3, 6,
                                                     raw, 8 if corruption == 'short' else 65, C.byref(batch)), 1)
            self.assertEqual((batch.reset_flags, batch.count, state.connected), (4, 16, 0))
        state, raw, batch = self.held(), report(), Batch()
        raw[0] = 1
        original = bytes(state)
        self.assertEqual(LIB.mk1_pad_stream_frame(C.byref(state), state.generation, 3, 6,
                                                 raw, 65, C.byref(batch)), 0)
        self.assertEqual(bytes(state), original)
        self.assertEqual(self.call('poll', state, 56).count, 16)

    def test_poll_clock_is_watermark_and_wraps(self):
        state = self.fresh(0xfffffffc)
        self.frame(state, 0xffffffff, 0xfffffffd)
        self.frame(state, 0, 0xfffffffe, [800]*16)
        self.assertEqual(self.frame(state, 1, 2, [800]*16).count, 16)
        self.call('poll', state, 3)
        original, raw, batch = bytes(state), report(), Batch()
        self.assertEqual(LIB.mk1_pad_stream_frame(C.byref(state), state.generation, 2, 2,
                                                 raw, 65, C.byref(batch)), 0)
        self.assertEqual(bytes(state), original)
        self.assertEqual(self.call('disconnect', state, 4).count, 16)

    def test_reject_duplicate_routes_without_replacing_state(self):
        state = self.held()
        original = bytes(state)
        configs = (Config*16)(*[state.pads[i].config for i in range(16)])
        configs[1].note = configs[0].note
        self.assertEqual(LIB.mk1_pad_stream_init(C.byref(state), configs, 16, 50), 0)
        self.assertEqual(bytes(state), original)

    def test_randomized_transport_faults_keep_note_balance(self):
        tick = 0xfffffff0
        state, rng, active = self.fresh(tick), random.Random(2026), set()
        sequence = 0xffffffff
        note_on_count = 0
        for _ in range(4000):
            tick = (tick+rng.randrange(1, 21)) & 0xffffffff
            action = rng.randrange(10)
            batch, before = Batch(), bytes(state)
            if action == 0:
                accepted = LIB.mk1_pad_stream_connect(C.byref(state), tick, C.byref(batch))
            elif action == 1:
                accepted = LIB.mk1_pad_stream_disconnect(C.byref(state), tick, C.byref(batch))
            elif action == 2:
                accepted = LIB.mk1_pad_stream_poll(C.byref(state), tick, C.byref(batch))
            else:
                sequence = (sequence+1+rng.randrange(2)) & 0xffffffff
                values = [800 if rng.randrange(3) else 0 for _ in range(16)]
                raw = report(values, shuffle=True)
                current_seq = state.last_sequence if action == 3 and state.has_frame else sequence
                generation = state.generation-1 if action == 4 else state.generation
                if action == 5:
                    raw[4] = raw[2]  # duplicate a channel tag in scan0
                accepted = LIB.mk1_pad_stream_frame(C.byref(state), generation, current_seq, tick,
                                                     raw, 65, C.byref(batch))
            if not accepted:
                self.assertEqual(bytes(state), before)
                continue
            self.assertLessEqual(batch.count, 32)
            for kind, control, value in get_events(batch):
                if kind == 0:
                    self.assertNotIn(control, active)
                    self.assertTrue(1 <= value <= 127)
                    active.add(control)
                    note_on_count += 1
                else:
                    self.assertEqual(kind, 1)
                    self.assertIn(control, active)
                    active.remove(control)
            self.assertEqual(active, {i+1 for i, pad in enumerate(state.pads) if pad.phase == 2})
        for kind, control, _ in get_events(self.call('disconnect', state, tick)):
            self.assertEqual(kind, 1)
            active.remove(control)
        self.assertFalse(active)
        self.assertGreater(note_on_count, 0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, required=True)
    args = parser.parse_args()
    LIB = bind(args.library)
    unittest.main(argv=['test_pad_stream'])
