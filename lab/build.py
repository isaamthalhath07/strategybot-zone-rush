"""Assemble a candidate from the tracker half and a decision half, with optional overrides.
  python3 lab/build.py NAME [key=value ...]     -> lab/cand/NAME.py
  python3 lab/build.py NAME gen=3 [key=value ...]   uses _head3.py + _tail3.py
zr1 to zr6 were built from _head.py + _tail2.py, which are kept unchanged so those files
still rebuild byte for byte.
"""
import sys, os, re
HERE = os.path.dirname(os.path.abspath(__file__))

def build(name, tailfile="_tail2.py", headfile="_head.py", **over):
    head = open(os.path.join(HERE, 'cand', headfile)).read()
    body = open(os.path.join(HERE, "cand", tailfile)).read()
    src = head + body
    for k, val in over.items():
        pat = r'("%s":\s*)([-0-9.e]+)' % re.escape(k)
        new, n = re.subn(pat, lambda mm: mm.group(1) + repr(val), src, count=1)
        if n != 1:
            raise KeyError(k)
        src = new
    path = os.path.join(HERE, 'cand', name + '.py')
    open(path, 'w').write(src)
    return path

if __name__ == '__main__':
    name = sys.argv[1]
    over = {}
    tailfile = '_tail2.py'
    headfile = '_head.py'
    for arg in sys.argv[2:]:
        k, val = arg.split('=')
        if k == 'tailfile':
            tailfile = val
        elif k == 'headfile':
            headfile = val
        elif k == 'gen':                # gen=3 -> _head3.py + _tail3.py
            headfile, tailfile = '_head%s.py' % val, '_tail%s.py' % val
        else:
            over[k] = float(val) if '.' in val or 'e' in val else int(val)
    print(build(name, tailfile, headfile, **over))
