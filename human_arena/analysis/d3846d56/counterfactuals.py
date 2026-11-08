"""Offline diagnostics of one uploaded transcript; does not execute its contents.

Counterfactual opponents repeat recorded requests and do not react to a new
position. Exhaustive short searches are hindsight diagnostics, not deployable
policies or guarantees. No bot parameters or live game state are changed.
"""
from collections import deque
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUT = Path(r"C:\Users\LEGION\Downloads\zone-rush-d3846d56f462413789041954bdc8bc38.json")
VENDOR = ROOT / "human_arena" / "vendor_harness" / "referee.py"
spec = importlib.util.spec_from_file_location("audited_transcript_referee", VENDOR)
referee = importlib.util.module_from_spec(spec)
spec.loader.exec_module(referee)
DYNAMIC = ("pos", "owner", "upg", "frozen", "cd", "prog", "score")
CENTER = (27, 28, 35, 36)
MOVES = {"NORTH": -8, "EAST": 1, "SOUTH": 8, "WEST": -1}
SEARCH_LIMIT = 150000


def xy(p):
    return list(divmod(p, 8))


def clone(g):
    out = object.__new__(referee.Referee)
    out.__dict__ = g.__dict__.copy()
    for key in DYNAMIC:
        setattr(out, key, getattr(g, key)[:])
    return out


def restore(metadata, snapshot):
    out = referee.Referee(metadata["base"], rules=metadata["rules"],
                          start_token=metadata["start_token"], max_turns=metadata["max_turns"])
    for key in DYNAMIC:
        setattr(out, key, snapshot[key][:])
    out.turn, out.token = snapshot["turn"], snapshot["token"]
    return out


def pw(scores, seat):
    mine = scores[seat - 1]
    return sum(1 if mine > value else .5 if mine == value else 0
               for j, value in enumerate(scores) if j != seat - 1)


def potential(g, seat):
    """Banked score plus frozen-ownership income, with no future work/reaction."""
    return g.score[seat - 1] + max(0, 81 - g.turn) * g.income()[seat - 1]


def key(g):
    return (g.turn, g.token) + tuple(tuple(getattr(g, name)) for name in DYNAMIC)


def step_changed(g, record, seat, action):
    out = clone(g)
    actions = record["used"][:]
    actions[seat - 1] = action
    result = out.step(actions)
    return out, result


def search(start, records, seat, horizon):
    """Exhaustive distinct-state search; opponent requests are fixed recordings."""
    terminal_turn = start.turn + horizon
    visited = set()
    best_score, best_pw, best_potential = None, None, None
    first_actions = {}
    leaves = 0
    truncated = False

    def summarize(g, path):
        return dict(actions=path, scores=g.score[:], income=g.income(),
                    pw=pw(g.score, seat), own_score=g.score[seat - 1],
                    static_ownership_projection=potential(g, seat),
                    end_pos=xy(g.pos[seat - 1]), end_frozen=g.frozen[seat - 1],
                    end_progress=g.prog[seat - 1])

    def visit(g, path):
        nonlocal best_score, best_pw, best_potential, leaves, truncated
        fingerprint = key(g)
        # First action is part of the cache key to preserve separate root-action
        # comparisons even if different first actions reach an identical state.
        cache_key = (path[0] if path else None, fingerprint)
        if cache_key in visited:
            return
        if len(visited) >= SEARCH_LIMIT:
            truncated = True
            return
        visited.add(cache_key)
        if g.turn == terminal_turn:
            leaves += 1
            item = summarize(g, path)
            if best_score is None or (item["own_score"], item["pw"]) > (best_score["own_score"], best_score["pw"]):
                best_score = item
            if best_pw is None or (item["pw"], item["own_score"]) > (best_pw["pw"], best_pw["own_score"]):
                best_pw = item
            if best_potential is None or item["static_ownership_projection"] > best_potential["static_ownership_projection"]:
                best_potential = item
            first = path[0]
            if first not in first_actions or item["static_ownership_projection"] > first_actions[first]["static_ownership_projection"]:
                first_actions[first] = item
            return
        legal = sorted(g.legal(seat - 1), key=lambda a: (a != "STAY", a == "SHIELD", a))
        for action in legal:
            changed, _ = step_changed(g, records[g.turn - 1], seat, action)
            visit(changed, path + [action])

    visit(start, [])
    actual = clone(start)
    actual_path = []
    for _ in range(horizon):
        record = records[actual.turn - 1]
        actual_path.append(record["used"][seat - 1])
        actual.step(record["used"])
    baseline = summarize(actual, actual_path)
    return dict(turn=start.turn, seat=seat, horizon=horizon, baseline=baseline,
                best_score=best_score, best_pw=best_pw, best_static_projection=best_potential,
                per_first_action=first_actions, states=len(visited), terminal_states=leaves,
                exhaustive=not truncated,
                own_score_gain=best_score["own_score"] - baseline["own_score"],
                pairwise_gain=best_pw["pw"] - baseline["pw"])


