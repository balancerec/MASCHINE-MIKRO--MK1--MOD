"""Bounded supervised MK1 session. Default output is memory, never a MIDI port."""
import argparse
import json
import multiprocessing
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'host'))
from mk1_host.native import Config, NativeEngine
from mk1_host.coordinator import Coordinator
from mk1_host.hid_reader import SupervisedHID
from mk1_host.memory import MemoryBackend
from mk1_host.midi_worker import SupervisedMIDI
from mk1_host.runtime import run_session

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', required=True, type=Path)
    parser.add_argument('--seconds', type=float, default=10)
    parser.add_argument('--max-age-us', type=int, required=True)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--port')
    parser.add_argument('--ni-input-isolated', action='store_true', help='Operator confirms old NI input cannot duplicate notes in FL')
    parser.add_argument('--sender-timeout-ms', type=int, default=100)
    parser.add_argument('--output', type=Path)
    for option in ('attack', 'release', 'full-scale', 'peak-us', 'release-us', 'retrigger-us', 'max-gap-us', 'retry-us'):
        parser.add_argument('--'+option, type=int, required=True)
    args = parser.parse_args()
    if not (0 < args.seconds <= 60 and 0 < args.max_age_us <= args.max_gap_us < 2**31 and
            0 <= args.release < args.attack < args.full_scale <= 4095 and
            0 < args.peak_us < 2**31 and 0 < args.release_us < 2**31 and
            0 <= args.retrigger_us < 2**31 and 0 < args.retry_us < 2**31 and
            10 <= args.sender_timeout_ms <= 2000):
        parser.error('Invalid explicit trial settings or supervisor limits')
    if args.live and (not args.port or not args.ni_input_isolated):
        parser.error('--live requires an exact --port and --ni-input-isolated operator confirmation')
    if not args.live and (args.port or args.ni_input_isolated):
        parser.error('Dry run cannot select a real MIDI port')
    mapping = json.loads((ROOT/'control-studio/src/physical-calibration.json').read_text())['pads']
    configs = [None]*16
    for pad, data in mapping.items():
        configs[data['input_channel']] = Config(args.peak_us, args.release_us, args.retrigger_us,
            args.attack, args.release, args.full_scale, int(pad), 1, 35+int(pad))
    engine = NativeEngine(args.library, configs, args.max_gap_us)
    backend = SupervisedMIDI(args.port, call_timeout=args.sender_timeout_ms/1000) if args.live else MemoryBackend()
    if args.live:
        backend.open()
    controller = Coordinator(engine, backend, args.retry_us)
    def ready():
        print(json.dumps({'READY': {'mode': 'live-explicit-port' if args.live else 'dry-run-memory-only',
                                     'seconds': args.seconds, 'port': args.port}}), flush=True)
    result = run_session(controller, SupervisedHID(), args.seconds, args.max_age_us, on_ready=ready)
    if args.live:
        # One bounded attempt to restore the same endpoint for note-offs only.
        # Never restart the musical producer automatically after a fault.
        if not result['clean_stop']:
            try:
                if backend.close():
                    backend.open()
                    result['clean_stop'] = controller.repair(time.monotonic_ns()//1000)
                    result['recovery_same_endpoint'] = True
            except Exception as error:
                result['recovery_error'] = str(error)
        result['backend_exited'] = backend.close()
        result['midi_worker_requests'] = backend.messages_attempted
        result['midi_worker_accepted'] = backend.messages_accepted
        result['note_on_accepted_by_backend'] = backend.note_on_accepted
        result['note_off_accepted_by_backend'] = backend.note_off_accepted
        result['uncertain_deliveries'] = backend.uncertain_deliveries
        result['final_status'] = controller.status()
        result['ok'] = result['ok'] and result['clean_stop'] and result['backend_exited']
    result['mode'] = 'live-explicit-port' if args.live else 'dry-run-memory-only'
    result['midi_port_opened'] = bool(args.live)
    result['parameters_are_experimental'] = True
    if not args.live:
        result['real_midi_messages_sent'] = 0
        result['simulated_note_on'] = sum(m[0] & 0xf0 == 0x90 for m in backend.messages)
        result['simulated_note_off'] = sum(m[0] & 0xf0 == 0x80 for m in backend.messages)
    result['unresolved_routes'] = [(channel+1, note) for channel in range(16) for note in range(128)
        if engine.output.possible_notes[channel][note//8] & (1 << (note % 8))]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    return 0 if result['ok'] else 2

if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(main())
