"""Actual OpenGL depth/decals and SDL state interoperability on this Mac."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include <SDL3/SDL.h>
#include <vector>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <algorithm>
#include <cassert>
#include "timeline.h"
using namespace ridge;
#include "geometry.h"
#include "depth_renderer.h"
#include "scenery_layers.h"
struct Face{uint32_t texture;int32_t bias;std::vector<MeshVertex>vertices;bool shadow=false;Vec contactPlane{};};
void quad(std::vector<Face>&f,int texture,int bias,float radius,float z){
    MeshVertex a{{-radius,-radius,z},0,0},b{{radius,-radius,z},1,0},c{{-radius,radius,z},0,1},d{{radius,radius,z},1,1};
    f.push_back({uint32_t(texture),bias,{a,b,c}});f.push_back({uint32_t(texture),bias,{c,b,d}});
}
int main(){
    assert(SDL_Init(SDL_INIT_VIDEO));
    auto*w=SDL_CreateWindow("depth regression",64,64,SDL_WINDOW_HIDDEN);
    auto*r=SDL_CreateRenderer(w,"opengl");assert(r);
    auto*target=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA8888,SDL_TEXTUREACCESS_TARGET,64,64);assert(target);
    std::vector<SDL_Texture*>textures;
    for(auto rgba:std::vector<std::array<uint8_t,4>>{{255,0,0,255},{0,255,0,255},{0,0,255,255},{255,0,255,0}}){
        auto*t=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA32,SDL_TEXTUREACCESS_STATIC,1,1);assert(t);
        assert(SDL_UpdateTexture(t,nullptr,rgba.data(),4));textures.push_back(t);
    }
    DepthRenderer depth;
    for(int reverse=0;reverse<2;reverse++){
        SDL_SetRenderTarget(r,target);SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderClear(r);
        std::vector<Face>faces;quad(faces,0,4,30,100);quad(faces,1,-8,30,100);
        quad(faces,2,0,5,50);quad(faces,3,0,10,30); // transparent pixels must not occlude
        if(reverse)std::reverse(faces.begin(),faces.end());
        assert(depth.draw(r,textures,faces,64,64));
        SDL_SetRenderDrawColor(r,0,255,255,255);SDL_FRect hud{0,0,4,4};SDL_RenderFillRect(r,&hud);
        auto*surface=SDL_RenderReadPixels(r,nullptr);assert(surface);
        auto check=[&](int x,int y,int red,int green,int blue){Uint8 rr,gg,bb,aa;assert(SDL_ReadSurfacePixel(surface,x,y,&rr,&gg,&bb,&aa));assert(rr==red&&gg==green&&bb==blue);};
        check(32,32,0,0,255);check(15,32,0,255,0);check(1,1,0,255,255);
        SDL_DestroySurface(surface);
    }
    // Road overlap retains the original screen silhouette and per-car depth
    // ordering. A nearer wall still occludes; an untagged buried object stays
    // hidden. Reverse submission order to expose flattening/depth-tie mistakes.
    for(int bias:{0,-8,20})for(int reverse=0;reverse<2;reverse++)for(bool perspective:{true,false}){
        SDL_SetRenderTarget(r,target);SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderClear(r);
        float road=150000.f/(150000.f-20)*(1-20.f/(100+bias*.125f))+bias/16777216.f;
        std::vector<Face>f;quad(f,0,bias,30,100);quad(f,2,0,28,110);
        size_t car=f.size();quad(f,1,0,20,110);quad(f,2,0,10,105);
        for(size_t i=car;i<f.size();i++)f[i].contactPlane={0,0,road};
        quad(f,0,0,3,80);quad(f,3,0,15,60);
        if(reverse)std::reverse(f.begin(),f.end());
        assert(depth.draw(r,textures,f,64,64,perspective));
        auto*surface=SDL_RenderReadPixels(r,nullptr);assert(surface);
        auto check=[&](int x,int red,int green,int blue){Uint8 rr,gg,bb,aa;assert(SDL_ReadSurfacePixel(surface,x,32,&rr,&gg,&bb,&aa));assert(rr==red&&gg==green&&bb==blue);};
        check(11,255,0,0);check(19,0,255,0);check(26,0,0,255);check(32,255,0,0);
        SDL_DestroySurface(surface);
    }
    // The two authored half-black shadow passes darken the road, retain
    // nearer car occlusion, and must not disable depth writes next frame.
    auto*black=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA32,SDL_TEXTUREACCESS_STATIC,1,1);
    const uint8_t blackPixel[4]={0,0,0,255};assert(SDL_UpdateTexture(black,nullptr,blackPixel,4));textures.push_back(black);
    for(int repeat=0;repeat<2;repeat++){
        SDL_SetRenderTarget(r,target);SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderClear(r);
        std::vector<Face>f;quad(f,0,0,30,100);quad(f,2,0,5,50);
        size_t first=f.size();quad(f,4,-16,20,100);quad(f,4,-16,20,100);
        for(size_t i=first;i<f.size();i++)f[i].shadow=true;
        assert(depth.draw(r,textures,f,64,64));
        auto*surface=SDL_RenderReadPixels(r,nullptr);assert(surface);Uint8 rr,gg,bb,aa;
        SDL_ReadSurfacePixel(surface,20,32,&rr,&gg,&bb,&aa);assert(rr>=62&&rr<=65&&gg==0&&bb==0&&aa==255);
        SDL_ReadSurfacePixel(surface,32,32,&rr,&gg,&bb,&aa);assert(rr==0&&gg==0&&bb==255);
        SDL_DestroySurface(surface);
    }
    SDL_DestroyTexture(textures.back());textures.pop_back();
    // Authored layers can sit a quarter-unit behind their backing surface.
    // Test both orderings and grazing views, with a truly nearer occluder.
    for(float angle:{0.f,.3f,.8f,1.3f})for(int reverse=0;reverse<2;reverse++){
        SDL_SetRenderTarget(r,target);SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderClear(r);
        std::vector<Face>faces;quad(faces,0,-9,500,1000);quad(faces,1,-16,400,1000.25f);
        for(auto&face:faces)for(auto&v:face.vertices){auto p=v.position;v.position={p.x*std::cos(angle)+(p.z-1000)*std::sin(angle),p.y,1000-p.x*std::sin(angle)+(p.z-1000)*std::cos(angle)};}
        quad(faces,2,0,50,700);quad(faces,3,-20,60,600);
        if(reverse)std::reverse(faces.begin(),faces.end());
        assert(depth.draw(r,textures,faces,64,64));auto*surface=SDL_RenderReadPixels(r,nullptr);assert(surface);
        Uint8 rr,gg,bb,aa;assert(SDL_ReadSurfacePixel(surface,32,16,&rr,&gg,&bb,&aa));assert(rr==0&&gg==255&&bb==0);
        assert(SDL_ReadSurfacePixel(surface,32,32,&rr,&gg,&bb,&aa));assert(rr==0&&gg==0&&bb==255);SDL_DestroySurface(surface);
    }
    // Broad crowd/board overlap needs more separation than a thin decal.
    // Retain the crowd's projected pixels elsewhere and a genuinely nearer car.
    for(int reverse=0;reverse<2;reverse++){
        assert(sceneryLayerBias(60,26,0x7985,0x40318,14)==112);
        for(int model:{59,61})assert(sceneryLayerBias(model,26,0x7985,0x40318,14)==14);
        assert(sceneryLayerBias(60,27,0x7985,0x40318,14)==14);
        assert(sceneryLayerBias(60,26,0x7986,0x40318,14)==14);
        assert(sceneryLayerBias(60,26,0x7985,0,14)==14);
        assert(sceneryLayerBias(60,26,0x7985,0x40318,-9)==-9);
        SDL_SetRenderTarget(r,target);SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderClear(r);
        std::vector<Face>faces;quad(faces,0,sceneryLayerBias(60,26,0x7985,0x40318,14),500,1000);
        quad(faces,1,3,300,1008);quad(faces,2,0,40,700);
        if(reverse)std::reverse(faces.begin(),faces.end());
        assert(depth.draw(r,textures,faces,64,64));auto*surface=SDL_RenderReadPixels(r,nullptr);assert(surface);
        Uint8 rr,gg,bb,aa;assert(SDL_ReadSurfacePixel(surface,32,16,&rr,&gg,&bb,&aa));assert(rr==0&&gg==255&&bb==0);
        assert(SDL_ReadSurfacePixel(surface,32,2,&rr,&gg,&bb,&aa));assert(rr==255&&gg==0&&bb==0);
        assert(SDL_ReadSurfacePixel(surface,32,32,&rr,&gg,&bb,&aa));assert(rr==0&&gg==0&&bb==255);
        SDL_DestroySurface(surface);
    }
    // Changing a layer's depth must preserve its coverage and perspective UVs.
    auto*checker=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA32,SDL_TEXTUREACCESS_STATIC,2,2);assert(checker);
    uint8_t pixels[]={255,0,0,255,0,255,0,255,0,0,255,255,255,255,255,255};
    assert(SDL_UpdateTexture(checker,nullptr,pixels,8));textures.push_back(checker);
    std::vector<uint32_t>reference;
    for(int bias:{0,40}){
        SDL_SetRenderTarget(r,target);SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderClear(r);
        std::vector<Face>faces;quad(faces,4,bias,200,700);
        for(auto&face:faces)for(auto&v:face.vertices)v.position.z+=v.position.x*.8f;
        assert(depth.draw(r,textures,faces,64,64));auto*surface=SDL_RenderReadPixels(r,nullptr);assert(surface);
        std::vector<uint32_t>actual;
        for(int y=0;y<64;y++)for(int x=0;x<64;x++){Uint8 rr,gg,bb,aa;assert(SDL_ReadSurfacePixel(surface,x,y,&rr,&gg,&bb,&aa));actual.push_back(rr|(gg<<8)|(bb<<16));}
        if(!bias)reference=actual;else assert(reference==actual);SDL_DestroySurface(surface);
    }
    // Affine mode must change the skewed checker UVs, without changing coverage.
    SDL_SetRenderTarget(r,target);SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderClear(r);
    std::vector<Face>affine;quad(affine,4,0,200,700);
    for(auto&face:affine)for(auto&v:face.vertices)v.position.z+=v.position.x*.8f;
    assert(depth.draw(r,textures,affine,64,64,false));auto*surface=SDL_RenderReadPixels(r,nullptr);assert(surface);
    unsigned changed=0;
    for(int y=0;y<64;y++)for(int x=0;x<64;x++){
        Uint8 rr,gg,bb,aa;assert(SDL_ReadSurfacePixel(surface,x,y,&rr,&gg,&bb,&aa));
        uint32_t actual=rr|(gg<<8)|(bb<<16),expected=reference[y*64+x];
        assert(bool(actual)==bool(expected));changed+=actual!=expected;
    }
    assert(changed>10);SDL_DestroySurface(surface);
    depth.close();for(auto*t:textures)SDL_DestroyTexture(t);SDL_DestroyTexture(target);
    SDL_DestroyRenderer(r);SDL_DestroyWindow(w);SDL_Quit();
}
'''
class DepthTests(unittest.TestCase):
    def test_coplanar_order_occlusion_and_hud(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(HARNESS)
            flags=shlex.split(subprocess.check_output(['/opt/homebrew/bin/pkg-config','--cflags','--libs','sdl3'],text=True))
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),*flags,'-framework','OpenGL','-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True,capture_output=True,timeout=20)
