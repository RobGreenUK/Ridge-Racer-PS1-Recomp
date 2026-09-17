#pragma once
#include "scene_flags.h"
#include <stdint.h>
/* Local same-host IPC, versioned and fixed-size. Raw matrix avoids doing floating
 * point work in the guest thread. Datagram loss drops a visual sample, never a tick. */
#define RR_LIVE_MAGIC 0x52524c32u
struct RRLiveFrame {
    uint32_t magic,sequence;
    uint64_t cycles;
    uint32_t state,flags,track;
    int32_t camera[3],car[3],yaw;
    int16_t matrix[9];
    uint16_t reserved;
    uint64_t published_ns;
};
#ifdef __cplusplus
static_assert(sizeof(RRLiveFrame)==88,"scene IPC layout changed");
#else
_Static_assert(sizeof(struct RRLiveFrame)==88,"scene IPC layout changed");
#endif
#define RR_INPUT_MAGIC 0x52524931u
struct RRLiveInput { uint32_t magic,buttons,active,sequence; };
#include "models.h"
#define RR_MODEL_CHUNK_MAGIC 0x52524d33u
#define RR_MODEL_CHUNK_CAP 32u
struct RRModelChunk {uint32_t magic,sequence,total,offset,count;struct RRRawModel models[RR_MODEL_CHUNK_CAP];};
#define RR_MODELS_MAGIC 0x52524d32u
struct RRLiveModels {uint32_t magic,sequence,count;struct RRRawModel models[RR_MODEL_CAP];};

#include "sky_state.h"
#define RR_SKY_MAGIC 0x52525331u
struct RRLiveSky {uint32_t magic,sequence;struct RRRawSky sky;};

#include "hud.h"
#define RR_HUD_MAGIC 0x52524831u
struct RRLiveHud {uint32_t magic,sequence,count;uint32_t words[RR_HUD_CAP];};

// Menu packet streams include the animated flag's camera-space vertices. Split
// below the platform datagram limit; install only a complete matching sequence.
#define RR_MENU_HUD_MAGIC 0x52524832u
#define RR_MENU_HUD_CHUNK_CAP 512u
struct RRMenuHudChunk {uint32_t magic,sequence,total,offset,count,back_count;uint32_t words[RR_MENU_HUD_CHUNK_CAP];};
