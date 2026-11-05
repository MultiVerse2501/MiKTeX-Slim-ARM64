"""One entry for the Biber stages. Run from the biber directory, or from the
parent via ``build.cmd biber``.

    python build.py                 prereqs through pack, writes dist/biber.exe
    python build.py all             every stage; test and install need the MiKTeX bin
    python build.py pack            one stage
    python build.py biber --no-test extra arguments go to that stage only
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile

_RECIPES = str(Path(__file__).resolve().parents[1])
if _RECIPES not in sys.path:
    sys.path.insert(0, _RECIPES)
from _common import fetch as download
from _common import miktex_bin, msys_candidates, pe_record, require_python, run_component, sha256
from _common import read_json as _read_json
from _common import system_path, system_root

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
DOWNLOADS = WORK / "downloads"
CPAN = WORK / "cpan"
PREFIX = WORK / "local"
LOGS = WORK / "logs"
DIST = ROOT / "dist"


def clangarm64() -> Path:
    for root in msys_candidates():
        clang = root / "clangarm64"
        if (clang / "bin" / "perl.exe").is_file():
            return clang
    raise SystemExit("Set MSYS2_ROOT to the MSYS2 installation.")


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


# --- stage: fetch -----------------------------------------------------------
# Download and SHA-256-verify the pinned Biber and PAR::Packer archives.
# An archive that already matches its pin is left in place.

def fetch(name: str, url: str, want: str, dest: Path) -> None:
    if dest.exists() and sha256(dest) == want:
        print(f"ok (cached)   {name}")
        return
    print(f"downloading   {name}  <- {url}")
    download(url, dest, want)
    print(f"verified      {name}")


def fetch_sources(extra: list[str]) -> int:
    require_python()
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    biber = read_json("sources.lock.json")["biber"]
    if biber["extract_dir"] != "biber-" + biber["version"]:
        raise SystemExit(f"extract_dir {biber['extract_dir']} does not match version {biber['version']}")
    fetch(biber["archive"], biber["url"], biber["sha256"], DOWNLOADS / biber["archive"])

    cpan = read_json("cpan-sources.json")
    for name in cpan["_order"]:
        spec = cpan[name]
        fetch(name, spec["url"], spec["sha256"], DOWNLOADS / (name + ".tar.gz"))

    print("\nAll sources present and verified in", DOWNLOADS)
    return 0


# --- stage: support ---------------------------------------------------------
# Build the PAR::Packer toolchain into work/local, in cpan-sources.json
# _order: dependencies first, PAR-Packer last. MSYS2's Perl installation is
# left unchanged.
#
#   python build.py support PAR-Packer-1.064   build only that package
#
# ``--stage-packer-after-test`` finishes a PAR::Packer run that already failed
# inside the known-failure allowlist: it re-checks that log, then installs.

# Each entry's "allowed" set is an allowlist: every failing *.t must be a
# member, so a file outside the set aborts the build. These self-tests are
# environment-sensitive (locale, temp paths with spaces, pp relocation) and
# flaky between runs, so any subset of the set is tolerated. End-to-end
# correctness is the isolated biber.exe run in the test stage.
KNOWN_TEST_FAILURES = {
    # t/24 dies while creating a file named "euro-€" under the C locale.
    # The module itself reports 0 failed subtest assertions.
    "Archive-Zip-1.68": {"allowed": {"t/24_unicode_win32.t"}},
    # Upstream PAR::Packer self-tests: pp relocation / PAR_GLOBAL_TMPDIR
    # and paths-with-spaces. Either or both may fail on a given run.
    "PAR-Packer-1.064": {"allowed": {"t/20-pp.t", "t/30-current_exec.t"}},
}


def review_known_failures(name: str) -> None:
    allowed = KNOWN_TEST_FAILURES[name]["allowed"]
    summary = read_log(name + "-test").decode("utf-8", errors="replace").split(
        "Test Summary Report\n")[-1]
    failed = {line.split()[0] for line in summary.splitlines() if "(Wstat:" in line}
    assert failed, f"{name}: test run failed but no failing files were parsed\n{summary}"
    unexpected = failed - allowed
    assert not unexpected, (
        f"{name}: unexpected failing test file(s) {sorted(unexpected)} "
        f"(allowlist: {sorted(allowed)})\n{summary}")
    print(f"{name}: {len(failed)} known-tolerated test failure(s) {sorted(failed)} "
          "retained; standalone Biber validation still required.", flush=True)


def patch_encode_jis2k(dest: Path) -> None:
    """enc2xs lives under core_perl on MSYS2, and the extensionless script is not executable on Windows."""
    path = dest / "Makefile.PL"
    original = path.read_text(encoding="utf-8")
    marker = "my $enc2xs_fpath = File::Spec->catfile($dpath, 'enc2xs');"
    addition = ("\n$enc2xs_fpath = File::Spec->catfile($dpath, 'core_perl', 'enc2xs')\n"
                "    unless -f $enc2xs_fpath;")
    if addition not in original:
        assert marker in original
        original = original.replace(marker, marker + addition)
    path.write_text(original.replace("if (-x $enc2xs_fpath);", "if (-f $enc2xs_fpath);"), encoding="utf-8")


def ensure_extracted(archive: Path, dest: Path, digest: str) -> None:
    """Keep an extract whose stamp matches the pin. A different pin replaces it."""
    stamp = dest / ".archive-sha256"
    want = digest + "\n"
    if dest.exists():
        if stamp.is_file() and stamp.read_text(encoding="ascii") == want:
            return
        if not stamp.is_file():
            stamp.write_text(want, encoding="ascii")
            return
        print(f"pin changed; replacing {dest}", flush=True)
        shutil.rmtree(dest)
    with tarfile.open(archive) as packed:
        packed.extractall(CPAN, filter="data")
    if not dest.is_dir():
        raise SystemExit(f"{archive.name} did not extract to {dest}")
    stamp.write_text(want, encoding="ascii")


def build_one(name: str, manifest: dict, perl: Path, make: Path, env: dict) -> None:
    archive = DOWNLOADS / (name + ".tar.gz")
    assert sha256(archive) == manifest[name]["sha256"], archive
    dest = CPAN / name
    ensure_extracted(archive, dest, manifest[name]["sha256"])
    if name == "Encode-JIS2K-0.05":
        patch_encode_jis2k(dest)

    run(name + "-configure", [perl, "Makefile.PL", f"INSTALL_BASE={PREFIX.as_posix()}"], cwd=dest, env=env)
    run(name + "-build", [make, "-j4"], cwd=dest, env=env)
    tolerated = name in KNOWN_TEST_FAILURES
    status = run(name + "-test", [make, "test"], cwd=dest, env=env, allow_failure=tolerated)
    if status:
        review_known_failures(name)
    run(name + "-stage", [make, "install"], cwd=dest, env=env)


def build_support(extra: list[str]) -> None:
    require_python()
    msys = clangarm64()
    perl = msys / "bin" / "perl.exe"
    make = msys / "bin" / "mingw32-make.exe"
    for folder in (CPAN, LOGS, PREFIX):
        folder.mkdir(parents=True, exist_ok=True)
    env = perl_env(msys=msys)

    if extra == ["--stage-packer-after-test"]:
        review_known_failures("PAR-Packer-1.064")
        run("PAR-Packer-1.064-stage", [make, "install"], cwd=CPAN / "PAR-Packer-1.064", env=env)
        return

    manifest = read_json("cpan-sources.json")
    names = extra or manifest["_order"]
    for name in names:
        build_one(name, manifest, perl, make, env)
    print("\nSupport build complete: PAR::Packer toolchain staged into", PREFIX)


# --- stage: biber -----------------------------------------------------------
# Build the pinned Biber from source against the MSYS2 ARM64 modules.
# Module::Build installs into ``work/local``, the same prefix as the support
# stage; MSYS2's Perl tree is left unchanged. ``--no-test`` skips the test
# run. ``--install`` also installs into work/local; it is optional, because
# the pack stage freezes bin/biber from the build tree.

def build_biber(extra: list[str]) -> None:
    require_python()
    msys = clangarm64()
    perl = msys / "bin" / "perl.exe"
    LOGS.mkdir(parents=True, exist_ok=True)
    # The biber build stays on core_perl. site_perl is for the packer stages.
    env = perl_env(msys=msys, site_perl=False)

    lock = read_json("sources.lock.json")["biber"]
    if lock["extract_dir"] != "biber-" + lock["version"]:
        raise SystemExit(f"extract_dir {lock['extract_dir']} does not match version {lock['version']}")
    src = CPAN / lock["extract_dir"]
    archive = DOWNLOADS / lock["archive"]
    assert sha256(archive) == lock["sha256"], archive
    stamp = src / ".archive-sha256"
    want = lock["sha256"] + "\n"
    if src.exists() and stamp.is_file() and stamp.read_text(encoding="ascii") != want:
        print(f"pin changed; replacing {src}", flush=True)
        shutil.rmtree(src)
    if not src.exists():
        CPAN.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as tar:
            tar.extractall(CPAN, filter="data")
        if not src.is_dir():
            raise SystemExit(f"{archive.name} did not extract to {src}")
    if not stamp.is_file():
        stamp.write_text(want, encoding="ascii")

    run("biber-build-pl", [perl, "Build.PL"], cwd=src, env=env)
    run("biber-build", [perl, "Build"], cwd=src, env=env, timeout=1800)

    tested = "--no-test" not in extra
    if tested:
        status = run("biber-test", [perl, "Build", "test"], cwd=src, env=env,
                     timeout=1800, allow_failure=True)
        report = read_log("biber-test").decode("utf-8", errors="replace")
        print(report[-4000:], flush=True)
        if status:
            fails = [line for line in report.splitlines()
                     if line.startswith("not ok") or "Result: FAIL" in line]
            print("\n".join(fails[-40:]), flush=True)
            raise SystemExit(f"biber Build test failed (exit {status}); see {LOGS / 'biber-test.log'}")

    installed = "--install" in extra
    if installed:
        run("biber-install", [perl, "Build", "install", "--install_base", PREFIX.as_posix()],
            cwd=src, env=env, timeout=1800)

    print("\nBiber build complete"
          + (" + tested" if tested else "")
          + (" + installed into work/local" if installed else "")
          + ".")


# --- stage: pack ------------------------------------------------------------
# Pack the built Biber into one ARM64 exe. ``pp`` freezes bin/biber with the
# workspace PAR::Packer, then the pack repeats until every non-system DLL
# import is inside the exe. Every embedded PE must be machine 0xAA64.
# Writes ``dist/biber.exe``, ``dist/binary-manifest.json``, and
# ``dist/linked-dlls.json``.

MODULES = [
    "deprecate",
    "Biber::Input::file::bibtex",
    "Biber::Input::file::biblatexml",
    "Biber::Output::dot",
    "Biber::Output::bbl",
    "Biber::Output::bblxml",
    "Biber::Output::bibtex",
    "Biber::Output::biblatexml",
    "Pod::Simple::TranscodeSmart",
    "Pod::Simple::TranscodeDumb",
    "List::MoreUtils::XS",
    "List::SomeUtils::PP",
    "List::MoreUtils::PP",
    "HTTP::Status",
    "HTTP::Date",
    "Encode::",
    "IO::Socket::SSL",
    "IO::String",
    "PerlIO::utf8_strict",
    "File::Find::Rule",
    "Text::CSV_XS",
    "DateTime",
    "Win32::Unicode",
]


def perl_runtime_dll(msys: Path) -> Path:
    found = sorted((msys / "bin").glob("perl5*.dll"))
    if len(found) != 1:
        raise SystemExit(f"expected one perl5*.dll in {msys / 'bin'}, found {[p.name for p in found]}")
    return found[0]


def embedded_files(source: Path, perl: Path, env: dict) -> list[tuple[Path, str]]:
    probe = (
        "use JSON::PP qw(encode_json); "
        "print encode_json({map { $_ => $INC{$_} } "
        "qw(Unicode/Collate.pm Mozilla/CA.pm Business/ISBN/Data.pm)});"
    )
    run("biber-module-paths",
        [perl, "-MUnicode::Collate", "-MMozilla::CA", "-MBusiness::ISBN::Data", "-e", probe],
        cwd=source, env=env)
    located = json.loads(read_log("biber-module-paths"))

    files = []
    for name in ("biber-tool.conf", "bcf.xsl"):
        files.append((source / "data" / name, "lib/Biber/" + name))
    for name in ("config.rnc", "config.rng", "bcf.rnc", "bcf.rng"):
        files.append((source / "data" / "schemata" / name, "lib/Biber/" + name))
    files.append((source / "lib" / "Biber" / "LaTeX" / "recode_data.xml",
                  "lib/Biber/LaTeX/recode_data.xml"))
    collate = Path(located["Unicode/Collate.pm"]).with_suffix("")
    for name in ("Locale", "CJK", "allkeys.txt", "keys.txt"):
        files.append((collate / name, "lib/Unicode/Collate/" + name))
    files.append((Path(located["Mozilla/CA.pm"]).with_suffix("") / "cacert.pem",
                  "lib/Mozilla/CA/cacert.pem"))
    files.append((Path(located["Business/ISBN/Data.pm"]).parent / "RangeMessage.xml",
                  "lib/Business/ISBN/RangeMessage.xml"))
    for path, _target in files:
        assert path.exists(), path
    return files


def pack_biber(extra: list[str]) -> None:
    msys = clangarm64()
    perl = msys / "bin" / "perl.exe"
    readobj = msys / "bin" / "llvm-readobj.exe"
    perl_dll = perl_runtime_dll(msys)
    lock = read_json("sources.lock.json")["biber"]
    source = CPAN / lock["extract_dir"]
    if not (source / "bin" / "biber").is_file():
        raise SystemExit(f"missing {source / 'bin' / 'biber'}; run the biber stage first")

    for folder in (LOGS, DIST, WORK / "pe-audit"):
        folder.mkdir(parents=True, exist_ok=True)
    env = perl_env(
        msys=msys,
        extra_perl5lib=f"{source}/blib/lib",
        extras={"PAR_VERBATIM": "1"},
    )

    files = embedded_files(source, perl, env)
    # The packed script must not be named "biber": on a case-insensitive volume
    # that clashes with the Biber library directory.
    main_script = WORK / "biber-main-arm64"
    shutil.copy2(source / "bin" / "biber", main_script)
    exe = DIST / "biber.exe"
    command = [
        perl, PREFIX / "bin" / "pp",
        "--execute", "--xargs=--version",
        "--output=" + str(exe),
        "--cachedeps=" + str(WORK / "scancache"),
    ]
    command += ["--module=" + module for module in MODULES]
    command += ["--addfile=" + str(path) + ";" + target for path, target in files]

    links = {}
    system = system_root() / "System32"
    audit = WORK / "pe-audit"
    for attempt in range(3):
        run(
            "biber-pack-" + str(attempt),
            command + ["--link=" + str(path) for path in links.values()] + [main_script],
            cwd=source, env=env, timeout=1800,
        )
        records = {"biber.exe": pe_record(exe, readobj)}
        with zipfile.ZipFile(exe) as bundle:
            for name in bundle.namelist():
                if not name.lower().endswith((".dll", ".exe")):
                    continue
                extracted = audit / Path(name).name
                extracted.write_bytes(bundle.read(name))
                records[name] = pe_record(extracted, readobj)
        included = {Path(name).name.lower() for name in records}
        for boot in (PREFIX / "bin" / "parl.exe", perl_dll):
            records["bootstrap/" + boot.name] = pe_record(boot, readobj)
        included.add(perl_dll.name.lower())
        pending = [dll for record in records.values() for dll in record["imports"]]
        missing = []
        while pending:
            dll = pending.pop()
            key = dll.lower()
            if key.startswith(("api-ms-win-", "ext-ms-win-")) or (system / dll).is_file():
                continue
            assert not key.startswith(("msys-", "cygwin")), dll
            if key in included:
                continue
            path = msys / "bin" / dll
            assert path.exists(), f"Missing DLL: {dll}"
            if key not in links:
                links[key] = path
                pending.extend(pe_record(path, readobj)["imports"])
            missing.append(key)
            included.add(key)
        if not missing:
            (DIST / "binary-manifest.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
            (DIST / "linked-dlls.json").write_text(
                json.dumps({key: path.name for key, path in sorted(links.items())}, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Created {exe.stat().st_size:,}-byte biber.exe; "
                  f"audited {len(records)} ARM64 PE files.", flush=True)
            return
        print(f"pack attempt {attempt}: {len(missing)} DLL(s) still outside the exe", flush=True)
    raise RuntimeError("DLL closure did not converge")


# --- stage: test ------------------------------------------------------------
# Run dist/biber.exe with no MSYS2 or external Perl on PATH. Isolation checks
# use a copy of the packed exe. The biblatex round trip calls the sibling
# MiKTeX ``miktex-pdflatex`` by full path, so its DLLs still resolve, while
# Biber's PATH stays limited to the isolated directory.
#
# ``--installed`` puts the MiKTeX bin first on PATH and invokes bare
# ``biber.exe``, which is how biblatex finds it after the install stage.

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


def test_biber(extra: list[str]) -> None:
    version = read_json("sources.lock.json")["biber"]["version"].encode("ascii")
    dist_exe = DIST / "biber.exe"
    if not dist_exe.is_file():
        raise SystemExit(f"missing {dist_exe}; run the pack stage first")
    bin_dir = miktex_bin(ROOT)
    pdflatex = bin_dir / "miktex-pdflatex.exe"
    installed = "--installed" in extra

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

    def run(label, args, cwd=check, timeout=300, extra_env=None):
        run_env = env.copy()
        if extra_env:
            run_env.update(extra_env)
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
            extra_env={"PERL5OPT": "-MThisExternalPerlModuleMustNotLoad"})
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


# --- stage: install ---------------------------------------------------------
# Copy dist/biber.exe into the sibling MiKTeX ARM64 bin and refresh the
# file-name database so biblatex can resolve ``biber.exe``.

def install_biber(extra: list[str]) -> None:
    src = DIST / "biber.exe"
    if not src.is_file():
        raise SystemExit(f"missing {src}; run the pack stage first")
    dest_dir = miktex_bin(ROOT)
    dest = dest_dir / "biber.exe"
    shutil.copy2(src, dest)
    print(f"copied {src} -> {dest}", flush=True)

    miktex = dest_dir / "miktex.exe"
    if not miktex.is_file():
        raise SystemExit(f"copied biber.exe, but {miktex} is missing so the FNDB was not refreshed")
    env = os.environ.copy()
    env["PATH"] = f"{dest_dir};{system_path()}"
    subprocess.run([str(miktex), "fndb", "refresh"], cwd=dest_dir, env=env, check=True)
    print("refreshed the MiKTeX file-name database", flush=True)


STAGES = {
    "prereqs": "prereqs.cmd",
    "fetch": fetch_sources,
    "support": build_support,
    "biber": build_biber,
    "pack": pack_biber,
    "test": test_biber,
    "install": install_biber,
}
BUILD = ("prereqs", "fetch", "support", "biber", "pack")

if __name__ == "__main__":
    run_component("biber", ROOT, STAGES, BUILD, __doc__,
                  example="python build.py biber --no-test")
