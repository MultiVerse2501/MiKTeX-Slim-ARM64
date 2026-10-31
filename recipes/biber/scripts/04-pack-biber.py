"""Stage 4: pack the built Biber into one ARM64 exe.

``pp`` freezes ``bin/biber`` with the workspace PAR::Packer, then the pack
repeats until every non-system DLL import is inside the exe. Every embedded
PE must be machine 0xAA64. MSYS2's Perl tree is left unchanged.

    python scripts/04-pack-biber.py

Writes ``dist/biber.exe``, ``dist/binary-manifest.json``, and
``dist/linked-dlls.json``.
"""
from pathlib import Path
import hashlib
import json
import re
import shutil
import struct
import subprocess
import zipfile

from common import CPAN, DIST, LOGS, PREFIX, WORK, perl_env, read_json, read_log, run
from locate import clangarm64, system_root

# llvm-readobj indents "Name:" by two spaces. A single leading space misses it.
IMPORT_NAME = re.compile(r"^\s*Name:\s+(.+\.dll)\s*$", re.M | re.I)

MODULES = [
    "deprecate",
    "Biber::Input::file::bibtex",
    "Biber::Input::file::biblatexml",
    "Biber::Output::dot",
    "Biber::Output::bbl",
    "Biber::Output::bblxml",
    "Biber::Output::bibtex",
    "Biber::Output::biblatexml",
    "Pod::Simple::TranscodeSmart",
    "Pod::Simple::TranscodeDumb",
    "List::MoreUtils::XS",
    "List::SomeUtils::PP",
    "List::MoreUtils::PP",
    "HTTP::Status",
    "HTTP::Date",
    "Encode::",
    "IO::Socket::SSL",
    "IO::String",
    "PerlIO::utf8_strict",
    "File::Find::Rule",
    "Text::CSV_XS",
    "DateTime",
    "Win32::Unicode",
]


def perl_runtime_dll(msys: Path) -> Path:
    found = sorted((msys / "bin").glob("perl5*.dll"))
    if len(found) != 1:
        raise SystemExit(f"expected one perl5*.dll in {msys / 'bin'}, found {[p.name for p in found]}")
    return found[0]


def inspect(path: Path, readobj: Path) -> dict:
    raw = path.read_bytes()
    assert raw[:2] == b"MZ", path
    offset = struct.unpack_from("<I", raw, 0x3C)[0]
    assert raw[offset:offset + 4] == b"PE\0\0", path
    machine = struct.unpack_from("<H", raw, offset + 4)[0]
    assert machine == 0xAA64, f"Not ARM64: {path} machine=0x{machine:04x}"
    text = subprocess.check_output(
        [str(readobj), "--coff-imports", str(path)],
        text=True,
        errors="replace",
    )
    return dict(
        sha256=hashlib.sha256(raw).hexdigest(),
        machine="ARM64 (0xAA64)",
        imports=IMPORT_NAME.findall(text),
    )


def embedded_files(source: Path, perl: Path, env: dict) -> list[tuple[Path, str]]:
    probe = (
        "use JSON::PP qw(encode_json); "
        "print encode_json({map { $_ => $INC{$_} } "
        "qw(Unicode/Collate.pm Mozilla/CA.pm Business/ISBN/Data.pm)});"
    )
    run("biber-module-paths",
        [perl, "-MUnicode::Collate", "-MMozilla::CA", "-MBusiness::ISBN::Data", "-e", probe],
        cwd=source, env=env)
    located = json.loads(read_log("biber-module-paths"))

    files = []
    for name in ("biber-tool.conf", "bcf.xsl"):
        files.append((source / "data" / name, "lib/Biber/" + name))
    for name in ("config.rnc", "config.rng", "bcf.rnc", "bcf.rng"):
        files.append((source / "data" / "schemata" / name, "lib/Biber/" + name))
    files.append((source / "lib" / "Biber" / "LaTeX" / "recode_data.xml",
                  "lib/Biber/LaTeX/recode_data.xml"))
    collate = Path(located["Unicode/Collate.pm"]).with_suffix("")
    for name in ("Locale", "CJK", "allkeys.txt", "keys.txt"):
        files.append((collate / name, "lib/Unicode/Collate/" + name))
    files.append((Path(located["Mozilla/CA.pm"]).with_suffix("") / "cacert.pem",
                  "lib/Mozilla/CA/cacert.pem"))
    files.append((Path(located["Business/ISBN/Data.pm"]).parent / "RangeMessage.xml",
                  "lib/Business/ISBN/RangeMessage.xml"))
    for path, _target in files:
        assert path.exists(), path
    return files


