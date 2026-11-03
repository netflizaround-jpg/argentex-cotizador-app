"""Validación de hasta cuatro fotografías por artículo; nunca infiere datos comerciales."""
import base64
import binascii
import re

MAX_ITEM_PHOTOS = 4
MAX_PHOTO_BYTES = 2_500_000
ROLES = {'producto', 'sku', 'precio', 'detalle'}
MIMES = {
    'image/jpeg': (b'\xff\xd8\xff',),
    'image/png': (b'\x89PNG\r\n\x1a\n',),
    'image/webp': (b'RIFF',),
}

class PhotoError(ValueError):
    pass

def decode_image(image):
    if not isinstance(image, dict):
        raise PhotoError('Cada fotografía necesita datos válidos.')
    data_url = image.get('data_url')
    role = str(image.get('role') or 'detalle').strip().lower()
    if role not in ROLES:
        raise PhotoError('Tipo de foto inválido.')
    if not isinstance(data_url, str) or len(data_url) > 3_600_000:
        raise PhotoError('Foto demasiado grande o inválida. Máximo 2,5 MB por foto.')
    match = re.fullmatch(r'data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/]+={0,2})', data_url)
    if not match:
        raise PhotoError('La foto debe ser JPEG, PNG o WebP. Convertí HEIC en el iPhone antes de enviarla.')
    mime, raw_b64 = match.groups()
    try:
        blob = base64.b64decode(raw_b64, validate=True)
    except (ValueError, binascii.Error):
        raise PhotoError('Foto dañada o codificación inválida.')
    if not blob or len(blob) > MAX_PHOTO_BYTES:
        raise PhotoError('Cada foto debe pesar menos de 2,5 MB luego de comprimirla.')
    if not any(blob.startswith(signature) for signature in MIMES[mime]):
        raise PhotoError('La imagen no corresponde al formato declarado.')
    if mime == 'image/webp' and blob[8:12] != b'WEBP':
        raise PhotoError('Archivo WebP inválido.')
    return blob, mime, role

def validated_images(images, remaining=MAX_ITEM_PHOTOS):
    if not isinstance(images, list) or not (0 <= len(images) <= remaining):
        raise PhotoError('Máximo 4 fotos por producto (incluyendo las ya guardadas).')
    return [decode_image(image) for image in images]
