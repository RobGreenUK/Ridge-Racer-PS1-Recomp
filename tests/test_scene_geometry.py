"""Perspective reconstruction preserves coverage of steep near-camera surfaces."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "timeline.h"
using namespace ridge;
#include "geometry.h"
#include <cassert>
int main(){
    MeshVertex a{{-20,10,20},0,0},b{{20,10,20},1,0},c{{0,-100,1000},.5,1};
    auto area=[](MeshVertex a,MeshVertex b,MeshVertex c){
        return std::abs((b.position.x/b.position.z-a.position.x/a.position.z)*(c.position.y/c.position.z-a.position.y/a.position.z)-(b.position.y/b.position.z-a.position.y/a.position.z)*(c.position.x/c.position.z-a.position.x/a.position.z));
    };
    double coverage=0;int triangles=0;
    perspectiveTriangles(a,b,c,[&](MeshVertex x,MeshVertex y,MeshVertex z){
        coverage+=area(x,y,z);triangles++;
        // At the projected centroid, compare the affine UV with the analytic
        // reciprocal-depth UV. One texel tolerance in this regression scene.
        for(int component=0;component<2;component++) {
            float u=component?x.v:x.u,v=component?y.v:y.u,w=component?z.v:z.u;
            float correct=(u/x.position.z+v/y.position.z+w/z.position.z)/(1/x.position.z+1/y.position.z+1/z.position.z);
            assert(std::abs(correct-(u+v+w)/3)*256<1);
        }
    });
    assert(triangles>1&&triangles<=16384);
    assert(std::abs(coverage-area(a,b,c))<1e-5);
}
'''
class GeometryTests(unittest.TestCase):
    def test_perspective_uv_and_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(HARNESS)
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),'-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True,capture_output=True)
