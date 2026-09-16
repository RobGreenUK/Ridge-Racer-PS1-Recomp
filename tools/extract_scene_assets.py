#!/usr/bin/env python3
"""Decode USA course meshes/textures from the user's local disc into preview assets.
No extracted data belongs in version control. CPU world convention follows USA
section placement: origin ((30-column)*2048, 0, row*2048), vertices /4.
"""
import argparse
import array
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'psxrecomp/tools'))
from new_project_layout.probe_disc import read_user_bin, parse_root_entries, read_file


def decode_tms(data, vram):
    if len(data)<8 or struct.unpack_from('<I',data)[0]!=256:
        raise ValueError('Unsupported TMS header')
    offset, count = 4, 0
    while offset+4<=len(data):
        size=struct.unpack_from('<I',data,offset)[0];offset+=4
        if size==0:
            if offset!=len(data): raise ValueError('Data after TMS terminator')
            return count
        if size<20 or offset+size>len(data):raise ValueError('Truncated TMS image')
        image=data[offset:offset+size];offset+=size
        magic,flags=struct.unpack_from('<II',image)
        if magic!=16 or flags&~15:raise ValueError('Unsupported TIM header')
        cursor=8
        for block in range(2 if flags&8 else 1):
            if cursor+12>len(image):raise ValueError('Truncated TIM rectangle')
            claimed,x,y,w,h=struct.unpack_from('<I4H',image,cursor)
            end=cursor+12+w*h*2
            if x+w>1024 or y+h>512 or end>len(image):raise ValueError('Invalid TIM upload')
            # TMS's image block length can count twice the actual pixel bytes;
            # the enclosing TMS size and upload rectangle delimit stored data.
            if claimed not in (12+w*h*2,12+w*h*4):raise ValueError('Unknown TIM block length')
            pixels=struct.unpack_from('<'+str(w*h)+'H',image,cursor+12)
            for row in range(h):
                vram[(y+row)*1024+x:(y+row)*1024+x+w]=array.array('H',pixels[row*w:(row+1)*w])
            cursor=end
        if cursor!=len(image):raise ValueError('Unconsumed TIM bytes')
        count+=1
    raise ValueError('Missing TMS terminator')


