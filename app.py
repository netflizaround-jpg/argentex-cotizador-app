"""Argentex Cotizador App 1.0 — API + PWA local, SQLite persistente."""
import os, hmac, hashlib, time, base64, json, pathlib, secrets, sqlite3, tempfile, datetime
from contextlib import asynccontextmanager
from urllib.parse import quote
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, Response, JSONResponse
from starlette.background import BackgroundTask
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from database import init, connect, get_settings, now, new_id, all_orders, patch, invalidate_order, ensure_fields, DB_PATH
from core import calculate_order, classify_market, D
from fx import get_fx, refresh
from vision import inspect_image

BASE = pathlib.Path(__file__).resolve().parent
PUBLIC = BASE/'public'
AUTH_PASSWORD=os.getenv('APP_ADMIN_PASSWORD','')
APP_SECRET=os.getenv('APP_SECRET') or secrets.token_hex(32)
SESSION_SECONDS=60*60*24*14

@asynccontextmanager
async def lifespan(app):
    if os.getenv('PORT') and not AUTH_PASSWORD:
        raise RuntimeError('Definí APP_ADMIN_PASSWORD para despliegues públicos.')
    init()
    yield

app=FastAPI(title='Argentex Cotizador App', version='1.2.0', lifespan=lifespan)
app.mount('/assets',StaticFiles(directory=PUBLIC),name='assets')

class Data(BaseModel):
    data:dict=Field(default_factory=dict)

class Login(BaseModel):
    password:str

class PhotoRequest(BaseModel):
    data_url:str


def auth_token():
    time_part=str(int(time.time()))
    digest=hmac.new(APP_SECRET.encode(),time_part.encode(),hashlib.sha256).hexdigest()
    return time_part+'.'+digest

def auth_ok(request):
    if not AUTH_PASSWORD: return True
    cookie=request.cookies.get('argentex_session','')
    try:
        timestamp,sig=cookie.split('.',1)
        if abs(time.time()-int(timestamp))>SESSION_SECONDS: return False
        expected=hmac.new(APP_SECRET.encode(),timestamp.encode(),hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig,expected)
    except Exception: return False

@app.middleware('http')
async def gate(request,call_next):
    public=['/api/health','/api/login','/api/auth/status','/manifest.webmanifest','/sw.js','/favicon.svg']
    if request.url.path.startswith('/api/') and request.url.path not in public and not auth_ok(request):
        return JSONResponse({'detail':'Iniciá sesión'},status_code=401)
    response=await call_next(request)
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

@app.get('/')
def index():return FileResponse(PUBLIC/'index.html')
@app.get('/manifest.webmanifest')
def manifest():return FileResponse(PUBLIC/'manifest.webmanifest',media_type='application/manifest+json')
@app.get('/sw.js')
def sw():return FileResponse(PUBLIC/'sw.js',media_type='text/javascript',headers={'Cache-Control':'no-store'})
@app.get('/favicon.svg')
def icon():return FileResponse(PUBLIC/'favicon.svg',media_type='image/svg+xml')
@app.get('/api/health')
def health():return {'ok':True,'service':'argentex-1.2','auth_configured':bool(AUTH_PASSWORD)}
@app.get('/api/auth/status')
def auth_status(request:Request):return {'protected':bool(AUTH_PASSWORD),'authenticated':auth_ok(request)}
@app.post('/api/login')
def login(payload:Login):
    if AUTH_PASSWORD and not hmac.compare_digest(payload.password,AUTH_PASSWORD):
        raise HTTPException(401,'Contraseña incorrecta')
    response=JSONResponse({'ok':True})
    response.set_cookie('argentex_session',auth_token(),httponly=True,secure=bool(os.getenv('PORT')),
                        samesite='lax',max_age=SESSION_SECONDS)
    return response
@app.post('/api/logout')
def logout():
    response=JSONResponse({'ok':True})
    response.delete_cookie('argentex_session')
    return response

