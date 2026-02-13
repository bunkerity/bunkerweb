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

| Ajuste                       | Predeterminado | Contexto  | Múltiple | Descripción                                                                                            |
| ---------------------------- | -------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------ |
| `USE_GRPC`                   | `no`           | multisite | no       | **Habilitar gRPC:** Pon `yes` para habilitar el proxy gRPC.                                            |
| `GRPC_HOST`                  |                | multisite | sí       | **Upstream gRPC:** Valor usado por `grpc_pass` (por ejemplo `grpc://service:50051` o `grpcs://...`).   |
| `GRPC_URL`                   | `/`            | multisite | sí       | **URL de location:** Ruta que se enviará al upstream gRPC.                                             |
| `GRPC_CUSTOM_HOST`           |                | multisite | no       | **Cabecera Host personalizada:** Sobrescribe la cabecera `Host` enviada al upstream.                   |
| `GRPC_HEADERS`               |                | multisite | sí       | **Cabeceras extra al upstream:** Lista separada por punto y coma de valores para `grpc_set_header`.    |
| `GRPC_HIDE_HEADERS`          |                | multisite | sí       | **Cabeceras de respuesta ocultas:** Lista separada por espacios de valores para `grpc_hide_header`.    |
| `GRPC_INTERCEPT_ERRORS`      | `yes`          | multisite | no       | **Interceptar errores:** Activa/desactiva `grpc_intercept_errors`.                                     |
| `GRPC_CONNECT_TIMEOUT`       | `60s`          | multisite | sí       | **Timeout de conexión:** Tiempo límite para conectar con el upstream.                                  |
| `GRPC_READ_TIMEOUT`          | `60s`          | multisite | sí       | **Timeout de lectura:** Tiempo límite para leer desde el upstream.                                     |
| `GRPC_SEND_TIMEOUT`          | `60s`          | multisite | sí       | **Timeout de envío:** Tiempo límite para enviar al upstream.                                           |
| `GRPC_SOCKET_KEEPALIVE`      | `off`          | multisite | sí       | **Keepalive de socket:** Activa/desactiva keepalive en sockets hacia upstream.                         |
| `GRPC_SSL_SNI`               | `no`           | multisite | no       | **SSL SNI:** Activa/desactiva SNI para upstreams TLS.                                                  |
| `GRPC_SSL_SNI_NAME`          |                | multisite | no       | **Nombre SSL SNI:** Nombre SNI que se enviará cuando `GRPC_SSL_SNI=yes`.                               |
| `GRPC_NEXT_UPSTREAM`         |                | multisite | sí       | **Condiciones de siguiente upstream:** Valor para `grpc_next_upstream`.                                |
| `GRPC_NEXT_UPSTREAM_TIMEOUT` |                | multisite | sí       | **Timeout de siguiente upstream:** Valor para `grpc_next_upstream_timeout`.                            |
| `GRPC_NEXT_UPSTREAM_TRIES`   |                | multisite | sí       | **Intentos de siguiente upstream:** Valor para `grpc_next_upstream_tries`.                             |
| `GRPC_INCLUDES`              |                | multisite | sí       | **Includes adicionales:** Archivos `include` separados por espacios dentro del bloque gRPC `location`. |

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
    GRPC_NEXT_UPSTREAM: "error timeout unavailable"
    GRPC_NEXT_UPSTREAM_TIMEOUT: "15s"
    GRPC_NEXT_UPSTREAM_TRIES: "3"
    ```
