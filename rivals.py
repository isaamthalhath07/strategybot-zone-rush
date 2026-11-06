"""
Frozen parameter snapshots, so the bot can be made to play against earlier
versions of itself and against counter-bots tuned specifically to beat it.
"""
import json
import os

import mybot

PATH = "snapshots.json"


def load():
    if os.path.exists(PATH):
        return json.load(open(PATH))
    return {}


def save(d):
    json.dump(d, open(PATH, "w"), indent=1, sort_keys=True)


def register(name, params):
    d = load()
    full = dict(mybot.PARAMS)
    full.update(params)
    d[name] = full
    save(d)
    return full


def names():
    return sorted(load().keys())


def factory(name):
    params = load()[name]

    def make(seed):
        return mybot.Agent(seed=seed, params=params)
    return make
