#pragma once
#include <stdint.h>
#define RR_VRAM_MAGIC 0x31565252u
struct RRVram {uint32_t magic,sequence;uint16_t words[1024*512];};
