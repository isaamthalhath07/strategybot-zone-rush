"""Portable local play entry point; Python3.12 and its standard library only."""
from pathlib import Path
import sys

if sys.version_info[:2]!=(3,12): raise SystemExit('Please run this release with Python3.12.')
sys.path.insert(0,str(Path(__file__).resolve().parent))
from simulator.server import main

if __name__=='__main__': main()
