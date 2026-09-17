"""Exercise the real C hook with mocked RAM; no copyrighted fixture needed."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include "cpu_state.h"
#include "mod_plugins.h"
#include "usa_layout.h"
#include <assert.h>
#include <string.h>
#include <stdlib.h>
static unsigned char ram[0x200000], before[0x200000];
uint64_t psx_cycle_count = 123456;
static uint32_t addresses[6];
static PSXModFunctionEntryCallback callbacks[6];
static unsigned count;
void ridge_live_publish(void) {}
#include "models.h"
struct RRRawModel ridge_models[RR_MODEL_CAP];
unsigned ridge_model_count,ridge_model_overflow;
void ridge_models_reset(void) {}
void ridge_models_complete(void) {}
void ridge_signs_complete(void) {}
int psx_mod_register_function_entry_plugin(const char *id, uint32_t a, PSXModFunctionEntryCallback cb) {
    assert(count < 6); addresses[count] = a; callbacks[count++] = cb; return 1;
}
uint8_t psx_mod_read_byte(uint32_t a) { assert((a >> 21) == (0x80000000u >> 21)); return ram[a & 0x1fffff]; }
uint16_t psx_mod_read_half(uint32_t a) { return psx_mod_read_byte(a) | psx_mod_read_byte(a+1)<<8; }
uint32_t psx_mod_read_word(uint32_t a) { return psx_mod_read_half(a) | (uint32_t)psx_mod_read_half(a+2)<<16; }
static void put(uint32_t a, uint32_t v) { for(int i=0;i<4;i++)ram[(a+i)&0x1fffff] = v>>(i*8); }
int main(void) {
    if (!getenv("RIDGE_SCENE_CAPTURE")) { assert(count == 0); return 0; }
    assert(count == 6);
    CPUState cpu = {0}, saved;
    cpu.gpr[4] = RR_PLAYER;
    cpu.gpr[31] = RR_MAIN_AFTER_DRAWSYNC_CALL;
    saved = cpu;
    put(0x800143cc, 0x27bdffd0); put(0x800195b0, 0x27bdffb8);
    if(!getenv("BAD_CODE"))put(0x80013338, 0x34020180);
    put(RR_TRACK_POINTER, getenv("BAD_POINTER") ? 0x1f801800 : 0x80057d64);
    put(RR_TRACK_COUNT, 256);
    memcpy(before, ram, sizeof ram);
    // Wrong caller must not produce a record.
    cpu.gpr[31] = 0; callbacks[3](&cpu, addresses[3]); cpu = saved;
    for(int n=0;n<5;n++) {
        for(unsigned i=0;i<count;i++)callbacks[i](&cpu, addresses[i]);
        assert(memcmp(&cpu, &saved, sizeof cpu) == 0);
        assert(memcmp(ram, before, sizeof ram) == 0);
        assert(psx_cycle_count == 123456);
    }
    return 0;
}
'''


class SceneCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        source = cls.directory / 'harness.c'
        source.write_text(HARNESS)
        cls.binary = cls.directory / 'capture_test'
        subprocess.run(['cc', '-std=c11', '-D_POSIX_C_SOURCE=200809L',
                        '-I' + str(ROOT / 'psxrecomp/runtime/include'),
                        '-I' + str(ROOT / 'src/scene'),
                        str(source), str(ROOT / 'src/scene/capture.c'), str(ROOT / 'src/scene/hud.c'),
                        '-o', str(cls.binary)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_capture(self, **extra):
        target = self.directory / (self.id().split('.')[-1] + '.jsonl')
        env = {k: v for k, v in os.environ.items() if not k.startswith('RIDGE_SCENE_CAPTURE')}
        env.update(RIDGE_SCENE_CAPTURE=str(target), RIDGE_SCENE_CAPTURE_FRAMES='3', **extra)
        subprocess.run([str(self.binary)], env=env, check=True, capture_output=True)
        return target

    def test_capture_is_bounded_and_does_not_mutate_guest(self):
        rows = [json.loads(line) for line in self.run_capture().read_text().splitlines()]
        self.assertEqual([row['type'] for row in rows], ['header', 'track', 'frame', 'frame', 'frame'])
        self.assertEqual([r['race_entries'] for r in rows[2:]], [1, 2, 3])
        self.assertEqual(len(bytes.fromhex(rows[2]['entities'])), 12 * 0x114)

    def test_unsupported_code_fails_closed(self):
        self.assertFalse(self.run_capture(BAD_CODE='1').exists())

    def test_invalid_track_pointer_is_not_dereferenced(self):
        rows = [json.loads(line) for line in self.run_capture(BAD_POINTER='1').read_text().splitlines()]
        self.assertNotIn('track', [r['type'] for r in rows])

    def test_existing_capture_is_not_overwritten(self):
        path = self.run_capture()
        data = path.read_bytes()
        self.run_capture()
        self.assertEqual(path.read_bytes(), data)

    def test_disabled_registers_no_callbacks(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith('RIDGE_SCENE_CAPTURE')}
        subprocess.run([str(self.binary)], env=env, check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
