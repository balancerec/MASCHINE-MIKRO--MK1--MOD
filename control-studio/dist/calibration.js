/* Physical HID format verified on MIKRO MK1. No MIDI remapping here. */
window.MikroCalibration={
  createEncoderTracker(){
    let previous=null,total=0;
    return {
      reset(){previous=null;total=0},
      read(packet){
        if(!Array.isArray(packet)||packet[0]!==1||packet.length<6||
           packet.slice(0,6).some(v=>!Number.isInteger(v)||v<0||v>255))return null;
        const position=packet[5]&15,pressed=Boolean(packet[2]&8);
        const delta=previous===null?0:((position-previous.position+24)%16)-8;
        const ambiguous=delta===-8;
        const pushChanged=previous===null?pressed:pressed!==previous.pressed;
        if(!ambiguous)total+=delta;
        const baseline=previous===null;
        previous={position,pressed};
        return {position,pressed,delta:ambiguous?0:delta,total,pushChanged,baseline,ambiguous};
      }
    };
  },
  decode(packet,map){
    const active=[];
    if(packet[0]===32&&packet.length>=65){
      for(const [pad,config] of Object.entries(map.pads)){
        const c=config.input_channel;
        const read=bank=>{const i=1+2*(c+16*bank);return (packet[i]|packet[i+1]<<8)&4095};
        const level=Math.max(read(0),read(1));
        if(level>120)active.push({id:'pad'+pad,level});
      }
    }else if(packet[0]===1&&packet.length>=6){
      const bits=(packet[1]|packet[2]<<8|packet[3]<<16|packet[4]<<24)>>>0;
      for(const [id,config] of Object.entries(map.controls||{})){
        if((bits>>>config.input_bit)&1)active.push({id,level:1});
      }
    }
    return active;
  },
  ledDefaults(map){
    const result={};
    for(const [pad,config] of Object.entries(map.pads))if(config.led_addresses.length)result['pad'+pad]=config.led_addresses[0];
    for(const [id,config] of Object.entries(map.controls||{}))if(config.led_addresses.length)result[id]=config.led_addresses[0];
    return result;
  }
};
