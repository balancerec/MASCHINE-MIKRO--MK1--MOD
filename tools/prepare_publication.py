"""Explicit publication allowlist. Does not stage, commit, push or read secrets."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = '''README.md PLANO.md PROMPT-CONTINUIDADE.md AGENTS.md .gitignore
.gitattributes requirements.txt requirements-research.txt package.json
build_editor.py mikro_bridge.py Iniciar-MIKRO.ps1 CONEXAO-USB.md FL-STUDIO.md
16-PADS.md integrar_presets.py ler_templates_ni.py test_16_pads.py test_display.py
test_bridge.py test_encoder.cjs test_encoder_browser.cjs'''.split()
RESEARCH = '''encoder_model.py led_pwm_model.py verify_encoder.py verify_led_pwm.py
verify_xmos_image_crc.py inspect_boot_container.py test_boot_container.py
map_xs1_resources.py reconstruct_signal_roles.py trace_fw55.py
capture_encoder_hid.py capture_pad_sensitivity.py analyze_encoder_capture.py
analyze_pad_sensitivity.py analyze_pad_neighbors.py analyze_pad_corners.py'''.split()

def paths():
    result = list(ROOT_FILES)
    result += ['firmware-research/'+name for name in RESEARCH]
    result += ['fl-integration/device_MIKRO_16_Pads.py', '.github/workflows/offline.yml',
               'tools/prepare_publication.py', 'tools/check_public_editor.cjs', 'tests/fixtures/encoder-ten-right.json',
               'control-studio/src/app.js', 'control-studio/src/physical-calibration.json',
               'firmware-research/physical-board/PLACA-MK1.md']
    result += ['docs/'+name for name in ('ESTADO-ATUAL.md', 'ARQUITETURA-PROPOSTA.md', 'MATERIAIS-E-FONTES.md')]
    result += ['control-studio/dist/'+name for name in '''index.html style.css hardware.css
    calibration.js hardware.js display.js physical-controls.js fl-studio.js presets.js'''.split()]
    result += [p.relative_to(ROOT).as_posix() for p in
               sorted((ROOT/'firmware-research/fw55-analysis/architecture').glob('*.md'))]
    result += ['CMakeLists.txt', 'core/README.md', 'core/include/mk1_core.h',
               'core/src/mk1_core.c', 'core/tests/test_core.c', 'core/tests/compare_models.py',
               'tools/test_core.py', 'tools/fetch_host_compiler.py']
    return sorted(set(result))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tree-json', action='store_true')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    names = paths()
    records = []
    tree = []
    for name in names:
        path = ROOT/name
        assert path.is_file() and not path.is_symlink(), name
        content = path.read_bytes().decode('utf-8').replace('\r\n', '\n')
        data = content.encode('utf-8')
        assert len(data) < 100000, name
        assert ('-----BEGIN '+'PRIVATE KEY-----') not in content, name
        records.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        tree.append({'path': name, 'mode': '100644', 'type': 'blob', 'content': content})
    manifest = ROOT/'publication-manifest.json'
    result = {'scope': 'Own source, authored research reports and reduced physical fixture; no NI firmware or installers',
              'hash_representation': 'UTF-8 with LF line endings; independent of working-copy CRLF conversion',
              'files': records, 'manifest_self_excluded_from_hashes': True}
    if args.verify:
        assert json.loads(manifest.read_text(encoding='utf-8')) == result
        print(f'Publication manifest verified: {len(records)} files, {sum(r["bytes"] for r in records)} bytes.')
        return
    manifest.write_bytes((json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    if args.tree_json:
        tree.append({'path': manifest.name, 'mode': '100644', 'type': 'blob', 'content': manifest.read_text(encoding='utf-8')})
        print(json.dumps(tree, ensure_ascii=True))
    else:
        print(f'Prepared {len(records)} files; manifest adds one file.')

if __name__ == '__main__':
    main()
