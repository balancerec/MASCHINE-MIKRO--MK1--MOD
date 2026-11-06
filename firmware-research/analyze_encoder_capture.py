"""Analyze normal MK1 report 01: 32 buttons plus two four-bit fields."""
import json
import argparse
from pathlib import Path
from encoder_model import hid_position_delta

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--capture', default='encoder-right-20261105-211604')
parser.add_argument('--detents', type=int)
parser.add_argument('--two-clicks', action='store_true')
args = parser.parse_args()
capture = ROOT/'fw55-analysis/physical-check'/args.capture
events = [json.loads(line) for line in (capture/'events.jsonl').read_text().splitlines()]
# Stop at the first encoder press and its release: the user's end marker.
end = None
press = None
clicks = []
for index, event in enumerate(events):
    buttons = int.from_bytes(bytes(event['bytes'][1:5]), 'little')
    if buttons & (1 << 11):
        press = index if press is None else press
    elif press is not None:
        clicks.append((press, index))
        press = None
        if len(clicks) == (2 if args.two_clicks else 1):
            break
if len(clicks) != (2 if args.two_clicks else 1):
    raise RuntimeError('Required complete encoder clicks not found')
press, end = clicks[-1]
start = clicks[0][1] if args.two_clicks else 0
for pressed, released in clicks:
    assert events[pressed]['bytes'][5] & 15 == events[released]['bytes'][5] & 15
first_click = {'position': events[clicks[0][1]]['bytes'][5] & 15,
               'release_epoch_ns': events[clicks[0][1]]['epoch_ns']}
events = events[start:end+1]
press -= start
end -= start
positions = [event['bytes'][5] & 15 for event in events]
deltas = [hid_position_delta(a, b) for a, b in zip(positions, positions[1:])]
assert hid_position_delta(15, 0) == 1
assert hid_position_delta(0, 15) == -1
moving = [value for value in deltas if value]
assert moving and all(value == 1 for value in moving)
assert positions[press] == positions[end]
button_map = json.loads((ROOT/'calibration/button-map.json').read_text())
assert button_map['buttons']['encoder']['input_bit'] == 11
descriptor = (ROOT/'hid-report-descriptor.bin').read_bytes()
assert bytes.fromhex('250f750495028102') in descriptor
result = {
    'source': str(capture/'events.jsonl'), 'two_click_markers': args.two_clicks,
    'events_analyzed': len(events), 'first_position': positions[0], 'last_position': positions[-1],
    'nonzero_transitions': len(moving), 'all_nonzero_transitions': '+1 modulo 16',
    'wrap_15_to_0': sum(a == 15 and b == 0 for a, b in zip(positions, positions[1:])),
    'right_turn_sign': 1, 'direction_basis': 'User instructed right-only rotation and reported finishing with encoder click',
    'encoder_position_report': {'id': 1, 'byte_index_including_id': 5, 'bit_offset': 0, 'bits': 4},
    'encoder_push': {'button_bit': 11, 'press_epoch_ns': events[press]['epoch_ns'],
                     'release_epoch_ns': events[end]['epoch_ns'],
                     'duration_ms': (events[end]['epoch_ns']-events[press]['epoch_ns'])/1e6,
                     'rotation_during_click': False},
    'physical_detent_ratio': None,
    'limits': ['First observed position is a baseline, not a counted transition.',
               'User did not state an exact physical detent count.',
               'No electrical quadrature samples are present in HID input.',
               'Only the first six bytes of report 01 are meaningful; trailing buffer bytes are ignored.'],
}
if args.detents is not None:
    assert args.detents > 0
    rotation_reports = len(moving) if args.two_clicks else 1 + len(moving)
    result['counted_trial'] = {
        'user_counted_right_detents': args.detents,
        'position_reports_before_click': rotation_reports,
        'directly_observed_increment_transitions': len(moving),
        'supported_increments_per_detent': 1 if rotation_reports == args.detents else None,
        'confidence': ('Directly measured between two clicks' if args.two_clicks else
                       'Counted trial supports 1:1; first report lacks a fresh pre-motion baseline'),
    }
    result['limits'] = [v for v in result['limits'] if 'did not state' not in v]
    if args.two_clicks:
        result['initial_click'] = first_click
        result['physical_detent_ratio'] = sum(moving)/args.detents
        assert len(moving) == args.detents, 'Counted detents do not match observed increments'
(capture/'analysis.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
