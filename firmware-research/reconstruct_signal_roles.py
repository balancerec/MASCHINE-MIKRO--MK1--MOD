"""Reconstruct bounded signal traces offline; never opens a hardware device.

This is a specification model, not an XS1 emulator. Evidence instructions are
checked against the pinned firmware bytes before producing any results.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARCH = ROOT / 'fw55-analysis/architecture'
HASH = '8b9363b6155fcd230151ed67bc7d9708cfcd6b912800c2ac6f4ace4c4e0ecb5c'

# Evidence anchors selected by register flow from the service wrappers.
ANCHORS = {
    'lcd': [0x6574, 0x6576, 0x657e, 0x6480, 0x6494,
            0x6586, 0x658a, 0x64ec, 0x64f0, 0x6552, 0x6554],
    'pads': [0x6834, 0x6836, 0x6838, 0x683a, 0x683c,
             0x689e, 0x68b2, 0x68b6, 0x68b8, 0x68ba, 0x68bc,
             0x68c0, 0x68c2, 0x68ca, 0x68d0],
    'buttons': [0x630e, 0x6310, 0x6312, 0x631c, 0x6402,
                0x640e, 0x6414, 0x642c, 0x642e, 0x6432],
    'leds': [0x694c, 0x696c, 0x717c, 0x71ca, 0x71d0,
             0x6c74, 0x6c76, 0x6c7c, 0x71e2, 0x71f4, 0x7202, 0x7208],
}


def lcd_cycle(byte, data=False):
    """Relative port timestamps; deliberately no conversion to seconds."""
    if not 0 <= byte <= 255:
        raise ValueError('LCD byte outside 0..255')
    return [{'port': '8A', 'value': byte, 'relative_tick': None},
            {'port': '8C', 'value': 6 if data else 4, 'relative_tick': 0},
            {'port': '8C', 'value': 8, 'relative_tick': 9},
            {'port': '8C', 'value': 8, 'relative_tick': 25}]


def pad_word(serial_word, channel):
    if not 0 <= serial_word <= 0xffffffff or not 0 <= channel < 16:
        raise ValueError('Invalid pad acquisition argument')
    reversed_word = int(f'{serial_word:032b}'[::-1], 2)
    return (channel << 12) | (reversed_word & 0xfff)


def led_shift_trace(frame):
    if len(frame) != 8 or any(not 0 <= b <= 255 for b in frame):
        raise ValueError('LED serial frame must contain eight bytes')
    # Relative to the latch-port timestamp read by getts at 0x71e6.
    return ([{'port': '1F', 'value': 0, 'relative_tick': 0}]
            + [{'port': '1C', 'value': frame[i], 'relative_tick': 10 + 8*(7-i)}
               for i in range(7, -1, -1)]
            + [{'port': '1F', 'value': 1, 'relative_tick': 74},
               {'port': '1F', 'value': 0, 'relative_tick': 75}])


def main():
    raw = (ROOT / 'fw55-analysis/FW55.bit-normalized.bin').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == HASH
    instructions = {}
    for line in (ARCH / 'segment1.annotated.asm').read_text().splitlines():
        match = re.match(r'^([0-9a-f]{8})\s+([0-9a-f]+)\s+(.*)', line)
        if match:
            offset = int(match[1], 16)
            code = bytes.fromhex(match[2])
            instructions[offset] = (code, match[3])
    evidence = {}
    for group, offsets in ANCHORS.items():
        evidence[group] = []
        for offset in offsets:
            code, instruction = instructions[offset]
            assert raw[offset:offset+len(code)] == code, hex(offset)
            evidence[group].append({'offset': hex(offset), 'bytes': code.hex(),
                                    'instruction': instruction})

    roles = {
        'display': {'8A': 'parallel byte output: commands and bitmap data',
                    '8C': 'control vector: command=4, data=6, post-write=8',
                    '1A': 'reset-like startup output: low, wait, high, wait'},
        'pads': {'8B': 'channel selector output (permutation table)',
                 '1J': 'serial acquisition input, 16-bit transfer count',
                 '1I': 'clock-associated port; physical ADC clock inferred',
                 '1H': 'low/high acquisition framing; chip-select interpretation inferred'},
        'buttons': {'1L': 'clock-associated port', '1M': 'serial input, four byte reads',
                    '1K': 'high-low-high load/latch-like pulse before input'},
        'leds': {'1E': 'clock-associated port', '1C': 'serial byte output, indices 7 down to 0',
                 '1F': 'low-high-low latch-like output after serial frame',
                 '1D': 'auxiliary output, complete electrical role unresolved',
                 '1N': 'display backlight PWM output, passed to thread 0x7170'},
    }
    # Check the acquisition transform across all 16 channels and all 12-bit values.
    for channel in range(16):
        for adc in range(4096):
            serial = int(f'{adc:032b}'[::-1], 2)
            assert pad_word(serial, channel) == (channel << 12) | adc
    assert lcd_cycle(0x81)[1]['value'] == 4
    assert lcd_cycle(0x5a, data=True)[1]['value'] == 6
    trace = led_shift_trace(list(range(8)))
    assert [item['value'] for item in trace[1:9]] == list(range(7, -1, -1))
    assert [item['relative_tick'] for item in trace[-2:]] == [74, 75]
    result = {'firmware_sha256': HASH, 'hardware_access': False,
              'method': 'static register flow plus bounded specification model; not CPU emulation',
              'roles': roles, 'evidence': evidence,
              'examples': {'lcd_command_81': lcd_cycle(0x81),
                           'lcd_data_5a': lcd_cycle(0x5a, True),
                           'led_serial_frame': trace},
              'verification': {'instruction_anchors': sum(map(len, ANCHORS.values())),
                               'pad_transform_cases': 16*4096},
              'limits': ['Relative port timestamps are not absolute time units.',
                         'No physical pin assignments or exact peripheral part numbers established.',
                         'External signal names such as reset, chip select and latch remain functional interpretations.',
                         'Serial LED frame example is not the HID LED report or a physical LED calibration.']}
    (ARCH / 'signal-roles.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result['verification']))


if __name__ == '__main__':
    main()
