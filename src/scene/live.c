/* Loss-tolerant read-only visual bridge. Nonblocking local datagrams keep an
 * absent or slow viewer from delaying simulation. Opt-in via RIDGE_SCENE_SOCKET. */
#include "mod_plugins.h"
#include "usa_layout.h"
#define RR_SKY_GUEST
#include "live_protocol.h"
#include "cpu_state.h"
#include "../../psx_symbols.h"
#include "usa_layout.h"
#include "mod_plugins.h"
#include "psx_cycles.h"
#include "sio.h"
#include "../platform/transport.h"
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <time.h>
#include <stddef.h>
extern void ridge_screen_publish(void);
extern void mod_register_frame_hook(void (*hook)(void));
/* Set only at the revision-verified main scene boundary; boot RAM is not a
 * reliable presentation classifier. */
int ridge_main_scene_active;
extern void ridge_vram_publish(void);
static RRSocket socket_fd=RR_INVALID_SOCKET;
static int initialized;
static RRAddress destination;
static uint32_t sequence;
static int input_bound;
static char input_path[512];
static void cleanup(void){if(socket_fd!=RR_INVALID_SOCKET)rr_socket_close(socket_fd);if(input_bound)remove(input_path);socket_fd=RR_INVALID_SOCKET;}
static void initialize(void) {
    if(!initialized) {
        initialized=1;const char*path=getenv("RIDGE_SCENE_SOCKET");
        if(!path||!*path)return;
        if(rr_address(&destination,path))return;
        socket_fd=rr_socket();
        if(socket_fd==RR_INVALID_SOCKET)return;
        if(rr_buffer(socket_fd,SO_SNDBUF,262144)||rr_nonblocking(socket_fd)){cleanup();return;}
        const char*control=getenv("RIDGE_SCENE_INPUT");
        if(control&&strcmp(control,"1")==0&&strlen(path)+4<sizeof input_path){
            snprintf(input_path,sizeof input_path,"%s.pad",path);
            if(rr_bind(socket_fd,input_path)==0)input_bound=1;
            else fprintf(stderr,"ridge live: input socket unavailable; original controls retained\n");
        }
        atexit(cleanup);
    }
}
void ridge_live_publish(void) {
    initialize();
    ridge_main_scene_active=1;
    if(socket_fd==RR_INVALID_SOCKET)return;
    ridge_screen_publish();
    ridge_vram_publish();
    struct RRLiveFrame f={0};f.magic=RR_LIVE_MAGIC;f.sequence=sequence++;
    f.cycles=psx_cycle_count;f.state=psx_mod_read_half(RR_STATE);
    f.flags=psx_mod_read_half(RR_PHASE)|(uint32_t)psx_mod_read_half(RR_PAUSED)<<16;
    // Replay camera selector and target are the actual arguments at 8003D568.
    // Changes cut interpolation even for same-position orientation switches.
    // State 26 uses the same selector/target arguments at 8003D1E8.
    if(f.state==5||f.state==26)f.flags|=RR_SCENE_REPLAY|
        ((psx_mod_read_word(0x801dae48u)&15u)<<20)|
        ((psx_mod_read_word(0x80176ad0u)&15u)<<24);
    // 8002AF74..AFA8 selects camera 1 for demo ticks 1..74, else 0;
    // target is always RR_PLAYER. Preserve this authored cut independently
    // of the state-5 selector globals, which are stale during state 9.
    // State 29 repeats this recorded-player camera selection at 8002B224.
    if(f.state==9||f.state==29){unsigned tick=psx_mod_read_half(0x80176ae4u);
        f.flags|=RR_SCENE_REPLAY|((tick>0&&tick<75?1u:0u)<<20);}
    if(psx_mod_read_half(RR_NIGHT_STATE))f.flags|=RR_SCENE_NIGHT;
    if(ridge_native_menu_state(f.state))f.flags=RR_SCENE_MENU | (f.state<<24) | (psx_mod_read_half(0x801dafe0u)<<20) | psx_mod_read_half(0x801ecbe4u);
    f.track=psx_mod_read_word(RR_TRACK_POINTER);
    for(unsigned i=0;i<3;i++) {
        f.camera[i]=(int32_t)psx_mod_read_word(RR_CAMERA_POSITION+i*4);
        f.car[i]=(int32_t)psx_mod_read_word(RR_PLAYER+16+i*4);
    }
    f.yaw=(int32_t)psx_mod_read_word(RR_PLAYER+36);
    for(unsigned i=0;i<9;i++)f.matrix[i]=(int16_t)psx_mod_read_half(RR_CAMERA_MATRIX+i*2);
    f.published_ns=rr_clock_ns();
    (void)rr_send(socket_fd,&f,sizeof f,&destination);
    struct RRLiveSky sky={RR_SKY_MAGIC,f.sequence,ridge_read_sky()};
    (void)rr_send(socket_fd,&sky,sizeof sky,&destination);
    if(ridge_native_menu_state(f.state)){
        if(ridge_hud_valid)for(unsigned offset=0;;offset+=RR_MENU_HUD_CHUNK_CAP){
            struct RRMenuHudChunk h={0};h.magic=RR_MENU_HUD_MAGIC;h.sequence=f.sequence;
            h.total=ridge_hud_count;h.offset=offset;h.back_count=ridge_hud_back_count;
            h.count=h.total-offset;if(h.count>RR_MENU_HUD_CHUNK_CAP)h.count=RR_MENU_HUD_CHUNK_CAP;
            memcpy(h.words,ridge_hud+offset,h.count*4);
            (void)rr_send(socket_fd,&h,24+h.count*4,&destination);
            if(offset+h.count>=h.total)break;
        }
    }else{
        struct RRLiveHud hud={0};hud.magic=RR_HUD_MAGIC;hud.sequence=f.sequence;hud.count=ridge_hud_count;
        memcpy(hud.words,ridge_hud,ridge_hud_count*4);
        (void)rr_send(socket_fd,&hud,12+ridge_hud_count*4,&destination);
    }
    for(unsigned offset=0;;offset+=RR_MODEL_CHUNK_CAP){
        struct RRModelChunk chunk={0};chunk.magic=RR_MODEL_CHUNK_MAGIC;chunk.sequence=f.sequence;
        chunk.total=ridge_model_count;chunk.offset=offset;
        chunk.count=ridge_model_count-offset; if(chunk.count>RR_MODEL_CHUNK_CAP)chunk.count=RR_MODEL_CHUNK_CAP;
        memcpy(chunk.models,ridge_models+offset,chunk.count*sizeof chunk.models[0]);
        (void)rr_send(socket_fd,&chunk,offsetof(struct RRModelChunk,models)+chunk.count*sizeof chunk.models[0],&destination);
        if(offset+chunk.count>=ridge_model_count)break;
    }
}

