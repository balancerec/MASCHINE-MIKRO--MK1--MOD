"""Offline verification of inferred legacy XMOS image CRC coverage.

Only reads pinned packages. It neither repairs nor emits firmware images.
"""
import hashlib,json,struct,sys
from pathlib import Path
from inspect_boot_container import ROOT,BITREV

POLY=0xedb88320
def instruction_crc(crc,word):
    for bit in range(32):
        old=crc&1
        crc=(crc>>1)|(((word>>bit)&1)<<31)
        if old:crc^=POLY
    return crc

TABLE=[]
for i in range(256):
    c=i
    for _ in range(8):c=(c>>1)^(POLY if c&1 else 0)
    TABLE.append(c)

def image_crc(data):
    if len(data)%4:raise ValueError('Word-aligned data expected')
    crc=0xffffffff
    for b in data:crc=(crc>>8)^TABLE[crc&255]^(b<<24)
    return instruction_crc(crc,0xffffffff)

def slow_image_crc(data):
    if len(data)%4:raise ValueError('Word-aligned data expected')
    crc=0xffffffff
    for (word,) in struct.iter_unpack('<I',data):crc=instruction_crc(crc,word)
    return instruction_crc(crc,0xffffffff)

def verify(raw):
    d=raw.translate(BITREV)
    if len(d)<256 or struct.unpack_from('<I',d)[0]!=0x1a551e5:raise ValueError('Not a supported legacy image')
    length=struct.unpack_from('<I',d,12)[0]
    if not 256<=length<=len(d) or length%4:raise ValueError('Invalid declared extent')
    expected=struct.unpack_from('<2I',d,4)
    computed=(image_crc(d[16:256]),image_crc(d[16:length]))
    return {'bytes':len(raw),'declared_extent':length,'expected':[hex(x) for x in expected],
            'computed':[hex(x) for x in computed],'first_page_crc_matches':expected[0]==computed[0],
            'content_crc_matches':expected[1]==computed[1],
            'crc_matches':expected==computed,'sha256':hashlib.sha256(raw).hexdigest()}

def main():
    from disassemble_updater120 import load
    raw,pe=load();base=pe.OPTIONAL_HEADER.ImageBase;images=[]
    for i in range(14):
        off=pe.get_offset_from_rva(0x72c410+20*i-base)
        model,version,size,pointer,flags=struct.unpack_from('<5I',raw,off)
        p=pe.get_offset_from_rva(pointer-base);blob=raw[p:p+size]
        try:r=verify(blob)
        except ValueError as error:images.append({'table_index':i,'ni_version':version,'supported':False,'reason':str(error)});continue
        r.update(table_index=i,ni_version=version,supported=True);images.append(r)
    official=(ROOT/'official-firmware/Maschine-Mikro-MK1-FW55.official-payload.bin').read_bytes()
    d=official.translate(BITREV);extent=struct.unpack_from('<I',d,12)[0]
    assert image_crc(d[16:256])==slow_image_crc(d[16:256])
    assert image_crc(d[16:extent])==slow_image_crc(d[16:extent])
    assert verify(official)['crc_matches']
    mutations=[]
    for offset in [32,128,255,256,500,extent-1,len(official)-1]:
        m=bytearray(official);m[offset]^=1;r=verify(bytes(m))
        mutations.append({'file_offset':offset,'first_page_crc_matches':r['first_page_crc_matches'],'content_crc_matches':r['content_crc_matches']})
        if offset<256:assert not r['first_page_crc_matches'] and not r['content_crc_matches']
        elif offset<extent:assert r['first_page_crc_matches'] and not r['content_crc_matches']
        else:assert r['crc_matches']
    supported=[i for i in images if i['supported']]
    assert supported and all(i['crc_matches'] for i in supported)
    result={'algorithm':'XMOS CRC32 instruction semantics, polynomial EDB88320, initial FFFFFFFF, final ingested word FFFFFFFF',
            'normalization':'Reverse bits within each byte before computing',
            'coverage':{'offset_04':'normalized bytes [0x10,0x100)','offset_08':'normalized bytes [0x10,header_uint32_at_0x0c)'},
            'mk1':verify(official),'cross_validation_images':images,'byte_mutation_tests':mutations,
            'fast_vs_bitwise_reference_match':True,'hardware_access':False,'firmware_written':False,
            'limits':['Computational matching is not a trace of the actual device bootloader.',
                      'CRC is not cryptographic authentication; additional checks remain unknown.',
                      'No image repair, flasher, recovery or modified image is produced.']}
    out=ROOT/'fw55-analysis/architecture/legacy-crc-validation.json';out.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
