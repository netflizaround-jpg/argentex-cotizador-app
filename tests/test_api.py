import os
os.environ['DATA_DIR']='/tmp/argentex_app_tests'
from fastapi.testclient import TestClient
from app import app


def test_persistencia_orden_y_cliente():
    with TestClient(app) as cli:
        c=cli.post('/api/customers',json={'data':{'full_name':'Cliente Test','phone':'5493434000000'}})
        assert c.status_code==200,c.text
        cid=c.json()['id']
        o=cli.post('/api/orders',json={'data':{'customer_id':cid,'label':'Pedido test'}})
        assert o.status_code==200,o.text
        oid=o.json()['id']
        item=cli.post(f'/api/orders/{oid}/items',json={'data':{'name':'Perfume Test','category':'perfumes','unit_price_usd':100,'unit_weight_g':500,'qty':1}})
        assert item.status_code==200,item.text
        saved=cli.get('/api/state').json()
        record=next(x for x in saved['orders'] if x['id']==oid)
        assert record['calc']['weight_billable_g']==700
        assert record['calc']['cost_usd']==146.5
        assert record['items'][0]['name']=='Perfume Test'
        denied=cli.get(f'/api/orders/{oid}/whatsapp')
        assert denied.status_code==403
        assert cli.post(f'/api/orders/{oid}/approve').status_code==400
