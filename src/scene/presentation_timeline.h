#pragma once
#include "timeline.h"
#include <deque>
// Keep presentation advancing continuously rather than restarting on receipt.
// A short buffer absorbs the fractional producer/display sampling relationship.
struct PresentationTimeline {
    std::deque<ridge::Frame> frames;double offset=0,interval=1./30;mutable bool heldLatest=false;
    void clear(){frames.clear();offset=0;interval=1./30;}
    void push(ridge::Frame frame,double produced){
        double observed=frame.time-produced;
        if(frames.empty())offset=observed;
        else {
            double step=frame.time-frames.back().time;
            if(step<=0||step>.15||ridge::sceneFlagsCut(frames.back().flags,frame.flags)){clear();offset=observed;}
            else {
                // Correct slow clock drift, not per-frame scheduling noise.
                offset+=std::clamp(observed-offset,-.005,.005)*.01;
                if(step>interval*.5&&step<interval*1.5)interval+=(step-interval)*.05;
            }
        }
        frames.push_back(std::move(frame));while(frames.size()>8)frames.pop_front();
    }
    ridge::Frame at(double now,double displayInterval)const{
        heldLatest=false;if(frames.empty())return {};
        double time=now+offset-interval-displayInterval;
        if(time<=frames.front().time)return frames.front();
        auto upper=std::upper_bound(frames.begin(),frames.end(),time,[](double t,const ridge::Frame&f){return t<f.time;});
        if(upper==frames.end()){heldLatest=time>frames.back().time+.001;return frames.back();}
        return ridge::interpolate(*(upper-1),*upper,time);
    }
};
