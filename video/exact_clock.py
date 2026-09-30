"""Trim the final MP4 video sample to the WAV clock without dropping a frame.

30 fps cannot represent 179.840 s as an integer frame count. Adjust only the
last sample duration to the master; retain all preceding 30-fps samples.
Update movie/track edit durations and chunk offsets after moov growth.
"""
import argparse,struct
from pathlib import Path

CONTAINERS={b'moov',b'trak',b'mdia',b'minf',b'stbl',b'edts'}
def atoms(raw):
    result=[];i=0
    while i<len(raw):
        size,kind=struct.unpack_from('>I4s',raw,i);header=8
        if size==1:size=struct.unpack_from('>Q',raw,i+8)[0];header=16
        if size==0:size=len(raw)-i
        assert size>=header and i+size<=len(raw)
        data=raw[i+header:i+size]
        result.append({'kind':kind,'data':bytearray(data),'children':atoms(data) if kind in CONTAINERS else None})
        i+=size
    return result

def walk(nodes):
    for n in nodes:
        yield n
        if n['children']:yield from walk(n['children'])

def encode(n):
    data=b''.join(map(encode,n['children'])) if n['children'] is not None else bytes(n['data'])
    size=8+len(data)
    return struct.pack('>I4s',size,n['kind'])+data

def fix(path,duration):
    raw=path.read_bytes();nodes=atoms(raw)
    moov=next(n for n in nodes if n['kind']==b'moov');before=len(encode(moov))
    mvhd=next(n for n in walk([moov]) if n['kind']==b'mvhd');assert mvhd['data'][0]==0
    movie_scale=struct.unpack_from('>I',mvhd['data'],12)[0]
    struct.pack_into('>I',mvhd['data'],16,round(duration*movie_scale))
    for track in moov['children']:
        if track['kind']!=b'trak':continue
        items=list(walk([track]));handler=next(n for n in items if n['kind']==b'hdlr')
        if handler['data'][8:12]!=b'vide':continue
        mdhd=next(n for n in items if n['kind']==b'mdhd');assert mdhd['data'][0]==0
        scale=struct.unpack_from('>I',mdhd['data'],12)[0];target=round(duration*scale)
        stts=next(n for n in items if n['kind']==b'stts');data=stts['data'];count=struct.unpack_from('>I',data,4)[0]
        entries=[struct.unpack_from('>II',data,8+i*8) for i in range(count)]
        total=sum(n*dt for n,dt in entries);trim=total-target
        assert abs(trim)<entries[-1][1], 'Only a fractional final frame may be adjusted'
        if trim:
            n,dt=entries.pop()
            if n>1:entries.append((n-1,dt))
            entries.append((1,dt-trim))
            stts['data']=bytearray(data[:4]+struct.pack('>I',len(entries))+b''.join(struct.pack('>II',*e) for e in entries))
        struct.pack_into('>I',mdhd['data'],16,target)
        tkhd=next(n for n in items if n['kind']==b'tkhd');assert tkhd['data'][0]==0
        struct.pack_into('>I',tkhd['data'],20,round(duration*movie_scale))
        for n in items:
            if n['kind']==b'elst':
                assert n['data'][0]==0 and struct.unpack_from('>I',n['data'],4)[0]==1
                struct.pack_into('>I',n['data'],8,round(duration*movie_scale))
    delta=len(encode(moov))-before
    moov_pos=raw.find(b'moov')-4
    if delta:
        for n in walk(nodes):
            if n['kind'] not in {b'stco',b'co64'}:continue
            fmt='>I' if n['kind']==b'stco' else '>Q';step=4 if n['kind']==b'stco' else 8
            for i in range(struct.unpack_from('>I',n['data'],4)[0]):
                offset=8+i*step;value=struct.unpack_from(fmt,n['data'],offset)[0]
                if value>moov_pos+before:struct.pack_into(fmt,n['data'],offset,value+delta)
    temporary=path.with_suffix('.clock.mp4');temporary.write_bytes(b''.join(map(encode,nodes)));temporary.replace(path)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('duration',type=float)
    a=p.parse_args();fix(a.file,a.duration)
