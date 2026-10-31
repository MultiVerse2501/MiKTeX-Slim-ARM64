#!/usr/bin/env bash
# Configure and build the pinned Ghostscript as a shared library with clangarm64.
# Follows the MSYS2 CLANGARM64 flags used by abenori/texlive-2026-windows-arm64.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
WINSYS=$(cygpath -u "${SYSTEMROOT:?}")/System32
export PATH="/clangarm64/bin:/usr/bin:${WINSYS}"
export TMPDIR="$ROOT/work/tmp"
mkdir -p "$TMPDIR" "$ROOT/work/logs"
export CC=clang CXX=clang++ CCAUX=clang
export AR=llvm-ar RANLIB=llvm-ranlib STRIP=llvm-strip
export CFLAGS='-O2 -pipe -std=gnu17'
export CXXFLAGS='-O2 -pipe -std=gnu++17'
export MINGW_PREFIX=/clangarm64 MINGW_CHOST=aarch64-w64-mingw32
export MSYSTEM=CLANGARM64
patch_stamp=$(cd "$ROOT/patches" && sha256sum *.patch)
cd "$ROOT/work/source"
if test -f .arm64-patch-stamp && test "$(cat .arm64-patch-stamp)" = "$patch_stamp"; then
    :
elif test -f .arm64-patched && test ! -f .arm64-patch-stamp; then
    printf '%s' "$patch_stamp" > .arm64-patch-stamp
elif test -f .arm64-patched; then
    echo "Ghostscript patches changed. Delete recipes/ghostscript/work/source and run fetch again." >&2
    exit 1
else
    for patchfile in "$ROOT"/patches/*.patch; do
        patch --batch -p1 -i "$patchfile"
    done
    sed -i 's|/usr|/clangarm64/aarch64-w64-mingw32|g' base/all-arch.mak base/unix-aux.mak
    touch .arm64-patched
    printf '%s' "$patch_stamp" > .arm64-patch-stamp
fi
if test ! -f .arm64-prepared; then
    libtoolize --force --copy --install
    autoconf -f -i
    touch .arm64-prepared
fi
if test ! -f .arm64-configured; then
    ./configure --prefix="$(cygpath -m "$ROOT/work/install")" \
      --host=aarch64-w64-mingw32 --target=aarch64-w64-mingw32 --build=aarch64-w64-mingw32 \
      --disable-contrib --enable-fontconfig --disable-dbus \
      --disable-cups --enable-openjpeg --disable-gtk --with-jbig2dec \
      --with-libiconv=gnu --with-libidn --with-libpaper --with-system-libtiff \
      --without-x --with-drivers=ALL --disable-compile-inits \
      2>&1 | tee "$ROOT/work/logs/configure.log"
    touch .arm64-configured
fi
jobs=$(nproc 2>/dev/null || echo 8)
make -j"$jobs" DEVICE_DEVS_EXTRA=soobj/bbox.dev MINGW_WITH_WINLIB_NAMES=0 \
  MINGW_PLATFORM_BITS=64 GS_SONAME_MAJOR=gsdll64.dll so \
  2>&1 | tee "$ROOT/work/logs/build.log"
test -f sobin/gsc.exe
test -f sobin/gsdll64.dll
echo "Ghostscript build complete"
