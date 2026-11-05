"""One entry for the Biber stages. Run from the biber directory, or from the
parent via ``build.cmd biber``.

    python build.py                 stages 0-4, writes dist/biber.exe
    python build.py all             stages 0-6; test and install need the MiKTeX bin
    python build.py pack            one stage
    python build.py biber --no-test extra arguments go to that stage only
"""
from pathlib import Path
import sys

_RECIPES = str(Path(__file__).resolve().parents[1])
if _RECIPES not in sys.path:
    sys.path.insert(0, _RECIPES)
from _common import run_component

ROOT = Path(__file__).resolve().parent

STAGES = (
    ("prereqs", "00-prereqs.cmd"),
    ("fetch", "01-fetch-sources.py"),
    ("support", "02-build-support.py"),
    ("biber", "03-build-biber.py"),
    ("pack", "04-pack-biber.py"),
    ("test", "05-test-biber.py"),
    ("install", "06-install.py"),
)
BUILD = ("prereqs", "fetch", "support", "biber", "pack")

if __name__ == "__main__":
    run_component("biber", ROOT, STAGES, BUILD, __doc__,
                  example="python build.py biber --no-test")
