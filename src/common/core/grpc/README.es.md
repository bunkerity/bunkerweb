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

### Ajustes de configuración

| Ajuste                                  | Predeterminado | Contexto  | Múltiple | Descripción                                                                                                                                                       |
| --------------------------------------- | -------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GRPC`                              | `no`           | multisite | no       | **Habilitar gRPC:** Pon `yes` para habilitar el proxy gRPC.                                                                                                       |
| `GRPC_HOST`                             |                | multisite | sí       | **Upstream gRPC:** Valor usado por `grpc_pass` (por ejemplo `grpc://service:50051` o `grpcs://...`).                                                              |
| `GRPC_URL`                              | `/`            | multisite | sí       | **URL de location:** Ruta que se enviará al upstream gRPC.                                                                                                        |
| `GRPC_CUSTOM_HOST`                      |                | multisite | no       | **Cabecera Host personalizada:** Sobrescribe la cabecera `Host` enviada al upstream.                                                                              |
| `GRPC_HEADERS`                          |                | multisite | sí       | **Cabeceras extra al upstream:** Lista separada por punto y coma de valores para `grpc_set_header`.                                                               |
| `GRPC_HIDE_HEADERS`                     |                | multisite | sí       | **Cabeceras de respuesta ocultas:** Lista separada por espacios de valores para `grpc_hide_header`.                                                               |
| `GRPC_HEADERS_CLIENT`                   |                | multisite | sí       | **Cabeceras de respuesta al cliente:** Lista separada por punto y coma de valores `add_header` enviados al cliente.                                               |
| `GRPC_PASS_HEADERS`                     |                | multisite | sí       | **Cabeceras de respuesta reenviadas:** Lista separada por espacios de valores `grpc_pass_header`, para reenviar cabeceras que NGINX oculta por defecto.           |
| `GRPC_IGNORE_HEADERS`                   |                | multisite | sí       | **Cabeceras de respuesta ignoradas:** Lista separada por espacios de valores `grpc_ignore_headers`, para que NGINX no las procese.                                |
| `GRPC_UNDERSCORES_IN_HEADERS`           | `no`           | multisite | no       | **Guiones bajos en cabeceras:** Activa/desactiva `underscores_in_headers`.                                                                                        |
| `GRPC_INTERCEPT_ERRORS`                 | `yes`          | multisite | no       | **Interceptar errores:** Activa/desactiva `grpc_intercept_errors`.                                                                                                |
| `GRPC_BUFFER_SIZE`                      |                | multisite | sí       | **Tamaño de búfer:** Valor para `grpc_buffer_size` (búfer usado para leer la respuesta del upstream).                                                             |
| `GRPC_CONNECT_TIMEOUT`                  | `60s`          | multisite | sí       | **Timeout de conexión:** Tiempo límite para conectar con el upstream.                                                                                             |
| `GRPC_READ_TIMEOUT`                     | `60s`          | multisite | sí       | **Timeout de lectura:** Tiempo límite para leer desde el upstream.                                                                                                |
| `GRPC_SEND_TIMEOUT`                     | `60s`          | multisite | sí       | **Timeout de envío:** Tiempo límite para enviar al upstream.                                                                                                      |
| `GRPC_SOCKET_KEEPALIVE`                 | `off`          | multisite | sí       | **Keepalive de socket:** Activa/desactiva keepalive en sockets hacia upstream.                                                                                    |
| `GRPC_SSL_SNI`                          | `no`           | multisite | no       | **SSL SNI:** Activa/desactiva SNI para upstreams TLS.                                                                                                             |
| `GRPC_SSL_SNI_NAME`                     |                | multisite | no       | **Nombre SSL SNI:** Nombre SNI que se enviará cuando `GRPC_SSL_SNI=yes`.                                                                                          |
| `GRPC_SSL_VERIFY`                       | `no`           | multisite | no       | **Verificación SSL:** Activa/desactiva la verificación del certificado del upstream gRPC.                                                                         |
| `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY` | `file`         | multisite | no       | **Prioridad del certificado de confianza:** Origen del bundle CA, `file` o `data`.                                                                                |
| `GRPC_SSL_TRUSTED_CERTIFICATE`          |                | multisite | no       | **Ruta del certificado de confianza:** Ruta a un bundle CA PEM legible por el scheduler (prioridad `file`).                                                       |
| `GRPC_SSL_TRUSTED_CERTIFICATE_DATA`     |                | multisite | no       | **Datos del certificado de confianza:** Bundle CA en base64 o PEM en texto plano (prioridad `data`).                                                              |
| `GRPC_SSL_VERIFY_DEPTH`                 | `1`            | multisite | no       | **Profundidad de verificación SSL:** Profundidad de verificación en la cadena de certificados del upstream.                                                       |
| `GRPC_SSL_CERT_PRIORITY`                | `file`         | multisite | no       | **Prioridad del certificado cliente:** Origen del certificado y la clave cliente, `file` o `data`.                                                                |
| `GRPC_SSL_CERT`                         |                | multisite | no       | **Ruta del certificado cliente:** Certificado cliente PEM presentado al upstream para TLS mutuo (prioridad `file`).                                               |
| `GRPC_SSL_CERT_DATA`                    |                | multisite | no       | **Datos del certificado cliente:** Certificado cliente en base64 o PEM en texto plano (prioridad `data`).                                                         |
| `GRPC_SSL_KEY`                          |                | multisite | no       | **Ruta de la clave cliente:** Clave privada PEM correspondiente al certificado cliente (prioridad `file`). No debe estar cifrada.                                 |
| `GRPC_SSL_KEY_DATA`                     |                | multisite | no       | **Datos de la clave cliente:** Clave privada cliente en base64 o PEM en texto plano (prioridad `data`).                                                           |
| `GRPC_SSL_CRL`                          |                | multisite | no       | **Ruta de la CRL:** Lista de revocación PEM aplicada al verificar el upstream. Tiene prioridad sobre los datos de CRL.                                            |
| `GRPC_SSL_CRL_DATA`                     |                | multisite | no       | **Datos de la CRL:** Lista de revocación en base64 o PEM en texto plano. Solo se usan si la ruta de la CRL está vacía.                                            |
| `GRPC_SSL_PROTOCOLS`                    |                | multisite | no       | **Protocolos SSL del upstream:** Versiones TLS ofrecidas al upstream. Vacío mantiene el valor por defecto de NGINX.                                               |
| `GRPC_SSL_CIPHERS`                      |                | multisite | no       | **Cifrados SSL del upstream:** Cadena de cifrados ofrecida al upstream. Vacío mantiene el valor por defecto de NGINX.                                             |
| `GRPC_NEXT_UPSTREAM`                    |                | multisite | sí       | **Condiciones de siguiente upstream:** Valor para `grpc_next_upstream`.                                                                                           |
| `GRPC_NEXT_UPSTREAM_TIMEOUT`            |                | multisite | sí       | **Timeout de siguiente upstream:** Valor para `grpc_next_upstream_timeout`.                                                                                       |
| `GRPC_NEXT_UPSTREAM_TRIES`              |                | multisite | sí       | **Intentos de siguiente upstream:** Valor para `grpc_next_upstream_tries`.                                                                                        |
| `GRPC_AUTH_REQUEST`                     |                | multisite | sí       | **Auth request:** Valor para `auth_request`, para autenticar mediante un proveedor externo.                                                                       |
| `GRPC_AUTH_REQUEST_SIGNIN_URL`          |                | multisite | sí       | **URL de inicio de sesión del auth request:** Destino de redirección cuando el auth request devuelve 401.                                                         |
| `GRPC_AUTH_REQUEST_SET`                 |                | multisite | sí       | **Auth request set:** Lista separada por punto y coma de valores `auth_request_set`.                                                                              |
| `GRPC_INCLUDES`                         |                | multisite | sí       | **Includes adicionales:** Archivos `include` separados por espacios dentro del bloque gRPC `location`.                                                            |
| `GRPC_MAX_CLIENT_SIZE`                  |                | multisite | sí       | **Tamaño máximo del cuerpo:** Valor para `client_max_body_size` en esta location (`0` para ilimitado). Si está vacío se aplica el `MAX_CLIENT_SIZE` del servicio. |

