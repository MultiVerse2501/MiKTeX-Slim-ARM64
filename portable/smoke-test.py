"""Exercise a packed portable zip the way a user would: extract it, run the
bootstrap, and compile documents with only the portable tree on PATH. The
run tree lives in portable/dist/smoke-run; a completed bootstrap is reused,
and ``--fresh`` wipes the tree and starts over.

    python smoke-test.py              newest portable/dist zip
    python smoke-test.py --zip <zip>  a specific zip
    python smoke-test.py --fresh      wipe the run and bootstrap again
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent            # portable/
REPO = HERE.parent
RUN = HERE / "dist" / "smoke-run"
LOGS = RUN / "logs"

START = time.monotonic()
RESULTS: list[dict] = []


class SmokeFail(Exception):
    pass


def wipe(path: Path) -> None:
    """rmtree that clears the read-only attributes MiKTeX puts on some
    configured files."""
    if not path.exists():
        return

    def relax(function, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        function(target)

    shutil.rmtree(path, onexc=relax)


def stamp() -> str:
    return f"[{time.monotonic() - START:7.1f}s]"


HELLO = r"""\documentclass{article}
\begin{document}
Hello ARM64.
\end{document}
"""

BIBLIOGRAPHY = """@book{knuth,
  author = {Donald E. Knuth},
  title = {The Art of Computer Programming},
  year = {1968},
  publisher = {Addison-Wesley}}
@article{muller,
  author = {Anna Müller},
  title = {Unicode Bibliography Test},
  journaltitle = {Example Journal},
  year = {2026},
  volume = {1},
  pages = {1-2}}
