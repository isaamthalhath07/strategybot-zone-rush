"""Freeze v9 and apply only public-history bookkeeping corrections.

Never modifies root bot.py or its research inputs. The starting artifact's
SHA256 is fixed so concurrent work cannot silently change this candidate.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXPECTED = "d2bef4e077e9b601a4bdf42dd3351a708b9d70b725b897ff6870cea048178890"


SHIELD_BLOCK = '''        stayed = [newpos[i] is not None and newpos[i] == self.pos[i] for i in range(4)]
        on_land = {}
        for j in range(4):
            pj = self.pos[j]
            if pj is None or frozen_prev[j]:
                continue
            o = pow_[pj]
            if o and o != j + 1:
                on_land.setdefault(o - 1, []).append(j)
        # Completing visible work, moving, or losing land proves a player did
        # not SHIELD. In particular, an owner's observed upgrade rules out
        # attributing a rival's simultaneous self-backfire to that owner.
        did_work = [False] * 4
        lost_a_cell = [False] * 4
        for p in range(_base_NC):
            old_owner = pow_[p]
            if old_owner and owner[p] != old_owner:
                lost_a_cell[old_owner - 1] = True
        for j, p in enumerate(newpos):
            if p is not None and owner[p] == j + 1:
                did_work[j] = (pow_[p] != j + 1 or (upg[p] and not pupg[p]))
        previous_possible = getattr(self, 'cd_possible', [set([n]) for n in cd_prev])
        cand = [s for s in range(4) if 0 in previous_possible[s]
                and not frozen_prev[s] and stayed[s] and not did_work[s]
                and not lost_a_cell[s]]
        mi = seat - 1
        # A returned SHIELD is a request: a late response may have become STAY.
        # Non-SHIELD requests cannot become SHIELD. Current legal availability
        # can disambiguate accepted own shields when the player is not frozen.
        if my_last is not None and my_last != 'SHIELD' and mi in cand:
            cand.remove(mi)
        newly_set = set(newly)
        explanations = []
        next_values = [set() for _ in range(4)]
        for mask in range(1 << len(cand)):
            S = set(cand[k] for k in range(len(cand)) if mask >> k & 1)
            pred = set()
            for s in S:
                victims = [j for j in on_land.get(s, []) if stayed[j] and j not in S]
                pred.update(victims if victims else [s])
            if pred != newly_set:
                continue
            values = [set([4]) if j in S else set(max(0, n - 1) for n in previous_possible[j])
                      for j in range(4)]
            if (legal_actions is not None and not frozen_now[mi]
                    and 'SHIELD' not in legal_actions):
                # Absence proves a positive cooldown. Presence alone does not
                # erase an observed shield: permissive servers may list an
                # unusable SHIELD and normalize it to STAY.
                values[mi] = set(n for n in values[mi] if n > 0)
                if not values[mi]:
                    continue
            explanations.append(S)
            for j in range(4):
                next_values[j].update(values[j])
        if explanations:
            shielders = set.intersection(*explanations)
            possible_shielders = set.union(*explanations)
            self.cd_possible = next_values
        else:
            # Unexpected/missed observations are uncertainty, not permission
            # to invent a safe enemy cooldown. Preserve conservative readiness.
            shielders = set()
            possible_shielders = set(cand)
            self.cd_possible = [set([0]) | set(max(0, n - 1) for n in values)
                                for values in previous_possible]
            if legal_actions is not None and not frozen_now[mi]:
                if 'SHIELD' not in legal_actions:
                    self.cd_possible[mi] = set([1, 2, 3, 4])
        self.cd = [min(values) for values in self.cd_possible]
        for s in shielders:
            self.shields_seen[s] += 1
'''


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError("Expected one fixed source anchor, found %d: %r" % (text.count(old), old[:80]))
    return text.replace(old, new, 1)


def build():
    HERE.mkdir(parents=True, exist_ok=True)
    frozen = HERE / "forward_original.py"
    original = frozen.read_bytes() if frozen.exists() else (ROOT / "bot.py").read_bytes()
    if hashlib.sha256(original).hexdigest() != EXPECTED:
        raise RuntimeError("Original v9 does not match the reviewed frozen artifact")
    if not frozen.exists():
        frozen.write_bytes(original)
    text = original.decode("utf8")
    text = replace_once(text, "    def observe(self, owner, upg, occ, frz, seat, is_token, base, home_of, my_last=None):",
                        "    def observe(self, owner, upg, occ, frz, seat, is_token, base, home_of, my_last=None, legal_actions=None):")
    text = replace_once(text, "        self.cd = [0] * 4\n        self.prog = [0] * 4\n        self.score = [0] * 4\n        self.token = 1",
                        "        self.cd = [0] * 4\n        self.cd_possible = [set([0]) for _ in range(4)]\n        self.prog = [0] * 4\n        self.score = [0] * 4\n        self.token = 1")
    old = """        fresh = self._is_fresh(owner, occ, home_of)
        if fresh or self.prev is None or self.turn > 400:"""
    new = """        fresh = self._is_fresh(owner, occ, home_of) and not any(upg) and not any(frz)
        previous_irreversible_work = False
        if self.prev is not None:
            previous_owner, previous_upg, previous_occ, previous_frz = self.prev
            # A home backfire can thaw back into an unchanged pristine board;
            # that is ordinary play, not a new game. Ownership never becomes
            # neutral and upgraded homes never revert within one game.
            previous_irreversible_work = (any(previous_upg) or any(
                previous_owner[p] and not home_of[p] for p in range(_base_NC)))
        restarted = fresh and (previous_irreversible_work or self.turn >= _base_MAX_TURNS
                              or self.base != base or self.home_of != home_of)
        if restarted or self.prev is None or self.turn > 400:"""
    text = replace_once(text, old, new)
    text = replace_once(text, "            self.income = [0, 0, 0, 0]", """            # Current ownership already earns income, although no turn has
            # yet been banked. Do not add that income to score until observed.
            self.income = [sum(base[p] * (2 if upg[p] else 1)
                               for p in range(_base_NC) if owner[p] == j + 1)
                           for j in range(4)]""")
    start = text.index("        stayed = [newpos[i] is not None and newpos[i] == self.pos[i] for i in range(4)]")
    end = text.index("        for i in range(4):\n            pp = self.pos[i]", start)
    text = text[:start] + SHIELD_BLOCK + text[end:]
    text = replace_once(text, """            if cd_prev[o - 1] == 0 and (not frozen_prev[o - 1]):
                if o - 1 in shielders:
                    self.sh_yes[o - 1] += 1.0
                else:
                    self.sh_no[o - 1] += 1.0""", """            if previous_possible[o - 1] == set([0]) and not frozen_prev[o - 1]:
                if o - 1 in shielders:
                    self.sh_yes[o - 1] += 1.0
                elif o - 1 not in possible_shielders:
                    self.sh_no[o - 1] += 1.0""")
    text = replace_once(text, "            if newpos[i] != self.pos[i] or i in shielders:",
                        "            if newpos[i] != self.pos[i] or i in possible_shielders:")
    text = replace_once(text, """            if need is None:
                continue
            self.prog[i] += 1""", """            if need is None:
                self.prog[i] = 0
                continue
            if upg[newpos[i]] and not pupg[newpos[i]] and owner[newpos[i]] == i + 1:
                self.prog[i] = 0
                continue
            self.prog[i] += 1""")
    text = replace_once(text, "            if p != w[0] or owner[p] != i + 1 or self.frozen[i] > 0:",
                        "            if (p != w[0] or owner[p] != i + 1 or self.frozen[i] > 0\n                    or frozen_prev[i] or i in possible_shielders):")
    text = replace_once(text, "tr.observe(owner, upg, occ, frz, seat, view.is_priority_token, base, home_of, self.last_action)",
                        "tr.observe(owner, upg, occ, frz, seat, view.is_priority_token, base, home_of, self.last_action, view.legal_actions)")
    compile(text, "forward_fixed.py", "exec")
    output = HERE / "forward_fixed.py"
    output.write_text(text, encoding="utf8", newline="\n")
    manifest = dict(original_path=str(frozen), original_sha256=EXPECTED,
        candidate_path=str(output), sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        scope="Public-history bookkeeping only; unchanged route weights, forward opponent models, simulation physics, and runtime guards.",
        changes=["Distinguish continued pristine-board turns from a new game; retain progress, scores, and time while bots remain home.",
                 "Initialize current income without prematurely banking it.",
                 "Exclude shield hypotheses contradicted by movement, visible work, lost land, or own known non-shield request.",
                 "Retain feasible cooldown sets; never turn attribution ambiguity into a certain safe enemy cooldown.",
                 "Use own current legal actions to distinguish accepted shields from late-response STAY when observable.",
                 "Censor ambiguous shield model labels and partial-progress/carry observations; reset completed work from visible upgrades."])
    (HERE / "forward_fixed.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    build()
