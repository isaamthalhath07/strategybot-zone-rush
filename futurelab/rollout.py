"""Conditional joint futures with exact reference-engine mechanics."""
import math

import engine
from futurelab import models


def reconstruct(board, tracker):
    base, owner, up, home, occ, frozen = board
    game = engine.Game(base=base)
    game.owner = owner[:]
    game.upg = up[:]
    game.home = [owner[p] if home[p] else 0 for p in range(64)]
    game.pos = [occ.index(j) for j in range(1,5)]
    game.cd = tracker.cd[:]
    game.frozen = tracker.frozen[:]
    game.prog = tracker.prog[:]
    game.income = [sum(base[p]*(2 if up[p] else 1) for p in range(64) if owner[p]==j) for j in range(1,5)]
    game.score = tracker.score[:]
    game.turn = tracker.turn
    game.token = tracker.token
    return game


def noise(particle, turn, seat):
    # Common draws across candidate routes: changes in branching cannot shift
    # an RNG stream and fabricate a paired advantage.
    value = (particle+13)*2654435761 ^ (turn+41)*2246822519 ^ (seat+7)*3266489917
    value = ((value ^ (value>>16))*2246822519) & 0xffffffff
    return value/4294967296


def simulate(initial, seat, route, profiles, particle, horizon, snapshot=False, first_action=None):
    game = initial.clone()
    remaining = 81-game.turn
    route = list(route)
    targets = [None]*4
    my_profile = (0.91, 1.58, 1.40, 0.0, 1.0, 0.75)
    blocked = 0
    traces = []
    for elapsed in range(min(horizon, remaining)):
        actions = []
        for j in range(4):
            draw = noise(particle, game.turn, j)
            if j != seat:
                a, targets[j] = models.action(game, j, profiles[j], targets[j], draw)
            elif elapsed == 0 and first_action is not None:
                a = first_action
            elif game.frozen[j]:
                a = "STAY"
            elif models.should_shield(game, j, my_profile[5], draw):
                a = "SHIELD"
            else:
                while route:
                    p, level = route[0]
                    complete = level > 0 and game.owner[p] == j+1 and (level == 1 or game.upg[p])
                    if complete or (game.home[p] and game.owner[p] != j+1):
                        route.pop(0)
                    else:
                        break
                if route:
                    goal = route[0][0]
                    a = models.step(game,j,goal)
                    if route[0][1] == 0 and game.pos[j] == goal:
                        route.pop(0)
                    if a == "STAY" and game.pos[j] != goal:
                        blocked += 1
                        if blocked >= 2:
                            route.pop(0)
                            blocked = 0
                    else:
                        blocked = 0
                else:
                    a, targets[j] = models.action(game,j,my_profile,targets[j],draw)
            actions.append(a)
        game.step(actions)
        if snapshot:
            traces.append((game.owner[:], game.upg[:], game.pos[:]))
    # Tail is a terminal heuristic, not a claim that later ownership is fixed.
    tail = max(0, 81-game.turn)
    projected = [s+tail*i for s,i in zip(game.score,game.income)]
    own = projected[seat]
    pw = sum(1/(1+math.exp(max(-20,min(20,(projected[j]-own)/180)))) for j in range(4) if j != seat)
    return own, pw, traces
