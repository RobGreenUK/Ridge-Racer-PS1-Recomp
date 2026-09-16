#pragma once
// Verified USA atlas regions containing lettering. Keep directional arrows and
// neighbouring atlas tiles reflected with the course. UV-space correction also
// handles signs split into triangles without reversing their tile order.
inline void identifyMirrorSign(MeshQuad&q,int page,uint32_t clut){
    struct Region {int page;uint32_t clut;int u0,v0,u1,v1,axis;};
    static constexpr Region regions[]={
        {24,31555,128,192,255,223,1}, // CHECK POINT
        {24,31556,128,224,255,255,1}, // checkpoint alternate panel
        {24,31553,9,202,39,222,1},   // zoomed EX animation uses a subregion
        {24,31553,0,192,127,255,1},   // rotating extended-time panel
        {24,31559,0,192,127,255,1},
        {22,31819,96,65,189,127,1},  // Starblade advert
        {22,31820,0,65,93,127,1},    // Cyber Sled advert
        {29,30862,128,16,175,39,1},  // PAC-MAN shop sign
        {29,30857,176,66,191,117,2}, // rotated RALLY NAMCO shop lettering
        {29,31311,2,146,92,158,1},   // NAMCO beneath the tunnel display
    };
    for(const auto&r:regions){
        if(page!=r.page||clut!=r.clut)continue;
        bool inside=true;float lo=256,hi=-1;
        for(const auto&v:q.v){float u=v.u*256,w=v.v*256;
            inside&=u>=r.u0&&u<=r.u1&&w>=r.v0&&w<=r.v1;
            float c=r.axis==1?u:w;lo=std::min(lo,c);hi=std::max(hi,c);
        }
        if(inside&&hi>lo){q.mirrorAxis=r.axis;q.mirrorSum=(r.axis==1?r.u0+r.u1:r.v0+r.v1)/256.f;return;}
    }
}
// The tunnel display is a composition of a background, animated presenter,
// labels and digits. Reflect the complete composition in its own plane so all
// parts stay aligned; independently flipping each patch would overlap them.
struct MirrorDisplay {
    bool active=false;Vec origin{},normal{};
    explicit MirrorDisplay(const Frame&frame){
        if(!frame.sky.mirror)return;
        for(const auto&p:frame.models)if(p.model==146){
            origin=p.position;normal={p.matrix[2],p.matrix[5],p.matrix[8]};
            float length=std::sqrt(normal.x*normal.x+normal.y*normal.y+normal.z*normal.z);
            if(length>1e-6){normal=normal*(1/length);active=true;}break;
        }
    }
    Vec reflect(Vec v)const{return v-normal*(2*(v.x*normal.x+v.y*normal.y+v.z*normal.z));}
    bool applies(const ModelPose&p)const{return active&&p.model>=145&&p.model<=164;}
    ModelPose pose(ModelPose p)const{
        p.position=origin+reflect(p.position-origin);
        for(int c=0;c<3;c++){Vec v=reflect({p.matrix[c],p.matrix[c+3],p.matrix[c+6]});p.matrix[c]=v.x;p.matrix[c+3]=v.y;p.matrix[c+6]=v.z;}
        return p;
    }
};
