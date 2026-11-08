"""Build one isolated macro-lifetime experiment; never changes the release bot."""
import hashlib
import json
from pathlib import Path

from evolution.genomes import GenomeSpace

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PARENT = "e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5"


def sha(body):
    return hashlib.sha256(body).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Expected one exact parent fragment: " + old[:80])
    return text.replace(old, new, 1)


def transform(body):
    if sha(body) != PARENT:
        raise ValueError("This experiment requires its audited frozen parent")
    text = body.decode("utf8")
    helper = '''def _future_task_reward(reward, income_per_turn, original_life, retention, left, completion_cost):
    """Move a macro job to its actual completion clock, preserving its cash.

    The parent priced every job at the route from our CURRENT position. A
    second/third job finishes later; only its recurring-income component ages.
    Existing risk/denial/upgrade multipliers and one-off raid bonus stay intact.
    """
    if completion_cost > left:
        return 0.0
    future_life = min(left-completion_cost+1, retention)
    return max(0.0, reward + income_per_turn*(future_life-original_life))


'''
    text = once(text, "def _policy(state):\n", helper + "def _policy(state):\n")
    text = once(text, "    completion, renewal_traps = {}, set()\n",
                "    completion, renewal_traps = {}, set()\n    reward_clock = {}\n")
    text = once(text, "        risk = 0\n        completion[i] = 1.0\n",
                "        risk = 0\n        cash_reward = raid*v*8*config['cash_weight']*(1+up) if who not in (0, me) else 0.0\n"
                "        completion[i] = 1.0\n")
    text = once(text, "                reward /= 1.0 + risk*(0.65 if up else 0.18)\n",
                "                divisor = 1.0 + risk*(0.65 if up else 0.18)\n"
                "                reward /= divisor\n                cash_reward /= divisor\n")
    text = once(text, "        effort = work + risk*(3.5 if up else 2.4)\n",
                "        reward_clock[i] = ((reward-cash_reward)/life, life, retention)\n"
                "        effort = work + risk*(3.5 if up else 2.4)\n")
    text = once(text, "                    candidate = reward2/(between+effort2+extra)\n",
                "                    future_reward = _future_task_reward(\n"
                "                        reward2, *reward_clock[j], left, cost+between+work2+extra)\n"
                "                    candidate = future_reward/(between+effort2+extra)\n")
    text = once(text, "                        third_rate = max(third_rate, reward3/(between+effort3+extra))\n",
                "                        future_reward = _future_task_reward(\n"
                "                            reward3, *reward_clock[k], left, cost+second_cost+between+work3+extra)\n"
                "                        third_rate = max(third_rate, future_reward/(between+effort3+extra))\n")
    return text.encode("utf8")


def build():
    body = (ROOT/"bot.py").read_bytes()
    candidate = transform(body)
    space = GenomeSpace(body)
    genes2 = dict(space.genes, depth=2)
    artifacts = {
        "arrival_lifetime.py": candidate,
        "arrival_lifetime_depth2.py": GenomeSpace(candidate).export(genes2),
        "baseline_depth2.py": space.export(genes2),
    }
    entries = []
    for filename, payload in artifacts.items():
        path = HERE/filename
        if path.exists() and path.read_bytes() != payload:
            raise ValueError("Refusing to overwrite another experiment: " + filename)
        path.write_bytes(payload)
        entries.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(payload), bytes=len(payload)))
    manifest = dict(format="zone-rush-mathematical-candidate/1", parent_sha256=PARENT,
                    source_builder_sha256=sha(Path(__file__).read_bytes()),
                    production_changed=False, strength_evaluation="pending independent fresh games",
                    changes=["Reprice second/third macro recurring income at cumulative completion time",
                             "Preserve raid cash, existing risk/denial multipliers and all tactical guards"],
                    unchanged_genes=space.genes, artifacts=entries)
    (HERE/"arrival_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    build()
