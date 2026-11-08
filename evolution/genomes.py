"""Bounded parameter evolution and exact standalone exports of the current bot."""
import ast
import hashlib
import math
import random

GROUPS = (
    ("upgrade_open", "upgrade_late", "income_lifetime", "fortify_premium", "cash_weight"),
    ("raid_open", "raid_late", "denial_base", "denial_close"),
    ("risk_open", "risk_late", "safety_slope", "contest_cost"),
    ("depth", "breadth", "route_weight", "route_delay", "inertia"),
    ("shield_weight", "backfire_cost", "shield_prior", "stay_prior", "feint_weight"),
)


def digest(body):
    return hashlib.sha256(body).hexdigest()


class GenomeSpace:
    def __init__(self, body):
        self.body = body
        self.text = body.decode("utf8")
        tree = ast.parse(self.text)
        assignments = {node.targets[0].id: node for node in tree.body
                       if isinstance(node, ast.Assign) and len(node.targets) == 1
                       and isinstance(node.targets[0], ast.Name)}
        self.genes = ast.literal_eval(assignments["CONFIG"].value)
        self.bounds = ast.literal_eval(assignments["BOUNDS"].value)
        self.integer = ast.literal_eval(assignments["INTEGER_GENES"].value)
        self.node = assignments["CONFIG"]
        if set(self.genes) != set(self.bounds) or any(type(v) is bool for v in self.genes.values()):
            raise ValueError("Expected only the existing bounded numerical genome")
        self.validate(self.genes)

    def validate(self, genes):
        if set(genes) != set(self.genes):
            raise ValueError("Genome keys changed; correctness switches are not genes")
        for key, value in genes.items():
            low, high = self.bounds[key]
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError("Invalid bounded gene: " + key)
            if key in self.integer and type(value) is not int:
                raise ValueError("Integer gene required: " + key)

    def export(self, genes):
        self.validate(genes)
        if genes == self.genes:
            return self.body  # Preserve the incumbent's exact submission bytes.
        lines = self.text.splitlines(keepends=True)
        literal = "CONFIG = " + repr(dict(sorted(genes.items()))) + "\n"
        result = "".join(lines[:self.node.lineno-1]) + literal + "".join(lines[self.node.end_lineno:])
        # Only this assignment changes. No trainer imports or runtime overrides.
        exported = result.encode("utf8")
        old_tree, new_tree = ast.parse(self.text), ast.parse(result)
        old_tree.body = [n for n in old_tree.body if not self._is_config(n)]
        new_tree.body = [n for n in new_tree.body if not self._is_config(n)]
        if ast.dump(old_tree) != ast.dump(new_tree):
            raise AssertionError("Export changed policy logic")
        return exported

    @staticmethod
    def _is_config(node):
        return isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CONFIG" for t in node.targets)

    def mutate(self, parent, seed, scale=0.08, grouped=False):
        self.validate(parent)
        rng, child = random.Random(seed), dict(parent)
        keys = list(rng.choice(GROUPS)) if grouped else rng.sample(sorted(child), rng.randint(1, 4))
        for key in keys:
            low, high = self.bounds[key]
            value = parent[key] + rng.gauss(0, scale * (high-low))
            value = max(low, min(high, value))
            child[key] = int(round(value)) if key in self.integer else round(value, 6)
        self.validate(child)
        return child

    def crossover(self, a, b, seed):
        self.validate(a)
        self.validate(b)
        rng = random.Random(seed)
        child = {}
        for group in GROUPS:
            chosen = a if rng.random() < 0.5 else b
            child.update({key: chosen[key] for key in group})
        self.validate(child)
        return child
