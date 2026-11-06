"""Build the public editor without bundling NI binaries or original presets."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
dist = ROOT/'control-studio/dist'
dist.mkdir(parents=True, exist_ok=True)
app = dist/'app.js'
marker = '/* MIKRO PRESET LIBRARY BUNDLE */'
if app.exists() and marker in app.read_text(encoding='utf-8'):
    print('Existing local preset bundle preserved; use a clean checkout to build the public editor.')
else:
    flags = {'flTemplate': (dist/'fl-template.json').exists()}
    app.write_text((ROOT/'control-studio/src/app.js').read_text(encoding='utf-8')
                   +'\nwindow.MikroLocalAssets='+json.dumps(flags)+';\n'
                   +'window.MikroBundledPresets={index:[],entries:{},originals:{}};\n'
                   +(dist/'presets.js').read_text(encoding='utf-8'), encoding='utf-8')
    print('Public editor built; optional NI preset library not included.')
calibration = dist/'physical-calibration.json'
if not calibration.exists():
    calibration.write_bytes((ROOT/'control-studio/src/physical-calibration.json').read_bytes())

