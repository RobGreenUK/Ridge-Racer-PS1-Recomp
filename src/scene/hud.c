#include "presentation_mode.h"
/* HUD occupies USA OT slots 702/703 (environment +0xB68/+0xB6C).
 * Copy packet words only. Bounded RAM traversal never executes guest commands. */
#include "hud.h"
#include "mod_plugins.h"
#include "usa_layout.h"
uint32_t ridge_hud[RR_HUD_CAP],ridge_hud_count;
void ridge_hud_capture(void){
    ridge_hud_count=0;if(!ridge_scene_state(psx_mod_read_half(RR_STATE)))return;
    uint32_t env=psx_mod_read_word(0x80130ea4u)&0x1fffffffu;
    if(env>0x200000u-0xb70u)return;
    // Recorded post-race results are inserted in slot 703 by 80029E10
    // (80029E54); race/music overlays use slot 702. Include the results head.
    uint32_t addr=env+(psx_mod_read_half(RR_STATE)==29?0xb6cu:0xb68u);
    for(unsigned links=0;links<512;links++){
        if((addr&0xffffffu)==0xffffffu)return;
        uint32_t phys=addr&0x1fffffffu;
        if(phys>0x1ffffcu||(phys&3))break;
        uint32_t tag=psx_mod_read_word(phys|0x80000000u),n=tag>>24;
        if(phys+4+n*4>0x200000u||ridge_hud_count+1+n>RR_HUD_CAP)break;
        if(n){ridge_hud[ridge_hud_count++]=n;for(unsigned i=0;i<n;i++)ridge_hud[ridge_hud_count++]=psx_mod_read_word(0x80000000u| (phys+4+i*4));}
        addr=tag&0xffffffu;
    }
    ridge_hud_count=0; // Invalid or cyclic list: omit overlay, retain game execution.
}
