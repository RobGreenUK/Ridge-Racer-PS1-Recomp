"""Car contact preserves geometry and matches road depth, including mirror mode."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class CarContactTests(unittest.TestCase):
 def test_contact_plane_and_pose_identity(self):
  code=r'''
#include "timeline.h"
using namespace ridge;
#include "shadow_ground.h"
#include "car_contact.h"
#include <cassert>
int main(){
 ModelPose p{(uint64_t(0x80080194)<<32)|0x80020f8cu,38,{0,-6.7f,0},{1,0,0,0,1,0,0,0,1}};
 ShadowGround g;g.valid=true;g.xSlope=.1f;g.zSlope=.05f;
 Frame frame{};Vec camera{0,-40,0};
 // The plane equation must reproduce true projected road depth across pixels.
 for(int bias:{0,-8,20}){g.depthBias=bias;
 auto plane=carRoadDepthPlane(g,frame,camera,640,480);
 for(float x:{-100.f,0.f,100.f})for(float z:{500.f,1000.f}){
  Vec v{x,g.height(x,z)+40+bias*.125f*std::sqrt(1+g.xSlope*g.xSlope+g.zSlope*g.zSlope),z};float sx=320+640*v.x/z,sy=240+640*v.y/z;
  float expected=150000.f/(150000.f-20)*(1-20/z)+bias/16777216.f;
  assert(std::abs(plane.x*sx+plane.y*sy+plane.z-expected)<.000001);
  frame.sky.mirror=1;auto mirrored=carRoadDepthPlane(g,frame,camera,640,480);
  assert(std::abs(mirrored.x*(640-sx)+mirrored.y*sy+mirrored.z-expected)<.000001);frame.sky.mirror=0;
 }
 }
 assert(carRoadDepthPlane(g,frame,{0,40,0},640,480).z==0);
 g.valid=false;assert(carRoadDepthPlane(g,frame,camera,640,480).z==0);
 // Plane calculation never moves or rotates the authored geometry.
 assert(p.position.y==-6.7f&&p.matrix[4]==1);
 for(uint32_t site:{0x80020e1cu,0x80020e7cu,0x80020eccu,0x80020f8cu,0x8002102cu}){p.key=uint64_t(0x80080194)<<32|site;assert(carSolidPart(p));}
 p.key=uint64_t(0x80080194)<<32|0x80020d60u;assert(!carSolidPart(p)); // shadows remain on road
 p.key=uint64_t(0x801db97c)<<32|0x80039694u;assert(!carSolidPart(p));
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'t.cpp').write_text(code)
   subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'t.cpp'),'-o',str(p/'t')],check=True,capture_output=True)
   subprocess.run([str(p/'t')],check=True,capture_output=True)
