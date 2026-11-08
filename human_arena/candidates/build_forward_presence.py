"""Create a new v9 candidate for the user's clarified presence shield rule.

Preserves forward_fixed.py, original bot.py, and all historical artifacts.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = "95da830e6f29d0ac06b095fb4de57ace8eb7962881818fa50a4c19f714ec07d9"


def once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError("Source anchor count mismatch: %d %r" % (text.count(old), old[:90]))
    return text.replace(old, new, 1)


def build():
    source = (HERE / "forward_fixed.py").read_bytes()
    if hashlib.sha256(source).hexdigest() != EXPECTED:
        raise RuntimeError("The frozen source candidate changed")
    text = source.decode("utf8")
    text = once(text, "'catch_requires_stay': True", "'catch_requires_stay': False")
    text = once(text, """        for j in range(4):
            pj = self.pos[j]
            if pj is None or frozen_prev[j]:
                continue
            o = pow_[pj]
            if o and o != j + 1:
                on_land.setdefault(o - 1, []).append(j)""", """        for j in range(4):
            # Shields see occupancy AFTER movement, using ownership BEFORE
            # captures. An arrival or a move between the owner's cells remains
            # eligible; only already-frozen rivals are excluded.
            pj = newpos[j]
            if pj is None or frozen_prev[j]:
                continue
            o = pow_[pj]
            if o and o != j + 1:
                on_land.setdefault(o - 1, []).append(j)""")
    text = once(text, "                victims = [j for j in on_land.get(s, []) if stayed[j] and j not in S]",
                        "                victims = on_land.get(s, [])  # rival SHIELD is not immunity")
    text = once(text, """            if newpos[i] != pp:
                self.baits[i] += 1.0
            else:
                self.raids[i] += 1""", """            if newpos[i] is None or pow_[newpos[i]] != o:
                self.baits[i] += 1.0
            else:
                # Moving inside the same territory still exposes the rival.
                self.raids[i] += 1""")
    old = """        if tr.frozen[ridx] >= travel + need:
            return 0.0
        cd = tr.cd[ridx]
        if cd >= travel + need:
            return 0.0
        exposed = need if cd <= travel else max(0, travel + need - cd)
        if exposed <= 0:
            return 0.0"""
    new = """        blocked = max(tr.cd[ridx], tr.frozen[ridx])
        if blocked >= travel + need:
            return 0.0
        # With presence shields, the arrival turn is exposed too. A cooldown
        # of C prevents shielding on action turns 1..C, becoming ready at C+1.
        first_presence = max(1, travel)
        exposed = max(0, travel + need - max(first_presence, blocked + 1) + 1)
        if exposed <= 0:
            return 0.0"""
    text = once(text, old, new)
    text = once(text, "            commit = self._commit_prob(j)", """            # If every legal exit stays on our land (or is initially closed),
            # a moving opponent cannot evade this shield. Otherwise the model
            # estimates territorial residence rather than the STAY action.
            can_exit = any(owner[q] != seat and not occ[q] for q in _base_NEIGH[p])
            commit = self._commit_prob(j) if can_exit else 1.0""")
    header = '''"""Presence-shield candidate, following the user's 2026-11-08 clarification.
All non-already-frozen rivals occupying the owner's land after movement can be
caught, including arrivals and rivals choosing SHIELD. Previous snapshots remain
unchanged. Forward-model and bookkeeping verification is recorded separately.
"""

'''
    text = header + text
    compile(text, "forward_presence.py", "exec")
    target = HERE / "forward_presence.py"
    target.write_text(text, encoding="utf8", newline="\n")
    manifest = dict(source="forward_fixed.py", source_sha256=EXPECTED,
        candidate="forward_presence.py", sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        rule="catch_requires_stay=False: after movement, every non-already-frozen rival on shield-owner land is eligible, including rival SHIELD; captures occur afterward.",
        authority="Explicit user rule correction, 2026-11-08; not a claim that the previously ambiguous public wording was explicit.",
        changes=["All embedded hypothetical worlds default to presence shielding.",
                 "Shield attribution uses observed new positions and pre-capture ownership, including moving and SHIELD-choosing victims.",
                 "Territorial residence labels do not count moves within the same territory as escapes.",
                 "Raid risk includes arrival exposure and both cooldown/frozen unavailable turns.",
                 "Defensive catch model recognizes intruders with no unoccupied exit outside our land."])
    (HERE / "forward_presence.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    build()
