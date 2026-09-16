"""Read-only car capture range, part selection and capacity at real entry hooks."""
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
#include <stdlib.h>
#include <string.h>
void ridge_scenery_reset(void){}
int ridge_scenery_owns(uint32_t site){return 0;}
void ridge_scenery_compare(const struct RRRawModel*m){}
static unsigned char ram[2097152],before_ram[2097152];
static PSXModFunctionEntryCallback callbacks[16];static uint32_t addresses[16];static unsigned count;
int psx_mod_register_function_entry_plugin(const char*id,uint32_t pc,PSXModFunctionEntryCallback cb){assert(count<16);addresses[count]=pc;callbacks[count++]=cb;return 1;}
uint16_t psx_mod_read_half(uint32_t a){uint16_t v;memcpy(&v,ram+(a&0x1fffff),2);return v;}
uint32_t psx_mod_read_word(uint32_t a){uint32_t v;memcpy(&v,ram+(a&0x1fffff),4);return v;}
void word(uint32_t a,int32_t v){memcpy(ram+(a&0x1fffff),&v,4);}
void half(uint32_t a,int16_t v){memcpy(ram+(a&0x1fffff),&v,2);}
int main(){
    unsigned owner=0x801ece34;int mult=atoi(getenv("RIDGE_SCENE_CAR_DISTANCE"));
    half(RR_STATE,1);half(owner+2,0);word(owner+36,2048);
    half(0x8007878c+1024*2,4096); // identity rotation from the original lookup format
    for(int i=0;i<9;i++)half(RR_CAMERA_MATRIX+i*2,i%4==0?4096:0);
    half(0x80056b40,19);half(0x80056b42,21);half(0x80056b46,17);half(0x80056b48,160);word(0x80176aec,319);
    CPUState cpu={0};cpu.gpr[4]=owner;cpu.gpr[31]=0x80015054;CPUState before=cpu;
    if(mult==0){
        half(owner,1);word(owner+88,1);word(owner+16,70000);
        memcpy(before_ram,ram,sizeof ram);ridge_models_complete();assert(ridge_model_count==7);
        assert(ridge_models[0].translation[0]==280000);assert(!memcmp(ram,before_ram,sizeof ram));
        ridge_models_complete();assert(ridge_model_count==7);
        ridge_models_reset();word(owner+88,0);ridge_models_complete();assert(ridge_model_count==7);
        ridge_models_reset();half(owner,0);ridge_models_complete();assert(ridge_model_count==0);return 0;
    }
    word(owner+16,3327);callbacks[0](&cpu,addresses[0]);assert(ridge_model_count==0);
    word(owner+16,3328);memcpy(before_ram,ram,sizeof ram);
    callbacks[0](&cpu,addresses[0]);assert(!memcmp(&cpu,&before,sizeof cpu));assert(!memcmp(ram,before_ram,sizeof ram));
    assert(ridge_model_count==(mult==1?0:7));
    if(mult>1){
        assert(ridge_models[0].site==0x80020d60&&ridge_models[1].site==0x80020db0);
        assert(ridge_models[2].model==21&&ridge_models[2].site==0x80020e1c);
        assert(ridge_models[0].owner==owner&&ridge_models[0].translation[0]==3328*4);
        assert(ridge_models[5].model==18&&ridge_models[6].translation[2]==160*4);
    }
    // Simplified simulation cars are omitted by the original RenderCar loop.
    // They must use their current transform, including when inside 3328 units.
    ridge_models_reset();half(owner,1);word(owner+88,0);word(owner+16,2000);
    memcpy(before_ram,ram,sizeof ram);ridge_models_complete();
    assert(ridge_model_count==(mult==1?0:7));assert(!memcmp(ram,before_ram,sizeof ram));
    ridge_models_complete();assert(ridge_model_count==(mult==1?0:7)); // idempotent
    if(mult>1)assert(ridge_models[0].translation[0]==8000);
    ridge_models_reset();word(owner+16,2100);ridge_models_complete();
    if(mult>1)assert(ridge_models[0].translation[0]==8400); // no stale pose
    ridge_models_reset();word(owner+88,1);ridge_models_complete();assert(ridge_model_count==0);
    word(owner+88,0);half(owner,0);ridge_models_complete();assert(ridge_model_count==0);
    ridge_models_reset();word(owner+16,3328*mult);callbacks[0](&cpu,addresses[0]);assert(ridge_model_count==0);
    if(mult>1){
        word(owner+16,3328*mult-1);callbacks[0](&cpu,addresses[0]);assert(ridge_model_count==7);
        ridge_models_reset();ridge_model_count=RR_MODEL_CAP-4;callbacks[0](&cpu,addresses[0]);assert(ridge_model_count==RR_MODEL_CAP-4&&ridge_model_overflow==1);
        ridge_models_reset();cpu.gpr[31]=0x80012340;callbacks[0](&cpu,addresses[0]);assert(ridge_model_count==0);
    }
}
'''
class DistantCarTests(unittest.TestCase):
    def test_range_parts_and_read_only_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.c').write_text(HARNESS)
            subprocess.run(['cc','-I'+str(ROOT/'src/scene'),'-I'+str(ROOT/'psxrecomp/runtime/include'),str(p/'test.c'),str(ROOT/'src/scene/models.c'),'-o',str(p/'test')],check=True,capture_output=True)
            for multiplier in range(0,6):
                env=dict(os.environ,RIDGE_SCENE_SOCKET='unused',RIDGE_SCENE_CAR_DISTANCE=str(multiplier));env.pop('RIDGE_SCENE_CAPTURE',None)
                subprocess.run([str(p/'test')],env=env,check=True,capture_output=True)
