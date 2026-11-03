"""Pruebas reales del contrato de cuatro fotos y del flujo foto-primero."""
import os
os.environ.setdefault('DATA_DIR','/tmp/argentex_app_tests')
import base64
import sqlite3
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from app import app
from photo_utils import decode_image, PhotoError

# Pequeño PNG válido para enviar imágenes reales en el protocolo JSON.
PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAOq+h0kAAAAASUVORK5CYII='


def payload(role='producto'):
    return {'data_url':PNG,'role':role}


def test_venta_rapida_con_cuatro_fotos_persistidas_y_roles():
    with TestClient(app) as c:
        images=[payload(x) for x in ['producto','sku','precio','detalle']]
        r=c.post('/api/quick-quote',json={'data':{
            'name':'Producto por identificar','category':'perfumes','unit_price_usd':0,
            'qty':1,'unit_weight_g':0,'photos':images
        }})
        assert r.status_code==200,r.text
        iid,oid=r.json()['id'],r.json()['order_id']
        state=c.get('/api/state').json()
        order=next(x for x in state['orders'] if x['id']==oid)
        assert order['status']=='draft'
        item=order['items'][0]
        assert item['id']==iid and item['has_photo']
        assert [x['role'] for x in item['photos']]==['producto','sku','precio','detalle']
        assert all('data' not in x for x in item['photos'])
        for photo in item['photos']:
            response=c.get('/api/items/'+iid+'/photos/'+photo['id'])
            assert response.status_code==200
            assert response.headers['content-type'].startswith('image/png')
            assert response.content==base64.b64decode(PNG.split(',')[1])
        assert c.post('/api/items/'+iid+'/photos',json={'images':[payload()]}).status_code==400
        assert c.post('/api/items/'+iid+'/photo',json={'data_url':PNG}).status_code==400
        assert c.get('/api/items/'+iid+'/photo').status_code==200  # retrocompatibilidad
        assert c.post('/api/orders/'+oid+'/approve').status_code==400
        photo=item['photos'][2]
        assert c.patch('/api/items/'+iid+'/photos/'+photo['id'],json={'data':{'role':'detalle'}}).status_code==200
        assert c.delete('/api/items/'+iid+'/photos/'+photo['id']).status_code==200
        assert c.get('/api/items/'+iid+'/photos/'+photo['id']).status_code==404
        assert c.post('/api/items/'+iid+'/photos',json={'images':[payload('precio')]}).status_code==200
        assert len(next(x for x in c.get('/api/state').json()['orders'] if x['id']==oid)['items'][0]['photos'])==4


def test_limites_y_integridad_no_dejan_pedidos_huerfanos():
    with TestClient(app) as c:
        before=len(c.get('/api/state').json()['orders'])
        too_many=[payload()]*5
        r=c.post('/api/quick-quote',json={'data':{'name':'Sin publicar','category':'ropa','photos':too_many}})
        assert r.status_code in (400,422)
        assert len(c.get('/api/state').json()['orders'])==before
        invalid=c.post('/api/quick-quote',json={'data':{
            'name':'No guardar','category':'calzado','photos':[{'data_url':'data:image/png;base64,abc','role':'sku'}]
        }})
        assert invalid.status_code==400
        assert len(c.get('/api/state').json()['orders'])==before
        o=c.post('/api/orders',json={'data':{'label':'Pedido multiimagen'}}).json()['id']
        a=c.post('/api/orders/'+o+'/items',json={'data':{'name':'Zapatillas','category':'calzado','unit_price_usd':95,'photos':[payload('sku'),payload('precio')]}})
        assert a.status_code==200,a.text
        iid=a.json()['id']
        more=c.patch('/api/items/'+iid,json={'data':{'brand':'Nike','photos':[payload('producto'),payload('detalle')]}})
        assert more.status_code==200,more.text
        assert len(next(x for x in c.get('/api/state').json()['orders'] if x['id']==o)['items'][0]['photos'])==4
        oversized=c.patch('/api/items/'+iid,json={'data':{'brand':'No debe cambiar','photos':[payload()]}})
        assert oversized.status_code==400
        assert next(x for x in c.get('/api/state').json()['orders'] if x['id']==o)['items'][0]['brand']=='Nike'


def test_vision_separa_integracion_de_fotografia():
    from unittest.mock import patch
    with TestClient(app) as c, patch.dict(os.environ,{'OPENAI_API_KEY':''}):
        out=c.post('/api/vision',json={'images':[payload('sku'),payload('precio')]})
        assert out.status_code==200,out.text
        assert out.json()['available'] is False
        assert 'IA' in out.json()['message']
        assert c.post('/api/vision',json={'images':[]}).status_code==400


def test_migracion_foto_unica_v13_a_album_v14():
    """Un item del esquema viejo con foto se migra sin borrarla ni duplicarla."""
    import database as m
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as tmp:
        dbfile=Path(tmp)/'argentex.sqlite3'
        original_path,original_dir=m.DB_PATH,m.DATA_DIR
        try:
            m.DB_PATH=dbfile;m.DATA_DIR=Path(tmp)
            m.init()
            blob=base64.b64decode(PNG.split(',')[1])
            with m.connect() as db:
                db.execute("INSERT INTO orders(id,label,created_at,updated_at) VALUES('oldorder','Viejo',?,?)",(m.now(),m.now()))
                db.execute("INSERT INTO items(id,order_id,name,category,photo,created_at) VALUES('olditem','oldorder','Viejo','ropa',?,?)",(blob,m.now()))
            m.init()
            with m.connect() as db:
                row=db.execute("SELECT data,role FROM item_photos WHERE item_id='olditem'").fetchone()
                assert row and row['data']==blob and row['role']=='producto'
                assert db.execute("SELECT photo FROM items WHERE id='olditem'").fetchone()['photo'] is None
            m.init()
            with m.connect() as db:
                assert db.execute("SELECT COUNT(*) FROM item_photos WHERE item_id='olditem'").fetchone()[0]==1
        finally:
            m.DB_PATH=original_path;m.DATA_DIR=original_dir
