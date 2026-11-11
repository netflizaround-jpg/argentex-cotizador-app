import {initialState,pairOf,pairName,categoryOf,promotionTargets,pendingMatches,promotePair,countHeadToHead,createRematch,registerResult,standings,parseScore} from './model.mjs';
const $=id=>document.getElementById(id);
const escapeHTML=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const STORAGE_KEY='puntoliga-farola-preview-2026-v1';
function recover(){try{const d=JSON.parse(sessionStorage.getItem(STORAGE_KEY));if(d?.version===1&&Array.isArray(d.pairs)&&Array.isArray(d.matches)&&d.pairs.length>=11&&d.categories.length===5)return d;}catch{}return initialState()}
let state=recover();
let activeTab='promotion';
function persist(){try{sessionStorage.setItem(STORAGE_KEY,JSON.stringify(state));}catch{}}
function selectOptions(items,placeholder,previous=''){const result=`<option value="">${escapeHTML(placeholder)}</option>`+items.map(x=>`<option value="${escapeHTML(x.id)}"${x.id===previous?' selected':''}>${escapeHTML(x.name)}</option>`).join('');return result;}
function notify(text,error=false){const box=$('alert');box.classList.remove('hidden');box.classList.toggle('error',error);box.textContent=text;box.scrollIntoView({block:'nearest',behavior:'smooth'})}
function categoryName(id){return categoryOf(state,id)?.name||id}
function updateSummary(){$('stat-pairs').textContent=state.pairs.length;$('stat-matches').textContent=state.matches.length;$('stat-promotions').textContent=state.movements.length;}
function promotionForm(){const select=$('promotion-pair'),before=select.value;select.innerHTML=selectOptions(state.pairs.map(p=>({...p,name:`${p.name} · ${categoryName(p.categoryId)}`})),'Elegí una pareja',before);if(!select.value)select.value='P101';
 const pairId=select.value,p=pairOf(state,pairId),targets=promotionTargets(state,pairId),target=$('promotion-target'),prior=target.value;
 target.innerHTML=selectOptions(targets,'Elegí el destino',prior);if(!target.value&&targets.length)target.value=targets[0].id;
 const count=pendingMatches(state,pairId).length;let msg=!p?'Seleccioná una pareja.':!targets.length?'Esta pareja no tiene una categoría superior disponible en esta muestra.':count?`Esta pareja tiene ${count} partido(s) pendiente(s). Resolvelos antes del ascenso.`:`La pareja conservará todos los encuentros de ${categoryName(p.categoryId)} en el historial. No se duplicará su identidad (${p.id}).`;
 $('promotion-explain').textContent=msg;$('form-promotion').querySelector('button[type=submit]').disabled=!p||!targets.length||count>0;
}
function rematchForm(){const c=$('rematch-category'),catBefore=c.value;c.innerHTML=selectOptions(state.categories,'Elegí una categoría',catBefore);if(!c.value)c.value='mas-6';const pairs=state.pairs.filter(p=>p.categoryId===c.value);
 for(const [id,idx] of [['rematch-a',0],['rematch-b',1]]){const el=$(id),prior=el.value;el.innerHTML=selectOptions(pairs,'Elegí una pareja',prior);if(!el.value&&pairs[idx])el.value=pairs[idx].id;}
 const a=$('rematch-a').value,b=$('rematch-b').value;const valid=a&&b&&a!==b;
 const count=valid?countHeadToHead(state,a,b,c.value):0;
 $('rematch-explain').textContent=valid?`Ya existen ${count} encuentro(s) entre estas parejas en ${categoryName(c.value)}. El nuevo tendrá un ID propio y no reemplazará ninguno.`:'Seleccioná dos parejas distintas de la misma categoría.';
 $('form-rematch').querySelector('button[type=submit]').disabled=!valid;
}
function renderActivities(){const area=$('activity'),items=state.movements.slice().reverse().slice(0,3);area.innerHTML=items.length?items.map(m=>`<div class="activity-row"><span class="activity-icon">↗</span><div class="activity-copy"><strong>${escapeHTML(pairName(state,m.pairId))}</strong><small>${escapeHTML(categoryName(m.fromCategoryId))} → ${escapeHTML(categoryName(m.toCategoryId))}</small></div><span class="match-id">${escapeHTML(m.id)}</span></div>`).join(''):'<div class="activity-row"><span class="activity-icon">◫</span><div class="activity-copy"><strong>Historial preservado</strong><small>Probá un ascenso para ver el registro del movimiento.</small></div></div>';
 const changes=state.movements.length;
 $('insight-content').innerHTML=changes?`<h3>${changes} movimiento${changes>1?'s':''} registrado${changes>1?'s':''}.</h3><p>Cada ascenso se registra sin cambiar el ID de la pareja ni los resultados de los partidos anteriores. Los nuevos encuentros se contabilizan en la categoría de destino.</p>`:'<h3>La historia se conserva.</h3><p>Los resultados ya disputados permanecen vinculados a su categoría original. El ascenso solo cambia la categoría activa de la pareja.</p>';
}
function refreshHistory(){const sel=$('history-category'),prev=sel.value;sel.innerHTML=selectOptions(state.categories,'Seleccioná categoría',prev);if(!sel.value)sel.value='mas-6';
 const cat=sel.value,ms=state.matches.filter(m=>m.categoryId===cat).slice().reverse();$('match-count').textContent=`${ms.length} partido${ms.length===1?'':'s'}`;
 $('matches').innerHTML=ms.length?ms.map(m=>`<div class="match-row"><div><div class="match-meta"><span class="match-id">${escapeHTML(m.id)}</span><span>${escapeHTML(m.date)}</span><span>${escapeHTML(m.court)}</span></div><div class="match-pairs">${escapeHTML(pairName(state,m.a))}<span class="vs">VS</span>${escapeHTML(pairName(state,m.b))}</div></div><div class="match-right">${m.status==='played'?`<div class="match-score">${escapeHTML(m.score)}</div><span class="status-tag">FINALIZADO</span>`:`<div class="match-pending">PENDIENTE</div><button class="result-btn" data-result="${escapeHTML(m.id)}">Cargar resultado</button>`}</div></div>`).join(''):'<div class="empty">Todavía no hay partidos en esta categoría.</div>';
 const rows=standings(state,cat);$('standings').innerHTML=rows.map(r=>{const p=pairOf(state,r.pairId),old=p?.categoryId!==cat;return `<tr><td>${escapeHTML(pairName(state,r.pairId))}${old?'<small class="archived-note">Ascendida · registro histórico</small>':''}</td><td>${r.played}</td><td>${r.wins}</td><td>${r.losses}</td></tr>`}).join('');
 for(const btn of document.querySelectorAll('[data-result]'))btn.addEventListener('click',()=>{const matchId=btn.dataset.result,score=prompt(`Resultado de ${matchId}. Escribí los sets en orden de pareja 1, ejemplo 6-4, 6-3:`, '6-4, 6-3');if(score===null)return;try{state=registerResult(state,matchId,score);persist();renderAll();notify(`Resultado del partido ${matchId} cargado. El historial de los demás encuentros no cambió.`)}catch(e){notify(e.message,true)}});
}
function renderAll(){updateSummary();promotionForm();rematchForm();renderActivities();refreshHistory();}
for(const tab of document.querySelectorAll('[data-tab]'))tab.addEventListener('click',()=>{
 activeTab=tab.dataset.tab;for(const b of document.querySelectorAll('[data-tab]')){const yes=b.dataset.tab===activeTab;b.classList.toggle('active',yes);b.setAttribute('aria-selected',String(yes));}
 $('panel-promotion').classList.toggle('hidden',activeTab!=='promotion');$('panel-rematch').classList.toggle('hidden',activeTab!=='rematch');$('alert').classList.add('hidden');
});
$('promotion-pair').addEventListener('change',promotionForm);$('promotion-target').addEventListener('change',promotionForm);
$('rematch-category').addEventListener('change',rematchForm);$('rematch-a').addEventListener('change',rematchForm);$('rematch-b').addEventListener('change',rematchForm);
$('history-category').addEventListener('change',refreshHistory);
$('form-promotion').addEventListener('submit',e=>{e.preventDefault();const id=$('promotion-pair').value,to=$('promotion-target').value;try{const old=categoryName(pairOf(state,id).categoryId);const newName=categoryName(to);state=promotePair(state,id,to);persist();renderAll();$('promotion-pair').value=id;promotionForm();notify(`Ascenso registrado: ${pairName(state,id)}, ${old} → ${newName}. Se conservan los resultados previos.`)}catch(err){notify(err.message,true)}});
$('form-rematch').addEventListener('submit',e=>{e.preventDefault();const categoryId=$('rematch-category').value,a=$('rematch-a').value,b=$('rematch-b').value;try{const {state:next,matchId}=createRematch(state,{categoryId,a,b,date:$('rematch-date').value,time:$('rematch-time').value,court:$('rematch-court').value,score:$('rematch-score').value});state=next;persist();renderAll();$('history-category').value=categoryId;refreshHistory();$('rematch-score').value='';notify(`Nuevo partido ${matchId} registrado. Se agregó al historial sin sobrescribir enfrentamientos anteriores.`)}catch(err){notify(err.message,true)}});
$('reset').addEventListener('click',()=>{if(!confirm('¿Restablecer los datos ficticios de esta demostración?'))return;state=initialState();persist();renderAll();$('alert').classList.add('hidden');});
$('download-state').addEventListener('click',()=>{const exportData={advertencia:'DEMO / DATOS FICTICIOS. No son resultados oficiales de La Farola.',exportedAt:new Date().toISOString(),...state};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(exportData,null,2)],{type:'application/json'}));a.download='puntoliga-la-farola-demo.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1500);});
renderAll();