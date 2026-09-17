"""Synthetic title-strip capture: topology, GTE transform, bounded packets; no disc."""
from pathlib import Path
import os, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
SOURCE=r'''
#include "cpu_state.h"
#include "mod_plugins.h"
#include <assert.h>
#include <string.h>
static unsigned char ram[0x200000],scratch[1024],before[0x200000];
static unsigned char *ptr(uint32_t a){return (a&0xfffffc00u)==0x1f800000u?scratch+(a&1023):ram+(a&0x1fffff);}
uint16_t psx_mod_read_half(uint32_t a){uint16_t v;memcpy(&v,ptr(a),2);return v;}
uint32_t psx_mod_read_word(uint32_t a){uint32_t v;memcpy(&v,ptr(a),4);return v;}
int psx_mod_register_function_entry_plugin(const char*id,uint32_t pc,PSXModFunctionEntryCallback cb){return 1;}
#include "hud.c"
static void put(uint32_t a,uint32_t v){memcpy(ptr(a),&v,4);}
static void vertex(uint32_t a,int16_t x,int16_t y,int16_t z){int16_t v[4]={x,y,z,0};memcpy(ptr(a),v,8);}
int main(){
 put(RR_STATE,3);put(0x80130ea4,0x80010000);put(0x10070,0x20000);put(0x20000,0x0cffffff);put(0x20004,0x3c808080);
 CPUState cpu={0};cpu.gte_ctrl[0]=cpu.gte_ctrl[2]=cpu.gte_ctrl[4]=4096;cpu.gte_ctrl[5]=10;cpu.gte_ctrl[7]=300;
 cpu.gte_ctrl[24]=160*65536;cpu.gte_ctrl[25]=120*65536;cpu.gte_ctrl[26]=320;
 cpu.gpr[4]=0x1f800068;cpu.gpr[5]=0x1f800070;
 vertex(cpu.gpr[4],-40,0,0);vertex(cpu.gpr[5],-40,20,0);cpu.gpr[31]=0x800263d4;ridge_flag_hook(&cpu,0x800477a4);
 vertex(cpu.gpr[4],0,2,1);vertex(cpu.gpr[5],0,22,1);cpu.gpr[31]=0x80026480;ridge_flag_hook(&cpu,0x800477a4);
 cpu.gpr[5]=0x80020000;cpu.gpr[31]=0x8002655c;
 CPUState saved=cpu;memcpy(before,ram,sizeof ram);ridge_flag_hook(&cpu,0x80043f38);ridge_hud_capture();
 assert(!memcmp(before,ram,sizeof ram)&&!memcmp(&saved,&cpu,sizeof cpu));
 assert(ridge_hud_valid&&ridge_hud_count==28&&ridge_hud[0]==27&&ridge_hud[1]==0xbc808080);
 // Original GT4 is a vertical strip: left top/bottom, right top/bottom.
 assert((int32_t)ridge_hud[13]==-30*4096&&ridge_hud[14]==0&&ridge_hud[15]==300*4096);
 assert((int32_t)ridge_hud[16]==-30*4096&&ridge_hud[17]==20*4096);
 assert(ridge_hud[19]==10*4096&&ridge_hud[20]==2*4096&&ridge_hud[21]==301*4096);
 assert(ridge_hud[22]==10*4096&&ridge_hud[23]==22*4096&&ridge_hud[27]==320);
 ridge_hud_capture();assert(!ridge_hud_valid&&ridge_hud_count==0); // no stale grid
 // Clipped columns still advance the pair for the next submitted primitive.
 cpu.gpr[4]=0x1f800068;cpu.gpr[5]=0x1f800070;cpu.gpr[31]=0x80026480;
 vertex(cpu.gpr[4],40,4,2);vertex(cpu.gpr[5],40,24,2);ridge_flag_hook(&cpu,0x800477a4);
 vertex(cpu.gpr[4],80,6,3);vertex(cpu.gpr[5],80,26,3);ridge_flag_hook(&cpu,0x800477a4);
 cpu.gpr[5]=0x80020000;cpu.gpr[31]=0x8002655c;ridge_flag_hook(&cpu,0x80043f38);ridge_hud_capture();
 assert(ridge_hud[13]==50*4096&&ridge_hud[19]==90*4096);
 put(RR_STATE,1);ridge_flag_hook(&cpu,0x80043f38);assert(ridge_flag_count==0);
}
'''
class MenuFlagTests(unittest.TestCase):
 def test_capture_geometry_without_mutating_game(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.c').write_text(SOURCE)
   subprocess.run(['cc','-I'+str(ROOT/'src/scene'),'-I'+str(ROOT/'psxrecomp/runtime/include'),str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True)
   subprocess.run([str(p/'test')],check=True,capture_output=True)
 def test_bundled_commands_keep_extended_grid_packet(self):
  source=r'''
#include "gp0_commands.h"
#include <cassert>
int main(){
 std::vector<uint32_t> p={4,0xe1000005,0x600000ff,0,0x00010001,27,0xbc808080};p.resize(33,0);
 auto s=splitDrawingCommands(p);assert(s.size()==34&&s[0]==1&&s[2]==3&&s[6]==27&&s[7]==0xbc808080);
 p.pop_back();s=splitDrawingCommands(p);assert(s.size()==6); // truncated data rejected
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.cpp').write_text(source)
   subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),'-o',str(p/'test')],check=True,capture_output=True)
   subprocess.run([str(p/'test')],check=True,capture_output=True)
