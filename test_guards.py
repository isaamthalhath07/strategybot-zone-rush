"""
The safety net, tested on purpose.

Round 1 gives no simulator and no second chance: whatever is in the repository at
the deadline is played once, by a server whose exact reading of two or three rule
details I cannot verify. So the guards matter as much as the strategy, and each
one here is checked rather than assumed.

    python test_guards.py
"""
import json
import random
import sys

import engine
import mybot
import zoo

P = dict(mybot.PARAMS)
P.update(json.load(open("v6_params.json")))
# Both wall-clock guards off. Several checks here compare two runs for exact
# equality, and the bot has two ways to let machine load change its play: the
# adaptive beam (throttle) and the hard deadline inside the beam search
# (budget_ms). Pinning only the first is not enough -- under load the deadline
# truncates the search differently between the two runs and a state-leak check
# fails for a reason that has nothing to do with state. Both guards stay in the
# shipped bot; they just cannot be left on while testing for determinism.
P["throttle"] = 0
P["budget_ms"] = 10000.0
fails = []


def play(bots, base, token=1, rules=None, max_turns=80):
    g = engine.Game(base=base, start_token=token, rules=rules, max_turns=max_turns)
    while not g.over():
        vs = g.views()
        acts = []
        for i in range(4):
            try:
                a = bots[i](vs[i])
            except Exception:
                a = "STAY"
            if a not in vs[i].legal_actions:
                a = "STAY"
            acts.append(a)
        g.step(acts)
    return g


# ---------------------------------------------------------------------------
print("=== A. the progress rule is read off the board, not assumed ===========")
print("A neutral cell costs 4 stays to own-and-upgrade if capturing resets")
print("progress, or 3 if it carries over. The bot has to find out which.\n")
for label, rules, want in (("resets (my default reading)", None, False),
                           ("carries over", {"claim_resets_progress": False}, True)):
    seen = []
    exact = True
    settled_wrong = 0
    for gi in range(10):
        base = engine.make_map(seed=gi + 1)
        ag = mybot.Agent(seed=gi, params=P)
        bots = [ag] + [zoo.SpineFarmerBot(gi * 4 + i) for i in range(1, 4)]
        settled = None
        g = engine.Game(base=base, start_token=1, rules=rules)
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                a = bots[i](vs[i])
                if a not in vs[i].legal_actions:
                    a = "STAY"
                acts.append(a)
            # observe() runs on the PRE-step board, so its progress describes the
            # state the engine is in right now -- compare before stepping, not
            # after, or the check is one turn out of phase.
            wrong = list(ag.tr.prog) != list(g.prog)
            if wrong:
                exact = False
                # The sequence that reveals the rule is itself mistracked, by
                # construction: the answer only arrives when that first upgrade
                # lands. What must hold is that everything after it is exact.
                if ag.tr.carry is not None and settled is not None and g.turn > settled + 1:
                    settled_wrong += 1
            if ag.tr.carry is not None and settled is None:
                settled = g.turn
            g.step(acts)
        seen.append(ag.tr.carry)
    right = sum(1 for c in seen if c is want)
    unknown = sum(1 for c in seen if c is None)
    # One stray turn per few hundred is tolerated: a bot whose first capture
    # straddles the turn the rule is settled can be one short for a single turn.
    # It costs the planner one unit of progress on one cell on one turn.
    ok = right + unknown == len(seen) and right >= 7 and settled_wrong <= 2
    print("  %-28s detected %s in %d/%d games (%d undecided), %d wrong turns "
          "after it settled   %s"
          % (label, want, right, len(seen), unknown, settled_wrong,
             "OK" if ok else "BAD"))
    if right + unknown != len(seen) or right < 7:
        fails.append("carry detection under %s" % label)
    if settled_wrong > 2:
        fails.append("progress wrong %d turns after the rule was settled (%s)"
                     % (settled_wrong, label))

# ---------------------------------------------------------------------------
print("\n=== B. a broken decide() must not become 80 turns of STAY =============")
print("This is the failure that actually happened: one missing parameter key")
print("made the shipped bot play the skeleton for a whole game while the")
print("harness reported no crashes.\n")


class Broken(mybot.Agent):
    def decide(self, view):
        raise RuntimeError("pretend the state object is not what I expected")


rows = []
for name, mk in (("healthy bot", lambda s: mybot.Agent(seed=s, params=P)),
                 ("decide() always raises", lambda s: Broken(seed=s, params=P)),
                 ("the skeleton (STAY)", lambda s: zoo.StayBot(s))):
    tot = 0
    for gi in range(10):
        base = engine.make_map(seed=gi + 1)
        bots = [mk(gi)] + [zoo.SpineFarmerBot(gi * 4 + i) for i in range(1, 4)]
        tot += play(bots, base).score[0]
    rows.append((name, tot / 10.0))
