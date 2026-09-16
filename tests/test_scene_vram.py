"""Real VRAM publisher drops locked updates and preserves source pixels."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "vram_protocol.h"
#include <assert.h>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
static uint16_t source[524288];
const uint16_t*gpu_get_vram(void){return source;}
extern void ridge_vram_publish(void);
int main(){
    source[123]=0x1234;ridge_vram_publish();
    char path[256];snprintf(path,sizeof path,"%s.vram",getenv("RIDGE_SCENE_SOCKET"));
    int fd=open(path,O_RDONLY);assert(fd>=0);
    struct RRVram*p=mmap(NULL,sizeof *p,PROT_READ,MAP_SHARED,fd,0);assert(p!=MAP_FAILED);
    assert(p->magic==RR_VRAM_MAGIC&&p->sequence==1&&p->words[123]==0x1234);
    assert(!flock(fd,LOCK_SH));source[123]=0x5678;ridge_vram_publish();
    assert(p->sequence==1&&p->words[123]==0x1234); // producer did not wait/write
    flock(fd,LOCK_UN);ridge_vram_publish();
    assert(p->sequence==2&&p->words[123]==0x5678&&source[123]==0x5678);
    munmap(p,sizeof *p);close(fd);
}
'''
class VramTests(unittest.TestCase):
    def test_nonblocking_upload_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.c').write_text(HARNESS)
            subprocess.run(['cc','-I'+str(ROOT/'src/scene'),str(p/'test.c'),str(ROOT/'src/scene/vram.c'),'-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],env=dict(os.environ,RIDGE_SCENE_SOCKET=str(p/'scene')),check=True,capture_output=True,timeout=5)
            self.assertFalse((p/'scene.vram').exists())
