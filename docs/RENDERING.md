# Rendering and timing decisions

Read [Architecture](ARCHITECTURE.md) first for process and data ownership. This
page explains why the enhanced renderer does more than scale the original image.

## Interpolate geometry, preserve simulation timing

[presentation_timeline.h](../src/scene/presentation_timeline.h) buffers up to eight
source frames, maps game time to host time, and samples behind the newest expected
source time by one estimated producer interval plus one display interval. It
corrects slow clock drift gradually rather than following packet-arrival jitter.
When no later sample is available it holds the newest pose and records that hold;
it does not advance the game to manufacture another state.

[timeline.h](../src/scene/timeline.h) interpolates compatible camera and object
poses. Genuine cuts and incompatible states must remain discrete. Cosmetic
changes such as day/night appearance should not unnecessarily reset continuous
motion. [scene_flags.h](../src/scene/scene_flags.h) and the transition tests encode
this distinction.

Model identity and motion identity are not always the same. Wheel animation can
alternate meshes while still representing one axle. Matching only by mesh would
freeze or interrupt axle interpolation. The verified car/axle matching preserves
pose continuity while retaining the selected wheel appearance.

This buffer trades some presentation latency for continuity between producer and
display rates. Reduce it only with evidence about input latency, held frames and
delivery gaps. More rendering frames do not imply a higher physics tick rate.

## Geometry and visibility

[mesh.h](../src/scene/mesh.h) combines locally extracted course assets with captured
model transforms. [scenery_eval.cpp](../src/scene/scenery_eval.cpp) evaluates a
bounded subset of game scenery submission behaviour against a private memory
copy. It preserves game decisions about phase, animation and object state without
mutating authoritative guest state or advancing guest clocks.

[distant_cars.h](../src/scene/distant_cars.h) reconstructs supported additional car
parts using current guest transforms. Expanded visibility does not mean disabling
all culling: conservative bounds reject static groups and whole model instances
before detailed triangle processing. The renderer still streams visible transformed
geometry; it is not a fully static GPU-resident world.

[depth_renderer.h](../src/scene/depth_renderer.h) batches geometry in a streaming
vertex buffer while preserving material, depth-bias and submission-order needs.
It shares a graphics context with SDL composition, so restoring GL state is part
of correctness. Do not optimize away that boundary without checking the HUD and
fallback screens as well as the world.

## Textures and original framebuffer screens

The viewer follows live VRAM rather than treating extracted textures as immutable.
[texture_data.h](../src/scene/texture_data.h) shares page signatures across palette
lookups, reducing redundant hashing while retaining palette and upload changes.
Perspective-correct and affine texturing are separate presentation choices.

[presentation_mode.h](../src/scene/presentation_mode.h) currently recognizes USA
states 1 (race), 5 (post-race replay), 9 (intro/demo), 26 (music-player replay) and
29 (recorded lap-time replay) for enhanced scene delivery. Unknown/setup states
retain the original framebuffer path rather than guessing a scene layout.
This also lets the startup minigame and menus remain interactive in the main
window. Their correctness depends on both input forwarding and coherent runtime
framebuffer readback.

## Mirror mode and HUD

A course reflection changes geometry handedness. Applying it indiscriminately to
texture orientation and vehicle appearance produces reversed signs or decals.
[mirror_signs.h](../src/scene/mirror_signs.h) and
[mirror_cars.h](../src/scene/mirror_cars.h) apply targeted corrections to verified
content. Preserve the world reflection while keeping readable signage and the
intended vehicle appearance. These adjustments must not invert steering or swap
HUD instrument groups.

[hud_layout.h](../src/scene/hud_layout.h) anchors supported side HUD groups in
widescreen. A minimap includes both its background and indicators; moving only one
layer breaks their alignment. Test 4:3 identity as well as widescreen and mirror
variants. Avoid stretching every original framebuffer screen into a new layout.

## Cars, shadows and road depth

The original ordering-table presentation and a modern per-pixel depth buffer do
not resolve overlapping surfaces identically. Physically raising cars to avoid
road clipping can introduce hovering and alter the intended pose.

The current approach preserves original car and shadow transforms. Shadow
submissions use a separate verified flat-model capture path; the underside model
is not a shadow. [car_contact.h](../src/scene/car_contact.h),
[shadow_ground.h](../src/scene/shadow_ground.h) and the mesh code find a suitable
nearby rendered-road plane with bounded work.

[contact_depth_shader.h](../src/scene/contact_depth_shader.h) changes depth only
for tagged car/shadow overlap. It keeps projected XY and texture coordinates and
compresses overlapping depths monotonically into a narrow band immediately in
front of the local road plane. Monotonic compression retains ordering between
body, wheels and shadow; it is not a global depth-test disable. Nearer walls must
still occlude correctly. Mirror projection and existing road-layer bias must be
included when forming the plane.

Useful regression cases include banked roads, slopes, bridges, jumps, nearby
walls, transparency, reversed submission order and both texture modes. A flat-road
screenshot cannot establish correctness for all of them.

## Moving signs and replay

[sign_capture.h](../src/scene/sign_capture.h) and
[road_signs.h](../src/scene/road_signs.h) retain supported sign poses, complete
missing visible submissions and associate replay history with recorded indices.
Do not replace this with the last live pose during replay. Rendering completion
must not rewrite original sign movement or collision state: signs may travel off
the road under the game's own motion.

Check normal and mirror views, knocked-over signs on later laps, and recorded
replay. Windows fallen-sign appearance remains a platform validation concern;
Mac results alone do not close it.

## Display pacing and measurement

[display_pacer.h](../src/scene/display_pacer.h) implements the Mac display-callback
path. Waiting before input sampling and drawing avoids deferring freshly completed
work immediately before presentation. The separate pacing executable enables the
phase trial; its launcher selects a 2 ms phase and requires enhanced mode,
fullscreen, V-sync On and Display FPS. It is not the same configuration as the
ordinary viewer. Windows uses its own presentation path without CoreVideo.

[frame_metrics.h](../src/scene/frame_metrics.h) queues fixed-size telemetry rows
for a writer thread. Saturation drops telemetry rather than blocking drawing.
[gpu_timer.h](../src/scene/gpu_timer.h) uses delayed query results rather than
synchronous GPU waits. Associate a GPU result with the frame that issued it.

A flat CPU frame graph is not proof of smooth physical scanout. Distinguish
producer cadence, scene age, interpolation holds, CPU draw time, GPU completion,
swap return and display handoff. P captures cause synchronous work and must be
excluded from ordinary pacing comparisons. See the [validation guide](DEVELOPMENT.md)
for a reproducible investigation workflow.