def main() -> None:
    msys = clangarm64()
    perl = msys / "bin" / "perl.exe"
    readobj = msys / "bin" / "llvm-readobj.exe"
    perl_dll = perl_runtime_dll(msys)
    lock = read_json("sources.lock.json")["biber"]
    source = CPAN / lock["extract_dir"]
    if not (source / "bin" / "biber").is_file():
        raise SystemExit(f"missing {source / 'bin' / 'biber'}; run stage 3 first")

    for folder in (LOGS, DIST, WORK / "pe-audit"):
        folder.mkdir(parents=True, exist_ok=True)
    env = perl_env(
        msys=msys,
        extra_perl5lib=f"{source}/blib/lib",
        extras={"PAR_VERBATIM": "1"},
    )

    files = embedded_files(source, perl, env)
    # The packed script must not be named "biber": on a case-insensitive volume
    # that clashes with the Biber library directory.
    main_script = WORK / "biber-main-arm64"
    shutil.copy2(source / "bin" / "biber", main_script)
    exe = DIST / "biber.exe"
    command = [
        perl, PREFIX / "bin" / "pp",
        "--execute", "--xargs=--version",
        "--output=" + str(exe),
        "--cachedeps=" + str(WORK / "scancache"),
    ]
    command += ["--module=" + module for module in MODULES]
    command += ["--addfile=" + str(path) + ";" + target for path, target in files]

    links = {}
    system = system_root() / "System32"
    audit = WORK / "pe-audit"
    for attempt in range(3):
        run(
            "biber-pack-" + str(attempt),
            command + ["--link=" + str(path) for path in links.values()] + [main_script],
            cwd=source, env=env, timeout=1800,
        )
        records = {"biber.exe": inspect(exe, readobj)}
        with zipfile.ZipFile(exe) as bundle:
            for name in bundle.namelist():
                if not name.lower().endswith((".dll", ".exe")):
                    continue
                extracted = audit / Path(name).name
                extracted.write_bytes(bundle.read(name))
                records[name] = inspect(extracted, readobj)
        included = {Path(name).name.lower() for name in records}
        for boot in (PREFIX / "bin" / "parl.exe", perl_dll):
            records["bootstrap/" + boot.name] = inspect(boot, readobj)
        included.add(perl_dll.name.lower())
        pending = [dll for record in records.values() for dll in record["imports"]]
        missing = []
        while pending:
            dll = pending.pop()
            key = dll.lower()
            if key.startswith(("api-ms-win-", "ext-ms-win-")) or (system / dll).is_file():
                continue
            assert not key.startswith(("msys-", "cygwin")), dll
            if key in included:
                continue
            path = msys / "bin" / dll
            assert path.exists(), f"Missing DLL: {dll}"
            if key not in links:
                links[key] = path
                pending.extend(inspect(path, readobj)["imports"])
            missing.append(key)
            included.add(key)
        if not missing:
            (DIST / "binary-manifest.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
            (DIST / "linked-dlls.json").write_text(
                json.dumps({key: path.name for key, path in sorted(links.items())}, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Created {exe.stat().st_size:,}-byte biber.exe; "
                  f"audited {len(records)} ARM64 PE files.", flush=True)
            return
        print(f"pack attempt {attempt}: {len(missing)} DLL(s) still outside the exe", flush=True)
    raise RuntimeError("DLL closure did not converge")


if __name__ == "__main__":
    main()
