#pragma once
// Original triangle-strip topology and near clipping, with native GPU depth.
// Non-OpenGL diagnostic fallback uses perspective tessellation and sorting.
#include "geometry.h"
#include "texture_data.h"
#include "depth_renderer.h"
#include "scenery_layers.h"
#include <tuple>
struct MeshQuad { MeshVertex v[4]; uint32_t texture,kind; int32_t bias;uint32_t window=0,dayOnly=0;unsigned mirrorAxis=0;float mirrorSum=0; };
#include "mirror_signs.h"
#include "mirror_cars.h"
#include "car_shadows.h"
#include "shadow_ground.h"
#include "road_signs.h"
#include "car_contact.h"
inline bool nightScenery(const Frame&frame){
    if(frame.flags&RR_SCENE_NIGHT)return true;
    // Older marker recordings predate the explicit state bit. This draw site
    // and model range identify the game's nighttime replacement building list.
    for(const auto&p:frame.models)if(uint32_t(p.key)==0x80015ae4u&&p.model>=84&&p.model<=137)return true;
    return false;
}
struct CourseMesh {
    bool fullCourse=true,perspective=true;
    struct Face {float depth;uint32_t texture;int32_t bias;std::array<MeshVertex,3> vertices;size_t order;bool shadow=false;Vec contactPlane{};};
    std::vector<Face> faces;
    double buildMs=0,uploadMs=0,sortMs=0,depthMs=0;
    unsigned candidateTriangles=0,culledChunks=0,culledModels=0;
    struct Bounds {
        Vec low{INFINITY,INFINITY,INFINITY},high{-INFINITY,-INFINITY,-INFINITY};
        void add(Vec p){low={std::min(low.x,p.x),std::min(low.y,p.y),std::min(low.z,p.z)};high={std::max(high.x,p.x),std::max(high.y,p.y),std::max(high.z,p.z)};}
        bool visible(const Frame&frame,Vec camera,const ModelPose*pose,int width,int height)const{
            if(!std::isfinite(low.x))return false;
            bool outside[5]={true,true,true,true,true};float focal=height*(320.f/240),sx=width*.5f/focal,sy=height*.5f/focal;
            for(int i=0;i<8;i++){
                Vec v{i&1?high.x:low.x,i&2?high.y:low.y,i&4?high.z:low.z};
                if(pose){const auto&m=pose->matrix;v=pose->position+Vec{m[0]*v.x+m[1]*v.y+m[2]*v.z,m[3]*v.x+m[4]*v.y+m[5]*v.z,m[6]*v.x+m[7]*v.y+m[8]*v.z};}
                v=rotate(frame.rotation,v-camera);
                // Conservative margin avoids precision differences at boundaries.
                outside[0]&=v.z<12;outside[1]&=v.x+sx*v.z < -8;outside[2]&=sx*v.z-v.x < -8;
                outside[3]&=v.y+sy*v.z < -8;outside[4]&=sy*v.z-v.y < -8;
            }
            for(bool rejected:outside)if(rejected)return false;return true;
        }
    };
    static constexpr size_t chunkSize=64;
    std::vector<Bounds>chunkBounds,modelBounds;
    unsigned textureUpdates=0;
    std::vector<uint8_t> uploadPixels;
    SkyRenderer sky;
    DepthRenderer depthRenderer;
    std::vector<SDL_Texture*> textures;
    std::vector<MeshQuad> quads;
    std::vector<std::pair<int32_t,uint32_t>>textureKeys;
    std::vector<std::vector<MeshQuad>> models;
    using PaletteKey=std::tuple<int32_t,uint32_t,uint32_t,bool>;
    std::map<PaletteKey,uint32_t>paletteLookup;size_t indexedTextures=0;
    std::vector<uint32_t>textureWindows;
    std::vector<bool> textureDirty;
    std::vector<std::vector<uint16_t>> residentTexels;
    void prepareTexture(unsigned i){
        if(i>=textureDirty.size()||!textureDirty[i])return;
        auto [page,clut]=textureKeys[i];
        texturePixelsInto(uploadPixels,sky.vram,page,clut,i<textureWindows.size()?textureWindows[i]:0,i<residentTexels.size()?&residentTexels[i]:nullptr);
        if(!SDL_UpdateTexture(textures[i],nullptr,uploadPixels.data(),1024))throw std::runtime_error(SDL_GetError());
        textureDirty[i]=false;textureUpdates++;
    }
    void load(SDL_Renderer*renderer,const std::string&path) {
        std::ifstream in(path,std::ios::binary);in.exceptions(std::ios::badbit|std::ios::failbit);
        char magic[8];in.read(magic,8);if(std::memcmp(magic,"RRASSET1",8)&&std::memcmp(magic,"RRASSET2",8)&&std::memcmp(magic,"RRASSET3",8)&&std::memcmp(magic,"RRASSET4",8)&&std::memcmp(magic,"RRASSET5",8)&&std::memcmp(magic,"RRASSET6",8)&&std::memcmp(magic,"RRASSET7",8))throw std::runtime_error("invalid assets header");
        auto nt=u32(in),nq=u32(in);if(nt>4096||nq>100000||nt==0)throw std::runtime_error("invalid mesh counts");
        std::vector<uint8_t> pixels(256*256*4);
        for(unsigned i=0;i<nt;i++) {
            in.read((char*)pixels.data(),pixels.size());
            SDL_Texture*t=SDL_CreateTexture(renderer,SDL_PIXELFORMAT_RGBA32,SDL_TEXTUREACCESS_STATIC,256,256);
            if(!t||!SDL_UpdateTexture(t,nullptr,pixels.data(),256*4))throw std::runtime_error(SDL_GetError());
            SDL_SetTextureScaleMode(t,SDL_SCALEMODE_NEAREST);SDL_SetTextureBlendMode(t,SDL_BLENDMODE_BLEND);textures.push_back(t);
        }
        auto readQuad=[&](){
            MeshQuad q;q.texture=u32(in);q.kind=u32(in);q.bias=int32_t(u32(in));if(magic[7]>='5')q.window=u32(in);if(magic[7]>='6')q.dayOnly=u32(in);
            if(q.texture>=nt||q.kind>2||q.dayOnly>1)throw std::runtime_error("invalid quad attributes");
            for(auto&v:q.v){v.position=vec(in);v.u=f32(in);v.v=f32(in);}
            return q;
        };
        for(unsigned i=0;i<nq;i++)quads.push_back(readQuad());
        if(magic[7]>='2') {
            unsigned count=u32(in);if(count>4096)throw std::runtime_error("invalid model count");
            models.resize(count);
            for(auto&model:models){unsigned size=u32(in);if(size>10000)throw std::runtime_error("invalid model size");for(unsigned i=0;i<size;i++)model.push_back(readQuad());}
        }
        if(magic[7]>='3')sky.load(in);
        if(magic[7]>='4')for(unsigned i=0;i<nt;i++){int32_t page=int32_t(u32(in));auto clut=u32(in);textureKeys.emplace_back(page,clut);textureWindows.push_back(0);}
        if(magic[7]>='7'){
            residentTexels.resize(nt);textureDirty.resize(nt);
            unsigned count=u32(in);if(count>nt)throw std::runtime_error("invalid resident texture count");
            for(unsigned j=0;j<count;j++){
                unsigned i=u32(in);if(i>=nt||(textureKeys[i].first!=28&&textureKeys[i].first!=29)||!residentTexels[i].empty())throw std::runtime_error("invalid resident texture");
                auto&words=residentTexels[i];words.resize(16384);
                for(unsigned k=0;k<words.size();k+=2){auto packed=u32(in);words[k]=packed&65535;words[k+1]=packed>>16;}
                textureDirty[i]=true;
            }
        }
        auto identify=[&](MeshQuad&q){if(q.texture<textureKeys.size()){auto key=textureKeys[q.texture];identifyMirrorSign(q,key.first,key.second);}};
        for(auto&q:quads)identify(q);
        for(auto&model:models)for(auto&q:model)identify(q);
        chunkBounds.resize((quads.size()+chunkSize-1)/chunkSize);
        for(size_t i=0;i<quads.size();i++)for(const auto&v:quads[i].v)chunkBounds[i/chunkSize].add(v.position);
        modelBounds.resize(models.size());
        for(size_t i=0;i<models.size();i++)for(const auto&q:models[i])for(const auto&v:q.v)modelBounds[i].add(v.position);
        faces.reserve(quads.size()*2);
    }
    uint32_t paletteTexture(SDL_Renderer*renderer,uint32_t base,uint32_t packed,uint32_t window=0) {
        if(base>=textureKeys.size())return base;
        auto key=textureKeys[base];if(key.first<0)return base;
        key.second=packed>>16;
        bool resident=base<residentTexels.size()&&!residentTexels[base].empty();
        while(indexedTextures<textureKeys.size()){
            size_t i=indexedTextures++;
            paletteLookup.emplace(PaletteKey{textureKeys[i].first,textureKeys[i].second,i<textureWindows.size()?textureWindows[i]:0,i<residentTexels.size()&&!residentTexels[i].empty()},uint32_t(i));
        }
        auto found=paletteLookup.find(PaletteKey{key.first,key.second,window,resident});if(found!=paletteLookup.end())return found->second;
        if(textures.size()>=4096)throw std::runtime_error("too many model palettes");
        auto source=base<residentTexels.size()?residentTexels[base]:std::vector<uint16_t>{};
        auto rgba=texturePixels(sky.vram,key.first,key.second,window,&source);
        auto*t=SDL_CreateTexture(renderer,SDL_PIXELFORMAT_RGBA32,SDL_TEXTUREACCESS_STATIC,256,256);
        if(!t)throw std::runtime_error(SDL_GetError());
        if(!SDL_UpdateTexture(t,nullptr,rgba.data(),1024)){SDL_DestroyTexture(t);throw std::runtime_error(SDL_GetError());}
        SDL_SetTextureScaleMode(t,SDL_SCALEMODE_NEAREST);SDL_SetTextureBlendMode(t,SDL_BLENDMODE_BLEND);
        residentTexels.resize(textureKeys.size());residentTexels.push_back(std::move(source));
        textureWindows.resize(textureKeys.size());textureWindows.push_back(window);textureKeys.push_back(key);textures.push_back(t);return uint32_t(textures.size()-1);
    }
    void updateVram(const std::vector<uint16_t>&words) {
        TextureSignatures before{sky.vram,{}},after{words,{}};updateVram(words,before,after);
    }
    void updateVram(const std::vector<uint16_t>&words,TextureSignatures&before,TextureSignatures&after) {
        textureUpdates=0;
        if(words.size()!=524288)return;
        textureDirty.resize(textureKeys.size());
        for(size_t i=0;i<textureKeys.size();i++){
            auto [page,clut]=textureKeys[i];if(page<0)continue;
            // Resident scenery reads immutable texels, but still follows its live palette.
            bool resident=((page>>7)&3)==0&&i<residentTexels.size()&&residentTexels[i].size()==16384;
            if(before.get(page,clut,resident)==after.get(page,clut,resident))continue;
            textureDirty[i]=true;
        }
        if(sky.palette!=~0u&&(before.get(21,sky.palette)!=after.get(21,sky.palette)||before.get(22,sky.palette)!=after.get(22,sky.palette)))sky.close();
        sky.vram=words;
    }
    static MeshVertex lerp(MeshVertex a,MeshVertex b,float t) {
        return {a.position+(b.position-a.position)*t,a.u+(b.u-a.u)*t,a.v+(b.v-a.v)*t};
    }
    ShadowGround roadAt(Vec contact)const{
        ShadowGround ground;
        auto check=[&](const MeshQuad&q){float before=ground.distance;ground.consider(q.v[0].position,q.v[1].position,q.v[2].position,contact);ground.consider(q.v[2].position,q.v[1].position,q.v[3].position,contact);if(ground.distance<before)ground.depthBias=q.bias;};
        if(chunkBounds.empty()){for(const auto&q:quads)check(q);}
        else for(size_t chunk=0;chunk<chunkBounds.size();chunk++){
            const auto&b=chunkBounds[chunk];
            if(contact.x<b.low.x||contact.x>b.high.x||contact.z<b.low.z||contact.z>b.high.z||contact.y+32<b.low.y||contact.y-32>b.high.y)continue;
            for(size_t i=chunk*chunkSize;i<std::min(quads.size(),(chunk+1)*chunkSize);i++)check(quads[i]);
        }
        return ground;
    }
    void draw(SDL_Renderer*renderer,const Frame&frame,Vec camera,int width,int height) {
        const float cx=width/2.f,cy=height/2.f,focal=height*(320.f/240);
        uint64_t buildStart=SDL_GetTicksNS();buildMs=uploadMs=sortMs=depthMs=0;candidateTriangles=culledChunks=culledModels=0;
        bool depthPass=std::strcmp(SDL_GetRendererName(renderer),"opengl")==0;
        faces.clear();MirrorDisplay display(frame);
        std::array<std::pair<uint32_t,ShadowGround>,13> groundCache{};unsigned groundCount=0;
        Vec contactPlane{};
        for(const auto&p:frame.models)if(carShadowPart(p)&&p.model<models.size()&&!models[p.model].empty()){
            unsigned owner=uint32_t(p.key>>32),slot=0;
            while(slot<groundCount&&groundCache[slot].first!=owner)slot++;
            if(slot<groundCount||groundCount==groundCache.size())continue;
            Vec contact=p.position;contact.y+=models[p.model][0].v[0].position.y;
            groundCache[groundCount++]={owner,roadAt(contact)};
        }
        auto addTriangle=[&](const MeshQuad&q,const ModelPose*pose,std::array<int,3> order) {
            candidateTriangles++;
            if(pose&&(display.applies(*pose)||mirrorCarPart(frame,*pose)))std::swap(order[1],order[2]);
            const bool shadow=pose&&carShadowPart(*pose);
            int32_t layerBias=q.bias;
            if(depthPass&&pose&&q.texture<textureKeys.size()){
                auto key=textureKeys[q.texture];
                layerBias=sceneryLayerBias(pose->model,key.first,key.second,q.window,q.bias);
            }
            uint32_t texture=q.texture,packed=0;
            bool remap=((pose&&pose->paletteOffset)||q.window)&&q.texture<textureKeys.size()&&textureKeys[q.texture].first>=0;
            if(remap){
                packed=(textureKeys[q.texture].second<<16)|uint32_t(q.v[0].v*256)<<8|uint32_t(q.v[0].u*256);
                if(pose)packed+=pose->paletteOffset;
            }
            // PS1 FT4 order is a triangle strip (0,1,2,3), not a perimeter.
            std::array<MeshVertex,3> polygon;unsigned vertexIndex=0;float depth=0;
            for(int i:order){auto v=q.v[i];
                if(remap&&i==0){v.u=(packed&255)/256.f;v.v=((packed>>8)&255)/256.f;}
                if(frame.sky.mirror){if(q.mirrorAxis==1)v.u=q.mirrorSum-v.u;else if(q.mirrorAxis==2)v.v=q.mirrorSum-v.v;}
                if(pose){auto p=v.position;const auto&m=pose->matrix;v.position=pose->position+Vec{m[0]*p.x+m[1]*p.y+m[2]*p.z,m[3]*p.x+m[4]*p.y+m[5]*p.z,m[6]*p.x+m[7]*p.y+m[8]*p.z};}

                v.position=rotate(frame.rotation,v.position-camera);depth+=v.position.z;polygon[vertexIndex++]=v;}
            if(!fullCourse&&depth/3>18000)return;
            std::array<MeshVertex,4> clipped;size_t clippedCount=0;
            for(size_t i=0;i<polygon.size();i++) {
                auto a=polygon[i],b=polygon[(i+1)%polygon.size()];bool ai=a.position.z>=20,bi=b.position.z>=20;
                if(ai)clipped[clippedCount++]=a;
                if(ai!=bi)clipped[clippedCount++]=lerp(a,b,(20-a.position.z)/(b.position.z-a.position.z));
            }
            if(clippedCount<3)return;
            // USA 0x80047518 retains positive NCLIP area in the normal view.
            float area=0;
            for(size_t i=0;i<clippedCount;i++) {
                auto a=clipped[i].position,b=clipped[(i+1)%clippedCount].position;
                area+=(a.x/a.z)*(b.y/b.z)-(a.y/a.z)*(b.x/b.z);
            }
            if(area<=0)return;
            bool outside[4]={true,true,true,true};
            for(size_t k=0;k<clippedCount;k++){const auto&v=clipped[k];float x=cx+focal*v.position.x/v.position.z,y=cy+focal*v.position.y/v.position.z;
                outside[0]&=x<0;outside[1]&=x>width;outside[2]&=y<0;outside[3]&=y>height;}
            if(outside[0]||outside[1]||outside[2]||outside[3])return;
            if(remap)texture=paletteTexture(renderer,q.texture,packed,q.window);
            for(size_t i=1;i+1<clippedCount;i++){
                auto emit=[&](MeshVertex a,MeshVertex b,MeshVertex c){
                    // The hidden course mode reflects the projected world, not
                    // its simulation coordinates. Sky/HUD already use guest
                    // mirror state. Cull in the ordinary view, then reflect all
                    // world/model faces and restore winding for depth bias.
                    if(frame.sky.mirror){a.position.x=-a.position.x;b.position.x=-b.position.x;c.position.x=-c.position.x;std::swap(b,c);}
                    faces.push_back({(a.position.z+b.position.z+c.position.z)/3,texture,layerBias,{a,b,c},faces.size(),shadow,contactPlane});
                };
                if(depthPass||!perspective)emit(clipped[0],clipped[i],clipped[i+1]);
                else perspectiveTriangles(clipped[0],clipped[i],clipped[i+1],emit);
            }
        };
        auto addQuad=[&](const MeshQuad&q,const ModelPose*pose){addTriangle(q,pose,{0,1,2});addTriangle(q,pose,{2,1,3});};
        bool night=nightScenery(frame);
        if(chunkBounds.empty())for(const auto&q:quads)if(!q.dayOnly||!night)addQuad(q,nullptr);
        for(size_t chunk=0;chunk<chunkBounds.size();chunk++){
            if(!chunkBounds[chunk].visible(frame,camera,nullptr,width,height)){culledChunks++;continue;}
            for(size_t i=chunk*chunkSize;i<std::min(quads.size(),(chunk+1)*chunkSize);i++){const auto&q=quads[i];if(!q.dayOnly||!night)addQuad(q,nullptr);}
        }
        for(const auto&sourcePose:frame.models){
            auto pose=display.applies(sourcePose)?display.pose(sourcePose):sourcePose;
            if(mirrorCarPart(frame,sourcePose))pose=readableMirrorCar(pose);

            if(movableRoadSign(pose)&&pose.model<models.size())pose=supportedRoadSign(pose,models[pose.model]);
            // This isolated 26-quad facade has no enclosing structure on its
            // reverse side and floats above the expert extension when exposed
            // by full-course rendering. Omit only this authored instance.
            if(pose.model==179&&pose.key==0x8006e9dc800159c8ull)continue;
            if(pose.model<modelBounds.size()&&!modelBounds[pose.model].visible(frame,camera,&pose,width,height)){culledModels++;continue;}
            contactPlane={};
            if(carSolidPart(pose)||carShadowPart(pose))for(unsigned i=0;i<groundCount;i++){
                const auto&g=groundCache[i].second;
                if(groundCache[i].first!=uint32_t(pose.key>>32)||!g.valid)continue;
                contactPlane=carRoadDepthPlane(g,frame,camera,width,height);
                break;
            }
            if(pose.model<models.size())for(const auto&q:models[pose.model])addQuad(q,&pose);
        }
        // Decode/upload only textures needed by surviving faces. Dirty off-screen
        // variants retain their flag and use the newest VRAM when seen again.
        buildMs=double(SDL_GetTicksNS()-buildStart)/1e6;uint64_t uploadStart=SDL_GetTicksNS();
        for(const auto&face:faces)prepareTexture(face.texture);
        uploadMs=double(SDL_GetTicksNS()-uploadStart)/1e6;uint64_t sortStart=SDL_GetTicksNS();
        if(depthPass){
            std::sort(faces.begin(),faces.end(),[](const Face&a,const Face&b){if(a.shadow!=b.shadow)return !a.shadow;if(a.texture!=b.texture)return a.texture<b.texture;if(a.bias!=b.bias)return a.bias<b.bias;return a.order<b.order;});
            sortMs=double(SDL_GetTicksNS()-sortStart)/1e6;uint64_t depthStart=SDL_GetTicksNS();
            bool drawn=depthRenderer.draw(renderer,textures,faces,width,height,perspective);depthMs=double(SDL_GetTicksNS()-depthStart)/1e6;if(drawn)return;
        }
        // This approximate ordering is diagnostic, not a replacement for the
        // game's ordering-table/depth-bias rules (bridges/transparency pending).
        std::stable_sort(faces.begin(),faces.end(),[](const Face&a,const Face&b){return a.depth+a.bias*8>b.depth+b.bias*8;});
        std::vector<SDL_Vertex> vertices;
        uint32_t texture=0;
        auto flush=[&](){
            if(!vertices.empty()&&!SDL_RenderGeometry(renderer,textures[texture],vertices.data(),int(vertices.size()),nullptr,0))throw std::runtime_error(SDL_GetError());
            vertices.clear();
        };
        for(const auto&face:faces) {
            if(face.texture!=texture){flush();texture=face.texture;}
            for(const auto&v:face.vertices)vertices.push_back({{cx+focal*v.position.x/v.position.z,cy+focal*v.position.y/v.position.z},{1,1,1,face.shadow?.5f:1.f},{v.u,v.v}});
        }
        flush();
    }
    void close(){depthRenderer.close();sky.close();for(auto*t:textures)SDL_DestroyTexture(t);textures.clear();}
};