!!! tip "TLS mutuo hacia el upstream"
    Hay que proporcionar el certificado cliente y su clave, y la clave no debe estar cifrada. El scheduler valida el par, lo cachea y lo distribuye a las instancias; si no valida, las directivas de certificado simplemente no se generan. Una CRL solo se aplica mientras la verificación del upstream está activa.

!!! warning "ModSecurity en ubicaciones gRPC"
    Actualmente ModSecurity se desactiva automáticamente dentro de los bloques gRPC `location` generados por este plugin, porque ModSecurity no soporta de forma fiable los patrones de tráfico gRPC.

!!! tip "Verificar el certificado del upstream"
    `GRPC_SSL_VERIFY` solo surte efecto cuando hay un bundle CA disponible. Proporciónalo con `GRPC_SSL_TRUSTED_CERTIFICATE` (una ruta legible por el scheduler) o `GRPC_SSL_TRUSTED_CERTIFICATE_DATA` (base64 o PEM en texto plano), y elige el origen con `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY`. El scheduler valida el bundle, lo cachea y lo distribuye a las instancias. Sin un bundle utilizable, la verificación permanece desactivada.

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
    GRPC_NEXT_UPSTREAM: "error timeout unavailable"
    GRPC_NEXT_UPSTREAM_TIMEOUT: "15s"
    GRPC_NEXT_UPSTREAM_TRIES: "3"
    ```

=== "Upstream TLS verificado"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpcs://internal-grpc.example.net:443"
    GRPC_URL: "/"
    GRPC_SSL_SNI: "yes"
    GRPC_SSL_SNI_NAME: "internal-grpc.example.net"
    GRPC_SSL_VERIFY: "yes"
    GRPC_SSL_TRUSTED_CERTIFICATE: "/etc/ssl/certs/ca-certificates.crt"
    GRPC_SSL_VERIFY_DEPTH: "2"
    ```

=== "Autenticación externa"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_AUTH_REQUEST: "/auth"
    GRPC_AUTH_REQUEST_SIGNIN_URL: "https://sso.example.com/login"
    GRPC_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_email $upstream_http_x_email"
    GRPC_HEADERS: "x-forwarded-user $auth_user"
    ```
