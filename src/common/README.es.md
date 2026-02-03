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
    | `KEEP_CONFIG_ON_RESTART` | `no` | global | No | **Mantener Configuración al Reiniciar:** Mantener la configuración al reiniciar. Establecer a 'yes' para evitar el restablecimiento de la configuración al reiniciar. |
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
