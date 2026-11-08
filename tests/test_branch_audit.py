"""Check the new audit instrumentation against deliberately broken callbacks."""
from pathlib import Path
import tempfile
import unittest

from tools import audit_run


class InstrumentTests(unittest.TestCase):
    def callback(self,source,trace=False):
        temp_root = audit_run.ROOT/'simulator/.test-tmp'
        temp_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as folder:
            path = Path(folder)/'bot.py'
            path.write_text(source,encoding='utf8')
            old = audit_run.match.WORKER
            audit_run.match.WORKER = str(audit_run.WORKER)
            worker = audit_run.AuditProcess(str(path),trace)
            try:
                worker.spawn()
                self.assertTrue(worker.finish_load(5)['ok'])
                game = audit_run.Referee([2]*64)
                timing = dict(audit_run.match.DEFAULT_TIMING,hard_s=2,load_s=5)
                return worker.act(game.observation(1),1,timing)
            finally:
                worker.close()
                audit_run.match.WORKER = old

    def test_caught_failure_is_visible_in_diagnostic(self):
        result = self.callback('def act(state):\n    try:\n        return missing_value\n    except NameError:\n        return "STAY"\n',True)
        self.assertEqual(result['status'],'ok')
        self.assertEqual([e['type'] for e in result['handled_exceptions']],['NameError'])

    def test_mutating_public_input_is_a_fault(self):
        result = self.callback('def act(state):\n    state.board[0][0].owner = 4\n    return "STAY"\n')
        self.assertEqual(result['status'],'input-mutation')
        self.assertTrue(result['input_mutated'])

    def test_legal_policy_is_not_reported_as_failing(self):
        result = self.callback('def act(state):\n    return "STAY"\n',True)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['handled_exceptions'],[])
        self.assertFalse(result['input_mutated'])


if __name__=='__main__':
    unittest.main()
