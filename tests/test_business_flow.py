from fastapi.testclient import TestClient
from app import app
from core import classify_market


def test_no_confundir_tienda_por_nombre_con_mercadolibre():
    fake={'source_name':'Mercado Libre Argentina','source_url':'https://example.com/product','same_sku':1,'brand_new':1,'original':1,'in_stock':1,'reputation_ok':1,'payment_verified':1,'shipping_verified':1}
    assert classify_market(fake)[0] is False
    real_host={**fake,'source_url':'https://articulo.mercadolibre.com.ar/MLA-TEST'}
    assert classify_market(real_host)[0] is True


def test_aprobacion_whatsapp_y_precio_usd_congelado():
    with TestClient(app) as c:
        order=c.post('/api/orders',json={'data':{'label':'Test QA snapshot'}}).json()['id']
        item=c.post(f'/api/orders/{order}/items',json={'data':{'name':'Producto de prueba','category':'perfumes','unit_price_usd':100,'unit_weight_g':500,'qty':1,'weight_verified':True,'weight_source':'Pesaje propio'}}).json()['id']
        c.post('/api/fx/manual',json={'data':{'blue':1400,'mep':1500,'blue_source':'https://dolarapi.com/v1/dolares/blue','mep_source':'https://dolarapi.com/v1/dolares/bolsa'}})
        for name,url,ars in [('Mercado Libre Argentina','https://articulo.mercadolibre.com.ar/MLA-QATEST',450000),('Otra tienda','https://example.com/test-articulo',460000)]:
            r=c.post(f'/api/items/{item}/market',json={'data':{'source_name':name,'source_url':url,'price_ars':ars,'shipping_ars':0,'same_sku':True,'brand_new':True,'original':True,'in_stock':True,'reputation_ok':True,'payment_verified':True,'shipping_verified':True}})
            assert r.status_code==200,r.text
        assert c.post(f'/api/orders/{order}/approve').status_code==400 # faltan revisiones de impuestos
        patch=c.patch(f'/api/orders/{order}',json={'data':{'tax_reviewed':True,'import_cost_reviewed':True}})
        assert patch.status_code==200,patch.text
        approval=c.post(f'/api/orders/{order}/approve')
        assert approval.status_code==200,approval.text
        a=next(x for x in c.get('/api/state').json()['orders'] if x['id']==order)
        assert a['status']=='approved'
        sell=a['approved_sell_usd'];assert sell>146.5
        msg=c.get(f'/api/orders/{order}/whatsapp')
        assert msg.status_code==200
        assert 'Costo' not in msg.json()['message']
        assert 'ganancia' not in msg.json()['message']
        c.post('/api/fx/manual',json={'data':{'blue':1650,'mep':1600,'blue_source':'https://dolarapi.com/v1/dolares/blue','mep_source':'https://dolarapi.com/v1/dolares/bolsa'}})
        b=next(x for x in c.get('/api/state').json()['orders'] if x['id']==order)
        assert b['calc']['sell_price_usd']==sell # dólar no cambia precio USD aprobado
        assert b['calc']['sell_price_ars_approx']==round(sell*1650,2)
        assert c.get(f'/api/orders/{order}/whatsapp').status_code==200
        c.patch(f'/api/orders/{order}',json={'data':{'outer_packaging_g':200}})
        assert c.get(f'/api/orders/{order}/whatsapp').status_code==403
