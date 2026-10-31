"""Find MSYS2 and the MiKTeX ARM64 bin from the Ghostscript recipe."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
_BIN_TAIL = Path("build") / "sandbox" / "miktex" / "bin" / "arm64"


def msys_root() -> Path:
    roots = []
    if os.environ.get("MSYS2_ROOT"):
        roots.append(Path(os.environ["MSYS2_ROOT"]))
    drive = os.environ.get("SystemDrive")
    if drive:
        roots.append(Path(drive + os.sep) / "msys64")
    for root in roots:
        if (root / "usr" / "bin" / "bash.exe").is_file() and (root / "clangarm64" / "bin" / "clang.exe").is_file():
            return root
    raise SystemExit("Set MSYS2_ROOT to an MSYS2 install that has clangarm64.")


def miktex_bin() -> Path:
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
