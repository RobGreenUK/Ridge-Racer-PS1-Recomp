cmake_minimum_required(VERSION 3.20)
set(PSXRECOMP_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/psxrecomp" CACHE PATH
    "Path to psxrecomp")
if(NOT EXISTS "${PSXRECOMP_ROOT}/runtime/runtime.cmake")
    message(FATAL_ERROR
        "PSXRecomp runtime is missing: ${PSXRECOMP_ROOT}/runtime/runtime.cmake\n"
        "This project expects the psxrecomp framework checkout at ${PSXRECOMP_ROOT}.\n"
        "Run: git submodule update --init --recursive\n"
        "If psxrecomp/ is not a submodule, set -DPSXRECOMP_ROOT=<path-to-psxrecomp>.")
endif()

project(RidgeRacerRecomp LANGUAGES C CXX)

# --- Opt-in product surfaces (OFF by default in the framework) -------------
# Scaffold prompts / flags fill these. Without recomp-ui, PSX_RECOMP_UI is OFF.
# Setup-host CI requires WIZARD_CMAKE_BLOCK / ENABLE_SETUP_WIZARD (FORCE_SETUP_HOST
# alone does not open first-run / Generate & rebuild).
# recomp-ui submodule present (PSX_RECOMP_UI defaults ON).
# Full netplay UI — enable after adding recomp-ui + testing:
# if(EXISTS "${PSXRECOMP_ROOT}/lib/recomp-net/CMakeLists.txt")
#     set(PSX_NETPLAY ON CACHE BOOL "…" FORCE)
# endif()
set(PSX_SETUP_WIZARD ON CACHE BOOL
    "Advertise first-run setup wizard + Generate & rebuild in recomp-ui" FORCE)
include("${PSXRECOMP_ROOT}/runtime/runtime.cmake")

# This project's own mod catalog. The FRAMEWORK stages it -- together with its
# builtin psx.* packages -- into <exe-dir>/mods/bundled, and refuses to
# configure if a catalog exists here but is not declared. Never copy it by
# hand: five titles did, and framework 4cc04be3's rename of the staged
# directory broke all five silently (bead beads-eio.3.101).
set(PSX_PRELOADED_MODS "${CMAKE_CURRENT_SOURCE_DIR}/mods/preloaded")
if(NOT IS_DIRECTORY "${PSX_PRELOADED_MODS}")
    set(PSX_PRELOADED_MODS "NONE")
endif()

psxrecomp_add_game_runtime(psx-runtime
    PRELOADED_MODS_DIR "${PSX_PRELOADED_MODS}"
    # ENABLE_NETPLAY_IF_PRESENT
    # NETPLAY_LOBBY_URL "ws://netplay.retcomm.net:8765"
    ENABLE_SETUP_WIZARD
    WINDOW_TITLE "RidgeRacer Recompiled"
    DEFAULT_GAME_CONFIG_PATH "game.toml"
    MAX_PLAYERS 1
    # LAUNCHER_BOXART "${CMAKE_CURRENT_SOURCE_DIR}/launcher_assets/img/boxart.tga"
    APP_ICON "${CMAKE_CURRENT_SOURCE_DIR}/assets/psxrecomp.ico"
    GEN_MARKER "generated/SCUS-943.00_dispatch.c"
    GEN_FULL_GLOB "generated/SCUS-943.00_full_*.c"
    CODEGEN_SETUP_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/codegen_setup.c"
)

target_sources(psx-runtime PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/launcher/presentation.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/scene/capture.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/scene/live.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/scene/input_replay.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/scene/models.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/scene/scenery_eval.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/scene/palette.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/scene/sky.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/scene/hud.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/scene/screen.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/scene/vram.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/scene/test_driver.c")
set_property(TARGET psx-runtime APPEND PROPERTY LINK_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/mods/preloaded/packages/ridge.presentation/1.0.0/manifest.toml"
    "${CMAKE_CURRENT_SOURCE_DIR}/game.toml")

# Stage runtime configs next to the exe for direct build/ launches. Only copy
# files that exist — never fail POST_BUILD when game_options.toml is absent.
foreach(_PSX_RUNTIME_CONFIG game.toml game_options.toml)
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${_PSX_RUNTIME_CONFIG}")
        add_custom_command(TARGET psx-runtime POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${CMAKE_CURRENT_SOURCE_DIR}/${_PSX_RUNTIME_CONFIG}"
                "$<TARGET_FILE_DIR:psx-runtime>/${_PSX_RUNTIME_CONFIG}"
            COMMENT "Staging ${_PSX_RUNTIME_CONFIG}"
            VERBATIM)
    endif()
endforeach()

# The enhanced renderer shares the runtime's pinned SDL build on Windows.
if(WIN32)
    target_compile_definitions(psx-runtime PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
    add_executable(RidgeScenePreview src/scene/preview.cpp)
    target_compile_features(RidgeScenePreview PRIVATE cxx_std_17)
    target_compile_definitions(RidgeScenePreview PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
    target_link_libraries(RidgeScenePreview PRIVATE SDL3::SDL3 opengl32 ws2_32 winpthread)
    if(MINGW)
        target_link_options(RidgeScenePreview PRIVATE -static -static-libgcc -static-libstdc++)
    endif()
endif()
if(WIN32)
    add_executable(RidgeTransportCheck tests/windows_transport_smoke.c)
    target_link_libraries(RidgeTransportCheck PRIVATE ws2_32 winpthread)
    if(MINGW)
        target_link_options(RidgeTransportCheck PRIVATE -static)
    endif()
endif()
