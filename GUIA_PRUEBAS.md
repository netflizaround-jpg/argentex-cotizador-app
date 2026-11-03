# Argentex Cotizador — guía de pruebas con productos reales

## A. Empezar hoy (sin publicación)

1. Descomprimí el ZIP en una computadora con Python 3.10 o superior. En Windows, hacé doble clic en `run-mobile.bat`. En macOS/Linux, abrí Terminal y ejecutá `./run-mobile.sh`.
2. Elegí una contraseña de acceso de al menos 12 caracteres. La pantalla mostrará una dirección local del estilo `http://192.168.1.15:8000`. Abrila **en el teléfono conectado a la misma Wi-Fi**. Si no responde, permití Python en el firewall privado de la computadora. No abrir el puerto 8000 a Internet.
3. Ingresá con la contraseña. En la pantalla de inicio, tocá **Fotografiar o cargar producto**. La foto se guarda junto al artículo cuando tocás **Agregar al pedido**.
4. **Sin OPENAI_API_KEY**, el modelo/SKU/precio no se reconocen solos: completá esos campos manualmente. La integración de IA puede activarse después en el servidor.
5. Ingresá marca, modelo, SKU, presentación, categoría, precio de compra USD, cantidad y peso **real con caja, envase y accesorios**. Si el peso es aproximado, no marques *confirmo peso* y documentá la estimación.
6. Dentro del pedido, tocá **Datos y costos**: indicá el embalaje exterior una sola vez para todo el pedido, revisá impuestos aplicables y cualquier cargo adicional. Para probar consolidación, agregá un segundo artículo al mismo pedido.
7. Mirá el Resumen Express: deben mostrarse costo de compra, protección 15% (mín. 150 g), redondeo de 100 g, flete de 45/50 USD/kg, USD 15 de envío interno si el pedido no supera 5 kg y costo puesto en Argentina.
8. Tocá **Actualizar dólar**. Si falla la consulta, podés cargar blue/MEP de venta manualmente **solo con cifras y URLs que hayas verificado**. El sistema indica cuándo la carga fue manual.
9. Registrá las publicaciones **exactas**, verificadas por vos, de Mercado Libre Argentina y al menos otra tienda reconocida para cada producto. Marcá solamente los controles que hayas comprobado (SKU, originalidad, stock, reputación, promoción, envío, condiciones de pago). Si faltan fuentes reales, la app no inventa precio recomendado.
10. Para habilitar WhatsApp, confirmá peso y costos, fuentes competitivas de cada artículo y rentabilidad positiva; luego aprobá la cotización. WhatsApp sólo mostrará datos comerciales aprobados.
11. En **Configuración → Descargar copia de seguridad**, guardá un archivo SQLite en un lugar privado. Contiene también clientes, fotos y fuentes.

## B. Publicación de prueba en Render + Neon (sin Vercel)

**Todavía no hay sitio publicado.** La aplicación 1.2 está configurada para Render Free (web) y Neon Free (persistencia de un archivo SQLite completo). Una aplicación alojada requiere el repositorio Git privado y secretos del servidor; ninguna clave se entrega al navegador. No elegir varias instancias/worker, porque la sincronización se apoya en un archivo único.

1. Crear un repositorio privado nuevo y subir los archivos del paquete sin `.env` ni archivos dentro de `data/`.
2. Conectar ese repositorio a Render → New Web Service. Comando de build `pip install -r requirements.txt`. Inicio `uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1`.
3. Introducir en Render `DATABASE_URL` de Neon, `DATA_DIR=/tmp/argentex-data`, `APP_SECRET` aleatorio y `APP_ADMIN_PASSWORD` de al menos 12 caracteres.
4. Comprobar que `/api/health` devuelva `ok: true`, que pida sesión, que se pueda crear un cliente y pedido, y que sigan existiendo tras reiniciar el servicio.
5. Desde Safari en iPhone abrir HTTPS, compartir → Añadir a pantalla de inicio. Probar captura de foto, costos y exportación de backup.
6. No cargar información comercial sensible definitiva hasta validar el ciclo de reinicio y respaldo; la arquitectura de prueba se migrará a PostgreSQL directo posteriormente.

## C. Qué probar primero

- **Perfume**: validar si etiqueta y caja identifican tamaño exacto (p. ej. 50/100 ml no son equivalentes); no inventar UPC/SKU.
- **Zapatillas**: identificar talle y SKU; incluir el peso de la caja de calzado.
- **Pedido combinado**: perfume + zapatillas = tarifas 45 USD/kg para ambos, **USD 15 una sola vez**, embalaje exterior y protección una sola vez.
- **Pedido mixto**: perfume (45) + accesorio (50), misma protección única y distribución proporcional del peso.
- **Más de 5 kg protegidos**: no aceptar USD 15 automáticamente; registrar el costo interno real del pedido.
- **Sin precios argentinos verificados**: no generar una recomendación basada en cifras inventadas.

La app no tiene investigación automática de Mercado Libre ni peso en fabricantes. Las búsquedas y confirmaciones son manuales en esta fase. El modo local por HTTP puede permitir subir fotos, pero el acceso seguro y la instalación como PWA requieren el despliegue HTTPS.

### Cámara iPhone y carga multifoto — v1.4

1. Ingresá desde Safari a la URL HTTPS de Argentex.
2. Tocá **Fotografiar o cargar producto**. Se abre directamente una nueva ficha.
3. Tocá **Sacar foto** sobre el botón celeste: la opción se activa mediante el selector **nativo de archivos/cámara de Safari**. Aceptá la foto y volvé a tocar para obtener otra.
4. Como alternativa, tocá **Elegir de Fotos (hasta 4)** y seleccioná varias fotos en una sola operación.
5. Revisá que el contador marque **3 / 4** o **4 / 4**. Asigná roles «Producto», «Etiqueta / SKU», «Precio» y «Detalles».
6. Completá los datos disponibles; también podés guardar fotos sin precio o SKU confirmado. Guardá y abrí el pedido: las cuatro imágenes se recuperan desde el servidor.
7. Las integraciones de IA visual solo se habilitan cuando se configura una clave API en el servidor; las fotos por sí solas no producen una identificación automática.

No hace falta pedir permiso de `getUserMedia` para la captura nativa; el gesto del usuario abre el selector del propio navegador. Si Safari bloquea incluso este selector, probá abriendo la URL directamente en Safari (no en navegador integrado de otras aplicaciones) y comprobá las restricciones de cámara del iPhone.
