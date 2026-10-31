"""Stage 2: build the PAR::Packer toolchain into work/local.

Order is ``cpan-sources.json`` ``_order``: dependencies first, PAR::Packer last.
MSYS2's Perl installation is left unchanged.

    python scripts/02-build-support.py
    python scripts/02-build-support.py PAR-Packer-1.064

``--stage-packer-after-test`` finishes a PAR::Packer run that already failed
inside the known-failure allowlist: it re-checks that log, then installs.
"""
from pathlib import Path
import shutil
import sys
import tarfile

from common import CPAN, DOWNLOADS, LOGS, PREFIX, perl_env, read_json, read_log, require_python, run, sha256
from locate import clangarm64

# Each entry's "allowed" set is an allowlist: every failing *.t must be a
# member, so a file outside the set aborts the build. These self-tests are
# environment-sensitive (locale, temp paths with spaces, pp relocation) and
# flaky between runs, so any subset of the set is tolerated. End-to-end
# correctness is the isolated biber.exe run in stage 5.
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


def main() -> None:
    require_python()
    msys = clangarm64()
    perl = msys / "bin" / "perl.exe"
    make = msys / "bin" / "mingw32-make.exe"
    for folder in (CPAN, LOGS, PREFIX):
        folder.mkdir(parents=True, exist_ok=True)
    env = perl_env(msys=msys)

    if sys.argv[1:] == ["--stage-packer-after-test"]:
        review_known_failures("PAR-Packer-1.064")
        run("PAR-Packer-1.064-stage", [make, "install"], cwd=CPAN / "PAR-Packer-1.064", env=env)
        return

    manifest = read_json("cpan-sources.json")
    names = sys.argv[1:] or manifest["_order"]
    for name in names:
        build_one(name, manifest, perl, make, env)
    print("\nStage 2 complete: PAR::Packer toolchain staged into", PREFIX)


if __name__ == "__main__":
    main()
