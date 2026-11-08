"""Bind shipped code, frozen comparison evidence, and saved visual evidence."""
import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    # Normalise line endings before hashing. git stores LF and may check a file
    # out as CRLF, so hashing raw bytes made this pass on the machine that
    # wrote the evidence and fail on every fresh clone.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def policy(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    params = None
    body = []
    for i, node in enumerate(tree.body):
        if i == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if (isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "PARAMS" for t in node.targets)):
            params = ast.literal_eval(node.value)
        else:
            body.append(node)
    assert params is not None, path
    tree.body = body
    return ast.dump(tree, include_attributes=False), params


def main():
    snapshot = ROOT / "audit" / "final_candidate_mybot.py"
    submitted = ROOT / "bot.py"
    frozen_ast, params = policy(snapshot)
    shipped_ast, shipped_params = policy(submitted)
    params.update(json.loads((ROOT / "v7_params.json").read_text()))
    assert frozen_ast == shipped_ast, "submission executable code differs from tested policy"
    assert params == shipped_params, "submission parameters differ from tested policy"
    results = json.loads((ROOT / "audit" / "final_comparison.json").read_text())
    assert not results["changed_sources"], "comparison source hash guards failed"
    assert results["current_snapshot_sha256"] == sha(snapshot)
    for row in results["results"]:
        assert not row["current"]["faults"]
        assert not row["baseline"]["faults"]
    replay = json.loads((ROOT / "visual" / "replays.json").read_text())
    assert replay["bot_sha256"] == sha(submitted)
    assert replay["engine_sha256"] == sha(ROOT / "engine.py")
    assert replay["independent_opponent_sha256"] == sha(ROOT / "audit" / "independent_bot.py")
    assert len(replay["games"]) == 5
    assert all(not g["failures"] for g in replay["games"])
    evidence = dict(
        bot_sha256=sha(submitted), candidate_sha256=sha(snapshot),
        live_source_matches_candidate=sha(ROOT / "mybot.py") == sha(snapshot),
        executable_ast_and_params_match=True, comparison_source_guards_pass=True,
        paired_tasks=len(results["results"]),
        observed_comparison_calls=sum(sum(r[v]["calls"]) for r in results["results"]
                                      for v in ("current", "baseline")),
        comparison_faults=0, visual_games=len(replay["games"]),
        visual_actions=sum((len(g["frames"])-1)*4 for g in replay["games"]),
        visual_faults=0,
    )
    (ROOT / "audit" / "final_artifact_verification.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
