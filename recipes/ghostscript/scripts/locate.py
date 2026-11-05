"""Find MSYS2 and the MiKTeX ARM64 bin from the Ghostscript recipe."""
from pathlib import Path
import sys

_RECIPES = str(Path(__file__).resolve().parents[2])
if _RECIPES not in sys.path:
    sys.path.insert(0, _RECIPES)
from _common import (  # noqa: F401 -- re-exported for the stage scripts
    fetch, miktex_bin, msys_candidates, pe_record, read_json, require_python,
    sha256, system_path, system_root,
)

ROOT = Path(__file__).resolve().parent.parent


def msys_root() -> Path:
    for root in msys_candidates():
        if (root / "usr" / "bin" / "bash.exe").is_file() and (root / "clangarm64" / "bin" / "clang.exe").is_file():
            return root
    raise SystemExit("Set MSYS2_ROOT to an MSYS2 install that has clangarm64.")
