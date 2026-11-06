"""Loop policy tests, no native library or devices."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mk1_host.runtime import run_session

class Clock:
    def __init__(self, start=0): self.now = start
    def read(self): return self.now
    def sleep(self, seconds): self.now += int(seconds*1e9)

class Controller:
    def __init__(self): self.phase, self.reason, self.feeds, self.stops = 'stopped', None, [], 0
    def start(self, tick): self.phase = 'running'; return 7
    def feed(self, data, tick, generation, sequence): self.feeds.append((data, generation, sequence))
    def advance(self, tick): pass
    def stop(self, tick): self.stops += 1; self.phase = 'stopped'; return True
    def status(self): return {'phase': self.phase, 'possible_notes': 0}

class Reader:
    def __init__(self, rows=(), fault=None): self.rows, self.fault, self.closed = list(rows), fault, False
    def start(self): pass
    def status(self): return {'fault': self.fault}
    def read(self): return self.rows.pop(0) if self.rows else None
    def close(self): self.closed = True; return True

class RuntimeTests(unittest.TestCase):
    def run_loop(self, reader, controller=None, start=0, budget=32):
        clock, controller = Clock(start), controller or Controller()
        result = run_session(controller, reader, .01, 5000, budget, clock.read, clock.sleep)
        return result, controller

    def test_duration_and_normal_close(self):
        reader = Reader([(0, 0, b'a'), (1, 0, b'b')])
        result, controller = self.run_loop(reader)
        self.assertTrue(result['ok'])
        self.assertEqual(result['reports'], 2)
        self.assertEqual([row[2] for row in controller.feeds], [0, 1])
        self.assertTrue(reader.closed)

    def test_stale_and_future_frames_never_reach_detector(self):
        for stamp in (0, 10000001):
            result, controller = self.run_loop(Reader([(0, stamp, b'x')]), start=10000000)
            self.assertFalse(result['ok'])
            self.assertEqual(controller.feeds, [])
            self.assertEqual(controller.stops, 1)

    def test_worker_fault_discards_queued_data(self):
        result, controller = self.run_loop(Reader([(0, 0, b'x')], 'overflow'))
        self.assertEqual(result['reason'], 'overflow')
        self.assertFalse(result['ok'])
        self.assertEqual(controller.feeds, [])

    def test_startup_failure_still_closes_and_stops(self):
        class Failed(Reader):
            def start(self): raise TimeoutError('fake startup hang')
        reader = Failed()
        result, controller = self.run_loop(reader)
        self.assertFalse(result['ok'])
        self.assertTrue(reader.closed)
        self.assertEqual(controller.stops, 1)

    def test_unclean_stop_cannot_report_success(self):
        class Dirty(Controller):
            def stop(self, tick): return False
        result, _ = self.run_loop(Reader(), Dirty())
        self.assertFalse(result['ok'])

    def test_budget_allows_periodic_clock_progress(self):
        rows = [(i, 0, b'x') for i in range(40)]
        result, controller = self.run_loop(Reader(rows), budget=10)
        self.assertTrue(result['ok'])
        self.assertEqual(result['reports'], 40)
        self.assertEqual(len(controller.feeds), 40)

if __name__ == '__main__': unittest.main()
