El plugin gRPC permite a BunkerWeb hacer proxy de servicios gRPC a través de HTTP/2 usando `grpc_pass`. Está diseñado para entornos multisitio donde cada host virtual puede exponer uno o varios backends gRPC en rutas específicas.

!!! example "Funcionalidad experimental"
    Esta funcionalidad todavía no está lista para producción. Siéntete libre de probarla y reportar cualquier bug mediante [issues](https://github.com/bunkerity/bunkerweb/issues) en el repositorio de GitHub.

**Cómo funciona:**

1. Un cliente envía una petición HTTP/2 a BunkerWeb.
2. El plugin gRPC hace coincidir una `location` configurada (`GRPC_URL`) y reenvía la petición al upstream configurado (`GRPC_HOST`) con `grpc_pass`.
3. BunkerWeb añade cabeceras de reenvío y aplica timeouts/reintentos de upstream.
4. El servidor gRPC upstream responde y BunkerWeb devuelve la respuesta al cliente.

### Cómo usarlo

1. **Activar la función:** Establece `USE_GRPC` en `yes`.
2. **Configurar upstream(s):** Define al menos `GRPC_HOST` (y opcionalmente `GRPC_HOST_2`, `GRPC_HOST_3`, ...).
3. **Mapear ruta(s):** Define `GRPC_URL` para cada upstream (y los sufijos correspondientes para entradas múltiples).
4. **Ajustar comportamiento:** Configura, si hace falta, timeouts, reintentos, cabeceras y opciones TLS SNI.

!!! tip "Grupos reutilizables de backends gRPC"
    Un `GRPC_HOST` apunta a un único backend. Para repartir la carga entre varios backends, o compartir los mismos backends entre servicios, declare un **grupo de upstreams gRPC** en la página **Upstreams** (o a través de la API `/upstreams`) y adjúntelo a un servicio en una ruta — BunkerWeb escribirá entonces `grpc://<grupo>` en el `GRPC_HOST` correspondiente por usted. Tenga en cuenta que los `location` de gRPC y de proxy inverso comparten un único espacio de nombres de rutas en un servicio: la misma ruta no puede reclamarse dos veces, sea cual sea el complemento que la sirva. Consulte la sección *Upstreams reutilizables* de la documentación del Proxy Inverso.

!!! tip "TLS mutuo con el backend gRPC"
    gRPC tiene su propia identidad de upstream, independiente del reverse proxy. Para upstreams TLS, use `grpcs://` y configure `GRPC_SSL_SNI` y `GRPC_SSL_SNI_NAME` según sea necesario. Para verificar el certificado del upstream, ponga `GRPC_SSL_VERIFY=yes` y proporcione un paquete de CA en PEM mediante `GRPC_SSL_TRUSTED_CERTIFICATE` o `_DATA`, seleccionando la fuente con `_PRIORITY` (`file` o `data`). `GRPC_SSL_VERIFY_DEPTH` es `1` por defecto. No se selecciona ningún paquete de CA automáticamente: sin una CA en caché, la configuración generada deshabilita la verificación e incluye un comentario explicando cómo configurarla. Una CRL es opcional (`GRPC_SSL_CRL` o `_DATA`) y solo se aplica cuando hay verificación y una CA en caché presentes. `GRPC_SSL_PROTOCOLS` y `GRPC_SSL_CIPHERS` dejan sin cambios los valores por defecto de NGINX cuando están vacíos.

    Para TLS mutuo, configure `GRPC_SSL_CLIENT_CERT` y `GRPC_SSL_CLIENT_KEY`, o sus variantes `_DATA`; `GRPC_SSL_CLIENT_CERT_PRIORITY` selecciona rutas de archivo o datos para el par. Ambas mitades deben ser válidas y coincidir — BunkerWeb comprueba que el certificado de cliente del upstream coincide con su clave; los fallos temporales de lectura de archivo conservan el material TLS en caché y notifican un fallo del job, mientras que borrar los ajustes o un material inválido elimina la caché afectada. Esta identidad pertenece a gRPC; el reverse proxy y stream usan `REVERSE_PROXY_SSL_CLIENT_*` de forma independiente. El job compartido `trusted-cert` almacena en caché la CA, la CRL y el par de cliente de gRPC en el directorio de caché de reverseproxy, y activa la regeneración de la configuración cuando el material cambia. No existe un job de certificado independiente para gRPC. Los ajustes TLS se aplican a todo el servicio, incluidos los grupos de upstream adjuntos; no son ajustes por ubicación. Consulte *TLS mutuo con el upstream* en la documentación del Reverse Proxy.

### Ajustes de Configuración

| Setting                                 | Por defecto | Contexto  | Múltiple | Descripción                                                                                                                                |
| ---------------------------------------- | ----------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GRPC`                              | `no`        | multisite | no       | **Habilitar gRPC:** Pon `yes` para habilitar el proxy gRPC.                                                                               |
| `GRPC_HOST`                             |             | multisite | sí       | **Upstream gRPC:** Valor usado por `grpc_pass` (por ejemplo `grpc://service:50051` o `grpcs://...`).                                      |
| `GRPC_URL`                              | `/`         | multisite | sí       | **URL de location:** Ruta que se enviará al upstream gRPC. Un valor que comienza por `^` o termina en `$` se trata como una ubicación de expresión regular. Opcionalmente, se puede anteponer `~`, `~*`, `=` o `^~` seguido de un espacio para establecer explícitamente el modificador de ubicación de nginx; no se permiten espacios, `;`, `{` ni `}` en el resto del valor. |
| `GRPC_CUSTOM_HOST`                      |             | multisite | no       | **Cabecera Host personalizada:** Sobrescribe la cabecera `Host` enviada al upstream.                                                      |
| `GRPC_HEADERS`                          |             | multisite | sí       | **Cabeceras al upstream:** Lista separada por punto y coma de valores `grpc_set_header`; las cabeceras generadas coincidentes se reemplazan sin distinguir mayúsculas/minúsculas. |
| `GRPC_HIDE_HEADERS`                     |             | multisite | sí       | **Cabeceras de respuesta ocultas:** Lista separada por espacios de valores para `grpc_hide_header`.                                       |
| `GRPC_HEADERS_CLIENT`                   |             | multisite | sí       | **Cabeceras de respuesta al cliente:** Lista separada por punto y coma de valores `add_header` enviados al cliente.                       |
| `GRPC_PASS_HEADERS`                     |             | multisite | sí       | **Cabeceras de respuesta reenviadas:** Lista separada por espacios de valores `grpc_pass_header`, para reenviar cabeceras que NGINX oculta por defecto. |
| `GRPC_IGNORE_HEADERS`                   |             | multisite | sí       | **Cabeceras de respuesta ignoradas:** Lista separada por espacios de valores `grpc_ignore_headers`, para que NGINX no las procese.         |
| `GRPC_UNDERSCORES_IN_HEADERS`           | `no`        | multisite | no       | **Guiones bajos en cabeceras:** Activa/desactiva `underscores_in_headers`. Se comparte a nivel de servidor con los plugins reverse proxy y misc: si un servicio la habilita para una ubicación, se aplica a todo el servicio. |
| `GRPC_INTERCEPT_ERRORS`                 | `yes`       | multisite | no       | **Interceptar errores:** Activa/desactiva `grpc_intercept_errors`.                                                                        |
| `GRPC_BUFFER_SIZE`                      |             | multisite | sí       | **Tamaño del buffer:** Valor para `grpc_buffer_size` (buffer usado para leer la respuesta del upstream).                                  |
| `GRPC_CONNECT_TIMEOUT`                  | `60s`       | multisite | sí       | **Timeout de conexión:** Tiempo límite para conectar con el upstream.                                                                     |
| `GRPC_READ_TIMEOUT`                     | `60s`       | multisite | sí       | **Timeout de lectura:** Tiempo límite para leer desde el upstream.                                                                        |
| `GRPC_SEND_TIMEOUT`                     | `60s`       | multisite | sí       | **Timeout de envío:** Tiempo límite para enviar al upstream.                                                                              |
| `GRPC_SOCKET_KEEPALIVE`                 | `off`       | multisite | sí       | **Keepalive de socket:** Activa/desactiva keepalive en sockets hacia upstream.                                                            |
| `GRPC_SSL_SNI`                          | `no`        | multisite | no       | **SSL SNI:** Activa/desactiva SNI para upstreams TLS.                                                                                     |
| `GRPC_SSL_SNI_NAME`                     |             | multisite | no       | **Nombre SSL SNI:** Nombre SNI que se enviará cuando `GRPC_SSL_SNI=yes`.                                                                  |
| `GRPC_SSL_VERIFY`                       | `no`        | multisite | no       | **Verificación SSL:** Activa/desactiva la verificación del certificado del upstream gRPC.                                                 |
| `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY` | `file`      | multisite | no       | **Prioridad del certificado de confianza:** Origen del paquete de CA, `file` o `data`.                                                    |
| `GRPC_SSL_TRUSTED_CERTIFICATE`          |             | multisite | no       | **Ruta del certificado de confianza:** Ruta a un paquete de CA en PEM legible por el planificador (prioridad `file`).                     |
| `GRPC_SSL_TRUSTED_CERTIFICATE_DATA`     |             | multisite | no       | **Datos del certificado de confianza:** Paquete de CA como base64 o PEM en texto plano (prioridad `data`).                                |
| `GRPC_SSL_VERIFY_DEPTH`                 | `1`         | multisite | no       | **Profundidad de verificación SSL:** Profundidad de verificación en la cadena de certificados del upstream.                               |
| `GRPC_SSL_CLIENT_CERT_PRIORITY`         | `file`      | multisite | no       | **Prioridad del certificado de cliente:** Origen del certificado y clave de cliente, `file` o `data`.                                     |
| `GRPC_SSL_CLIENT_CERT`                  |             | multisite | no       | **Ruta del certificado de cliente:** Certificado de cliente en PEM presentado al upstream para TLS mutuo (prioridad `file`).              |
| `GRPC_SSL_CLIENT_CERT_DATA`             |             | multisite | no       | **Datos del certificado de cliente:** Certificado de cliente como base64 o PEM en texto plano (prioridad `data`).                         |
| `GRPC_SSL_CLIENT_KEY`                   |             | multisite | no       | **Ruta de la clave de cliente:** Clave privada en PEM que coincide con el certificado de cliente (prioridad `file`). No debe estar cifrada. |
| `GRPC_SSL_CLIENT_KEY_DATA`              |             | multisite | no       | **Datos de la clave de cliente:** Clave privada de cliente como base64 o PEM en texto plano (prioridad `data`).                            |
| `GRPC_SSL_CRL`                          |             | multisite | no       | **Ruta de la CRL:** Lista de revocación en PEM aplicada al verificar el upstream; solo se aplica cuando `GRPC_SSL_VERIFY=yes`. Tiene prioridad sobre el ajuste de datos de la CRL; una ruta definida pero ausente es un error y el ajuste de datos no se usa como alternativa. |
| `GRPC_SSL_CRL_DATA`                     |             | multisite | no       | **Datos de la CRL:** Lista de revocación como base64 o PEM en texto plano. Solo se usa cuando la ruta de la CRL está vacía.                |
| `GRPC_SSL_PROTOCOLS`                    |             | multisite | no       | **Protocolos SSL del upstream:** Versiones de TLS ofrecidas al upstream. Vacío mantiene el valor por defecto de NGINX.                     |
| `GRPC_SSL_CIPHERS`                      |             | multisite | no       | **Cifrados SSL del upstream:** Cadena de suite de cifrado ofrecida al upstream. Vacío mantiene el valor por defecto de NGINX.              |
| `GRPC_NEXT_UPSTREAM`                    |             | multisite | sí       | **Condiciones de siguiente upstream:** Valor para `grpc_next_upstream`.                                                                   |
| `GRPC_NEXT_UPSTREAM_TIMEOUT`            |             | multisite | sí       | **Timeout de siguiente upstream:** Valor para `grpc_next_upstream_timeout`.                                                               |
| `GRPC_NEXT_UPSTREAM_TRIES`              |             | multisite | sí       | **Intentos de siguiente upstream:** Valor para `grpc_next_upstream_tries`.                                                                |
| `GRPC_AUTH_REQUEST`                     |             | multisite | sí       | **Auth Request:** Valor para `auth_request`, para autenticar mediante un proveedor externo.                                               |
| `GRPC_AUTH_REQUEST_SIGNIN_URL`          |             | multisite | sí       | **URL de inicio de sesión de Auth Request:** Destino de redirección cuando la auth request devuelve 401. Se admiten fragmentos (`#`).      |
| `GRPC_AUTH_REQUEST_SET`                 |             | multisite | sí       | **Auth Request Set:** Lista separada por punto y coma de valores `auth_request_set`.                                                      |
| `GRPC_INCLUDES`                         |             | multisite | sí       | **Includes adicionales:** Archivos `include` separados por espacios dentro del bloque gRPC `location`.                                    |
| `GRPC_MAX_CLIENT_SIZE`                  |             | multisite | sí       | **Tamaño máximo del cuerpo:** Valor para `client_max_body_size` en esta ubicación (`0` para infinito). Recurre a `MAX_CLIENT_SIZE` del servicio. |

`GRPC_HOST`, `GRPC_URL`, `GRPC_HEADERS`, `GRPC_HIDE_HEADERS`, `GRPC_HEADERS_CLIENT`, `GRPC_PASS_HEADERS`, `GRPC_IGNORE_HEADERS`, `GRPC_BUFFER_SIZE`, `GRPC_CONNECT_TIMEOUT`, `GRPC_READ_TIMEOUT`, `GRPC_SEND_TIMEOUT`, `GRPC_SOCKET_KEEPALIVE`, `GRPC_NEXT_UPSTREAM{,_TIMEOUT,_TRIES}`, `GRPC_AUTH_REQUEST{,_SIGNIN_URL,_SET}`, `GRPC_INCLUDES` y `GRPC_MAX_CLIENT_SIZE` admiten sufijos numéricos para múltiples upstreams/ubicaciones (`GRPC_HOST_2`, `GRPC_URL_2`, ...). `GRPC_HEADERS_CLIENT` usa la semántica `add_header` de NGINX (añada `always` cuando sea necesario). Las URL de inicio de sesión conservan el soporte de fragmentos (`#`). ModSecurity permanece deshabilitado en las ubicaciones gRPC.

!!! warning "ModSecurity en ubicaciones gRPC"
    Actualmente ModSecurity se desactiva automáticamente dentro de los bloques gRPC `location` generados por este plugin, porque ModSecurity no soporta de forma fiable los patrones de tráfico gRPC.

!!! warning "Streams de larga duración y timeouts del core"
    Los RPC de larga duración o en streaming pueden requerir timeouts NGINX genéricos más altos que los valores globales por defecto. Los ajustes más comunes son `CLIENT_BODY_TIMEOUT` y `CLIENT_HEADER_TIMEOUT` en la configuración del plugin General.

!!! tip "Múltiples backends gRPC"
    Usa ajustes con sufijo para varias rutas:
    - `GRPC_HOST`, `GRPC_URL`
    - `GRPC_HOST_2`, `GRPC_URL_2`
    - `GRPC_HOST_3`, `GRPC_URL_3`

### Ejemplos de configuración

=== "Proxy gRPC básico"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_CONNECT_TIMEOUT: "10s"
    GRPC_READ_TIMEOUT: "300s"
    GRPC_SEND_TIMEOUT: "300s"
    ```

=== "Upstream TLS (grpcs + SNI)"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpcs://internal-grpc.example.net:443"
    GRPC_URL: "/"
    GRPC_SSL_SNI: "yes"
    GRPC_SSL_SNI_NAME: "internal-grpc.example.net"
    ```

=== "Múltiples rutas / backends"

    ```yaml
    USE_GRPC: "yes"

    GRPC_HOST: "grpc://user-service:50051"
    GRPC_URL: "/users.UserService/"

    GRPC_HOST_2: "grpc://billing-service:50052"
    GRPC_URL_2: "/billing.BillingService/"

    GRPC_HOST_3: "grpc://inventory-service:50053"
    GRPC_URL_3: "/inventory.InventoryService/"
    ```

=== "Cabeceras y política de reintentos"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_HEADERS: "x-request-source bunkerweb;x-env production"
    GRPC_NEXT_UPSTREAM: "error timeout http_502"
    GRPC_NEXT_UPSTREAM_TIMEOUT: "15s"
    GRPC_NEXT_UPSTREAM_TRIES: "3"
    ```
