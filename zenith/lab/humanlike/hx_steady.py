"""Human-like exploiter, style 'steady'. See _hxcore.py for what each style does."""
import os as _os

_CORE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_hxcore.py")
with open(_CORE) as _f:
    exec(compile(_f.read(), _CORE, "exec"))
STYLE = "steady"
