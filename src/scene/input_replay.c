/* Test-only controller packet replay. Intentionally writes ONLY the four-byte
 * SDK digital-pad packet immediately before the game decodes it. All edge,
 * steering, gear, timer and physics logic continues through the original code.
 * This is separate from the read-only capture/visual bridge. */
#include "cpu_state.h"
#include "mod_plugins.h"
#include "../../psx_symbols.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
static struct {unsigned duration;uint16_t buttons;} steps[4096];
static unsigned count,step_index,remaining;
extern uint16_t ridge_test_drive(void);
static void replay(CPUState*cpu,uint32_t address) {
    (void)address;
    if(cpu->gpr[31]!=0x80011CA0u)return;
    if(psx_mod_read_word(PSX_FN_ReadPad)!=0x3C028017u)return;
    uint16_t buttons=step_index<count?steps[step_index].buttons:0xffff;
    if(step_index>=count&&getenv("RIDGE_TEST_DRIVE"))buttons=ridge_test_drive();
    psx_mod_write_byte(0x80176948,0); // valid response
    psx_mod_write_byte(0x80176949,0x41); // digital pad
    psx_mod_write_byte(0x8017694a,buttons&255);
    psx_mod_write_byte(0x8017694b,buttons>>8);
    if(step_index<count&&--remaining==0){step_index++;if(step_index<count)remaining=steps[step_index].duration;}
}
PSX_MOD_CONSTRUCTOR(register_ridge_replay) {
    const char*path=getenv("RIDGE_INPUT_REPLAY");if(!path||!*path)return;
    FILE*f=fopen(path,"r");if(!f){perror("ridge input replay");return;}
    char line[128];unsigned duration,buttons;int invalid=0;
    while(fgets(line,sizeof line,f)) {
        if(line[0]=='#'||line[0]=='\n')continue;
        char extra;
        if(sscanf(line,"%u %x %c",&duration,&buttons,&extra)!=2||duration==0||duration>100000||buttons>65535||count==4096){invalid=1;break;}
        steps[count].duration=duration;steps[count++].buttons=(uint16_t)buttons;
    }
    fclose(f);
    if(invalid||!count){fprintf(stderr,"ridge input replay: invalid route\n");count=0;return;}
    remaining=steps[0].duration;
    fprintf(stderr,"ridge input replay: loaded %u steps\n",count);
    psx_mod_register_function_entry_plugin("ridge.replay.pad",PSX_FN_ReadPad,replay);
}
