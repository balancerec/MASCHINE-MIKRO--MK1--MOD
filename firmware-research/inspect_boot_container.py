"""Offline XMOS legacy container inspector. No USB, image rewriting or flashing."""
import argparse,hashlib,json,struct,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BITREV=bytes(int(f'{i:08b}'[::-1],2) for i in range(256))

def inspect(raw):
    data=raw.translate(BITREV)
    if len(data)<28:raise ValueError('Truncated header')
    h=struct.unpack_from('<7I',data)
    if h[0]!=0x01a551e5:raise ValueError('Not the legacy XMOS image tag')
    count=h[6];header_end=28+12*count
    if not 1<=count<=32 or header_end>len(data):raise ValueError('Invalid segment table')
    if not header_end<=h[3]<=h[5]<=len(data):raise ValueError('Invalid declared image extent')
    segments=[];previous=header_end
    for i in range(count):
        start,flags,words=struct.unpack_from('<3I',data,28+12*i);end=start+words*4
        if start!=previous or not words or end>h[3]:raise ValueError('Noncontiguous or out-of-bounds segment')
        segments.append({'index':i,'offset':start,'end_exclusive':end,'words':words,
                         'flags_unresolved':f'0x{flags:08x}',
                         'tail_word_unresolved':f'0x{struct.unpack_from("<I",data,end-4)[0]:08x}',
                         'sha256':hashlib.sha256(data[start:end]).hexdigest()})
        previous=end
    if previous!=h[3]:raise ValueError('Segments do not cover declared content')
    from verify_xmos_image_crc import verify
    checksums=verify(raw)
    return {'payload_sha256':hashlib.sha256(raw).hexdigest(),'normalized_sha256':hashlib.sha256(data).hexdigest(),
            'format':'XMOS legacy image tag, prior to tools-13 header variant',
            'tag':f'0x{h[0]:08x}','checksums':checksums,
            'content_extent':h[3],'container_version':h[4],'container_stride_bytes':h[5],
            'segment_count':count,'segments':segments,'padding_bytes':len(data)-h[5],
            'padding_all_zero':not any(data[h[5]:]),'crc_validated':checksums['crc_matches'],'flash_compatibility_validated':False,
            'notes':['Header version is not the NI firmware version 55.',
                     'Segment table interpretation is structural inference; flags remain unresolved.',
                     'Tag/version/stride interpretation grounded in pinned XMOS flashlib.c.',
                     'Image CRCs are stored at header offsets04/08, not established at segment tails.',
                     'This payload is not a verified full-device flash backup.']}

def crc_probe(raw,result):
    data=raw.translate(BITREV);probes=[]
    for s in result['segments']:
        start,end=s['offset'],s['end_exclusive'];target=struct.unpack_from('<I',data,end-4)[0];matches=[];attempts=0
        for begin in sorted(set(range(max(0,start-16),start+33,4))|{0,4,8,12,16,20,24,28}):
            for prefix in (b'',struct.pack('<I',s['words']),struct.pack('<I',s['words']-1),struct.pack('<I',start),struct.pack('<I',end-start)):
                b=prefix+data[begin:end-4]
                for transform,payload in [('identity',b),('reverse_bytes_per_word',b''.join(b[i:i+4][::-1] for i in range(0,len(b),4)))]:
                    for init in (0,0xffffffff):
                        for xor in (0,0xffffffff):
                            attempts+=1
                            if zlib.crc32(payload,init)^xor==target:matches.append({'start':begin,'prefix':prefix.hex(),'transform':transform,'init':init,'xor':xor})
        probes.append({'segment':s['index'],'hypothesis':'tail word equals one of the tested standard CRC32 variants',
                       'attempts':attempts,'matches':matches,'conclusion':'No tested match; neither proves encryption nor establishes tail as CRC.'})
    return probes

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('image',nargs='?',type=Path,default=ROOT/'official-firmware/Maschine-Mikro-MK1-FW55.official-payload.bin');a=p.parse_args()
    raw=a.image.read_bytes();r=inspect(raw);r['crc_probes']=crc_probe(raw,r)
    out=ROOT/'fw55-analysis/architecture/boot-container.json';out.write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
