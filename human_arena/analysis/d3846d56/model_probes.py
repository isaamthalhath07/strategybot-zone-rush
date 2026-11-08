"""Offline diagnostic ablations; no submitted or running bot is changed."""
import copy
import json
from pathlib import Path
import types

import analyze


def build(kind, seat):
    text = analyze.SOURCE.read_text(encoding="utf-8")
    if kind in ("no_postraid_upgrade", "both"):
        old = "if owner[i] != me and cost+3 <= left:"
        assert text.count(old) == 1
        text = text.replace(old, "if owner[i] == 0 and cost+3 <= left:")
    if kind in ("attribution_fix", "both"):
        old = "        just_shielded = set()"
        assert text.count(old) == 1
        text = text.replace(old, """        just_shielded = {me} if own_shield else set()
        visibly_worked = {owner[p] for p in range(64) if owner[p] and
            (owner[p] != prior_owner[p] or (level[p] and not old[\"level\"][p]))}""")
        old = "            if frozen[seat] and not old[\"frozen\"][seat] and defender in (0, seat):"
        assert text.count(old) == 1
        text = text.replace(old, """            if (frozen[seat] and not old[\"frozen\"][seat]
                    and defender not in (0, seat) and defender in visibly_worked):
                just_shielded.add(seat)  # Owner worked, so this must be self-backfire.
            if frozen[seat] and not old[\"frozen\"][seat] and defender in (0, seat):""")
        old = "if frozen[seat] and not frozen[defender] and prior_pos[defender] == positions[defender]:"
        assert text.count(old) == 1
        text = text.replace(old, "if (frozen[seat] and not frozen[defender] and prior_pos[defender] == positions[defender] and defender not in visibly_worked and not (seat == me and own_shield)):")
    module = types.ModuleType("probe_%s_%s" % (kind, seat))
    exec(compile(text, str(analyze.SOURCE) + ":offline-" + kind, "exec"), module.__dict__)
    if kind == "no_route":
        module.CONFIG["route_weight"] = 0.0
    return module


def rollout(data, variant, changed_seats):
    m = data["metadata"]
    game = analyze.referee.Referee(m["base"], rules=m["rules"], start_token=m["start_token"], max_turns=m["max_turns"])
    bots = {s: build(variant if s in changed_seats else "baseline", s)
            for s in range(1, 5) if s != m["human_seat"]}
    trajectory, faults, original_differences = [], [], []
    for original in data["turns"]:
        views = {s: game.observation(s) for s in range(1, 5)}
        actions = []
        for seat in range(1, 5):
            action = original["human_action"] if seat == m["human_seat"] else bots[seat].act(analyze.view(views[seat]))
            if action not in views[seat]["legal_actions"]:
                faults.append(dict(turn=game.turn, seat=seat, requested=action))
                action = "STAY"
            actions.append(action)
        result = game.step(actions)
        if game.snapshot() != original["after"]:
            original_differences.append(original["turn"])
        trajectory.append(dict(turn=original["turn"], actions=actions, score=game.score[:],
                               income=game.income(), events=result["events"]))
    if variant == "baseline":
        assert not original_differences
    return dict(variant=variant, changed_seats=changed_seats, score=game.score, income=game.income(),
                places=analyze.referee.places(game.score), faults=faults,
                first_changed_turn=original_differences[0] if original_differences else None,
                trajectory=trajectory)


def main():
    data = json.loads(analyze.INPUT.read_text(encoding="utf-8"))
    diagnostics = json.loads((analyze.OUT / "decisions.json").read_text())
    prior = {(d["turn"]+1, d["seat"]): d["memory"] for d in diagnostics}
    local = []
    for turn, seat in ((10,4),(37,4),(38,4),(42,4),(43,4),(47,4),(48,4),(49,4),(55,4),(56,4),(57,4),(55,2)):
        observation = data["turns"][turn-1]["observations"][str(seat)]
        for kind in ("baseline", "no_route", "no_postraid_upgrade", "attribution_fix", "both"):
            module = build(kind, seat)
            # Rebuild corrected beliefs from the ACTUAL observed prefix. Force
            # only actions/targets/baits that really occurred between calls,
            # rather than inheriting an already-corrupted baseline cooldown.
            for previous in data["turns"][:turn]:
                action = module.act(analyze.view(previous["observations"][str(seat)]))
                if previous["turn"] < turn:
                    original_memory = prior[(previous["turn"]+1, seat)]
                    for key in ("last", "prior_target", "last_bait"):
                        if key in original_memory:
                            module._history[seat][key] = copy.deepcopy(original_memory[key])
            memory = module._history[seat]
            local.append(dict(turn=turn, seat=seat, variant=kind, action=action,
                              target=memory.get("prior_target"), human_cooldown=memory["cooldown"][1],
                              own_cooldown=memory["cooldown"][seat]))
    rollouts = [rollout(data, "baseline", []),
                rollout(data, "no_postraid_upgrade", [4]),
                rollout(data, "attribution_fix", [4]),
                rollout(data, "attribution_fix", [2,3,4]),
                rollout(data, "both", [4]),
                rollout(data, "both", [2,3,4])]
    report = dict(caveat="Diagnostic ablations on ONE game. Human requested actions are held to the recorded script (illegal alternatives become STAY); all AI seats recompute from changed boards. The human could adapt. These results do not establish a stronger tournament policy and no variant was shipped.",
                  information="Variants use only documented current inputs and prior public observations; no hidden referee fields or future human moves enter their decisions.",
                  local_decisions=local, rollouts=rollouts)
    (analyze.OUT / "model_probes.json").write_text(json.dumps(report, separators=(",", ":")), encoding="utf-8")
    print(json.dumps([dict((k,v) for k,v in r.items() if k != "trajectory") for r in rollouts], indent=2))
    print("LOCAL:")
    for row in local:
        if row["turn"] in (42,55,56,57):
            print(row)


if __name__ == "__main__":
    main()
