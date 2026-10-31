# Notices

MiKTeX Slim is an unofficial native ARM64 build of MiKTeX. It is not a release from [MiKTeX.org](https://miktex.org/). The files written for this repository, including `patches/miktex-arm64.patch`, are under the GNU General Public License, version 3 or any later version (`LICENSE`). MiKTeX is a collection of independently licensed packages. The upstream copying conditions are `COPYING.md` in the MiKTeX source. This project does not vendor that source. The ARM64 changes are `patches/miktex-arm64.patch`, applied to the MiKTeX commit in [versions.txt](versions.txt).

Biber and the PAR::Packer toolchain keep the upstream licenses recorded in their source archives. The packed `biber.exe` embeds that Perl runtime.

Ghostscript is Copyright Artifex Software, Inc., under the GNU Affero General Public License, version 3. The 10.08.0 tarball is pinned in `recipes/ghostscript/sources.lock.json`.

The four files in `recipes/ghostscript/patches/` are the MSYS2 `mingw-w64-ghostscript` patches `001`, `002`, `003`, and `005`, with the SHA-256 values recorded in that lock. They come from <https://github.com/msys2/MINGW-packages/tree/master/mingw-w64-ghostscript>. `001-mingw-build.patch` keeps the `$(LDFLAGSAUX)` terms Ghostscript 10.08.0 uses on the mkromfs link lines.

The Ghostscript configure line and the shared-library make flags follow <https://github.com/abenori/texlive-2026-windows-arm64>, retargeted so the program MiKTeX looks up is `mgs.exe`.

The Biber pack follows the same TeX Live ARM64 recipe, retargeted so the packed executable is installed beside the MiKTeX engines.
