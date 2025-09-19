El complemento GZIP mejora el rendimiento del sitio web al comprimir las respuestas HTTP utilizando el algoritmo GZIP. Esta función reduce el uso de ancho de banda y mejora los tiempos de carga de la página al comprimir el contenido web antes de que se envíe al navegador del cliente, lo que resulta en una entrega más rápida y una mejor experiencia de usuario.

### Cómo funciona

1.  Cuando un cliente solicita contenido de su sitio web, BunkerWeb comprueba si el cliente admite la compresión GZIP.
2.  Si es compatible, BunkerWeb comprime la respuesta utilizando el algoritmo GZIP en el nivel de compresión que haya configurado.
3.  El contenido comprimido se envía al cliente con las cabeceras adecuadas que indican la compresión GZIP.
4.  El navegador del cliente descomprime el contenido antes de mostrarlo.
5.  Tanto el uso de ancho de banda como los tiempos de carga de la página se reducen, mejorando el rendimiento general del sitio y la experiencia del usuario.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de compresión GZIP:

1.  **Habilite la función:** La función GZIP está desactivada por defecto. Habilítela estableciendo el ajuste `USE_GZIP` en `yes`.
2.  **Configure los tipos MIME:** Especifique qué tipos de contenido deben comprimirse utilizando el ajuste `GZIP_TYPES`.
3.  **Establezca el tamaño mínimo:** Defina el tamaño mínimo de respuesta requerido para la compresión con el ajuste `GZIP_MIN_LENGTH` para evitar comprimir archivos pequeños.
4.  **Elija un nivel de compresión:** Seleccione su equilibrio preferido entre velocidad y tasa de compresión utilizando el ajuste `GZIP_COMP_LEVEL`.
5.  **Configure las solicitudes proxy:** Especifique qué solicitudes proxy deben comprimirse utilizando el ajuste `GZIP_PROXIED`.

### Ajustes de Configuración

| Ajuste            | Valor por defecto                                                                                                                                                                                                                                                                                                                                                                                                                | Contexto  | Múltiple | Descripción                                                                                                                            |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GZIP`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | no       | **Habilitar GZIP:** Establezca en `yes` para habilitar la compresión GZIP.                                                             |
| `GZIP_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | no       | **Tipos MIME:** Lista de tipos de contenido que se comprimirán con GZIP.                                                               |
| `GZIP_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | no       | **Tamaño Mínimo:** El tamaño mínimo de respuesta (en bytes) para que se aplique la compresión GZIP.                                    |
| `GZIP_COMP_LEVEL` | `5`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | no       | **Nivel de Compresión:** Nivel de compresión de 1 (compresión mínima) a 9 (compresión máxima). Los valores más altos consumen más CPU. |
| `GZIP_PROXIED`    | `no-cache no-store private expired auth`                                                                                                                                                                                                                                                                                                                                                                                         | multisite | no       | **Solicitudes Proxy:** Especifica qué solicitudes proxy deben comprimirse según las cabeceras de respuesta.                            |

!!! tip "Optimizando el Nivel de Compresión"
El nivel de compresión por defecto (5) ofrece un buen equilibrio entre la tasa de compresión y el uso de la CPU. Para contenido estático o cuando los recursos de la CPU del servidor son abundantes, considere aumentarlo a 7-9 para una compresión máxima. Para contenido dinámico o cuando los recursos de la CPU son limitados, es posible que desee utilizar 1-3 para una compresión más rápida con una reducción de tamaño razonable.

!!! info "Soporte de Navegadores"
GZIP es compatible con todos los navegadores modernos y ha sido el método de compresión estándar para las respuestas HTTP durante muchos años, lo que garantiza una excelente compatibilidad en todos los dispositivos y navegadores.

!!! warning "Compresión vs. Uso de CPU"
Aunque la compresión GZIP reduce el ancho de banda y mejora los tiempos de carga, los niveles de compresión más altos consumen más recursos de la CPU. Para sitios de alto tráfico, encuentre el equilibrio adecuado entre la eficiencia de la compresión y el rendimiento del servidor.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración estándar que habilita GZIP con los ajustes por defecto:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json application/xml text/css text/html text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "5"
    ```

=== "Compresión Máxima"

    Configuración optimizada para un ahorro máximo de compresión:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "500"
    GZIP_COMP_LEVEL: "9"
    GZIP_PROXIED: "any"
    ```

=== "Rendimiento Equilibrado"

    Configuración que equilibra la tasa de compresión con el uso de la CPU:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "3"
    GZIP_PROXIED: "no-cache no-store private expired"
    ```

=== "Enfoque en Contenido Proxy"

    Configuración que se centra en manejar adecuadamente la compresión para el contenido proxy:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "4"
    GZIP_PROXIED: "any"
    ```
