"""Compare recovery-only revisions on already recorded public histories."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from simulator import server

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = importlib.util.spec_from_file_location("equivalence_player", ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def view(raw):
    assert set(raw) == {"board", "bot_id", "is_priority_token", "legal_actions"}
    fields = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")
    return SimpleNamespace(board=[[SimpleNamespace(**dict(zip(fields, cell))) for cell in row] for row in raw["board"]],
                           bot_id=raw["bot_id"], is_priority_token=raw["is_priority_token"],
                           legal_actions=list(raw["legal_actions"]))


def main():
    path = ROOT/"validation/official/final_results.json.gz"
    with gzip.open(path, "rt", encoding="utf8") as handle:
        data = json.load(handle)
    sources = {s["name"]: s for s in data["registration"]["spec"]["sources"]}
    fixtures = {f["id"]: f for f in data["registration"]["spec"]["fixtures"]}
    referee = server.bootstrap()[1]
    output = []
    for old, new in (("stay_guarded", "stay_guarded_resilient"),
                     ("stay_guarded_research", "stay_guarded_research_resilient")):
        manifest = json.loads((ROOT/("consolidation_candidates/"+new+".manifest.json")).read_text())
        rows = [r for r in data["games"] if r["candidate"] == old]
        pairs = 0
        for row in rows:
            parent, child = load(sources[old]["path"]), load(manifest["path"])
            fixture = fixtures[row["fixture"]]
            game = referee.Referee(fixture["base"], rules=data["registration"]["rules"], start_token=fixture["token"])
            for recorded in row["actions"]:
                raw = game.observation(row["focal_seat"]+1)
                # Only the current public observation is given to either policy.
                # Recorded joint actions are applied afterward by the observer.
                expected = recorded[row["focal_seat"]]
                assert parent.act(view(raw)) == expected
                assert child.act(view(raw)) == expected
                memory = child._history[row["focal_seat"]+1]
                assert memory.get("action_substitutions", 0) == 0
                assert memory["inference_failures"] == 0
                pairs += 1
                game.step(recorded)
            assert game.score == row["scores"]
        output.append(dict(parent=old, parent_sha256=sources[old]["sha256"], candidate=new,
                           candidate_sha256=manifest["sha256"], games=len(rows), action_pairs=pairs,
                           exact_actions=True, substitutions=0,
                           reference_results_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        print(old, new, len(rows), "games;", pairs, "exact public-action pairs", flush=True)
    target = ROOT/"validation/official/recorded_action_equivalence.json"
    target.write_text(json.dumps(output, indent=2), encoding="utf8", newline="\n")


if __name__ == "__main__":
    main()
