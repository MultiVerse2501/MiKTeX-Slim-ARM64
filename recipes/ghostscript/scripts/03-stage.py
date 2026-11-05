"""Copy gsc.exe to dist/mgs.exe and close over non-system ARM64 DLLs.

MiKTeX looks up the interpreter as mgs.exe (MIKTEX_GS_EXE). The shared library
keeps the name the build linked, gsdll64.dll. Every staged PE must be machine
0xAA64. System and api-ms-win imports stay with Windows.
"""
from pathlib import Path
import json
import shutil

from locate import ROOT, msys_root, pe_record, system_root

DIST = ROOT / "dist"
SOURCE_BIN = ROOT / "work" / "source" / "sobin"


def main() -> None:
    gsc = SOURCE_BIN / "gsc.exe"
    dll = SOURCE_BIN / "gsdll64.dll"
    if not gsc.is_file() or not dll.is_file():
        raise SystemExit(f"missing build outputs in {SOURCE_BIN}; run the build stage first")
    clang_bin = msys_root() / "clangarm64" / "bin"
    readobj = clang_bin / "llvm-readobj.exe"
    if not readobj.is_file():
        raise SystemExit(f"missing {readobj}")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copy2(gsc, DIST / "mgs.exe")
    shutil.copy2(dll, DIST / "gsdll64.dll")

    system = system_root() / "System32"
    manifest = {}
    queue = [DIST / "mgs.exe", DIST / "gsdll64.dll"]
    while queue:
        path = queue.pop(0)
        if path.name.lower() in manifest:
            continue
        record = pe_record(path, readobj)
        manifest[path.name] = record
        for name in record["imports"]:
            lower = name.lower()
            if lower.startswith(("api-ms-win-", "ext-ms-win-")) or (system / name).is_file():
                continue
            if lower.startswith(("msys-", "cyg")):
                raise SystemExit(f"{path.name} imports {name}")
            dest = DIST / name
            if not dest.is_file():
                src = clang_bin / name
                if not src.is_file():
                    raise SystemExit(f"{path.name} imports {name}, not in {clang_bin}")
                shutil.copy2(src, dest)
            queue.append(dest)
    (DIST / "binary-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"staged {len(manifest)} ARM64 files in {DIST}", flush=True)


if __name__ == "__main__":
    main()
