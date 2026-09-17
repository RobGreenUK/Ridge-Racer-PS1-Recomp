#include "presentation_mode.h"
#pragma once
/* Read-only USA RenderCar transform reconstruction for cars beyond its 0xd00
 * X/Z Manhattan cutoff. Uses the game's Q12 trig table and part selectors.
 * No guest calls, writes, GTE mutations or cycle accounting. */
#include <string.h>
#define RR_CAR_ORIGINAL_DISTANCE 3328
struct RRCarMatrix {int16_t v[9];};
static int rr_car_sin(int angle){
    unsigned a=(unsigned)angle&4095;int sign=a>2048?-1:1;
    if(a>2048)a=4096-a;if(a>1024)a=2048-a;
    return sign*(int16_t)psx_mod_read_half(0x8007878cu+a*2);
}
static struct RRCarMatrix rr_car_rotation(int axis,int angle){
    int s=rr_car_sin(angle),c=rr_car_sin(angle+1024);
    struct RRCarMatrix r={{4096,0,0,0,4096,0,0,0,4096}};
    int a=axis==0?1:0,b=axis==2?1:2;
    r.v[a*3+a]=r.v[b*3+b]=c;r.v[a*3+b]=-s;r.v[b*3+a]=s;return r;
}
static struct RRCarMatrix rr_car_mul(struct RRCarMatrix a,struct RRCarMatrix b){
    struct RRCarMatrix r;
    for(int i=0;i<3;i++)for(int j=0;j<3;j++){
        int64_t sum=0;for(int k=0;k<3;k++)sum+=(int32_t)a.v[i*3+k]*b.v[k*3+j];
        r.v[i*3+j]=(int16_t)(sum>>12);
    }return r;
}
static int32_t rr_car_word(uint32_t a){return (int32_t)psx_mod_read_word(a);}
static void rr_car_part(struct RRRawModel*out,uint32_t who,unsigned model,uint32_t site,struct RRCarMatrix matrix,struct RRCarMatrix camera,const int32_t position[3]){
    memset(out,0,sizeof *out);out->owner=who;out->site=site;
    unsigned count=psx_mod_read_word(0x80176aecu);out->model=model<count?model:1;
    for(int i=0;i<9;i++)out->rotation[i/2]|=(uint32_t)(uint16_t)matrix.v[i]<<((i%2)*16);
    for(int i=0;i<3;i++){
        int64_t sum=0;for(int k=0;k<3;k++)sum+=(int64_t)camera.v[i*3+k]*(position[k]-rr_car_word(RR_CAMERA_POSITION+k*4));
        out->translation[i]=(int32_t)(sum>>12)*4;
    }
}
/* At most seven parts, matching the same owner/site IDs used by normal capture. */
static unsigned rr_car_parts(uint32_t who,struct RRRawModel out[7]){
    unsigned type=psx_mod_read_half(who+2);if(type>=16)return 0;
    uint32_t table=0x80056b40u+type*16;unsigned base=psx_mod_read_half(table+6),n=0;
    struct RRCarMatrix camera;for(int i=0;i<9;i++)camera.v[i]=(int16_t)psx_mod_read_half(RR_CAMERA_MATRIX+i*2);
    struct RRCarMatrix world=rr_car_mul(rr_car_rotation(1,2048-rr_car_word(who+36)),rr_car_rotation(0,rr_car_word(who+32)));
    struct RRCarMatrix view=rr_car_mul(camera,world),body=rr_car_mul(view,rr_car_rotation(2,rr_car_word(who+40)));
    int32_t position[3];for(int i=0;i<3;i++)position[i]=rr_car_word(who+16+i*4);
    // Shadow uses ground height (+64), yaw/pitch without body roll. Both
    // half-black passes are authored at 80020D58 and 80020DA8.
    int32_t ground[3]={position[0],rr_car_word(who+64),position[2]};
    rr_car_part(&out[n++],who,base+2,0x80020d60u,view,camera,ground);
    rr_car_part(&out[n++],who,base+2,0x80020db0u,view,camera,ground);
    rr_car_part(&out[n++],who,psx_mod_read_half(table+2),0x80020e1cu,body,camera,position);
    if(type<12)rr_car_part(&out[n++],who,base,0x80020e7cu,body,camera,position);
    rr_car_part(&out[n++],who,base+3,0x80020eccu,body,camera,position);
    int spin=rr_car_word(who+56);unsigned wheel=(spin&4096)?psx_mod_read_half(table):base+1;
    struct RRCarMatrix wheels=rr_car_mul(rr_car_mul(view,rr_car_rotation(2,rr_car_word(who+40)/2)),rr_car_rotation(0,spin));
    rr_car_part(&out[n++],who,wheel,0x80020f8cu,wheels,camera,position);
    int16_t length=(int16_t)psx_mod_read_half(table+8);
    for(int i=0;i<3;i++)position[i]+=((int32_t)world.v[i*3+2]*length)>>12;
    rr_car_part(&out[n++],who,wheel,0x8002102cu,wheels,camera,position);return n;
}
static void rr_capture_car_in_range(uint32_t who,int minimum_distance){
    static int multiplier=-1;
    if(multiplier<0){const char*s=getenv("RIDGE_SCENE_CAR_DISTANCE");multiplier=s?atoi(s):0;if(multiplier<0||multiplier>5)multiplier=0;}
    int64_t dx=(int64_t)rr_car_word(who+16)-rr_car_word(RR_CAMERA_POSITION),dz=(int64_t)rr_car_word(who+24)-rr_car_word(RR_CAMERA_POSITION+8);
    int64_t distance=(dx<0?-dx:dx)+(dz<0?-dz:dz);
    if(multiplier==1||(multiplier!=0&&(distance<minimum_distance||distance>=RR_CAR_ORIGINAL_DISTANCE*multiplier)))return;
    struct RRRawModel parts[7];unsigned n=rr_car_parts(who,parts);
    if(ridge_model_count+n>RR_MODEL_CAP){ridge_model_overflow++;return;}
    memcpy(ridge_models+ridge_model_count,parts,n*sizeof parts[0]);ridge_model_count+=n;
}

static void rr_capture_distant_car(uint32_t who){const char*s=getenv("RIDGE_SCENE_CAR_DISTANCE");if(s&&atoi(s)>0)rr_capture_car_in_range(who,RR_CAR_ORIGINAL_DISTANCE);}
/* USA 8002229C switches car+58 to zero outside a progress-distance window.
 * Positions continue to update, but RaceMain omits RenderCar entirely. Fill
 * these models at publication; never wake the full AI or reuse old transforms. */
void ridge_models_complete(void){
    unsigned state=psx_mod_read_half(RR_STATE);
    if(!ridge_world_state(state))return;
    // Setup can change RR_STATE to 5 before its first 3D handler executes.
    // Do not complete cars from that boundary's old camera/entity transforms.
    if(ridge_replay_state(state)&&!ridge_model_count)return;
    for(unsigned i=0;i<RR_ENTITY_COUNT;i++){
        uint32_t who=0x801ece34u+i*RR_ENTITY_SIZE;
        if(!psx_mod_read_half(who))continue;
        const char*s=getenv("RIDGE_SCENE_CAR_DISTANCE");
        if(s&&atoi(s)!=0&&rr_car_word(who+0x58)!=0)continue;
        int captured=0;
        for(unsigned j=0;j<ridge_model_count;j++)if(ridge_models[j].owner==who){captured=1;break;}
        if(!captured)rr_capture_car_in_range(who,0);
    }
}
