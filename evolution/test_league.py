"""League lineage, consumed holdouts, immutable replay and fail-closed checks."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from evolution import league, runner
from evolution.genomes import GenomeSpace, digest

ROOT = league.ROOT


class LeagueTests(unittest.TestCase):
    def setUp(self):
        cache = ROOT/'.cache'
        cache.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='league-test-', dir=cache)
        self.directory = Path(self.temporary.name).resolve()
        self.assertTrue(self.directory.is_relative_to(cache.resolve()))
        self.space = GenomeSpace((ROOT/'bot.py').read_bytes())
        self.research = GenomeSpace((ROOT/'tester_bots/research_alternative.py').read_bytes()).genes

    def tearDown(self):
        self.temporary.cleanup()

    def spec(self, directory=None):
        return league.load_spec(directory or self.directory, 1987, 2, 8, 1, 1, 1)

    def test_offspring_lineage_is_deterministic_and_logic_is_preserved(self):
        population = league.make_population(self.space, self.research, [], 16, 30311)
        self.assertEqual(population, league.make_population(self.space, self.research, [], 16, 30311))
        self.assertEqual(population[0]['sha256'], digest((ROOT/'bot.py').read_bytes()))
        self.assertEqual(len({entry['sha256'] for entry in population}), 16)
        kinds = {entry['lineage']['kind'] for entry in population}
        self.assertTrue(set(league.METHODS) <= kinds)
        ancestors = {population[0]['sha256'],
                     digest(self.space.export(self.research))}
        baseline = ast.parse(self.space.body)
        baseline.body = [node for node in baseline.body if not GenomeSpace._is_config(node)]
        for entry in population:
            self.space.validate(entry['genes'])
            body = self.space.export(entry['genes'])
            self.assertEqual(digest(body), entry['sha256'])
            tree = ast.parse(body)
            tree.body = [node for node in tree.body if not GenomeSpace._is_config(node)]
            self.assertEqual(ast.dump(tree), ast.dump(baseline))
            self.assertTrue(set(entry['lineage']['parents']) <= ancestors)
        elites = [dict(genes=entry['genes'], sha256=entry['sha256']) for entry in population[2:5]]
        next_generation = league.make_population(self.space, self.research, elites, 12, 30312)
        self.assertEqual(next_generation[0]['sha256'], population[0]['sha256'])
        retained = [entry for entry in next_generation if entry['lineage']['kind'] == 'elite_retained']
        self.assertEqual(len(retained), 3)
        self.assertEqual({entry['sha256'] for entry in retained}, {entry['sha256'] for entry in elites})

    def test_confirmation_is_rejected_as_evolutionary_fitness(self):
        with self.assertRaises(ValueError):
            league.select_elites(dict(role='confirmation'), [])

    def test_stage_preparation_is_immutable_and_excludes_previous_round_maps(self):
        spec = self.spec()
        entries = league.make_population(self.space, self.research, [], 4, 71)
        first_path = self.directory/'round_000/discovery'
        first = league.prepare_stage(first_path, self.directory, spec, 0, 'discovery', entries, 1)
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in first_path.iterdir() if path.is_file()}
        self.assertEqual(league.prepare_stage(first_path, self.directory, spec, 0, 'discovery', entries, 1), first)
        after = {path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                 for path in first_path.iterdir() if path.is_file()}
        self.assertEqual(after, before)
        second_path = self.directory/'round_001/discovery'
        second = league.prepare_stage(second_path, self.directory, spec, 1, 'discovery', entries, 1)
        self.assertFalse({tuple(f['base']) for f in first['fixtures']}
                         & {tuple(f['base']) for f in second['fixtures']})
        self.assertIn(str((ROOT/'evolution/league.py').resolve()), first['guards'])
        self.assertFalse(first['promotion_allowed'])
        (first_path/'games.jsonl').write_text('consumed', encoding='utf8')
        (first_path/'registration.sha256').write_text('wrong', encoding='ascii')
        with self.assertRaises(ValueError):
            league.prepare_stage(first_path, self.directory, spec, 0, 'discovery', entries, 1)

    def test_completed_stage_replays_a_real_game_and_does_not_overwrite_results(self):
        spec = self.spec()
        entries = [league.gene_entry(self.space, self.space.genes, 'production_control')]
        entries[0]['name'] = 'incumbent'
        original_create = runner.create_registration

        def one_fixture(*args, **kwargs):
            registration = original_create(*args, **kwargs)
            registration['fixtures'] = registration['fixtures'][:1]
            return registration

        directory = self.directory/'real_smoke'
        with mock.patch.object(runner, 'create_registration', side_effect=one_fixture):
            registration = league.prepare_stage(directory, self.directory, spec, 0, 'discovery', entries, 1)
        candidate, fixture = registration['candidates'][0], registration['fixtures'][0]
        row = runner.play_game(candidate, fixture, registration['sources'])
        runner.verify_row(row, candidate, fixture)
        (directory/'games.jsonl').write_bytes(runner.canonical(row)+b'\n')
        summary = dict(registration_sha256=digest((directory/'registration.json').read_bytes()),
                       summary=runner.summarize([row], registration['candidates']), paired=[],
                       games_completed=1, callbacks=320, games_bmcts_audited=0,
                       primary_campaign_games=0, promoted=False)
        (directory/'summary.json').write_bytes(league.encoded(summary))
        before = (directory/'summary.json').stat().st_mtime_ns
        with mock.patch.object(runner, 'evaluate', side_effect=AssertionError('Consumed evidence rerun')):
            self.assertEqual(league.evaluate_stage(directory, 1), summary)
        self.assertEqual((directory/'summary.json').stat().st_mtime_ns, before)
        corrupted = copy.deepcopy(summary)
        corrupted['summary'][0]['mean_pw'] += 0.01
        (directory/'summary.json').write_bytes(league.encoded(corrupted))
        with self.assertRaises(ValueError):
            league.completed_stage(directory)

    @staticmethod
    def fake_evaluator(confirmation_wins, calls):
        def evaluate(directory, workers):
            directory = Path(directory)
            registration = league.stage_registration(directory)
            calls.append((str(directory), registration['role']))
            candidates = registration['candidates']
            rows = []
            for index, candidate in enumerate(candidates):
                if registration['role'] == 'discovery':
                    score = 2.5 if index == 1 else 1.5
                else:
                    score = 2.0 if index == 0 else 2.5 if confirmation_wins else 1.0
                rows.append(dict(name=candidate['name'], sha256=candidate['sha256'],
                                 mean_pw=score, mean_score=3000+score,
                                 games=len(registration['fixtures']), fields={}, max_ms=1,
                                 all_player_max_ms=1))
            paired = []
            if registration['role'] == 'confirmation':
                paired = [dict(first=candidates[1]['sha256'], second=candidates[0]['sha256'],
                               mean=0.5 if confirmation_wins else -1.0,
                               bootstrap_95=[0.1, 0.8] if confirmation_wins else [-1.2, -0.5])]
            count = len(candidates)*len(registration['fixtures'])
            summary = dict(registration_sha256=digest((directory/'registration.json').read_bytes()),
                           summary=rows, paired=paired, games_completed=count, callbacks=count*320,
                           primary_campaign_games=0, games_bmcts_audited=0, promoted=False)
            (directory/'summary.json').write_bytes(league.encoded(summary))
            return summary
        return evaluate

    def test_holdout_outcomes_do_not_change_future_offspring_and_resume_is_idempotent(self):
        populations, states = [], []
        baseline_before = (ROOT/'bot.py').read_bytes()
        for label, wins in (('passed', True), ('failed', False)):
            directory = self.directory/label
            calls = []
            with mock.patch.object(league, 'independent_gate', return_value={'validity': 'passed'}), \
                    mock.patch.object(runner, 'evaluate', side_effect=self.fake_evaluator(wins, calls)), \
                    mock.patch.object(league, 'completed_stage', side_effect=lambda p: json.loads((Path(p)/'summary.json').read_text())):
                state = league.run_league(directory, seed=1991, rounds=2, population=8,
                                          discovery_maps=1, confirmation_maps=1, workers=1)
                first_calls = list(calls)
                immutable_before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                                    for path in directory.rglob('*.json')
                                    if path.name != 'league_state.json'}
                resumed = league.run_league(directory, seed=1991, rounds=2, population=8,
                                            discovery_maps=1, confirmation_maps=1, workers=1)
                self.assertEqual(resumed, state)
                self.assertEqual(calls, first_calls)
                for path, expected in immutable_before.items():
                    self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), expected)
            self.assertEqual(len(calls), 4)
            second = json.loads((directory/'round_001/discovery/registration.json').read_text())
            populations.append([(entry['sha256'], entry['genes']) for entry in second['candidates']])
            states.append(state)
            self.assertEqual(state['rounds_completed'], 2)
            self.assertFalse(state['promoted'])
            self.assertFalse(state['production_changed'])
            self.assertEqual(state['primary_campaign_games'], 0)
            self.assertEqual(state['games_bmcts_audited'], 0)
            self.assertEqual(state['audit_status'], 'pending_independent_review')
        self.assertEqual(populations[0], populations[1])
        self.assertTrue(states[0]['rounds'][0]['eligible_for_review'])
        self.assertFalse(states[1]['rounds'][0]['eligible_for_review'])
        self.assertEqual((ROOT/'bot.py').read_bytes(), baseline_before)

    def test_errors_fail_closed_and_never_modify_production(self):
        before = (ROOT/'bot.py').read_bytes()
        with mock.patch.object(league, 'evaluate_stage', side_effect=RuntimeError('deliberate evaluator failure')):
            with self.assertRaises(RuntimeError):
                league.run_league(self.directory, rounds=1, population=4,
                                  discovery_maps=1, confirmation_maps=1, workers=1)
        failure = json.loads((self.directory/'league_failure.json').read_text())
        self.assertFalse(failure['promoted'])
        self.assertFalse(failure['production_changed'])
        self.assertEqual(failure['rounds_completed'], 0)
        self.assertEqual((ROOT/'bot.py').read_bytes(), before)

    def test_independent_audit_failure_blocks_breeding(self):
        calls = []
        with mock.patch.object(league, 'evaluate_stage', side_effect=self.fake_evaluator(True, calls)), \
                mock.patch.object(league, 'independent_gate', side_effect=ValueError('deliberate independent veto')), \
                mock.patch.object(league, 'select_elites') as select:
            with self.assertRaisesRegex(ValueError, 'independent veto'):
                league.run_league(self.directory, rounds=2, population=4,
                                  discovery_maps=1, confirmation_maps=1, workers=1)
            select.assert_not_called()
        self.assertEqual(len(calls), 1)
        failure = json.loads((self.directory/'league_failure.json').read_text())
        self.assertEqual(failure['rounds_completed'], 0)
        self.assertFalse(failure['production_changed'])

    def test_changed_resume_settings_and_fingerprint_are_rejected(self):
        self.spec()
        with self.assertRaises(ValueError):
            league.load_spec(self.directory, 1987, 3, 8, 1, 1, 1)
        path = self.directory/'league_spec.json'
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(ValueError):
            self.spec()


if __name__ == '__main__':
    unittest.main()
