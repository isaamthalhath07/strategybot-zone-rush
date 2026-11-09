"""Bind isolated runtime reports to their already-audited source campaign."""
import json
from pathlib import Path

from runtime_bench.pilot import ROOT, sha


def main():
    cache = ROOT/'.cache/runtime_bench'
    evidence = ROOT/'runtime_bench/evidence'
    evidence.mkdir(exist_ok=True)
    names = ('cpython_1w_a', 'cpython_1w_b', 'pypy_1w_b', 'cpython_2w', 'pypy_2w')
    reports = {}
    for name in names:
        source = cache/name/'report.json'
        body = source.read_bytes()
        report = json.loads(body)
        if not report['all_recorded_actions_equal'] or report['primary_games_accepted'] != 0:
            raise ValueError('Runtime probe failed its uncredited parity contract')
        for path, expected in report['source_guards'].items():
            if sha(Path(path).read_bytes()) != expected:
                raise ValueError('Pinned source no longer matches runtime proof')
        (evidence/(name+'.json')).write_bytes(body)
        metrics = (cache/name/'game_metrics.json').read_bytes()
        (evidence/(name+'_game_metrics.json')).write_bytes(metrics)
        reports[name] = dict(sha256=sha(body), game_metrics_sha256=sha(metrics),
                             runtime=report['runtime'], games_per_s=report['games_per_s'],
                             timed_games=report['timed_games'], workers=report['workers'])
    for name in ('cpython_1w_b', 'pypy_1w_b', 'cpython_2w', 'pypy_2w'):
        report = json.loads((evidence/(name+'.json')).read_bytes())
        if report['benchmark_helper_sha256'] != sha((ROOT/'runtime_bench/pilot.py').read_bytes()):
            raise ValueError('Matched runtime comparison does not use current exact helper')
    stage = ROOT/'.cache/primary/campaign_v1_20261109/train_000'
    audit = json.loads((stage/'audit.json').read_bytes())
    if audit['approved'] is not True or audit['games_sha256'] != sha((stage/'games.jsonl').read_bytes()):
        raise ValueError('Source campaign evidence is not the approved immutable transcript')
    result = dict(source_stage=str(stage), source_registration_sha256=sha((stage/'registration.json').read_bytes()),
                  source_games_sha256=audit['games_sha256'], source_audit_sha256=sha((stage/'audit.json').read_bytes()),
                  reports=reports,
                  pypy_speed_relative_to_cpython_1w=reports['pypy_1w_b']['games_per_s']/reports['cpython_1w_b']['games_per_s'],
                  pypy_speed_relative_to_cpython_2w=reports['pypy_2w']['games_per_s']/reports['cpython_2w']['games_per_s'],
                  recommendation='Retain CPython for this unchanged harness; tested PyPy is slower. Profile a versioned public-view cloning optimization separately before any campaign migration.',
                  primary_games_accepted=0, bmcts_audits=0, production_files_edited=False)
    (evidence/'experiment.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    (evidence/'verified_pypy.json').write_bytes((cache/'verified_pypy.json').read_bytes())
    (evidence/'helper_current.py.txt').write_bytes((ROOT/'runtime_bench/pilot.py').read_bytes())
    for path in (cache/'helper_versions').glob('*.py'):
        (evidence/(path.stem+'.py.txt')).write_bytes(path.read_bytes())
    print(json.dumps({key: value for key, value in result.items() if key != 'reports'}, indent=2))


if __name__ == '__main__':
    main()
