# Argentex Imports — Cotizador Inteligente App 1.2

PWA móvil + FastAPI + SQLite + respaldo síncrono del archivo completo en Neon PostgreSQL para pruebas en Render Free (un solo proceso) + motor `Decimal` con tests. **No incluye precios ni cotizaciones de ejemplo en la base real.**

## Iniciar la app

Requiere **Python 3.10+**. Desde esta carpeta:

```bash
python -m pip install -r requirements.txt
python app.py
```

Abrí **http://127.0.0.1:8000** desde la computadora. En Windows también podés ejecutar `run-local.bat`; en macOS/Linux, `./run-local.sh`.

Para usar desde el celular en la **misma Wi-Fi**, ejecutá `run-mobile.bat` (Windows) o `./run-mobile.sh` (macOS/Linux). Te pedirá una contraseña (mín. 12 caracteres) y mostrará la URL IP local que debés abrir en el teléfono. Esta modalidad admite carga de fotografías, pero la **instalación PWA y acceso seguro en Internet requieren HTTPS**. No expongas directamente el puerto 8000 a Internet. Consultá `GUIA_PRUEBAS.md` para el recorrido completo.

## Arquitectura

- `app.py`: API HTTP REST, validación, sesiones protegidas por cookie HTTP-only, flujos comerciales.
- `core.py`: motor de peso, tarifas, impuestos y rentabilidad. **Sin dependencia de servicios externos**.
- `database.py`: esquemas y persistencia SQLite (`data/argentex.sqlite3`).
- `fx.py`: dólar blue y MEP venta mediante DolarAPI; valida fecha/frescura de ambas, identifica la mayor. Si falla, conserva registro previo pero lo señala como no vigente. Tiene carga manual.
- `vision.py`: identificación por foto con OpenAI, **opcional**. Requiere variable `OPENAI_API_KEY` en servidor, no navegador.
- `public/`: frontend responsive, manifest y service worker. El cache offline cubre **solo la interfaz**; guardar datos y consultar API exige conexión.
- `tests/`: pruebas de cálculo, persistencia, reglas de aprobación, WhatsApp y snapshots de precio USD.
- `serve_lan.py` y scripts `run-mobile.*`: pruebas desde celular en Wi-Fi, con contraseña.
- `render.yaml`: Blueprint de **Render**, plan Starter con disco persistente de 1 GB, HTTPS y secretos de servidor.
- `/api/backup`: respaldo completo y consistente de SQLite descargable en Configuración (requiere sesión).

## Metodología comercial

Las tarifas por categoría se siembran en SQLite según política de Argentex (45/50 USD por kg), y luego son editables desde Configuración. Cada artículo lleva peso físico por unidad **con packaging original y accesorios**; se suma un único embalaje exterior por pedido. La protección del pedido es `max(15% × peso_base, 150 g)`; el **peso final** (base + protección) se redondea hacia arriba a cada 100 g. Si hay varias categorías, distribuye la masa facturable consolidada proporcionalmente al peso de cada ítem para aplicar su respectivo USD/kg. No hay peso volumétrico ni cargo de depósito.

Envío interno de EE. UU.: USD 15 **una vez por pedido de hasta 5 kg**. Por encima de ese límite, se debe ingresar un valor manual; no se supone que también son USD 15. Impuestos: tres estados (no corresponde, incluidos, adicionar un porcentaje) para evitar contarlos dos veces. El costo de otros cargos de importación se ingresa manualmente solo si procede.

El precio sugerido solo se genera cuando están completos los costos, ambas cotizaciones de dólar vigentes y **ofertas de mercado exactas validadas**. Fórmula inicial configurable de sugerencia:

`precio_sugerido = costo_puesto_Argentina + (precio_competitivo_AR_en_USD − costo) × participación_de_oportunidad`.

