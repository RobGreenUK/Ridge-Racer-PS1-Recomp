"""Movable signs retain road contact through their knock-over rotation."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class RoadSignTests(unittest.TestCase):
 def test_rigid_support_and_identity(self):
  code=r'''
#include "timeline.h"
using namespace ridge;
#include "road_signs.h"
#include <cassert>
struct Vertex{Vec position;};struct Quad{Vertex v[4];};
int main(){
 std::vector<Quad> mesh={{{{{26,-39.25f,0}},{{-26,-39.25f,0}},{{26,0,0}},{{-26,0,0}}}},
                         {{{{-26,-39.25f,0}},{{26,-39.25f,0}},{{-26,0,-19.5f}},{{26,0,-19.5f}}}}};
 ModelPose p{(uint64_t(0x801db7b0u)<<32)|0x80039d44u,200,{53000,0,35000},{1,0,0,0,1,0,0,0,1}};
 assert(supportedRoadSign(p,mesh).position.y==0);
 for(unsigned owner=0;owner<6;owner++)for(int angle=0;angle<=180;angle++){
  p.key=(uint64_t(0x801db7b0u+owner*0x38u)<<32)|0x80039d44u;
  float a=angle*3.14159265f/180;p.matrix={1,0,0,0,std::cos(a),-std::sin(a),0,std::sin(a),std::cos(a)};
  for(float height:{0.f,-50.f}){
   p.position.y=height;auto fixed=supportedRoadSign(p,mesh);
   assert(fixed.matrix==p.matrix&&fixed.position.x==p.position.x&&fixed.position.z==p.position.z);
   float bottom=-1000;
   for(auto&q:mesh)for(auto&v:q.v){auto x=v.position;bottom=std::max(bottom,fixed.position.y+p.matrix[3]*x.x+p.matrix[4]*x.y+p.matrix[5]*x.z);}
   assert(std::abs(bottom-height)<.0001); // rest on base; airborne clearance retained
  }
 }
 p.position.y=0;p.model=100;assert(supportedRoadSign(p,mesh).position.y==0);
 p.model=200;p.key=uint64_t(0x801db7b1u)<<32|0x80039d44u;assert(!movableRoadSign(p));
 p.key=uint64_t(0x801db7b0u)<<32|0x80039694u;assert(!movableRoadSign(p));
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'t.cpp').write_text(code)
   subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'t.cpp'),'-o',str(p/'t')],check=True,capture_output=True)
   subprocess.run([str(p/'t')],check=True,capture_output=True)
