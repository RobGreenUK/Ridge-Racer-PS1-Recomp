"""Exercise real nonblocking IPC and the restricted digital input boundary."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "cpu_state.h"
#include "mod_plugins.h"
#include "live_protocol.h"
#include "usa_layout.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <assert.h>
#include <stdlib.h>
#include <string.h>
uint64_t psx_cycle_count=12345;uint32_t ridge_hud[RR_HUD_CAP],ridge_hud_count,ridge_hud_back_count;int ridge_hud_valid=1;
struct RRRawModel ridge_models[RR_MODEL_CAP];unsigned ridge_model_count=1,ridge_model_overflow;
static PSXModFunctionEntryCallback callback;static unsigned writes;static uint8_t pad[4];
int psx_mod_register_function_entry_plugin(const char*id,uint32_t pc,PSXModFunctionEntryCallback cb){assert(pc==0x8002e0bc);callback=cb;return 1;}
uint8_t psx_mod_read_byte(uint32_t a){return 0;}
uint16_t psx_mod_read_half(uint32_t a){return a==RR_STATE?1:0;}
uint32_t psx_mod_read_word(uint32_t a){return a;}
void psx_mod_write_byte(uint32_t a,uint8_t v){assert(a>=0x80176948&&a<=0x8017694b);pad[a-0x80176948]=v;writes++;}
extern void ridge_live_publish(void);
static void (*frame_hook)(void);static unsigned startup_reads;static uint16_t sio_buttons;
void mod_register_frame_hook(void (*hook)(void)){frame_hook=hook;}
void sio_set_pad_state_slot(int slot,uint16_t buttons){assert(slot==0);sio_buttons=buttons;}
void ridge_screen_publish(void){startup_reads++;}
void ridge_vram_publish(void){}
int main(void){
 if(getenv("EXPECT_DISABLED")){assert(!callback);return 0;}
 assert(callback);int fd=socket(AF_UNIX,SOCK_DGRAM,0);assert(fd>=0);
 struct sockaddr_un address={0};address.sun_family=AF_UNIX;strcpy(address.sun_path,getenv("RIDGE_SCENE_SOCKET"));
 assert(bind(fd,(struct sockaddr*)&address,sizeof address)==0);
 assert(frame_hook);frame_hook();assert(startup_reads==1&&writes==0);
 struct sockaddr_un boot=address;strcat(boot.sun_path,".pad");
 struct RRLiveInput boot_input={RR_INPUT_MAGIC,0xbfff,1,0};
 assert(sendto(fd,&boot_input,sizeof boot_input,0,(struct sockaddr*)&boot,sizeof boot)==sizeof boot_input);
 frame_hook();assert(sio_buttons==0xbfff&&writes==0);
 ridge_models[0].owner=123;ridge_models[0].model=7;ridge_models[0].palette_offset=0xffcd0000;
 ridge_live_publish();struct RRLiveFrame frame;assert(recv(fd,&frame,sizeof frame,0)==sizeof frame);
 assert(frame.published_ns>0);
 assert(frame.magic==RR_LIVE_MAGIC&&frame.cycles==12345&&frame.state==1&&frame.sequence==0);
 struct RRLiveSky sky;assert(recv(fd,&sky,sizeof sky,0)==sizeof sky);assert(sky.magic==RR_SKY_MAGIC);
 struct RRLiveHud hud;assert(recv(fd,&hud,sizeof hud,0)==12);assert(hud.magic==RR_HUD_MAGIC);
 struct RRModelChunk models;assert(recv(fd,&models,sizeof models,0)==20+sizeof(struct RRRawModel));
 assert(models.models[0].palette_offset==0xffcd0000);
 assert(models.magic==RR_MODEL_CHUNK_MAGIC&&models.count==1&&models.models[0].owner==123);
 strcat(address.sun_path,".pad");struct RRLiveInput input={RR_INPUT_MAGIC,0xbfff,1,0};
 assert(sendto(fd,&input,sizeof input,0,(struct sockaddr*)&address,sizeof address)==sizeof input);
 CPUState cpu={0};cpu.gpr[31]=0x80011ca0;CPUState before=cpu;
 callback(&cpu,0);assert(writes==4&&pad[0]==0&&pad[1]==0x41&&pad[2]==255&&pad[3]==191);
 assert(!memcmp(&before,&cpu,sizeof cpu)&&psx_cycle_count==12345);
 input.active=0;sendto(fd,&input,sizeof input,0,(struct sockaddr*)&address,sizeof address);callback(&cpu,0);assert(writes==4);
 input.active=1;sendto(fd,&input,sizeof input,0,(struct sockaddr*)&address,sizeof address);callback(&cpu,0);assert(writes==8);
 usleep(280000);callback(&cpu,0);assert(writes==8); // disconnected controls expire
 close(fd);unlink(getenv("RIDGE_SCENE_SOCKET"));
 for(int i=0;i<10000;i++)ridge_live_publish(); // absent renderer never blocks guest
 return 0;
}
'''
class LiveTests(unittest.TestCase):
    def test_nonblocking_bridge_and_input_timeout(self):
        with tempfile.TemporaryDirectory(prefix='rrtest-',dir='/tmp') as tmp:
            p=Path(tmp);(p/'test.c').write_text(HARNESS)
            subprocess.run(['cc','-I'+str(ROOT/'psxrecomp/runtime/include'),'-I'+str(ROOT/'src/scene'),str(p/'test.c'),str(ROOT/'src/scene/live.c'),'-o',str(p/'test')],check=True,capture_output=True)
            env=dict(os.environ,RIDGE_SCENE_SOCKET=str(p/'s'),RIDGE_SCENE_INPUT='1');env.pop('RIDGE_INPUT_REPLAY',None)
            subprocess.run([str(p/'test')],env=env,check=True,capture_output=True,timeout=5)
            env['EXPECT_DISABLED']='1';env.pop('RIDGE_SCENE_INPUT')
            subprocess.run([str(p/'test')],env=env,check=True,capture_output=True,timeout=5)
if __name__=='__main__':unittest.main()
