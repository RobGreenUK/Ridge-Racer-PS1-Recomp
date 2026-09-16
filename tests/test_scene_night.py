"""Day/night building switching must retain course geometry and legacy markers."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#define main ridge_preview_main
#include "preview.cpp"
#undef main
#include <cassert>
int main(){
 assert(SDL_Init(SDL_INIT_VIDEO));auto*w=SDL_CreateWindow("night regression",64,64,SDL_WINDOW_HIDDEN);
 auto*r=SDL_CreateRenderer(w,"opengl");assert(r);
 auto*target=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA8888,SDL_TEXTUREACCESS_TARGET,64,64);assert(target);
 CourseMesh mesh;
 for(auto color:std::vector<std::array<uint8_t,4>>{{255,0,0,255},{0,255,0,255},{0,0,255,255}}){
  auto*t=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA32,SDL_TEXTUREACCESS_STATIC,1,1);assert(t);
  assert(SDL_UpdateTexture(t,nullptr,color.data(),4));mesh.textures.push_back(t);
 }
 auto quad=[](unsigned texture,float radius,float depth,unsigned day){MeshQuad q{};q.texture=texture;q.dayOnly=day;
  q.v[0]={{-radius,-radius,depth},0,0};q.v[1]={{radius,-radius,depth},1,0};q.v[2]={{-radius,radius,depth},0,1};q.v[3]={{radius,radius,depth},1,1};return q;};
 mesh.quads={quad(0,30,100,1),quad(2,5,50,0)};mesh.models.resize(85);mesh.models[84]={quad(1,60,200,0)};
 Frame day{};day.rotation.w=1;Frame night=day;night.flags=RR_SCENE_NIGHT;
 night.models.push_back({0,84,{0,0,0},{1,0,0,0,1,0,0,0,1},0});
 assert(!nightScenery(day)&&nightScenery(night));
 Frame legacy=night;legacy.flags=0;legacy.models[0].key=0x80015ae4;assert(nightScenery(legacy));
 Frame unrelated=legacy;unrelated.models[0].key=0x80020e1c;assert(!nightScenery(unrelated));
 for(const Frame*f:{&day,&night,&legacy,&day}){
  SDL_SetRenderTarget(r,target);SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderClear(r);mesh.draw(r,*f,{},64,64);
  auto*s=SDL_RenderReadPixels(r,nullptr);assert(s);Uint8 rr,gg,bb,aa;
  assert(SDL_ReadSurfacePixel(s,15,32,&rr,&gg,&bb,&aa));assert(nightScenery(*f)?(rr==0&&gg==255):(rr==255&&gg==0));
  assert(SDL_ReadSurfacePixel(s,32,32,&rr,&gg,&bb,&aa));assert(rr==0&&gg==0&&bb==255);
  SDL_DestroySurface(s);
 }
 mesh.close();SDL_DestroyTexture(target);SDL_DestroyRenderer(r);SDL_DestroyWindow(w);SDL_Quit();
}
'''
class NightTests(unittest.TestCase):
    def test_day_night_replacements_and_return_to_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(HARNESS)
            flags=shlex.split(subprocess.check_output(['/opt/homebrew/bin/pkg-config','--cflags','--libs','sdl3'],text=True))
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),*flags,'-framework','OpenGL','-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True,capture_output=True,timeout=20)
