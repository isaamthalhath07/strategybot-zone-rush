"""Analyze the second untouched cohort; preserve the original final separately."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audit_report import interval

OUT = ROOT/'validation/branch_audit'
MAIN = 'bot_e8b3682d8b39'
FEINT = 'bot_f95dc9fc2266'
LABELS = {MAIN:'Merged Guarded Transfer',FEINT:'Original Feint',
          'bot_1bb70109a75e':'Original Blocker',
          'bot_92f38af1a559':'Archived evolved Transfer (depth 2)',
          'bot_191059b37141':'Blocker with archived seat-1 seed'}

def main():
    target = OUT/'late_decision.json'
    if target.exists():
        raise ValueError('the confirmation decision is immutable')
    data = json.loads(gzip.decompress((OUT/'late_final_results.json.gz').read_bytes()))
    selected = json.loads((OUT/'late_selection.json').read_text())['advancing']
    tests = max(1,2*len(selected))
    comparisons = {}
    for name in selected:
        comparisons[name] = dict(
            references={r:interval(data['games'],name,r,alpha=.05/tests) for r in (MAIN,FEINT)},
            novel_only_vs_main=interval(data['games'],name,MAIN,field={'novel_economy','novel_dynamic'}),
            field_mean_differences={f:data['summary'][name]['fields'][f]-data['summary'][MAIN]['fields'][f]
                                    for f in ('league','novel_economy','novel_dynamic')})
    eligible = [n for n in selected if data['summary'][n]['focal_faults']==0
                and all(c['interval'][0]>0 for c in comparisons[n]['references'].values())
                and comparisons[n]['novel_only_vs_main']['interval'][0]>0
                and all(comparisons[n]['field_mean_differences'][f]>=0 for f in ('novel_economy','novel_dynamic'))]
    recommendation = max(eligible,key=lambda n:data['summary'][n]['mean_pw']) if eligible else MAIN
    point = next(iter(data['summary']))
    sources = {s['name']:s for s in data['registration']['spec']['sources']}
    source = (ROOT/sources[point]['path']).read_bytes()
    if hashlib.sha256(source).hexdigest()!=sources[point]['sha256']:
        raise AssertionError('export does not match tested file')
    (ROOT/'audit_best_measured.py').write_bytes(source)
    (ROOT/'audit_recommended.py').write_bytes((ROOT/sources[recommendation]['path']).read_bytes())
    decision = dict(best_measured=point,best_measured_sha256=sources[point]['sha256'],
                    conservative_recommendation=recommendation,comparisons=comparisons,
                    caveat='Second-cohort means are compared only within that cohort. Original final is preserved and not pooled. A finite field is not a universal ranking.')
    diagnostic = OUT/'final_diagnostic_results.json.gz'
    if diagnostic.exists():
        rows = json.loads(gzip.decompress(diagnostic.read_bytes()))['games']
        originals = {(r['candidate'],r['fixture']):r for r in data['games']}
        decision['all_turn_diagnostic_reproduction'] = dict(games=len(rows),
            exact_actions_and_scores=sum(r['actions']==originals[(r['candidate'],r['fixture'])]['actions'] and r['scores']==originals[(r['candidate'],r['fixture'])]['scores'] for r in rows),
            exception_events=sum(len(x['events']) for r in rows for x in r['handled_exceptions']),
            worker_faults=sum(len(r['faults']) for r in rows))
    target.write_text(json.dumps(decision,indent=2),encoding='utf8',newline='\n')
    lines = ['# Late-branch fresh confirmation','',
             'The initial five-policy final is retained in REPORT.md. A branch published during the audit added 58 exact-byte standalone exports, including numerical genomes, mathematical planners and reseeded opponents. All 58 were frozen before evaluation. Two passed the preregistered shared-development gate.','',
             '**Best measured on this fresh panel: %s** (`%s`).' % (LABELS[point],sources[point]['sha256']),
             '**Conservative recommendation: %s.**' % LABELS[recommendation], '',
             '| Frozen policy | PW / 3 | Historical league | Novel economy | Novel dynamic | Faults | Worst ms |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for name,s in data['summary'].items():
        lines.append('| %s | %.4f | %.4f | %.4f | %.4f | %d | %.3f |' % (LABELS[name],s['mean_pw'],s['fields']['league'],s['fields']['novel_economy'],s['fields']['novel_dynamic'],s['focal_faults'],s['max_ms']))
    lines += ['', 'Each policy played the same 1,152 fixtures: 24 new boards x 4 seats x 4 starting priority tokens x 3 equally weighted fields. Neither field weights nor board distribution are estimates of the unknown competition population.','',
              '| Late challenger minus reference | Difference | Simultaneous 95% interval |',
              '|---|---:|---|']
    for name,c in comparisons.items():
        for ref,v in c['references'].items():
            lines.append('| %s minus %s | %+.4f | [%+.4f, %+.4f] |' % (LABELS[name],LABELS[ref],v['mean'],*v['interval']))
    lines += ['', 'Intervals resample whole boards, retaining all seat/token/field combinations. Bonferroni adjusts across all four registered challenger-versus-reference tests. Promotion requires positive adjusted intervals against both main and Feint, a positive ordinary 95% novel-only interval against main, no negative novel-field mean changes and zero focal faults. Blocker is an additional descriptive control; its seed variant is not treated as a new architecture.','',
              'No policy weights or seeds were changed. Candidate selection used the separate six-board panel only. The 24 confirmation boards were excluded by actual contents from earlier local validation and 217 boards recovered from the late branch registration archives. No current opponent action or private referee field was supplied to a bot.','',
              'The new challenge rules were specified before this confirmation: space_split shifts outward when multiple rivals crowd the centre; rental_horizon favors holdings likely to remain safe; junction_keeper values nearby contested junctions; late_flipper changes from investment to raids late in the game. Parameters were drawn without measuring candidate fitness. All share basic parsing and pathfinding, so this is not an independent-implementer certificate or proof against overfitting.','',
              'The first-cohort Feint result (+0.1528 overall versus main, adjusted interval -0.0816 to +0.3698) remains historical evidence from its own field. It is not pooled to manufacture significance. No conclusion here proves an absolute best bot or bug-free code.','',
              '## Files and verification','',
              '- [Best measured source](../../audit_best_measured.py), byte-identical to its tested snapshot.',
              '- [Conservatively recommended source](../../audit_recommended.py).',
              '- [Frozen selection rule](late_confirmation_rule.json), [selected exports](late_selection.json), [new panel](late_final_spec.json), [decision](late_decision.json).',
              '- [Independent replay](late_final_independent_replay.json), [full results](late_final_results.json.gz), [source archive manifest](source_archive_manifest.json).',
              '- [All-turn exception diagnostics](final_diagnostic_safety.json) rerun 120 complete games; their scores and timings are excluded from the ranking. Reproduction counts are in late_decision.json.',
              '- The merged `bot.py` and its release manifest are preserved on this audit branch. This is an auditable source recommendation, not a merge into main.','']
    (OUT/'LATE_CONFIRMATION.md').write_text('\n'.join(lines),encoding='utf8',newline='\n')
    print(json.dumps(decision,indent=2))

if __name__=='__main__':
    main()
