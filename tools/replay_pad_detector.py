"""Replay private raw captures through the compiled experimental detector.

Only reads capture files and writes an analysis file. No MIDI/HID output.
All thresholds/times must be supplied explicitly; none is a calibration default.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'core/tests'))
from pad_native import Config, Detector, Events, load, read_events

parser = argparse.ArgumentParser()
parser.add_argument('capture', type=Path)
parser.add_argument('--library', required=True, type=Path)
for option in ('attack', 'release', 'full-scale', 'peak-us', 'release-us', 'retrigger-us'):
    parser.add_argument('--'+option, required=True, type=int)
args = parser.parse_args()
if not (0 <= args.release < args.attack < args.full_scale <= 4095 and
        0 < args.peak_us < 2**31 and 0 < args.release_us < 2**31 and
        0 <= args.retrigger_us < 2**31):
    parser.error('Invalid detector parameters')
library = load(args.library)
physical = json.loads((ROOT/'control-studio/src/physical-calibration.json').read_text())['pads']
states = {}
for pad, mapping in physical.items():
    pad = int(pad)
    state = Detector()
    config = Config(args.peak_us, args.release_us, args.retrigger_us,
                    args.attack, args.release, args.full_scale, pad, 1, 35+pad)
    assert library.mk1_pad_detector_init(C.byref(state), C.byref(config))
    states[pad] = (state, mapping['input_channel'])

events, first, tick, reports = [], None, 0, 0
active = set()

def collect(batch, phase, flush=False):
    for event in read_events(batch):
        control = event['control']
        if event['kind'] == 0:
            assert control not in active, 'Duplicate note-on'
            active.add(control)
        else:
            assert control in active, 'Unmatched note-off'
            active.remove(control)
        events.append(dict(event, phase=phase, from_flush=flush))

with (args.capture/'samples.jsonl').open() as stream:
    for line in stream:
        row = json.loads(line)
        first = row['epoch_ns'] if first is None else first
        tick = ((row['epoch_ns']-first)//1000) & 0xffffffff
        raw = bytes.fromhex(row['hex'])
        assert len(raw) == 65 and raw[0] == 32
        values = [0]*16
        for word in struct.unpack('<32H', raw[1:]):
            values[word >> 12] = max(values[word >> 12], word & 4095)
        for state, channel in states.values():
            batch = Events()
            assert library.mk1_pad_detector_sample(C.byref(state), values[channel], tick, C.byref(batch))
            collect(batch, row['phase'])
        reports += 1
for state, _ in states.values():
    batch = Events()
    assert library.mk1_pad_detector_flush(C.byref(state), tick, C.byref(batch))
    collect(batch, None, flush=True)
assert not active
phase_counts = {}
for event in events:
    key = str(event['phase'])
    counts = phase_counts.setdefault(key, {'note_on': {}, 'note_off': {}})
    kind = 'note_on' if event['kind'] == 0 else 'note_off'
    pad = str(event['control'])
    counts[kind][pad] = counts[kind].get(pad, 0)+1
result = {'experimental_algorithm': True, 'timebase': 'microseconds derived from capture timestamps',
          'parameters': {key: value for key, value in vars(args).items() if key not in ('capture', 'library')},
          'reports_replayed': reports, 'phase_counts': phase_counts,
          'events': events, 'flush_note_offs': sum(e['from_flush'] for e in events),
          'active_notes_after_flush': 0, 'hardware_access': False, 'midi_sent': False,
          'limits': ['Parameters are trial values, not a validated device calibration.',
                     'Raw capture replay is not physical MIDI/latency validation.',
                     'ADC values use the maximum of the two samples of each channel per report.']}
(args.capture/'detector-replay.json').write_text(json.dumps(result, indent=2))
print(json.dumps({key: value for key, value in result.items() if key != 'events'}))
