"""Passive MK1 pressure capture with three encoder-release phase markers.

Phase0: rest; phase1: light PAD1 strikes; phase2: strong PAD1 strikes.
No output reports, feature reports, firmware writes or service changes.
"""
import json
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent/'.deps'))
import hid

parser = argparse.ArgumentParser()
parser.add_argument('--strong-only', action='store_true')
parser.add_argument('--corners', action='store_true')
args = parser.parse_args()
if args.strong_only and args.corners:
    parser.error('Choose one capture protocol')
phase_count = 5 if args.corners else 2 if args.strong_only else 3

out = ROOT/'fw55-analysis/physical-check'/time.strftime('pad-sensitivity-%Y%m%d-%H%M%S')
out.mkdir(parents=True)
summary = {'output': str(out), 'hardware_writes': False, 'ni_service_changed': False,
           'target_pad': None if args.corners else 1,
           'target_pads': [1, 4, 13, 16] if args.corners else [1],
           'phase_reports': [0]*phase_count, 'markers': [], 'complete': False,
           'phase_labels': (['rest', 'pad1', 'pad4', 'pad13', 'pad16'] if args.corners else
                            ['rest', 'strong'] if args.strong_only else ['rest', 'light', 'strong'])}
device = None
try:
    devices = hid.enumerate(0x17cc, 0x1110)
    if len(devices) != 1:
        raise RuntimeError('Expected one MK1 normal HID interface')
    device = hid.device()
    device.open_path(devices[0]['path'])
    device.set_nonblocking(1)
    phase = 0
    pressed = False
    summary['ready_epoch_ns'] = time.time_ns()
    (out/'ready.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({'READY': summary}), flush=True)
    deadline = time.monotonic()+240
    with (out/'samples.jsonl').open('w', encoding='utf-8') as stream:
        while time.monotonic() < deadline:
            packet = bytes(device.read(1024))
            if not packet:
                time.sleep(.001)
                continue
            now = time.time_ns()
            if packet[0] == 1 and len(packet) >= 6:
                current = bool(packet[2] & 8)
                if pressed and not current:
                    summary['markers'].append({'epoch_ns': now, 'finished_phase': phase})
                    phase += 1
                    (out/'progress.json').write_text(json.dumps(summary, indent=2))
                    print(json.dumps({'phase': phase, 'markers': summary['markers']}), flush=True)
                    if phase == phase_count:
                        summary['complete'] = True
                        break
                pressed = current
            elif packet[0] == 32 and len(packet) >= 65:
                summary['phase_reports'][phase] += 1
                stream.write(json.dumps({'epoch_ns': now, 'phase': phase, 'hex': packet[:65].hex()})+'\n')
                if summary['phase_reports'][phase] % 500 == 0:
                    stream.flush()
except Exception as error:
    summary['error'] = repr(error)
finally:
    if device:
        device.close()
    summary['ended_epoch_ns'] = time.time_ns()
    (out/'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({'COMPLETE': summary}), flush=True)
