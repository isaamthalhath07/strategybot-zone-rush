"""Fetch one official portable interpreter; verify its published SHA BEFORE use."""
import hashlib
import json
from pathlib import Path
import re
import stat
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILENAME = 'pypy3.11-v8.0.1-win64.zip'
URL = 'https://downloads.python.org/pypy/'+FILENAME
CHECKSUM_URL = 'https://pypy.org/checksums'
EXPECTED = 'cba5f9e9543c679ea5d31b6c81b7a6667d836e3c18bf3eb6cb8c72147f829896'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def main():
    directory = ROOT/'.cache/runtime_bench'
    directory.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(CHECKSUM_URL, headers={'User-Agent': 'StrategyBot-runtime-verification/1'})
    checksum_body = urllib.request.urlopen(request, timeout=30).read()
    matches = re.findall(r'([0-9a-f]{64})\s+'+re.escape(FILENAME), checksum_body.decode('utf8'))
    if matches != [EXPECTED]:
        raise ValueError('Official checksum page did not confirm the expected release hash')
    archive = directory/FILENAME
    if not archive.exists():
        request = urllib.request.Request(URL, headers={'User-Agent': 'StrategyBot-runtime-verification/1'})
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
        if sha(body) != EXPECTED:
            raise ValueError('Downloaded interpreter SHA mismatch; it will not execute')
        archive.write_bytes(body)
    if sha(archive.read_bytes()) != EXPECTED:
        raise ValueError('Cached interpreter SHA mismatch; it will not execute')
    destination = directory/'portable_pypy'
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        for entry in zipped.infolist():
            target = (destination/entry.filename).resolve()
            if not target.is_relative_to(destination.resolve()) or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError('Unsafe archive path')
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            body = zipped.read(entry)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != body:
                raise ValueError('Existing portable runtime differs from verified archive')
            if not target.exists():
                target.write_bytes(body)
    executable = destination/FILENAME.removesuffix('.zip')/'pypy3.exe'
    if not executable.exists():
        executable = destination/FILENAME.removesuffix('.zip')/'pypy.exe'
    if not executable.exists():
        raise ValueError('Verified archive contained no expected interpreter')
    proof = dict(source=URL, checksum_source=CHECKSUM_URL, archive_sha256=EXPECTED,
                 checksum_page_sha256=sha(checksum_body), archive_bytes=archive.stat().st_size,
                 executable=str(executable), executable_sha256=sha(executable.read_bytes()),
                 globally_installed=False, executed_by_fetcher=False)
    (directory/'verified_pypy.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf8')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
