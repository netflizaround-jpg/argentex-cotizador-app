"""Reconocimiento multimodal opcional. Nunca crea SKU, pesos ni precios sin evidencia."""
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import os
from photo_utils import validated_images

ROLE_NAMES = {'producto':'frente y producto','sku':'etiqueta y SKU','precio':'precio en tienda','detalle':'detalles y presentación'}


def inspect_images(images):
    """Analizar entre 1 y 4 imágenes asociadas AL MISMO producto."""
    if not images or len(images)>4:
        raise ValueError('Se requieren entre 1 y 4 fotografías del mismo artículo.')
    validated_images(images)
    api_key=os.getenv('OPENAI_API_KEY')
    if not api_key:
        return {'available':False,'message':'La identificación por IA requiere OPENAI_API_KEY en Render. Las fotos se guardan y los datos se cargan manualmente.'}
    instructions=(
        'Actuás como analista de compras internacionales para Argentex Imports. '
        'Se te proporcionan hasta cuatro imágenes DEL MISMO artículo: frente, etiqueta/SKU, precio, y detalles. '
        'Relacioná las cuatro fotos y distinguí el precio en la tienda en EE. UU. de otros precios. '
        'Extraé solo información que sea CLARAMENTE VISIBLE: modelo, nombre, marca, SKU exacto, variante '
        '(volumen ml, talla, concentración, color o presentación), categoría y precio USD visible. '
        'Respondé ÚNICAMENTE JSON con claves: '
        'name (string), brand (string), sku (string), variant (string), category (string), '
        'visible_price_usd (number o null), confidence (0 a 1), warnings (array string), '
        'evidence (objeto con name,brand,sku,variant,visible_price_usd: índice 1-4 de foto o null). '
        'category solo puede ser ropa, perfumes, calzado, maquillaje, vitaminas, juguetes, accesorios, paletas_padel. '
        'Si el SKU, precio, modelo, tamaño o marca es dudoso, poné texto vacío o null y añadí advertencia. '
        'Si se ven SKU distintos, advertí posible mezcla de productos y NO combines datos. '
        'Para precio solo devolvé visible_price_usd si en la foto se identifica USD inequívocamente; '
        'no inventes el precio a partir de tiendas online, ni conviertas moneda, ni estimes pesos. '
        'No des por comprobada la autenticidad, precio de Mercado Libre, estado de stock, peso o impuestos. '
        'No uses la incertidumbre para completar faltantes. El resultado es asistido y requiere revisión humana.'
    )
    content=[{'type':'text','text':instructions}]
    for idx,photo in enumerate(images,1):
        role=photo.get('role','detalle')
        content.extend([
            {'type':'text','text':f'Foto {idx} ({ROLE_NAMES.get(role,"detalle")}):'},
            {'type':'image_url','image_url':{'url':photo['data_url'],'detail':'high'}}
        ])
    payload={
        'model':os.getenv('OPENAI_VISION_MODEL','gpt-4.1-mini'),
        'response_format':{'type':'json_object'},
        'messages':[{'role':'user','content':content}],
        'max_completion_tokens':850
    }
    req=Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode(),
                headers={'Authorization':f'Bearer {api_key}', 'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(req,timeout=55) as response:
            data=json.load(response)
        output=json.loads(data['choices'][0]['message']['content'])
        return {'available':True,'data':output,'message':'Análisis de las fotos completado. Confirmá modelo, SKU, presentación y precio antes de cotizar.'}
    except HTTPError as e:
        raise ValueError(f'No fue posible utilizar la IA (HTTP {e.code}); comprobá la clave y los límites de uso.')
    except (URLError,TimeoutError):
        raise RuntimeError('No se pudo conectar con el proveedor de IA.')


def inspect_image(data_url):
    """Compatibilidad con llamadas anteriores."""
    return inspect_images([{'data_url':data_url,'role':'producto'}])
