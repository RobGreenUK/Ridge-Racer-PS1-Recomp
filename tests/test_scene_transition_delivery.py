"""Exercise race-start track replacement and lighting changes through real IPC."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class TransitionDeliveryTests(unittest.TestCase):
    def test_track_table_handoff_keeps_motion_buffer(self):
        code=r'''
#include "timeline.h"
#include <cstdio>
#include <cstring>
#include <string>
#include <cassert>
static uint64_t now=1000000000;
static uint64_t SDL_GetTicksNS(){return now;}
using namespace ridge;
#include "live_client.h"
int main(int argc,char**argv){
 LiveClient client;client.open(argv[1]);int sender=socket(AF_UNIX,SOCK_DGRAM,0);
 sockaddr_un address{};address.sun_family=AF_UNIX;strcpy(address.sun_path,argv[1]);
 auto send=[&](const void*p,size_t n){assert(sendto(sender,p,n,0,(sockaddr*)&address,sizeof address)==ssize_t(n));};
 unsigned next=0;double last=0;Frame out;
 for(int tick=0;tick<75*7;tick++){
  double wall=tick/75.;now=1000000000+uint64_t(wall*1e9);
  while(next/30.<=wall){
   RRLiveFrame f{};f.magic=RR_LIVE_MAGIC;f.sequence=next;f.state=1;f.cycles=next*1128960;
   f.flags=(next<45?1:next<90?2:3)|(next>=120&&next<180?RR_SCENE_NIGHT:0);
   f.track=next<90?0x80059164:0x80057d64;f.camera[0]=next*100;
   for(int i=0;i<9;i++)f.matrix[i]=i%4==0?4096:0;
   send(&f,sizeof f);
   RRModelChunk c{};c.magic=RR_MODEL_CHUNK_MAGIC;c.sequence=next;send(&c,20);
   next++;
  }
  assert(client.poll(out,1./75));
  if(wall>1){assert(std::abs(out.time-last-1./75)<.0003);assert(std::abs(out.camera.x-out.time*3000)<.01);}
  last=out.time;
 }
 // A different course during phase 3 remains a reset, even at a nearby position.
 RRLiveFrame f{};f.magic=RR_LIVE_MAGIC;f.sequence=next;f.state=1;f.cycles=next*1128960;
 f.flags=3;f.track=0x8005a564;f.camera[0]=next*100;
 for(int i=0;i<9;i++)f.matrix[i]=i%4==0?4096:0;
 send(&f,sizeof f);RRModelChunk c{};c.magic=RR_MODEL_CHUNK_MAGIC;c.sequence=next;send(&c,20);
 assert(client.poll(out,1./75));assert(out.camera.x==float(next*100));
 // Verified replay enters with a clean timeline; unknown state stays fallback.
 f.state=5;f.sequence++;f.cycles+=1128960;f.flags=RR_SCENE_REPLAY|(3u<<20);f.camera[0]=42;
 send(&f,sizeof f);c.sequence=f.sequence;send(&c,20);
 assert(!client.poll(out,1./75)); // replay setup has no geometry yet
 c.total=c.count=1;c.models[0].rotation[0]=4096;c.models[0].rotation[2]=4096;c.models[0].rotation[4]=4096;
 // Start a new assembly for the first real replay scene.
 f.sequence++;f.cycles+=1128960;send(&f,sizeof f);c.sequence=f.sequence;send(&c,20+sizeof(RRRawModel));
 assert(client.poll(out,1./75));assert(out.camera.x==42);assert(out.flags&RR_SCENE_REPLAY);
 Frame a=out,b=out;b.time+=1./30;b.flags^=1u<<24;
 assert(sceneFramesCut(a,b)); // same-position cut when replay target changes
 b.flags=a.flags;b.camera.x+=100;assert(!sceneFramesCut(a,b));
 f.state=10;f.sequence++;f.cycles+=1128960;send(&f,sizeof f);c.sequence=f.sequence;send(&c,20);
 assert(!client.poll(out,1./75));
 // State 9 intro/demo: reject empty setup, then accept complete geometry
 // even without a race navigation table. State changes discard old replay.
 f.state=9;f.track=0;f.sequence++;f.cycles+=1128960;f.camera[0]=900;
 send(&f,sizeof f);c.sequence=f.sequence;c.total=c.count=0;send(&c,20);
 assert(!client.poll(out,1./75));
 f.sequence++;f.cycles+=1128960;send(&f,sizeof f);c.sequence=f.sequence;c.total=c.count=1;
 send(&c,20+sizeof(RRRawModel));assert(client.poll(out,1./75));assert(out.camera.x==900);
 // Music-player (26) and recorded lap-time replay (29) share setup guards.
 for(unsigned mode:{26u,29u}) {
 f.state=mode;f.sequence++;f.cycles+=1128960;f.camera[0]=2600;
 send(&f,sizeof f);c.sequence=f.sequence;c.total=c.count=0;send(&c,20);
 assert(!client.poll(out,1./75));
 f.sequence++;f.cycles+=1128960;send(&f,sizeof f);c.sequence=f.sequence;c.total=c.count=1;
 send(&c,20+sizeof(RRRawModel));assert(client.poll(out,1./75));assert(out.camera.x==2600);
 }
 close(sender);
}
'''
        with tempfile.TemporaryDirectory(prefix='rrtransition-',dir='/tmp') as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(code)
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),'-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test'),str(p/'socket')],check=True,capture_output=True)
