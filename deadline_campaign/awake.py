"""Temporary per-thread Windows system-awake request during owned work only."""
import ctypes
import os


def _request(flags):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.SetThreadExecutionState.argtypes=[ctypes.c_uint]
    kernel.SetThreadExecutionState.restype=ctypes.c_uint
    if not kernel.SetThreadExecutionState(flags):
        raise OSError(ctypes.get_last_error(),'Could not set temporary task execution state')


class KeepAwake:
    def __enter__(self):
        self.enabled=os.name=='nt'
        if self.enabled: _request(0x80000001)
        return self

    def __exit__(self,*_):
        if self.enabled: _request(0x80000000)
        self.enabled=False
