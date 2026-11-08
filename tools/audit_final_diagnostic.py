"""Trace every focal turn in one balanced case per fresh board, without fitting."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import audit_run

OUT = ROOT/'validation/branch_audit'

def main():
    original = json.loads((OUT/'late_final_spec.json').read_text())
    fixtures = []
    for group in range(24):
        seat = group%4
        token = 1+(group//4+group)%4
        field = ('league','novel_economy','novel_dynamic')[group%3]
        fixtures.append(next(f for f in original['fixtures'] if f['map_group']==group and f['seat']==seat and f['token']==token and f['field']==field))
    spec = dict(original,id='all_branches_final_diagnostic',stage='final_diagnostic',diagnostic=True,fixtures=fixtures)
    helper_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    spec['instrumentation'] = dict(trace='Every focal callback, every turn. No line events. Competitor timings are diagnostic only.',helper_sha256=helper_hash)
    path = OUT/'final_diagnostic_spec.json'
    if path.exists():
        raise ValueError('immutable diagnostic')
    path.write_text(json.dumps(spec,indent=2),encoding='utf8',newline='\n')
    normal_send = audit_run.AuditProcess.send
    def send(self,message):
        if self.diagnostic and message.get('cmd')=='act':
            message = dict(message,audit_trace=True)
        return normal_send(self,message)
    audit_run.AuditProcess.send = send
    try:
        data = audit_run.run(path,OUT/'final_diagnostic_results.json.gz',8)
    finally:
        audit_run.AuditProcess.send = normal_send
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=helper_hash:
        raise AssertionError('instrumentation changed')
    events = [e for r in data['games'] for x in r['handled_exceptions'] for e in x['events']]
    summary = dict(games=len(data['games']),focal_callbacks=sum(r['timing'][r['focal_seat']]['calls'] for r in data['games']),
                   faults=sum(len(r['faults']) for r in data['games']),observed_python_exception_events=len(events),events=events,
                   selection='One fixture per map, balanced across seats/tokens and fields. Diagnostic scores and timings never enter ranking.')
    (OUT/'final_diagnostic_safety.json').write_text(json.dumps(summary,indent=2),encoding='utf8',newline='\n')
    print('ALL-TURN SAFETY:',json.dumps(summary),flush=True)

if __name__=='__main__':
    main()