def one_turns(metadata, records):
    opportunities, shields, blocked = [], [], []
    for record in records:
        before = restore(metadata, record["before"])
        actual = restore(metadata, record["after"])
        for seat in (2, 3, 4):
            candidates = []
            for action in before.legal(seat - 1):
                changed, result = step_changed(before, record, seat, action)
                candidates.append(dict(action=action,
                    own_score_delta_vs_actual=changed.score[seat - 1] - actual.score[seat - 1],
                    income_delta_vs_actual=changed.income()[seat - 1] - actual.income()[seat - 1],
                    static_projection_delta=potential(changed, seat) - potential(actual, seat),
                    score=changed.score[seat - 1], income=changed.income()[seat - 1],
                    frozen=changed.frozen[seat - 1], progress=changed.prog[seat - 1],
                    events=result["events"]))
            best = max(candidates, key=lambda c: (c["own_score_delta_vs_actual"], c["static_projection_delta"]))
            item = dict(turn=record["turn"], seat=seat, position=xy(before.pos[seat - 1]),
                        actual_action=record["used"][seat - 1], candidates=candidates, best_immediate=best)
            if best["own_score_delta_vs_actual"] > 0:
                opportunities.append(item)
            if record["used"][seat - 1] == "SHIELD":
                event = next(e for e in record["resolved"]["events"] if e["type"] == "shield" and e["seat"] == seat)
                item["actual_shield"] = event
                item["own_progress_before"] = before.prog[seat - 1]
                item["own_work_required"] = before.need(seat - 1)
                shields.append(item)
            failures = [e for e in record["resolved"]["events"] if e["type"] in ("blocked", "lost") and e["seat"] == seat]
            if failures:
                item["failure_events"] = failures
                blocked.append(item)
    opportunities.sort(key=lambda row: -row["best_immediate"]["static_projection_delta"])
    return opportunities, shields, blocked


def neighbors(p):
    r, c = divmod(p, 8)
    return [q for q, ok in ((p - 8, r > 0), (p + 8, r < 7), (p - 1, c > 0), (p + 1, c < 7)) if ok]


def manhattan(a, b):
    ar, ac = divmod(a, 8)
    br, bc = divmod(b, 8)
    return abs(ar - br) + abs(ac - bc)


def economic_jobs(g, seat):
    at = g.pos[seat - 1]
    closed = {p for j, p in enumerate(g.pos) if j != seat - 1}
    distances, queue = {at: 0}, deque([at])
    while queue:
        p = queue.popleft()
        for q in neighbors(p):
            if q not in closed and q not in distances:
                distances[q] = distances[p] + 1
                queue.append(q)
    remaining = 81 - g.turn
    out = []
    for p, travel in distances.items():
        owner = g.owner[p]
        if g.home[p] and owner != seat or owner == seat and g.upg[p]:
            continue
        need = 3 if owner == seat or owner and g.upg[p] else 1
        if p == at:
            need = max(1, need - g.prog[seat - 1])
        cost = travel + need
        if cost > remaining:
            continue
        bonus = 8 * g.base[p] * (2 if g.upg[p] else 1) if owner not in (0, seat) else 0
        gain = g.base[p] * (remaining - cost + 1) + bonus
        out.append(dict(cell=p, coordinate=xy(p), center=p in CENTER, owner=owner,
                        upgraded=bool(g.upg[p]), travel=travel, work=need, cost=cost,
                        gain_if_undisturbed=gain, rate_if_undisturbed=gain / cost,
                        raid_bonus=bonus, base=g.base[p]))
    return sorted(out, key=lambda j: -j["rate_if_undisturbed"])


