Las cabeceras juegan un papel crucial en la seguridad HTTP. El complemento de Cabeceras proporciona una gestión robusta tanto de cabeceras HTTP estándar como personalizadas, mejorando la seguridad y la funcionalidad. Aplica dinámicamente medidas de seguridad, como [HSTS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Strict-Transport-Security), [CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy) (incluido un modo de informe), y la inyección de cabeceras personalizadas, al tiempo que previene la fuga de información.

**Cómo funciona**

1.  Cuando un cliente solicita contenido de su sitio web, BunkerWeb procesa las cabeceras de la respuesta.
2.  Se aplican las cabeceras de seguridad de acuerdo con su configuración.
3.  Se pueden añadir cabeceras personalizadas para proporcionar información o funcionalidad adicional a los clientes.
4.  Las cabeceras no deseadas que podrían revelar información del servidor se eliminan automáticamente.
5.  Las cookies se modifican para incluir indicadores de seguridad apropiados según sus ajustes.
6.  Las cabeceras de los servidores de origen (upstream) se pueden preservar selectivamente cuando sea necesario.

### Cómo usar

Siga estos pasos para configurar y usar la función de Cabeceras:

1.  **Configure las cabeceras de seguridad:** Establezca valores para las cabeceras comunes.
2.  **Añada cabeceras personalizadas:** Defina cualquier cabecera personalizada usando el ajuste `CUSTOM_HEADER`.
3.  **Elimine las cabeceras no deseadas:** Use `REMOVE_HEADERS` para asegurarse de que se eliminen las cabeceras que podrían exponer detalles del servidor.
4.  **Establezca la seguridad de las cookies:** Habilite una seguridad robusta para las cookies configurando `COOKIE_FLAGS` y estableciendo `COOKIE_AUTO_SECURE_FLAG` en `yes` para que el indicador `Secure` se añada automáticamente en las conexiones HTTPS.
5.  **Preserve las cabeceras de origen:** Especifique qué cabeceras de origen conservar usando `KEEP_UPSTREAM_HEADERS`.
6.  **Aproveche la aplicación condicional de cabeceras:** Si desea probar políticas sin interrupciones, habilite el modo [CSP Report-Only](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy-Report-Only) a través de `CONTENT_SECURITY_POLICY_REPORT_ONLY`.

### Guía de Configuración

=== "Cabeceras de Seguridad"

    **Descripción General**

    Las cabeceras de seguridad imponen una comunicación segura, restringen la carga de recursos y previenen ataques como el clickjacking y la inyección. Unas cabeceras configuradas correctamente crean una capa defensiva robusta para su sitio web.

    !!! success "Beneficios de las Cabeceras de Seguridad"
        - **HSTS:** Asegura que todas las conexiones estén cifradas, protegiendo contra ataques de degradación de protocolo.
        - **CSP:** Previene la ejecución de scripts maliciosos, reduciendo el riesgo de ataques XSS.
        - **X-Frame-Options:** Bloquea los intentos de clickjacking controlando la incrustación de iframes.
        - **Referrer Policy:** Limita la fuga de información sensible a través de las cabeceras de referencia.

