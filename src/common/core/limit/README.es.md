El complemento de Límite en BunkerWeb proporciona capacidades robustas para aplicar políticas de limitación en su sitio web, asegurando un uso justo y protegiendo sus recursos del abuso, ataques de denegación de servicio y consumo excesivo de recursos. Estas políticas incluyen:

- **Número de conexiones por dirección IP** (soporte para STREAM :white_check_mark:)
- **Número de solicitudes por dirección IP y URL dentro de un período de tiempo específico** (soporte para STREAM :x:)

### Cómo funciona

1.  **Limitación de Tasa de Solicitudes:** Rastrea el número de solicitudes de cada dirección IP del cliente a URL específicas. Si un cliente excede el límite de tasa configurado, las solicitudes posteriores son denegadas temporalmente.
2.  **Limitación de Conexiones:** Monitorea y restringe el número de conexiones concurrentes de cada dirección IP del cliente. Se pueden aplicar diferentes límites de conexión según el protocolo utilizado (HTTP/1, HTTP/2, HTTP/3 o stream).
3.  En ambos casos, los clientes que exceden los límites definidos reciben un código de estado HTTP **"429 - Demasiadas Solicitudes"**, lo que ayuda a prevenir la sobrecarga del servidor.

### Pasos para usar

1.  **Habilitar la Limitación de Tasa de Solicitudes:** Use `USE_LIMIT_REQ` para habilitar la limitación de tasa de solicitudes y defina patrones de URL junto con sus correspondientes límites de tasa.
2.  **Habilitar la Limitación de Conexiones:** Use `USE_LIMIT_CONN` para habilitar la limitación de conexiones y establezca el número máximo de conexiones concurrentes para diferentes protocolos.
3.  **Aplicar Control Granular:** Cree múltiples reglas de límite de tasa para diferentes URL para proporcionar diferentes niveles de protección en su sitio.
4.  **Monitorear la Efectividad:** Use la [interfaz de usuario web](web-ui.md) para ver estadísticas sobre las solicitudes y conexiones limitadas.

### Ajustes de Configuración

=== "Limitación de Tasa de Solicitudes"

    | Ajuste           | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                                                       |
    | ---------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_LIMIT_REQ`  | `yes`             | multisite | no       | **Habilitar Limitación de Solicitudes:** Establezca en `yes` para habilitar la función de limitación de tasa de solicitudes.                                                      |
    | `LIMIT_REQ_URL`  | `/`               | multisite | yes      | **Patrón de URL:** Patrón de URL (expresión regular PCRE) al que se aplicará el límite de tasa; use `/` para aplicar a todas las solicitudes.                                     |
    | `LIMIT_REQ_RATE` | `2r/s`            | multisite | yes      | **Límite de Tasa:** Tasa máxima de solicitudes en el formato `Nr/t`, donde N es el número de solicitudes y t es la unidad de tiempo: s (segundo), m (minuto), h (hora) o d (día). |

    !!! tip "Formato de Limitación de Tasa"
        El formato del límite de tasa se especifica como `Nr/t` donde:

        -   `N` es el número de solicitudes permitidas
        -   `r` es una 'r' literal (para 'solicitudes')
        -   `/` es una barra literal
        -   `t` es la unidad de tiempo: `s` (segundo), `m` (minuto), `h` (hora) o `d` (día)

        Por ejemplo, `5r/m` significa que se permiten 5 solicitudes por minuto desde cada dirección IP.

=== "Limitación de Conexiones"

    | Ajuste                  | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                        |
    | ----------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------ |
    | `USE_LIMIT_CONN`        | `yes`             | multisite | no       | **Habilitar Limitación de Conexiones:** Establezca en `yes` para habilitar la función de limitación de conexiones. |
    | `LIMIT_CONN_MAX_HTTP1`  | `10`              | multisite | no       | **Conexiones HTTP/1.X:** Número máximo de conexiones HTTP/1.X concurrentes por dirección IP.                       |
    | `LIMIT_CONN_MAX_HTTP2`  | `100`             | multisite | no       | **Flujos HTTP/2:** Número máximo de flujos HTTP/2 concurrentes por dirección IP.                                   |
    | `LIMIT_CONN_MAX_HTTP3`  | `100`             | multisite | no       | **Flujos HTTP/3:** Número máximo de flujos HTTP/3 concurrentes por dirección IP.                                   |
    | `LIMIT_CONN_MAX_STREAM` | `10`              | multisite | no       | **Conexiones de Flujo:** Número máximo de conexiones de flujo concurrentes por dirección IP.                       |

!!! info "Limitación de Conexiones vs. Solicitudes" - **La limitación de conexiones** restringe el número de conexiones simultáneas que una sola dirección IP puede mantener. - **La limitación de tasa de solicitudes** restringe el número de solicitudes que una dirección IP puede hacer dentro de un período de tiempo definido.

    El uso de ambos métodos proporciona una protección completa contra varios tipos de abuso.

!!! warning "Estableciendo Límites Apropiados"
Establecer límites demasiado restrictivos puede afectar a los usuarios legítimos, especialmente para HTTP/2 y HTTP/3, donde los navegadores a menudo usan múltiples flujos. Los valores predeterminados están equilibrados para la mayoría de los casos de uso, pero considere ajustarlos según las necesidades de su aplicación y el comportamiento del usuario.

### Configuraciones de Ejemplo

=== "Protección Básica"

    Una configuración simple que utiliza los ajustes predeterminados para proteger todo su sitio:

    ```yaml
    USE_LIMIT_REQ: "yes"
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "2r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "Protegiendo Puntos Finales Específicos"

    Configuración con diferentes límites de tasa para varios puntos finales:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Regla predeterminada para todas las solicitudes
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "10r/s"

    # Límite más estricto para la página de inicio de sesión
    LIMIT_REQ_URL_2: "^/login"
    LIMIT_REQ_RATE_2: "1r/s"

    # Límite más estricto para la API
    LIMIT_REQ_URL_3: "^/api/"
    LIMIT_REQ_RATE_3: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "Configuración para un Sitio de Alto Tráfico"

    Configuración ajustada para sitios de alto tráfico con límites más permisivos:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Límite general
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "30r/s"

    # Protección del área de administración
    LIMIT_REQ_URL_2: "^/admin/"
    LIMIT_REQ_RATE_2: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "50"
    LIMIT_CONN_MAX_HTTP2: "200"
    LIMIT_CONN_MAX_HTTP3: "200"
    LIMIT_CONN_MAX_STREAM: "30"
    ```

=== "Configuración para un Servidor API"

    Configuración optimizada para un servidor API con límites de tasa expresados en solicitudes por minuto:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Puntos finales de la API pública
    LIMIT_REQ_URL: "^/api/public/"
    LIMIT_REQ_RATE: "120r/m"

    # Puntos finales de la API privada
    LIMIT_REQ_URL_2: "^/api/private/"
    LIMIT_REQ_RATE_2: "300r/m"

    # Punto final de autenticación
    LIMIT_REQ_URL_3: "^/api/auth"
    LIMIT_REQ_RATE_3: "10r/m"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "20"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "20"
    ```
