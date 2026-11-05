"""Stage 1: download and sha256-verify Biber and the PAR::Packer archives.

Uses the Windows Python on PATH. An archive that already matches its pin is
left in place.
"""
from pathlib import Path
import sys

from common import DOWNLOADS, download, read_json, require_python, sha256


def fetch(name: str, url: str, want: str, dest: Path) -> None:
    if dest.exists() and sha256(dest) == want:
        print(f"ok (cached)   {name}")
        return
    print(f"downloading   {name}  <- {url}")
    download(url, dest, want)
    print(f"verified      {name}")


def main() -> int:
    require_python()
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    biber = read_json("sources.lock.json")["biber"]
    if biber["extract_dir"] != "biber-" + biber["version"]:
        raise SystemExit(f"extract_dir {biber['extract_dir']} does not match version {biber['version']}")
    fetch(biber["archive"], biber["url"], biber["sha256"], DOWNLOADS / biber["archive"])

    cpan = read_json("cpan-sources.json")
    for name in cpan["_order"]:
        spec = cpan[name]
        fetch(name, spec["url"], spec["sha256"], DOWNLOADS / (name + ".tar.gz"))

    print("\nAll sources present and verified in", DOWNLOADS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
