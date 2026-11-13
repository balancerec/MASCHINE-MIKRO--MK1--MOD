"""Compare compiled C with existing Python models; no official firmware needed."""
import argparse
import ctypes as C
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'firmware-research'))
from encoder_model import Encoder
from led_pwm_model import LedPwm

U8 = C.c_uint8
B64 = U8*64

class EncoderC(C.Structure):
    _fields_ = [('previous', U8), ('gate', U8), ('position', U8), ('ambiguous_returns', C.c_uint32)]

class HidState(C.Structure):
    _fields_ = [('valid', U8), ('position', U8), ('pressed', U8)]

class HidEvent(C.Structure):
    _fields_ = [('delta', C.c_int8), ('position', U8), ('pressed', U8),
                ('push_changed', U8), ('baseline', U8), ('ambiguous', U8)]

class PwmC(C.Structure):
    _fields_ = [('levels', B64), ('mask', U8*8), ('phase', U8),
                ('previous_phase', U8), ('deadline', C.c_uint32)]

class Update(C.Structure):
    _fields_ = [('frame', U8*8), ('wire_frame', U8*8), ('phase_at_entry', U8),
                ('next_phase', U8), ('deadline', C.c_uint32)]

class PadSample(C.Structure):
    _fields_ = [('tick', C.c_uint32), ('adc', C.c_uint16), ('channel', U8), ('scan', U8)]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', required=True, type=Path)
    args = parser.parse_args()
    lib = C.CDLL(str(args.library.resolve()))
    signatures = {
        'mk1_encoder_sample': [C.POINTER(EncoderC), U8, C.POINTER(C.c_int8)],
        'mk1_hid_encoder_init': [C.POINTER(HidState)],
        'mk1_hid_encoder_read': [C.POINTER(HidState), C.POINTER(U8), C.c_size_t, C.POINTER(HidEvent)],
        'mk1_led_init': [C.POINTER(PwmC), C.POINTER(U8), C.c_size_t, C.c_uint32],
        'mk1_led_set': [C.POINTER(PwmC), C.c_size_t, C.c_uint16],
        'mk1_led_load': [C.POINTER(PwmC), C.POINTER(U8), C.c_size_t],
        'mk1_led_tick': [C.POINTER(PwmC), C.POINTER(Update)],
        'mk1_pad_report_read': [C.POINTER(U8), C.c_size_t, C.c_uint32, C.POINTER(PadSample)],
    }
    for name, arguments in signatures.items():
        getattr(lib, name).argtypes = arguments
        getattr(lib, name).restype = C.c_int
    rng = random.Random(55)
    encoder_cases = 0
    for previous in range(4):
        for gate in range(4):
            for position in (0, 1, 127, 254, 255):
                for byte in range(256):
                    for errors in (0, 0xffffffff):
                        py = Encoder(previous, gate, position, errors)
                        native = EncoderC(previous, gate, position, errors)
                        delta = C.c_int8(99)
                        assert lib.mk1_encoder_sample(C.byref(native), byte, C.byref(delta)) == 1
                        assert delta.value == py.sample(byte)
                        assert (native.previous, native.gate, native.position, native.ambiguous_returns) == (
                            py.previous, py.gate, py.position, py.ambiguous_returns)
                        encoder_cases += 1
    py, native = Encoder(), EncoderC(3, 0, 0, 0)
    for _ in range(10000):
        byte, delta = rng.randrange(256), C.c_int8()
        assert lib.mk1_encoder_sample(C.byref(native), byte, C.byref(delta))
        assert delta.value == py.sample(byte)
        assert (native.position, native.ambiguous_returns) == (py.position, py.ambiguous_returns)

    scenarios = [[0]*64, [31]*64, [i % 32 for i in range(64)]]
    scenarios += [[value if i == slot else 0 for i in range(64)]
                  for slot in range(64) for value in (1, 15, 30, 31)]
    scenarios += [[rng.randrange(32) for _ in range(64)] for _ in range(80)]
    pwm_steps = 0
    for levels in scenarios:
        py, native, update = LedPwm(levels), PwmC(), Update()
        assert lib.mk1_led_init(C.byref(native), B64(*levels), 64, 0xffff0000)
        py.deadline = 0xffff0000
        for step in range(40):
            if step in (10, 20):
                slot, value = rng.randrange(64), 65535 if step == 10 else 0
                assert lib.mk1_led_set(C.byref(native), slot, value)
                py.set_level(slot, value)
            if step == 25:
                values = [rng.randrange(256) for _ in range(64)]
                assert lib.mk1_led_load(C.byref(native), B64(*values), 64)
                py.load_bulk(values)
            expected = py.tick()
            assert lib.mk1_led_tick(C.byref(native), C.byref(update))
            assert list(native.levels) == py.levels
            assert bytes(native.mask) == py.mask
            assert (native.phase, native.previous_phase, native.deadline) == (
                py.phase, py.previous_phase, py.deadline)
            assert (update.phase_at_entry, update.next_phase, update.deadline) == (
                expected['phase_at_entry'], expected['next_phase'], expected['deadline'])
            assert bytes(update.frame).hex() == expected['mask_hex']
            assert bytes(update.wire_frame).hex() == expected['wire_byte_order_hex']
            pwm_steps += 1

    packets = json.loads((ROOT/'tests/fixtures/encoder-ten-right.json').read_text())['packets']
    state, event, total, presses, releases = HidState(), HidEvent(), 0, 0, 0
    assert lib.mk1_hid_encoder_init(C.byref(state))
    for packet in packets:
        data = (U8*len(packet))(*packet)
        assert lib.mk1_hid_encoder_read(C.byref(state), data, len(packet), C.byref(event))
        total += event.delta
        presses += bool(event.pressed and event.push_changed)
        releases += bool(not event.pressed and event.push_changed)
    assert (total, presses, releases) == (10, 2, 2)
    for old in range(16):
        for new in range(16):
            state = HidState(1, old, 0)
            data = (U8*6)(1, 0, 0, 0, 0, new)
            assert lib.mk1_hid_encoder_read(C.byref(state), data, 6, C.byref(event))
            expected = ((new-old+8) % 16)-8
            assert event.ambiguous == (expected == -8)
            assert event.delta == (0 if expected == -8 else expected)

    for _ in range(100):
        words = []
        for scan in range(2):
            channels = list(range(16))
            rng.shuffle(channels)
            words.extend((channel << 12) | rng.randrange(4096) for channel in channels)
        packet = [32]+[byte for word in words for byte in (word & 255, word >> 8)]
        data, samples = (U8*65)(*packet), (PadSample*32)()
        assert lib.mk1_pad_report_read(data, 65, 1234, samples)
        assert [(s.channel, s.adc, s.scan, s.tick) for s in samples] == [
            (word >> 12, word & 4095, i//16, 1234) for i, word in enumerate(words)]
    print(json.dumps({'encoder_single_steps': encoder_cases, 'encoder_sequence_samples': 10000,
                      'pwm_scenarios': len(scenarios), 'pwm_steps': pwm_steps,
                      'hid_delta_pairs': 256, 'physical_fixture_detents': total,
                      'pad_report_cases': 100, 'hardware_access': False}))

if __name__ == '__main__':
    main()
