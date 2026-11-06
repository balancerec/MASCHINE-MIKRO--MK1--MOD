"""Analyze the four-corner capture without changing any calibration values."""
import argparse
import json
import statistics
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('capture', type=Path)
args = parser.parse_args()
summary = json.loads((args.capture/'summary.json').read_text())
assert summary['complete'] and summary['target_pads'] == [1, 4, 13, 16]
assert len(summary['markers']) == 5
mapping = json.loads((ROOT/'calibration/pad-map.json').read_text())['pads']
rows = [[] for _ in range(5)]
for line in (args.capture/'samples.jsonl').read_text().splitlines():
    event = json.loads(line)
    raw = bytes.fromhex(event['hex'])
    assert len(raw) == 65 and raw[0] == 32
    words = struct.unpack('<32H', raw[1:])
    assert sorted(w >> 12 for w in words) == sorted(list(range(16))*2)
    values = [0]*16
    for word in words:
        values[word >> 12] = max(values[word >> 12], word & 4095)
    rows[event['phase']].append((event['epoch_ns'], values))

def pulses(samples, channel):
    groups, group, last = [], [], None
    for timestamp, values in samples:
        if values[channel] <= 100:
            continue
        if group and timestamp-last > 150_000_000:
            groups.append(group)
            group = []
        group.append((timestamp, values[channel]))
        last = timestamp
    if group:
        groups.append(group)
    return [{'start_ns': g[0][0], 'end_ns': g[-1][0], 'peak': max(v for _, v in g)}
            for g in groups]

results = []
for phase, pad in enumerate(summary['target_pads'], 1):
    channel = mapping[str(pad)]['channel']
    groups = pulses(rows[phase], channel)
    peaks = [group['peak'] for group in groups]
    others = []
    for other_pad, config in mapping.items():
        if int(other_pad) == pad:
            continue
        other = pulses(rows[phase], config['channel'])
        if other:
            others.append({'pad': int(other_pad), 'pulses': other})
    results.append({'pad': pad, 'channel': channel, 'reports': len(rows[phase]),
                    'observed_pulses': len(groups), 'pulses': groups,
                    'peak_min': min(peaks) if peaks else None,
                    'peak_max': max(peaks) if peaks else None,
                    'peak_median': statistics.median(peaks) if peaks else None,
                    'saturated_reports': sum(v[channel] == 4095 for _, v in rows[phase]),
                    'other_pad_activity': others})
result = {'source': str(args.capture), 'expected_strikes_per_pad': 6,
          'rest_channel_peaks': [max(v[c] for _, v in rows[0]) for c in range(16)],
          'results': results, 'calibration_applied': False,
          'method': 'max of two banks; threshold 100; group gap 150ms; physical channel map',
          'limits': ['Hand-applied force is not standardized between pads.',
                     'Raw peak differences do not establish sensitivity ratios.',
                     'Pulse groups are diagnostic and not necessarily emitted MIDI notes.',
                     'Only four pads tested; no light-velocity calibration in this trial.']}
(args.capture/'corner-analysis.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
