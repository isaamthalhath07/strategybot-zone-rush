"""Independent fixed-grid control-flow tests; every execution/proof is mocked.

No known control, policy, physics, GPU, live authority or strength run is used.
Synthetic records test timing/coverage bindings, not physical attestation.
"""
from collections import Counter
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadline_runner import optimize as o


def known_metadata():
    registration=dict(fixtures=[{'id':'SYNTHETIC-KNOWN-%d'%i} for i in range(8)],
        candidates=[],sources={},guards={'SYNTHETIC-GUARD':'a'*64},rules={'catch_requires_stay':True})
    return registration,[{'fixture':f['id']} for f in registration['fixtures']],{'SYNTHETIC-INPUT':'b'*64}


def measurement(seconds):
    return dict(games=512,wall_seconds=seconds,full_actor_audits=512,both_referees=True)


def measurements(seconds=(20.,10.,12.,15.)):
    return [dict(configuration=copy.deepcopy(config),origin='published_baseline' if i==0 else o.label(config),
                 **measurement(seconds[i])) for i,config in enumerate([o.BASELINE_CONFIGURATION,*o.CONFIGURATIONS])]


def rewrite(path,value):
    body=o.runner.canonical(value)+b'\n';path.write_bytes(body)
    path.with_suffix('.sha256').write_text(o.runner.sha(body)+'\n')


class OptimizerIndependentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-OPTIMIZER-',dir=o.runner.ROOT/'deadline_runner')
        self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name)

    def test_fixed_complete_grid_selects_only_elapsed_time_with_deterministic_ties(self):
        chosen=o.select(measurements())
        self.assertEqual(chosen['configuration'],o.CONFIGURATIONS[0])
        self.assertEqual(set(chosen['measurement']),{'games','wall_seconds','full_actor_audits','both_referees'})
        self.assertEqual(o.select(measurements((10.,10.,10.,10.)))['configuration'],o.CONFIGURATIONS[0])
        for rows in (measurements()[:-1],list(reversed(measurements()))):
            with self.assertRaises(ValueError): o.select(rows)
        for key,value in (('games',512.0),('games',True),('full_actor_audits',511),
                ('both_referees',False),('wall_seconds',float('nan')),('wall_seconds',0)):
            rows=measurements();rows[1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): o.select(rows)
        rows=measurements();rows[1]['configuration']['batch_size']=128.0
        with self.assertRaises(ValueError): o.select(rows)

    def test_each_variant_has512_fresh_ids_balanced64_per_known_recipe(self):
        registration,controls,_=known_metadata();all_ids=set()
        for configuration in o.CONFIGURATIONS:
            original=copy.deepcopy(registration)
            replicas,mapping=o._replicas(registration,controls,configuration)
            ids=[m['lane_id'] for m in mapping]
            self.assertEqual(len(ids),512);self.assertEqual(len(set(ids)),512)
            self.assertTrue(all_ids.isdisjoint(ids));all_ids.update(ids)
            self.assertEqual(Counter(m['source_fixture_id'] for m in mapping),
                Counter({row['fixture']:64 for row in controls}))
            self.assertEqual([f['id'] for f in replicas['fixtures']],ids)
            self.assertEqual(registration,original)
            for binding in mapping:
                self.assertEqual(binding['lane_id'],o.runner.sha(o.runner.canonical([
                    o.FORMAT,o.label(configuration),binding['source_fixture_id'],binding['repetition']])))

    def test_variant_timing_cannot_be_shorter_than_nested_full_executor_wall(self):
        registration,controls,inputs=known_metadata();configuration=o.CONFIGURATIONS[0]
        baseline={'SYNTHETIC-BASELINE':True};pins={'SYNTHETIC-PIN':'a'*64}
        directory=self.directory/'variant';directory.mkdir();pipeline=directory/'pipeline';pipeline.mkdir()
        _,mapping=o._replicas(registration,controls,configuration)
        protocol=o._protocol(configuration,mapping,baseline,inputs,pins,'cuda')
        summary=dict(original_games=512,independent_full_game_audits=512,wall_before_final_publication_s=20.)
        rewrite(pipeline/'summary.json',summary);rewrite(pipeline/'execution_started.json',configuration)
        report=dict(protocol,measurement=measurement(22.),outer_run_fixtures_wall_s=21.,final_verification_s=1.,
            equivalence={'SYNTHETIC-EXACT':True},pipeline_summary=summary,
            pipeline_summary_sha256=o.runner.sha((pipeline/'summary.json').read_bytes()))
        rewrite(directory/'variant_registration.json',protocol);rewrite(directory/'variant_result.json',report)
        with patch.object(o.benchmark,'_verify_pipeline_artifacts',return_value={'summary':summary}),\
                patch.object(o.benchmark,'_verify_result',return_value=report['equivalence']):
            self.assertEqual(o._verify_variant(directory,configuration,baseline,registration,controls,inputs,pins,'cuda'),report)
            understated=copy.deepcopy(report);understated.update(measurement=measurement(2.),
                outer_run_fixtures_wall_s=1.,final_verification_s=1.)
            rewrite(directory/'variant_result.json',understated)
            with self.assertRaises(ValueError):
                o._verify_variant(directory,configuration,baseline,registration,controls,inputs,pins,'cuda')

    def synthetic_grid(self):
        output=self.directory/'grid';output.mkdir();(output/'source_snapshot.json').write_bytes(b'SYNTHETIC-SOURCE-SNAPSHOT')
        (output/'sources').mkdir();(output/'.execution_claim').mkdir()
        pins={'SYNTHETIC-PIN':'a'*64};registration,controls,inputs=known_metadata()
        baseline=dict(configuration=copy.deepcopy(o.BASELINE_CONFIGURATION),measurement=measurement(20.))
        plan=dict(format=o.FORMAT,source_sha256=pins,baseline=baseline,
            configurations=copy.deepcopy(list(o.CONFIGURATIONS)),known_input_sha256=inputs,device='cuda',
            primary_games=0,study_games=0,completed_per_game_bmcts_audits=0)
        bindings=[];variants={}
        for configuration,seconds in zip(o.CONFIGURATIONS,(10.,12.,15.)):
            label=o.label(configuration);directory=output/label;directory.mkdir()
            variant={'measurement':measurement(seconds)};variants[label]=variant
            rewrite(directory/'variant_result.json',variant)
            bindings.append(dict(variant=label,path=label,sha256=o.runner.sha((directory/'variant_result.json').read_bytes())))
        values=measurements();chosen=o.select(values)
        report=dict(plan,variants=bindings,measurements=values,selected_configuration=chosen['configuration'],
            selected_measurement=chosen['measurement'],selected_origin=chosen['origin'],
            source_snapshot_sha256=o.runner.sha((output/'source_snapshot.json').read_bytes()))
        rewrite(output/'optimization_registration.json',plan);rewrite(output/'optimization_result.json',report)
        return output,pins,baseline,registration,controls,inputs,variants,report

    def test_whole_grid_verifier_rejects_missing_failed_or_reselected_variants(self):
        output,pins,baseline,registration,controls,inputs,variants,report=self.synthetic_grid()
        calls=[]
        def variant(directory,*args): calls.append(Path(directory).name);return variants[Path(directory).name]
        with patch.object(o,'source_pins',return_value=pins),patch.object(o,'_baseline',return_value=baseline),\
                patch.object(o.benchmark,'_load_known',return_value=(registration,controls,inputs)),\
                patch.object(o.verify,'_source_archive'),patch.object(o,'_verify_variant',side_effect=variant),\
                patch.object(o.benchmark.serial_reference,'_guards'):
            self.assertEqual(o.verify_complete(output),report)
            self.assertEqual(calls,[o.label(c) for c in o.CONFIGURATIONS])
            for label,mutate in {
                    'omit':lambda r:r['variants'].pop(),
                    'wrong_bytes':lambda r:r['variants'][0].__setitem__('sha256','0'*64),
                    'wrong_config':lambda r:r.__setitem__('selected_configuration',o.BASELINE_CONFIGURATION),
                    'wrong_time':lambda r:r['selected_measurement'].__setitem__('wall_seconds',.001),
                    'wrong_origin':lambda r:r.__setitem__('selected_origin','published_baseline'),
                    'extra_credit':lambda r:r.__setitem__('study_games',1),
                    }.items():
                with self.subTest(label=label):
                    changed=copy.deepcopy(report);mutate(changed);rewrite(output/'optimization_result.json',changed)
                    with self.assertRaises(ValueError): o.verify_complete(output)
            rewrite(output/'optimization_result.json',report)
            (output/'optimization_error.json').write_bytes(b'SYNTHETIC-FAILED-ATTEMPT')
            with self.assertRaises(ValueError): o.verify_complete(output)

    def test_interrupt_preserves_prior_variant_partial_evidence_and_never_selects_or_retries(self):
        output=self.directory/'interrupted';pins={'SYNTHETIC-PIN':'a'*64}
        registration,controls,inputs=known_metadata();baseline={'configuration':o.BASELINE_CONFIGURATION,'measurement':measurement(20.)}
        failure=KeyboardInterrupt('SYNTHETIC-INTERRUPT');failure.deadline_runner_partial={'SYNTHETIC-REPORTED-ATTEMPTS':17}
        submissions=[]
        def run(registration,ids,path,**kwargs):
            submissions.append(kwargs)
            if len(submissions)==2: raise failure
            path.mkdir();rewrite(path/'summary.json',{'SYNTHETIC-COMPLETE':True})
        with patch.object(o,'source_pins',return_value=pins),patch.object(o,'_baseline',return_value=baseline),\
                patch.object(o.benchmark,'_load_known',return_value=(registration,controls,inputs)),\
                patch.object(o.benchmark.serial_reference,'_guards'),\
                patch.object(o.runner,'_snapshot_sources',return_value={}),patch.object(o.runner,'_verify_source_snapshot'),\
                patch.object(o.runner,'run_fixtures',side_effect=run),\
                patch.object(o.benchmark,'_verify_pipeline_artifacts',return_value={'summary':{'SYNTHETIC-COMPLETE':True}}),\
                patch.object(o.benchmark,'_verify_result',return_value={'SYNTHETIC-EXACT':True}):
            with self.assertRaises(KeyboardInterrupt) as caught: o.run(output)
            self.assertIs(caught.exception,failure)
            with self.assertRaises(ValueError): o.run(output)
        self.assertEqual(len(submissions),2)
        error=o.verify.read_sealed(output/'optimization_error.json')
        self.assertEqual(error['active_variant'],o.label(o.CONFIGURATIONS[1]))
        self.assertEqual([v['variant'] for v in error['completed_variants']],[o.label(o.CONFIGURATIONS[0])])
        self.assertEqual(error['pipeline_partial'],failure.deadline_runner_partial)
        self.assertFalse((output/'optimization_result.json').exists())
        self.assertEqual(error['primary_games'],0);self.assertEqual(error['study_games'],0)


if __name__=='__main__': unittest.main()
