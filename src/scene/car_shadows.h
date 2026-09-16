#pragma once
// SCUS-94300 RenderCar's two flat semitransparent passes. The following
// 80020ECC part is the car underside, not a shadow.
inline bool carShadowPart(const ModelPose&p){
    uint32_t owner=uint32_t(p.key>>32),site=uint32_t(p.key);
    bool vehicle=owner==0x80080194u ||
        (owner>=0x801ece34u&&owner<0x801ece34u+12*0x114u&&(owner-0x801ece34u)%0x114u==0);
    return vehicle&&(site==0x80020d60u||site==0x80020db0u);
}