def center_forks(metadata, records):
    forks = []
    for record in records[:65]:
        g = restore(metadata, record["before"])
        for seat in (2, 3, 4):
            action = record["used"][seat - 1]
            if action not in MOVES or record["resolved"]["eff"][seat - 1] != action:
                continue
            at, after = g.pos[seat - 1], record["after"]["pos"][seat - 1]
            olddist, newdist = min(manhattan(at, c) for c in CENTER), min(manhattan(after, c) for c in CENTER)
            if newdist <= olddist:
                continue
            candidates = economic_jobs(g, seat)
            center = next((j for j in candidates if j["center"]), None)
            outside = next((j for j in candidates if not j["center"]), None)
            if center:
                forks.append(dict(turn=g.turn, seat=seat, before=xy(at), after=xy(after), action=action,
                    center_distance_before=olddist, center_distance_after=newdist,
                    best_center=center, best_outside=outside,
                    center_rate_over_outside=center["rate_if_undisturbed"] / outside["rate_if_undisturbed"] if outside else None))
    return sorted(forks, key=lambda row: -(row["center_rate_over_outside"] or 0))


def public_t75_scenarios(metadata, records):
    """Intent-blind current-turn safety comparison, using no future action.

    At T75 the only rival occupying seat-2 land just arrived at T74, so its
    progress is visibly zero. Other rivals occupy their own land. Their own
    private progress cannot affect seat-2 income this turn. To avoid relying on
    hidden rival cooldowns, every rival is conservatively allowed to SHIELD.
    """
    record = records[74]
    g = restore(metadata, record["before"])
    assert g.pos == [8, 2, 12, 40]
    assert records[73]["before"]["pos"][2] != g.pos[2]
    for j in (0, 2, 3):
        g.cd[j] = 0
        g.prog[j] = 0
    other_seats = (1, 3, 4)
    choices = [g.legal(s - 1) for s in other_seats]
    output = {}
    for own_action in g.legal(1):
        own_incomes, own_frozen, own_positions, frozen_rivals = [], [], [], []
        for others in itertools.product(*choices):
            changed = clone(g)
            actions = ["STAY"] * 4
            actions[1] = own_action
            for s, action in zip(other_seats, others):
                actions[s - 1] = action
            changed.step(actions)
            own_incomes.append(changed.income()[1])
            own_frozen.append(changed.frozen[1])
            own_positions.append(changed.pos[1])
            frozen_rivals.append(sum(changed.frozen[j] for j in (0, 2, 3)))
        output[own_action] = dict(scenarios=len(own_incomes), minimum_own_income=min(own_incomes),
            maximum_own_freeze=max(own_frozen), possible_end_positions=[xy(p) for p in sorted(set(own_positions))],
            maximum_total_rival_freeze_including_self_backfires=max(frozen_rivals))
    return dict(turn=75, seat=2, alternatives=output,
        interpretation="WEST or SOUTH preserves all 36 current income under every enumerated rival request, cannot be caught on arrival, and leaves shield ready. SHIELD can instead deny rival tempo if it catches; this is not dominance or a guarantee of a better reactive-game outcome.")


def fixed_own_path(metadata, records, turn, seat, path):
    actual = restore(metadata, records[turn - 1]["before"])
    alternative = clone(actual)
    steps = []
    for action in path:
        record = records[alternative.turn - 1]
        alternative, resolved = step_changed(alternative, record, seat, action)
        actual.step(record["used"])
        steps.append(dict(turn=record["turn"], own_action=action, effective=resolved["eff"][seat - 1],
            own_pos=xy(alternative.pos[seat - 1]), own_frozen=alternative.frozen[seat - 1],
            own_progress=alternative.prog[seat - 1], events=resolved["events"],
            own_score_delta=alternative.score[seat - 1] - actual.score[seat - 1],
            own_income_delta=alternative.income()[seat - 1] - actual.income()[seat - 1]))
    return dict(turn=turn, seat=seat, actions=path, steps=steps,
        score_delta=alternative.score[seat - 1] - actual.score[seat - 1],
        static_projection_delta=potential(alternative, seat) - potential(actual, seat),
        alternative_scores=alternative.score, recorded_scores=actual.score)


