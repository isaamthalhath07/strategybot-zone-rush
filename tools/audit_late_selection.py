"""Apply the preregistered late-branch gate without changing any policy."""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'validation/branch_audit'

def main():
    rule = json.loads((OUT/'late_confirmation_rule.json').read_text())
    with gzip.open(OUT/'late_development_results.json.gz','rt') as f:
        data = json.load(f)
    names = {p['name'] for p in json.loads((OUT/'inventory_late_branch.json').read_text())['policies']}
    reference = data['summary'][rule['reference']]['mean_pw']
    ranked = [n for n,s in data['summary'].items() if n in names and not s['focal_faults']]
    advancing = [n for n in ranked if data['summary'][n]['mean_pw']>=reference-.05][:2]
    result = dict(reference_mean=reference,threshold=reference-.05,advancing=advancing,
                  top_late=[dict(name=n,**data['summary'][n]) for n in ranked[:10]],
                  interpretation='Late scores are selection data only. No training or parameter fitting. No final promotion is made from this panel.')
    original = json.loads(gzip.decompress((OUT/'development_results.json.gz').read_bytes()))
    stable = {}
    for name in (rule['reference'],'bot_e8b3682d8b39'):
        aa = {r['fixture']:r for r in original['games'] if r['candidate']==name}
        bb = [r for r in data['games'] if r['candidate']==name]
        stable[name] = dict(games=len(bb),exact_actions_and_scores=sum(aa[r['fixture']]['actions']==r['actions'] and aa[r['fixture']]['scores']==r['scores'] for r in bb))
    result['reference_reproduction'] = stable
    path = OUT/'late_selection.json'
    if path.exists():
        raise ValueError('never overwrite a consumed selection')
    path.write_text(json.dumps(result,indent=2),encoding='utf8',newline='\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
