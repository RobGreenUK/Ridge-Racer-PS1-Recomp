"""Readable mirror signage must not unmirror the road or neighbouring atlas tiles."""
from pathlib import Path
import shlex,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#define main ridge_preview_main
#include "preview.cpp"
#undef main
#include <cassert>
int main(){
 auto region=[](int u0,int v0,int u1,int v1){MeshQuad q{};
  q.v[0].u=q.v[2].u=u0/256.f;q.v[1].u=q.v[3].u=u1/256.f;
  q.v[0].v=q.v[1].v=v0/256.f;q.v[2].v=q.v[3].v=v1/256.f;return q;};
 auto checkpoint=region(128,192,255,223);identifyMirrorSign(checkpoint,24,31555);
 assert(checkpoint.mirrorAxis==1&&checkpoint.mirrorSum==383/256.f);
 auto zoom=region(9,202,39,222);identifyMirrorSign(zoom,24,31553);assert(zoom.mirrorSum==48/256.f);
 auto arrow=region(0,0,31,31);identifyMirrorSign(arrow,24,31555);assert(!arrow.mirrorAxis);
 auto otherPalette=region(128,192,255,223);identifyMirrorSign(otherPalette,24,1);assert(!otherPalette.mirrorAxis);
 auto rotated=region(176,66,191,117);identifyMirrorSign(rotated,29,30857);
 assert(rotated.mirrorAxis==2&&rotated.mirrorSum==183/256.f);
 auto triangle=region(2,146,92,158);triangle.v[3]=triangle.v[1];identifyMirrorSign(triangle,29,31311);
 assert(triangle.mirrorAxis==1&&triangle.mirrorSum==94/256.f);
 Frame f{};f.rotation.w=1;f.sky.mirror=1;
 ModelPose board{1,146,{100,200,300},{1,0,0,0,1,0,0,0,1},0};f.models.push_back(board);
 MirrorDisplay display(f);assert(display.active);
 ModelPose patch=board;patch.model=147;patch.position.z+=80;
 auto reflected=display.pose(patch);assert(reflected.position.z==220&&reflected.matrix[8]==-1);
 auto twice=display.pose(reflected);assert(twice.position.z==patch.position.z&&twice.matrix==patch.matrix);
 patch.model=154;assert(display.applies(patch));patch.model=247;assert(!display.applies(patch));
 f.sky.mirror=0;assert(!MirrorDisplay(f).active);f.sky.mirror=1;f.models.clear();assert(!MirrorDisplay(f).active);
 assert(SDL_Init(SDL_INIT_VIDEO));auto*w=SDL_CreateWindow("readable sign",128,96,SDL_WINDOW_HIDDEN);
 auto*r=SDL_CreateRenderer(w,"opengl");assert(r);CourseMesh mesh;
 uint8_t pixels[]={255,0,0,255,0,255,0,255,0,0,255,255,255,255,0,255};
 auto*t=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA32,SDL_TEXTUREACCESS_STATIC,2,2);assert(t);
 SDL_UpdateTexture(t,nullptr,pixels,8);SDL_SetTextureScaleMode(t,SDL_SCALEMODE_NEAREST);mesh.textures.push_back(t);
 MeshQuad q{};q.mirrorAxis=1;q.mirrorSum=1;
 q.v[0]={{-20,-15,100},0,0};q.v[1]={{20,-15,100},1,0};q.v[2]={{-20,15,100},0,1};q.v[3]={{20,15,100},1,1};mesh.quads={q};
 auto*target=SDL_CreateTexture(r,SDL_PIXELFORMAT_RGBA8888,SDL_TEXTUREACCESS_TARGET,128,96);
 for(bool perspective:{true,false}){
  mesh.perspective=perspective;
  auto draw=[&](bool mirror){Frame a{};a.rotation.w=1;a.sky.mirror=mirror;
   SDL_SetRenderTarget(r,target);SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderClear(r);mesh.draw(r,a,{},128,96);
   auto*s=SDL_RenderReadPixels(r,nullptr);assert(s);return s;};
  auto*normal=draw(false);auto*mirrored=draw(true);int colored=0;
  for(int y=0;y<96;y++)for(int x=0;x<128;x++){
   Uint8 a,b,c,d,e,g,h,j;SDL_ReadSurfacePixel(normal,x,y,&a,&b,&c,&d);SDL_ReadSurfacePixel(mirrored,x,y,&e,&g,&h,&j);
   assert(a==e&&b==g&&c==h);colored+=a||b||c;
  }
  assert(colored>1000);SDL_DestroySurface(normal);SDL_DestroySurface(mirrored);
 }
 SDL_SetRenderTarget(r,nullptr);mesh.close();SDL_DestroyTexture(target);SDL_DestroyRenderer(r);SDL_DestroyWindow(w);SDL_Quit();
}
'''
class MirrorSignTests(unittest.TestCase):
    def test_atlas_selection_composite_display_and_readable_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(HARNESS)
            flags=shlex.split(subprocess.check_output(['/opt/homebrew/bin/pkg-config','--cflags','--libs','sdl3'],text=True))
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),*flags,'-framework','OpenGL','-o',str(p/'test')],check=True,capture_output=True)
            result=subprocess.run([str(p/'test')],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
