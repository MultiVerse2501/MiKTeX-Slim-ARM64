"""Find tools that live outside the Biber recipe.

MSYS2 supplies the ARM64 Perl used to build and pack Biber. The MiKTeX tree is
optional until stages 5 and 6. This recipe lives at ``recipes/biber``.
``MSYS2_ROOT`` and ``MIKTEX_BIN`` override the search.
"""
from pathlib import Path
import sys

_RECIPES = str(Path(__file__).resolve().parents[2])
if _RECIPES not in sys.path:
    sys.path.insert(0, _RECIPES)
from _common import miktex_bin, msys_candidates, system_path, system_root  # noqa: F401 -- re-exported

ROOT = Path(__file__).resolve().parent.parent


def clangarm64() -> Path:
    for root in msys_candidates():
        clang = root / "clangarm64"
        if (clang / "bin" / "perl.exe").is_file():
            return clang
    raise SystemExit("Set MSYS2_ROOT to the MSYS2 installation.")
