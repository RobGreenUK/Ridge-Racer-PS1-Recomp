#include "../platform/mapped_file.h"
#pragma once
#include "vram_protocol.h"
class VramClient {
    int fd=-1;const RRVram*shared=nullptr;uint32_t sequence=0;
public:
    bool poll(const std::string&socket,std::vector<uint16_t>&words){
        if(fd<0){
            fd=::open((socket+".vram").c_str(),O_RDONLY);if(fd<0)return false;
            struct stat st{};if(fstat(fd,&st)||st.st_size!=sizeof(RRVram)){::close(fd);fd=-1;return false;}
            void*p=mmap(nullptr,sizeof(RRVram),PROT_READ,MAP_SHARED,fd,0);
            if(p==MAP_FAILED){::close(fd);fd=-1;return false;}shared=static_cast<const RRVram*>(p);
        }
        if(flock(fd,LOCK_SH|LOCK_NB)<0)return false;
        bool changed=shared->magic==RR_VRAM_MAGIC&&shared->sequence!=sequence;
        if(changed){sequence=shared->sequence;words.assign(shared->words,shared->words+524288);}
        flock(fd,LOCK_UN);return changed;
    }
    ~VramClient(){if(shared)munmap((void*)shared,sizeof *shared);if(fd>=0)::close(fd);}
};
