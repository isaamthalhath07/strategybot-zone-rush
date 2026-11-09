"""Independent synthetic/admission checks; zero real trial outcomes or actors.

The frozen reference engine supplies synthetic public-board witnesses only.
Expensive accepted-data admission is mocked where protocol sealing is tested.
No real prepare/execute call, existing transcript, recommendation or branch
outcome is used as test data.
"""
import copy
import hashlib
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from intent_trials import experiment as trial
from primary_campaign import core
from search_coach.belief import PublicObservation
from tests import reference_engine as engine


def observation(game, focal=0):
    return PublicObservation.from_view(game.views()[focal])


def reseal(path, value):
    body = core.canonical(value)+b'\n'
    path.write_bytes(body)
    path.with_suffix('.sha256').write_text(core.digest(body)+'\n', encoding='ascii')


def candidates():
    result = []
    for t, turn in enumerate(trial.TURNS):
        for f, field in enumerate(trial.FIELDS):
            for choice in range(3):
                identity = 'SYNTHETIC_%d_%d_%d' % (t, f, choice)
                result.append(dict(turn=turn, field=field, fixture=identity,
                    map_id=identity+'-MAP', rotation_orbit=identity+'-ORBIT',
                    nearest_projected_rank_margin=choice,
                    public_scores=[0]*4, public_income=[1]*4,
                    remaining_turns=81-turn, projected_scores=[81-turn]*4,
                    legal_actions=['NORTH', 'STAY', 'SHIELD'],
                    focal_publicly_unfrozen=True, public_prefix_sha256='c'*64))
    return result


def facts(directory):
    return dict(stage_directory=str(directory/'synthetic-campaign'/'train_000'),
        campaign_id='SYNTHETIC_ZERO_CREDIT', generation=0,
        stage_files_sha256={'games.jsonl':'1'*64, 'actor_audits.jsonl':'2'*64},
        accepted_snapshot_sha256=trial.SNAPSHOT_SHA256,
        manifest_sha256='3'*64, catalog_sha256='4'*64,
        candidate_sha256=core.INCUMBENT, exclusions={'SYNTHETIC_ONLY':True},
        eligible_public_roots=48, selected=trial.select_cases(candidates(), []))


def synthetic_cases(protocol):
    result = []
    # Every stratum is heterogeneous; descriptive intervals must actually
    # resample paired map records instead of collapsing to a constant.
    for index, case in enumerate(protocol['selected']):
        field = trial.FIELDS.index(case['field'])
        position = index//4
        delta = ((field+position)%7-3)/2
        opportunity = max(0, delta)+((field+2*position)%3)/2
        result.append(dict(case=copy.deepcopy(case), teacher_delta_pairwise=delta,
            hindsight_opportunity_pairwise=opportunity,
            recommended_action='SHIELD', baseline_action='STAY'))
    return result


