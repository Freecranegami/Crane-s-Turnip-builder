# Turnip custom builder

Builds the Turnip (Adreno Vulkan) driver from upstream Mesa with our own patches applied on top, and publishes an adrenotools-compatible zip as a GitHub Release.

## How it works

1. CI runs every 6 hours (and on any push touching `patches/`, `build.sh` or `config.env`).
2. It looks up the current upstream Mesa commit. If a release for that commit already exists, scheduled runs stop.
3. Otherwise `build.sh` clones Mesa, applies everything in `patches/` in filename order, cross-compiles with the Android NDK and zips `vulkan.ad07XX.so` + `meta.json`.
4. The zip is attached to a release tagged `mesa-<sha>`.

## Setup

1. Create a GitHub repo and push this folder to it.
2. Settings, Actions, General: allow workflows to have read and write permissions.
3. Add patches to `patches/` (see `patches/README.md`).
4. Run the "Build Turnip" workflow manually once to check it works.

## Local build

    ANDROID_NDK_HOME=/path/to/android-ndk-r27c ./build.sh          # tracks MESA_REF
    ANDROID_NDK_HOME=/path/to/android-ndk-r27c ./build.sh mesa-25.3.0   # a specific ref

Needs: meson, ninja, python3-mako, python3-yaml, glslang, bison, flex, zip, ccache.

## Config

Edit `config.env` to change the upstream repo or ref, Android API level, NDK version and output name.

## Notes

- Patch failures stop the build and name the patch. Rebase it against current Mesa and commit the new version.
- The Meson options in `build.sh` follow Mesa's Android cross-build conventions, but Mesa changes option names over time. If configure fails on a new upstream, that is the first place to look.
- Not yet tested against a real build; the first CI run is the real test.
