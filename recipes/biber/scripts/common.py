"""Paths, pinned-source helpers, and the Perl build environment.

Stages 2 to 4 share one workspace under ``work/`` and never write into the
MSYS2 Perl tree. ``INSTALL_BASE`` is ``work/local``. The recipe-agnostic
helpers come from ``recipes/_common.py`` and are re-exported here.
"""
from pathlib import Path
import os
import subprocess
import sys

_RECIPES = str(Path(__file__).resolve().parents[2])
if _RECIPES not in sys.path:
    sys.path.insert(0, _RECIPES)
from _common import fetch as download  # noqa: F401 -- re-exported
from _common import pe_record, require_python, sha256  # noqa: F401 -- re-exported
from _common import read_json as _read_json
from locate import ROOT, clangarm64, system_path, system_root  # noqa: F401 -- re-exported

WORK = ROOT / "work"
DOWNLOADS = WORK / "downloads"
CPAN = WORK / "cpan"
PREFIX = WORK / "local"
LOGS = WORK / "logs"
DIST = ROOT / "dist"


def read_json(name: str):
    """Read a JSON file from the recipe root (``sources.lock.json`` etc.)."""
    return _read_json(ROOT, name)


def perl_env(*, msys: Path | None = None, site_perl: bool = True,
             extra_perl5lib: str = "", extras: dict | None = None) -> dict:
    """Environment for clangarm64 Perl. Host PERL* and PAR_* values are dropped."""
    if msys is None:
        msys = clangarm64()
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("PERL", "PAR_")) or key in ("SHELL", "MAKEFLAGS", "MFLAGS"):
            env.pop(key)
    path = f"{PREFIX}/bin;{msys}/bin;{msys}/bin/core_perl;"
    if site_perl:
        path += f"{msys}/bin/site_perl;"
    path += system_path()
    perl5lib = f"{PREFIX}/lib/perl5;{PREFIX}/lib/perl5/MSWin32-arm64-perlio"
    if extra_perl5lib:
        perl5lib = extra_perl5lib + ";" + perl5lib
    env.update(PATH=path, PERL5LIB=perl5lib, LANG="C", LC_ALL="C")
    if extras:
        env.update(extras)
    return env


def run(label: str, command, *, cwd, env, timeout: int = 900, allow_failure: bool = False) -> int:
    """Run a command, append its output to ``work/logs/<label>.log``, and return the exit code."""
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / (label + ".log")
    with log.open("wb") as out:
        proc = subprocess.Popen(
            [str(arg) for arg in command],
            cwd=cwd,
            env=env,
            stdout=out,
            stderr=subprocess.STDOUT,
        )
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(
                [str(system_root() / "System32" / "taskkill.exe"), "/PID", str(proc.pid), "/T", "/F"],
                stdout=out,
                stderr=subprocess.STDOUT,
            )
            raise RuntimeError(f"Timeout: {label}; see {log}")
    print(f"{label}: exit {code}", flush=True)
    if code and not allow_failure:
        print(log.read_text(errors="replace")[-6000:], flush=True)
        raise SystemExit(code)
    return code


def read_log(label: str) -> bytes:
    return (LOGS / (label + ".log")).read_bytes()
