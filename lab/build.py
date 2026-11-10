"""Assemble a candidate from the tracker half and a decision half, with optional overrides.
  python3 lab/build.py NAME [key=value ...]     -> lab/cand/NAME.py
"""
import sys, os, re
HERE = os.path.dirname(os.path.abspath(__file__))

def build(name, tailfile="_tail2.py", **over):
    head = open(os.path.join(HERE, 'cand', '_head.py')).read()
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
    for arg in sys.argv[2:]:
        k, val = arg.split('=')
        if k == 'tailfile':
            tailfile = val
        else:
            over[k] = float(val) if '.' in val or 'e' in val else int(val)
    print(build(name, tailfile, **over))
