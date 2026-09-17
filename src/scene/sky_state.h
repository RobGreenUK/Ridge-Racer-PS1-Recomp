#include "presentation_mode.h"
#pragma once
#include <stdint.h>
struct RRRawSky { int32_t pitch,yaw,roll;uint32_t mirror,clut,rgb,enabled; };
#ifdef RR_SKY_GUEST
static struct RRRawSky ridge_read_sky(void){
    struct RRRawSky s={0};
    s.pitch=(int32_t)psx_mod_read_word(0x801dcb94);
    s.yaw=(int32_t)psx_mod_read_word(0x801dcb98);
    s.roll=(int32_t)psx_mod_read_word(0x801dcb9c);
    s.mirror=psx_mod_read_word(0x80131050)!=0;
    int32_t index=(int16_t)psx_mod_read_half(0x8017693a);
    s.clut=(uint32_t)((index/16+480)*64+(index&15));
    if(psx_mod_read_half(0x80176bf8)&&index==98)s.clut=0x7909;
    uint32_t r,g,b;
    if(psx_mod_read_half(0x8017693c)){r=g=b=psx_mod_read_byte(0x8017692d);}
    else {r=psx_mod_read_byte(0x8017692a);g=psx_mod_read_byte(0x8017692b);b=psx_mod_read_byte(0x8017692c);}
    s.rgb=r|(g<<8)|(b<<16);s.enabled=ridge_scene_state(psx_mod_read_half(RR_STATE))&&!ridge_native_menu_state(psx_mod_read_half(RR_STATE));return s;
}
#endif
