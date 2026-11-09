"""Evolution contracts: unchanged policy logic, independent games and map balance."""
import ast
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest import mock
from concurrent.futures import Future

from evolution.genomes import GenomeSpace
from evolution import maps
from evolution.opponents import FAMILIES, Rival
from evolution import runner
from tests import reference_engine as engine


ROOT = Path(__file__).resolve().parents[1]


def observation_signature(public):
    return (public.bot_id, public.is_priority_token, tuple(public.legal_actions),
            tuple((cell.occupant, cell.owner, cell.is_upgraded, cell.is_home,
                   cell.is_frozen, cell.base_points)
                  for row in public.board for cell in row))


def without_config_bytes(body):
    """Compare every byte outside the explicitly tunable assignment."""
    text = body.decode('utf8')
    node = next(node for node in ast.parse(text).body
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == 'CONFIG'
                    for target in node.targets))
    lines = text.splitlines(keepends=True)
    return ''.join(lines[:node.lineno-1]), ''.join(lines[node.end_lineno:])


class EvolutionGenomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body = (ROOT/'bot.py').read_bytes()
        cls.space = GenomeSpace(cls.body)

    def test_incumbent_is_an_exact_export_and_its_state_is_not_shared(self):
        self.assertEqual(self.space.export(dict(self.space.genes)), self.body)
        modules = []
        for _ in range(2):
            namespace = {'__name__': 'independent_evolution_candidate'}
            exec(compile(self.body, '<candidate>', 'exec'), namespace)
            modules.append(namespace)
        public = engine.Game().views()[0]
        before = observation_signature(public)
        first = modules[0]['act'](public)
        self.assertTrue(modules[0]['_history'])
        self.assertFalse(modules[1]['_history'])
        self.assertEqual(modules[1]['act'](public), first)
        self.assertEqual(observation_signature(public), before)

    def test_exported_mutations_change_only_config_bytes(self):
        baseline_rest = without_config_bytes(self.body)
        for seed in range(24):
            child = self.space.mutate(self.space.genes, seed,
                                      grouped=bool(seed % 2))
            exported = self.space.export(child)
            self.assertEqual(without_config_bytes(exported), baseline_rest)
            parsed = GenomeSpace(exported)
            self.assertEqual(parsed.genes, child)
            self.assertEqual(parsed.bounds, self.space.bounds)
            self.assertEqual(parsed.integer, self.space.integer)
            namespace = {'__name__': 'exported_evolution_candidate'}
            exec(compile(exported, '<export>', 'exec'), namespace)
            self.assertEqual(namespace['CONFIG'], child)
            for guard in ('conditional_postraid_upgrade', 'renewal_guard',
                          'imminent_shield'):
                self.assertTrue(namespace['DEFAULT_CONFIG'][guard])
                self.assertNotIn(guard, child)

    def test_mutation_and_crossover_preserve_bounds_and_do_not_touch_global_rng(self):
        before = random.getstate()
        parent = dict(self.space.genes)
        original = dict(parent)
        for seed in range(400):
            child = self.space.mutate(parent, seed, grouped=bool(seed % 2))
            self.assertEqual(child, self.space.mutate(parent, seed,
                                                     grouped=bool(seed % 2)))
            self.space.validate(child)
            crossed = self.space.crossover(parent, child, seed)
            self.space.validate(crossed)
            self.assertEqual(crossed, self.space.crossover(parent, child, seed))
            self.assertTrue(all(crossed[key] in (parent[key], child[key])
                                for key in crossed))
        self.assertEqual(parent, original)
        self.assertEqual(random.getstate(), before)

    def test_invalid_and_correctness_genes_cannot_be_exported(self):
        key = 'shield_weight'
        invalid = []
        for value in (float('inf'), float('-inf'), float('nan'), True, '1',
                      self.space.bounds[key][0]-0.01,
                      self.space.bounds[key][1]+0.01):
            invalid.append(dict(self.space.genes, **{key: value}))
        invalid.append(dict(self.space.genes, depth=2.0))
        invalid.append(dict(self.space.genes, renewal_guard=False))
        missing = dict(self.space.genes)
        del missing[key]
        invalid.append(missing)
        for genes in invalid:
            with self.assertRaises(ValueError):
                self.space.export(genes)


class EvolutionMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.excluded = [engine.make_map(canonical=True)]
        for relative in ('validation/official/screen_spec.json',
                         'validation/official/selection_spec.json',
                         'validation/official/final_spec.json',
                         'validation/official/followup_spec.json'):
            spec = json.loads((ROOT/relative).read_text(encoding='utf8'))
            cls.excluded.extend(fixture['base'] for fixture in spec['fixtures'])
        cls.generated = maps.generate(10000, 202611082210, cls.excluded)

    def test_ten_thousand_content_distinct_legal_maps_exclude_prior_boards(self):
        self.assertEqual(len(self.generated), 10000)
        bases = {tuple(row['base']) for row in self.generated}
        self.assertEqual(len(bases), 10000)
        self.assertFalse(bases & {tuple(base) for base in self.excluded})
        ids = set()
        for row in self.generated:
            base = row['base']
            self.assertTrue(maps.valid(base))
            self.assertEqual(len(base), 64)
            self.assertTrue(all(type(value) is int and 1 <= value <= 3 for value in base))
            for r in range(8):
                for c in range(8):
                    self.assertEqual(base[r*8+c], base[r*8+7-c])
                    self.assertEqual(base[r*8+c], base[(7-r)*8+c])
            self.assertEqual(row['id'], hashlib.sha256(bytes(base)).hexdigest())
            ids.add(row['id'])
        self.assertEqual(len(ids), 10000)

    def test_map_reproduction_preserves_global_rng_and_exclusion_input(self):
        before_rng = random.getstate()
        before_excluded = copy.deepcopy(self.excluded)
        prefix = maps.generate(50, 202611082210, self.excluded)
        self.assertEqual(prefix, self.generated[:50])
        self.assertEqual(self.excluded, before_excluded)
        self.assertEqual(random.getstate(), before_rng)

    def test_two_million_games_have_balanced_seat_and_token_crossings(self):
        total = Counter()
        for map_index in range(10000):
            local = Counter(maps.seat_token(map_index, episode)
                            for episode in range(200))
            self.assertEqual(set(local.values()), {12, 13})
            self.assertEqual(len(local), 16)
            for seat in range(4):
                self.assertEqual(sum(n for (s, t), n in local.items() if s == seat), 50)
            for token in range(1, 5):
                self.assertEqual(sum(n for (s, t), n in local.items() if t == token), 50)
            total.update(local)
        self.assertEqual(sum(total.values()), 2000000)
        self.assertEqual(set(total.values()), {125000})


class EvolutionOpponentTests(unittest.TestCase):
    def test_seeded_rivals_are_independent_reproducible_and_public_only(self):
        before_rng = random.getstate()
        for family_index, family in enumerate(FAMILIES):
            specs = [dict(family=family, seed=1000*family_index+seat,
                          epsilon=seat/12, commitment=0.75)
                     for seat in range(4)]
            left = [Rival(spec) for spec in specs]
            right = [Rival(spec) for spec in specs]
            unrelated = Rival(dict(family='wanderer', seed=193,
                                   epsilon=0.9, commitment=0.5))
            games = [engine.Game(base=engine.make_map(971+family_index),
                                 rules={'catch_requires_stay': True})
                     for _ in range(2)]
            for _ in range(80):
                public_left, public_right = games[0].views(), games[1].views()
                a, b = [], []
                for seat in range(4):
                    public = public_left[seat]
                    self.assertEqual(set(type(public).__slots__),
                                     {'board', 'bot_id', 'is_priority_token', 'legal_actions'})
                    before = observation_signature(public)
                    action = left[seat].act(public)
                    self.assertIn(action, public.legal_actions)
                    self.assertEqual(before, observation_signature(public))
                    a.append(action)
                    unrelated.act(public)
                    other = right[seat].act(public_right[seat])
                    self.assertIn(other, public_right[seat].legal_actions)
                    b.append(other)
                self.assertEqual(a, b)
                games[0].step(a)
                games[1].step(b)
                self.assertEqual(games[0].score, games[1].score)
            self.assertTrue(all(rival.turn == 80 for rival in left+right))
        self.assertEqual(random.getstate(), before_rng)

    def test_hidden_referee_values_cannot_change_an_identical_public_decision(self):
        first = engine.Game()
        second = first.clone()
        second.cd[1:] = [4, 2, 1]
        second.prog[1:] = [2, 1, 2]
        second.score[1:] = [700, 800, 900]
        public_a, public_b = first.views()[0], second.views()[0]
        self.assertEqual(observation_signature(public_a), observation_signature(public_b))
        for family in FAMILIES:
            spec = dict(family=family, seed=1133, epsilon=0.2, commitment=0.7)
            self.assertEqual(Rival(spec).act(public_a), Rival(spec).act(public_b))


