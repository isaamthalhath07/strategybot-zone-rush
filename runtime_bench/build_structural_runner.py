"""Build a separate versioned runner; never edits or monkeypatches the original."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = 'bae5c92c51efa83eaef90db0ede9940be72201d2bb78e9d0527e3f6139d7503b'
NAMES = ('signature', 'namespace', 'init_worker', 'opponent', 'play_game', 'verify_row')


def build():
    source = ROOT/'evolution/runner.py'
    body = source.read_bytes()
    if hashlib.sha256(body).hexdigest() != EXPECTED:
        raise ValueError('Frozen base runner changed; versioned experiment must be reviewed again')
    text = body.decode('utf8')
    functions = {node.name: ast.get_source_segment(text, node) for node in ast.parse(text).body
                 if isinstance(node, ast.FunctionDef) and node.name in NAMES}
    if set(functions) != set(NAMES):
        raise ValueError('Frozen runner functions changed')
    if functions['play_game'].count('view = copy.deepcopy(view)') != 1:
        raise ValueError('Expected exactly one public-copy boundary')
    functions['play_game'] = functions['play_game'].replace('view = copy.deepcopy(view)', 'view = clone_public(view)')
    header = '''"""EXPERIMENTAL structural public-copy runner v1; zero primary credit.

Selected functions are exact copies of the hash-pinned base runner, with only
the public-view copy call replaced. No registration/execution/promotion CLI is
included. The production runner and live campaign remain unchanged.
"""
import hashlib
import math
from pathlib import Path
import time
from evolution.genomes import digest
from evolution.opponents import Rival
from tests import reference_engine as engine
from runtime_bench.public_copy_v1 import clone_public

ROOT = Path(__file__).resolve().parents[1]
BASE_RUNNER_SHA256 = %r
if hashlib.sha256((ROOT/'evolution/runner.py').read_bytes()).hexdigest() != BASE_RUNNER_SHA256:
    raise ValueError('Experimental base runner no longer matches frozen source')
_CODE = {}

''' % EXPECTED
    exported = (header+'\n\n'.join(functions[name] for name in NAMES)+'\n').encode('utf8')
    path = ROOT/'runtime_bench/structural_runner_v1.py'
    if path.exists() and path.read_bytes() != exported:
        raise ValueError('Version1 experimental runner already exists with different code')
    if not path.exists():
        path.write_bytes(exported)
    proof = dict(base_path='evolution/runner.py', base_sha256=EXPECTED,
                 experimental_path='runtime_bench/structural_runner_v1.py',
                 experimental_sha256=hashlib.sha256(exported).hexdigest(), copied_functions=list(NAMES),
                 sole_function_change='play_game: view = copy.deepcopy(view) -> view = clone_public(view)',
                 clone_sha256=hashlib.sha256((ROOT/'runtime_bench/public_copy_v1.py').read_bytes()).hexdigest(),
                 original_edited=False, monkeypatch=False, primary_games_accepted=0)
    out = ROOT/'runtime_bench/evidence/structural_v1_source.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(proof, indent=2)+'\n', encoding='utf8')
    print(json.dumps(proof, indent=2))
    return proof


if __name__ == '__main__':
    build()
