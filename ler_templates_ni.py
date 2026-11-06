"""Read and preserve the Controller Editor MK1 XML; never write the original."""
from pathlib import Path
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET

SOURCE = Path(r'C:\ProgramData\Native Instruments\Controller Editor\MaschineMikro.ncs')
DEST = Path(__file__).resolve().parent / 'docs' / 'templates-ni'

def node(element):
    return {'tag':element.tag,'attributes':dict(element.attrib),
            'value':(element.text or '').strip(), 'children':[node(c) for c in element]}

def control(element):
    result = {'kind':element.tag, **element.attrib}
    for child in element:
        result[child.tag] = {'value':(child.text or '').strip(), **child.attrib} if child.attrib else (child.text or '').strip()
    if 'channel' in result:
        result['channel_display'] = int(result['channel']) + 1
    return result

def main():
    data=SOURCE.read_bytes()
    root=ET.fromstring(data)
    DEST.mkdir(parents=True,exist_ok=True)
    shutil.copy2(SOURCE,DEST / SOURCE.name)
    templates=[]
    for index,t in enumerate(root.findall('midi-map')):
        templates.append({'index':index,'name':t.get('name'),'attributes':dict(t.attrib),
            'settings':{c.tag:(c.text or '').strip() for c in t if not list(c)},
            'controls':[control(c) for c in t.findall('./controls/*')],
            'pages':[{'name':p.get('name'),'controls':[control(c) for c in p]} for p in t.findall('./pages/page')],
            'pad_groups':[{'name':g.get('name'),'controls':[control(c) for c in g]} for g in t.findall('.//group')],
            'xml_tree':node(t)})
    result={'source':str(SOURCE),'source_sha256':hashlib.sha256(data).hexdigest(),
            'current_index':root.findtext('current_index'),'display_state':node(root.find('display_state')),
            'templates':templates}
    (DEST/'templates-lidos.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    report=['# Templates reais do Controller Editor — MASCHINE MIKRO', '',
        'Fonte: `'+str(SOURCE)+'`.', '',
        'Leitura do arquivo local da Native Instruments. Não é uma extração de memória interna pelo USB. O arquivo original não foi alterado.', '',
        'Índice atual salvo no arquivo: '+str(result['current_index'])+' (base zero). Não comprova qual template estava ativo no equipamento durante a ponte HID.', '',
        'Os canais no XML são base zero; `channel_display` no JSON contém o canal MIDI 1–16.', '',
        '| Entrada | Template | Páginas de controles | Grupos de pads |',
        '|---|---|---:|---:|']
    for t in templates:
        report.append(f"| {t['index']+1} | {t['name']} | {len(t['pages'])} | {len(t['pad_groups'])} |")
    for t in templates:
        report += ['', '## '+str(t['index']+1)+'. '+t['name'], '',
            'Páginas: '+', '.join(p['name'] for p in t['pages'])+'.', '',
            'Grupos de pads: '+', '.join(g['name'] for g in t['pad_groups'])+'.']
        if t['name']=='FL Studio':
            report += ['', '### Atribuições dos pads — grupo '+t['pad_groups'][0]['name'], '',
                '| Pad | Nome | Mensagem | Canal | Modo | LED |','|---|---|---|---:|---|---|']
            for c in sorted((c for c in t['pad_groups'][0]['controls'] if c.get('subtype')=='trigger'),key=lambda c:int(c['id'][3:])):
                behavior=c.get('behavior','')
                report.append('| '+str(c['id'])+' | '+str(c.get('label',c.get('name','')))+' | '+str(c.get('note',c.get('controller','')))+' | '+str(c.get('channel_display',''))+' | '+str(behavior.get('value','') if isinstance(behavior,dict) else behavior)+' | '+str(c.get('led',c.get('ledOn','')))+' |')
    (DEST/'inventario.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps([{k:t[k] for k in ['index','name']} | {'pages':len(t['pages']),'pad_groups':len(t['pad_groups'])} for t in templates],ensure_ascii=False,indent=2))
    fl=next(t for t in templates if t['name']=='FL Studio')
    print('FL Studio sample: '+json.dumps(fl['pad_groups'][0]['controls'][:2],ensure_ascii=False))

if __name__=='__main__':
    main()
