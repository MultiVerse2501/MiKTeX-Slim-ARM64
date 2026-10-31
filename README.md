# MiKTeX Slim: Native Lightweight ARM64 TeX Suite

Unofficial native ARM64 MiKTeX for Windows 11 on Arm. A small core installs the engines, Biber, and Ghostscript. TeX packages download the first time a document needs them. The program you copy to another PC is a portable zip. This is not a release from [MiKTeX.org](https://miktex.org/).

The Qt console and the installer are left out. Pins for MiKTeX, vcpkg, ICU, Boost, Biber, and Ghostscript are in [versions.txt](versions.txt). The ARM64 changes to MiKTeX are [patches/miktex-arm64.patch](patches/miktex-arm64.patch). Reproducing the zip is [BUILD.md](BUILD.md).

The files in this repository are released under the GNU General Public License, version 3 or any later version ([LICENSE](LICENSE)). The Ghostscript patches under `recipes/ghostscript/patches/` stay under the GNU Affero General Public License, version 3. Third-party licenses for the programs in the zip are in [NOTICE.md](NOTICE.md).

## Layout

```
README.md            purpose, layout, and how to run the zip
BUILD.md             how to build the zip
LICENSE              GPL-3.0-or-later for the files in this repository
NOTICE.md            upstream licenses
versions.txt         pinned commits and package versions
miktex-env.cmd       ARM64 Visual Studio, vcpkg, and MSYS2
fetch-upstream.cmd   checks out the pinned MiKTeX and vcpkg commits
link-boost-libs.cmd  libboost_ names for the vcpkg Boost libraries
arch-scan.cmd        checks that sandbox binaries are ARM64
patches/             the ARM64 patch for the pinned MiKTeX commit
recipes/             Biber and Ghostscript, which MiKTeX does not compile
portable/            the pack script and the two launch scripts stored in the zip
```

`upstream/`, `build/`, `recipes/*/work/`, `recipes/*/dist/`, and `portable/dist/` are created by the build and are not stored in git.

## Use

Build the zip with [BUILD.md](BUILD.md), or take the zip from a release. Its name is `miktex-portable-arm64-` plus the MiKTeX version it was built from, currently `miktex-portable-arm64-26.5.zip`. In Explorer, right-click it and choose **Extract All**, into any normal folder. The window shows `miktex-portable.cmd`, `bootstrap-portable.cmd`, `version.txt`, `NOTICE.md`, and `texmfs`. `version.txt` is that same MiKTeX version.

Run `miktex-portable.cmd`.

The first run needs a network connection. It downloads the package list, installs the configuration packages, and builds `pdftex`, `pdflatex`, `xetex`, `xelatex`, `luatex`, and `lualatex`. A command window titled **MiKTeX ARM64** then opens. Its `PATH` is `texmfs\install\miktex\bin\arm64` plus the Windows system directories.

```bat
notepad hello.tex
pdflatex hello.tex
```

```tex
\documentclass{article}
\begin{document}
Hello ARM64.
\end{document}
```

`xelatex`, `lualatex`, `biber`, `mgs`, and `kpsewhich` are on the same `PATH`. A package the document asks for is downloaded the first time it is needed.

Later runs of `miktex-portable.cmd` open the prompt directly, once both `texmfs\install\miktex\config\miktexstartup.ini` and `texmfs\install\miktex\config\bootstrap-complete.txt` exist. If the first run stops before the marker file exists, run `miktex-portable.cmd` again.

Downloaded packages, font maps, and format files stay under `texmfs\config` and `texmfs\data`. Move or copy the whole extracted folder together. The script sets `MIKTEX_COMMONSTARTUPFILE` and `MIKTEX_USERSTARTUPFILE` to this tree, so another MiKTeX install on the same PC does not take over the prompt.

`texify` starts `miktex-bibtex` only. On a biblatex document, run `biber.exe` between LaTeX passes. LuaJIT's interpreter is included and its JIT stays off. LuaTeX still uses Lua 5.3. The programs are unsigned: SmartScreen may warn, and Smart App Control blocks them when that feature is turned on.

## Not included

TeXworks, Yap, and the MFC setup wizard. A hosted `windows-arm64` package set, code signing, and CI. The Xindy Lisp image, the obsolete `biber-ms` fork, Info-ZIP, and LuaMetaTeX.
