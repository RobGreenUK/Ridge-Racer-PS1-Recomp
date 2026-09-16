#pragma once
#ifdef __APPLE__
#include <OpenGL/OpenGL.h>
#include <CoreVideo/CVDisplayLink.h>
#include "display_callback_trace.h"
// Schedule work at the display callback, before drawing. SDL's Cocoa GL swap
// path instead waits immediately before submission, leaving little headroom.
// Resolve CoreVideo dynamically so other platforms/build dependencies stay put.
struct DisplayPacer {
    SDL_SharedObject*library=nullptr;CVDisplayLinkRef link=nullptr;
    SDL_Mutex*mutex=nullptr;SDL_Condition*condition=nullptr;
    bool trace=false;
    uint64_t produced=0,consumed=0;
    DisplayCallbackSample latest,sample;DisplayCallbackTrace callbackTrace;
    using Create=CVReturn(*)(CVDisplayLinkRef*);
    using Bind=CVReturn(*)(CVDisplayLinkRef,CGLContextObj,CGLPixelFormatObj);
    using Callback=CVReturn(*)(CVDisplayLinkRef,CVDisplayLinkOutputCallback,void*);
    using Start=CVReturn(*)(CVDisplayLinkRef);using Stop=CVReturn(*)(CVDisplayLinkRef);using Release=void(*)(CVDisplayLinkRef);
    Bind bind=nullptr;Stop stop=nullptr;Release release=nullptr;
    static CVReturn tick(CVDisplayLinkRef,const CVTimeStamp*current,const CVTimeStamp*output,CVOptionFlags,CVOptionFlags*,void*context){
        auto*self=static_cast<DisplayPacer*>(context);
        const uint64_t entry=self->trace?SDL_GetTicksNS():0;
        SDL_LockMutex(self->mutex);
        ++self->produced;
        if(self->trace){
        self->latest.id=self->produced;self->latest.entry=entry;
        self->latest.currentHost=current?current->hostTime:0;
        self->latest.outputHost=output?output->hostTime:0;
        self->latest.currentFlags=current?current->flags:0;
        self->latest.outputFlags=output?output->flags:0;
        self->latest.exit=SDL_GetTicksNS();
        self->callbackTrace.record(self->latest);
        }
        SDL_SignalCondition(self->condition);SDL_UnlockMutex(self->mutex);
        return kCVReturnSuccess;
    }
    template<class T>T symbol(const char*name){return reinterpret_cast<T>(SDL_LoadFunction(library,name));}
    bool open(const std::string&metricsPath={}){
        const char*setting=SDL_getenv("RIDGE_HANDOFF_TRACE");trace=setting&&SDL_strcmp(setting,"1")==0;
        library=SDL_LoadObject("/System/Library/Frameworks/CoreVideo.framework/CoreVideo");if(!library)return false;
        auto create=symbol<Create>("CVDisplayLinkCreateWithActiveCGDisplays");bind=symbol<Bind>("CVDisplayLinkSetCurrentCGDisplayFromOpenGLContext");
        auto callback=symbol<Callback>("CVDisplayLinkSetOutputCallback");auto start=symbol<Start>("CVDisplayLinkStart");
        stop=symbol<Stop>("CVDisplayLinkStop");release=symbol<Release>("CVDisplayLinkRelease");
        if(!create||!bind||!callback||!start||!stop||!release)return false;
        mutex=SDL_CreateMutex();condition=SDL_CreateCondition();
        if(!mutex||!condition||create(&link)!=kCVReturnSuccess)return false;
        if(trace&&!metricsPath.empty())callbackTrace.open(metricsPath+".callbacks.csv");
        auto context=CGLGetCurrentContext();
        return context&&bind(link,context,CGLGetPixelFormat(context))==kCVReturnSuccess&&callback(link,tick,this)==kCVReturnSuccess&&start(link)==kCVReturnSuccess;
    }
    bool wait(){
        const uint64_t begin=trace?SDL_GetTicksNS():0;
        SDL_LockMutex(mutex);
        if(produced==consumed)SDL_WaitConditionTimeout(condition,mutex,100);
        bool arrived=produced!=consumed;
        sample=arrived?latest:DisplayCallbackSample{};
        sample.skipped=arrived?produced-consumed-1:0;
        sample.waitStart=begin;sample.waitEnd=trace?SDL_GetTicksNS():0;
        consumed=produced;SDL_UnlockMutex(mutex);return arrived;
    }
    void close(){
        if(link){stop(link);release(link);link=nullptr;}
        callbackTrace.close();
        if(condition){SDL_DestroyCondition(condition);condition=nullptr;}
        if(mutex){SDL_DestroyMutex(mutex);mutex=nullptr;}
        if(library){SDL_UnloadObject(library);library=nullptr;}
    }
    ~DisplayPacer(){close();}
};
#endif
