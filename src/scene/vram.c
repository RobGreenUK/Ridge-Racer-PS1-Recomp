#include "../platform/mapped_file.h"
/* Read the runtime's CPU VRAM mirror after scene submission. No GPU readback
 * or blocking waits. Original texture uploads already update this mirror. */
#include "vram_protocol.h"
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
extern const uint16_t* gpu_get_vram(void);
static int fd=-1,initialized;static struct RRVram*shared;static char path[256];
static void cleanup(void){if(shared)munmap(shared,sizeof *shared);if(fd>=0){close(fd);unlink(path);}shared=NULL;fd=-1;}
void ridge_vram_publish(void){
    if(!initialized){
        initialized=1;const char*socket=getenv("RIDGE_SCENE_SOCKET");if(!socket)return;
        if(snprintf(path,sizeof path,"%s.vram",socket)>=(int)sizeof path)return;
        fd=open(path,O_RDWR|O_CREAT|O_EXCL,0600);if(fd<0)return;
        if(ftruncate(fd,sizeof(struct RRVram))<0){cleanup();return;}
        void*p=mmap(NULL,sizeof(struct RRVram),PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
        if(p==MAP_FAILED){cleanup();return;}shared=p;atexit(cleanup);
    }
    if(!shared||flock(fd,LOCK_EX|LOCK_NB)<0)return;
    const uint16_t*source=gpu_get_vram();
    if(source){memcpy(shared->words,source,sizeof shared->words);shared->magic=RR_VRAM_MAGIC;shared->sequence++;}
    flock(fd,LOCK_UN);
}
