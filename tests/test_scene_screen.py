"""Menu readback is skipped during racing and never waits on the consumer."""
from pathlib import Path
import os,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
SOURCE=r'''
#include "screen_protocol.h"
#include "gpu.h"
#include "usa_layout.h"
#include <sys/file.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
int ridge_main_scene_active;unsigned ridge_model_count=1;
static int state=1,reads;
uint16_t psx_mod_read_half(uint32_t a){assert(a==RR_STATE);return state;}
void gpu_get_display_info(GpuDisplayInfo*i){*i=(GpuDisplayInfo){0};i->width=320;i->height=240;}
int gr_render_display(uint32_t*p,int pitch,int x,int y,int w,int h){reads++;p[0]=0xff123456;return w*h;}
void gr_vram_transfer_out(int x,int y,int w,int h,uint16_t*p){assert(0);}
extern void ridge_screen_publish(void);
int main(){
 ridge_screen_publish();assert(reads==1);char path[256];snprintf(path,sizeof path,"%s.screen",getenv("RIDGE_SCENE_SOCKET"));
 int fd=open(path,O_RDONLY);assert(fd>=0);struct RRScreen*copy=malloc(sizeof *copy);assert(read(fd,copy,sizeof *copy)==sizeof *copy);assert(copy->magic==RR_SCREEN_MAGIC&&copy->width==320&&copy->pixels[0]==0xff123456);
 ridge_main_scene_active=1;state=1;ridge_screen_publish();assert(reads==1); // no GPU readback in race
 assert(flock(fd,LOCK_SH|LOCK_NB)==0);state=0;ridge_screen_publish();assert(reads==1); // consumer holds lock: drop update
 flock(fd,LOCK_UN);ridge_screen_publish();assert(reads==2);
 state=5;ridge_screen_publish();assert(reads==2);
 ridge_model_count=0;ridge_screen_publish();assert(reads==3); // replay setup fallback
 close(fd);free(copy);
}
'''
class ScreenTests(unittest.TestCase):
 def test_menu_only_nonblocking_readback(self):
  with tempfile.TemporaryDirectory(prefix='rrscreen-',dir='/tmp') as tmp:
   p=Path(tmp);(p/'t.c').write_text(SOURCE)
   subprocess.run(['cc','-I'+str(ROOT/'src/scene'),'-I'+str(ROOT/'psxrecomp/runtime/include'),str(p/'t.c'),str(ROOT/'src/scene/screen.c'),'-o',str(p/'t')],check=True,capture_output=True)
   subprocess.run([str(p/'t')],env=dict(os.environ,RIDGE_SCENE_SOCKET=str(p/'s'),RIDGE_SCENE_SCREEN='1'),check=True,capture_output=True,timeout=5)
if __name__=='__main__':unittest.main()
