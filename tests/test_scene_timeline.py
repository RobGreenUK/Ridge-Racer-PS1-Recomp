"""Time conversion, rotation/cut handling, and non-integer presentation ratios."""
import importlib.util
from pathlib import Path
import math
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('export_scene', ROOT / 'tools/export_scene.py')
export_scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_scene)

HARNESS = r'''
#include "timeline.h"
#include <cassert>
#include <set>
using namespace ridge;
int main() {
    Frame a{0,3,{0,0,0},{0,0,0,1},{0,0,0},3.1f};
    Frame b{1./30,3,{10,0,0},{0,0,0,-1},{20,0,0},-3.1f};
    auto f=interpolate(a,b,1./60);
    assert(std::abs(f.camera.x-5)<1e-5);
    assert(std::abs(f.car.x-10)<1e-5);
    assert(std::abs(f.rotation.w-1)<1e-5); // q and -q represent same rotation
    assert(std::abs(f.yaw-3.14159265f)<1e-4); // shortest path across wrap
    b.flags=4; assert(interpolate(a,b,1./60).camera.x==0);
    assert(interpolate(a,b,1./30).camera.x==10); // cut only at its timestamp
    b.flags=3;b.camera.x=5000;assert(interpolate(a,b,1./60).camera.x==0);
    b.camera.x=10;b.time=.3;assert(interpolate(a,b,.1).camera.x==0);
    a.models={{uint64_t(1)<<32|12,0,{0,0,0},{2,0,0,0,2,0,0,0,2}}};
    b.models={{uint64_t(1)<<32|12,0,{10,0,0},{-2,0,0,0,2,0,0,0,-2}}};b.time=1./30;
    auto turn=interpolate(a,b,1./60).models.front();
    assert(std::abs(turn.position.x-5)<1e-5);
    assert(std::abs(turn.matrix[0])<1e-5);
    assert(std::abs(std::abs(turn.matrix[6])-2)<1e-5); // no shrinking
    b.models[0].key=99;
    assert(interpolate(a,b,1./60).models[0].position.x==0); // never blend different objects
    assert(interpolate(a,b,b.time).models[0].key==99);
    // Wheel animation changes mesh every few original ticks. Axles must
    // travel with the body even when the next sample uses the alternate mesh.
    for(uint32_t owner:{0x80080194u,0x801ece34u})for(uint32_t site:{0x80020f8cu,0x8002102cu}) {
        a.models[0].key=b.models[0].key=(uint64_t(owner)<<32)|site;
        a.models[0].model=2;b.models[0].model=36;
        auto wheel=interpolate(a,b,1./60).models[0];
        assert(std::abs(wheel.position.x-5)<1e-5);
        assert(wheel.model==2); // authored appearance changes at the boundary
        assert(interpolate(a,b,b.time).models[0].model==36);
    }
    a.models[0].key=b.models[0].key=(uint64_t(0x80080194u)<<32)|0x80020e1cu;
    assert(interpolate(a,b,1./60).models[0].position.x==0); // other mesh changes retain cut
    a.sky={0,4090,0,0,1,0x808080,1};b.sky={0,6,0,0,2,0xffffff,1};
    a.hud={1,2};b.hud={3,4};
    auto skyMid=interpolate(a,b,1./60);
    assert(std::abs(skyMid.sky.yaw-4096)<1e-5);
    assert(skyMid.sky.clut==1 && skyMid.hud==a.hud);
    assert(interpolate(a,b,b.time).hud==b.hud);
    b.sky.mirror=1;assert(interpolate(a,b,1./60).sky.yaw==4090);
    std::vector<Frame> frames;
    // NTSC-derived 29.97 sample rate vs exact 60/120/144 presentation.
    for(int i=0;i<=300;i++) {
        Frame x=a;x.time=i*(1001./30000);x.camera.x=x.car.x=float(x.time*100);frames.push_back(x);
    }
    for(int fps:{60,120,144}) {
        std::set<int> positions;
        for(int i=0;i<fps*10;i++) {
            double t=double(i)/fps;auto x=sample(frames,t);
            assert(std::abs(x.car.x-t*100)<.001);
            positions.insert(int(std::round(x.car.x*10000)));
        }
        assert(positions.size()==size_t(fps*10)); // real distinct transform samples
        assert(std::abs(sample(frames,10).car.x-1000)<.001); // same distance/duration
    }
    assert(sample(frames,-1).car.x==frames.front().car.x);
    assert(sample(frames,100).car.x==frames.back().car.x);
}
'''


class SceneTimelineTests(unittest.TestCase):
    def test_world_model_export_ignores_camera(self):
        import struct
        frame=dict(camera_position=struct.pack('<3i',9000,10,-500).hex(),
                   camera_matrix=struct.pack('<9h',0,0,4096,0,4096,0,-4096,0,0).hex(),
                   models=[dict(owner=1,site=2,model=0x8000003f,rotation=[4096,0,4096,0,4096],translation=[400000,40,-80])])
        pose=export_scene.model_poses(frame)[0]
        self.assertEqual(pose[1:5],(63,100000,10,-20))
        self.assertEqual(pose[5:14],(1,0,0,0,1,0,0,0,1))

    def test_native_interpolation_and_arbitrary_rates(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'test.cpp'; source.write_text(HARNESS)
            binary = Path(tmp) / 'test'
            subprocess.run(['c++', '-std=c++17', '-I' + str(ROOT / 'src/scene'),
                            str(source), '-o', str(binary)], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True, capture_output=True)

    def test_matrix_quaternion_identity_and_half_turn(self):
        q = export_scene.quaternion([1,0,0,0,1,0,0,0,1])
        self.assertEqual(q, [0,0,0,1])
        q = export_scene.quaternion([-1,0,0,0,1,0,0,0,-1])
        self.assertAlmostEqual(abs(q[1]), 1)
        self.assertAlmostEqual(sum(x*x for x in q), 1)


if __name__ == '__main__':
    unittest.main()