class InlineExecutor:
    """Exercise durable dispatch without spawning a pool for each test case."""
    def __init__(self, **kwargs):
        if kwargs.get('initializer'):
            kwargs['initializer']()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def submit(self, function, *args):
        future = Future()
        try:
            future.set_result(function(*args))
        except BaseException as error:
            future.set_exception(error)
        return future


class EvolutionRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {name: runner.source_entry(ROOT/relative) for name, relative in {
            'planner': 'bot.py', 'research': 'tester_bots/research_alternative.py',
            'racer': 'tester_bots/racer.py', 'blocker': 'tester_bots/blocker.py'}.items()}
        cls.candidate = dict(name='incumbent', **runner.source_entry(ROOT/'bot.py'))
        cls.space = GenomeSpace((ROOT/'bot.py').read_bytes())

    def fixture(self, families):
        base = engine.make_map(202611082229)
        specs = []
        for seat, family in enumerate(families, 1):
            spec = dict(seat=seat, family=family, seed=70+seat,
                        epsilon=0.1, commitment=0.7)
            if family in ('planner', 'research'):
                spec['genes'] = dict(self.space.genes)
            spec['id'] = runner.digest(runner.canonical(spec))
            specs.append(spec)
        fixture = dict(base=base, map_id=hashlib.sha256(bytes(base)).hexdigest(),
                       seat=0, token=3, field='test', opponents=specs)
        fixture['id'] = runner.digest(runner.canonical(fixture))
        return fixture

    def test_complete_mixed_games_reproduce_without_cross_game_memory(self):
        for families in (('planner', 'racer', 'blocker'),
                         ('research', 'farmer', 'feinter')):
            fixture = self.fixture(families)
            first = runner.play_game(self.candidate, fixture, self.sources)
            second = runner.play_game(self.candidate, fixture, self.sources)
            runner.verify_row(first, self.candidate, fixture)
            self.assertEqual(first['actions'], second['actions'])
            self.assertEqual(first['scores'], second['scores'])
            self.assertEqual(sum(t['calls'] for t in first['timing']), 320)
            self.assertFalse(first['faults'])
            self.assertEqual(first['focal_seat'], fixture['seat'])

    def test_replay_rejects_tampered_scores_actions_identities_and_timing(self):
        fixture = self.fixture(('planner', 'racer', 'blocker'))
        original = runner.play_game(self.candidate, fixture, self.sources)
        variants = []
        for key, value in (('candidate', 'wrong'), ('fixture', 'wrong'),
                           ('map_id', 'wrong'), ('field', 'wrong'),
                           ('focal_seat', 2), ('focal_pw', -1),
                           ('focal_score', -1), ('faults', ['ignored fallback'])):
            row = copy.deepcopy(original)
            row[key] = value
            variants.append(row)
        row = copy.deepcopy(original)
        row['scores'][0] += 1
        variants.append(row)
        row = copy.deepcopy(original)
        row['opponent_ids'][0] = 'wrong'
        variants.append(row)
        row = copy.deepcopy(original)
        row['actions'][0][0] = 'TELEPORT'
        variants.append(row)
        row = copy.deepcopy(original)
        row['actions'].pop()
        variants.append(row)
        for key, value in (('calls', True), ('calls', 79), ('max_ms', float('nan')),
                           ('total_ms', -1), ('total_ms', float('inf')),
                           ('first_ms', 2000.1), ('regular_max_ms', 200.1)):
            row = copy.deepcopy(original)
            row['timing'][0][key] = value
            variants.append(row)
        for row in variants:
            with self.assertRaises(ValueError):
                runner.verify_row(row, self.candidate, fixture)

    def test_focal_timing_is_distinct_from_opponent_timing(self):
        fixture = self.fixture(('planner', 'racer', 'blocker'))
        row = runner.play_game(self.candidate, fixture, self.sources)
        row['timing'][0]['max_ms'] = 1.0
        row['timing'][1]['max_ms'] = 190.0
        summary = runner.summarize([row], [self.candidate])[0]
        self.assertEqual(summary['max_ms'], 1.0)
        self.assertEqual(summary['all_player_max_ms'], 190.0)

    def test_cached_source_still_rejects_a_changed_file(self):
        cache = ROOT/'.cache'
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='evolution-source-test-', dir=cache) as name:
            path = Path(name)/'candidate.py'
            path.write_bytes((ROOT/'bot.py').read_bytes())
            expected = self.candidate['sha256']
            runner.namespace(path, expected)
            path.write_bytes(path.read_bytes()+b'\n# changed\n')
            with self.assertRaises(ValueError):
                runner.namespace(path, expected)

    def test_actor_mutation_and_silent_fallbacks_invalidate_the_game(self):
        fixture = self.fixture(('farmer', 'feinter', 'wanderer'))

        def mutate(public):
            self.assertEqual(set(public.__slots__),
                             {'board', 'bot_id', 'legal_actions', 'is_priority_token'})
            public.board[0][0].owner = 99
            return 'STAY'

        examples = [dict(act=mutate),
                    dict(act=lambda public: 'STAY', _input_failures=1),
                    dict(act=lambda public: 'STAY', _policy_failures=1),
                    dict(act=lambda public: 'STAY', _history={1: {
                        'inference_failures': 1, 'progress': 0,
                        'scores': [0]*5, 'cooldown_possible': [set()]+[{0} for _ in range(4)]}})]
        for namespace in examples:
            with mock.patch.object(runner, 'namespace', return_value=namespace):
                with self.assertRaises(ValueError):
                    runner.play_game(self.candidate, fixture, self.sources)

    def test_registration_balances_each_field_across_seat_token_pairs(self):
        cache = ROOT/'.cache'
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='evolution-registration-test-', dir=cache) as name:
            registration = runner.create_registration(Path(name)/'new', 202611082230, 8, 2)
            self.assertFalse(registration['promotion_allowed'])
            self.assertEqual(registration['candidates'][0]['sha256'], self.candidate['sha256'])
            fields = {}
            opponent_ids = []
            for fixture in registration['fixtures']:
                fields.setdefault(fixture['field'], Counter()).update([(fixture['seat'], fixture['token'])])
                self.assertEqual({spec['seat'] for spec in fixture['opponents']},
                                 set(range(4))-{fixture['seat']})
                opponent_ids.extend(spec['id'] for spec in fixture['opponents'])
            self.assertEqual(len(set(opponent_ids)), len(opponent_ids))
            for crossings in fields.values():
                self.assertEqual(len(crossings), 16)
                self.assertEqual(set(crossings.values()), {2})

    def test_completed_resume_replays_nothing_and_rejects_registration_changes(self):
        cache = ROOT/'.cache'
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='evolution-resume-test-', dir=cache) as name:
            directory = Path(name)/'new'
            runner.create_registration(directory, 202611082231, 1, 1)
            with mock.patch.object(runner, 'ProcessPoolExecutor', InlineExecutor):
                first = runner.evaluate(directory, 1)
            rows_before = (directory/'games.jsonl').read_bytes()
            with mock.patch.object(runner, 'ProcessPoolExecutor', InlineExecutor), \
                    mock.patch.object(InlineExecutor, 'submit', side_effect=AssertionError('Repeated task')):
                second = runner.evaluate(directory, 1)
            self.assertEqual((directory/'games.jsonl').read_bytes(), rows_before)
            self.assertEqual(first, second)
            self.assertEqual(first['games_completed'], 16)
            self.assertEqual(first['callbacks'], 5120)
            self.assertEqual(first['primary_campaign_games'], 0)
            self.assertEqual(first['games_bmcts_audited'], 0)
            self.assertFalse(first['promoted'])
            # Interrupted appends are preserved and removed before retrying;
            # complete corrupt rows must never be silently discarded.
            result_path = directory/'games.jsonl'
            tail = b'{"candidate":"interrupted'
            result_path.write_bytes(rows_before+tail)
            with mock.patch.object(runner, 'ProcessPoolExecutor', InlineExecutor), \
                    mock.patch.object(InlineExecutor, 'submit', side_effect=AssertionError('Repeated task')):
                recovered = runner.evaluate(directory, 1)
            self.assertEqual(recovered, first)
            self.assertEqual(result_path.read_bytes(), rows_before)
            backups = list(directory.glob('interrupted-tail-*.bin'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), tail)
            lines = rows_before.splitlines(keepends=True)
            changed_row = json.loads(lines[0])
            changed_row['scores'][0] += 1
            corruptions = [runner.canonical(changed_row)+b'\n'+b''.join(lines[1:]),
                           rows_before+lines[0], rows_before+b'{broken JSON\n']
            for corrupted in corruptions:
                result_path.write_bytes(corrupted)
                with self.assertRaises(ValueError):
                    runner.evaluate(directory, 1)
            result_path.write_bytes(rows_before)
            path = directory/'registration.json'
            changed = json.loads(path.read_text(encoding='utf8'))
            changed['seed'] += 1
            path.write_text(json.dumps(changed), encoding='utf8')
            with self.assertRaises(ValueError):
                runner.evaluate(directory, 1)


if __name__ == '__main__':
    unittest.main()