@app.get('/api/backup')
def backup():
    """Descarga consistente de todos los pedidos/clientes/fotos. Requiere sesión."""
    fd, path = tempfile.mkstemp(prefix='argentex-backup-', suffix='.sqlite3')
    os.close(fd)
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as original:
            with sqlite3.connect(path) as copy:
                original.backup(copy)
        filename='argentex-respaldo-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')+'.sqlite3'
        return FileResponse(path, filename=filename, media_type='application/vnd.sqlite3',
                            background=BackgroundTask(os.unlink,path),
                            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    except Exception:
        if os.path.exists(path): os.unlink(path)
        raise

@app.get('/api/state')
def state():
    with connect() as db:
        settings=get_settings(db); fx=get_fx(db,settings)
        orders=all_orders(db)
        for o in orders:
            o['calc']=calculate_order(o,settings,fx)
            if o['status']=='approved' and o.get('approved_sell_usd') is not None:
                # Precio comercial USD aprobado permanece congelado hasta nueva edición.
                o['calc']['sell_price_usd']=o['approved_sell_usd']
                o['calc']['profit_usd']=round(o['approved_sell_usd']-o['approved_cost_usd'],2) if o.get('approved_cost_usd') is not None else None
                o['calc']['cost_usd']=o['approved_cost_usd']
                o['calc']['sell_price_ars_approx']=round(o['approved_sell_usd']*fx['selected_rate'],2) if fx['valid'] else None
        customers=[dict(c) for c in db.execute('SELECT * FROM customers ORDER BY created_at DESC')]
        return {'settings':settings,'fx':fx,'orders':orders,'customers':customers,
                'services':{'vision':bool(os.getenv('OPENAI_API_KEY')),'market_api':False,'fx_api':True,
                            'weight_api':False,'storage':'neon-snapshot' if os.getenv('DATABASE_URL') else 'sqlite'},'server_at':now()}

@app.post('/api/customers')
def create_customer(payload:Data):
    d=ensure_fields(payload.data, {'full_name','phone','notes'})
    name=str(d.get('full_name','')).strip()
    if not name: raise HTTPException(400,'Ingresá el nombre del cliente')
    id=new_id()
    with connect() as db:
        db.execute('INSERT INTO customers(id,full_name,phone,notes,created_at) VALUES(?,?,?,?,?)',
                   (id,name,str(d.get('phone','')),str(d.get('notes','')),now()))
    return {'ok':True,'id':id}

@app.patch('/api/customers/{cid}')
def update_customer(cid:str,payload:Data):
    d=ensure_fields(payload.data,{'full_name','phone','notes'})
    if 'full_name' in d and not str(d['full_name']).strip():raise HTTPException(400,'Nombre obligatorio')
    with connect() as db:
        patch(db,'customers',cid,d,{'full_name','phone','notes'})
    return {'ok':True}

@app.post('/api/orders')
def create_order(payload:Data):
    d=ensure_fields(payload.data,{'customer_id','label'})
    id=new_id(); stamp=now()
    with connect() as db:
        db.execute('INSERT INTO orders(id,customer_id,label,created_at,updated_at) VALUES(?,?,?,?,?)',
                   (id,d.get('customer_id') or None,str(d.get('label') or 'Nueva cotización'),stamp,stamp))
    return {'ok':True,'id':id}

@app.patch('/api/orders/{oid}')
def update_order(oid:str,payload:Data):
    allowed={'customer_id','label','outer_packaging_g','tax_mode','tax_rate','us_shipping_override','import_extra_usd','notes','price_override_usd','tax_reviewed','import_cost_reviewed'}
    d=ensure_fields(payload.data,allowed)
    if 'outer_packaging_g' in d and (int(d['outer_packaging_g'])<0 or int(d['outer_packaging_g'])>100000):raise HTTPException(400,'Embalaje inválido')
    if 'tax_mode' in d and d['tax_mode'] not in ('not_applicable','included','apply'):raise HTTPException(400,'Impuestos inválidos')
    for f in ('tax_rate','import_extra_usd','us_shipping_override','price_override_usd'):
        if f in d and d[f] not in ('',None) and float(d[f])<0: raise HTTPException(400,'Valor negativo')
    for f in ('tax_reviewed','import_cost_reviewed'):
        if f in d: d[f]=int(bool(d[f]))
    for f in ('us_shipping_override','price_override_usd','customer_id'):
        if d.get(f)=='': d[f]=None
    with connect() as db:
        patch(db,'orders',oid,d,allowed)
        invalidate_order(db,oid)
    return {'ok':True}

@app.post('/api/orders/{oid}/items')
def create_item(oid:str,payload:Data):
    with connect() as db:
        if not db.execute('SELECT id FROM orders WHERE id=?',(oid,)).fetchone():raise HTTPException(404,'Pedido inexistente')
        category=payload.data.get('category','accesorios')
        if category not in get_settings(db)['rates_usd_kg']:raise HTTPException(400,'Categoría inválida')
        data=payload.data
        name=str(data.get('name') or 'Producto por identificar').strip()
        price=float(data.get('unit_price_usd') or 0)
        grams=int(data.get('unit_weight_g') or 0)
        qty=int(data.get('qty') or 1)
        if price<0 or grams<0 or qty<1 or qty>500:raise HTTPException(400,'Datos de producto inválidos')
        id=new_id()
        db.execute('INSERT INTO items(id,order_id,name,brand,sku,variant,category,unit_price_usd,qty,unit_weight_g,weight_source,weight_verified,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (id,oid,name,str(data.get('brand') or ''),str(data.get('sku') or ''),str(data.get('variant') or ''),category,price,qty,grams,
                    str(data.get('weight_source') or ''),int(bool(data.get('weight_verified'))),now()))
        invalidate_order(db,oid)
        return {'ok':True,'id':id}

