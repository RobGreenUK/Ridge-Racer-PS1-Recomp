# Contributor and AI agent guide

Start at the [technical overview](TECHNICAL_OVERVIEW.md), then read the relevant
source and tests. This guide applies equally to human contributors and coding
agents. The repository contains the implementation knowledge needed to begin;
private development records are not prerequisites.

## Working boundaries

- Target the supported USA revision. Verify addresses, callers, units and model
  classifications against the user's executable before extending support.
- Preserve original physics, simulation timing, input semantics, audio, saves and
  replay. Rendering FPS is a presentation setting.
- Keep generated C disposable. Durable changes belong in source hooks, generation
  configuration, extraction tools or explicit upstream patches.
- Keep render/callback/transport work bounded. Avoid blocking I/O, synchronous GPU
  waits or new per-triangle allocations in hot paths without measured justification.
- Preserve settings and saves. Use isolated capture sessions and clean up only
  processes owned by the test or launcher.
- Keep game content, generated code and diagnostic captures out of source commits,
  pull requests and CI artifacts. Describe reproduction steps and results in prose.
- Check submodule changes separately. Record required changes as patches against
  the pinned revision; do not silently update dependencies.

## Source map

| Area | Maintained entry points |
|---|---|
| Build and generation | [CMakeLists.txt](../CMakeLists.txt), [game.toml](../game.toml), [scripts](../scripts) |
| Symbol naming and guest addresses | [symbols.toml](../symbols.toml), [sync_symbols.py](../tools/sync_symbols.py), [usa_layout.h](../src/scene/usa_layout.h) |
| Runtime state capture | [live.c](../src/scene/live.c), [models.c](../src/scene/models.c), [capture.c](../src/scene/capture.c) |
| IPC and sample assembly | [platform helpers](../src/platform), [live_protocol.h](../src/scene/live_protocol.h), [live_client.h](../src/scene/live_client.h) |
| Interpolation | [timeline.h](../src/scene/timeline.h), [presentation_timeline.h](../src/scene/presentation_timeline.h) |
| World rendering | [preview.cpp](../src/scene/preview.cpp), [mesh.h](../src/scene/mesh.h), [depth_renderer.h](../src/scene/depth_renderer.h) |
| Title flag geometry | [menu_flag.h](../src/scene/menu_flag.h), [menu/HUD capture](../src/scene/hud.c) |
| Original screens, sky and HUD | [screen_client.h](../src/scene/screen_client.h), [sky_renderer.h](../src/scene/sky_renderer.h), [hud_renderer.h](../src/scene/hud_renderer.h) |
| Launchers and settings | [launcher](../launcher), [preloaded mod](../mods/preloaded/packages/ridge.presentation/1.0.0/manifest.toml) |
| Extraction and diagnostics | [tools](../tools), [tests](../tests) |

`psx_symbols.h` is generated from the symbol definitions. Use its synchronization
tool instead of maintaining two different address maps by hand.

## Build and launch identity

Follow the [Mac](BUILD_MACOS.md) or [Windows](BUILD_WINDOWS.md) guide for first
builds. On a configured Mac checkout, useful incremental commands are:

```sh
. scripts/macos-env.sh
sh scripts/build-scene-preview.sh
sh scripts/build-pacing-test.sh
sh scripts/build-launcher-macos.sh
cmake --build build-macos --target psx-runtime -j 8
```

Choose only the commands needed by the change. Regenerate/reconfigure when
changing generation inputs or CMake. Asset preparation rebuilds the ordinary Mac
viewer and may run an isolated capture; it is more than a file-copy step.

`RidgeScenePreview` is the ordinary viewer. `RidgeScenePacingTest` is the separate
Mac phase-trial viewer. The app normally selects the former; the pacing launcher
selects the latter. `dist/` outputs are copies made at packaging time and are not
updated merely by recompiling `build-macos/` or `build-windows/`. Record the actual
executable path and hash when comparing behaviour.

## Tests and evidence

On Mac, source the environment before Python commands. For launcher changes:

```sh
. scripts/macos-env.sh
python3 -m unittest discover -s tests -p 'test_launcher.py' -v
python3 -m unittest discover -s tests -p 'test_native_scene_launch.py' -v
```

For broader changes, the project suite is:

```sh
python3 -m unittest discover -s tests -v
```

