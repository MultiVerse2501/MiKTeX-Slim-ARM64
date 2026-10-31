"""Copy gsc.exe to dist/mgs.exe and close over non-system ARM64 DLLs.

MiKTeX looks up the interpreter as mgs.exe (MIKTEX_GS_EXE). The shared library
keeps the name the build linked, gsdll64.dll. Every staged PE must be machine
0xAA64. System and api-ms-win imports stay with Windows.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess

from locate import ROOT, msys_root

DIST = ROOT / "dist"
SOURCE_BIN = ROOT / "work" / "source" / "sobin"
IMPORT_NAME = re.compile(r"^\s+Name:\s+(\S+\.dll)\s*$", re.IGNORECASE | re.MULTILINE)


def machine(path: Path) -> int:
    raw = path.read_bytes()
    if raw[:2] != b"MZ":
        raise SystemExit(f"not a PE: {path}")
    offset = struct.unpack_from("<I", raw, 0x3C)[0]
    if raw[offset:offset + 4] != b"PE\0\0":
        raise SystemExit(f"not a PE: {path}")
    return struct.unpack_from("<H", raw, offset + 4)[0]


def imports(path: Path, readobj: Path) -> list[str]:
    text = subprocess.check_output(
        [str(readobj), "--coff-imports", str(path)],
        text=True,
        errors="replace",
    )
    return IMPORT_NAME.findall(text)


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

    system = Path(os.environ["SystemRoot"]) / "System32"
    manifest = {}
    queue = [DIST / "mgs.exe", DIST / "gsdll64.dll"]
    while queue:
        path = queue.pop(0)
        if path.name.lower() in manifest:
            continue
        kind = machine(path)
        if kind != 0xAA64:
            raise SystemExit(f"not ARM64: {path} machine=0x{kind:04x}")
        needed = imports(path, readobj)
        manifest[path.name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "machine": "ARM64 (0xAA64)",
            "imports": needed,
        }
        for name in needed:
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