@app.patch('/api/items/{iid}')
def update_item(iid:str,payload:Data):
    allowed={'name','brand','sku','variant','category','unit_price_usd','qty','unit_weight_g','weight_source','weight_verified'}
    d=ensure_fields(payload.data,allowed)
    with connect() as db:
        row=db.execute('SELECT order_id FROM items WHERE id=?',(iid,)).fetchone()
        if not row:raise HTTPException(404,'Producto inexistente')
        if 'category' in d and d['category'] not in get_settings(db)['rates_usd_kg']:raise HTTPException(400,'Categoría inválida')
        if 'qty' in d and (int(d['qty'])<1 or int(d['qty'])>500):raise HTTPException(400,'Cantidad inválida')
        if 'unit_weight_g' in d and (int(d['unit_weight_g'])<0 or int(d['unit_weight_g'])>200000):raise HTTPException(400,'Peso inválido')
        if 'unit_price_usd' in d and float(d['unit_price_usd'])<0:raise HTTPException(400,'Precio inválido')
        if 'weight_verified' in d: d['weight_verified']=int(bool(d['weight_verified']))
        patch(db,'items',iid,d,allowed)
        invalidate_order(db,row['order_id'])
    return {'ok':True}

@app.delete('/api/items/{iid}')
def delete_item(iid:str):
    with connect() as db:
        row=db.execute('SELECT order_id FROM items WHERE id=?',(iid,)).fetchone()
        if not row:raise HTTPException(404,'Producto inexistente')
        db.execute('DELETE FROM items WHERE id=?',(iid,))
        invalidate_order(db,row['order_id'])
    return {'ok':True}

@app.post('/api/items/{iid}/photo')
def save_photo(iid:str,payload:PhotoRequest):
    data=payload.data_url
    if not data.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,')) or len(data)>7_000_000:
        raise HTTPException(400,'Foto inválida (máximo ~5 MB)')
    try: photo=base64.b64decode(data.split(',',1)[1],validate=True)
    except Exception:raise HTTPException(400,'Imagen inválida')
    with connect() as db:
        cur=db.execute('UPDATE items SET photo=? WHERE id=?',(photo,iid))
        if not cur.rowcount:raise HTTPException(404,'Producto inexistente')
    return {'ok':True}

@app.get('/api/items/{iid}/photo')
def get_photo(iid:str):
    with connect() as db:
        x=db.execute('SELECT photo FROM items WHERE id=?',(iid,)).fetchone()
        if not x or not x['photo']:raise HTTPException(404,'Foto no encontrada')
        data=x['photo']
        mime='image/png' if data.startswith(b'\x89PNG') else 'image/webp' if data.startswith(b'RIFF') else 'image/jpeg'
        return Response(data,media_type=mime,headers={'Cache-Control':'private, max-age=300'})

