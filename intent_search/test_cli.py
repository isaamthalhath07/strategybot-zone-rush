"""Publication boundary checks using synthetic public inputs only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from .test_mcts import job


class CLITests(unittest.TestCase):
    def test_success_overwrite_refusal_and_private_input_never_publish_partial_result(self):
        cache=Path(__file__).resolve().parent/'.cache';cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            folder=Path(directory);source=folder/'public.json';output=folder/'result.json'
            raw=job(simulations=12,horizon=2)[1]
            source.write_text(json.dumps(raw),encoding='utf8')
            def call(target):
                return subprocess.run([sys.executable,'-m','intent_search','--input',str(source),'--output',str(target)],
                    cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=30)
            successful=call(output)
            self.assertEqual(successful.returncode,0,successful.stderr)
            first=output.read_bytes();result=json.loads(first)
            self.assertEqual(result['counterfactual_dual_referee_turns'],24)
            self.assertEqual(result['primary_match_credit'],0)
            self.assertNotEqual(call(output).returncode,0);self.assertEqual(first,output.read_bytes())
            raw['actual_opponent_seed']=3;source.write_text(json.dumps(raw),encoding='utf8')
            rejected=folder/'must-not-exist.json'
            self.assertNotEqual(call(rejected).returncode,0)
            self.assertFalse(rejected.exists())
            self.assertEqual(list(folder.glob('.intent-search-unpublished-*')),[])


if __name__=='__main__':unittest.main()
