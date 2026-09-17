#pragma once
#include <stdint.h>
// SCUS-94300 table 8006E7BC: race=1, post-race camera replay=5,
// recorded intro/demo replay=9 (8002AE20), music-player replay=26
// (8003CCE0), recorded post-race/lap-time replay=29 (8002B074).
// State 7 is the setup menu; 3/12 are the animated title flag. Other setup
// states retain framebuffer fallback. Keep world-only capture gated separately.
static inline int ridge_replay_state(uint32_t state){return state==5||state==9||state==26||state==29;}
static inline int ridge_menu_state(uint32_t state){return state==7;}
static inline int ridge_flag_state(uint32_t state){return state==3||state==12;}
static inline int ridge_native_menu_state(uint32_t state){return ridge_menu_state(state)||ridge_flag_state(state);}
static inline int ridge_world_state(uint32_t state){return state==1||ridge_replay_state(state);}
static inline int ridge_scene_state(uint32_t state){return ridge_world_state(state)||ridge_native_menu_state(state);}
