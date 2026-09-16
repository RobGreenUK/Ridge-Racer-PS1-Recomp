"""Alternate model paths preserve transforms, identity and guest CPU state."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "cpu_state.h"
#include "mod_plugins.h"
#include "usa_layout.h"
#include "models.h"
#include <assert.h>
#include <string.h>
void ridge_scenery_reset(void){}
int ridge_scenery_owns(uint32_t site){return 0;}
void ridge_scenery_compare(const struct RRRawModel*m){}
static PSXModFunctionEntryCallback callbacks[7];static uint32_t addresses[7];static unsigned count;
int psx_mod_register_function_entry_plugin(const char*id,uint32_t pc,PSXModFunctionEntryCallback cb){assert(count<7);addresses[count]=pc;callbacks[count++]=cb;return 1;}
uint16_t psx_mod_read_half(uint32_t a){assert(a==RR_STATE);return 1;}
uint32_t psx_mod_read_word(uint32_t a){return 5;}
int main(){
    assert(count==7);CPUState cpu={0};cpu.gpr[6]=63;cpu.gpr[7]=0x770000;cpu.gpr[31]=0x800159c8;
    for(int i=0;i<8;i++)cpu.gte_ctrl[i]=100+i;
    CPUState before=cpu;callbacks[2](&cpu,addresses[2]);
    assert(!memcmp(&cpu,&before,sizeof cpu));assert(ridge_model_count==1);
    assert(ridge_models[0].palette_offset==0x770000);
    assert(ridge_models[0].model==63&&ridge_models[0].owner==0&&ridge_models[0].translation[0]==105);
    cpu.gpr[31]=0x80039d44;cpu.gpr[6]=200;cpu.gpr[16]=0x801db7b0;
    callbacks[1](&cpu,addresses[1]);assert(ridge_models[1].owner==0x801db7b0);
    cpu.gpr[16]+=0x38;callbacks[1](&cpu,addresses[1]);assert(ridge_models[2].owner!=ridge_models[1].owner);
    cpu.gpr[31]=0x800397b0;cpu.gpr[17]=0x801dba80;callbacks[1](&cpu,addresses[1]);assert(ridge_models[3].owner==0x801dba80);
    cpu.gpr[6]=319;callbacks[1](&cpu,addresses[1]);assert(ridge_model_count==4);
    cpu.gpr[6]=200;
    for(int i=0;i<RR_MODEL_CAP+1;i++)callbacks[1](&cpu,addresses[1]);
    assert(ridge_model_count==RR_MODEL_CAP&&ridge_model_overflow>0);
    ridge_models_reset();assert(ridge_model_count==0&&ridge_model_overflow==0);
    cpu.gpr[4]=0x80080194;cpu.gpr[31]=0x80015054;
    // Register ownership without invoking the optional distant reconstruction.
    cpu.gpr[31]=0x80015000;callbacks[0](&cpu,addresses[0]);
    cpu.gpr[6]=3;cpu.gpr[7]=0;cpu.gpr[31]=0x80020d60;before=cpu;
    callbacks[4](&cpu,addresses[4]);assert(!memcmp(&cpu,&before,sizeof cpu));
    assert(ridge_model_count==1&&ridge_models[0].owner==0x80080194&&ridge_models[0].model==3);
    cpu.gpr[31]=0x80020db0;callbacks[4](&cpu,addresses[4]);assert(ridge_model_count==2);
    assert(ridge_models[0].site!=ridge_models[1].site);

}
'''
class ModelTests(unittest.TestCase):
    def test_alternate_paths_identity_and_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.c').write_text(HARNESS)
            subprocess.run(['cc','-I'+str(ROOT/'src/scene'),'-I'+str(ROOT/'psxrecomp/runtime/include'),str(p/'test.c'),str(ROOT/'src/scene/models.c'),'-o',str(p/'test')],check=True,capture_output=True)
            env=dict(os.environ,RIDGE_SCENE_SOCKET='unused');env.pop('RIDGE_SCENE_CAPTURE',None)
            subprocess.run([str(p/'test')],env=env,check=True,capture_output=True)
