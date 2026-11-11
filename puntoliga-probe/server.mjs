import http from 'node:http';
import crypto from 'node:crypto';
import {get} from '@vercel/blob';

function decryptDocument(path, raw, master) {
 const record=JSON.parse(raw);
 if(record.alg!=='A256GCM'||record.v!==1)throw new Error('encrypted document format mismatch');
 const bytes=Buffer.from(master||'','base64url');
 if(bytes.length!==32)throw new Error('master key invalid');
 const key=Buffer.from(crypto.hkdfSync('sha256',bytes,Buffer.from('padel-platform-v1'),Buffer.from(path.split('/').slice(0,2).join('/')),32));
 const decipher=crypto.createDecipheriv('aes-256-gcm',key,Buffer.from(record.iv,'base64url'));
 decipher.setAAD(Buffer.from(path));
 decipher.setAuthTag(Buffer.from(record.tag,'base64url'));
 return JSON.parse(Buffer.concat([decipher.update(Buffer.from(record.data,'base64url')),decipher.final()]).toString('utf8'));
}

async function inspectReadOnly() {
 if(!process.env.BLOB_READ_WRITE_TOKEN||!process.env.PLATFORM_MASTER_KEY)return {ok:false,code:'not_configured'};
 try {
  const blob=await get('platform/catalog',{access:'private',token:process.env.BLOB_READ_WRITE_TOKEN,useCache:false});
  if(!blob||blob.statusCode!==200||!blob.stream)return {ok:false,code:'catalog_unavailable'};
  const raw=await new Response(blob.stream).text();
  const doc=decryptDocument('platform/catalog',raw,process.env.PLATFORM_MASTER_KEY);
  const exists=Array.isArray(doc.leagues)&&doc.leagues.some(l=>l.slug==='liga-la-farola');
  return {ok:exists,code:exists?'source_verified':'farola_not_in_catalog'};
 } catch {return {ok:false,code:'source_inaccessible_or_incompatible'};}
}
const port=Number(process.env.PORT||10000);
http.createServer(async(req,res)=>{
 if(req.method!=='GET'||!['/healthz','/'].includes(req.url?.split('?')[0]||'')) {res.writeHead(404);return res.end();}
 const info=await inspectReadOnly();
 res.writeHead(info.ok?200:503,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
 res.end(JSON.stringify({service:'PuntoLiga migration readiness',...info,readOnly:true}));
}).listen(port,'0.0.0.0');
