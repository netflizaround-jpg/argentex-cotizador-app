# PuntoLiga · Liga La Farola | Presentación interactiva

**Demo aislada**, sin cuentas reales, datos reales ni conexión al servicio de producción de puntoliga.com. El banner superior identifica inequívocamente que los nombres y resultados son ficticios.

## Incluye
- Ascenso a categoría superior de la misma rama, conservando los partidos históricos de la categoría de origen y la identidad de la pareja.
- Registro de revancha repetida con fecha, hora, cancha, marcador e identificador independiente, además de carga posterior del resultado.
- Historial y rendimiento por categoría, con parejas ascendidas identificadas como registro histórico.
- Restablecimiento de la demo y exportación JSON para una presentación.

## Publicación
Sitio estático. En Render elegir `Static Site`, la rama de esta demostración y `Publish Directory` = `puntoliga-preview`. No requiere variables de entorno ni llaves privadas; tampoco almacena cambios de la liga real.

## Limitaciones
Esto **no es una integración en el sistema vigente**. No reutilizarlo como backend de producción ni confundirlo con el panel autenticado del organizador. Para activar las funciones sobre datos reales sigue siendo necesaria la integración y pruebas autenticadas del backend actual y la migración de almacenamiento.