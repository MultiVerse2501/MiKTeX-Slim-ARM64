"""Stage 6: copy dist/biber.exe into the sibling MiKTeX ARM64 bin.

Refreshes the file-name database so biblatex can resolve ``biber.exe``.

    python scripts/06-install.py
"""
import os
import shutil
import subprocess

from common import DIST
from locate import miktex_bin, system_path


def main() -> None:
    src = DIST / "biber.exe"
    if not src.is_file():
        raise SystemExit(f"missing {src}; run stage 4 first")
    dest_dir = miktex_bin()
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


if __name__ == "__main__":
    main()
