"""Synthetic benchmark admission only; never run the actual known-eight task."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local_policy_pool import benchmark
from local_policy_pool.pool import sha
from tests import reference_engine as engine


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        parent=benchmark.ROOT/'local_policy_pool'/'.cache'; parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-BENCH-',dir=parent); self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name); source=self.directory/'toy.py'
        source.write_text('CONFIG={}\ndef act(view): return "STAY"\n',encoding='utf8')
        entry=dict(path=str(source),sha256=sha(source.read_bytes())); fixtures=[]; rows=[]
        for lane in range(2):
            base=engine.make_map(canonical=True); game=engine.Game(base=base,start_token=lane+1)
            tape=[['STAY']*4 for _ in range(80)]
            for joint in tape: game.step(joint)
            opponents=[dict(id='SYNTHETIC-R%d'%s,seat=s,family='planner',genes={},seed=1) for s in range(4) if s!=lane]
            fixture=dict(id='SYNTHETIC-%d'%lane,candidate=entry['sha256'],base=base,token=lane+1,seat=lane,
                         map_id=sha(bytes(base)),field='SYNTHETIC',opponents=opponents)
            fixtures.append(fixture); rows.append(dict(candidate=entry['sha256'],fixture=fixture['id'],map_id=fixture['map_id'],
                focal_seat=lane,field='SYNTHETIC',scores=game.score,focal_pw=1.5,focal_score=game.score[lane],
                opponent_ids=[s['id'] for s in opponents],actions=tape,faults=[]))
        self.registration=dict(candidates=[entry],sources={'planner':entry},fixtures=fixtures,guards={str(source):entry['sha256']})
        self.rows=rows; self.inputs={'SYNTHETIC_ONLY':'a'*64}

    def test_two_synthetic_repeats_match_full_tapes_and_report_cold_warm_complete_costs(self):
        output=self.directory/'output'
        with patch.object(benchmark,'_load_known',return_value=(self.registration,self.rows,self.inputs)):
            report=benchmark.run(output)
        self.assertEqual([m['arm'] for m in report['measurements']],['serial','pool','serial','pool'])
        self.assertEqual([m['phase'] for m in report['measurements']],['cold','cold','warm-reset','warm-reset'])
        self.assertEqual(report['all_actual_callbacks'],2*80*4*4)
        self.assertEqual(report['all_two_cpu_referee_state_comparisons'],2*81*4)
        self.assertTrue(report['all_entire_canonical_action_tapes_scores_exact'])
        self.assertEqual(report['measurements'][1]['worker_pids'],report['measurements'][3]['worker_pids'])
        self.assertEqual(report['primary_games'],0); self.assertEqual(report['study_games'],0)
        for measurement in report['measurements']:
            self.assertGreater(measurement['wire_conversion_public_checks_s'],0)
            self.assertGreater(measurement['referee_step_checks_s'],0)
            self.assertGreater(measurement['turn_evidence_write_s'],0)
            self.assertEqual(measurement['actual_callbacks'],640)
        self.assertTrue((output/'pool_events'/'events.jsonl').exists())
        self.assertFalse((output/'error.json').exists())
        with self.assertRaises(ValueError): benchmark.run(output)

    def test_wrong_canonical_tape_aborts_without_retry_or_results(self):
        wrong=copy.deepcopy(self.rows); wrong[0]['actions'][0][0]='EAST'
        output=self.directory/'failed'
        with patch.object(benchmark,'_load_known',return_value=(self.registration,wrong,self.inputs)):
            with self.assertRaisesRegex(ValueError,'canonical known control action tape'): benchmark.run(output)
        self.assertTrue((output/'error.json').exists()); self.assertFalse((output/'results.json').exists())
        failure=benchmark.oversight.strict_loads((output/'error.json').read_bytes())
        self.assertEqual(failure['partial']['turn'],1)
        self.assertEqual(failure['partial']['counters'][0]['attempts'],[1]*4)
        self.assertEqual(failure['primary_games'],0)

    def test_known_input_pin_changes_fail_before_actor_or_output(self):
        with (patch.dict(benchmark.PINNED_KNOWN,{'registration.json':'0'*64}),
              patch.object(benchmark,'ActorPool',side_effect=AssertionError('Actor pool started'))):
            with self.assertRaisesRegex(ValueError,'canonical input bytes changed'):
                benchmark.run(self.directory/'pin-rejected')
        self.assertFalse((self.directory/'pin-rejected').exists())


if __name__=='__main__': unittest.main()
