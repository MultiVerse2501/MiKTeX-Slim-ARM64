"""Dispatch a utility build.

    python build.py biber
    python build.py biber all
    python build.py ghostscript
    python build.py ghostscript test
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
COMPONENTS = ("biber", "ghostscript")


def main() -> None:
    if sys.version_info < (3, 12):
        raise SystemExit("Python 3.12 or newer is required, found " + sys.version.split()[0] + ".")
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        print("\nComponents:", ", ".join(COMPONENTS))
        print("Each component accepts: build (default), all, or one stage name.")
        raise SystemExit(0 if argv else 1)
    name = argv[0]
    if name not in COMPONENTS:
        raise SystemExit(f"Unknown component {name!r}. Choose from: {', '.join(COMPONENTS)}")
    script = ROOT / name / "build.py"
    completed = subprocess.run([sys.executable, str(script), *argv[1:]], cwd=ROOT / name)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
