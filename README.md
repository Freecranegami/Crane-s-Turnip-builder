# Crane's Turnip builder

Automated builds of **Turnip**, the open-source Mesa Vulkan driver for Qualcomm Adreno GPUs, with a small set of
patches aimed at **lower power draw and heat in native Android games** while keeping frame rates about the same.

Releases are zips in the [libadrenotools](https://github.com/bylaws/libadrenotools) driver format
(`vulkan.ad07XX.so` + `meta.json`), so they work with apps that load custom Adreno drivers, such as
[Epinephro](https://github.com/Freecranegami/Epinephro). The app loads the driver itself, so no root and no
system changes are needed.

> **Status: experimental.** The patch series has not been verified on a device yet, and the defaults are starting
> points, not measured values. If something misbehaves, set `TU_PROFILE=stock` to get upstream behaviour back and
> please open an issue with the details.

## Install

1. Download the newest zip from the [Releases](../../releases) page (tagged `mesa-<commit>`).
2. Import it in an app that supports custom Adreno drivers (in Epinephro: Vulkan driver, Import).
3. Select it and start your game. Pick another driver again if the game fails to start.

Targets Adreno GPUs that upstream Mesa supports (built with Android API 34). Some patches only apply to A7xx; see the
table.

## What is different from upstream

Each change has an environment variable, so a build can be A/B tested without rebuilding. Set the variables in the
environment of the game process (the same place you would put `TU_DEBUG`).

| Patch | What it does | Switch | Default |
|---|---|---|---|
| `0001` autotune settles | The bandwidth autotuner reads a GPU samples-passed counter around every render pass. Once a pass's average has had enough updates it measures only 1 in N executions, which saves GPU commands and CPU post-processing | `TU_AUTOTUNE_SETTLE=4..1000`, `TU_AUTOTUNE_RESAMPLE=1..100000` | `24`, `32` (`RESAMPLE=1` = stock) |
| `0002` anisotropy cap | Caps the anisotropic filtering a game requests (games often ask for 16x), which cuts texture-unit work and memory traffic with little visible change on a phone screen | `TU_MAX_ANISOTROPY=1..16` | `8` (`16` = stock) |
| `0003` concurrent binning | Turns on concurrent binning (A7xx) by default: binning of the next render pass overlaps the current one. Upstream keeps it off because it hurts desktop games with many small passes | `TU_DEBUG=nocb` turns it off | on |
| `0004` SYSMEM margin | The autotuner picks SYSMEM (straight to DDR) only when its bandwidth estimate wins by a margin, so near-ties go to on-chip GMEM | `TU_AUTOTUNE_SYSMEM_MARGIN=0..50` | `30` (`0` = stock) |
| `0005` depth store skipping | Games often write their depth buffer to DDR every frame although nothing reads it. The driver watches depth/stencil images that have no reader usage (sampled, storage, input attachment, transfer source, host transfer, external) and that no pass has ever loaded; after 300 stores it stops emitting them. If a pass loads the image later, stores resume at once (one frame of stale depth at worst) | `TU_DS_STORE_SKIP=0..` | `300` (`0` = off) |
| `0006` profile switch | One variable that puts every custom default back to upstream behaviour, for quick A/B tests. The individual switches still override it | `TU_PROFILE=stock` | `mobile` |
| `0007` stats and small-pass knob | `TU_STATS=1` prints a line every 5 s: passes in GMEM and SYSMEM (and how many were forced rather than chosen), and depth stores skipped. `TU_AUTOTUNE_SMALL_RP=<draws>` makes the autotuner's "ignore passes under 5 draws" rule adjustable | `TU_STATS=1`, `TU_AUTOTUNE_SMALL_RP` | off, `5` (unchanged) |
| `0008` parallel pipeline compile | Compiles the pipelines of a single `vkCreateGraphicsPipelines` call on up to 3 threads (the calling thread included), so loading-screen warm-ups finish sooner. Same total CPU work. Skipped for tiny batches, app allocators and early-return-on-failure | `TU_PAR_PIPELINES=<threads>` (0 = off) | `3` (stock profile: off) |
| `0009` GPU clock hold | Opt-in: asks the KGSL power controller to hold the GPU at a percentage of its maximum clock while a queue has work (the control Android perf hints use). The kernel may ignore it; the result is logged once per queue | `TU_GPU_PERC=2..100` | off (`0`) |

`TU_PROFILE=stock` puts every default above back to upstream behaviour in one go; the individual switches still
override it. `TU_DEBUG=startup` prints which profile is active.

### Comparing with stock

Play the same scene for 10-15 minutes with `TU_PROFILE=stock`, then with the defaults, and note FPS, temperature and
battery drop. `TU_STATS=1` adds a line every 5 seconds with how many render passes went to GMEM or SYSMEM.

## How the builds are made

1. CI runs every 6 hours (and on pushes that touch `patches/`, `build.sh` or `config.env`).
2. It looks up the current upstream Mesa commit. If a release for that commit already exists, scheduled runs stop.
3. Otherwise `build.sh` clones Mesa, applies everything in `patches/` in filename order, cross-compiles with the
   Android NDK and zips the driver with a `meta.json`.
4. The zip is attached to a release tagged `mesa-<sha>`.

You can also run the "Build Turnip" workflow by hand and give it a Mesa branch or tag (`mesa_ref`).

### Build locally

    ANDROID_NDK_HOME=/path/to/android-ndk-r29 ./build.sh               # tracks MESA_REF
    ANDROID_NDK_HOME=/path/to/android-ndk-r29 ./build.sh mesa-25.3.0    # a specific ref

Needs: meson, ninja, python3-mako, python3-yaml, glslang, bison, flex, zip, ccache. `config.env` sets the upstream
repo and ref, Android API level, NDK version, LTO mode (`thin` or `off`) and the output name.

## Contributing

Patches live in `patches/` and are applied in filename order (see `patches/README.md` for how to make one). When
upstream moves and a patch stops applying, the CI build fails and prints the rejected hunks next to the current
upstream code. Rebase the patch, keep its number prefix and open a pull request. Measurements from real devices
(driver, game, settings, FPS, temperature, battery) are the most useful contribution.

`0004` and `0006` use a helper added by `0001`/`0006`, so keep the series in order.

## Licence

This repository (build scripts, workflow and patches) is released under the [MIT licence](LICENSE). Turnip is part of
[Mesa](https://www.mesa3d.org/), which is MIT-licensed with some files under other permissive licences; see Mesa's
`docs/license.rst`. Built drivers contain Mesa code, so keep the Mesa licence notice when you redistribute them.
Not affiliated with Mesa, Qualcomm or Google.
