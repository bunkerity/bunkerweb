El complemento de Proxy Inverso proporciona capacidades de proxy sin interrupciones para BunkerWeb, lo que le permite enrutar solicitudes a servidores y servicios de backend. Esta función permite que BunkerWeb actúe como un frontend seguro para sus aplicaciones al tiempo que proporciona beneficios adicionales como la terminación de SSL y el filtrado de seguridad.

**Cómo funciona:**

1.  Cuando un cliente envía una solicitud a BunkerWeb, el complemento de Proxy Inverso reenvía la solicitud a su servidor de backend configurado.
2.  BunkerWeb agrega encabezados de seguridad, aplica reglas de WAF y realiza otras verificaciones de seguridad antes de pasar las solicitudes a su aplicación.
3.  El servidor de backend procesa la solicitud y devuelve una respuesta a BunkerWeb.
4.  BunkerWeb aplica medidas de seguridad adicionales a la respuesta antes de enviarla de vuelta al cliente.
5.  El complemento admite el proxy de flujo tanto HTTP como TCP/UDP, lo que permite una amplia gama de aplicaciones, incluidos WebSockets y otros protocolos no HTTP.

### Cómo usar

Siga estos pasos para configurar y usar la función de Proxy Inverso:

1.  **Habilite la función:** Establezca el ajuste `USE_REVERSE_PROXY` en `yes` para habilitar la funcionalidad de proxy inverso.
2.  **Configure sus servidores de backend:** Especifique los servidores upstream utilizando el ajuste `REVERSE_PROXY_HOST`.
3.  **Ajuste la configuración del proxy:** Afine el comportamiento con ajustes opcionales para tiempos de espera, tamaños de búfer y otros parámetros.
4.  **Configure las opciones específicas del protocolo:** Para WebSockets o requisitos HTTP especiales, ajuste la configuración correspondiente.
5.  **Configure el almacenamiento en caché (opcional):** Habilite y configure el almacenamiento en caché del proxy para mejorar el rendimiento del contenido al que se accede con frecuencia.

### Guía de Configuración

=== "Configuración Básica"

    **Ajustes Principales**

    Los ajustes de configuración esenciales habilitan y controlan la funcionalidad básica de la función de proxy inverso.

    !!! success "Beneficios del Proxy Inverso"
        - **Mejora de la Seguridad:** Todo el tráfico pasa a través de las capas de seguridad de BunkerWeb antes de llegar a sus aplicaciones
        - **Terminación SSL:** Administre los certificados SSL/TLS de forma centralizada mientras que los servicios de backend pueden usar conexiones no cifradas
        - **Manejo de Protocolos:** Soporte para HTTP, HTTPS, WebSockets y otros protocolos
        - **Interceptación de Errores:** Personalice las páginas de error para una experiencia de usuario consistente

