"""Small dependency-free protocol shared with offline helper packages."""
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

FORMAT = 'zone-rush-distributed-primary/1'


class ResultBusy(ValueError):
    pass


class ResultLease:
    """One OS-held writer per result directory, including recovery/header IO."""
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.descriptor = None

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.directory/'.worker.lock', os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b'\0')
                os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            os.close(descriptor)
            raise ResultBusy('This result folder already has an active helper; do not start it twice') from error
        self.descriptor = descriptor
        return self

    def __exit__(self, *args):
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.descriptor = None
        # Persistent lock inode; never delete it to infer ownership.


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def loads(body):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate JSON key')
            value[key] = item
        return value
    def reject(value):
        raise ValueError('Nonfinite JSON constant')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=reject)


def safe_path(root, relative):
    root = Path(root).resolve()
    if type(relative) is not str or Path(relative).is_absolute() or ':' in relative or '\\' in relative:
        raise ValueError('Package paths must be safe relative POSIX paths')
    path = (root/relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Package path escapes its root')
    return path


def write_new(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError('Existing immutable distributed artifact changed')
        return
    with path.open('xb') as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def json_new(path, value):
    write_new(path, canonical(value)+b'\n')


def complete_rows(path, recover=False):
    path = Path(path)
    if not path.exists():
        return []
    body = path.read_bytes()
    if body and not body.endswith(b'\n'):
        if not recover:
            raise ValueError('Result contains an incomplete append; transfer a stable checkpoint')
        cut = body.rfind(b'\n')+1
        write_new(path.with_name(path.name+'.interrupted-'+sha(body[cut:])+'.bin'), body[cut:])
        with path.open('r+b') as handle:
            handle.truncate(cut)
            handle.flush()
            os.fsync(handle.fileno())
        body = body[:cut]
    return [loads(line) for line in body.splitlines()]


def runtime():
    return dict(implementation=platform.python_implementation(), version=platform.python_version(),
                full_version=sys.version, executable_sha256=sha(Path(sys.executable).read_bytes()),
                platform=platform.platform(), logical_cores=os.cpu_count(),
                actor_backend='CPython CPU', cuda_used_by_policy=False)


def verify_bundle(root, expected):
    root = Path(root).resolve()
    body = (root/'bundle.json').read_bytes()
    if type(expected) is not str or sha(body) != expected:
        raise ValueError('Bundle manifest does not match the owner-published hash')
    value = loads(body)
    if value['format'] != FORMAT or value['worker_primary_credit'] != 0:
        raise ValueError('Unsupported distributed bundle')
    for relative, digest in value['files'].items():
        if sha(safe_path(root, relative).read_bytes()) != digest:
            raise ValueError('A bundled source/candidate file changed')
    return value
