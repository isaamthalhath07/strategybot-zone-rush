"""Exact original/build comparison for the supplementary historical controls."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audit_exports import public
from tools.audit_outsiders import COMMIT
from tools.audit_run import Referee

def main():
    modules = {}
    for name,path in (('engine','engine.py'),('outsiders','strategy_audit/outsiders.py')):
        body = subprocess.check_output(['git','show',COMMIT+':'+path],cwd=ROOT)
        module = types.ModuleType(name)
        sys.modules[name] = module
        exec(compile(body,path,'exec'),module.__dict__)
        modules[name] = module
    out = ROOT/'validation/branch_audit'
    inventory = json.loads((out/'inventory_outsiders.json').read_text())
    checks = []
    for p in inventory['policies']:
        cls = p['aliases'][0]['class_name']
        namespace = {}
        exec(compile((ROOT/p['path']).read_bytes(),p['path'],'exec'),namespace)
        originals = {s:getattr(modules['outsiders'],cls)(seed=s*7919) for s in range(1,5)}
        game = Referee([2]*64)
        calls = 0
        while not game.over():
            actions = []
            for seat in range(1,5):
                a = originals[seat](public(game,seat))
                b = namespace['act'](public(game,seat))
                if a!=b:
                    raise AssertionError((cls,game.turn,seat,a,b))
                calls += 1
                actions.append(a)
            game.step(actions)
        checks.append(dict(class_name=cls,calls=calls,exact_actions=True,sha256=p['sha256']))
    (out/'outsiders_equivalence.json').write_text(json.dumps(checks,indent=2),encoding='utf8',newline='\n')
    print('Outsider builds match %d original public decisions' % sum(x['calls'] for x in checks))

if __name__=='__main__':
    main()
