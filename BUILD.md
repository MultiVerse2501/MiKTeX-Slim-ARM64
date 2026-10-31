# Build

Reproduce the portable zip on Windows 11 on Arm. Run the commands from the project root. They need the network, Visual Studio 2022 with the ARM64 C++ toolset, CMake, Ninja, Python 3.12 or newer, and [MSYS2](https://www.msys2.org/). Set `MSYS2_ROOT` when MSYS2 is not on the system drive. Qt is not used.

Pinned commits and package versions are in [versions.txt](versions.txt).

## Upstream

```bat
fetch-upstream.cmd
```

This reads the `miktex` and `vcpkg` commits from [versions.txt](versions.txt), checks them out, and applies [patches/miktex-arm64.patch](patches/miktex-arm64.patch) when that patch is not already applied. Running it again leaves an existing checkout in place. The patch covers CMake, LuaJIT, pixman, the FNV hash width, the COM builds, and luaffi.

## Libraries

Start a shell with `miktex-env.cmd`, then from `upstream\vcpkg`:

```bat
bootstrap-vcpkg.bat -disableMetrics
vcpkg install icu:arm64-windows boost-locale:arm64-windows-static-md
```

ICU is dynamic (`arm64-windows`). Boost.Locale is static with the dynamic CRT (`arm64-windows-static-md`). The vcpkg CMake toolchain file is not passed. MiKTeX looks up the `libboost_` prefix. From the project root:

```bat
link-boost-libs.cmd
```

That creates a `libboost_` hardlink beside each `boost_*.lib`. Links that already exist are left alone.

## MiKTeX

From the project root, in the same `miktex-env.cmd` shell:

```bat
cmake -S upstream\miktex -B build -G Ninja ^
  -DWITH_UI_MFC=OFF -DWITH_UI_QT=OFF ^
  -DWITH_MIKTEX_DOC=OFF -DWITH_MIKTEX_API_DOC=OFF
cmake --build build -- -k 0
```

A finished tree has one `ninja -n` step left, the git-info stamp. Anything else still listed means the build is not done. `arch-scan.cmd` then prints `NON_ARM64=0` for every top-level `.exe` and `.dll` in `build\sandbox\miktex\bin\arm64`.

## Recipes and the zip

```bat
recipes\build.cmd biber all
recipes\build.cmd ghostscript all
portable\pack-portable.cmd
```

`biber all` fetches, builds, packs, tests, and copies `biber.exe` into the sandbox. `ghostscript all` does the same for `mgs.exe`, `gsdll64.dll`, and the DLL closure. Details are in [recipes/README.md](recipes/README.md).

`portable\pack-portable.cmd` writes `portable\dist\miktex-portable-arm64-v` plus `version` and `miktex-tag` from [versions.txt](versions.txt), for example `miktex-portable-arm64-v0.1-26.5.zip`. `version` is this project's dotted release number. `miktex-tag` has to match the MiKTeX version compiled into `build\include\miktex\Version.h`, and `initexmf --version` has to report it. The zip also contains `version.txt` (`v0.1-26.5`), `LICENSE`, and `NOTICE.md`.

The pack refuses `miktex-console.exe`, `Qt6*.dll`, `*ui-Qt.dll`, `dxcompiler.dll`, and `dxil.dll`. It also omits `miktexsetup.exe`, `miktexsetup_standalone.exe`, and the build-host and unit-test executables that share the sandbox directory with the engines. Those names are listed in [portable/pack-portable.cmd](portable/pack-portable.cmd). The sandbox `biber.exe` must match `recipes\biber\dist\biber.exe`, and every Ghostscript `.exe` and `.dll` in `recipes\ghostscript\dist` must match the sandbox. `biber --version` and `mgs --version` must report the versions in the recipe locks, which must match [versions.txt](versions.txt). The ICU DLLs for the `icu` major in that file are copied from the vcpkg install when the sandbox does not already hold them, and the ARM64 VC++ runtime is copied from the Visual Studio redistributable.
