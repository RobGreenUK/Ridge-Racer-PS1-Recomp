#include "presentation_mode.h"
/* Bounded, read-only evaluator of the USA scenery submission routines.
 * Only arithmetic/branches and local RAM/scratch accesses execute. Matrix and
 * draw calls are native operations; no guest CPU, GPU, I/O or clocks are touched.
 * A private visibility mask exposes the complete object lists, while the game's
 * phase/animation/object-state decisions still select the appropriate models. */
#include "models.h"
#include "cpu_state.h"
#include "../physics/legacy_math.h"
#include <algorithm>
#include <array>
#include <vector>
#include <unordered_map>
#include <cstdio>
#include <cstring>
#include <cstdlib>
extern "C" {extern unsigned char*g_psx_ram;}
namespace {
using Mat=std::array<int16_t,9>;
struct Eval {
 std::vector<uint8_t> ram;std::array<uint8_t,1024> scratch{};
 uint32_t r[32]{},pc,next,hi=0,lo=0;int pending=-1;uint32_t pendingValue=0;
 Mat rotation{},worldRotation{};int32_t translation[3]{},worldTranslation[3]{};bool worldPose=false;
 std::unordered_map<uint32_t,Mat> worldMatrices;
 std::vector<RRRawModel> output;
 bool full;
 Eval(const uint8_t*source,const CPUState*cpu,uint32_t entry,bool all):ram(source,source+2097152),pc(entry),next(entry+4),full(all){
  std::memcpy(r,cpu->gpr,sizeof r);r[31]=0;r[29]=0x801ff000;
 }
 uint8_t*address(uint32_t a,unsigned n){a&=0x1fffffff;if(a<0x800000&&(a&0x1fffff)+n<=ram.size())return ram.data()+(a&0x1fffff);if(a>=0x1f800000&&a+n<=0x1f800400)return scratch.data()+a-0x1f800000;throw std::runtime_error("scenery memory bounds");}
 uint32_t read(uint32_t a,unsigned n){if(full&&n==4&&(a&0x1fffffff)>=0x1dbb2c&&(a&0x1fffffff)<0x1dbbac)return ~0u;uint32_t v=0;std::memcpy(&v,address(a,n),n);return v;}
 void write(uint32_t a,uint32_t v,unsigned n){std::memcpy(address(a,n),&v,n);}
 Mat matrix(uint32_t a){Mat m;for(int i=0;i<9;i++)m[i]=int16_t(read(a+i*2,2));return m;}
 void matrix(uint32_t a,const Mat&m){worldMatrices.erase(a&0x1fffffff);for(int i=0;i<9;i++)write(a+i*2,uint16_t(m[i]),2);}
 Mat multiply(const Mat&a,const Mat&b){Mat m;for(int i=0;i<3;i++)for(int j=0;j<3;j++){int64_t s=0;for(int k=0;k<3;k++)s+=int(a[i*3+k])*b[k*3+j];m[i*3+j]=int16_t(s>>12);}return m;}
 bool helper(){
  using namespace ridge::physics;
  if(pc==0x80017e40||pc==0x80017eac||pc==0x80017f18){
   int s=Memory{ram.data()}.sin(int32_t(r[5])),c=Memory{ram.data()}.cos(int32_t(r[5]));
   Mat m={4096,0,0,0,4096,0,0,0,4096};int a=pc==0x80017f18?1:0,b=pc==0x80017e40?1:2;
   m[a*3+a]=m[b*3+b]=c;m[a*3+b]=-s;m[b*3+a]=s;matrix(r[4],m);return true;
  }
  if(pc==0x80047024){
   // Retain the pre-camera basis so stationary scenery never round-trips
   // through quantized camera coordinates in the native viewer.
   auto b=matrix(r[5]);auto old=worldMatrices.find(r[4]&0x1fffffff);Mat world{};
   bool known=(r[4]&0x1fffffff)==0x1ecd60||old!=worldMatrices.end();
   if(known)world=old!=worldMatrices.end()?multiply(old->second,b):b;
   matrix(r[5],multiply(matrix(r[4]),b));
   if(known)worldMatrices[r[5]&0x1fffffff]=world;
   r[2]=r[5];return true;
  }
  if(pc==0x80047130){auto m=matrix(r[4]);int16_t v[3];for(int i=0;i<3;i++)v[i]=int16_t(read(r[5]+i*2,2));for(int i=0;i<3;i++){int64_t s=0;for(int k=0;k<3;k++)s+=int(m[i*3+k])*v[k];write(r[6]+i*4,uint32_t(s>>12),4);}return true;}
  if(pc==0x80012148){
   rotation=matrix(r[6]);auto camera=matrix(0x801ecd60);int32_t v[3];
   auto found=worldMatrices.find(r[6]&0x1fffffff);
   worldPose=full&&((r[6]&0x1fffffff)==0x1ecd60||found!=worldMatrices.end());
   worldRotation=found!=worldMatrices.end()?found->second:Mat{4096,0,0,0,4096,0,0,0,4096};
   for(int i=0;i<3;i++)worldTranslation[i]=int32_t(read(r[5]+i*4,4)*4u);
   for(int i=0;i<3;i++){v[i]=int32_t(read(r[5]+i*4,4)-read(0x801dcb84+i*4,4));if(!full)v[i]=int16_t(v[i]);}
   for(int i=0;i<3;i++){int64_t s=0;for(int k=0;k<3;k++)s+=int64_t(camera[i*3+k])*v[k];translation[i]=int32_t((s>>12)*4);write(r[4]+44+i*4,translation[i],4);}
   // The original helper installs translation from scratch+18 (a4+24).
   return true;
  }
  if(pc==0x80048e54){r[2]=Memory{ram.data()}.sin(int32_t(r[4]));return true;}
  if(pc==0x800348e8||pc==0x80034f78||pc==0x80035f28||pc==0x800372b0){
   if(r[6]>=319)throw std::runtime_error("scenery model index");
   RRRawModel m{};m.model=r[6]|(worldPose?RR_MODEL_WORLD_POSE:0);m.site=r[31];m.palette_offset=r[7];
   // List records give repeated instances a stable identity. Other sites are
   // unique or use an occurrence index, stable while the full list is emitted.
   unsigned ordinal=0;for(const auto&old:output)if(old.site==m.site)ordinal++;
   m.owner=(m.site==0x800158b8||m.site==0x800159c8||m.site==0x80015ae4)?r[17]:0x70000000u+ordinal;
   for(int i=0;i<9;i++)m.rotation[i/2]|=uint32_t(uint16_t((worldPose?worldRotation:rotation)[i]))<<((i%2)*16);
   std::memcpy(m.translation,worldPose?worldTranslation:translation,sizeof translation);output.push_back(m);
   if(output.size()>RR_MODEL_CAP)throw std::runtime_error("scenery capacity");r[2]=r[4];return true;
  }
  return false;
 }
 void run(){
  for(unsigned steps=0;pc;steps++){
   if(steps>=50000)throw std::runtime_error("scenery instruction budget");
   if(helper()){pc=r[31];next=pc+4;continue;}
   if(pc<0x80015350||pc>=0x80017068)throw std::runtime_error("scenery call boundary");
   uint32_t w=read(pc,4),op=w>>26,s=(w>>21)&31,t=(w>>16)&31,d=(w>>11)&31,a=(w>>6)&31,fn=w&63;
   uint32_t x=r[s],y=r[t],nn=next+4;int32_t imm=int16_t(w);int old=pending,written=-1;uint32_t value=pendingValue;pending=-1;
   auto reg=[&](unsigned i,uint32_t v){if(i){r[i]=v;written=i;}};
   auto branch=[&](bool yes){if(yes)nn=pc+4+imm*4;};
   if(op==0){switch(fn){
    case 0:reg(d,y<<a);break;case 2:reg(d,y>>a);break;case 3:reg(d,int32_t(y)>>a);break;
    case 4:reg(d,y<<(x&31));break;case 6:reg(d,y>>(x&31));break;case 7:reg(d,int32_t(y)>>(x&31));break;
    case 8:nn=x;break;case 9:nn=x;reg(d,pc+8);break;case 16:reg(d,hi);break;case 18:reg(d,lo);break;
    case 24:case 25:{uint64_t v=fn==24?uint64_t(int64_t(int32_t(x))*int32_t(y)):uint64_t(x)*y;lo=v;hi=v>>32;break;}
    case 26:case 27:{int64_t xx=fn==26?int64_t(int32_t(x)):int64_t(x),yy=fn==26?int64_t(int32_t(y)):int64_t(y);if(!yy)throw std::runtime_error("scenery divide by zero");lo=xx/yy;hi=xx%yy;break;}
    case 32:case 33:reg(d,x+y);break;case 34:case 35:reg(d,x-y);break;
    case 36:reg(d,x&y);break;case 37:reg(d,x|y);break;case 38:reg(d,x^y);break;case 39:reg(d,~(x|y));break;
    case 42:reg(d,int32_t(x)<int32_t(y));break;case 43:reg(d,x<y);break;
    default:throw std::runtime_error("scenery SPECIAL");}
   }else switch(op){
    case 1:if(t>1)throw std::runtime_error("scenery branch");branch(t?int32_t(x)>=0:int32_t(x)<0);break;
    case 2:case 3:nn=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2);if(op==3)reg(31,pc+8);break;
    case 4:branch(x==y);break;case 5:branch(x!=y);break;case 6:branch(int32_t(x)<=0);break;case 7:branch(int32_t(x)>0);break;
    case 8:case 9:reg(t,x+imm);break;case 10:reg(t,int32_t(x)<imm);break;case 11:reg(t,x<uint32_t(imm));break;
    case 12:reg(t,x&(w&65535));break;case 13:reg(t,x|(w&65535));break;case 14:reg(t,x^(w&65535));break;case 15:reg(t,w<<16);break;
    case 32:case 33:case 35:case 36:case 37:{unsigned n=op==35?4:(op==33||op==37)?2:1;uint32_t v=read(x+imm,n);if(op==32)v=int8_t(v);if(op==33)v=int16_t(v);pending=t;pendingValue=v;break;}
    case 40:case 41:case 43:write(x+imm,y,op==43?4:op==41?2:1);break;
    default:throw std::runtime_error("scenery opcode");
   }
   if(old>0&&old!=written)r[old]=value;r[0]=0;pc=next;next=nn;
  }
 }
};
}
extern "C" int ridge_scenery_evaluate(const uint8_t*ram,const CPUState*cpu,uint32_t entry,int full,RRRawModel*out,unsigned capacity){
 try{Eval e(ram,cpu,entry,full!=0);e.run();if(e.output.size()>capacity)return -1;std::memcpy(out,e.output.data(),e.output.size()*sizeof *out);return int(e.output.size());}
 catch(const std::exception&e){static unsigned errors;if(errors++<5)std::fprintf(stderr,"scenery evaluator %08x: %s\n",entry,e.what());return -1;}
}

