"""Compile and test the C core on the host. No device APIs or flashing."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--cc', default=os.environ.get('CC', 'cc'), help='Compiler executable, not a shell command')
parser.add_argument('--zig', action='store_true', help='Use the cc subcommand of the provided Zig executable')
args = parser.parse_args()
compiler = shutil.which(args.cc)
if not compiler:
    parser.error('C compiler not found; pass --cc or use the optional pinned host compiler')
command = [compiler]+(['cc'] if args.zig else [])
build = ROOT/'build/core-host'
build.mkdir(parents=True, exist_ok=True)
flags = ['-std=c99', '-Wall', '-Wextra', '-Wpedantic', '-Werror', '-O2',
         '-I', str(ROOT/'core/include')]
library = build/('mk1_core.dll' if os.name == 'nt' else 'libmk1_core.so')
test = build/('mk1_core_test.exe' if os.name == 'nt' else 'mk1_core_test')
sources = [str(ROOT/'core/src'/name) for name in ('mk1_core.c', 'mk1_pad.c', 'mk1_stream.c', 'mk1_midi.c')]
subprocess.run(command+flags+sources+[str(ROOT/'core/tests/test_core.c'), '-o', str(test)], check=True)
subprocess.run(command+flags+(['-fPIC'] if os.name != 'nt' else [])
               +['-DMK1_CORE_SHARED', '-shared']+sources+['-o', str(library)], check=True)
subprocess.run([str(test)], check=True)
pad_test = build/('mk1_pad_test.exe' if os.name == 'nt' else 'mk1_pad_test')
subprocess.run(command+flags+sources+[str(ROOT/'core/tests/test_pad.c'), '-o', str(pad_test)], check=True)
subprocess.run([str(pad_test)], check=True)
subprocess.run([sys.executable, str(ROOT/'core/tests/compare_models.py'), '--library', str(library)], check=True)
subprocess.run([sys.executable, str(ROOT/'core/tests/test_pad_detector.py'), '--library', str(library)], check=True)
subprocess.run([sys.executable, str(ROOT/'core/tests/test_pad_stream.py'), '--library', str(library)], check=True)
subprocess.run([sys.executable, str(ROOT/'core/tests/test_midi_output.py'), '--library', str(library)], check=True)
subprocess.run([sys.executable, str(ROOT/'host/tests/test_winmm.py')], check=True)
subprocess.run([sys.executable, str(ROOT/'host/tests/test_coordinator.py'), '--library', str(library)], check=True)
