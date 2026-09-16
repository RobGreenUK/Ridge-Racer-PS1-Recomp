"""Appearance/race metadata must not reset motion, or mix day/night scenery."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class SceneTransitionContinuityTests(unittest.TestCase):
    def test_motion_and_discrete_appearance_boundaries(self):
        code=r'''
#include "presentation_timeline.h"
#include <cassert>
using namespace ridge;
uint32_t flags(int n){return (n<90?1:n<180?2:3) | (n>=120&&n<210?RR_SCENE_NIGHT:0);}
int main(){
 // Warm buffer, jittered delivery, two race transitions and both lighting edges.
 for(int fps:{60,75,120,144,240}){
  PresentationTimeline timeline;int next=0;double last=0;
  constexpr double step=1001./30000;
  for(int tick=0;tick<fps*9;tick++){
   double now=double(tick)/fps;
   while(next*step+.003*std::sin(next*1.7)<=now){
    Frame f{};f.time=next*step;f.flags=flags(next);f.camera.x=f.time*100;f.car.x=f.time*200;
    timeline.push(f,next*step+.003*std::sin(next*1.7));next++;
   }
   auto f=timeline.at(now,1./fps);
   if(now>1){
    assert(std::abs(f.time-last-1./fps)<.0002);
    assert(std::abs(f.camera.x-f.time*100)<.001);
    assert(std::abs(f.car.x-f.time*200)<.001);
    assert(f.flags==flags(int(std::floor(f.time/step))));
    assert(!timeline.heldLatest);
   }
   last=f.time;
  }
 }
 // Transform continuity is independent of discrete palette/model membership.
 Frame a{},b{};a.flags=3;b.flags=3|RR_SCENE_NIGHT;b.time=1./30;
 b.camera.x=10;b.car.x=20;a.hud={1};b.hud={2};
 a.sky={0,10,0,0,1,0x808080,1};b.sky={0,20,0,0,2,0x404040,1};
 a.models={{1ull<<32,7,{0,0,0},{1,0,0,0,1,0,0,0,1},10}, {11,8,{},{},20}};
 b.models={{1ull<<32,7,{10,0,0},{1,0,0,0,1,0,0,0,1},30}, {12,9,{},{},40}};
 auto mid=interpolate(a,b,b.time/2);
 assert(mid.camera.x==5 && mid.car.x==10 && mid.models[0].position.x==5);
 assert(mid.flags==a.flags && mid.hud==a.hud && mid.sky.clut==1 && mid.sky.rgb==a.sky.rgb);
 assert(mid.models.size()==2 && mid.models[1].key==11 && mid.models[0].paletteOffset==10);
 assert(std::abs(mid.sky.yaw-15)<.001);
 auto boundary=interpolate(a,b,b.time);
 assert(boundary.flags==b.flags && boundary.models[1].key==12 && boundary.models[0].paletteOffset==30);
 assert(boundary.sky.clut==2 && boundary.hud==b.hud && boundary.camera.x==10);
 // The night->day switch has the same boundary policy.
 a.flags|=RR_SCENE_NIGHT;b.flags=3;
 assert(interpolate(a,b,b.time/2).flags==a.flags);
 assert(interpolate(a,b,b.time).flags==b.flags);
 // Keep pauses, reverse/unknown phases and unknown bits as real cuts.
 for(uint32_t f:{4u,2u,3u|0x10000u,3u|0x40000u}){
  a.flags=3;b.flags=f;b.time=1./30;
  PresentationTimeline timeline;timeline.push(a,0);timeline.push(b,b.time);
  assert(timeline.frames.size()==1);
  assert(interpolate(a,b,b.time/2).camera.x==a.camera.x);
  assert(interpolate(a,b,b.time).flags==b.flags);
 }
 // A large camera cut stays a cut even when appearance or routine phase changes.
 a.flags=2;b.flags=3|RR_SCENE_NIGHT;b.camera.x=5001;
 assert(interpolate(a,b,b.time/2).camera.x==a.camera.x);
 assert(interpolate(a,b,b.time).camera.x==5001);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(code)
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),'-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True,capture_output=True)
