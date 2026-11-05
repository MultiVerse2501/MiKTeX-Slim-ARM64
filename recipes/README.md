# Recipes

Biber and Ghostscript are not CMake targets in MiKTeX. Official Windows ships them as `windows-x64` packages, which this ARM64 suite does not install. Each recipe below builds the program and copies it into `build/sandbox/miktex/bin/arm64`.

| Directory | Result |
|---|---|
| [biber/](biber/README.md) | One packed `biber.exe` (Biber 2.22) |
| [ghostscript/](ghostscript/README.md) | `mgs.exe`, `gsdll64.dll`, and the DLL closure (Ghostscript 10.08.0) |

Attribution is in [NOTICE.md](../NOTICE.md). The MiKTeX build in [BUILD.md](../BUILD.md) has to be finished before `all`, because the test and install stages look for `build/sandbox/miktex/bin/arm64` (or `MIKTEX_BIN`).

## Build

From this directory. Set `MSYS2_ROOT` when MSYS2 is not on the system drive.

```bat
build.cmd biber all
build.cmd ghostscript all
```

`biber` or `ghostscript` with no further argument stops once the program is staged under that recipe's `dist\`. `all` continues with the test and the copy into the MiKTeX bin. Each directory also has its own `build.cmd`.

MiKTeX resolves Ghostscript as `mgs.exe`. The shared library keeps the name Ghostscript 10.08.0 links, `gsdll64.dll`, plus the clangarm64 DLLs that library imports. PostScript library files (`gs_init.ps` and the rest) stay the architecture-neutral `ghostscript` package, under `texmf/ghostscript/base`. The recipe test points `GS_LIB` at the extracted source tree.

## Adding a component

A component is a directory under `recipes/` with its own `build.py` — a stage table plus one `run_component(...)` call from `_common.py` (see `biber/build.py`) — a one-line `build.cmd`, and stage scripts under `scripts/`. List it in `COMPONENTS` in [build.py](build.py). The shared plumbing lives in `_common.py`: pinned-source downloads and SHA-256 checks, MSYS2 and MiKTeX tool discovery, ARM64 PE checks, and the stage dispatcher. A `.cmd` stage runs through cmd; a `.py` stage is loaded and called as `main()` with any extra arguments in `sys.argv`. A new component writes only what makes it different.
