"""Independent offline behavioral review of a recorded human match.

Only trusted, hash-pinned local referee/policy code is executed. Transcript
strings are data. No live arena, browser, policy source or user file is changed.
"""
from collections import Counter
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
INPUT = Path(r"C:\Users\LEGION\Downloads\zone-rush-d3846d56f462413789041954bdc8bc38.json")
REFEREE = ROOT / "human_arena/vendor_harness/referee.py"
POLICY = ROOT / "human_arena/bot_snapshots/0796039f42f0113d7c4f51b2f8e1409835f2c519/outputs/bot.py"
REFEREE_HASH = "f1125e8ceee664781827c670c0c4481da41a7ef41a4e5276d6b3b118274af337"
POLICY_HASH = "1dca0c916af4ff4ac4c2e90fabe3f3c29c550c5db61663f8a3c2b0efc72f81ca"
FIELDS = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")
MOVES = {"NORTH", "EAST", "SOUTH", "WEST"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, name, expected):
    assert sha(path) == expected, "trusted source hash mismatch"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cell(p):
    return "ABCDEFGH"[p % 8] + str(p // 8 + 1)


def state(raw):
    return SimpleNamespace(board=[[SimpleNamespace(**dict(zip(FIELDS, c))) for c in row]
                                   for row in raw["board"]], bot_id=raw["bot_id"],
                           is_priority_token=raw["is_priority_token"], legal_actions=list(raw["legal_actions"]))


def from_snapshot(referee, meta, snapshot):
    game = referee.Referee(meta["base"], rules=meta["rules"], start_token=meta["start_token"],
                           max_turns=meta["max_turns"])
    for name in ("owner", "upg", "pos", "frozen", "cd", "prog", "score"):
        setattr(game, name, copy.deepcopy(snapshot[name]))
    game.turn, game.token = snapshot["turn"], snapshot["token"]
    assert game.snapshot() == snapshot
    return game


def replay(referee, data):
    meta = data["metadata"]
    game = from_snapshot(referee, meta, meta["initial"])
    assert len(data["turns"]) == 80 and not meta["partial"]
    for turn in data["turns"]:
        assert game.snapshot() == turn["before"], (turn["turn"], "before")
        for seat in range(1, 5):
            assert game.observation(seat) == turn["observations"][str(seat)]
            assert turn["used"][seat-1] in game.legal(seat-1)
        assert game.step(turn["used"]) == turn["resolved"], (turn["turn"], "resolution")
        assert game.snapshot() == turn["after"], (turn["turn"], "after")
    assert game.snapshot() == data["ending"]["final"]
    return dict(turns=80, public_observations=320, transitions_exact=True,
                final_scores=game.score, places=referee.places(game.score))


def behavior(data):
    rows = []
    for seat in range(1, 5):
        idx = seat-1
        counts = Counter()
        idle, freeze, abandoned, reversals, returns, shields, raids, high_claims = [], [], [], [], [], [], [], []
        previous_move = None
        previous_turn = None
        events_work = {"claim", "upgrade", "raid"}
        for t in data["turns"]:
            n, before, after = t["turn"], t["before"], t["after"]
            chosen, effective = t["used"][idx], t["resolved"]["eff"][idx]
            p, q = before["pos"][idx], after["pos"][idx]
            counts["requested_" + chosen] += 1
            if before["frozen"][idx]:
                freeze.append(n)
            if chosen in MOVES and p != q:
                counts["successful_moves"] += 1
                if previous_turn and previous_turn["after"]["pos"][idx] == p and previous_turn["before"]["pos"][idx] == q:
                    if previous_turn["used"][idx] in MOVES:
                        reversals.append([n-1, n, cell(q), cell(p), cell(q)])
                if previous_move and previous_move["from"] == q:
                    completed = [e for u in data["turns"][previous_move["turn"]-1:n]
                                 for e in u["resolved"]["events"]
                                 if e.get("seat") == seat and e["type"] in events_work]
                    if not completed:
                        returns.append(dict(from_turn=previous_move["turn"], to_turn=n,
                                            path=[cell(q), cell(p), cell(q)]))
                previous_move = dict(turn=n, **{"from": p, "to": q})
                if before["prog"][idx]:
                    abandoned.append(dict(turn=n, cell=cell(p), progress=before["prog"][idx], action=chosen))
            work = [e for e in t["resolved"]["events"] if e.get("seat") == seat and e["type"] in ("claim", "upgrade", "raid", "progress")]
            if effective == "STAY" and not before["frozen"][idx] and not work:
                idle.append(dict(turn=n, cell=cell(p), requested=chosen,
                                 own_finished=before["owner"][p] == seat and bool(before["upg"][p]),
                                 enemy_home=before["owner"][p] != seat and p in (0, 7, 56, 63),
                                 frozen_after=bool(after["frozen"][idx])))
            for e in t["resolved"]["events"]:
                if e.get("seat") != seat:
                    continue
                counts["event_" + e["type"]] += 1
                if e["type"] == "shield":
                    shields.append(dict(turn=n, caught=e["caught"], backfire=e["backfire"], cell=cell(p)))
                if e["type"] == "raid":
                    raids.append(dict(turn=n, cell=cell(e["cell"]), **{k: e[k] for k in ("from", "level", "base", "bonus")}))
                if e["type"] in ("claim", "raid") and e["base"] == 3:
                    high_claims.append(dict(turn=n, cell=cell(e["cell"]), kind=e["type"]))
            previous_turn = t
        final = data["ending"]["final"]
        rows.append(dict(seat=seat, score=final["score"][idx], income=sum(t["resolved"]["income"][idx] for t in data["turns"]),
                         raid_bonus=sum(t["resolved"]["bonus"][idx] for t in data["turns"]), final_income=final["income"][idx],
                         final_cells=final["cells"][idx], final_upgraded=final["upgraded"][idx], counts=dict(counts),
                         forced_frozen_turns=freeze, shields=shields, raids=raids, high_value_claims=high_claims,
                         immediate_move_reversals=reversals, return_without_completed_work=returns,
                         abandoned_progress=abandoned, nonproductive_unfrozen_stays=idle))
    return rows


def beliefs(data):
    snapshots, mismatches = [], []
    for seat in (2, 3, 4):
        module = load(POLICY, "behavior_policy_%d" % seat, POLICY_HASH)
        for t in data["turns"]:
            output = module.act(state(t["observations"][str(seat)]))
            assert output == t["used"][seat-1], (seat, t["turn"], output)
            mem = module._history[seat]
            actual, estimated = t["before"]["cd"], mem["cooldown"][1:]
            wrong = [i+1 for i in range(4) if actual[i] != estimated[i]]
            if wrong:
                mismatches.append(dict(turn=t["turn"], observer=seat, seats=wrong,
                                       actual=actual, estimated=list(estimated)))
            if 53 <= t["turn"] <= 59:
                snapshots.append(dict(turn=t["turn"], observer=seat, own_progress=mem["progress"],
                                      true_own_progress=t["before"]["prog"][seat-1],
                                      cooldown=list(estimated), true_cooldown=actual,
                                      last_bait=mem["last_bait"], defense_hits=list(mem["defense_hits"]),
                                      defense_trials=list(mem["defense_trials"])))
    return dict(all_240_actions_match=True, cooldown_mismatches=mismatches, critical_snapshots=snapshots)


def counterfactual(referee, data, start, end, changes):
    """Other recorded requests are fixed: conditional hindsight, not deployment."""
    meta = data["metadata"]
    game = from_snapshot(referee, meta, data["turns"][start-1]["before"])
    forced, realized = [], []
    for t in data["turns"][start-1:end]:
        requests = list(t["used"])
        for seat, action in changes.get(t["turn"], {}).items():
            assert action in game.legal(seat-1), (t["turn"], seat, action)
            requests[seat-1] = action
        used = []
        for i, action in enumerate(requests):
            if action not in game.legal(i):
                forced.append(dict(turn=t["turn"], seat=i+1, request=action))
                action = "STAY"
            used.append(action)
        result = game.step(used)
        realized.append(dict(turn=t["turn"], used=used, events=result["events"]))
    baseline = data["turns"][end-1]["after"]["score"]
    return dict(start_turn=start, end_turn=end,
                changes={str(n): {str(s): a for s, a in c.items()} for n, c in changes.items()},
                baseline_scores=baseline, alternative_scores=list(game.score),
                score_differences=[game.score[i]-baseline[i] for i in range(4)],
                newly_forced_stays=forced, events=realized,
                caveat="Conditional hindsight: every other realized request is held fixed. Opponents do not adapt; this is not a deployable-policy or win-rate estimate.")


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    referee = load(REFEREE, "behavior_referee", REFEREE_HASH)
    assert data["metadata"]["bot"]["sha256"] == POLICY_HASH
    validation = replay(referee, data)
    metrics = behavior(data)
    memory = beliefs(data)
    experiments = {
        "seat2_capture_instead_of_premature_shield54": counterfactual(referee, data, 54, 80, {54: {2: "STAY"}}),
        "seat2_wait75_shield_completion78": counterfactual(referee, data, 75, 80, {75: {2: "STAY"}, 78: {2: "SHIELD"}}),
        "seat4_feint44_then_capture_E3_47": counterfactual(referee, data, 44, 47, {44: {4: "NORTH"}, 47: {4: "STAY"}}),
        "seat4_naive_center_rush_opening": counterfactual(referee, data, 1, 10,
            {1: {4: "NORTH"}, 2: {4: "NORTH"}, 3: {4: "NORTH"}, 4: {4: "EAST"},
             5: {4: "EAST"}, 6: {4: "EAST"}, 7: {4: "STAY"}, 8: {4: "STAY"},
             9: {4: "STAY"}, 10: {4: "STAY"}}),
    }
    plateaus = []
    for seat in (2, 3, 4):
        start = 1
        for t in data["turns"]:
            work = [e for e in t["resolved"]["events"] if e.get("seat") == seat and e["type"] in ("claim", "upgrade", "raid")]
            if work:
                if t["turn"]-start >= 6:
                    plateaus.append(dict(seat=seat, from_turn=start, to_turn=t["turn"]-1,
                                         length=t["turn"]-start, next_work_turn=t["turn"]))
                start = t["turn"]+1
        if 81-start >= 6:
            plateaus.append(dict(seat=seat, from_turn=start, to_turn=80, length=81-start))
    result = dict(input_file=str(INPUT), input_sha256=sha(INPUT), policy_sha256=POLICY_HASH,
                  referee_sha256=REFEREE_HASH, validation=validation, players=metrics,
                  no_completed_work_intervals=plateaus, policy_memory=memory, counterfactuals=experiments,
                  milestones=[dict(turn=t["turn"], scores=t["after"]["score"], income=t["after"]["income"],
                                   cells=t["after"]["cells"], upgrades=t["after"]["upgraded"])
                              for t in data["turns"] if t["turn"] % 10 == 0])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "behavior_review.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    text = ["# Independent match behavior review", "",
            "Verified all 80 physical transitions and 320 public observations against the hash-pinned local referee. All 240 AI actions reproduce from the exact recorded policy.", "",
            "| Seat | Score | Recurring income | Raid bonus | End income | Cells / upgraded | Frozen turns |", "|---|---:|---:|---:|---:|---:|---:|"]
    for row in metrics:
        text.append("| %d | %d | %d | %d | %d | %d / %d | %d |" % (row["seat"], row["score"], row["income"], row["raid_bonus"], row["final_income"], row["final_cells"], row["final_upgraded"], len(row["forced_frozen_turns"])))
    text += ["", "## Persistent observed weaknesses", "",
             "1. **Seat 4 remained in a shield/raid trap.** It was caught on E4 at turns 39 and 44, E5 at turn 50, and D4 at turn 57. Eight subsequent turns were forced STAYs. It completed no capture or upgrade during turns 37–62, while recurring income remained 24. After a catch, a four-turn shield cooldown minus two frozen turns leaves only two safe active STAYs, insufficient for a three-STAY upgraded-cell raid before the defender can shield again. This does not make raids impossible against every opponent: the defender can choose another action. It does make persistent commitment exploitable by a defender willing to repeat.", "",
             "2. **The policy falsely inferred a human shield at turn 54.** Seat 2 actually shielded and backfired on the human's C2; the human stayed and upgraded C3. At turns 55–57 all three AI copies inferred human cooldowns 4, 3, 2, while the true cooldown was zero. The upgrade is visible evidence that the human could not have shielded at turn 54. This avoidable state-reconstruction error fed overconfident attacks into the real human SHIELD at turn 57. Seat 2 also missed its own real cooldown following its backfire.", "",
             "3. **Seat 2 spent shields before a raid could complete, with competing scoring work available.** Its turn-54 shield missed seat 4 as it left E4, while seat 2 could capture the ordinary human C2 with STAY. Its turn-75 shield also missed as seat 3 moved from E2 to D2; the cooldown then covered the turn-78 upgraded D2 capture. These are failures on this realized path, not proofs that every shield was irrational under uncertainty.", "",
             "4. **Contest handling cost seat 2 tempo.** At turn 49 it lost C2 to the human by token priority; at turn 51 it lost C3 to the human's ownership priority. The intervening D2–D3–D2 return at turns 50–52 completed no work. This is a short failed-contest detour, not evidence of pervasive perpetual oscillation.", "",
             "5. **The human converted safe recurring income more consistently.** The human finished with all 14 owned cells upgraded and 50 income/turn. Seat 4 had 13 cells but only 9 upgraded and 32 income/turn. Income growth, rather than an AI execution fault or exceptional raid bounty, explains the bulk of the score gap.", "",
             "## Important strengths and distinctions", "",
             "Seat 3 was not trapped or frozen at all. Its turn-75 move from E2 to D2 successfully escaped seat 2's simultaneous SHIELD, then captured upgraded D2 on turn 78 during the cooldown. Its three raids earned 80 points. It still lost by 199 because recurring income was 279 behind the human, partly offset by those bonuses. This match does not establish that each of seat 3's choices was a mistake. Its successful feint also isolates the problematic progress-sensitive commitment in seat 4: feinting is allowed when progress is zero, but disabled after progress has been banked.", "",
             "Seat 2's shields at turns 39 and 44 actually caught seat 4 and protected a valuable upgraded holding. Those are different from its empty shields at turns 54 and 75. A blanket instruction to stop shielding would discard a real defensive strength. The failure is in conditional timing, opportunity cost, observation attribution, and the response to a defender who repeatedly shields.", "",
             "## What this match does not establish", "",
             "A blanket 'rush the center earlier' prescription is unsupported. Seat 4 led the human 39–25 at turn 10 under its actual opening. A legal six-move direct D5 rush followed by claim and upgrade scores only 25 by turn 10 with other requests fixed, versus its actual 39. It contests a useful future cell, but sacrifices early income; the rest of that different game requires a policy-level comparison. There were no ordinary occupied-cell blocked moves and no immediate consecutive movement reversals in the AI traces. Empty late STAYs are not automatically errors when no scoring action can finish before turn 80.", "",
             "## Bounded conditional counterfactuals", "",
             "All following comparisons hold other realized requests fixed, enforcing legality under the modified state. They use hindsight and do not forecast adaptive opponents or prove a stronger deployable policy.", ""]
    for name, experiment in experiments.items():
        text.append("- **%s**, turns %d–%d: score differences [human, seat 2, seat 3, seat 4] = `%s`." % (name.replace("_", " "), experiment["start_turn"], experiment["end_turn"], experiment["score_differences"]))
    text += ["", "Raw per-seat counts, event coordinates, freeze turns, cooldown mismatches, milestone states and legal counterfactual event traces are preserved in behavior_review.json. Exact full-game and remembered-belief verification is local to the recorded referee/policy versions, not official-server validation."]
    (OUT / "behavior_review.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print(json.dumps(dict(validation=validation, financials=[{k: r[k] for k in ("seat", "score", "income", "raid_bonus", "final_income", "forced_frozen_turns", "immediate_move_reversals", "return_without_completed_work")} for r in metrics], plateaus=plateaus,
                          experiments={k: v["score_differences"] for k, v in experiments.items()}), indent=2))


if __name__ == "__main__":
    main()
