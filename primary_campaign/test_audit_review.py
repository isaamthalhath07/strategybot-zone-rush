"""Independent adversarial acceptance checks; execute ZERO campaign games."""
import copy
from pathlib import Path
import tempfile
import unittest

from evolution.genomes import digest
from primary_campaign import core


class IndependentPrimaryReviewTests(unittest.TestCase):
    def setUp(self):
        self.cache = (core.ROOT/'.cache').resolve()
        self.temp = tempfile.TemporaryDirectory(prefix='primary-independent-review-', dir=self.cache)
        self.directory = Path(self.temp.name).resolve()
        self.assertTrue(self.directory.is_relative_to(self.cache))
        self.shape = dict(train_maps=8, development_maps=4, final_maps=4,
                          maps_per_generation=4, episodes_per_map=200, population=8)
        self.manifest = core.create_catalog(self.directory, 202611090741, self.shape)
        self.manifest, self.catalog = core.load_catalog(self.directory)
        self.registration = core.prepare_generation(self.directory, 0)
        self.stage = self.directory/'train_000'

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def overwrite_test_seal(path, value):
        """Simulate coherent corruption inside this disposable test directory."""
        body = core.canonical(value)+b'\n'
        path.write_bytes(body)
        path.with_suffix('.sha256').write_text(digest(body)+'\n', encoding='ascii')

    def reidentify_fixture(self, fixture):
        context = [self.manifest['campaign_id'], fixture['map_index'], fixture['episode']]
        for spec in fixture['opponents']:
            spec['id'] = digest(core.canonical(dict(
                context=context, seat=spec['seat'], spec={k: v for k, v in spec.items() if k != 'id'})))
        fixture['id'] = digest(core.canonical({k: v for k, v in fixture.items() if k != 'id'}))

    def test_rehashed_easier_rival_cannot_keep_a_strong_field_label(self):
        changed = copy.deepcopy(self.registration)
        fixture = next(f for f in changed['fixtures'] if f['field'] == 'economic')
        rival = next(s for s in fixture['opponents'] if s['family'] == 'planner')
        rival['family'] = 'wanderer'
        self.reidentify_fixture(fixture)
        with self.assertRaises(ValueError):
            core.validate_registration(changed, self.manifest, self.catalog)

    def test_rehashed_rival_seed_style_or_genome_cannot_change(self):
        for kind in ('seed', 'style', 'genome'):
            changed = copy.deepcopy(self.registration)
            fixture = next(f for f in changed['fixtures'] if f['field'] == 'economic')
            rival = next(s for s in fixture['opponents'] if s['family'] == 'planner')
            if kind == 'seed':
                rival['seed'] += 1
            elif kind == 'style':
                rival['epsilon'] = 2.0
            else:
                rival['genes']['depth'] = 1
            self.reidentify_fixture(fixture)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                core.validate_registration(changed, self.manifest, self.catalog)

    def test_small_mechanics_catalog_cannot_claim_full_primary_credit(self):
        changed = copy.deepcopy(self.manifest)
        changed.update(profile='full_primary', scheduled_games=2000000, training_generations=80)
        changed['campaign_id'] = digest(core.canonical({k: v for k, v in changed.items() if k != 'campaign_id'}))
        self.overwrite_test_seal(self.directory/'manifest.json', changed)
        with self.assertRaises(ValueError):
            core.load_catalog(self.directory)

    def test_resealed_phase_swap_cannot_move_a_holdout_into_training(self):
        changed_catalog = copy.deepcopy(self.catalog)
        train = next(b for b in changed_catalog if b['phase'] == 'train' and b['phase_index'] == 0)
        final = next(b for b in changed_catalog if b['phase'] == 'final' and b['phase_index'] == 0)
        train['phase'], final['phase'] = final['phase'], train['phase']
        self.overwrite_test_seal(self.directory/'catalog.json', changed_catalog)
        changed_manifest = copy.deepcopy(self.manifest)
        changed_manifest['catalog_sha256'] = digest((self.directory/'catalog.json').read_bytes())
        changed_manifest['campaign_id'] = digest(core.canonical({k: v for k, v in changed_manifest.items() if k != 'campaign_id'}))
        self.overwrite_test_seal(self.directory/'manifest.json', changed_manifest)
        with self.assertRaises(ValueError):
            core.load_catalog(self.directory)

    def test_manifest_identity_and_required_source_guards_are_enforced(self):
        variants = []
        changed = copy.deepcopy(self.manifest)
        changed['seed'] += 1  # Keep old identity and phase seeds, but reseal JSON.
        variants.append(changed)
        changed = copy.deepcopy(self.manifest)
        changed['guards'].pop(str((core.ROOT/'evolution/oversight.py').resolve()))
        changed['campaign_id'] = digest(core.canonical({k: v for k, v in changed.items() if k != 'campaign_id'}))
        variants.append(changed)
        for changed in variants:
            self.overwrite_test_seal(self.directory/'manifest.json', changed)
            with self.assertRaises(ValueError):
                core.load_catalog(self.directory)

    def write_empty_approved_claim(self):
        """No policy is called; this deliberately false claim must be rejected."""
        (self.stage/'games.jsonl').write_bytes(b'')
        (self.stage/'actor_audits.jsonl').write_bytes(b'')
        summary = dict(format=core.FORMAT, phase='train', generation=0,
                       profile=self.manifest['profile'], candidates=[], games_completed=800,
                       actual_callbacks=800*320, bmcts_audits=0, promoted=False,
                       registration_sha256=digest((self.stage/'registration.json').read_bytes()),
                       games_sha256=digest(b''))
        core.seal(self.stage/'summary.json', summary)
        claim = dict(format=core.FORMAT, approved=True, all_actors_regenerated=True,
                     campaign_id=self.manifest['campaign_id'], phase='train', generation=0,
                     profile=self.manifest['profile'], bmcts_audits=0, promoted=False,
                     registration_sha256=digest((self.stage/'registration.json').read_bytes()),
                     games_sha256=digest(b''), summary_sha256=digest((self.stage/'summary.json').read_bytes()),
                     actor_audits_sha256=digest(b''), games_audited=800,
                     callbacks_regenerated=800*320, public_memory_oracles=800*80,
                     primary_games_accepted=0, audit_replays_are_new_primary_games=False,
                     oversight_sha256=digest((core.ROOT/'evolution/oversight.py').read_bytes()))
        core.seal(self.stage/'audit.json', claim)

    def test_sealed_aggregate_flags_cannot_credit_empty_game_and_audit_files(self):
        self.write_empty_approved_claim()
        with self.assertRaisesRegex(ValueError, 'incomplete|coverage|actual'):
            core.validated_audit(self.stage)

    def test_false_previous_approval_cannot_breed_another_generation(self):
        self.write_empty_approved_claim()
        with self.assertRaises(ValueError):
            core.prepare_generation(self.directory, 1)
        self.assertFalse((self.directory/'train_001/registration.json').exists())

    def test_registration_cannot_silently_remove_guards_or_relabel_phase(self):
        variants = []
        changed = copy.deepcopy(self.registration)
        changed['guards'].pop(str((core.ROOT/'evolution/oversight.py').resolve()))
        variants.append(changed)
        changed = copy.deepcopy(self.registration)
        changed['phase'] = 'final'
        variants.append(changed)
        for changed in variants:
            with self.assertRaises(ValueError):
                core.validate_registration(changed, self.manifest, self.catalog)


if __name__ == '__main__':
    unittest.main()
