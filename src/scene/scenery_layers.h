#pragma once
#include <cstdint>
// SCUS-94300 model 60's repeating crowd surface penetrates the grid boards.
// It is a broad authored overlap, not a nearly coplanar decal. Give its +14
// ordering bias one world unit per step (the depth renderer normally uses 1/8).
// Only this verified material/window changes; signs, supports and decals retain
// their existing separation. UVs and projected coverage remain unchanged.
inline int32_t sceneryLayerBias(unsigned model,int page,uint32_t clut,
                                uint32_t window,int32_t bias){
    return model==60&&page==26&&clut==0x7985&&window==0x40318&&bias==14
        ? bias*8 : bias;
}