static uint64_t monotonic_ns(void){return rr_clock_ns();}
static uint16_t buttons=0xffff;
static int poll_input(void) {
    if(!input_bound)return 0;
    static uint64_t received;static int active;
    struct RRLiveInput message;
    for(int i=0;i<128;i++) {
        int n=rr_receive(socket_fd,&message,sizeof message);if(n<0)break;
        if(n!=sizeof message||message.magic!=RR_INPUT_MAGIC||message.buttons>65535)continue;
        received=monotonic_ns();buttons=(uint16_t)message.buttons;active=message.active!=0;
    }
    return active&&monotonic_ns()-received<=250000000;
}
static void startup_frame(void) {
    initialize();
    if(ridge_main_scene_active)return;
    ridge_screen_publish();
    // This runtime hook runs after normal input sampling, before guest resumes.
    // Feed the emulated controller, never the main game's uninitialized RAM.
    if(poll_input())sio_set_pad_state_slot(0,buttons);
}
static void input(CPUState*cpu,uint32_t address) {
    (void)address;
    if(cpu->gpr[31]!=0x80011CA0u||!poll_input())return;
    // Same verified digital packet boundary as the test replay. Simulation
    // computes held/rising-edge state itself; no gameplay fields are written.
    psx_mod_write_byte(0x80176948,0);psx_mod_write_byte(0x80176949,0x41);
    psx_mod_write_byte(0x8017694a,buttons&255);psx_mod_write_byte(0x8017694b,buttons>>8);
}
PSX_MOD_CONSTRUCTOR(register_ridge_live_input) {
    if(getenv("RIDGE_SCENE_SOCKET"))mod_register_frame_hook(startup_frame);
    const char*enable=getenv("RIDGE_SCENE_INPUT");
    if(enable&&strcmp(enable,"1")==0&&!getenv("RIDGE_INPUT_REPLAY"))
        psx_mod_register_function_entry_plugin("ridge.live.input",PSX_FN_ReadPad,input);
}
