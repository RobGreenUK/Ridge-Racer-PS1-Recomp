"""Streamed packed pixels and palettes invalidate only the affected textures."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include <vector>
#include <cstdint>
#include <cassert>
#include "texture_data.h"
int main(){
    std::vector<uint16_t>vram(524288);
    const unsigned page=15,clut=480<<6;
    vram[960]=0x3210;vram[480*1024+1]=31;
    TextureSignatures first{vram,{}};auto hash=first.get(page,clut);
    auto rgba=texturePixels(vram,page,clut);assert(rgba[3]==0&&rgba[4]==255&&rgba[5]==0&&rgba[7]==255);
    vram[0]=123;TextureSignatures unrelated{vram,{}};assert(hash==unrelated.get(page,clut));
    vram[480*1024+1]=0x3e0;TextureSignatures palette{vram,{}};assert(hash!=palette.get(page,clut));
    rgba=texturePixels(vram,page,clut);assert(rgba[4]==0&&rgba[5]==255);
    hash=palette.get(page,clut);vram[960]=0;TextureSignatures pixels{vram,{}};assert(hash!=pixels.get(page,clut));
    rgba=texturePixels(vram,page,clut);assert(rgba[7]==0);
    // Repeat only the requested 8x8 window, without sampling neighbouring atlas data.
    for(unsigned y=0;y<8;y++){vram[y*1024+962]=0x2222;vram[y*1024+963]=0x2222;}
    vram[480*1024+2]=0x7c00;
    rgba=texturePixels(vram,page,clut,31|(31<<5)|(1<<10));
    for(unsigned i=0;i<256*256;i++)assert(rgba[i*4]==0&&rgba[i*4+1]==0&&rgba[i*4+2]==255&&rgba[i*4+3]==255);
    // Resident scenery survives bank reuse but follows the live palette.
    std::vector<uint16_t>resident(16384,0x1111);vram[480*1024+1]=31;
    rgba=texturePixels(vram,page,clut,0,&resident);assert(rgba[0]==255&&rgba[1]==0);
    vram[960]=0x2222;vram[480*1024+1]=0x3e0;
    rgba=texturePixels(vram,page,clut,0,&resident);assert(rgba[0]==0&&rgba[1]==255);
    auto streamed=texturePixels(vram,page,clut);assert(streamed[2]==255&&streamed[1]==0);
}
'''
class TextureTests(unittest.TestCase):
    def test_streamed_pixels_and_palette(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(HARNESS)
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),'-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True,capture_output=True)

PALETTE_HARNESS=r'''
#define main ridge_preview_main
#include "preview.cpp"
#undef main
#include <cassert>
int main(){
    assert(SDL_Init(SDL_INIT_VIDEO));
    auto*w=SDL_CreateWindow("palette regression",32,32,SDL_WINDOW_HIDDEN);
    auto*r=SDL_CreateRenderer(w,"opengl");assert(r);
    CourseMesh mesh;mesh.sky.vram.resize(524288);
    const unsigned page=15,clut=480<<6,variant=clut+1;
    mesh.sky.vram[960]=0x1111;
    mesh.sky.vram[480*1024+1]=31;mesh.sky.vram[480*1024+17]=0x3e0;
    auto pixels=texturePixels(mesh.sky.vram,page,clut);
    auto*t=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA32,SDL_TEXTUREACCESS_STATIC,256,256);assert(t);
    assert(SDL_UpdateTexture(t,nullptr,pixels.data(),1024));SDL_SetTextureScaleMode(t,SDL_SCALEMODE_NEAREST);mesh.textures.push_back(t);mesh.textureKeys.emplace_back(page,clut);
    auto index=mesh.paletteTexture(r,0,variant<<16);assert(index==1);
    assert(mesh.paletteTexture(r,0,variant<<16)==index&&mesh.textures.size()==2);
    auto check=[&](unsigned texture,int red,int green,int blue){
        SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderClear(r);
        SDL_FRect source{0,0,1,1};assert(SDL_RenderTexture(r,mesh.textures[texture],&source,nullptr));
        auto*s=SDL_RenderReadPixels(r,nullptr);assert(s);Uint8 rr,gg,bb,aa;
        assert(SDL_ReadSurfacePixel(s,16,16,&rr,&gg,&bb,&aa));assert(rr==red&&gg==green&&bb==blue);SDL_DestroySurface(s);
    };
    check(0,255,0,0);check(index,0,255,0);
    auto updated=mesh.sky.vram;updated[480*1024+17]=0x7c00;mesh.updateVram(updated);
    assert(mesh.textureUpdates==0); // No invisible texture upload.
    mesh.prepareTexture(0);assert(mesh.textureUpdates==0);
    mesh.prepareTexture(index);assert(mesh.textureUpdates==1);
    mesh.prepareTexture(index);assert(mesh.textureUpdates==1); // Once per dirty version.
    check(0,255,0,0);check(index,0,0,255);
    updated[480*1024+17]=31;mesh.updateVram(updated);
    updated[480*1024+17]=0x3e0;mesh.updateVram(updated);
    mesh.prepareTexture(index);check(index,0,255,0); // Latest skipped version wins.
    // A resident source and a streamed source can share page/CLUT/window.
    // They must remain separate cache entries when a model changes palettes.
    mesh.residentTexels.resize(mesh.textures.size());mesh.residentTexels[0].assign(16384,0x2222);
    updated[480*1024+18]=31;mesh.updateVram(updated);
    auto fixed=mesh.paletteTexture(r,0,variant<<16);assert(fixed!=index);
    assert(mesh.paletteTexture(r,0,variant<<16)==fixed);check(fixed,255,0,0);
    updated[480*1024+18]=0x7c00;updated[960]=0;mesh.updateVram(updated);
    mesh.prepareTexture(fixed);check(fixed,0,0,255);
    updated[960]=0x3333;mesh.updateVram(updated);
    assert(!mesh.textureDirty[fixed]); // Displaced live page cannot invalidate resident pixels.
    assert(mesh.textureDirty[index]); // The same page still matters to streamed textures.
    mesh.prepareTexture(fixed);assert(mesh.textureUpdates==0);check(fixed,0,0,255);
    updated[480*1024+18]=31;mesh.updateVram(updated);
    assert(mesh.textureDirty[fixed]);mesh.prepareTexture(fixed);
    assert(mesh.textureUpdates==1);check(fixed,255,0,0);
    mesh.close();SDL_DestroyRenderer(r);SDL_DestroyWindow(w);SDL_Quit();
}
'''
class ModelPaletteTests(unittest.TestCase):
    def test_instance_palette_cache_and_streaming(self):
        import shlex
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(PALETTE_HARNESS)
            flags=shlex.split(subprocess.check_output(['/opt/homebrew/bin/pkg-config','--cflags','--libs','sdl3'],text=True))
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),*flags,'-framework','OpenGL','-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True,capture_output=True,timeout=20)
