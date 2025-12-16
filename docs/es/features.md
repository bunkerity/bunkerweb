# Características

Esta sección contiene la lista completa de ajustes admitidos por BunkerWeb. Si aún no está familiarizado con BunkerWeb, primero lea la sección de [conceptos](concepts.md) de la documentación. Siga las instrucciones de su [integración](integrations.md) para aplicar los ajustes.

## Configuración global


Compatibilidad con STREAM :warning:

El plugin General proporciona el marco de configuración principal para BunkerWeb, permitiéndote definir los ajustes esenciales que controlan cómo se protegen y entregan tus servicios web. Este plugin fundamental gestiona aspectos básicos como los modos de seguridad, los valores predeterminados del servidor, el comportamiento de los registros y los parámetros operativos críticos para todo el ecosistema de BunkerWeb.

**Cómo funciona:**

1. Cuando BunkerWeb se inicia, el plugin General carga y aplica tus ajustes de configuración principales.
2. Los modos de seguridad se establecen de forma global o por sitio, determinando el nivel de protección aplicado.
3. Los ajustes predeterminados del servidor establecen valores de respaldo para cualquier configuración multisitio no especificada.
4. Los parámetros de registro controlan qué información se graba y cómo se formatea.
5. Estos ajustes crean la base sobre la que operan todos los demás plugins y funcionalidades de BunkerWeb.

### Modo Multisite {#multisite-mode}

Cuando `MULTISITE` se establece en `yes`, BunkerWeb puede alojar y proteger múltiples sitios web, cada uno con su propia configuración única. Esta característica es particularmente útil para escenarios como:

- Alojar múltiples dominios con configuraciones distintas
- Ejecutar múltiples aplicaciones con diferentes requisitos de seguridad
- Aplicar políticas de seguridad personalizadas a diferentes servicios

En el modo multisitio, cada sitio se identifica por un `SERVER_NAME` único. Para aplicar ajustes específicos a un sitio, antepón el `SERVER_NAME` principal al nombre del ajuste. Por ejemplo:

- `www.example.com_USE_ANTIBOT=captcha` habilita el CAPTCHA para `www.example.com`.
- `myapp.example.com_USE_GZIP=yes` habilita la compresión GZIP para `myapp.example.com`.

Este enfoque asegura que los ajustes se apliquen al sitio correcto en un entorno multisitio.

### Ajustes Múltiples {#multiple-settings}

Algunos ajustes en BunkerWeb admiten múltiples configuraciones para la misma característica. Para definir múltiples grupos de ajustes, añade un sufijo numérico al nombre del ajuste. Por ejemplo:

- `REVERSE_PROXY_URL_1=/subdir` y `REVERSE_PROXY_HOST_1=http://myhost1` configuran el primer proxy inverso.
- `REVERSE_PROXY_URL_2=/anotherdir` y `REVERSE_PROXY_HOST_2=http://myhost2` configuran el segundo proxy inverso.

Este patrón te permite gestionar múltiples configuraciones para características como proxies inversos, puertos u otros ajustes que requieren valores distintos para diferentes casos de uso.

### Orden de ejecución de plugins {#plugin-order}

Puede ajustar el orden con listas separadas por espacios:

- Fases globales: `PLUGINS_ORDER_INIT`, `PLUGINS_ORDER_INIT_WORKER`, `PLUGINS_ORDER_TIMER`.
- Fases por sitio: `PLUGINS_ORDER_SET`, `PLUGINS_ORDER_ACCESS`, `PLUGINS_ORDER_SSL_CERTIFICATE`, `PLUGINS_ORDER_HEADER`, `PLUGINS_ORDER_LOG`, `PLUGINS_ORDER_PREREAD`, `PLUGINS_ORDER_LOG_STREAM`, `PLUGINS_ORDER_LOG_DEFAULT`.
- Semántica: los plugins listados se ejecutan primero en esa fase; el resto se ejecuta después en su secuencia normal. Separe los IDs solo con espacios.

### Modos de Seguridad {#security-modes}

El ajuste `SECURITY_MODE` determina cómo BunkerWeb maneja las amenazas detectadas. Esta característica flexible te permite elegir entre monitorizar o bloquear activamente la actividad sospechosa, dependiendo de tus necesidades específicas:

- **`detect`**: Registra las amenazas potenciales sin bloquear el acceso. Este modo es útil para identificar y analizar falsos positivos de una manera segura y no disruptiva.
- **`block`** (predeterminado): Bloquea activamente las amenazas detectadas mientras registra los incidentes para prevenir el acceso no autorizado y proteger tu aplicación.

Cambiar al modo `detect` puede ayudarte a identificar y resolver posibles falsos positivos sin interrumpir a los clientes legítimos. Una vez que estos problemas se resuelvan, puedes volver con confianza al modo `block` para una protección completa.

### Ajustes de Configuración

=== "Ajustes Principales"

    | Parámetro             | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                     |
    | --------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
    | `SERVER_NAME`         | `www.example.com` | multisite | No       | **Dominio Principal:** El nombre de dominio principal para este sitio. Requerido en modo multisitio.                            |
    | `BUNKERWEB_INSTANCES` | `127.0.0.1`       | global    | No       | **Instancias de BunkerWeb:** Lista de instancias de BunkerWeb separadas por espacios.                                           |
    | `MULTISITE`           | `no`              | global    | No       | **Múltiples Sitios:** Establécelo en `yes` para permitir el alojamiento de múltiples sitios web con diferentes configuraciones. |
    | `SECURITY_MODE`       | `block`           | multisite | No       | **Nivel de Seguridad:** Controla el nivel de aplicación de la seguridad. Opciones: `detect` o `block`.                          |
    | `SERVER_TYPE`         | `http`            | multisite | No       | **Tipo de Servidor:** Define si el servidor es de tipo `http` o `stream`.                                                       |

=== "Ajustes de la API"

    | Parámetro          | Valor por defecto | Contexto | Múltiple | Descripción                                                                                                                             |
    | ------------------ | ----------------- | -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_API`          | `yes`             | global   | No       | **Activar API:** Activa la API para controlar BunkerWeb.                                                                                |
    | `API_HTTP_PORT`    | `5000`            | global   | No       | **Puerto de la API:** Número de puerto de escucha para la API.                                                                          |
    | `API_HTTPS_PORT`   | `5443`            | global   | No       | **Puerto HTTPS de la API:** Número de puerto de escucha (TLS) para la API.                                                              |
    | `API_LISTEN_HTTP`  | `yes`             | global   | No       | **Escucha HTTP de la API:** Habilita el listener HTTP para la API.                                                                      |
    | `API_LISTEN_HTTPS` | `no`              | global   | No       | **Escucha HTTPS de la API:** Habilita el listener HTTPS (TLS) para la API.                                                              |
    | `API_LISTEN_IP`    | `0.0.0.0`         | global   | No       | **IP de Escucha de la API:** Dirección IP de escucha para la API.                                                                       |
    | `API_SERVER_NAME`  | `bwapi`           | global   | No       | **Nombre del Servidor de la API:** Nombre del servidor (host virtual) para la API.                                                      |
    | `API_WHITELIST_IP` | `127.0.0.0/8`     | global   | No       | **IP de la Lista Blanca de la API:** Lista de IP/redes permitidas para contactar con la API.                                            |
    | `API_TOKEN`        |                   | global   | No       | **Token de Acceso a la API (opcional):** Si se establece, todas las solicitudes a la API deben incluir `Authorization: Bearer <token>`. |

    Nota: por razones de arranque, si habilitas `API_TOKEN` debes establecerlo en el entorno de AMBAS, la instancia de BunkerWeb y el Programador. El Programador incluye automáticamente el encabezado `Authorization` cuando `API_TOKEN` está presente en su entorno. Si no se establece, no se envía ningún encabezado y BunkerWeb no aplicará la autenticación por token. Puedes exponer la API a través de HTTPS estableciendo `API_LISTEN_HTTPS=yes` (puerto: `API_HTTPS_PORT`, predeterminado `5443`).

    Prueba de ejemplo con curl (reemplaza el token y el host):

    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://<bunkerweb-host>:5000/ping

    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         --insecure \
         https://<bunkerweb-host>:5443/ping
    ```

=== "Ajustes de Red y Puertos"

    | Parámetro       | Valor por defecto | Contexto | Múltiple | Descripción                                                     |
    | --------------- | ----------------- | -------- | -------- | --------------------------------------------------------------- |
    | `HTTP_PORT`     | `8080`            | global   | Sí       | **Puerto HTTP:** Número de puerto para el tráfico HTTP.         |
    | `HTTPS_PORT`    | `8443`            | global   | Sí       | **Puerto HTTPS:** Número de puerto para el tráfico HTTPS.       |
    | `USE_IPV6`      | `no`              | global   | No       | **Soporte IPv6:** Habilita la conectividad IPv6.                |
    | `DNS_RESOLVERS` | `127.0.0.11`      | global   | No       | **Resolutores DNS:** Direcciones DNS de los resolutores a usar. |

=== "Ajustes del Servidor de Stream"

    | Parámetro                | Valor por defecto | Contexto  | Múltiple | Descripción                                                           |
    | ------------------------ | ----------------- | --------- | -------- | --------------------------------------------------------------------- |
    | `LISTEN_STREAM`          | `yes`             | multisite | No       | **Escucha de Stream:** Habilita la escucha para no-ssl (passthrough). |
    | `LISTEN_STREAM_PORT`     | `1337`            | multisite | Sí       | **Puerto de Stream:** Puerto de escucha para no-ssl (passthrough).    |
    | `LISTEN_STREAM_PORT_SSL` | `4242`            | multisite | Sí       | **Puerto SSL de Stream:** Puerto de escucha para ssl (passthrough).   |
    | `USE_TCP`                | `yes`             | multisite | No       | **Escucha TCP:** Habilita la escucha TCP (stream).                    |
    | `USE_UDP`                | `no`              | multisite | No       | **Escucha UDP:** Habilita la escucha UDP (stream).                    |

=== "Ajustes de Workers"

    | Parámetro              | Valor por defecto | Contexto | Múltiple | Descripción                                                                                              |
    | ---------------------- | ----------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------- |
    | `WORKER_PROCESSES`     | `auto`            | global   | No       | **Procesos Worker:** Número de procesos worker. Establécelo en `auto` para usar los núcleos disponibles. |
    | `WORKER_CONNECTIONS`   | `1024`            | global   | No       | **Conexiones por Worker:** Número máximo de conexiones por worker.                                       |
    | `WORKER_RLIMIT_NOFILE` | `2048`            | global   | No       | **Límite de Descriptores de Archivo:** Número máximo de archivos abiertos por worker.                    |

=== "Ajustes de Memoria"

    | Parámetro                      | Valor por defecto | Contexto | Múltiple | Descripción                                                                                        |
    | ------------------------------ | ----------------- | -------- | -------- | -------------------------------------------------------------------------------------------------- |
    | `WORKERLOCK_MEMORY_SIZE`       | `48k`             | global   | No       | **Tamaño de Memoria de Workerlock:** Tamaño de lua_shared_dict para los workers de inicialización. |
    | `DATASTORE_MEMORY_SIZE`        | `64m`             | global   | No       | **Tamaño de Memoria del Datastore:** Tamaño del datastore interno.                                 |
    | `CACHESTORE_MEMORY_SIZE`       | `64m`             | global   | No       | **Tamaño de Memoria del Cachestore:** Tamaño del cachestore interno.                               |
    | `CACHESTORE_IPC_MEMORY_SIZE`   | `16m`             | global   | No       | **Tamaño de Memoria IPC del Cachestore:** Tamaño del cachestore interno (ipc).                     |
    | `CACHESTORE_MISS_MEMORY_SIZE`  | `16m`             | global   | No       | **Tamaño de Memoria de Fallos del Cachestore:** Tamaño del cachestore interno (fallos).            |
    | `CACHESTORE_LOCKS_MEMORY_SIZE` | `16m`             | global   | No       | **Tamaño de Memoria de Bloqueos del Cachestore:** Tamaño del cachestore interno (bloqueos).        |

=== "Ajustes de Registro"

    | Parámetro          | Valor por defecto                                                                                                                          | Contexto | Múltiple | Descripción                                                                                                                                                                 |
    | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `LOG_FORMAT`       | `$host $remote_addr - $request_id $remote_user [$time_local] \"$request\" $status $body_bytes_sent \"$http_referer\" \"$http_user_agent\"` | global   | No       | **Formato de Registro:** El formato a usar para los registros de acceso.                                                                                                    |
    | `ACCESS_LOG`       | `/var/log/bunkerweb/access.log`                                                                                                            | global   | Sí       | **Ruta de Registro de Acceso:** Archivo, `syslog:server=host[:port][,param=valor]` o búfer compartido `memory:nombre:tamaño`; establezca `off` para desactivar el registro. |
    | `ERROR_LOG`        | `/var/log/bunkerweb/error.log`                                                                                                             | global   | Sí       | **Ruta de Registro de Errores:** Archivo, `stderr`, `syslog:server=host[:port][,param=valor]` o `memory:tamaño`.                                                            |
    | `LOG_LEVEL`        | `notice`                                                                                                                                   | global   | Sí       | **Nivel de Registro:** Nivel de verbosidad para los registros de errores. Opciones: `debug`, `info`, `notice`, `warn`, `error`, `crit`, `alert`, `emerg`.                   |
    | `TIMERS_LOG_LEVEL` | `debug`                                                                                                                                    | global   | No       | **Nivel de Registro de Temporizadores:** Nivel de registro para los temporizadores. Opciones: `debug`, `info`, `notice`, `warn`, `err`, `crit`, `alert`, `emerg`.           |

    !!! tip "Mejores Prácticas de Registro"
        - Para entornos de producción, usa los niveles de registro `notice`, `warn`, o `error` para minimizar el volumen de registros.
        - Para depurar problemas, establece temporalmente el nivel de registro en `debug` para obtener información más detallada.

=== "Ajustes de Integración"

    | Parámetro         | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                 |
    | ----------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------- |
    | `AUTOCONF_MODE`   | `no`              | global    | No       | **Modo Autoconf:** Habilita la integración con Docker Autoconf.                                                             |
    | `SWARM_MODE`      | `no`              | global    | No       | **Modo Swarm:** Habilita la integración con Docker Swarm.                                                                   |
    | `KUBERNETES_MODE` | `no`              | global    | No       | **Modo Kubernetes:** Habilita la integración con Kubernetes.                                                                |
    | `USE_TEMPLATE`    |                   | multisite | No       | **Usar Plantilla:** Plantilla de configuración a usar que sobrescribirá los valores predeterminados de ajustes específicos. |

=== "Ajustes de Nginx"

    | Parámetro                       | Valor por defecto | Contexto | Múltiple | Descripción                                                                                                    |
    | ------------------------------- | ----------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------------- |
    | `NGINX_PREFIX`                  | `/etc/nginx/`     | global   | No       | **Prefijo de Nginx:** Dónde buscará Nginx las configuraciones.                                                 |
    | `SERVER_NAMES_HASH_BUCKET_SIZE` |                   | global   | No       | **Tamaño del Bucket de Hash de Nombres de Servidor:** Valor para la directiva `server_names_hash_bucket_size`. |

### Configuraciones de Ejemplo

=== "Configuración Básica de Producción"

    Una configuración estándar para un sitio de producción con seguridad estricta:

    ```yaml
    SECURITY_MODE: "block"
    SERVER_NAME: "example.com"
    LOG_LEVEL: "notice"
    ```

=== "Modo de Desarrollo"

    Configuración para un entorno de desarrollo con registro adicional:

    ```yaml
    SECURITY_MODE: "detect"
    SERVER_NAME: "dev.example.com"
    LOG_LEVEL: "debug"
    ```

=== "Configuración Multisite"

    Configuración para alojar múltiples sitios web:

    ```yaml
    MULTISITE: "yes"

    # Primer sitio
    site1.example.com_SERVER_NAME: "site1.example.com"
    site1.example.com_SECURITY_MODE: "block"

    # Segundo sitio
    site2.example.com_SERVER_NAME: "site2.example.com"
    site2.example.com_SECURITY_MODE: "detect"
    ```

=== "Configuración del Servidor de Stream"

    Configuración para un servidor TCP/UDP:

    ```yaml
    SERVER_TYPE: "stream"
    SERVER_NAME: "stream.example.com"
    LISTEN_STREAM: "yes"
    LISTEN_STREAM_PORT: "1337"
    USE_TCP: "yes"
    USE_UDP: "no"
    ```

## Anti DDoS <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Compatibilidad con STREAM :x:

Provides enhanced protection against DDoS attacks by analyzing and filtering suspicious traffic.

| Parámetro                    | Valor predeterminado | Contexto | Múltiple | Descripción                                                             |
| ---------------------------- | -------------------- | -------- | -------- | ----------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`                 | global   | no       | Enable or disable anti DDoS protection to mitigate high traffic spikes. |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`                | global   | no       | Size of in-memory storage for DDoS metrics (e.g., 10M, 500k).           |
| `ANTIDDOS_THRESHOLD`         | `100`                | global   | no       | Maximum suspicious requests allowed from a single IP before blocking.   |
| `ANTIDDOS_WINDOW_TIME`       | `10`                 | global   | no       | Time window (seconds) to detect abnormal request patterns.              |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444`        | global   | no       | HTTP status codes treated as suspicious for DDoS analysis.              |
| `ANTIDDOS_DISTINCT_IP`       | `5`                  | global   | no       | Minimum distinct IP count before enabling anti DDoS measures.           |

## Antibot

Compatibilidad con STREAM :x:

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

| Configuración               | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                      |
| --------------------------- | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_IGNORE_URI`        |                   | multisite | no       | **URL excluidas:** Lista de patrones regex de URI separados por espacios que deben omitir el desafío.                            |
| `ANTIBOT_IGNORE_IP`         |                   | multisite | no       | **IP excluidas:** Lista de direcciones IP o rangos CIDR separados por espacios que deben omitir el desafío.                      |
| `ANTIBOT_IGNORE_RDNS`       |                   | multisite | no       | **DNS inverso excluido:** Lista de sufijos de DNS inverso separados por espacios que deben omitir el desafío.                    |
| `ANTIBOT_RDNS_GLOBAL`       | `yes`             | multisite | no       | **Solo IP globales:** Si se establece en `yes`, solo realiza comprobaciones de DNS inverso en direcciones IP públicas.           |
| `ANTIBOT_IGNORE_ASN`        |                   | multisite | no       | **ASN excluidos:** Lista de números de ASN separados por espacios que deben omitir el desafío.                                   |
| `ANTIBOT_IGNORE_USER_AGENT` |                   | multisite | no       | **User-Agents excluidos:** Lista de patrones regex de User-Agent separados por espacios que deben omitir el desafío.             |
| `ANTIBOT_IGNORE_COUNTRY`    |                   | multisite | no       | **Países excluidos:** Lista de códigos de país ISO 3166-1 alfa-2 separados por espacios que deben omitir el desafío.             |
| `ANTIBOT_ONLY_COUNTRY`      |                   | multisite | no       | **Países con desafío obligatorio:** Lista de códigos de país ISO 3166-1 alfa-2 que deben resolver el desafío. El resto se omite. |

!!! note "Comportamiento de la configuración basada en países"
      - Cuando se configuran `ANTIBOT_IGNORE_COUNTRY` y `ANTIBOT_ONLY_COUNTRY`, la lista de exclusiones tiene prioridad: los países presentes en ambas listas omiten el desafío.
      - Las direcciones IP privadas o desconocidas omiten el desafío cuando `ANTIBOT_ONLY_COUNTRY` está configurado, porque no se puede determinar un código de país.

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

- `ANTIBOT_IGNORE_COUNTRY: "US CA"`
  Esto omitirá el desafío antibot para visitantes ubicados en Estados Unidos o Canadá.

- `ANTIBOT_ONLY_COUNTRY: "CN RU"`
  Esto solo desafiará a los visitantes de China o Rusia. Las solicitudes de otros países (o rangos IP privados) omitirán el desafío.

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

## Auth basic

Compatibilidad con STREAM :x:

El plugin Auth Basic proporciona autenticación básica HTTP para proteger su sitio web o recursos específicos. Esta función añade una capa extra de seguridad al requerir que los usuarios introduzcan un nombre de usuario y una contraseña antes de acceder al contenido protegido. Este tipo de autenticación es fácil de implementar y es ampliamente compatible con los navegadores.

**Cómo funciona:**

1.  Cuando un usuario intenta acceder a un área protegida de su sitio web, el servidor envía un desafío de autenticación.
2.  El navegador muestra un cuadro de diálogo de inicio de sesión pidiendo al usuario un nombre de usuario y una contraseña.
3.  El usuario introduce sus credenciales, que se envían al servidor.
4.  Si las credenciales son válidas, se le concede al usuario acceso al contenido solicitado.
5.  Si las credenciales no son válidas, se le muestra al usuario un mensaje de error con el código de estado 401 No autorizado.

### Cómo usar

Siga estos pasos para habilitar y configurar la autenticación básica:

1.  **Habilite la función:** Establezca el ajuste `USE_AUTH_BASIC` en `yes` en su configuración de BunkerWeb.
2.  **Elija el ámbito de protección:** Decida si proteger todo su sitio o solo URL específicas configurando el ajuste `AUTH_BASIC_LOCATION`.
3.  **Defina las credenciales:** Configure al menos un par de nombre de usuario y contraseña utilizando los ajustes `AUTH_BASIC_USER` y `AUTH_BASIC_PASSWORD`.
4.  **Personalice el mensaje:** Opcionalmente, cambie el `AUTH_BASIC_TEXT` para mostrar un mensaje personalizado en la solicitud de inicio de sesión.

### Ajustes de configuración

| Ajuste                | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                                                                                                                         |
| --------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_AUTH_BASIC`      | `no`              | multisite | no       | **Habilitar autenticación básica:** Establezca en `yes` para habilitar la autenticación básica.                                                                                                                                                     |
| `AUTH_BASIC_LOCATION` | `sitewide`        | multisite | no       | **Ámbito de protección:** Establezca en `sitewide` para proteger todo el sitio, o especifique una ruta de URL (p. ej., `/admin`) para proteger solo áreas específicas. También puede utilizar modificadores de estilo Nginx (`=`, `~`, `~*`, `^~`). |
| `AUTH_BASIC_USER`     | `changeme`        | multisite | yes      | **Nombre de usuario:** El nombre de usuario requerido para la autenticación. Puede definir múltiples pares de nombre de usuario/contraseña.                                                                                                         |
| `AUTH_BASIC_PASSWORD` | `changeme`        | multisite | yes      | **Contraseña:** La contraseña requerida para la autenticación. Las contraseñas se hash con scrypt para máxima seguridad.                                                                                                                            |
| `AUTH_BASIC_TEXT`     | `Restricted area` | multisite | no       | **Texto de la solicitud:** El mensaje que se muestra en la solicitud de autenticación mostrada a los usuarios.                                                                                                                                      |

!!! warning "Consideraciones de seguridad"
    La autenticación básica HTTP transmite las credenciales codificadas (no cifradas) en Base64. Aunque esto es aceptable cuando se utiliza sobre HTTPS, no debe considerarse seguro sobre HTTP plano. Habilite siempre SSL/TLS cuando utilice la autenticación básica.

!!! tip "Uso de múltiples credenciales"
    Puede configurar múltiples pares de nombre de usuario/contraseña para el acceso. Cada ajuste `AUTH_BASIC_USER` debe tener un ajuste `AUTH_BASIC_PASSWORD` correspondiente.

### Configuraciones de ejemplo

=== "Protección de todo el sitio"

    Para proteger todo su sitio web con un único conjunto de credenciales:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Protección de áreas específicas"

    Para proteger solo una ruta específica, como un panel de administración:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "/admin/"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Múltiples usuarios"

    Para configurar múltiples usuarios con diferentes credenciales:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_TEXT: "Staff Area"

    # Primer usuario
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "admin_password"

    # Segundo usuario
    AUTH_BASIC_USER_2: "editor"
    AUTH_BASIC_PASSWORD_2: "editor_password"

    # Tercer usuario
    AUTH_BASIC_USER_3: "viewer"
    AUTH_BASIC_PASSWORD_3: "viewer_password"
    ```

## Backup

Compatibilidad con STREAM :white_check_mark:

El complemento de copia de seguridad proporciona una solución de respaldo automatizada para proteger sus datos de BunkerWeb. Esta función garantiza la seguridad y disponibilidad de su importante base de datos mediante la creación de copias de seguridad periódicas según el cronograma que prefiera. Las copias de seguridad se almacenan en una ubicación designada y se pueden gestionar fácilmente a través de procesos automatizados y comandos manuales.

**Cómo funciona:**

1.  Su base de datos se respalda automáticamente según el cronograma que establezca (diario, semanal o mensual).
2.  Las copias de seguridad se almacenan en un directorio específico de su sistema.
3.  Las copias de seguridad antiguas se rotan automáticamente según su configuración de retención.
4.  Puede crear copias de seguridad manualmente, enumerar las copias de seguridad existentes o restaurar desde una copia de seguridad en cualquier momento.
5.  Antes de cualquier operación de restauración, el estado actual se respalda automáticamente como medida de seguridad.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de copia de seguridad:

1.  **Habilite la función:** La función de copia de seguridad está habilitada por defecto. Si es necesario, puede controlarla con el ajuste `USE_BACKUP`.
2.  **Configure el cronograma de copia de seguridad:** Elija la frecuencia con la que deben realizarse las copias de seguridad estableciendo el parámetro `BACKUP_SCHEDULE`.
3.  **Establezca la política de retención:** Especifique cuántas copias de seguridad conservar utilizando el ajuste `BACKUP_ROTATION`.
4.  **Defina la ubicación de almacenamiento:** Elija dónde se almacenarán las copias de seguridad utilizando el ajuste `BACKUP_DIRECTORY`.
5.  **Use los comandos de la CLI:** Gestione las copias de seguridad manualmente con los comandos `bwcli plugin backup` cuando sea necesario.

### Ajustes de configuración

| Ajuste             | Valor por defecto            | Contexto | Múltiple | Descripción                                                                                                                                                                                   |
| ------------------ | ---------------------------- | -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global   | no       | **Habilitar copia de seguridad:** Establezca en `yes` para habilitar las copias de seguridad automáticas.                                                                                     |
| `BACKUP_SCHEDULE`  | `daily`                      | global   | no       | **Frecuencia de la copia de seguridad:** Con qué frecuencia se realizan las copias de seguridad. Opciones: `daily`, `weekly` o `monthly`.                                                     |
| `BACKUP_ROTATION`  | `7`                          | global   | no       | **Retención de copias de seguridad:** El número de archivos de copia de seguridad que se deben conservar. Las copias de seguridad más antiguas que este número se eliminarán automáticamente. |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global   | no       | **Ubicación de la copia de seguridad:** El directorio donde se almacenarán los archivos de copia de seguridad.                                                                                |

### Interfaz de línea de comandos

El complemento de copia de seguridad proporciona varios comandos de la CLI para gestionar sus copias de seguridad:

```bash
# Listar todas las copias de seguridad disponibles
bwcli plugin backup list

# Crear una copia de seguridad manual
bwcli plugin backup save

# Crear una copia de seguridad en una ubicación personalizada
bwcli plugin backup save --directory /ruta/a/ubicacion/personalizada

# Restaurar desde la copia de seguridad más reciente
bwcli plugin backup restore

# Restaurar desde un archivo de copia de seguridad específico
bwcli plugin backup restore /ruta/a/copia/de/seguridad/backup-sqlite-2023-08-15_12-34-56.zip
```

!!! tip "La seguridad es lo primero"
    Antes de cualquier operación de restauración, el complemento de copia de seguridad crea automáticamente una copia de seguridad del estado actual de su base de datos en una ubicación temporal. Esto proporciona una protección adicional en caso de que necesite revertir la operación de restauración.

!!! warning "Compatibilidad de la base de datos"
    El complemento de copia de seguridad es compatible con las bases de datos SQLite, MySQL/MariaDB y PostgreSQL. Las bases de datos de Oracle no son compatibles actualmente para las operaciones de copia de seguridad y restauración.

### Configuraciones de ejemplo

=== "Copias de seguridad diarias con retención de 7 días"

    Configuración por defecto que crea copias de seguridad diarias y conserva los 7 archivos más recientes:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Copias de seguridad semanales con retención extendida"

    Configuración para copias de seguridad menos frecuentes con una retención más prolongada:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Copias de seguridad mensuales en una ubicación personalizada"

    Configuración para copias de seguridad mensuales almacenadas en una ubicación personalizada:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```

## Backup S3 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Compatibilidad con STREAM :white_check_mark:

Automatically backup your data to an S3 bucket

| Parámetro                     | Valor predeterminado | Contexto | Múltiple | Descripción                                  |
| ----------------------------- | -------------------- | -------- | -------- | -------------------------------------------- |
| `USE_BACKUP_S3`               | `no`                 | global   | no       | Enable or disable the S3 backup feature      |
| `BACKUP_S3_SCHEDULE`          | `daily`              | global   | no       | The frequency of the backup                  |
| `BACKUP_S3_ROTATION`          | `7`                  | global   | no       | The number of backups to keep                |
| `BACKUP_S3_ENDPOINT`          |                      | global   | no       | The S3 endpoint                              |
| `BACKUP_S3_BUCKET`            |                      | global   | no       | The S3 bucket                                |
| `BACKUP_S3_DIR`               |                      | global   | no       | The S3 directory                             |
| `BACKUP_S3_REGION`            |                      | global   | no       | The S3 region                                |
| `BACKUP_S3_ACCESS_KEY_ID`     |                      | global   | no       | The S3 access key ID                         |
| `BACKUP_S3_ACCESS_KEY_SECRET` |                      | global   | no       | The S3 access key secret                     |
| `BACKUP_S3_COMP_LEVEL`        | `6`                  | global   | no       | The compression level of the backup zip file |

## Bad behavior

Compatibilidad con STREAM :white_check_mark:

El complemento de Mal Comportamiento protege su sitio web al detectar y bloquear automáticamente las direcciones IP que generan demasiados errores o códigos de estado HTTP "malos" dentro de un período de tiempo específico. Esto ayuda a defenderse contra ataques de fuerza bruta, raspadores web, escáneres de vulnerabilidades y otras actividades maliciosas que podrían generar numerosas respuestas de error.

Los atacantes a menudo generan códigos de estado HTTP "sospechosos" al sondear o explotar vulnerabilidades, códigos que un usuario típico es poco probable que active en un período de tiempo determinado. Al detectar este comportamiento, BunkerWeb puede bloquear automáticamente la dirección IP infractora, obligando al atacante a usar una nueva dirección IP para continuar sus intentos.

**Cómo funciona:**

1.  El complemento supervisa las respuestas HTTP de su sitio.
2.  Cuando un visitante recibe un código de estado HTTP "malo" (como 400, 401, 403, 404, etc.), el contador para esa dirección IP se incrementa.
3.  Si una dirección IP excede el umbral configurado de códigos de estado malos dentro del período de tiempo especificado, la IP se bloquea automáticamente.
4.  Las IP bloqueadas pueden ser bloqueadas a nivel de servicio (solo para el sitio específico) o globalmente (en todos los sitios), dependiendo de su configuración.
5.  Los bloqueos expiran automáticamente después de la duración de bloqueo configurada, o permanecen permanentes si se configuran con `0`.

!!! success "Beneficios clave"

    1.  **Protección automática:** Detecta y bloquea clientes potencialmente maliciosos sin requerir intervención manual.
    2.  **Reglas personalizables:** Ajuste con precisión lo que constituye un "mal comportamiento" según sus necesidades específicas.
    3.  **Conservación de recursos:** Evita que los actores maliciosos consuman recursos del servidor con repetidas solicitudes no válidas.
    4.  **Ámbito flexible:** Elija si los bloqueos deben aplicarse solo al servicio actual o globalmente a todos los servicios.
    5.  **Control de la duración del bloqueo:** Establezca bloqueos temporales que expiran automáticamente después de la duración configurada, o bloqueos permanentes que permanecen hasta que se eliminan manualmente.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de Mal Comportamiento:

1.  **Habilite la función:** La función de Mal Comportamiento está habilitada por defecto. Si es necesario, puede controlarla con la configuración `USE_BAD_BEHAVIOR`.
2.  **Configure los códigos de estado:** Defina qué códigos de estado HTTP deben considerarse "malos" utilizando la configuración `BAD_BEHAVIOR_STATUS_CODES`.
3.  **Establezca los valores de umbral:** Determine cuántas respuestas "malas" deben desencadenar un bloqueo utilizando la configuración `BAD_BEHAVIOR_THRESHOLD`.
4.  **Configure los períodos de tiempo:** Especifique la duración para contar las respuestas malas y la duración del bloqueo utilizando las configuraciones `BAD_BEHAVIOR_COUNT_TIME` y `BAD_BEHAVIOR_BAN_TIME`.
5.  **Elija el ámbito del bloqueo:** Decida si los bloqueos deben aplicarse solo al servicio actual o globalmente a todos los servicios utilizando la configuración `BAD_BEHAVIOR_BAN_SCOPE`. Cuando el tráfico llega al servidor predeterminado (nombre de servidor `_`), los bloqueos siempre son globales para que la IP quede bloqueada en todas partes.

!!! tip "Modo Stream"
    En **modo stream**, solo el código de estado `444` se considera "malo" y activará este comportamiento.

### Ajustes de configuración

| Ajuste                      | Valor por defecto             | Contexto  | Múltiple | Descripción                                                                                                                                                                                                                           |
| --------------------------- | ----------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BAD_BEHAVIOR`          | `yes`                         | multisite | no       | **Habilitar Mal Comportamiento:** Establezca en `yes` para habilitar la función de detección y bloqueo de mal comportamiento.                                                                                                         |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | multisite | no       | **Códigos de estado malos:** Lista de códigos de estado HTTP que se contarán como comportamiento "malo" cuando se devuelvan a un cliente.                                                                                             |
| `BAD_BEHAVIOR_THRESHOLD`    | `10`                          | multisite | no       | **Umbral:** El número de códigos de estado "malos" que una IP puede generar dentro del período de conteo antes de ser bloqueada.                                                                                                      |
| `BAD_BEHAVIOR_COUNT_TIME`   | `60`                          | multisite | no       | **Período de conteo:** La ventana de tiempo (en segundos) durante la cual se cuentan los códigos de estado malos para alcanzar el umbral.                                                                                             |
| `BAD_BEHAVIOR_BAN_TIME`     | `86400`                       | multisite | no       | **Duración del bloqueo:** Cuánto tiempo (en segundos) permanecerá bloqueada una IP después de exceder el umbral. El valor por defecto es de 24 horas (86400 segundos). Establezca en `0` para bloqueos permanentes que nunca expiran. |
| `BAD_BEHAVIOR_BAN_SCOPE`    | `service`                     | global    | no       | **Ámbito del bloqueo:** Determina si los bloqueos se aplican solo al servicio actual (`service`) o a todos los servicios (`global`). En el servidor predeterminado (`_`), los bloqueos son siempre globales.                          |

