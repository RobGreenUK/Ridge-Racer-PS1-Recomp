/* Independently paced native scene renderer. Every frame projects original
 * geometry at an interpolated camera/object pose; no completed-image blending. */
#include "timeline.h"
#include <SDL3/SDL.h>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>
#include <iostream>
#include <iomanip>
#include <csignal>
#if defined(__APPLE__) && defined(RIDGE_PRESENT_PROBE)
#include "present_probe.h"
#endif
#include "frame_metrics.h"
#include "frame_graph.h"
#include "frame_snapshot.h"
static volatile std::sig_atomic_t stopRequested=0;
static void stopPreview(int){stopRequested=1;}
using namespace ridge;
struct Node {Vec center;float halfWidth;};
static uint32_t u32(std::ifstream&in) { uint8_t b[4];in.read((char*)b,4);return b[0]|uint32_t(b[1])<<8|uint32_t(b[2])<<16|uint32_t(b[3])<<24; }
static float f32(std::ifstream&in) {uint32_t bits=u32(in);float f;std::memcpy(&f,&bits,4);if(!std::isfinite(f))throw std::runtime_error("non-finite recording");return f;}
static Vec vec(std::ifstream&in) {float x=f32(in),y=f32(in),z=f32(in);return{x,y,z};}
static double f64(std::ifstream&in) {uint64_t bits=u32(in);bits|=uint64_t(u32(in))<<32;double d;std::memcpy(&d,&bits,8);if(!std::isfinite(d))throw std::runtime_error("non-finite timestamp");return d;}
#include "sky_renderer.h"
#include "mesh.h"
#include "live_client.h"
#include "hud_renderer.h"
#include "screen_client.h"
#include "vram_client.h"
#include "display_pacer.h"
#ifdef __APPLE__
#include <mach/mach_time.h>
#endif
int main(int argc,char**argv) try {
    if(argc<2)throw std::runtime_error("usage: RidgeScenePreview recording.rrscene [--fps 60|120|144] [--seconds N] [--shot path.bmp] [--at seconds] [--game-camera]");
    double fps=60,seconds=0,at=0;std::string shot,assets,live,metricsPath,vramPath,vsync="off";bool fullCourse=true,perspective=true,showGraph=false;bool chase=true,control=false,fullscreen=false,statsOverlay=false;int width=1280,height=720;
    int firstOption=2;
    if(std::string(argv[1])=="--live"){if(argc<3)throw std::runtime_error("missing live socket");live=argv[2];firstOption=3;}
    for(int i=firstOption;i<argc;i++) {
        std::string arg=argv[i];
        if(arg=="--affine-textures"){perspective=false;continue;}
        if(arg=="--legacy-distance"){fullCourse=false;continue;}
        if(arg=="--game-camera"){chase=false;continue;}
        if(arg=="--frame-graph"){showGraph=true;continue;}
        if(arg=="--stats-overlay"){statsOverlay=true;continue;}
        if(arg=="--fullscreen"){fullscreen=true;continue;}
        if(arg=="--control"){control=true;continue;}
        if(i+1==argc)throw std::runtime_error("missing option value");
        if(arg=="--width")width=std::stoi(argv[++i]);
        else if(arg=="--height")height=std::stoi(argv[++i]);
        else if(arg=="--fps")fps=std::stod(argv[++i]);
        else if(arg=="--seconds")seconds=std::stod(argv[++i]);
        else if(arg=="--at")at=std::stod(argv[++i]);
        else if(arg=="--shot")shot=argv[++i];
        else if(arg=="--vsync")vsync=argv[++i];
        else if(arg=="--vram")vramPath=argv[++i];
        else if(arg=="--metrics")metricsPath=argv[++i];
        else if(arg=="--assets")assets=argv[++i];
        else throw std::runtime_error("unknown option");
    }
    if(!std::isfinite(fps)||(fps!=0&&fps<1)||fps>360||!std::isfinite(seconds)||seconds<0||!std::isfinite(at)||at<0)
        throw std::runtime_error("invalid playback settings");
    if(width<320||width>7680||height<240||height>4320)throw std::runtime_error("invalid rendering resolution");
    std::vector<Node>nodes;std::vector<Frame>frames;uint32_t nn=0,nf=0;
    if(live.empty()){
    std::ifstream in(argv[1],std::ios::binary);in.exceptions(std::ios::badbit|std::ios::failbit);
    char magic[8];in.read(magic,8);if(std::memcmp(magic,"RRSCENE1",8)&&std::memcmp(magic,"RRSCENE2",8)&&std::memcmp(magic,"RRSCENE3",8)&&std::memcmp(magic,"RRSCENE4",8)&&std::memcmp(magic,"RRSCENE5",8))throw std::runtime_error("invalid scene header");
    nn=u32(in);nf=u32(in);if(nn<3||nn>368||nf<2||nf>18000)throw std::runtime_error("invalid scene counts");
    nodes.resize(nn);for(auto&n:nodes){n.center=vec(in);n.halfWidth=f32(in);if(n.halfWidth<=0||n.halfWidth>1000)throw std::runtime_error("invalid width");}
    frames.resize(nf);
    for(size_t i=0;i<nf;i++) {
        auto&f=frames[i];f.time=f64(in);f.flags=u32(in);f.camera=vec(in);
        float x=f32(in),y=f32(in),z=f32(in),w=f32(in);f.rotation=normalized({x,y,z,w});
        f.car=vec(in);f.yaw=f32(in);if(f.time<0||(i&&f.time<=frames[i-1].time))throw std::runtime_error("non-increasing timeline");
        if(magic[7]>='2'){
            unsigned n=u32(in);if(n>RR_MODEL_CAP)throw std::runtime_error("invalid pose count");
            for(unsigned j=0;j<n;j++){
                ModelPose p;p.key=u32(in);p.key|=uint64_t(u32(in))<<32;p.model=u32(in);p.position=vec(in);
                for(auto&v:p.matrix)v=f32(in);if(magic[7]>='5')p.paletteOffset=u32(in);f.models.push_back(p);
            }
        }
        if(magic[7]>='3'){auto&s=f.sky;s.pitch=f32(in);s.yaw=f32(in);s.roll=f32(in);s.mirror=u32(in);s.clut=u32(in);s.rgb=u32(in);s.enabled=u32(in);}
        if(magic[7]>='4'){unsigned count=u32(in);if(count>RR_HUD_CAP)throw std::runtime_error("oversized HUD");f.hud.resize(count);for(auto&w:f.hud)w=u32(in);}
    }
    }
    VramClient vramClient;std::vector<uint16_t>liveVram;ScreenClient screen;LiveClient client;if(!live.empty())client.open(live);
    if(!SDL_Init(SDL_INIT_VIDEO))throw std::runtime_error(SDL_GetError());
    SDL_Window*window=nullptr;SDL_Renderer*renderer=nullptr;
    if(!SDL_CreateWindowAndRenderer("Ridge Racer - native scene (experimental)",width,height,SDL_WINDOW_RESIZABLE,&window,&renderer))throw std::runtime_error(SDL_GetError());
    if(fullscreen){
        if(!SDL_SetWindowFullscreen(window,true))throw std::runtime_error(SDL_GetError());
        // Fullscreen is asynchronous on macOS. Resolve the final display and
        // drawable size before selecting the pacing rate and recording metadata.
        if(!SDL_SyncWindow(window))std::cerr<<"fullscreen transition: "<<SDL_GetError()<<"\n";
    }
    if(!SDL_SetRenderLogicalPresentation(renderer,width,height,SDL_LOGICAL_PRESENTATION_LETTERBOX))throw std::runtime_error(SDL_GetError());
    const float cx=width/2.f,cy=height/2.f,focal=height*(320.f/240);
    if(vsync!="off"&&vsync!="on"&&vsync!="adaptive")throw std::runtime_error("invalid vsync option");
    int syncValue=vsync=="off"?0:vsync=="adaptive"?-1:1;
    bool syncEnabled=SDL_SetRenderVSync(renderer,syncValue)&&syncValue!=0;
    if(!syncEnabled&&syncValue!=0){syncEnabled=SDL_SetRenderVSync(renderer,1);if(!syncEnabled)std::cerr<<"scene preview vsync unavailable: "<<SDL_GetError()<<"\n";}
    std::cerr << "scene preview backend: " << SDL_GetRendererName(renderer) << "\n";
    HudRenderer hud;CourseMesh mesh;mesh.fullCourse=fullCourse;mesh.perspective=perspective;if(!assets.empty())mesh.load(renderer,assets);
    if(!vramPath.empty()){
        std::ifstream in(vramPath,std::ios::binary|std::ios::ate);
        if(!in||in.tellg()!=1048576)throw std::runtime_error("invalid marker VRAM size");
        std::vector<uint16_t>words(524288);in.seekg(0);in.read((char*)words.data(),1048576);mesh.updateVram(words);
    }
    SDL_Texture*sceneTarget=SDL_CreateTexture(renderer,SDL_PIXELFORMAT_RGBA8888,SDL_TEXTUREACCESS_TARGET,width,height);
    if(!sceneTarget)throw std::runtime_error(SDL_GetError());
    SDL_SetTextureScaleMode(sceneTarget,SDL_SCALEMODE_LINEAR);
    FrameMetrics metrics(metricsPath);FrameGraph graph;
    #if defined(__APPLE__) || defined(_WIN32)
    GpuTimer renderTimer;
    const bool glRenderer=std::strcmp(SDL_GetRendererName(renderer),"opengl")==0;
    #endif
    stopRequested=0;std::signal(SIGTERM,stopPreview);std::signal(SIGINT,stopPreview);
    bool markRequested=false;std::string captureNotice;uint64_t noticeUntil=0;
    uint64_t keyboardUntil=0;
    bool focusRaised=false;
    bool running=true;uint64_t begin=SDL_GetTicksNS(),last=begin;double next=0;unsigned count=0;
    std::vector<double>intervals,sceneIntervals;unsigned sceneCount=0;bool lastReady=false;
    uint64_t drawNs=0,presentNs=0,eventNs=0,lastPresentEnd=begin;
    double frameEvents=0,frameInput=0,frameSleep=0,frameDisplayWait=0,previousRecordMs=0;
    unsigned displayWaitTimeouts=0;
    const SDL_DisplayID pacingDisplay=SDL_GetDisplayForWindow(window);
    const SDL_DisplayMode* mode=SDL_GetCurrentDisplayMode(pacingDisplay);
    std::cerr << "scene preview display Hz: " << (mode?mode->refresh_rate:0) << "\n";
    double displayHz=mode?mode->refresh_rate:0;
    double requestedFps=fps;if(fps==0)fps=displayHz>0?displayHz:60;
    double pacedFps=syncEnabled&&displayHz>0?std::min(fps,displayHz):fps;
    bool displayPaced=syncEnabled&&displayHz>0&&fps>=displayHz-.01;
    std::cerr<<"scene preview pacing: requested="<<fps<<" effective="<<pacedFps<<" vsync="<<syncEnabled<<"\n";
    bool earlyPresent=false;
    #ifdef __APPLE__
    DisplayPacer displayPacer;
    // Keep the wait ahead of drawing, not ahead of swapping. The compositor
    // receives the completed frame early in the display interval. Fixed FPS
    // below refresh, adaptive V-sync, windowed and non-GL paths retain SDL pacing.
    const char*earlyOverride=SDL_getenv("RIDGE_MAC_EARLY_PRESENT");
    if(fullscreen&&syncValue==1&&displayPaced&&glRenderer&&(!earlyOverride||std::strcmp(earlyOverride,"0")!=0)){
        if(displayPacer.open(metricsPath))earlyPresent=SDL_SetRenderVSync(renderer,0);
        if(!earlyPresent)displayPacer.close();
    }
    #endif
    #if defined(__APPLE__) && defined(RIDGE_PRESENT_PROBE)
    installProbe();
    #endif
    #if defined(__APPLE__) && defined(RIDGE_PRESENT_PHASE_TEST)
    if(!earlyPresent)throw std::runtime_error("Pacing test requires the fullscreen OpenGL display-link path with V-sync On and Display frame rate");
    #endif
    std::cerr<<"scene preview early presentation: "<<earlyPresent<<"\n";
    if(!metricsPath.empty()){
        std::ofstream info(metricsPath+".presentation.json");
        info<<"{\"requested_fps\":"<<requestedFps<<",\"effective_fps\":"<<pacedFps<<",\"display_hz\":"<<displayHz<<",\"vsync\":"<<(syncEnabled?"true":"false");
        int drawableWidth=0,drawableHeight=0;SDL_GetWindowSizeInPixels(window,&drawableWidth,&drawableHeight);
        info<<",\"presentation_strategy\":"<<std::quoted(earlyPresent?"mac-display-link-before-render":"sdl-swap");
        #if defined(__APPLE__) && defined(RIDGE_PRESENT_PHASE_TEST)
        info<<",\"presentation_test\":\"phase2ms\",\"presentation_phase_ms\":"<<(earlyPresent?2:0);
        #endif
        #if defined(__APPLE__) && defined(RIDGE_PRESENT_PROBE)
        info<<",\"presentation_probe\":true";
        #endif
        info<<",\"gpu_sampling\":\"alternating-render-and-depth; excludes-swap\"";
        info<<",\"sdl_version\":"<<SDL_GetVersion();
        #ifdef __APPLE__
        mach_timebase_info_data_t timebase{};mach_timebase_info(&timebase);
        const auto clockBefore=SDL_GetTicksNS(),hostTicks=mach_absolute_time(),clockAfter=SDL_GetTicksNS();
        info<<",\"handoff_trace_version\":1,\"handoff_trace_enabled\":"<<(displayPacer.trace?"true":"false");
        info<<",\"sdl_clock\":\"SDL_GetTicksNS\",\"cv_clock\":\"mach_absolute_time\"";
        info<<",\"mach_timebase_numer\":"<<timebase.numer<<",\"mach_timebase_denom\":"<<timebase.denom;
        info<<",\"calibration_sdl_before_ns\":"<<clockBefore<<",\"calibration_mach_ticks\":"<<hostTicks<<",\"calibration_sdl_after_ns\":"<<clockAfter;
        info<<",\"renderer_pid\":"<<getpid()<<",\"display_id\":"<<SDL_GetDisplayForWindow(window);
        #endif
        info<<",\"display_hz_numerator\":"<<(mode?mode->refresh_rate_numerator:0)<<",\"display_hz_denominator\":"<<(mode?mode->refresh_rate_denominator:0);
        info<<",\"fullscreen\":"<<((SDL_GetWindowFlags(window)&SDL_WINDOW_FULLSCREEN)?"true":"false");
        info<<",\"render_width\":"<<width<<",\"render_height\":"<<height<<",\"window_pixel_width\":"<<drawableWidth<<",\"window_pixel_height\":"<<drawableHeight;
        #if defined(__APPLE__) || defined(_WIN32)
        if(std::strcmp(SDL_GetRendererName(renderer),"opengl")==0){
            auto glText=[](GLenum name){const GLubyte*s=glGetString(name);return s?reinterpret_cast<const char*>(s):"unknown";};
            info<<",\"gpu_vendor\":"<<std::quoted(glText(GL_VENDOR))<<",\"gpu_renderer\":"<<std::quoted(glText(GL_RENDERER))<<",\"gl_version\":"<<std::quoted(glText(GL_VERSION));
        }
        #endif
        info<<"}";
    }
    uint64_t eventMarker=0,eventTime=0;
    while(running&&!stopRequested) {
        #ifdef __APPLE__
        if(earlyPresent){
            uint64_t waitStart=SDL_GetTicksNS();
            if(!displayPacer.wait()){
                ++displayWaitTimeouts;earlyPresent=false;displayPacer.close();
                if(!SDL_SetRenderVSync(renderer,syncValue))throw std::runtime_error(SDL_GetError());
                std::cerr<<"display-link timeout; restored SDL V-sync\n";
            }
            #if defined(RIDGE_PRESENT_PHASE_TEST)
            // Experimental build only: allow display-buffer recycling to progress
            // before submitting. This is a phase test, not a proven stall fix.
            if(earlyPresent)SDL_DelayPrecise(2000000);
            #endif
            frameDisplayWait+=double(SDL_GetTicksNS()-waitStart)/1e6;
        }
        #endif
        uint64_t eventStart=SDL_GetTicksNS();
        SDL_Event event;while(SDL_PollEvent(&event)){
            if(event.type==SDL_EVENT_KEY_DOWN&&!event.key.repeat&&event.key.key==SDLK_G)showGraph=!showGraph;
            #ifdef __APPLE__
            if(earlyPresent&&event.type==SDL_EVENT_WINDOW_DISPLAY_CHANGED&&SDL_GetDisplayForWindow(window)!=pacingDisplay){
                earlyPresent=false;displayPacer.close();
                if(!SDL_SetRenderVSync(renderer,syncValue))throw std::runtime_error(SDL_GetError());
                std::cerr<<"display changed; restored SDL V-sync\n";
            }
            #endif
            if(event.type==SDL_EVENT_KEY_DOWN&&!event.key.repeat&&event.key.key==SDLK_M){++eventMarker;eventTime=SDL_GetTicksNS();}
            if(event.type==SDL_EVENT_QUIT||(event.type==SDL_EVENT_KEY_DOWN&&event.key.key==SDLK_ESCAPE))running=false;
            if(event.type==SDL_EVENT_KEY_DOWN&&!event.key.repeat&&(event.key.key==SDLK_F8||event.key.key==SDLK_P)&&!metricsPath.empty())markRequested=true;
        }
        uint64_t eventEnd=SDL_GetTicksNS();eventNs+=eventEnd-eventStart;frameEvents+=double(eventEnd-eventStart)/1e6;
        uint64_t inputStart=SDL_GetTicksNS();
        if(control&&!live.empty()) {
            const bool*keys=SDL_GetKeyboardState(nullptr);uint16_t buttons=0xffff;
            if(keys[SDL_SCANCODE_RETURN])buttons&=~8;
            if(keys[SDL_SCANCODE_UP])buttons&=~0x10;
            if(keys[SDL_SCANCODE_RIGHT])buttons&=~0x20;
            if(keys[SDL_SCANCODE_DOWN])buttons&=~0x40;
            if(keys[SDL_SCANCODE_LEFT])buttons&=~0x80;
            if(keys[SDL_SCANCODE_X]||keys[SDL_SCANCODE_SPACE])buttons&=~0x4000;
            if(keys[SDL_SCANCODE_Z])buttons&=~0x8000;
            if(keys[SDL_SCANCODE_A])buttons&=~0x1000;
            if(keys[SDL_SCANCODE_S])buttons&=~0x2000;
            if(keys[SDL_SCANCODE_Q])buttons&=~0x0400;
            if(keys[SDL_SCANCODE_E])buttons&=~0x0800;
            // Send a neutral release briefly, then let the original controller backend resume.
            const uint64_t inputNow=SDL_GetTicksNS();
            if(buttons!=0xffff)keyboardUntil=inputNow+100000000;
            client.send_input(buttons,(SDL_GetWindowFlags(window)&SDL_WINDOW_INPUT_FOCUS)!=0&&inputNow<keyboardUntil);
        }
        frameInput+=double(SDL_GetTicksNS()-inputStart)/1e6;
        if(!running)break;
        uint64_t now=SDL_GetTicksNS();double elapsed=double(now-begin)/1e9;
        if(seconds>0&&elapsed>=seconds)break;
        if(!displayPaced&&elapsed<next){uint64_t sleepStart=SDL_GetTicksNS();SDL_DelayPrecise(uint64_t((next-elapsed)*1e9));frameSleep+=double(SDL_GetTicksNS()-sleepStart)/1e6;continue;}
        // Absolute deadlines preserve fractional rates and avoid accumulated drift.
        double lateMs=displayPaced?(count?std::max(0.,double(now-last)/1e9-1/pacedFps)*1000:0):std::max(0.,elapsed-next)*1000;
        next=(std::floor(elapsed*pacedFps)+1)/pacedFps;
        double t=live.empty()?std::fmod(elapsed+at,frames.back().time):elapsed;
        uint64_t sceneStart=SDL_GetTicksNS();
        Frame f{};bool ready=true;
        if(live.empty())f=sample(frames,t);else ready=client.poll(f,1/pacedFps);
        double sourceAgeStart=live.empty()?-1:client.sourceAgeMs();
        #if defined(__APPLE__) || defined(_WIN32)
        // Elapsed queries cannot nest. Alternate full-render and depth samples.
        bool measureRender=glRenderer&&!metricsPath.empty()&&(count%2==0);
        mesh.depthRenderer.measureGpu=!measureRender;
        if(measureRender)renderTimer.begin(count);
        #endif
        uint64_t screenStart=SDL_GetTicksNS();
        if(!live.empty())screen.poll(renderer,live);
        uint64_t vramStart=SDL_GetTicksNS();mesh.textureUpdates=0;
        if(!live.empty()&&vramClient.poll(live,liveVram)){TextureSignatures before{mesh.sky.vram,{}},after{liveVram,{}};hud.updateVram(before,after);mesh.updateVram(liveVram,before,after);}
        uint64_t vramEnd=SDL_GetTicksNS();
        Vec camera=f.camera;
        if(chase)camera=camera+rotate({-f.rotation.x,-f.rotation.y,-f.rotation.z,f.rotation.w},{0,-420,-1300});
        mesh.depthRenderer.frameId=count;mesh.depthRenderer.gpuMs=-1;mesh.depthRenderer.gpuFrame=-1;
        mesh.buildMs=mesh.uploadMs=mesh.sortMs=mesh.depthMs=0;mesh.candidateTriangles=mesh.culledChunks=mesh.culledModels=0;mesh.faces.clear();
        uint64_t drawStart=SDL_GetTicksNS();
        if(!SDL_SetRenderTarget(renderer,sceneTarget))throw std::runtime_error(SDL_GetError());
        SDL_SetRenderDrawColor(renderer,0,16,128,255);SDL_RenderClear(renderer);
        auto line=[&](Vec a,Vec b){
            a=rotate(f.rotation,a-camera);b=rotate(f.rotation,b-camera);
            constexpr float near=20;
            if(a.z<near&&b.z<near)return;
            if(a.z<near)a=a+(b-a)*((near-a.z)/(b.z-a.z));
            if(b.z<near)b=b+(a-b)*((near-b.z)/(a.z-b.z));
            SDL_RenderLine(renderer,cx+focal*a.x/a.z,cy+focal*a.y/a.z,cx+focal*b.x/b.z,cy+focal*b.y/b.z);
        };
        if(ready&&!assets.empty()){mesh.sky.draw(renderer,f,width,height);mesh.draw(renderer,f,camera,width,height);}
        else {
        std::vector<Vec>left(nn),right(nn);
        for(size_t i=0;i<nn;i++) {
            Vec tangent=nodes[(i+1)%nn].center-nodes[(i+nn-1)%nn].center;
            float length=std::hypot(tangent.x,tangent.z);
            if(length<1)continue;
            Vec side={tangent.z/length*nodes[i].halfWidth,0,-tangent.x/length*nodes[i].halfWidth};
            left[i]=nodes[i].center+side;right[i]=nodes[i].center-side;
        }
        SDL_SetRenderDrawColor(renderer,56,191,177,255);
        for(size_t i=0;i<nn;i++){size_t j=(i+1)%nn;line(left[i],left[j]);line(right[i],right[j]);line(left[i],right[i]);}
        }
        SDL_SetRenderDrawColor(renderer,255,184,84,255);
        Vec car[8];for(int i=0;i<8;i++) {
            float x=(i&1)?80:-80,z=(i&2)?170:-170,y=(i&4)?-60:0;
            car[i]=f.car+Vec{x*std::cos(f.yaw)+z*std::sin(f.yaw),y,-x*std::sin(f.yaw)+z*std::cos(f.yaw)};
        }
        if(ready&&chase&&f.models.empty())for(int i=0;i<8;i++)for(int bit:{1,2,4})if(!(i&bit))line(car[i],car[i|bit]);
        if(ready)hud.draw(renderer,f,mesh.sky.vram,width,height);
        SDL_SetRenderDrawColor(renderer,224,236,246,255);
        char label[220];std::snprintf(label,sizeof label,"NATIVE SCENE | %.0f fps target | t %.2fs | %s\nExperimental renderer | ESC closes.",fps,t,chase?"chase camera":"game camera");
        if(statsOverlay)SDL_RenderDebugText(renderer,20,20,label);
        bool menuShown=!ready&&screen.draw(renderer,width,height);
        if(control&&!focusRaised&&(ready||menuShown)){SDL_RaiseWindow(window);focusRaised=true;}
        if(!ready&&!menuShown)SDL_RenderDebugText(renderer,20,45,"Starting game... Original game window supplies audio and menus.");
        if(count)graph.add(elapsed,double(now-last)/1e6);
        if(showGraph)graph.draw(renderer,width,height,elapsed,pacedFps);
        unsigned marker=0;double markerMs=0;
        if(markRequested){
            uint64_t markStart=SDL_GetTicksNS();marker=++metrics.marker;markRequested=false;
            std::string prefix=metricsPath+".marker-"+std::to_string(marker);
            try {
            if(ready)saveFrameSnapshot(prefix+".rrscene",f);
            SDL_Surface*surface=SDL_RenderReadPixels(renderer,nullptr);
            if(!surface)throw std::runtime_error(SDL_GetError());
            bool saved=SDL_SaveBMP(surface,(prefix+".bmp").c_str());SDL_DestroySurface(surface);
            if(!saved)throw std::runtime_error(SDL_GetError());
            if(!mesh.sky.vram.empty()){std::ofstream dump(prefix+".vram",std::ios::binary);dump.exceptions(std::ios::failbit|std::ios::badbit);dump.write((const char*)mesh.sky.vram.data(),mesh.sky.vram.size()*2);}
            std::ofstream snapshot(prefix+".json");snapshot.exceptions(std::ios::failbit|std::ios::badbit);snapshot<<"{\"time\":"<<f.time<<",\"camera\":["<<f.camera.x<<","<<f.camera.y<<","<<f.camera.z<<"],\"models\":[";
            bool comma=false;for(const auto&p:f.models){if(comma)snapshot<<",";comma=true;snapshot<<"{\"key\":"<<p.key<<",\"model\":"<<p.model<<",\"palette\":"<<p.paletteOffset<<",\"position\":["<<p.position.x<<","<<p.position.y<<","<<p.position.z<<"]}";}snapshot<<"]}";
            captureNotice="Bug capture "+std::to_string(marker)+" saved";
            std::cerr<<captureNotice<<": "<<prefix<<"\n";
            }catch(const std::exception&e){captureNotice="Capture failed - see launcher log";std::cerr<<"bug capture failed: "<<e.what()<<"\n";}
            noticeUntil=SDL_GetTicksNS()+3000000000ull;
            markerMs=double(SDL_GetTicksNS()-markStart)/1e6;
        }
        if(!shot.empty() && (live.empty() || ((ready||menuShown) && elapsed>=at))) {
            SDL_Surface*surface=SDL_RenderReadPixels(renderer,nullptr);
            if(!surface||!SDL_SaveBMP(surface,shot.c_str()))throw std::runtime_error(SDL_GetError());
            SDL_DestroySurface(surface);if(live.empty())running=false;else shot.clear();
        }
        if(!metricsPath.empty()&&(elapsed<10||SDL_GetTicksNS()<noticeUntil)){
            float oldX=1,oldY=1;SDL_GetRenderScale(renderer,&oldX,&oldY);
            float noticeScale=std::max(1.5f,height/540.f);SDL_SetRenderScale(renderer,noticeScale,noticeScale);
            SDL_SetRenderDrawBlendMode(renderer,SDL_BLENDMODE_BLEND);SDL_SetRenderDrawColor(renderer,0,0,0,220);
            SDL_FRect box{8, height/noticeScale-28,340,24};SDL_RenderFillRect(renderer,&box);
            SDL_SetRenderDrawColor(renderer,255,255,255,255);
            SDL_RenderDebugText(renderer,16,height/noticeScale-20,SDL_GetTicksNS()<noticeUntil?captureNotice.c_str():"P or F8: save bug capture");
            SDL_SetRenderScale(renderer,oldX,oldY);
        }
        if(!SDL_SetRenderTarget(renderer,nullptr))throw std::runtime_error(SDL_GetError());
        SDL_SetRenderDrawColor(renderer,0,0,0,255);SDL_RenderClear(renderer);
        if(!SDL_RenderTexture(renderer,sceneTarget,nullptr,nullptr))throw std::runtime_error(SDL_GetError());
        uint64_t presentStart=SDL_GetTicksNS();drawNs+=presentStart-drawStart;
        if(!SDL_FlushRenderer(renderer))throw std::runtime_error(SDL_GetError());
        #if defined(__APPLE__) || defined(_WIN32)
        if(measureRender)renderTimer.end();
        #endif
        #if defined(__APPLE__) && defined(RIDGE_PRESENT_PROBE)
        probeFlush=probeUpdate=0;probeFlushBegin=probeFlushEnd=probeUpdateBegin=probeUpdateEnd=0;
        #endif
        uint64_t swapStart=SDL_GetTicksNS();
        SDL_RenderPresent(renderer);uint64_t presentEnd=SDL_GetTicksNS();presentNs+=presentEnd-presentStart;
        FrameDetail detail;detail.gap=count?double(now-lastPresentEnd)/1e6:0;detail.events=frameEvents;detail.input=frameInput;detail.sleep=frameSleep;detail.previousRecord=previousRecordMs;detail.sourceAgeStart=sourceAgeStart;
        detail.frameStart=now;detail.sourceSelect=sceneStart;detail.drawStart=drawStart;
        detail.flushStart=presentStart;detail.swapStart=swapStart;detail.presentEnd=presentEnd;
        detail.eventMarker=eventMarker;detail.eventTime=eventTime;
        #ifdef __APPLE__
        const auto& callback=displayPacer.sample;
        detail.callbackId=callback.id;detail.callbackSkipped=callback.skipped;
        detail.callbackEntry=callback.entry;detail.callbackExit=callback.exit;
        detail.waitStart=callback.waitStart;detail.waitEnd=callback.waitEnd;
        detail.currentHost=callback.currentHost;detail.outputHost=callback.outputHost;
        detail.currentFlags=callback.currentFlags;detail.outputFlags=callback.outputFlags;
        #endif
        detail.candidate=(presentEnd-swapStart>5000000?1:0)|(detail.callbackSkipped?2:0)|(count&&presentEnd-lastPresentEnd>1.5e9/pacedFps?4:0);
        detail.displayWait=frameDisplayWait;detail.displayWaitTimeouts=displayWaitTimeouts;
        #if defined(__APPLE__) && defined(RIDGE_PRESENT_PROBE)
        detail.nativeFlush=probeFlush;detail.drawableUpdate=probeUpdate;
        detail.nativeBegin=probeFlushBegin;detail.nativeEnd=probeFlushEnd;detail.updateBegin=probeUpdateBegin;detail.updateEnd=probeUpdateEnd;
        #endif
        detail.renderFlush=double(swapStart-presentStart)/1e6;detail.swap=double(presentEnd-swapStart)/1e6;
        #if defined(__APPLE__) || defined(_WIN32)
        if(measureRender){detail.gpuRender=renderTimer.ms;detail.gpuRenderFrame=renderTimer.frame;}
        #endif
        detail.meshBuild=mesh.buildMs;detail.textureUpload=mesh.uploadMs;detail.sort=mesh.sortMs;detail.depth=mesh.depthMs;
        detail.gpuMs=mesh.depthRenderer.gpuMs;detail.gpuFrame=mesh.depthRenderer.gpuFrame;
        detail.candidates=mesh.candidateTriangles;detail.faces=mesh.faces.size();detail.chunksCulled=mesh.culledChunks;detail.modelsCulled=mesh.culledModels;
        detail.sequenceGaps=client.sequenceGaps;detail.incompleteFrames=client.incompleteFrames;detail.held=ready&&client.heldLatest();
        detail.sceneFlags=f.flags;detail.phase=f.flags&65535;detail.paused=(f.flags>>16)&1;detail.focused=(SDL_GetWindowFlags(window)&SDL_WINDOW_INPUT_FOCUS)!=0;detail.graph=showGraph;
        uint64_t recordStart=SDL_GetTicksNS();
        metrics.record(count,elapsed,count?double(now-last)/1e6:0,lateMs,double(screenStart-sceneStart)/1e6,double(vramStart-screenStart)/1e6,double(vramEnd-vramStart)/1e6,double(presentStart-drawStart)/1e6-markerMs,double(presentEnd-presentStart)/1e6,ready,client.sequence(),client.sourceAgeMs(),f.models.size(),mesh.textureUpdates,f.camera.x,f.camera.y,f.camera.z,f.time,marker,markerMs,detail);
        previousRecordMs=double(SDL_GetTicksNS()-recordStart)/1e6;lastPresentEnd=presentEnd;frameEvents=frameInput=frameSleep=frameDisplayWait=0;
        if(count)intervals.push_back(double(now-last)/1e6);
        if(ready){sceneCount++;if(lastReady)sceneIntervals.push_back(double(now-last)/1e6);}
        lastReady=ready;last=now;count++;
    }
    double wall=double(SDL_GetTicksNS()-begin)/1e9;
    std::sort(intervals.begin(),intervals.end());
    double p95=intervals.empty()?0:intervals[size_t((intervals.size()-1)*.95)];
    double sceneDuration=0;for(double dt:sceneIntervals)sceneDuration+=dt/1000;
    std::sort(sceneIntervals.begin(),sceneIntervals.end());
    double sceneP95=sceneIntervals.empty()?0:sceneIntervals[size_t((sceneIntervals.size()-1)*.95)];
    std::cout<<"{\"presents\":"<<count<<",\"wall_seconds\":"<<wall<<",\"scene_presents\":"<<sceneCount<<",\"scene_interval_seconds\":"<<sceneDuration<<",\"scene_p95_interval_ms\":"<<sceneP95<<",\"p95_interval_ms\":"<<p95<<",\"target_fps\":"<<fps<<",\"draw_ms\":"<<double(drawNs)/1e6<<",\"present_ms\":"<<double(presentNs)/1e6<<",\"event_ms\":"<<double(eventNs)/1e6<<"}\n";
    client.send_input(0xffff,false);
    #if defined(__APPLE__) || defined(_WIN32)
    renderTimer.close();
    #ifdef __APPLE__
    displayPacer.close();
    #endif
    #endif
    screen.close();SDL_DestroyTexture(sceneTarget);hud.close();mesh.close();SDL_DestroyRenderer(renderer);SDL_DestroyWindow(window);SDL_Quit();return 0;
} catch(const std::exception&e){std::cerr<<"scene preview: "<<e.what()<<"\n";return 1;}
