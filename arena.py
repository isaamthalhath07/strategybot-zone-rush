"""
Tournament harness: 4-bot games with randomised seats, maps and starting token,
scored the way Round 1 scores them (each game = 3 pairwise results per bot -> Elo).
"""
import itertools
import random
import time

import engine


def pairwise_wins(places):
    """places[i] is seat i+1's place. Returns wins/draws/losses per seat."""
    out = []
    for i in range(4):
        w = d = l = 0
        for j in range(4):
            if i == j:
                continue
            if places[i] < places[j]:
                w += 1
            elif places[i] == places[j]:
                d += 1
            else:
                l += 1
        out.append((w, d, l))
    return out


class Registry(object):
    """name -> zero-arg factory returning a callable act(view)."""

    def __init__(self):
        self.f = {}

    def add(self, name, factory):
        self.f[name] = factory
        return self

    def make(self, name, seed):
        return self.f[name](seed)

    def names(self):
        return list(self.f.keys())


def run_game(reg, names, map_seed, token, game_seed, rules=None, max_turns=80):
    """names[i] plays seat i+1. Returns (scores, places, pairwise)."""
    base = engine.make_map(seed=map_seed)
    bots = [reg.make(names[i], game_seed * 4 + i) for i in range(4)]
    g = engine.play(bots, base=base, max_turns=max_turns, rules=rules,
                    start_token=token)
    pl = g.places()
    return g.score[:], pl, pairwise_wins(pl)


class Stats(object):
    def __init__(self, names):
        self.names = list(names)
        self.elo = dict((n, 1500.0) for n in names)
        self.games = dict((n, 0) for n in names)
        self.pw = dict((n, 0.0) for n in names)       # pairwise wins (draw = 0.5)
        self.score = dict((n, 0.0) for n in names)
        self.place = dict((n, 0.0) for n in names)
        self.firsts = dict((n, 0) for n in names)
        self.h2h = {}

    def add_game(self, names, scores, places, pws, k=16.0):
        for i, n in enumerate(names):
            w, d, l = pws[i]
            self.games[n] += 1
            self.pw[n] += w + 0.5 * d
            self.score[n] += scores[i]
            self.place[n] += places[i]
            if places[i] == 1:
                self.firsts[n] += 1
        for i, j in itertools.combinations(range(4), 2):
            a, b = names[i], names[j]
            if places[i] < places[j]:
                sa = 1.0
            elif places[i] == places[j]:
                sa = 0.5
            else:
                sa = 0.0
            ea = 1.0 / (1.0 + 10 ** ((self.elo[b] - self.elo[a]) / 400.0))
            self.elo[a] += k * (sa - ea)
            self.elo[b] += k * ((1.0 - sa) - (1.0 - ea))
            key = (a, b)
            rk = self.h2h.setdefault(key, [0.0, 0])
            rk[0] += sa
            rk[1] += 1
            key2 = (b, a)
            rk2 = self.h2h.setdefault(key2, [0.0, 0])
            rk2[0] += 1.0 - sa
            rk2[1] += 1

    def table(self, sort="elo"):
        rows = []
        for n in self.names:
            g = max(1, self.games[n])
            rows.append((n, self.elo[n], self.pw[n] / g, self.score[n] / g,
                         self.place[n] / g, self.firsts[n] / float(g), self.games[n]))
        idx = {"elo": 1, "pw": 2, "score": 3}[sort]
        rows.sort(key=lambda r: -r[idx])
        out = ["%-16s %7s %6s %8s %6s %6s %6s" %
               ("bot", "elo", "PW/3", "score", "place", "1st%", "games"),
               "-" * 60]
        for r in rows:
            out.append("%-16s %7.0f %6.2f %8.0f %6.2f %5.0f%% %6d" %
                       (r[0], r[1], r[2], r[3], r[4], r[5] * 100, r[6]))
        return "\n".join(out)

    def h2h_table(self, focus):
        out = ["head-to-head for %s (share of pairwise results won)" % focus, "-" * 48]
        rows = []
        for n in self.names:
            if n == focus:
                continue
            s, c = self.h2h.get((focus, n), [0.0, 0])
            if c:
                rows.append((n, s / c, c))
        rows.sort(key=lambda r: r[1])
        for n, w, c in rows:
            out.append("  vs %-16s %5.1f%%  (%d)" % (n, w * 100, c))
        return "\n".join(out)


def tournament(reg, entrants, games=400, seed=0, focus=None, rules=None,
               max_turns=80, verbose=False, opponents=None):
    """
    Random-matchup tournament. If `focus` is given, that bot is in every game and
    the other three seats are drawn from `opponents` (default: all other entrants).
    """
    rnd = random.Random(seed)
    st = Stats(entrants)
    pool = [n for n in (opponents or entrants) if n != focus]
    t0 = time.time()
    for gi in range(games):
        if focus:
            others = [pool[rnd.randrange(len(pool))] for _ in range(3)]
            names = [focus] + others
        else:
            names = [entrants[rnd.randrange(len(entrants))] for _ in range(4)]
        rnd.shuffle(names)
        sc, pl, pw = run_game(reg, names, rnd.randrange(1 << 30),
                              rnd.randint(1, 4), rnd.randrange(1 << 30),
                              rules=rules, max_turns=max_turns)
        st.add_game(names, sc, pl, pw)
        if verbose and (gi + 1) % 100 == 0:
            print("  %d/%d  (%.1fs)" % (gi + 1, games, time.time() - t0))
    return st


def default_registry(include_main=True):
    import zoo
    reg = Registry()
    for cls in zoo.ZOO:
        reg.add(cls.name, (lambda c: (lambda seed: c(seed)))(cls))
    if include_main:
        import mybot
        reg.add("mybot", lambda seed: mybot.Agent(seed))
    return reg


if __name__ == "__main__":
    import sys
    reg = default_registry(include_main=False)
    names = reg.names()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    st = tournament(reg, names, games=n, seed=1, verbose=True)
    print(st.table())
