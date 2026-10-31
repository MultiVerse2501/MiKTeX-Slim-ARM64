# Ghostscript 10.08.0

Builds a native `mgs.exe` so `miktex-rungs.exe` has an interpreter to run. The official package `miktex-ghostscript-bin-x64` is Ghostscript 9.25 and is tagged `windows-x64`, so this suite does not install it.

The configure line and the shared-library make flags follow [abenori/texlive-2026-windows-arm64](https://github.com/abenori/texlive-2026-windows-arm64). That recipe installs `gswin64c.exe` for TeX Live. This one installs `mgs.exe`, the name `MIKTEX_GS_EXE` looks up. The DLL stays `gsdll64.dll`. Patches in `patches/` are the MSYS2 `mingw-w64-ghostscript` files pinned in `sources.lock.json`. `001-mingw-build.patch` keeps the `$(LDFLAGSAUX)` terms Ghostscript 10.08.0 uses on the mkromfs link lines.

## Layout

| Stage | Script | Result |
|---|---|---|
| `prereqs` | `scripts/00-prereqs.cmd` | clangarm64 compiler, GNU make, and the Ghostscript libraries |
| `fetch` | `scripts/01-fetch.py` | Hash-checked tarball in `work/downloads`, sources in `work/source` |
| `build` | `scripts/02-build.py` | `work/source/sobin/gsc.exe` and `gsdll64.dll` |
| `stage` | `scripts/03-stage.py` | `dist/mgs.exe`, `dist/gsdll64.dll`, and the DLL closure, all machine `0xAA64` |
| `test` | `scripts/04-test.py` | `--version` is 10.08.0 and a small PostScript file becomes a PDF |
| `install` | `scripts/05-install.py` | Those files copied into the MiKTeX bin, then the file-name database is refreshed |

`work/` and `dist/` are created by the scripts and are not stored in git. Fetch records the tarball and patch hashes in `work/source/.extracted`. A different pin replaces that tree. An existing tree built before the stamp is kept and stamped, not rebuilt.

## Build

From this directory, or `build.cmd ghostscript` from `recipes`:

```bat
build.cmd
build.cmd all
```

`build.cmd` stops after `stage`. `all` continues through `install`. Set `MSYS2_ROOT` when MSYS2 is not on the system drive. `test` and `install` need the extracted source (`GS_LIB`). Install also needs the MiKTeX bin at `build/sandbox/miktex/bin/arm64`, or `MIKTEX_BIN`. The test keeps MSYS2 off `PATH`.

Bundled copies of expat, freetype, jbig2dec, jpeg, libpng, openjpeg, tiff, zlib, tesseract, and leptonica are not extracted. The build links the MSYS2 packages. OCR stays out.
