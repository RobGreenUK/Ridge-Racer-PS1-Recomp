#pragma once
#include <stdint.h>
// SCUS-94300 table 8006E7BC: race=1, post-race camera replay=5,
// recorded intro/demo replay=9 (8002AE20), music-player replay=26
// (8003CCE0), recorded post-race/lap-time replay=29 (8002B074).
// Setup states remain framebuffer.
static inline int ridge_replay_state(uint32_t state){return state==5||state==9||state==26||state==29;}
static inline int ridge_scene_state(uint32_t state){return state==1||ridge_replay_state(state);}
