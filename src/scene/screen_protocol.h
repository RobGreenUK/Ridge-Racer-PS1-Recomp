#pragma once
#include <stdint.h>
#define RR_SCREEN_MAGIC 0x52524631u
#define RR_SCREEN_PIXELS (640*512)
struct RRScreen {uint32_t magic,sequence,width,height,state;uint32_t pixels[RR_SCREEN_PIXELS];};
