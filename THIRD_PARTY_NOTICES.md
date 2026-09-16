# Licensing and attribution

The MIT licence in LICENSE applies to original project contributions for which
these contributors hold copyright. It permits use, modification and redistribution
with attribution, and includes warranty and liability disclaimers. It does not
relicense third-party code, game content or trademarks.

## PSXRecomp — PolyForm Noncommercial 1.0.0

PSXRecomp is Copyright (c) 2026 Matthew Stan. The pinned dependency and its
project scaffolding remain subject to [its licence](psxrecomp/LICENSE), including
the additional clarification at the end of that file. Commercial use is not
granted by this project's MIT licence. The complete dependency-based project is
therefore source-available for permitted noncommercial uses, not an unrestricted
MIT-only distribution.

The project CMake/scaffold configuration, codegen_setup.c, codegen_setup.h,
framework artwork in assets/, and modifications in patches/ retain the applicable
PSXRecomp terms. Preserve upstream notices when redistributing these files.
Dependency source: https://github.com/mstan/psxrecomp
Pinned commit: d3e91e07b56c0b672be6136e9fce6af541e9d1e9

## recomp-ui — MIT

Copyright (c) 2026 Matthew Stanley. See [the full licence](recomp-ui/LICENSE).
Dependency source: https://github.com/mstan/recomp-ui
Pinned commit: 028fa5c238265090a6596d1256168bb0b69b0e60

## Other dependencies

PSXRecomp's [third-party attribution](psxrecomp/THIRD_PARTY_ATTRIBUTION.md)
and the licences within its vendored libraries remain applicable. SDL, fmt,
toml11, ELFIO, rabbitizer, libchdr and compression libraries retain their notices.
The framework supplies replacement OpenBIOS under the terms recorded in
[OpenBIOS.LICENSE](psxrecomp/bios/OpenBIOS.LICENSE); no Sony BIOS is supplied by
this project. Mac local packages also bundle Python and Homebrew libraries with
their respective licences. Generated local builds are not public release artifacts.

## Game content

Ridge Racer and its associated game content and trademarks belong to their
respective owners. This is an unofficial project. No licence to game content is
granted. Supply your own supported disc dump; all generated game code, extracted
assets and playable packages must remain local. Do not upload them to GitHub,
including Releases, Actions artifacts or Git LFS.