def decode_map(data, grid):
    if len(data)<4 or len(grid)!=2048:raise ValueError('Invalid map header/grid')
    n=struct.unpack_from('<H',data)[0]
    if not 0<n<=1024 or len(data)<4+n*8:raise ValueError('Invalid section directory')
    placements={}
    for cell,section in enumerate(struct.unpack('<1024H',grid)):
        if section==65535:continue
        if section>=n or section in placements:raise ValueError('Invalid/duplicate section assignment')
        placements[section]=((30-cell%32)*2048,0,(cell//32)*2048)
    if len(placements)!=n:raise ValueError('Unplaced sections')
    offset=4+n*8;faces=[]
    for section in range(n):
        counts=struct.unpack_from('<4H',data,4+section*8)
        if counts[3]:raise ValueError('Unsupported fourth record type')
        origin=placements[section]
        for kind,count in enumerate(counts[:3]):
            for _ in range(count):
                if offset+40>len(data):raise ValueError('Truncated quad')
                xyz=struct.unpack_from('<12h',data,offset)
                clut=struct.unpack_from('<H',data,offset+26)[0]
                page=struct.unpack_from('<H',data,offset+30)[0]
                bias=struct.unpack_from('<h',data,offset+34)[0]
                vertices=[]
                for i in range(4):
                    vertices.append((*[origin[j]+xyz[i*3+j]/4 for j in range(3)],
                                     data[offset+24+i*4]/256, data[offset+25+i*4]/256))
                faces.append((vertices,(page,clut),kind,bias));offset+=40
    if offset!=len(data):raise ValueError('Unconsumed map bytes')
    return faces


def decode_objects(data):
    if len(data)<4:raise ValueError('Truncated object header')
    count=struct.unpack_from('<I',data)[0]
    if not 1<=count<=4096 or 4+count*16>len(data):raise ValueError('Invalid object directory')
    offset=4+count*16;models=[]
    for model in range(count):
        faces=[]
        for kind,(n,size) in enumerate(zip(struct.unpack_from('<6H',data,4+model*16),[40,48,32,64,72,56])):
            for _ in range(n):
                if offset+size>len(data):raise ValueError('Truncated object primitive')
                xyz=struct.unpack_from('<12h',data,offset)
                tail=offset+(48 if kind>=3 else 24)
                flat=kind in (2,5)
                if flat:
                    rgb=tuple(data[tail:tail+3]);key=(-1,rgb[0]|rgb[1]<<8|rgb[2]<<16)
                else:
                    key=(struct.unpack_from('<H',data,tail+6)[0],struct.unpack_from('<H',data,tail+2)[0])
                vertices=[]
                for i in range(4):
                    vertices.append((*[v/4 for v in xyz[i*3:i*3+3]],
                                     0.5 if flat else data[tail+i*4]/256,
                                     0.5 if flat else data[tail+i*4+1]/256))
                bias=struct.unpack_from('<h',data,tail+(4 if flat else 10))[0]
                window=0
                if kind in (1,4):
                    x,y,w,h=struct.unpack_from('<4h',data,offset+size-8)
                    window=(((-w)&255)>>3)|((((-h)&255)>>3)<<5)|(((x&255)>>3)<<10)|(((y&255)>>3)<<15)
                faces.append((vertices,key,0,bias,window));offset+=size
        models.append(faces)
    if offset!=len(data):raise ValueError('Unconsumed object bytes')
    return models


def decode_static_scenery(exe,models):
    # USA optimized scene renderer 0x80036778 consumes this 24-byte list
    # directly, bypassing RenderModel. Terminator is a negative model ID.
    faces=[];offset=0x5eafc
    for _ in range(256):
        if offset+24>len(exe):raise ValueError('Truncated scenery list')
        model,unused,x,y,z,flags,yaw,pad=struct.unpack_from('<hh4ihh',exe,offset)
        if model<0:return faces
        if model>=len(models):raise ValueError('Invalid scenery model')
        angle=yaw*math.tau/4096;co=math.cos(angle);si=math.sin(angle)
        for face in models[model]:
            vertices,key,kind,bias=face[:4]
            transformed=[(x+co*v[0]-si*v[2],y+v[1],z+si*v[0]+co*v[2],v[3],v[4]) for v in vertices]
            # RaceMain 80014FC4 chooses this baked list only in daytime.
            # At night the native model list supplies its replacement surfaces.
            faces.append((transformed,key,kind,bias,face[4] if len(face)>4 else 0,1))
        offset+=24
    raise ValueError('Unterminated scenery list')


def texture_rgba(vram,page,clut):
    if page==-1:
        return bytes([clut&255,(clut>>8)&255,(clut>>16)&255,255])*(256*256)
    mode=(page>>7)&3
    if mode==3:raise ValueError('Reserved texture depth')
    xbase=(page&15)*64;ybase=((page>>4)&1)*256
    cx=(clut&63)*16;cy=(clut>>6)&511
    out=bytearray()
    for y in range(256):
        for x in range(256):
            word=vram[((ybase+y)&511)*1024+((xbase+(x>>(2-mode)))&1023)]
            if mode==0:word=vram[cy*1024+((cx+((word>>((x&3)*4))&15))&1023)]
            elif mode==1:word=vram[cy*1024+((cx+((word>>((x&1)*8))&255))&1023)]
            channels=[word&31,(word>>5)&31,(word>>10)&31]
            out.extend([*((c<<3)|(c>>2) for c in channels),0 if word==0 else 255])
    return out


def resident_building_pages(tms, keys):
    """Keep TEX2's page-28/29 buildings resident when VRAM banks are reused.

    Match the TIM's own CLUT and upload rectangle, rather than guessing from
    colours or applying a replacement to every material using the shared page.
    Palettes remain live so the game's day/night colour changes still apply.
    """
    vram=array.array('H',[0])*524288
    decode_tms(tms,vram)  # Validate all enclosing records before inspecting them.
    materials=set();offset=4
    while True:
        size=struct.unpack_from('<I',tms,offset)[0];offset+=4
        if not size:break
        image=tms[offset:offset+size];offset+=size
        flags=struct.unpack_from('<I',image,4)[0]
        if flags!=8:continue # This scenery bank uses 4-bit indexed TIMs.
        _,cx,cy,cw,ch=struct.unpack_from('<I4H',image,8)
        _,x,y,w,h=struct.unpack_from('<I4H',image,20+cw*ch*2)
        for page in (28,29):
            left=(page&15)*64
            if w and h and x>=left and x+w<=left+64 and y>=256 and y+h<=512:
                materials.add((page,(cy<<6)|(cx>>4)))
    banks={page:b''.join(struct.pack('<64H',*vram[y*1024+(page&15)*64:y*1024+(page&15)*64+64]) for y in range(256,512)) for page in (28,29)}
    return {i:banks[key[0]] for i,key in enumerate(keys) if key in materials}


def extract(disc,destination,vram_path=None):
    data=disc.read_bytes()
    # Use the project's recorded identity rather than accepting a different revision.
    expected=json.loads((ROOT/'disc_probe.json').read_text())['data_track_sha1']
    if hashlib.sha1(data).hexdigest()!=expected:raise ValueError('Unsupported data-track revision')
    pvd=read_user_bin(data,16)
    root=read_file(read_user_bin,data,struct.unpack_from('<I',pvd,158)[0],struct.unpack_from('<I',pvd,166)[0])
    directory=parse_root_entries(root)
    def file(name):return read_file(read_user_bin,data,*directory[name])
    faces=decode_map(file('MAP.RRM'),file('IDX.HED'))
    models=decode_objects(file('OBJ.RRO'))
    executable=(ROOT/'disc/SCUS-943.00').read_bytes()
    if hashlib.sha256(executable).hexdigest()!='bde353330bf4032d8c4b86a04dbcc78c95e6b2c5aa17dc15b79de613b52cf8c5':
        raise ValueError('Unsupported executable revision')
    exe=executable[2048:]
    faces.extend(decode_static_scenery(exe,models))
    vram=array.array('H',[0])*(1024*512)
    uploads={name:decode_tms(file(name),vram) for name in [f'TEX{i}.TMS' for i in range(5)]}
    if vram_path:
        raw=vram_path.read_bytes()
        if len(raw)!=1024*512*2:raise ValueError('Invalid VRAM snapshot size')
        vram=array.array('H',struct.unpack('<524288H',raw))
    keys=sorted({f[1] for group in [faces,*models] for f in group});lookup={key:i for i,key in enumerate(keys)}
    resident=resident_building_pages(file('TEX2.TMS'),keys)
    with io.BytesIO() as output:
        output.write(struct.pack('<8sII',b'RRASSET7',len(keys),len(faces)))
        for key in keys:output.write(texture_rgba(vram,*key))
        def write_faces(group):
            for face in group:
                vertices,key,kind,bias=face[:4]
                output.write(struct.pack('<IIiII',lookup[key],kind,bias,face[4] if len(face)>4 else 0,face[5] if len(face)>5 else 0))
                for vertex in vertices:output.write(struct.pack('<5f',*vertex))
        write_faces(faces)
        output.write(struct.pack('<I',len(models)))
        for model in models:
            output.write(struct.pack('<I',len(model)))
            write_faces(model)
        output.write(struct.pack('<524288H',*vram))
        output.write(exe[0x60898:0x608b8]) # 16 panorama tile indices
        output.write(exe[0x608b8:0x60918]) # 12 sets of four packed UVs
        for page,clut in keys:output.write(struct.pack("<iI",page,clut))
        output.write(struct.pack('<I',len(resident)))
        for index,packed in resident.items():
            output.write(struct.pack('<I',index));output.write(packed)
        encoded=output.getvalue()
    with destination.open('xb') as output:output.write(encoded)
    print(json.dumps(dict(quads=len(faces),models=len(models),model_quads=sum(map(len,models)),textures=len(keys),tms_images=uploads,bytes=len(encoded)),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--disc',type=Path,default=ROOT/'Ridge Racer (USA)/Ridge Racer (USA) (Track 01).bin')
    parser.add_argument('--vram',type=Path,help='Authoritative local VRAM snapshot from validation run')
    args=parser.parse_args();extract(args.disc,args.output,args.vram)
