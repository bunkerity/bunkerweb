El complemento Brotli permite la compresión eficiente de las respuestas HTTP utilizando el algoritmo Brotli. Esta función ayuda a reducir el uso de ancho de banda y a mejorar los tiempos de carga de la página al comprimir el contenido web antes de que se envíe al navegador del cliente.

En comparación con otros métodos de compresión como gzip, Brotli suele alcanzar mayores tasas de compresión, lo que se traduce en archivos de menor tamaño y una entrega de contenido más rápida.

**Cómo funciona:**

1.  Cuando un cliente solicita contenido de su sitio web, BunkerWeb comprueba si el cliente admite la compresión Brotli.
2.  Si es compatible, BunkerWeb comprime la respuesta utilizando el algoritmo Brotli en el nivel de compresión que haya configurado.
3.  El contenido comprimido se envía al cliente con las cabeceras adecuadas que indican la compresión Brotli.
4.  El navegador del cliente descomprime el contenido antes de mostrarlo al usuario.
5.  Tanto el uso de ancho de banda como los tiempos de carga de la página se reducen, mejorando la experiencia general del usuario.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de compresión Brotli:

1.  **Habilite la función:** La función Brotli está desactivada por defecto. Habilítela estableciendo el ajuste `USE_BROTLI` en `yes`.
2.  **Configure los tipos MIME:** Especifique qué tipos de contenido deben comprimirse utilizando el ajuste `BROTLI_TYPES`.
3.  **Establezca el tamaño mínimo:** Defina el tamaño mínimo de respuesta para la compresión con `BROTLI_MIN_LENGTH` para evitar comprimir archivos muy pequeños.
4.  **Elija el nivel de compresión:** Seleccione su equilibrio preferido entre velocidad y tasa de compresión con `BROTLI_COMP_LEVEL`.
5.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, la compresión se realiza automáticamente para las respuestas que cumplan los requisitos.

### Ajustes de configuración

| Ajuste              | Valor por defecto                                                                                                                                                                                                                                                                                                                                                                                                                | Contexto  | Múltiple | Descripción                                                                                                                          |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_BROTLI`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | no       | **Habilitar Brotli:** Establezca en `yes` para habilitar la compresión Brotli.                                                       |
| `BROTLI_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | no       | **Tipos MIME:** Lista de tipos de contenido que se comprimirán con Brotli.                                                           |
| `BROTLI_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | no       | **Tamaño mínimo:** El tamaño mínimo de respuesta (en bytes) para que se aplique la compresión Brotli.                                |
| `BROTLI_COMP_LEVEL` | `6`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | no       | **Nivel de compresión:** Nivel de compresión de 0 (sin compresión) a 11 (compresión máxima). Los valores más altos consumen más CPU. |

!!! tip "Optimización del nivel de compresión"
El nivel de compresión por defecto (6) ofrece un buen equilibrio entre la tasa de compresión y el uso de la CPU. Para contenido estático o cuando los recursos de la CPU del servidor son abundantes, considere aumentarlo a 9-11 para una compresión máxima. Para contenido dinámico o cuando los recursos de la CPU son limitados, es posible que desee utilizar 4-5 para una compresión más rápida con una reducción de tamaño razonable.

!!! info "Soporte de navegadores"
Brotli es compatible con todos los navegadores modernos, incluidos Chrome, Firefox, Edge, Safari y Opera. Los navegadores más antiguos recibirán automáticamente el contenido sin comprimir, lo que garantiza la compatibilidad.

### Configuraciones de ejemplo

=== "Configuración básica"

    Una configuración estándar que habilita Brotli con los ajustes por defecto:

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json application/xml application/xhtml+xml text/css text/html text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "6"
    ```

=== "Compresión máxima"

    Configuración optimizada para un ahorro máximo de compresión:

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "500"
    BROTLI_COMP_LEVEL: "11"
    ```

=== "Rendimiento equilibrado"

    Configuración que equilibra la tasa de compresión con el uso de la CPU:

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "4"
    ```
