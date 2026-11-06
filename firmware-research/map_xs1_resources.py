"""Offline resource-name mapping grounded in the XMOS XS1 ports table."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PORTS={0x200000:'32A',0x100000:'16A',0x100100:'16B',
       0x80000:'8A',0x80100:'8B',0x80200:'8C',0x80300:'8D',
       **{0x40000+256*i:'4'+chr(65+i) for i in range(6)}}
PORTS.update(dict(zip([0x10200,0x10000,0x10100,0x10300,0x10600,0x10400,0x10500,0x10700,
                      0x10a00,0x10800,0x10900,0x10b00,0x10c00,0x10d00,0x10e00,0x10f00],
                     ['1'+chr(65+i) for i in range(16)])))
def main():
    raw=(ROOT/'fw55-analysis/FW55.bit-normalized.bin').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='8b9363b6155fcd230151ed67bc7d9708cfcd6b912800c2ac6f4ace4c4e0ecb5c'
    groups=[('SPI flash',0,0x53d8,[0x1f,0x20,0x21,0x22],['MISO','SS','SCLK','MOSI']),
            ('Display',1,0x7d0c,[0x10,0x0f,0x11],None),
            ('Pads',1,0x7d0c,[0x16,0x13,0x14,0x12],None),
            ('Buttons',1,0x7d0c,[0x0d,0x0b,0x0c],None),
            ('LEDs',1,0x7d0c,[0x07,0x06,0x08,0x09,0x17],None)]
    result=[]
    for name,segment,dp,slots,roles in groups:
        values=[]
        for index,slot in enumerate(slots):
            value=struct.unpack_from('<I',raw,dp+4*slot)[0]
            assert value in PORTS
            values.append({'dp_slot':hex(slot),'initial_data_file_offset':hex(dp+4*slot),
                           'resource':hex(value),'port':'XS1_PORT_'+PORTS[value],
                           'signal_role':roles[index] if roles else 'not assigned; wrapper argument only'})
        result.append({'service':name,'segment_context':segment,'resources':values})
    assert [v['port'] for v in result[0]['resources']]==['XS1_PORT_1A','XS1_PORT_1B','XS1_PORT_1C','XS1_PORT_1D']
    out={'source':'https://www.xmos.com/download/XS1-Ports-Specification%281_02%29.pdf',
         'reference':'Table2, page32, XS1 Ports: use and specification 1.02',
         'resource_dictionary':{hex(k):'XS1_PORT_'+v for k,v in PORTS.items()},
         'services':result,'hardware_access':False,
         'limits':['Port resource names are local to an execution tile, not board pin numbers.',
                   'Segment context is not a proven tile ID.',
                   'Non-SPI signal roles still require instruction-level tracing.',
                   'Initial DP values were used only at previously identified initialized wrapper slots.']}
    outpath=ROOT/'fw55-analysis/architecture/xs1-resource-map.json';outpath.write_text(json.dumps(out,indent=2))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
