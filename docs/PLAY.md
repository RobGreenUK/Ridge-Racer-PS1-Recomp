# Playing your local build

On Mac open `Play.command`; on Windows open `Play.cmd`. Keep the full output
folder together. Configure resolution, aspect ratio, enhanced/original rendering,
frame rate and V-sync in the service menu. A useful starting point is enhanced
1920×1080, 16:9, Display FPS and V-sync On. Lower the resolution if needed.

Enhanced-window keyboard controls: Enter starts, arrow keys steer, X or Space
accelerates, Z brakes, and Esc closes the session. G toggles the frame-time graph;
P captures local diagnostics and may briefly interrupt rendering.

The original game controls physics, audio, race progression and replay. Higher
rendering FPS does not increase the original physics rate. Close one session
before opening another. The enhanced mode uses a hidden companion process.

Saves are in `saves/`. Mac preferences are in `build-macos/settings.toml` and
`build-macos/mods/state.toml` inside the output; Windows preferences include
`settings.toml`, `launcher-settings.json` when present, and `mods/state.toml`.
Preserve these and your saves when replacing the local output.

All game-derived data, saves and diagnostics are local. Do not upload the playable
folder, generated game code, disc files or extracted assets to the source repository.

Custom render resolution is entered as **Horizontal × Vertical**, followed by
**Apply**. Both dimensions are editable and must match the selected 4:3 or 16:9
aspect ratio. Invalid dimensions leave the applied resolution unchanged.

## Game controllers

Choose your controller for Player 1 in **Controls & advanced settings** and
configure its button bindings there. Modern USB/Bluetooth controllers are used
as an original digital PlayStation pad. The left stick supplies directional
buttons in this mode; it does not provide analogue steering.

The game does not accept DualShock analogue packets. The project enforces the
supported digital protocol and hides the incompatible pad-mode selector. This
also overrides an old saved `p1_mode = "analog"` automatically: there is no need
to erase settings, rebind the controller or replace saves. Controller assignment
and button mappings are retained. The enhanced window's keyboard controls listed
above remain available, including during the startup minigame.