class IndependentProtocolTests(unittest.TestCase):
    def setUp(self):
        cache = Path(trial.__file__).resolve().parent/'.cache'
        cache.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='review-SYNTHETIC-', dir=cache)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def prepare_synthetic(self):
        source = facts(self.directory)
        output = self.directory/'synthetic-registration'
        pins = {'SYNTHETIC_RUNTIME':'a'*64}
        with (patch.object(trial, '_facts', return_value=copy.deepcopy(source)) as admission,
              patch.object(trial, 'source_pins', return_value=pins),
              patch.object(trial.oversight, 'make_actors', side_effect=AssertionError('Actor called in preparation'))):
            protocol = trial.prepare(Path(source['stage_directory']), output)
        self.assertEqual(admission.call_count, 1)
        self.assertFalse((output/'execution_started.json').exists())
        return output, protocol, source, pins

    def test_public_accounting_opening_has_income_but_zero_score(self):
        game = engine.Game()
        scores, income = trial.public_accounting(None, observation(game), [0]*4)
        self.assertEqual(scores, [0]*4)
        self.assertEqual(income, game.income)
        self.assertGreater(sum(income), 0)

    def test_complete_public_boards_reconstruct_every_score_and_upgraded_capture_bonus(self):
        game = engine.Game(rules={'catch_requires_stay': True})
        previous = observation(game)
        scores, _ = trial.public_accounting(None, previous, [0]*4)
        # Rival2 claims and upgrades cell6, then leaves. A move into a
        # pre-turn-occupied cell is blocked, so focal waits before entering.
        focal = ['EAST']*5+['STAY','EAST']+['STAY']*3
        rival = ['WEST']+['STAY']*4+['SOUTH']+['STAY']*4
        upgraded_captures = 0
        for a, b in zip(focal, rival):
            game.step([a, b, 'STAY', 'STAY'])
            current = observation(game)
            upgraded_captures += sum(old[1] and new[1] and old[1] != new[1] and old[2]
                                     for old, new in zip(previous.cells, current.cells))
            scores, income = trial.public_accounting(previous, current, scores)
            self.assertEqual(scores, game.score)
            self.assertEqual(income, game.income)
            previous = current
        self.assertEqual(upgraded_captures, 1)
        self.assertEqual(game.owner[6], 1)
        self.assertEqual(game.upg[6], 0)

    def test_all_seats_public_accounting_matches_80_synthetic_legal_turns(self):
        for token in range(1, 5):
            with self.subTest(token=token):
                game = engine.Game(start_token=token, rules={'catch_requires_stay': True})
                rng = random.Random(7000+token)
                previous = observation(game, token-1)
                scores, _ = trial.public_accounting(None, previous, [0]*4)
                for _ in range(80):
                    joint = [rng.choice(game.legal(seat)) for seat in range(4)]
                    game.step(joint)
                    current = observation(game, token-1)
                    scores, income = trial.public_accounting(previous, current, scores)
                    self.assertEqual(scores, game.score)
                    self.assertEqual(income, game.income)
                    previous = current

    def test_public_margin_uses_true_remaining_clock_and_public_eligibility_only(self):
        obs = observation(engine.Game())
        scores = [100, 94, 90, 70]
        for turn in trial.TURNS:
            context = trial.public_context(obs, scores, turn)
            self.assertEqual(context['remaining_turns'], 81-turn)
            self.assertEqual(context['public_scores'], scores)
            expected = [score+(81-turn)*rate for score, rate in zip(scores, context['public_income'])]
            self.assertEqual(context['projected_scores'], expected)
            self.assertEqual(context['nearest_projected_rank_margin'], min(abs(expected[0]-other) for other in expected[1:]))
        frozen = list(obs.cells)
        frozen[obs.positions[0]] = tuple((*frozen[obs.positions[0]][:4], True, frozen[obs.positions[0]][5]))
        blocked = PublicObservation(tuple(frozen), obs.bot_id, obs.is_priority_token, obs.legal_actions)
        self.assertIsNone(trial.public_context(blocked, scores, 30))
        forced = PublicObservation(obs.cells, obs.bot_id, obs.is_priority_token, ('STAY', 'SHIELD'))
        self.assertIsNone(trial.public_context(forced, scores, 30))
        with self.assertRaises(ValueError):
            trial.public_context(obs, scores, 31)

    def test_selection_never_reads_final_score_or_current_future_intention_tape(self):
        class PriorOnlyTape(list):
            def __getitem__(self, index):
                if not isinstance(index,int) or index >= 74:
                    raise AssertionError('Current turn75 or later tape reached selection')
                return super().__getitem__(index)
        class NoFinalScore(dict):
            def __getitem__(self, key):
                if key in ('scores','focal_pw','focal_score'):
                    raise AssertionError('Final outcome reached selection')
                return super().__getitem__(key)
        stage = self.directory/'synthetic-selection'
        stage.mkdir()
        (stage/'games.jsonl').write_bytes(b'SYNTHETIC_ROW_WITH_POISON_FUTURE\n')
        base = engine.make_map(canonical=True)
        fixture = dict(id='SYNTHETIC_FIXTURE',candidate=core.INCUMBENT,base=base,token=1,
                       seat=0,field=trial.FIELDS[0],map_id='SYNTHETIC_MAP')
        tape = PriorOnlyTape([['STAY']*4 for _ in range(80)])
        row = NoFinalScore(candidate=core.INCUMBENT,fixture=fixture['id'],actions=tape)
        with patch.object(trial.oversight, 'strict_loads', return_value=row):
            selected = trial._selection_candidates(stage,{'fixtures':[fixture]})
        self.assertEqual([case['turn'] for case in selected],list(trial.TURNS))
        game = engine.Game(base=base,start_token=1,rules={'catch_requires_stay':True})
        opening = observation(game).serializable()
        prefix = []
        by_turn = {case['turn']:case for case in selected}
        for turn in range(1,76):
            if turn in by_turn:
                expected = dict(initial_observation=opening,transitions=prefix)
                self.assertEqual(by_turn[turn]['public_prefix_sha256'],trial.sha(core.canonical(expected)))
            if turn < 75:
                game.step(['STAY']*4)
                prefix.append(dict(own_action='STAY',observation=observation(game).serializable()))

    def test_selector_minimizes_public_margin_then_stable_fixture_and_never_reuses_orbits(self):
        pool = candidates()
        excluded = [pool[0]['rotation_orbit']]
        selected = trial.select_cases(pool, excluded)
        shuffled = list(reversed(pool))
        self.assertEqual(selected, trial.select_cases(shuffled, excluded))
        self.assertEqual([(case['turn'], case['field']) for case in selected],
                         [(turn, field) for turn in trial.TURNS for field in trial.FIELDS])
        self.assertEqual(len({case['rotation_orbit'] for case in selected}), 16)
        self.assertFalse(set(excluded) & {case['rotation_orbit'] for case in selected})
        self.assertEqual(selected[0]['nearest_projected_rank_margin'], 1)
        tied = copy.deepcopy(pool)
        tied[0]['nearest_projected_rank_margin'] = tied[1]['nearest_projected_rank_margin'] = 0
        tied[0]['fixture'], tied[1]['fixture'] = 'z-FIXTURE', 'a-FIXTURE'
        self.assertEqual(trial.select_cases(tied, [])[0]['fixture'], 'a-FIXTURE')
        reused = copy.deepcopy(pool)
        reused[3]['rotation_orbit'] = reused[0]['rotation_orbit']
        selected = trial.select_cases(reused, [])
        self.assertEqual(selected[1]['nearest_projected_rank_margin'], 1)

    def test_insufficient_nonexcluded_maps_abort_instead_of_relaxing_or_replacing_cases(self):
        pool = candidates()
        excluded = [case['rotation_orbit'] for case in pool if case['turn'] == 30 and case['field'] == trial.FIELDS[0]]
        with self.assertRaisesRegex(ValueError, 'Insufficient distinct'):
            trial.select_cases(pool, excluded)
        insufficient = [dict(case, rotation_orbit='ONE_SHARED_ORBIT') for case in pool]
        with self.assertRaisesRegex(ValueError, 'Insufficient distinct'):
            trial.select_cases(insufficient, [])

    def test_rehashed_plan_cannot_change_schedule_claims_caps_cases_or_runtime_pins(self):
        output, original, source, pins = self.prepare_synthetic()
        with (patch.object(trial, '_facts', return_value=copy.deepcopy(source)),
              patch.object(trial, 'source_pins', return_value=pins)):
            self.assertEqual(trial._validated(output), original)
        changed = []
        for key, value in [('metric','win rate'), ('intervention','replace complete policy'),
                           ('diagnostics','globally optimal strategy'), ('baseline','future tape'),
                           ('failure_policy','omit failed cases'), ('execution_gate','execute before publish'),
                           ('data_scope','fresh reserved confirmation'), ('primary_games',False),
                           ('completed_per_game_bmcts_audits',1), ('promoted',True),
                           ('unregistered_claim','best policy')]:
            bad = copy.deepcopy(original); bad[key] = value; changed.append((key, bad))
        for key, value in [('replicates',100), ('seed',1), ('quantile_indices',[0,19999]),
                           ('allocation','pool fields'), ('algorithm','independent draws per metric'),
                           ('scope','fresh-match guarantee')]:
            bad = copy.deepcopy(original); bad['bootstrap'][key] = value; changed.append(('bootstrap.'+key,bad))
        bad = copy.deepcopy(original); bad['search']['horizon'] += 1; changed.append(('horizon',bad))
        bad = copy.deepcopy(original); bad['search']['seeds'][0] += 1; changed.append(('seed',bad))
        bad = copy.deepcopy(original); bad['selection']['turns'][0] = 29; changed.append(('turns',bad))
        bad = copy.deepcopy(original); bad['selected'][0]['fixture'] = 'REPLACED'; changed.append(('case',bad))
        bad = copy.deepcopy(original); bad['source_sha256']['SYNTHETIC_RUNTIME'] = '0'*64; changed.append(('source',bad))
        for label, bad in changed:
            reseal(output/'registration.json', bad)
            with (self.subTest(field=label),
                  patch.object(trial, '_facts', return_value=copy.deepcopy(source)),
                  patch.object(trial, 'source_pins', return_value=pins),
                  self.assertRaisesRegex(ValueError, 'Exact causal protocol')):
                trial._validated(output)

    def test_stratified_paired_bootstrap_matches_independent_seeded_draws_and_quantiles(self):
        _, protocol, _, _ = self.prepare_synthetic()
        cases = synthetic_cases(protocol)
        actual = trial.statistics(cases, protocol)
        groups = [[index for index, case in enumerate(protocol['selected']) if case['field'] == field]
                  for field in trial.FIELDS]
        rng = random.Random(202611092330)
        teacher_boot, opportunity_boot = [], []
        digest = hashlib.sha256()
        for _ in range(20000):
            sampled = []
            for group in groups:
                for _ in range(4):
                    sampled.append(group[rng.randrange(4)])
            digest.update(bytes(sampled))
            teacher_boot.append(sum(cases[index]['teacher_delta_pairwise'] for index in sampled)/16)
            opportunity_boot.append(sum(cases[index]['hindsight_opportunity_pairwise'] for index in sampled)/16)
        for name, key, samples in [('selected_teacher','teacher_delta_pairwise',teacher_boot),
                                    ('hindsight_opportunity','hindsight_opportunity_pairwise',opportunity_boot)]:
            samples.sort()
            self.assertEqual(actual[name]['mean_delta_pairwise'], sum(case[key] for case in cases)/16)
            self.assertEqual(actual[name]['descriptive95_interval'], [samples[499],samples[19499]])
            self.assertLess(samples[499],samples[19499])
            self.assertEqual(actual[name]['fields'],
                             {field:sum(cases[index][key] for index in group)/4 for field,group in zip(trial.FIELDS,groups)})
        self.assertEqual(actual['bootstrap']['shared_draw_indices_sha256'],digest.hexdigest())
        self.assertEqual(actual['wins']+actual['losses']+actual['ties'],16)
        self.assertEqual(actual['recommendations_changed'],16)

    def test_partial_duplicate_reordered_nonfinite_and_reassigned_results_never_form_statistics(self):
        _, protocol, _, _ = self.prepare_synthetic()
        original = synthetic_cases(protocol)
        bad_values = [original[:-1], original[:-1]+[original[0]], list(reversed(original))]
        for key, value in [('teacher_delta_pairwise',float('nan')), ('teacher_delta_pairwise',float('inf')),
                           ('teacher_delta_pairwise',True), ('teacher_delta_pairwise',0.25),
                           ('hindsight_opportunity_pairwise',3.5), ('hindsight_opportunity_pairwise',-0.5)]:
            bad = copy.deepcopy(original); bad[0][key] = value; bad_values.append(bad)
        bad = copy.deepcopy(original); bad[0]['teacher_delta_pairwise'] = 2; bad[0]['hindsight_opportunity_pairwise'] = 1; bad_values.append(bad)
        bad = copy.deepcopy(original); bad[0]['recommended_action'] = bad[0]['baseline_action']; bad_values.append(bad)
        bad = copy.deepcopy(original); bad[0]['case']['field'] = 'REASSIGNED'; bad_values.append(bad)
        bad = copy.deepcopy(original); bad[0]['case']['rotation_orbit'] = 'REASSIGNED'; bad_values.append(bad)
        for index, bad in enumerate(bad_values):
            with self.subTest(corruption=index), self.assertRaises(ValueError):
                trial.statistics(bad, protocol)

    def test_published_snapshot_raw_pin_and_distinct_stage_semantics_reject_forgery(self):
        source = self.directory/'snapshot-root'
        snapshot = source/trial.SNAPSHOT
        snapshot.parent.mkdir(parents=True)
        snapshot.write_bytes(b'{}')
        with patch.object(trial, 'ROOT', source), self.assertRaisesRegex(ValueError, 'snapshot changed'):
            trial._snapshot()
        false_snapshot = dict(primary_games_accepted=100000, callbacks_regenerated=32000000,
                              bmcts_audits=0, promoted=False, stages=[{'generation':0}]*5)
        body = core.canonical(false_snapshot)
        snapshot.write_bytes(body)
        with (patch.object(trial, 'ROOT', source), patch.object(trial, 'SNAPSHOT_SHA256', trial.sha(body)),
              self.assertRaisesRegex(ValueError, 'stages 0 through 4')):
            trial._snapshot()

    def test_admission_binds_original_raw_logs_exact_receipts_and_source_guards_despite_new_sidecars(self):
        source = self.directory/'admission-root'
        stage = source/'campaign'/'train_000'
        stage.mkdir(parents=True)
        protected = source/'synthetic-runtime.py'
        protected.write_bytes(b'SYNTHETIC_RUNTIME = True\n')
        registration = dict(generation=0, phase='train', campaign_id='SYNTHETIC',
                            guards={str(protected):trial.sha(protected.read_bytes())})
        core.seal(stage/'registration.json',registration)
        (stage/'games.jsonl').write_bytes(b'{"synthetic":"raw-80turn-log-placeholder"}\n')
        (stage/'actor_audits.jsonl').write_bytes(b'{"synthetic":"raw-admission-placeholder"}\n')
        receipt = dict(registration_sha256=trial.sha((stage/'registration.json').read_bytes()),
                       games_sha256=trial.sha((stage/'games.jsonl').read_bytes()),
                       actor_audits_sha256=trial.sha((stage/'actor_audits.jsonl').read_bytes()))
        audit = dict(approved=True, all_actors_regenerated=True, callbacks_regenerated=6400000,
                     primary_games_accepted=20000, campaign_id='SYNTHETIC', **receipt)
        core.seal(stage/'audit.json',audit)
        published = source/'primary_campaign'/'evidence'/'train_000'
        published.mkdir(parents=True)
        receipt['exact_copy_files'] = {}
        for name in ('audit.json','audit.sha256'):
            body = (stage/name).read_bytes()
            (published/name).write_bytes(body)
            receipt['exact_copy_files'][name] = trial.sha(body)
        original = {name:(stage/name).read_bytes() for name in
                    ('registration.json','registration.sha256','games.jsonl','actor_audits.jsonl','audit.json','audit.sha256')}
        with (patch.object(trial, 'ROOT', source), patch.object(trial, 'STAGE', stage),
              patch.object(trial, '_snapshot', return_value={'stages':[receipt]})):
            self.assertEqual(trial._admission(stage)[0],registration)
            for name in ('registration.json','games.jsonl','actor_audits.jsonl','audit.json'):
                with self.subTest(raw_file=name):
                    body = original[name]+b' '
                    (stage/name).write_bytes(body)
                    (stage/name).with_suffix('.sha256').write_text(trial.sha(body)+'\n',encoding='ascii')
                    with self.assertRaisesRegex(ValueError, 'raw bytes changed'):
                        trial._admission(stage)
                    for original_name, original_body in original.items():
                        (stage/original_name).write_bytes(original_body)
            (published/'audit.json').write_bytes(b'REPLACED COPY')
            with self.assertRaisesRegex(ValueError, 'exact-copy bytes differ'):
                trial._admission(stage)
            (published/'audit.json').write_bytes(original['audit.json'])
            protected.write_bytes(b'SYNTHETIC_RUNTIME = False\n')
            with self.assertRaisesRegex(ValueError, 'code/source changed'):
                trial._admission(stage)
            with self.assertRaisesRegex(ValueError, 'fixed accepted TRAIN'):
                trial._admission(source/'foreign-stage')

    def test_existing_preparation_directory_is_preserved_and_rejected_before_admission(self):
        output = self.directory/'existing'
        output.mkdir()
        marker = output/'marker.txt'; marker.write_text('PRESERVE',encoding='ascii')
        with patch.object(trial, '_facts', side_effect=AssertionError('Must reject before admission')):
            with self.assertRaises(ValueError):
                trial.prepare(self.directory/'source'/'train_000', output)
        self.assertEqual(marker.read_text(encoding='ascii'), 'PRESERVE')

    def test_concurrent_execution_claim_rejects_loser_before_any_model_actor_or_outcome(self):
        output = self.directory/'synthetic-execution-gate'
        output.mkdir()
        def another_invocation_wins(_):
            (output/'.execution_claim').mkdir()
            return {'SYNTHETIC_VALIDATED_ONLY':True}
        with (patch.object(trial, '_validated', side_effect=another_invocation_wins) as validate,
              patch.object(trial.oversight, 'make_actors', side_effect=AssertionError('Actor called before claim')),
              self.assertRaises(FileExistsError)):
            trial.execute(output)
        self.assertEqual(validate.call_count,1)
        self.assertFalse((output/'execution_started.json').exists())
        self.assertFalse((output/'error.json').exists())
        with (patch.object(trial, '_validated', side_effect=AssertionError('Existing claim must reject first')),
              self.assertRaisesRegex(ValueError,'Preserve')):
            trial.execute(output)

    def test_interrupts_preserve_sealed_active_partial_evidence_and_reraise_same_object(self):
        from intent_search import mcts
        stage = self.directory/'synthetic-interruption-source'
        stage.mkdir()
        fixture = {'id':'SYNTHETIC_INTERRUPTED_FIXTURE'}
        core.seal(stage/'registration.json',dict(candidates=[{'sha256':core.INCUMBENT}],
                                               fixtures=[fixture],sources={}))
        (stage/'games.jsonl').write_bytes(core.canonical({'fixture':fixture['id']})+b'\n')
        protocol = dict(stage_directory=str(stage),selected=[{'fixture':fixture['id']}],
                        search={'seeds':[202611092300]})
        for index, error in enumerate((KeyboardInterrupt('SYNTHETIC_INTERRUPT'),SystemExit(7))):
            with self.subTest(exception=type(error).__name__):
                output = self.directory/('synthetic-interrupted-%d'%index)
                output.mkdir()
                core.seal(output/'registration.json',protocol)
                partial = dict(SYNTHETIC_ONLY=True,actions=[['STAY']*4],
                               audit={'callbacks_regenerated':4,'dual_referee_turns':1})
                error.branch_evidence = partial
                with (patch.object(trial, '_validated', return_value=protocol),
                      patch.object(trial, 'public_job', side_effect=error),
                      patch.object(mcts, 'recommend', side_effect=AssertionError('Teacher called in interruption test')),
                      patch.object(trial.oversight, 'make_actors', side_effect=AssertionError('Actor called in interruption test')),
                      self.assertRaises(type(error)) as raised):
                    trial.execute(output)
                self.assertIs(raised.exception,error)
                failure = core.read_sealed(output/'error.json')
                self.assertEqual(failure['exception_type'],type(error).__name__)
                self.assertEqual(failure['active'],{'case':0,'branch':'public_teacher'})
                self.assertEqual(failure['partial_branch'],partial)
                self.assertEqual(failure['completed_cases'],0)
                self.assertEqual(failure['primary_games'],0)
                self.assertEqual(failure['completed_per_game_bmcts_audits'],0)
                self.assertFalse(failure['promoted'])
                self.assertTrue((output/'.execution_claim').is_dir())
                self.assertTrue((output/'execution_started.json').exists())
                self.assertFalse((output/'results.json').exists())


if __name__ == '__main__':
    unittest.main()
