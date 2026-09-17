"""Dropped/reordered scene model chunks must never expose a partial world."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "timeline.h"
#include <cstring>
#include <cstdio>
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
 auto frame=[&](unsigned seq){RRLiveFrame f{};f.magic=RR_LIVE_MAGIC;f.sequence=seq;f.state=1;f.cycles=seq*1128960;for(int i=0;i<9;i++)f.matrix[i]=i%4==0?4096:0;send(&f,sizeof f);};
 auto chunk=[&](unsigned seq,unsigned total,unsigned offset,unsigned count){RRModelChunk c{};c.magic=RR_MODEL_CHUNK_MAGIC;c.sequence=seq;c.total=total;c.offset=offset;c.count=count;for(unsigned i=0;i<count;i++){c.models[i].owner=100+offset+i;c.models[i].rotation[0]=4096;c.models[i].rotation[2]=4096;c.models[i].rotation[4]=4096;}send(&c,20+count*sizeof(RRRawModel));};
 Frame out;frame(1);assert(!client.poll(out));chunk(1,2,0,1);assert(!client.poll(out));chunk(1,2,1,1);assert(client.poll(out)&&out.models.size()==2);
 now+=34000000;frame(2);chunk(2,2,0,1);assert(client.poll(out)&&out.models.size()==2&&out.time<.04); // previous COMPLETE world
 now+=34000000;frame(3);chunk(2,2,1,1);assert(client.poll(out)&&out.models.size()==2); // late old packet rejected
 chunk(3,300,288,12);chunk(3,300,0,32);assert(client.poll(out)&&out.models.size()==2);
 chunk(3,300,32,32);chunk(3,300,32,32);assert(client.poll(out)&&out.models.size()==2);
 for(unsigned offset=64;offset<288;offset+=32){chunk(3,300,offset,32);assert(client.poll(out));}
 now+=100000000;assert(client.poll(out)&&out.models.size()==300);
 now+=34000000;frame(4);chunk(4,0,0,0);assert(client.poll(out));now+=100000000;assert(client.poll(out)&&out.models.empty()); // real empty state is allowed
 now+=34000000;
 RRLiveFrame worldFrame{};worldFrame.magic=RR_LIVE_MAGIC;worldFrame.sequence=5;worldFrame.state=1;worldFrame.cycles=5*1128960;
 worldFrame.camera[0]=9000;worldFrame.matrix[2]=4096;worldFrame.matrix[4]=4096;worldFrame.matrix[6]=-4096;send(&worldFrame,sizeof worldFrame);
 RRModelChunk world{};world.magic=RR_MODEL_CHUNK_MAGIC;world.sequence=5;world.total=world.count=1;
 world.models[0].model=RR_MODEL_WORLD_POSE|63;world.models[0].translation[0]=400000;
 world.models[0].rotation[0]=world.models[0].rotation[2]=world.models[0].rotation[4]=4096;
 send(&world,20+sizeof(RRRawModel));assert(client.poll(out));now+=100000000;assert(client.poll(out));
 assert(out.models[0].model==63&&out.models[0].position.x==100000&&out.models[0].position.z==0&&out.models[0].matrix[0]==1);
 struct timespec stamp;clock_gettime(CLOCK_MONOTONIC,&stamp);
 worldFrame.sequence=6;worldFrame.cycles+=1128960;
 worldFrame.published_ns=uint64_t(stamp.tv_sec)*1000000000+stamp.tv_nsec-7000000;
 send(&worldFrame,sizeof worldFrame);world.sequence=6;send(&world,20+sizeof(RRRawModel));
 assert(client.poll(out));assert(client.sourceAgeMs()>=7&&client.sourceAgeMs()<100);
 // Menu model completion alone must not reveal a stale or partial overlay.
 RRLiveFrame menu=worldFrame;menu.sequence=7;menu.cycles+=1128960;menu.state=7;menu.flags=RR_SCENE_MENU;send(&menu,sizeof menu);
 chunk(7,0,0,0);assert(!client.poll(out));
 RRMenuHudChunk h{};h.magic=RR_MENU_HUD_MAGIC;h.sequence=7;h.total=4;h.back_count=2;h.count=2;h.offset=2;h.words[0]=1;h.words[1]=0xe1000001;
 send(&h,32);assert(!client.poll(out));send(&h,32);assert(!client.poll(out));
 h.sequence=6;h.offset=0;send(&h,32);assert(!client.poll(out));
 h.sequence=7;h.back_count=5;send(&h,32);assert(!client.poll(out));
 h.back_count=2;send(&h,32);assert(client.poll(out)&&out.hud.size()==4&&out.menuBackCount==2&&out.models.empty());
 Frame next=out;next.time+=1./30;assert(interpolate(out,next,out.time+.01).menuBackCount==2);
 menu.sequence=8;menu.cycles+=1128960;menu.state=1;menu.flags=3;send(&menu,sizeof menu);chunk(8,0,0,0);
 assert(client.poll(out)&&out.menuBackCount==0&&!(out.flags&RR_SCENE_MENU));
 close(sender);
}
'''
class DeliveryTests(unittest.TestCase):
    def test_complete_snapshot_publication(self):
        with tempfile.TemporaryDirectory(prefix='rrdelivery-',dir='/tmp') as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(HARNESS)
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),'-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test'),str(p/'socket')],check=True,capture_output=True)
