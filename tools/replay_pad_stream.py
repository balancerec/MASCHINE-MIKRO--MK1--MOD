"""Offline replay through native report parser, stream adapter and detector.

No USB/MIDI calls. Trial parameters explicit; not device calibration.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'core/tests'))
from pad_native import Config
from test_pad_stream import Stream, Batch, bind
from midi_native import Output, PumpResult, Send, bind_output, possible

parser = argparse.ArgumentParser()
parser.add_argument('capture', type=Path)
parser.add_argument('--library', required=True, type=Path)
parser.add_argument('--midi-simulated', action='store_true', help='Accept messages into an in-memory fake backend only')
for option in ('attack', 'release', 'full-scale', 'peak-us', 'release-us', 'retrigger-us', 'max-gap-us'):
    parser.add_argument('--'+option, required=True, type=int)
args = parser.parse_args()
if not (0 <= args.release < args.attack < args.full_scale <= 4095 and
        0 < args.peak_us < 2**31 and 0 < args.release_us < 2**31 and
        0 <= args.retrigger_us < 2**31 and 0 < args.max_gap_us < 2**31):
    parser.error('Invalid trial parameters')
lib, state, batch = bind(args.library), Stream(), Batch()
output, midi_messages, simulated_notes = Output(), [], set()
if args.midi_simulated:
    bind_output(lib)
    assert lib.mk1_midi_output_init(C.byref(output)) == 1

@Send
def simulated_backend(context, message):
    data = list(message[:3])
    midi_messages.append(data)
    route = (data[0] & 15, data[1])
    if data[0] & 0xf0 == 0x90:
        if route in simulated_notes:
            return 3  # fail closed; final validation will expose unexpected cleanup
        simulated_notes.add(route)
    else:
        simulated_notes.discard(route)
    return 1
mapping = json.loads((ROOT/'control-studio/src/physical-calibration.json').read_text())['pads']
configs = (Config*16)()
for pad, data in mapping.items():
    configs[data['input_channel']] = Config(args.peak_us, args.release_us, args.retrigger_us,
                                           args.attack, args.release, args.full_scale, int(pad), 1, 35+int(pad))
assert lib.mk1_pad_stream_init(C.byref(state), configs, 16, args.max_gap_us)
assert lib.mk1_pad_stream_connect(C.byref(state), 0, C.byref(batch))
generation, reports, first, tick = state.generation, 0, None, 0
active, phase_counts, reset_flags = set(), {}, []

def collect(phase):
    if args.midi_simulated:
        status = lib.mk1_midi_output_submit(C.byref(output), output.generation, C.byref(batch))
        assert status in (1, 5)
        result = PumpResult()
        assert lib.mk1_midi_output_pump(C.byref(output), simulated_backend, None, 64, C.byref(result)) == 1
        assert not output.blocked and not output.recovering
    if batch.reset_flags:
        reset_flags.append({'phase': phase, 'flags': batch.reset_flags})
    for event in list(batch.events)[:batch.count]:
        if event.kind == 0:
            assert event.control not in active
            active.add(event.control)
        else:
            assert event.kind == 1 and event.control in active
            active.remove(event.control)
        counts = phase_counts.setdefault(str(phase), {'note_on': {}, 'note_off': {}})
        target = counts['note_on' if event.kind == 0 else 'note_off']
        pad = str(event.control)
        target[pad] = target.get(pad, 0)+1

with (args.capture/'samples.jsonl').open() as samples:
    for line in samples:
        row = json.loads(line)
        first = row['epoch_ns'] if first is None else first
        tick = ((row['epoch_ns']-first)//1000) & 0xffffffff
        raw = bytes.fromhex(row['hex'])
        data = (C.c_uint8*len(raw)).from_buffer_copy(raw)
        assert lib.mk1_pad_stream_frame(C.byref(state), generation, reports, tick,
                                        data, len(raw), C.byref(batch))
        collect(row['phase'])
        reports += 1
pending_before_disconnect = len(active)
assert lib.mk1_pad_stream_disconnect(C.byref(state), tick, C.byref(batch))
disconnect_offs = batch.count
collect('disconnect')
assert not active
result = {'experimental_algorithm': True, 'native_stream_adapter': True,
          'parameters': {key: value for key, value in vars(args).items() if key not in ('capture', 'library')},
          'reports_replayed': reports, 'phase_counts': phase_counts,
          'reset_flags': reset_flags, 'pending_before_disconnect': pending_before_disconnect,
          'disconnect_note_offs': disconnect_offs, 'active_notes_at_end': 0,
          'hardware_access': False, 'midi_sent': False,
          'limits': ['Host-arrival microsecond timebase; no physical latency measurement.',
                     'Host sequence assigned to capture rows; USB loss before capture is not observable.',
                     'Trial parameters are not validated calibration defaults.']}
if args.midi_simulated:
    assert not simulated_notes and not possible(output) and output.count == 0
    result['simulated_midi'] = {'backend': 'in-memory acceptance, no MIDI port opened',
                                'note_on': sum(m[0] & 0xf0 == 0x90 for m in midi_messages),
                                'note_off': sum(m[0] & 0xf0 == 0x80 for m in midi_messages),
                                'active_at_end': 0, 'physical_acknowledgement': False}
(args.capture/'stream-replay.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