Several tests compile C/C++ harnesses, and some create real OpenGL contexts.
The suite includes Mac-specific assumptions; it is not a claim of a portable,
headless Windows test runner. A missing dependency, skipped test or unavailable
display is not evidence that rendering passed.

Choose verification that exercises the changed boundary:

| Change | Relevant test areas and additional evidence |
|---|---|
| Protocol or delivery | `test_scene_live.py`, `test_scene_delivery.py`, `test_scene_transition_delivery.py`; check sequence gaps and incomplete frames |
| Timeline or cuts | `test_presentation_timeline.py`, `test_scene_timeline.py`, transition tests; compare continuous driving and discrete camera/state changes |
| Depth, contact or mirrors | `test_scene_depth.py`, `test_scene_car_contact.py`, shadow/mirror tests; real GL and matched scene/VRAM comparisons |
| HUD or original screens | HUD/layout/screen tests and `test_gl_readback_macos.py`; check startup interaction, menus, race and replay |
| Visibility | `test_distant_cars.py`, `test_scenery_eval.py`; verify read-only guest state and bounded output |
| Pacing or diagnostics | `test_display_pacer.py`, `test_frame_metrics.py`, `test_async_metrics.py`; live timing and display evidence |
| Build or packaging | Fresh clone, recursive submodules, own disc, no pre-existing generated assets; startup and save persistence on the target OS |

Use `tools/run_scene_validation.py --help` for isolated captures and the analysis
tools' `--help` for supported options. Keep a scene sample with its matching VRAM
and metadata. Comparing different interpolation times or palettes can look like a
renderer regression even when the code is unchanged.

For performance comparisons record executable hash, settings, OS/GPU, display Hz,
render target, course, camera, mirror state and capture conditions. Separate
focused gameplay from menus, transitions, pauses and diagnostic capture stalls.
Check sample age and held frames as well as CPU/GPU timings. Do not infer physical
scanout from a loop timer alone.

State the evidence level explicitly: successful compilation, synthetic regression,
real-GL comparison, live smoke test and full gameplay test answer different
questions. Native Windows validation requires running the Windows-native workflow;
a cross-build does not substitute for it.

## Branch, review and merge

1. Inspect `git status --short` and `git submodule status`; preserve unrelated edits.
   Start a focused branch from current `main` (coding agents use `codex/` names).
2. Implement a bounded change. Update the relevant public documentation and tests
   when a contract changes. Avoid unrelated formatting or dependency updates.
3. Run focused checks, inspect the complete diff and stage explicit paths.
4. Run `git diff --cached --check` and `python3 tools/audit_source.py`.
   The audit checks the index and reachable root history. New public document
   paths must be explicitly reviewed and added to its document allowlist; do not
   broaden it to admit arbitrary private documentation.
5. Push the branch and open a pull request explaining the problem, final behaviour,
   validation and remaining platform limits. Never attach disc data or captures
   containing game assets. Ask for another contributor's review when available;
   do not describe self-review as independent approval.
6. Address review findings and required checks, then merge through GitHub. A squash
   merge gives a focused change one commit on `main`. Do not bypass branch rules
   or rewrite published `main` history. Verify the merged revision and remove the
   completed branch.

For an agent handoff, report changed files, build/launch identity, checks actually
run and unresolved questions. Keep explanations factual and reproducible so a
human or another agent can continue from the repository itself.

## Controller protocol compatibility

Keep `[controller] default_mode = "digital"` and `lock_mode = true` in
`game.toml`. The original pad decoder accepts digital ID `0x41` and neGcon ID
`0x23`, but rejects DualShock ID `0x73`. A modern host gamepad is not evidence
that the original game understands DualShock emulation. The runtime's digital
mode maps its buttons and left-stick directions to the supported wire format.

The SDK applies the game lock after saved settings, again on advanced-launcher
return, and disables analogue multitap overrides for a digital-locked title.
This preserves device assignment and mappings while correcting stale analogue
settings. Do not replace that with a one-time preference edit or change the guest
input decoder. The viewer's keyboard bridge and the companion's controller path
must both reach a supported pad type, including before the main game has loaded.

An isolated SIO-level regression with saved analogue mode confirmed that Start
arrived as `0073f7ff80808080` and was rejected before the lock; with the lock the
packet was `0041f7ff` and the original decoder accepted Start. These are protocol
observations, not copyrighted fixtures. Physical controller connection, custom
bindings and hotplug still require device-specific playtesting.
