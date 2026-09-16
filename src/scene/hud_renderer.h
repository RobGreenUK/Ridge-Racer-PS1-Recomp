#pragma once
#include <unordered_map>
#include "texture_data.h"
#include "hud_layout.h"
struct HudRenderer {
    std::unordered_map<uint32_t,SDL_Texture*>textures;
    void updateVram(const std::vector<uint16_t>&oldWords,const std::vector<uint16_t>&words){
        TextureSignatures before{oldWords,{}},after{words,{}};updateVram(before,after);
    }
    void updateVram(TextureSignatures&before,TextureSignatures&after){
        const auto&words=after.vram;
        for(auto&entry:textures){unsigned page=entry.first&65535,clut=entry.first>>16;
            if(before.get(page,clut)==after.get(page,clut))continue;
            auto rgba=texturePixels(words,page,clut);
            if(!SDL_UpdateTexture(entry.second,nullptr,rgba.data(),1024))throw std::runtime_error(SDL_GetError());
        }
    }
    SDL_Texture*texture(SDL_Renderer*r,const std::vector<uint16_t>&vram,uint16_t page,uint16_t clut){
        uint32_t key=uint32_t(clut)<<16|page;
        auto found=textures.find(key);if(found!=textures.end())return found->second;
        unsigned mode=(page>>7)&3;if(mode==3||vram.size()!=524288)return nullptr;
        // Bound texture cache even during long sessions with changing palettes.
        if(textures.size()>=256)close();
        std::vector<uint8_t>rgba(256*256*4);unsigned cx=(clut&63)*16,cy=(clut>>6)&511;
        for(unsigned y=0;y<256;y++)for(unsigned x=0;x<256;x++){
            uint16_t word=vram[((((page>>4)&1)*256+y)&511)*1024+(((page&15)*64+(x>>(2-mode)))&1023)];
            if(mode<2){unsigned index=(word>>((x&((1u<<(2-mode))-1))*(4u<<mode)))&((1u<<(4u<<mode))-1);word=vram[cy*1024+((cx+index)&1023)];}
            for(int c=0;c<3;c++){unsigned v=(word>>(c*5))&31;rgba[(y*256+x)*4+c]=(v<<3)|(v>>2);}
            rgba[(y*256+x)*4+3]=word?255:0;
        }
        SDL_Texture*t=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA32,SDL_TEXTUREACCESS_STATIC,256,256);
        if(!t||!SDL_UpdateTexture(t,nullptr,rgba.data(),1024))throw std::runtime_error(SDL_GetError());
        SDL_SetTextureScaleMode(t,SDL_SCALEMODE_NEAREST);SDL_SetTextureBlendMode(t,SDL_BLENDMODE_BLEND);textures.emplace(key,t);return t;
    }
    void draw(SDL_Renderer*r,const Frame&f,const std::vector<uint16_t>&vram,int width,int height){
        uint16_t page=0;float scale=height/240.f,left=(width-320*scale)/2;
        auto color=[](uint32_t rgb,float divisor){return SDL_FColor{(rgb&255)/divisor,((rgb>>8)&255)/divisor,((rgb>>16)&255)/divisor,1};};
        for(size_t offset=0;offset<f.hud.size();){
            unsigned n=f.hud[offset++];if(!n||n>f.hud.size()-offset)break;
            const uint32_t*p=f.hud.data()+offset;offset+=n;unsigned cmd=p[0]>>24,type=cmd&0xfc;
            if(cmd>=0xe0){for(unsigned i=0;i<n;i++)if(p[i]>>24==0xe1)page=p[i]&0x1ff;continue;}
            SDL_Vertex v[4];int count=4;SDL_Texture*t=nullptr;
            auto xy=[&](uint32_t packed){return SDL_FPoint{left+int16_t(packed)*scale,int16_t(packed>>16)*scale};};
            if((type==0x64&&n==4)||((type==0x74||type==0x7c)&&n==3)){
                unsigned w=type==0x64?(p[3]&0xffff):(type==0x74?8:16),h=type==0x64?(p[3]>>16):w;
                float u=p[2]&255,texY=(p[2]>>8)&255;auto origin=xy(p[1]);
                t=texture(r,vram,page,p[2]>>16);if(!t)continue;
                for(int i=0;i<4;i++)v[i]={{origin.x+(i&1?w*scale:0),origin.y+(i&2?h*scale:0)},color(p[0],cmd&1?255:128),{(u+(i&1?w:0))/256,(texY+(i&2?h:0))/256}};
                if(cmd&1)for(auto&vertex:v)vertex.color={1,1,1,1};
            }else if(type==0x2c&&n==9){
                page=(p[4]>>16)&0x1ff;t=texture(r,vram,page,p[2]>>16);if(!t)continue;
                for(int i=0;i<4;i++){uint32_t uv=p[2+i*2];v[i]={xy(p[1+i*2]),cmd&1?SDL_FColor{1,1,1,1}:color(p[0],128),{(uv&255)/256.f,((uv>>8)&255)/256.f}};}
            }else if((type==0x28&&n==5)||(type==0x20&&n==4)){
                count=type==0x20?3:4;for(int i=0;i<count;i++)v[i]={xy(p[i+1]),color(p[0],255),{0,0}};
            }else if(type==0x60&&n==3){
                auto origin=xy(p[1]);for(int i=0;i<4;i++)v[i]={{origin.x+(i&1?(p[2]&0xffff)*scale:0),origin.y+(i&2?(p[2]>>16)*scale:0)},color(p[0],255),{0,0}};
            }else continue;
            const float shift=hudAnchorShift((f.flags&RR_SCENE_REPLAY)?0:raceHudAnchor(p,n,page),width,height);
            for(int i=0;i<count;i++)v[i].position.x+=shift;
            // Average transparency covers the HUD's basic fades. Other PS1
            // semitransparency equations remain part of renderer fidelity work.
            if(cmd&2)for(int i=0;i<count;i++)v[i].color.a=.5f;
            int indices[6]={0,1,2,2,1,3};SDL_SetRenderDrawBlendMode(r,SDL_BLENDMODE_BLEND);
            if(!SDL_RenderGeometry(r,t,v,count,indices,count==3?3:6))throw std::runtime_error(SDL_GetError());
        }
    }
    void close(){for(auto&entry:textures)SDL_DestroyTexture(entry.second);textures.clear();}
};
