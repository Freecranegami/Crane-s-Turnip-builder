#!/usr/bin/env bash
# Build Turnip from upstream Mesa + our patches.
# Usage: ANDROID_NDK_HOME=/path/to/ndk ./build.sh [mesa-ref]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/config.env"
REF="${1:-$MESA_REF}"
: "${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME to your NDK path}"

WORK="$ROOT/work"
OUT="$ROOT/out"
rm -rf "$WORK" "$OUT"
mkdir -p "$WORK" "$OUT"

echo "==> Cloning Mesa ($REF)"
git clone --depth 1 --branch "$REF" "$MESA_REPO" "$WORK/mesa" 2>/dev/null \
  || { git clone "$MESA_REPO" "$WORK/mesa"; git -C "$WORK/mesa" checkout "$REF"; }
cd "$WORK/mesa"
MESA_SHA="$(git rev-parse --short HEAD)"
git config user.name  "turnip-ci"
git config user.email "turnip-ci@localhost"

echo "==> Applying patches"
shopt -s nullglob
for p in "$ROOT"/patches/*.patch "$ROOT"/patches/*.diff; do
  echo "   - $(basename "$p")"
  if ! git am --3way "$p" 2>/dev/null; then
    git am --abort 2>/dev/null || true
    git apply --3way --index "$p" || { echo "!! Patch failed: $p"; exit 1; }
  fi
done

echo "==> Writing cross file"
TOOLCHAIN="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin"
cat > "$WORK/cross.txt" <<EOF
[binaries]
ar = '$TOOLCHAIN/llvm-ar'
c = ['ccache', '$TOOLCHAIN/aarch64-linux-android${ANDROID_API}-clang']
cpp = ['ccache', '$TOOLCHAIN/aarch64-linux-android${ANDROID_API}-clang++', '-fno-exceptions', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables', '-static-libstdc++']
c_ld = 'lld'
cpp_ld = 'lld'
strip = '$TOOLCHAIN/llvm-strip'
pkg-config = ['env', 'PKG_CONFIG_LIBDIR=$WORK/pkgconfig', '/usr/bin/pkg-config']

[host_machine]
system = 'android'
cpu_family = 'aarch64'
cpu = 'armv8'
endian = 'little'
EOF
mkdir -p "$WORK/pkgconfig"

echo "==> Configuring"
meson setup "$WORK/build" \
  --cross-file "$WORK/cross.txt" \
  -Dbuildtype=release -Db_lto=false -Dstrip=true \
  -Dplatforms=android -Dplatform-sdk-version="$PLATFORM_SDK_VERSION" \
  -Dandroid-stub=true -Dandroid-libbacktrace=disabled \
  -Dgallium-drivers= -Dvulkan-drivers=freedreno -Dvideo-codecs= \
  -Dvulkan-beta=true -Dfreedreno-kmds=kgsl \
  -Degl=disabled -Dglx=disabled -Dgbm=disabled -Dllvm=disabled \
  -Dvalgrind=disabled -Dlibunwind=disabled -Dzstd=disabled \
  -Dc_args=-w -Dcpp_args=-w

echo "==> Building"
if ! ninja -C "$WORK/build" src/freedreno/vulkan/libvulkan_freedreno.so 2>&1 | tee "$WORK/ninja.log"; then
  echo
  echo "==================== COMPILER ERRORS ===================="
  grep -n -B3 -A8 "error:" "$WORK/ninja.log" | head -150 || true
  echo "========================================================="
  exit 1
fi

echo "==> Packaging (adrenotools format)"
PKG="$WORK/pkg"; mkdir -p "$PKG"
cp "$WORK/build/src/freedreno/vulkan/libvulkan_freedreno.so" "$PKG/vulkan.ad07XX.so"
cat > "$PKG/meta.json" <<EOF
{
  "schemaVersion": 1,
  "name": "$DRIVER_NAME $MESA_SHA",
  "description": "Turnip from Mesa $REF @ $MESA_SHA + custom patches",
  "author": "custom",
  "packageVersion": "1",
  "vendor": "Mesa",
  "driverVersion": "Vulkan 1.3 ($MESA_SHA)",
  "minApi": 28,
  "libraryName": "vulkan.ad07XX.so"
}
EOF
( cd "$PKG" && zip -9 "$OUT/${DRIVER_NAME}-${MESA_SHA}.zip" vulkan.ad07XX.so meta.json )
echo "$MESA_SHA" > "$OUT/mesa_sha.txt"
echo "==> Done: $OUT/${DRIVER_NAME}-${MESA_SHA}.zip"
