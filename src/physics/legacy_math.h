#pragma once
#include <cstdint>
#include <initializer_list>
#include <cstring>
#include <stdexcept>
namespace ridge::physics {
inline int32_t wrap(int64_t v){return int32_t(uint32_t(v));}
inline int32_t mul(int32_t a,int32_t b){return wrap(int64_t(a)*b);}
inline int32_t add(int32_t a,int32_t b){return wrap(int64_t(a)+b);}
inline int32_t sub(int32_t a,int32_t b){return wrap(int64_t(a)-b);}
inline int32_t truncShift(int32_t v,unsigned shift){return v/int32_t(1u<<shift);}
struct Memory {
    uint8_t*ram;
    unsigned offset(uint32_t a,unsigned n) const {a&=0x1fffffff;if(a>=0x800000||(a&0x1fffff)+n>0x200000)throw std::runtime_error("physics memory bounds");return a&0x1fffff;}
    int32_t word(uint32_t a)const{int32_t v;std::memcpy(&v,ram+offset(a,4),4);return v;}
    int16_t half(uint32_t a)const{int16_t v;std::memcpy(&v,ram+offset(a,2),2);return v;}
    void half(uint32_t a,int16_t v){std::memcpy(ram+offset(a,2),&v,2);}
    void word(uint32_t a,int32_t v){std::memcpy(ram+offset(a,4),&v,4);}
    int sin(int angle)const{unsigned a=unsigned(angle)&4095;int sign=a>2048?-1:1;if(a>2048)a=4096-a;if(a>1024)a=2048-a;return sign*half(0x8007878c+a*2);}
    int cos(int angle)const{return sin(angle+1024);}
    int angle(int x,int y)const{
        if(!x)return y>0?1024:y<0?-1024:0;
        int64_t ax=x<0?-int64_t(x):x,ay=y<0?-int64_t(y):y;
        int v=ax>=ay?half(0x8005c254+unsigned((ay*1024)/ax)*2):1024-half(0x8005c254+unsigned((ax*1024)/ay)*2);
        return x>0?(y<0?-v:v):(y<0?2048+v:2048-v);
    }
};
inline int angleDelta(int a,int b){int delta=(b&4095)-(a&4095);if(delta>2048)delta-=4096;if(delta< -2048)delta+=4096;return delta;}
}
