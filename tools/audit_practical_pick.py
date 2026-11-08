"""Export the original Blocker without optimizing its random seed.

This is an explicit practical judgment following the registered tests. It does
not rewrite the automatic promotion gate or its immutable decision record.
"""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'validation/branch_audit'
PICK = 'bot_1bb70109a75e'
SEED_VARIANT = 'bot_191059b37141'
FEINT = 'bot_f95dc9fc2266'

def main():
    target = OUT/'practical_recommendation.json'
    if target.exists():
        raise ValueError('preserve the recorded judgment')
    data = json.loads(gzip.decompress((OUT/'late_final_results.json.gz').read_bytes()))
    first = json.loads(gzip.decompress((OUT/'final_results.json.gz').read_bytes()))
    sources = {s['name']:s for s in data['registration']['spec']['sources']}
    body = (ROOT/sources[PICK]['path']).read_bytes()
    if hashlib.sha256(body).hexdigest()!=sources[PICK]['sha256']:
        raise AssertionError('tested source mismatch')
    (ROOT/'audit_recommended.py').write_bytes(body)
    choice = dict(kind='Practical judgment after tests; separate from the preregistered automatic promotion decision.',
                  selected=PICK,sha256=sources[PICK]['sha256'],
                  latest_mean=data['summary'][PICK]['mean_pw'],
                  seeded_variant_mean=data['summary'][SEED_VARIANT]['mean_pw'],
                  seed_variant_minus_original=data['summary'][SEED_VARIANT]['mean_pw']-data['summary'][PICK]['mean_pw'],
                  first_final_difference_vs_feint=first['summary'][PICK]['mean_pw']-first['summary'][FEINT]['mean_pw'],
                  latest_difference_vs_feint=data['summary'][PICK]['mean_pw']-data['summary'][FEINT]['mean_pw'],
                  reason='Original Blocker led the strong historical league and the minimum field mean in both fresh cohorts. Its latest mean is essentially identical to the highest-scoring reseeded export. Prefer the unchanged original to selecting a seed on noise. No coefficients or seeds are changed.',
                  uncertainty='Blocker and Feint are not conclusively separated. The automatic gate requiring superiority over both references was not met. This practical pick does not claim universal optimality or bug-free code.')
    target.write_text(json.dumps(choice,indent=2),encoding='utf8',newline='\n')
    report = OUT/'LATE_CONFIRMATION.md'
    text = report.read_text(encoding='utf8')
    text = text.replace('**Conservative recommendation: Merged Guarded Transfer.**',
        '**Practical pick: original Blocker**, exported unchanged as `audit_recommended.py`. It led the strong historical league and minimum field mean in both fresh cohorts. Its latest score is effectively tied with the reseeded version; selecting that seed offers no credible demonstrated edge. Blocker is not conclusively stronger than Feint.\n\n**Automatic promotion gate: not met.** The registered rule required a positive adjusted advantage over both main and Feint. The baseline `bot.py` remains unchanged; that mechanical decision is separate from the practical recommendation above. [Recorded judgment](practical_recommendation.json).')
    text = text.replace('[Conservatively recommended source](../../audit_recommended.py).',
        '[Practical recommended source: original Blocker](../../audit_recommended.py), byte-identical to its tested snapshot.')
    report.write_text(text,encoding='utf8',newline='\n')
    print(json.dumps(choice,indent=2))

if __name__=='__main__':
    main()
