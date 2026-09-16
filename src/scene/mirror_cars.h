#pragma once
// USA RenderCar's car draw sites, shared by near capture and distant-car
// reconstruction. Owner identity prevents other uses of the same models from
// being treated as vehicles. Includes the player in the external camera view.
inline bool mirrorCarPart(const Frame&frame,const ModelPose&p){
    if(!frame.sky.mirror)return false;
    uint32_t owner=uint32_t(p.key>>32),site=uint32_t(p.key);
    bool vehicle=owner==0x80080194u ||
        (owner>=0x801ece34u&&owner<0x801ece34u+12*0x114u&&(owner-0x801ece34u)%0x114u==0);
    if(!vehicle)return false;
    return site==0x80020d60u||site==0x80020db0u||site==0x80020e1cu||site==0x80020e7cu||site==0x80020eccu||site==0x80020f8cu||site==0x8002102cu;
}
inline ModelPose readableMirrorCar(ModelPose p){
    // Reflect local lateral X, retaining each part's translation, pitch, roll
    // and wheel spin. Together with the final camera-space reflection this
    // presents the original model/decals with normal handedness. Do this only
    // on the drawn copy, after interpolation; never feed it back into motion.
    p.matrix[0]=-p.matrix[0];p.matrix[3]=-p.matrix[3];p.matrix[6]=-p.matrix[6];
    return p;
}
