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

# Explain why a patch no longer applies: the rejected hunks plus the current upstream code around them.
explain_patch_failure() {
  local p="$1" rej f start
  echo
  echo "==================== PATCH FAILURE: $(basename "$p") ===================="
  git apply --reject --whitespace=nowarn "$p" 2>&1 | head -40 || true
  for rej in $(git ls-files --others --exclude-standard | grep '\.rej$' || true); do
    f="${rej%.rej}"
    echo "---- rejected hunks ($rej):"
    cat "$rej"
    for start in $(grep -o '^@@ -[0-9]*' "$rej" | tr -d '@ -'); do
      echo "---- current upstream $f, lines $((start > 40 ? start - 40 : 1)) onwards:"
      sed -n "$((start > 40 ? start - 40 : 1)),$((start + 140))p" "$f"
    done
  done
  echo "======================================================================="
  git checkout -q -- . 2>/dev/null || true
  git clean -fdq 2>/dev/null || true
}

echo "==> Applying patches"
shopt -s nullglob
FAILED_PATCHES=()
for p in "$ROOT"/patches/*.patch "$ROOT"/patches/*.diff; do
  echo "   - $(basename "$p")"
  if ! git am --3way "$p" >/dev/null 2>&1; then
    git am --abort 2>/dev/null || true
    if ! git apply --3way --index "$p" >/dev/null 2>&1; then
      FAILED_PATCHES+=("$(basename "$p")")
      explain_patch_failure "$p"
    fi
  fi
done
if [ "${#FAILED_PATCHES[@]}" -gt 0 ]; then
  echo "!! Patches that no longer apply: ${FAILED_PATCHES[*]}"
  exit 1
fi

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

# Configure and build once. $1 = thin (ThinLTO) or off. Returns non-zero on any failure, so the caller can fall back.
build_driver() {
  local lto_mode="$1"
  local lto_args=(-Db_lto=false)
  if [ "$lto_mode" = "thin" ]; then
    lto_args=(-Db_lto=true -Db_lto_mode=thin)
  fi

  rm -rf "$WORK/build"
  echo "==> Configuring (LTO: $lto_mode)"
  meson setup "$WORK/build" \
    --cross-file "$WORK/cross.txt" \
    -Dbuildtype=release "${lto_args[@]}" -Dstrip=true \
    -Dplatforms=android -Dplatform-sdk-version="$PLATFORM_SDK_VERSION" \
    -Dandroid-stub=true -Dandroid-libbacktrace=disabled \
    -Dgallium-drivers= -Dvulkan-drivers=freedreno -Dvideo-codecs= \
    -Dvulkan-beta=true -Dfreedreno-kmds=kgsl \
    -Degl=disabled -Dglx=disabled -Dgbm=disabled -Dllvm=disabled \
    -Dvalgrind=disabled -Dlibunwind=disabled -Dzstd=disabled \
    -Dc_args=-w -Dcpp_args=-w 2>&1 | tee "$WORK/meson-$lto_mode.log"
  [ "${PIPESTATUS[0]}" -eq 0 ] || return 1

  echo "==> Building (LTO: $lto_mode)"
  ninja -C "$WORK/build" src/freedreno/vulkan/libvulkan_freedreno.so 2>&1 | tee "$WORK/ninja-$lto_mode.log"
  [ "${PIPESTATUS[0]}" -eq 0 ] || return 1
}

print_errors() {
  echo
  echo "==================== COMPILER ERRORS ($1) ===================="
  grep -n -B3 -A8 -e "error:" -e "ERROR:" "$WORK/ninja-$1.log" "$WORK/meson-$1.log" 2>/dev/null | head -150 || true
  echo "========================================================="
}

# ThinLTO trims the driver's CPU-side overhead a little. It is the least tested part of the build, so if it fails for
# any reason (a new upstream, a toolchain quirk) report why and fall back to the plain build instead of losing the release.
LTO_USED="off"
if [ "${LTO:-thin}" = "thin" ]; then
  if build_driver thin; then
    LTO_USED="thin"
  else
    print_errors thin
    echo "!! ThinLTO build failed, retrying without LTO"
  fi
fi
if [ "$LTO_USED" = "off" ]; then
  if ! build_driver off; then
    print_errors off
    exit 1
  fi
fi

echo "==> Packaging (adrenotools format)"
PKG="$WORK/pkg"; mkdir -p "$PKG"
cp "$WORK/build/src/freedreno/vulkan/libvulkan_freedreno.so" "$PKG/vulkan.ad07XX.so"
cat > "$PKG/meta.json" <<EOF
{
  "schemaVersion": 1,
  "name": "$DRIVER_NAME $MESA_SHA",
  "description": "Turnip from Mesa $REF @ $MESA_SHA + custom patches (LTO: $LTO_USED)",
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