def public_t55_escape(metadata, records):
    # Infer the shielder solely from public board changes, not recorded choices.
    prior = [c for row in records[53]["observations"]["4"]["board"] for c in row]
    now = [c for row in records[54]["observations"]["4"]["board"] for c in row]
    assert prior[10][0] == now[10][0] == 2 and prior[10][1] == 1
    assert not prior[10][4] and now[10][4]
    assert prior[18][0] == now[18][0] == 1 and not prior[18][2] and now[18][2]
    assert now[28][1] == 2 and now[28][2] and now[28][0] == 0
    assert now[27][0] == 4
    game = restore(metadata, records[54]["before"])
    # Allow every unfrozen rival to shield regardless of uncertain cooldowns,
    # except seat 2's cooldown, proved from the public backfire attribution.
    game.cd[0] = game.cd[2] = 0
    choices = [game.legal(j) for j in (0, 1, 2)]
    arrivals = []
    for opponents in itertools.product(*choices):
        changed = clone(game)
        actions = list(opponents) + ["EAST"]
        changed.step(actions)
        arrivals.append((changed.pos[3], changed.frozen[3]))
    assert set(arrivals) == {(28, 0)}
    # Once on E4, occupancy prevents entry. Only owner seat 2 can freeze this
    # raider, and its T54 shield forbids another shield on T55..T58 inclusive.
    return dict(turn=55, seat=4, current_cell="D4", escape="EAST to E4, then STAY three turns",
        public_proof=[
            "Seat 2 newly freezes on human-owned C2 after T54.",
            "The human visibly upgrades C3 in that same turn, which is incompatible with SHIELD.",
            "Therefore seat 2's freeze was its own SHIELD backfire, so it cannot shield during T55-T58.",
            "E4 is empty, owned by seat 2, upgraded, and worth 3; nobody else can reach it on T55.",
            "EAST arrives without staying, so cannot be caught; occupancy then prevents a rival entering.",
            "Three stays on T56-T58 therefore take E4 before seat 2 can shield again, irrespective of rival requests under these rules."],
        enumerated_first_turn_scenarios=len(arrivals), all_arrive_unfrozen_on_E4=True,
        guaranteed_target_specific_raid_bonus=48, guaranteed_target_specific_new_income=3,
        capture_turn=58,
        caveat="The capture and bounty are guaranteed by the current public facts and rules, not the final score or continued retention of E4. Other land can change; an adapting defender can react from T59 onward.")


