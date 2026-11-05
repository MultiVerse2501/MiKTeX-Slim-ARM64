"""Shared plumbing for the MiKTeX Slim component recipes.

Recipe-agnostic helpers: pinned-source downloads with hash checks, JSON and
SHA-256 readers, MSYS2 and MiKTeX tool discovery, ARM64 PE checks, and the
stage dispatcher behind ``build.py``. Component-specific logic stays in that
component's directory.

A new component is a directory under ``recipes/`` with a ``build.py`` that
calls :func:`run_component` (see biber or ghostscript), a one-line
``build.cmd``, and its stage scripts under ``scripts/``. List the component
in ``COMPONENTS`` in ``recipes/build.py``.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import struct
import subprocess
import sys
import urllib.request

# llvm-readobj indents "Name:" by two spaces. A single leading space misses it.
_IMPORT_NAME = re.compile(r"^\s*Name:\s+(.+\.dll)\s*$", re.M | re.I)
_SANDBOX_TAIL = Path("build") / "sandbox" / "miktex" / "bin" / "arm64"
ARM64 = 0xAA64


def require_python() -> None:
    if sys.version_info < (3, 12):
        raise SystemExit("Python 3.12 or newer is required, found " + sys.version.split()[0] + ".")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(base: Path, name: str):
    return json.loads((base / name).read_text(encoding="utf-8"))


def fetch(url: str, dest: Path, want: str | None = None) -> None:
    """Download ``url`` into ``dest`` with the project User-Agent and a 120 s
    timeout, 1 MiB at a time. With ``want``, the SHA-256 is verified and a
    mismatched file is removed."""
    req = urllib.request.Request(url, headers={"User-Agent": "miktex-slim-arm64-fetch"})
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as out:
        for chunk in iter(lambda: resp.read(1 << 20), b""):
            out.write(chunk)
    if want is not None:
        got = sha256(dest)
        if got != want:
            dest.unlink(missing_ok=True)
            raise SystemExit(f"SHA256 MISMATCH {dest.name}\n  want {want}\n  got  {got}")


def system_root() -> Path:
    return Path(os.environ["SystemRoot"])


def system_path() -> str:
    root = system_root()
    return os.pathsep.join((str(root / "System32"), str(root)))


def msys_candidates() -> list[Path]:
    """MSYS2 roots to try: ``MSYS2_ROOT`` first, then ``<SystemDrive>\\msys64``."""
    roots = []
    if os.environ.get("MSYS2_ROOT"):
        roots.append(Path(os.environ["MSYS2_ROOT"]))
    drive = os.environ.get("SystemDrive")
    if drive:
        roots.append(Path(drive + os.sep) / "msys64")
    return roots


def miktex_bin(start: Path) -> Path:
    """Directory that contains miktex-pdflatex.exe for the ARM64 sandbox,
    searched upward from ``start``. ``MIKTEX_BIN`` overrides the search."""
    override = os.environ.get("MIKTEX_BIN")
    if override:
        path = Path(override)
        if (path / "miktex-pdflatex.exe").is_file():
            return path
        raise SystemExit(f"MIKTEX_BIN has no miktex-pdflatex.exe: {path}")
    here = start
    for _ in range(6):
        candidate = here / _SANDBOX_TAIL
        if (candidate / "miktex-pdflatex.exe").is_file():
            return candidate
        if here.parent == here:
            break
        here = here.parent
    raise SystemExit(
        "MiKTeX ARM64 bin was not found. Set MIKTEX_BIN to the directory "
        "that contains miktex-pdflatex.exe."
    )


def pe_machine(path: Path) -> int:
    """PE machine field of ``path``. Exits unless it is ARM64 (0xAA64)."""
    raw = path.read_bytes()
    if raw[:2] != b"MZ":
        raise SystemExit(f"not a PE: {path}")
    offset = struct.unpack_from("<I", raw, 0x3C)[0]
    if raw[offset:offset + 4] != b"PE\0\0":
        raise SystemExit(f"not a PE: {path}")
    machine = struct.unpack_from("<H", raw, offset + 4)[0]
    if machine != ARM64:
        raise SystemExit(f"Not ARM64: {path} machine=0x{machine:04x}")
    return machine


def pe_imports(path: Path, readobj: Path) -> list[str]:
    """DLL names ``path`` imports, via llvm-readobj --coff-imports."""
    text = subprocess.check_output(
        [str(readobj), "--coff-imports", str(path)],
        text=True,
        errors="replace",
    )
    return _IMPORT_NAME.findall(text)


def pe_record(path: Path, readobj: Path) -> dict:
    """Manifest record for one ARM64 PE: sha256, machine string, imports."""
    pe_machine(path)
    return dict(
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        machine="ARM64 (0xAA64)",
        imports=pe_imports(path, readobj),
    )


def run_component(component: str, root: Path, stages: tuple, build: tuple,
                  doc: str | None, example: str | None = None) -> None:
    """Stage dispatcher for one component's ``build.py``.

    ``stages`` is ``((name, filename), ...)`` under ``root/scripts`` and
    ``build`` is the subset run with no argument; ``doc`` is the build.py
    module docstring, shown by ``help``. ``.cmd`` stages run through cmd,
    ``.py`` stages are loaded and called as ``main()`` with any extra
    arguments left in ``sys.argv``.
    """
    require_python()
    scripts = root / "scripts"
    names = {name: filename for name, filename in stages}

    def load_main(filename: str):
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        path = scripts / filename
        module_name = component + "_stage_" + path.stem.replace("-", "_")
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.main

    def run_stage(name: str, extra: list[str]) -> None:
        filename = names[name]
        print(f"=== {component} {name} ({filename}) ===", flush=True)
        if filename.endswith(".cmd"):
            completed = subprocess.run(["cmd", "/d", "/c", str(scripts / filename)], cwd=root)
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

    argv = sys.argv[1:]
    if not argv or argv[0] == "build":
        selected, extra = list(build), []
    elif argv[0] == "all":
        selected, extra = [name for name, _filename in stages], argv[1:]
    elif argv[0] in names:
        selected, extra = [argv[0]], argv[1:]
    elif argv[0] in ("-h", "--help", "help"):
        print((doc or "").strip())
        print("\nStages:", ", ".join(names))
        raise SystemExit(0)
    else:
        raise SystemExit(f"Unknown stage {argv[0]!r}. Choose from: build, all, {', '.join(names)}")
    if len(selected) > 1 and extra:
        message = "Pass stage options only when running one stage."
        if example:
            message += " Example: " + example
        raise SystemExit(message)
    for name in selected:
        run_stage(name, extra)
