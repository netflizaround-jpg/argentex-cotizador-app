/* PuntoLiga · Liga La Farola. Isolated, nonproduction demonstration model.
   No access to real league records. Exported for repeatable QA. */
const CATEGORIES = Object.freeze([
  {id:'mas-5',name:'5ª Masculina',branch:'Masculina',level:5},
  {id:'mas-6',name:'6ª Masculina',branch:'Masculina',level:6},
  {id:'mas-7',name:'7ª Masculina',branch:'Masculina',level:7},
  {id:'fem-6',name:'6ª Femenina',branch:'Femenina',level:6},
  {id:'fem-7',name:'7ª Femenina',branch:'Femenina',level:7}
]);
const PAIRS = Object.freeze([
  {id:'P101',name:'Ríos / Suárez',people:'Matías Ríos · Joaquín Suárez',categoryId:'mas-6'},
  {id:'P102',name:'Castro / Vega',people:'Lucas Castro · Bruno Vega',categoryId:'mas-6'},
  {id:'P103',name:'Ferrer / Benítez',people:'Nicolás Ferrer · Diego Benítez',categoryId:'mas-6'},
  {id:'P104',name:'Acosta / Molina',people:'Francisco Acosta · Tomás Molina',categoryId:'mas-5'},
  {id:'P105',name:'Gómez / Arias',people:'Pablo Gómez · Ramiro Arias',categoryId:'mas-5'},
  {id:'P106',name:'Ortiz / Luna',people:'Santiago Ortiz · Martín Luna',categoryId:'mas-7'},
  {id:'P107',name:'Peralta / Ruiz',people:'Ezequiel Peralta · Bruno Ruiz',categoryId:'mas-7'},
  {id:'P201',name:'Díaz / Quiroga',people:'Marina Díaz · Valentina Quiroga',categoryId:'fem-7'},
  {id:'P202',name:'Silva / Herrera',people:'Julieta Silva · Ana Herrera',categoryId:'fem-7'},
  {id:'P203',name:'López / Álvarez',people:'Clara López · Micaela Álvarez',categoryId:'fem-6'},
  {id:'P204',name:'Ramos / Medina',people:'Agustina Ramos · Lucía Medina',categoryId:'fem-6'}
]);
const MATCHES = Object.freeze([
  {id:'LF-101',categoryId:'mas-6',a:'P101',b:'P102',date:'2026-11-01',time:'19:00',court:'Cancha 1',score:'6-4, 6-3',status:'played'},
  {id:'LF-102',categoryId:'mas-6',a:'P101',b:'P103',date:'2026-11-02',time:'20:00',court:'Cancha 2',score:'4-6, 4-6',status:'played'},
  {id:'LF-103',categoryId:'mas-6',a:'P102',b:'P103',date:'2026-11-04',time:'21:00',court:'Cancha 3',score:'6-2, 7-5',status:'played'},
  {id:'LF-104',categoryId:'mas-5',a:'P104',b:'P105',date:'2026-11-05',time:'18:30',court:'Cancha 2',score:'6-3, 6-4',status:'played'},
  {id:'LF-105',categoryId:'fem-7',a:'P201',b:'P202',date:'2026-11-06',time:'20:00',court:'Cancha 1',score:'6-4, 7-5',status:'played'},
  {id:'LF-106',categoryId:'fem-6',a:'P203',b:'P204',date:'2026-11-07',time:'18:00',court:'Cancha 2',score:'4-6, 6-3, 6-4',status:'played'},
  {id:'LF-107',categoryId:'mas-7',a:'P106',b:'P107',date:'2026-11-14',time:'19:00',court:'Cancha 3',score:'',status:'scheduled'}
]);
export function initialState(){return {version:1,revision:1,categories:CATEGORIES.map(x=>({...x})),pairs:PAIRS.map(x=>({...x})),matches:MATCHES.map(x=>({...x})),movements:[],nextMatch:108,nextMove:1};}
const fail=msg=>{throw new Error(msg)};
const clone=s=>JSON.parse(JSON.stringify(s));
export function categoryOf(s,id){return s.categories.find(c=>c.id===id)}
export function pairOf(s,id){return s.pairs.find(p=>p.id===id)}
export function pairName(s,id){return pairOf(s,id)?.name??id}
export function promotionTargets(s,pairId){const p=pairOf(s,pairId);if(!p)return [];const c=categoryOf(s,p.categoryId);if(!c)return [];return s.categories.filter(x=>x.branch===c.branch && x.level<c.level).sort((a,b)=>b.level-a.level);}
export function pendingMatches(s,pairId){const p=pairOf(s,pairId);if(!p)return [];return s.matches.filter(m=>m.categoryId===p.categoryId&&m.status!=='played'&&(m.a===pairId||m.b===pairId));}
export function promotePair(s,pairId,toCategoryId,at='2026-11-10T20:00:00-03:00'){
 const p=pairOf(s,pairId);if(!p)fail('La pareja no existe.');const from=categoryOf(s,p.categoryId),to=categoryOf(s,toCategoryId);
 if(!from||!to||from.branch!==to.branch||!(to.level<from.level))fail('Elegí una categoría superior de la misma rama.');
 const pending=pendingMatches(s,pairId);if(pending.length)fail(`La pareja tiene ${pending.length} partido(s) pendiente(s) en su categoría. Resolvelos antes de ascender.`);
 const n=clone(s);n.pairs.find(x=>x.id===pairId).categoryId=to.id;
 n.movements.push({id:`LF-A-${String(n.nextMove++).padStart(3,'0')}`,pairId,fromCategoryId:from.id,toCategoryId:to.id,at});
 n.revision++;return n;
}
export function parseScore(score){
 const parts=String(score||'').trim().split(/[,;]/).map(x=>x.trim()).filter(Boolean);
 if(parts.length<2||parts.length>3)fail('Ingresá 2 o 3 sets, por ejemplo 6-4, 6-3.');
 let wonA=0,wonB=0;
 for(const part of parts){const m=part.match(/^(\d{1,2})\s*[-:]\s*(\d{1,2})$/);if(!m)fail('Formato de marcador inválido. Usá 6-4, 6-3.');const a=Number(m[1]),b=Number(m[2]);if(a===b||a>7||b>7||Math.max(a,b)<6||Math.abs(a-b)<2&&Math.max(a,b)!==7||Math.max(a,b)===7&&Math.min(a,b)<5)fail('Marcador de set inválido.');
 if(a>b)wonA++;else wonB++;
 }
 if(Math.max(wonA,wonB)!==2||wonA===wonB||parts.length!==wonA+wonB||parts.length===3&&parts.slice(0,2).filter(x=>Number(x.split(/[-:]/)[0])>Number(x.split(/[-:]/)[1])).length!==1)fail('El partido debe terminar cuando una pareja gana 2 sets.');
 return {winner:wonA>wonB?'a':'b',wonA,wonB,normalized:parts.join(', ')};
}
export function countHeadToHead(s,a,b,categoryId){return s.matches.filter(m=>m.categoryId===categoryId&&((m.a===a&&m.b===b)||(m.a===b&&m.b===a))).length;}
export function createRematch(s,{categoryId,a,b,date,time,court,score=''}){
 if(!a||!b||a===b)fail('Seleccioná dos parejas diferentes.');const cat=categoryOf(s,categoryId),pa=pairOf(s,a),pb=pairOf(s,b);
 if(!cat||!pa||!pb||pa.categoryId!==cat.id||pb.categoryId!==cat.id)fail('Las dos parejas deben estar activas en la categoría seleccionada.');
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date||'')||!/^([01]\d|2[0-3]):[0-5]\d$/.test(time||'')||!court?.trim())fail('Completá fecha, hora y cancha.');
 if(Number.isNaN(Date.parse(`${date}T${time}:00`)))fail('Fecha inválida.');
 if(court.trim().length>80)fail('El nombre de la cancha es demasiado largo.');
 const parsed=score?.trim()?parseScore(score):null;
 const n=clone(s),id=`LF-${n.nextMatch++}`;
 n.matches.push({id,categoryId,a,b,date,time,court:court.trim(),score:parsed?.normalized||'',status:parsed?'played':'scheduled'});
 n.revision++;return {state:n,matchId:id};
}
export function registerResult(s,matchId,score){const m=s.matches.find(x=>x.id===matchId);if(!m)fail('Partido inexistente.');if(m.status==='played')fail('El partido ya tiene un resultado.');const parsed=parseScore(score);const n=clone(s);Object.assign(n.matches.find(x=>x.id===matchId),{score:parsed.normalized,status:'played'});n.revision++;return n;}
export function standings(s,categoryId){
 const table=new Map();function row(id){if(!table.has(id))table.set(id,{pairId:id,played:0,wins:0,losses:0});return table.get(id)}
 for(const p of s.pairs.filter(p=>p.categoryId===categoryId))row(p.id);
 for(const m of s.matches.filter(m=>m.categoryId===categoryId&&m.status==='played')){
  const winner=parseScore(m.score).winner;for(const id of [m.a,m.b])row(id).played++;
  row(m[winner]).wins++;row(m[winner==='a'?'b':'a']).losses++;
 }
 return [...table.values()].sort((a,b)=>b.wins-a.wins||b.played-a.played||pairName(s,a.pairId).localeCompare(pairName(s,b.pairId)));
}