!!! warning "Falsos positivos"
    Tenga cuidado al establecer el umbral y el tiempo de conteo. Establecer estos valores demasiado bajos puede bloquear inadvertidamente a usuarios legítimos que encuentren errores mientras navegan por su sitio.

!!! tip "Ajuste de su configuración"
    Comience con configuraciones conservadoras (umbral más alto, tiempo de bloqueo más corto) y ajústelas según sus necesidades específicas y patrones de tráfico. Supervise sus registros para asegurarse de que los usuarios legítimos no sean bloqueados por error.

### Configuraciones de ejemplo

=== "Configuración por defecto"

    La configuración por defecto proporciona un enfoque equilibrado adecuado para la mayoría de los sitios web:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "86400"
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Configuración estricta"

    Para aplicaciones de alta seguridad donde se desea ser más agresivo al bloquear amenazas potenciales:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444 500 502 503"
    BAD_BEHAVIOR_THRESHOLD: "5"
    BAD_BEHAVIOR_COUNT_TIME: "120"
    BAD_BEHAVIOR_BAN_TIME: "604800"  # 7 días
    BAD_BEHAVIOR_BAN_SCOPE: "global" # Bloquear en todos los servicios
    ```

=== "Configuración permisiva"

    Para sitios con alto tráfico legítimo donde se desea evitar falsos positivos:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "401 403 429"  # Solo contar no autorizados, prohibidos y con límite de velocidad
    BAD_BEHAVIOR_THRESHOLD: "20"
    BAD_BEHAVIOR_COUNT_TIME: "30"
    BAD_BEHAVIOR_BAN_TIME: "3600"  # 1 hora
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Configuración de bloqueo permanente"

    Para escenarios donde desea que los atacantes detectados sean bloqueados permanentemente hasta que se desbloqueen manualmente:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "0"  # Bloqueo permanente (nunca expira)
    BAD_BEHAVIOR_BAN_SCOPE: "global" # Bloquear en todos los servicios
    ```

## Blacklist

Compatibilidad con STREAM :warning:

El complemento de Lista Negra proporciona una protección robusta para su sitio web al bloquear el acceso basado en varios atributos del cliente. Esta función defiende contra entidades maliciosas conocidas, escáneres y visitantes sospechosos al denegar el acceso basado en direcciones IP, redes, entradas de DNS inverso, ASN, agentes de usuario y patrones de URI específicos.

**Cómo funciona:**

1.  El complemento comprueba las solicitudes entrantes contra múltiples criterios de la lista negra (direcciones IP, redes, rDNS, ASN, User-Agent o patrones de URI).
2.  Las listas negras se pueden especificar directamente en su configuración o cargar desde URL externas.
3.  Si un visitante coincide con alguna regla de la lista negra (y no coincide con ninguna regla de omisión), se le deniega el acceso.
4.  Las listas negras se actualizan automáticamente en un horario regular desde las URL configuradas.
5.  Puede personalizar exactamente qué criterios se comprueban y se omiten según sus necesidades de seguridad específicas.

### Cómo usar

Siga estos pasos para configurar y usar la función de Lista Negra:

1.  **Habilite la función:** La función de Lista Negra está habilitada por defecto. Si es necesario, puede controlarla con el ajuste `USE_BLACKLIST`.
2.  **Configure las reglas de bloqueo:** Defina qué IP, redes, patrones de rDNS, ASN, User-Agents o URI deben ser bloqueados.
3.  **Configure las reglas de omisión:** Especifique cualquier excepción que deba omitir las comprobaciones de la lista negra.
4.  **Añada fuentes externas:** Configure las URL para descargar y actualizar automáticamente los datos de la lista negra.
5.  **Supervise la eficacia:** Consulte la [interfaz de usuario web](web-ui.md) para ver las estadísticas de las solicitudes bloqueadas.

!!! info "modo stream"
    Cuando se utiliza el modo stream, solo se realizarán comprobaciones de IP, rDNS y ASN.

### Ajustes de configuración

**General**

| Ajuste                      | Valor por defecto                                       | Contexto  | Múltiple | Descripción                                                                                                                            |
| --------------------------- | ------------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BLACKLIST`             | `yes`                                                   | multisite | no       | **Habilitar Lista Negra:** Establezca en `yes` para habilitar la función de lista negra.                                               |
| `BLACKLIST_COMMUNITY_LISTS` | `ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents` | multisite | no       | **Listas Negras de la Comunidad:** Seleccione listas negras preconfiguradas mantenidas por la comunidad para incluirlas en el bloqueo. |

=== "Listas Negras de la Comunidad"
    **Qué hace esto:** Le permite añadir rápidamente listas negras bien mantenidas y de origen comunitario sin tener que configurar manualmente las URL.

    El ajuste `BLACKLIST_COMMUNITY_LISTS` le permite seleccionar de fuentes de listas negras curadas. Las opciones disponibles incluyen:

    | ID                                                                                                                           | Descripción                                                                                                                                                                                                                    | Fuente                                                                                                                         |
    | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
    | `ip:laurent-minne-data-shield-aggressive`                                                                                    | Lista de bloqueo de IPv4 de Data-Shield. DST = Europa                                                                                                                                                                          |
    | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_data-shield_ipv4_blocklist.txt` |
    | `ip:danmeuk-tor-exit`                                                                                                        | IP de nodos de salida de Tor (dan.me.uk)                                                                                                                                                                                       | `https://www.dan.me.uk/torlist/?exit`                                                                                          |
    | `ua:mitchellkrogza-bad-user-agents`                                                                                          | Nginx Block Bad Bots, Spam Referrer Blocker, Vulnerability Scanners, User-Agents, Malware, Adware, Ransomware, Malicious Sites, con anti-DDOS, Wordpress Theme Detector Blocking y Fail2Ban Jail para infractores reincidentes | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` |

    **Configuración:** Especifique múltiples listas separadas por espacios. Por ejemplo:
    ```yaml
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    !!! tip "Comunidad vs Configuración Manual"
        Las listas negras de la comunidad proporcionan una forma conveniente de empezar con fuentes de listas negras probadas. Puede usarlas junto con configuraciones de URL manuales para una máxima flexibilidad.

=== "Dirección IP"
    **Qué hace esto:** Bloquea a los visitantes según su dirección IP o red.

    | Ajuste                     | Valor por defecto                     | Contexto  | Múltiple | Descripción                                                                                                              |
    | -------------------------- | ------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
    | `BLACKLIST_IP`             |                                       | multisite | no       | **Lista Negra de IP:** Lista de direcciones IP o redes (notación CIDR) a bloquear, separadas por espacios.               |
    | `BLACKLIST_IGNORE_IP`      |                                       | multisite | no       | **Lista de Omisión de IP:** Lista de direcciones IP o redes que deben omitir las comprobaciones de la lista negra de IP. |
    | `BLACKLIST_IP_URLS`        | `https://www.dan.me.uk/torlist/?exit` | multisite | no       | **URL de la Lista Negra de IP:** Lista de URL que contienen direcciones IP o redes a bloquear, separadas por espacios.   |
    | `BLACKLIST_IGNORE_IP_URLS` |                                       | multisite | no       | **URL de la Lista de Omisión de IP:** Lista de URL que contienen direcciones IP o redes a omitir.                        |

    El ajuste por defecto de `BLACKLIST_IP_URLS` incluye una URL que proporciona una **lista de nodos de salida de Tor conocidos**. Esta es una fuente común de tráfico malicioso y es un buen punto de partida para muchos sitios.

=== "DNS Inverso"
    **Qué hace esto:** Bloquea a los visitantes según su nombre de dominio inverso. Esto es útil para bloquear escáneres y rastreadores conocidos basados en los dominios de su organización.

    | Ajuste                       | Valor por defecto       | Contexto  | Múltiple | Descripción                                                                                                                  |
    | ---------------------------- | ----------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_RDNS`             | `.shodan.io .censys.io` | multisite | no       | **Lista Negra de rDNS:** Lista de sufijos de DNS inverso a bloquear, separados por espacios.                                 |
    | `BLACKLIST_RDNS_GLOBAL`      | `yes`                   | multisite | no       | **Solo Global para rDNS:** Solo realizar comprobaciones de rDNS en direcciones IP globales cuando se establece en `yes`.     |
    | `BLACKLIST_IGNORE_RDNS`      |                         | multisite | no       | **Lista de Omisión de rDNS:** Lista de sufijos de DNS inverso que deben omitir las comprobaciones de la lista negra de rDNS. |
    | `BLACKLIST_RDNS_URLS`        |                         | multisite | no       | **URL de la Lista Negra de rDNS:** Lista de URL que contienen sufijos de DNS inverso a bloquear, separadas por espacios.     |
    | `BLACKLIST_IGNORE_RDNS_URLS` |                         | multisite | no       | **URL de la Lista de Omisión de rDNS:** Lista de URL que contienen sufijos de DNS inverso a omitir.                          |

    El ajuste por defecto de `BLACKLIST_RDNS` incluye dominios de escáneres comunes como **Shodan** y **Censys**. Estos son a menudo utilizados por investigadores de seguridad y escáneres para identificar sitios vulnerables.

=== "ASN"
    **Qué hace esto:** Bloquea a los visitantes de proveedores de red específicos. Los ASN son como los códigos postales de Internet: identifican a qué proveedor u organización pertenece una IP.

    | Ajuste                      | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                             |
    | --------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_ASN`             |                   | multisite | no       | **Lista Negra de ASN:** Lista de Números de Sistema Autónomo a bloquear, separados por espacios.        |
    | `BLACKLIST_IGNORE_ASN`      |                   | multisite | no       | **Lista de Omisión de ASN:** Lista de ASN que deben omitir las comprobaciones de la lista negra de ASN. |
    | `BLACKLIST_ASN_URLS`        |                   | multisite | no       | **URL de la Lista Negra de ASN:** Lista de URL que contienen ASN a bloquear, separadas por espacios.    |
    | `BLACKLIST_IGNORE_ASN_URLS` |                   | multisite | no       | **URL de la Lista de Omisión de ASN:** Lista de URL que contienen ASN a omitir.                         |

=== "Agente de Usuario"
    **Qué hace esto:** Bloquea a los visitantes según el navegador o la herramienta que dicen estar usando. Esto es efectivo contra los bots que se identifican honestamente (como "ScannerBot" o "WebHarvestTool").

    | Ajuste                             | Valor por defecto                                                                                                              | Contexto  | Múltiple | Descripción                                                                                                                              |
    | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_USER_AGENT`             |                                                                                                                                | multisite | no       | **Lista Negra de User-Agent:** Lista de patrones de User-Agent (expresión regular PCRE) a bloquear, separados por espacios.              |
    | `BLACKLIST_IGNORE_USER_AGENT`      |                                                                                                                                | multisite | no       | **Lista de Omisión de User-Agent:** Lista de patrones de User-Agent que deben omitir las comprobaciones de la lista negra de User-Agent. |
    | `BLACKLIST_USER_AGENT_URLS`        | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` | multisite | no       | **URL de la Lista Negra de User-Agent:** Lista de URL que contienen patrones de User-Agent a bloquear.                                   |
    | `BLACKLIST_IGNORE_USER_AGENT_URLS` |                                                                                                                                | multisite | no       | **URL de la Lista de Omisión de User-Agent:** Lista de URL que contienen patrones de User-Agent a omitir.                                |

    El ajuste por defecto de `BLACKLIST_USER_AGENT_URLS` incluye una URL que proporciona una **lista de agentes de usuario maliciosos conocidos**. Estos son a menudo utilizados por bots y escáneres maliciosos para identificar sitios vulnerables.

=== "URI"
    **Qué hace esto:** Bloquea las solicitudes a URL específicas en su sitio. Esto es útil para bloquear intentos de acceso a páginas de administración, formularios de inicio de sesión u otras áreas sensibles que podrían ser objetivo de ataques.

    | Ajuste                      | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                         |
    | --------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_URI`             |                   | multisite | no       | **Lista Negra de URI:** Lista de patrones de URI (expresión regular PCRE) a bloquear, separados por espacios.       |
    | `BLACKLIST_IGNORE_URI`      |                   | multisite | no       | **Lista de Omisión de URI:** Lista de patrones de URI que deben omitir las comprobaciones de la lista negra de URI. |
    | `BLACKLIST_URI_URLS`        |                   | multisite | no       | **URL de la Lista Negra de URI:** Lista de URL que contienen patrones de URI a bloquear, separadas por espacios.    |
    | `BLACKLIST_IGNORE_URI_URLS` |                   | multisite | no       | **URL de la Lista de Omisión de URI:** Lista de URL que contienen patrones de URI a omitir.                         |

!!! info "Soporte de Formato de URL"
    Todos los ajustes `*_URLS` admiten URL HTTP/HTTPS así como rutas de archivos locales usando el prefijo `file:///`. Se admite la autenticación básica usando el formato `http://usuario:contraseña@url`.

!!! tip "Actualizaciones Regulares"
    Las listas negras de las URL se descargan y actualizan automáticamente cada hora para asegurar que su protección se mantenga actualizada contra las últimas amenazas.

### Configuraciones de Ejemplo

=== "Protección Básica de IP y User-Agent"

    Una configuración simple que bloquea los nodos de salida de Tor conocidos y los agentes de usuario maliciosos comunes usando listas negras de la comunidad:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    Alternativamente, puede usar la configuración manual de URL:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Protección Avanzada con Reglas Personalizadas"

    Una configuración más completa con entradas de lista negra personalizadas y excepciones:

    ```yaml
    USE_BLACKLIST: "yes"

    # Entradas de lista negra personalizadas
    BLACKLIST_IP: "192.168.1.100 203.0.113.0/24"
    BLACKLIST_RDNS: ".shodan.io .censys.io .scanner.com"
    BLACKLIST_ASN: "16509 14618"  # ASN de AWS y Amazon
    BLACKLIST_USER_AGENT: "(?:\b)SemrushBot(?:\b) (?:\b)AhrefsBot(?:\b)"
    BLACKLIST_URI: "^/wp-login\.php$ ^/administrator/"

    # Reglas de omisión personalizadas
    BLACKLIST_IGNORE_IP: "192.168.1.200 203.0.113.42"

    # Fuentes de listas negras externas
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit https://www.spamhaus.org/drop/drop.txt"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Usando Archivos Locales"

    Configuración usando archivos locales para las listas negras:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "file:///ruta/a/ip-blacklist.txt"
    BLACKLIST_RDNS_URLS: "file:///ruta/a/rdns-blacklist.txt"
    BLACKLIST_ASN_URLS: "file:///ruta/a/asn-blacklist.txt"
    BLACKLIST_USER_AGENT_URLS: "file:///ruta/a/user-agent-blacklist.txt"
    BLACKLIST_URI_URLS: "file:///ruta/a/uri-blacklist.txt"
    ```

### Trabajar con archivos de listas locales

Las configuraciones `*_URLS` de los plugins de lista blanca, lista gris y lista negra utilizan el mismo descargador. Cuando referencia una URL `file:///`:

- La ruta se resuelve dentro del contenedor del **scheduler** (en despliegues Docker normalmente `bunkerweb-scheduler`). Monte los archivos allí y asegúrese de que el usuario del scheduler tenga permisos de lectura.
- Cada archivo es texto codificado en UTF-8 con una entrada por línea. Las líneas vacías se ignoran y las líneas de comentario deben comenzar con `#` o `;`. Los comentarios `//` no son compatibles.
- Valores esperados por tipo de lista:
  - **Listas IP** aceptan direcciones IPv4/IPv6 o redes CIDR (por ejemplo `192.0.2.10` o `2001:db8::/48`).
  - **Listas rDNS** esperan un sufijo sin espacios (por ejemplo `.search.msn.com`). Los valores se normalizan automáticamente a minúsculas.
  - **Listas ASN** pueden contener solo el número (`32934`) o el número con el prefijo `AS` (`AS15169`).
  - **Listas de User-Agent** se tratan como patrones PCRE y se conserva la línea completa (incluidos los espacios). Mantenga los comentarios en una línea separada para que no se interpreten como parte del patrón.
  - **Listas URI** deben comenzar con `/` y pueden usar tokens PCRE como `^` o `$`.

Ejemplos de archivos con el formato esperado:

```text
# /etc/bunkerweb/lists/ip-blacklist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-blacklist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```

## Brotli

Compatibilidad con STREAM :x:

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

## BunkerNet

Compatibilidad con STREAM :white_check_mark:

El complemento BunkerNet permite el intercambio colectivo de inteligencia sobre amenazas entre las instancias de BunkerWeb, creando una poderosa red de protección contra actores maliciosos. Al participar en BunkerNet, su instancia se beneficia y contribuye a una base de datos global de amenazas conocidas, mejorando la seguridad para toda la comunidad de BunkerWeb.

**Cómo funciona:**

1.  Su instancia de BunkerWeb se registra automáticamente con la API de BunkerNet para recibir un identificador único.
2.  Cuando su instancia detecta y bloquea una dirección IP o comportamiento malicioso, informa anónimamente la amenaza a BunkerNet.
3.  BunkerNet agrega la inteligencia sobre amenazas de todas las instancias participantes y distribuye la base de datos consolidada.
4.  Su instancia descarga regularmente una base de datos actualizada de amenazas conocidas desde BunkerNet.
5.  Esta inteligencia colectiva permite que su instancia bloquee proactivamente las direcciones IP que han exhibido comportamiento malicioso en otras instancias de BunkerWeb.

!!! success "Beneficios clave"

      1. **Defensa Colectiva:** Aproveche los hallazgos de seguridad de miles de otras instancias de BunkerWeb a nivel mundial.
      2. **Protección Proactiva:** Bloquee a los actores maliciosos antes de que puedan atacar su sitio basándose en su comportamiento en otros lugares.
      3. **Contribución a la Comunidad:** Ayude a proteger a otros usuarios de BunkerWeb compartiendo datos de amenazas anónimos sobre los atacantes.
      4. **Cero Configuración:** Funciona desde el primer momento con valores predeterminados sensatos, requiriendo una configuración mínima.
      5. **Enfoque en la Privacidad:** Solo comparte la información de amenazas necesaria sin comprometer su privacidad ni la de sus usuarios.

### Cómo usar

Siga estos pasos para configurar y usar la función BunkerNet:

1.  **Habilite la función:** La función BunkerNet está habilitada por defecto. Si es necesario, puede controlarla con la configuración `USE_BUNKERNET`.
2.  **Registro inicial:** En el primer arranque, su instancia se registrará automáticamente con la API de BunkerNet y recibirá un identificador único.
3.  **Actualizaciones automáticas:** Su instancia descargará automáticamente la última base de datos de amenazas en un horario regular.
4.  **Informes automáticos:** Cuando su instancia bloquee una dirección IP maliciosa, contribuirá automáticamente estos datos a la comunidad.
5.  **Monitoree la protección:** Consulte la [interfaz de usuario web](web-ui.md) para ver estadísticas sobre las amenazas bloqueadas por la inteligencia de BunkerNet.

### Ajustes de configuración

| Ajuste             | Valor por defecto          | Contexto  | Múltiple | Descripción                                                                                                             |
| ------------------ | -------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------- |
| `USE_BUNKERNET`    | `yes`                      | multisite | no       | **Habilitar BunkerNet:** Establezca en `yes` para habilitar el intercambio de inteligencia sobre amenazas de BunkerNet. |
| `BUNKERNET_SERVER` | `https://api.bunkerweb.io` | global    | no       | **Servidor BunkerNet:** La dirección del servidor de la API de BunkerNet para compartir inteligencia sobre amenazas.    |

!!! tip "Protección de Red"
    Cuando BunkerNet detecta que una dirección IP ha estado involucrada en actividades maliciosas en múltiples instancias de BunkerWeb, añade esa IP a una lista negra colectiva. Esto proporciona una capa de defensa proactiva, protegiendo su sitio de amenazas antes de que puedan atacarlo directamente.

!!! info "Informes Anónimos"
    Al informar sobre amenazas a BunkerNet, su instancia solo comparte los datos necesarios para identificar la amenaza: la dirección IP, el motivo del bloqueo y datos contextuales mínimos. No se comparte información personal sobre sus usuarios ni detalles sensibles sobre su sitio.

### Configuraciones de Ejemplo

=== "Configuración por Defecto (Recomendada)"

    La configuración por defecto habilita BunkerNet con el servidor oficial de la API de BunkerWeb:

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://api.bunkerweb.io"
    ```

=== "Configuración Deshabilitada"

    Si prefiere no participar en la red de inteligencia sobre amenazas de BunkerNet:

    ```yaml
    USE_BUNKERNET: "no"
    ```

=== "Configuración de Servidor Personalizado"

    Para organizaciones que ejecutan su propio servidor BunkerNet (poco común):

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://bunkernet.example.com"
    ```

### Integración con la Consola de CrowdSec

