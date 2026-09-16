# Ridge Racer PS1 Recomp

An unofficial recompilation of **Ridge Racer for the original PlayStation
(USA, SCUS-94300)**, with an enhanced renderer for Apple Silicon Macs and Windows
11 x64 PCs. Build it locally using your own copy of the game.

The project uses [PSXRecomp](https://github.com/mstan/psxrecomp) to generate native
code from the supplied disc. An independent renderer adds higher resolutions,
4:3 and 16:9 output, perspective-correct textures, expanded scene visibility and
interpolated rendering at selectable frame rates. The original game continues to
control physics, simulation timing, race progression, audio and replay behaviour.
Increasing the rendering frame rate does not increase the physics rate.

**Development of this project was carried out using OpenAI Codex**, directed and
playtested by Rob Green. Codex was used for implementation, debugging, build
tooling, tests and documentation. The supporting projects credited below are the
work of their respective authors and contributors.

## Game files and copyright

**No copyrighted Ridge Racer game files are included in this repository.** This
includes BIN/CUE disc images, the original game executable, extracted textures,
models, music and other game assets. Generated game code and playable game builds
are also excluded. You must supply your own supported USA disc dump; the build
tools generate the necessary code and assets locally.

No Sony PlayStation BIOS is supplied. The framework uses the separately licensed
OpenBIOS replacement. Project source and third-party dependencies retain their
applicable copyrights and licences; this is not a claim that all source code is
copyright-free. Ridge Racer and its game content and trademarks belong to their
respective owners. This project is unofficial and is not affiliated with or
endorsed by the game's rights holders.

## Get the source and supply your disc

Install the tools for your platform using the guides below, then clone the
repository **with its submodules**:

```sh
git clone --recurse-submodules https://github.com/RobGreenUK/Ridge-Racer-PS1-Recomp.git
cd Ridge-Racer-PS1-Recomp
```

If you already cloned without submodules, run:

```sh
git submodule update --init --recursive
```

Create `Ridge Racer (USA)/` inside the repository and place your CUE and all
**14 referenced BIN tracks** there. The expected layout is:

```text
Ridge-Racer-PS1-Recomp/
  Ridge Racer (USA)/
    Ridge Racer (USA).cue
    Ridge Racer (USA) (Track 01).bin
    ...
    Ridge Racer (USA) (Track 14).bin
```

Keep track filenames consistent with the CUE. Other regions and revisions are
not supported. The build checks the configured USA disc identity. An Internet
connection is needed initially to obtain build dependencies; there is no step
that downloads the game or its assets.

## Build on macOS

Requires an Apple Silicon Mac, macOS 26 or newer, Apple's command-line tools and
Homebrew. See the [complete macOS guide](docs/BUILD_MACOS.md) for setup and
troubleshooting. From the repository root:

```sh
brew install cmake ninja python@3.13 pkg-config sdl3
sh scripts/build-macos.sh
sh scripts/prepare-native-scene.sh
sh scripts/build-pacing-test.sh
. scripts/macos-env.sh
python3 tools/package_macos.py
```

Open **`dist/macos/Play.command`**. The local package includes its Python and
library dependencies. The optional Mac display-callback pacing launcher and its
required settings are explained in the macOS guide.

## Build on Windows

Build directly on a Windows 11 x64 PC using the **MSYS2 UCRT64** terminal; a Mac
is not required. Follow the [complete Windows guide](docs/BUILD_WINDOWS.md) to
install MSYS2 and the compiler, CMake, Ninja, Python and pkg-config packages.
After cloning and supplying your disc, run from the repository root in UCRT64:

```sh
bash scripts/build-windows.sh
```

Open **`dist/windows/Play.cmd`** in Explorer. The script generates game code,
builds the runtime and renderer, prepares assets from your disc and stages the
local playable folder. Python is needed to build, but not to play this Windows
output.

**Validation status:** the Mac workflow has been checked from a clean checkout.
Windows executables have been cross-compiled, but the Windows-native workflow
still needs end-to-end validation on Windows. Graphics and presentation behaviour
can vary with Windows hardware and drivers.

## Playing and local data

See [Playing and settings](docs/PLAY.md) for controls, rendering options and save
locations. Keep the entire playable folder together. Packaging refuses to
overwrite an existing output: preserve its saves and preferences before replacing
it with a new build.

Disc files, `generated/`, `disc/`, `build-*/`, `dist/`, saves and diagnostics are
ignored by Git. They are local inputs or outputs, not source release material.
Do not upload game-derived files or playable packages to GitHub, including Releases,
Actions artifacts or Git LFS.

## Acknowledgements

Thank you to the authors, maintainers and contributors of the projects that make
this work possible:

- **[PSXRecomp](https://github.com/mstan/psxrecomp)** — the PlayStation recompilation
  framework, code generation tools and runtime on which this project is built.
- **[recomp-ui](https://github.com/mstan/recomp-ui)** — supporting runtime user
  interface components.
- **[PCSX-Redux / OpenBIOS](https://github.com/grumpycoders/pcsx-redux)** and
  **[uC-sdk](https://github.com/grumpycoders/uC-sdk)** — the replacement BIOS and
  supporting work used by the framework.
- **[SDL](https://github.com/libsdl-org/SDL)** — cross-platform windowing, input,
  audio and rendering infrastructure.
- The contributors to **fmt, toml11, ELFIO, rabbitizer, libchdr**, their supporting
  libraries, and the **Python, CMake, Ninja, MSYS2 and Homebrew** toolchains.

Their work remains credited and licensed independently. See
[third-party notices](THIRD_PARTY_NOTICES.md) and the notices within each dependency.

## Licence

Original project contributions use the [MIT licence](LICENSE), including its
warranty and liability disclaimers. **PSXRecomp is licensed under PolyForm
Noncommercial**, and those restrictions remain applicable to the framework and
applicable derived work. The complete project is therefore not an unrestricted
MIT-only distribution. See [third-party notices](THIRD_PARTY_NOTICES.md) for the
licensing boundaries. No rights to game content are granted.
