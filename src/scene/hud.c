#include "presentation_mode.h"
#include "hud.h"
#include "mod_plugins.h"
#include "usa_layout.h"
#include "menu_flag.h"
uint32_t ridge_hud[RR_HUD_CAP],ridge_hud_count,ridge_hud_back_count;
int ridge_hud_valid;
/* Forward-linked USA OT starts at environment+70. Race overlays occupy
 * 702/703. Menus draw tiled backdrop at slot 0, 3D in the middle, and all
 * labels/panels at 701..703. Title flag uses the complete list. */
static int packets(uint32_t addr,uint32_t stop,int flag){
    for(unsigned links=0;links<4096;links++){
        if((addr&0xffffffu)==0xffffffu||addr==stop)return 1;
        uint32_t phys=addr&0x1fffffffu;
        if(phys>0x1ffffcu||(phys&3))return 0;
        uint32_t tag=psx_mod_read_word(phys|0x80000000u),n=tag>>24;
        int grid=flag?ridge_flag_packet(phys):-1;
        unsigned extra=grid>=0&&n==12?15:0;
        if(phys+4+n*4>0x200000u||ridge_hud_count+1+n+extra>RR_HUD_CAP)return 0;
        if(n){
            ridge_hud[ridge_hud_count++]=n+extra;
            for(unsigned i=0;i<n;i++)ridge_hud[ridge_hud_count++]=psx_mod_read_word(0x80000000u|(phys+4+i*4));
            if(extra){
                ridge_hud[ridge_hud_count-n]|=0x80000000u;
                for(unsigned i=0;i<15;i++)ridge_hud[ridge_hud_count++]=(uint32_t)ridge_flag_quads[grid].xyz[i];
            }
        }
        addr=tag&0xffffffu;
    }
    return 0;
}
void ridge_hud_capture(void){
    ridge_hud_count=ridge_hud_back_count=0;ridge_hud_valid=0;
    uint32_t state=psx_mod_read_half(RR_STATE),env=psx_mod_read_word(0x80130ea4u)&0x1fffffffu;
    if(ridge_scene_state(state)&&env<=0x200000u-0xb70u){
        if(ridge_flag_state(state))ridge_hud_valid=ridge_flag_count&&packets(env+0x70,0,1);
        else if(ridge_menu_state(state)){
            ridge_hud_valid=packets(env+0x70,env+0x74,0);ridge_hud_back_count=ridge_hud_count;
            ridge_hud_valid=ridge_hud_valid&&packets(env+0xb64,0,0);
        }else ridge_hud_valid=packets(env+(state==29?0xb6c:0xb68),0,0);
    }
    if(!ridge_hud_valid)ridge_hud_count=ridge_hud_back_count=0;
    ridge_flag_count=0;
}
