"""Read-only scenery evaluation and large-coordinate transforms without game data."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "models.h"
#include "mod_plugins.h"
#include "cpu_state.h"
#include <vector>
#include <cstring>
#include <cassert>
RRRawModel ridge_models[RR_MODEL_CAP];unsigned ridge_model_count,ridge_model_overflow;
extern "C" {unsigned char*g_psx_ram=nullptr;
int psx_mod_register_function_entry_plugin(const char*,uint32_t,PSXModFunctionEntryCallback){return 1;}
uint16_t psx_mod_read_half(uint32_t){return 0;}
int ridge_scenery_evaluate(const uint8_t*,const CPUState*,uint32_t,int,RRRawModel*,unsigned);
}
int main(){
 std::vector<uint8_t>ram(2097152);auto word=[&](unsigned a,uint32_t v){memcpy(ram.data()+(a&0x1fffff),&v,4);};
 auto half=[&](unsigned a,int16_t v){memcpy(ram.data()+(a&0x1fffff),&v,2);};
 unsigned words[]={0x3c041f80,0x34840060,0x3c058010,0x3c06801e,0x34c6cd60,0x0c004852,0,
 0x3c041f80,0x24050038,0x24060005,0x24070000,0x0c00d23a,0,0x0000f821,0x03e00008,0};
 for(unsigned i=0;i<sizeof words/4;i++)word(0x80015b90+i*4,words[i]);
 word(0x80100000,100000);for(int i=0;i<9;i++){half(0x80110000+i*2,i%4==0?4096:0);half(0x801ecd60+i*2,i%4==0?4096:0);}
 auto before=ram;CPUState cpu{},beforeCPU=cpu;RRRawModel output[8]{};
 assert(ridge_scenery_evaluate(ram.data(),&cpu,0x80015b90,1,output,8)==1);
 assert(output[0].translation[0]==400000&&output[0].model==(5|RR_MODEL_WORLD_POSE));
 // Camera translation and quantized rotation must not move a static world pose.
 word(0x801dcb84,31337);half(0x801ecd60,4000);half(0x801ecd64,700);
 assert(ridge_scenery_evaluate(ram.data(),&cpu,0x80015b90,1,output,8)==1);
 assert(output[0].translation[0]==400000&&output[0].rotation[0]==4096);
 ram=before;
 assert(ram==before&&!memcmp(&cpu,&beforeCPU,sizeof cpu));
 assert(ridge_scenery_evaluate(ram.data(),&cpu,0x80015b90,0,output,8)==1);
 assert(output[0].translation[0]==int16_t(100000)*4);
 assert(ridge_scenery_evaluate(ram.data(),&cpu,0x80015b90,1,output,0)==-1);
 word(0x80015b90,0xffffffff);assert(ridge_scenery_evaluate(ram.data(),&cpu,0x80015b90,1,output,8)==-1);
 word(0x80015b90,0x1000ffff);word(0x80015b94,0);assert(ridge_scenery_evaluate(ram.data(),&cpu,0x80015b90,1,output,8)==-1);
}
'''
class SceneryEvalTests(unittest.TestCase):
    def test_read_only_native_transforms_and_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(HARNESS)
            subprocess.run(['c++','-std=c++17','-O2','-I'+str(ROOT/'src/scene'),'-I'+str(ROOT/'psxrecomp/runtime/include'),str(p/'test.cpp'),str(ROOT/'src/scene/scenery_eval.cpp'),'-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True,capture_output=True)