for name, sc in rows:
    print("  %-26s %7.0f" % (name, sc))
if rows[1][1] < rows[2][1] * 2.0:
    fails.append("fallback policy is no better than STAY")
    print("  BAD: the fallback is not pulling its weight")
else:
    print("  OK: the fallback scores %.1fx the skeleton" % (rows[1][1] / max(1.0, rows[2][1])))

# ---------------------------------------------------------------------------
print("\n=== C. module state reused across games ===============================")
print("The organisers confirmed memory between turns is allowed but said the")
print("burden is mine. If the server plays several games in one process, a")
print("tracker carrying game 1's history into game 2 would poison it.\n")
reused = mybot.Agent(seed=5, params=P)
rs, fs = [], []
for gi in range(6):
    base = engine.make_map(seed=gi + 1)
    rs.append(play([reused] + [zoo.SpineFarmerBot(gi * 4 + i) for i in range(1, 4)],
                   base).score[0])
    fs.append(play([mybot.Agent(seed=5, params=P)]
                   + [zoo.SpineFarmerBot(gi * 4 + i) for i in range(1, 4)],
                   base).score[0])
same = rs == fs
print("  one Agent across 6 games : %s" % rs)
print("  a fresh Agent each game  : %s" % fs)
print("  %s" % ("OK: identical, so the new-game reset works"
                if same else "BAD: stale state changed play"))
if not same:
    fails.append("state leaks between games")

# ---------------------------------------------------------------------------
print("\n=== D. dropped in mid-game ============================================")
print("If the server ever starts calling act() partway through, the bot must")
print("not play the opening for 80 straight turns.\n")
for start in (20, 45, 65):
    base = engine.make_map(seed=7)
    g = engine.Game(base=base, start_token=1)
    fillers = [zoo.SpineFarmerBot(i) for i in range(4)]
    while g.turn < start:
        vs = g.views()
        g.step([fillers[i](vs[i]) for i in range(4)])
    ag = mybot.Agent(seed=1, params=P)
    vs = g.views()
    ag(vs[0])
    print("  real turn %2d  ->  bot's estimate %2d   (error %+d)"
          % (g.turn, ag.tr.turn, ag.tr.turn - g.turn))
    if abs(ag.tr.turn - g.turn) > 20:
        fails.append("mid-game turn estimate off by more than 20 at turn %d" % start)
    if ag.tr.turn < g.turn:
        fails.append("mid-game turn estimate too low at turn %d (would misplay "
                     "the endgame as the opening)" % start)

# ---------------------------------------------------------------------------
print("\n=== E. malformed and hostile state objects ============================")


class FlatView(object):
    """board as a flat 64-list instead of 8x8, which the starter files both imply."""
    __slots__ = ("board", "bot_id", "is_priority_token", "legal_actions")


base = engine.make_map(seed=11)
g = engine.Game(base=base, start_token=1)
v = g.views()[0]
flat = FlatView()
flat.board = [v.board[r][c] for r in range(8) for c in range(8)]
flat.bot_id = v.bot_id
flat.is_priority_token = v.is_priority_token
flat.legal_actions = v.legal_actions
ag = mybot.Agent(seed=1, params=P)
a1 = ag(v)
ag2 = mybot.Agent(seed=1, params=P)
a2 = ag2(flat)
print("  8x8 board -> %-6s   flat 64 board -> %-6s   %s"
      % (a1, a2, "OK" if a1 == a2 else "BAD: layouts disagree"))
if a1 != a2:
    fails.append("flat vs 8x8 board give different moves")

# only STAY offered
v2 = g.views()[0]


class OneAction(object):
    __slots__ = ("board", "bot_id", "is_priority_token", "legal_actions")


oa = OneAction()
oa.board, oa.bot_id, oa.is_priority_token = v2.board, v2.bot_id, True
oa.legal_actions = ["STAY"]
r = mybot.Agent(seed=1, params=P)(oa)
print("  legal_actions = ['STAY'] -> %-6s   %s" % (r, "OK" if r == "STAY" else "BAD"))
if r != "STAY":
    fails.append("ignored a single-action legal list")

print("\n=== F. no file here may shadow a standard-library module ============")
print("A file named select.py in this directory shadows the stdlib select")
print("module, which multiprocessing imports. That silently broke every")
print("parallel script here and surfaced as an unrelated argument error, so")
print("it is worth a permanent check rather than a second afternoon.\n")
import os as _os