| Ajuste                           | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                     |
| -------------------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REVERSE_PROXY`              | `no`              | multisite | no       | **Habilitar Proxy Inverso:** Establezca en `yes` para habilitar la funcionalidad de proxy inverso.                                              |
| `REVERSE_PROXY_HOST`             |                   | multisite | yes      | **Host de Backend:** URL completa del recurso al que se hace proxy (proxy_pass).                                                                |
| `REVERSE_PROXY_URL`              | `/`               | multisite | yes      | **URL de Ubicación:** Ruta que se enviará al servidor de backend.                                                                               |
| `REVERSE_PROXY_BUFFERING`        | `yes`             | multisite | yes      | **Almacenamiento en Búfer de Respuesta:** Habilite o deshabilite el almacenamiento en búfer de las respuestas del recurso al que se hace proxy. |
| `REVERSE_PROXY_REQUEST_BUFFERING`| `yes`             | multisite | yes      | **Almacenamiento en Búfer de Solicitudes:** Habilite o deshabilite el almacenamiento en búfer de las solicitudes al recurso al que se hace proxy. |
| `REVERSE_PROXY_KEEPALIVE`        | `no`              | multisite | yes      | **Keep-Alive:** Habilite o deshabilite las conexiones keepalive con el recurso al que se hace proxy.                                            |
| `REVERSE_PROXY_CUSTOM_HOST`      |                   | multisite | no       | **Host Personalizado:** Anule el encabezado Host enviado al servidor upstream.                                                                  |
| `REVERSE_PROXY_INTERCEPT_ERRORS` | `yes`             | multisite | no       | **Interceptar Errores:** Si se deben interceptar y reescribir las respuestas de error del backend.                                              |

    !!! tip "Mejores Prácticas"
        - Siempre especifique la URL completa en `REVERSE_PROXY_HOST`, incluido el protocolo (http:// o https://)
        - Use `REVERSE_PROXY_INTERCEPT_ERRORS` para proporcionar páginas de error consistentes en todos sus servicios
        - Al configurar múltiples backends, use el formato de sufijo numerado (por ejemplo, `REVERSE_PROXY_HOST_2`, `REVERSE_PROXY_URL_2`)

    !!! warning "Comportamiento del almacenamiento en búfer de solicitudes"
        Desactivar `REVERSE_PROXY_REQUEST_BUFFERING` solo tiene efecto cuando ModSecurity está deshabilitado, porque el almacenamiento en búfer de solicitudes se fuerza de otro modo.

=== "Ajustes de Conexión"

    **Configuración de Conexión y Tiempo de Espera**

    Estos ajustes controlan el comportamiento de la conexión, el almacenamiento en búfer y los valores de tiempo de espera para las conexiones con proxy.

    !!! success "Beneficios"
        - **Rendimiento Optimizado:** Ajuste los tamaños de los búferes y la configuración de la conexión según las necesidades de su aplicación
        - **Gestión de Recursos:** Controle el uso de la memoria mediante configuraciones de búfer adecuadas
        - **Fiabilidad:** Configure los tiempos de espera adecuados para manejar conexiones lentas o problemas de backend

| Ajuste                          | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                    |
| ------------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `REVERSE_PROXY_CONNECT_TIMEOUT` | `60s`             | multisite | yes      | **Tiempo de Espera de Conexión:** Tiempo máximo para establecer una conexión con el servidor de backend.                       |
| `REVERSE_PROXY_READ_TIMEOUT`    | `60s`             | multisite | yes      | **Tiempo de Espera de Lectura:** Tiempo máximo entre las transmisiones de dos paquetes sucesivos desde el servidor de backend. |
| `REVERSE_PROXY_SEND_TIMEOUT`    | `60s`             | multisite | yes      | **Tiempo de Espera de Envío:** Tiempo máximo entre las transmisiones de dos paquetes sucesivos al servidor de backend.         |
| `PROXY_BUFFERS`                 |                   | multisite | no       | **Búferes:** Número y tamaño de los búferes para leer la respuesta del servidor de backend.                                    |
| `PROXY_BUFFER_SIZE`             |                   | multisite | no       | **Tamaño del Búfer:** Tamaño del búfer para leer la primera parte de la respuesta del servidor de backend.                     |
| `PROXY_BUSY_BUFFERS_SIZE`       |                   | multisite | no       | **Tamaño de los Búferes Ocupados:** Tamaño de los búferes que pueden estar ocupados enviando la respuesta al cliente.          |

    !!! warning "Consideraciones sobre el Tiempo de Espera"
        - Establecer tiempos de espera demasiado bajos puede hacer que se terminen las conexiones legítimas pero lentas
        - Establecer tiempos de espera demasiado altos puede dejar las conexiones abiertas innecesariamente, lo que podría agotar los recursos
        - Para las aplicaciones WebSocket, aumente significativamente los tiempos de espera de lectura y envío (se recomienda 300s o más)

=== "Configuración SSL/TLS"

    **Ajustes SSL/TLS para Conexiones de Backend**

    Estos ajustes controlan cómo BunkerWeb establece conexiones seguras con los servidores de backend.

    !!! success "Beneficios"
        - **Cifrado de Extremo a Extremo:** Mantenga las conexiones cifradas desde el cliente hasta el backend
        - **Validación de Certificados:** Controle cómo se validan los certificados del servidor de backend
        - **Soporte SNI:** Especifique la Indicación del Nombre del Servidor para los backends que alojan múltiples sitios

| Ajuste                       | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                          |
| ---------------------------- | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------- |
| `REVERSE_PROXY_SSL_SNI`      | `no`              | multisite | no       | **SSL SNI:** Habilite o deshabilite el envío de SNI (Indicación del Nombre del Servidor) al upstream.                |
| `REVERSE_PROXY_SSL_SNI_NAME` |                   | multisite | no       | **Nombre de SSL SNI:** Establece el nombre de host de SNI que se enviará al upstream cuando SSL SNI esté habilitado. |

    !!! info "SNI Explicado"
        La Indicación del Nombre del Servidor (SNI) es una extensión de TLS que permite a un cliente especificar el nombre de host al que intenta conectarse durante el proceso de handshake. Esto permite a los servidores presentar múltiples certificados en la misma dirección IP y puerto, lo que permite que múltiples sitios web seguros (HTTPS) se sirvan desde una única dirección IP sin requerir que todos esos sitios usen el mismo certificado.

=== "Soporte de Protocolo"

    **Configuración Específica del Protocolo**

    Configure el manejo especial de protocolos, particularmente para WebSockets y otros protocolos no HTTP.

    !!! success "Beneficios"
        - **Flexibilidad de Protocolo:** El soporte para WebSockets permite aplicaciones en tiempo real
        - **Aplicaciones Web Modernas:** Habilite características interactivas que requieren comunicación bidireccional

| Ajuste             | Valor por defecto | Contexto  | Múltiple | Descripción                                                              |
| ------------------ | ----------------- | --------- | -------- | ------------------------------------------------------------------------ |
| `REVERSE_PROXY_WS` | `no`              | multisite | yes      | **Soporte de WebSocket:** Habilite el protocolo WebSocket en el recurso. |

    !!! tip "Configuración de WebSocket"
        - Al habilitar WebSockets con `REVERSE_PROXY_WS: "yes"`, considere aumentar los valores de tiempo de espera
        - Las conexiones WebSocket permanecen abiertas más tiempo que las conexiones HTTP típicas
        - Para las aplicaciones WebSocket, una configuración recomendada es:
          ```yaml
          REVERSE_PROXY_WS: "yes"
          REVERSE_PROXY_READ_TIMEOUT: "300s"
          REVERSE_PROXY_SEND_TIMEOUT: "300s"
          ```

=== "Gestión de Encabezados"

    **Configuración de Encabezados HTTP**

    Controle qué encabezados se envían a los servidores de backend y a los clientes, lo que le permite agregar, modificar o preservar los encabezados HTTP.

    !!! success "Beneficios"
        - **Control de la Información:** Administre con precisión qué información se comparte entre los clientes y los backends
        - **Mejora de la Seguridad:** Agregue encabezados relacionados con la seguridad o elimine los encabezados que podrían filtrar información sensible
        - **Soporte de Integración:** Proporcione los encabezados necesarios para la autenticación y el correcto funcionamiento del backend

| Ajuste                                 | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                          |
| -------------------------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------- |
| `REVERSE_PROXY_HEADERS`                |                   | multisite | yes      | **Encabezados Personalizados:** Encabezados HTTP para enviar al backend separados por punto y coma.  |
| `REVERSE_PROXY_HIDE_HEADERS`           | `Upgrade`         | multisite | yes      | **Ocultar Encabezados:** Encabezados HTTP para ocultar a los clientes cuando se reciben del backend. |
| `REVERSE_PROXY_HEADERS_CLIENT`         |                   | multisite | yes      | **Encabezados del Cliente:** Encabezados HTTP para enviar al cliente separados por punto y coma.     |
| `REVERSE_PROXY_UNDERSCORES_IN_HEADERS` | `no`              | multisite | no       | **Guiones Bajos en los Encabezados:** Habilite o deshabilite la directiva `underscores_in_headers`.  |

    !!! warning "Consideraciones de Seguridad"
        Al usar la función de proxy inverso, tenga cuidado con los encabezados que reenvía a sus aplicaciones de backend. Ciertos encabezados pueden exponer información sensible sobre su infraestructura o eludir los controles de seguridad.

    !!! example "Ejemplos de Formato de Encabezado"
        Encabezados personalizados para los servidores de backend:
        ```
        REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"
        ```

        Encabezados personalizados para los clientes:
        ```
        REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
        ```

=== "Autenticación"

    **Configuración de Autenticación Externa**

    Integre con sistemas de autenticación externos para centralizar la lógica de autorización en sus aplicaciones.

    !!! success "Beneficios"
        - **Autenticación Centralizada:** Implemente un único punto de autenticación para múltiples aplicaciones
        - **Seguridad Consistente:** Aplique políticas de autenticación uniformes en diferentes servicios
        - **Control Mejorado:** Reenvíe los detalles de la autenticación a las aplicaciones de backend a través de encabezados o variables

| Ajuste                                  | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                      |
| --------------------------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| `REVERSE_PROXY_AUTH_REQUEST`            |                   | multisite | yes      | **Solicitud de Autenticación:** Habilite la autenticación mediante un proveedor externo.                         |
| `REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` |                   | multisite | yes      | **URL de Inicio de Sesión:** Redirija a los clientes a la URL de inicio de sesión cuando falle la autenticación. |
| `REVERSE_PROXY_AUTH_REQUEST_SET`        |                   | multisite | yes      | **Conjunto de Solicitudes de Autenticación:** Variables a establecer desde el proveedor de autenticación.        |

    !!! tip "Integración de Autenticación"
        - La función de solicitud de autenticación permite la implementación de microservicios de autenticación centralizados
        - Su servicio de autenticación debe devolver un código de estado 200 para una autenticación exitosa o 401/403 para fallas
        - Use la directiva `auth_request_set` para extraer y reenviar información del servicio de autenticación

=== "Configuración Avanzada"

    **Opciones de Configuración Adicionales**

    Estos ajustes proporcionan una mayor personalización del comportamiento del proxy inverso para escenarios especializados.

    !!! success "Beneficios"
        - **Personalización:** Incluya fragmentos de configuración adicionales para requisitos complejos
        - **Optimización del Rendimiento:** Afine el manejo de solicitudes para casos de uso específicos
        - **Flexibilidad:** Adáptese a los requisitos únicos de la aplicación con configuraciones especializadas

| Ajuste                            | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                     |
| --------------------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------- |
| `REVERSE_PROXY_INCLUDES`          |                   | multisite | yes      | **Configuraciones Adicionales:** Incluya configuraciones adicionales en el bloque de ubicación. |
| `REVERSE_PROXY_PASS_REQUEST_BODY` | `yes`             | multisite | yes      | **Pasar el Cuerpo de la Solicitud:** Habilite o deshabilite el paso del cuerpo de la solicitud. |

    !!! warning "Consideraciones de Seguridad"
        Tenga cuidado al incluir fragmentos de configuración personalizados, ya que pueden anular la configuración de seguridad de BunkerWeb o introducir vulnerabilidades si no se configuran correctamente.

=== "Configuración de Caché"

    **Ajustes de Almacenamiento en Caché de Respuestas**

    Mejore el rendimiento almacenando en caché las respuestas de los servidores de backend, reduciendo la carga y mejorando los tiempos de respuesta.

    !!! success "Beneficios"
        - **Rendimiento:** Reduzca la carga en los servidores de backend sirviendo contenido en caché
        - **Latencia Reducida:** Tiempos de respuesta más rápidos para el contenido solicitado con frecuencia
        - **Ahorro de Ancho de Banda:** Minimice el tráfico de la red interna almacenando en caché las respuestas
        - **Personalización:** Configure exactamente qué, cuándo y cómo se almacena en caché el contenido

| Ajuste                       | Valor por defecto                  | Contexto  | Múltiple | Descripción                                                                                                         |
| ---------------------------- | ---------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
| `USE_PROXY_CACHE`            | `no`                               | multisite | no       | **Habilitar Caché:** Establezca en `yes` para habilitar el almacenamiento en caché de las respuestas del backend.   |
| `PROXY_CACHE_PATH_LEVELS`    | `1:2`                              | global    | no       | **Niveles de Ruta de Caché:** Cómo estructurar la jerarquía del directorio de caché.                                |
| `PROXY_CACHE_PATH_ZONE_SIZE` | `10m`                              | global    | no       | **Tamaño de la Zona de Caché:** Tamaño de la zona de memoria compartida utilizada para los metadatos de la caché.   |
| `PROXY_CACHE_PATH_PARAMS`    | `max_size=100m`                    | global    | no       | **Parámetros de la Ruta de Caché:** Parámetros adicionales para la ruta de la caché.                                |
| `PROXY_CACHE_METHODS`        | `GET HEAD`                         | multisite | no       | **Métodos de Caché:** Métodos HTTP que se pueden almacenar en caché.                                                |
| `PROXY_CACHE_MIN_USES`       | `2`                                | multisite | no       | **Usos Mínimos de Caché:** Número mínimo de solicitudes antes de que una respuesta se almacene en caché.            |
| `PROXY_CACHE_KEY`            | `$scheme$host$request_uri`         | multisite | no       | **Clave de Caché:** La clave utilizada para identificar de forma única una respuesta en caché.                      |
| `PROXY_CACHE_VALID`          | `200=24h 301=1h 302=24h`           | multisite | no       | **Validez de la Caché:** Cuánto tiempo almacenar en caché los códigos de respuesta específicos.                     |
| `PROXY_NO_CACHE`             | `$http_pragma $http_authorization` | multisite | no       | **Sin Caché:** Condiciones para no almacenar en caché las respuestas aunque normalmente sean almacenables en caché. |
| `PROXY_CACHE_BYPASS`         | `0`                                | multisite | no       | **Omitir Caché:** Condiciones bajo las cuales omitir la caché.                                                      |

    !!! tip "Mejores Prácticas de Almacenamiento en Caché"
        - Almacene en caché solo el contenido que no cambia con frecuencia o no es personalizado
        - Use duraciones de caché apropiadas según el tipo de contenido (los activos estáticos se pueden almacenar en caché por más tiempo)
        - Configure `PROXY_NO_CACHE` para evitar almacenar en caché contenido sensible o personalizado
        - Supervise las tasas de aciertos de la caché y ajuste la configuración en consecuencia

!!! danger "Usuarios de Docker Compose - Variables de NGINX"
    Al usar Docker Compose con variables de NGINX en sus configuraciones, debe escapar el signo de dólar (`$`) usando signos de dólar dobles (`$$`). Esto se aplica a todos los ajustes que contienen variables de NGINX como `$remote_addr`, `$proxy_add_x_forwarded_for`, etc.

    Sin este escape, Docker Compose intentará sustituir estas variables por variables de entorno, que normalmente no existen, lo que dará como resultado valores vacíos en su configuración de NGINX.

### Configuraciones de Ejemplo

=== "Proxy HTTP Básico"

    Una configuración simple para hacer proxy de las solicitudes HTTP a un servidor de aplicaciones de backend:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "60s"
    REVERSE_PROXY_READ_TIMEOUT: "60s"
    ```

