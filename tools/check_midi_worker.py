"""Open and close an explicit WinMM endpoint in a worker, never send notes."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'host'))
from mk1_host.midi_worker import SupervisedMIDI

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    sender = SupervisedMIDI(args.port, call_timeout=.5)
    try:
        sender.open()
        identity = asdict(sender.identity)
        closed = sender.close()
        print(json.dumps({'identity': identity, 'worker_exited': closed, 'note_messages_sent': 0}))
        return 0 if closed else 2
    finally:
        sender.close()

if __name__ == '__main__': raise SystemExit(main())
