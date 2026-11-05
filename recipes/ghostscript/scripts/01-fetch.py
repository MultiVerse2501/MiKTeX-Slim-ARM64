"""Download the pinned Ghostscript, check the vendored patches, and extract sources.

Bundled third-party libraries listed in sources.lock.json are left out of the
working tree. The build links the MSYS2 copies instead. work/source/.extracted
records the archive and patch hashes. A different pin replaces that tree.
"""
from pathlib import Path
import shutil
import tarfile

from locate import ROOT, fetch, read_json, require_python, sha256

WORK = ROOT / "work"
DOWNLOADS = WORK / "downloads"
SOURCE = WORK / "source"


def extract_stamp(gs: dict, patches: dict) -> str:
    lines = [f"archive {gs['sha256']}", f"extract {gs['extract_dir']}"]
    for name in sorted(patches):
        lines.append(f"patch {name} {patches[name]}")
    return "\n".join(lines) + "\n"


def main() -> None:
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
        fetch(gs["url"], archive)
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


if __name__ == "__main__":
    main()
