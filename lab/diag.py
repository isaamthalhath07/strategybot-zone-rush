"""Where do a bot's points and turns go? Aggregates referee events over many games."""
import collections
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim


def profile(result, seat):
    """Per-game action/event accounting for one seat (0-based)."""
    c = collections.Counter()
    s = seat + 1
    for snap, chosen, out in result["log"]:
        turn = snap["turn"]
        a = chosen[seat]
        eff = out["eff"][seat]
        frozen = snap["frozen"][seat] > 0
        phase = "early" if turn <= 27 else "mid" if turn <= 54 else "late"
        if frozen:
            c["frozen_turns"] += 1
        elif a == "SHIELD":
            c["shield"] += 1
        elif a == "STAY":
            c["stay"] += 1
        else:
            c["move"] += 1
            if eff == "STAY":
                c["move_failed"] += 1
        productive = False
        for e in out["events"]:
            t = e["type"]
            if t == "claim" and e["seat"] == s:
                c["claims"] += 1; c["claim_value"] += e["base"]; productive = True
                c["claims_" + phase] += 1
            elif t == "upgrade" and e["seat"] == s:
                c["upgrades"] += 1; c["upgrade_value"] += e["base"]; productive = True
                c["upgrades_" + phase] += 1
            elif t == "progress" and e["seat"] == s:
                productive = True
            elif t == "raid":
                if e["seat"] == s:
                    c["raids"] += 1; c["raid_bonus"] += e["bonus"]; productive = True
                    c["raids_L%d" % e["level"]] += 1
                    c["raids_" + phase] += 1
                elif e["from"] == s:
                    c["lost_cells"] += 1; c["lost_bonus"] += e["bonus"]
                    c["lost_L%d" % e["level"]] += 1
            elif t == "shield" and e["seat"] == s:
                if e["backfire"]:
                    c["backfires"] += 1
                else:
                    c["catches"] += len(e["caught"])
            elif t == "freeze" and e["seat"] == s and e["why"] == "caught":
                c["got_caught"] += 1
            elif t == "reset" and e["seat"] == s and e["why"] == "moved" and e["lost"] > 0:
                c["abandoned_progress"] += e["lost"]
        if not frozen and a == "STAY" and not productive:
            c["idle_stay"] += 1
        c["income_" + phase] += out["income"][seat]
    fin = result["final"]
    c["score"] = fin["score"][seat]
    c["final_income"] = fin["income"][seat]
    c["final_cells"] = fin["cells"][seat]
    c["final_upgraded"] = fin["upgraded"][seat]
    return c


KEYS = ["score", "income_early", "income_mid", "income_late", "final_income", "final_cells",
        "final_upgraded", "claims", "claim_value", "upgrades", "upgrade_value", "raids", "raid_bonus",
        "raids_L1", "raids_L2", "lost_cells", "lost_bonus", "lost_L1", "lost_L2", "shield", "catches",
        "backfires", "got_caught", "frozen_turns", "move", "move_failed", "stay", "idle_stay",
        "abandoned_progress", "claims_early", "claims_mid", "claims_late", "upgrades_early",
        "upgrades_mid", "upgrades_late", "raids_early", "raids_mid", "raids_late"]
