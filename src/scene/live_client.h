#include "presentation_mode.h"
#pragma once
#include "live_protocol.h"
#include "presentation_timeline.h"
#include <time.h>
#include "../platform/transport.h"
#include <unistd.h>
#include <fcntl.h>
class LiveClient {
    RRSocket fd=RR_INVALID_SOCKET;bool ownsPath=false;std::string path;Frame previous{},current{};PresentationTimeline timeline;double produced=0;bool queued=false;
    bool have=false;uint32_t state=0,track=0,currentSequence=0;uint64_t received=0;
    RRAddress inputAddress{};bool inputAddressReady=false;
    bool hudReady=false;uint32_t hudTotal=~0u,hudCount=0,hudBack=0;
    std::array<uint32_t,RR_HUD_CAP>hudAssembly{};std::array<bool,RR_HUD_CAP>hudSeen{};
    bool complete()const{return modelReady&&(!ridge_native_menu_state(state)||hudReady);}
    bool modelReady=false,havePrevious=false;uint64_t completeReceived=0;
    uint32_t assemblyTotal=~0u,assemblyCount=0;
    std::array<bool,RR_MODEL_CAP>seen{};
    std::array<RRRawModel,RR_MODEL_CAP>assembly{};
    void installModels(const RRRawModel*models,unsigned count){
        if(ridge_replay_state(state)&&!count)return; // setup boundary, not a complete replay scene
        current.models.clear();Quat inverse{-current.rotation.x,-current.rotation.y,-current.rotation.z,current.rotation.w};
        for(unsigned i=0;i<count;i++){
            const auto&m=models[i];ModelPose pose{};pose.key=(uint64_t(m.owner)<<32)|m.site;bool world=(m.model&RR_MODEL_WORLD_POSE)!=0;pose.model=m.model&~RR_MODEL_WORLD_POSE;pose.paletteOffset=m.palette_offset;
            Vec translation{m.translation[0]/4.f,m.translation[1]/4.f,m.translation[2]/4.f};
            pose.position=world?translation:current.camera+rotate(inverse,translation);
            float r[9];for(int k=0;k<9;k++)r[k]=int16_t(m.rotation[k/2]>>((k%2)*16))/4096.f;
            for(int column=0;column<3;column++){Vec columnVector{r[column],r[column+3],r[column+6]};Vec v=world?columnVector:rotate(inverse,columnVector);pose.matrix[column]=v.x;pose.matrix[column+3]=v.y;pose.matrix[column+6]=v.z;}
            current.models.push_back(pose);
        }
        modelReady=true;completeReceived=SDL_GetTicksNS();
    }
    static Quat rotation(const int16_t*raw) {
        std::array<float,9> m;for(int i=0;i<9;i++)m[i]=raw[i]/4096.f;
        return matrixRotation(m);
    }
public:
    uint64_t sequenceGaps=0,incompleteFrames=0;
    bool heldLatest()const{return timeline.heldLatest;}
    uint32_t sequence()const{return currentSequence;}
    double sourceAgeMs()const{return have?std::max(0.,double(SDL_GetTicksNS())/1e9-produced)*1000:-1;}
    void open(const std::string&p){
        path=p;fd=rr_socket();
        if(fd==RR_INVALID_SOCKET||rr_bind(fd,p.c_str()))throw std::runtime_error("cannot bind live scene endpoint");
        ownsPath=true;
        if(rr_buffer(fd,SO_RCVBUF,262144)||rr_nonblocking(fd))throw std::runtime_error("cannot configure live scene socket");
    }

