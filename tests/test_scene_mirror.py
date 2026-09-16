"""Mirror-course rendering reflects all 3D geometry without changing simulation."""
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
 Frame a{};a.time=1;a.flags=3;a.rotation.w=1;Frame b=a;b.time+=1./30;b.sky.mirror=1;b.camera.x=100;
 assert(sceneFramesCut(a,b));assert(interpolate(a,b,1.01).sky.mirror==0);
 assert(interpolate(a,b,b.time).sky.mirror==1);
 Frame c=b;c.time+=1./30;c.camera.x=200;
 assert(!sceneFramesCut(b,c));assert(std::abs(interpolate(b,c,(b.time+c.time)/2).camera.x-150)<.01);
 assert(SDL_Init(SDL_INIT_VIDEO));
 for(const char*driver:{"opengl","software"}){
 auto*w=SDL_CreateWindow("mirror regression",128,96,SDL_WINDOW_HIDDEN);
 auto*r=SDL_CreateRenderer(w,driver);assert(r);CourseMesh mesh;
 for(auto pixels:std::vector<std::array<uint8_t,16>>{
  {255,0,0,255,0,255,0,255,0,0,255,255,255,255,0,255},
  {255,0,255,255,255,0,255,255,255,0,255,255,255,0,255,255}}){
  auto*t=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA32,SDL_TEXTUREACCESS_STATIC,2,2);assert(t);
  assert(SDL_UpdateTexture(t,nullptr,pixels.data(),8));SDL_SetTextureScaleMode(t,SDL_SCALEMODE_NEAREST);mesh.textures.push_back(t);
 }
 auto quad=[](float x,float y,float z,float radius,unsigned tex,int bias=0){MeshQuad q{};q.texture=tex;q.bias=bias;
  q.v[0]={{x-radius,y-radius,z},0,0};q.v[1]={{x+radius,y-radius,z},1,0};
  q.v[2]={{x-radius,y+radius,z},0,1};q.v[3]={{x+radius,y+radius,z},1,1};return q;};
 mesh.quads={quad(-20,0,100,12,0),quad(-20,0,100,3,1,-10)};
 // A model and a near-clipped face exercise both production paths.
 mesh.models={{quad(0,0,100,8,0)}};
 auto clipped=quad(0,20,40,8,1);clipped.v[0].position.z=10;mesh.quads.push_back(clipped);
 Frame normal{};normal.rotation.w=1;normal.flags=3;
 normal.models.push_back({7,0,{22,-5,0},{1,0,0,0,1,0,0,0,1},0});
 Frame mirror=normal;mirror.sky.mirror=1;
 for(int width:{128,170})for(bool perspective:{true,false}){
  int height=96;mesh.perspective=perspective;
  auto*target=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA8888,SDL_TEXTUREACCESS_TARGET,width,height);assert(target);
  auto render=[&](const Frame&f){
   SDL_SetRenderTarget(r,target);SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderClear(r);
   mesh.draw(r,f,{},width,height);auto*s=SDL_RenderReadPixels(r,nullptr);assert(s);return s;
  };
  auto*left=render(normal);auto originalFaces=mesh.faces;auto count=mesh.faces.size();assert(count>=7);
  auto*right=render(mirror);assert(mesh.faces.size()==count);
  for(size_t i=0;i<count;i++){
   const auto&before=originalFaces[i];const auto&after=mesh.faces[i];
   assert(before.texture==after.texture&&before.bias==after.bias&&before.depth==after.depth);
   for(int j=0;j<3;j++){
    auto u=before.vertices[j],v=after.vertices[j?3-j:0];
    assert(u.position.x==-v.position.x&&u.position.y==v.position.y&&u.position.z==v.position.z);
    assert(u.u==v.u&&u.v==v.v);
   }
  }
  int colored=0,differences=0;
  for(int y=0;y<height;y++)for(int x=0;x<width;x++){
   Uint8 ar,ag,ab,aa,br,bg,bb,ba;
   assert(SDL_ReadSurfacePixel(left,x,y,&ar,&ag,&ab,&aa));
   assert(SDL_ReadSurfacePixel(right,width-1-x,y,&br,&bg,&bb,&ba));
   colored+=(ar||ag||ab);differences+=(ar!=br||ag!=bg||ab!=bb);

  }
  assert(colored>500); // Prevent an empty scene from passing.
  // Production OpenGL must be pixel-exact. For the approximate software
  // fallback, assert reflected vertices/UVs above, not rasterizer equivalence.
  if(std::strcmp(driver,"opengl")==0)assert(differences==0);
  SDL_DestroySurface(left);SDL_DestroySurface(right);
  SDL_SetRenderTarget(r,nullptr);SDL_DestroyTexture(target);
 }
 mesh.close();SDL_DestroyRenderer(r);SDL_DestroyWindow(w);
 }
 SDL_Quit();
}
'''
class MirrorTests(unittest.TestCase):
    def test_world_models_textures_and_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(HARNESS)
            flags=shlex.split(subprocess.check_output(['/opt/homebrew/bin/pkg-config','--cflags','--libs','sdl3'],text=True))
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),*flags,'-framework','OpenGL','-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True,capture_output=True,timeout=30)
