"""Publish the frozen comparison, including uncertainty and source coverage."""
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audit_campaign import MAIN_SHA
from tools.benchmark import summarize

OUT = ROOT/'validation/branch_audit'

def interval(rows,a,b,alpha=.05,field=None):
    aa = {r['fixture']:r for r in rows if r['candidate']==a and (field is None or r['field'] in field)}
    bb = {r['fixture']:r for r in rows if r['candidate']==b and (field is None or r['field'] in field)}
    groups = {}
    for key in aa.keys() & bb.keys():
        r = aa[key]
        groups.setdefault(r['map_group'],[]).append(r['focal_pw']-bb[key]['focal_pw'])
    values = [sum(v)/len(v) for v in groups.values()]
    rng = random.Random(2026110803)
    boot = sorted(sum(rng.choices(values,k=len(values)))/len(values) for _ in range(40000))
    return dict(mean=sum(values)/len(values),clusters=len(values),alpha=alpha,
                interval=[boot[int(len(boot)*alpha/2)],boot[min(len(boot)-1,int(len(boot)*(1-alpha/2)))]])

def main():
    inventory = json.loads((OUT/'inventory.json').read_text())
    policies = inventory['policies']+json.loads((OUT/'inventory_extension.json').read_text())['policies']+json.loads((OUT/'inventory_outsiders.json').read_text())['policies']
    by_name = {p['name']:p for p in policies}
    def label(name):
        p = by_name[name]
        names = p.get('registered_names',[])
        if p['sha256']==MAIN_SHA:
            return 'Current main: Guarded Transfer'
        pretty = {'bot_a35c2c481164':'Novel B Racer (destination forecasts)',
                  'bot_1bb70109a75e':'Novel B Blocker (spatial denial)',
                  'bot_95da830e6f29':'Forward planner, fixed export',
                  'bot_d2bef4e077e9':'Forward planner, original export',
                  'bot_a8f7a74e7ed3':'Ultimate',
                  'bot_f95dc9fc2266':'Novel B Feint'}
        if name in pretty:
            return pretty[name]
        refs = [a['ref'].replace('refs/remotes/origin/','') for a in p['aliases'] if a.get('path')=='bot.py' and a.get('ref','').startswith('refs/remotes/origin/')]
        return ', '.join(refs) if refs else ', '.join(names) or name
    stages = {}
    for stage in ('contracts','contracts_extra','screen','development','outsiders_contract','outsiders_screen','final'):
        with gzip.open(OUT/(stage+'_results.json.gz'),'rt',encoding='utf8') as f:
            stages[stage] = json.load(f)
    final = stages['final']
    summary = final['summary']
    incumbent = next(p['name'] for p in policies if p['sha256']==MAIN_SHA)
    challengers = [n for n in summary if n!=incumbent]
    comparisons = {}
    for name in challengers:
        comparisons[name] = dict(aggregate=interval(final['games'],name,incumbent,.05/max(1,len(challengers))),
                                 novel_only=interval(final['games'],name,incumbent,field={'novel_economy','novel_dynamic'}),
                                 fields={f:interval(final['games'],name,incumbent,field={f}) for f in ('league','novel_economy','novel_dynamic')})
    eligible = [n for n in challengers if not summary[n]['focal_faults'] and comparisons[n]['aggregate']['interval'][0]>0
                and comparisons[n]['novel_only']['interval'][0]>0
                and all(comparisons[n]['fields'][f]['mean']>=0 for f in ('novel_economy','novel_dynamic'))]
    selected = max(eligible,key=lambda n:summary[n]['mean_pw']) if eligible else incumbent
    totals = dict(games=sum(len(s['games']) for s in stages.values()),
                  callbacks=sum(t['calls'] for s in stages.values() for r in s['games'] for t in r['timing']),
                  faults=sum(len(r['faults']) for s in stages.values() for r in s['games']))
    decision = dict(selected=selected,selected_sha256=by_name[selected]['sha256'],point_leader=next(iter(summary)),incumbent=incumbent,
                    comparisons=comparisons,totals=totals,criterion='Positive Bonferroni-adjusted paired board-clustered bootstrap interval against incumbent; positive ordinary 95% novel-only interval; nonnegative mean difference in each novel field; no focal faults. Otherwise retain incumbent.')
    (OUT/'decision.json').write_text(json.dumps(decision,indent=2),encoding='utf8',newline='\n')
    lines = ['# All-branches frozen bot audit','',
        'Snapshot: 8 November 2026. All policies and opponent draws were frozen before their registered panels. No weights were trained or fitted in this campaign.','',
        '## Result','',
        '**Best measured: %s** (`%s`).' % (label(next(iter(summary))),by_name[next(iter(summary))]['sha256']),
        '**Conservative promotion decision: retain %s** under the preregistered uncertainty threshold. A larger sample mean alone does not establish superiority.' % label(selected), '',
        '| Frozen finalist | PW / 3 | League | Novel economy | Novel dynamic | Focal faults | Worst callback ms |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for name,s in summary.items():
        lines.append('| %s (`%s`) | %.4f | %.4f | %.4f | %.4f | %d | %.3f |' % (label(name),name,s['mean_pw'],s['fields']['league'],s['fields']['novel_economy'],s['fields']['novel_dynamic'],s['focal_faults'],s['max_ms']))
    lines += ['', 'PW is the number of opponents outscored (0 to 3); ties count one half. It is the pairwise outcome used by the event, not an absolute Elo rating.','',
              '| Challenger minus current main | Difference | Simultaneous 95% interval | Novel-only difference (ordinary 95% interval) |',
              '|---|---:|---|---|']
    for name,c in comparisons.items():
        a,n = c['aggregate'],c['novel_only']
        lines.append('| %s | %+.4f | [%+.4f, %+.4f] | %+.4f [%+.4f, %+.4f] |' % (label(name),a['mean'],*a['interval'],n['mean'],*n['interval']))
    lines += ['', 'Intervals resample complete map groups, keeping every seat, priority-token and field crossing together. The aggregate intervals adjust across all final challengers with Bonferroni. Promotion also requires a positive ordinary 95% novel-only interval and a nonnegative mean difference in both novel fields. Per-field intervals are descriptive. This is finite sampled-field evidence, not a proof against all competitors.','',
              '## Every remote branch head','',
              'Every distinct passing remote root `bot.py` received the same 96-game development panel. These are selection scores, not independent confirmation results. Equal hashes mean the same bot appears in more than one branch. Archived policies and other exports are listed in COVERAGE.md.','',
              '| Branch | Pinned commit | Root SHA | Development PW / 3 |',
              '|---|---|---|---:|']
    for ref in sorted((r for r in inventory['refs'] if r['ref'].startswith('refs/remotes/origin/')),key=lambda r:r['ref']):
        name = next((p['name'] for p in policies if any(a.get('ref')==ref['ref'] and a.get('path')=='bot.py' for a in p['aliases'])),None)
        if name:
            value = stages['development']['summary'].get(name,{}).get('mean_pw')
            lines.append('| %s | `%s` | `%s` | %s |' % (ref['ref'].replace('refs/remotes/origin/',''),ref['commit'][:12],by_name[name]['sha256'][:12],'%.4f' % value if value is not None else 'not qualified'))
    lines += ['',
              '## Coverage and protocol','',
              '- %d live remote branches and %d local/remote references were pinned; %d unique Python sources parsed with zero syntax errors.' % (inventory['remote_branch_count'],len(inventory['refs']),inventory['unique_python_sources']),
              '- %d exact-byte standalone exports plus %d class builds were inventoried. Class builds matched their originals on 10,560 public callbacks. The NN export embeds the existing frozen weights; its training-side Torch self-test is removed.' % (len(inventory['policies']),len(policies)-len(inventory['policies'])),
              '- Independent per-seat processes receive only board, bot ID, priority-token flag and legal actions. Input fingerprints detect mutation. Diagnostic games sample caught exceptions; strength games use the actual 200 ms limit (2 seconds first turn).',
              '- Only current effective-STAY Shield rules are used. Moving successfully escapes Shield; a blocked or lost move counts as STAY; frozen STAY does not advance work.',
              '- Boards are rejected by actual contents if present in earlier validation JSON. Final boards and four final challenger decision families are separate from screening/development.',
              '- Generated challengers use fresh per-map configurations without testing those settings against a candidate. Every candidate gets the same fixtures. Historical policies remain in the league field for evaluation only; there is no training on them.',
              '- Each final policy plays 1,152 games: 24 fresh boards x 4 seats x 4 priority-token starts x 3 fields. Mean weights the three fields equally.','',
              '| Panel | Candidates | Games | Callbacks | All worker faults |',
              '|---|---:|---:|---:|---:|']
    for name,d in stages.items():
        lines.append('| %s | %d | %d | %d | %d |' % (name,len(d['summary']),len(d['games']),sum(t['calls'] for r in d['games'] for t in r['timing']),sum(len(r['faults']) for r in d['games'])))
    lines += ['', '**Total: %(games)d games, %(callbacks)d callbacks.**' % totals,'',
              'Contract games diagnose safety, not playing strength. The incomplete `agent_new.py` fragment crashes because `PARAMS` is missing. `opp_buggy_01.py` intentionally returns diagonal illegal actions and is a negative control. Neither is eligible for promotion. Other deliberate negative controls (slow, oscillator and Flaky) can return legal actions while deliberately playing poorly; legal execution is distinct from strategic correctness. Original sources and failures are preserved instead of silently rewriting their history.','',
              'Eight class-only outsider controls were discovered in the final coverage review. They were frozen, checked for exact build equivalence, and tested against the original contract and screen fixtures before final outcomes were opened. None met the original eighth-place screen threshold, so the frozen final pool stayed unchanged. See inventory_outsiders.json, outsiders_selection.json and outsiders_equivalence.json.','',
              '## Challenger families','',
              '| Stage | Families and decisions |','|---|---|',
              '| Screen | District rate rewards nearby free income; time discount penalizes long travel; turn budget balances upgrades and claims; local pairs values a second nearby job. |',
              '| Development | Return schedule commits to capture plus upgrade; capture deadline anticipates races; sector bids values neighborhood resources and congestion; sampling portfolio randomizes among valuable jobs. |',
              '| Final | Boundary cluster works near enemy borders; periodic switch changes between inner and outer priorities; cooldown feint steps away from a ready landlord; chase income attacks projected leaders. |','',
              'These are distinct decision rules using shared parsing and pathfinding, not independently authored AI submissions. Novel families reduce dependence on the historical zoo; they cannot establish that overfitting is impossible.','',
              '## Reproduce and inspect','',
              'Run `python tools/unpack_sources.py`, then `python tools/check_release.py`. The source archive manifest checks every restored file. Specs, registrations, compressed full trajectories, per-panel summaries and `decision.json` are retained here. Sources and runner/referee hashes were checked before and after each panel.','',
              'To rerun a panel, use `python tools/audit_run.py --spec validation/branch_audit/final_spec.json --out .cache/recheck.json.gz --workers 8`. Use a new output path. `--resume` only accepts an identical registration and code. Some historical policies use unseeded global randomness or wall-clock throttling; reruns need not reproduce their exact moves. Raw recorded actions preserve what actually happened.','',
              '[Complete policy coverage](COVERAGE.md). [Decision and intervals](decision.json). [Pinned branch/source inventory](inventory.json). [Class exports](inventory_extension.json).','',
              '## Limits','',
              'All branch tips and known archived standalone builds are covered, plus listed class defaults from the historical audit branch. This is not an enumeration of every historical commit, every possible parameter combination, or every training checkpoint. Early stages are selection data; their scores are not pooled with final scores. Zero observed faults is not proof of bug-free code. Timing is measured on this machine. No official server simulator is available; the independent-engine release tests check the local interpretation.','']
    (OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf8',newline='\n')
    coverage = ['# Policy coverage','', '| SHA / label | Contract | Screen PW / 3 | Development PW / 3 | Final PW / 3 |','|---|---|---:|---:|---:|']
    contract = dict(stages['contracts']['summary'],**stages['contracts_extra']['summary'],**stages['outsiders_contract']['summary'])
    for name in sorted(by_name):
        status = contract.get(name,{})
        mark = ('%d faults' % status['focal_faults']) if status.get('focal_faults') else 'passed'
        screen = dict(stages['screen']['summary'],**stages['outsiders_screen']['summary'])
        values = [screen.get(name,{}).get('mean_pw'),stages['development']['summary'].get(name,{}).get('mean_pw'),stages['final']['summary'].get(name,{}).get('mean_pw')]
        coverage.append('| `%s` %s | %s | %s |' % (name[4:],label(name),mark,' | '.join('%.4f' % v if v is not None else '-' for v in values)))
    coverage += ['', 'A dash means not selected for that next panel; it does not mean a draw or a failed execution. Each column is a different matched field and must not be compared as if it were the same tournament. Detailed source aliases, commit hashes and build inputs are in the inventories.','']
    (OUT/'COVERAGE.md').write_text('\n'.join(coverage),encoding='utf8',newline='\n')
    winner_path = ROOT/'audit_best_measured.py'
    winner_source = (ROOT/by_name[next(iter(summary))]['path']).read_bytes()
    winner_path.write_bytes(winner_source)
    lines = (OUT/'REPORT.md').read_text(encoding='utf8')
    lines += '\nThe best measured frozen source is exported as [`audit_best_measured.py`](../../audit_best_measured.py), byte-identical to its tested snapshot. `bot.py` and the existing release manifest retain the initial merged release under the stricter promotion rule; this audit is on a separate branch. See [release checks](release_checks.txt) and [independent replay](independent_replay.json).\n'
    (OUT/'REPORT.md').write_text(lines,encoding='utf8',newline='\n')
    archive = OUT/'source_archive.zip'
    entries = []
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        sources = {s['path']:s['sha256'] for d in stages.values() for s in d['registration']['spec']['sources']}
        for p in policies:
            sources[p['path']] = p['sha256']
        for p,sha in sorted(sources.items()):
            body = (ROOT/p).read_bytes()
            if hashlib.sha256(body).hexdigest()!=sha:
                raise AssertionError(p)
            info = zipfile.ZipInfo(p,date_time=(2026,11,8,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info,body)
            entries.append(dict(path=p,sha256=sha))
    manifest = dict(archive=str(archive.relative_to(ROOT)).replace('\\','/'),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=entries)
    (OUT/'source_archive_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8',newline='\n')
    print(json.dumps(dict(selected=selected,point_leader=next(iter(summary)),totals=totals,comparisons=comparisons),indent=2))

if __name__=='__main__':
    main()
