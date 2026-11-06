(()=>{
const section=document.createElement('section');section.className='hardware-panel';
section.innerHTML='<div><span class="eyebrow">DISPLAY / MK1</span><h3>Ajustes do equipamento</h3><p id="display-state">Leia os valores atuais do display.</p></div><div class="calibration-controls"><label>Brilho<input id="display-brightness" type="number" min="0" max="100" disabled></label><label>Contraste<input id="display-contrast" type="number" min="0" max="100" disabled></label><label><input id="display-inverted" type="checkbox" disabled> Inverter imagem</label><button id="display-read">Ler equipamento</button><button id="display-apply" disabled>Aplicar display</button></div><p class="hint">A leitura mantém o serviço NI ativo. Para aplicar, conecte o USB pela ponte. Os ajustes são conferidos no equipamento e podem ser substituídos pelo Controller Editor ao retomar. Não alteram o template MIDI.</p>';
document.querySelector('.hardware-bar').after(section);
const el=id=>document.getElementById('display-'+id);let loaded=false,busy=false;
async function call(changes){const session=changes?await (await fetch('/api/session')).json():null;
const response=await fetch('/api/display',changes?{method:'POST',headers:{'Content-Type':'application/json','X-Mikro-Token':session.token},body:JSON.stringify(changes)}:{});
const result=await response.json();if(!response.ok)throw Error(result.error||'Falha no display');return result;}
function render(s){el('brightness').value=s.brightness;el('contrast').value=s.contrast;el('inverted').checked=s.inverted;loaded=true;for(const id of ['brightness','contrast','inverted','apply'])el(id).disabled=false;el('state').textContent='Lido do hardware · brilho '+s.brightness+' · contraste '+s.contrast+' · '+(s.inverted?'invertido':'normal');}
async function run(changes){if(busy)return;busy=true;el('read').disabled=true;el('apply').disabled=true;try{render(await call(changes));}catch(e){el('state').textContent=e.message;}finally{busy=false;el('read').disabled=false;el('apply').disabled=!loaded;}}
el('read').onclick=()=>run();el('apply').onclick=()=>{const brightness=Number(el('brightness').value),contrast=Number(el('contrast').value);if(![brightness,contrast].every(x=>Number.isInteger(x)&&x>=0&&x<=100)||!el('brightness').value||!el('contrast').value){el('state').textContent='Use valores inteiros entre 0 e 100.';return;}run({brightness,contrast,inverted:el('inverted').checked});};
if(location.origin!=='http://127.0.0.1:8765'){el('read').disabled=true;el('state').textContent='Abra a conexão local para ler o display.';}
})();
