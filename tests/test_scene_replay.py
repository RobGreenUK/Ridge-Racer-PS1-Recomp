import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "cpu_state.h"
#include "mod_plugins.h"
#include <assert.h>
#include <string.h>
#include <stdlib.h>
static unsigned char ram[0x200000];
uint16_t ridge_test_drive(void){return 0xffff;}
static PSXModFunctionEntryCallback callback;
int psx_mod_register_function_entry_plugin(const char*id,uint32_t pc,PSXModFunctionEntryCallback cb){assert(pc==0x8002e0bc);callback=cb;return 1;}
uint32_t psx_mod_read_word(uint32_t a){assert(a==0x8002e0bc);return 0x3c028017;}
void psx_mod_write_byte(uint32_t a,uint8_t v){assert(a>=0x80176948&&a<=0x8017694b);ram[a&0x1fffff]=v;}
int main(void){
 if(getenv("EXPECT_DISABLED")){assert(!callback);return 0;}assert(callback);
 CPUState cpu={0},before={0};cpu.gpr[31]=1;callback(&cpu,0x8002e0bc); // must not consume an input step
 cpu.gpr[31]=0x80011ca0;before=cpu;
 unsigned expected[]={0xfff7,0xfff7,0xffff,0xbfff,0xbfff,0xbfff,0xffff};
 for(unsigned i=0;i<7;i++){
   callback(&cpu,0x8002e0bc);assert(memcmp(&cpu,&before,sizeof cpu)==0);
   assert(ram[0x176948]==0&&ram[0x176949]==0x41);
   assert((ram[0x17694a]|(ram[0x17694b]<<8))==expected[i]);
 }
}
'''
class ReplayTests(unittest.TestCase):
    def test_packet_replay_and_disabled_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'harness.c').write_text(HARNESS);(p/'route').write_text('2 fff7\n1 ffff\n3 bfff\n')
            binary=p/'test'
            subprocess.run(['cc','-I'+str(ROOT/'psxrecomp/runtime/include'),str(p/'harness.c'),str(ROOT/'src/scene/input_replay.c'),'-o',str(binary)],check=True,capture_output=True)
            env=dict(os.environ,RIDGE_INPUT_REPLAY=str(p/'route'))
            subprocess.run([str(binary)],env=env,check=True,capture_output=True)
            env.pop('RIDGE_INPUT_REPLAY');env['EXPECT_DISABLED']='1'
            subprocess.run([str(binary)],env=env,check=True,capture_output=True)
            (p/'bad').write_text('0 ffff\n');env['RIDGE_INPUT_REPLAY']=str(p/'bad')
            subprocess.run([str(binary)],env=env,check=True,capture_output=True)
if __name__=='__main__':unittest.main()
