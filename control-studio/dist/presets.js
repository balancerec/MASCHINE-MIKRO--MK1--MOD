(()=>{
const E=window.MikroEditor,container=document.createElement('section');container.className='ni-parameters';
container.innerHTML='<div class="section-label">PRESETS NI / MK1</div><label>Preset<select id="preset-library"></select></label><label>Banco de pads<select id="preset-bank"></select></label><button id="preset-load" class="primary" disabled>Carregar na página</button><button id="preset-original" disabled>Baixar original .ncmm</button><p id="preset-info" class="hint">Carregando biblioteca…</p><p class="hint">Carregar edita a prévia e mantém o arquivo NI completo. Para usar no equipamento, exporte o .ncmm e abra no Controller Editor. O preset escolhido pode ter notas e funções diferentes do perfil FL atual.</p>';
document.getElementById('templates').prepend(container);
const el=id=>document.getElementById('preset-'+id),value=x=>x&&typeof x==='object'?x.value:x;
let items=[],native=null,loading=0;
const mapping={F1:'button0',F2:'button1',F3:'button2',Main:'button3',Enter:'button7',Browse:'button8',Sampling:'button9',Group:'button10',Repeat:'button11',Restart:'button12',Prev:'button13',Next:'button14',Grid:'button15',Play:'button16',Rec:'button17',Erase:'button18',Scene:'button20',Pattern:'button21','Pad Mode':'button22',Navigate:'button23',Duplicate:'button24',Select:'button25',Solo:'button26',Mute:'button27',Dial:'encoder'};
for(let n=1;n<=16;n++)mapping['Pad'+n]='pad'+n;
function convert(c){
 const type='disabled' in c?'disabled':'note' in c?'note':'controller' in c?'cc':'polyat' in c?'poly-pressure':'disabled';
 const mode=value(c.behavior)||'gate',lo=Number(value(c.min??c.off??0)),hi=Number(value(c.max??c.on??127));
 const result={name:String(value(c.name)||c.id).slice(0,24),type,channel:Number(value(c.channel)||0)+1,number:Number(value(c.note??c.controller??c.polyat??0)),mode:['gate','toggle','trigger'].includes(mode)?mode:'gate',min:Math.max(0,Math.min(127,lo)),max:Math.max(0,Math.min(127,hi)),led:type==='disabled'?'off':'midi',brightness:80,ni:structuredClone(c)};
 result.niEditorBaseline=JSON.stringify(Object.fromEntries(['name','type','channel','number','mode','min','max'].map(k=>[k,result[k]])));
 return result;
}
function template(source,bankIndex){
 const bank=source.pad_groups[bankIndex],defaults=structuredClone(E.controls());
 for(const [id,c] of Object.entries(defaults))defaults[id]={name:c.name,type:'disabled',channel:1,number:0,mode:'gate',min:0,max:127,led:'off',brightness:80,ni:{reserved:true}};
 const pages=source.pages.map(page=>{
  const controls=structuredClone(defaults);
  for(const c of [...source.controls,...page.controls,...(bank?.controls||[])]){const id=mapping[c.id];if(id)controls[id]=convert(c);}
  for(const c of bank?.controls||[])if(c.subtype==='pressure'&&controls['pad'+c.id.slice(8)])controls['pad'+c.id.slice(8)].pressure=convert(c);
  const push=page.controls.find(c=>c.id==='Push');if(push)controls.encoder.push=convert(push);
  return {name:page.name,controls};
 });
 return {name:source.name+(source.pad_groups.length>1?' · '+bank.name:''),sourceId:'library:'+source.id+':'+bankIndex,pages,niSource:structuredClone(source),niSettings:source.settings,padGroup:bank?.name,source_sha256:source.sha256};
}
async function select(){const generation=++loading;native=null;el('load').disabled=el('original').disabled=true;try{let data=window.MikroBundledPresets?.entries[el('library').value];if(!data){const response=await fetch('presets/'+el('library').value+'.json');if(!response.ok)throw Error('Preset indisponível');data=await response.json();}if(generation!==loading)return;native=data;el('bank').replaceChildren(...data.pad_groups.map((b,i)=>new Option(b.name,i)));el('bank').disabled=data.pad_groups.length<2;el('load').disabled=el('original').disabled=false;el('info').textContent=data.pages.length+' páginas · '+data.pad_groups.length+' bancos · '+data.file;}catch(e){el('info').textContent=e.message;}}
el('library').onchange=select;
el('load').onclick=()=>{if(!native)return;E.importNative(template(native,Number(el('bank').value)||0));E.toast('Preset carregado na página; hardware preservado');};
el('original').onclick=()=>{if(!native)return;const a=document.createElement('a'),encoded=window.MikroBundledPresets?.originals[native.id];let url;if(encoded){url=URL.createObjectURL(new Blob([Uint8Array.from(atob(encoded),c=>c.charCodeAt(0))],{type:'application/xml'}));a.href=url;}else a.href='presets/'+encodeURIComponent(native.file);a.download=native.file;a.click();if(url)setTimeout(()=>URL.revokeObjectURL(url),1000);};
const catalogue=window.MikroBundledPresets?Promise.resolve(window.MikroBundledPresets.index):fetch('presets/index.json').then(r=>{if(!r.ok)throw Error('Biblioteca indisponível');return r.json();});
catalogue.then(data=>{items=data;el('library').replaceChildren(...items.map((t,i)=>new Option(String(i+1).padStart(2,'0')+' · '+t.name,t.id)));if(!items.length){el('info').textContent='Biblioteca NI opcional: nenhum preset local incluído.';el('load').disabled=el('original').disabled=true;return;}return select();}).catch(e=>{el('info').textContent=e.message;});
window.MikroPresetLibrary={convert,template};
})();
