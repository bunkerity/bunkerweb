El complemento Zstandard comprime las respuestas HTTP utilizando el algoritmo Zstandard (zstd). Reduce el uso de ancho de banda para los clientes que anuncian `Accept-Encoding: zstd`.

### Cómo usar

1.  **Habilite la compresión:** Establezca `USE_ZSTD` en `yes` (desactivado por defecto).
2.  **Elija los tipos MIME y el tamaño mínimo:** Defina los tipos de contenido con `ZSTD_TYPES` y el tamaño mínimo de respuesta con `ZSTD_MIN_LENGTH`.
3.  **Ajuste el nivel de compresión:** Establezca `ZSTD_COMP_LEVEL` entre `1` (más rápido) y `19` (máxima compresión admitida). El valor por defecto es `3`.

Los clientes compatibles con zstd reciben `Content-Encoding: zstd` y `Vary: Accept-Encoding`. Los clientes sin compatibilidad con zstd, incluidos los que envían `zstd;q=0`, pueden recibir Brotli o gzip si esos complementos están habilitados; en caso contrario, reciben respuestas sin comprimir.

Cuando hay varios complementos de compresión habilitados, el servidor da preferencia a zstd, luego a Brotli y después a gzip. Cada codificación respeta su propio `q=0`; los pesos positivos no se comparan entre complementos de compresión.

### Ajustes de configuración

| Ajuste            | Valor por defecto                                                                                                                                                                                                                                                                                                                                                                                                                | Contexto  | Múltiple | Descripción                                                                                                                |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------- |
| `USE_ZSTD`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | no       | **Habilitar Zstandard:** Habilita la compresión de respuestas con Zstandard.                                               |
| `ZSTD_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | no       | **Tipos MIME:** Tipos MIME que se comprimirán, además de `text/html`, que siempre está incluido.                           |
| `ZSTD_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | no       | **Tamaño mínimo:** Tamaño mínimo de respuesta en bytes. También pueden comprimirse las respuestas de longitud desconocida. |
| `ZSTD_COMP_LEVEL` | `3`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | no       | **Nivel de compresión:** Nivel de compresión de `1` a `19`. Los niveles más altos consumen más CPU y memoria.              |

!!! tip "Nivel de compresión"
    Comience con el nivel `3`. Los niveles más altos aumentan el uso de CPU y memoria por solicitud; deje capacidad para las solicitudes concurrentes. Los niveles se limitan a `19` para respetar el límite de ventana zstd de 8 MB para HTTP.

!!! warning "Respuestas sensibles"
    La compresión puede exponer secretos a través de las diferencias en el tamaño de la respuesta cuando esta contiene tanto secretos como datos controlados por un atacante. Desactive la compresión en los servicios sensibles o aborde este riesgo en la aplicación. `text/html` siempre es apto para la compresión cuando zstd está habilitado, aunque se omita de `ZSTD_TYPES`.

!!! info "Compresión en el upstream"
    Las respuestas que el upstream ya ha comprimido no se vuelven a comprimir. El complemento inject necesita una respuesta del upstream sin comprimir para modificar el HTML; configure el upstream en consecuencia si utiliza ambas funciones.

### Configuración de ejemplo

Habilitar zstd con Brotli y gzip como alternativa:

```yaml
USE_ZSTD: "yes"
ZSTD_MIN_LENGTH: "1000"
ZSTD_COMP_LEVEL: "3"
USE_BROTLI: "yes"
USE_GZIP: "yes"
```
