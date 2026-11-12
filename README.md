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

    ANDROID_NDK_HOME=/path/to/android-ndk-r29 ./build.sh          # tracks MESA_REF
    ANDROID_NDK_HOME=/path/to/android-ndk-r29 ./build.sh mesa-25.3.0   # a specific ref

Needs: meson, ninja, python3-mako, python3-yaml, glslang, bison, flex, zip, ccache.

## Included patches (applied to every build)

These target power draw and heat in native Android games. Each one has a switch, so a build can be A/B tested without
rebuilding. Set the variables in the environment of the game process (the same place as `TU_DEBUG`).

| Patch | What it does | Switch | Default |
|---|---|---|---|
| `0001` autotune GMEM bias | Counts SYSMEM (straight-to-DDR) rendering as more expensive, so near-ties go to on-chip tiled rendering (GMEM) | `TU_AUTOTUNE_SYSMEM_PENALTY=50..400` | `125` (`100` = stock) |
| `0002` sparse sampling | After a render pass's average has settled, collects the per-pass pixel counter for 1 in N instances instead of all | `TU_AUTOTUNE_RESAMPLE_PERIOD=1..1024` | `16` (`1` = stock) |
| `0003` UBWC diagnostics | `TU_DEBUG=perf` logs large color attachments that ended up uncompressed; `TU_DEBUG=startup` logs the kernel's UBWC version | `TU_DEBUG=perf` / `startup` | log only, no behaviour change |
| `0004` GPU frequency hint | Asks KGSL to hold the GPU at a percentage of its maximum clock. Experimental, the kernel may ignore it | `TU_KGSL_PWR_PERCENT=2..100` | off |

Build side: `config.env` has `LTO=thin` (default) or `LTO=off`. With `thin` the build tries ThinLTO first and falls back
to a plain build if it fails. The result is recorded in the zip's `meta.json` description.

**Status:** the defaults (`125`, `16`) are starting points, not measured values. The patches were checked against Mesa
`main` as of May 2026 and have not been run on a device yet. To compare, play the same scene for 10-15 minutes and note
FPS, temperature and battery drop with `TU_AUTOTUNE_SYSMEM_PENALTY=100 TU_AUTOTUNE_RESAMPLE_PERIOD=1` (stock behaviour)
against the defaults.

## Config

Edit `config.env` to change the upstream repo or ref, Android API level, NDK version, LTO mode and output name.

## Notes

- Patch failures stop the build and name the patch. Rebase it against current Mesa and commit the new version.
- The Meson options in `build.sh` follow Mesa's Android cross-build conventions, but Mesa changes option names over time. If configure fails on a new upstream, that is the first place to look.
- The build has run once on CI with no patches. The patch series is new, so the first run with it is the real test.
