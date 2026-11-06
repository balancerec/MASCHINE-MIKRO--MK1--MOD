"""Temporal association of channel13 activity with channel12, without causal claims."""
import argparse
import json
import struct
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('capture', type=Path)
args = parser.parse_args()
rows = []
for line in (args.capture/'samples.jsonl').read_text().splitlines():
    event = json.loads(line)
    words = struct.unpack('<32H', bytes.fromhex(event['hex'])[1:65])
    values = [0]*16
    for word in words:
        values[word >> 12] = max(values[word >> 12], word & 4095)
    rows.append((event['phase'], event['epoch_ns'], values))

def groups(channel):
    result = []
    current = []
    last = None
    for row in rows:
        phase, timestamp, values = row
        if values[channel] <= 100:
            continue
        if current and (phase != current[-1][0] or timestamp-last > 150_000_000):
            result.append(current)
            current = []
        current.append(row)
        last = timestamp
    if current:
        result.append(current)
    return result

target = groups(12)
neighbors = []
for group in groups(13):
    start, end = group[0][1], group[-1][1]
    matches = [g for g in target if g[0][0] == group[0][0] and
               g[0][1] <= end+20_000_000 and g[-1][1] >= start-20_000_000]
    neighbors.append({'phase': group[0][0], 'start_epoch_ns': start,
                      'end_epoch_ns': end, 'neighbor_peak': max(r[2][13] for r in group),
                      'target_peak_during_neighbor_activity': max(r[2][12] for r in group),
                      'associated_target_bursts_with_20ms_margin': len(matches)})
result = {'source': str(args.capture), 'threshold': 100, 'group_gap_ms': 150,
          'target_bursts': [{'phase': g[0][0], 'peak': max(r[2][12] for r in g)} for g in target],
          'neighbor_bursts': neighbors, 'calibration_applied': False,
          'limits': ['Temporal association is not proof of electrical or mechanical crosstalk.',
                     'Grouped excursions are not guaranteed physical strike counts.',
                     'Threshold is diagnostic, not a recommended musical trigger threshold.']}
(args.capture/'neighbor-analysis.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
