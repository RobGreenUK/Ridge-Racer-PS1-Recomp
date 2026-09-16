#pragma once
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#undef near
#undef far
#include <GL/gl.h>
#include <GL/glext.h>
/* Windows exports GL 1.1 only; resolve the compatibility-context extensions
 * from the same SDL context used by the enhanced renderer. */
#define RR_GL_FUNCTIONS(X) \
 X(PFNGLGENBUFFERSPROC,glGenBuffers) \
 X(PFNGLDELETEBUFFERSPROC,glDeleteBuffers) \
 X(PFNGLBINDBUFFERPROC,glBindBuffer) \
 X(PFNGLBUFFERDATAPROC,glBufferData) \
 X(PFNGLBUFFERSUBDATAPROC,glBufferSubData) \
 X(PFNGLCLIENTACTIVETEXTUREPROC,glClientActiveTexture) \
 X(PFNGLDELETERENDERBUFFERSEXTPROC,glDeleteRenderbuffersEXT) \
 X(PFNGLGETFRAMEBUFFERATTACHMENTPARAMETERIVEXTPROC,glGetFramebufferAttachmentParameterivEXT) \
 X(PFNGLGENRENDERBUFFERSEXTPROC,glGenRenderbuffersEXT) \
 X(PFNGLBINDRENDERBUFFEREXTPROC,glBindRenderbufferEXT) \
 X(PFNGLRENDERBUFFERSTORAGEEXTPROC,glRenderbufferStorageEXT) \
 X(PFNGLFRAMEBUFFERRENDERBUFFEREXTPROC,glFramebufferRenderbufferEXT) \
 X(PFNGLCHECKFRAMEBUFFERSTATUSEXTPROC,glCheckFramebufferStatusEXT) \
 X(PFNGLUSEPROGRAMPROC,glUseProgram) \
 X(PFNGLCREATESHADERPROC,glCreateShader) \
 X(PFNGLSHADERSOURCEPROC,glShaderSource) \
 X(PFNGLCOMPILESHADERPROC,glCompileShader) \
 X(PFNGLGETSHADERIVPROC,glGetShaderiv) \
 X(PFNGLGETSHADERINFOLOGPROC,glGetShaderInfoLog) \
 X(PFNGLDELETESHADERPROC,glDeleteShader) \
 X(PFNGLCREATEPROGRAMPROC,glCreateProgram) \
 X(PFNGLATTACHSHADERPROC,glAttachShader) \
 X(PFNGLLINKPROGRAMPROC,glLinkProgram) \
 X(PFNGLGETPROGRAMIVPROC,glGetProgramiv) \
 X(PFNGLGETPROGRAMINFOLOGPROC,glGetProgramInfoLog) \
 X(PFNGLDELETEPROGRAMPROC,glDeleteProgram) \
 X(PFNGLGETUNIFORMLOCATIONPROC,glGetUniformLocation) \
 X(PFNGLUNIFORM1IPROC,glUniform1i) \
 X(PFNGLUNIFORM3FPROC,glUniform3f) \
 X(PFNGLACTIVETEXTUREPROC,glActiveTexture) \
 X(PFNGLFRAMEBUFFERTEXTURE2DEXTPROC,glFramebufferTexture2DEXT)
#define RR_DECLARE(type,name) static type name;
RR_GL_FUNCTIONS(RR_DECLARE)
#undef RR_DECLARE
static void rr_load_gl(){
    static bool loaded=false;if(loaded)return;
#define RR_LOAD(type,name) name=reinterpret_cast<type>(SDL_GL_GetProcAddress(#name));if(!name)throw std::runtime_error("Missing graphics function: " #name);
    RR_GL_FUNCTIONS(RR_LOAD)
#undef RR_LOAD
    loaded=true;
}