#include "mod_plugins.h"
namespace {
bool rootOwned=false,listOwned[3]{};std::vector<RRRawModel> reference;
unsigned checks=0,mismatches=0;
bool fullEnabled(){const char*s=std::getenv("RIDGE_SCENE_FULL_COURSE");return !s||std::strcmp(s,"0")!=0;}
void sceneryEntry(CPUState*cpu,uint32_t entry){
 if(!fullEnabled()||!ridge_world_state(psx_mod_read_half(0x801d6d28)))return;
 if(entry!=0x80015b90&&cpu->gpr[31]>=0x80015b90&&cpu->gpr[31]<0x80017068)return;
 RRRawModel models[RR_MODEL_CAP];int n=ridge_scenery_evaluate(g_psx_ram,cpu,entry,1,models,RR_MODEL_CAP);
 if(n<0||ridge_model_count+unsigned(n)>RR_MODEL_CAP){ridge_model_overflow++;return;}
 std::memcpy(ridge_models+ridge_model_count,models,n*sizeof *models);ridge_model_count+=n;
 if(entry==0x80015b90)rootOwned=true;
 else listOwned[entry==0x800157d8?0:entry==0x800158e8?1:2]=true;
 if(std::getenv("RIDGE_SCENE_EVAL_AUDIT")){
  int count=ridge_scenery_evaluate(g_psx_ram,cpu,entry,0,models,RR_MODEL_CAP);
  static unsigned auditEntries;if(auditEntries++<4)std::fprintf(stderr,"scenery audit entry=%08x reference=%d full=%d\n",entry,count,n);
  if(count>=0)reference.insert(reference.end(),models,models+count);
 }
}
}
extern "C" void ridge_scenery_reset(void){rootOwned=false;for(auto&v:listOwned)v=false;reference.clear();}
extern "C" int ridge_scenery_owns(uint32_t site){
 if(site==0x800158b8)return rootOwned||listOwned[0];
 if(site==0x800159c8)return rootOwned||listOwned[1];
 if(site==0x80015ae4)return rootOwned||listOwned[2];
 return rootOwned&&site>=0x800154b8&&site<0x80017068;
}
extern "C" void ridge_scenery_compare(const RRRawModel*actual){
 if(reference.empty())return;
 auto it=std::find_if(reference.begin(),reference.end(),[&](const RRRawModel&m){return m.site==actual->site&&m.model==actual->model;});
 if(it==reference.end())return;
 bool same=it->palette_offset==actual->palette_offset;
 for(int i=0;i<9;i++)same&=uint16_t(it->rotation[i/2]>>((i%2)*16))==uint16_t(actual->rotation[i/2]>>((i%2)*16));
 for(int i=0;i<3;i++)same&=it->translation[i]==actual->translation[i];
 checks++;if(checks%1000==0)std::fprintf(stderr,"scenery compare: %u checks, %u mismatches\n",checks,mismatches);if(!same&&mismatches++<5)std::fprintf(stderr,"scenery compare mismatch site=%08x model=%u native=(%d,%d,%d) original=(%d,%d,%d)\n",actual->site,actual->model,it->translation[0],it->translation[1],it->translation[2],actual->translation[0],actual->translation[1],actual->translation[2]);
 reference.erase(it);
}
static void reportScenery(){if(checks)std::fprintf(stderr,"scenery compare: %u checks, %u mismatches\n",checks,mismatches);}
PSX_MOD_CONSTRUCTOR(register_full_scenery){
 if(!std::getenv("RIDGE_SCENE_CAPTURE")&&!std::getenv("RIDGE_SCENE_SOCKET"))return;
 for(uint32_t entry:{0x80015b90u,0x800157d8u,0x800158e8u,0x800159f8u})psx_mod_register_function_entry_plugin("ridge.full_scenery",entry,sceneryEntry);
 std::atexit(reportScenery);
}
