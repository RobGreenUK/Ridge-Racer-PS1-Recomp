"""SCUS-94300 HUD packet groups preserve center instruments and 4:3 geometry."""
from pathlib import Path
import subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
class HudLayoutTests(unittest.TestCase):
 def test_groups_and_native_margins(self):
  source=r'''
#include "hud_layout.h"
#include <cassert>
int main(){
 uint32_t map[]={0x65000000,0x00080008,0x7a006800,0x00300048};
 uint32_t best[]={0x75000000,0x00400008,0x79cf0058};
 uint32_t gear[]={0x65000000,0x00c00008,0x7a022830,0x00080018};
 uint32_t lap[]={0x75000000,0x001800f8,0x79cf00a8};
 uint32_t tach[]={0x65000000,0x009800e8,0x79844848,0x00500050};
 uint32_t mirrorMap[]={0x2d000000,0x00380050,0x7a009800,0x00380008,0x00059847,0x00080050,0x6800,0x00080008,0x6847};
 assert(raceHudAnchor(mirrorMap,9,5)==-1);
 mirrorMap[2]=0x7a019800;assert(raceHudAnchor(mirrorMap,9,5)==-1);
 mirrorMap[2]=0x7a029800;assert(raceHudAnchor(mirrorMap,9,5)==0);
 uint32_t top[]={0x65000000,0x001800c2,0x7a00b0a0,0x00100010};
 uint32_t fade[]={0x62000000,0,0x00f00140};
 uint32_t arrow[]={0x290000ff,0x003e0030,0x00370027,0x0038002f,0x00350033};
 uint32_t needle[]={0x2900ffff,0x00c00112,0x00e100fb,0x00be0110,0x00e100fa};
 assert(raceHudAnchor(map,4,5)==-1&&raceHudAnchor(best,3,5)==-1&&raceHudAnchor(gear,4,5)==-1);
 assert(raceHudAnchor(lap,3,5)==1&&raceHudAnchor(tach,4,5)==1);
 assert(raceHudAnchor(top,4,5)==0&&raceHudAnchor(fade,3,5)==0);
 assert(raceHudAnchor(arrow,5,5)==-1&&raceHudAnchor(needle,5,5)==1);
 assert(raceHudAnchor(map,4,6)==0&&raceHudAnchor(map,3,5)==0);
 map[2]=0x7a016800;assert(raceHudAnchor(map,4,5)==-1);
 map[2]=0x7a026800;assert(raceHudAnchor(map,4,5)==0);
 map[2]=0x12346800;assert(raceHudAnchor(map,4,5)==0);
 for(int height:{240,720,1080,2160}){
  assert(hudAnchorShift(-1,height*4/3,height)==0);
  assert(hudAnchorShift(0,height*16/9,height)==0);
 }
 assert(hudAnchorShift(-1,1280,720)==-160);
 assert(hudAnchorShift(1,1920,1080)==240);
 assert(hudAnchorShift(1,3840,2160)==480);
 assert(hudAnchorShift(-1,320,300)==0);
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.cpp').write_text(source)
   subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'t.cpp'),'-o',str(p/'t')],check=True,capture_output=True)
   subprocess.run([str(p/'t')],check=True)
