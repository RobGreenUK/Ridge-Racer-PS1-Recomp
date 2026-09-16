/* Optional read-only VRAM snapshot for validating the TMS upload interpretation.
 * In headless validation the software VRAM is authoritative, including palettes
 * selected/modified by the original game after its loaders run. */
#include "cpu_state.h"
#include "mod_plugins.h"
#include "usa_layout.h"
#include "../../psx_symbols.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
extern const uint16_t* gpu_get_vram(void);
extern uint8_t *g_psx_ram;
static void dump(CPUState*cpu,uint32_t address) {
    (void)address;static int done;
    const char*at=getenv("RIDGE_VRAM_DUMP_FRAME");unsigned frame=at?(unsigned)strtoul(at,NULL,10):300;
    if(frame<1||frame>18000)frame=300;
    if(done||cpu->gpr[31]!=RR_MAIN_AFTER_DRAWSYNC_CALL||psx_mod_read_half(RR_STATE)!=1||psx_mod_read_half(RR_RACE_CALLS)<frame)return;
    done=1;FILE*f=fopen(getenv("RIDGE_VRAM_DUMP"),"wx");
    if(!f){perror("ridge VRAM snapshot");return;}
    if(fwrite(gpu_get_vram(),2,1024*512,f)!=1024*512)perror("ridge VRAM write");
    fclose(f);
    const char*ram_path=getenv("RIDGE_RAM_DUMP");
    if(ram_path&&*ram_path){
        f=fopen(ram_path,"wx");
        if(!f){perror("ridge RAM snapshot");return;}
        if(fwrite(g_psx_ram,1,2*1024*1024,f)!=2*1024*1024)perror("ridge RAM write");
        fclose(f);
    }
}
PSX_MOD_CONSTRUCTOR(register_ridge_vram_dump) {
    const char*path=getenv("RIDGE_VRAM_DUMP");if(!path||!*path)return;
    psx_mod_register_function_entry_plugin("ridge.capture.vram",PSX_FN_DrawSync,dump);
}
