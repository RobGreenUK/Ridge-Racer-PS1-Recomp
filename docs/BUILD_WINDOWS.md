# Build on Windows 11 x64

Use a Windows PC with working OpenGL graphics drivers. This workflow builds and
runs the generation tools on Windows; a Mac is not required. It is implemented
but has not yet been validated end to end on a Windows machine.

## Install tools

Install [MSYS2](https://www.msys2.org/), open its **UCRT64** terminal and update:

```sh
pacman -Syu
```

If asked to close the terminal, reopen UCRT64 and run that command again. Install:

```sh
pacman -S --needed git mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-pkgconf
```

Use UCRT64 throughout, including its native Windows Python (3.11 or newer).
Do not mix MSYS or MINGW64 compilers and libraries. See MSYS2's
[environment guide](https://www.msys2.org/docs/environments/).

## Clone and build

In UCRT64, clone using the URL from this repository's GitHub Code button:

```sh
git clone --recurse-submodules https://github.com/RobGreenUK/Ridge-Racer-PS1-Recomp.git ridge-racer
cd ridge-racer
```

Place the supported USA CUE and 14 BIN tracks in `Ridge Racer (USA)/` as described
in the root README, then run:

```sh
bash scripts/build-windows.sh
```

The script applies the recorded runtime patches, compiles the recompiler, derives
game C from your disc, builds the runtime and viewer, captures local palette data
in an isolated runtime session, extracts scene assets and stages `dist/windows/`.
Asset preparation can take several minutes. It uses separate temporary saves.
SDL and other runtime dependencies are fetched by the pinned framework as needed.
Use `RIDGE_JOBS=4 bash scripts/build-windows.sh` to reduce build concurrency.

Open `dist/windows/Play.cmd` in Explorer. Keep the entire folder together. It
contains your game data and must not be uploaded or distributed as a source release.
No Python is needed to play the resulting Windows output.

## Troubleshooting

- Missing `tomllib`: use the UCRT64 Python package, version 3.11 or newer.
- Wrong compiler or stale CMake toolchain: preserve saves, then remove only
  `build-windows/` and `build-recompiler/` and rerun in UCRT64.
- Disc mismatch: use the supported USA revision and all its original track files.
- Palette capture failure: inspect the new `diagnostics/runs/native-palette-*`
  runtime log; do not replace the missing assets with downloads.
- Existing `dist/windows/`: preserve its saves and preferences, move it aside,
  rerun packaging, then restore those files into the new output.

A Windows gameplay test remains necessary, particularly enhanced rendering,
V-sync, controllers, replay, fallen signs and save persistence.
