/* Read-only scene boundary for the native renderer and optional JSONL capture.
 * Enabled by RIDGE_SCENE_SOCKET or RIDGE_SCENE_CAPTURE. Never writes CPU, RAM
 * or guest clocks; input forwarding is a separate opt-in adapter. */
#include "cpu_state.h"
#include "mod_plugins.h"
#include "psx_cycles.h"
#include "../../psx_symbols.h"
#include "usa_layout.h"
#include "models.h"
#include "hud.h"
#define RR_SKY_GUEST
#include "sky_state.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <time.h>

extern void ridge_live_publish(void);
static FILE *output;
static unsigned sequence, race_entries, car_entries, sim_entries;
static uint32_t last_car, track_pointer;
static unsigned limit = 1800;
static int closed, verified;

static void finish(void) {
    if (output) {
        fclose(output);
        output = NULL;
    }
    closed = 1;
}

static void bytes(uint32_t address, unsigned length) {
    static const char hex[] = "0123456789abcdef";
    fputc('"', output);
    for (unsigned i = 0; i < length; ++i) {
        uint8_t v = psx_mod_read_byte(address + i);
        fputc(hex[v >> 4], output); fputc(hex[v & 15], output);
    }
    fputc('"', output);
}

static void capture(CPUState *cpu, uint32_t address) {
    if (verified < 0) return;
    if (address == PSX_FN_RaceMain) { ++race_entries; return; }
    if (address == PSX_FN_CarUpdateCandidate) {
        ++car_entries; last_car = cpu->gpr[4]; return;
    }
    if (address == PSX_FN_CarSimulateCandidate) { ++sim_entries; return; }
    /* DrawSync has many callers. Only this return address is the outer loop,
     * after the scene handler has completed and before the wait/submission. */
    if (cpu->gpr[31] != RR_MAIN_AFTER_DRAWSYNC_CALL) return;
    if (!verified) {
        if (psx_mod_read_word(PSX_FN_RaceMain) != 0x27BDFFD0u ||
            psx_mod_read_word(PSX_FN_CarSimulateCandidate) != 0x27BDFFB8u ||
            psx_mod_read_word(0x80013338u) != 0x34020180u) {
            fprintf(stderr, "ridge scene: unsupported loaded code; capture disabled\n");
            verified = -1; finish(); return;
        }
        verified = 1;
    }
    ridge_hud_capture();
    ridge_models_complete();
    ridge_signs_complete();
    ridge_live_publish();
    const char *capture_path = getenv("RIDGE_SCENE_CAPTURE");
    if (closed || !capture_path || !*capture_path) {ridge_models_reset(); return;}
    /* Open lazily after BIOS/loader has handed off to this game's main loop.
     * Exclusive creation prevents silently replacing an earlier capture. */
    if (!output) {
        output = fopen(getenv("RIDGE_SCENE_CAPTURE"), "wx");
        if (!output) { perror("ridge scene capture"); closed = 1; return; }
        setvbuf(output, NULL, _IOFBF, 256 * 1024);
        fprintf(output, "{\"type\":\"header\",\"version\":1,\"exe_sha256\":\"bde353330bf4032d8c4b86a04dbcc78c95e6b2c5aa17dc15b79de613b52cf8c5\",\"boundary\":\"main_after_scene\"}\n");
        fprintf(stderr, "ridge scene: capturing up to %u scene boundaries\n", limit);
    }
    uint32_t pointer = psx_mod_read_word(RR_TRACK_POINTER);
    unsigned count = psx_mod_read_word(RR_TRACK_COUNT);
    if (pointer != track_pointer &&
        ((pointer == 0x80057D64u && count == 256) ||
         (pointer == 0x80059164u && count == 256) ||
         (pointer == 0x8005A564u && count == 368))) {
        fprintf(output, "{\"type\":\"track\",\"address\":%u,\"count\":%u,\"data\":", pointer, count);
        bytes(pointer, count * 20); fputs("}\n", output);
        track_pointer = pointer;
    }
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    uint64_t ns = (uint64_t)now.tv_sec * 1000000000u + (uint64_t)now.tv_nsec;
    fprintf(output, "{\"type\":\"frame\",\"sequence\":%u,\"host_ns\":%" PRIu64
            ",\"cycles\":%" PRIu64 ",\"loop\":%u,\"state\":%u,\"phase\":%u,\"paused\":%u,"
            "\"wait_scale\":%u,\"pad\":%u,\"race_counter\":%u,\"race_entries\":%u,"
            "\"car_entries\":%u,\"sim_entries\":%u,\"last_car\":%u,\"track\":%u,\"mirror_x\":%d,",
            sequence++, ns, psx_cycle_count, psx_mod_read_half(RR_LOOP),
            psx_mod_read_half(RR_STATE), psx_mod_read_half(RR_PHASE), psx_mod_read_half(RR_PAUSED),
            psx_mod_read_half(RR_WAIT_SCALE), psx_mod_read_half(RR_PAD),
            psx_mod_read_half(RR_RACE_CALLS), race_entries, car_entries, sim_entries,
            last_car, pointer, (int32_t)psx_mod_read_word(RR_TRACK_MIRROR_X));
    fprintf(output,"\"replay_camera\":%u,\"replay_target\":%u,",psx_mod_read_word(0x801dae48u),psx_mod_read_word(0x80176ad0u));
    fprintf(output,"\"night\":%u,",psx_mod_read_half(RR_NIGHT_STATE)!=0);
    fputs("\"player\":", output); bytes(RR_PLAYER, RR_ENTITY_SIZE);
    fputs(",\"camera_position\":", output); bytes(RR_CAMERA_POSITION, 32);
    fputs(",\"camera_matrix\":", output); bytes(RR_CAMERA_MATRIX, 32);
    fputs(",\"road_signs\":", output); bytes(0x801db7acu, 6*0x38);
    fputs(",\"entities\":", output); bytes(RR_ENTITIES, RR_ENTITY_SIZE * RR_ENTITY_COUNT);
    fprintf(output,",\"model_overflow\":%u,\"models\":[",ridge_model_overflow);
    for(unsigned i=0;i<ridge_model_count;i++) {
        const struct RRRawModel*m=&ridge_models[i];
        fprintf(output,"%s{\"owner\":%u,\"model\":%u,\"site\":%u,\"palette_offset\":%u,\"rotation\":[%u,%u,%u,%u,%u],\"translation\":[%d,%d,%d]}",
            i?",":"",m->owner,m->model,m->site,m->palette_offset,m->rotation[0],m->rotation[1],m->rotation[2],m->rotation[3],m->rotation[4],m->translation[0],m->translation[1],m->translation[2]);
    }
    fputs("],\"hud\":[",output);for(unsigned i=0;i<ridge_hud_count;i++)fprintf(output,"%s%u",i?",":"",ridge_hud[i]);
    struct RRRawSky sky=ridge_read_sky();
    fprintf(output,"],\"sky\":[%d,%d,%d,%u,%u,%u,%u]}\n",sky.pitch,sky.yaw,sky.roll,sky.mirror,sky.clut,sky.rgb,sky.enabled);ridge_models_reset();
    if (sequence % 30 == 0) fflush(output);
    if (ferror(output) || sequence >= limit) finish();
}

PSX_MOD_CONSTRUCTOR(register_ridge_capture) {
    const char *path = getenv("RIDGE_SCENE_CAPTURE");
    const char *live = getenv("RIDGE_SCENE_SOCKET");
    if ((!path || !*path) && (!live || !*live)) return;
    const char *setting = getenv("RIDGE_SCENE_CAPTURE_FRAMES");
    if (setting && *setting) {
        char *end;
        unsigned long n = strtoul(setting, &end, 10);
        if (*end || n < 1 || n > 18000) {
            fprintf(stderr, "ridge scene: frame limit must be 1..18000\n");
            return;
        }
        limit = (unsigned)n;
    }
    atexit(finish);
    psx_mod_register_function_entry_plugin("ridge.capture.race", PSX_FN_RaceMain, capture);
    psx_mod_register_function_entry_plugin("ridge.capture.car", PSX_FN_CarUpdateCandidate, capture);
    psx_mod_register_function_entry_plugin("ridge.capture.sim", PSX_FN_CarSimulateCandidate, capture);
    psx_mod_register_function_entry_plugin("ridge.capture.scene", PSX_FN_DrawSync, capture);
}