@app.post('/api/items/{iid}/market')
def create_market(iid:str,payload:Data):
    d=ensure_fields(payload.data,{'source_name','source_url','price_ars','shipping_ars','same_sku','brand_new','original','in_stock','reputation_ok','payment_verified','shipping_verified','conditions_note'})
    source=str(d.get('source_name') or '').strip(); url=str(d.get('source_url') or '').strip()
    if not source or not url.startswith('https://') or len(url)>1200:raise HTTPException(400,'Nombre y enlace https:// obligatorios')
    price=float(d.get('price_ars') or 0); shipping=float(d.get('shipping_ars') or 0)
    if price<=0 or shipping<0:raise HTTPException(400,'Precio o envío inválido')
    with connect() as db:
        item=db.execute('SELECT order_id FROM items WHERE id=?',(iid,)).fetchone()
        if not item:raise HTTPException(404,'Producto inexistente')
        id=new_id()
        db.execute('INSERT INTO market(id,item_id,source_name,source_url,price_ars,shipping_ars,same_sku,brand_new,original,in_stock,reputation_ok,payment_verified,shipping_verified,conditions_note,observed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (id,iid,source,url,price,shipping,*[int(bool(d.get(k))) for k in ('same_sku','brand_new','original','in_stock','reputation_ok','payment_verified','shipping_verified')],str(d.get('conditions_note') or '')[:600],now()))
        invalidate_order(db,item['order_id'])
    return {'ok':True,'id':id}

@app.delete('/api/market/{mid}')
def delete_market(mid:str):
    with connect() as db:
        row=db.execute('SELECT items.order_id FROM market JOIN items ON items.id=market.item_id WHERE market.id=?',(mid,)).fetchone()
        if not row:raise HTTPException(404,'Evidencia inexistente')
        db.execute('DELETE FROM market WHERE id=?',(mid,))
        invalidate_order(db,row['order_id'])
    return {'ok':True}

@app.patch('/api/settings')
def set_settings(payload:Data):
    d=ensure_fields(payload.data,{'rates_usd_kg','internal_shipping_usd','internal_shipping_limit_kg','weight_protection_pct','min_protection_g','rounding_g','capture_market_gap_pct','fx_max_age_hours'})
    with connect() as db:
        obj=get_settings(db)
        if 'rates_usd_kg' in d:
            if set(d['rates_usd_kg']) != set(obj['rates_usd_kg']):raise HTTPException(400,'No cambiar categorías sin migración')
            if any(float(v)<=0 or float(v)>1000 for v in d['rates_usd_kg'].values()):raise HTTPException(400,'Tarifas inválidas')
        obj.update(d)
        for k in ('internal_shipping_limit_kg','rounding_g','fx_max_age_hours'):
            if float(obj[k])<=0:raise HTTPException(400,k+' debe ser positivo')
        for k in ('internal_shipping_usd','weight_protection_pct','min_protection_g','capture_market_gap_pct'):
            if not 0<=float(obj[k])<=10000:raise HTTPException(400,'Parámetro inválido '+k)
        if float(obj['capture_market_gap_pct'])>100:raise HTTPException(400,'Participación de mercado entre 0 y 100')
        db.execute('UPDATE settings SET content=? WHERE id=1',(json.dumps(obj),))
        db.execute("UPDATE orders SET status='draft',approved_at=NULL,approved_fx_ars=NULL,approved_sell_usd=NULL,approved_cost_usd=NULL,updated_at=? WHERE status='approved'",(now(),))
    return {'ok':True}

@app.post('/api/fx/refresh')
def refresh_fx():
    with connect() as db:
        result=refresh(db)
    if not result['ok']:raise HTTPException(502,'No se pudieron verificar ambas fuentes: '+', '.join(result['errors']))
    return result

@app.post('/api/fx/manual')
def manual_fx(payload:Data):
    d=ensure_fields(payload.data,{'blue','mep','blue_source','mep_source'})
    if not all(d.get(k) for k in ('blue','mep','blue_source','mep_source')):raise HTTPException(400,'Ingresá ambos valores y fuentes')
    if not all(str(d[k]).startswith('https://') for k in ('blue_source','mep_source')):raise HTTPException(400,'Fuentes https:// obligatorias')
    if float(d['blue'])<=0 or float(d['mep'])<=0:raise HTTPException(400,'Valores positivos obligatorios')
    with connect() as db:
        for label in ('blue','mep'):
            db.execute('INSERT OR REPLACE INTO fx_quotes(label,sell_ars,source_url,updated_at,fetched_at,kind) VALUES(?,?,?,?,?,?)',
                       (label,float(d[label]),d[label+'_source'],now(),now(),'manual'))
    return {'ok':True,'manual':True}

@app.post('/api/vision')
def vision(payload:PhotoRequest):
    try:return inspect_image(payload.data_url)
    except ValueError as e:raise HTTPException(400,str(e))
    except Exception:raise HTTPException(502,'No fue posible analizar la fotografía. Ingresá los datos manualmente.')

@app.post('/api/orders/{oid}/approve')
def approve(oid:str):
    with connect() as db:
        order=next((x for x in all_orders(db) if x['id']==oid),None)
        if not order:raise HTTPException(404,'Pedido inexistente')
        settings=get_settings(db); fx=get_fx(db,settings); calc=calculate_order(order,settings,fx)
        if not calc['approval_ready']:
            raise HTTPException(400,'Faltan costos completos, dólar válido, precio rentable y ofertas validadas de Mercado Libre y otra tienda por artículo.')
        if not (order.get('tax_reviewed') and order.get('import_cost_reviewed')):
            raise HTTPException(400,'Confirmá la revisión de impuestos estadounidenses y cargos de importación antes de aprobar.')
        if not all(bool(x.get('weight_verified')) and bool((x.get('weight_source') or '').strip()) for x in order['items']):
            raise HTTPException(400,'Confirmá el peso completo de cada artículo antes de aprobar.')
        for i in order['items']:
            valid=[e for e in i['market'] if classify_market(e)[1]]
            if not any(classify_market(e)[0] for e in valid) or not any(not classify_market(e)[0] for e in valid):
                raise HTTPException(400,'Cada producto requiere una oferta validada de Mercado Libre y otra tienda.')
        db.execute('UPDATE orders SET status=?,approved_at=?,approved_fx_ars=?,approved_sell_usd=?,approved_cost_usd=?,updated_at=? WHERE id=?',
                   ('approved',now(),fx['selected_rate'],calc['sell_price_usd'],calc['cost_usd'],now(),oid))
    return {'ok':True,'approved_at':now()}

@app.get('/api/orders/{oid}/whatsapp')
def whatsapp(oid:str):
    with connect() as db:
        order=next((x for x in all_orders(db) if x['id']==oid),None)
        if not order:raise HTTPException(404,'Pedido inexistente')
        if order['status']!='approved':raise HTTPException(403,'Aprobá la cotización antes de preparar el mensaje')
        fx=get_fx(db,get_settings(db)); calc=calculate_order(order,get_settings(db),fx)
        if not fx['valid']:
            raise HTTPException(409,'Dólar desactualizado: refrescá ambos tipos de cambio antes de compartir.')
        client=db.execute('SELECT * FROM customers WHERE id=?',(order['customer_id'],)).fetchone() if order['customer_id'] else None
        lines=['¡Hola'+(' '+client['full_name'].split()[0] if client else '')+'! 👋', '',
               'Te paso la cotización de Argentex Imports:','']
        lines += [f"• {i['name']}"+(' · '+i['variant'] if i['variant'] else '')+f" (x{i['qty']})" for i in order['items']]
        approved_usd=order.get('approved_sell_usd') or calc['sell_price_usd']
        lines += ['',f"*Total del pedido: USD {approved_usd:,.2f}*",
                  f"Equivalente orientativo: ARS {(approved_usd * fx['selected_rate']):,.2f}",
                  '', 'El monto en pesos se recalcula al momento del pago según la cotización de venta más alta entre dólar blue y MEP.',
                  '¿Querés que coordinemos tu pedido?']
        msg='\n'.join(x for x in lines if x is not None)
        return {'message':msg,'phone':client['phone'] if client else '', 'url':'https://wa.me/?text='+quote(msg)}

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='0.0.0.0' if os.getenv('PORT') else '127.0.0.1',port=int(os.getenv('PORT','8000')))
