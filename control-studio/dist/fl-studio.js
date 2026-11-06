(()=>{
const E=window.MikroEditor,$=id=>document.getElementById(id);
let loaded=false,refreshing=false,template;
const section=document.createElement('section');section.className='fl-native';
section.innerHTML='<div><b>FL STUDIO 2025</b><span id="fl-native-status">Carregando template oficial…</span></div><button id="fl-native-load">Usar template FL Studio</button><button id="fl-native-export">Exportar NI .ncmm</button><button id="fl-native-mode">Usar no FL (MIDI)</button>';
document.querySelector('.hardware-bar').after(section);
const box=document.createElement('section');box.className='ni-parameters';box.innerHTML='<div class="section-label">PARÂMETROS DO TEMPLATE NI</div><label>Ação do controle<select id="ni-action"><option value="hit">Hit / controle principal</option><option value="pressure">Press / pressão do pad</option><option value="push">Clique do encoder</option></select></label><p id="ni-global" class="hint"></p><details><summary>Todos os parâmetros originais</summary><pre id="ni-raw"></pre></details><p class="hint">A exportação .ncmm preserva páginas, bancos, pressão e clique do encoder. No FL, selecione MIKRO - 16 Pads e um canal FPC. O modo MIDI libera o acesso HID direto.</p>';
$('assign').append(box);
function refresh(){if(refreshing)return;refreshing=true;const t=E.template(),base=E.controls()[E.selected()];const action=$('ni-action');action.options[1].disabled=!base.pressure;action.options[2].disabled=!base.push;if((window.niAction==='pressure'&&!base.pressure)||(window.niAction==='push'&&!base.push)){window.niAction='hit';E.refresh()}action.value=window.niAction||'hit';const c=window.niAction==='pressure'?base.pressure:window.niAction==='push'?base.push:base;$('ni-raw').textContent=JSON.stringify(c?.ni||{info:'Este controle não possui atribuição no template NI.'},null,2);$('ni-global').textContent=t.niSettings?'Curva (código '+t.niSettings.velocitycurve+') · Host Transport: '+t.niSettings.handleTransport+' · Wrap: '+t.niSettings.wrapmode+' · Pads: '+t.padGroup:'Selecione FL Studio · NI para consultar o template importado.';refreshing=false}
$('ni-action').onchange=()=>{window.niAction=$('ni-action').value;E.refresh();refresh()};
window.addEventListener('mikro-selection',refresh);window.addEventListener('mikro-change',()=>{if(refreshing)return;const t=E.template(),id=E.selected(),c=E.controls()[id];if(t.niSource&&(id.startsWith('pad')||t.niSource.controls.some(x=>x.id===c.ni?.id))){refreshing=true;for(const page of t.pages)if(page.controls!==E.controls())page.controls[id]=structuredClone(c);E.save();refreshing=false}refresh()});
if(window.MikroLocalAssets?.flTemplate===false){$('fl-native-status').textContent='Template NI opcional não incluído nesta distribuição.';$('fl-native-load').disabled=true;}else fetch('fl-template.json').then(r=>{if(!r.ok)throw Error('Falha ao carregar template');return r.json()}).then(t=>{template=t;loaded=true;$('fl-native-status').textContent='FPC · 16 sons no banco A · BROWSE / PLAY e funções físicas';const existing=E.template().sourceId===t.sourceId;if(!E.template().sourceId?.startsWith('library:'))E.importNative(t);refresh();if(!existing&&!E.template().sourceId?.startsWith('library:'))E.toast('Template FL Studio oficial carregado com todos os parâmetros')}).catch(e=>{$('fl-native-status').textContent=e.message});
$('fl-native-load').onclick=()=>{if(loaded)E.importNative(structuredClone(template))};
function value(v){return v&&typeof v==='object'?v.value:v}
function xmlNode(doc,n){const el=doc.createElement(n.tag);for(const [k,v]of Object.entries(n.attributes||{}))el.setAttribute(k,v);if(n.value)el.append(doc.createTextNode(n.value));for(const c of n.children||[])el.append(xmlNode(doc,c));return el}
function set(el,tag,text){let c=[...el.children].find(x=>x.tagName===tag);if(text===null){c?.remove();return}if(!c){c=el.ownerDocument.createElement(tag);el.append(c)}c.textContent=String(text);return c}
function merge(el,c){
 if(!el||!c)return;
 const original=c.niEditorBaseline?JSON.parse(c.niEditorBaseline):null;
 const changed=key=>!original||original[key]!==c[key];
 if(changed('name')&&([...el.children].some(x=>x.tagName==='name')||c.name!==c.ni?.id))set(el,'name',c.name);
 if(changed('channel'))set(el,'channel',c.channel-1);
 if(changed('type')||changed('number')){
  for(const key of ['note','controller','polyat','program'])set(el,key,null);
  const tag={note:'note',cc:'controller','poly-pressure':'polyat',program:'program'}[c.type];
  if(tag)set(el,tag,c.number);
  set(el,'disabled',c.type==='disabled'?'':null);
 }
 if(changed('mode')&&[...el.children].some(x=>x.tagName==='behavior'))set(el,'behavior',c.mode);
 const pad=el.tagName==='pad'||el.tagName==='wheel';
 if(changed('min'))set(el,pad?'min':'off',c.min);
 if(changed('max'))set(el,pad?'max':'on',c.max);
}
$('fl-native-export').onclick=()=>{const t=E.template();if(!t.niSource)return E.toast('Selecione o template FL Studio · NI');const doc=document.implementation.createDocument('','ni-controller-midi-map');doc.documentElement.setAttribute('version','1');const root=xmlNode(doc,t.niSource.xml_tree);doc.documentElement.append(root);const padGroup=[...root.querySelectorAll('groups > group')].find(g=>g.getAttribute('name')===t.padGroup)||root.querySelector('groups > group');const find=(nodes,id)=>[...nodes].find(n=>n.getAttribute('id')===id);for(const page of t.pages){const p=[...root.querySelectorAll('pages > page')].find(x=>x.getAttribute('name')===page.name);for(const c of Object.values(page.controls)){if(!c.ni?.id||c.ni.reserved)continue;const n=find(p?.children||[],c.ni.id)||find(root.querySelector('controls')?.children||[],c.ni.id)||find(padGroup?.children||[],c.ni.id);merge(n,c);if(c.pressure)merge(find(padGroup?.children||[],c.pressure.ni.id),c.pressure);if(c.push)merge(find(p?.children||[],'Push'),c.push)}}const output='<?xml version="1.0" encoding="UTF-8"?>\n'+new XMLSerializer().serializeToString(doc);const url=URL.createObjectURL(new Blob([output],{type:'application/xml'})),a=document.createElement('a');a.href=url;a.download=t.name.replace(/[\\/:*?"<>|]/g,'-')+' - Control Studio.ncmm';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);E.toast('Template NI completo exportado')};
$('fl-native-mode').onclick=async()=>{if(location.origin!=='http://127.0.0.1:8765')return window.open('http://127.0.0.1:8765/','_blank','noopener');try{const session=await (await fetch('/api/session')).json();const r=await fetch('/api/disconnect',{method:'POST',headers:{'Content-Type':'application/json','X-Mikro-Token':session.token},body:'{}'});const result=await r.json();if(!r.ok)throw Error(result.error);$('fl-native-status').textContent='Modo MIDI: serviço NI ativo · perfil MIKRO - 16 Pads no FL';E.toast('Use FL Studio - 16 Pads no Controller Editor e SHIFT + F1 no equipamento')}catch(e){E.toast(e.message)}};
refresh();
})();
