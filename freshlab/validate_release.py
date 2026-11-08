"""Bind the generated standalone bot to the pre-registered winning policy."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import time

import engine
from freshlab import baseline, candidate, evaluate, population


def main():
    root = Path(__file__).resolve().parents[1]
    artifact = root / "baselines/v8.py"
    result = json.loads((root / "freshlab/results/final.json").read_text())
    registration = json.loads((root / "freshlab/final_registration.json").read_text())
    if result["sources"] != evaluate.hashes() or result["sources"] != registration["sources"]:
        raise AssertionError("historical final sources changed; reproduce the original release at commit 9df9497 (the v8 export is preserved in baselines/v8.py)")
    if result["summary"]["raid_calibration"]["ci95"][0] <= 0:
        raise AssertionError("the pre-registered promotion rule did not pass")
    balanced_path = root / "freshlab/results/balanced_confirmation.json"
    balanced = json.loads(balanced_path.read_text())
    if balanced["sources"] != evaluate.hashes() or balanced["summary"]["raid_calibration"]["ci95"][0] <= 0:
        raise AssertionError("balanced independent confirmation did not pass")
    for filename, expected in balanced["extra_sources"].items():
        if hashlib.sha256((root / filename).read_bytes()).hexdigest() != expected:
            raise AssertionError("extra opponent or confirmation sources changed")
    spec = importlib.util.spec_from_file_location("fresh_release", artifact)
    shipped = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shipped)
    params = dict(baseline.PARAMS)
    params.update(json.loads((root / "v7_params.json").read_text()))
    params.update(throttle=0, budget_ms=10000.0, first_turn_ms=0)
    export_params = dict(shipped.PARAMS)
    expected_params = dict(baseline.PARAMS)
    expected_params.update(json.loads((root / "v7_params.json").read_text()))
    for k, v in candidate.VARIANTS["raid_calibration"]["scale"].items():
        expected_params[k] *= v
    if export_params != expected_params:
        raise AssertionError("exported parameters differ from tested candidate")
    count, worst = 0, 0.0
    for task in evaluate.tasks("final", 16, 739119):
        seat = task["seat"]
        reference = candidate.AdaptiveAgent(task["map_seed"], params,
                                             candidate.VARIANTS["raid_calibration"])
        release = shipped.Agent(seed=task["map_seed"], params={"throttle": 0, "budget_ms": 10000})
        others = iter(population.ProceduralOpponent(s) for s in task["specs"])
        bots = [reference if j == seat else next(others) for j in range(4)]
        game = engine.Game(base=task["base"], start_token=task["token"])
        while not game.over():
            views = game.views()
            actions = []
            for j, (bot, view) in enumerate(zip(bots, views)):
                before = evaluate.signature(view)
                action = bot(view)
                if j == seat:
                    start = time.perf_counter()
                    actual = release(view)
                    worst = max(worst, 1000*(time.perf_counter() - start))
                    if actual != action:
                        raise AssertionError("export diverged on game %d turn %d" % (task["id"], game.turn))
                    count += 1
                if action not in view.legal_actions or before != evaluate.signature(view):
                    raise AssertionError("export contract failed")
                actions.append(action)
            game.step(actions)
    source = artifact.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    if not imports <= {"time", "collections"}:
        raise AssertionError("unexpected submission dependency")
    payload = dict(bot_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
                   params_sha256=hashlib.sha256((root / "v8_fresh_params.json").read_bytes()).hexdigest(),
                   final_result_sha256=hashlib.sha256((root / "freshlab/results/final.json").read_bytes()).hexdigest(),
                   balanced_result_sha256=hashlib.sha256(balanced_path.read_bytes()).hexdigest(),
                   sources_unchanged=True, exact_policy_actions=count,
                   deterministic_policy_worst_ms=worst, imports=sorted(imports),
                   note="Pinned-clock equivalence checks. Actual timing guards are tested separately by ship.py and the public input contract.")
    (root / "freshlab/release_verification.json").write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
