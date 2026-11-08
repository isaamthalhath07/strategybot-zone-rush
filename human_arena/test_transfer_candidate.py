"""Keep the second parameter finalist reproducible without new policy edits."""
import ast
import hashlib
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent / "candidates"


def parts(name):
    tree = ast.parse((HERE/name).read_text(encoding="utf8"))
    config = None
    kept = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=="CONFIG" for t in node.targets):
            config = ast.literal_eval(node.value)
        else:
            kept.append(node)
    tree.body = kept
    return config, ast.dump(tree,include_attributes=False)


class TransferProvenanceTests(unittest.TestCase):
    def test_corrected_implementation_is_identical_outside_configuration(self):
        self.assertEqual(parts("research_fixed.py")[1],parts("transfer_fixed.py")[1])
        self.assertEqual(hashlib.sha256((HERE/"transfer_fixed.py").read_bytes()).hexdigest(),
                         "fe03b8164ed3b4ebd2a04abcdfbb6fa729bdc34dea825088f7e82bf6e5b5ab5e")

    def test_exact_preexisting_transfer_weights_without_tuning(self):
        self.assertEqual(parts("transfer_fixed.py")[0],parts("branch_5457b5fdf4ca.py")[0])
        self.assertEqual(hashlib.sha256((HERE/"branch_5457b5fdf4ca.py").read_bytes()).hexdigest(),
                         "5457b5fdf4ca0e52d8502c6b237f975a88b1e8a97dd7bb4900f2b2acfbda1497")


if __name__ == "__main__":
    unittest.main()
