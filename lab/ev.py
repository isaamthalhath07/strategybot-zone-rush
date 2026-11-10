"""Paired evaluation helper.
  python3 lab/ev.py --field DEV_ELITE --maps 60 --seed 11 --ref cur_e8 cand1 cand2 ...
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena, fields

def main():
    args = sys.argv[1:]
    opt = {"--field": "DEV_ELITE", "--maps": "60", "--seed": "11", "--ref": None, "--per": "4"}
    for k in list(opt):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    names = []
    for part in opt["--field"].split("+"):
        names += getattr(fields, part)
    fx = arena.fixtures(names, maps=int(opt["--maps"]), seed=int(opt["--seed"]), per_map=int(opt["--per"]))
    cands = args
    ref = opt["--ref"] or cands[0]
    if ref not in cands:
        cands = [ref] + cands
    t = time.time()
    per, err = arena.evaluate(cands, fx)
    print("field=%s maps=%s seed=%s games=%d errors=%d %.0fs" % (opt["--field"], opt["--maps"], opt["--seed"],
                                                                 len(fx) * len(cands), err, time.time() - t))
    arena.show(arena.summarize(per, ref=ref))

if __name__ == "__main__":
    main()
