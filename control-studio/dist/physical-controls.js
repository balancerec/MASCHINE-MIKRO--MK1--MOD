(()=>{
const E=window.MikroEditor;
const info=document.createElement('p');info.className='physical-role';document.getElementById('selected').after(info);
const kit=document.createElement('p');kit.className='hint';info.after(kit);
function kitInfo(){const c=E.controls()[E.selected()];kit.textContent=c.role==='pad'&&c.fpcSound?'FPC · Banco A · '+c.fpcSound+' · Nota de destino inicial '+c.fpcNote+'. O script acompanha o mapa do kit selecionado no FL.':''}
window.addEventListener('mikro-selection',kitInfo);window.addEventListener('mikro-change',kitInfo);kitInfo();
function refresh(){const base=E.controls()[E.selected()];const c=window.niAction==='pressure'&&base.pressure?base.pressure:window.niAction==='push'&&base.push?base.push:base;const isFunction=c.role==='function';for(const id of ['type','number','channel'])document.getElementById(id).disabled=isFunction;info.textContent=isFunction?'FUNÇÃO FL · '+(c.function||'Navegação local NI'):c.role==='pad'?'PAD MUSICAL · Nota '+c.number+' · Canal '+c.channel:c.role==='pressure'?'PRESSÃO DO PAD · Não dispara uma segunda nota':'';if(isFunction)document.getElementById('lcdvalue').textContent='FUNÇÃO / FL STUDIO';document.querySelectorAll('.control').forEach(b=>{const data=E.controls()[b.dataset.id];b.classList.toggle('function-control',data.role==='function');b.classList.toggle('musical-pad',data.role==='pad')})}
window.addEventListener('mikro-selection',refresh);window.addEventListener('mikro-change',refresh);refresh();
})();
