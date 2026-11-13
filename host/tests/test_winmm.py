"""WinMM adapter tests use a fake API on every OS. No ports are opened."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mk1_host.winmm import Port, PortKey, WinMMBackend

KEY = PortKey('MIKRO MOD FL', 1, 102, 256, 1)

class Api:
    def __init__(self):
        self.available = [Port(7, KEY)]
        self.opened = []
        self.closed = []
        self.sent = []
        self.send_code = self.close_code = 0
        self.open_key = KEY
    def ports(self): return self.available
    def open(self, index):
        self.opened.append(index)
        return 101
    def opened_key(self, handle): return self.open_key
    def short(self, handle, packed):
        self.sent.append((handle, packed))
        return self.send_code
    def close(self, handle):
        self.closed.append(handle)
        return self.close_code

class BackendTests(unittest.TestCase):
    def test_no_implicit_open_or_default(self):
        api = Api()
        backend = WinMMBackend(api)
        self.assertFalse(api.opened)
        self.assertEqual(backend.send([0x90, 36, 100]), 2)
        self.assertFalse(api.sent)
        with self.assertRaises(ValueError): backend.open('Missing')
        self.assertFalse(api.opened)

    def test_exact_port_and_packed_short_message(self):
        api, backend = Api(), None
        backend = WinMMBackend(api)
        backend.open(KEY.name)
        self.assertEqual(api.opened, [7])
        self.assertEqual(backend.identity, KEY)
        self.assertEqual(backend.send([0x90, 36, 100]), 1)
        self.assertEqual(api.sent, [(101, 0x00642490)])
        backend.close()
        self.assertEqual(api.closed, [101])
        self.assertFalse(backend.ready)

    def test_ambiguous_prohibited_and_synth_destinations(self):
        for ports, name in (([Port(1, KEY), Port(2, KEY)], KEY.name),
                             ([Port(0, PortKey('Custom Synth', 1, 1, 1, 7))], 'Custom Synth')):
            api = Api(); api.available = ports
            backend = WinMMBackend(api)
            with self.assertRaises(ValueError): backend.open(name)
            self.assertFalse(api.opened)
        for name in ('Maschine Mikro Out', 'Microsoft GS Wavetable Synth', 'Microsoft MIDI Mapper', ''):
            with self.assertRaises(ValueError): WinMMBackend(Api()).open(name)

    def test_open_race_closes_without_sending(self):
        api = Api(); api.open_key = PortKey('Other', 1, 1, 1, 1)
        backend = WinMMBackend(api)
        with self.assertRaises(RuntimeError): backend.open(KEY.name)
        self.assertEqual(api.closed, [101])
        self.assertFalse(api.sent)
        self.assertIsNone(backend.handle)

    def test_send_error_is_uncertain_and_latched(self):
        api = Api(); api.send_code = 67
        backend = WinMMBackend(api); backend.open(KEY.name)
        self.assertEqual(backend.send([0x90, 36, 100]), 3)
        self.assertFalse(backend.ready)
        self.assertEqual(backend.send([0x80, 36, 0]), 3)
        self.assertEqual(len(api.sent), 1)

    def test_reopen_keeps_identity_and_close_failure_keeps_handle(self):
        api = Api(); backend = WinMMBackend(api); backend.open(KEY.name)
        api.close_code = 65
        with self.assertRaises(OSError): backend.close()
        self.assertEqual(backend.handle, 101)
        self.assertFalse(backend.ready)
        api.close_code = 0; backend.close()
        api.available = [Port(12, KEY)]
        backend.open(KEY.name)
        self.assertEqual(api.opened[-1], 12)
        backend.close()
        api.available = [Port(4, PortKey(KEY.name, 2, 102, 256, 1))]
        with self.assertRaises(RuntimeError): backend.open(KEY.name)

    def test_invalid_messages_do_not_call_api(self):
        api = Api(); backend = WinMMBackend(api); backend.open(KEY.name)
        for message in ([0x90, 36, 0], [0x80, 36, 1], [0x90, 128, 10],
                        [0xb0, 1, 1], [0x90, 1], [0x90, True, 1]):
            with self.assertRaises(ValueError): backend.send(message)
        self.assertFalse(api.sent)

if __name__ == '__main__': unittest.main()
