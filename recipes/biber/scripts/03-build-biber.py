"""Stage 3: build the pinned Biber from source against the MSYS2 ARM64 modules.

Module::Build installs into ``work/local``, the same prefix as stage 2.
MSYS2's Perl tree is left unchanged.

    python scripts/03-build-biber.py
    python scripts/03-build-biber.py --no-test
    python scripts/03-build-biber.py --install

``--install`` is optional. Stage 4 packs ``work/cpan/<biber>/bin/biber`` from
the build tree, so a green ``Build test`` is enough to continue.
"""
import shutil
import sys
import tarfile

from common import CPAN, DOWNLOADS, LOGS, PREFIX, perl_env, read_json, read_log, require_python, run, sha256
from locate import clangarm64


def main() -> None:
    require_python()
    msys = clangarm64()
    perl = msys / "bin" / "perl.exe"
    LOGS.mkdir(parents=True, exist_ok=True)
    # Stage 3 stays on core_perl. site_perl is for the packer in stages 2 and 4.
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

    tested = "--no-test" not in sys.argv
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

    installed = "--install" in sys.argv
    if installed:
        run("biber-install", [perl, "Build", "install", "--install_base", PREFIX.as_posix()],
            cwd=src, env=env, timeout=1800)

    print("\nStage 3 complete: Biber built"
          + (" + tested" if tested else "")
          + (" + installed into work/local" if installed else "")
          + ".")


if __name__ == "__main__":
    main()
