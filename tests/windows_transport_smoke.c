/* Also runs natively on macOS to guard the unchanged Unix transport. */
#include "../src/platform/transport.h"
#include "../src/platform/mapped_file.h"
#include <stdlib.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"Transport check failed at line %d\n",__LINE__);return 1;}}while(0)
int main(int argc,char**argv){
    CHECK(argc==2);char a[512],b[512],file[512];
    snprintf(a,sizeof a,"%s.scene",argv[1]);snprintf(b,sizeof b,"%s.pad",argv[1]);snprintf(file,sizeof file,"%s.vram",argv[1]);
    RRSocket viewer=rr_socket(),engine=rr_socket();CHECK(viewer!=RR_INVALID_SOCKET&&engine!=RR_INVALID_SOCKET);
    CHECK(!rr_bind(viewer,a)&&!rr_bind(engine,b));CHECK(!rr_nonblocking(viewer)&&!rr_nonblocking(engine));
    CHECK(!rr_buffer(viewer,SO_RCVBUF,65536));RRAddress address;CHECK(!rr_address(&address,a));
    uint32_t sent=0x12345678,got=0;CHECK(rr_send(engine,&sent,sizeof sent,&address)==sizeof sent);
    uint64_t deadline=rr_clock_ns()+1000000000;int n;
    do{n=rr_receive(viewer,&got,sizeof got);}while(n<0&&rr_clock_ns()<deadline);CHECK(n==sizeof got&&got==sent);
    CHECK(!rr_address(&address,b));CHECK(rr_send(viewer,&sent,sizeof sent,&address)==sizeof sent);
    deadline=rr_clock_ns()+1000000000;
    do{n=rr_receive(engine,&got,sizeof got);}while(n<0&&rr_clock_ns()<deadline);CHECK(n==sizeof got&&got==sent);
    int fd=open(file,O_RDWR|O_CREAT|O_EXCL,0600);CHECK(fd>=0);CHECK(!ftruncate(fd,4096));
    uint32_t*w=mmap(NULL,4096,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);CHECK(w!=MAP_FAILED);
    CHECK(!flock(fd,LOCK_EX|LOCK_NB));*w=sent;CHECK(!flock(fd,LOCK_UN));
    int reader=open(file,O_RDONLY);CHECK(reader>=0);uint32_t*r=mmap(NULL,4096,PROT_READ,MAP_SHARED,reader,0);CHECK(r!=MAP_FAILED);
    CHECK(!flock(reader,LOCK_SH|LOCK_NB));CHECK(*r==sent);
    CHECK(flock(fd,LOCK_EX|LOCK_NB)<0);CHECK(!flock(reader,LOCK_UN));
    CHECK(!flock(fd,LOCK_EX|LOCK_NB));CHECK(!flock(fd,LOCK_UN));
    munmap(w,4096);munmap(r,4096);close(reader);close(fd);rr_socket_close(engine);rr_socket_close(viewer);remove(file);remove(a);remove(b);
    puts("Scene, input and shared-surface checks passed.");return 0;
}
