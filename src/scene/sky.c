/* Read-only capture of the original background renderer's primitive range. */
#include "cpu_state.h"
#include "mod_plugins.h"
#include "usa_layout.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
static uint32_t start;
static void sky(CPUState*cpu,uint32_t address){
    static int done;
    if(done||psx_mod_read_half(RR_STATE)!=1)return;
    if(address==0x80018358u){start=psx_mod_read_word(0x1f800000u);return;}
    if(cpu->gpr[31]!=0x800150b8u||!start)return;
    uint32_t end=psx_mod_read_word(0x1f800000u),begin=start;start=0;
    if(psx_mod_read_half(RR_RACE_CALLS)<300)return;
    if(begin<0x80000000u||end<begin||end>0x80200000u||end-begin>16384)return;
    FILE*f=fopen(getenv("RIDGE_SKY_DUMP"),"wx");if(!f)return;
    for(uint32_t a=begin;a<end;a++){uint8_t value=psx_mod_read_byte(a);fwrite(&value,1,1,f);}
    fclose(f);done=1;fprintf(stderr,"ridge sky: %u bytes at %08x\n",end-begin,begin);
}
PSX_MOD_CONSTRUCTOR(register_ridge_sky){
    const char*path=getenv("RIDGE_SKY_DUMP");if(!path||!*path)return;
    psx_mod_register_function_entry_plugin("ridge.sky.begin",0x80018358u,sky);
    psx_mod_register_function_entry_plugin("ridge.sky.end",0x8002a99cu,sky);
}
