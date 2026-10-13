"""Compiler and library flags for the tests' native C/C++ harnesses.

Harnesses that open an SDL window and an OpenGL context need SDL3 from
pkg-config and the host's OpenGL library. This module finds both on macOS
(Homebrew) and Windows (MSYS2 UCRT64) without hard-coding install paths.

On a host the renderer does not target, or when SDL3/pkg-config is missing,
the calling test is skipped with the reason. A skip is not evidence that
rendering passed (see docs/DEVELOPMENT.md).
"""
import os
import shlex
import shutil
import subprocess
import sys
import unittest

# Fallback for macOS shells where Homebrew is installed but not on PATH.
HOMEBREW_PKG_CONFIG = '/opt/homebrew/bin/pkg-config'


def find_pkg_config():
    """Return the pkg-config executable to use, or None if none is available."""
    configured = os.environ.get('PKG_CONFIG')
    if configured:
        return configured
    for name in ('pkg-config', 'pkgconf'):
        found = shutil.which(name)
        if found:
            return found
    if os.path.exists(HOMEBREW_PKG_CONFIG):
        return HOMEBREW_PKG_CONFIG
    return None


def sdl3_flags():
    """Compiler and linker flags for SDL3, or skip the test if unavailable."""
    tool = find_pkg_config()
    if tool is None:
        raise unittest.SkipTest('pkg-config not found; install it with SDL3 '
                                '(see docs/BUILD_MACOS.md or docs/BUILD_WINDOWS.md)')
    try:
        output = subprocess.check_output([tool, '--cflags', '--libs', 'sdl3'],
                                         text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        raise unittest.SkipTest(f'SDL3 is not visible to {tool}')
    return shlex.split(output)


def opengl_flags():
    """Linker flags for the host OpenGL library, or skip on untargeted hosts."""
    if sys.platform == 'darwin':
        return ['-framework', 'OpenGL']
    if sys.platform == 'win32':
        return ['-lopengl32']
    raise unittest.SkipTest(f'the renderer targets macOS and Windows OpenGL, '
                            f'not {sys.platform}')


def gl_harness_flags():
    """SDL3 and OpenGL flags for a harness that creates a GL context."""
    gl = opengl_flags()  # Check the platform first so the skip reason is clear.
    return [*sdl3_flags(), *gl]
