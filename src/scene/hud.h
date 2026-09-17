#pragma once
#include <stdint.h>
#define RR_HUD_CAP 32768
extern uint32_t ridge_hud[RR_HUD_CAP],ridge_hud_count,ridge_hud_back_count;
extern int ridge_hud_valid;
void ridge_hud_capture(void);
