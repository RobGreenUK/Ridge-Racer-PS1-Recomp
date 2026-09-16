"""The Mac display callback wakes rendering and stops cleanly on a lost source."""
import csv
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'darwin', 'CoreVideo is macOS-only')
class DisplayPacerTests(unittest.TestCase):
    def test_real_callbacks_timeout_and_cleanup(self):
        source = r'''
#include <SDL3/SDL.h>
#include "display_pacer.h"
#include <cassert>
int main(int argc,char**argv) {
    assert(SDL_Init(SDL_INIT_VIDEO));
    auto* window=SDL_CreateWindow("Display pacing test",320,240,SDL_WINDOW_HIDDEN);
    assert(window);
    auto* renderer=SDL_CreateRenderer(window,"opengl");
    assert(renderer);
    SDL_setenv_unsafe("RIDGE_HANDOFF_TRACE","1",1);
    DisplayPacer pacer;
    assert(pacer.open(argv[1]));
    for(int i=0;i<3;++i){assert(pacer.wait());assert(pacer.sample.id>0);assert(pacer.sample.waitEnd>=pacer.sample.waitStart);assert(pacer.sample.entry>0);}
    SDL_Delay(80);assert(pacer.wait());assert(pacer.sample.skipped>0);
    assert(pacer.stop(pacer.link)==kCVReturnSuccess);
    // A callback already in flight may leave one pending wake after Stop.
    const auto begin=SDL_GetTicksNS();
    if(pacer.wait())assert(!pacer.wait());
    assert(SDL_GetTicksNS()-begin<1000000000ull);
    pacer.close();pacer.close();
    SDL_DestroyRenderer(renderer);SDL_DestroyWindow(window);SDL_Quit();
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'test.cpp').write_text(source)
            flags = shlex.split(subprocess.check_output(
                ['/opt/homebrew/bin/pkg-config', '--cflags', '--libs', 'sdl3'], text=True))
            subprocess.run(['c++', '-std=c++17', '-I'+str(ROOT/'src/scene'),
                            str(path/'test.cpp'), *flags, '-framework', 'OpenGL',
                            '-o', str(path/'test')], check=True, capture_output=True)
            subprocess.run([str(path/'test'),str(path/'trace')], check=True, capture_output=True, timeout=10)

            with (path/'trace.callbacks.csv').open() as stream:rows=list(csv.DictReader(stream))
            self.assertGreater(len(rows),3)
            self.assertEqual([int(r['callback_id'])for r in rows],list(range(1,len(rows)+1)))
            self.assertTrue(all(r['dropped']=='0'for r in rows))
