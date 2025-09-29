Los atacantes suelen utilizar herramientas automatizadas (bots) para intentar explotar su sitio web. Para protegerse contra esto, BunkerWeb incluye una función "Antibot" que desafía a los usuarios a demostrar que son humanos. Si un usuario completa con éxito el desafío, se le concede acceso a su sitio web. Esta función está desactivada por defecto.

**Cómo funciona:**

1.  Cuando un usuario visita su sitio, BunkerWeb comprueba si ya ha superado el desafío antibot.
2.  Si no, el usuario es redirigido a una página de desafío.
3.  El usuario debe completar el desafío (por ejemplo, resolver un CAPTCHA, ejecutar JavaScript).
4.  Si el desafío tiene éxito, el usuario es redirigido de nuevo a la página que intentaba visitar originalmente y puede navegar por su sitio web con normalidad.

### Cómo usar

Siga estos pasos para habilitar y configurar la función Antibot:

1.  **Elija un tipo de desafío:** Decida qué tipo de desafío antibot usar (p. ej., [captcha](#__tabbed_3_3), [hcaptcha](#__tabbed_3_5), [javascript](#__tabbed_3_2)).
2.  **Habilite la función:** Establezca la configuración `USE_ANTIBOT` en el tipo de desafío elegido en su configuración de BunkerWeb.
3.  **Configure los ajustes:** Ajuste las otras configuraciones `ANTIBOT_*` según sea necesario. Para reCAPTCHA, hCaptcha, Turnstile y mCaptcha, debe crear una cuenta con el servicio respectivo y obtener claves de API.
4.  **Importante:** Asegúrese de que el `ANTIBOT_URI` sea una URL única en su sitio que no esté en uso.

!!! important "Acerca de la configuración `ANTIBOT_URI`"
Asegúrese de que el `ANTIBOT_URI` sea una URL única en su sitio que no esté en uso.

!!! warning "Configuración de sesión en entornos de clúster"
La función antibot utiliza cookies para rastrear si un usuario ha completado el desafío. Si está ejecutando BunkerWeb en un entorno de clúster (múltiples instancias de BunkerWeb), **debe** configurar la gestión de sesiones correctamente. Esto implica establecer las configuraciones `SESSIONS_SECRET` y `SESSIONS_NAME` con los **mismos valores** en todas las instancias de BunkerWeb. Si no lo hace, es posible que a los usuarios se les pida repetidamente que completen el desafío antibot. Puede encontrar más información sobre la configuración de sesiones [aquí](#sessions).

### Configuraciones comunes

Las siguientes configuraciones son compartidas por todos los mecanismos de desafío:

| Configuración          | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                                            |
| ---------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_URI`          | `/challenge`      | multisite | no       | **URL del desafío:** La URL a la que se redirigirá a los usuarios para completar el desafío. Asegúrese de que esta URL no se utilice para nada más en su sitio.        |
| `ANTIBOT_TIME_RESOLVE` | `60`              | multisite | no       | **Límite de tiempo del desafío:** El tiempo máximo (en segundos) que un usuario tiene para completar el desafío. Después de este tiempo, se generará un nuevo desafío. |
| `ANTIBOT_TIME_VALID`   | `86400`           | multisite | no       | **Validez del desafío:** Cuánto tiempo (en segundos) es válido un desafío completado. Después de este tiempo, los usuarios tendrán que resolver un nuevo desafío.      |

### Excluir tráfico de los desafíos

BunkerWeb le permite especificar ciertos usuarios, IP o solicitudes que deben omitir por completo el desafío antibot. Esto es útil para incluir en la lista blanca servicios de confianza, redes internas o páginas específicas que siempre deben ser accesibles sin desafío:

| Configuración               | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                            |
| --------------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_IGNORE_URI`        |                   | multisite | no       | **URL excluidas:** Lista de patrones regex de URI separados por espacios que deben omitir el desafío.                  |
| `ANTIBOT_IGNORE_IP`         |                   | multisite | no       | **IP excluidas:** Lista de direcciones IP o rangos CIDR separados por espacios que deben omitir el desafío.            |
| `ANTIBOT_IGNORE_RDNS`       |                   | multisite | no       | **DNS inverso excluido:** Lista de sufijos de DNS inverso separados por espacios que deben omitir el desafío.          |
| `ANTIBOT_RDNS_GLOBAL`       | `yes`             | multisite | no       | **Solo IP globales:** Si se establece en `yes`, solo realiza comprobaciones de DNS inverso en direcciones IP públicas. |
| `ANTIBOT_IGNORE_ASN`        |                   | multisite | no       | **ASN excluidos:** Lista de números de ASN separados por espacios que deben omitir el desafío.                         |
| `ANTIBOT_IGNORE_USER_AGENT` |                   | multisite | no       | **User-Agents excluidos:** Lista de patrones regex de User-Agent separados por espacios que deben omitir el desafío.   |

**Ejemplos:**

- `ANTIBOT_IGNORE_URI: "^/api/ ^/webhook/ ^/assets/"`
  Esto excluirá del desafío antibot todas las URI que comiencen con `/api/`, `/webhook/` o `/assets/`.
- `ANTIBOT_IGNORE_IP: "192.168.1.0/24 10.0.0.1"`
  Esto excluirá del desafío antibot la red interna `192.168.1.0/24` y la IP específica `10.0.0.1`.
- `ANTIBOT_IGNORE_RDNS: ".googlebot.com .bingbot.com"`
  Esto excluirá del desafío antibot las solicitudes de hosts con DNS inverso que terminen en `googlebot.com` o `bingbot.com`.
- `ANTIBOT_IGNORE_ASN: "15169 8075"`
  Esto excluirá del desafío antibot las solicitudes de los ASN 15169 (Google) y 8075 (Microsoft).
- `ANTIBOT_IGNORE_USER_AGENT: "^Mozilla.+Chrome.+Safari"`
  Esto excluirá del desafío antibot las solicitudes con User-Agents que coincidan con el patrón regex especificado.

### Mecanismos de desafío compatibles

=== "Cookie"

    El desafío de Cookie es un mecanismo ligero que se basa en establecer una cookie en el navegador del usuario. Cuando un usuario accede al sitio, el servidor envía una cookie al cliente. En solicitudes posteriores, el servidor comprueba la presencia de esta cookie para verificar que el usuario es legítimo. Este método es simple y eficaz para la protección básica contra bots sin requerir interacción adicional del usuario.

    **Cómo funciona:**

    1.  El servidor genera una cookie única y la envía al cliente.
    2.  El cliente debe devolver la cookie en las solicitudes posteriores.
    3.  Si la cookie falta o no es válida, el usuario es redirigido a la página del desafío.

    **Ajustes de configuración:**

    | Configuración | Valor por defecto | Contexto  | Múltiple | Descripción                                                                        |
    | ------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`              | multisite | no       | **Habilitar Antibot:** Establezca en `cookie` para habilitar el desafío de Cookie. |

    Consulte los [Ajustes comunes](#configuraciones-comunes) para opciones de configuración adicionales.

=== "JavaScript"

    El desafío de JavaScript requiere que el cliente resuelva una tarea computacional usando JavaScript. Este mecanismo asegura que el cliente tenga JavaScript habilitado y pueda ejecutar el código requerido, lo cual está típicamente fuera de la capacidad de la mayoría de los bots.

    **Cómo funciona:**

    1.  El servidor envía un script de JavaScript al cliente.
    2.  El script realiza una tarea computacional (p. ej., hashing) y envía el resultado de vuelta al servidor.
    3.  El servidor verifica el resultado para confirmar la legitimidad del cliente.

    **Características principales:**

    *   El desafío genera dinámicamente una tarea única para cada cliente.
    *   La tarea computacional implica hashing con condiciones específicas (p. ej., encontrar un hash con un prefijo determinado).

    **Ajustes de configuración:**

    | Configuración | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                |
    | ------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------ |
    | `USE_ANTIBOT` | `no`              | multisite | no       | **Habilitar Antibot:** Establezca en `javascript` para habilitar el desafío de JavaScript. |

    Consulte los [Ajustes comunes](#configuraciones-comunes) para opciones de configuración adicionales.

=== "Captcha"

    El desafío de Captcha es un mecanismo casero que genera desafíos basados en imágenes alojados completamente dentro de su entorno de BunkerWeb. Pone a prueba la capacidad de los usuarios para reconocer e interpretar caracteres aleatorios, asegurando que los bots automatizados sean bloqueados eficazmente sin depender de servicios externos.

    **Cómo funciona:**

    1.  El servidor genera una imagen CAPTCHA que contiene caracteres aleatorios.
    2.  El usuario debe introducir los caracteres que se muestran en la imagen en un campo de texto.
    3.  El servidor valida la entrada del usuario con el CAPTCHA generado.

    **Características principales:**

    *   Totalmente autoalojado, eliminando la necesidad de API de terceros.
    *   Los desafíos generados dinámicamente aseguran la unicidad para cada sesión de usuario.
    *   Utiliza un conjunto de caracteres personalizable para la generación de CAPTCHA.

    **Caracteres admitidos:**

    El sistema CAPTCHA admite los siguientes tipos de caracteres:

    *   **Letras:** Todas las letras minúsculas (a-z) y mayúsculas (A-Z)
    *   **Números:** 2, 3, 4, 5, 6, 7, 8, 9 (excluye 0 y 1 para evitar confusiones)
    *   **Caracteres especiales:** ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„```

    Para tener el conjunto completo de caracteres admitidos, consulte el [mapa de caracteres de la fuente](https://www.dafont.com/moms-typewriter.charmap?back=theme) utilizada para el CAPTCHA.

    **Ajustes de configuración:**

    | Configuración              | Valor por defecto                                      | Contexto  | Múltiple | Descripción                                                                                                                                                                                                                               |
    | -------------------------- | ------------------------------------------------------ | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                                                   | multisite | no       | **Habilitar Antibot:** Establezca en `captcha` para habilitar el desafío de Captcha.                                                                                                                                                      |
    | `ANTIBOT_CAPTCHA_ALPHABET` | `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ` | multisite | no       | **Alfabeto del Captcha:** Una cadena de caracteres para usar en la generación del CAPTCHA. Caracteres admitidos: todas las letras (a-z, A-Z), números 2-9 (excluye 0 y 1) y caracteres especiales: ``+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„`` |

    Consulte los [Ajustes comunes](#configuraciones-comunes) para opciones de configuración adicionales.

=== "reCAPTCHA"

    Cuando está habilitado, reCAPTCHA se ejecuta en segundo plano (v3) para asignar una puntuación basada en el comportamiento del usuario. Una puntuación inferior al umbral configurado solicitará una verificación adicional o bloqueará la solicitud. Para los desafíos visibles (v2), los usuarios deben interactuar con el widget de reCAPTCHA antes de continuar.

    Ahora hay dos formas de integrar reCAPTCHA:
    *   La versión clásica (claves de sitio/secretas, punto final de verificación v2/v3)
    *   La nueva versión que utiliza Google Cloud (ID del proyecto + clave de API). La versión clásica sigue disponible y se puede activar con `ANTIBOT_RECAPTCHA_CLASSIC`.

    Para la versión clásica, obtenga sus claves de sitio y secretas en la [consola de administración de Google reCAPTCHA](https://www.google.com/recaptcha/admin).
    Para la nueva versión, cree una clave de reCAPTCHA en su proyecto de Google Cloud y use el ID del proyecto y una clave de API (consulte la [consola de reCAPTCHA de Google Cloud](https://console.cloud.google.com/security/recaptcha)). Todavía se requiere una clave de sitio.

    **Ajustes de configuración:**

    | Configuración                  | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                |
    | ------------------------------ | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`                  | `no`              | multisite | no       | Habilitar antibot; establezca en `recaptcha` para habilitar reCAPTCHA.                                                     |
    | `ANTIBOT_RECAPTCHA_CLASSIC`    | `yes`             | multisite | no       | Usar reCAPTCHA clásico. Establezca en `no` para usar la nueva versión basada en Google Cloud.                              |
    | `ANTIBOT_RECAPTCHA_SITEKEY`    |                   | multisite | no       | Clave de sitio de reCAPTCHA. Requerida para las versiones clásica y nueva.                                                 |
    | `ANTIBOT_RECAPTCHA_SECRET`     |                   | multisite | no       | Clave secreta de reCAPTCHA. Requerida solo para la versión clásica.                                                        |
    | `ANTIBOT_RECAPTCHA_PROJECT_ID` |                   | multisite | no       | ID del proyecto de Google Cloud. Requerido solo para la nueva versión.                                                     |
    | `ANTIBOT_RECAPTCHA_API_KEY`    |                   | multisite | no       | Clave de API de Google Cloud utilizada para llamar a la API de reCAPTCHA Enterprise. Requerida solo para la nueva versión. |
    | `ANTIBOT_RECAPTCHA_JA3`        |                   | multisite | no       | Huella digital JA3 TLS opcional para incluir en las evaluaciones de Enterprise.                                            |
    | `ANTIBOT_RECAPTCHA_JA4`        |                   | multisite | no       | Huella digital JA4 TLS opcional para incluir en las evaluaciones de Enterprise.                                            |
    | `ANTIBOT_RECAPTCHA_SCORE`      | `0.7`             | multisite | no       | Puntuación mínima requerida para pasar (se aplica tanto a la v3 clásica como a la nueva versión).                          |

    Consulte los [Ajustes comunes](#configuraciones-comunes) para opciones de configuración adicionales.

=== "hCaptcha"

    Cuando está habilitado, hCaptcha proporciona una alternativa eficaz a reCAPTCHA al verificar las interacciones del usuario sin depender de un mecanismo de puntuación. Desafía a los usuarios con una prueba simple e interactiva para confirmar su legitimidad.

    Para integrar hCaptcha con BunkerWeb, debe obtener las credenciales necesarias del panel de hCaptcha en [hCaptcha](https://www.hcaptcha.com). Estas credenciales incluyen una clave de sitio y una clave secreta.

    **Ajustes de configuración:**

    | Configuración              | Valor por defecto | Contexto  | Múltiple | Descripción                                                                             |
    | -------------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`              | multisite | no       | **Habilitar Antibot:** Establezca en `hcaptcha` para habilitar el desafío de hCaptcha.  |
    | `ANTIBOT_HCAPTCHA_SITEKEY` |                   | multisite | no       | **Clave del sitio de hCaptcha:** Su clave de sitio de hCaptcha (obtenerla de hCaptcha). |
    | `ANTIBOT_HCAPTCHA_SECRET`  |                   | multisite | no       | **Clave secreta de hCaptcha:** Su clave secreta de hCaptcha (obtenerla de hCaptcha).    |

    Consulte los [Ajustes comunes](#configuraciones-comunes) para opciones de configuración adicionales.

=== "Turnstile"

    Turnstile es un mecanismo de desafío moderno y respetuoso con la privacidad que aprovecha la tecnología de Cloudflare para detectar y bloquear el tráfico automatizado. Valida las interacciones del usuario de manera fluida y en segundo plano, reduciendo la fricción para los usuarios legítimos y desalentando eficazmente a los bots.

    Para integrar Turnstile con BunkerWeb, asegúrese de obtener las credenciales necesarias de [Cloudflare Turnstile](https://www.cloudflare.com/turnstile).

    **Ajustes de configuración:**

    | Configuración               | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                 |
    | --------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`               | `no`              | multisite | no       | **Habilitar Antibot:** Establezca en `turnstile` para habilitar el desafío Turnstile.       |
    | `ANTIBOT_TURNSTILE_SITEKEY` |                   | multisite | no       | **Clave del sitio de Turnstile:** Su clave de sitio de Turnstile (obtenerla de Cloudflare). |
    | `ANTIBOT_TURNSTILE_SECRET`  |                   | multisite | no       | **Clave secreta de Turnstile:** Su clave secreta de Turnstile (obtenerla de Cloudflare).    |

    Consulte los [Ajustes comunes](#configuraciones-comunes) para opciones de configuración adicionales.

=== "mCaptcha"

    mCaptcha es un mecanismo de desafío CAPTCHA alternativo que verifica la legitimidad de los usuarios presentando una prueba interactiva similar a otras soluciones antibot. Cuando está habilitado, desafía a los usuarios con un CAPTCHA proporcionado por mCaptcha, asegurando que solo los usuarios genuinos omitan las comprobaciones de seguridad automatizadas.

    mCaptcha está diseñado pensando en la privacidad. Es totalmente compatible con el GDPR, lo que garantiza que todos los datos del usuario involucrados en el proceso de desafío cumplan con estrictos estándares de protección de datos. Además, mCaptcha ofrece la flexibilidad de ser autoalojado, lo que permite a las organizaciones mantener un control total sobre sus datos e infraestructura. Esta capacidad de autoalojamiento no solo mejora la privacidad, sino que también optimiza el rendimiento y la personalización para adaptarse a las necesidades específicas de implementación.

    Para integrar mCaptcha con BunkerWeb, debe obtener las credenciales necesarias de la plataforma [mCaptcha](https://mcaptcha.org/) o de su propio proveedor. Estas credenciales incluyen una clave de sitio y una clave secreta para la verificación.

    **Ajustes de configuración:**

    | Configuración              | Valor por defecto           | Contexto  | Múltiple | Descripción                                                                             |
    | -------------------------- | --------------------------- | --------- | -------- | --------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                        | multisite | no       | **Habilitar Antibot:** Establezca en `mcaptcha` para habilitar el desafío mCaptcha.     |
    | `ANTIBOT_MCAPTCHA_SITEKEY` |                             | multisite | no       | **Clave del sitio de mCaptcha:** Su clave de sitio de mCaptcha (obtenerla de mCaptcha). |
    | `ANTIBOT_MCAPTCHA_SECRET`  |                             | multisite | no       | **Clave secreta de mCaptcha:** Su clave secreta de mCaptcha (obtenerla de mCaptcha).    |
    | `ANTIBOT_MCAPTCHA_URL`     | `https://demo.mcaptcha.org` | multisite | no       | **Dominio de mCaptcha:** El dominio a utilizar para el desafío mCaptcha.                |

    Consulte los [Ajustes comunes](#configuraciones-comunes) para opciones de configuración adicionales.

### Configuraciones de ejemplo

=== "Desafío de Cookie"

    Configuración de ejemplo para habilitar el desafío de Cookie:

    ```yaml
    USE_ANTIBOT: "cookie"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Desafío de JavaScript"

    Configuración de ejemplo para habilitar el desafío de JavaScript:

    ```yaml
    USE_ANTIBOT: "javascript"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Desafío de Captcha"

    Configuración de ejemplo para habilitar el desafío de Captcha:

    ```yaml
    USE_ANTIBOT: "captcha"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ANTIBOT_CAPTCHA_ALPHABET: "23456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ```

    Nota: El ejemplo anterior utiliza los números del 2 al 9 y todas las letras, que son los caracteres más utilizados para los desafíos CAPTCHA. Puede personalizar el alfabeto para incluir caracteres especiales según sea necesario.

=== "reCAPTCHA Clásico"

    Configuración de ejemplo para el reCAPTCHA clásico (claves de sitio/secretas):

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "yes"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "reCAPTCHA (nuevo)"

    Configuración de ejemplo para el nuevo reCAPTCHA basado en Google Cloud (ID del proyecto + clave de API):

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "no"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_PROJECT_ID: "your-gcp-project-id"
    ANTIBOT_RECAPTCHA_API_KEY: "your-gcp-api-key"
    # Huellas dactilares opcionales para mejorar las evaluaciones de Enterprise
    # ANTIBOT_RECAPTCHA_JA3: "<ja3-fingerprint>"
    # ANTIBOT_RECAPTCHA_JA4: "<ja4-fingerprint>"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Desafío de hCaptcha"

    Configuración de ejemplo para habilitar el desafío de hCaptcha:

    ```yaml
    USE_ANTIBOT: "hcaptcha"
    ANTIBOT_HCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_HCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Desafío de Turnstile"

    Configuración de ejemplo para habilitar el desafío de Turnstile:

    ```yaml
    USE_ANTIBOT: "turnstile"
    ANTIBOT_TURNSTILE_SITEKEY: "your-site-key"
    ANTIBOT_TURNSTILE_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Desafío de mCaptcha"

    Configuración de ejemplo para habilitar el desafío de mCaptcha:

    ```yaml
    USE_ANTIBOT: "mcaptcha"
    ANTIBOT_MCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_MCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_MCAPTCHA_URL: "https://demo.mcaptcha.org"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```
