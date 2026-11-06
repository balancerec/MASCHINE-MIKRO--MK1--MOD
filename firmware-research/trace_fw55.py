"""Offline XCore control-flow index with explicit file-offset addressing."""
from pathlib import Path
import hashlib,json,re,struct,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'.deps-research'))
import capstone
B=(ROOT/'fw55-analysis/FW55.bit-normalized.bin').read_bytes()
assert hashlib.sha256(B).hexdigest()=='8b9363b6155fcd230151ed67bc7d9708cfcd6b912800c2ac6f4ace4c4e0ecb5c'
OUT=ROOT/'fw55-analysis/architecture';OUT.mkdir(exist_ok=True)
md=capstone.Cs(capstone.CS_ARCH_XCORE,0);md.skipdata=True
NAMES={0x444:'hid_input_report_transmit',0x4e8:'hid_event_multiplexer',0x684:'feature_f8_configuration_receive',0x8b4:'led_report_store',0x916:'pad_buffer_receive',0x6830:'pad_acquisition_2x16',0x6820:'pad_channel_table_lookup',0x6944:'led_service',0x64ac:'lcd_page_write',0x6570:'lcd_service',0x7170:'display_backlight_pwm',0x3300:'byte_copy_loop'}
allrows=[];segments=[]
for seg,start,end,cp_site,dp_site in [(0,0x34,0x51cc,0x4c,0x52),(1,0x61a4,0x7bb4,0x61bc,0x61c2)]:
 ins=list(md.disasm(B[start:end],start));byaddr={i.address:i for i in ins}
 def relative(i):
  match=re.search(r'(-?0x[0-9a-f]+|-?\d+)$',i.op_str)
  return i.address+i.size+2*int(match[0],0) if match else None
 cp=relative(byaddr[cp_site]);dp=relative(byaddr[dp_site])
 rows=[];edges=[];events=[];spawn=[];ldap=None
 for i in ins:
  row={'offset':i.address,'bytes':i.bytes.hex(),'mnemonic':i.mnemonic,'operands':i.op_str}
  if i.mnemonic in ('bl','bu','bt','bf','ldap'):
   target=relative(i);row['relative_target']=target
   if i.mnemonic=='bl':edges.append({'call_site':i.address,'target':target,'target_label':NAMES.get(target),'instruction_aligned':target in byaddr})
  if i.mnemonic=='ldap' and i.op_str.startswith('r11,'):
   ldap=(i.address,relative(i))
  elif ldap and i.address-ldap[0]<=20:
   if i.mnemonic=='setv':events.append({'ldap_site':ldap[0],'handler_offset':ldap[1],'register_site':i.address,'resource':i.op_str})
   if i.mnemonic=='init' and ':pc, r11' in i.op_str:spawn.append({'ldap_site':ldap[0],'entry_offset':ldap[1],'init_site':i.address,'thread':i.op_str})
   # A different destination r11 invalidates the tracked address.
   if i.op_str.startswith('r11,') or (i.mnemonic=='ldaw' and i.op_str.startswith('r11,')):ldap=None
  match=re.search(r'cp\[(0x[0-9a-f]+|\d+)\]',i.op_str)
  if match and i.mnemonic in ('ldw','ldaw'):
   at=cp+4*int(match[1],0)
   if 0<=at<=len(B)-4:
    row['cp_file_offset']=at;row['cp_word_le']=struct.unpack_from('<I',B,at)[0]
  rows.append(row)
 anchors=[start]+[i.address for i in ins if i.mnemonic=='entsp']
 segments.append({'segment':seg,'analyzed_code_window':[start,end],'cp_file_offset':cp,'dp_file_offset':dp,'prologue_candidates':anchors,'calls':edges,'event_handlers':events,'thread_entry_candidates':spawn})
 lines=[]
 for row in rows:
  address=row['offset']
  if address in NAMES:lines.append(f'\n; ANALYST LABEL: {NAMES[address]}')
  note=''
  if 'relative_target' in row:note=f" ; -> file 0x{row['relative_target']:x} {NAMES.get(row['relative_target'],'')}"
  if 'cp_word_le' in row:note+=f" ; CP slot @file 0x{row['cp_file_offset']:x} = 0x{row['cp_word_le']:08x}"
  lines.append(f"{address:08x} {row['bytes']:<10} {row['mnemonic']:<9} {row['operands']}{note}")
 (OUT/f'segment{seg}.annotated.asm').write_text('\n'.join(lines),encoding='utf-8');allrows.extend(rows)
# Dispatcher target check independently ties PC-relative decoding to the known LED arm.
assert next(r for r in allrows if r['offset']==0x7e2)['relative_target']==0x8b4
assert segments[1]['cp_file_offset']==0x7bb8
table=list(struct.unpack_from('<16I',B,0x7bb8))
assert set(table)==set(range(16))
result={'address_kind':'file offsets; no absolute RAM map inferred','segments':segments,'pad_channel_select_table':{'offset':0x7bb8,'values':table},'limits':['Code windows exclude known constant pools but may still contain embedded data','Prologues and thread entries are candidates, not recovered source symbols','Register tracking is local and does not prove inter-task channel wiring']}
(OUT/'control-flow.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'segments':[{'segment':s['segment'],'cp':hex(s['cp_file_offset']),'dp':hex(s['dp_file_offset']),'calls':len(s['calls']),'events':s['event_handlers'],'threads':s['thread_entry_candidates']} for s in segments],'pad_selection':table},indent=2))
