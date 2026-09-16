#pragma once
/* File-backed shared surfaces, with nonblocking cross-process locking. */
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <io.h>
#include <fcntl.h>
#include <sys/stat.h>
#define LOCK_SH 1
#define LOCK_EX 2
#define LOCK_NB 4
#define LOCK_UN 8
#define PROT_READ 1
#define PROT_WRITE 2
#define MAP_SHARED 1
#define MAP_FAILED ((void*)-1)
static void* mmap(void*hint,size_t size,int protection,int flags,int fd,long offset){
    (void)hint;(void)flags;(void)offset;
    HANDLE file=(HANDLE)_get_osfhandle(fd);
    HANDLE mapping=CreateFileMappingA(file,NULL,(protection&PROT_WRITE)?PAGE_READWRITE:PAGE_READONLY,0,0,NULL);
    if(!mapping)return MAP_FAILED;
    void*p=MapViewOfFile(mapping,(protection&PROT_WRITE)?FILE_MAP_WRITE:FILE_MAP_READ,0,0,size);
    CloseHandle(mapping);return p?p:MAP_FAILED;
}
static int munmap(void*p,size_t size){(void)size;return UnmapViewOfFile(p)?0:-1;}
static int flock(int fd,int operation){
    OVERLAPPED offset={0};HANDLE file=(HANDLE)_get_osfhandle(fd);
    if(operation&LOCK_UN)return UnlockFileEx(file,0,MAXDWORD,MAXDWORD,&offset)?0:-1;
    DWORD flags=(operation&LOCK_EX?LOCKFILE_EXCLUSIVE_LOCK:0)|(operation&LOCK_NB?LOCKFILE_FAIL_IMMEDIATELY:0);
    return LockFileEx(file,flags,0,MAXDWORD,MAXDWORD,&offset)?0:-1;
}
#else
#include <sys/file.h>
#include <sys/mman.h>
#include <sys/stat.h>
#endif
#include <fcntl.h>
#include <unistd.h>
