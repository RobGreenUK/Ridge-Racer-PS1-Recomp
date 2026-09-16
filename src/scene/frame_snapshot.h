#pragma once
// Private same-host RRSCENE5 marker recording, readable by the normal preview.
// Two identical samples make the exact marked scene independently replayable.
inline void saveFrameSnapshot(const std::string&path,const ridge::Frame&f){
    std::ofstream out(path,std::ios::binary);out.exceptions(std::ios::badbit|std::ios::failbit);
    auto word=[&](uint32_t v){out.write((const char*)&v,4);};
    auto scalar=[&](float v){out.write((const char*)&v,4);};
    auto vector=[&](ridge::Vec v){scalar(v.x);scalar(v.y);scalar(v.z);};
    out.write("RRSCENE5",8);word(3);word(2);
    // Fallback ribbon is unused when loading the real asset bundle.
    for(int i=0;i<3;i++){vector({float(i*100),0,float(i==1?100:0)});scalar(50);}
    for(int sample=0;sample<2;sample++){
        double time=sample/30.;out.write((const char*)&time,8);word(f.flags);
        vector(f.camera);scalar(f.rotation.x);scalar(f.rotation.y);scalar(f.rotation.z);scalar(f.rotation.w);
        vector(f.car);scalar(f.yaw);word(f.models.size());
        for(const auto&p:f.models){word(uint32_t(p.key));word(uint32_t(p.key>>32));word(p.model);vector(p.position);for(float v:p.matrix)scalar(v);word(p.paletteOffset);}
        scalar(f.sky.pitch);scalar(f.sky.yaw);scalar(f.sky.roll);word(f.sky.mirror);word(f.sky.clut);word(f.sky.rgb);word(f.sky.enabled);
        word(f.hud.size());for(uint32_t v:f.hud)word(v);
    }
}
