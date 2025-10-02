El complemento CORS habilita el Intercambio de Recursos de Origen Cruzado para su sitio web, permitiendo un acceso controlado a sus recursos desde diferentes dominios. Esta característica le ayuda a compartir su contenido de forma segura con sitios web de terceros de confianza, manteniendo la seguridad al definir explícitamente qué orígenes, métodos y encabezados están permitidos.

**Cómo funciona:**

1.  Cuando un navegador realiza una solicitud de origen cruzado a su sitio web, primero envía una solicitud de comprobación previa (preflight) con el método `OPTIONS`.
2.  BunkerWeb comprueba si el origen solicitante está permitido según su configuración.
3.  Si está permitido, BunkerWeb responde con los encabezados CORS apropiados que definen lo que el sitio solicitante puede hacer.
4.  Para los orígenes no permitidos, la solicitud puede ser denegada por completo o servida sin los encabezados CORS.
5.  Se pueden configurar políticas adicionales de origen cruzado, como [COEP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Embedder-Policy), [COOP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Opener-Policy) y [CORP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Resource-Policy), para mejorar aún más la seguridad.

### Cómo usar

Siga estos pasos para configurar y usar la función CORS:

1.  **Habilite la función:** La función CORS está deshabilitada por defecto. Establezca el ajuste `USE_CORS` en `yes` para habilitarla.
2.  **Configure los orígenes permitidos:** Especifique qué dominios pueden acceder a sus recursos utilizando el ajuste `CORS_ALLOW_ORIGIN`.
3.  **Establezca los métodos permitidos:** Defina qué métodos HTTP están permitidos para las solicitudes de origen cruzado con `CORS_ALLOW_METHODS`.
4.  **Configure los encabezados permitidos:** Especifique qué encabezados se pueden usar en las solicitudes con `CORS_ALLOW_HEADERS`.
5.  **Controle las credenciales:** Decida si las solicitudes de origen cruzado pueden incluir credenciales utilizando `CORS_ALLOW_CREDENTIALS`.

### Ajustes de Configuración

| Ajuste                         | Valor por defecto                                                                    | Contexto  | Múltiple | Descripción                                                                                                                                                |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CORS`                     | `no`                                                                                 | multisite | no       | **Habilitar CORS:** Establezca en `yes` para habilitar el Intercambio de Recursos de Origen Cruzado.                                                       |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | no       | **Orígenes Permitidos:** Expresión regular PCRE que representa los orígenes permitidos; use `*` para cualquier origen, o `self` solo para el mismo origen. |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | no       | **Métodos Permitidos:** Métodos HTTP que se pueden usar en solicitudes de origen cruzado.                                                                  |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | no       | **Encabezados Permitidos:** Encabezados HTTP que se pueden usar en solicitudes de origen cruzado.                                                          |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | no       | **Permitir Credenciales:** Establezca en `yes` para permitir credenciales (cookies, autenticación HTTP) en solicitudes CORS.                               |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | no       | **Encabezados Expuestos:** Encabezados HTTP a los que los navegadores pueden acceder desde respuestas de origen cruzado.                                   |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | no       | **Cross-Origin-Opener-Policy:** Controla la comunicación entre contextos de navegación.                                                                    |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | no       | **Cross-Origin-Embedder-Policy:** Controla si un documento puede cargar recursos de otros orígenes.                                                        |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | no       | **Cross-Origin-Resource-Policy:** Controla qué sitios web pueden incrustar sus recursos.                                                                   |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | no       | **Duración de la Caché de Preflight:** Cuánto tiempo (en segundos) los navegadores deben almacenar en caché la respuesta de preflight.                     |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | no       | **Denegar Orígenes No Autorizados:** Cuando es `yes`, las solicitudes de orígenes no autorizados se deniegan con un código de error.                       |

!!! tip "Optimizando las Solicitudes de Preflight"
El ajuste `CORS_MAX_AGE` determina cuánto tiempo los navegadores almacenarán en caché los resultados de una solicitud de preflight. Establecer esto en un valor más alto (como el predeterminado de 86400 segundos/24 horas) reduce el número de solicitudes de preflight, mejorando el rendimiento para los recursos a los que se accede con frecuencia.

!!! warning "Consideraciones de Seguridad"
Tenga cuidado al establecer `CORS_ALLOW_ORIGIN` en `*` (todos los orígenes) o `CORS_ALLOW_CREDENTIALS` en `yes` porque estas configuraciones pueden introducir riesgos de seguridad si no se gestionan adecuadamente. Generalmente es más seguro enumerar explícitamente los orígenes de confianza y limitar los métodos y encabezados permitidos.

### Configuraciones de Ejemplo

Aquí hay ejemplos de posibles valores para el ajuste `CORS_ALLOW_ORIGIN`, junto con su comportamiento:

- **`*`**: Permite solicitudes de todos los orígenes.
- **`self`**: Permite automáticamente solicitudes del mismo origen que el `server_name` configurado.
- **`^https://www\.example\.com$`**: Permite solicitudes solo de `https://www.example.com`.
- **`^https://.+\.example\.com$`**: Permite solicitudes de cualquier subdominio que termine en `.example.com`.
- **`^https://(www\.example1\.com|www\.example2\.com)$`**: Permite solicitudes de `https://www.example1.com` o `https://www.example2.com`.
- **`^https?://www\.example\.com$`**: Permite solicitudes tanto de `https://www.example.com` como de `http://www.example.com`.

=== "Configuración Básica"

    Una configuración simple que permite solicitudes de origen cruzado desde el mismo dominio:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "self"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Configuración de API Pública"

    Configuración para una API pública que necesita ser accesible desde cualquier origen:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "*"
    CORS_ALLOW_METHODS: "GET, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, X-API-Key"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "3600"
    CORS_DENY_REQUEST: "no"
    ```

=== "Múltiples Dominios de Confianza"

    Configuración para permitir múltiples dominios específicos con un único patrón de expresión regular PCRE:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(app|api|dashboard)\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, DELETE, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Requested-With"
    CORS_ALLOW_CREDENTIALS: "yes"
    CORS_EXPOSE_HEADERS: "Content-Length, Content-Range, X-RateLimit-Remaining"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Comodín de Subdominio"

    Configuración que permite todos los subdominios de un dominio principal utilizando un patrón de expresión regular PCRE:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://.*\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Múltiples Patrones de Dominio"

    Configuración que permite solicitudes de múltiples patrones de dominio con alternancia:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(.*\\.example\\.com|.*\\.trusted-partner\\.org|api\\.third-party\\.net)$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Custom-Header"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```
