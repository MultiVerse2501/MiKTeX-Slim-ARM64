"""One entry for the Ghostscript stages. Run from the ghostscript directory,
or from the parent via ``build.cmd ghostscript``.

    python build.py            prereqs, fetch, build, stage
    python build.py all        those, then test and install
    python build.py test       one stage
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
    ("fetch", "01-fetch.py"),
    ("build", "02-build.py"),
    ("stage", "03-stage.py"),
    ("test", "04-test.py"),
    ("install", "05-install.py"),
)
BUILD = ("prereqs", "fetch", "build", "stage")

if __name__ == "__main__":
    run_component("ghostscript", ROOT, STAGES, BUILD, __doc__)
