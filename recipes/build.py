"""Dispatch a utility build.

    python build.py biber
    python build.py biber all
    python build.py ghostscript
    python build.py ghostscript test
"""
from pathlib import Path
import subprocess
import sys

_RECIPES = str(Path(__file__).resolve().parent)
if _RECIPES not in sys.path:
    sys.path.insert(0, _RECIPES)
from _common import require_python

ROOT = Path(__file__).resolve().parent
# A new component: create recipes/<name>/ with a build.py that calls
# _common.run_component (see biber or ghostscript), then list it here.
COMPONENTS = ("biber", "ghostscript")


def main() -> None:
    require_python()
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        print("\nComponents:", ", ".join(COMPONENTS))
        print("Each component accepts: build (default), all, or one stage name.")
        raise SystemExit(0 if argv else 1)
    name = argv[0]
    if name not in COMPONENTS:
        raise SystemExit(f"Unknown component {name!r}. Choose from: {', '.join(COMPONENTS)}")
    completed = subprocess.run([sys.executable, str(ROOT / name / "build.py"), *argv[1:]], cwd=ROOT / name)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
