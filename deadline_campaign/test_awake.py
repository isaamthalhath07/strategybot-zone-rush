import unittest
from unittest.mock import patch
from . import awake


class AwakeTests(unittest.TestCase):
    def test_system_request_clears_on_success_and_failure_without_display_or_power_changes(self):
        for fail in (False,True):
            with self.subTest(fail=fail),patch.object(awake.os,'name','nt'),patch.object(awake,'_request') as call:
                try:
                    with awake.KeepAwake():
                        if fail: raise ValueError('Synthetic task failure')
                except ValueError: pass
                self.assertEqual([args.args[0] for args in call.call_args_list],[0x80000001,0x80000000])

    def test_other_platform_does_not_call_windows(self):
        with patch.object(awake.os,'name','posix'),patch.object(awake,'_request') as call:
            with awake.KeepAwake(): pass
        call.assert_not_called()


if __name__=='__main__':unittest.main()
