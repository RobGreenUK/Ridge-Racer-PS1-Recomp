#pragma once
// Find the nearby road plane used for car/shadow depth compatibility.
// Authored contact poses and the visible road differ; preserve their projected
// geometry instead of relocating cars or shadows to this plane.
struct ShadowGround {
    bool valid=false;float distance=32,xSlope=0,zSlope=0,constant=0;int depthBias=0;
    float height(float x,float z)const{return xSlope*x+zSlope*z+constant;}
    void consider(Vec a,Vec b,Vec c,Vec contact){
        float det=(b.z-c.z)*(a.x-c.x)+(c.x-b.x)*(a.z-c.z);
        if(std::abs(det)<.01f)return;
        float u=((b.z-c.z)*(contact.x-c.x)+(c.x-b.x)*(contact.z-c.z))/det;
        float v=((c.z-a.z)*(contact.x-c.x)+(a.x-c.x)*(contact.z-c.z))/det;
        if(u<-.0001f||v<-.0001f||u+v>1.0001f)return;
        float y=u*a.y+v*b.y+(1-u-v)*c.y,d=std::abs(y-contact.y);
        if(d>=distance)return;
        float sx=((a.y-c.y)*(b.z-c.z)-(b.y-c.y)*(a.z-c.z))/det;
        float sz=((a.x-c.x)*(b.y-c.y)-(b.x-c.x)*(a.y-c.y))/det;
        if(std::abs(sx)>1||std::abs(sz)>1)return; // reject walls/steep scenery
        valid=true;distance=d;xSlope=sx;zSlope=sz;constant=y-sx*contact.x-sz*contact.z;
    }
};
