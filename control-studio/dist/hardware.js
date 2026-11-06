/* The hosted editor launches the same UI served by the Windows loopback bridge. */
(()=>{
const local=location.origin==='http://127.0.0.1:8765';
const bar=document.createElement('section');bar.className='hardware-bar';
bar.innerHTML='<div><b id="usb-state">USB / DESCONECTADO</b><small id="usb-detail">Conecte a ponte local para controlar a MK1.</small></div><button id="usb-connect">'+(local?'Conectar USB':'Abrir conexão local ↗')+'</button><button id="usb-disconnect" hidden>Devolver à NI</button><button id="usb-apply" hidden>Enviar LEDs</button><label id="usb-live-wrap" hidden><input type="checkbox" id="usb-live"> Enviar ao editar</label><button id="usb-calibrate" hidden>Calibrar LEDs</button>';
document.querySelector('.toolbar').after(bar);
const panel=document.createElement('section');panel.className='hardware-panel';panel.hidden=true;
panel.innerHTML='<div><span class="eyebrow">CALIBRAÇÃO FÍSICA / MK1</span><h3>Qual controle está aceso?</h3><p>Escolha um endereço, acenda o LED e clique no controle correspondente no desenho. Depois associe. Apenas endereços confirmados são usados no envio individual.</p></div><div class="calibration-controls"><label>Endereço LED (0–59)<input id="usb-slot" type="number" min="0" max="59" value="0"></label><button id="usb-probe">Acender este endereço</button><button id="usb-next">Próximo →</button><button id="usb-bind">Associar ao selecionado</button><button id="usb-unbind">Remover associação</button><button id="usb-map-export">Exportar mapa</button></div><p id="usb-mapping"></p><p class="hint">O envio de LEDs funciona por HID. As atribuições MIDI continuam salvas no template; ainda não há roteamento MIDI pela ponte. Durante a calibração, o envio automático fica pausado.</p>';
bar.after(panel);
const el=id=>document.getElementById(id),editor=window.MikroEditor;
let token=null,connected=false,busy=false,seq=0,debounce,probing=false,testing=false,polling=false;
let map={button12:0,pad16:28,pad12:44};
let physicalMap=null;
const inputTimers=new Map();
const encoderTracker=window.MikroCalibration.createEncoderTracker();
const encoderMonitor=document.createElement('p');encoderMonitor.className='hint';
encoderMonitor.id='usb-encoder';encoderMonitor.setAttribute('aria-live','polite');
encoderMonitor.textContent='Encoder físico · aguardando conexão USB';bar.after(encoderMonitor);
let encoderSequence=null;
function showPhysical(event){
 if(encoderSequence!==null&&event.seq!==encoderSequence+1)encoderTracker.reset();
 encoderSequence=event.seq;
 const turn=encoderTracker.read(event.bytes);
 if(turn){
  const action=turn.ambiguous?'salto ambíguo · referência atualizada':turn.delta>0?'direita +'+turn.delta:turn.delta<0?'esquerda '+turn.delta:turn.pushChanged?(turn.pressed?'clique pressionado':'clique solto'):'posição inicial';
  encoderMonitor.textContent='Encoder físico · '+action+' · posição '+turn.position+'/15 · saldo '+turn.total+(turn.pressed?' · pressionado':'');
  const knob=document.querySelector('[data-id="encoder"]');
  if(knob&&(turn.delta||turn.pressed)){knob.classList.add('usb-active');clearTimeout(inputTimers.get('encoder'));inputTimers.set('encoder',setTimeout(()=>knob.classList.remove('usb-active'),180));}
 }
 if(!physicalMap||!Array.isArray(event.bytes))return;
 for(const hit of window.MikroCalibration.decode(event.bytes,physicalMap)){
  const button=document.querySelector('[data-id="'+hit.id+'"]');
  if(!button)continue;
  button.classList.add('usb-active');
  clearTimeout(inputTimers.get(hit.id));
  inputTimers.set(hit.id,setTimeout(()=>button.classList.remove('usb-active'),180));
 }
}
try{const saved=JSON.parse(localStorage.getItem('mikro-led-map-v1'));if(saved&&typeof saved==='object')for(const [id,slot] of Object.entries(saved))if(editor.controls()[id]&&Number.isInteger(slot)&&slot>=0&&slot<60)map[id]=slot}catch{}
function mapSave(){localStorage.setItem('mikro-led-map-v1',JSON.stringify(map));mapping()}
function resetEncoderMonitor(){encoderTracker.reset();encoderSequence=null;encoderMonitor.textContent='Encoder físico · aguardando novos movimentos';}
el('usb-connect').addEventListener('click',resetEncoderMonitor);
el('usb-disconnect').addEventListener('click',resetEncoderMonitor);
fetch('physical-calibration.json',{cache:'no-store'}).then(response=>{
 if(!response.ok)throw Error('Mapa físico indisponível');return response.json();
}).then(data=>{
 if(data.model!=='17cc:1110'||Object.keys(data.pads||{}).length!==16||Object.keys(data.controls||{}).length!==29)throw Error('Mapa físico incompleto');
 physicalMap=data;el('usb-calibrate').hidden=false;
 const defaults=window.MikroCalibration.ledDefaults(data),revision=data.serial+':'+data.version;
 if(localStorage.getItem('mikro-calibration-revision')!==revision){
  localStorage.setItem('mikro-led-map-before-calibration',JSON.stringify(map));
  map={...map,...defaults};mapSave();localStorage.setItem('mikro-calibration-revision',revision);
 }else map={...defaults,...map};
 mapping();
}).catch(error=>{el('usb-detail').textContent=error.message;});
function mapping(){const id=editor.selected(),slot=map[id];el('usb-mapping').textContent='Selecionado: '+editor.controls()[id].name+' · '+(slot===undefined?'sem endereço confirmado':'LED '+slot)+' · '+Object.keys(map).length+' controles associados.'+(physicalMap?' · Mapa físico verificado':'');if(slot!==undefined&&!probing)el('usb-slot').value=slot}
async function api(path,data){const response=await fetch('/api/'+path,{method:data===undefined?'GET':'POST',headers:data===undefined?{}:{'Content-Type':'application/json','X-Mikro-Token':token},body:data===undefined?undefined:JSON.stringify(data),signal:AbortSignal.timeout(path==='connect'||path==='disconnect'?100000:5000)});const result=await response.json();if(!response.ok)throw Error(result.error||'Falha na ponte USB');return result}
function status(s){connected=s.connected;el('usb-state').textContent=connected?'USB / MK1 CONECTADA':'USB / DESCONECTADO';el('usb-state').classList.toggle('usb-online',connected);el('usb-detail').textContent=s.error|| (connected?s.device.product_string+' · FW '+s.device.release_number+' · '+s.packets+' pacotes · '+s.writes+' envios':'A ponte está pronta. Clique em Conectar USB.');for(const id of ['usb-disconnect','usb-apply','usb-live-wrap'])el(id).hidden=!connected;el('usb-connect').hidden=connected;if(!connected){probing=false}document.querySelector('.status').textContent=connected?'● HARDWARE USB CONECTADO':'● PONTE LOCAL DISPONÍVEL';document.querySelector('.notice').textContent=connected?'Conectado à MK1 por HID. LEDs físicos ativos; mapa calibrado carregado quando disponível. Eventos abaixo são dados reais quando recebidos.':'Modo de simulação: conecte o USB para enviar LEDs ao equipamento.';for(const event of s.events||[]){if(event.seq<=seq)continue;seq=event.seq;showPhysical(event);el('event').textContent='USB real · Report 0x'+event.report.toString(16)+' · bytes alterados: '+event.changed.join(', ')}mapping()}
function frame(){const levels=Array(60).fill(0),pulses=[];for(const [id,c]of Object.entries(editor.controls())){const slot=map[id];if(slot===undefined)continue;levels[slot]=c.led==='on'||c.led==='pulse'?Math.round(c.brightness*31/100):0;if(c.led==='pulse')pulses.push(slot)}return {levels,pulses}}
async function send(data){if(!connected)return;try{await api('leds',data)}catch(error){editor.toast(error.message);el('usb-detail').textContent=error.message;throw error}}
async function apply(){probing=false;await send(frame());editor.toast('LEDs enviados à MK1 · endereços calibrados')}
function fail(error){editor.toast(error.message);el('usb-detail').textContent=error.message}
async function probe(){if(!connected)return;const slot=Number(el('usb-slot').value);if(!Number.isInteger(slot)||slot<0||slot>59)return editor.toast('Use um endereço entre 0 e 59');probing=true;const levels=Array(60).fill(0);levels[slot]=31;await send({levels,pulses:[]});editor.toast('Endereço '+slot+' aceso no hardware')}
el('usb-connect').onclick=async()=>{if(!local){window.open('http://127.0.0.1:8765/','_blank','noopener');return}if(busy)return;busy=true;el('usb-connect').disabled=true;try{token=(await api('session')).token;status(await api('connect',{}));editor.toast('MK1 conectada. Envie os LEDs ou calibre um controle.')}catch(error){fail(error)}finally{busy=false;el('usb-connect').disabled=false}};
el('usb-disconnect').onclick=async()=>{busy=true;clearTimeout(debounce);el('usb-disconnect').disabled=true;try{status(await api('disconnect',{}));editor.toast('USB liberado e serviço NI restaurado')}catch(error){fail(error)}finally{busy=false;el('usb-disconnect').disabled=false}};
el('usb-apply').onclick=()=>apply().catch(()=>{});
el('usb-calibrate').onclick=()=>{panel.hidden=!panel.hidden;if(panel.hidden){probing=false;send(frame()).catch(()=>{})}mapping()};
el('usb-probe').onclick=()=>probe().catch(()=>{});
el('usb-next').onclick=()=>{el('usb-slot').value=(Number(el('usb-slot').value)+1)%60;probe().catch(()=>{})};
el('usb-bind').onclick=()=>{const slot=Number(el('usb-slot').value);if(!Number.isInteger(slot)||slot<0||slot>59)return;const id=editor.selected();for(const [other,value]of Object.entries(map))if(value===slot&&other!==id)delete map[other];map[id]=slot;mapSave();editor.toast(editor.controls()[id].name+' associado ao LED '+slot)};
el('usb-unbind').onclick=()=>{delete map[editor.selected()];mapSave()};
el('usb-map-export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({model:'17cc:1110',leds:map},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='mikro-mk1-mapa-leds.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
window.addEventListener('mikro-selection',mapping);
window.addEventListener('mikro-change',()=>{if(!connected||!el('usb-live').checked||probing||testing)return;clearTimeout(debounce);debounce=setTimeout(()=>send(frame()).catch(()=>{}),100)});
for(const [id,value]of [['all',31],['off',0]])el(id).addEventListener('click',()=>{if(!connected)return;probing=false;send({levels:Array(60).fill(value),pulses:[]}).catch(()=>{})});
async function testPhysical(){if(!connected)return;const id=editor.selected(),slot=map[id];if(slot===undefined)return editor.toast('Selecione Calibrar LEDs para associar este controle.');if(testing)return;testing=true;const data=frame();data.levels[slot]=31;data.pulses=data.pulses.filter(x=>x!==slot);try{await send(data);el('event').textContent='LED físico · '+editor.controls()[id].name+' · comando enviado por USB';setTimeout(()=>{testing=false;send(frame()).catch(()=>{})},700)}catch{testing=false}}
el('test').addEventListener('click',testPhysical);document.querySelectorAll('.control').forEach(b=>b.addEventListener('dblclick',testPhysical));
if(local){api('session').then(s=>{token=s.token;return api('status')}).then(status).catch(fail);setInterval(async()=>{if(polling||busy)return;polling=true;try{status(await api('status'))}catch(error){connected=false;el('usb-state').textContent='PONTE INDISPONÍVEL';el('usb-detail').textContent='Reabra Iniciar-MIKRO.ps1 no computador.'}finally{polling=false}},500)}else{el('usb-detail').textContent='Execute Iniciar-MIKRO.ps1 no Windows e abra a conexão local.'}mapping();
})();
