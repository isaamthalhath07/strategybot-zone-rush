"""Scheduling-grid unit tests with metadata-only mocks; no actual GPU/grid."""
import copy
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadline_runner import optimize as opt


def measurement(seconds): return dict(games=512,wall_seconds=seconds,full_actor_audits=512,both_referees=True)


class OptimizerTests(unittest.TestCase):
    def setUp(self):
        parent=opt.runner.ROOT/'deadline_runner'/'.cache'; parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-OPTIMIZE-',dir=parent); self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        self.controls=[dict(fixture='SYNTHETIC-CONTROL-%d'%i) for i in range(8)]
        self.reg=dict(fixtures=[dict(id=c['fixture']) for c in self.controls],candidates=[],sources={},guards={})
        self.baseline=dict(configuration=dict(opt.BASELINE_CONFIGURATION),measurement=measurement(44),
                           benchmark_result_sha256='b'*64,source_sha256={'SYNTHETIC_ONLY':'a'*64})
        self.calls=[]

    def mocks(self,fail_at=None):
        stack=ExitStack(); pins={'SYNTHETIC_ONLY':'a'*64}
        stack.enter_context(patch.object(opt,'source_pins',return_value=pins))
        stack.enter_context(patch.object(opt,'_baseline',return_value=copy.deepcopy(self.baseline)))
        stack.enter_context(patch.object(opt.benchmark,'_load_known',return_value=(self.reg,self.controls,{'SYNTHETIC_ONLY':'c'*64})))
        stack.enter_context(patch.object(opt.benchmark.serial_reference,'_guards',return_value=None))
        def snapshot(output,*_):
            (output/'sources').mkdir(); opt.runner.frozen._seal(output/'source_snapshot.json',{'SYNTHETIC_ONLY':True}); return {}
        stack.enter_context(patch.object(opt.runner,'_snapshot_sources',side_effect=snapshot))
        stack.enter_context(patch.object(opt.runner,'_verify_source_snapshot',return_value=None))
        stack.enter_context(patch.object(opt.verify,'_source_archive',return_value=None))
        def pipeline(reg,ids,output,device,**cfg):
            self.calls.append((copy.deepcopy(cfg),list(ids)))
            if fail_at is not None and len(self.calls)==fail_at: raise RuntimeError('SYNTHETIC_VARIANT_FAILURE')
            output.mkdir(); opt.runner.frozen._seal(output/'execution_started.json',cfg)
            opt.runner.frozen._seal(output/'summary.json',dict(original_games=512,independent_full_game_audits=512,
                                                               wall_before_final_publication_s=15.0))
        stack.enter_context(patch.object(opt.runner,'run_fixtures',side_effect=pipeline))
        stack.enter_context(patch.object(opt.benchmark,'_verify_pipeline_artifacts',side_effect=lambda path,*_:dict(summary=opt.verify.read_sealed(path/'summary.json'))))
        stack.enter_context(patch.object(opt.benchmark,'_verify_result',return_value={'SYNTHETIC_ONLY':True}))
        stack.enter_context(patch.object(opt.time,'perf_counter',side_effect=[0,30,31,100,120,121,200,225,226]))
        return stack

    def reseal(self,path,value):
        body=opt.runner.canonical(value)+b'\n'; path.write_bytes(body); path.with_suffix('.sha256').write_text(opt.runner.sha(body)+'\n')

    def test_fixed_grid_and_minimum_complete_elapsed_with_deterministic_tie(self):
        entries=[dict(configuration=copy.deepcopy(c),origin=str(i),**measurement(s))
                 for i,(c,s) in enumerate(zip((opt.BASELINE_CONFIGURATION,*opt.CONFIGURATIONS),(44,31,21,26)))]
        self.assertEqual(opt.select(entries)['configuration'],opt.CONFIGURATIONS[1])
        entries[1]['wall_seconds']=21
        self.assertEqual(opt.select(entries)['configuration'],opt.CONFIGURATIONS[0])
        with self.assertRaises(ValueError): opt.select(entries[:-1])
        bad=copy.deepcopy(entries); bad[1]['full_actor_audits']=511
        with self.assertRaises(ValueError): opt.select(bad)
        bad=copy.deepcopy(entries); bad[1]['configuration']['batch_size']=128.0
        with self.assertRaises(ValueError): opt.select(bad)

    def test_balanced_variant_ids_are_disjoint_from_baseline_and_other_variants(self):
        all_ids=set(); original=copy.deepcopy(self.reg)
        for cfg in opt.CONFIGURATIONS:
            replicas,mapping=opt._replicas(self.reg,self.controls,cfg); ids={f['id'] for f in replicas['fixtures']}
            self.assertEqual(len(ids),512); self.assertFalse(ids&all_ids); all_ids|=ids
            self.assertEqual([m['source_fixture_id'] for m in mapping],[c['fixture'] for _ in range(64) for c in self.controls])
        self.assertEqual(self.reg,original)

    def test_metadata_only_grid_roundtrip_and_selected_config_tamper_rejection(self):
        output=self.directory/'complete'
        with self.mocks():
            report=opt.run(output)
            self.assertEqual([cfg for cfg,_ in self.calls],list(opt.CONFIGURATIONS))
            self.assertTrue(all(len(ids)==512 for _,ids in self.calls))
            self.assertEqual(opt.verify_complete(output),report)
            bad=copy.deepcopy(report); bad['selected_configuration']=dict(opt.BASELINE_CONFIGURATION)
            self.reseal(output/'optimization_result.json',bad)
            with self.assertRaisesRegex(ValueError,'minimum complete elapsed'): opt.verify_complete(output)
        self.assertEqual(report['primary_games'],0); self.assertEqual(report['study_games'],0)

    def test_failed_second_variant_preserves_first_and_never_runs_third_or_selects(self):
        output=self.directory/'failed'
        with self.mocks(fail_at=2):
            with self.assertRaisesRegex(RuntimeError,'SYNTHETIC_VARIANT_FAILURE'): opt.run(output)
            with self.assertRaisesRegex(ValueError,'Failed or partial'): opt.verify_complete(output)
        self.assertEqual(len(self.calls),2); self.assertTrue((output/opt.label(opt.CONFIGURATIONS[0])/'variant_result.json').exists())
        self.assertFalse((output/'optimization_result.json').exists()); self.assertTrue((output/'optimization_error.json').exists())

    def test_understated_nested_lifecycle_cannot_win_even_when_outer_fields_agree(self):
        output=self.directory/'understated'
        with self.mocks():
            report=opt.run(output); cfg=opt.CONFIGURATIONS[1]; folder=output/opt.label(cfg)
            variant=opt.verify.read_sealed(folder/'variant_result.json')
            variant.update(outer_run_fixtures_wall_s=1,final_verification_s=1,measurement=measurement(2))
            self.reseal(folder/'variant_result.json',variant)
            with self.assertRaisesRegex(ValueError,'understates'):
                opt._verify_variant(folder,cfg,self.baseline,self.reg,self.controls,{'SYNTHETIC_ONLY':'c'*64},{'SYNTHETIC_ONLY':'a'*64},'cuda')

    def test_changed_published_baseline_bytes_reject_before_reference_verification(self):
        baseline=self.directory/'bad-baseline'; baseline.mkdir(); (baseline/'benchmark_result.json').write_bytes(b'{}')
        with patch.object(opt,'BASELINE',baseline),patch.object(opt.benchmark,'verify_complete',side_effect=AssertionError('Should reject pin first')):
            with self.assertRaisesRegex(ValueError,'baseline result bytes changed'): opt._baseline()


if __name__=='__main__': unittest.main()