| Ajuste                                | Valor por defecto                                                                                   | Contexto  | Múltiple | Descripción                                                                                                                                                     |
| ------------------------------------- | --------------------------------------------------------------------------------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `STRICT_TRANSPORT_SECURITY`           | `max-age=63072000; includeSubDomains; preload`                                                      | multisite | no       | **HSTS:** Impone conexiones HTTPS seguras, reduciendo los riesgos de ataques de intermediario (man-in-the-middle).                                              |
| `CONTENT_SECURITY_POLICY`             | `object-src 'none'; form-action 'self'; frame-ancestors 'self';`                                    | multisite | no       | **CSP:** Restringe la carga de recursos a fuentes de confianza, mitigando los ataques de cross-site scripting e inyección de datos.                             |
| `CONTENT_SECURITY_POLICY_REPORT_ONLY` | `no`                                                                                                | multisite | no       | **Modo de Informe CSP:** Informa de las violaciones sin bloquear el contenido, ayudando a probar las políticas de seguridad mientras se capturan los registros. |
| `X_FRAME_OPTIONS`                     | `SAMEORIGIN`                                                                                        | multisite | no       | **X-Frame-Options:** Previene el clickjacking controlando si su sitio puede ser enmarcado (framed).                                                             |
| `X_CONTENT_TYPE_OPTIONS`              | `nosniff`                                                                                           | multisite | no       | **X-Content-Type-Options:** Evita que los navegadores realicen "MIME-sniffing", protegiendo contra ataques de descarga no autorizada (drive-by download).       |
| `X_DNS_PREFETCH_CONTROL`              | `off`                                                                                               | multisite | no       | **X-DNS-Prefetch-Control:** Regula la captación previa de DNS para reducir las solicitudes de red no intencionadas y mejorar la privacidad.                     |
| `REFERRER_POLICY`                     | `strict-origin-when-cross-origin`                                                                   | multisite | no       | **Política de Referencia:** Controla la cantidad de información de referencia enviada, salvaguardando la privacidad del usuario.                                |
| `PERMISSIONS_POLICY`                  | `accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), ...` | multisite | no       | **Política de Permisos:** Restringe el acceso a las funciones del navegador, reduciendo los posibles vectores de ataque.                                        |
| `KEEP_UPSTREAM_HEADERS`               | `Content-Security-Policy Permissions-Policy X-Frame-Options`                                        | multisite | no       | **Conservar Cabeceras:** Preserva las cabeceras de origen seleccionadas, ayudando a la integración con sistemas heredados mientras se mantiene la seguridad.    |

    !!! tip "Mejores Prácticas"
        - Revise y actualice regularmente sus cabeceras de seguridad para alinearse con los estándares de seguridad en evolución.
        - Use herramientas como [Mozilla Observatory](https://observatory.mozilla.org/) para validar la configuración de sus cabeceras.
        - Pruebe el CSP en modo `Report-Only` antes de aplicarlo para evitar romper la funcionalidad.

=== "Configuración de Cookies"

    **Descripción General**

    Una configuración adecuada de las cookies garantiza sesiones de usuario seguras al prevenir el secuestro, la fijación y el cross-site scripting. Las cookies seguras mantienen la integridad de la sesión sobre HTTPS y mejoran la protección general de los datos del usuario.

    !!! success "Beneficios de las Cookies Seguras"
        - **Indicador HttpOnly:** Evita que los scripts del lado del cliente accedan a las cookies, mitigando los riesgos de XSS.
        - **Indicador SameSite:** Reduce los ataques CSRF al restringir el uso de cookies entre diferentes orígenes.
        - **Indicador Secure:** Asegura que las cookies se transmitan solo a través de conexiones HTTPS cifradas.

| Ajuste                    | Valor por defecto         | Contexto  | Múltiple | Descripción                                                                                                                                                                               |
| ------------------------- | ------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `COOKIE_FLAGS`            | `* HttpOnly SameSite=Lax` | multisite | yes      | **Indicadores de Cookie:** Añade automáticamente indicadores de seguridad como HttpOnly y SameSite, protegiendo las cookies del acceso de scripts del lado del cliente y de ataques CSRF. |
| `COOKIE_AUTO_SECURE_FLAG` | `yes`                     | multisite | no       | **Indicador Secure Automático:** Asegura que las cookies solo se envíen a través de conexiones HTTPS seguras añadiendo automáticamente el indicador Secure.                               |

    !!! tip "Mejores Prácticas"
        - Use `SameSite=Strict` para cookies sensibles para prevenir el acceso entre orígenes.
        - Audite regularmente la configuración de sus cookies para asegurar el cumplimiento con las regulaciones de seguridad y privacidad.
        - Evite establecer cookies sin el indicador `Secure` en entornos de producción.

=== "Cabeceras Personalizadas"

    **Descripción General**

    Las cabeceras personalizadas le permiten añadir cabeceras HTTP específicas para cumplir con los requisitos de la aplicación o el rendimiento. Ofrecen flexibilidad pero deben configurarse con cuidado para evitar exponer detalles sensibles del servidor.

    !!! success "Beneficios de las Cabeceras Personalizadas"
        - Mejore la seguridad eliminando cabeceras innecesarias que puedan filtrar detalles del servidor.
        - Añada cabeceras específicas de la aplicación para mejorar la funcionalidad o la depuración.

| Ajuste           | Valor por defecto                                                                    | Contexto  | Múltiple | Descripción                                                                                                                                                                                           |
| ---------------- | ------------------------------------------------------------------------------------ | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CUSTOM_HEADER`  |                                                                                      | multisite | yes      | **Cabecera Personalizada:** Proporciona un medio para añadir cabeceras definidas por el usuario en el formato `NombreCabecera: ValorCabecera` para mejoras especializadas de seguridad o rendimiento. |
| `REMOVE_HEADERS` | `Server Expect-CT X-Powered-By X-AspNet-Version X-AspNetMvc-Version Public-Key-Pins` | multisite | no       | **Eliminar Cabeceras:** Especifica las cabeceras a eliminar, disminuyendo la posibilidad de exponer detalles internos del servidor y vulnerabilidades conocidas.                                      |

    !!! warning "Consideraciones de Seguridad"
        - Evite exponer información sensible a través de cabeceras personalizadas.
        - Revise y actualice regularmente las cabeceras personalizadas para alinearlas con los requisitos de su aplicación.

    !!! tip "Mejores Prácticas"
        - Use `REMOVE_HEADERS` para eliminar cabeceras como `Server` y `X-Powered-By` para reducir los riesgos de "fingerprinting" (identificación del servidor).
        - Pruebe las cabeceras personalizadas en un entorno de preproducción (staging) antes de desplegarlas en producción.

### Configuraciones de Ejemplo

=== "Cabeceras de Seguridad Básicas"

    Una configuración estándar con cabeceras de seguridad esenciales:

    ```yaml
    STRICT_TRANSPORT_SECURITY: "max-age=63072000; includeSubDomains; preload"
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'self'"
    X_FRAME_OPTIONS: "SAMEORIGIN"
    X_CONTENT_TYPE_OPTIONS: "nosniff"
    REFERRER_POLICY: "strict-origin-when-cross-origin"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version"
    ```

=== "Seguridad de Cookies Mejorada"

    Configuración con ajustes robustos de seguridad para cookies:

    ```yaml
    COOKIE_FLAGS: "* HttpOnly SameSite=Strict"
    COOKIE_FLAGS_2: "session_cookie Secure HttpOnly SameSite=Strict"
    COOKIE_FLAGS_3: "auth_cookie Secure HttpOnly SameSite=Strict Max-Age=3600"
    COOKIE_AUTO_SECURE_FLAG: "yes"
    ```

=== "Cabeceras Personalizadas para API"

    Configuración para un servicio de API con cabeceras personalizadas:

    ```yaml
    CUSTOM_HEADER: "API-Version: 1.2.3"
    CUSTOM_HEADER_2: "Access-Control-Max-Age: 86400"
    CONTENT_SECURITY_POLICY: "default-src 'none'; frame-ancestors 'none'"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version X-Runtime"
    ```

=== "Content Security Policy - Modo de Informe"

    Configuración para probar CSP sin romper la funcionalidad:

    ```yaml
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self' https://trusted-cdn.example.com; img-src 'self' data: https://*.example.com; style-src 'self' 'unsafe-inline' https://trusted-cdn.example.com; connect-src 'self' https://api.example.com; object-src 'none'; frame-ancestors 'self'; form-action 'self'; base-uri 'self'; report-uri https://example.com/csp-reports"
    CONTENT_SECURITY_POLICY_REPORT_ONLY: "yes"
    ```
