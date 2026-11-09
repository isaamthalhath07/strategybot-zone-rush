"""Narrow public-history defense-availability experiment, never a release edit."""
import hashlib
import json
from pathlib import Path

from evolution.mathematical_candidates.build_arrival import once, transform as arrival_transform

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PARENT = "e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5"


def sha(body):
    return hashlib.sha256(body).hexdigest()


def transform(body):
    text = body.decode('utf8')
    helper = '''def _future_defense_at_risk(me, at, owner, frozen, memory, occupied, legal):
    """A ready landlord can remove our next defense while every exit is closed.

    Readiness is CERTAIN only when every public-history explanation says zero.
    This changes no freeze inference and never reads an actual private counter.
    """
    landlord = owner[at]
    return (landlord not in (0, me) and not frozen[landlord]
            and memory['cooldown_possible'][landlord] == {0}
            and not any(action in legal and target not in occupied
                        for action, target in _ADJ[at]))


'''
    text = once(text, 'def _policy(state):\n', helper+'def _policy(state):\n')
    text = once(text, '        threat = 0.0\n        miss = 1.0\n',
                '        threat = 0.0\n        miss = 1.0\n'
                '        defense_at_risk = _future_defense_at_risk(me, at, owner, frozen, memory, occupied, legal)\n')
    text = once(text, "            if config['imminent_shield'] and tier and memory['enemy_progress'][s] < 2:\n",
                "            if (config['imminent_shield'] and tier and memory['enemy_progress'][s] < 2\n"
                "                    and not defense_at_risk):\n")
    return text.encode('utf8')


def main():
    parent = (ROOT/'bot.py').read_bytes()
    if sha(parent) != PARENT:
        raise ValueError('This experiment requires the frozen guarded Transfer parent')
    variants = {'availability_only.py': transform(parent),
                'arrival_and_availability.py': transform(arrival_transform(parent))}
    artifacts = []
    for name, body in variants.items():
        path = HERE/name
        if path.exists() and path.read_bytes() != body:
            raise ValueError('Do not overwrite an already frozen candidate')
        path.write_bytes(body)
        artifacts.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(body)))
    manifest = dict(parent_sha256=PARENT, builder_sha256=sha(Path(__file__).read_bytes()),
                    artifacts=artifacts, production_changed=False,
                    hypothesis='Preserve defense when a certainly ready landlord can freeze us before a later raid completion and every immediate exit is closed.',
                    statistical_strength='untested', genes_changed=False,
                    caveat='A reachable counterexample motivates this narrow change; field performance must be tested independently.')
    path = HERE/'manifest.json'
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError('Refusing to replace a frozen experiment manifest')
    path.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf8', newline='\n')


if __name__ == '__main__':
    main()
