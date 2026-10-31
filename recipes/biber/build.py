"""One entry for the Biber stages. Run from the biber directory, or from the
parent via ``build.cmd biber``.

    python build.py                 stages 0-4, writes dist/biber.exe
    python build.py all             stages 0-6; test and install need the MiKTeX bin
    python build.py pack            one stage
    python build.py biber --no-test extra arguments go to that stage only
"""
from pathlib import Path
import importlib.util
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"

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
NAMES = {name: filename for name, filename in STAGES}


def load_main(filename: str):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    path = SCRIPTS / filename
    module_name = "biber_stage_" + path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def run_stage(name: str, extra: list[str]) -> None:
    filename = NAMES[name]
    print(f"=== biber {name} ({filename}) ===", flush=True)
    if filename.endswith(".cmd"):
        completed = subprocess.run(["cmd", "/d", "/c", str(SCRIPTS / filename)], cwd=ROOT)
        if completed.returncode:
            raise SystemExit(completed.returncode)
        return
    main = load_main(filename)
    saved = sys.argv
    sys.argv = [filename, *extra]
    try:
        result = main()
    finally:
        sys.argv = saved
    if result:
        raise SystemExit(result)


def selected(argv: list[str]) -> tuple[list[str], list[str]]:
    if not argv or argv[0] == "build":
        return list(BUILD), []
    if argv[0] == "all":
        return [name for name, _filename in STAGES], argv[1:]
    if argv[0] in NAMES:
        return [argv[0]], argv[1:]
    if argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        print("\nStages:", ", ".join(NAMES))
        raise SystemExit(0)
    names = ", ".join(NAMES)
    raise SystemExit(f"Unknown stage {argv[0]!r}. Choose from: build, all, {names}")


def main() -> None:
    if sys.version_info < (3, 12):
        raise SystemExit("Python 3.12 or newer is required, found " + sys.version.split()[0] + ".")
    stages, extra = selected(sys.argv[1:])
    if len(stages) > 1 and extra:
        raise SystemExit("Pass stage options only when running one stage. Example: python build.py biber --no-test")
    for name in stages:
        run_stage(name, extra)


if __name__ == "__main__":
    main()