Si aún no está familiarizado con la integración de la Consola de CrowdSec, [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) aprovecha la inteligencia colectiva para combatir las ciberamenazas. Piense en ello como el "Waze de la ciberseguridad": cuando un servidor es atacado, otros sistemas en todo el mundo son alertados y protegidos de los mismos atacantes. Puede obtener más información al respecto [aquí](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

A través de nuestra asociación con CrowdSec, puede inscribir sus instancias de BunkerWeb en su [Consola de CrowdSec](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration). Esto significa que los ataques bloqueados por BunkerWeb serán visibles en su Consola de CrowdSec junto con los ataques bloqueados por los Motores de Seguridad de CrowdSec, brindándole una vista unificada de las amenazas.

Es importante destacar que no es necesario instalar CrowdSec para esta integración (aunque recomendamos encarecidamente probarlo con el [complemento de CrowdSec para BunkerWeb](https://github.com/bunkerity/bunkerweb-plugins/tree/main/crowdsec) para mejorar aún más la seguridad de sus servicios web). Además, puede inscribir sus Motores de Seguridad de CrowdSec en la misma cuenta de la Consola para una sinergia aún mayor.

**Paso #1: Cree su cuenta en la Consola de CrowdSec**

Vaya a la [Consola de CrowdSec](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration) y regístrese si aún no tiene una cuenta. Una vez hecho esto, anote la clave de inscripción que se encuentra en "Security Engines" después de hacer clic en "Add Security Engine":

<figure markdown>
  ![Descripción general](assets/img/crowdity1.png){ align=center }
  <figcaption>Obtenga su clave de inscripción de la Consola de CrowdSec</figcaption>
</figure>

**Paso #2: Obtenga su ID de BunkerNet**

Activar la función BunkerNet (habilitada por defecto) es obligatorio si desea inscribir su(s) instancia(s) de BunkerWeb en su Consola de CrowdSec. Habilítela estableciendo `USE_BUNKERNET` en `yes`.

Para Docker, obtenga su ID de BunkerNet usando:

```shell
docker exec mi-bw-scheduler cat /var/cache/bunkerweb/bunkernet/instance.id
```

Para Linux, use:

```shell
cat /var/cache/bunkerweb/bunkernet/instance.id
```

**Paso #3: Inscriba su instancia usando el Panel**

Una vez que tenga su ID de BunkerNet y la clave de inscripción de la Consola de CrowdSec, [solicite el producto gratuito "BunkerNet / CrowdSec" en el Panel](https://panel.bunkerweb.io/store/bunkernet?utm_campaign=self&utm_source=doc). Es posible que se le pida que cree una cuenta si aún no lo ha hecho.

Ahora puede seleccionar el servicio "BunkerNet / CrowdSec" y completar el formulario pegando su ID de BunkerNet y la clave de inscripción de la Consola de CrowdSec:

<figure markdown>
  ![Descripción general](assets/img/crowdity2.png){ align=center }
  <figcaption>Inscriba su instancia de BunkerWeb en la Consola de CrowdSec</figcaption>
</figure>

**Paso #4: Acepte el nuevo motor de seguridad en la Consola**

Luego, vuelva a su Consola de CrowdSec y acepte el nuevo Motor de Seguridad:

<figure markdown>
  ![Descripción general](assets/img/crowdity3.png){ align=center }
  <figcaption>Acepte la inscripción en la Consola de CrowdSec</figcaption>
</figure>

**¡Felicitaciones, su instancia de BunkerWeb ahora está inscrita en su Consola de CrowdSec!**

Consejo profesional: Al ver sus alertas, haga clic en la opción "columnas" y marque la casilla "contexto" para acceder a datos específicos de BunkerWeb.

<figure markdown>
  ![Descripción general](assets/img/crowdity4.png){ align=center }
  <figcaption>Datos de BunkerWeb mostrados en la columna de contexto</figcaption>
</figure>

## CORS

Compatibilidad con STREAM :x:

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

## Cache <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Compatibilidad con STREAM :x:

Provides caching functionality at the reverse proxy level.

| Parámetro                   | Valor predeterminado              | Contexto  | Múltiple | Descripción                                                                    |
| --------------------------- | --------------------------------- | --------- | -------- | ------------------------------------------------------------------------------ |
| `CACHE_PATH`                |                                   | global    | sí       | Path and parameters for a cache.                                               |
| `CACHE_ZONE`                |                                   | multisite | no       | Name of cache zone to use (specified in a CACHE_PATH setting).                 |
| `CACHE_HEADER`              | `X-Cache`                         | multisite | no       | Add header about cache status.                                                 |
| `CACHE_BACKGROUND_UPDATE`   | `no`                              | multisite | no       | Enable or disable background update of the cache.                              |
| `CACHE_BYPASS`              |                                   | multisite | no       | List of variables to determine if the cache should be bypassed or not.         |
| `CACHE_NO_CACHE`            | `$http_pragma$http_authorization` | multisite | no       | Disable caching if variables are set.                                          |
| `CACHE_KEY`                 | `$scheme$proxy_host$request_uri`  | multisite | no       | Key used to identify cached elements.                                          |
| `CACHE_CONVERT_HEAD_TO_GET` | `yes`                             | multisite | no       | Convert HEAD requests to GET when caching.                                     |
| `CACHE_LOCK`                | `no`                              | multisite | no       | Lock concurrent requests when populating the cache.                            |
| `CACHE_LOCK_AGE`            | `5s`                              | multisite | no       | Pass request to upstream if cache is locked for that time (possible cache).    |
| `CACHE_LOCK_TIMEOUT`        | `5s`                              | multisite | no       | Pass request to upstream if cache is locked for that time (no cache).          |
| `CACHE_METHODS`             | `GET HEAD`                        | multisite | no       | Only cache response if corresponding method is present.                        |
| `CACHE_MIN_USES`            | `1`                               | multisite | no       | Number of requests before we put the corresponding response in cache.          |
| `CACHE_REVALIDATE`          | `no`                              | multisite | no       | Revalidate expired items using conditional requests to upstream.               |
| `CACHE_USE_STALE`           | `off`                             | multisite | no       | Determines the use of staled cache response (proxy_cache_use_stale directive). |
| `CACHE_VALID`               | `10m`                             | multisite | sí       | Defines default caching with optional status code.                             |

## Client cache

Compatibilidad con STREAM :x:

El complemento de Caché del Cliente optimiza el rendimiento del sitio web al controlar cómo los navegadores almacenan en caché el contenido estático. Reduce el uso de ancho de banda, disminuye la carga del servidor y mejora los tiempos de carga de la página al indicar a los navegadores que almacenen y reutilicen activos estáticos —como imágenes, archivos CSS y JavaScript— localmente en lugar de solicitarlos en cada visita a la página.

**Cómo funciona:**

1.  Cuando está habilitado, BunkerWeb agrega encabezados `Cache-Control` a las respuestas para archivos estáticos.
2.  Estos encabezados le dicen a los navegadores por cuánto tiempo deben almacenar el contenido en caché localmente.
3.  Para los archivos con extensiones específicas (como imágenes, CSS, JavaScript), BunkerWeb aplica la política de almacenamiento en caché configurada.
4.  El soporte opcional de ETag proporciona un mecanismo de validación adicional para determinar si el contenido en caché todavía está actualizado.
5.  Cuando los visitantes regresan a su sitio, sus navegadores pueden usar los archivos almacenados en caché localmente en lugar de descargarlos nuevamente, lo que resulta en tiempos de carga de página más rápidos.

### Cómo usar

Siga estos pasos para configurar y usar la función de Caché del Cliente:

1.  **Habilite la función:** La función de Caché del Cliente está deshabilitada por defecto; establezca la configuración `USE_CLIENT_CACHE` en `yes` para habilitarla.
2.  **Configure las extensiones de archivo:** Especifique qué tipos de archivo deben almacenarse en caché utilizando la configuración `CLIENT_CACHE_EXTENSIONS`.
3.  **Establezca las directivas de control de caché:** Personalice cómo los clientes deben almacenar el contenido en caché utilizando la configuración `CLIENT_CACHE_CONTROL`.
4.  **Configure el soporte de ETag:** Decida si habilitar los ETags para validar la frescura de la caché con la configuración `CLIENT_CACHE_ETAG`.
5.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, los encabezados de caché se aplican automáticamente a las respuestas elegibles.

### Ajustes de Configuración

| Ajuste                    | Valor por defecto          | Contexto  | Múltiple | Descripción                                                                                                                                    |
| ------------------------- | -------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CLIENT_CACHE`        | `no`                       | multisite | no       | **Habilitar Caché del Cliente:** Establezca en `yes` para habilitar el almacenamiento en caché del lado del cliente de los archivos estáticos. |
| `CLIENT_CACHE_EXTENSIONS` | `jpg                       | jpeg      | png      | bmp                                                                                                                                            | ico | svg | tif | css | js | otf | ttf | eot | woff | woff2` | global | no | **Extensiones Cacheadas:** Lista de extensiones de archivo (separadas por barras verticales) que deben ser almacenadas en caché por el cliente. |
| `CLIENT_CACHE_CONTROL`    | `public, max-age=15552000` | multisite | no       | **Encabezado Cache-Control:** Valor para el encabezado HTTP Cache-Control para controlar el comportamiento del almacenamiento en caché.        |
| `CLIENT_CACHE_ETAG`       | `yes`                      | multisite | no       | **Habilitar ETags:** Establezca en `yes` para enviar el encabezado HTTP ETag para los recursos estáticos.                                      |

!!! tip "Optimizando los Ajustes de Caché"
    Para contenido que se actualiza con frecuencia, considere usar valores de `max-age` más cortos. Para contenido que cambia raramente (como bibliotecas de JavaScript versionadas o logotipos), use tiempos de caché más largos. El valor por defecto de 15552000 segundos (180 días) es apropiado para la mayoría de los activos estáticos.

!!! info "Comportamiento del Navegador"
    Diferentes navegadores implementan el almacenamiento en caché de manera ligeramente diferente, pero todos los navegadores modernos respetan las directivas estándar de `Cache-Control`. Los ETags proporcionan un mecanismo de validación adicional que ayuda a los navegadores a determinar si el contenido en caché sigue siendo válido.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple que habilita el almacenamiento en caché para activos estáticos comunes:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|gif|css|js|svg|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=86400"  # 1 día
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Almacenamiento en Caché Agresivo"

    Configuración optimizada para un almacenamiento en caché máximo, adecuada para sitios con contenido estático que se actualiza con poca frecuencia:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2|pdf|xml|txt"
    CLIENT_CACHE_CONTROL: "public, max-age=31536000, immutable"  # 1 año
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Estrategia de Contenido Mixto"

    Para sitios con una mezcla de contenido actualizado con frecuencia y con poca frecuencia, considere usar el versionado de archivos en su aplicación y una configuración como esta:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=604800"  # 1 semana
    CLIENT_CACHE_ETAG: "yes"
    ```

## Country

Compatibilidad con STREAM :white_check_mark:

El complemento de País habilita la funcionalidad de bloqueo geográfico para su sitio web, permitiéndole restringir el acceso según la ubicación geográfica de sus visitantes. Esta función le ayuda a cumplir con las regulaciones regionales, prevenir actividades fraudulentas a menudo asociadas con regiones de alto riesgo e implementar restricciones de contenido basadas en límites geográficos.

**Cómo funciona:**

1.  Cuando un visitante accede a su sitio web, BunkerWeb determina su país basándose en su dirección IP.
2.  Su configuración especifica una lista blanca (países permitidos) o una lista negra (países bloqueados).
3.  Si ha configurado una lista blanca, solo los visitantes de los países de esa lista tendrán acceso.
4.  Si ha configurado una lista negra, se denegará el acceso a los visitantes de los países de esa lista.
5.  El resultado se almacena en caché para mejorar el rendimiento de los visitantes recurrentes de la misma dirección IP.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de País:

1.  **Defina su estrategia:** Decida si desea utilizar un enfoque de lista blanca (permitir solo países específicos) o un enfoque de lista negra (bloquear países específicos).
2.  **Configure los códigos de país:** Añada los códigos de país ISO 3166-1 alfa-2 (códigos de dos letras como US, GB, FR) a la configuración `WHITELIST_COUNTRY` o `BLACKLIST_COUNTRY`.
3.  **Aplique la configuración:** Una vez configuradas, las restricciones basadas en el país se aplicarán a todos los visitantes de su sitio.
4.  **Supervise la eficacia:** Consulte la [interfaz de usuario web](web-ui.md) para ver estadísticas sobre las solicitudes bloqueadas por país.

### Ajustes de configuración

| Ajuste              | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                             |
| ------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `WHITELIST_COUNTRY` |                   | multisite | no       | **Lista Blanca de Países:** Lista de códigos de país (formato ISO 3166-1 alfa-2) separados por espacios. Solo se permiten estos países. |
| `BLACKLIST_COUNTRY` |                   | multisite | no       | **Lista Negra de Países:** Lista de códigos de país (formato ISO 3166-1 alfa-2) separados por espacios. Estos países están bloqueados.  |

!!! tip "Lista Blanca vs. Lista Negra"
    Elija el enfoque que mejor se adapte a sus necesidades:

    -   Use la lista blanca cuando quiera restringir el acceso a un pequeño número de países.
    -   Use la lista negra cuando quiera bloquear el acceso desde regiones problemáticas específicas mientras permite a todos los demás.

!!! warning "Regla de Precedencia"
    Si se configuran tanto la lista blanca como la lista negra, la lista blanca tiene prioridad. Esto significa que el sistema primero comprueba si un país está en la lista blanca; si no, se deniega el acceso independientemente de la configuración de la lista negra.

!!! info "Detección de País"
    BunkerWeb utiliza la [base de datos mmdb lite de db-ip](https://db-ip.com/db/download/ip-to-country-lite) para determinar el país de origen basándose en las direcciones IP.

### Configuraciones de Ejemplo

=== "Solo Lista Blanca"

    Permitir el acceso solo desde Estados Unidos, Canadá y el Reino Unido:

    ```yaml
    WHITELIST_COUNTRY: "US CA GB"
    ```

=== "Solo Lista Negra"

    Bloquear el acceso desde países específicos mientras se permite a todos los demás:

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP"
    ```

=== "Acceso Solo para la UE"

    Permitir el acceso solo desde los estados miembros de la Unión Europea:

    ```yaml
    WHITELIST_COUNTRY: "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE"
    ```

=== "Bloqueo de Países de Alto Riesgo"

    Bloquear el acceso desde países a menudo asociados con ciertas ciberamenazas:

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP IR SY"
    ```

## CrowdSec

Compatibilidad con STREAM :x:

<figure markdown>
  ![Descripción general](assets/img/crowdsec.svg){ align=center, width="600" }
</figure>

El complemento CrowdSec integra BunkerWeb con el motor de seguridad CrowdSec, proporcionando una capa adicional de protección contra diversas ciberamenazas. Este complemento actúa como un bouncer de [CrowdSec](https://crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs), denegando solicitudes basadas en decisiones de la API de CrowdSec.

CrowdSec es un motor de seguridad moderno y de código abierto que detecta y bloquea direcciones IP maliciosas basándose en el análisis de comportamiento y la inteligencia colectiva de su comunidad. También puede configurar [escenarios](https://docs.crowdsec.net/docs/concepts?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios) para prohibir automáticamente direcciones IP basadas en comportamiento sospechoso, beneficiándose de una lista negra de origen colectivo.

**Cómo funciona:**

1.  El motor de CrowdSec analiza los registros y detecta actividades sospechosas en su infraestructura.
2.  Cuando se detecta una actividad maliciosa, CrowdSec crea una decisión para bloquear la dirección IP infractora.
3.  BunkerWeb, actuando como un bouncer, consulta la API local de CrowdSec para obtener decisiones sobre las solicitudes entrantes.
4.  Si la dirección IP de un cliente tiene una decisión de bloqueo activa, BunkerWeb deniega el acceso a los servicios protegidos.
5.  Opcionalmente, el Componente de Seguridad de Aplicaciones puede realizar una inspección profunda de las solicitudes para una mayor seguridad.

!!! success "Beneficios clave"

      1. **Seguridad impulsada por la comunidad:** Benefíciese de la inteligencia de amenazas compartida en toda la comunidad de usuarios de CrowdSec.
      2. **Análisis de comportamiento:** Detecte ataques sofisticados basados en patrones de comportamiento, no solo en firmas.
      3. **Integración ligera:** Impacto mínimo en el rendimiento de su instancia de BunkerWeb.
      4. **Protección multinivel:** Combine la defensa perimetral (bloqueo de IP) con la seguridad de aplicaciones para una protección en profundidad.

### Requisitos previos

- Una API local de CrowdSec a la que BunkerWeb pueda acceder (normalmente el agente que se ejecuta en el mismo host o dentro de la misma red Docker).
- Acceso a los registros de acceso de BunkerWeb (`/var/log/bunkerweb/access.log` de forma predeterminada) para que el agente de CrowdSec pueda analizar las solicitudes.
- Acceso a `cscli` en el host de CrowdSec para registrar la clave del bouncer de BunkerWeb.

### Flujo de integración

1. Preparar el agente de CrowdSec para ingerir los registros de BunkerWeb.
2. Configurar BunkerWeb para que consulte la API local de CrowdSec.
3. Validar el enlace mediante la API `/crowdsec/ping` o la tarjeta de CrowdSec en el panel de administración.

Las siguientes secciones desarrollan cada paso.

### Paso&nbsp;1 – Preparar CrowdSec para ingerir los registros de BunkerWeb

=== "Docker"
    **Archivo de adquisición**

    Necesitará ejecutar una instancia de CrowdSec y configurarla para analizar los registros de BunkerWeb. Utilice el valor dedicado `bunkerweb` para el parámetro `type` en su archivo de adquisición (suponiendo que los registros de BunkerWeb se almacenan tal cual sin datos adicionales):

    ```yaml
    filenames:
      - /var/log/bunkerweb.log
    labels:
      type: bunkerweb
    ```

    Si la colección no aparece dentro del contenedor de CrowdSec, ejecuta `docker exec -it <crowdsec-container> cscli hub update` y luego reinicia ese contenedor (`docker restart <crowdsec-container>`) para que los nuevos recursos estén disponibles. Sustituye `<crowdsec-container>` por el nombre de tu contenedor CrowdSec.

    **Componente de Seguridad de Aplicaciones (*opcional*)**

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    **Syslog**

    ```syslog
    @version: 4.10

    source s_net {
        udp(
            ip("0.0.0.0")
        );
    };

    template t_imp {
        template("$MSG\n");
        template_escape(no);
    };

    destination d_file {
        file("/var/log/bunkerweb.log" template(t_imp) logrotate(enable(yes), size(100MB), rotations(7)));
    };

    log {
        source(s_net);
        destination(d_file);
    };
    ```

    **Docker Compose**

    ```yaml
    x-bw-env: &bw-env
      # Usamos un ancla para evitar repetir la misma configuración para ambos servicios
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Asegúrese de establecer el rango de IP correcto para que el planificador pueda enviar la configuración a la instancia

    services:
      bunkerweb:
        # Este es el nombre que se utilizará para identificar la instancia en el Planificador
        image: bunkerity/bunkerweb:1.6.7-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Para soporte de QUIC / HTTP3
        environment:
          <<: *bw-env # Usamos el ancla para evitar repetir la misma configuración para todos los servicios
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog # Enviar registros a syslog
          options:
            syslog-address: "udp://10.20.30.254:514" # La dirección IP del servicio syslog

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Asegúrese de establecer el nombre de instancia correcto
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerde establecer una contraseña más segura para la base de datos
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_CROWDSEC: "yes"
          CROWDSEC_API: "http://crowdsec:8080" # Esta es la dirección de la API del contenedor de CrowdSec en la misma red
          CROWDSEC_APPSEC_URL: "http://crowdsec:7422" # Comente si no desea usar el Componente AppSec
          CROWDSEC_API_KEY: "s3cr3tb0unc3rk3y" # Recuerde establecer una clave más segura para el bouncer
        volumes:
          - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Establecemos el tamaño máximo de paquete permitido para evitar problemas con consultas grandes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Recuerde establecer una contraseña más segura para la base de datos
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      crowdsec:
        image: crowdsecurity/crowdsec:v1.7.3 # Use la última versión pero siempre fije la versión para una mejor estabilidad/seguridad
        volumes:
          - cs-data:/var/lib/crowdsec/data # Para persistir los datos de CrowdSec
          - bw-logs:/var/log:ro # Los registros de BunkerWeb para que CrowdSec los analice
          - ./acquis.yaml:/etc/crowdsec/acquis.yaml # El archivo de adquisición para los registros de BunkerWeb
          - ./appsec.yaml:/etc/crowdsec/acquis.d/appsec.yaml # Comente si no desea usar el Componente AppSec
        environment:
          BOUNCER_KEY_bunkerweb: "s3cr3tb0unc3rk3y" # Recuerde establecer una clave más segura para el bouncer
          COLLECTIONS: "bunkerity/bunkerweb crowdsecurity/appsec-virtual-patching crowdsecurity/appsec-generic-rules"
          #   COLLECTIONS: "bunkerity/bunkerweb" # Si no desea usar el Componente AppSec, use esta línea en su lugar
        networks:
          - bw-universe

      syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE  # Vincular a puertos bajos
          - NET_BROADCAST  # Enviar difusiones
          - NET_RAW  # Usar sockets sin procesar
          - DAC_READ_SEARCH  # Leer archivos omitiendo permisos
          - DAC_OVERRIDE  # Anular permisos de archivo
          - CHOWN  # Cambiar propietario
          - SYSLOG  # Escribir en registros del sistema
        volumes:
          - bw-logs:/var/log/bunkerweb # Este es el volumen utilizado para almacenar los registros
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # Este es el archivo de configuración de syslog-ng
        networks:
            bw-universe:
              ipv4_address: 10.20.30.254

    volumes:
      bw-data:
      bw-storage:
      bw-logs:
      cs-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Asegúrese de establecer el rango de IP correcto para que el planificador pueda enviar la configuración a la instancia
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Linux"

    Necesita instalar CrowdSec y configurarlo para analizar los registros de BunkerWeb. Siga la [documentación oficial](https://doc.crowdsec.net/docs/getting_started/install_crowdsec?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios).

    Para permitir que CrowdSec analice los registros de BunkerWeb, agregue las siguientes líneas a su archivo de adquisición ubicado en `/etc/crowdsec/acquis.yaml`:

    ```yaml
    filenames:
      - /var/log/bunkerweb/access.log
      - /var/log/bunkerweb/error.log
      - /var/log/bunkerweb/modsec_audit.log
    labels:
        type: bunkerweb
    ```

    Actualiza el hub de CrowdSec e instala la colección de BunkerWeb:

    ```shell
    sudo cscli hub update
    sudo cscli collections install bunkerity/bunkerweb
    ```

    Ahora, agregue su bouncer personalizado a la API de CrowdSec usando la herramienta `cscli`:

    ```shell
    sudo cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6
    ```

    !!! warning "Clave de API"
        Guarde la clave generada por el comando `cscli`; la necesitará más tarde.

    Luego reinicie el servicio de CrowdSec:

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Componente de Seguridad de Aplicaciones (*opcional*)**

    Si desea usar el Componente AppSec, debe crear otro archivo de adquisición para él ubicado en `/etc/crowdsec/acquis.d/appsec.yaml`:

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
        type: appsec
    listen_addr: 127.0.0.1:7422
    source: appsec
    ```

    También necesitará instalar las colecciones del Componente AppSec:

    ```shell
    sudo cscli collections install crowdsecurity/appsec-virtual-patching
    sudo cscli collections install crowdsecurity/appsec-generic-rules
    ```

    Finalmente, reinicie el servicio de CrowdSec:

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Ajustes**

    Configure el complemento agregando los siguientes ajustes a su archivo de configuración de BunkerWeb:

    ```env
    USE_CROWDSEC=yes
    CROWDSEC_API=http://127.0.0.1:8080
    CROWDSEC_API_KEY=<La clave proporcionada por cscli>
    # Comente si no desea usar el Componente AppSec
    CROWDSEC_APPSEC_URL=http://127.0.0.1:7422
    ```

    Finalmente, recargue el servicio de BunkerWeb:

    ```shell
    sudo systemctl reload bunkerweb
    ```

=== "Todo en uno"

    La imagen Docker Todo en Uno (AIO) de BunkerWeb viene con CrowdSec totalmente integrado. No necesita configurar una instancia de CrowdSec separada ni configurar manualmente los archivos de adquisición para los registros de BunkerWeb cuando usa el agente interno de CrowdSec.

    Consulte la [documentación de integración de la Imagen Todo en Uno (AIO)](integrations.md#crowdsec-integration).

### Paso&nbsp;2 – Configurar los ajustes de BunkerWeb

Aplica las siguientes variables de entorno (o valores del scheduler) para que la instancia de BunkerWeb pueda comunicarse con la API local de CrowdSec. Como mínimo necesitas `USE_CROWDSEC`, `CROWDSEC_API` y una clave válida creada con `cscli bouncers add`.

| Ajuste                      | Valor por defecto      | Contexto  | Múltiple | Descripción                                                                                                                                   |
| --------------------------- | ---------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | no       | **Habilitar CrowdSec:** Establezca en `yes` para habilitar el bouncer de CrowdSec.                                                            |
| `CROWDSEC_API`              | `http://crowdsec:8080` | global    | no       | **URL de la API de CrowdSec:** La dirección del servicio de la API Local de CrowdSec.                                                         |
| `CROWDSEC_API_KEY`          |                        | global    | no       | **Clave de API de CrowdSec:** La clave de API para autenticarse con la API de CrowdSec, obtenida usando `cscli bouncers add`.                 |
| `CROWDSEC_MODE`             | `live`                 | global    | no       | **Modo de Operación:** `live` (consultar la API para cada solicitud) o `stream` (almacenar en caché periódicamente todas las decisiones).     |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | global    | no       | **Tráfico Interno:** Establezca en `yes` para verificar el tráfico interno contra las decisiones de CrowdSec.                                 |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | global    | no       | **Tiempo de Espera de la Solicitud:** Tiempo de espera en milisegundos para las solicitudes HTTP a la API Local de CrowdSec en modo `live`.   |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | global    | no       | **Ubicaciones Excluidas:** Lista de ubicaciones (URI) separadas por comas para excluir de las verificaciones de CrowdSec.                     |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | global    | no       | **Expiración de la Caché:** El tiempo de expiración de la caché en segundos para las decisiones de IP en modo `live`.                         |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | global    | no       | **Frecuencia de Actualización:** Con qué frecuencia (en segundos) obtener decisiones nuevas/expiradas de la API de CrowdSec en modo `stream`. |

#### Ajustes del Componente de Seguridad de Aplicaciones

| Ajuste                            | Valor por defecto | Contexto | Múltiple | Descripción                                                                                                                      |
| --------------------------------- | ----------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `CROWDSEC_APPSEC_URL`             |                   | global   | no       | **URL de AppSec:** La URL del Componente de Seguridad de Aplicaciones de CrowdSec. Dejar vacío para deshabilitar AppSec.         |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough`     | global   | no       | **Acción en Caso de Falla:** Acción a tomar cuando AppSec devuelve un error. Puede ser `passthrough` o `deny`.                   |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`             | global   | no       | **Tiempo de Espera de Conexión:** El tiempo de espera en milisegundos para conectarse al Componente AppSec.                      |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`             | global   | no       | **Tiempo de Espera de Envío:** El tiempo de espera en milisegundos para enviar datos al Componente AppSec.                       |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`             | global   | no       | **Tiempo de Espera de Procesamiento:** El tiempo de espera en milisegundos para procesar la solicitud en el Componente AppSec.   |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`              | global   | no       | **Enviar Siempre:** Establezca en `yes` para enviar siempre las solicitudes a AppSec, incluso si hay una decisión a nivel de IP. |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`              | global   | no       | **Verificar SSL:** Establezca en `yes` para verificar el certificado SSL del Componente AppSec.                                  |

!!! info "Sobre los Modos de Operación" - **Modo `live`** consulta la API de CrowdSec para cada solicitud entrante, proporcionando protección en tiempo real a costa de una mayor latencia. - **Modo `stream`** descarga periódicamente todas las decisiones de la API de CrowdSec y las almacena en caché localmente, reduciendo la latencia con un ligero retraso en la aplicación de nuevas decisiones.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Esta es una configuración simple para cuando CrowdSec se ejecuta en el mismo host:

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "tu-clave-de-api-aqui"
    CROWDSEC_MODE: "live"
    ```

=== "Configuración Avanzada con AppSec"

    Una configuración más completa que incluye el Componente de Seguridad de Aplicaciones:

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "tu-clave-de-api-aqui"
    CROWDSEC_MODE: "stream"
    CROWDSEC_UPDATE_FREQUENCY: "30"
    CROWDSEC_EXCLUDE_LOCATION: "/health,/metrics"

    # Configuración de AppSec
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_APPSEC_FAILURE_ACTION: "deny"
    CROWDSEC_ALWAYS_SEND_TO_APPSEC: "yes"
    CROWDSEC_APPSEC_SSL_VERIFY: "yes"
    ```

### Paso&nbsp;3 – Validar la integración

- En los registros del scheduler, busque las entradas `CrowdSec configuration successfully generated` y `CrowdSec bouncer denied request` para verificar que el complemento esté activo.
- En el lado de CrowdSec, supervise `cscli metrics show` o la CrowdSec Console para asegurarse de que las decisiones de BunkerWeb aparezcan como se espera.
- En la interfaz de BunkerWeb, abra la página del complemento CrowdSec para ver el estado de la integración.
    # Configuración de AppSec
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_APPSEC_FAILURE_ACTION: "deny"
    CROWDSEC_ALWAYS_SEND_TO_APPSEC: "yes"
    CROWDSEC_APPSEC_SSL_VERIFY: "yes"
    ```

## Custom Pages <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Compatibilidad con STREAM :x:

Tweak BunkerWeb error/antibot/default pages with custom HTML.

| Parámetro                        | Valor predeterminado | Contexto  | Múltiple | Descripción                                                                                                        |
| -------------------------------- | -------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------ |
| `CUSTOM_ERROR_PAGE`              |                      | multisite | no       | Full path of the custom error page (must be readable by the scheduler) (Can be a lua template).                    |
| `CUSTOM_DEFAULT_SERVER_PAGE`     |                      | global    | no       | Full path of the custom default server page (must be readable by the scheduler) (Can be a lua template).           |
| `CUSTOM_ANTIBOT_CAPTCHA_PAGE`    |                      | multisite | no       | Full path of the custom antibot captcha page (must be readable by the scheduler) (Can be a lua template).          |
| `CUSTOM_ANTIBOT_JAVASCRIPT_PAGE` |                      | multisite | no       | Full path of the custom antibot javascript check page (must be readable by the scheduler) (Can be a lua template). |
| `CUSTOM_ANTIBOT_RECAPTCHA_PAGE`  |                      | multisite | no       | Full path of the custom antibot recaptcha page (must be readable by the scheduler) (Can be a lua template).        |
| `CUSTOM_ANTIBOT_HCAPTCHA_PAGE`   |                      | multisite | no       | Full path of the custom antibot hcaptcha page (must be readable by the scheduler) (Can be a lua template).         |
| `CUSTOM_ANTIBOT_TURNSTILE_PAGE`  |                      | multisite | no       | Full path of the custom antibot turnstile page (must be readable by the scheduler) (Can be a lua template).        |
| `CUSTOM_ANTIBOT_MCAPTCHA_PAGE`   |                      | multisite | no       | Full path of the custom antibot mcaptcha page (must be readable by the scheduler) (Can be a lua template).         |

## Custom SSL certificate

Compatibilidad con STREAM :white_check_mark:

El complemento de certificado SSL personalizado le permite usar sus propios certificados SSL/TLS con BunkerWeb en lugar de los generados automáticamente. Esta función es particularmente útil si tiene certificados existentes de una Autoridad de Certificación (CA) de confianza, necesita usar certificados con configuraciones específicas o desea mantener una gestión de certificados consistente en toda su infraestructura.

**Cómo funciona:**

1.  Usted proporciona a BunkerWeb sus archivos de certificado y clave privada, ya sea especificando las rutas de los archivos o proporcionando los datos en formato PEM codificado en base64 o en texto plano.
2.  BunkerWeb valida su certificado y clave para asegurarse de que estén formateados correctamente y sean utilizables.
3.  Cuando se establece una conexión segura, BunkerWeb sirve su certificado personalizado en lugar del generado automáticamente.
4.  BunkerWeb supervisa automáticamente la validez de su certificado y muestra advertencias si se acerca a su vencimiento.
5.  Usted tiene control total sobre la gestión de certificados, lo que le permite usar certificados de cualquier emisor que prefiera.

!!! info "Monitoreo Automático de Certificados"
    Cuando habilita SSL/TLS personalizado estableciendo `USE_CUSTOM_SSL` en `yes`, BunkerWeb monitorea automáticamente el certificado personalizado especificado en `CUSTOM_SSL_CERT`. Comprueba los cambios diariamente y recarga NGINX si se detecta alguna modificación, asegurando que el certificado más reciente esté siempre en uso.

### Cómo usar

Siga estos pasos para configurar y usar la función de certificado SSL personalizado:

1.  **Habilite la función:** Establezca el ajuste `USE_CUSTOM_SSL` en `yes` para habilitar el soporte de certificados personalizados.
2.  **Elija un método:** Decida si proporcionar los certificados a través de rutas de archivo o como datos codificados en base64/texto plano, y establezca la prioridad usando `CUSTOM_SSL_CERT_PRIORITY`.
3.  **Proporcione los archivos de certificado:** Si usa rutas de archivo, especifique las ubicaciones de sus archivos de certificado y clave privada.
4.  **O proporcione los datos del certificado:** Si usa datos, proporcione su certificado y clave como cadenas codificadas en base64 o en formato PEM de texto plano.
5.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, BunkerWeb usa automáticamente sus certificados personalizados para todas las conexiones HTTPS.

!!! tip "Configuración en Modo Stream"
    Para el modo stream, debe configurar el ajuste `LISTEN_STREAM_PORT_SSL` para especificar el puerto de escucha SSL/TLS. Este paso es esencial para el correcto funcionamiento en modo stream.

### Ajustes de Configuración

| Ajuste                     | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                      |
| -------------------------- | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CUSTOM_SSL`           | `no`              | multisite | no       | **Habilitar SSL personalizado:** Establezca en `yes` para usar su propio certificado en lugar del generado automáticamente.      |
| `CUSTOM_SSL_CERT_PRIORITY` | `file`            | multisite | no       | **Prioridad del Certificado:** Elija si priorizar el certificado de la ruta del archivo o de los datos base64 (`file` o `data`). |
| `CUSTOM_SSL_CERT`          |                   | multisite | no       | **Ruta del Certificado:** Ruta completa a su archivo de certificado SSL o paquete de certificados.                               |
| `CUSTOM_SSL_KEY`           |                   | multisite | no       | **Ruta de la Clave Privada:** Ruta completa a su archivo de clave privada SSL.                                                   |
| `CUSTOM_SSL_CERT_DATA`     |                   | multisite | no       | **Datos del Certificado:** Su certificado codificado en formato base64 o como texto plano PEM.                                   |
| `CUSTOM_SSL_KEY_DATA`      |                   | multisite | no       | **Datos de la Clave Privada:** Su clave privada codificada en formato base64 o como texto plano PEM.                             |

!!! warning "Consideraciones de Seguridad"
    Cuando use certificados personalizados, asegúrese de que su clave privada esté debidamente protegida y tenga los permisos adecuados. Los archivos deben ser legibles por el programador de BunkerWeb.

!!! tip "Formato del Certificado"
    BunkerWeb espera los certificados en formato PEM. Si su certificado está en un formato diferente, es posible que necesite convertirlo primero.

!!! info "Cadenas de Certificados"
    Si su certificado incluye una cadena (intermediarios), debe proporcionar la cadena de certificados completa en el orden correcto, con su certificado primero, seguido de los certificados intermedios.

### Configuraciones de Ejemplo

=== "Usando Rutas de Archivo"

    Una configuración que usa archivos de certificado y clave en el disco:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/ruta/a/su/certificado.pem"
    CUSTOM_SSL_KEY: "/ruta/a/su/clave-privada.pem"
    ```

=== "Usando Datos Base64"

    Una configuración que usa datos de certificado y clave codificados en base64:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR...certificado codificado en base64...Cg=="
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV...clave codificada en base64...Cg=="
    ```

=== "Usando Datos PEM de Texto Plano"

    Una configuración que usa datos de certificado y clave en texto plano en formato PEM:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: |
      -----BEGIN CERTIFICATE-----
      MIIDdzCCAl+gAwIBAgIUJH...contenido del certificado...AAAA
      -----END CERTIFICATE-----
    CUSTOM_SSL_KEY_DATA: |
      -----BEGIN PRIVATE KEY-----
      MIIEvQIBADAN...contenido de la clave...AAAA
      -----END PRIVATE KEY-----
    ```

=== "Configuración de Respaldo"

    Una configuración que prioriza los archivos pero recurre a los datos base64 si los archivos no están disponibles:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/ruta/a/su/certificado.pem"
    CUSTOM_SSL_KEY: "/ruta/a/su/clave-privada.pem"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR...certificado codificado en base64...Cg=="
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV...clave codificada en base64...Cg=="
    ```

## DNSBL

Compatibilidad con STREAM :white_check_mark:

El complemento DNSBL (Domain Name System Blacklist) proporciona protección contra direcciones IP maliciosas conocidas al verificar las direcciones IP de los clientes contra servidores DNSBL externos. Esta función ayuda a proteger su sitio web contra el spam, las redes de bots y diversos tipos de ciberamenazas al aprovechar listas mantenidas por la comunidad de direcciones IP problemáticas.

**Cómo funciona:**

1.  Cuando un cliente se conecta a su sitio web, BunkerWeb consulta los servidores DNSBL que ha elegido utilizando el protocolo DNS.
2.  La verificación se realiza enviando una consulta de DNS inversa a cada servidor DNSBL con la dirección IP del cliente.
3.  Si algún servidor DNSBL confirma que la dirección IP del cliente está listada como maliciosa, BunkerWeb prohibirá automáticamente al cliente, evitando que amenazas potenciales lleguen a su aplicación.
4.  Los resultados se almacenan en caché para mejorar el rendimiento de los visitantes recurrentes de la misma dirección IP.
5.  Las búsquedas se realizan de manera eficiente utilizando consultas asíncronas para minimizar el impacto en los tiempos de carga de la página.

### Cómo usar

Siga estos pasos para configurar y usar la función DNSBL:

1.  **Habilite la función:** La función DNSBL está deshabilitada de forma predeterminada. Establezca la configuración `USE_DNSBL` en `yes` para habilitarla.
2.  **Configure los servidores DNSBL:** Agregue los nombres de dominio de los servicios DNSBL que desea usar a la configuración `DNSBL_LIST`.
3.  **Aplique la configuración:** Una vez configurado, BunkerWeb verificará automáticamente las conexiones entrantes contra los servidores DNSBL especificados.
4.  **Supervise la eficacia:** Consulte la [interfaz de usuario web](web-ui.md) para ver las estadísticas de las solicitudes bloqueadas por las verificaciones de DNSBL.

### Ajustes de Configuración

**General**

| Ajuste       | Valor por defecto                                   | Contexto  | Múltiple | Descripción                                                                                                    |
| ------------ | --------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------- |
| `USE_DNSBL`  | `no`                                                | multisite | no       | Habilitar DNSBL: establezca en `yes` para habilitar las verificaciones de DNSBL para las conexiones entrantes. |
| `DNSBL_LIST` | `bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org` | global    | no       | Servidores DNSBL: lista de dominios de servidores DNSBL para verificar, separados por espacios.                |

**Listas de Omisión**

| Ajuste                 | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                      |
| ---------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| `DNSBL_IGNORE_IP`      | ``                | multisite | yes      | IPs/CIDRs separados por espacios para omitir las verificaciones de DNSBL (lista blanca).                         |
| `DNSBL_IGNORE_IP_URLS` | ``                | multisite | yes      | URL separadas por espacios que proporcionan IPs/CIDRs para omitir. Admite los esquemas `http(s)://` y `file://`. |

!!! tip "Elección de Servidores DNSBL"
    Elija proveedores de DNSBL de buena reputación para minimizar los falsos positivos. La lista predeterminada incluye servicios bien establecidos que son adecuados para la mayoría de los sitios web:

    -   **bl.blocklist.de:** Lista las IP que han sido detectadas atacando otros servidores.
    -   **sbl.spamhaus.org:** Se centra en fuentes de spam y otras actividades maliciosas.
    -   **xbl.spamhaus.org:** Apunta a sistemas infectados, como máquinas comprometidas o proxies abiertos.

!!! info "Cómo Funciona DNSBL"
    Los servidores DNSBL funcionan respondiendo a consultas DNS con formato especial. Cuando BunkerWeb verifica una dirección IP, invierte la IP y añade el nombre de dominio del DNSBL. Si la consulta DNS resultante devuelve una respuesta de "éxito", la IP se considera en la lista negra.

!!! warning "Consideraciones de Rendimiento"
    Aunque BunkerWeb optimiza las búsquedas de DNSBL para el rendimiento, agregar un gran número de servidores DNSBL podría afectar potencialmente los tiempos de respuesta. Comience con unos pocos servidores DNSBL de buena reputación y supervise el rendimiento antes de agregar más.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple que utiliza los servidores DNSBL predeterminados:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org"
    ```

=== "Configuración Mínima"

    Una configuración mínima que se centra en los servicios DNSBL más fiables:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    ```

    Esta configuración utiliza solo:

    -   **zen.spamhaus.org**: La lista combinada de Spamhaus a menudo se considera suficiente como una solución independiente debido a su amplia cobertura y reputación de precisión. Combina las listas SBL, XBL y PBL en una sola consulta, lo que la hace eficiente y completa.

=== "Excluyendo IPs de Confianza"

    Puede excluir clientes específicos de las verificaciones de DNSBL utilizando valores estáticos y/o archivos remotos:

    -   `DNSBL_IGNORE_IP`: Agregue IPs y rangos CIDR separados por espacios. Ejemplo: `192.0.2.10 203.0.113.0/24 2001:db8::/32`.
    -   `DNSBL_IGNORE_IP_URLS`: Proporcione URL cuyo contenido liste una IP/CIDR por línea. Los comentarios que comienzan con `#` o `;` se ignoran. Las entradas duplicadas se eliminan.

    Cuando la IP de un cliente entrante coincide con la lista de omisión, BunkerWeb omite las búsquedas de DNSBL y almacena en caché el resultado como "ok" para solicitudes posteriores más rápidas.

=== "Usando URL Remotas"

    El trabajo `dnsbl-download` descarga y almacena en caché las IPs a omitir cada hora:

    -   Protocolos: `https://`, `http://` y rutas locales `file://`.
    -   La caché por URL con suma de verificación evita descargas redundantes (período de gracia de 1 hora).
    -   Archivo combinado por servicio: `/var/cache/bunkerweb/dnsbl/<service>/IGNORE_IP.list`.
    -   Se carga al inicio y se combina con `DNSBL_IGNORE_IP`.

    Ejemplo que combina fuentes estáticas y de URL:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP: "10.0.0.0/8 192.168.0.0/16 2001:db8::/32"
    DNSBL_IGNORE_IP_URLS: "https://example.com/allow-cidrs.txt file:///etc/bunkerweb/dnsbl/ignore.txt"
    ```

=== "Usando Archivos Locales"

    Cargue las IPs a omitir desde archivos locales usando URL `file://`:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP_URLS: "file:///etc/bunkerweb/dnsbl/ignore.txt file:///opt/data/allow-cidrs.txt"
    ```

## Database

Compatibilidad con STREAM :white_check_mark:

El complemento de Base de Datos proporciona una integración robusta de base de datos para BunkerWeb al habilitar el almacenamiento y la gestión centralizados de datos de configuración, registros y otra información esencial.

Este componente principal admite múltiples motores de base de datos, incluidos SQLite, PostgreSQL, MySQL/MariaDB y Oracle, lo que le permite elegir la solución de base de datos que mejor se adapte a su entorno y requisitos.

**Cómo funciona:**

1.  BunkerWeb se conecta a su base de datos configurada utilizando el URI proporcionado en el formato SQLAlchemy.
2.  Los datos críticos de configuración, la información en tiempo de ejecución y los registros de trabajos se almacenan de forma segura en la base de datos.
3.  Los procesos de mantenimiento automático optimizan su base de datos al gestionar el crecimiento de los datos y limpiar los registros sobrantes.
4.  Para escenarios de alta disponibilidad, puede configurar un URI de base de datos de solo lectura que sirva tanto como respaldo (failover) como método para descargar las operaciones de lectura.
5.  Las operaciones de la base de datos se registran según el nivel de registro especificado, proporcionando una visibilidad adecuada de las interacciones con la base de datos.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de Base de Datos:

1.  **Elija un motor de base de datos:** Seleccione entre SQLite (predeterminado), PostgreSQL, MySQL/MariaDB u Oracle según sus requisitos.
2.  **Configure el URI de la base de datos:** Establezca el `DATABASE_URI` para conectarse a su base de datos principal utilizando el formato SQLAlchemy.
3.  **Base de datos de solo lectura opcional:** Para configuraciones de alta disponibilidad, configure un `DATABASE_URI_READONLY` como respaldo o para operaciones de lectura.

### Ajustes de Configuración

| Ajuste                          | Valor por defecto                         | Contexto | Múltiple | Descripción                                                                                                                                                           |
| ------------------------------- | ----------------------------------------- | -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URI`                  | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global   | no       | **URI de la Base de Datos:** La cadena de conexión de la base de datos principal en formato SQLAlchemy.                                                               |
| `DATABASE_URI_READONLY`         |                                           | global   | no       | **URI de la Base de Datos de Solo Lectura:** Base de datos opcional para operaciones de solo lectura o como respaldo si la base de datos principal está caída.        |
| `DATABASE_LOG_LEVEL`            | `warning`                                 | global   | no       | **Nivel de Registro:** El nivel de verbosidad para los registros de la base de datos. Opciones: `debug`, `info`, `warn`, `warning` o `error`.                         |
| `DATABASE_MAX_JOBS_RUNS`        | `10000`                                   | global   | no       | **Máximo de Ejecuciones de Trabajos:** El número máximo de registros de ejecución de trabajos que se conservarán en la base de datos antes de la limpieza automática. |
| `DATABASE_MAX_SESSION_AGE_DAYS` | `14`                                      | global   | no       | **Retención de Sesiones:** La edad máxima (en días) de las sesiones de usuarios de la UI antes de que se purguen automáticamente.                                     |

!!! tip "Selección de Base de Datos" - **SQLite** (predeterminado): Ideal para implementaciones de un solo nodo o entornos de prueba debido a su simplicidad y naturaleza basada en archivos. - **PostgreSQL**: Recomendado para entornos de producción con múltiples instancias de BunkerWeb debido a su robustez y soporte de concurrencia. - **MySQL/MariaDB**: Una buena alternativa a PostgreSQL con capacidades similares de nivel de producción. - **Oracle**: Adecuado para entornos empresariales donde Oracle ya es la plataforma de base de datos estándar.

!!! info "Formato de URI de SQLAlchemy"
    El URI de la base de datos sigue el formato de SQLAlchemy:

    -   SQLite: `sqlite:////ruta/a/database.sqlite3`
    -   PostgreSQL: `postgresql://usuario:contraseña@hostname:puerto/basededatos`
    -   MySQL/MariaDB: `mysql://usuario:contraseña@hostname:puerto/basededatos` o `mariadb://usuario:contraseña@hostname:puerto/basededatos`
    -   Oracle: `oracle://usuario:contraseña@hostname:puerto/basededatos`

!!! warning "Mantenimiento de la Base de Datos"
    El complemento ejecuta automáticamente trabajos de mantenimiento diarios:

- **Limpiar Ejecuciones de Trabajos en Exceso:** Purga el historial que supera el límite `DATABASE_MAX_JOBS_RUNS`.
- **Limpiar Sesiones de UI Caducadas:** Elimina las sesiones de usuarios de la UI que superan `DATABASE_MAX_SESSION_AGE_DAYS`.

Estas tareas evitan el crecimiento ilimitado de la base de datos mientras conservan un historial operativo útil.

## Easy Resolve <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Compatibilidad con STREAM :x:

Provides a simpler way to fix false positives in reports.

## Errors

Compatibilidad con STREAM :x:

El complemento de Errores proporciona un manejo de errores personalizable para su sitio web, permitiéndole configurar cómo aparecen las respuestas de error HTTP a los usuarios. Esta característica le ayuda a presentar páginas de error amigables y con su marca que mejoran la experiencia del usuario durante escenarios de error, en lugar de mostrar las páginas de error predeterminadas del servidor, que pueden parecer técnicas y confusas para los visitantes.

**Cómo funciona:**

1.  Cuando un cliente encuentra un error HTTP (por ejemplo, 400, 404 o 500), BunkerWeb intercepta la respuesta de error.
2.  En lugar de mostrar la página de error predeterminada, BunkerWeb muestra una página de error personalizada y diseñada profesionalmente.
3.  Las páginas de error son totalmente personalizables a través de su configuración, permitiéndole especificar páginas personalizadas para códigos de error específicos. **Los archivos de las páginas de error personalizadas deben colocarse en el directorio definido por el ajuste `ROOT_FOLDER` (consulte la documentación del complemento Varios).**
    - Por defecto, `ROOT_FOLDER` es `/var/www/html/{server_name}` (donde `{server_name}` se reemplaza por el nombre real del servidor).
    - En el modo multisitio, cada sitio puede tener su propio `ROOT_FOLDER`, por lo que las páginas de error personalizadas deben colocarse en el directorio correspondiente para cada sitio.
4.  Las páginas de error predeterminadas proporcionan explicaciones claras, ayudando a los usuarios a entender qué salió mal y qué pueden hacer a continuación.

### Cómo usar

Siga estos pasos para configurar y usar la función de Errores:

1.  **Defina las páginas de error personalizadas:** Especifique qué códigos de error HTTP deben usar páginas de error personalizadas utilizando el ajuste `ERRORS`. Los archivos de las páginas de error personalizadas deben estar ubicados en la carpeta especificada por el ajuste `ROOT_FOLDER` para el sitio. En el modo multisitio, esto significa que cada sitio/servidor puede tener su propia carpeta para las páginas de error personalizadas.
2.  **Configure sus páginas de error:** Para cada código de error, puede usar la página de error predeterminada de BunkerWeb o proporcionar su propia página HTML personalizada (colocada en el `ROOT_FOLDER` apropiado).
3.  **Establezca los códigos de error interceptados:** Seleccione qué códigos de error siempre deben ser manejados por BunkerWeb con el ajuste `INTERCEPTED_ERROR_CODES`.
4.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, el manejo de errores ocurre automáticamente para todos los códigos de error especificados.

### Ajustes de Configuración

| Ajuste                    | Valor por defecto                                 | Contexto  | Múltiple | Descripción                                                                                                                                                                  |
| ------------------------- | ------------------------------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ERRORS`                  |                                                   | multisite | no       | **Páginas de Error Personalizadas:** Asigne códigos de error específicos a archivos HTML personalizados usando el formato `CODIGO_DE_ERROR=/ruta/al/archivo.html`.           |
| `INTERCEPTED_ERROR_CODES` | `400 401 403 404 405 413 429 500 501 502 503 504` | multisite | no       | **Errores Interceptados:** Lista de códigos de error HTTP que BunkerWeb debe manejar con su página de error predeterminada cuando no se especifica una página personalizada. |

!!! tip "Diseño de la Página de Error"
    Las páginas de error predeterminadas de BunkerWeb están diseñadas para ser informativas, amigables y de apariencia profesional. Incluyen:

    -   Descripciones claras del error
    -   Información sobre qué pudo haber causado el error
    -   Acciones sugeridas para que los usuarios resuelvan el problema
    -   Indicadores visuales que ayudan a los usuarios a comprender si el problema está del lado del cliente o del servidor

!!! info "Tipos de Error"
    Los códigos de error se clasifican por tipo:

    -   **Errores 4xx (del lado del cliente):** Indican problemas con la solicitud del cliente, como intentar acceder a páginas inexistentes o carecer de la autenticación adecuada.
    -   **Errores 5xx (del lado del servidor):** Indican problemas con la capacidad del servidor para cumplir una solicitud válida, como errores internos del servidor o indisponibilidad temporal.

### Configuraciones de Ejemplo

=== "Manejo de Errores Predeterminado"

    Deje que BunkerWeb maneje los códigos de error comunes con sus páginas de error predeterminadas:

    ```yaml
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Páginas de Error Personalizadas"

    Use páginas de error personalizadas para códigos de error específicos:

    ```yaml
    ERRORS: "404=/custom/404.html 500=/custom/500.html"
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Manejo de Errores Selectivo"

    Solo maneje códigos de error específicos con BunkerWeb:

    ```yaml
    INTERCEPTED_ERROR_CODES: "404 500"
    ```

## Greylist

Compatibilidad con STREAM :warning:

El complemento de Lista Gris proporciona un enfoque de seguridad flexible que permite el acceso de los visitantes mientras se mantienen las características de seguridad esenciales.

A diferencia de los enfoques tradicionales de [lista negra](#blacklist)/[lista blanca](#whitelist) —que bloquean o permiten completamente el acceso—, la lista gris crea un punto intermedio al conceder acceso a ciertos visitantes mientras los somete a controles de seguridad.

**Cómo funciona:**

1.  Usted define los criterios para que los visitantes sean incluidos en la lista gris (_direcciones IP, redes, DNS inverso, ASN, User-Agent o patrones de URI_).
2.  Cuando un visitante coincide con cualquiera de estos criterios, se le concede acceso a su sitio mientras las demás características de seguridad permanecen activas.
3.  Si un visitante no coincide con ningún criterio de la lista gris, se le deniega el acceso.
4.  Los datos de la lista gris se pueden actualizar automáticamente desde fuentes externas de forma programada.

### Cómo usar

Siga estos pasos para configurar y usar la función de Lista Gris:

1.  **Habilite la función:** La función de Lista Gris está desactivada por defecto. Establezca el ajuste `USE_GREYLIST` en `yes` para habilitarla.
2.  **Configure las reglas de la lista gris:** Defina qué IPs, redes, patrones de DNS inverso, ASNs, User-Agents o URIs deben incluirse en la lista gris.
3.  **Añada fuentes externas:** Opcionalmente, configure URLs para descargar y actualizar automáticamente los datos de la lista gris.
4.  **Supervise el acceso:** Revise la [interfaz de usuario web](web-ui.md) para ver qué visitantes están siendo permitidos o denegados.

!!! tip "Comportamiento del Control de Acceso"
    Cuando la función de lista gris está habilitada con el ajuste `USE_GREYLIST` establecido en `yes`:

    1.  **Visitantes en la lista gris:** Se les permite el acceso pero siguen estando sujetos a todos los controles de seguridad.
    2.  **Visitantes no incluidos en la lista gris:** Se les deniega completamente el acceso.

!!! info "modo stream"
    Cuando se utiliza el modo stream, solo se realizan las comprobaciones de IP, DNS inverso y ASN.

### Ajustes de Configuración

**General**

| Ajuste         | Valor por defecto | Contexto  | Múltiple | Descripción                                                                 |
| -------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------- |
| `USE_GREYLIST` | `no`              | multisite | no       | **Habilitar Lista Gris:** Establezca en `yes` para habilitar la lista gris. |

=== "Dirección IP"
    **Qué hace esto:** Incluye en la lista gris a los visitantes según su dirección IP o red. Estos visitantes obtienen acceso pero siguen estando sujetos a los controles de seguridad.

    | Ajuste             | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                             |
    | ------------------ | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_IP`      |                   | multisite | no       | **Lista Gris de IP:** Lista de direcciones IP o redes (en notación CIDR) para incluir en la lista gris, separadas por espacios.         |
    | `GREYLIST_IP_URLS` |                   | multisite | no       | **URLs de Lista Gris de IP:** Lista de URLs que contienen direcciones IP o redes para incluir en la lista gris, separadas por espacios. |

=== "DNS Inverso"
    **Qué hace esto:** Incluye en la lista gris a los visitantes según su nombre de dominio (en inverso). Útil para permitir el acceso condicional a visitantes de organizaciones o redes específicas.

    | Ajuste                 | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                               |
    | ---------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_RDNS`        |                   | multisite | no       | **Lista Gris de rDNS:** Lista de sufijos de DNS inverso para incluir en la lista gris, separados por espacios.                            |
    | `GREYLIST_RDNS_GLOBAL` | `yes`             | multisite | no       | **Solo rDNS Global:** Realiza comprobaciones de la lista gris de rDNS solo en direcciones IP globales cuando se establece en `yes`.       |
    | `GREYLIST_RDNS_URLS`   |                   | multisite | no       | **URLs de Lista Gris de rDNS:** Lista de URLs que contienen sufijos de DNS inverso para incluir en la lista gris, separadas por espacios. |

=== "ASN"
    **Qué hace esto:** Incluye en la lista gris a los visitantes de proveedores de red específicos utilizando Números de Sistema Autónomo. Los ASN identifican a qué proveedor u organización pertenece una IP.

    | Ajuste              | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                            |
    | ------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_ASN`      |                   | multisite | no       | **Lista Gris de ASN:** Lista de Números de Sistema Autónomo para incluir en la lista gris, separados por espacios.     |
    | `GREYLIST_ASN_URLS` |                   | multisite | no       | **URLs de Lista Gris de ASN:** Lista de URLs que contienen ASNs para incluir en la lista gris, separadas por espacios. |

=== "User Agent"
    **Qué hace esto:** Incluye en la lista gris a los visitantes según el navegador o la herramienta que dicen estar usando. Esto permite el acceso controlado para herramientas específicas mientras se mantienen los controles de seguridad.

    | Ajuste                     | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                   |
    | -------------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_USER_AGENT`      |                   | multisite | no       | **Lista Gris de User-Agent:** Lista de patrones de User-Agent (expresión regular PCRE) para incluir en la lista gris, separados por espacios. |
    | `GREYLIST_USER_AGENT_URLS` |                   | multisite | no       | **URLs de Lista Gris de User-Agent:** Lista de URLs que contienen patrones de User-Agent para incluir en la lista gris.                       |

=== "URI"
    **Qué hace esto:** Incluye en la lista gris las solicitudes a URLs específicas de su sitio. Esto permite el acceso condicional a ciertos puntos finales mientras se mantienen los controles de seguridad.

    | Ajuste              | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                       |
    | ------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_URI`      |                   | multisite | no       | **Lista Gris de URI:** Lista de patrones de URI (expresión regular PCRE) para incluir en la lista gris, separados por espacios.   |
    | `GREYLIST_URI_URLS` |                   | multisite | no       | **URLs de Lista Gris de URI:** Lista de URLs que contienen patrones de URI para incluir en la lista gris, separadas por espacios. |

!!! info "Soporte de Formato de URL"
    Todos los ajustes `*_URLS` admiten URLs HTTP/HTTPS así como rutas de archivos locales usando el prefijo `file:///`. Se admite la autenticación básica usando el formato `http://usuario:contraseña@url`.

!!! tip "Actualizaciones Regulares"
    Las listas grises de las URLs se descargan y actualizan automáticamente cada hora para asegurar que su protección se mantenga actualizada con las últimas fuentes de confianza.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple que aplica la lista gris a la red interna y al rastreador de una empresa:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP: "192.168.1.0/24 10.0.0.0/8"
    GREYLIST_USER_AGENT: "(?:\b)CompanyCrawler(?:\b)"
    ```

=== "Configuración Avanzada"

    Una configuración más completa con múltiples criterios de lista gris:

    ```yaml
    USE_GREYLIST: "yes"

    # Activos de la empresa y rastreadores aprobados
    GREYLIST_IP: "192.168.1.0/24 203.0.113.0/24"
    GREYLIST_RDNS: ".company.com .partner-company.org"
    GREYLIST_ASN: "12345 67890"  # ASNs de la empresa y del socio
    GREYLIST_USER_AGENT: "(?:\b)GoodBot(?:\b) (?:\b)PartnerCrawler(?:\b)"
    GREYLIST_URI: "^/api/v1/"

    # Fuentes externas de confianza
    GREYLIST_IP_URLS: "https://example.com/trusted-networks.txt"
    GREYLIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Usando Archivos Locales"

    Configuración usando archivos locales para las listas grises:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP_URLS: "file:///ruta/a/ip-greylist.txt"
    GREYLIST_RDNS_URLS: "file:///ruta/a/rdns-greylist.txt"
    GREYLIST_ASN_URLS: "file:///ruta/a/asn-greylist.txt"
    GREYLIST_USER_AGENT_URLS: "file:///ruta/a/user-agent-greylist.txt"
    GREYLIST_URI_URLS: "file:///ruta/a/uri-greylist.txt"
    ```

=== "Acceso Selectivo a la API"

    Una configuración que permite el acceso a puntos finales específicos de la API:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_URI: "^/api/v1/public/ ^/api/v1/status"
    GREYLIST_IP: "203.0.113.0/24"  # Red del socio externo
    ```

### Trabajar con archivos de listas locales

Las configuraciones `*_URLS` de los plugins de lista blanca, lista gris y lista negra utilizan el mismo descargador. Cuando referencia una URL `file:///`:

- La ruta se resuelve dentro del contenedor del **scheduler** (en despliegues Docker normalmente `bunkerweb-scheduler`). Monte los archivos allí y asegúrese de que el usuario del scheduler tenga permisos de lectura.
- Cada archivo es texto codificado en UTF-8 con una entrada por línea. Las líneas vacías se ignoran y las líneas de comentario deben comenzar con `#` o `;`. Los comentarios `//` no son compatibles.
- Valores esperados por tipo de lista:
  - **Listas IP** aceptan direcciones IPv4/IPv6 o redes CIDR (por ejemplo `192.0.2.10` o `2001:db8::/48`).
  - **Listas rDNS** esperan un sufijo sin espacios (por ejemplo `.search.msn.com`). Los valores se normalizan automáticamente a minúsculas.
  - **Listas ASN** pueden contener solo el número (`32934`) o el número con el prefijo `AS` (`AS15169`).
  - **Listas de User-Agent** se tratan como patrones PCRE y se conserva la línea completa (incluidos los espacios). Mantenga los comentarios en una línea separada para que no se interpreten como parte del patrón.
  - **Listas URI** deben comenzar con `/` y pueden usar tokens PCRE como `^` o `$`.

Ejemplos de archivos con el formato esperado:

```text
# /etc/bunkerweb/lists/ip-greylist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-greylist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```

## Gzip

Compatibilidad con STREAM :x:

El complemento GZIP mejora el rendimiento del sitio web al comprimir las respuestas HTTP utilizando el algoritmo GZIP. Esta función reduce el uso de ancho de banda y mejora los tiempos de carga de la página al comprimir el contenido web antes de que se envíe al navegador del cliente, lo que resulta en una entrega más rápida y una mejor experiencia de usuario.

### Cómo funciona

1.  Cuando un cliente solicita contenido de su sitio web, BunkerWeb comprueba si el cliente admite la compresión GZIP.
2.  Si es compatible, BunkerWeb comprime la respuesta utilizando el algoritmo GZIP en el nivel de compresión que haya configurado.
3.  El contenido comprimido se envía al cliente con las cabeceras adecuadas que indican la compresión GZIP.
4.  El navegador del cliente descomprime el contenido antes de mostrarlo.
5.  Tanto el uso de ancho de banda como los tiempos de carga de la página se reducen, mejorando el rendimiento general del sitio y la experiencia del usuario.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de compresión GZIP:

1.  **Habilite la función:** La función GZIP está desactivada por defecto. Habilítela estableciendo el ajuste `USE_GZIP` en `yes`.
2.  **Configure los tipos MIME:** Especifique qué tipos de contenido deben comprimirse utilizando el ajuste `GZIP_TYPES`.
3.  **Establezca el tamaño mínimo:** Defina el tamaño mínimo de respuesta requerido para la compresión con el ajuste `GZIP_MIN_LENGTH` para evitar comprimir archivos pequeños.
4.  **Elija un nivel de compresión:** Seleccione su equilibrio preferido entre velocidad y tasa de compresión utilizando el ajuste `GZIP_COMP_LEVEL`.
5.  **Configure las solicitudes proxy:** Especifique qué solicitudes proxy deben comprimirse utilizando el ajuste `GZIP_PROXIED`.

### Ajustes de Configuración

| Ajuste            | Valor por defecto                                                                                                                                                                                                                                                                                                                                                                                                                | Contexto  | Múltiple | Descripción                                                                                                                            |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GZIP`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | no       | **Habilitar GZIP:** Establezca en `yes` para habilitar la compresión GZIP.                                                             |
| `GZIP_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | no       | **Tipos MIME:** Lista de tipos de contenido que se comprimirán con GZIP.                                                               |
| `GZIP_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | no       | **Tamaño Mínimo:** El tamaño mínimo de respuesta (en bytes) para que se aplique la compresión GZIP.                                    |
| `GZIP_COMP_LEVEL` | `5`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | no       | **Nivel de Compresión:** Nivel de compresión de 1 (compresión mínima) a 9 (compresión máxima). Los valores más altos consumen más CPU. |
| `GZIP_PROXIED`    | `no-cache no-store private expired auth`                                                                                                                                                                                                                                                                                                                                                                                         | multisite | no       | **Solicitudes Proxy:** Especifica qué solicitudes proxy deben comprimirse según las cabeceras de respuesta.                            |

!!! tip "Optimizando el Nivel de Compresión"
    El nivel de compresión por defecto (5) ofrece un buen equilibrio entre la tasa de compresión y el uso de la CPU. Para contenido estático o cuando los recursos de la CPU del servidor son abundantes, considere aumentarlo a 7-9 para una compresión máxima. Para contenido dinámico o cuando los recursos de la CPU son limitados, es posible que desee utilizar 1-3 para una compresión más rápida con una reducción de tamaño razonable.

!!! info "Soporte de Navegadores"
    GZIP es compatible con todos los navegadores modernos y ha sido el método de compresión estándar para las respuestas HTTP durante muchos años, lo que garantiza una excelente compatibilidad en todos los dispositivos y navegadores.

!!! warning "Compresión vs. Uso de CPU"
    Aunque la compresión GZIP reduce el ancho de banda y mejora los tiempos de carga, los niveles de compresión más altos consumen más recursos de la CPU. Para sitios de alto tráfico, encuentre el equilibrio adecuado entre la eficiencia de la compresión y el rendimiento del servidor.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración estándar que habilita GZIP con los ajustes por defecto:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json application/xml text/css text/html text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "5"
    ```

=== "Compresión Máxima"

    Configuración optimizada para un ahorro máximo de compresión:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "500"
    GZIP_COMP_LEVEL: "9"
    GZIP_PROXIED: "any"
    ```

=== "Rendimiento Equilibrado"

    Configuración que equilibra la tasa de compresión con el uso de la CPU:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "3"
    GZIP_PROXIED: "no-cache no-store private expired"
    ```

=== "Enfoque en Contenido Proxy"

    Configuración que se centra en manejar adecuadamente la compresión para el contenido proxy:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "4"
    GZIP_PROXIED: "any"
    ```

## HTML injection

Compatibilidad con STREAM :x:

El complemento de Inyección de HTML le permite agregar sin problemas código HTML personalizado a las páginas de su sitio web antes de las etiquetas de cierre `</body>` o `</head>`. Esta función es particularmente útil para agregar scripts de análisis, píxeles de seguimiento, JavaScript personalizado, estilos CSS u otras integraciones de terceros sin modificar el código fuente de su sitio web.

**Cómo funciona:**

1.  Cuando se sirve una página de su sitio web, BunkerWeb examina la respuesta HTML.
2.  Si ha configurado la inyección en el cuerpo (body), BunkerWeb inserta su código HTML personalizado justo antes de la etiqueta de cierre `</body>`.
3.  Si ha configurado la inyección en la cabecera (head), BunkerWeb inserta su código HTML personalizado justo antes de la etiqueta de cierre `</head>`.
4.  La inserción se realiza automáticamente para todas las páginas HTML servidas por su sitio web.
5.  Esto le permite agregar scripts, estilos u otros elementos sin modificar el código de su aplicación.

### Cómo usar

Siga estos pasos para configurar y usar la función de Inyección de HTML:

1.  **Prepare su HTML personalizado:** Decida qué código HTML desea inyectar en sus páginas.
2.  **Elija las ubicaciones de inyección:** Determine si necesita inyectar código en la sección `<head>`, en la sección `<body>`, o en ambas.
3.  **Configure los ajustes:** Agregue su HTML personalizado a los ajustes apropiados (`INJECT_HEAD` y/o `INJECT_BODY`).
4.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, el HTML se inyectará automáticamente en todas las páginas HTML servidas.

### Ajustes de Configuración

| Ajuste        | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                  |
| ------------- | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------------- |
| `INJECT_HEAD` |                   | multisite | no       | **Código HTML de la Cabecera:** El código HTML para inyectar antes de la etiqueta `</head>`. |
| `INJECT_BODY` |                   | multisite | no       | **Código HTML del Cuerpo:** El código HTML para inyectar antes de la etiqueta `</body>`.     |

!!! tip "Mejores Prácticas" - Por razones de rendimiento, coloque los archivos de JavaScript al final del cuerpo para evitar el bloqueo del renderizado. - Coloque CSS y JavaScript crítico en la sección de la cabecera para evitar un "destello" de contenido sin estilo (FOUC). - Tenga cuidado con el contenido inyectado que podría potencialmente romper la funcionalidad de su sitio.

!!! info "Casos de Uso Comunes" - Agregar scripts de análisis (como Google Analytics, Matomo) - Integrar widgets de chat o herramientas de soporte al cliente - Incluir píxeles de seguimiento para campañas de marketing - Agregar estilos CSS personalizados o funcionalidad de JavaScript - Incluir bibliotecas de terceros sin modificar el código de su aplicación

### Configuraciones de Ejemplo

=== "Google Analytics"

    Agregar el seguimiento de Google Analytics a su sitio web:

    ```yaml
    INJECT_HEAD: ""
    INJECT_BODY: "<script async src=\"https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX\"></script><script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag('js', new Date());gtag('config', 'G-XXXXXXXXXX');</script>"
    ```

=== "Estilos Personalizados"

    Agregar estilos CSS personalizados a su sitio web:

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .custom-element { color: blue; }</style>"
    INJECT_BODY: ""
    ```

=== "Múltiples Integraciones"

    Agregar tanto estilos personalizados como JavaScript:

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .notification-banner { background: #f8f9fa; padding: 10px; text-align: center; }</style>"
    INJECT_BODY: "<script src=\"https://cdn.example.com/js/widget.js\"></script><script>initializeWidget('your-api-key');</script>"
    ```

=== "Banner de Consentimiento de Cookies"

    Agregar un banner simple de consentimiento de cookies:

    ```yaml
    INJECT_HEAD: "<style>.cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #f1f1f1; padding: 20px; text-align: center; z-index: 1000; } .cookie-banner button { background: #4CAF50; border: none; color: white; padding: 10px 20px; cursor: pointer; }</style>"
    INJECT_BODY: "<div id=\"cookie-banner\" class=\"cookie-banner\">Este sitio web utiliza cookies para garantizar que obtenga la mejor experiencia. <button onclick=\"acceptCookies()\">Aceptar</button></div><script>function acceptCookies() { document.getElementById('cookie-banner').style.display = 'none'; localStorage.setItem('cookies-accepted', 'true'); } if(localStorage.getItem('cookies-accepted') === 'true') { document.getElementById('cookie-banner').style.display = 'none'; }</script>"
    ```

## Headers

Compatibilidad con STREAM :x:

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

## Let's Encrypt

Compatibilidad con STREAM :white_check_mark:

El complemento de Let's Encrypt simplifica la gestión de certificados SSL/TLS al automatizar la creación, renovación y configuración de certificados gratuitos de Let's Encrypt. Esta función permite conexiones HTTPS seguras para sus sitios web sin la complejidad de la gestión manual de certificados, reduciendo tanto los costos como la sobrecarga administrativa.

**Cómo funciona:**

1.  Cuando está habilitado, BunkerWeb detecta automáticamente los dominios configurados para su sitio web.
2.  BunkerWeb solicita certificados SSL/TLS gratuitos a la autoridad de certificación de Let's Encrypt.
3.  La propiedad del dominio se verifica mediante desafíos HTTP (demostrando que usted controla el sitio web) o desafíos DNS (demostrando que usted controla el DNS de su dominio).
4.  Los certificados se instalan y configuran automáticamente para sus dominios.
5.  BunkerWeb se encarga de las renovaciones de certificados en segundo plano antes de su vencimiento, garantizando la disponibilidad continua de HTTPS.
6.  Todo el proceso está totalmente automatizado, requiriendo una intervención mínima después de la configuración inicial.

!!! info "Requisitos previos"
    Para utilizar esta función, asegúrese de que los **registros A** de DNS adecuados estén configurados para cada dominio, apuntando a la(s) IP(s) pública(s) donde BunkerWeb es accesible. Sin una configuración de DNS correcta, el proceso de verificación del dominio fallará.

### Cómo usar

Siga estos pasos para configurar y usar la función de Let's Encrypt:

1.  **Habilite la función:** Establezca el ajuste `AUTO_LETS_ENCRYPT` en `yes` para habilitar la emisión y renovación automática de certificados.
2.  **Proporcione un correo electrónico de contacto (recomendado):** Ingrese su dirección de correo electrónico con el ajuste `EMAIL_LETS_ENCRYPT` para que Let's Encrypt pueda avisarle antes de que caduque un certificado. Si lo deja vacío, BunkerWeb se registrará sin dirección (opción de Certbot `--register-unsafely-without-email`) y no recibirá recordatorios ni correos de recuperación.
3.  **Elija el tipo de desafío:** Seleccione la verificación `http` o `dns` con el ajuste `LETS_ENCRYPT_CHALLENGE`.
4.  **Configure el proveedor de DNS:** Si utiliza desafíos DNS, especifique su proveedor de DNS y sus credenciales.
5.  **Seleccione el perfil del certificado:** Elija su perfil de certificado preferido utilizando el ajuste `LETS_ENCRYPT_PROFILE` (classic, tlsserver o shortlived).
6.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, los certificados se emiten, instalan y renuevan automáticamente según sea necesario.

!!! tip "Perfiles de Certificado"
    Let's Encrypt proporciona diferentes perfiles de certificado para diferentes casos de uso: - **classic**: Certificados de propósito general con una validez de 90 días (predeterminado) - **tlsserver**: Optimizado para la autenticación de servidores TLS con una validez de 90 días y una carga útil más pequeña - **shortlived**: Seguridad mejorada con una validez de 7 días para entornos automatizados - **custom**: Si su servidor ACME admite un perfil diferente, configúrelo usando `LETS_ENCRYPT_CUSTOM_PROFILE`.

!!! info "Disponibilidad del Perfil"
    Tenga en cuenta que los perfiles `tlsserver` y `shortlived` pueden no estar disponibles en todos los entornos o con todos los clientes ACME en este momento. El perfil `classic` tiene la compatibilidad más amplia y se recomienda para la mayoría de los usuarios. Si un perfil seleccionado no está disponible, el sistema volverá automáticamente al perfil `classic`.

### Ajustes de Configuración

| Ajuste                                      | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AUTO_LETS_ENCRYPT`                         | `no`              | multisite | no       | **Habilitar Let's Encrypt:** Establezca en `yes` para habilitar la emisión y renovación automática de certificados.                                                                                                                                                                                                                                                         |
| `LETS_ENCRYPT_PASSTHROUGH`                  | `no`              | multisite | no       | **Pasar a través de Let's Encrypt:** Establezca en `yes` para pasar las solicitudes de Let's Encrypt al servidor web. Esto es útil cuando BunkerWeb está detrás de otro proxy inverso que maneja SSL.                                                                                                                                                                       |
| `EMAIL_LETS_ENCRYPT`                        | `-`               | multisite | no       | **Correo electrónico de contacto:** Dirección utilizada para los avisos de caducidad de Let's Encrypt. Déjelo en blanco solo si acepta no recibir alertas ni correos de recuperación (Certbot se registra con `--register-unsafely-without-email`).                                                                                                                         |
| `LETS_ENCRYPT_CHALLENGE`                    | `http`            | multisite | no       | **Tipo de desafío:** Método utilizado para verificar la propiedad del dominio. Opciones: `http` o `dns`.                                                                                                                                                                                                                                                                    |
| `LETS_ENCRYPT_DNS_PROVIDER`                 |                   | multisite | no       | **Proveedor de DNS:** Cuando se utilizan desafíos DNS, el proveedor de DNS a utilizar (por ejemplo, cloudflare, route53, digitalocean).                                                                                                                                                                                                                                     |
| `LETS_ENCRYPT_DNS_PROPAGATION`              | `default`         | multisite | no       | **Propagación de DNS:** El tiempo de espera para la propagación de DNS en segundos. Si no se proporciona ningún valor, se utiliza el tiempo de propagación predeterminado del proveedor.                                                                                                                                                                                    |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`          |                   | multisite | yes      | **Elemento de credencial:** Elementos de configuración para la autenticación del proveedor de DNS (por ejemplo, `cloudflare_api_token 123456`). Los valores pueden ser texto sin formato, codificados en base64 o un objeto JSON.                                                                                                                                           |
| `LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64` | `yes`             | multisite | no       | **Decodificar credenciales DNS en Base64:** Decodifica automáticamente las credenciales del proveedor DNS codificadas en base64 cuando se establece en `yes`. Cuando está habilitado, los valores que coinciden con el formato base64 se decodifican antes de su uso (excepto para el proveedor `rfc2136`). Desactive si sus credenciales están intencionalmente en base64. |
| `USE_LETS_ENCRYPT_WILDCARD`                 | `no`              | multisite | no       | **Certificados comodín:** Cuando se establece en `yes`, crea certificados comodín para todos los dominios. Solo disponible con desafíos DNS.                                                                                                                                                                                                                                |
| `USE_LETS_ENCRYPT_STAGING`                  | `no`              | multisite | no       | **Usar entorno de prueba:** Cuando se establece en `yes`, utiliza el entorno de prueba de Let's Encrypt para realizar pruebas. El entorno de prueba tiene límites de velocidad más altos pero produce certificados que no son de confianza para los navegadores.                                                                                                            |
| `LETS_ENCRYPT_CLEAR_OLD_CERTS`              | `no`              | global    | no       | **Limpiar certificados antiguos:** Cuando se establece en `yes`, elimina los certificados antiguos que ya no son necesarios durante la renovación.                                                                                                                                                                                                                          |
| `LETS_ENCRYPT_PROFILE`                      | `classic`         | multisite | no       | **Perfil de certificado:** Seleccione el perfil de certificado a utilizar. Opciones: `classic` (propósito general), `tlsserver` (optimizado para servidores TLS) o `shortlived` (certificados de 7 días).                                                                                                                                                                   |
| `LETS_ENCRYPT_CUSTOM_PROFILE`               |                   | multisite | no       | **Perfil de certificado personalizado:** Ingrese un perfil de certificado personalizado si su servidor ACME admite perfiles no estándar. Esto anula `LETS_ENCRYPT_PROFILE` si está configurado.                                                                                                                                                                             |
| `LETS_ENCRYPT_MAX_RETRIES`                  | `3`               | multisite | no       | **Máximo de reintentos:** Número de veces que se reintentará la generación de certificados en caso de fallo. Establezca en `0` para deshabilitar los reintentos. Útil para manejar problemas de red temporales o límites de velocidad de la API.                                                                                                                            |

!!! info "Información y comportamiento"
    - El ajuste `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` es un ajuste múltiple y se puede utilizar para establecer varios elementos para el proveedor de DNS. Los elementos se guardarán como un archivo de caché, y Certbot leerá las credenciales de él.
    - Si no se proporciona ningún ajuste `LETS_ENCRYPT_DNS_PROPAGATION`, se utiliza el tiempo de propagación predeterminado del proveedor.
    - La automatización completa de Let's Encrypt utilizando el desafío `http` funciona en modo de flujo (stream) siempre que abra el puerto `80/tcp` desde el exterior. Utilice el ajuste `LISTEN_STREAM_PORT_SSL` para elegir su puerto de escucha SSL/TLS.
    - Si `LETS_ENCRYPT_PASSTHROUGH` se establece en `yes`, BunkerWeb no manejará las solicitudes de desafío ACME por sí mismo, sino que las pasará al servidor web de backend. Esto es útil en escenarios donde BunkerWeb actúa como un proxy inverso frente a otro servidor que está configurado para manejar los desafíos de Let's Encrypt.

!!! tip "Desafíos HTTP vs. DNS"
    **Los desafíos HTTP** son más fáciles de configurar y funcionan bien para la mayoría de los sitios web:

    - Requiere que su sitio web sea accesible públicamente en el puerto 80
    - Configurado automáticamente por BunkerWeb
    - No se puede utilizar para certificados comodín

    **Los desafíos DNS** ofrecen más flexibilidad y son necesarios para los certificados comodín:

    - Funciona incluso cuando su sitio web no es accesible públicamente
    - Requiere credenciales de la API del proveedor de DNS
    - Requerido para certificados comodín (por ejemplo, *.example.com)
    - Útil cuando el puerto 80 está bloqueado o no está disponible

!!! warning "Certificados comodín"
    Los certificados comodín solo están disponibles con desafíos DNS. Si desea utilizarlos, debe establecer el ajuste `USE_LETS_ENCRYPT_WILDCARD` en `yes` y configurar correctamente las credenciales de su proveedor de DNS.

!!! warning "Límites de velocidad"
    Let's Encrypt impone límites de velocidad en la emisión de certificados. Al probar las configuraciones, utilice el entorno de prueba estableciendo `USE_LETS_ENCRYPT_STAGING` en `yes` para evitar alcanzar los límites de velocidad de producción. Los certificados de prueba no son de confianza para los navegadores, pero son útiles para validar su configuración.

### Proveedores de DNS compatibles

El complemento de Let's Encrypt admite una amplia gama de proveedores de DNS para los desafíos de DNS. Cada proveedor requiere credenciales específicas que deben proporcionarse utilizando el ajuste `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`.

| Proveedor         | Descripción      | Ajustes obligatorios                                                                                         | Ajustes opcionales                                                                                                                                                                                                                                                                                   | Documentación                                                                                         |
| ----------------- | ---------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `bunny`           | bunny.net        | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/mwt/certbot-dns-bunny/blob/main/README.rst)                        |
| `cloudflare`      | Cloudflare       | ya sea `api_token`<br>o `email` y `api_key`                                                                  |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)                             |
| `desec`           | deSEC            | `token`                                                                                                      |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/desec-io/certbot-dns-desec/blob/main/README.md)                    |
| `digitalocean`    | DigitalOcean     | `token`                                                                                                      |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)                           |
| `domainoffensive` | Domain-Offensive | `api_token`                                                                                                  |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/domainoffensive/certbot-dns-domainoffensive/blob/master/README.md) |
| `dnsimple`        | DNSimple         | `token`                                                                                                      |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)                               |
| `dnsmadeeasy`     | DNS Made Easy    | `api_key`<br>`secret_key`                                                                                    |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)                            |
| `duckdns`         | DuckDNS          | `duckdns_token`                                                                                              |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/infinityofspace/certbot_dns_duckdns/blob/main/Readme.md)           |
| `dynu`            | Dynu             | `auth_token`                                                                                                 |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/bikram990/certbot-dns-dynu/blob/main/README.md)                    |
| `gehirn`          | Gehirn DNS       | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                                 |
| `google`          | Google Cloud     | `project_id`<br>`private_key_id`<br>`private_key`<br>`client_email`<br>`client_id`<br>`client_x509_cert_url` | `type` (predeterminado: `service_account`)<br>`auth_uri` (predeterminado: `https://accounts.google.com/o/oauth2/auth`)<br>`token_uri` (predeterminado: `https://accounts.google.com/o/oauth2/token`)<br>`auth_provider_x509_cert_url` (predeterminado: `https://www.googleapis.com/oauth2/v1/certs`) | [Documentación](https://certbot-dns-google.readthedocs.io/en/stable/)                                 |
| `infomaniak`      | Infomaniak       | `token`                                                                                                      |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/infomaniak/certbot-dns-infomaniak/blob/main/README.rst)            |
| `ionos`           | IONOS            | `prefix`<br>`secret`                                                                                         | `endpoint` (predeterminado: `https://api.hosting.ionos.com`)                                                                                                                                                                                                                                         | [Documentación](https://github.com/helgeerbe/certbot-dns-ionos/blob/master/README.md)                 |
| `linode`          | Linode           | `key`                                                                                                        |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-linode.readthedocs.io/en/stable/)                                 |
| `luadns`          | LuaDNS           | `email`<br>`token`                                                                                           |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-luadns.readthedocs.io/en/stable/)                                 |
| `njalla`          | Njalla           | `token`                                                                                                      |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/chaptergy/certbot-dns-njalla/blob/main/README.md)                  |
| `nsone`           | NS1              | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-nsone.readthedocs.io/en/stable/)                                  |
| `ovh`             | OVH              | `application_key`<br>`application_secret`<br>`consumer_key`                                                  | `endpoint` (predeterminado: `ovh-eu`)                                                                                                                                                                                                                                                                | [Documentación](https://certbot-dns-ovh.readthedocs.io/en/stable/)                                    |
| `pdns`            | PowerDNS         | `endpoint`<br>`api_key`<br>`server_id` (default: `localhost`)<br>`disable_notify` (default: `false`)         |                                                                                                                                                                                                                                                                                                      | [Documentation](https://github.com/kaechele/certbot-dns-pdns/blob/main/README.md)                     |
| `rfc2136`         | RFC 2136         | `server`<br>`name`<br>`secret`                                                                               | `port` (predeterminado: `53`)<br>`algorithm` (predeterminado: `HMAC-SHA512`)<br>`sign_query` (predeterminado: `false`)                                                                                                                                                                               | [Documentación](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                                |
| `route53`         | Amazon Route 53  | `access_key_id`<br>`secret_access_key`                                                                       |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-route53.readthedocs.io/en/stable/)                                |
| `sakuracloud`     | Sakura Cloud     | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)                            |
| `scaleway`        | Scaleway         | `application_token`                                                                                          |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst)                 |

### Configuraciones de Ejemplo

=== "Desafío HTTP Básico"

    Configuración simple que utiliza desafíos HTTP para un solo dominio:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ```

=== "DNS de Cloudflare con Comodín"

    Configuración para certificados comodín utilizando el DNS de Cloudflare:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "api_token SU_TOKEN_DE_API"
    USE_LETS_ENCRYPT_WILDCARD: "yes"
    ```

=== "Configuración de AWS Route53"

    Configuración que utiliza Amazon Route53 para los desafíos de DNS:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "route53"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "aws_access_key_id SU_CLAVE_DE_ACCESO"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "aws_secret_access_key SU_CLAVE_SECRETA"
    ```

=== "Pruebas con el Entorno de Prueba y Reintentos"

    Configuración para probar la configuración con el entorno de prueba y ajustes de reintento mejorados:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    USE_LETS_ENCRYPT_STAGING: "yes"
    LETS_ENCRYPT_MAX_RETRIES: "5"
    ```

=== "DigitalOcean con Tiempo de Propagación Personalizado"

    Configuración que utiliza el DNS de DigitalOcean con un tiempo de espera de propagación más largo:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "digitalocean"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "token SU_TOKEN_DE_API"
    LETS_ENCRYPT_DNS_PROPAGATION: "120"
    ```

=== "DNS de Google Cloud"

    Configuración que utiliza el DNS de Google Cloud con credenciales de cuenta de servicio:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "google"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "project_id su-id-de-proyecto"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "private_key_id su-id-de-clave-privada"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_3: "private_key su-clave-privada"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_4: "client_email su-correo-de-cuenta-de-servicio"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_5: "client_id su-id-de-cliente"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_6: "client_x509_cert_url su-url-de-certificado"
    ```

## Limit

Compatibilidad con STREAM :warning:

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

## Load Balancer <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


<p align='center'><iframe style='display: block;' width='560' height='315' data-src='https://www.youtube-nocookie.com/embed/cOVp0rAt5nw' title='Balanceador de carga' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe></p>

Compatibilidad con STREAM :x:

Provides load balancing feature to group of upstreams with optional healthchecks.

| Parámetro                                 | Valor predeterminado | Contexto | Múltiple | Descripción                                                        |
| ----------------------------------------- | -------------------- | -------- | -------- | ------------------------------------------------------------------ |
| `LOADBALANCER_HEALTHCHECK_DICT_SIZE`      | `10m`                | global   | no       | Shared dict size (datastore for all healthchecks).                 |
| `LOADBALANCER_UPSTREAM_NAME`              |                      | global   | sí       | Name of the upstream (used in REVERSE_PROXY_HOST).                 |
| `LOADBALANCER_UPSTREAM_SERVERS`           |                      | global   | sí       | List of servers/IPs in the server group.                           |
| `LOADBALANCER_UPSTREAM_MODE`              | `round-robin`        | global   | sí       | Load balancing mode (round-robin or sticky).                       |
| `LOADBALANCER_UPSTREAM_STICKY_METHOD`     | `ip`                 | global   | sí       | Sticky session method (ip or cookie).                              |
| `LOADBALANCER_UPSTREAM_RESOLVE`           | `no`                 | global   | sí       | Dynamically resolve upstream hostnames.                            |
| `LOADBALANCER_UPSTREAM_KEEPALIVE`         |                      | global   | sí       | Number of keepalive connections to cache per worker.               |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIMEOUT` | `60s`                | global   | sí       | Keepalive timeout for upstream connections.                        |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIME`    | `1h`                 | global   | sí       | Keepalive time for upstream connections.                           |
| `LOADBALANCER_HEALTHCHECK_URL`            | `/status`            | global   | sí       | The healthcheck URL.                                               |
| `LOADBALANCER_HEALTHCHECK_INTERVAL`       | `2000`               | global   | sí       | Healthcheck interval in milliseconds.                              |
| `LOADBALANCER_HEALTHCHECK_TIMEOUT`        | `1000`               | global   | sí       | Healthcheck timeout in milliseconds.                               |
| `LOADBALANCER_HEALTHCHECK_FALL`           | `3`                  | global   | sí       | Number of failed healthchecks before marking the server as down.   |
| `LOADBALANCER_HEALTHCHECK_RISE`           | `1`                  | global   | sí       | Number of successful healthchecks before marking the server as up. |
| `LOADBALANCER_HEALTHCHECK_VALID_STATUSES` | `200`                | global   | sí       | HTTP status considered valid in healthchecks.                      |
| `LOADBALANCER_HEALTHCHECK_CONCURRENCY`    | `10`                 | global   | sí       | Maximum number of concurrent healthchecks.                         |
| `LOADBALANCER_HEALTHCHECK_TYPE`           | `http`               | global   | sí       | Type of healthcheck (http or https).                               |
| `LOADBALANCER_HEALTHCHECK_SSL_VERIFY`     | `yes`                | global   | sí       | Verify SSL certificate in healthchecks.                            |
| `LOADBALANCER_HEALTHCHECK_HOST`           |                      | global   | sí       | Host header for healthchecks (useful for HTTPS).                   |

## Metrics

Compatibilidad con STREAM :warning:

El complemento de Métricas proporciona capacidades completas de monitoreo y recolección de datos para su instancia de BunkerWeb. Esta función le permite rastrear varios indicadores de rendimiento, eventos de seguridad y estadísticas del sistema, brindándole información valiosa sobre el comportamiento y la salud de sus sitios web y servicios protegidos.

**Cómo funciona:**

1.  BunkerWeb recopila métricas clave durante el procesamiento de solicitudes y respuestas.
2.  Estas métricas incluyen contadores de solicitudes bloqueadas, mediciones de rendimiento y varias estadísticas relacionadas con la seguridad.
3.  Los datos se almacenan de manera eficiente en la memoria, con límites configurables para evitar el uso excesivo de recursos.
4.  Para configuraciones de múltiples instancias, se puede usar Redis para centralizar y agregar datos de métricas.
5.  Las métricas recopiladas se pueden acceder a través de la API o visualizarse en la [interfaz de usuario web](web-ui.md).
6.  Esta información le ayuda a identificar amenazas de seguridad, solucionar problemas y optimizar su configuración.

### Implementación Técnica

El complemento de métricas funciona mediante:

- El uso de diccionarios compartidos en NGINX, donde `metrics_datastore` se utiliza para HTTP y `metrics_datastore_stream` para el tráfico TCP/UDP
- El aprovechamiento de una caché LRU para un almacenamiento eficiente en memoria
- La sincronización periódica de datos entre los trabajadores (workers) mediante temporizadores
- El almacenamiento de información detallada sobre las solicitudes bloqueadas, incluida la dirección IP del cliente, el país, la marca de tiempo, los detalles de la solicitud y el motivo del bloqueo
- El soporte para métricas específicas de complementos a través de una interfaz común de recolección de métricas
- La provisión de puntos finales de API para consultar las métricas recopiladas

### Cómo usar

Siga estos pasos para configurar y usar la función de Métricas:

1.  **Habilite la función:** La recolección de métricas está habilitada por defecto. Puede controlar esto con el ajuste `USE_METRICS`.
2.  **Configure la asignación de memoria:** Establezca la cantidad de memoria a asignar para el almacenamiento de métricas utilizando el ajuste `METRICS_MEMORY_SIZE`.
3.  **Establezca los límites de almacenamiento:** Defina cuántas solicitudes bloqueadas almacenar por trabajador y en Redis con los ajustes respectivos.
4.  **Acceda a los datos:** Vea las métricas recopiladas a través de la [interfaz de usuario web](web-ui.md) o los puntos finales de la API.
5.  **Analice la información:** Use los datos recopilados para identificar patrones, detectar problemas de seguridad y optimizar su configuración.

### Métricas Recopiladas

El complemento de métricas recopila la siguiente información:

1.  **Solicitudes Bloqueadas**: Para cada solicitud bloqueada, se almacenan los siguientes datos:
    - ID de la solicitud y marca de tiempo
    - Dirección IP del cliente y país (cuando esté disponible)
    - Método HTTP y URL
    - Código de estado HTTP
    - Agente de usuario
    - Motivo del bloqueo y modo de seguridad
    - Nombre del servidor
    - Datos adicionales relacionados con el motivo del bloqueo

2.  **Contadores de Complementos**: Varios contadores específicos de complementos que rastrean actividades y eventos.

### Acceso a la API

Se puede acceder a los datos de las métricas a través de los puntos finales de la API interna de BunkerWeb:

- **Punto final**: `/metrics/{filtro}`
- **Método**: GET
- **Descripción**: Recupera los datos de las métricas según el filtro especificado
- **Formato de respuesta**: Objeto JSON que contiene las métricas solicitadas

Por ejemplo, `/metrics/requests` devuelve información sobre las solicitudes bloqueadas.

!!! info "Configuración del Acceso a la API"
    Para acceder a las métricas a través de la API, debe asegurarse de que:

    1.  La función de API esté habilitada con `USE_API: "yes"` (habilitada por defecto)
    2.  Su IP de cliente esté incluida en el ajuste `API_WHITELIST_IP` (el valor predeterminado es `127.0.0.0/8`)
    3.  Esté accediendo a la API en el puerto configurado (el valor predeterminado es `5000` a través del ajuste `API_HTTP_PORT`)
    4.  Esté utilizando el valor correcto de `API_SERVER_NAME` en el encabezado Host (el valor predeterminado es `bwapi`)
    5.  Si `API_TOKEN` está configurado, incluya `Authorization: Bearer <token>` en los encabezados de la solicitud.

    Solicitudes típicas:

    Sin token (cuando `API_TOKEN` no está configurado):
    ```bash
    curl -H "Host: bwapi" \
         http://su-instancia-de-bunkerweb:5000/metrics/requests
    ```

    Con token (cuando `API_TOKEN` está configurado):
    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://su-instancia-de-bunkerweb:5000/metrics/requests
    ```

    Si ha personalizado el `API_SERVER_NAME` a algo diferente del valor predeterminado `bwapi`, use ese valor en el encabezado Host en su lugar.

    Para entornos de producción seguros, restrinja el acceso a la API a IPs de confianza y habilite `API_TOKEN`.

### Ajustes de Configuración

| Ajuste                               | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                        |
| ------------------------------------ | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_METRICS`                        | `yes`             | multisite | no       | **Habilitar Métricas:** Establezca en `yes` para habilitar la recolección y recuperación de métricas.                                              |
| `METRICS_MEMORY_SIZE`                | `16m`             | global    | no       | **Tamaño de la Memoria:** Tamaño del almacenamiento interno para las métricas (p. ej., `16m`, `32m`).                                              |
| `METRICS_MAX_BLOCKED_REQUESTS`       | `1000`            | global    | no       | **Máximo de Solicitudes Bloqueadas:** Número máximo de solicitudes bloqueadas para almacenar por trabajador.                                       |
| `METRICS_MAX_BLOCKED_REQUESTS_REDIS` | `100000`          | global    | no       | **Máximo de Solicitudes Bloqueadas en Redis:** Número máximo de solicitudes bloqueadas para almacenar en Redis.                                    |
| `METRICS_SAVE_TO_REDIS`              | `yes`             | global    | no       | **Guardar Métricas en Redis:** Establezca en `yes` para guardar las métricas (contadores y tablas) en Redis para la agregación en todo el clúster. |

!!! tip "Dimensionamiento de la Asignación de Memoria"
    El ajuste `METRICS_MEMORY_SIZE` debe ajustarse en función de su volumen de tráfico y el número de instancias. Para sitios de alto tráfico, considere aumentar este valor para garantizar que todas las métricas se capturen sin pérdida de datos.

!!! info "Integración con Redis"
    Cuando BunkerWeb está configurado para usar [Redis](#redis), el complemento de métricas sincronizará automáticamente los datos de las solicitudes bloqueadas con el servidor Redis. Esto proporciona una vista centralizada de los eventos de seguridad en múltiples instancias de BunkerWeb.

!!! warning "Consideraciones de Rendimiento"
    Establecer valores muy altos para `METRICS_MAX_BLOCKED_REQUESTS` o `METRICS_MAX_BLOCKED_REQUESTS_REDIS` puede aumentar el uso de la memoria. Supervise los recursos de su sistema y ajuste estos valores según sus necesidades reales y los recursos disponibles.

!!! note "Almacenamiento Específico del Trabajador"
    Cada trabajador de NGINX mantiene sus propias métricas en la memoria. Al acceder a las métricas a través de la API, los datos de todos los trabajadores se agregan automáticamente para proporcionar una vista completa.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Configuración predeterminada adecuada para la mayoría de las implementaciones:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "16m"
    METRICS_MAX_BLOCKED_REQUESTS: "1000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "100000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Entorno de Bajos Recursos"

    Configuración optimizada para entornos con recursos limitados:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "8m"
    METRICS_MAX_BLOCKED_REQUESTS: "500"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10000"
    METRICS_SAVE_TO_REDIS: "no"
    ```

=== "Entorno de Alto Tráfico"

    Configuración para sitios web de alto tráfico que necesitan rastrear más eventos de seguridad:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "64m"
    METRICS_MAX_BLOCKED_REQUESTS: "5000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "500000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Métricas Deshabilitadas"

    Configuración con la recolección de métricas deshabilitada:

    ```yaml
    USE_METRICS: "no"
    ```

## Migration <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Compatibilidad con STREAM :white_check_mark:

Migration of BunkerWeb configuration between instances made easy via the web UI

## Miscellaneous

Compatibilidad con STREAM :warning:

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

| Ajuste            | Valor por defecto | Contexto | Múltiple | Descripción |
| ----------------- | ----------------- | -------- | -------- | ----------- |
| `ALLOWED_METHODS` | `GET              | POST     | HEAD`    | multisite   | no | **Métodos HTTP:** Lista de métodos HTTP permitidos, separados por caracteres de barra vertical. |

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

## ModSecurity

Compatibilidad con STREAM :x:

El complemento ModSecurity integra el potente Firewall de Aplicaciones Web (WAF) [ModSecurity](https://modsecurity.org) en BunkerWeb. Esta integración ofrece una protección robusta contra una amplia gama de ataques web al aprovechar el [OWASP Core Rule Set (CRS)](https://coreruleset.org) para detectar y bloquear amenazas como la inyección de SQL, el cross-site scripting (XSS), la inclusión de archivos locales y más.

**Cómo funciona:**

1.  Cuando se recibe una solicitud, ModSecurity la evalúa con el conjunto de reglas activo.
2.  El OWASP Core Rule Set inspecciona las cabeceras, las cookies, los parámetros de la URL y el contenido del cuerpo.
3.  Cada violación detectada contribuye a una puntuación de anomalía general.
4.  Si esta puntuación excede el umbral configurado, la solicitud se bloquea.
5.  Se crean registros detallados para ayudar a diagnosticar qué reglas se activaron y por qué.

!!! success "Beneficios clave"

      1. **Protección estándar de la industria:** Utiliza el firewall de código abierto ModSecurity, ampliamente utilizado.
      2. **OWASP Core Rule Set:** Emplea reglas mantenidas por la comunidad que cubren el OWASP Top Ten y más.
      3. **Niveles de seguridad configurables:** Ajuste los niveles de paranoia para equilibrar la seguridad con los posibles falsos positivos.
      4. **Registro detallado:** Proporciona registros de auditoría exhaustivos para el análisis de ataques.
      5. **Soporte de complementos:** Amplíe la protección con complementos CRS opcionales adaptados a sus aplicaciones.

### Cómo usar

Siga estos pasos para configurar y usar ModSecurity:

1.  **Habilite la función:** ModSecurity está habilitado por defecto. Esto se puede controlar usando el ajuste `USE_MODSECURITY`.
2.  **Seleccione una versión de CRS:** Elija una versión del OWASP Core Rule Set (v3, v4 o nightly).
3.  **Añada complementos:** Opcionalmente, active los complementos de CRS para mejorar la cobertura de las reglas.
4.  **Supervise y ajuste:** Utilice los registros y la [interfaz de usuario web](web-ui.md) para identificar falsos positivos y ajustar la configuración.

### Ajustes de Configuración

| Ajuste                                | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                                                                                                                    |
| ------------------------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MODSECURITY`                     | `yes`             | multisite | no       | **Habilitar ModSecurity:** Active la protección del Firewall de Aplicaciones Web ModSecurity.                                                                                                                                                  |
| `USE_MODSECURITY_CRS`                 | `yes`             | multisite | no       | **Usar Core Rule Set:** Habilite el OWASP Core Rule Set para ModSecurity.                                                                                                                                                                      |
| `MODSECURITY_CRS_VERSION`             | `4`               | multisite | no       | **Versión de CRS:** La versión del OWASP Core Rule Set a utilizar. Opciones: `3`, `4` o `nightly`.                                                                                                                                             |
| `MODSECURITY_SEC_RULE_ENGINE`         | `On`              | multisite | no       | **Motor de Reglas:** Controle si se aplican las reglas. Opciones: `On`, `DetectionOnly` u `Off`.                                                                                                                                               |
| `MODSECURITY_SEC_AUDIT_ENGINE`        | `RelevantOnly`    | multisite | no       | **Motor de Auditoría:** Controle cómo funciona el registro de auditoría. Opciones: `On`, `Off` o `RelevantOnly`.                                                                                                                               |
| `MODSECURITY_SEC_AUDIT_LOG_PARTS`     | `ABIJDEFHZ`       | multisite | no       | **Partes del Registro de Auditoría:** Qué partes de las solicitudes/respuestas incluir en los registros de auditoría.                                                                                                                          |
| `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` | `131072`          | multisite | no       | **Límite del Cuerpo de la Solicitud (Sin Archivos):** Tamaño máximo para los cuerpos de las solicitudes sin carga de archivos. Acepta bytes simples o sufijos legibles por humanos (`k`, `m`, `g`), por ejemplo, `131072`, `256k`, `1m`, `2g`. |
| `USE_MODSECURITY_CRS_PLUGINS`         | `yes`             | multisite | no       | **Habilitar Complementos de CRS:** Habilite conjuntos de reglas de complementos adicionales para el Core Rule Set.                                                                                                                             |
| `MODSECURITY_CRS_PLUGINS`             |                   | multisite | no       | **Lista de Complementos de CRS:** Lista de complementos separados por espacios para descargar e instalar (`nombre-plugin[/etiqueta]` o URL).                                                                                                   |
| `USE_MODSECURITY_GLOBAL_CRS`          | `no`              | global    | no       | **CRS Global:** Cuando está habilitado, aplica las reglas de CRS globalmente a nivel HTTP en lugar de por servidor.                                                                                                                            |

!!! warning "ModSecurity y el OWASP Core Rule Set"
    **Recomendamos encarecidamente mantener habilitados tanto ModSecurity como el OWASP Core Rule Set (CRS)** para proporcionar una protección robusta contra las vulnerabilidades web comunes. Aunque pueden ocurrir falsos positivos ocasionales, se pueden resolver con un poco de esfuerzo ajustando las reglas o utilizando exclusiones predefinidas.

    El equipo de CRS mantiene activamente una lista de exclusiones para aplicaciones populares como WordPress, Nextcloud, Drupal y Cpanel, lo que facilita la integración sin afectar la funcionalidad. Los beneficios de seguridad superan con creces el mínimo esfuerzo de configuración necesario para solucionar los falsos positivos.

### Versiones de CRS Disponibles

Seleccione una versión de CRS que se ajuste mejor a sus necesidades de seguridad:

- **`3`**: Estable [v3.3.7](https://github.com/coreruleset/coreruleset/releases/tag/v3.3.7).
- **`4`**: Estable [v4.21.0](https://github.com/coreruleset/coreruleset/releases/tag/v4.21.0) (**predeterminada**).
- **`nightly`**: [Compilación nocturna](https://github.com/coreruleset/coreruleset/releases/tag/nightly) que ofrece las últimas actualizaciones de reglas.

!!! example "Compilación Nocturna"
    La **compilación nocturna** contiene las reglas más actualizadas, ofreciendo las últimas protecciones contra amenazas emergentes. Sin embargo, dado que se actualiza diariamente y puede incluir cambios experimentales o no probados, se recomienda utilizar primero la compilación nocturna en un **entorno de preproducción** antes de implementarla en producción.

!!! tip "Niveles de Paranoia"
    El OWASP Core Rule Set utiliza "niveles de paranoia" (PL) para controlar la rigurosidad de las reglas:

    -   **PL1 (predeterminado):** Protección básica con mínimos falsos positivos
    -   **PL2:** Seguridad más estricta con una coincidencia de patrones más rigurosa
    -   **PL3:** Seguridad mejorada con una validación más estricta
    -   **PL4:** Máxima seguridad con reglas muy estrictas (puede causar muchos falsos positivos)

    Puede establecer el nivel de paranoia agregando un archivo de configuración personalizado en `/etc/bunkerweb/configs/modsec-crs/`.

### Configuraciones Personalizadas {#custom-configurations}

El ajuste de ModSecurity y el OWASP Core Rule Set (CRS) se puede lograr a través de configuraciones personalizadas. Estas configuraciones le permiten personalizar el comportamiento en etapas específicas del procesamiento de las reglas de seguridad:

- **`modsec-crs`**: Se aplica **antes** de que se cargue el OWASP Core Rule Set.
- **`modsec`**: Se aplica **después** de que se haya cargado el OWASP Core Rule Set. También se utiliza si el CRS no se carga en absoluto.
- **`crs-plugins-before`**: Se aplica **antes** de que se carguen los complementos de CRS.
- **`crs-plugins-after`**: Se aplica **después** de que se hayan cargado los complementos de CRS.

Esta estructura proporciona flexibilidad, permitiéndole ajustar la configuración de ModSecurity y CRS para adaptarse a las necesidades específicas de su aplicación mientras mantiene un flujo de configuración claro.

#### Agregar Exclusiones de CRS con `modsec-crs`

Puede usar una configuración personalizada de tipo `modsec-crs` para agregar exclusiones para casos de uso específicos, como habilitar exclusiones predefinidas para WordPress:

```conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"
```

En este ejemplo:

- La acción se ejecuta en la **Fase 1** (temprano en el ciclo de vida de la solicitud).
- Habilita las exclusiones de CRS específicas de WordPress estableciendo la variable `tx.crs_exclusions_wordpress`.

#### Actualizar las Reglas de CRS con `modsec`

Para ajustar las reglas de CRS cargadas, puede usar una configuración personalizada de tipo `modsec`. Por ejemplo, puede eliminar reglas o etiquetas específicas para ciertas rutas de solicitud:

```conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"
```

En este ejemplo:

- **Regla 1**: Elimina las reglas etiquetadas como `attack-xss` y `attack-rce` para las solicitudes a `/wp-admin/admin-ajax.php`.
- **Regla 2**: Elimina las reglas etiquetadas como `attack-xss` para las solicitudes a `/wp-admin/options.php`.
- **Regla 3**: Elimina una regla específica (ID `930120`) para las solicitudes que coinciden con `/wp-json/yoast`.

!!! info "Orden de ejecución"
    El orden de ejecución de ModSecurity en BunkerWeb es el siguiente, asegurando una progresión clara y lógica de la aplicación de reglas:

    1.  **Configuración de OWASP CRS**: Configuración base para el OWASP Core Rule Set.
    2.  **Configuración de Complementos Personalizados (`crs-plugins-before`)**: Ajustes específicos de los complementos, aplicados antes de cualquier regla de CRS.
    3.  **Reglas de Complementos Personalizados (Antes de las Reglas de CRS) (`crs-plugins-before`)**: Reglas personalizadas para los complementos ejecutadas antes de las reglas de CRS.
    4.  **Configuración de Complementos Descargados**: Configuración para los complementos descargados externamente.
    5.  **Reglas de Complementos Descargados (Antes de las Reglas de CRS)**: Reglas para los complementos descargados ejecutadas antes de las reglas de CRS.
    6.  **Reglas de CRS Personalizadas (`modsec-crs`)**: Reglas definidas por el usuario aplicadas antes de cargar las reglas de CRS.
    7.  **Reglas de OWASP CRS**: El conjunto principal de reglas de seguridad proporcionado por OWASP.
    8.  **Reglas de Complementos Personalizados (Después de las Reglas de CRS) (`crs-plugins-after`)**: Reglas de complementos personalizadas ejecutadas después de las reglas de CRS.
    9.  **Reglas de Complementos Descargados (Después de las Reglas de CRS)**: Reglas para los complementos descargados ejecutadas después de las reglas de CRS.
    10. **Reglas Personalizadas (`modsec`)**: Reglas definidas por el usuario aplicadas después de todas las reglas de CRS y de los complementos.

    **Notas Clave**:

    -   Las personalizaciones **pre-CRS** (`crs-plugins-before`, `modsec-crs`) le permiten definir excepciones o reglas preparatorias antes de que se carguen las reglas principales de CRS.
    -   Las personalizaciones **post-CRS** (`crs-plugins-after`, `modsec`) son ideales para anular o ampliar las reglas después de que se hayan aplicado las reglas de CRS y de los complementos.
    -   Esta estructura proporciona la máxima flexibilidad, permitiendo un control preciso sobre la ejecución y personalización de las reglas mientras se mantiene una sólida línea de base de seguridad.

### Complementos de OWASP CRS

El OWASP Core Rule Set también admite una gama de **complementos** diseñados para ampliar su funcionalidad y mejorar la compatibilidad con aplicaciones o entornos específicos. Estos complementos pueden ayudar a ajustar el CRS para su uso con plataformas populares como WordPress, Nextcloud y Drupal, o incluso con configuraciones personalizadas. Para obtener más información y una lista de los complementos disponibles, consulte el [registro de complementos de OWASP CRS](https://github.com/coreruleset/plugin-registry).

!!! tip "Descarga de complementos"
    El ajuste `MODSECURITY_CRS_PLUGINS` le permite descargar e instalar complementos para ampliar la funcionalidad del OWASP Core Rule Set (CRS). Este ajuste acepta una lista de nombres de complementos con etiquetas o URL opcionales, lo que facilita la integración de funciones de seguridad adicionales adaptadas a sus necesidades específicas.

    Aquí hay una lista no exhaustiva de valores aceptados para el ajuste `MODSECURITY_CRS_PLUGINS`:

    *   `fake-bot` - Descargar la última versión del complemento.
    *   `wordpress-rule-exclusions/v1.0.0` - Descargar la versión 1.0.0 del complemento.
    *   `https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip` - Descargar el complemento directamente desde la URL.

!!! warning "Falsos Positivos"
    Una configuración de seguridad más alta puede bloquear el tráfico legítimo. Comience con la configuración predeterminada y supervise los registros antes de aumentar los niveles de seguridad. Esté preparado para agregar reglas de exclusión para las necesidades específicas de su aplicación.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración estándar con ModSecurity y CRS v4 habilitados:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "Modo de Solo Detección"

    Configuración para monitorear amenazas potenciales sin bloquear:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "DetectionOnly"
    MODSECURITY_SEC_AUDIT_ENGINE: "On"
    MODSECURITY_SEC_AUDIT_LOG_PARTS: "ABIJDEFHZ"
    ```

=== "Configuración Avanzada con Complementos"

    Configuración con CRS v4 y complementos habilitados para protección adicional:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions fake-bot"
    MODSECURITY_REQ_BODY_NO_FILES_LIMIT: "262144"
    ```

=== "Configuración Heredada"

    Configuración que utiliza CRS v3 para compatibilidad con configuraciones más antiguas:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "3"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "ModSecurity Global"

    Configuración que aplica ModSecurity globalmente a todas las conexiones HTTP:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    USE_MODSECURITY_GLOBAL_CRS: "yes"
    ```

=== "Compilación Nocturna con Complementos Personalizados"

    Configuración que utiliza la compilación nocturna de CRS con complementos personalizados:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "nightly"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions/v1.0.0 https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip"
    ```

!!! note "Valores de tamaño legibles por humanos"
    Para los ajustes de tamaño como `MODSECURITY_REQ_BODY_NO_FILES_LIMIT`, se admiten los sufijos `k`, `m` y `g` (sin distinción entre mayúsculas y minúsculas) y representan kibibytes, mebibytes y gibibytes (múltiplos de 1024). Ejemplos: `256k` = 262144, `1m` = 1048576, `2g` = 2147483648.

## Monitoring <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Compatibilidad con STREAM :x:

BunkerWeb monitoring pro system. This plugin is a prerequisite for some other plugins.

| Parámetro                      | Valor predeterminado | Contexto | Múltiple | Descripción                                                                 |
| ------------------------------ | -------------------- | -------- | -------- | --------------------------------------------------------------------------- |
| `USE_MONITORING`               | `yes`                | global   | no       | Enable monitoring of BunkerWeb.                                             |
| `MONITORING_METRICS_DICT_SIZE` | `10M`                | global   | no       | Size of the dict to store monitoring metrics.                               |
| `MONITORING_IGNORE_URLS`       |                      | global   | no       | List of URLs to ignore when monitoring separated with spaces (e.g. /health) |

## Mutual TLS

Compatibilidad con STREAM :white_check_mark:

El plugin Mutual TLS (mTLS) protege las aplicaciones sensibles exigiendo que los clientes presenten certificados emitidos por autoridades en las que confía. Con la función activada, BunkerWeb autentica cada llamada antes de que llegue a sus servicios, lo que mantiene blindadas herramientas internas e integraciones con socios.

BunkerWeb evalúa cada handshake TLS con base en el paquete de CA y en la política que configure. Los clientes que no cumplen las reglas se bloquean, mientras que las conexiones válidas pueden reenviar los detalles del certificado a las aplicaciones de backend para aplicar autorizaciones más precisas.

**Cómo funciona:**

1. El plugin vigila los handshakes HTTPS del sitio seleccionado.
2. Durante el intercambio TLS, BunkerWeb inspecciona el certificado del cliente y verifica la cadena con su almacén de confianza.
3. El modo de verificación decide si los clientes no autenticados se rechazan, se aceptan con tolerancia o se habilitan solo para diagnósticos.
4. (Opcional) BunkerWeb expone el resultado por medio de las cabeceras `X-SSL-Client-*` para que sus aplicaciones apliquen su propia lógica de acceso.

!!! success "Beneficios clave"

      1. **Control perimetral sólido:** Solo las máquinas y usuarios autenticados alcanzan las rutas críticas.
      2. **Políticas flexibles:** Combine modos estrictos y opcionales según sus flujos de incorporación.
      3. **Visibilidad para las apps:** Reenvíe huellas e identidades de certificados a los servicios posteriores.
      4. **Seguridad en capas:** Refuerce mTLS con otros plugins de BunkerWeb como limitación de tasas o listas de control.

### Cómo utilizarlo

Siga estos pasos para desplegar Mutual TLS con confianza:

1. **Active la función:** Establezca `USE_MTLS` en `yes` en los sitios que necesitan autenticación por certificado.
2. **Aporte el paquete de CA:** Guarde los emisores de confianza en un archivo PEM y apunte `MTLS_CA_CERTIFICATE` a su ruta absoluta.
3. **Elija el modo de verificación:** Use `on` para exigir certificados, `optional` para permitir una ruta alternativa u `optional_no_ca` de manera temporal para diagnosticar.
4. **Ajuste la profundidad de la cadena:** Modifique `MTLS_VERIFY_DEPTH` si su PKI incorpora varios intermedios.
5. **Reenvíe resultados (opcional):** Mantenga `MTLS_FORWARD_CLIENT_HEADERS` en `yes` si los servicios posteriores necesitan inspeccionar el certificado.
6. **Mantenga la revocación:** Si publica una CRL, configure `MTLS_CRL` para que BunkerWeb rechace certificados revocados.

### Parámetros de configuración

| Parámetro                     | Valor predeterminado | Contexto  | Múltiple | Descripción                                                                                                                                                            |
| ----------------------------- | -------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                    | `no`                 | multisite | no       | **Usar mutual TLS:** habilita la autenticación mediante certificados de cliente para el sitio actual.                                                                  |
| `MTLS_CA_CERTIFICATE`         |                      | multisite | no       | **Paquete de CA de clientes:** ruta absoluta al paquete de CA de confianza (PEM). Obligatorio cuando `MTLS_VERIFY_CLIENT` es `on` u `optional`; debe ser legible.      |
| `MTLS_VERIFY_CLIENT`          | `on`                 | multisite | no       | **Modo de verificación:** elija si los certificados son obligatorios (`on`), opcionales (`optional`) o aceptados sin validación de CA (`optional_no_ca`).              |
| `MTLS_VERIFY_DEPTH`           | `2`                  | multisite | no       | **Profundidad de verificación:** profundidad máxima de la cadena aceptada para los certificados de cliente.                                                            |
| `MTLS_FORWARD_CLIENT_HEADERS` | `yes`                | multisite | no       | **Reenviar cabeceras del cliente:** propaga los resultados de la verificación (`X-SSL-Client-*` con estado, DN, emisor, serie, huella y ventana de validez).           |
| `MTLS_CRL`                    |                      | multisite | no       | **Ruta de la CRL de clientes:** ruta opcional a una lista de revocación de certificados en formato PEM. Solo se aplica cuando el paquete de CA se carga correctamente. |

!!! tip "Mantén los certificados actualizados"
    Guarde los paquetes de CA y las listas de revocación en un volumen montado que el Scheduler pueda leer, de modo que cada reinicio recupere los últimos anclajes de confianza.

!!! warning "Paquete de CA obligatorio en modos estrictos"
    Cuando `MTLS_VERIFY_CLIENT` está en `on` u `optional`, el archivo de CA debe existir en tiempo de ejecución. Si falta, BunkerWeb omite las directivas de mTLS para evitar que el servicio arranque con una ruta no válida. Utilice `optional_no_ca` solo para diagnóstico porque debilita la autenticación.

!!! info "Certificado confiable y verificación"
    BunkerWeb reutiliza el mismo paquete de CA tanto para comprobar clientes como para construir la cadena de confianza, manteniendo coherentes las verificaciones de revocación y el handshake.

### Ejemplos de configuración

=== "Control de acceso estricto"

    Exija certificados de cliente válidos emitidos por su CA privada y reenvíe la información de verificación al backend:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Autenticación de cliente opcional"

    Permita usuarios anónimos, pero reenvíe los detalles del certificado cuando un cliente presente uno:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Diagnóstico sin CA"

    Permita que las conexiones finalicen incluso si un certificado no puede encadenarse con un paquete de CA de confianza. Úselo solo para la resolución de problemas:

    ```yaml
    USE_MTLS: "yes"
    MTLS_VERIFY_CLIENT: "optional_no_ca"
    MTLS_FORWARD_CLIENT_HEADERS: "no"
    ```

## PHP

Compatibilidad con STREAM :x:

El complemento PHP proporciona una integración perfecta con PHP-FPM para BunkerWeb, lo que permite el procesamiento dinámico de PHP para sus sitios web. Esta característica es compatible tanto con instancias locales de PHP-FPM que se ejecutan en la misma máquina como con servidores remotos de PHP-FPM, lo que le brinda flexibilidad en la forma en que configura su entorno PHP.

**Cómo funciona:**

1.  Cuando un cliente solicita un archivo PHP de su sitio web, BunkerWeb enruta la solicitud a la instancia de PHP-FPM configurada.
2.  Para PHP-FPM local, BunkerWeb se comunica con el intérprete de PHP a través de un archivo de socket de Unix.
3.  Para PHP-FPM remoto, BunkerWeb reenvía las solicitudes al host y puerto especificados utilizando el protocolo FastCGI.
4.  PHP-FPM procesa el script y devuelve el contenido generado a BunkerWeb, que luego lo entrega al cliente.
5.  La reescritura de URL se configura automáticamente para admitir los marcos de trabajo y aplicaciones PHP comunes que utilizan "URL amigables".

### Cómo usar

Siga estos pasos para configurar y usar la función PHP:

1.  **Elija su configuración de PHP-FPM:** Decida si utilizará una instancia de PHP-FPM local o remota.
2.  **Configure la conexión:** Para PHP local, especifique la ruta del socket; para PHP remoto, proporcione el nombre de host y el puerto.
3.  **Establezca la raíz del documento:** Configure la carpeta raíz que contiene sus archivos PHP utilizando la configuración de ruta adecuada.
4.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, BunkerWeb enruta automáticamente las solicitudes de PHP a su instancia de PHP-FPM.

### Ajustes de Configuración

| Ajuste            | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                           |
| ----------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
| `REMOTE_PHP`      |                   | multisite | no       | **Host PHP Remoto:** Nombre de host de la instancia remota de PHP-FPM. Deje en blanco para usar PHP local.            |
| `REMOTE_PHP_PATH` |                   | multisite | no       | **Ruta Remota:** Carpeta raíz que contiene los archivos en la instancia remota de PHP-FPM.                            |
| `REMOTE_PHP_PORT` | `9000`            | multisite | no       | **Puerto Remoto:** Puerto de la instancia remota de PHP-FPM.                                                          |
| `LOCAL_PHP`       |                   | multisite | no       | **Socket PHP Local:** Ruta al archivo de socket de PHP-FPM. Deje en blanco para usar una instancia remota de PHP-FPM. |
| `LOCAL_PHP_PATH`  |                   | multisite | no       | **Ruta Local:** Carpeta raíz que contiene los archivos en la instancia local de PHP-FPM.                              |

!!! tip "PHP-FPM Local vs. Remoto"
    Elija la configuración que mejor se adapte a su infraestructura:

    -   **PHP-FPM local** ofrece un mejor rendimiento debido a la comunicación basada en sockets y es ideal cuando PHP se ejecuta en la misma máquina que BunkerWeb.
    -   **PHP-FPM remoto** proporciona más flexibilidad y escalabilidad al permitir que el procesamiento de PHP se realice en servidores separados.

!!! warning "Configuración de la Ruta"
    La `REMOTE_PHP_PATH` o `LOCAL_PHP_PATH` debe coincidir con la ruta real del sistema de archivos donde se almacenan sus archivos PHP; de lo contrario, se producirá un error de "Archivo no encontrado".

!!! info "Reescritura de URL"
    El complemento PHP configura automáticamente la reescritura de URL para admitir aplicaciones PHP modernas. Las solicitudes de archivos inexistentes se dirigirán a `index.php` con el URI de la solicitud original disponible como parámetro de consulta.

### Configuraciones de Ejemplo

=== "Configuración de PHP-FPM Local"

    Configuración para usar una instancia de PHP-FPM local:

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html"
    ```

=== "Configuración de PHP-FPM Remoto"

    Configuración para usar una instancia de PHP-FPM remota:

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9000"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "Configuración de Puerto Personalizado"

    Configuración para usar PHP-FPM en un puerto no estándar:

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9001"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "Configuración de WordPress"

    Configuración optimizada para WordPress:

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html/wordpress"
    ```

## Pro

Compatibilidad con STREAM :x:

El complemento Pro agrupa características avanzadas y mejoras para implementaciones empresariales de BunkerWeb. Desbloquea capacidades adicionales, complementos premium y funcionalidades extendidas que complementan la plataforma principal de BunkerWeb. Ofrece seguridad, rendimiento y opciones de gestión mejoradas para implementaciones de nivel empresarial.

**Cómo funciona:**

1.  Con una clave de licencia Pro válida, BunkerWeb se conecta al servidor de la API Pro para validar su suscripción.
2.  Una vez autenticado, el complemento descarga e instala automáticamente los complementos y extensiones exclusivos de Pro.
3.  Su estado Pro se verifica periódicamente para garantizar el acceso continuo a las funciones premium.
4.  Los complementos premium se integran sin problemas con su configuración existente de BunkerWeb.
5.  Todas las funciones Pro funcionan en armonía con el núcleo de código abierto, mejorando en lugar de reemplazar la funcionalidad.

!!! success "Beneficios clave"

      1. **Extensiones Premium:** Acceso a complementos y características exclusivas no disponibles en la edición comunitaria.
      2. **Rendimiento Mejorado:** Configuraciones optimizadas y mecanismos de almacenamiento en caché avanzados.
      3. **Soporte Empresarial:** Asistencia prioritaria y canales de soporte dedicados.
      4. **Integración Perfecta:** Las características Pro funcionan junto con las características comunitarias sin conflictos de configuración.
      5. **Actualizaciones Automáticas:** Los complementos premium se descargan y se mantienen actualizados automáticamente.

### Cómo usar

Siga estos pasos para configurar y usar las características Pro:

1.  **Obtenga una clave de licencia:** Compre una licencia Pro en el [Panel de BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc).
2.  **Configure su clave de licencia:** Use el ajuste `PRO_LICENSE_KEY` para configurar su licencia.
3.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado con una licencia válida, los complementos Pro se descargan y activan automáticamente.
4.  **Supervise su estado Pro:** Verifique los indicadores de salud en la [interfaz de usuario web](web-ui.md) para confirmar el estado de su suscripción Pro.

### Ajustes de Configuración

| Ajuste            | Valor por defecto | Contexto | Múltiple | Descripción                                                                             |
| ----------------- | ----------------- | -------- | -------- | --------------------------------------------------------------------------------------- |
| `PRO_LICENSE_KEY` |                   | global   | no       | **Clave de Licencia Pro:** Su clave de licencia de BunkerWeb Pro para la autenticación. |

!!! tip "Gestión de Licencias"
    Su licencia Pro está vinculada a su entorno de implementación específico. Si necesita transferir su licencia o tiene preguntas sobre su suscripción, póngase en contacto con el soporte a través del [Panel de BunkerWeb](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc).

!!! info "Características Pro"
    Las características Pro específicas disponibles pueden evolucionar con el tiempo a medida que se agregan nuevas capacidades. El complemento Pro se encarga automáticamente de la instalación y configuración de todas las características disponibles.

!!! warning "Requisitos de Red"
    El complemento Pro requiere acceso a Internet de salida para conectarse a la API de BunkerWeb para la verificación de la licencia y para descargar los complementos premium. Asegúrese de que su firewall permita conexiones a `api.bunkerweb.io` en el puerto 443 (HTTPS).

### Preguntas Frecuentes

**P: ¿Qué sucede si mi licencia Pro expira?**

R: Si su licencia Pro expira, se desactivará el acceso a las características y complementos premium. Sin embargo, su instalación de BunkerWeb seguirá funcionando con todas las características de la edición comunitaria intactas. Para recuperar el acceso a las características Pro, simplemente renueve su licencia.

**P: ¿Las características Pro interrumpirán mi configuración existente?**

R: No, las características Pro están diseñadas para integrarse sin problemas con su configuración actual de BunkerWeb. Mejoran la funcionalidad sin alterar ni interferir con su configuración existente, garantizando una experiencia fluida y confiable.

**P: ¿Puedo probar las características Pro antes de comprometerme a una compra?**

R: ¡Absolutamente! BunkerWeb ofrece dos planes Pro para satisfacer sus necesidades:

- **BunkerWeb PRO Standard:** Acceso completo a las características Pro sin soporte técnico.
- **BunkerWeb PRO Enterprise:** Acceso completo a las características Pro con soporte técnico dedicado.

Puede explorar las características Pro con una prueba gratuita de 1 mes utilizando el código de promoción `freetrial`. Visite el [Panel de BunkerWeb](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc) para activar su prueba y obtener más información sobre las opciones de precios flexibles basadas en el número de servicios protegidos por BunkerWeb PRO.

## Prometheus exporter <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Compatibilidad con STREAM :x:

Prometheus exporter for BunkerWeb internal metrics.

| Parámetro                      | Valor predeterminado                                  | Contexto | Múltiple | Descripción                                                              |
| ------------------------------ | ----------------------------------------------------- | -------- | -------- | ------------------------------------------------------------------------ |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | global   | no       | Enable the Prometheus export.                                            |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | global   | no       | Listening IP of the Prometheus exporter.                                 |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | global   | no       | Listening port of the Prometheus exporter.                               |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | global   | no       | HTTP URL of the Prometheus exporter.                                     |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | global   | no       | List of IP/networks allowed to contact the Prometheus exporter endpoint. |

## Real IP

Compatibilidad con STREAM :warning:

El complemento de IP Real asegura que BunkerWeb identifique correctamente la dirección IP del cliente incluso cuando se encuentra detrás de proxies. Esto es esencial para aplicar correctamente las reglas de seguridad, la limitación de velocidad y el registro; sin él, todas las solicitudes parecerían provenir de la IP de su proxy en lugar de la IP real del cliente.

**Cómo funciona:**

1.  Cuando está habilitado, BunkerWeb examina las solicitudes entrantes en busca de encabezados específicos (como [`X-Forwarded-For`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Forwarded-For)) que contienen la dirección IP original del cliente.
2.  BunkerWeb comprueba si la IP entrante está en su lista de proxies de confianza (`REAL_IP_FROM`), asegurando que solo los proxies legítimos puedan pasar las IP de los clientes.
3.  La IP original del cliente se extrae del encabezado especificado (`REAL_IP_HEADER`) y se utiliza para todas las evaluaciones de seguridad y el registro.
4.  Para las cadenas de IP recursivas, BunkerWeb puede rastrear a través de múltiples saltos de proxy para determinar la IP del cliente de origen.
5.  Además, se puede habilitar el soporte para el [protocolo PROXY](https://netnut.io/what-is-proxy-protocol-and-how-does-it-work/) para recibir las IP de los clientes directamente de proxies compatibles como [HAProxy](https://www.haproxy.org/).
6.  Las listas de IP de proxies de confianza se pueden descargar y actualizar automáticamente desde fuentes externas a través de URL.

### Cómo usar

Siga estos pasos para configurar y usar la función de IP Real:

1.  **Habilite la función:** Establezca el ajuste `USE_REAL_IP` en `yes` para habilitar la detección de la IP real.
2.  **Defina los proxies de confianza:** Enumere las direcciones IP o redes de sus proxies de confianza utilizando el ajuste `REAL_IP_FROM`.
3.  **Especifique el encabezado:** Configure qué encabezado contiene la IP real utilizando el ajuste `REAL_IP_HEADER`.
4.  **Configure la recursividad:** Decida si desea rastrear las cadenas de IP de forma recursiva con el ajuste `REAL_IP_RECURSIVE`.
5.  **Fuentes de URL opcionales:** Configure las descargas automáticas de listas de proxies de confianza con `REAL_IP_FROM_URLS`.
6.  **Protocolo PROXY:** Para la comunicación directa con el proxy, habilítelo con `USE_PROXY_PROTOCOL` si su upstream lo admite.

!!! danger "Advertencia sobre el Protocolo PROXY"
    Habilitar `USE_PROXY_PROTOCOL` sin configurar correctamente su proxy upstream para enviar los encabezados del protocolo PROXY **romperá su aplicación**. Solo habilite este ajuste si está seguro de que su proxy upstream está configurado correctamente para enviar la información del protocolo PROXY. Si su proxy no está enviando los encabezados del protocolo PROXY, todas las conexiones a BunkerWeb fallarán con errores de protocolo.

### Ajustes de Configuración

| Ajuste               | Valor por defecto                         | Contexto  | Múltiple | Descripción                                                                                                                                                 |
| -------------------- | ----------------------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REAL_IP`        | `no`                                      | multisite | no       | **Habilitar IP Real:** Establezca en `yes` para habilitar la obtención de la IP real del cliente desde los encabezados o el protocolo PROXY.                |
| `REAL_IP_FROM`       | `192.168.0.0/16 172.16.0.0/12 10.0.0.0/8` | multisite | no       | **Proxies de Confianza:** Lista de direcciones IP o redes de confianza desde donde provienen las solicitudes de proxy, separadas por espacios.              |
| `REAL_IP_HEADER`     | `X-Forwarded-For`                         | multisite | no       | **Encabezado de IP Real:** Encabezado HTTP que contiene la IP real o el valor especial `proxy_protocol` para el protocolo PROXY.                            |
| `REAL_IP_RECURSIVE`  | `yes`                                     | multisite | no       | **Búsqueda Recursiva:** Cuando se establece en `yes`, realiza una búsqueda recursiva en el encabezado que contiene múltiples direcciones IP.                |
| `REAL_IP_FROM_URLS`  |                                           | multisite | no       | **URL de la Lista de IP:** URL que contienen las IP/redes de los proxies de confianza para descargar, separadas por espacios. Admite URL de tipo `file://`. |
| `USE_PROXY_PROTOCOL` | `no`                                      | global    | no       | **Protocolo PROXY:** Establezca en `yes` para habilitar el soporte del protocolo PROXY para la comunicación directa de proxy a BunkerWeb.                   |

!!! tip "Redes de Proveedores de la Nube"
    Si está utilizando un proveedor de la nube como AWS, GCP o Azure, considere agregar los rangos de IP de sus balanceadores de carga a su ajuste `REAL_IP_FROM` para garantizar la correcta identificación de la IP del cliente.

!!! danger "Consideraciones de Seguridad"
    Solo incluya las IP de los proxies de confianza en su configuración. Agregar fuentes no confiables podría permitir ataques de suplantación de IP, donde los actores maliciosos podrían falsificar la IP del cliente manipulando los encabezados.

!!! info "Múltiples Direcciones IP"
    Cuando `REAL_IP_RECURSIVE` está habilitado y un encabezado contiene múltiples IP (p. ej., `X-Forwarded-For: cliente, proxy1, proxy2`), BunkerWeb identificará como la IP del cliente la IP más a la izquierda que no esté en su lista de proxies de confianza.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple para un sitio detrás de un proxy inverso:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24 10.0.0.5"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "Balanceador de Carga en la Nube"

    Configuración para un sitio detrás de un balanceador de carga en la nube:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "Protocolo PROXY"

    Configuración utilizando el protocolo PROXY con un balanceador de carga compatible:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24"
    REAL_IP_HEADER: "proxy_protocol"
    USE_PROXY_PROTOCOL: "yes"
    ```

=== "Múltiples Fuentes de Proxy con URL"

    Configuración avanzada con listas de IP de proxy actualizadas automáticamente:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Real-IP"
    REAL_IP_RECURSIVE: "yes"
    REAL_IP_FROM_URLS: "https://example.com/proxy-ips.txt file:///etc/bunkerweb/custom-proxies.txt"
    ```

=== "Configuración de CDN"

    Configuración para un sitio web detrás de una CDN:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_FROM_URLS: "https://cdn-provider.com/ip-ranges.txt"
    REAL_IP_HEADER: "CF-Connecting-IP"  # Ejemplo para Cloudflare
    REAL_IP_RECURSIVE: "no"  # No es necesario con encabezados de una sola IP
    ```

=== "Detrás de Cloudflare"

    Configuración para un sitio web detrás de Cloudflare:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "" # Solo confiamos en las IPs de Cloudflare
    REAL_IP_FROM_URLS: "https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/" # Descargar las IPs de Cloudflare automáticamente
    REAL_IP_HEADER: "CF-Connecting-IP"  # Encabezado de Cloudflare para la IP del cliente
    REAL_IP_RECURSIVE: "yes"
    ```

## Redirect

Compatibilidad con STREAM :x:

El complemento de Redirección proporciona capacidades de redirección HTTP simples y eficientes para sus sitios web protegidos por BunkerWeb. Esta función le permite redirigir fácilmente a los visitantes de una URL a otra, admitiendo tanto redirecciones de dominio completo, redirecciones de ruta específicas como redirecciones que preservan la ruta.

**Cómo funciona:**

1.  Cuando un visitante accede a su sitio web, BunkerWeb verifica si hay una redirección configurada.
2.  Si está habilitado, BunkerWeb redirige al visitante a la URL de destino especificada.
3.  Puede configurar si desea preservar la ruta de la solicitud original (agregándola automáticamente a la URL de destino) o redirigir a la URL de destino exacta.
4.  El código de estado HTTP utilizado para la redirección se puede personalizar entre redirecciones permanentes (301) y temporales (302).
5.  Esta funcionalidad es ideal para migraciones de dominio, establecer dominios canónicos o redirigir URL obsoletas.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de Redirección:

1.  **Establezca la ruta de origen:** Configure la ruta desde la que se redirigirá utilizando el ajuste `REDIRECT_FROM` (por ejemplo, `/`, `/old-page`).
2.  **Establezca la URL de destino:** Configure la URL de destino a la que se redirigirá a los visitantes utilizando el ajuste `REDIRECT_TO`.
3.  **Elija el tipo de redirección:** Decida si desea preservar la ruta de la solicitud original con el ajuste `REDIRECT_TO_REQUEST_URI`.
4.  **Seleccione el código de estado:** Establezca el código de estado HTTP apropiado con el ajuste `REDIRECT_TO_STATUS_CODE` para indicar una redirección permanente o temporal.
5.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, todas las solicitudes al sitio se redirigirán automáticamente según su configuración.

### Ajustes de Configuración

| Ajuste                    | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                     |
| ------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_FROM`           | `/`               | multisite | yes      | **Ruta desde la que redirigir:** La ruta que se redirigirá.                                                                     |
| `REDIRECT_TO`             |                   | multisite | yes      | **URL de destino:** La URL de destino a la que se redirigirá a los visitantes. Deje en blanco para deshabilitar la redirección. |
| `REDIRECT_TO_REQUEST_URI` | `no`              | multisite | yes      | **Preservar ruta:** Cuando se establece en `yes`, agrega el URI de la solicitud original a la URL de destino.                   |
| `REDIRECT_TO_STATUS_CODE` | `301`             | multisite | yes      | **Código de estado HTTP:** El código de estado HTTP a utilizar. Opciones: `301`, `302`, `303`, `307` o `308`.                   |

!!! tip "Elegir el Código de Estado Correcto"
    - **`301` (Moved Permanently):** Redirección permanente, almacenada en caché por navegadores. Puede cambiar POST a GET. Ideal para migraciones de dominio.
    - **`302` (Found):** Redirección temporal. Puede cambiar POST a GET.
    - **`303` (See Other):** Siempre redirige usando el método GET. Útil después de envíos de formularios.
    - **`307` (Temporary Redirect):** Redirección temporal que preserva el método HTTP. Ideal para APIs.
    - **`308` (Permanent Redirect):** Redirección permanente que preserva el método HTTP. Para migraciones permanentes de API.

!!! info "Preservación de la Ruta"
    Cuando `REDIRECT_TO_REQUEST_URI` se establece en `yes`, BunkerWeb preserva la ruta de la solicitud original. Por ejemplo, si un usuario visita `https://dominio-antiguo.com/blog/post-1` y ha configurado una redirección a `https://dominio-nuevo.com`, será redirigido a `https://dominio-nuevo.com/blog/post-1`.

### Configuraciones de Ejemplo

=== "Redirección de Múltiples Rutas"

    Una configuración que redirige múltiples rutas a diferentes destinos:

    ```yaml
    # Redirigir /blog a un nuevo dominio de blog
    REDIRECT_FROM: "/blog/"
    REDIRECT_TO: "https://blog.example.com/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"

    # Redirigir /shop a otro dominio
    REDIRECT_FROM_2: "/shop/"
    REDIRECT_TO_2: "https://shop.example.com/"
    REDIRECT_TO_REQUEST_URI_2: "no"
    REDIRECT_TO_STATUS_CODE_2: "301"

    # Redirigir el resto del sitio
    REDIRECT_FROM_3: "/"
    REDIRECT_TO_3: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI_3: "no"
    REDIRECT_TO_STATUS_CODE_3: "301"
    ```

=== "Redirección de Dominio Simple"

    Una configuración que redirige a todos los visitantes a un nuevo dominio:

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Redirección con Preservación de Ruta"

    Una configuración que redirige a los visitantes a un nuevo dominio mientras preserva la ruta solicitada:

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Redirección Temporal"

    Una configuración para una redirección temporal a un sitio de mantenimiento:

    ```yaml
    REDIRECT_TO: "https://maintenance.example.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "302"
    ```

=== "Consolidación de Subdominios"

    Una configuración para redirigir un subdominio a una ruta específica en el dominio principal:

    ```yaml
    REDIRECT_TO: "https://example.com/support"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Migración de Endpoint de API"

    Una configuración para redirigir permanentemente un endpoint de API preservando el método HTTP:

    ```yaml
    REDIRECT_FROM: "/api/v1/"
    REDIRECT_TO: "https://api.example.com/v2/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "308"
    ```

=== "Redirección Post-Formulario"

    Una configuración para redirigir después del envío de un formulario usando el método GET:

    ```yaml
    REDIRECT_TO: "https://example.com/gracias"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "303"
    ```

## Redis

Compatibilidad con STREAM :white_check_mark:

El complemento Redis integra [Redis](https://redis.io/) o [Valkey](https://valkey.io/) en BunkerWeb para el almacenamiento en caché y la recuperación rápida de datos. Esta función es esencial para implementar BunkerWeb en entornos de alta disponibilidad donde los datos de sesión, las métricas y otra información compartida deben ser accesibles a través de múltiples nodos.

**Cómo funciona:**

1.  Cuando está habilitado, BunkerWeb establece una conexión con su servidor Redis o Valkey configurado.
2.  Los datos críticos como la información de la sesión, las métricas y los datos relacionados con la seguridad se almacenan en Redis/Valkey.
3.  Múltiples instancias de BunkerWeb pueden compartir estos datos, lo que permite la agrupación en clúster y el equilibrio de carga sin problemas.
4.  El complemento admite varias opciones de implementación de Redis/Valkey, incluidos servidores independientes, autenticación con contraseña, cifrado SSL/TLS y Redis Sentinel para alta disponibilidad.
5.  La reconexión automática y los tiempos de espera configurables garantizan la solidez en los entornos de producción.

### Cómo usar

Siga estos pasos para configurar y usar el complemento de Redis:

1.  **Habilite la función:** Establezca el ajuste `USE_REDIS` en `yes` para habilitar la integración de Redis/Valkey.
2.  **Configure los detalles de la conexión:** Especifique el nombre de host/dirección IP y el puerto de su servidor Redis/Valkey.
3.  **Establezca las opciones de seguridad:** Configure las credenciales de autenticación si su servidor Redis/Valkey las requiere.
4.  **Configure las opciones avanzadas:** Establezca la selección de la base de datos, las opciones de SSL y los tiempos de espera según sea necesario.
5.  **Para alta disponibilidad,** configure los ajustes de Sentinel si está utilizando Redis Sentinel.

### Ajustes de Configuración

| Ajuste                    | Valor por defecto | Contexto | Múltiple | Descripción                                                                                                             |
| ------------------------- | ----------------- | -------- | -------- | ----------------------------------------------------------------------------------------------------------------------- |
| `USE_REDIS`               | `no`              | global   | no       | **Habilitar Redis:** Establezca en `yes` para habilitar la integración de Redis/Valkey para el modo de clúster.         |
| `REDIS_HOST`              |                   | global   | no       | **Servidor Redis/Valkey:** Dirección IP o nombre de host del servidor Redis/Valkey.                                     |
| `REDIS_PORT`              | `6379`            | global   | no       | **Puerto Redis/Valkey:** Número de puerto del servidor Redis/Valkey.                                                    |
| `REDIS_DATABASE`          | `0`               | global   | no       | **Base de datos Redis/Valkey:** Número de base de datos a utilizar en el servidor Redis/Valkey (0-15).                  |
| `REDIS_SSL`               | `no`              | global   | no       | **SSL de Redis/Valkey:** Establezca en `yes` para habilitar el cifrado SSL/TLS para la conexión de Redis/Valkey.        |
| `REDIS_SSL_VERIFY`        | `yes`             | global   | no       | **Verificación SSL de Redis/Valkey:** Establezca en `yes` para verificar el certificado SSL del servidor Redis/Valkey.  |
| `REDIS_TIMEOUT`           | `5`               | global   | no       | **Tiempo de espera de Redis/Valkey:** Tiempo de espera de la conexión en segundos para las operaciones de Redis/Valkey. |
| `REDIS_USERNAME`          |                   | global   | no       | **Nombre de usuario de Redis/Valkey:** Nombre de usuario para la autenticación de Redis/Valkey (Redis 6.0+).            |
| `REDIS_PASSWORD`          |                   | global   | no       | **Contraseña de Redis/Valkey:** Contraseña para la autenticación de Redis/Valkey.                                       |
| `REDIS_SENTINEL_HOSTS`    |                   | global   | no       | **Hosts de Sentinel:** Lista de hosts de Redis Sentinel separados por espacios (nombredehost:puerto).                   |
| `REDIS_SENTINEL_USERNAME` |                   | global   | no       | **Nombre de usuario de Sentinel:** Nombre de usuario para la autenticación de Redis Sentinel.                           |
| `REDIS_SENTINEL_PASSWORD` |                   | global   | no       | **Contraseña de Sentinel:** Contraseña para la autenticación de Redis Sentinel.                                         |
| `REDIS_SENTINEL_MASTER`   | `mymaster`        | global   | no       | **Maestro de Sentinel:** Nombre del maestro en la configuración de Redis Sentinel.                                      |
| `REDIS_KEEPALIVE_IDLE`    | `300`             | global   | no       | **Tiempo de inactividad de keepalive:** Tiempo (en segundos) entre las sondas TCP keepalive para conexiones inactivas.  |
| `REDIS_KEEPALIVE_POOL`    | `3`               | global   | no       | **Grupo de keepalive:** Número máximo de conexiones de Redis/Valkey mantenidas en el grupo.                             |

!!! tip "Alta Disponibilidad con Redis Sentinel"
    Para entornos de producción que requieren alta disponibilidad, configure los ajustes de Redis Sentinel. Esto proporciona capacidades de conmutación por error automática si el servidor Redis principal deja de estar disponible.

!!! warning "Consideraciones de Seguridad"
    Cuando utilice Redis en producción:

    -   Establezca siempre contraseñas seguras tanto para la autenticación de Redis como de Sentinel
    -   Considere habilitar el cifrado SSL/TLS para las conexiones de Redis
    -   Asegúrese de que su servidor Redis no esté expuesto a la Internet pública
    -   Restrinja el acceso al puerto de Redis mediante cortafuegos o segmentación de red

!!! info "Requisitos del Clúster"
    Al implementar BunkerWeb en un clúster:

    -   Todas las instancias de BunkerWeb deben conectarse al mismo servidor Redis o Valkey o al clúster de Sentinel
    -   Configure el mismo número de base de datos en todas las instancias
    -   Asegúrese de que haya conectividad de red entre todas las instancias de BunkerWeb y los servidores Redis/Valkey

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple para conectarse a un servidor Redis o Valkey en la máquina local:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "localhost"
    REDIS_PORT: "6379"
    ```

=== "Configuración Segura"

    Configuración con autenticación por contraseña y SSL habilitado:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_SSL: "yes"
    REDIS_SSL_VERIFY: "yes"
    ```

=== "Configuración de Redis Sentinel"

    Configuración para alta disponibilidad utilizando Redis Sentinel:

    ```yaml
    USE_REDIS: "yes"
    REDIS_SENTINEL_HOSTS: "sentinel1:26379 sentinel2:26379 sentinel3:26379"
    REDIS_SENTINEL_MASTER: "mymaster"
    REDIS_SENTINEL_PASSWORD: "sentinel-password"
    REDIS_PASSWORD: "redis-password"
    ```

=== "Ajuste Avanzado"

    Configuración con parámetros de conexión avanzados para la optimización del rendimiento:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_DATABASE: "3"
    REDIS_TIMEOUT: "3"
    REDIS_KEEPALIVE_IDLE: "60"
    REDIS_KEEPALIVE_POOL: "5"
    ```

### Mejores Prácticas de Redis

Cuando utilice Redis o Valkey con BunkerWeb, considere estas mejores prácticas para garantizar un rendimiento, seguridad y fiabilidad óptimos:

#### Gestión de la Memoria

- **Supervise el uso de la memoria:** Configure Redis con los ajustes `maxmemory` apropiados para evitar errores de falta de memoria
- **Establezca una política de desalojo:** Utilice `maxmemory-policy` (p. ej., `volatile-lru` o `allkeys-lru`) apropiada para su caso de uso
- **Evite claves grandes:** Asegúrese de que las claves individuales de Redis se mantengan en un tamaño razonable para evitar la degradación del rendimiento

#### Persistencia de Datos

- **Habilite las instantáneas RDB:** Configure instantáneas periódicas para la persistencia de datos sin un impacto significativo en el rendimiento
- **Considere AOF:** Para datos críticos, habilite la persistencia AOF (Append-Only File) con una política de `fsync` apropiada
- **Estrategia de copia de seguridad:** Implemente copias de seguridad regulares de Redis como parte de su plan de recuperación de desastres

#### Optimización del Rendimiento

- **Agrupación de conexiones:** BunkerWeb ya implementa esto, pero asegúrese de que otras aplicaciones sigan esta práctica
- **Canalización:** Cuando sea posible, utilice la canalización para operaciones masivas para reducir la sobrecarga de la red
- **Evite operaciones costosas:** Tenga cuidado con comandos como `KEYS` en entornos de producción
- **Compare su carga de trabajo:** Utilice `redis-benchmark` para probar sus patrones de carga de trabajo específicos

### Recursos Adicionales

- [Documentación de Redis](https://redis.io/documentation)
- [Guía de Seguridad de Redis](https://redis.io/topics/security)
- [Alta Disponibilidad de Redis](https://redis.io/topics/sentinel)
- [Persistencia de Redis](https://redis.io/topics/persistence)

## Reporting <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Compatibilidad con STREAM :x:

Regular reporting of important data from BunkerWeb (global, attacks, bans, requests, reasons, AS...). Monitoring pro plugin needed to work.

| Parámetro                      | Valor predeterminado | Contexto | Múltiple | Descripción                                                                                                                        |
| ------------------------------ | -------------------- | -------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`                 | global   | no       | Enable sending the report via email.                                                                                               |
| `USE_REPORTING_WEBHOOK`        | `no`                 | global   | no       | Enable sending the report via webhook.                                                                                             |
| `REPORTING_SCHEDULE`           | `weekly`             | global   | no       | The frequency at which reports are sent.                                                                                           |
| `REPORTING_WEBHOOK_URLS`       |                      | global   | no       | List of webhook URLs to receive the report in Markdown (separated by spaces).                                                      |
| `REPORTING_SMTP_EMAILS`        |                      | global   | no       | List of email addresses to receive the report in HTML format (separated by spaces).                                                |
| `REPORTING_SMTP_HOST`          |                      | global   | no       | The host server used for SMTP sending.                                                                                             |
| `REPORTING_SMTP_PORT`          | `465`                | global   | no       | The port used for SMTP. Please note that there are different standards depending on the type of connection (SSL = 465, TLS = 587). |
| `REPORTING_SMTP_FROM_EMAIL`    |                      | global   | no       | The email address used as the sender. Note that 2FA must be disabled for this email address.                                       |
| `REPORTING_SMTP_FROM_USER`     |                      | global   | no       | The user authentication value for sending via the from email address.                                                              |
| `REPORTING_SMTP_FROM_PASSWORD` |                      | global   | no       | The password authentication value for sending via the from email address.                                                          |
| `REPORTING_SMTP_SSL`           | `SSL`                | global   | no       | Determine whether or not to use a secure connection for SMTP.                                                                      |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report`   | global   | no       | The subject line of the email.                                                                                                     |

## Reverse proxy

Compatibilidad con STREAM :warning:

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
| `REVERSE_PROXY_KEEPALIVE`        | `no`              | multisite | yes      | **Keep-Alive:** Habilite o deshabilite las conexiones keepalive con el recurso al que se hace proxy.                                            |
| `REVERSE_PROXY_CUSTOM_HOST`      |                   | multisite | no       | **Host Personalizado:** Anule el encabezado Host enviado al servidor upstream.                                                                  |
| `REVERSE_PROXY_INTERCEPT_ERRORS` | `yes`             | multisite | no       | **Interceptar Errores:** Si se deben interceptar y reescribir las respuestas de error del backend.                                              |

    !!! tip "Mejores Prácticas"
        - Siempre especifique la URL completa en `REVERSE_PROXY_HOST`, incluido el protocolo (http:// o https://)
        - Use `REVERSE_PROXY_INTERCEPT_ERRORS` para proporcionar páginas de error consistentes en todos sus servicios
        - Al configurar múltiples backends, use el formato de sufijo numerado (por ejemplo, `REVERSE_PROXY_HOST_2`, `REVERSE_PROXY_URL_2`)

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

## Reverse scan

Compatibilidad con STREAM :white_check_mark:

El complemento de Escaneo Inverso protege de manera robusta contra los intentos de evasión de proxy al escanear los puertos de los clientes para detectar si están ejecutando servidores proxy u otros servicios de red. Esta función ayuda a identificar y bloquear posibles amenazas de clientes que puedan estar intentando ocultar su verdadera identidad u origen, mejorando así la postura de seguridad de su sitio web.

**Cómo funciona:**

1.  Cuando un cliente se conecta a su servidor, BunkerWeb intenta escanear puertos específicos en la dirección IP del cliente.
2.  El complemento comprueba si alguno de los puertos de proxy comunes (como 80, 443, 8080, etc.) está abierto en el lado del cliente.
3.  Si se detectan puertos abiertos, lo que indica que el cliente puede estar ejecutando un servidor proxy, se deniega la conexión.
4.  Esto agrega una capa adicional de seguridad contra herramientas automatizadas, bots y usuarios maliciosos que intentan enmascarar su identidad.

!!! success "Beneficios clave"

      1. **Seguridad Mejorada:** Identifica a los clientes que potencialmente ejecutan servidores proxy que podrían ser utilizados con fines maliciosos.
      2. **Detección de Proxy:** Ayuda a detectar y bloquear a los clientes que intentan ocultar su verdadera identidad.
      3. **Ajustes Configurables:** Personalice qué puertos escanear según sus requisitos de seguridad específicos.
      4. **Optimizado para el Rendimiento:** Escaneo inteligente con tiempos de espera configurables para minimizar el impacto en los usuarios legítimos.
      5. **Integración Perfecta:** Funciona de forma transparente con sus capas de seguridad existentes.

### Cómo usar

Siga estos pasos para configurar y usar la función de Escaneo Inverso:

1.  **Habilite la función:** Establezca el ajuste `USE_REVERSE_SCAN` en `yes` para habilitar el escaneo de puertos del cliente.
2.  **Configure los puertos a escanear:** Personalice el ajuste `REVERSE_SCAN_PORTS` para especificar qué puertos del cliente deben ser verificados.
3.  **Establezca el tiempo de espera del escaneo:** Ajuste el `REVERSE_SCAN_TIMEOUT` para equilibrar un escaneo exhaustivo con el rendimiento.
4.  **Supervise la actividad de escaneo:** Verifique los registros y la [interfaz de usuario web](web-ui.md) para revisar los resultados del escaneo y los posibles incidentes de seguridad.

### Ajustes de Configuración

| Ajuste                 | Valor por defecto          | Contexto  | Múltiple | Descripción                                                                                                  |
| ---------------------- | -------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| `USE_REVERSE_SCAN`     | `no`                       | multisite | no       | **Habilitar Escaneo Inverso:** Establezca en `yes` para habilitar el escaneo de los puertos de los clientes. |
| `REVERSE_SCAN_PORTS`   | `22 80 443 3128 8000 8080` | multisite | no       | **Puertos a Escanear:** Lista de puertos separados por espacios para verificar en el lado del cliente.       |
| `REVERSE_SCAN_TIMEOUT` | `500`                      | multisite | no       | **Tiempo de Espera del Escaneo:** Tiempo máximo en milisegundos permitido para escanear un puerto.           |

!!! warning "Consideraciones de Rendimiento"
    Escanear múltiples puertos puede agregar latencia a las conexiones de los clientes. Use un valor de tiempo de espera apropiado y limite el número de puertos escaneados para mantener un buen rendimiento.

!!! info "Puertos de Proxy Comunes"
    La configuración predeterminada incluye puertos comunes utilizados por los servidores proxy (80, 443, 8080, 3128) y SSH (22). Es posible que desee personalizar esta lista según su modelo de amenaza.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple para habilitar el escaneo de puertos del cliente:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "500"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Escaneo Exhaustivo"

    Una configuración más completa que verifica puertos adicionales:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1000"
    REVERSE_SCAN_PORTS: "22 80 443 3128 8080 8000 8888 1080 3333 8081"
    ```

=== "Configuración Optimizada para el Rendimiento"

    Configuración ajustada para un mejor rendimiento al verificar menos puertos con un tiempo de espera más bajo:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "250"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Configuración de Alta Seguridad"

    Configuración enfocada en la máxima seguridad con un escaneo extendido:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1500"
    REVERSE_SCAN_PORTS: "22 25 80 443 1080 3128 3333 4444 5555 6588 6666 7777 8000 8080 8081 8800 8888 9999"
    ```

## Robots.txt

Compatibilidad con STREAM :white_check_mark:

El complemento Robots.txt gestiona el archivo [robots.txt](https://www.robotstxt.org/) para su sitio web. Este archivo indica a los rastreadores web y robots qué partes de su sitio pueden o no pueden acceder.

**Cómo funciona:**

Cuando está habilitado, BunkerWeb genera dinámicamente el archivo `/robots.txt` en la raíz de su sitio web. Las reglas dentro de este archivo se agregan de múltiples fuentes en el siguiente orden:

1.  **API de DarkVisitors:** Si se proporciona `ROBOTSTXT_DARKVISITORS_TOKEN`, las reglas se obtienen de la API de [DarkVisitors](https://darkvisitors.com/), lo que permite el bloqueo dinámico de bots maliciosos y rastreadores de IA según los tipos de agentes configurados y los agentes de usuario no permitidos.
2.  **Listas de la Comunidad:** Se incluyen reglas de listas `robots.txt` predefinidas y mantenidas por la comunidad (especificadas por `ROBOTSTXT_COMMUNITY_LISTS`).
3.  **URL personalizadas:** Las reglas se obtienen de las URL proporcionadas por el usuario (especificadas por `ROBOTSTXT_URLS`).
4.  **Reglas manuales:** Se agregan las reglas definidas directamente a través de las variables de entorno `ROBOTSTXT_RULE`.

Todas las reglas de estas fuentes se combinan. Después de la agregación, se aplican `ROBOTSTXT_IGNORE_RULE` para filtrar cualquier regla no deseada utilizando patrones de expresiones regulares PCRE. Finalmente, si no queda ninguna regla después de todo este proceso, se aplica automáticamente una regla predeterminada `User-agent: *` y `Disallow: /` para garantizar un nivel básico de protección. Las URL de mapa de sitio opcionales (especificadas por `ROBOTSTXT_SITEMAP`) también se incluyen en la salida final de `robots.txt`.

### Evasión Dinámica de Bots con la API de DarkVisitors

[DarkVisitors](https://darkvisitors.com/) es un servicio que proporciona un archivo `robots.txt` dinámico para ayudar a bloquear bots maliciosos conocidos y rastreadores de IA. Al integrarse con DarkVisitors, BunkerWeb puede obtener y servir automáticamente un `robots.txt` actualizado que ayuda a proteger su sitio del tráfico automatizado no deseado.

Para habilitar esto, debe registrarse en [darkvisitors.com](https://darkvisitors.com/docs/robots-txt) y obtener un token de portador (bearer token).

### Cómo usar

1.  **Habilite la función:** Establezca el ajuste `USE_ROBOTSTXT` en `yes`.
2.  **Configure las reglas:** Elija uno o más métodos para definir sus reglas de `robots.txt`:
    - **API de DarkVisitors:** Proporcione `ROBOTSTXT_DARKVISITORS_TOKEN` y, opcionalmente, `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` y `ROBOTSTXT_DARKVISITORS_DISALLOW`.
    - **Listas de la Comunidad:** Especifique `ROBOTSTXT_COMMUNITY_LISTS` (IDs separados por espacios).
    - **URL personalizadas:** Proporcione `ROBOTSTXT_URLS` (URLs separadas por espacios).
    - **Reglas manuales:** Use `ROBOTSTXT_RULE` para reglas individuales (se pueden especificar múltiples reglas con `ROBOTSTXT_RULE_N`).
3.  **Filtre las reglas (opcional):** Use `ROBOTSTXT_IGNORE_RULE_N` para excluir reglas específicas por patrón de expresión regular.
4.  **Agregue mapas de sitio (opcional):** Use `ROBOTSTXT_SITEMAP_N` para las URL de los mapas de sitio.
5.  **Obtenga el archivo robots.txt generado:** Una vez que BunkerWeb esté funcionando con los ajustes anteriores, puede acceder al archivo `robots.txt` generado dinámicamente haciendo una solicitud HTTP GET a `http(s)://su-dominio.com/robots.txt`.

### Ajustes de Configuración

| Ajuste                               | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                           |
| ------------------------------------ | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_ROBOTSTXT`                      | `no`              | multisite | No       | Habilita o deshabilita la función `robots.txt`.                                                                                                       |
| `ROBOTSTXT_DARKVISITORS_TOKEN`       |                   | multisite | No       | Token de portador para la API de DarkVisitors.                                                                                                        |
| `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` |                   | multisite | No       | Lista de tipos de agentes separados por comas (por ejemplo, `AI Data Scraper`) para incluir desde DarkVisitors.                                       |
| `ROBOTSTXT_DARKVISITORS_DISALLOW`    | `/`               | multisite | No       | Una cadena que especifica qué URL no están permitidas. Este valor se enviará como el campo de no permitir al contactar con la API de DarkVisitors.    |
| `ROBOTSTXT_COMMUNITY_LISTS`          |                   | multisite | No       | Lista separada por espacios de IDs de conjuntos de reglas mantenidos por la comunidad para incluir.                                                   |
| `ROBOTSTXT_URLS`                     |                   | multisite | No       | Lista separada por espacios de URL para obtener reglas adicionales de `robots.txt`. Admite `file://` y autenticación básica (`http://user:pass@url`). |
| `ROBOTSTXT_RULE`                     |                   | multisite | Sí       | Una sola regla para `robots.txt`.                                                                                                                     |
| `ROBOTSTXT_HEADER`                   |                   | multisite | Sí       | Encabezado para el archivo `robots.txt` (antes de las reglas). Puede estar codificado en Base64.                                                      |
| `ROBOTSTXT_FOOTER`                   |                   | multisite | Sí       | Pie de página para el archivo `robots.txt` (después de las reglas). Puede estar codificado en Base64.                                                 |
| `ROBOTSTXT_IGNORE_RULE`              |                   | multisite | Sí       | Un único patrón de expresión regular PCRE para ignorar reglas.                                                                                        |
| `ROBOTSTXT_SITEMAP`                  |                   | multisite | Sí       | Una única URL de mapa de sitio.                                                                                                                       |

### Configuraciones de Ejemplo

**Reglas Manuales Básicas**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**Usando Fuentes Dinámicas (DarkVisitors y Lista de la Comunidad)**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "su-token-de-darkvisitors-aqui"
ROBOTSTXT_DARKVISITORS_AGENT_TYPES: "AI Data Scraper"
ROBOTSTXT_COMMUNITY_LISTS: "robots-disallowed"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
```

**Configuración Combinada**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "su-token-de-darkvisitors-aqui"
ROBOTSTXT_COMMUNITY_LISTS: "ai-robots-txt"
ROBOTSTXT_URLS: "https://example.com/my-custom-rules.txt"
ROBOTSTXT_RULE: "User-agent: MyOwnBot"
ROBOTSTXT_RULE_1: "Disallow: /admin"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**Con Encabezado y Pie de Página**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_HEADER: "# Este es un encabezado personalizado"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_FOOTER: "# Este es un pie de página personalizado"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

---

Para más información, consulte la [documentación de robots.txt](https://www.robotstxt.org/robotstxt.html).

## SSL

Compatibilidad con STREAM :white_check_mark:

El complemento SSL proporciona capacidades robustas de cifrado SSL/TLS para sus sitios web protegidos por BunkerWeb. Este componente principal permite conexiones HTTPS seguras al configurar y optimizar protocolos criptográficos, cifrados y ajustes de seguridad relacionados para proteger los datos en tránsito entre los clientes y sus servicios web.

**Cómo funciona:**

1.  Cuando un cliente inicia una conexión HTTPS a su sitio web, BunkerWeb gestiona el handshake SSL/TLS utilizando su configuración.
2.  El complemento impone protocolos de cifrado modernos y conjuntos de cifrado sólidos, al tiempo que deshabilita las opciones vulnerables conocidas.
3.  Los parámetros de sesión SSL optimizados mejoran el rendimiento de la conexión sin sacrificar la seguridad.
4.  La presentación de certificados se configura de acuerdo con las mejores prácticas para garantizar la compatibilidad y la seguridad.

!!! success "Beneficios de Seguridad" - **Protección de Datos:** Cifra los datos en tránsito, previniendo la interceptación y los ataques de intermediario (man-in-the-middle). - **Autenticación:** Verifica la identidad de su servidor a los clientes. - **Integridad:** Asegura que los datos no han sido manipulados durante la transmisión. - **Estándares Modernos:** Configurado para cumplir con las mejores prácticas y los estándares de seguridad de la industria.

### Cómo usar

Siga estos pasos para configurar y usar la función SSL:

1.  **Configure los protocolos:** Elija qué versiones de protocolo SSL/TLS admitir utilizando el ajuste `SSL_PROTOCOLS`.
2.  **Seleccione los conjuntos de cifrado:** Especifique la fuerza del cifrado utilizando el ajuste `SSL_CIPHERS_LEVEL` o proporcione cifrados personalizados con `SSL_CIPHERS_CUSTOM`.
3.  **Configure la redirección de HTTP a HTTPS:** Configure la redirección automática utilizando los ajustes `AUTO_REDIRECT_HTTP_TO_HTTPS` o `REDIRECT_HTTP_TO_HTTPS`.

### Ajustes de Configuración

| Ajuste                        | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                         |
| ----------------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_HTTP_TO_HTTPS`      | `no`              | multisite | no       | **Redirigir HTTP a HTTPS:** Cuando se establece en `yes`, todas las solicitudes HTTP se redirigen a HTTPS.                                          |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` | `yes`             | multisite | no       | **Redirección Automática de HTTP a HTTPS:** Cuando se establece en `yes`, redirige automáticamente de HTTP a HTTPS si se detecta HTTPS.             |
| `SSL_PROTOCOLS`               | `TLSv1.2 TLSv1.3` | multisite | no       | **Protocolos SSL:** Lista de protocolos SSL/TLS a admitir, separados por espacios.                                                                  |
| `SSL_CIPHERS_LEVEL`           | `modern`          | multisite | no       | **Nivel de Cifrados SSL:** Nivel de seguridad preestablecido para los conjuntos de cifrado (`modern`, `intermediate` o `old`).                      |
| `SSL_CIPHERS_CUSTOM`          |                   | multisite | no       | **Cifrados SSL Personalizados:** Lista de conjuntos de cifrado separados por dos puntos para usar en las conexiones SSL/TLS (sobrescribe el nivel). |
| `SSL_SESSION_CACHE_SIZE`      | `10m`             | multisite | no       | **Tamaño de Caché de Sesión SSL:** Tamaño de la caché de sesión SSL (ej., `10m`, `512k`). Establecer a `off` o `none` para desactivar.              |

!!! tip "Pruebas de SSL Labs"
    Después de configurar sus ajustes de SSL, utilice la [Prueba de Servidor de SSL Labs de Qualys](https://www.ssllabs.com/ssltest/) para verificar su configuración y buscar posibles problemas de seguridad. Una configuración de SSL adecuada de BunkerWeb debería obtener una calificación A+.

!!! warning "Selección de Protocolo"
    El soporte para protocolos más antiguos como SSLv3, TLSv1.0 y TLSv1.1 está deshabilitado intencionadamente por defecto debido a vulnerabilidades conocidas. Solo habilite estos protocolos si es absolutamente necesario para admitir clientes heredados y comprende las implicaciones de seguridad de hacerlo.

### Configuraciones de Ejemplo

=== "Seguridad Moderna (Predeterminada)"

    La configuración predeterminada que proporciona una seguridad sólida mientras mantiene la compatibilidad con los navegadores modernos:

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Máxima Seguridad"

    Configuración enfocada en la máxima seguridad, potencialmente con compatibilidad reducida para clientes más antiguos:

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

=== "Compatibilidad Heredada"

    Configuración con mayor compatibilidad para clientes más antiguos (úsela solo si es necesario):

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "old"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Cifrados Personalizados"

    Configuración que utiliza una especificación de cifrado personalizada:

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_CUSTOM: "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

## Security.txt

Compatibilidad con STREAM :white_check_mark:

El complemento Security.txt implementa el estándar [Security.txt](https://securitytxt.org/) ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116)) para su sitio web. Esta función ayuda a los investigadores de seguridad a acceder a sus políticas de seguridad y proporciona una forma estandarizada para que informen sobre las vulnerabilidades de seguridad que descubran en sus sistemas.

**Cómo funciona:**

1.  Cuando está habilitado, BunkerWeb crea un archivo `/.well-known/security.txt` en la raíz de su sitio web.
2.  Este archivo contiene información sobre sus políticas de seguridad, contactos y otros detalles relevantes.
3.  Los investigadores de seguridad y las herramientas automatizadas pueden encontrar fácilmente este archivo en la ubicación estándar.
4.  El contenido se configura mediante ajustes simples que le permiten especificar información de contacto, claves de cifrado, políticas y agradecimientos.
5.  BunkerWeb formatea automáticamente el archivo de acuerdo con la RFC 9116.

### Cómo usar

Siga estos pasos para configurar y usar la función Security.txt:

1.  **Habilite la función:** Establezca el ajuste `USE_SECURITYTXT` en `yes` para habilitar el archivo security.txt.
2.  **Configure la información de contacto:** Especifique al menos un método de contacto utilizando el ajuste `SECURITYTXT_CONTACT`.
3.  **Establezca información adicional:** Configure campos opcionales como la fecha de vencimiento, el cifrado, los agradecimientos y las URL de las políticas.
4.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, BunkerWeb creará y servirá automáticamente el archivo security.txt en la ubicación estándar.

### Ajustes de Configuración

| Ajuste                         | Valor por defecto           | Contexto  | Múltiple | Descripción                                                                                                                        |
| ------------------------------ | --------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_SECURITYTXT`              | `no`                        | multisite | no       | **Habilitar Security.txt:** Establezca en `yes` para habilitar el archivo security.txt.                                            |
| `SECURITYTXT_URI`              | `/.well-known/security.txt` | multisite | no       | **URI de Security.txt:** Indica la URI donde estará accesible el archivo security.txt.                                             |
| `SECURITYTXT_CONTACT`          |                             | multisite | sí       | **Información de contacto:** Cómo pueden contactarlo los investigadores de seguridad (p. ej., `mailto:security@example.com`).      |
| `SECURITYTXT_EXPIRES`          |                             | multisite | no       | **Fecha de vencimiento:** Cuándo debe considerarse que este archivo security.txt ha expirado (formato ISO 8601).                   |
| `SECURITYTXT_ENCRYPTION`       |                             | multisite | sí       | **Cifrado:** URL que apunta a las claves de cifrado que se utilizarán para la comunicación segura.                                 |
| `SECURITYTXT_ACKNOWLEDGEMENTS` |                             | multisite | sí       | **Agradecimientos:** URL donde se reconoce a los investigadores de seguridad por sus informes.                                     |
| `SECURITYTXT_POLICY`           |                             | multisite | sí       | **Política de seguridad:** URL que apunta a la política de seguridad que describe cómo informar vulnerabilidades.                  |
| `SECURITYTXT_HIRING`           |                             | multisite | sí       | **Empleos de seguridad:** URL que apunta a las ofertas de trabajo relacionadas con la seguridad.                                   |
| `SECURITYTXT_CANONICAL`        |                             | multisite | sí       | **URL canónica:** La(s) URI(s) canónica(s) para este archivo security.txt.                                                         |
| `SECURITYTXT_PREFERRED_LANG`   | `en`                        | multisite | no       | **Idioma(s) preferido(s):** El(los) idioma(s) utilizado(s) en las comunicaciones. Especificado como un código de idioma ISO 639-1. |
| `SECURITYTXT_CSAF`             |                             | multisite | sí       | **CSAF:** Enlace al `provider-metadata.json` de su proveedor de Common Security Advisory Framework.                                |

!!! warning "Se requiere fecha de vencimiento"
    Según la RFC 9116, el campo `Expires` es obligatorio. Si no proporciona un valor para `SECURITYTXT_EXPIRES`, BunkerWeb establece automáticamente la fecha de vencimiento en un año a partir de la fecha actual.

!!! info "La información de contacto es esencial"
    El campo `Contact` es la parte más importante del archivo security.txt. Debe proporcionar al menos una forma para que los investigadores de seguridad se pongan en contacto con usted. Puede ser una dirección de correo electrónico, un formulario web, un número de teléfono o cualquier otro método que funcione para su organización.

!!! warning "Las URL deben usar HTTPS"
    Según la RFC 9116, todas las URL del archivo security.txt (excepto los enlaces `mailto:` y `tel:`) DEBEN usar HTTPS. BunkerWeb convertirá automáticamente las URL que no sean HTTPS a HTTPS para garantizar el cumplimiento de la norma.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración mínima con solo información de contacto:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    ```

=== "Configuración Completa"

    Una configuración más completa con todos los campos:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "https://example.com/security-contact-form"
    SECURITYTXT_EXPIRES: "2023-12-31T23:59:59+00:00"
    SECURITYTXT_ENCRYPTION: "https://example.com/pgp-key.txt"
    SECURITYTXT_ACKNOWLEDGEMENTS: "https://example.com/hall-of-fame"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_HIRING: "https://example.com/jobs/security"
    SECURITYTXT_CANONICAL: "https://example.com/.well-known/security.txt"
    SECURITYTXT_PREFERRED_LANG: "en"
    SECURITYTXT_CSAF: "https://example.com/provider-metadata.json"
    ```

=== "Configuración de Múltiples Contactos"

    Configuración con múltiples métodos de contacto:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "tel:+1-201-555-0123"
    SECURITYTXT_CONTACT_3: "https://example.com/security-form"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_EXPIRES: "2024-06-30T23:59:59+00:00"
    ```

## Self-signed certificate

Compatibilidad con STREAM :white_check_mark:

El complemento de Certificado Autofirmado genera y gestiona automáticamente certificados SSL/TLS directamente dentro de BunkerWeb, lo que permite conexiones HTTPS seguras sin necesidad de una autoridad de certificación externa. Esta función es particularmente útil en entornos de desarrollo, redes internas o siempre que necesite implementar HTTPS rápidamente sin configurar certificados externos.

**Cómo funciona:**

1.  Cuando está habilitado, BunkerWeb genera automáticamente un certificado SSL/TLS autofirmado para sus dominios configurados.
2.  El certificado incluye todos los nombres de servidor definidos en su configuración, lo que garantiza una validación SSL adecuada para cada dominio.
3.  Los certificados se almacenan de forma segura y se utilizan para cifrar todo el tráfico HTTPS a sus sitios web.
4.  El certificado se renueva automáticamente antes de su vencimiento, lo que garantiza la disponibilidad continua de HTTPS.

!!! warning "Advertencias de Seguridad del Navegador"
    Los navegadores mostrarán advertencias de seguridad cuando los usuarios visiten sitios que utilizan certificados autofirmados, ya que estos certificados no están validados por una autoridad de certificación de confianza. Para entornos de producción, considere usar [Let's Encrypt](#lets-encrypt) en su lugar.

### Cómo usar

Siga estos pasos para configurar y usar la función de Certificado Autofirmado:

1.  **Habilite la función:** Establezca el ajuste `GENERATE_SELF_SIGNED_SSL` en `yes` para habilitar la generación de certificados autofirmados.
2.  **Elija el algoritmo criptográfico:** Seleccione su algoritmo preferido utilizando el ajuste `SELF_SIGNED_SSL_ALGORITHM`.
3.  **Configure el período de validez:** Opcionalmente, establezca cuánto tiempo debe ser válido el certificado utilizando el ajuste `SELF_SIGNED_SSL_EXPIRY`.
4.  **Establezca el sujeto del certificado:** Configure el sujeto del certificado utilizando el ajuste `SELF_SIGNED_SSL_SUBJ`.
5.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, los certificados se generan y aplican automáticamente a sus dominios.

!!! tip "Configuración en Modo Stream"
    Para el modo stream, configure el ajuste `LISTEN_STREAM_PORT_SSL` para especificar el puerto de escucha SSL/TLS. Este paso es esencial para el correcto funcionamiento en modo stream.

### Ajustes de Configuración

| Ajuste                      | Valor por defecto      | Contexto  | Múltiple | Descripción                                                                                                                                      |
| --------------------------- | ---------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GENERATE_SELF_SIGNED_SSL`  | `no`                   | multisite | no       | **Habilitar autofirmado:** Establezca en `yes` para habilitar la generación automática de certificados autofirmados.                             |
| `SELF_SIGNED_SSL_ALGORITHM` | `ec-prime256v1`        | multisite | no       | **Algoritmo del certificado:** Algoritmo utilizado para la generación de certificados: `ec-prime256v1`, `ec-secp384r1`, `rsa-2048` o `rsa-4096`. |
| `SELF_SIGNED_SSL_EXPIRY`    | `365`                  | multisite | no       | **Validez del certificado:** Número de días que el certificado autofirmado debe ser válido (predeterminado: 1 año).                              |
| `SELF_SIGNED_SSL_SUBJ`      | `/CN=www.example.com/` | multisite | no       | **Sujeto del certificado:** Campo de sujeto para el certificado que identifica el dominio.                                                       |

!!! tip "Entornos de Desarrollo"
    Los certificados autofirmados son ideales para entornos de desarrollo y prueba donde se necesita HTTPS pero no se requieren certificados de confianza para los navegadores públicos.

!!! info "Información del Certificado"
    Los certificados autofirmados generados utilizan el algoritmo especificado (por defecto, criptografía de curva elíptica con la curva prime256v1) e incluyen el sujeto configurado, lo que garantiza la funcionalidad adecuada para sus dominios.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple que utiliza certificados autofirmados con los ajustes predeterminados:

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=mysite.local/"
    ```

=== "Certificados de Corta Duración"

    Configuración con certificados que expiran con más frecuencia (útil para probar regularmente los procesos de renovación de certificados):

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "90"
    SELF_SIGNED_SSL_SUBJ: "/CN=dev.example.com/"
    ```

=== "Pruebas con Certificados RSA"

    Configuración para un entorno de prueba donde un dominio utiliza certificados RSA autofirmados:

    ```yaml
    SERVER_NAME: "test.example.com"
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "rsa-4096"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=test.example.com/"
    ```

## Sessions

Compatibilidad con STREAM :white_check_mark:

El complemento de Sesiones proporciona una gestión robusta de sesiones HTTP para BunkerWeb, lo que permite un seguimiento seguro y confiable de las sesiones de usuario entre solicitudes. Esta característica principal es esencial para mantener el estado del usuario, la persistencia de la autenticación y admitir otras funciones que requieren continuidad de la identidad, como la protección [anti-bot](#antibot) y los sistemas de autenticación de usuarios.

**Cómo funciona:**

1.  Cuando un usuario interactúa por primera vez con su sitio web, BunkerWeb crea un identificador de sesión único.
2.  Este identificador se almacena de forma segura en una cookie en el navegador del usuario.
3.  En solicitudes posteriores, BunkerWeb recupera el identificador de sesión de la cookie y lo utiliza para acceder a los datos de la sesión del usuario.
4.  Los datos de la sesión se pueden almacenar localmente o en [Redis](#redis) para entornos distribuidos con múltiples instancias de BunkerWeb.
5.  Las sesiones se gestionan automáticamente con tiempos de espera configurables, lo que garantiza la seguridad y la facilidad de uso.
6.  La seguridad criptográfica de las sesiones se garantiza mediante una clave secreta que se utiliza para firmar las cookies de sesión.

### Cómo usar

Siga estos pasos para configurar y usar la función de Sesiones:

1.  **Configure la seguridad de la sesión:** Establezca un `SESSIONS_SECRET` fuerte y único para garantizar que las cookies de sesión no puedan ser falsificadas. (El valor predeterminado es "random", lo que hace que BunkerWeb genere una clave secreta aleatoria).
2.  **Elija un nombre de sesión:** Opcionalmente, personalice el `SESSIONS_NAME` para definir cómo se llamará su cookie de sesión en el navegador. (El valor predeterminado es "random", lo que hace que BunkerWeb genere un nombre aleatorio).
3.  **Establezca los tiempos de espera de la sesión:** Configure cuánto tiempo permanecen válidas las sesiones con los ajustes de tiempo de espera (`SESSIONS_IDLING_TIMEOUT`, `SESSIONS_ROLLING_TIMEOUT`, `SESSIONS_ABSOLUTE_TIMEOUT`).
4.  **Configure la integración con Redis:** Para entornos distribuidos, establezca `USE_REDIS` en "yes" y configure su [conexión Redis](#redis) para compartir los datos de la sesión entre múltiples nodos de BunkerWeb.
5.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, la gestión de sesiones se realiza automáticamente para su sitio web.

### Ajustes de Configuración

| Ajuste                      | Valor por defecto | Contexto | Múltiple | Descripción                                                                                                                                         |
| --------------------------- | ----------------- | -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SESSIONS_SECRET`           | `random`          | global   | no       | **Secreto de sesión:** Clave criptográfica utilizada para firmar las cookies de sesión. Debe ser una cadena fuerte y aleatoria única para su sitio. |
| `SESSIONS_NAME`             | `random`          | global   | no       | **Nombre de la cookie:** El nombre de la cookie que almacenará el identificador de sesión.                                                          |
| `SESSIONS_IDLING_TIMEOUT`   | `1800`            | global   | no       | **Tiempo de espera por inactividad:** Tiempo máximo (en segundos) de inactividad antes de que la sesión se invalide.                                |
| `SESSIONS_ROLLING_TIMEOUT`  | `3600`            | global   | no       | **Tiempo de espera renovable:** Tiempo máximo (en segundos) antes de que una sesión deba renovarse.                                                 |
| `SESSIONS_ABSOLUTE_TIMEOUT` | `86400`           | global   | no       | **Tiempo de espera absoluto:** Tiempo máximo (en segundos) antes de que una sesión se destruya independientemente de la actividad.                  |
| `SESSIONS_CHECK_IP`         | `yes`             | global   | no       | **Comprobar IP:** Cuando se establece en `yes`, destruye la sesión si la dirección IP del cliente cambia.                                           |
| `SESSIONS_CHECK_USER_AGENT` | `yes`             | global   | no       | **Comprobar User-Agent:** Cuando se establece en `yes`, destruye la sesión si el User-Agent del cliente cambia.                                     |

!!! warning "Consideraciones de Seguridad"
    El ajuste `SESSIONS_SECRET` es fundamental para la seguridad. En entornos de producción:

    1. Use un valor fuerte y aleatorio (al menos 32 caracteres)
    2. Mantenga este valor confidencial
    3. Use el mismo valor en todas las instancias de BunkerWeb en un clúster
    4. Considere usar variables de entorno o gestión de secretos para evitar almacenar esto en texto plano

!!! tip "Entornos en Clúster"
    Si está ejecutando múltiples instancias de BunkerWeb detrás de un balanceador de carga:

    1. Establezca `USE_REDIS` en `yes` y configure su conexión Redis
    2. Asegúrese de que todas las instancias usen exactamente el mismo `SESSIONS_SECRET` y `SESSIONS_NAME`
    3. Esto garantiza que los usuarios mantengan su sesión independientemente de qué instancia de BunkerWeb maneje sus solicitudes

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple para una única instancia de BunkerWeb:

    ```yaml
    SESSIONS_SECRET: "su-clave-secreta-fuerte-y-aleatoria-aqui"
    SESSIONS_NAME: "sesiondemicliente"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    ```

=== "Seguridad Mejorada"

    Configuración con ajustes de seguridad aumentados:

    ```yaml
    SESSIONS_SECRET: "su-clave-secreta-muy-fuerte-y-aleatoria-aqui"
    SESSIONS_NAME: "sesionsegura"
    SESSIONS_IDLING_TIMEOUT: "900"  # 15 minutos
    SESSIONS_ROLLING_TIMEOUT: "1800"  # 30 minutos
    SESSIONS_ABSOLUTE_TIMEOUT: "43200"  # 12 horas
    SESSIONS_CHECK_IP: "yes"
    SESSIONS_CHECK_USER_AGENT: "yes"
    ```

=== "Entorno en Clúster con Redis"

    Configuración para múltiples instancias de BunkerWeb que comparten datos de sesión:

    ```yaml
    SESSIONS_SECRET: "su-clave-secreta-fuerte-y-aleatoria-aqui"
    SESSIONS_NAME: "sesiondelcluster"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    USE_REDIS: "yes"
    # Asegúrese de que la conexión a Redis esté configurada correctamente
    ```

=== "Sesiones de Larga Duración"

    Configuración para aplicaciones que requieren persistencia de sesión extendida:

    ```yaml
    SESSIONS_SECRET: "su-clave-secreta-fuerte-y-aleatoria-aqui"
    SESSIONS_NAME: "sesionpersistente"
    SESSIONS_IDLING_TIMEOUT: "86400"  # 1 día
    SESSIONS_ROLLING_TIMEOUT: "172800"  # 2 días
    SESSIONS_ABSOLUTE_TIMEOUT: "604800"  # 7 días
    ```

## UI

Compatibilidad con STREAM :x:

Integrate easily the BunkerWeb UI.

| Parámetro | Valor predeterminado | Contexto  | Múltiple | Descripción                                  |
| --------- | -------------------- | --------- | -------- | -------------------------------------------- |
| `USE_UI`  | `no`                 | multisite | no       | Use UI                                       |
| `UI_HOST` |                      | global    | no       | Address of the web UI used for initial setup |

## User Manager <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


<p align='center'><iframe style='display: block;' width='560' height='315' data-src='https://www.youtube-nocookie.com/embed/EIohiUf9Fg4' title='Página del Administrador de usuarios' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe></p>

Compatibilidad con STREAM :x:

Add the possibility to manage users on the web interface

| Parámetro           | Valor predeterminado | Contexto | Múltiple | Descripción                                     |
| ------------------- | -------------------- | -------- | -------- | ----------------------------------------------- |
| `USERS_REQUIRE_2FA` | `no`                 | global   | no       | Require two-factor authentication for all users |

## Whitelist

Compatibilidad con STREAM :warning:

El complemento de Lista Blanca le permite definir una lista de direcciones IP de confianza que omiten otros filtros de seguridad.
Para bloquear clientes no deseados, consulte el [complemento de Lista Negra](#blacklist).

El complemento de Lista Blanca proporciona un enfoque integral para permitir explícitamente el acceso a su sitio web basándose en diversos atributos del cliente. Esta característica proporciona un mecanismo de seguridad: a los visitantes que coinciden con criterios específicos se les concede acceso inmediato, mientras que todos los demás deben pasar por los controles de seguridad habituales.

**Cómo funciona:**

1.  Usted define los criterios para los visitantes que deben estar en la "lista blanca" (_direcciones IP, redes, DNS inverso, ASN, User-Agent o patrones de URI_).
2.  Cuando un visitante intenta acceder a su sitio, BunkerWeb comprueba si coincide con alguno de estos criterios de la lista blanca.
3.  Si un visitante coincide con alguna regla de la lista blanca (y no coincide con ninguna regla de omisión), se le concede acceso a su sitio y **omite todos los demás controles de seguridad**.
4.  Si un visitante no coincide con ningún criterio de la lista blanca, procede a través de todos los controles de seguridad normales como de costumbre.
5.  Las listas blancas se pueden actualizar automáticamente desde fuentes externas de forma programada.

### Cómo usar

Siga estos pasos para configurar y usar la función de Lista Blanca:

1.  **Habilite la función:** La función de Lista Blanca está deshabilitada por defecto. Establezca el ajuste `USE_WHITELIST` en `yes` para habilitarla.
2.  **Configure las reglas de permiso:** Defina qué IP, redes, patrones de DNS inverso, ASN, User-Agents o URI deben estar en la lista blanca.
3.  **Configure las reglas de omisión:** Especifique cualquier excepción que deba omitir las comprobaciones de la lista blanca.
4.  **Añada fuentes externas:** Configure URL para descargar y actualizar automáticamente los datos de la lista blanca.
5.  **Supervise el acceso:** Consulte la [interfaz de usuario web](web-ui.md) para ver qué visitantes están siendo permitidos o denegados.

!!! info "modo stream"
    Cuando se utiliza el modo stream, solo se realizan las comprobaciones de IP, DNS inverso y ASN.

### Ajustes de Configuración

**General**

| Ajuste          | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                |
| --------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------ |
| `USE_WHITELIST` | `no`              | multisite | no       | **Habilitar Lista Blanca:** Establezca en `yes` para habilitar la función de lista blanca. |

=== "Dirección IP"
    **Qué hace esto:** Pone en la lista blanca a los visitantes según su dirección IP o red. Estos visitantes omitirán todos los controles de seguridad.

    | Ajuste                     | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                               |
    | -------------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_IP`             |                   | multisite | no       | **Lista Blanca de IP:** Lista de direcciones IP o redes (notación CIDR) para permitir, separadas por espacios.                            |
    | `WHITELIST_IGNORE_IP`      |                   | multisite | no       | **Lista de Omisión de IP:** Lista de direcciones IP o redes que deben omitir las comprobaciones de la lista blanca de IP.                 |
    | `WHITELIST_IP_URLS`        |                   | multisite | no       | **URL de Lista Blanca de IP:** Lista de URL que contienen direcciones IP o redes para incluir en la lista blanca, separadas por espacios. |
    | `WHITELIST_IGNORE_IP_URLS` |                   | multisite | no       | **URL de Lista de Omisión de IP:** Lista de URL que contienen direcciones IP o redes para ignorar.                                        |

=== "DNS Inverso"
    **Qué hace esto:** Pone en la lista blanca a los visitantes según su nombre de dominio (en inverso). Esto es útil para permitir el acceso a visitantes de organizaciones o redes específicas por su dominio.

    | Ajuste                       | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                 |
    | ---------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_RDNS`             |                   | multisite | no       | **Lista Blanca de rDNS:** Lista de sufijos de DNS inverso para permitir, separados por espacios.                                            |
    | `WHITELIST_RDNS_GLOBAL`      | `yes`             | multisite | no       | **Solo rDNS Global:** Realiza comprobaciones de la lista blanca de rDNS solo en direcciones IP globales cuando se establece en `yes`.       |
    | `WHITELIST_IGNORE_RDNS`      |                   | multisite | no       | **Lista de Omisión de rDNS:** Lista de sufijos de DNS inverso que deben omitir las comprobaciones de la lista blanca de rDNS.               |
    | `WHITELIST_RDNS_URLS`        |                   | multisite | no       | **URL de Lista Blanca de rDNS:** Lista de URL que contienen sufijos de DNS inverso para incluir en la lista blanca, separadas por espacios. |
    | `WHITELIST_IGNORE_RDNS_URLS` |                   | multisite | no       | **URL de Lista de Omisión de rDNS:** Lista de URL que contienen sufijos de DNS inverso para ignorar.                                        |

=== "ASN"
    **Qué hace esto:** Pone en la lista blanca a los visitantes de proveedores de red específicos utilizando Números de Sistema Autónomo. Los ASN identifican a qué proveedor u organización pertenece una IP.

    | Ajuste                      | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                             |
    | --------------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_ASN`             |                   | multisite | no       | **Lista Blanca de ASN:** Lista de Números de Sistema Autónomo para permitir, separados por espacios.                    |
    | `WHITELIST_IGNORE_ASN`      |                   | multisite | no       | **Lista de Omisión de ASN:** Lista de ASN que deben omitir las comprobaciones de la lista blanca de ASN.                |
    | `WHITELIST_ASN_URLS`        |                   | multisite | no       | **URL de Lista Blanca de ASN:** Lista de URL que contienen ASN para incluir en la lista blanca, separados por espacios. |
    | `WHITELIST_IGNORE_ASN_URLS` |                   | multisite | no       | **URL de Lista de Omisión de ASN:** Lista de URL que contienen ASN para ignorar.                                        |

=== "User Agent"
    **Qué hace esto:** Pone en la lista blanca a los visitantes según el navegador o la herramienta que dicen estar usando. Esto es efectivo para permitir el acceso a herramientas o servicios conocidos específicos.

    | Ajuste                             | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                               |
    | ---------------------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_USER_AGENT`             |                   | multisite | no       | **Lista Blanca de User-Agent:** Lista de patrones de User-Agent (expresión regular PCRE) para permitir, separados por espacios.           |
    | `WHITELIST_IGNORE_USER_AGENT`      |                   | multisite | no       | **Lista de Omisión de User-Agent:** Lista de patrones de User-Agent que deben omitir las comprobaciones de la lista blanca de User-Agent. |
    | `WHITELIST_USER_AGENT_URLS`        |                   | multisite | no       | **URL de Lista Blanca de User-Agent:** Lista de URL que contienen patrones de User-Agent para incluir en la lista blanca.                 |
    | `WHITELIST_IGNORE_USER_AGENT_URLS` |                   | multisite | no       | **URL de Lista de Omisión de User-Agent:** Lista de URL que contienen patrones de User-Agent para ignorar.                                |

=== "URI"
    **Qué hace esto:** Pone en la lista blanca las solicitudes a URL específicas de su sitio. Esto es útil para permitir el acceso a puntos finales específicos independientemente de otros factores.

    | Ajuste                      | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                         |
    | --------------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_URI`             |                   | multisite | no       | **Lista Blanca de URI:** Lista de patrones de URI (expresión regular PCRE) para permitir, separados por espacios.                   |
    | `WHITELIST_IGNORE_URI`      |                   | multisite | no       | **Lista de Omisión de URI:** Lista de patrones de URI que deben omitir las comprobaciones de la lista blanca de URI.                |
    | `WHITELIST_URI_URLS`        |                   | multisite | no       | **URL de Lista Blanca de URI:** Lista de URL que contienen patrones de URI para incluir en la lista blanca, separados por espacios. |
    | `WHITELIST_IGNORE_URI_URLS` |                   | multisite | no       | **URL de Lista de Omisión de URI:** Lista de URL que contienen patrones de URI para ignorar.                                        |

!!! info "Soporte de Formato de URL"
    Todos los ajustes `*_URLS` admiten URL HTTP/HTTPS así como rutas de archivos locales usando el prefijo `file:///`. Se admite la autenticación básica usando el formato `http://usuario:contraseña@url`.

!!! tip "Actualizaciones Regulares"
    Las listas blancas de las URL se descargan y actualizan automáticamente cada hora para asegurar que su protección se mantenga actualizada con las últimas fuentes de confianza.

!!! warning "Omisión de Seguridad"
    Los visitantes en la lista blanca **omitirán por completo todos los demás controles de seguridad** en BunkerWeb, incluidas las reglas del WAF, la limitación de velocidad, la detección de bots maliciosos y cualquier otro mecanismo de seguridad. Use la lista blanca solo para fuentes de confianza en las que esté absolutamente seguro.

### Configuraciones de Ejemplo

=== "Acceso Básico de la Organización"

    Una configuración simple que pone en la lista blanca las IP de la oficina de la empresa:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP: "192.168.1.0/24 10.0.0.0/8 203.0.113.42"
    ```

=== "Configuración Avanzada"

    Una configuración más completa con múltiples criterios de lista blanca:

    ```yaml
    USE_WHITELIST: "yes"

    # Activos de la empresa y de socios de confianza
    WHITELIST_IP: "192.168.1.0/24 203.0.113.0/24"
    WHITELIST_RDNS: ".company.com .partner-company.org"
    WHITELIST_ASN: "12345 67890"  # ASN de la empresa y del socio
    WHITELIST_USER_AGENT: "(?:\b)CompanyBot(?:\b) (?:\b)PartnerCrawler(?:\b)"

    # Fuentes externas de confianza
    WHITELIST_IP_URLS: "https://example.com/trusted-networks.txt"
    WHITELIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Usando Archivos Locales"

    Configuración usando archivos locales para las listas blancas:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP_URLS: "file:///ruta/a/ip-whitelist.txt"
    WHITELIST_RDNS_URLS: "file:///ruta/a/rdns-whitelist.txt"
    WHITELIST_ASN_URLS: "file:///ruta/a/asn-whitelist.txt"
    WHITELIST_USER_AGENT_URLS: "file:///ruta/a/user-agent-whitelist.txt"
    WHITELIST_URI_URLS: "file:///ruta/a/uri-whitelist.txt"
    ```

=== "Patrón de Acceso a la API"

    Una configuración enfocada en permitir el acceso solo a puntos finales específicos de la API:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_URI: "^/api/v1/public/ ^/api/v1/status"
    WHITELIST_IP: "192.168.1.0/24"  # Red interna para todos los puntos finales
    ```

=== "Rastreadores Conocidos"

    Una configuración que pone en la lista blanca a los rastreadores comunes de motores de búsqueda y redes sociales:

    ```yaml
    USE_WHITELIST: "yes"

    # Verificación con DNS inverso para mayor seguridad
    WHITELIST_RDNS: ".googlebot.com .search.msn.com .crawl.yahoo.net .yandex.com .baidu.com .facebook.com"
    WHITELIST_RDNS_GLOBAL: "yes"  # Solo verificar IP globales
    ```

    Esta configuración permite que los rastreadores legítimos indexen su sitio sin estar sujetos a la limitación de velocidad u otras medidas de seguridad que podrían bloquearlos. Las comprobaciones de DNS inverso ayudan a verificar que los rastreadores provienen realmente de las empresas que dicen ser.

### Trabajar con archivos de listas locales

Las configuraciones `*_URLS` de los plugins de lista blanca, lista gris y lista negra utilizan el mismo descargador. Cuando referencia una URL `file:///`:

- La ruta se resuelve dentro del contenedor del **scheduler** (en despliegues Docker normalmente `bunkerweb-scheduler`). Monte los archivos allí y asegúrese de que el usuario del scheduler tenga permisos de lectura.
- Cada archivo es texto codificado en UTF-8 con una entrada por línea. Las líneas vacías se ignoran y las líneas de comentario deben comenzar con `#` o `;`. Los comentarios `//` no son compatibles.
- Valores esperados por tipo de lista:
  - **Listas IP** aceptan direcciones IPv4/IPv6 o redes CIDR (por ejemplo `192.0.2.10` o `2001:db8::/48`).
  - **Listas rDNS** esperan un sufijo sin espacios (por ejemplo `.search.msn.com`). Los valores se normalizan automáticamente a minúsculas.
  - **Listas ASN** pueden contener solo el número (`32934`) o el número con el prefijo `AS` (`AS15169`).
  - **Listas de User-Agent** se tratan como patrones PCRE y se conserva la línea completa (incluidos los espacios). Mantenga los comentarios en una línea separada para que no se interpreten como parte del patrón.
  - **Listas URI** deben comenzar con `/` y pueden usar tokens PCRE como `^` o `$`.

Ejemplos de archivos con el formato esperado:

```text
# /etc/bunkerweb/lists/ip-whitelist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-whitelist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
