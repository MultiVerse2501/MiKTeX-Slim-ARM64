"""Stage 1: download and sha256-verify Biber and the PAR::Packer archives.

Uses the Windows Python on PATH. An archive that already matches its pin is
left in place.
"""
from pathlib import Path
import sys
import urllib.request

from common import DOWNLOADS, read_json, require_python, sha256


def fetch(name: str, url: str, want: str, dest: Path) -> None:
    if dest.exists() and sha256(dest) == want:
        print(f"ok (cached)   {name}")
        return
    print(f"downloading   {name}  <- {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "miktex-slim-arm64-fetch"})
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as out:
        out.write(resp.read())
    got = sha256(dest)
    if got != want:
        dest.unlink(missing_ok=True)
        raise SystemExit(f"SHA256 MISMATCH {name}\n  want {want}\n  got  {got}")
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
