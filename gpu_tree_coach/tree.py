"""Compact per-root information-history UCT tree, with reported optional pruning."""
from dataclasses import dataclass, field
import math

from .protocol import legal_actions


@dataclass(slots=True)
class Node:
    parent: int
    action: int
    observation: bytes
    legal: tuple
    visits: int = 0
    value_sum: int = 0
    counts: list = field(default_factory=lambda: [0]*6)
    values: list = field(default_factory=lambda: [0]*6)
    children: dict = field(default_factory=dict)
    active: tuple = ()
    pruned: tuple = ()


class Tree:
    def __init__(self, root):
        self.options = root.options
        self.nodes = [Node(-1, -1, root.packed, legal_actions(root.packed))]
        self.cap_hits = 0
        self.traces = []

    def select(self, node_id):
        # This interface has no latent game, rival action, model key or private counter.
        node = self.nodes[node_id]
        underexplored = [action for action in node.legal if node.counts[action] < 2]
        if underexplored:
            return min(underexplored, key=lambda action: (node.counts[action], action))
        if not node.active:
            ranked = sorted(node.legal, key=lambda action: (-node.values[action]/node.counts[action], action))
            node.active = tuple(ranked[:self.options['beam_width']])
            node.pruned = tuple(action for action in node.legal if action not in node.active)
        log = math.log(node.visits+1)
        c = self.options['exploration']
        return max(node.active, key=lambda action: (node.values[action]/(6*node.counts[action])
                    + c*math.sqrt(log/node.counts[action]), -action))

    def observe(self, parent, action, observation):
        # Root scope and parent ID plus exact bytes prevent hash-collision fusion.
        key = (action, observation)
        existing = self.nodes[parent].children.get(key)
        if existing is not None:
            return existing, False
        if len(self.nodes) >= self.options['max_nodes']:
            self.cap_hits += 1
            return None, True
        index = len(self.nodes)
        self.nodes.append(Node(parent, action, observation, legal_actions(observation)))
        self.nodes[parent].children[key] = index
        return index, True

    def backup(self, nodes, edges, value):
        if type(value) is not int or not 0 <= value <= 6:
            raise ValueError('Utility is an exact pairwise numerator0..6')
        for index in nodes:
            self.nodes[index].visits += 1
            self.nodes[index].value_sum += value
        for index, action in edges:
            self.nodes[index].counts[action] += 1
            self.nodes[index].values[action] += value

    def export(self):
        output = []
        for index, node in enumerate(self.nodes):
            output.append(dict(id=index, parent=node.parent, action=node.action, observation=node.observation.hex(),
                               legal=list(node.legal), visits=node.visits, value_sum=node.value_sum,
                               counts=list(node.counts), values=list(node.values), active=list(node.active), pruned=list(node.pruned),
                               children=[dict(action=action, observation=observation.hex(), node=child)
                                         for (action, observation), child in sorted(node.children.items())]))
        return output

    def recommend(self):
        node = self.nodes[0]
        if any(node.counts[action] < 2 for action in node.legal):
            raise ValueError('Every root action must receive at least two simulations')
        return max(node.legal, key=lambda action: (node.values[action]/node.counts[action], node.counts[action], -action))
