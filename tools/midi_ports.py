"""WinMM enumeration or explicit open/close check. Never sends MIDI notes."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'host'))
from mk1_host.winmm import WinMMApi, WinMMBackend

parser = argparse.ArgumentParser()
parser.add_argument('--check-port', help='Exact dedicated virtual port name; no default/mapper')
args = parser.parse_args()
api = WinMMApi()
result = {'ports': [asdict(port) for port in api.ports()], 'opened': False, 'messages_sent': 0}
if args.check_port:
    backend = WinMMBackend(api)
    backend.open(args.check_port)
    result['opened'] = True
    result['selected_identity'] = asdict(backend.identity)
    backend.close()
    result['closed'] = True
    result['messages_sent'] = backend.messages_attempted
print(json.dumps(result, ensure_ascii=False))
