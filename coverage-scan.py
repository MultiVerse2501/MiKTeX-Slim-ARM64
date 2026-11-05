"""Check that the ARM64 sandbox covers the official Windows distribution.

Every file the official windows-x64 packages install under
``texmf/miktex/bin/x64`` has to come from somewhere: the CMake build (already
in the sandbox), a recipe install (biber, mgs), the pack step (VC++ runtime,
ICU), or the documented exclusion list. Anything left over is a program this
release would silently lack, and a candidate for a new recipe.

    python coverage-scan.py <package-manifests.ini>
    python coverage-scan.py

Without an argument, the newest manifest under ``portable/dist`` is used; a
portable bootstrap downloads it to
``texmfs/data/miktex/cache/packages/<db>/package-manifests.ini``.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "recipes"))
from _common import miktex_bin, require_python  # noqa: E402

# Supplied by pack-portable.cmd from the Visual Studio redistributable or
# from vcpkg, or resolved by Windows itself at run time. Compared against
# the lowercase payload name.
PACK = [
    (r"^icu(dt|in|io|tu|uc)\d+\.dll$", "ICU is copied from the vcpkg install"),
    (r"^vcruntime140(_1|_threads)?\.dll$", "VC++ runtime is copied from the VS redist"),
    (r"^msvcp140(_\d|_atomic_wait|_codecvt_ids)?\.dll$", "VC++ runtime is copied from the VS redist"),
    (r"^(concrt140|vccorlib140)\.dll$", "VC++ runtime is copied from the VS redist"),
    (r"^mfc140\w*\.dll$", "MFC runtime; the MFC programs are excluded"),
    (r"^mfcm140\w*\.dll$", "MFC runtime; the MFC programs are excluded"),
    (r"^ucrtbase\.dll$", "the Universal CRT comes with Windows"),
    (r"^(api|ext)-ms-win-.*\.dll$", "UCRT API sets come with Windows"),
]

# Programs the release deliberately leaves out. Keep in sync with the
# README "Not included" section.
EXCLUDED = [
    (r"^qt6\w+\.dll$", "the Qt console is excluded"),
    (r"^qwindows\.dll$", "the Qt console is excluded"),
    (r"^qmodernwindowsstyle\.dll$", "the Qt console is excluded"),
    (r"^miktex\d+-(ui|poppler)-qt\.dll$", "the Qt console is excluded"),
    (r"^miktex-console(_admin)?\.exe$", "the Qt console is excluded"),
    (r"^miktex-texworks\.exe$", "TeXworks is excluded"),
    (r"^yap\.exe$", "Yap is excluded"),
    (r"^xindy\.mem$", "the Xindy Lisp engine is excluded"),
    (r"^xindy-lisp\.exe$", "the Xindy Lisp engine is excluded"),
    (r"^miktex-zip\.exe$", "Info-ZIP is excluded"),
    (r"^mgsdll64\.dll$", "this build ships the Ghostscript DLL under its build name gsdll64.dll"),
]

# Built by recipes/ and copied into the sandbox by their install stage.
RECIPES = {
    "biber.exe": "recipes\\biber",
    "mgs.exe": "recipes\\ghostscript",
    "gsdll64.dll": "recipes\\ghostscript",
}


def find_manifest() -> Path | None:
    dist = ROOT / "portable" / "dist"
    hits = sorted(
        dist.glob("*/texmfs/data/miktex/cache/packages/*/package-manifests.ini"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return hits[0] if hits else None


def payloads(manifest: Path) -> dict[str, set[str]]:
    """Lowercase file name -> the packages that ship it under bin/x64."""
    text = manifest.read_text(encoding="utf-8", errors="replace")
    found: dict[str, set[str]] = {}
    package = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            package = line[1:-1]
            continue
        hit = re.search(r"(?i)miktex/bin/x64/(\S+)", line)
        if hit:
            name = hit.group(1).rsplit("/", 1)[-1]
            found.setdefault(name.lower(), set()).add(package)
    return found


def classify(name: str) -> tuple[str, str]:
    for pattern, reason in PACK:
        if re.match(pattern, name):
            return "pack", reason
    for pattern, reason in EXCLUDED:
        if re.match(pattern, name):
            return "excluded", reason
    if name in RECIPES:
        return "recipe", RECIPES[name]
    return "missing", ""


def main() -> int:
    require_python()
    argv = sys.argv[1:]
    manifest = Path(argv[0]) if argv else find_manifest()
    if manifest is None or not manifest.is_file():
        print("coverage-scan: no package manifest was found.")
        print("  Pass the path to package-manifests.ini, or bootstrap the")
        print("  portable tree first; the bootstrap downloads the database")
        print("  under texmfs/data/miktex/cache/packages.")
        return 1
    sandbox = miktex_bin(ROOT)
    have = {path.name.lower() for path in sandbox.iterdir() if path.is_file()}

    shipped = payloads(manifest)
    buckets: dict[str, list[tuple[str, set[str], str]]] = {
        "pack": [], "excluded": [], "recipe": [], "missing": [],
    }
    for name in sorted(shipped):
        if name in have:
            continue
        kind, reason = classify(name)
        buckets[kind].append((name, shipped[name], reason))

    packages = {pkg for sources in shipped.values() for pkg in sources}
    print(f"coverage-scan: {manifest}")
    print(f"  {len(packages)} packages ship {len(shipped)} windows-x64 files")
    for kind in ("recipe", "pack", "excluded"):
        entries = buckets[kind]
        print(f"  {kind}: {len(entries)}")
        for name, sources, reason in entries:
            print(f"    {name} <- {', '.join(sorted(sources))} ({reason})")
    missing = buckets["missing"]
    if missing:
        print(f"  MISSING: {len(missing)}")
        for name, sources, _reason in missing:
            print(f"    {name} <- {', '.join(sorted(sources))}")
    else:
        print("  every windows-x64 payload is built, recipe-provided, pack-supplied, or excluded")
    print(f"SCANNED={len(shipped)} MISSING={len(missing)}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
