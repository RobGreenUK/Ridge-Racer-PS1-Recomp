#pragma once
/* USA title flag: RotTransPers3's two-column strip feeds AddPrim at
 * 80026554. Retain the original animated vertices, shading, UVs and OT order.
 * Coordinates are camera-space fixed 12; no guest geometry is recomputed or
 * modified. The native packet extends GT4 with 12 coordinate words. */
#include "cpu_state.h"
#include <stdlib.h>
static struct {uint32_t address;int32_t xyz[15];} ridge_flag_quads[560];
static unsigned ridge_flag_count;
static int32_t ridge_flag_pair[2][6];
static int ridge_flag_have_right;
static void ridge_flag_hook(CPUState*cpu,uint32_t address){
    if(!ridge_flag_state(psx_mod_read_half(RR_STATE)))return;
    uint32_t site=cpu->gpr[31];
    if(address==0x800477a4u&&(site==0x800263d4u||site==0x80026480u)){
        int pair=site==0x80026480u;
        if(!pair)ridge_flag_have_right=0;
        else{if(ridge_flag_have_right)for(unsigned k=0;k<6;k++)ridge_flag_pair[0][k]=ridge_flag_pair[1][k];ridge_flag_have_right=1;}
        for(unsigned p=0;p<2;p++){
            uint32_t ptr=cpu->gpr[4+p];int16_t v[3];
            for(unsigned k=0;k<3;k++)v[k]=(int16_t)psx_mod_read_half(ptr+2*k);
            for(unsigned r=0;r<3;r++){
                int64_t sum=(int64_t)(int32_t)cpu->gte_ctrl[5+r]*4096;
                for(unsigned c=0;c<3;c++){unsigned i=r*3+c;sum+=(int16_t)(cpu->gte_ctrl[i/2]>>((i%2)*16))*(int32_t)v[c];}
                ridge_flag_pair[pair][p*3+r]=(int32_t)sum;
            }
        }
    }
    if(address==0x80043f38u&&site==0x8002655cu){
        if(ridge_flag_count<560){
            unsigned i=ridge_flag_count++;ridge_flag_quads[i].address=cpu->gpr[5]&0x1fffffu;
            for(unsigned k=0;k<3;k++)ridge_flag_quads[i].xyz[12+k]=(int32_t)cpu->gte_ctrl[24+k];
            for(unsigned v=0;v<4;v++)for(unsigned k=0;k<3;k++)ridge_flag_quads[i].xyz[v*3+k]=ridge_flag_pair[v>>1][(v&1)*3+k];
        }
    }
    // Every new projected column becomes the previous pair even when the
    // guest clips it and never calls AddPrim. Roll it on the next projection.
}
static int ridge_flag_packet(uint32_t address){
    for(unsigned i=0;i<ridge_flag_count;i++)if(ridge_flag_quads[i].address==address)return (int)i;
    return -1;
}
PSX_MOD_CONSTRUCTOR(register_ridge_flag){
    if(!getenv("RIDGE_SCENE_CAPTURE")&&!getenv("RIDGE_SCENE_SOCKET"))return;
    psx_mod_register_function_entry_plugin("ridge.flag.vertices",0x800477a4u,ridge_flag_hook);
    psx_mod_register_function_entry_plugin("ridge.flag.packet",0x80043f38u,ridge_flag_hook);
}
