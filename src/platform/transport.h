#pragma once
/* Private, nonblocking scene transport. Windows uses loopback UDP and a
 * session-local endpoint file; Unix retains its existing datagram sockets. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
typedef SOCKET RRSocket;
typedef struct sockaddr_in RRAddress;
#define RR_INVALID_SOCKET INVALID_SOCKET
static int rr_network_start(void){static int started;WSADATA data;if(!started){if(WSAStartup(MAKEWORD(2,2),&data))return -1;started=1;}return 0;}
static int rr_address(RRAddress*a,const char*path){unsigned port=0;FILE*f=fopen(path,"rb");if(!f)return -1;int n=fscanf(f,"%u",&port);fclose(f);if(n!=1||!port||port>65535)return -1;memset(a,0,sizeof *a);a->sin_family=AF_INET;a->sin_addr.s_addr=htonl(INADDR_LOOPBACK);a->sin_port=htons((unsigned short)port);return 0;}
static RRSocket rr_socket(void){if(rr_network_start())return RR_INVALID_SOCKET;return socket(AF_INET,SOCK_DGRAM,IPPROTO_UDP);}
static int rr_bind(RRSocket s,const char*path){RRAddress a;memset(&a,0,sizeof a);a.sin_family=AF_INET;a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);if(bind(s,(struct sockaddr*)&a,sizeof a))return -1;int size=sizeof a;if(getsockname(s,(struct sockaddr*)&a,&size))return -1;char temporary[600];if(snprintf(temporary,sizeof temporary,"%s.new",path)>=(int)sizeof temporary)return -1;FILE*f=fopen(temporary,"wx");if(!f)return -1;int ok=fprintf(f,"%u\n",ntohs(a.sin_port))>0;if(fclose(f)||!ok){remove(temporary);return -1;}if(!MoveFileA(temporary,path)){remove(temporary);return -1;}return 0;}
static int rr_nonblocking(RRSocket s){u_long mode=1;return ioctlsocket(s,FIONBIO,&mode);}
static void rr_socket_close(RRSocket s){closesocket(s);}
static uint64_t rr_clock_ns(void){LARGE_INTEGER count,freq;QueryPerformanceCounter(&count);QueryPerformanceFrequency(&freq);return (uint64_t)(count.QuadPart/freq.QuadPart)*1000000000u+(uint64_t)(count.QuadPart%freq.QuadPart)*1000000000u/freq.QuadPart;}
#else
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <fcntl.h>
#include <time.h>
typedef int RRSocket;
typedef struct sockaddr_un RRAddress;
#define RR_INVALID_SOCKET (-1)
static int rr_address(RRAddress*a,const char*path){if(strlen(path)>=sizeof a->sun_path)return -1;memset(a,0,sizeof *a);a->sun_family=AF_UNIX;strcpy(a->sun_path,path);return 0;}
static RRSocket rr_socket(void){return socket(AF_UNIX,SOCK_DGRAM,0);}
static int rr_bind(RRSocket s,const char*path){RRAddress a;if(rr_address(&a,path))return -1;return bind(s,(struct sockaddr*)&a,sizeof a);}
static int rr_nonblocking(RRSocket s){return fcntl(s,F_SETFL,O_NONBLOCK);}
static void rr_socket_close(RRSocket s){close(s);}
static uint64_t rr_clock_ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return(uint64_t)t.tv_sec*1000000000u+t.tv_nsec;}
#endif
static int rr_buffer(RRSocket s,int which,int bytes){return setsockopt(s,SOL_SOCKET,which,(const char*)&bytes,sizeof bytes);}
static int rr_receive(RRSocket s,void*p,int size){return recv(s,(char*)p,size,0);}
static int rr_send(RRSocket s,const void*p,int size,const RRAddress*a){return sendto(s,(const char*)p,size,0,(const struct sockaddr*)a,sizeof *a);}
