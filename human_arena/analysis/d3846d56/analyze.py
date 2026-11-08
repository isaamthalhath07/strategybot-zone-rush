"""Verify the provided match and inspect the exact frozen AI offline."""
import copy
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
INPUT = Path(r"C:\Users\LEGION\Downloads\zone-rush-d3846d56f462413789041954bdc8bc38.json")
VENDOR = ROOT / "human_arena" / "vendor_harness"
SOURCE = ROOT / "human_arena" / "bot_snapshots" / "0796039f42f0113d7c4f51b2f8e1409835f2c519" / "outputs" / "bot.py"
sys.path.insert(0, str(VENDOR))
import referee
from worker import Cell, Game


def coord(p):
    return chr(65 + p % 8) + str(p // 8 + 1)


def load_bot(seat):
    spec = importlib.util.spec_from_file_location("analyzed_seat_%d" % seat, SOURCE)
    module = importlib.util.module_from_spec(spec)
    module._analysis_values = []
    def record_value(scope):
        module._analysis_values.append({key: copy.deepcopy(scope.get(key)) for key in
            ("i", "rate", "next_rate", "value", "cost", "work", "effort", "reward", "second", "second_cost")})
    module._analysis_record = record_value
    class Instrument(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name != "act":
                return node
            return self.generic_visit(node)

        def visit_Assign(self, node):
            if any(isinstance(target, ast.Name) and target.id == "value" for target in node.targets):
                added = ast.parse("_analysis_record(locals())").body[0]
                return [node, ast.copy_location(added, node)]
            return node
    tree = ast.fix_missing_locations(Instrument().visit(ast.parse(SOURCE.read_text(encoding="utf-8"))))
    exec(compile(tree, str(SOURCE), "exec"), module.__dict__)
    return module


def view(obs):
    return Game([[Cell(*c) for c in row] for row in obs["board"]], obs["bot_id"],
                obs["is_priority_token"], obs["legal_actions"][:])


def inspect_decision(module, obs):
    captured = {}
    module._analysis_values.clear()
    wanted = ("memory", "tasks", "at", "left", "pressure", "travel", "first",
              "chosen_cell", "best_value", "best_action", "projection", "denial",
              "exposure", "threat", "miss", "normal_rate", "risk_weight", "upgrade", "raid")

    def profile(frame, event, arg):
        if event == "return" and frame.f_code is module.act.__code__:
            for key in wanted:
                if key in frame.f_locals:
                    captured[key] = copy.deepcopy(frame.f_locals[key])
            captured["returned"] = arg

    sys.setprofile(profile)
    try:
        action = module.act(view(obs))
    finally:
        sys.setprofile(None)
    captured["macro_values"] = copy.deepcopy(module._analysis_values)
    return action, captured


def main():
    raw = INPUT.read_bytes()
    data = json.loads(raw)
    meta, turns = data["metadata"], data["turns"]
    assert data["game_id"] == "d3846d56f462413789041954bdc8bc38"
    assert not meta.get("partial") and not data.get("incomplete_last_record")
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == meta["bot"]["sha256"]
    assert hashlib.sha256((VENDOR / "referee.py").read_bytes()).hexdigest() == meta["referee_sha256"]
    assert hashlib.sha256(json.dumps(meta["rules"], sort_keys=True, separators=(",", ":")).encode()).hexdigest() == meta["rules_sha256"]
    game = referee.Referee(meta["base"], rules=meta["rules"], start_token=meta["start_token"], max_turns=meta["max_turns"])
    assert game.snapshot() == meta["initial"]
    bots = {seat: load_bot(seat) for seat in range(1, 5) if seat != meta["human_seat"]}
    decisions, mismatches, belief_errors = [], [], []
    events, timeline = [], []
    actions = [Counter() for _ in range(4)]
    bonuses = [0] * 4
    income = [0] * 4
    for record in turns:
        assert record["turn"] == game.turn
        assert game.snapshot() == record["before"]
        for seat in range(1, 5):
            assert game.observation(seat) == record["observations"][str(seat)]
            assert record["used"][seat-1] in game.legal(seat-1)
            actions[seat-1][record["used"][seat-1]] += 1
        for seat, module in bots.items():
            action, diagnostic = inspect_decision(module, record["observations"][str(seat)])
            returned = record["bots"][seat-1].get("chosen")
            if action != returned:
                mismatches.append(dict(turn=game.turn, seat=seat, replay=action, recorded=returned))
            mem = diagnostic.get("memory", {})
            truth = record["before"]
            fields = {"turn": (mem.get("turn"), truth["turn"]),
                      "own_progress": (mem.get("progress"), truth["prog"][seat-1]),
                      "scores": (mem.get("scores", [])[1:], truth["score"]),
                      "own_cooldown": (mem.get("cooldown", [0]*5)[seat], truth["cd"][seat-1])}
            for name, (estimated, actual) in fields.items():
                if estimated != actual:
                    belief_errors.append(dict(turn=game.turn, seat=seat, field=name, estimated=estimated, actual=actual))
            diagnostic.update(turn=game.turn, seat=seat, recorded=record["bots"][seat-1],
                              before=truth)
            decisions.append(diagnostic)
        resolved = game.step(record["used"])
        assert resolved == record["resolved"]
        assert game.snapshot() == record["after"]
        for i in range(4):
            bonuses[i] += resolved["bonus"][i]
            income[i] += resolved["income"][i]
        events.extend(dict(turn=record["turn"], **e) for e in resolved["events"])
        timeline.append(dict(turn=record["turn"], score=game.score[:], income=game.income(),
                             pos=game.pos[:], owner=game.owner[:], upg=game.upg[:],
                             frozen=game.frozen[:], cooldown=game.cd[:], progress=game.prog[:],
                             used=record["used"], resolved=resolved))
    assert data["ending"]["final"] == game.snapshot()
    assert [income[i]+bonuses[i] for i in range(4)] == game.score
    core = {27, 28, 35, 36}
    high = {i for i, value in enumerate(meta["base"]) if value == 3}
    faults = [dict(turn=r["turn"], seat=s+1, status=b.get("status"), error=b.get("error"))
              for r in turns for s, b in enumerate(r["bots"]) if b.get("status") != "ok"]
    summary = dict(game_id=data["game_id"], turns=len(turns), source_sha256=meta["bot"]["sha256"],
                   input_sha256=hashlib.sha256(raw).hexdigest(), all_physical_transitions_exact=True,
                   all_worker_inputs_exact=True, policy_calls=len(decisions), policy_action_mismatches=mismatches,
                   belief_errors=belief_errors, final=game.snapshot(), ownership_income=income,
                   raid_bonuses=bonuses, action_counts=[dict(c) for c in actions], faults=faults,
                   max_ai_ms=max(b["ms"] for r in turns for b in r["bots"] if b.get("ms") is not None),
                   core_cells=[coord(p) for p in sorted(core)], high_cells=[coord(p) for p in sorted(high)],
                   center_events=[e for e in events if e.get("cell") in core],
                   event_counts=[dict(Counter(e["type"] for e in events if e.get("seat")==s)) for s in range(1,5)])
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "decisions.json").write_text(json.dumps(decisions, separators=(",", ":")), encoding="utf-8")
    (OUT / "timeline.json").write_text(json.dumps(dict(metadata=meta, turns=timeline, events=events), separators=(",", ":")), encoding="utf-8")
    print(json.dumps({k:summary[k] for k in ("turns", "policy_calls", "policy_action_mismatches", "ownership_income", "raid_bonuses", "action_counts", "faults", "max_ai_ms", "center_events")}, indent=2))
    print("Belief-error counts:", dict(Counter(e["field"] for e in belief_errors)))


if __name__ == "__main__":
    main()
