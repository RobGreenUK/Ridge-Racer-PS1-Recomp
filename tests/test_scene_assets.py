import array
import importlib.util
from pathlib import Path
import struct
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('extract_scene_assets',ROOT/'tools/extract_scene_assets.py')
assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)

class SceneAssetsTests(unittest.TestCase):
    def map_fixture(self):
        # A single section in cell column 2, row 3 and one textured strip quad.
        quad=struct.pack('<12h',0,0,0,-4,0,0,0,0,4,-4,0,4)+bytes(16)
        data=struct.pack('<HH4H',1,0,1,0,0,0)+quad
        grid=[65535]*1024;grid[3*32+2]=0
        return data,struct.pack('<1024H',*grid)
    def test_grid_placement_and_vertex_scale(self):
        face=assets.decode_map(*self.map_fixture())[0]
        self.assertEqual(face[0][0][:3],(28*2048,0,3*2048))
        self.assertEqual(face[0][1][0],28*2048-1)
        self.assertEqual(face[0][2][2],3*2048+1)
    def test_truncated_and_unsupported_map(self):
        data,grid=self.map_fixture()
        with self.assertRaises(ValueError):assets.decode_map(data[:-1],grid)
        with self.assertRaises(ValueError):assets.decode_map(data,grid[:-1])
        bad=bytearray(data);struct.pack_into('<H',bad,10,1)
        with self.assertRaises(ValueError):assets.decode_map(bad,grid)
    def test_tms_upload_and_bounds(self):
        tim=struct.pack('<III4HH',16,2,14,10,20,1,1,0x1234)
        tms=struct.pack('<II',256,len(tim))+tim+bytes(4)
        vram=array.array('H',[0])*(1024*512)
        self.assertEqual(assets.decode_tms(tms,vram),1)
        self.assertEqual(vram[20*1024+10],0x1234)
        with self.assertRaises(ValueError):assets.decode_tms(tms[:-1],vram)
        bad=bytearray(tms);struct.pack_into('<H',bad,20,1024)
        with self.assertRaises(ValueError):assets.decode_tms(bad,vram)
    def test_static_scenery_rotation_and_terminator(self):
        data=bytearray(0x5eafc+48)
        struct.pack_into('<hh4ihh',data,0x5eafc,0,0,100,200,300,0,1024,0)
        struct.pack_into('<h',data,0x5eafc+24,-1)
        model=[([(4,8,12,0,0)]*4,(5,0x7984),0,0)]
        result=assets.decode_static_scenery(data,[model])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0][5],1) # Daytime-only baked geometry.
        for actual,expected in zip(result[0][0][0][:3],(88,208,304)):
            self.assertAlmostEqual(actual,expected)

    def test_resident_bank_uses_upload_owner_and_preserves_packed_indices(self):
        clut=483*64+1
        palette=struct.pack('<I4H16H',44,16,483,16,1,*range(16))
        pixels=struct.pack('<I4H2H',16,872,336,1,2,0x3210,0x7654)
        tim=struct.pack('<II',16,8)+palette+pixels
        tms=struct.pack('<II',256,len(tim))+tim+bytes(4)
        banks=assets.resident_building_pages(tms,[(29,clut),(29,clut+1),(28,clut)])
        self.assertEqual(set(banks),{0})
        self.assertEqual(len(banks[0]),32768)
        self.assertEqual(struct.unpack_from('<H',banks[0],((336-256)*64+872-832)*2)[0],0x3210)
        self.assertEqual(struct.unpack_from('<H',banks[0],((337-256)*64+872-832)*2)[0],0x7654)
        with self.assertRaises(ValueError):assets.resident_building_pages(tms[:-1],[(29,clut)])

    def test_object_groups_account_for_every_byte(self):
        # One 64-byte textured model quad; directory counts start at offset 0.
        directory=struct.pack('<6HI',0,0,0,1,0,0,0)
        primitive=struct.pack('<12h',4,8,12,*([0]*9))+bytes(40)
        data=struct.pack('<I',1)+directory+primitive
        models=assets.decode_objects(data)
        self.assertEqual(len(models[0]),1)
        self.assertEqual(models[0][0][0][0][:3],(1,2,3))
        with self.assertRaises(ValueError):assets.decode_objects(data[:-1])
        with self.assertRaises(ValueError):assets.decode_objects(data+b'pad')
    def test_model_texture_window_and_signed_bias(self):
        # USA 48/72-byte records append an SDK texture-window rectangle.
        for kind,size,tail in [(1,48,24),(4,72,48)]:
            counts=[0]*6;counts[kind]=1
            primitive=bytearray(size)
            struct.pack_into('<h',primitive,tail+10,-8)
            struct.pack_into('<4h',primitive,size-8,128,32,32,16)
            data=struct.pack('<I6HI',1,*counts,0)+primitive
            face=assets.decode_objects(data)[0][0]
            self.assertEqual(face[3],-8)
            self.assertEqual(face[4],28|(30<<5)|(16<<10)|(4<<15))

    def test_palette_nibbles_transparency_and_black(self):
        vram=array.array('H',[0])*(1024*512)
        vram[0]=0x3210
        vram[480*1024:480*1024+4]=array.array('H',[0,31,0x3e0,0x8000])
        rgba=assets.texture_rgba(vram,0,480<<6)
        self.assertEqual(rgba[:16],bytes([0,0,0,0,255,0,0,255,0,255,0,255,0,0,0,255]))

if __name__=='__main__':unittest.main()
