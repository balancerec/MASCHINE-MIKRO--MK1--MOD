"""Package user-provided NI presets; originals are copied without modification."""
import base64,hashlib,json,shutil,xml.etree.ElementTree as ET
from pathlib import Path
from ler_templates_ni import node,control
ROOT=Path(__file__).resolve().parent
SOURCE=Path(r'C:\Users\balancerec\Downloads\MIKRO_Control_Studio_Presets_MK1')
DEST=ROOT/'control-studio/dist/presets';DEST.mkdir(exist_ok=True)
manifest=[]
for index,path in enumerate(sorted(SOURCE.glob('*.ncmm'))):
    raw=path.read_bytes();root=ET.fromstring(raw);t=root if root.tag=='midi-map' else root.find('midi-map')
    if t is None:raise ValueError(path.name)
    entry={'id':f'user-mk1-{index:02d}','name':t.get('name'),'file':path.name,
           'sha256':hashlib.sha256(raw).hexdigest(),
           'settings':{c.tag:(c.text or '').strip() for c in t if not list(c)},
           'controls':[control(c) for c in t.findall('./controls/*')],
           'pages':[{'name':p.get('name'),'controls':[control(c) for c in p]} for p in t.findall('./pages/page')],
           'pad_groups':[{'name':g.get('name'),'controls':[control(c) for c in g]} for g in t.findall('.//group')],
           'xml_tree':node(t)}
    # Give the separately supplied SLUG copies distinct, recognizable library names.
    if 'SLUG' in path.name:entry['name']='FL Studio - 16 Pads SLUG'+(' · original' if path.name.startswith('original') else '')
    shutil.copy2(path,DEST/path.name)
    (DEST/(entry['id']+'.json')).write_text(json.dumps(entry,ensure_ascii=False),encoding='utf-8')
    manifest.append({k:entry[k] for k in ('id','name','file','sha256')}|{'banks':[g['name'] for g in entry['pad_groups']],'pages':len(entry['pages'])})
(DEST/'index.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
assert len(manifest)==13
print(f'{len(manifest)} presets packaged; original XML retained.')
bundle={'index':manifest,'entries':{},'originals':{}}
for item in manifest:
    bundle['entries'][item['id']]=json.loads((DEST/(item['id']+'.json')).read_text(encoding='utf-8'))
    bundle['originals'][item['id']]=base64.b64encode((DEST/item['file']).read_bytes()).decode()
# Keep the already-running bridge usable without interrupting its process.
app=DEST.parent/'app.js';marker='\n/* MIKRO PRESET LIBRARY BUNDLE */\n'
base=app.read_text(encoding='utf-8').split(marker)[0]
app.write_text(base+marker+'window.MikroBundledPresets='+json.dumps(bundle,ensure_ascii=False)+';\n'+(DEST.parent/'presets.js').read_text(encoding='utf-8'),encoding='utf-8')
