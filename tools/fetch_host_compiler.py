"""Optional pinned Zig C compiler for Windows x64; never accesses the MK1."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://ziglang.org/download/0.14.1/zig-x86_64-windows-0.14.1.zip'
SHA256 = '554f5378228923ffd558eac35e21af020c73789d87afeabf4bfd16f2e6feed2c'
directory = ROOT/'.tools'
directory.mkdir(exist_ok=True)
archive = directory/'zig-0.14.1.zip'
executable = directory/'zig-x86_64-windows-0.14.1/zig.exe'
if not executable.exists():
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == SHA256, 'Compiler archive hash mismatch'
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            assert (directory/info.filename).resolve().is_relative_to(directory.resolve())
        source.extractall(directory)
print(json.dumps({'compiler': str(executable), 'version': '0.14.1', 'archive_sha256': SHA256}))