"""

DOCUMENT = r"""\documentclass{article}
\usepackage[T1]{fontenc}
\usepackage[backend=biber,sorting=nyt]{biblatex}
\addbibresource{references.bib}
\begin{document}
\nocite{*}
\printbibliography
\end{document}
"""

POSTSCRIPT = (
    "%!PS\n"
    "0 0 0 setrgbcolor\n"
    "newpath 10 10 moveto 100 10 lineto 100 80 lineto closepath stroke\n"
    "showpage\n"
)


def read_versions() -> dict[str, str]:
    versions = {}
    for line in (REPO / "versions.txt").read_text(encoding="ascii").splitlines():
        key, eq, value = line.partition("=")
        if eq:
            versions[key.strip()] = value.strip()
    return versions


def find_zip() -> Path:
    hits = sorted((HERE / "dist").glob("miktex-portable-arm64-v*.zip"),
                  key=lambda path: path.stat().st_mtime, reverse=True)
    if not hits:
        raise SmokeFail("no portable zip in portable\\dist; run portable\\pack-portable.cmd first")
    return hits[0]


def extract(zip_path: Path) -> None:
    print(f"{stamp()} extracting {zip_path.name}", flush=True)
    try:
        # Pin the Windows bsdtar; a GNU tar on PATH cannot read zip.
        tar = Path(os.environ["SystemRoot"]) / "System32" / "tar.exe"
        completed = subprocess.run(
            [str(tar), "-a", "-xf", str(zip_path), "-C", str(RUN)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600,
        )
        if completed.returncode:
            raise OSError(completed.stderr.strip())
    except (OSError, FileNotFoundError):
        with zipfile.ZipFile(zip_path) as bundle:
            bundle.extractall(RUN)


def check_layout(run: Path, versions: dict[str, str]) -> None:
    for name in ("miktex-portable.cmd", "bootstrap-portable.cmd", "version.txt",
                 "LICENSE", "NOTICE.md"):
        if not (run / name).is_file():
            raise SmokeFail(f"the zip does not contain {name}")
    if not (run / "texmfs" / "install" / "miktex" / "bin" / "arm64" / "initexmf.exe").is_file():
        raise SmokeFail("the zip does not contain texmfs/install/miktex/bin/arm64/initexmf.exe")
    release = f"v{versions['version']}-{versions['miktex-tag']}"
    got = (run / "version.txt").read_text(encoding="ascii").strip()
    if got != release:
        raise SmokeFail(f"version.txt is {got!r}, expected {release!r}")


def bootstrap(run: Path) -> None:
    print(f"{stamp()} bootstrapping (network needed; downloads packages, builds formats)", flush=True)
    completed = subprocess.run(
        ["cmd", "/d", "/c", str(run / "bootstrap-portable.cmd")],
        cwd=run, stdin=subprocess.DEVNULL, timeout=1800,
    )
    if completed.returncode:
        raise SmokeFail(f"bootstrap-portable.cmd exited {completed.returncode}")
    if not (run / "texmfs" / "install" / "miktex" / "config" / "bootstrap-complete.txt").is_file():
        raise SmokeFail("bootstrap did not write bootstrap-complete.txt")
    print(f"{stamp()} bootstrap complete", flush=True)


def tool_env(run: Path) -> dict[str, str]:
    """The environment miktex-portable.cmd gives a user prompt, minus any
    inherited MiKTeX/TeX/Perl/GS state from the host."""
    install = run / "texmfs" / "install"
    startup = install / "miktex" / "config" / "miktexstartup.ini"
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("MIKTEX", "TEX", "PERL", "PAR_", "GS_")):
            env.pop(key)
    windows = Path(os.environ["SystemRoot"])
    env["PATH"] = os.pathsep.join((
        str(install / "miktex" / "bin" / "arm64"),
        str(windows / "System32"), str(windows),
    ))
    env["MIKTEX_COMMONSTARTUPFILE"] = str(startup)
    env["MIKTEX_USERSTARTUPFILE"] = str(startup)
    return env


def tool(label: str, args: list, cwd: Path, env: dict[str, str], timeout: int = 600) -> str:
    LOGS.mkdir(parents=True, exist_ok=True)
    argv = [str(arg) for arg in args]
    if not Path(argv[0]).is_absolute():
        resolved = shutil.which(argv[0], path=env["PATH"])
        if resolved is None:
            raise SmokeFail(f"{label}: {argv[0]} is not on the portable PATH")
        argv[0] = resolved
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise SmokeFail(f"{label}: timed out after {timeout}s (log: logs\\{label}.log)")
    (LOGS / (label + ".log")).write_text(completed.stdout or "", encoding="utf-8")
    if completed.returncode:
        print((completed.stdout or "")[-3000:], flush=True)
        raise SmokeFail(f"{label} exited {completed.returncode} (log: logs\\{label}.log)")
    seconds = round(time.monotonic() - started, 1)
    RESULTS.append({"step": label, "seconds": seconds, "status": "ok"})
    print(f"{stamp()} {label}: ok ({seconds}s)", flush=True)
    return completed.stdout or ""


def save_results(status: str) -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "smoke-results.json").write_text(
        json.dumps({"status": status, "steps": RESULTS}, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercise a packed portable zip end to end.")
    parser.add_argument("--zip", help="the zip to test (default: newest in portable/dist)")
    parser.add_argument("--fresh", action="store_true",
                        help="wipe the run tree and bootstrap again")
    args = parser.parse_args()

    versions = read_versions()
    zip_path = Path(args.zip) if args.zip else find_zip()
    marker = RUN / "texmfs" / "install" / "miktex" / "config" / "bootstrap-complete.txt"
    print(f"smoke-test: zip={zip_path.name} run={RUN}")

    if RUN.is_dir() and marker.is_file() and not args.fresh:
        print(f"{stamp()} reusing the bootstrapped run tree (use --fresh to redo)")
        check_layout(RUN, versions)
    else:
        wipe(RUN)
        RUN.mkdir(parents=True)
        extract(zip_path)
        check_layout(RUN, versions)
        RESULTS.append({"step": "extract", "status": "ok"})
        print(f"{stamp()} layout and version.txt ok", flush=True)
        bootstrap(RUN)

    install = RUN / "texmfs" / "install"
    bin_dir = install / "miktex" / "bin" / "arm64"
    startup = install / "miktex" / "config" / "miktexstartup.ini"
    if not (startup.is_file() and marker.is_file()):
        raise SmokeFail("the bootstrap markers are missing; miktex-portable.cmd would not launch")
    env = tool_env(RUN)
    work = RUN / "work"
    work.mkdir(exist_ok=True)

    out = tool("initexmf-version", [bin_dir / "initexmf.exe", "--version"], work, env)
    if versions["miktex-tag"] not in out:
        raise SmokeFail(f"initexmf --version did not report {versions['miktex-tag']}")
    out = tool("kpsewhich-hyphen", [bin_dir / "kpsewhich.exe", "hyphen.tex"], work, env)
    if "hyphen.tex" not in out:
        raise SmokeFail("kpsewhich did not resolve hyphen.tex")
    out = tool("biber-version", [bin_dir / "biber.exe", "--version"], work, env)
    if versions["biber"] not in out:
        raise SmokeFail(f"biber --version did not report {versions['biber']}")
    out = tool("mgs-version", [bin_dir / "mgs.exe", "--version"], work, env)
    if versions["ghostscript"] not in out:
        raise SmokeFail(f"mgs --version did not report {versions['ghostscript']}")

    (work / "hello.tex").write_text(HELLO, encoding="ascii")
    tool("hello-pdflatex",
         [bin_dir / "pdflatex.exe", "-interaction=nonstopmode", "-halt-on-error", "hello.tex"],
         work, env, timeout=900)
    if not (work / "hello.pdf").read_bytes().startswith(b"%PDF-"):
        raise SmokeFail("hello-pdflatex did not write a PDF")

    (work / "references.bib").write_text(BIBLIOGRAPHY, encoding="utf-8")
    (work / "sample.tex").write_text(DOCUMENT, encoding="utf-8")
    tool("biblatex-pdflatex-initial",
         [bin_dir / "pdflatex.exe", "-interaction=nonstopmode", "-halt-on-error", "sample.tex"],
         work, env, timeout=1200)
    if not (install / "tex" / "latex" / "biblatex").is_dir():
        raise SmokeFail("biblatex was not installed on first use")
    tool("biber-run", ["biber", "--validate-control", "sample"], work, env, timeout=600)
    bbl = (work / "sample.bbl").read_text(encoding="utf-8")
    if "\\entry{knuth}" not in bbl or "\\entry{muller}" not in bbl:
        raise SmokeFail("sample.bbl is missing the bibliography entries")
    if bbl.index("\\entry{knuth}") >= bbl.index("\\entry{muller}"):
        raise SmokeFail("sample.bbl sorts wrong; knuth must come before muller")
    tool("biblatex-pdflatex-final",
         [bin_dir / "pdflatex.exe", "-interaction=nonstopmode", "-halt-on-error", "sample.tex"],
         work, env, timeout=900)
    if not (work / "sample.pdf").read_bytes().startswith(b"%PDF-"):
        raise SmokeFail("the biblatex round trip did not write a PDF")
    tool("biber-tool", ["biber", "--tool", "--output-file=converted.bib", "references.bib"],
         work, env, timeout=600)
    if "Müller" not in (work / "converted.bib").read_text(encoding="utf-8"):
        raise SmokeFail("biber --tool lost the Unicode author name")

    if not (install / "ghostscript" / "base" / "Fontmap.MiKTeX").is_file():
        tool("install-ghostscript-package",
             [bin_dir / "miktex.exe", "packages", "install", "ghostscript"], work, env, timeout=900)
    else:
        RESULTS.append({"step": "install-ghostscript-package", "status": "already installed"})
        print(f"{stamp()} install-ghostscript-package: already installed")
    (work / "sample.ps").write_text(POSTSCRIPT, encoding="ascii")
    tool("rungs-pdfwrite",
         [bin_dir / "miktex-rungs.exe", "-dBATCH", "-dNOPAUSE", "-dSAFER",
          "-sDEVICE=pdfwrite", "-sOutputFile=gs.pdf", "sample.ps"],
         work, env, timeout=600)
    if not (work / "gs.pdf").read_bytes().startswith(b"%PDF-"):
        raise SmokeFail("miktex-rungs did not write a PDF")

    save_results("pass")
    total = time.monotonic() - START
    print(f"SMOKE PASS ({len(RESULTS)} steps, {total:.0f}s); run tree kept at {RUN}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SmokeFail as failure:
        print(f"SMOKE FAIL: {failure}", flush=True)
        save_results("fail")
        sys.exit(1)
