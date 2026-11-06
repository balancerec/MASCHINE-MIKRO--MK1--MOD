"""Replay private captures through the host coordinator to memory only."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'host'))
from mk1_host.native import Config, NativeEngine
from mk1_host.coordinator import Coordinator
from mk1_host.memory import MemoryBackend

parser = argparse.ArgumentParser()
parser.add_argument('capture', type=Path)
parser.add_argument('--library', type=Path, required=True)
for option in ('attack', 'release', 'full-scale', 'peak-us', 'release-us', 'retrigger-us', 'max-gap-us', 'retry-us'):
    parser.add_argument('--'+option, type=int, required=True)
args = parser.parse_args()
if not (0 <= args.release < args.attack < args.full_scale <= 4095 and
        0 < args.peak_us < 2**31 and 0 < args.release_us < 2**31 and
        0 <= args.retrigger_us < 2**31 and 0 < args.max_gap_us < 2**31 and 0 < args.retry_us < 2**31):
    parser.error('Invalid experimental detector/stream parameters')
mapping = json.loads((ROOT/'control-studio/src/physical-calibration.json').read_text())['pads']
configs = [None]*16
for pad, data in mapping.items():
    configs[data['input_channel']] = Config(args.peak_us, args.release_us, args.retrigger_us,
                                           args.attack, args.release, args.full_scale, int(pad), 1, 35+int(pad))
engine = NativeEngine(args.library, configs, args.max_gap_us)
backend = MemoryBackend()
controller = Coordinator(engine, backend, args.retry_us)
generation = controller.start(0)
first, tick, reports = None, 0, 0
with (args.capture/'samples.jsonl').open() as samples:
    for line in samples:
        row = json.loads(line)
        first = row['epoch_ns'] if first is None else first
        tick = (row['epoch_ns']-first)//1000
        assert controller.feed(bytes.fromhex(row['hex']), tick, generation, reports)
        assert controller.phase == 'running', controller.status()
        reports += 1
assert controller.stop(tick), controller.status()
assert not backend.active
result = {'reports_replayed': reports, 'destination': 'memory-only',
          'note_on': sum(message[0] & 0xf0 == 0x90 for message in backend.messages),
          'note_off': sum(message[0] & 0xf0 == 0x80 for message in backend.messages),
          'final_status': controller.status(), 'real_midi_messages_sent': 0,
          'hardware_access': False, 'parameters_are_experimental': True,
          'parameters': {key: value for key, value in vars(args).items() if key not in ('capture', 'library')}}
(args.capture/'host-replay.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
