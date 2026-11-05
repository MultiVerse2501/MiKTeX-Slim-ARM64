"""One entry for the Ghostscript stages. Run from the ghostscript directory,
or from the parent via ``build.cmd ghostscript``.

    python build.py            prereqs, fetch, build, stage
    python build.py all        those, then test and install
    python build.py test       one stage
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tarfile

_RECIPES = str(Path(__file__).resolve().parents[1])
if _RECIPES not in sys.path:
    sys.path.insert(0, _RECIPES)
from _common import fetch as download
from _common import miktex_bin, msys_candidates, pe_record, read_json, require_python
from _common import run_component, sha256, system_path, system_root

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
DOWNLOADS = WORK / "downloads"
SOURCE = WORK / "source"
SOURCE_BIN = WORK / "source" / "sobin"
DIST = ROOT / "dist"


def msys_root() -> Path:
    for root in msys_candidates():
        if (root / "usr" / "bin" / "bash.exe").is_file() and (root / "clangarm64" / "bin" / "clang.exe").is_file():
            return root
    raise SystemExit("Set MSYS2_ROOT to an MSYS2 install that has clangarm64.")


# --- stage: fetch -----------------------------------------------------------
# Download the pinned Ghostscript, check the vendored patches, and extract
# sources. Bundled third-party libraries listed in sources.lock.json are left
# out of the working tree; the build links the MSYS2 copies instead.
# work/source/.extracted records the archive and patch hashes. A different
# pin replaces that tree.

def extract_stamp(gs: dict, patches: dict) -> str:
    lines = [f"archive {gs['sha256']}", f"extract {gs['extract_dir']}"]
    for name in sorted(patches):
        lines.append(f"patch {name} {patches[name]}")
    return "\n".join(lines) + "\n"


def fetch(extra: list[str]) -> None:
    require_python()
    lock = read_json(ROOT, "sources.lock.json")
    gs = lock["ghostscript"]
    version = gs["version"]
    if gs["extract_dir"] != "ghostscript-" + version or version not in gs["archive"]:
        raise SystemExit(f"Ghostscript lock version {version} does not match its archive names")
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    archive = DOWNLOADS / gs["archive"]
    if not archive.is_file() or sha256(archive) != gs["sha256"]:
        print(f"downloading {gs['url']}", flush=True)
        download(gs["url"], archive)
    got = sha256(archive)
    if got != gs["sha256"]:
        raise SystemExit(f"hash mismatch for {archive.name}: {got}")
    print(f"archive ok {archive.name}", flush=True)

    for name, expected in lock["patches"].items():
        path = ROOT / "patches" / name
        if not path.is_file():
            raise SystemExit(f"missing patch {path}")
        got = sha256(path)
        if got != expected:
            raise SystemExit(f"hash mismatch for {name}: {got}")
    print(f"patches ok ({len(lock['patches'])})", flush=True)

    stamp = extract_stamp(gs, lock["patches"])
    marker = SOURCE / ".extracted"
    if marker.is_file() and marker.read_text(encoding="utf-8") == stamp:
        print(f"source already extracted in {SOURCE}", flush=True)
        return
    legacy = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    if SOURCE.exists() and legacy == gs["extract_dir"]:
        marker.write_text(stamp, encoding="utf-8")
        print(f"recorded the extract stamp for {SOURCE}", flush=True)
        return
    if SOURCE.exists():
        print(f"pin changed; replacing {SOURCE}", flush=True)
        shutil.rmtree(SOURCE)
    SOURCE.mkdir(parents=True)
    skip = set(lock["excluded_bundled_libraries"])
    with tarfile.open(archive) as packed:
        members = []
        for member in packed:
            parts = Path(member.name).parts
            if len(parts) < 2 or parts[0] != gs["extract_dir"] or parts[1] in skip:
                continue
            member.name = "/".join(parts[1:])
            target = (SOURCE / member.name).resolve()
            if not target.is_relative_to(SOURCE.resolve()):
                raise SystemExit(f"refusing to extract {member.name}")
            members.append(member)
        packed.extractall(SOURCE, members=members, filter="data")
    marker.write_text(stamp, encoding="utf-8")
    print(f"extracted {len(members)} members into {SOURCE}", flush=True)


# --- stage: build -----------------------------------------------------------
# Run compile.sh inside MSYS2 CLANGARM64 bash.

def build(extra: list[str]) -> None:
    root = msys_root()
    bash = root / "usr" / "bin" / "bash.exe"
    cygpath = root / "usr" / "bin" / "cygpath.exe"
    script = ROOT / "compile.sh"
    unix = subprocess.check_output([str(cygpath), "-u", str(script)], text=True).strip()
    env = os.environ.copy()
    env["MSYSTEM"] = "CLANGARM64"
    env["CHERE_INVOKING"] = "1"
    env.pop("MSYS2_ROOT", None)
    completed = subprocess.run([str(bash), "-lc", f"bash {unix}"], env=env)
    if completed.returncode:
        raise SystemExit(completed.returncode)


# --- stage: stage -----------------------------------------------------------
# Copy gsc.exe to dist/mgs.exe and close over non-system ARM64 DLLs.
# MiKTeX looks up the interpreter as mgs.exe (MIKTEX_GS_EXE). The shared
# library keeps the name the build linked, gsdll64.dll. System and
# api-ms-win imports stay with Windows.

def stage(extra: list[str]) -> None:
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


# --- stage: test ------------------------------------------------------------
# Run dist/mgs.exe with MSYS2 off PATH. GS_LIB points at the extracted
# Resource tree, so the test does not need the architecture-neutral
# ghostscript package installed in MiKTeX.

def test(extra: list[str]) -> None:
    expected = read_json(ROOT, "sources.lock.json")["ghostscript"]["version"]
    exe = DIST / "mgs.exe"
    if not exe.is_file():
        raise SystemExit(f"missing {exe}; run the stage step first")
    lib = []
    for name in ("Resource/Init", "Resource", "lib", "iccprofiles"):
        path = SOURCE / name
        if path.is_dir():
            lib.append(path.as_posix())
    if not lib:
        raise SystemExit(f"no Ghostscript library directories under {SOURCE}")
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GS_"):
            env.pop(key)
    env["PATH"] = os.pathsep.join((str(DIST), system_path()))
    env["GS_LIB"] = os.pathsep.join(lib)

    def run(label: str, args: list[str], cwd: Path) -> str:
        print(label, flush=True)
        completed = subprocess.run(
            [str(exe), *args],
            cwd=cwd,
            env=env,
            text=True,
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode:
            print(completed.stdout[-4000:], flush=True)
            raise SystemExit(f"{label} exited {completed.returncode}")
        return completed.stdout

    reported = run("version", ["--version"], DIST)
    if expected not in reported:
        raise SystemExit(f"expected {expected}, got {reported!r}")
    checks = WORK / "checks"
    checks.mkdir(parents=True, exist_ok=True)
    (checks / "sample.ps").write_text(
        "%!PS\n"
        "0 0 0 setrgbcolor\n"
        "newpath 10 10 moveto 100 10 lineto 100 80 lineto closepath stroke\n"
        "showpage\n",
        encoding="ascii",
    )
    run(
        "pdfwrite",
        ["-dBATCH", "-dNOPAUSE", "-dSAFER", "-sDEVICE=pdfwrite", "-sOutputFile=output.pdf", "sample.ps"],
        checks,
    )
    pdf = (checks / "output.pdf").read_bytes()
    if not pdf.startswith(b"%PDF-"):
        raise SystemExit("pdfwrite did not write a PDF")
    print(f"Ghostscript {expected} ok", flush=True)


# --- stage: install ---------------------------------------------------------
# Copy dist/mgs.exe and its DLL closure into the MiKTeX ARM64 bin. A file
# already there is left in place when the bytes match, and replaced when they
# do not. Re-running is safe. The file-name database is refreshed afterward.

def install(extra: list[str]) -> None:
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


STAGES = {
    "prereqs": "prereqs.cmd",
    "fetch": fetch,
    "build": build,
    "stage": stage,
    "test": test,
    "install": install,
}
BUILD = ("prereqs", "fetch", "build", "stage")

if __name__ == "__main__":
    run_component("ghostscript", ROOT, STAGES, BUILD, __doc__)
