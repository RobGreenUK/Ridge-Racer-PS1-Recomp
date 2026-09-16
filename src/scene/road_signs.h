#pragma once
// USA's six movable tunnel signs. Keep this separate from static signs and
// other effects that happen to use the same mesh.
inline bool movableRoadSign(const ModelPose&p){
    uint32_t owner=uint32_t(p.key>>32);
    return p.model==200&&uint32_t(p.key)==0x80039d44u&&
        owner>=0x801db7b0u&&owner<0x801db7b0u+6*0x38u&&
        (owner-0x801db7b0u)%0x38u==0;
}
template<class Quads> inline ModelPose supportedRoadSign(ModelPose p,const Quads&quads){
    if(!movableRoadSign(p)||quads.size()>16)return p;
    // The original effect keeps its base position while rotating the sign.
    // Its ordering table conceals penetration; a real depth buffer exposes it.
    // Move only the rendered copy so the rotated mesh's lowest point remains
    // at that authored base height. Upright geometry has zero correction.
    // Positive Y points down. Preserve the rigid shape and airborne clearance.
    float below=0;
    for(const auto&q:quads)for(const auto&v:q.v){
        const auto&a=v.position;
        below=std::max(below,p.matrix[3]*a.x+p.matrix[4]*a.y+p.matrix[5]*a.z);
    }
    p.position.y-=below;
    return p;
}
