#pragma once
#include <algorithm>
#include <cstdint>
// SCUS-94300 race OT packets, mapped against hud-state capture and VRAM.
// Unknown packets, full-screen fades, and top TIME/POSITION stay centered.
inline int raceHudAnchor(const uint32_t*p,unsigned n,uint16_t page){
    if(!n)return 0;
    unsigned type=(p[0]>>24)&0xfc;
    if((type==0x64&&n==4)||((type==0x74||type==0x7c)&&n==3)){
        if(page!=5)return 0;
        int x=int16_t(p[1]),y=int16_t(p[1]>>16);
        unsigned clut=p[2]>>16,u=p[2]&255,v=(p[2]>>8)&255;
        // Short/long courses share the map rectangle, using CLUT 0x7a00/0x7a01.
        // Its two untextured arrow layers follow below.
        if(type==0x64&&x==8&&y==8&&(clut==0x7a00||clut==0x7a01)&&u==0&&v==104&&p[3]==0x00300048)return -1;
        // BEST TIME / TOTAL labels and digits share two known glyph palettes.
        if(type==0x74&&x>=8&&x<=72&&(y==64||y==72||y==88||y==96)&&
           (clut==0x7984||clut==0x79cf)&&v<=8)return -1;
        // The six gear-selection strips, including the highlighted palette.
        if(type==0x64&&x==8&&y>=176&&y<=216&&(y-176)%8==0&&
           clut>=0x7a01&&clut<=0x7a07&&p[3]==0x00080018&&v>=32&&v<=40)return -1;
        // Lap-time label and timing glyphs; position fraction to its left stays.
        if(type==0x74&&x>=248&&x<=304&&y>=24&&y<=56&&
           (clut==0x79cf||clut==0x7984)&&v<=8)return 1;
        if(clut==0x7984){
            if(type==0x64&&x==232&&y==152&&u==72&&v==72&&p[3]==0x00500050)return 1;
            if(type==0x64&&x==288&&y==216&&u==0&&v==96&&p[3]==0x00080010)return 1;
            if(type==0x74&&x>=264&&x<=304&&y>=208&&y<=216&&v<=16)return 1;
        }
    }
    // Mirror-course minimap uses a reversed textured quad instead of a sprite.
    if(type==0x2c&&n==9&&page==5&&((p[2]>>16)==0x7a00||(p[2]>>16)==0x7a01)&&
       (p[2]&65535)==0x9800&&(p[4]&65535)==0x9847&&
       (p[6]&65535)==0x6800&&(p[8]&65535)==0x6847){
        bool map=true;
        for(unsigned i=1;i<9;i+=2){int x=int16_t(p[i]),y=int16_t(p[i]>>16);map &= x>=8&&x<=80&&y>=8&&y<=56;}
        if(map)return -1;
    }
    if(type==0x28&&n==5){
        bool map=true,needle=true;
        for(unsigned i=1;i<5;i++){
            int x=int16_t(p[i]),y=int16_t(p[i]>>16);
            map &= x>=4&&x<=84&&y>=4&&y<=64;
            needle &= x>=232&&x<=312&&y>=152&&y<=232;
        }
        if(map)return -1;
        if(needle)return 1;
    }
    return 0;
}
inline float hudAnchorShift(int anchor,int width,int height){
    return anchor*std::max(0.f,(width-height*4.f/3.f)/2.f);
}
