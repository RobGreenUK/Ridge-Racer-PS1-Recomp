#include "presentation_mode.h"
#include "../platform/mapped_file.h"
/* Original 2D screens for the native frontend. File locks are nonblocking;
 * during racing only the header changes: no framebuffer readback is requested. */
#include "screen_protocol.h"
#include "mod_plugins.h"
#include "usa_layout.h"
#include "gpu.h"
#include "gpu_render.h"
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
extern int ridge_main_scene_active;
extern unsigned ridge_model_count;
static int fd=-1,initialized;static struct RRScreen*shared;
static char path[256];
static void close_screen(void){if(shared)munmap(shared,sizeof *shared);if(fd>=0){close(fd);unlink(path);}shared=NULL;fd=-1;}
void ridge_screen_publish(void){
    if(!initialized){
        initialized=1;const char*socket=getenv("RIDGE_SCENE_SOCKET");
        if(!socket||(!getenv("RIDGE_NATIVE_SCENE")&&!getenv("RIDGE_SCENE_SCREEN")))return;
        if(snprintf(path,sizeof path,"%s.screen",socket)>=(int)sizeof path)return;
        fd=open(path,O_RDWR|O_CREAT|O_EXCL,0600);if(fd<0)return;
        if(ftruncate(fd,sizeof(struct RRScreen))<0){close_screen();return;}
        void*p=mmap(NULL,sizeof(struct RRScreen),PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
        if(p==MAP_FAILED){close_screen();return;}shared=p;atexit(close_screen);
    }
    if(!shared||flock(fd,LOCK_EX|LOCK_NB)<0)return;
    shared->magic=RR_SCREEN_MAGIC;shared->sequence++;shared->state=ridge_main_scene_active?psx_mod_read_half(RR_STATE):0xffffffffu;
    // Replay setup has no matching scene yet. Keep its original image until
    // the first actual replay geometry sample is available.
    if(ridge_native_menu_state(shared->state))shared->state=0xffffffffu;
    if(ridge_replay_state(shared->state)&&!ridge_model_count)shared->state=0xffffffffu;
    shared->width=shared->height=0;
    if(!ridge_scene_state(shared->state)){
        GpuDisplayInfo info;gpu_get_display_info(&info);
        if(!info.disabled&&info.width&&info.width<=640&&info.height&&info.height<=512){
            if(info.depth24){
                static uint16_t raw[1024*512];unsigned words=(info.width*3+1)/2;
                gr_vram_transfer_out(info.display_x,info.display_y,words,info.height,raw);
                for(unsigned y=0;y<info.height;y++)for(unsigned x=0;x<info.width;x++){
                    uint8_t*p=(uint8_t*)(raw+y*words)+x*3;
                    shared->pixels[y*info.width+x]=0xff000000u|(uint32_t)p[0]<<16|(uint32_t)p[1]<<8|p[2];
                }
            }else gr_render_display(shared->pixels,info.width*4,info.display_x,info.display_y,info.width,info.height);
            shared->width=info.width;shared->height=info.height;
        }
    }
    flock(fd,LOCK_UN);
}
