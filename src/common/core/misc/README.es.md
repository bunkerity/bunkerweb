El complemento Varios proporciona **ajustes básicos esenciales** que ayudan a mantener la seguridad y la funcionalidad de su sitio web. Este componente principal ofrece controles integrales para:

- **Comportamiento del servidor** - Configure cómo responde su servidor a diversas solicitudes
- **Ajustes HTTP** - Gestione métodos, tamaños de solicitud y opciones de protocolo
- **Gestión de archivos** - Controle la entrega de archivos estáticos y optimice la entrega
- **Soporte de protocolos** - Habilite protocolos HTTP modernos para un mejor rendimiento
- **Configuraciones del sistema** - Amplíe la funcionalidad y mejore la seguridad

Ya sea que necesite restringir los métodos HTTP, gestionar los tamaños de las solicitudes, optimizar el almacenamiento en caché de archivos o controlar cómo responde su servidor a diversas solicitudes, este complemento le brinda las herramientas para **afinar el comportamiento de su servicio web** mientras optimiza tanto el rendimiento como la seguridad.

### Características Clave

| Categoría de Característica                | Descripción                                                                                                                               |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **Control de Métodos HTTP**                | Defina qué métodos HTTP son aceptables para su aplicación                                                                                 |
| **Protección del Servidor Predeterminado** | Prevenga el acceso no autorizado a través de discrepancias de nombre de host y exija SNI para conexiones seguras                          |
| **Gestión del Tamaño de la Solicitud**     | Establezca límites para los cuerpos de las solicitudes de los clientes y las cargas de archivos                                           |
| **Entrega de Archivos Estáticos**          | Configure y optimice la entrega de contenido estático desde carpetas raíz personalizadas                                                  |
| **Almacenamiento en Caché de Archivos**    | Mejore el rendimiento a través de mecanismos avanzados de almacenamiento en caché de descriptores de archivos con ajustes personalizables |
| **Soporte de Protocolos**                  | Configure opciones de protocolos HTTP modernos (HTTP2/HTTP3) y ajustes de puerto Alt-Svc                                                  |
| **Informes Anónimos**                      | Informes de estadísticas de uso opcionales para ayudar a mejorar BunkerWeb                                                                |
| **Soporte de Complementos Externos**       | Amplíe la funcionalidad integrando complementos externos a través de URL                                                                  |
| **Control de Estado HTTP**                 | Configure cómo responde su servidor al denegar solicitudes (incluida la terminación de la conexión)                                       |

### Guía de Configuración

