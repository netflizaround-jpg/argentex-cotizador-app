from core import calculate_order, upward_step
from database import DEFAULT_SETTINGS

CFG=DEFAULT_SETTINGS.copy()
FX={'valid':True,'selected_rate':1500,'selected_name':'mep'}

def item(name='Zapatillas',cat='calzado',weight=500,price=100,qty=1,offers=None):
    return {'name':name,'category':cat,'unit_weight_g':weight,'unit_price_usd':price,'qty':qty,'market':offers or []}

def order(items, **kwargs):
    return {'items':items,'outer_packaging_g':0,'tax_mode':'not_applicable','tax_rate':0,'import_extra_usd':0,**kwargs}

def test_proteccion_minima_y_redondeo():
    x=calculate_order(order([item(weight=500,price=100)]),CFG,FX)
    assert x['weight_base_g']==500
    assert x['buffer_raw_g']==150
    assert x['weight_billable_g']==700
    assert x['international_freight_usd']==31.5
    assert x['internal_shipping_usd']==15
    assert x['cost_usd']==146.5

def test_proteccion_porcentaje_no_duplicada():
    x=calculate_order(order([item(weight=1000),item(cat='accesorios',weight=1000,price=50)],outer_packaging_g=100),CFG,FX)
    assert x['weight_base_g']==2100
    assert x['buffer_raw_g']==315
    assert x['weight_billable_g']==2500
    # Tarifas mixtas, masa consolidada 2.5kg: mitad a 45, mitad a 50
    assert x['international_freight_usd']==118.75
    assert x['internal_shipping_usd']==15
    assert x['cost_usd']==283.75

def test_envio_una_vez_pedido():
    x=calculate_order(order([item(price=70),item(price=60)]),CFG,FX)
    assert x['internal_shipping_usd']==15
    assert x['weight_billable_g']==1200
    assert x['cost_usd']==199

def test_mayor_a_5kg_obliga_envio_editable():
    x=calculate_order(order([item(weight=5000)]),CFG,FX)
    assert x['weight_billable_g']==5800
    assert x['cost_usd'] is None
    assert any('más de 5 kg' in p for p in x['problems'])
    y=calculate_order(order([item(weight=5000)],us_shipping_override=27),CFG,FX)
    assert y['internal_shipping_usd']==27
    assert y['cost_usd']==388

def test_impuestos_solo_una_vez():
    basic=order([item(price=100)])
    included=calculate_order({**basic,'tax_mode':'included','tax_rate':7},CFG,FX)
    additional=calculate_order({**basic,'tax_mode':'apply','tax_rate':7},CFG,FX)
    assert included['tax_usd']==0
    assert additional['tax_usd']==7
    assert additional['cost_usd']==included['cost_usd']+7

def test_si_no_hay_fuentes_no_hay_recomendacion_ni_precio_inventado():
    c=calculate_order(order([item()]),CFG,FX)
    assert c['market_min_ars'] is None
    assert c['recommended_price_usd'] is None
    assert c['sell_price_usd'] is None
    assert not c['approval_ready']

def test_recomendacion_variable_y_override():
    e=[{'source_name':'Mercado Libre Argentina','source_url':'https://www.mercadolibre.com.ar/x','price_ars':300000,'shipping_ars':10000,'same_sku':1,'brand_new':1,'original':1,'in_stock':1,'reputation_ok':1,'payment_verified':1,'shipping_verified':1},
       {'source_name':'Tienda XYZ','source_url':'https://tienda.example/p','price_ars':320000,'shipping_ars':0,'same_sku':1,'brand_new':1,'original':1,'in_stock':1,'reputation_ok':1,'payment_verified':1,'shipping_verified':1}]
    a=order([item(offers=e)])
    c=calculate_order(a,CFG,FX)
    assert c['market_min_ars']==310000
    assert c['market_min_usd']==206.67
    assert c['recommended_price_usd']==173.58
    assert c['approval_ready']
    d=calculate_order({**a,'price_override_usd':180},CFG,FX)
    assert d['sell_price_usd']==180
    assert d['profit_usd']==33.5

def test_sin_dolar_no_se_declara_piso_en_usd():
    c=calculate_order(order([item()]),CFG,{'valid':False,'quotes':{}})
    assert c['market_min_usd'] is None
    assert c['sell_price_ars_approx'] is None

def test_redondeo_exacto():
    assert upward_step(600,100)==600
    assert upward_step(601,100)==700
