"""Inventory and screen late-arriving frozen exports, without fitting policies."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.branch_audit import git,tree,blobs,inspect
from tools.audit_run import run

OUT = ROOT/'validation/branch_audit'
COMMIT = '482ef54435b1188b8fdceb9f9bf7a6dbdaf7ee43'

def inventory():
    target = OUT/'inventory_late_branch.json'
    if target.exists():
        raise ValueError('immutable inventory')
    known = set()
    for path in ('inventory.json','inventory_extension.json','inventory_outsiders.json'):
        known.update(p['sha256'] for p in json.loads((OUT/path).read_text())['policies'])
    policies = {}
    parsed = []
    def add(body,path):
        sha = hashlib.sha256(body).hexdigest()
        info = inspect(body)
        parsed.append(dict(path=path,sha256=sha,audit=info))
        if not info['eligible'] or sha in known:
            return
        if sha not in policies:
            dest = ROOT/'consolidation_candidates/branch_audit'/(sha+'.py')
            dest.write_bytes(body)
            policies[sha] = dict(name='bot_'+sha[:12],sha256=sha,path=str(dest.relative_to(ROOT)).replace('\\','/'),audit=info,aliases=[],registered_names=[])
        policies[sha]['aliases'].append(dict(commit=COMMIT,path=path,ref='refs/remotes/origin/codex/evolve-existing-league'))
    entries = tree(COMMIT)
    bodies = blobs(b for b,p in entries)
    for blob,path in entries:
        add(bodies[blob],path)
    for archive_path in ('evolution/mathematical_candidates/source_archive.zip','evolution/evidence/first_round_artifacts.zip','evolution/evidence/league_and_arrival_artifacts.zip'):
        body = git('show',COMMIT+':'+archive_path)
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            for name in z.namelist():
                if name.endswith('.py'):
                    add(z.read(name),archive_path+'!'+name)
    data = dict(commit=COMMIT,branch='codex/evolve-existing-league',policies=list(policies.values()),source_inventory=parsed,
                scope='Late branch appeared after the first final completed. Root bot matches incumbent; additional tree and three research-archive standalone exports are frozen for supplementary evaluation. No original panels or decisions overwritten.')
    target.write_text(json.dumps(data,indent=2),encoding='utf8',newline='\n')
    print('Late branch adds %d distinct standalone candidates' % len(policies))

def panels():
    extra = json.loads((OUT/'inventory_late_branch.json').read_text())['policies']
    previous = {}
    for stage,base in (('late_contract','contracts_extra'),('late_development','development')):
        spec = json.loads((OUT/(base+'_spec.json')).read_text())
        spec['id'] = 'all_branches_'+stage
        spec['stage'] = stage
        spec['sources'].extend(extra)
        names = [p['name'] for p in extra if not previous or not previous[p['name']]['focal_faults']]
        if stage=='late_development':
            # Rerun both references on the same selection panel.
            names += ['bot_f95dc9fc2266','bot_e8b3682d8b39']
        spec['candidates'] = names
        target = OUT/(stage+'_spec.json')
        if target.exists():
            raise ValueError('immutable panel')
        target.write_text(json.dumps(spec,indent=2),encoding='utf8',newline='\n')
        result = run(target,OUT/(stage+'_results.json.gz'),8)
        previous = result['summary']
    print('LATE PANEL COMPLETE',flush=True)

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command',choices=('inventory','panels'))
    args = parser.parse_args()
    inventory() if args.command=='inventory' else panels()
