"""Road contact selection must preserve slopes and avoid another bridge deck."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ShadowTests(unittest.TestCase):
    def test_contact_plane_and_verified_part_identity(self):
        source = r'''
#include "timeline.h"
#include <cassert>
using namespace ridge;
#include "shadow_ground.h"
#include "car_shadows.h"
int main(){
 ShadowGround ground;
 ground.consider({0,0,0},{100,10,0},{0,20,100},{20,7,20});
 assert(ground.valid&&std::abs(ground.height(20,20)-6)<.001);
 assert(std::abs(ground.height(40,30)-10)<.001); // preserve bank/slope
 ground.consider({0,-100,0},{100,-100,0},{0,-100,100},{20,7,20});
 assert(std::abs(ground.height(20,20)-6)<.001); // another deck cannot win
 ShadowGround outside;outside.consider({0,0,0},{100,0,0},{0,0,100},{90,0,90});
 assert(!outside.valid);
 ShadowGround wall;wall.consider({0,0,0},{0,100,0},{0,0,100},{0,0,20});
 assert(!wall.valid);
 ShadowGround missing;missing.consider({0,100,0},{100,100,0},{0,100,100},{20,0,20});
 assert(!missing.valid); // caller retains authored geometry when no road fits
 ModelPose p{};p.key=(uint64_t(0x80080194u)<<32)|0x80020d60u;assert(carShadowPart(p));
 p.key=(uint64_t(0x801ece34u+11*0x114u)<<32)|0x80020db0u;assert(carShadowPart(p));
 p.key=(uint64_t(0x80080194u)<<32)|0x80020eccu;assert(!carShadowPart(p)); // underside
 p.key=(uint64_t(0x801ece35u)<<32)|0x80020d60u;assert(!carShadowPart(p));
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'test.cpp').write_text(source)
            subprocess.run(['c++', '-std=c++17', '-I' + str(ROOT / 'src/scene'),
                            str(path / 'test.cpp'), '-o', str(path / 'test')],
                           check=True, capture_output=True)
            subprocess.run([str(path / 'test')], check=True, capture_output=True)
