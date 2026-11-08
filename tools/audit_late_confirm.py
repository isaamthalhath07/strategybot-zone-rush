"""Prospective fresh confirmation for the two late cohort leaders."""
import hashlib
import io
import json
from pathlib import Path
import random
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import audit_campaign as campaign
from tools.branch_audit import git
from tools.audit_run import run
from tools.audit_late_branch import COMMIT

OUT = ROOT/'validation/branch_audit'

def prior_branch_boards():
    found = set()
    def visit(x):
        if isinstance(x,dict):
            b = x.get('base')
            if isinstance(b,list) and len(b)==64 and all(type(v)==int and 1<=v<=3 for v in b):
                found.add(tuple(b))
            for v in x.values():
                visit(v)
        elif isinstance(x,list):
            for v in x:
                visit(v)
    for path in ('evolution/mathematical_candidates/source_archive.zip','evolution/evidence/first_round_artifacts.zip','evolution/evidence/league_and_arrival_artifacts.zip'):
        with zipfile.ZipFile(io.BytesIO(git('show',COMMIT+':'+path))) as z:
            for name in z.namelist():
                if name.endswith('.json'):
                    visit(json.loads(z.read(name).decode('utf-8-sig')))
    return found

def main():
    path = OUT/'late_final_spec.json'
    if path.exists():
        raise ValueError('confirmation is immutable')
    selection = json.loads((OUT/'late_selection.json').read_text())
    if not selection['advancing']:
        print('No advancing policies')
        return
    candidates = selection['advancing']+['bot_f95dc9fc2266','bot_e8b3682d8b39','bot_1bb70109a75e']
    sources = {}
    for file in ('inventory.json','inventory_extension.json','inventory_outsiders.json','inventory_late_branch.json'):
        sources.update({p['name']:p for p in json.loads((OUT/file).read_text())['policies']})
    old = json.loads((OUT/'final_spec.json').read_text())
    league = old['fixtures'][0]['opponents']
    branch_boards = prior_branch_boards()
    blocked = campaign.known_boards() | branch_boards
    forbidden = sorted(hashlib.sha256(json.dumps(list(b),separators=(',',':')).encode()).hexdigest() for b in blocked)
    rng = random.Random('late-independent-final:482ef54435b1188b:20261108')
    families = ('space_split','rental_horizon','junction_keeper','late_flipper')
    campaign.FAMILIES['late_final'] = families
    fixtures = []
    for group in range(24):
        kind = ('gradient','noise','edge','highhome','pockets','corridors')[group%6]
        while True:
            base = campaign.board(rng,kind)
            if tuple(base) not in blocked:
                break
        blocked.add(tuple(base))
        lineups = {'league':league}
        for field in ('novel_economy','novel_dynamic'):
            made = [campaign.novel('late_final',group,s,field,rng) for s in range(3)]
            sources.update({p['name']:p for p in made})
            lineups[field] = [p['name'] for p in made]
        for field in lineups:
            for seat in range(4):
                for token in range(1,5):
                    fixtures.append(dict(id=len(fixtures),map_group=group,map_family=kind,base=base,seat=seat,token=token,field=field,opponents=lineups[field]))
    required = set(candidates) | {n for f in fixtures for n in f['opponents']}
    spec = dict(id='all_branches_late_final',stage='late_final',diagnostic=False,candidates=candidates,
                sources=[sources[n] for n in sorted(required)],fixtures=fixtures,rules=old['rules'],
                previous_branch_registered_boards=len(branch_boards),forbidden_board_sha256=forbidden,
                challenger_families=families,
                inference='No parameters fitted. This is a new confirmation, not pooled with consumed earlier finals. Report all means and simultaneous map-clustered bootstrap intervals across all challenger-vs-main and challenger-vs-Feint tests. Retain main for shipping unless a late candidate has positive adjusted aggregate intervals against both references, positive novel-only interval against main and nonnegative novel-field mean differences. Blocker is a descriptive strong-field control.',
                source_selection='Top two late-development means within 0.05 PW of Feint or above, chosen before fresh board/opponent generation. Original policies and selected genotypes stay byte-identical.')
    path.write_text(json.dumps(spec,indent=2),encoding='utf8',newline='\n')
    print('FROZEN FRESH CONFIRMATION: %d games, %d prior branch boards excluded' % (len(candidates)*len(fixtures),len(branch_boards)),flush=True)
    run(path,OUT/'late_final_results.json.gz',8)

if __name__=='__main__':
    main()
