"""Behavior/property tests of our experimental detector. No NI oracle or device."""
import argparse
import ctypes as C
from pathlib import Path
import random
import unittest
from pad_native import Config, Detector, Events, load, read_events

parser = argparse.ArgumentParser()
parser.add_argument('--library', type=Path, required=True)
args = parser.parse_args()
LIB = load(args.library)

class PadTests(unittest.TestCase):
    def fresh(self, control=1):
        state = Detector()
        config = Config(4, 3, 5, 100, 40, 1000, control, 1, 35+control)
        self.assertEqual(LIB.mk1_pad_detector_init(C.byref(state), C.byref(config)), 1)
        return state

    def sample(self, state, value, tick):
        batch = Events()
        self.assertEqual(LIB.mk1_pad_detector_sample(C.byref(state), value, tick & 0xffffffff,
                                                    C.byref(batch)), 1)
        return read_events(batch)

    def test_all_peaks_monotonic_and_short_pulse_balanced(self):
        previous_velocity = 0
        for peak in range(100, 4096):
            state = self.fresh()
            events = self.sample(state, 0, 0)+self.sample(state, 100, 1)
            events += self.sample(state, peak, 2)+self.sample(state, 0, 3)
            events += self.sample(state, 0, 6)
            self.assertEqual([e['kind'] for e in events], [0, 1])
            velocity = events[0]['value']
            self.assertTrue(previous_velocity <= velocity <= 127)
            self.assertGreaterEqual(velocity, 1)
            self.assertEqual(events[1]['value'], 0)
            if peak == 100:
                self.assertEqual(velocity, 1)
            if peak >= 1000:
                self.assertEqual(velocity, 127)
            previous_velocity = velocity

    def test_noise_and_startup_pressure_do_not_trigger(self):
        state = self.fresh()
        for tick in range(20):
            self.assertEqual(self.sample(state, 900, tick), [])
        self.sample(state, 0, 20)
        rng = random.Random(1)
        for tick in range(21, 2021):
            self.assertEqual(self.sample(state, rng.randrange(100), tick), [])

    def test_sustained_note_and_release_jitter(self):
        state = self.fresh()
        self.sample(state, 0, 0)
        self.sample(state, 800, 1)
        self.assertEqual([e['kind'] for e in self.sample(state, 800, 5)], [0])
        for tick in range(6, 1006):
            # A one-tick drop every four samples must not release or retrigger.
            self.assertEqual(self.sample(state, 0 if tick % 4 == 0 else 600, tick), [])
        self.sample(state, 0, 1006)
        self.assertEqual([e['kind'] for e in self.sample(state, 0, 1009)], [1])

    def test_six_isolated_hits_balance_notes(self):
        state, events = self.fresh(), []
        for hit, peak in enumerate((100, 200, 500, 1000, 2000, 4095)):
            tick = hit*30
            for offset, value in ((0, 0), (1, 100), (2, peak), (5, 0), (8, 0)):
                events += self.sample(state, value, tick+offset)
        self.assertEqual([e['kind'] for e in events], [0, 1]*6)
        self.assertEqual([e['value'] for e in events if e['kind'] == 0], [1, 15, 57, 127, 127, 127])

    def test_16_independent_routes(self):
        states = [self.fresh(i+1) for i in range(16)]
        for state in states:
            self.sample(state, 0, 0)
        collected = []
        for tick in range(1, 10):
            for channel, state in enumerate(states):
                value = 800 if channel in (0, 3, 12, 15) and tick < 6 else 0
                collected += self.sample(state, value, tick)
        self.assertEqual(sorted(e['control'] for e in collected if e['kind'] == 0), [1, 4, 13, 16])
        self.assertEqual(sorted(e['control'] for e in collected if e['kind'] == 1), [1, 4, 13, 16])

    def test_flush_and_invalid_time_preserve_contracts(self):
        state = self.fresh()
        self.sample(state, 0, 10)
        self.sample(state, 500, 11)
        batch = Events()
        self.assertEqual(LIB.mk1_pad_detector_flush(C.byref(state), 12, C.byref(batch)), 1)
        self.assertEqual(batch.count, 0)  # pending peak has not emitted a note
        self.sample(state, 0, 13)
        self.sample(state, 500, 14)
        self.sample(state, 500, 18)
        before = bytes(state)
        batch.count = 77
        for adc, tick in ((4096, 19), (0, 17), (0, 18+0x80000000)):
            self.assertEqual(LIB.mk1_pad_detector_sample(C.byref(state), adc, tick, C.byref(batch)), 0)
            self.assertEqual(bytes(state), before)
            self.assertEqual(batch.count, 77)
        self.assertEqual(LIB.mk1_pad_detector_flush(C.byref(state), 19, C.byref(batch)), 1)
        self.assertEqual([e['kind'] for e in read_events(batch)], [1])
        self.assertEqual(LIB.mk1_pad_detector_flush(C.byref(state), 20, C.byref(batch)), 1)
        self.assertEqual(batch.count, 0)

    def test_invalid_configuration_does_not_replace_running_state(self):
        state = self.fresh()
        before = bytes(state)
        invalid = [('release', 100), ('attack', 1000), ('full_scale', 4096),
                   ('peak_ticks', 0), ('release_ticks', 0), ('peak_ticks', 2**31),
                   ('release_ticks', 2**31), ('retrigger_ticks', 2**31),
                   ('midi_channel', 0), ('midi_channel', 17), ('note', 128)]
        for field, value in invalid:
            config = Config.from_buffer_copy(state.config)
            setattr(config, field, value)
            self.assertEqual(LIB.mk1_pad_detector_init(C.byref(state), C.byref(config)), 0)
            self.assertEqual(bytes(state), before)

    def test_expired_cooldown_does_not_return_after_full_timer_wrap(self):
        state = self.fresh()
        for tick, value in ((0, 0), (1, 100), (2, 500), (5, 0), (8, 0), (20, 0),
                            (0x7fffffff, 0), (0xfffffff0, 0), (9, 0), (10, 500)):
            self.sample(state, value, tick)
        self.assertEqual([e['kind'] for e in self.sample(state, 500, 14)], [0])

if __name__ == '__main__':
    unittest.main(argv=['test_pad_detector'])
