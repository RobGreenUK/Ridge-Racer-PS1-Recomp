# Technical documentation

This documentation explains the implementation for contributors, maintainers and
AI coding agents. It describes the source in this repository and the reasoning
behind its main boundaries. It is intended to make the techniques reusable without
requiring private captures, game assets or a development conversation.

## Reading order

1. [Architecture and build pipeline](ARCHITECTURE.md): how the original runtime,
   enhanced renderer, local asset generation and launchers fit together.
2. [Rendering and timing decisions](RENDERING.md): interpolation, visibility,
   textures, mirror mode, car contact, HUD composition and display pacing.
3. [Contributor and agent guide](DEVELOPMENT.md): source navigation, change
   boundaries, tests, evidence and the branch/PR workflow.

For installation, use [Build on macOS](BUILD_MACOS.md) or
[Build on Windows](BUILD_WINDOWS.md). For controls and preferences, use
[Playing and settings](PLAY.md). Licensing is explained in
[third-party notices](../THIRD_PARTY_NOTICES.md).

## What was implemented

The project connects a PSXRecomp runtime generated from the supplied USA disc to
an independent scene renderer. Game-specific hooks publish camera, object, sky
and HUD state. Local tools derive scene assets from that same disc. The renderer
interpolates poses between source samples, reconstructs additional visible scenery
and cars, and combines enhanced geometry with original framebuffer screens when
an enhanced scene is unavailable.

The implementation includes mirror-mode appearance corrections, wheel-pose
matching, car/shadow depth compatibility, persistent sign rendering, widescreen
HUD placement, shared VRAM updates, process ownership and platform-specific
presentation diagnostics. Original game timing remains authoritative.

Development was carried out using Codex under human direction and playtesting.
The descriptions here are checked against maintained source; model-generated
explanations are not a substitute for source review or platform validation.

## Scope and validation boundary

Guest addresses and classifications target **USA / SCUS-94300**, not arbitrary
PlayStation games or other Ridge Racer revisions. Address constants and disc
identity metadata are source inputs; disc bytes, generated game C, textures,
models and captures are local inputs or outputs and are not distributed here.

The initial source release was checked with a clean Mac build, local asset
preparation and 77 passing project tests, including OpenGL tests. Windows
executables were cross-compiled. The Windows-native build and asset-preparation
workflow still requires end-to-end verification on Windows. Windows presentation
and fallen-sign rendering also need further platform validation. These are
validation limits, not reasons to infer that the two platforms behave identically.

Keep these documents current when changing protocols, build inputs, runtime
ownership or rendering behaviour. Link explanations to maintained source and
focused tests so the knowledge remains useful as the project evolves.