_std = set(sys.stdlib_module_names)
_here = _os.path.dirname(_os.path.abspath(__file__))
_mine = set(f[:-3] for f in _os.listdir(_here) if f.endswith(".py"))
_clash = sorted(_mine & _std)
print("  shadowing files: %s   %s"
      % (", ".join(_clash) if _clash else "none", "BAD" if _clash else "OK"))
if _clash:
    fails.append("these files shadow stdlib modules: %s" % _clash)

# The same trap one level up: a directory with a module's name. The strategy
# audit was first added as audit/ next to audit.py, which runtests.py runs.
# `import audit` still found audit.py, but only because the directory had no
# __init__.py -- one added file away from silently running the wrong thing.
_dirs = set(d for d in _os.listdir(_here)
            if _os.path.isdir(_os.path.join(_here, d)) and not d.startswith((".", "__")))
_dclash = sorted(_mine & _dirs)
print("  directory/module name clashes: %s   %s"
      % (", ".join(_dclash) if _dclash else "none", "BAD" if _dclash else "OK"))
if _dclash:
    fails.append("these names are both a directory and a module: %s" % _dclash)

print("\n=== H. my own shield cooldown must be exact ===========================")
print("decide() refuses to shield unless BOTH legal_actions offers it and the")
print("tracker believes the cooldown is clear -- insurance against a server that")
print("offers SHIELD during cooldown and scores the attempt as STAY. That guard")
print("is only safe if the tracker never overstates its own cooldown, or the bot")
print("would decline shields it was entitled to play.\n")
import aifield as _af

_own = _high = _ref = _turns = 0
_riv = 0
for _gi in range(10):
    _base = engine.make_map(seed=_gi + 1)
    _ag = mybot.Agent(seed=_gi, params=P)
    _opp = [_af.CheapRaiderBot, zoo.RaiderBot, zoo.BaiterBot]
    _bots = [_ag] + [_opp[i - 1](_gi * 4 + i) for i in range(1, 4)]
    _g = engine.Game(base=_base, start_token=(_gi % 4) + 1)
    while not _g.over():
        _vs = _g.views()
        _acts = []
        for _i in range(4):
            _a = _bots[_i](_vs[_i])
            if _a not in _vs[_i].legal_actions:
                _a = "STAY"
            _acts.append(_a)
        _turns += 1
        if _ag.tr.cd[0] != _g.cd[0]:
            _own += 1
            if _ag.tr.cd[0] > _g.cd[0]:
                _high += 1
        if "SHIELD" in _vs[0].legal_actions and _ag.tr.cd[0] != 0:
            _ref += 1
        for _j in (1, 2, 3):
            if _ag.tr.cd[_j] != _g.cd[_j]:
                _riv += 1
        _g.step(_acts)
print("  over %d turns: own cooldown wrong %d (overstated %d), rivals' wrong "
      "%d of %d (%.2f%%)" % (_turns, _own, _high, _riv, _turns * 3,
                             100.0 * _riv / max(1, _turns * 3)))
print("  shields declined because the tracker disagreed with legal_actions: %d"
      "   %s" % (_ref, "OK" if _ref == 0 and _high == 0 else "BAD"))
if _high:
    fails.append("tracker overstated its own cooldown %d times" % _high)
if _ref:
    fails.append("declined %d shields that legal_actions allowed" % _ref)
if _riv > _turns * 3 * 0.03:
    fails.append("rival cooldown inference degraded to %.1f%% error"
                 % (100.0 * _riv / max(1, _turns * 3)))

print("\n=== G. every tracked file must be valid UTF-8 =========================")
print("Python's open() writes in the platform's default encoding on Windows, so")
print("a script that rewrites a UTF-8 file without saying encoding='utf-8' can")
print("drop a cp1252 byte into it. In a public repository that renders as")
print("mojibake; in bot.py it would be a syntax error on the server.\n")
_badenc = []
for _f in sorted(_os.listdir(_here)):
    if not _f.endswith((".py", ".md", ".json")):
        continue
    try:
        open(_os.path.join(_here, _f), "rb").read().decode("utf-8")
    except UnicodeDecodeError as _e:
        _badenc.append("%s (byte %d is 0x%02x)" % (_f, _e.start, _e.object[_e.start]))
print("  files that are not valid UTF-8: %s   %s"
      % ("; ".join(_badenc) if _badenc else "none", "BAD" if _badenc else "OK"))
if _badenc:
    fails.append("not valid UTF-8: %s" % "; ".join(_badenc))

print("\n" + "=" * 72)
if fails:
    print("FAILURES (%d):" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("ALL GUARDS PASS")
