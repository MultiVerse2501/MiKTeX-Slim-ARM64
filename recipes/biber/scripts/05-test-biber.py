"""Stage 5: run dist/biber.exe with no MSYS2 or external Perl on PATH.

Isolation checks use a copy of the packed exe. The biblatex round-trip calls
the sibling MiKTeX ``miktex-pdflatex`` by full path, so its DLLs still resolve,
while Biber's PATH stays limited to the isolated directory.

    python scripts/05-test-biber.py
    python scripts/05-test-biber.py --installed

``--installed`` puts the MiKTeX bin first on PATH and invokes bare ``biber.exe``,
which is how biblatex finds it after stage 6.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

from common import ROOT, WORK, read_json
from locate import miktex_bin, system_path, system_root

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


def main() -> None:
    version = read_json("sources.lock.json")["biber"]["version"].encode("ascii")
    dist_exe = ROOT / "dist" / "biber.exe"
    if not dist_exe.is_file():
        raise SystemExit(f"missing {dist_exe}; run stage 4 first")
    bin_dir = miktex_bin()
    pdflatex = bin_dir / "miktex-pdflatex.exe"
    installed = "--installed" in sys.argv

    check = WORK / "standalone-check"
    check.mkdir(parents=True, exist_ok=True)
    isolated = check / "bin"
    isolated.mkdir(exist_ok=True)
    exe = isolated / "biber.exe"
    shutil.copy2(dist_exe, exe)

    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("PERL", "PAR_", "TEX")):
            env.pop(key)
    if installed:
        env["PATH"] = f"{bin_dir};{system_path()}"
        # CreateProcess does not append PATHEXT; biblatex on Windows runs biber.exe.
        biber = "biber.exe"
        found = shutil.which("biber.exe", path=env["PATH"])
        assert Path(found).resolve() == (bin_dir / "biber.exe").resolve(), found
    else:
        env["PATH"] = f"{isolated};{system_path()}"
        biber = str(exe)
    env.update(LANG="C", LC_ALL="C")
    cache = check / ("cache-" + hashlib.sha256(exe.read_bytes()).hexdigest()[:12])
    cache.mkdir(exist_ok=True)
    env["PAR_GLOBAL_TMPDIR"] = str(cache)

    results = []

    def run(label, args, cwd=check, timeout=300, extra=None):
        run_env = env.copy()
        if extra:
            run_env.update(extra)
        logfile = cwd / (label + ".log")
        argv = [str(arg) for arg in args]
        # This Python's CreateProcess does not search PATH for a bare name.
        if not Path(argv[0]).is_absolute():
            resolved = shutil.which(argv[0], path=run_env.get("PATH"))
            if resolved is None:
                raise FileNotFoundError(argv[0])
            argv[0] = resolved
        with logfile.open("wb") as stream:
            proc = subprocess.Popen(argv, cwd=cwd, env=run_env,
                                    stdout=stream, stderr=subprocess.STDOUT)
            try:
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                subprocess.run(
                    [str(system_root() / "System32" / "taskkill.exe"), "/PID", str(proc.pid), "/T", "/F"],
                    stdout=stream, stderr=subprocess.STDOUT,
                )
                code = "timeout"
        results.append(dict(label=label, exit_code=code, log=logfile.relative_to(ROOT).as_posix()))
        (WORK / "standalone-results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"{label}: exit {code}", flush=True)
        data = logfile.read_bytes()
        if code != 0:
            print(data.decode("utf-8", errors="replace")[-6000:], flush=True)
            raise SystemExit(1)
        return data

    if not installed:
        assert version in run("version", [exe, "--version"])
        run("help", [exe, "--help"], timeout=180)
        run("cache", [exe, "--cache"], timeout=180)
        assert version in run("via-path", [system_root() / "System32" / "cmd.exe", "/d", "/c",
                                           "biber.exe", "--version"])
        relocated = check / "日本語 実行"
        relocated.mkdir(exist_ok=True)
        shutil.copy2(exe, relocated / "biber.exe")
        assert version in run("relocated-executable", [relocated / "biber.exe", "--version"],
                              cwd=relocated)

    cwd = check / ("installed" if installed else "plain")
    if cwd.exists():
        shutil.rmtree(cwd)
    cwd.mkdir()
    (cwd / "references.bib").write_text(BIBLIOGRAPHY, encoding="utf-8")
    (cwd / "sample.tex").write_text(DOCUMENT, encoding="utf-8")

    prefix = "installed-" if installed else ""
    run(prefix + "latex-initial",
        [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "sample.tex"],
        cwd, timeout=900)
    run(prefix + "biber", [biber, "--validate-control", "sample"], cwd, timeout=300)
    clean = (cwd / "sample.bbl").read_text(encoding="utf-8")
    assert "\\entry{knuth}" in clean and "\\entry{muller}" in clean, clean
    assert clean.index("\\entry{knuth}") < clean.index("\\entry{muller}"), clean
    if not installed:
        run(prefix + "biber-perl5opt", [biber, "--validate-control", "sample"], cwd, timeout=300,
            extra={"PERL5OPT": "-MThisExternalPerlModuleMustNotLoad"})
        opted = (cwd / "sample.bbl").read_text(encoding="utf-8")
        assert opted == clean, "PERL5OPT changed Biber output"
    run(prefix + "latex-final",
        [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "sample.tex"],
        cwd, timeout=900)
    assert (cwd / "sample.pdf").read_bytes().startswith(b"%PDF-")
    run(prefix + "tool", [biber, "--tool", "--output-file=converted.bib", "references.bib"],
        cwd, timeout=300)
    assert "Müller" in (cwd / "converted.bib").read_text(encoding="utf-8")
    print("Standalone version, bibliography, sorting, PDF and tool checks passed.", flush=True)


if __name__ == "__main__":
    main()
