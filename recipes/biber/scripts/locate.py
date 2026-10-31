"""Find tools that live outside the Biber recipe.

MSYS2 supplies the ARM64 Perl used to build and pack Biber. The MiKTeX tree is
optional until stages 5 and 6. This recipe lives at ``recipes/biber``.
``MSYS2_ROOT`` and ``MIKTEX_BIN`` override the search.
"""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
_BIN_TAIL = Path("build") / "sandbox" / "miktex" / "bin" / "arm64"


def system_root() -> Path:
    return Path(os.environ["SystemRoot"])


def system_path() -> str:
    root = system_root()
    return os.pathsep.join((str(root / "System32"), str(root)))


def clangarm64() -> Path:
    roots = []
    if os.environ.get("MSYS2_ROOT"):
        roots.append(Path(os.environ["MSYS2_ROOT"]))
    drive = os.environ.get("SystemDrive")
    if drive:
        roots.append(Path(drive + os.sep) / "msys64")
    for root in roots:
        clang = root / "clangarm64"
        if (clang / "bin" / "perl.exe").is_file():
            return clang
    raise SystemExit("Set MSYS2_ROOT to the MSYS2 installation.")


def miktex_bin() -> Path:
    """Directory that contains miktex-pdflatex.exe for the ARM64 sandbox."""
    override = os.environ.get("MIKTEX_BIN")
    if override:
        path = Path(override)
        if (path / "miktex-pdflatex.exe").is_file():
            return path
        raise SystemExit(f"MIKTEX_BIN has no miktex-pdflatex.exe: {path}")
    here = ROOT
    for _ in range(6):
        candidate = here / _BIN_TAIL
        if (candidate / "miktex-pdflatex.exe").is_file():
            return candidate
        if here.parent == here:
            break
        here = here.parent
    raise SystemExit(
        "MiKTeX ARM64 bin was not found. Set MIKTEX_BIN to the directory "
        "that contains miktex-pdflatex.exe."
    )
