/* Opt-in validation driver. Chooses digital controls from track geometry;
 * never edits physics, progress, timers, or car/camera transforms. */
#include "mod_plugins.h"
#include "usa_layout.h"
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
struct Point {double x,z;};
static struct Point node(uint32_t table,int i,int n){
    i=(i%n+n)%n;uint32_t a=table+(unsigned)i*20;
    return(struct Point){(int32_t)psx_mod_read_word(RR_TRACK_MIRROR_X)-(int32_t)psx_mod_read_word(a)/16384,
                        (int32_t)psx_mod_read_word(a+4)/16384};
}
uint16_t ridge_test_drive(void){
    static double last_x,last_z,last_yaw;static int initialized,previous_node,direction;static uint32_t last_table;
    if(psx_mod_read_half(RR_STATE)!=1||psx_mod_read_half(RR_PAUSED))return 0xffff;
    uint32_t table=psx_mod_read_word(RR_TRACK_POINTER);int n=psx_mod_read_word(RR_TRACK_COUNT);
    if(!((table==0x80057d64u||table==0x80059164u)&&n==256)&&!(table==0x8005a564u&&n==368))return 0xffff;
    double x=(int32_t)psx_mod_read_word(RR_PLAYER+16),z=(int32_t)psx_mod_read_word(RR_PLAYER+24);
    double yaw=(int32_t)psx_mod_read_word(RR_PLAYER+36)*6.283185307179586/4096;
    double speed=initialized?hypot(x-last_x,z-last_z):0,yaw_rate=initialized?remainder(yaw-last_yaw,6.283185307179586):0;
    if(speed>500){speed=0;yaw_rate=0;}
    initialized=1;last_x=x;last_z=z;last_yaw=yaw;
    double best=1e30;int nearest=0;int fresh=last_table!=table;
    for(int j=0;j<(fresh?n:17);j++){int i=fresh?j:(previous_node+j-8+n)%n;struct Point p=node(table,i,n);double d=(p.x-x)*(p.x-x)+(p.z-z)*(p.z-z);if(d<best){best=d;nearest=i;}}
    struct Point ahead=node(table,nearest+1,n),behind=node(table,nearest-1,n);
    if(fresh)direction=((ahead.x-behind.x)*sin(yaw)+(ahead.z-behind.z)*cos(yaw))>=0?1:-1;
    previous_node=nearest;last_table=table;
    struct Point target=node(table,nearest+direction,n);
    // Look beyond the nearest point, but slow down for large heading corrections.
    if(hypot(target.x-x,target.z-z)<350)target=node(table,nearest+2*direction,n);
    double error=remainder(atan2(target.x-x,target.z-z)-yaw,6.283185307179586);
    double control=error-5*yaw_rate;
    double limit=fabs(error)>.45?25:(fabs(error)>.2?38:55);
    const char*setting=getenv("RIDGE_TEST_SPEED");if(setting){double chosen=atof(setting);if(chosen>=10&&chosen<=60&&limit>chosen)limit=chosen;}
    uint16_t pad=0xffff;
    if(speed<limit-1)pad&=~0x4000u;
    if(speed>limit+3)pad&=~0x8000u;
    if(control>.04)pad&=~0x20u;
    if(control<-.04)pad&=~0x80u;
    return pad;
}
