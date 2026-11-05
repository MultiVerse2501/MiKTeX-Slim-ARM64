# Biber 2.22

Builds one ARM64 `biber.exe` for MiKTeX Slim, so `biblatex` with `backend=biber` runs on Windows on Arm.

Biber is a Perl application. The architecture-specific part is its XS modules (`Text::BibTeX` / btparse, `XML::LibXML`, `Unicode::LineBreak`, `DateTime`). MSYS2's `clangarm64` repository ships that stack as `mingw-w64-clang-aarch64-biber`. This recipe installs those modules, builds PAR::Packer into a private prefix, builds Biber 2.22 from the tag in `sources.lock.json`, and freezes one executable. MSYS2's own Perl tree is left unchanged.

The approach follows [abenori/texlive-2026-windows-arm64](https://github.com/abenori/texlive-2026-windows-arm64), retargeted from TeX Live to MiKTeX.

## Layout

| Path | What it is |
|---|---|
| `sources.lock.json` | Pinned Biber tarball |
| `cpan-sources.json` | Pinned PAR::Packer toolchain, in build order |
| `prereqs.cmd` | Installs the MSYS2 ARM64 compiler, Perl, and the module stack |
| `build.py` | Every stage: fetch, support, biber, pack, test, install |
| `work/`, `dist/` | Created by the stages. Not stored in git. |

## Build

From this directory, or `build.cmd biber` from `recipes`. Requirements are Windows on Arm, [MSYS2](https://www.msys2.org/) with working `pacman`, and Python 3.12 or newer. Set `MSYS2_ROOT` when MSYS2 is not on the system drive. The prereqs stage installs `clang`, `make`, `perl`, and the module stack (about 340 MB the first time).

```bat
build.cmd
build.cmd all
```

`build.cmd` runs prereqs, fetch, support, biber, and pack, and leaves `dist\biber.exe`. `all` continues with the biblatex test and the copy into `build/sandbox/miktex/bin/arm64`. Set `MIKTEX_BIN` when that directory is somewhere else. The test looks for `miktex-pdflatex.exe` there.

The pack stage requires machine `0xAA64` on every embedded PE. The test stage checks `--version`, a path with spaces and Japanese characters, a `PERL5OPT` that must not change the `.bbl`, a UTF-8 biblatex run (Knuth sorts before Müller), and `--tool`. `python build.py test --installed` repeats the document run with the `biber.exe` on the MiKTeX `PATH`.

The Biber tag and the CPAN archives are pinned. The MSYS2 packages are not. An extract whose stamp does not match the pin is replaced on the next build.

## Known test exceptions

PAR::Packer 1.064 may fail `t/20-pp.t` and `t/30-current_exec.t`. Archive-Zip may fail `t/24_unicode_win32.t` while creating a filename that contains `€` under the C locale. Those names are an allowlist. Any other failing test stops the build. The packed executable still has to pass the test stage.
