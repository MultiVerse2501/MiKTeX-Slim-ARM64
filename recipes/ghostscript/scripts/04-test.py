"""Run dist/mgs.exe with MSYS2 off PATH.

GS_LIB points at the extracted Resource tree, so the test does not need the
architecture-neutral ghostscript package installed in MiKTeX.
"""
from pathlib import Path
import json
import os
import subprocess

from locate import ROOT

DIST = ROOT / "dist"
SOURCE = ROOT / "work" / "source"


def main() -> None:
    expected = json.loads((ROOT / "sources.lock.json").read_text(encoding="utf-8"))["ghostscript"]["version"]
    exe = DIST / "mgs.exe"
    if not exe.is_file():
        raise SystemExit(f"missing {exe}; run the stage step first")
    lib = []
    for name in ("Resource/Init", "Resource", "lib", "iccprofiles"):
        path = SOURCE / name
        if path.is_dir():
            lib.append(path.as_posix())
    if not lib:
        raise SystemExit(f"no Ghostscript library directories under {SOURCE}")
    windows = Path(os.environ["SystemRoot"])
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GS_"):
            env.pop(key)
    env["PATH"] = os.pathsep.join((str(DIST), str(windows / "System32"), str(windows)))
    env["GS_LIB"] = os.pathsep.join(lib)

    def run(label: str, args: list[str], cwd: Path) -> str:
        print(label, flush=True)
        completed = subprocess.run(
            [str(exe), *args],
            cwd=cwd,
            env=env,
            text=True,
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode:
            print(completed.stdout[-4000:], flush=True)
            raise SystemExit(f"{label} exited {completed.returncode}")
        return completed.stdout

    reported = run("version", ["--version"], DIST)
    if expected not in reported:
        raise SystemExit(f"expected {expected}, got {reported!r}")
    checks = ROOT / "work" / "checks"
    checks.mkdir(parents=True, exist_ok=True)
    (checks / "sample.ps").write_text(
        "%!PS\n"
        "0 0 0 setrgbcolor\n"
        "newpath 10 10 moveto 100 10 lineto 100 80 lineto closepath stroke\n"
        "showpage\n",
        encoding="ascii",
    )
    run(
        "pdfwrite",
        ["-dBATCH", "-dNOPAUSE", "-dSAFER", "-sDEVICE=pdfwrite", "-sOutputFile=output.pdf", "sample.ps"],
        checks,
    )
    pdf = (checks / "output.pdf").read_bytes()
    if not pdf.startswith(b"%PDF-"):
        raise SystemExit("pdfwrite did not write a PDF")
    print(f"Ghostscript {expected} ok", flush=True)


if __name__ == "__main__":
    main()
