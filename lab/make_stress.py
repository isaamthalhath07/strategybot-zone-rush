"""Generate lab/stress/st_*.py from lab/stress_base.py: 5 Shield habits x raid habits.

  python3 lab/make_stress.py

These are not in any development field. They exist to break the candidate's
assumptions on purpose: landlords that never shield, shield on sight, shield a stay
early or at random; raiders that feint, swarm level-1 land, wait for cooldowns, hold
grudges or only strike in the endgame.
"""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__))
VARIANTS = [
    ("farmer_noshield", dict(shield="never", raid="never")),
    ("farmer_sight", dict(shield="sight", raid="never")),
    ("farmer_decisive", dict(shield="decisive", raid="never")),
    ("farmer_early", dict(shield="early", raid="never")),
    ("farmer_coin", dict(shield="coin", raid="never")),
    ("farmer_mix", dict(shield="mix", raid="never", w_upgrade=1.3)),
    ("raider_l1", dict(shield="decisive", raid="l1", w_raid=1.6)),
    ("raider_all", dict(shield="decisive", raid="all", w_raid=1.2)),
    ("raider_feint", dict(shield="decisive", raid="feint", w_raid=1.4)),
    ("raider_noshield", dict(shield="never", raid="all", w_raid=1.5)),
    ("endgame", dict(shield="decisive", raid="endgame", w_raid=2.0)),
    ("grudger", dict(shield="early", raid="grudge", w_raid=2.0)),
    ("cooldown_sniper", dict(shield="mix", raid="cooldown", w_raid=1.8)),
    ("swarm_sight", dict(shield="sight", raid="l1", w_raid=2.5, w_upgrade=0.6)),
]

if __name__ == "__main__":
    src = open(os.path.join(HERE, "stress_base.py")).read()
    out = os.path.join(HERE, "stress")
    os.makedirs(out, exist_ok=True)
    for k, (name, over) in enumerate(VARIANTS):
        cfg = {"name": name, "shield": "decisive", "raid": "never", "w_raid": 1.0, "w_upgrade": 1.0, "seed": k + 1}
        cfg.update(over)
        new, n = re.subn(r"^CONFIG = \{.*\}$", "CONFIG = %r" % cfg, src, count=1, flags=re.M)
        assert n == 1
        open(os.path.join(out, "st_%s.py" % name), "w").write(new)
    print("%d stress bots written to lab/stress/" % len(VARIANTS))
