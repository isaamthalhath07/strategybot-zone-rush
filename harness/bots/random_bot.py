import random


def act(state):
    return random.choice(state.legal_actions)