=== "Aplicación WebSocket"

    Configuración optimizada para una aplicación WebSocket con tiempos de espera más largos:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://websocket-app:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_WS: "yes"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "300s"
    REVERSE_PROXY_READ_TIMEOUT: "300s"
    ```

=== "Múltiples Ubicaciones"

    Configuración para enrutar diferentes rutas a diferentes servicios de backend:

    ```yaml
    USE_REVERSE_PROXY: "yes"

    # Backend de la API
    REVERSE_PROXY_HOST: "http://api-server:8080"
    REVERSE_PROXY_URL: "/api/"

    # Backend de Administración
    REVERSE_PROXY_HOST_2: "http://admin-server:8080"
    REVERSE_PROXY_URL_2: "/admin/"

    # Aplicación Frontend
    REVERSE_PROXY_HOST_3: "http://frontend:3000"
    REVERSE_PROXY_URL_3: "/"
    ```

=== "Configuración de Caché"

    Configuración con el almacenamiento en caché del proxy habilitado para un mejor rendimiento:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    USE_PROXY_CACHE: "yes"
    PROXY_CACHE_VALID: "200=24h 301=1h 302=24h"
    PROXY_CACHE_METHODS: "GET HEAD"
    PROXY_NO_CACHE: "$http_authorization"
    ```

=== "Gestión Avanzada de Encabezados"

    Configuración con manipulación de encabezados personalizados:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Encabezados personalizados para el backend
    REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"

    # Encabezados personalizados para el cliente
    REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
    ```

=== "Integración de Autenticación"

    Configuración con autenticación externa:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Configuración de autenticación
    REVERSE_PROXY_AUTH_REQUEST: "/auth"
    REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: "https://login.example.com"
    REVERSE_PROXY_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_role $upstream_http_x_role"

    # Backend del servicio de autenticación
    REVERSE_PROXY_HOST_2: "http://auth-service:8080"
    REVERSE_PROXY_URL_2: "/auth"
    ```
