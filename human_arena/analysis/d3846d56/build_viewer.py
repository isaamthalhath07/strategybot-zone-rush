import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
timeline = json.loads((HERE / "timeline.json").read_text())
decisions = json.loads((HERE / "decisions.json").read_text())
data = dict(base=timeline["metadata"]["base"], initial=timeline["metadata"]["initial"],
            frames=timeline["turns"], decisions=[dict(turn=d["turn"], seat=d["seat"],
                target=d.get("chosen_cell"), cooldown=d["memory"]["cooldown"],
                values=sorted(d.get("macro_values", []), key=lambda v:v["value"], reverse=True))
                for d in decisions], notes={
    7: "You capture D4, the first central 3-point cell. The bots have not yet completed their own central captures.",
    10: "You upgrade D4. AI 2 and AI 3 capture E4 and E5. AI 4 prefers its immediate D7 claim; its D5 alternative is valued lower.",
    12: "You claim D5. You now hold two central 3-pointers; AI 2 and AI 3 hold one each.",
    37: "AI 4 moves into E4 to begin the long raid trap. Its last completed productive work was the F4 upgrade on turn 36.",
    39: "AI 2 shields and catches AI 4. That freeze and four-turn cooldown allow the defender to be ready again before a fresh three-stay raid can finish.",
    42: "AI 4 has served two frozen turns. E4 raid rate is only 8.77, but an assumed post-capture upgrade adds 49.67. Total 58.44 beats C2's 43.81 despite the defender recharging before capture.",
    44: "AI 4's repeated E4 raid is caught again. This shield protects a valuable upgraded 3-point holding.",
    50: "AI 4 is caught by AI 3 on E5. It has still completed no new economic work since turn 36.",
    54: "AI 2 shields and backfires while on your C2. You visibly upgrade C3, proving you stayed and did not shield. The model nevertheless attributes the freeze to you.",
    55: "The inspected AI falsely believes your shield cooldown is 4 instead of 0. Correct public inference also reveals AI 2's real cooldown 4: moving EAST to E4 then staying three times would safely capture it.",
    57: "You shield and catch both AI 2 and AI 4. AI 4 still falsely believes you are on cooldown. Its D4 raid fails.",
    62: "End of AI 4's 26-turn economic dry spell: no completed capture, raid or upgrade on turns 37–62; recurring income stayed 24.",
    75: "AI 3 leaves E2 for D2. AI 2's shield misses and backfires. This is a successful feint by AI 3.",
    78: "AI 3 captures upgraded D2 during the cooldown caused by AI 2's premature shield, earning a 32-point raid bonus.",
    80: "Final: you 2378, AI 3 2179, AI 2 1924, AI 4 1615. Exhaustive last-two-to-four-turn alternatives found no missed AI score gain with other requests held fixed."
})
payload = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
template = (HERE / "replay.template.html").read_text(encoding="utf-8")
(HERE / "replay.html").write_text(template.replace("__DATA__", payload), encoding="utf-8")
print("Written replay.html; embedded data bytes:", len(payload.encode()))
