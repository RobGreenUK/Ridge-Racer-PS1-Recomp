#pragma once
#include <stdint.h>
// High model bit marks native world-space rotation and translation.
#define RR_MODEL_WORLD_POSE 0x80000000u
#define RR_MODEL_CAP 512
struct RRRawModel {
    uint32_t owner,model,site;
    uint32_t rotation[5];
    int32_t translation[3];
    uint32_t palette_offset; // Original a3 added to packed UV0/CLUT word.
};
extern struct RRRawModel ridge_models[RR_MODEL_CAP];
extern unsigned ridge_model_count,ridge_model_overflow;
void ridge_models_reset(void);

void ridge_models_complete(void);
void ridge_signs_complete(void);
