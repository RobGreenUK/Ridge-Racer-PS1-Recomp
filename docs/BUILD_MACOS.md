# Build on macOS (Apple Silicon)

The current launcher targets macOS 26 or newer. Install Apple's command-line
tools (`xcode-select --install`) and [Homebrew](https://brew.sh/), then:

```sh
brew install cmake ninja python@3.13 pkg-config sdl3
```

Clone using the URL from GitHub's Code button:

```sh
git clone --recurse-submodules https://github.com/RobGreenUK/Ridge-Racer-PS1-Recomp.git ridge-racer
cd ridge-racer
```

Place the supported USA CUE and 14 BIN tracks in `Ridge Racer (USA)/` as described
in the root README. From the repository root:

```sh
sh scripts/build-macos.sh
sh scripts/prepare-native-scene.sh
sh scripts/build-pacing-test.sh
. scripts/macos-env.sh
python3 tools/package_macos.py
```

The scripts compile the recompiler, generate game C from your disc, build the
runtime and renderer, capture local palette data in an isolated session, and
extract the enhanced scene assets. The packaging step stages `dist/macos/` with
Python and local library dependencies. Allow several minutes for asset preparation.

Open `dist/macos/Play.command`. The app is locally ad-hoc signed, not notarized.
Keep its entire folder together. It contains your game data and is not a public
release artifact. `Test Ridge Racer Pacing.command` in that folder provides the
Mac display-callback timing mode; select enhanced rendering, fullscreen, V-sync On
and Display FPS before using it. The normal Play launcher supports the other
presentation settings.

For incremental use without packaging, open `build-macos/Ridge Racer.app`.
A full build replaces the ordinary viewer. Settings and saves are not build inputs
and should be retained when replacing an output. Packaging refuses an existing
`dist/macos/`; move it aside and preserve its saves/preferences first.

If Apple's default developer directory reports a licence error, source
`scripts/macos-env.sh`, which selects installed command-line tools. If that
installation itself needs a licence or update, complete Apple's setup in Terminal.
Use `RIDGE_JOBS=4 sh scripts/build-macos.sh` if memory is limited.