El porcentaje inicial de participación es **45%**, editable. **Esto no equivale a una política fija de ganancia** ni impide anular el precio sugerido con un precio manual. Si el piso competitivo no supera el costo, se desaconseja la operación. La ganancia no incluye obligaciones no informadas. Aprobación exige revisión explícita de impuestos y cargos de importación, peso confirmado con fuente, y al menos una publicación compatible de Mercado Libre y otra tienda por cada artículo, cotizaciones blue/MEP válidas y rentabilidad positiva. Si se modifica una cotización aprobada, vuelve automáticamente a borrador.

**USD** es el importe comercial. La conversión a ARS es orientativa; el mensaje indica que se recalcula al momento de pago. El precio USD aprobado queda registrado e inalterable; se exige volver a disponer de dólar vigente antes de preparar el mensaje. El sistema no procesa cobros ni congela ARS.

## Investigación de producto: qué está automatizado

| Área | Estado en 1.1 |
|---|---|
| Captura y almacenamiento de foto | Funcional (foto reducida en navegador y guardada en SQLite) |
| Modelo/brand/SKU/precio visible por IA | Funcional **si** existe `OPENAI_API_KEY`, de lo contrario carga manual |
| Peso documentado por fabricante | Búsqueda asistida y registro manual de fuente/verificación; API automática pendiente |
| Precios y stock Mercado Libre + otras tiendas | Búsqueda externa y registro manual de ofertas verificadas; no scraping ni precios simulados |
| Tarifas, peso, protección, flete, impuesto | Automático y probado |
| Dólar blue/MEP venta | API real DolarAPI, con fallback manual y aviso de obsolescencia |
| Pedidos/clientes/historial | Persistencia real SQLite |
| Mensaje WhatsApp | Se habilita tras aprobación; sólo cifras comerciales |
| PWA | Instalable por HTTPS, shell cacheado; datos requieren conexión |

### Fuentes consultadas en el desarrollo

- DolarAPI: https://ar.dolarapi.com/docs/argentina/operations/get-dolar-blue y https://ar.dolarapi.com/docs/argentina/operations/get-dolar-bolsa
- API Mercado Libre: https://developers.mercadolibre.com.ar/es_ar/guia-para-carrito-de-compras/items-y-busquedas (requiere planificar OAuth, permisos y límites; no se simula ninguna respuesta)
- OpenAI Vision: https://developers.openai.com/api/docs/guides/images-vision

## Publicación de prueba en Render Free + Neon Free (sin Vercel)

**Estado:** código listo para despliegue; **no hay URL pública desplegada ni verificada**. Existe una base de datos Neon separada para pruebas, sin datos de clientes reales; para conectar el hosting debe configurarse su `DATABASE_URL` como secreto.

La versión 1.2 usa un único worker con SQLite como motor de consultas y guarda en PostgreSQL Neon una **copia binaria consistente completa** de SQLite después de cada escritura. Al iniciar recupera la última copia remota. Incluye imágenes porque están en SQLite. Esto es un adaptador de prueba, **no una migración a PostgreSQL ni un esquema apropiado para múltiples workers o grandes volúmenes**. Una falla de red durante el respaldo remoto devuelve error; el operador deberá revalidar el estado antes de repetir la operación. Para una versión definitiva, migrar a tablas PostgreSQL y guardar fotos en almacenamiento de objetos con permisos.

Para publicar se requiere un repositorio privado nuevo en GitHub con los archivos de esta carpeta, excluyendo la base SQLite local y las credenciales. Render permite crear un web service `python` en plan `free` desde ese repositorio, comando de build `pip install -r requirements.txt`, comando de inicio `uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1`. Variables **de servidor**: `DATABASE_URL` (conexión secreta de Neon), `DATA_DIR=/tmp/argentex-data`, `APP_ADMIN_PASSWORD` (contraseña robusta), `APP_SECRET` (valor aleatorio estable de al menos 32 bytes). Elegir una sola instancia, sin escalamiento horizontal. Opcionalmente `OPENAI_API_KEY` para identificación de productos por foto, con consumo de API de pago a cargo del usuario.

