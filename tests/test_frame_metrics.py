"""Telemetry excludes intentional diagnostic stalls and replays marked scenes."""
import csv
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('analyze_frame_times',ROOT/'tools/analyze_frame_times.py')
analyzer=importlib.util.module_from_spec(spec);spec.loader.exec_module(analyzer)

class FrameMetricsTests(unittest.TestCase):
    def test_markers_and_partial_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'frames.csv'
            fields=['frame','wall_s','interval_ms','late_ms',*analyzer.STAGES,'ready','sequence','source_age_ms','models','texture_updates','camera_x','camera_y','camera_z','game_s','marker','marker_ms']
            with path.open('w') as out:
                writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
                for i in range(6):
                    r=dict.fromkeys(fields,0);r.update(frame=i,wall_s=i/120,ready=1,interval_ms=8.333)
                    if i==2:r.update(marker=1,marker_ms=200)
                    if i==3:r['interval_ms']=200
                    if i==4:r['interval_ms']=20
                    writer.writerow(r)
                out.write('7,0.1,')
            result=analyzer.summarize(path,120)
            self.assertEqual(result['race_frames'],3)
            self.assertEqual(result['over_1_5_budget'],1)
            self.assertEqual(len(result['markers']),1)
            self.assertEqual(result['timings']['interval_ms']['maximum'],20)
            Path(str(path)+'.presentation.json').write_text(json.dumps({'effective_fps':75,'vsync':True}))
            synced=analyzer.summarize(path,120)
            self.assertAlmostEqual(synced['budget_ms'],1000/75)
            self.assertEqual(synced['over_1_5_budget'],0)

    def test_record_and_snapshot_roundtrip(self):
        harness=r'''
#include <SDL3/SDL.h>
static bool hiddenTestWindow(const char*t,int w,int h,SDL_WindowFlags flags,SDL_Window**window,SDL_Renderer**renderer){return SDL_CreateWindowAndRenderer(t,w,h,flags|SDL_WINDOW_HIDDEN,window,renderer);}
#define SDL_CreateWindowAndRenderer hiddenTestWindow
#define main ridge_preview_main
#include "preview.cpp"
#undef main
#include <cassert>
int main(int argc,char**argv){
    Frame f{};f.rotation.w=1;f.camera={1,2,3};f.models.push_back({123,4,{5,6,7},{1,0,0,0,1,0,0,0,1},17});
    f.hud={2,0x600000ff,0};saveFrameSnapshot(std::string(argv[1])+".rrscene",f);
    {FrameMetrics m(std::string(argv[1])+".csv");FrameDetail detail;detail.renderFlush=.25;detail.swap=4.75;detail.gpuRender=1.5;detail.gpuRenderFrame=17;detail.displayWait=8;detail.displayWaitTimeouts=2;detail.sceneFlags=0x20003;detail.nativeFlush=4.5;detail.drawableUpdate=.125;m.record(1,1,8,0,1,2,3,4,5,true,42,6,1,7,1,2,3,4,1,8,detail);}
    std::string file=std::string(argv[1])+".rrscene";
    assert(SDL_Init(SDL_INIT_VIDEO));
    SDL_AddTimer(100,[](void*,SDL_TimerID,Uint32)->Uint32{SDL_Event e{};e.type=SDL_EVENT_KEY_DOWN;e.key.key=SDLK_P;SDL_PushEvent(&e);return 0;},nullptr);
    SDL_AddTimer(200,[](void*,SDL_TimerID,Uint32)->Uint32{SDL_Event e{};e.type=SDL_EVENT_KEY_DOWN;e.key.key=SDLK_M;SDL_PushEvent(&e);return 0;},nullptr);
    std::string metricPath=std::string(argv[1])+".live.csv";char metricsArg[]="--metrics";
    char app[]="preview",seconds[]="--seconds",duration[]="0.3",width[]="--width",w[]="320",height[]="--height",h[]="240";
    char*args[]={app,file.data(),seconds,duration,width,w,height,h,metricsArg,metricPath.data()};
    return ridge_preview_main(10,args);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(harness)
            flags=shlex.split(subprocess.check_output(['/opt/homebrew/bin/pkg-config','--cflags','--libs','sdl3'],text=True))
            subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'src/scene'),str(p/'test.cpp'),*flags,'-framework','OpenGL','-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test'),str(p/'capture')],check=True,capture_output=True,timeout=20)
            with (p/'capture.csv').open() as stream:rows=list(csv.DictReader(stream))
            self.assertTrue((p/'capture.live.csv.marker-1.bmp').is_file())
            self.assertFalse((p/'capture.live.csv.marker-2.bmp').exists())
            self.assertTrue((p/'capture.live.csv.marker-1.rrscene').is_file())
            with (p/'capture.live.csv').open() as stream:liveRows=list(csv.DictReader(stream))
            self.assertTrue(any(r['event_marker']=='1'for r in liveRows))
            self.assertEqual(sum(int(r['marker']) for r in liveRows),1)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['sequence'],'42')
            self.assertEqual(float(rows[0]['marker_ms']),8)
            self.assertEqual(float(rows[0]['render_flush_ms']),.25)
            self.assertEqual(float(rows[0]['swap_ms']),4.75)
            self.assertEqual(float(rows[0]['gpu_render_ms']),1.5)
            self.assertEqual(int(rows[0]['gpu_render_frame']),17)
            self.assertEqual(float(rows[0]['display_wait_ms']),8)
            self.assertEqual(int(rows[0]['display_wait_timeouts']),2)
            self.assertEqual(int(rows[0]['scene_flags']),0x20003)
            self.assertEqual(float(rows[0]['native_flush_ms']),4.5)
            self.assertEqual(float(rows[0]['drawable_update_ms']),.125)
            self.assertTrue(all(float(r['native_flush_ms']) == -1 and float(r['drawable_update_ms']) == -1 for r in liveRows))
            self.assertTrue(all(None not in r for r in liveRows))
            self.assertTrue(all(abs(float(r['present_ms'])-float(r['render_flush_ms'])-float(r['swap_ms']))<.001 for r in liveRows))
