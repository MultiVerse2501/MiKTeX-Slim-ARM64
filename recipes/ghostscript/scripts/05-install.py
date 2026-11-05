"""Copy dist/mgs.exe and its DLL closure into the MiKTeX ARM64 bin.

A file already there is left in place when the bytes match, and replaced when
they do not. Re-running is safe. The file-name database is refreshed afterward.
"""
from pathlib import Path
import os
import shutil
import subprocess

from locate import miktex_bin, ROOT, sha256, system_path

DIST = ROOT / "dist"


def main() -> None:
    exe = DIST / "mgs.exe"
    if not exe.is_file():
        raise SystemExit(f"missing {exe}; run the stage step first")
    dest_dir = miktex_bin(ROOT)
    copied = []
    replaced = []
    for path in sorted(DIST.iterdir()):
        if path.suffix.lower() not in (".exe", ".dll"):
            continue
        dest = dest_dir / path.name
        if dest.is_file() and sha256(dest) == sha256(path):
            continue
        existed = dest.is_file()
        shutil.copy2(path, dest)
        (replaced if existed else copied).append(dest.name)
    print(f"copied {len(copied)} and replaced {len(replaced)} files into {dest_dir}", flush=True)
    miktex = dest_dir / "miktex.exe"
    if not miktex.is_file():
        raise SystemExit(f"copied Ghostscript, but {miktex} is missing so the FNDB was not refreshed")
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(dest_dir), system_path()))
    subprocess.run([str(miktex), "fndb", "refresh"], cwd=dest_dir, env=env, check=True)
    print("refreshed the MiKTeX file-name database", flush=True)


if __name__ == "__main__":
    main()
