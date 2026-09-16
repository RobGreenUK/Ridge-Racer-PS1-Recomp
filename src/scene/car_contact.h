#pragma once
inline bool carSolidPart(const ModelPose&p){
    // wheelAxle validates the player/AI owner independently of the mesh ID.
    if(!wheelAxle((p.key&0xffffffff00000000ull)|0x80020f8cu))return false;
    uint32_t site=uint32_t(p.key);
    return site==0x80020e1cu||site==0x80020e7cu||site==0x80020eccu||wheelAxle(p.key);
}
// Keep the original projected car/shadow geometry. The PS1 ordering table
// permits small overlaps with the road; encode only that depth relationship.
// This is not a suspension or geometry-height adjustment.
inline Vec carRoadDepthPlane(const ShadowGround&g,const Frame&frame,Vec camera,int width,int height){
    if(!g.valid)return {};
    Vec n=rotate(frame.rotation,{-g.xSlope,1,-g.zSlope});
    if(frame.sky.mirror)n.x=-n.x;
    // Match the road's existing signed surface separation, not just its
    // un-biased mesh plane (DepthRenderer uses 1/8 unit per layer step).
    float d=g.constant+g.depthBias*.125f*std::sqrt(1+g.xSlope*g.xSlope+g.zSlope*g.zSlope)-
            (camera.y-g.xSlope*camera.x-g.zSlope*camera.z);
    if(d<=1)return {}; // camera on/below the local road plane
    float focal=height*(320.f/240),P=150000.f/(150000.f-20),Q=20*P;
    // Perspective window depth of a plane is affine in window X/Y.
    return {-Q*n.x/d/focal,-Q*n.y/d/focal,
            P-Q*n.z/d+Q*(n.x*width*.5f+n.y*height*.5f)/d/focal+g.depthBias/16777216.f};
}