**Seguridad:** el servicio tiene URL pública HTTPS, pero todas las APIs comerciales quedan protegidas con una contraseña y cookie de sesión. El HTML se puede visualizar antes de iniciar sesión; **no es una intranet**. Evitar colocar claves o información sensible en el repositorio o en campos de URL. El plan gratis puede suspender el servicio por inactividad y ocasionar demoras al reactivarlo; consultar condiciones vigentes de los proveedores.

**Instalar en iPhone:** abrir la URL HTTPS en Safari → Compartir → Añadir a pantalla de inicio. El Service Worker cachea solamente el shell de la interfaz; para consultar y guardar cotizaciones se necesita conexión.

**Limitaciones:** reconocimiento IA depende de credencial; búsqueda automatizada Mercado Libre y tiendas sigue pendiente; no inventa fuentes ni precios; la sincronización Neon debe probarse en un despliegue real antes de almacenar información comercial definitiva.

## Pruebas

```bash
python -m pytest tests -q
```

## Próximas versiones

1. Integración Mercado Libre con OAuth y validación automatizada de SKU, stock, shipping y estado de la publicación.
2. Agentes de búsqueda para peso embalada de fabricante y tiendas argentinas con fuentes y confianza.
3. Futuro backend Postgres, restauración automatizada de respaldos y cuentas con roles; Render HTTPS y respaldo descargable ya preparados en 1.1.
4. Auditoría por cambio y snapshots de precio/dólar al momento del pago.

## Versión 1.4 — carga de hasta cuatro fotos en iPhone

Se corrigió el controlador de clics que interceptaba el evento nativo de los botones de cámara y envío de formularios en Safari. La captura ahora utiliza un `<input type="file" accept="image/*" capture="environment">` **real y accionado directamente** (superpuesto al botón, no oculto con `display:none` ni abierto con `.click()`). La opción **Elegir de Fotos** permite varias imágenes por selección.

- Inicio → **Fotografiar o cargar producto** abre directamente la ficha del producto, sin crear primero el pedido. Luego de guardar, se crea el borrador con el producto y las fotos en una sola transacción.
- Hasta **cuatro fotos por producto**: frente/producto, etiqueta o SKU, cartel de precio, presentación u otros detalles. El usuario puede cambiar la etiqueta de cada foto, quitarla, añadir otras y conservar las fotos ya guardadas al editar el artículo.
- Una captura nueva en Safari no reemplaza a las anteriores: las fotografías se acumulan en `pendingPhotos` y se envían al servidor al guardar. Al elegir varias desde Fotos, se respetan los lugares restantes.
- Cada imagen se redimensiona a un máximo de 1600 px y se comprime a JPEG antes de transferir; máximo 2,5 MB por foto y cuatro por producto. Se valida el tipo real de los archivos en el backend.
- SQLite agrega la tabla `item_photos`, manteniendo una migración desde la antigua columna `items.photo`. Los backups completos y el respaldo a Neon incluyen las nuevas fotografías.
- Cuando `OPENAI_API_KEY` está configurada, la integración opcional recibe las **cuatro imágenes juntas**, sus roles y las analiza para extraer únicamente nombre, marca, modelo, SKU, variante y **precio en USD legible**, señalando dudas. Sin clave API, se guardan las fotos y el usuario puede completar los datos manualmente; no se inventan valores.
- Las fotografías no verifican por sí solas pesos, autenticidad, impuestos o precios comparables en Argentina; las reglas comerciales previas no cambian.

**Prueba móvil:** Safari en un iPhone → abrir la URL HTTPS → tocar «Fotografiar o cargar producto» → «Sacar foto» → sacar 3 o 4 fotos una por vez (o seleccionar varias de Fotos) → comprobar las miniaturas → guardar. Si el dispositivo había instalado la app, refrescar Safari para obtener el nuevo paquete PWA.
