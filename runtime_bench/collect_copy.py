"""Preserve bounded structural-copy evidence without modifying campaign files."""
import json
from pathlib import Path

from runtime_bench import compare_copy
from runtime_bench.pilot import ROOT, sha


def main():
    cache = ROOT/'.cache/runtime_bench'
    evidence = ROOT/'runtime_bench/evidence/structural_v1'
    evidence.mkdir(exist_ok=True)
    names = ('copy_frozen_1w', 'copy_structural_1w', 'copy_structural_2w', 'copy_frozen_2w')
    reports, summaries = {}, {}
    for name in names:
        body = (cache/name/'report.json').read_bytes()
        report = json.loads(body)
        if (not report['all_recorded_actions_equal'] or report['primary_games_accepted'] != 0
                or report['monkeypatch'] is not False or report['original_source_edited'] is not False
                or report['benchmark_helper_sha256'] != compare_copy.HELPER_SHA256):
            raise ValueError('Copy experiment proof does not match current controlled helper')
        for path, expected in dict(report['source_guards'], **report['experimental_sources']).items():
            if sha(Path(path).read_bytes()) != expected:
                raise ValueError('Experiment source changed')
        reports[name] = report
        (evidence/(name+'.json')).write_bytes(body)
        metrics = (cache/name/'game_metrics.json').read_bytes()
        (evidence/(name+'_game_metrics.json')).write_bytes(metrics)
        summaries[name] = dict(report_sha256=sha(body), metrics_sha256=sha(metrics),
                               games_per_s=report['games_per_s'], timed_games=report['timed_games'],
                               workers=report['workers'])
    for workers in (1, 2):
        frozen = reports['copy_frozen_%dw' % workers]
        revised = reports['copy_structural_%dw' % workers]
        if (frozen['task_ids'] != revised['task_ids'] or frozen['timed_games'] != revised['timed_games']
                or frozen['warmup_games_per_worker'] != revised['warmup_games_per_worker']
                or frozen['runtime']['executable_sha256'] != revised['runtime']['executable_sha256']):
            raise ValueError('Copy experiment conditions were not matched')
    proof = dict(experiment='structural_public_copy_v1', reports=summaries,
                 speedup_1worker=reports['copy_structural_1w']['games_per_s']/reports['copy_frozen_1w']['games_per_s'],
                 speedup_2workers=reports['copy_structural_2w']['games_per_s']/reports['copy_frozen_2w']['games_per_s'],
                 timed_game_repetitions=sum(report['timed_games'] for report in reports.values()),
                 action_vectors_compared=sum(report['action_vectors_compared'] for report in reports.values()),
                 callbacks=sum(report['callbacks'] for report in reports.values()),
                 observed_mismatches=0, primary_games_accepted=0, bmcts_audits=0,
                 original_source_edited=False, monkeypatch=False, migration_performed=False,
                 validation_scope='Canonical8x8 reference-engine View/Cell schema only. Finite repeated-game parity. No heldout-policy improvement or campaign admission.',
                 recommendation='Promising for a reviewed, versioned harness migration; leave live campaign frozen until broader independent replay and schema compatibility review.')
    (evidence/'experiment.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf8')
    for name in ('public_copy_v1.py', 'structural_runner_v1.py', 'compare_copy.py'):
        (evidence/(name+'.txt')).write_bytes((ROOT/'runtime_bench'/name).read_bytes())
    print(json.dumps({key: value for key, value in proof.items() if key != 'reports'}, indent=2))


if __name__ == '__main__':
    main()
