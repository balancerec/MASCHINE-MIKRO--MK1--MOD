"""Passive normal HID input capture; no writes and no NI service changes."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent/'.deps'))
import hid

out = ROOT/'fw55-analysis/physical-check'/time.strftime('encoder-right-%Y%m%d-%H%M%S')
out.mkdir(parents=True)
device = None
summary = {'output': str(out), 'seconds': 180, 'hardware_writes': False,
           'ni_service_changed': False, 'reports': {}, 'events': 0}
try:
    entries = hid.enumerate(0x17cc, 0x1110)
    if len(entries) != 1:
        raise RuntimeError('Expected one normal MK1 HID interface')
    device = hid.device()
    device.open_path(entries[0]['path'])
    device.set_nonblocking(1)
    previous = {}
    with (out/'events.jsonl').open('w', encoding='utf-8') as stream:
        summary['ready_epoch_ns'] = time.time_ns()
        (out/'ready.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps({'READY': summary}), flush=True)
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            packet = bytes(device.read(1024))
            if not packet:
                time.sleep(.002)
                continue
            key = str(packet[0])
            summary['reports'][key] = summary['reports'].get(key, 0)+1
            if packet[0] != 1 or previous.get(key) == packet:
                continue
            previous[key] = packet
            event = {'epoch_ns': time.time_ns(), 'hex': packet.hex(), 'bytes': list(packet)}
            stream.write(json.dumps(event)+'\n')
            stream.flush()
            summary['events'] += 1
            print(json.dumps(event), flush=True)
except Exception as error:
    summary['error'] = repr(error)
    print(json.dumps({'ERROR': summary['error']}), flush=True)
finally:
    if device:
        device.close()
    summary['ended_epoch_ns'] = time.time_ns()
    (out/'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({'COMPLETE': summary}), flush=True)
