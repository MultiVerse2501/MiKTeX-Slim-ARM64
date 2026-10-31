"""Run scripts/02-build.sh inside MSYS2 CLANGARM64 bash."""
import os
import subprocess

from locate import ROOT, msys_root


def main() -> None:
    root = msys_root()
    bash = root / "usr" / "bin" / "bash.exe"
    cygpath = root / "usr" / "bin" / "cygpath.exe"
    script = ROOT / "scripts" / "02-build.sh"
    unix = subprocess.check_output([str(cygpath), "-u", str(script)], text=True).strip()
    env = os.environ.copy()
    env["MSYSTEM"] = "CLANGARM64"
    env["CHERE_INVOKING"] = "1"
    env.pop("MSYS2_ROOT", None)
    completed = subprocess.run([str(bash), "-lc", f"bash {unix}"], env=env)
    if completed.returncode:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
