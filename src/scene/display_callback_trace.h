#pragma once
#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
struct DisplayCallbackSample {
    uint64_t id=0,skipped=0,entry=0,exit=0,waitStart=0,waitEnd=0;
    uint64_t currentHost=0,outputHost=0,currentFlags=0,outputFlags=0;
};
// Independent callback-producer / file-writer queue. Never feed the render
// thread's SPSC metrics ring from a CoreVideo callback.
class DisplayCallbackTrace {
    struct Row {DisplayCallbackSample sample;uint64_t dropped;};
    static constexpr size_t capacity=2048;
    std::unique_ptr<std::array<Row,capacity>> ring;
    std::atomic<size_t> head{0},tail{0};
    std::atomic<bool> finished{false};
    uint64_t dropped=0;bool failed=false;
    FILE*file=nullptr;std::thread writer;
public:
    void open(const std::string&path){
        if(path.empty())return;
        file=std::fopen(path.c_str(),"w");if(!file)throw std::runtime_error("cannot open callback trace");
        try{ring=std::make_unique<std::array<Row,capacity>>();writer=std::thread([this]{run();});}
        catch(...){std::fclose(file);file=nullptr;throw;}
    }
    void record(const DisplayCallbackSample&sample){
        if(!ring)return;
        size_t h=head.load(std::memory_order_relaxed),next=(h+1)%capacity;
        if(next==tail.load(std::memory_order_acquire)){++dropped;return;}
        (*ring)[h]={sample,dropped};head.store(next,std::memory_order_release);
    }
    void run(){
        std::setvbuf(file,nullptr,_IOFBF,65536);
        std::fputs("callback_id,entry_ns,publish_ns,current_host,output_host,current_flags,output_flags,dropped\n",file);
        uint64_t flushed=0;
        for(;;){
            size_t t=tail.load(std::memory_order_relaxed);
            if(t==head.load(std::memory_order_acquire)){
                if(finished.load(std::memory_order_acquire)&&t==head.load(std::memory_order_acquire))break;
                std::this_thread::sleep_for(std::chrono::milliseconds(2));continue;
            }
            Row row=(*ring)[t];tail.store((t+1)%capacity,std::memory_order_release);auto&s=row.sample;
            if(std::fprintf(file,"%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu\n",
                (unsigned long long)s.id,(unsigned long long)s.entry,(unsigned long long)s.exit,
                (unsigned long long)s.currentHost,(unsigned long long)s.outputHost,
                (unsigned long long)s.currentFlags,(unsigned long long)s.outputFlags,
                (unsigned long long)row.dropped)<0)failed=true;
            if(s.entry-flushed>1000000000){if(std::fflush(file))failed=true;flushed=s.entry;}
        }
        if(std::fclose(file))failed=true;file=nullptr;
    }
    // Caller stops CoreVideo before joining; producer-owned drop count is then safe.
    void close(){
        finished.store(true,std::memory_order_release);
        if(writer.joinable()){
            writer.join();std::fprintf(stderr,"callback trace: dropped=%llu write_failed=%d\n",(unsigned long long)dropped,int(failed));
        }
    }
    ~DisplayCallbackTrace(){close();}
};
