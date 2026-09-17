#pragma once
/* Read-only completion for the six USA movable signs. Original draw visibility
 * is not durable scene state; collisions continue to use these same records. */
#define RR_SIGN_COUNT 6
#define RR_SIGN_REPLAY_CAP 1800
struct RRSignPose {int32_t position[3],pitch,yaw;};
static struct RRSignPose rr_sign_history[RR_SIGN_REPLAY_CAP][RR_SIGN_COUNT];
static unsigned char rr_sign_valid[RR_SIGN_REPLAY_CAP];
static int rr_sign_initialized;
static void rr_sign_read(struct RRSignPose out[RR_SIGN_COUNT]){
    for(unsigned i=0;i<RR_SIGN_COUNT;i++){
        uint32_t a=0x801db7b0u+i*0x38;
        for(unsigned k=0;k<3;k++)out[i].position[k]=rr_car_word(a+k*4);
        out[i].pitch=rr_car_word(a+16);out[i].yaw=rr_car_word(a+20);
    }
}
static void rr_sign_hook(CPUState*cpu,uint32_t address){
    if(address==0x800397e4u){memset(rr_sign_valid,0,sizeof rr_sign_valid);rr_sign_initialized=1;return;}
    // 8002A78C writes one 40-byte original replay record at index a0.
    // Its 1800-record limit is enforced at 8002AAC0. Follow those exact indices,
    // not wall time, lap number, or the last visible sign pose.
    unsigned index=cpu->gpr[4];
    if(!rr_sign_initialized||psx_mod_read_half(RR_STATE)!=1||index>=RR_SIGN_REPLAY_CAP)return;
    if(index==0)memset(rr_sign_valid,0,sizeof rr_sign_valid);
    rr_sign_read(rr_sign_history[index]);rr_sign_valid[index]=1;
}
static void rr_sign_complete(void){
    if(!rr_sign_initialized||psx_mod_read_half(0x80176bf8u))return; // alternate cone course
    unsigned state=psx_mod_read_half(RR_STATE);
    if(!ridge_world_state(state)||!ridge_model_count)return;
    struct RRSignPose live[RR_SIGN_COUNT];const struct RRSignPose*signs=live;
    if(state==29){
        unsigned index=psx_mod_read_half(RR_RACE_CALLS);
        if(index>=RR_SIGN_REPLAY_CAP||!rr_sign_valid[index])return;
        signs=rr_sign_history[index];
    }else rr_sign_read(live);
    for(unsigned i=0;i<RR_SIGN_COUNT;i++){
        uint32_t owner=0x801db7b0u+i*0x38;int found=0;
        for(unsigned j=0;j<ridge_model_count;j++)if(ridge_models[j].owner==owner&&ridge_models[j].site==0x80039d44u){found=1;break;}
        if(found)continue;
        if(ridge_model_count==RR_MODEL_CAP){ridge_model_overflow++;return;}
        struct RRRawModel*m=&ridge_models[ridge_model_count++];memset(m,0,sizeof *m);
        m->owner=owner;m->site=0x80039d44u;m->model=200|RR_MODEL_WORLD_POSE;
        struct RRCarMatrix r=rr_car_mul(rr_car_rotation(1,signs[i].yaw),rr_car_rotation(0,signs[i].pitch));
        for(unsigned k=0;k<9;k++)m->rotation[k/2]|=(uint32_t)(uint16_t)r.v[k]<<((k%2)*16);
        for(unsigned k=0;k<3;k++)m->translation[k]=signs[i].position[k]*4;
    }
}
