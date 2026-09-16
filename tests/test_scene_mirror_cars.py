"""Car appearance stays normally handed while its position follows the mirrored course."""
from pathlib import Path
import shlex,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#define main ridge_preview_main
#include "preview.cpp"
#undef main
#include <cassert>
int main(){
 const uint32_t sites[]={0x80020d60,0x80020db0,0x80020e1c,0x80020e7c,0x80020ecc,0x80020f8c,0x8002102c};
 Frame mirror{};mirror.rotation.w=1;mirror.sky.mirror=1;
 for(unsigned car=0;car<13;car++)for(auto site:sites){
  uint32_t owner=car==12?0x80080194u:0x801ece34u+car*0x114u;
  ModelPose p{(uint64_t(owner)<<32)|site,0,{20,5,100},{1,0,0,0,1,0,0,0,1},17};
  assert(mirrorCarPart(mirror,p));auto fixed=readableMirrorCar(p);
  assert(p.matrix[0]==1&&fixed.matrix[0]==-1);assert(fixed.key==p.key&&fixed.paletteOffset==17);
  assert(fixed.position.x==20&&fixed.position.y==5&&fixed.position.z==100);
  assert(readableMirrorCar(fixed).matrix==p.matrix);
  Frame normal=mirror;normal.sky.mirror=0;assert(!mirrorCarPart(normal,p));
  auto wrong=p;wrong.key=(uint64_t(owner+1)<<32)|site;assert(!mirrorCarPart(mirror,wrong));
  wrong=p;wrong.key=(uint64_t(owner)<<32)|0x800159c8;assert(!mirrorCarPart(mirror,wrong));
 }
 assert(SDL_Init(SDL_INIT_VIDEO));auto*w=SDL_CreateWindow("mirror car decals",128,96,SDL_WINDOW_HIDDEN);
 auto*r=SDL_CreateRenderer(w,"opengl");assert(r);CourseMesh mesh;
 uint8_t pixels[]={255,0,0,255,0,255,0,255,0,0,255,255,255,255,0,255};
 auto*t=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA32,SDL_TEXTUREACCESS_STATIC,2,2);assert(t);
 SDL_UpdateTexture(t,nullptr,pixels,8);SDL_SetTextureScaleMode(t,SDL_SCALEMODE_NEAREST);mesh.textures.push_back(t);
 MeshQuad q{};q.v[0]={{-15,-12,0},0,0};q.v[1]={{15,-12,0},1,0};q.v[2]={{-15,12,0},0,1};q.v[3]={{15,12,0},1,1};mesh.models={{q}};
 auto*target=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA8888,SDL_TEXTUREACCESS_TARGET,128,96);assert(target);
 for(auto site:sites)for(bool perspective:{true,false})for(float turn:{-.3f,0.f,.3f}){
  mesh.perspective=perspective;
  ModelPose source{(uint64_t(0x801ece34u)<<32)|site,0,{20,0,100},{},0};
  Quat rotation=normalized({.05f,turn,.08f,1});
  for(int c=0;c<3;c++){auto v=rotate(rotation,{c==0?1.f:0.f,c==1?1.f:0.f,c==2?1.f:0.f});source.matrix[c]=v.x;source.matrix[c+3]=v.y;source.matrix[c+6]=v.z;}
  // The expected normal-handed pose on the reflected course is S*R*S.
  // Its translation is S*p, but source game state must remain untouched.
  auto expected=source;expected.position.x=-source.position.x;
  for(int row=0;row<3;row++)for(int col=0;col<3;col++)expected.matrix[row*3+col]*=(row==0?-1:1)*(col==0?-1:1);
  auto draw=[&](bool mirrored,const ModelPose&p){Frame f{};f.rotation.w=1;f.sky.mirror=mirrored;f.models={p};
   SDL_SetRenderTarget(r,target);SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderClear(r);mesh.draw(r,f,{},128,96);
   assert(f.models[0].matrix==p.matrix);assert(mesh.faces.size()==2);
   auto*s=SDL_RenderReadPixels(r,nullptr);assert(s);return s;};
  auto*a=draw(false,expected);auto*b=draw(true,source);int colored=0;
  for(int y=0;y<96;y++)for(int x=0;x<128;x++){
   Uint8 ar,ag,ab,aa,br,bg,bb,ba;SDL_ReadSurfacePixel(a,x,y,&ar,&ag,&ab,&aa);SDL_ReadSurfacePixel(b,x,y,&br,&bg,&bb,&ba);
   assert(ar==br&&ag==bg&&ab==bb);colored+=ar||ag||ab;
  }
  assert(colored>500);SDL_DestroySurface(a);SDL_DestroySurface(b);
 }
 SDL_SetRenderTarget(r,nullptr);mesh.close();SDL_DestroyTexture(target);SDL_DestroyRenderer(r);SDL_DestroyWindow(w);SDL_Quit();
}
'''
class MirrorCarTests(unittest.TestCase):
    def test_identity_part_transforms_and_normally_handed_decals(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(HARNESS)
            flags=shlex.split(subprocess.check_output(['/opt/homebrew/bin/pkg-config','--cflags','--libs','sdl3'],text=True))
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),*flags,'-framework','OpenGL','-o',str(p/'test')],check=True,capture_output=True)
            result=subprocess.run([str(p/'test')],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
