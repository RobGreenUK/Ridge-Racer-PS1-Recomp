#include "presentation_mode.h"
#include "models.h"
#include "mod_plugins.h"
#include "cpu_state.h"
#include "usa_layout.h"
#include "../../psx_symbols.h"
#include <stdlib.h>
#include <stdio.h>
struct RRRawModel ridge_models[RR_MODEL_CAP];
unsigned ridge_model_count,ridge_model_overflow;
#include "distant_cars.h"
#include "sign_capture.h"
void ridge_signs_complete(void){rr_sign_complete();}
extern void ridge_scenery_reset(void);
extern int ridge_scenery_owns(uint32_t);
extern void ridge_scenery_compare(const struct RRRawModel*);
static uint32_t owner;
void ridge_models_reset(void){ridge_scenery_reset();ridge_model_count=0;ridge_model_overflow=0;owner=0;}
static void capture_model(CPUState*cpu,uint32_t address) {
    if(!ridge_scene_state(psx_mod_read_half(RR_STATE))||ridge_flag_state(psx_mod_read_half(RR_STATE)))return;
    const int menu=ridge_menu_state(psx_mod_read_half(RR_STATE));
    if(address==PSX_FN_RenderCar){owner=cpu->gpr[4];if(cpu->gpr[31]==0x80015054u)rr_capture_distant_car(owner);return;}
    // Verified car calls have owner identity. Other scene-model calls use
    // static world transforms until their animation/identity semantics are mapped.
    uint32_t site=cpu->gpr[31];
    int car=site>=PSX_FN_RenderCar&&site<0x80021040;
    int scenery=site>=0x80012000&&site<0x80017150;
    int effects=site>=0x80038A30&&site<0x80039D60;
    if((menu?(site!=0x80012310u&&site!=0x80012394u):(!car&&!scenery&&!effects))||(car&&!owner)||cpu->gpr[6]>=319)return;
    static int logged;
    if(!logged&&getenv("RIDGE_SCENE_CAPTURE")){fprintf(stderr,"ridge model context: depth shift=%u\n",psx_mod_read_word(cpu->gpr[5]+32));logged=1;}
    if(ridge_model_count==RR_MODEL_CAP){ridge_model_overflow++;return;}
    struct RRRawModel*m=&ridge_models[ridge_model_count++];
    m->owner=menu?ridge_model_count:(car?owner:0);
    // USA effect callers retain their stable object record in these registers.
    if(site==0x80039694u||site==0x800397B0u)m->owner=cpu->gpr[17];
    if(site==0x80039D44u)m->owner=cpu->gpr[16];
    if(site==0x80038B7Cu||site==0x80038C00u)m->owner=cpu->gpr[19];
    if(site==0x80039094u||site==0x800390DCu)m->owner=cpu->gpr[17];
    m->model=cpu->gpr[6];m->site=site;m->palette_offset=cpu->gpr[7];
    for(int i=0;i<5;i++)m->rotation[i]=cpu->gte_ctrl[i];
    for(int i=0;i<3;i++)m->translation[i]=(int32_t)cpu->gte_ctrl[5+i];
    if(scenery&&!menu){ridge_scenery_compare(m);if(ridge_scenery_owns(site))ridge_model_count--;}
}
PSX_MOD_CONSTRUCTOR(register_ridge_models) {
    if(!getenv("RIDGE_SCENE_CAPTURE")&&!getenv("RIDGE_SCENE_SOCKET"))return;
    psx_mod_register_function_entry_plugin("ridge.models.owner",PSX_FN_RenderCar,capture_model);
    psx_mod_register_function_entry_plugin("ridge.models.geometry",PSX_FN_RenderModel,capture_model);
    psx_mod_register_function_entry_plugin("ridge.models.subdivided",PSX_FN_RenderModelSubdivided,capture_model);
    psx_mod_register_function_entry_plugin("ridge.models.clipped",PSX_FN_RenderModelClipped,capture_model);
    // USA RenderCar calls the flat semitransparent model routine twice for
    // its ground shadow (return sites 80020D60/80020DB0).
    psx_mod_register_function_entry_plugin("ridge.models.shadow",0x800372b0u,capture_model);
    psx_mod_register_function_entry_plugin("ridge.signs.reset",0x800397e4u,rr_sign_hook);
    psx_mod_register_function_entry_plugin("ridge.signs.record",0x8002a78cu,rr_sign_hook);
}
