"""Persistent sign completion and exact original replay-index association."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class SignCaptureTests(unittest.TestCase):
 def test_live_replay_identity_and_no_guest_writes(self):
  code=r'''
#include "cpu_state.h"
#include "models.h"
#include "usa_layout.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
static unsigned char ram[0x200000],before[0x200000];
uint16_t psx_mod_read_half(uint32_t a){uint16_t v;memcpy(&v,ram+(a&0x1fffff),2);return v;}
uint32_t psx_mod_read_word(uint32_t a){uint32_t v;memcpy(&v,ram+(a&0x1fffff),4);return v;}
static void put(uint32_t a,uint32_t v){memcpy(ram+(a&0x1fffff),&v,4);}
struct RRRawModel ridge_models[RR_MODEL_CAP];unsigned ridge_model_count,ridge_model_overflow;
#include "distant_cars.h"
#include "sign_capture.h"
static void fresh(){ridge_model_count=1;memset(ridge_models,0,sizeof ridge_models);}
int main(){
 CPUState cpu={0},old=cpu;
 put(RR_STATE,1);put(0x8007878c+1024*2,4096);
 for(unsigned i=0;i<6;i++){put(0x801db7b0+i*0x38,53000+i);put(0x801db7b8+i*0x38,35000+i);}
 fresh();rr_sign_complete();assert(ridge_model_count==1);
 rr_sign_hook(&cpu,0x800397e4);memcpy(before,ram,sizeof ram);
 rr_sign_complete();assert(ridge_model_count==7);assert(!memcmp(before,ram,sizeof ram));
 for(unsigned i=1;i<7;i++){assert(ridge_models[i].owner==0x801db7b0+(i-1)*0x38);assert(ridge_models[i].model==(200|RR_MODEL_WORLD_POSE));}
 rr_sign_complete();assert(ridge_model_count==7); // no duplicates of observed parts
 cpu.gpr[4]=7;old=cpu;rr_sign_hook(&cpu,0x8002a78c);assert(!memcmp(&cpu,&old,sizeof cpu));
 put(0x801db7b0,53200);cpu.gpr[4]=8;rr_sign_hook(&cpu,0x8002a78c);
 // Live completion reflects settled records even with no original sign draws.
 fresh();rr_sign_complete();assert(ridge_models[1].translation[0]==53200*4);
 put(0x801db7b0,53900);put(RR_STATE,29);put(RR_RACE_CALLS,7);
 fresh();rr_sign_complete();assert(ridge_models[1].translation[0]==53000*4);
 put(RR_RACE_CALLS,8);fresh();rr_sign_complete();assert(ridge_models[1].translation[0]==53200*4);
 put(RR_RACE_CALLS,9);fresh();rr_sign_complete();assert(ridge_model_count==1); // no stale/future samples
 rr_sign_hook(&cpu,0x800397e4);put(RR_RACE_CALLS,7);fresh();rr_sign_complete();assert(ridge_model_count==1);
 put(RR_STATE,1);put(0x80176bf8,1);fresh();rr_sign_complete();assert(ridge_model_count==1);
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'t.c').write_text(code)
   subprocess.run(['cc','-I'+str(ROOT/'src/scene'),'-I'+str(ROOT/'psxrecomp/runtime/include'),str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True)
   subprocess.run([str(p/'t')],check=True,capture_output=True)