    bool poll(Frame&out,double displayInterval=1./60) {
        RRLiveFrame message;
        alignas(8) unsigned char packet[sizeof(RRLiveModels)+sizeof(RRLiveHud)];
        // Bound drain work if the renderer is temporarily behind. Transport is
        // nonblocking and the sender is never asked to wait for presentation.
        for(int i=0;i<128;i++) {
            int n=rr_receive(fd,packet,sizeof packet);if(n<0)break;
            uint32_t magic=0;if(n>=4)std::memcpy(&magic,packet,4);
            if(magic==RR_MENU_HUD_MAGIC&&n>=24&&size_t(n)<=sizeof(RRMenuHudChunk)){
                RRMenuHudChunk h{};std::memcpy(&h,packet,size_t(n));
                if(!have||!ridge_native_menu_state(state)||h.sequence!=currentSequence||h.total>RR_HUD_CAP||h.offset>h.total||h.count>h.total-h.offset||h.count>RR_MENU_HUD_CHUNK_CAP||h.back_count>h.total||n!=24+h.count*4)continue;
                if(hudTotal==~0u){hudTotal=h.total;hudBack=h.back_count;}
                if(h.total!=hudTotal||h.back_count!=hudBack)continue;
                for(unsigned j=0;j<h.count;j++){unsigned k=h.offset+j;hudAssembly[k]=h.words[j];if(!hudSeen[k]){hudSeen[k]=true;hudCount++;}}
                if(hudCount==hudTotal){current.hud.assign(hudAssembly.begin(),hudAssembly.begin()+hudTotal);current.menuBackCount=hudBack;hudReady=true;if(modelReady)completeReceived=SDL_GetTicksNS();}
                continue;
            }
            if(magic==RR_HUD_MAGIC&&n>=12){
                uint32_t header[3];std::memcpy(header,packet,12);
                if(header[1]==currentSequence&&header[2]<=RR_HUD_CAP&&n==12+header[2]*4){current.hud.resize(header[2]);std::memcpy(current.hud.data(),packet+12,header[2]*4);}
                continue;
            }
            if(magic==RR_SKY_MAGIC&&n==sizeof(RRLiveSky)){
                RRLiveSky sky;std::memcpy(&sky,packet,sizeof sky);
                if(sky.sequence==currentSequence){const auto&s=sky.sky;current.sky={float(s.pitch),float(s.yaw),float(s.roll),s.mirror,s.clut,s.rgb,s.enabled};}
                continue;
            }
            if(magic==RR_MODEL_CHUNK_MAGIC&&n>=20&&size_t(n)<=sizeof(RRModelChunk)){
                RRModelChunk chunk{};std::memcpy(&chunk,packet,size_t(n));
                if(!have||chunk.sequence!=currentSequence||chunk.total>RR_MODEL_CAP||chunk.count>RR_MODEL_CHUNK_CAP||chunk.offset>chunk.total||chunk.count>chunk.total-chunk.offset||n!=20+chunk.count*sizeof(RRRawModel))continue;
                if(assemblyTotal==~0u)assemblyTotal=chunk.total;
                if(assemblyTotal!=chunk.total)continue;
                for(unsigned j=0;j<chunk.count;j++){unsigned k=chunk.offset+j;assembly[k]=chunk.models[j];if(!seen[k]){seen[k]=true;assemblyCount++;}}
                if(assemblyCount==assemblyTotal)installModels(assembly.data(),assemblyTotal);
                continue;
            }
            if(magic==RR_MODELS_MAGIC && n>=12 && size_t(n)<=sizeof(RRLiveModels)) {
                RRLiveModels models{};std::memcpy(&models,packet,size_t(n));
                if(models.count>RR_MODEL_CAP||n!=12+models.count*sizeof(RRRawModel)||models.sequence!=currentSequence)continue;
                installModels(models.models,models.count);
                continue;
            }
            if(n==sizeof message)std::memcpy(&message,packet,sizeof message);
            if(n!=sizeof message||message.magic!=RR_LIVE_MAGIC)continue;
            Frame incoming{double(message.cycles)/33868800.,message.flags,
                {float(message.camera[0]),float(message.camera[1]),float(message.camera[2])},rotation(message.matrix),
                {float(message.car[0]),float(message.car[1]),float(message.car[2])},float(message.yaw)*6.28318530718f/4096,{},{},{}};
            if(have){uint32_t step=message.sequence-currentSequence;if(step>1&&step<1000000)sequenceGaps+=step-1;if(state==1&&!modelReady)incompleteFrames++;}
            // The race start can replace the introduction's track table while
            // camera/car motion continues (observed 80059164 -> 80057d64).
            // Keep that buffer only for a continuous 2->3 transition in-race;
            // other course/state changes still reset it.
            bool raceStart=have&&state==1&&message.state==1&&
                (current.flags&65535)==2&&(incoming.flags&65535)==3&&
                !ridge::sceneFramesCut(current,incoming);
            bool continuous=have&&message.state==state&&(message.track==track||raceStart);
            if(complete()){previous=current;havePrevious=true;if(!queued)timeline.push(current,produced); }
            if(!continuous)timeline.clear();
            if(continuous&&havePrevious){incoming.hud=previous.hud;incoming.sky=previous.sky;}
            if(!continuous)havePrevious=false;
            current=incoming;currentSequence=message.sequence;have=true;state=message.state;track=message.track;received=SDL_GetTicksNS();
            uint64_t wall=rr_clock_ns();
            produced=double(received)/1e9-(message.published_ns&&wall>=message.published_ns?double(wall-message.published_ns)/1e9:0);
            queued=false;modelReady=false;hudReady=false;hudTotal=~0u;hudCount=0;hudSeen.fill(false);assemblyTotal=~0u;assemblyCount=0;seen.fill(false);
        }
        if(!have||!ridge_scene_state(state)||SDL_GetTicksNS()-received>500000000)return false;
        if(complete()&&!queued){timeline.push(current,produced);queued=true;}
        if(timeline.frames.empty()||SDL_GetTicksNS()-completeReceived>500000000)return false;
        out=timeline.at(double(SDL_GetTicksNS())/1e9,displayInterval);return true;
    }
    void send_input(uint16_t buttons,bool active) {
        if(fd==RR_INVALID_SOCKET)return;
        if(!inputAddressReady){
            if(rr_address(&inputAddress,(path+".pad").c_str()))return;
            inputAddressReady=true;
        }
        RRLiveInput input{RR_INPUT_MAGIC,buttons,active?1u:0u,0};
        (void)rr_send(fd,&input,sizeof input,&inputAddress);
    }
    void close(){inputAddressReady=false;if(fd!=RR_INVALID_SOCKET){rr_socket_close(fd);if(ownsPath)std::remove(path.c_str());fd=RR_INVALID_SOCKET;}}

    ~LiveClient(){close();}
};
