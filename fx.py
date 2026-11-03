"""Cotizaciones blue/MEP con trazabilidad y control de frescura."""
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from decimal import Decimal
import json
from database import now

API='https://dolarapi.com/v1/dolares/'

def refresh(db):
    result={}; errors=[]
    # No reemplazar la cotización anterior hasta validar AMBAS respuestas.
    for label, slug in [('blue','blue'),('mep','bolsa')]:
        url=API+slug
        try:
            req=Request(url, headers={'User-Agent':'Argentex-Cotizador/1.0', 'Accept':'application/json'})
            with urlopen(req,timeout=9) as response:
                payload=json.loads(response.read(15000).decode())
            val=float(payload['venta']); stamp=payload['fechaActualizacion']
            dt=datetime.fromisoformat(stamp.replace('Z','+00:00'))
            if val<=0 or dt.tzinfo is None: raise ValueError('Precio o fecha inválidos')
            result[label]={'label':label,'sell_ars':val,'updated_at':stamp,'source_url':url,'kind':'api'}
        except Exception as e:
            errors.append(f'{label}: {type(e).__name__}')
    if errors:
        return {'ok':False,'errors':errors}
    for name,obj in result.items():
        db.execute('INSERT OR REPLACE INTO fx_quotes(label,sell_ars,source_url,updated_at,fetched_at,kind) VALUES(?,?,?,?,?,?)',
                   (name,obj['sell_ars'],obj['source_url'],obj['updated_at'],now(),obj['kind']))
    return {'ok':True}

def get_fx(db, settings):
    quotes={x['label']:dict(x) for x in db.execute('SELECT * FROM fx_quotes')}
    valid=len(quotes)==2 and all(k in quotes for k in ('blue','mep'))
    current=datetime.now(timezone.utc)
    age={}
    if valid:
        for key in ('blue','mep'):
            try:
                date=datetime.fromisoformat(quotes[key]['updated_at'].replace('Z','+00:00'))
                h=(current-date).total_seconds()/3600
                age[key]=round(h,1)
                if h < -1 or h>float(settings['fx_max_age_hours']): valid=False
            except Exception: valid=False
    if valid:
        winner=max(('blue','mep'),key=lambda x:quotes[x]['sell_ars'])
        chosen=quotes[winner]
    else:
        winner=None; chosen=None
    return {'valid':valid,'selected_rate':chosen['sell_ars'] if chosen else None,'selected_name':winner,
            'selected_source':chosen['source_url'] if chosen else None,
            'selected_updated_at':chosen['updated_at'] if chosen else None,
            'manual':bool(chosen and chosen['kind']=='manual'), 'quotes':quotes, 'age_hours':age,
            'warning':None if valid else 'Sin ambas cotizaciones recientes: no se afirma el mayor valor.'}
