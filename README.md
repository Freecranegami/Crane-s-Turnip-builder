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

These target power draw and heat in native Android games while keeping frame rates about the same. Each one has a
switch, so a build can be A/B tested without rebuilding. Set the variables in the environment of the game process
(the same place as `TU_DEBUG`).

| Patch | What it does | Switch | Default |
|---|---|---|---|
| `0001` autotune settles | The bandwidth autotuner reads a GPU samples-passed counter around every render pass. Once a pass's average has had enough updates it measures only 1 in N executions, which saves GPU commands and CPU post-processing | `TU_AUTOTUNE_SETTLE=4..1000`, `TU_AUTOTUNE_RESAMPLE=1..100000` | `24`, `32` (`RESAMPLE=1` = stock) |
| `0002` anisotropy cap | Caps the anisotropic filtering a game requests (games often ask for 16x), which cuts texture-unit work and memory traffic with little visible change on a phone screen | `TU_MAX_ANISOTROPY=1..16` | `8` (`16` = stock) |
| `0003` concurrent binning | Turns on concurrent binning (A7xx) by default: binning of the next render pass overlaps the current one. Upstream keeps it off because it hurts desktop games with many small passes | `TU_DEBUG=nocb` turns it off | on |
| `0004` SYSMEM margin | The autotuner picks SYSMEM (straight to DDR) only when its bandwidth estimate wins by a margin, so near-ties go to on-chip GMEM | `TU_AUTOTUNE_SYSMEM_MARGIN=0..50` | `10` (`0` = stock) |

| `0005` depth store skipping | Games often write their depth buffer to DDR every frame although nothing reads it. The driver watches depth/stencil images that have no reader usage (sampled, storage, input attachment, transfer source, host transfer, external) and that no pass has ever loaded; after 300 stores it stops emitting them. If a pass loads the image later, stores resume at once (one frame of stale depth at worst) | `TU_DS_STORE_SKIP=0..` | `300` (`0` = off) |
| `0006` profile switch | One variable that puts every custom default back to upstream behaviour, for quick A/B tests. The individual switches still override it | `TU_PROFILE=stock` | `mobile` |

| `0007` stats and small-pass knob | `TU_STATS=1` prints a line every 5 s: passes in GMEM and SYSMEM (and how many were forced rather than chosen), and depth stores skipped. `TU_AUTOTUNE_SMALL_RP=<draws>` makes the autotuner's "ignore passes under 5 draws" rule adjustable | `TU_STATS=1`, `TU_AUTOTUNE_SMALL_RP` | off, `5` (unchanged) |
| `0008` parallel pipeline compile | Compiles the pipelines of a single `vkCreateGraphicsPipelines` call on up to 3 threads (the calling thread included), so loading-screen warm-ups finish sooner. Same total CPU work. Skipped for tiny batches, app allocators and early-return-on-failure | `TU_PAR_PIPELINES=<threads>` (0 = off) | `3` (stock profile: off) |

`0004` and `0006` use a helper added by `0001`/`0006`, so keep the series in order.

Build side: `config.env` has `LTO=thin` (default) or `LTO=off`. With `thin` the build tries ThinLTO first and falls back
to a plain build if it fails. The result is recorded in the zip's `meta.json` description.

**Status:** these patches were written against Mesa `main` as of 20 Nov 2026 (commit `3d9907d`) using that exact
source, but they have not been compiled or run on a device yet. The defaults are starting points, not measured values.
To compare, play the same scene for 10-15 minutes and note FPS, temperature and battery drop with the stock settings
(`TU_PROFILE=stock`) against the defaults.

## Config

Edit `config.env` to change the upstream repo or ref, Android API level, NDK version, LTO mode and output name.

## Notes

- Patch failures stop the build and name the patch. Rebase it against current Mesa and commit the new version.
- The Meson options in `build.sh` follow Mesa's Android cross-build conventions, but Mesa changes option names over time. If configure fails on a new upstream, that is the first place to look.
- The build has run once on CI with no patches. The patch series is new, so the first run with it is the real test.
