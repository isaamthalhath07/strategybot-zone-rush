"""A downloaded compact folder must run and record a whole isolated match."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from simulator import server


class DownloadedFolderTests(unittest.TestCase):
    def test_no_git_folder_finishes_eighty_turns_with_exact_public_inputs(self):
        directory = server.HERE / ".test-tmp"
        directory.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="downloaded-folder-", dir=directory) as folder:
            root = Path(folder)
            shutil.copytree(server.HERE, root / "simulator",
                            ignore=shutil.ignore_patterns("__pycache__", ".test-tmp", "bot_snapshots", "history", ".cache"))
            (root / "bot.py").write_bytes(b"def act(state):\n return 'STAY'\n")
            script = r'''import json,pathlib,subprocess,sys
sys.path.insert(0,sys.argv[1])
from simulator import server
subprocess.run=lambda *a,**k: (_ for _ in ()).throw(AssertionError('Git or a command-line dependency was invoked'))
root=pathlib.Path(sys.argv[1])
assert server.ROOT==root
app=server.App(root=root,history_dir=root/'saved')
try:
 state=app.new(dict(seed=192,seat=1,view='ai'))
 game_id=state['game_id']
 for expected in range(1,81):
  assert state['turn']==expected
  assert set(state)=={'game_id','turn','over','observation'}
  assert set(state['observation'])=={'board','bot_id','is_priority_token','legal_actions'}
  state=app.action(dict(game_id=game_id,turn=expected,action='STAY',view='ai'))
 assert state['over'] and state['turn']==81
 transcript=app.history_export(game_id)
 assert len(transcript['turns'])==80
 assert not transcript['metadata']['rules']['catch_requires_stay']
 assert not app.game.faults
 print(json.dumps(dict(turns=len(transcript['turns']),faults=len(app.game.faults),over=state['over'])))
finally:
 app.close()
'''
            result = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(root)],
                                    cwd=root, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout), dict(turns=80, faults=0, over=True))


if __name__ == "__main__":
    unittest.main()
