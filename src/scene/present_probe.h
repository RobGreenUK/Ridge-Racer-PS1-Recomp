#pragma once
#include <objc/runtime.h>
#include <objc/message.h>
#include <OpenGL/OpenGL.h>
// Diagnostic-only hooks; never installed into the normal executable.
static thread_local double probeFlush=0,probeUpdate=0;
static thread_local uint64_t probeFlushBegin=0,probeFlushEnd=0,probeUpdateBegin=0,probeUpdateEnd=0;
static IMP originalFlush=nullptr,originalUpdate=nullptr;
static void timedFlush(id object,SEL selector){auto t=SDL_GetTicksNS();reinterpret_cast<void(*)(id,SEL)>(originalFlush)(object,selector);probeFlushEnd=SDL_GetTicksNS();if(!probeFlushBegin)probeFlushBegin=t;probeFlush+=double(probeFlushEnd-t)/1e6;}
static void timedUpdate(id object,SEL selector){auto t=SDL_GetTicksNS();reinterpret_cast<void(*)(id,SEL)>(originalUpdate)(object,selector);probeUpdateEnd=SDL_GetTicksNS();if(!probeUpdateBegin)probeUpdateBegin=t;probeUpdate+=double(probeUpdateEnd-t)/1e6;}
static void installProbe(){
 auto cls=objc_getClass("SDL3OpenGLContext");if(!cls)throw std::runtime_error("SDL GL class unavailable");
 auto flush=sel_registerName("flushBuffer"),update=sel_registerName("updateIfNeeded");
 auto method=class_getInstanceMethod(cls,flush);if(!method)throw std::runtime_error("flush method unavailable");
 originalFlush=method_getImplementation(method);
 // flushBuffer is inherited; add override on SDL's class, not NSOpenGLContext.
 if(!class_addMethod(cls,flush,reinterpret_cast<IMP>(timedFlush),method_getTypeEncoding(method)))throw std::runtime_error("unexpected flush override");
 method=class_getInstanceMethod(cls,update);if(!method)throw std::runtime_error("update method unavailable");
 originalUpdate=method_setImplementation(method,reinterpret_cast<IMP>(timedUpdate));
}
