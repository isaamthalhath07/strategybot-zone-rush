"""Bounded heldout protocol tests; mocked admission never grants primary credit."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evolution import runner
from primary_campaign import core as primary, run as primary_run
from campaign_holdout import authority, core, run


def admitted_fixture(directory):
    """Control-flow fixture only: training admission is explicitly mocked."""
    shape = dict(train_maps=4, development_maps=4, final_maps=4,
                 maps_per_generation=4, episodes_per_map=200, population=8)
    primary.create_catalog(directory, 202611090819, shape)
    manifest, catalog = primary.load_catalog(directory)
    registration = primary.prepare_generation(directory, 0)
    stage = directory/"train_000"
    # These are deliberately NON-game test inputs. Real _deep_training rejects
    # them; the mock is confined to testing MAC/freeze/control-flow behavior.
    for name in ("summary", "audit"):
        core.seal(stage/(name+".json"), {"mocked_training_admission": True})
    (stage/"games.jsonl").write_bytes(b'{"mocked_admission_only":true}\n')
    (stage/"actor_audits.jsonl").write_bytes(b'{"mocked_admission_only":true}\n')
    bindings = core._base_bindings(directory, manifest)
    core._bind(bindings, [stage/name for name in core.TRAIN_FILES])
    core._bind(bindings, [c["path"] for c in registration["candidates"]])
    stages = [dict(index=0, directory=str(stage), games=800, primary_games=0,
                   registration_sha256=core.digest((stage/"registration.json").read_bytes()),
                   audit_sha256=core.digest((stage/"audit.json").read_bytes()),
                   candidate_paths=[c["path"] for c in registration["candidates"]])]
    with patch.object(core, "_deep_training", return_value=(bindings, stages, registration)):
        shortlist = core.admit_development(directory)
    return manifest, catalog, registration, shortlist


class HeldoutTests(unittest.TestCase):
    def setUp(self):
        cache = (primary.ROOT/".cache").resolve()
        self.temp = tempfile.TemporaryDirectory(prefix="heldout-unit-", dir=cache)
        self.directory = Path(self.temp.name).resolve()
        self.assertTrue(self.directory.is_relative_to(cache))
        self.addCleanup(self.temp.cleanup)

    def admitted(self):
        return admitted_fixture(self.directory)

    def test_missing_training_audits_block_before_any_dev_registration(self):
        shape = dict(train_maps=4, development_maps=4, final_maps=4,
                     maps_per_generation=4, episodes_per_map=200, population=8)
        primary.create_catalog(self.directory, 202611090820, shape)
        primary.prepare_generation(self.directory, 0)
        with patch.object(primary, "validated_audit", side_effect=AssertionError("Missing-audit preflight did not stop")):
            with self.assertRaises(ValueError):
                core.admit_development(self.directory)
        self.assertFalse((authority.location(self.directory)/"development_000/registration.json").exists())

    def test_forged_training_approval_cannot_admit_empty_logs(self):
        shape = dict(train_maps=4, development_maps=4, final_maps=4,
                     maps_per_generation=4, episodes_per_map=200, population=8)
        primary.create_catalog(self.directory, 202611090821, shape)
        primary.prepare_generation(self.directory, 0)
        stage = self.directory/"train_000"
        core.seal(stage/"audit.json", dict(approved=True, phase="train", generation=0, profile="mechanics_test"))
        with self.assertRaises((ValueError, KeyError, FileNotFoundError)):
            core.admit_development(self.directory)
        self.assertFalse((authority.location(self.directory)/"shortlist.json").exists())

    def test_exact_last_stage_shortlist_and_metric_are_frozen(self):
        manifest, _, training, shortlist = self.admitted()
        self.assertEqual([c["sha256"] for c in shortlist["candidates"]], [c["sha256"] for c in training["candidates"]])
        self.assertEqual(shortlist["candidates"][0]["sha256"], primary.INCUMBENT)
        self.assertEqual(shortlist["metric"], core.METRIC)
        self.assertEqual(shortlist["final_training_generation"], manifest["training_generations"]-1)
        before = (authority.location(self.directory)/"shortlist.json").read_bytes()
        with patch.object(core, "_deep_training", side_effect=AssertionError("Consumed admission revalidated deeply")):
            self.assertEqual(core.admit_development(self.directory), shortlist)
        self.assertEqual((authority.location(self.directory)/"shortlist.json").read_bytes(), before)

    def test_development_tasks_are_balanced_and_final_is_early_blocked(self):
        _, catalog, training, shortlist = self.admitted()
        registration = core.prepare_stage(self.directory, "development", 0)
        self.assertEqual(core.validate_registration(self.directory, registration), dict(games=800, candidates=8, maps=4))
        self.assertEqual({f["map_index"] for f in registration["fixtures"]}, {4, 5, 6, 7})
        self.assertFalse({f["id"] for f in registration["fixtures"]} & {f["id"] for f in training["fixtures"]})
        self.assertFalse({s["id"] for f in registration["fixtures"] for s in f["opponents"]}
                         & {s["id"] for f in training["fixtures"] for s in f["opponents"]})
        with self.assertRaises((ValueError, FileNotFoundError)):
            core.prepare_stage(self.directory, "final", 0)
        with self.assertRaises(ValueError):
            core.admit_final(self.directory)
        self.assertFalse((authority.location(self.directory)/"final_000/registration.json").exists())

    def test_phase_map_opponent_and_policy_substitution_fail(self):
        self.admitted()
        original = core.prepare_stage(self.directory, "development", 0)
        variants = []
        changed = copy.deepcopy(original); changed["phase"] = "final"; variants.append(changed)
        changed = copy.deepcopy(original); changed["fixtures"][0]["map_index"] = 0; variants.append(changed)
        changed = copy.deepcopy(original); changed["fixtures"][0]["opponents"][0]["family"] = "wanderer"; variants.append(changed)
        changed = copy.deepcopy(original); changed["candidates"] = list(reversed(changed["candidates"])); variants.append(changed)
        for changed in variants:
            with self.assertRaises((ValueError, FileNotFoundError)):
                core.validate_registration(self.directory, changed)

    def test_one_real_game_and_all_actor_proof_then_bad_result_rejected(self):
        self.admitted()
        registration = core.prepare_stage(self.directory, "development", 0)
        fixture = registration["fixtures"][0]
        candidate = next(c for c in registration["candidates"] if c["sha256"] == fixture["candidate"])
        row = runner.play_game(candidate, fixture, registration["sources"])
        proof = primary_run.audit_task(candidate, fixture, registration["sources"], row)
        key_id = run._authority(self.directory)
        envelope = authority.sign(self.directory, key_id, run._proof_purpose(registration), proof)
        self.assertEqual(run._validate_actor(self.directory, registration, envelope, row)["callbacks_regenerated"], 320)
        stage = core.stage_path(self.directory, "development", 0)
        (stage/"games.jsonl").write_bytes(primary.canonical(row)+b"\n")
        self.assertEqual(len(run.read_rows(stage, registration)), 1)
        with self.assertRaises((ValueError, FileNotFoundError)):
            run.validate_completed_stage(self.directory, "development", 0)
        changed = copy.deepcopy(row); changed["scores"][0] += 1
        (stage/"games.jsonl").write_bytes(primary.canonical(changed)+b"\n")
        with self.assertRaises(ValueError):
            run.read_rows(stage, registration)

    def test_completed_execution_resume_never_submits_or_rewrites(self):
        self.admitted()
        registration = core.prepare_stage(self.directory, "development", 0)
        stage = core.stage_path(self.directory, "development", 0)
        core.seal(stage/"summary.json", {"mocked_complete_summary": True})
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in stage.iterdir() if p.is_file()}
        # Execution control-flow only; no actual completed numerical proof is claimed.
        expected = {"mocked_complete_summary": True}
        with patch.object(run, "_completed_summary", return_value=(expected, [])), \
                patch.object(run, "_pool_results", side_effect=AssertionError("Completed tasks resubmitted")):
            self.assertEqual(run.execute_stage(self.directory, "development", 0), expected)
        after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in stage.iterdir() if p.is_file()}
        self.assertEqual(before, after)

    def test_all_dev_results_select_one_policy_before_final_and_final_data_cannot_reselect(self):
        self.admitted()
        registration = core.prepare_stage(self.directory, "development", 0)
        stage = core.stage_path(self.directory, "development", 0)
        desired = registration["candidates"][2]["sha256"]
        # Aggregation/control-flow test only. These deliberately incomplete rows
        # cannot pass a real actor/physical stage audit; admission is mocked.
        rows = [dict(fixture=f["id"], candidate=f["candidate"], focal_pw=3.0 if f["candidate"] == desired else 1.0,
                     focal_score=3000 if f["candidate"] == desired else 2000) for f in registration["fixtures"]]
        (stage/"games.jsonl").write_bytes(b"".join(primary.canonical(r)+b"\n" for r in rows))
        (stage/"active_audit.json").write_bytes(b'{"mocked_dev_stage_for_selector_only":true}\n')
        with patch.object(core, "validated_stage", return_value=dict(games_audited=800, primary_games_accepted=0)), \
                patch.object(run, "stage_artifacts", return_value=[stage/"registration.json", stage/"games.jsonl", stage/"active_audit.json"]):
            selection = core.admit_final(self.directory)
        self.assertEqual(selection["winner_sha256"], desired)
        self.assertEqual(selection["development_games"], 800)
        final = core.prepare_stage(self.directory, "final", 0)
        self.assertEqual([c["sha256"] for c in final["candidates"]], [desired])
        self.assertEqual({f["candidate"] for f in final["fixtures"]}, {desired})
        self.assertEqual({f["map_index"] for f in final["fixtures"]}, {8, 9, 10, 11})
        # Post-selection data is never input to the selector.
        (core.stage_path(self.directory, "final", 0)/"games.jsonl").write_bytes(b'{"not_valid_evidence":true}\n')
        with patch.object(core, "validated_stage", side_effect=AssertionError("Final data prompted reselection")):
            self.assertEqual(core.admit_final(self.directory), selection)


if __name__ == "__main__":
    unittest.main()