def markdown(result):
    lines = ["# Transcript counterfactual diagnostics", "",
        "All 80 recorded turns and observations replay exactly through the fingerprint-matched vendored referee. The policy source hash is verified against its pinned Git blob; this script does not execute or change the policy.", "",
        "These are post-game diagnostics. One-turn results hold other recorded requests fixed. Short exhaustive searches also hold subsequent requests fixed, so rivals do not react to the altered board. Static ownership projections assume remaining land never changes. None of these numbers is a guaranteed strategic improvement against adapting opponents.", "",
        "## Shield decisions", "",
        "| Turn | AI seat | Actual outcome | STAY immediate score difference | STAY frozen-ownership projection difference |", "|---|---|---|---:|---:|"]
    for item in result["shields"]:
        stay = next(c for c in item["candidates"] if c["action"] == "STAY")
        outcome = "backfire" if item["actual_shield"]["backfire"] else "caught " + str(item["actual_shield"]["caught"])
        lines.append("| %s | %s | %s | %+d | %+d |" % (item["turn"], item["seat"], outcome,
                     stay["own_score_delta_vs_actual"], stay["static_projection_delta"]))
    lines += ["", "T44 and T50 protect upgraded 3-point cells when the raider already has two of three stays. Giving up partial work on a 2-point own cell can be rational when it prevents the loss of 6 income and a 48-point opposing raid bonus. T39 is less urgent: the raider still needs two stays.", "",
        "T54 is the clearest missed realized raid: seat 2 shields while standing on the human's level-one 2-point cell; STAY would have taken it if the other recorded requests remain unchanged. This requires hindsight about the human not shielding. T75 differs: the potential raider had just arrived on an upgraded cell and could not capture it that turn. A public-state, future-intent-blind check finds WEST and SOUTH preserve current income and mobility in every enumerated rival request. Shielding still has a possible rival-tempo benefit, so waiting is an option-value improvement, not a proof of dominance.", "",
        "## T55–T57: a safer exit from the human's center", "",
        "At T55, seat 4 could move EAST from D4 to E4 (zero-based [3,3]→[3,4]) and stay three turns. This is more than an oracle response to the later human shield. The public board already proves seat 2 backfired at T54: seat 2 newly freezes on the human's C2, while the human visibly upgrades C3 and therefore could not have shielded. Seat 2's four-turn cooldown then covers T55–T58. E4 is its empty upgraded 3-point cell; arrival is uncontested and cannot be caught, and subsequent occupancy blocks entry. Three stays T56–T58 capture it before the owner can shield again. The 48 bonus and 3-point new gross income from that target are rule-guaranteed under the current public facts, although future retention and final score are not.", "",
        "This opportunity depends on correctly attributing the observed freeze. A model that invents a human cooldown can wrongly treat staying on human-owned D4 as safe, while missing the cooldown that actually exists on seat 2. The exact policy-belief defect is established by the separate decision replay, not by this counterfactual script.", "",
        "| Start | Seat-4 action path | Through turn | Score difference with recorded rival requests |", "|---|---|---|---:|"]
    for path in result["escape_paths"]:
        lines.append("| %d | %s | %d | %+d |" % (path["turn"], ", ".join(path["actions"]), path["steps"][-1]["turn"], path["score_delta"]))
    lines += ["", "The T56 exit has less inherent protection: three new stays would finish at T59, when seat 2 could normally shield again. Its success in the recorded continuation depends on later events. At T57, leaving D4 avoids the human's actual shield, but learning that exact request in advance would be hindsight.", "",
        "## Final 2–6 turns, fixed-request exhaustive search", "",
        "| Start | Turns left | AI seat | Recorded final score | Best own score | Gain | Best pairwise wins gain | States |", "|---|---|---|---:|---:|---:|---:|---:|"]
    for item in result["terminal_searches"]:
        lines.append("| %d | %d | %d | %d | %d | %+d | %+.1f | %d |" %
            (item["turn"], item["horizon"], item["seat"], item["baseline"]["own_score"],
             item["best_score"]["own_score"], item["own_score_gain"], item["pairwise_gain"], item["states"]))
    lines += ["", "The full action sequences, endpoint score vectors, per-first-action best static values, and exhaustive flags are in counterfactuals.json. A last-turn action that merely leaves an upgrade unfinished is not automatically a bug: movement also yields no capture on arrival. Check the one-turn alternatives and earlier scheduling separately.", "",
        "## Movement and central territory", "",
        "There are exactly two AI movement contest losses (seat 2, T49 and T51), both to the human; no AI occupied-cell blocked-move events occur. The human was ahead in token order in both contests. The rival's move was not known in advance, so these are costly contested choices rather than proof of an illegal-move bug.", "",
        "Central comparisons below use current public geometry and a simple undisturbed final-score-per-action calculation. They are intentionally optimistic about raids: enemy shields, changing occupancy and later retakes are omitted. A high central cell value alone does not establish the best route. Nearby upgrades and lower-travel claims can have better rates; an enemy upgraded center can be impossible to raid efficiently against a ready defender.", "",
        "| Turn | Seat | Move | Center job | Center rate | Best outside rate | Center/outside |", "|---|---|---|---|---:|---:|---:|"]
    for item in result["center_outward_forks"][:15]:
        c, o = item["best_center"], item["best_outside"]
        lines.append("| %d | %d | %s %s→%s | %s, owner %d, level %d, %d+%d turns | %.2f | %.2f | %.2f |" %
            (item["turn"], item["seat"], item["action"], item["before"], item["after"], c["coordinate"],
             c["owner"], 2 if c["upgraded"] else 1, c["travel"], c["work"], c["rate_if_undisturbed"],
             o["rate_if_undisturbed"] if o else 0, item["center_rate_over_outside"] or 0))
    lines += ["", "## Intent-blind T75 comparison", "", "```json", json.dumps(result["intent_blind_t75"], indent=2), "```", "",
        "No live app, source policy, weights, or recorded game was modified. Source observations and hidden referee counters are used for the explicit hindsight diagnostics only; the T75 safety comparison is separated and uses the visible just-arrived fact rather than future actions."]
    return "\n".join(lines) + "\n"