=== "Seguridad del Servidor Predeterminado"

    **Controles del Servidor Predeterminado**

    En HTTP, el encabezado `Host` especifica el servidor de destino, pero puede estar ausente o ser desconocido, a menudo debido a que los bots buscan vulnerabilidades.

    Para bloquear tales solicitudes:

    -   Establezca `DISABLE_DEFAULT_SERVER` en `yes` para denegar silenciosamente tales solicitudes utilizando el [código de estado `444` de NGINX](https://http.dev/444).
    -   Para una seguridad más estricta, habilite `DISABLE_DEFAULT_SERVER_STRICT_SNI` para rechazar las conexiones SSL/TLS sin un SNI válido.

    !!! success "Beneficios de Seguridad"
        -   Bloquea la manipulación del encabezado Host y el escaneo de hosts virtuales
        -   Mitiga los riesgos de contrabando de solicitudes HTTP
        -   Elimina el servidor predeterminado como un vector de ataque

| Ajuste                              | Valor por defecto | Contexto | Múltiple | Descripción                                                                                                                                           |
| ----------------------------------- | ----------------- | -------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DISABLE_DEFAULT_SERVER`            | `no`              | global   | no       | **Servidor Predeterminado:** Establezca en `yes` para deshabilitar el servidor predeterminado cuando ningún nombre de host coincida con la solicitud. |
| `DISABLE_DEFAULT_SERVER_STRICT_SNI` | `no`              | global   | no       | **SNI Estricto:** Cuando se establece en `yes`, requiere SNI para las conexiones HTTPS y rechaza las conexiones sin un SNI válido.                    |

    !!! warning "Aplicación de SNI"
        Habilitar la validación estricta de SNI proporciona una seguridad más fuerte, pero puede causar problemas si BunkerWeb está detrás de un proxy inverso que reenvía las solicitudes HTTPS sin preservar la información de SNI. Pruebe a fondo antes de habilitarlo en entornos de producción.

=== "Estado HTTP de Denegación"

    **Control de Estado HTTP**

    El primer paso para manejar el acceso denegado del cliente es definir la acción apropiada. Esto se puede configurar usando el ajuste `DENY_HTTP_STATUS`. Cuando BunkerWeb deniega una solicitud, puede controlar su respuesta usando este ajuste. Por defecto, devuelve un estado `403 Prohibido`, mostrando una página web o contenido personalizado al cliente.

    Alternativamente, establecerlo en `444` cierra la conexión inmediatamente sin enviar ninguna respuesta. Este [código de estado no estándar](https://http.dev/444), específico de NGINX, es útil para descartar silenciosamente las solicitudes no deseadas.

| Ajuste             | Valor por defecto | Contexto | Múltiple | Descripción                                                                                                                                 |
| ------------------ | ----------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `DENY_HTTP_STATUS` | `403`             | global   | no       | **Estado HTTP de Denegación:** Código de estado HTTP a enviar cuando se deniega la solicitud (403 o 444). El código 444 cierra la conexión. |

    !!! warning "Consideraciones del Código de Estado 444"
        Dado que los clientes no reciben retroalimentación, la solución de problemas puede ser más desafiante. Se recomienda establecer `444` solo si ha abordado a fondo los falsos positivos, tiene experiencia con BunkerWeb y requiere un mayor nivel de seguridad.

    !!! info "Modo stream"
        En **modo stream**, este ajuste siempre se aplica como `444`, lo que significa que la conexión se cerrará, independientemente del valor configurado.

=== "Métodos HTTP"

    **Control de Métodos HTTP**

    Restringir los métodos HTTP solo a los requeridos por su aplicación es una medida de seguridad fundamental que se adhiere al principio de privilegio mínimo. Al definir explícitamente los métodos HTTP aceptables, puede minimizar el riesgo de explotación a través de métodos no utilizados o peligrosos.

    Esta característica se configura utilizando el ajuste `ALLOWED_METHODS`, donde los métodos se enumeran y se separan por un `|` (predeterminado: `GET|POST|HEAD`). Si un cliente intenta utilizar un método no listado, el servidor responderá con un estado **405 - Método No Permitido**.

    Para la mayoría de los sitios web, el predeterminado `GET|POST|HEAD` es suficiente. Si su aplicación utiliza API RESTful, es posible que deba incluir métodos como `PUT` y `DELETE`.

    !!! success "Beneficios de Seguridad"
        -   Previene la explotación de métodos HTTP no utilizados o innecesarios
        -   Reduce la superficie de ataque al deshabilitar métodos potencialmente dañinos
        -   Bloquea las técnicas de enumeración de métodos HTTP utilizadas por los atacantes

| Ajuste            | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                     |
| ----------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------- |
| `ALLOWED_METHODS` | `GET\|POST\|HEAD` | multisite | no       | **Métodos HTTP:** Lista de métodos HTTP permitidos, separados por caracteres de barra vertical. |

    !!! abstract "CORS y Solicitudes de Pre-vuelo"
        Si su aplicación admite [Intercambio de Recursos de Origen Cruzado (CORS)](#cors), debe incluir el método `OPTIONS` en el ajuste `ALLOWED_METHODS` para manejar las solicitudes de pre-vuelo. Esto garantiza la funcionalidad adecuada para los navegadores que realizan solicitudes de origen cruzado.

    !!! danger "Consideraciones de Seguridad"
        -   **Evite habilitar `TRACE` o `CONNECT`:** Estos métodos rara vez se necesitan y pueden introducir riesgos de seguridad significativos, como habilitar el Rastreo entre Sitios (XST) o ataques de túnel.
        -   **Revise regularmente los métodos permitidos:** Audite periódicamente el ajuste `ALLOWED_METHODS` para asegurarse de que se alinee con los requisitos actuales de su aplicación.
        -   **Pruebe a fondo antes de la implementación:** Los cambios en las restricciones de los métodos HTTP pueden afectar la funcionalidad de la aplicación. Valide su configuración en un entorno de preproducción antes de aplicarla a la producción.

=== "Límites de Tamaño de Solicitud"

    **Límites de Tamaño de Solicitud**

    El tamaño máximo del cuerpo de la solicitud se puede controlar utilizando el ajuste `MAX_CLIENT_SIZE` (predeterminado: `10m`). Los valores aceptados siguen la sintaxis descrita [aquí](https://nginx.org/en/docs/syntax.html).

    !!! success "Beneficios de Seguridad"
        -   Protege contra ataques de denegación de servicio causados por tamaños de carga útil excesivos
        -   Mitiga las vulnerabilidades de desbordamiento de búfer
        -   Previene los ataques de carga de archivos
        -   Reduce el riesgo de agotamiento de los recursos del servidor

| Ajuste            | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                       |
| ----------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `MAX_CLIENT_SIZE` | `10m`             | multisite | no       | **Tamaño Máximo de Solicitud:** El tamaño máximo permitido para los cuerpos de las solicitudes de los clientes (por ejemplo, cargas de archivos). |

    !!! tip "Mejores Prácticas de Configuración del Tamaño de la Solicitud"
        Si necesita permitir un cuerpo de solicitud de tamaño ilimitado, puede establecer el valor de `MAX_CLIENT_SIZE` en `0`. Sin embargo, esto **no se recomienda** debido a los posibles riesgos de seguridad y rendimiento.

        **Mejores Prácticas:**

        -   Siempre configure `MAX_CLIENT_SIZE` al valor más pequeño que cumpla con los requisitos legítimos de su aplicación.
        -   Revise y ajuste regularmente este ajuste para alinearlo con las necesidades cambiantes de su aplicación.
        -   Evite establecer `0` a menos que sea absolutamente necesario, ya que puede exponer su servidor a ataques de denegación de servicio y agotamiento de recursos.

        Al gestionar cuidadosamente este ajuste, puede garantizar una seguridad y un rendimiento óptimos para su aplicación.

=== "Soporte de Protocolo"

    **Ajustes del Protocolo HTTP**

    Los protocolos HTTP modernos como HTTP/2 y HTTP/3 mejoran el rendimiento y la seguridad. BunkerWeb permite una fácil configuración de estos protocolos.

    !!! success "Beneficios de Seguridad y Rendimiento"
        -   **Ventajas de Seguridad:** Los protocolos modernos como HTTP/2 y HTTP/3 imponen TLS/HTTPS por defecto, reducen la susceptibilidad a ciertos ataques y mejoran la privacidad a través de encabezados cifrados (HTTP/3).
        -   **Beneficios de Rendimiento:** Características como la multiplexación, la compresión de encabezados, el empuje del servidor y la transferencia de datos binarios mejoran la velocidad y la eficiencia.

| Ajuste               | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                  |
| -------------------- | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------------- |
| `LISTEN_HTTP`        | `yes`             | multisite | no       | **Escucha HTTP:** Responda a las solicitudes HTTP (inseguras) cuando se establezca en `yes`. |
| `HTTP2`              | `yes`             | multisite | no       | **HTTP2:** Soporte para el protocolo HTTP2 cuando HTTPS está habilitado.                     |
| `HTTP3`              | `yes`             | multisite | no       | **HTTP3:** Soporte para el protocolo HTTP3 cuando HTTPS está habilitado.                     |
| `HTTP3_ALT_SVC_PORT` | `443`             | multisite | no       | **Puerto Alt-Svc de HTTP3:** Puerto a utilizar en el encabezado Alt-Svc para HTTP3.          |

    !!! example "Sobre HTTP/3"
        HTTP/3, la última versión del Protocolo de Transferencia de Hipertexto, utiliza QUIC sobre UDP en lugar de TCP, abordando problemas como el bloqueo de cabeza de línea para conexiones más rápidas y fiables.

        NGINX introdujo soporte experimental para HTTP/3 y QUIC a partir de la versión 1.25.0. Sin embargo, esta característica todavía es experimental y se recomienda precaución para su uso en producción. Para más detalles, consulte la [documentación oficial de NGINX](https://nginx.org/en/docs/quic.html).

        Se recomienda realizar pruebas exhaustivas antes de habilitar HTTP/3 en entornos de producción.

=== "Entrega de Archivos Estáticos"

    **Configuración de Entrega de Archivos**

    BunkerWeb puede servir archivos estáticos directamente o actuar como un proxy inverso a un servidor de aplicaciones. Por defecto, los archivos se sirven desde `/var/www/html/{server_name}`.

| Ajuste        | Valor por defecto             | Contexto  | Múltiple | Descripción                                                                                                                |
| ------------- | ----------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------- |
| `SERVE_FILES` | `yes`                         | multisite | no       | **Servir Archivos:** Cuando se establece en `yes`, BunkerWeb servirá archivos estáticos desde la carpeta raíz configurada. |
| `ROOT_FOLDER` | `/var/www/html/{server_name}` | multisite | no       | **Carpeta Raíz:** El directorio desde el cual servir archivos estáticos. Vacío significa usar la ubicación predeterminada. |

    !!! tip "Mejores Prácticas para la Entrega de Archivos Estáticos"
        -   **Servicio Directo:** Habilite el servicio de archivos (`SERVE_FILES=yes`) cuando BunkerWeb sea responsable de servir los archivos estáticos directamente.
        -   **Proxy Inverso:** Si BunkerWeb actúa como un proxy inverso, **desactive el servicio de archivos** (`SERVE_FILES=no`) para reducir la superficie de ataque y evitar exponer directorios innecesarios.
        -   **Permisos:** Asegúrese de tener los permisos de archivo y las configuraciones de ruta adecuados para evitar el acceso no autorizado.
        -   **Seguridad:** Evite exponer directorios o archivos sensibles a través de configuraciones incorrectas.

        Al gestionar cuidadosamente la entrega de archivos estáticos, puede optimizar el rendimiento mientras mantiene un entorno seguro.

=== "Ajustes del Sistema"

    **Gestión de Complementos y del Sistema**

    Estos ajustes gestionan la interacción de BunkerWeb con sistemas externos y contribuyen a mejorar el producto a través de estadísticas de uso anónimas opcionales.

    **Informes Anónimos**

    Los informes anónimos proporcionan al equipo de BunkerWeb información sobre cómo se está utilizando el software. Esto ayuda a identificar áreas de mejora y a priorizar el desarrollo de características. Los informes son estrictamente estadísticos y no incluyen ninguna información sensible o de identificación personal. Cubren:

    -   Características habilitadas
    -   Patrones de configuración generales

    Puede deshabilitar esta característica si lo desea estableciendo `SEND_ANONYMOUS_REPORT` en `no`.

    **Complementos Externos**

    Los complementos externos le permiten ampliar la funcionalidad de BunkerWeb integrando módulos de terceros. Esto permite una personalización adicional y casos de uso avanzados.

    !!! danger "Seguridad de los Complementos Externos"
        **Los complementos externos pueden introducir riesgos de seguridad si no se examinan adecuadamente.** Siga estas mejores prácticas para minimizar las amenazas potenciales:

        -   Solo use complementos de fuentes de confianza.
        -   Verifique la integridad del complemento utilizando sumas de verificación cuando estén disponibles.
        -   Revise y actualice regularmente los complementos para garantizar la seguridad y la compatibilidad.

        Para más detalles, consulte la [documentación de Complementos](plugins.md).

| Ajuste                  | Valor por defecto | Contexto | Múltiple | Descripción                                                                                   |
| ----------------------- | ----------------- | -------- | -------- | --------------------------------------------------------------------------------------------- |
| `SEND_ANONYMOUS_REPORT` | `yes`             | global   | no       | **Informes Anónimos:** Envíe informes de uso anónimos a los mantenedores de BunkerWeb.        |
| `EXTERNAL_PLUGIN_URLS`  |                   | global   | no       | **Complementos Externos:** URL para descargar complementos externos (separados por espacios). |

=== "Almacenamiento en Caché de Archivos"

    **Optimización del Almacenamiento en Caché de Archivos**

    La caché de archivos abiertos mejora el rendimiento al almacenar descriptores de archivos y metadatos en la memoria, reduciendo la necesidad de operaciones repetidas del sistema de archivos.

    !!! success "Beneficios del Almacenamiento en Caché de Archivos"
        -   **Rendimiento:** Reduce la E/S del sistema de archivos, disminuye la latencia y reduce el uso de la CPU para las operaciones de archivos.
        -   **Seguridad:** Mitiga los ataques de tiempo al almacenar en caché las respuestas de error y reduce el impacto de los ataques DoS dirigidos al sistema de archivos.

| Ajuste                     | Valor por defecto       | Contexto  | Múltiple | Descripción                                                                                                                            |
| -------------------------- | ----------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_OPEN_FILE_CACHE`      | `no`                    | multisite | no       | **Habilitar Caché:** Habilite el almacenamiento en caché de descriptores de archivos y metadatos para mejorar el rendimiento.          |
| `OPEN_FILE_CACHE`          | `max=1000 inactive=20s` | multisite | no       | **Configuración de Caché:** Configure la caché de archivos abiertos (por ejemplo, entradas máximas y tiempo de espera de inactividad). |
| `OPEN_FILE_CACHE_ERRORS`   | `yes`                   | multisite | no       | **Errores de Caché:** Almacene en caché los errores de búsqueda de descriptores de archivos, así como las búsquedas exitosas.          |
| `OPEN_FILE_CACHE_MIN_USES` | `2`                     | multisite | no       | **Usos Mínimos:** Número mínimo de accesos durante el período de inactividad para que un archivo permanezca en caché.                  |
| `OPEN_FILE_CACHE_VALID`    | `30s`                   | multisite | no       | **Validez de la Caché:** Tiempo después del cual los elementos en caché se revalidan.                                                  |

    **Guía de Configuración**

    Para habilitar y configurar el almacenamiento en caché de archivos:
    1.  Establezca `USE_OPEN_FILE_CACHE` en `yes` para activar la característica.
    2.  Ajuste los parámetros de `OPEN_FILE_CACHE` para definir el número máximo de entradas en caché y su tiempo de espera de inactividad.
    3.  Use `OPEN_FILE_CACHE_ERRORS` para almacenar en caché tanto las búsquedas exitosas como las fallidas, reduciendo las operaciones repetidas del sistema de archivos.
    4.  Establezca `OPEN_FILE_CACHE_MIN_USES` para especificar el número mínimo de accesos requeridos para que un archivo permanezca en caché.
    5.  Defina el período de validez de la caché con `OPEN_FILE_CACHE_VALID` para controlar con qué frecuencia se revalidan los elementos en caché.

    !!! tip "Mejores Prácticas"
        -   Habilite el almacenamiento en caché de archivos para sitios web con muchos archivos estáticos para mejorar el rendimiento.
        -   Revise y ajuste regularmente la configuración de la caché para equilibrar el rendimiento y el uso de recursos.
        -   En entornos dinámicos donde los archivos cambian con frecuencia, considere reducir el período de validez de la caché o deshabilitar la característica para garantizar la frescura del contenido.

### Configuraciones de Ejemplo

=== "Seguridad del Servidor Predeterminado"

    Configuración de ejemplo para deshabilitar el servidor predeterminado y aplicar un SNI estricto:

    ```yaml
    DISABLE_DEFAULT_SERVER: "yes"
    DISABLE_DEFAULT_SERVER_STRICT_SNI: "yes"
    ```

=== "Estado HTTP de Denegación"

    Configuración de ejemplo para descartar silenciosamente las solicitudes no deseadas:

    ```yaml
    DENY_HTTP_STATUS: "444"
    ```

=== "Métodos HTTP"

    Configuración de ejemplo para restringir los métodos HTTP solo a los requeridos por una API RESTful:

    ```yaml
    ALLOWED_METHODS: "GET|POST|PUT|DELETE"
    ```

=== "Límites de Tamaño de Solicitud"

    Configuración de ejemplo para limitar el tamaño máximo del cuerpo de la solicitud:

    ```yaml
    MAX_CLIENT_SIZE: "5m"
    ```

=== "Soporte de Protocolo"

    Configuración de ejemplo para habilitar HTTP/2 y HTTP/3 con un puerto Alt-Svc personalizado:

    ```yaml
    HTTP2: "yes"
    HTTP3: "yes"
    HTTP3_ALT_SVC_PORT: "443"
    ```

=== "Entrega de Archivos Estáticos"

    Configuración de ejemplo para servir archivos estáticos desde una carpeta raíz personalizada:

    ```yaml
    SERVE_FILES: "yes"
    ROOT_FOLDER: "/var/www/custom-folder"
    ```

=== "Almacenamiento en Caché de Archivos"

    Configuración de ejemplo para habilitar y optimizar el almacenamiento en caché de archivos:

    ```yaml
    USE_OPEN_FILE_CACHE: "yes"
    OPEN_FILE_CACHE: "max=2000 inactive=30s"
    OPEN_FILE_CACHE_ERRORS: "yes"
    OPEN_FILE_CACHE_MIN_USES: "3"
    OPEN_FILE_CACHE_VALID: "60s"
    ```
