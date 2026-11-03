"""Vision opcional server-side. No atribuye pesos, SKUs o precios no visibles."""
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json, os, base64

def inspect_image(data_url):
    api_key=os.getenv('OPENAI_API_KEY')
    if not api_key: return {'available':False,'message':'IA no configurada. Completá los datos manualmente.'}
    if not data_url.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,')):
        raise ValueError('Formato de imagen inválido')
    if len(data_url)>12_000_000: raise ValueError('Foto demasiado grande. Máximo aprox. 8 MB.')
    instructions=("Sos analista comercial de importaciones. Identificá EXCLUSIVAMENTE la información observable de este producto. "
        "Respondé SOLO JSON válido con keys: name, brand, sku, variant, category, visible_price_usd, confidence, warnings. "
        "category debe ser una de ropa, perfumes, calzado, maquillaje, vitaminas, juguetes, accesorios, paletas_padel. "
        "No inventes SKU, cantidad, presentación, precio ni peso. Si no son visibles, devolvé string vacío para texto, null para precio. "
        "Las advertencias deben ser un array de cadenas. El precio solo si el cartel indica claramente USD. "
        "confidence entre 0 y 1. Si no identificás categoría usá accesorios y advertí la incertidumbre.")
    payload={"model":os.getenv('OPENAI_VISION_MODEL','gpt-4.1-mini'), "temperature":0,
             "response_format":{"type":"json_object"},
             "messages":[{"role":"user","content":[{"type":"text","text":instructions},
                         {"type":"image_url","image_url":{"url":data_url,"detail":"high"}}]}]}
    req=Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode(),
            headers={'Authorization':f'Bearer {api_key}','Content-Type':'application/json'},method='POST')
    try:
        with urlopen(req,timeout=38) as r: response=json.load(r)
        output=json.loads(response['choices'][0]['message']['content'])
        return {'available':True,'data':output,'message':'Revisá todos los datos: identificación por IA no verificada.'}
    except HTTPError as e:
        raise ValueError(f'Error del proveedor de IA ({e.code})')
