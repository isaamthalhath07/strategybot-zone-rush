"""Final simultaneous turn: exact payoffs conditional on action hypotheses.

Opponent probabilities are forecasts. Conditional game arithmetic is exact for
STAY/SHIELD/successful-move actions; contested/blocked movements are represented
by the forecast's STAY mass, not clairvoyantly resolved.
"""
from itertools import product


def resolve(owner, upg, home, base, positions, frozen, progress, scores, actions):
    """Return scores AFTER the final scoring step. No input mutation."""
    own, levels = list(owner), list(upg)
    out = list(scores)
    shields = {j for j, a in enumerate(actions) if a == "SHIELD" and not frozen[j]}
    for j, p in enumerate(positions):
        if p is None or frozen[j] or actions[j] != "STAY":
            continue
        o = owner[p]
        if o and o - 1 in shields and o != j + 1:
            continue
        if o == j + 1:
            if not upg[p] and progress[j] >= 2:
                levels[p] = 1
        elif not home[p] and (not o or not upg[p] or progress[j] >= 2):
            if o:
                out[j] += 8 * base[p] * (2 if upg[p] else 1)
            own[p] = j + 1
            levels[p] = 0
    for p, o in enumerate(own):
        if o:
            out[o - 1] += base[p] * (2 if levels[p] else 1)
    return out


def utility(scores, seat):
    mine = scores[seat]
    return sum(1 if mine > v else .5 if mine == v else 0
               for j, v in enumerate(scores) if j != seat)


def distribution(agent, j, owner, upg, occ, frz, base):
    """Public-history forecast; no foreign actions or policy IDs are available."""
    tr, P = agent.tr, agent.P
    p = tr.pos[j]
    if p is None or tr.frozen[j]:
        return [("STAY", 1.0)]
    shield = 0.0
    if tr.cd[j] == 0:
        intruders = [(q, bot - 1) for q, bot in enumerate(occ)
                     if bot and bot != j + 1 and owner[q] == j + 1
                     and not frz[q] and not tr.home_of[q]]
        if intruders:
            imminent = any((3 if upg[q] else 1) - tr.prog[k] <= 1 for q, k in intruders)
            shield = tr.q_shield(j, P["q_prior"], P["q_weight"]) if imminent else 0.1
    o = owner[p]
    if o and o != j + 1 and not tr.home_of[p]:
        stay = agent._commit_prob(j)
    elif not o:
        stay = 0.95
    elif o == j + 1 and not upg[p]:
        stay = 0.90
    else:
        stay = 0.35
    return [("SHIELD", shield), ("STAY", (1 - shield) * stay),
            ("MOVE", (1 - shield) * (1 - stay))]


def choose(agent, owner, upg, occ, frz, base, seat, original):
    tr = agent.tr
    me = seat - 1
    others = [j for j in range(4) if j != me]
    distributions = [distribution(agent, j, owner, upg, occ, frz, base) for j in others]
    choices = ["STAY"]
    if agent._terminal_shield_legal:
        choices.append("SHIELD")
    if original not in choices:
        choices.append(original)
    totals = {}
    for choice in choices:
        win, score = 0.0, 0.0
        for scenario in product(*distributions):
            actions = ["MOVE"] * 4
            weight = 1.0
            for j, (action, probability) in zip(others, scenario):
                actions[j] = action
                weight *= probability
            if weight <= 0:
                continue
            actions[me] = choice if choice in ("STAY", "SHIELD") else "MOVE"
            scores = resolve(owner, upg, tr.home_of, base, tr.pos, tr.frozen,
                             tr.prog, tr.score, actions)
            win += weight * utility(scores, me)
            score += weight * scores[me]
        totals[choice] = (win, score)
    # Keep the baseline on ties: speculative reads should not cause churn.
    best = max(choices, key=lambda a: (totals[a][0], totals[a][1], a == original))
    if totals[best][0] > totals[original][0] + 1e-8:
        return best
    return original
