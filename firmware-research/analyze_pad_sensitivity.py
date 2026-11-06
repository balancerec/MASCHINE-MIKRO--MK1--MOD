"""Conservative offline inspection; measurements do not automatically tune pads."""
import argparse
import json
import statistics
import struct
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('capture', type=Path)
args = parser.parse_args()
summary = json.loads((args.capture/'summary.json').read_text())
assert summary['complete'] and len(summary['markers']) == 3
rows = []
for line in (args.capture/'samples.jsonl').read_text().splitlines():
    event = json.loads(line)
    raw = bytes.fromhex(event['hex'])
    assert len(raw) == 65 and raw[0] == 32
    values = [0]*16
    words = struct.unpack('<32H', raw[1:])
    assert sorted(word >> 12 for word in words) == sorted(list(range(16))*2)
    for word in words:
        channel = word >> 12
        values[channel] = max(values[channel], word & 4095)
    rows.append((event['phase'], event['epoch_ns'], values))

def bursts(selected, channel=12):
    result = []
    group = []
    last = None
    for _, timestamp, values in selected:
        if values[channel] <= 100:
            continue
        if last is not None and timestamp-last > 150_000_000 and group:
            result.append(group)
            group = []
        group.append((timestamp, values[channel]))
        last = timestamp
    if group:
        result.append(group)
    return [{'start_ns': group[0][0], 'end_ns': group[-1][0],
             'peak': max(value for _, value in group)} for group in result]

phases = []
for phase in range(3):
    selected = [row for row in rows if row[0] == phase]
    groups = bursts(selected)
    peaks = [group['peak'] for group in groups]
    phases.append({'phase': phase, 'reports': len(selected),
                   'channel_peaks': [max(row[2][c] for row in selected) for c in range(16)],
                   'pad1_bursts': groups, 'pad1_peak_median': statistics.median(peaks) if peaks else None})

# Use a documented, bounded quiet tail, excluding the encoder marker vicinity.
rest_end = summary['markers'][0]['epoch_ns']-500_000_000
quiet = [row for row in rows if row[0] == 0 and rest_end-10_000_000_000 <= row[1] < rest_end]
quiet_peaks = [max(row[2][c] for row in quiet) for c in range(16)] if quiet else None
result = {'source': str(args.capture), 'complete': True, 'phases': phases,
          'diagnostic_burst_threshold': 100, 'diagnostic_group_gap_ms': 150,
          'quiet_tail': {'duration_seconds': 10, 'guard_before_marker_ms': 500,
                         'reports': len(quiet), 'channel_peaks': quiet_peaks},
          'quality': {'requested_strikes_per_phase': 6,
                      'observed_groups_light': len(phases[1]['pad1_bursts']),
                      'observed_groups_strong': len(phases[2]['pad1_bursts']),
                      'activity_before_first_marker': bool(phases[0]['pad1_bursts']),
                      'other_active_channels': [c for c in range(16) if c != 12 and
                           max(phase['channel_peaks'][c] for phase in phases) > 100]},
          'applied_to_app': False, 'applied_to_fl': False,
          'limits': ['Grouping detects excursions, not guaranteed physical strikes.',
                     'Phase labels follow encoder markers and user instructions, not measured force.',
                     'Other-channel activity is not by itself proof of crosstalk.',
                     'No controlled pre-cleaning capture is available to quantify improvement.',
                     'One pad trial does not calibrate the other 15 pads.']}
(args.capture/'analysis.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({'phase_reports': [p['reports'] for p in phases],
                  'peak_groups': [[b['peak'] for b in p['pad1_bursts']] for p in phases],
                  'quiet_tail_peaks': quiet_peaks, 'quality': result['quality']}))
