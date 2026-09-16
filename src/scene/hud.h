#pragma once
#include <stdint.h>
#define RR_HUD_CAP 2048
extern uint32_t ridge_hud[RR_HUD_CAP],ridge_hud_count;
void ridge_hud_capture(void);
