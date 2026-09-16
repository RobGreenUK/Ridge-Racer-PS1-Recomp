"""Clock continuity with jittered producer delivery and display-rate sampling."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class PresentationTests(unittest.TestCase):
    def test_jittered_delivery_and_state_cuts(self):
        code=r'''
#include "presentation_timeline.h"
#include <cassert>
int main(){
 for(int fps:{60,75,120,144}){
  PresentationTimeline playback;int next=0;double last=0;bool have=false;
  constexpr double step=1001./30000;
  for(int tick=0;tick<fps*5;tick++){
   double now=double(tick)/fps;
   while(next*step+.003*std::sin(next*1.7)<=now){
    ridge::Frame f{};f.time=next*step;f.camera.x=f.time*100;
    playback.push(f,next*step+.003*std::sin(next*1.7));next++;
   }
   auto f=playback.at(now,1./fps);
   if(now>1&&have)assert(std::abs(f.camera.x-last-100./fps)<.05);
   last=f.camera.x;have=true;
  }
  ridge::Frame cut{};cut.time=6;cut.flags=1;cut.camera.x=900;
  playback.push(cut,6);assert(playback.frames.size()==1);
  assert(playback.at(6,1./fps).camera.x==900);
 }
}
'''
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'test.cpp').write_text(code)
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),'-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True)
