"""Close class-only coverage for the eight outsider audit controls.

Selection uses only the original screen/development fixtures, never final scores.
The raw final results must not be opened until this supplementary screen ends.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audit_exports import Flatten,PREFIX
from tools.audit_run import run

OUT = ROOT/'validation/branch_audit'
COMMIT = '9b7432bc40373e6be83cad844b0106dfbbaaf672'

def main():
    target = OUT/'inventory_outsiders.json'
    if target.exists():
        raise ValueError('immutable supplementary inventory')
    PREFIX.update(engine='_outsim_',outsiders='_out_')
    bodies = {name:subprocess.check_output(['git','show',COMMIT+':'+path],cwd=ROOT) for name,path in (('engine','engine.py'),('outsiders','strategy_audit/outsiders.py'))}
    flat = {}
    for name,body in bodies.items():
        tree = Flatten(body.decode(),name+'.py',PREFIX[name]).visit(ast.parse(body))
        ast.fix_missing_locations(tree)
        flat[name] = ast.unparse(tree)
    policies = []
    for cls in ('Fort','Leech','HomeBait','Jackal','Vulture','Flaky','Literal','Sim'):
        source = flat['engine']+'\n\n'+flat['outsiders']
        source += '\n_PLAYERS = {}\ndef act(state):\n    s = state.bot_id\n    if s not in _PLAYERS:\n        _PLAYERS[s] = _out_%s(seed=s*7919)\n    return _PLAYERS[s](state)\n' % cls
        body = source.encode()
        sha = hashlib.sha256(body).hexdigest()
        p = ROOT/'consolidation_candidates/branch_audit'/(sha+'.py')
        p.write_bytes(body)
        policies.append(dict(name='bot_'+sha[:12],path=str(p.relative_to(ROOT)).replace('\\','/'),sha256=sha,
                             aliases=[dict(commit=COMMIT,path='strategy_audit/outsiders.py',class_name=cls)],registered_names=['Outsider_'+cls],
                             scope='Historical class control; its internal rollout model retains original physics. It never receives private live state.',
                             build_inputs=[dict(commit=COMMIT,path=n,sha256=hashlib.sha256(b).hexdigest()) for n,b in bodies.items()]))
    target.write_text(json.dumps(dict(policies=policies,scope='Supplementary class-only controls found in final coverage review; frozen and screened before opening final outcomes.'),indent=2),encoding='utf8',newline='\n')
    previous = {}
    for stage,base in (('outsiders_contract','contracts_extra'),('outsiders_screen','screen')):
        spec = json.loads((OUT/(base+'_spec.json')).read_text())
        spec['id'] = 'all_branches_'+stage
        spec['stage'] = stage
        spec['sources'].extend(policies)
        qualified = {n for n,s in previous.items() if not s['focal_faults']} if previous else {p['name'] for p in policies}
        spec['candidates'] = [p['name'] for p in policies if p['name'] in qualified]
        path = OUT/(stage+'_spec.json')
        path.write_text(json.dumps(spec,indent=2),encoding='utf8',newline='\n')
        result = run(path,OUT/(stage+'_results.json.gz'),4)
        previous = result['summary']
    original = json.loads((OUT/'screen_results.json.summary.json').read_text())['summary']
    cutoff = list(original.values())[7]['mean_pw']
    promoted = [n for n,s in previous.items() if not s['focal_faults'] and s['mean_pw']>=cutoff]
    (OUT/'outsiders_selection.json').write_text(json.dumps(dict(screen_cutoff=cutoff,promoted=promoted,rule='Same eighth-place screening threshold as the original screen. No final results opened.'),indent=2),encoding='utf8',newline='\n')
    print('OUTSIDERS ADVANCING:',promoted,flush=True)

if __name__=='__main__':
    main()