def main():
    raw = INPUT.read_bytes()
    data = json.loads(raw)
    metadata, records = data["metadata"], data["turns"]
    assert data["game_id"] == "d3846d56f462413789041954bdc8bc38"
    assert len(records) == 80 and not data["incomplete_last_record"]
    referee_hash = hashlib.sha256(VENDOR.read_bytes()).hexdigest()
    assert referee_hash == metadata["referee_sha256"]
    bot = metadata["bot"]
    assert bot["commit"] == "0796039f42f0113d7c4f51b2f8e1409835f2c519"
    assert bot["path"] == "outputs/bot.py"
    assert bot["sha256"] == "1dca0c916af4ff4ac4c2e90fabe3f3c29c550c5db61663f8a3c2b0efc72f81ca"
    source = subprocess.check_output(["git", "show", bot["commit"] + ":" + bot["path"]], cwd=ROOT)
    assert hashlib.sha256(source).hexdigest() == bot["sha256"]
    game = restore(metadata, metadata["initial"])
    for record in records:
        assert game.snapshot() == record["before"], record["turn"]
        for seat in (1, 2, 3, 4):
            assert game.observation(seat) == record["observations"][str(seat)]
        actual = game.step(record["used"])
        assert actual == record["resolved"], record["turn"]
        assert game.snapshot() == record["after"], record["turn"]
    assert game.snapshot() == data["ending"]["final"]
    opportunities, shields, blocked = one_turns(metadata, records)
    terminal = []
    for horizon in range(2, 7):
        for seat in (2, 3, 4):
            start = restore(metadata, records[80 - horizon]["before"])
            item = search(start, records, seat, horizon)
            terminal.append(item)
            print("Terminal T%d seat%d: %+d score, %+.1f PW, %d states, exhaustive=%s" %
                  (start.turn, seat, item["own_score_gain"], item["pairwise_gain"], item["states"], item["exhaustive"]), flush=True)
    local = []
    for item in shields + blocked:
        local.append(search(restore(metadata, records[item["turn"] - 1]["before"]), records, item["seat"], 3))
    tracker_windows = [search(restore(metadata, records[turn - 1]["before"]), records, 4, horizon)
                       for turn, horizon in ((55, 4), (55, 6), (56, 4), (56, 6), (57, 4))]
    escape_paths = [fixed_own_path(metadata, records, turn, 4, path) for turn, path in (
        (55, ["EAST", "STAY", "STAY", "STAY"]),
        (55, ["EAST", "STAY", "STAY", "STAY", "STAY", "STAY"]),
        (56, ["EAST", "STAY", "STAY", "STAY"]),
        (57, ["EAST", "STAY", "STAY", "STAY"]))]
    last_turn = []
    for seat in (2, 3, 4):
        before = restore(metadata, records[79]["before"])
        last_turn.append(search(before, records, seat, 1))
    result = dict(input=str(INPUT), input_sha256=hashlib.sha256(raw).hexdigest(),
        game_id=data["game_id"], referee_sha256=referee_hash, bot=bot,
        replay_validation="80/80 exact before states, four public observations, full resolutions, after states, and ending",
        baseline_final_scores=game.score, one_turn_realized_opportunities=opportunities,
        shields=shields, movement_losses=blocked, terminal_searches=terminal,
        local_three_turn_searches=local, final_turn_searches=last_turn,
        tracker_error_window_searches=tracker_windows, escape_paths=escape_paths,
        intent_blind_t55_escape=public_t55_escape(metadata, records),
        center_outward_forks=center_forks(metadata, records), intent_blind_t75=public_t75_scenarios(metadata, records),
        limitations=["Other players repeat recorded action requests; they do not react to alternative play.",
                      "A static ownership projection is an accounting thought experiment, not a forecast.",
                      "Economic center-job rates ignore interference and are not a proof of policy error.",
                      "No alternative is claimed to guarantee a better result against reactive opponents."])
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "counterfactuals.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    (HERE / "counterfactuals.md").write_text(markdown(result), encoding="utf8")
    print("Saved counterfactuals.json and counterfactuals.md")


if __name__ == "__main__":
    main()
