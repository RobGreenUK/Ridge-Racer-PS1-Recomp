from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
SOURCE=r'''
#include "hud.h"
#include "mod_plugins.h"
int psx_mod_register_function_entry_plugin(const char*id,uint32_t pc,PSXModFunctionEntryCallback cb){return 1;}
#include "usa_layout.h"
#include <stdint.h>
#include <assert.h>
#include <string.h>
static uint8_t ram[0x200000];static uint16_t state=1;
uint16_t psx_mod_read_half(uint32_t a){assert(a==RR_STATE);return state;}
uint32_t psx_mod_read_word(uint32_t a){uint32_t v;assert((a&0x1fffffff)<=0x1ffffc);memcpy(&v,ram+(a&0x1fffffff),4);return v;}
static void put(uint32_t a,uint32_t v){memcpy(ram+a,&v,4);}
int main(){
 put(0x130ea4,0x80010000);put(0x10b68,0x20000);put(0x20000,0x03010b6c);
 put(0x20004,0x75000000);put(0x20008,123);put(0x2000c,456);put(0x10b6c,0x00ffffff);
 ridge_hud_capture();assert(ridge_hud_count==4&&ridge_hud[0]==3&&ridge_hud[2]==123);
 put(0x10b6c,0x10b68);ridge_hud_capture();assert(ridge_hud_count==0); // cycle
 put(0x10b6c,0x7ffffc);ridge_hud_capture();assert(ridge_hud_count==0); // invalid RAM
 put(0x130ea4,0x801ffff0);ridge_hud_capture();assert(ridge_hud_count==0);
 // Menu slot 0 is the backdrop, 701..703 are the complete foreground.
 put(0x130ea4,0x80010000);put(0x10070,0x21000);put(0x21000,0x01010074);put(0x21004,0xe1000005);
 put(0x10b64,0x20000);put(0x20000,0x03010b6c);put(0x10b6c,0xffffff);
 state=7;ridge_hud_capture();assert(ridge_hud_valid&&ridge_hud_back_count==2&&ridge_hud_count==6&&ridge_hud[4]==123);
 put(0x21000,0x01021000);ridge_hud_capture();assert(!ridge_hud_valid&&ridge_hud_count==0&&ridge_hud_back_count==0);
 state=0;ridge_hud_capture();assert(ridge_hud_count==0);
 // State 29's lap-time overlay lives one slot above the ordinary HUD.
 put(0x130ea4,0x80010000);put(0x10b68,0x00ffffff);
 put(0x10b6c,0x20000);put(0x20000,0x03010b68);
 state=1;ridge_hud_capture();assert(ridge_hud_count==0);
 state=29;ridge_hud_capture();assert(ridge_hud_count==4&&ridge_hud[2]==123);
 put(0x20000,0x03010b6c);ridge_hud_capture();assert(ridge_hud_count==0);
}
'''
class HudTests(unittest.TestCase):
 def test_original_packet_order_and_invalid_lists(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'t.c').write_text(SOURCE)
   subprocess.run(['cc','-I'+str(ROOT/'src/scene'),'-I'+str(ROOT/'psxrecomp/runtime/include'),str(p/'t.c'),str(ROOT/'src/scene/hud.c'),'-o',str(p/'t')],check=True,capture_output=True)
   subprocess.run([str(p/'t')],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
