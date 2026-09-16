#include "presentation_mode.h"
#include "../platform/mapped_file.h"
#pragma once
#include "screen_protocol.h"
class ScreenClient {
    int fd=-1;RRScreen*shared=nullptr;SDL_Texture*texture=nullptr;
    uint32_t sequence=0,w=0,h=0;uint64_t received=0;
public:
    void poll(SDL_Renderer*r,const std::string&socket){
        if(fd<0){
            fd=::open((socket+".screen").c_str(),O_RDONLY);if(fd<0)return;
            struct stat st{};if(fstat(fd,&st)||st.st_size!=sizeof(RRScreen)){::close(fd);fd=-1;return;}
            void*p=mmap(nullptr,sizeof(RRScreen),PROT_READ,MAP_SHARED,fd,0);
            if(p==MAP_FAILED){::close(fd);fd=-1;return;}shared=static_cast<RRScreen*>(p);
        }
        if(flock(fd,LOCK_SH|LOCK_NB)<0)return;
        if(shared->magic==RR_SCREEN_MAGIC&&shared->sequence!=sequence){
            sequence=shared->sequence;received=SDL_GetTicksNS();
            if(shared->width&&shared->width<=640&&shared->height&&shared->height<=512&&!ridge_scene_state(shared->state)){
                if(w!=shared->width||h!=shared->height){
                    if(texture)SDL_DestroyTexture(texture);w=shared->width;h=shared->height;
                    texture=SDL_CreateTexture(r,SDL_PIXELFORMAT_ARGB8888,SDL_TEXTUREACCESS_STREAMING,w,h);
                    if(texture)SDL_SetTextureScaleMode(texture,SDL_SCALEMODE_NEAREST);
                }
                if(texture)SDL_UpdateTexture(texture,nullptr,shared->pixels,w*4);
            }else {w=h=0;if(texture)SDL_DestroyTexture(texture);texture=nullptr;}
        }
        flock(fd,LOCK_UN);
    }
    bool draw(SDL_Renderer*r,int width,int height){
        if(!texture||SDL_GetTicksNS()-received>500000000)return false;
        float dh=std::min(float(height),width*.75f),dw=dh*4/3;
        SDL_FRect dest{(width-dw)/2,(height-dh)/2,dw,dh};
        SDL_RenderTexture(r,texture,nullptr,&dest);return true;
    }
    void close(){if(texture)SDL_DestroyTexture(texture);texture=nullptr;if(shared)munmap(shared,sizeof *shared);shared=nullptr;if(fd>=0)::close(fd);fd=-1;}
    ~ScreenClient(){close();}
};
