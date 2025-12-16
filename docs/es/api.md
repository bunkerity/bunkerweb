# API

## Rol de la API

La API de BunkerWeb es el plano de control para gestionar instancias, servicios, bloqueos, plugins, trabajos y configuraciones personalizadas. Se ejecuta como una app FastAPI detrás de Gunicorn y debe mantenerse en una red de confianza. Docs interactivas en `/docs` (o `<API_ROOT_PATH>/docs`); el esquema OpenAPI en `/openapi.json`.

!!! warning "Manténla privada"
    No expongas la API directamente a Internet. Mantenla en una red interna, restringe IPs de origen y exige autenticación.

!!! info "Datos rápidos"
    - Endpoints de salud: `GET /ping` y `GET /health`
    - Ruta raíz: define `API_ROOT_PATH` al usar reverse proxy en subruta para que docs y OpenAPI funcionen
    - Auth obligatoria: tokens Biscuit, Basic admin o un Bearer de override
    - Lista blanca IP por defecto a rangos RFC1918 (`API_WHITELIST_IPS`); desactiva solo si el upstream controla el acceso
    - Rate limiting activado por defecto; `/auth` siempre tiene su propio límite

## Checklist de seguridad

- Red: mantén el tráfico interno; escucha en loopback o interfaz interna y restringe IPs de origen con `API_WHITELIST_IPS` (activo por defecto).
- Auth presente: define `API_USERNAME`/`API_PASSWORD` (admin) y, si hace falta, `API_ACL_BOOTSTRAP_FILE` para más usuarios/ACL; guarda un `API_TOKEN` solo para emergencias.
- Ocultar ruta: con reverse proxy, elige un `API_ROOT_PATH` poco obvio y refléjalo en el proxy.
- Rate limiting: déjalo activado salvo que otra capa imponga límites equivalentes; `/auth` siempre está limitado.
- TLS: termina en el proxy o usa `API_SSL_ENABLED=yes` con rutas de cert/clave.

## Ejecución

Elige el sabor que encaje con tu entorno.

=== "Docker"

    Layout Compose mínimo con la API detrás de BunkerWeb. Ajusta versiones y contraseñas antes de usar.

    ```yaml
    x-bw-env: &bw-env
      # Usamos un ancla para no repetir ajustes entre servicios
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Ajusta el rango IP correcto para que el scheduler envíe la config a la instancia (API interna de BunkerWeb)
      # Opcional: define un token y refléjalo en ambos contenedores (API interna de BunkerWeb)
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Usa una contraseña más fuerte para la base de datos

    services:
      bunkerweb:
        # Nombre que usará el scheduler para identificar la instancia
        image: bunkerity/bunkerweb:1.6.7~rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Para QUIC / HTTP3
        environment:
          <<: *bw-env # Reutilizamos el ancla para evitar duplicados
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7~rc1
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Asegúrate de poner el nombre de instancia correcto
          SERVER_NAME: "api.example.com"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
          DISABLE_DEFAULT_SERVER: "yes"
          AUTO_LETS_ENCRYPT: "yes"
          api.example.com_USE_TEMPLATE: "api"
          api.example.com_USE_REVERSE_PROXY: "yes"
          api.example.com_REVERSE_PROXY_URL: "/"
          api.example.com_REVERSE_PROXY_HOST: "http://bw-api:8888"
        volumes:
          - bw-storage:/data # Persistir caché y backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.7~rc1
        environment:
          <<: *bw-env
          API_USERNAME: "admin"
          API_PASSWORD: "Str0ng&P@ss!"
          # API_TOKEN: "admin-override-token" # opcional
          FORWARDED_ALLOW_IPS: "*" # Cuidado: solo úsalo si el reverse proxy es la única vía
          API_ROOT_PATH: "/"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Max allowed packet más grande para evitar problemas con queries grandes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Usa una contraseña más fuerte
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis para persistir reports/bans/stats
        image: redis:8-alpine
        command: >
          redis-server
          --maxmemory 256mb
          --maxmemory-policy allkeys-lru
          --save 60 1000
          --appendonly yes
        volumes:
          - redis-data:/data
        restart: "unless-stopped"
        networks:
          - bw-universe

    volumes:
      bw-data:
      bw-storage:
      redis-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Ajusta el rango IP correcto para que el scheduler envíe la config a la instancia
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "All-in-One"

    ```bash
    docker run -d \
      --name bunkerweb-aio \
      -e SERVICE_API=yes \
      -e API_WHITELIST_IPS="127.0.0.0/8" \
      -p 80:8080/tcp -p 443:8443/tcp -p 443:8443/udp \
      bunkerity/bunkerweb-all-in-one:1.6.7~rc1
    ```

=== "Linux"

    Los paquetes DEB/RPM incluyen `bunkerweb-api.service`, gestionado por `/usr/share/bunkerweb/scripts/bunkerweb-api.sh`.

    - Activar/iniciar: `sudo systemctl enable --now bunkerweb-api.service`
    - Recargar: `sudo systemctl reload bunkerweb-api.service`
    - Logs: journal más `/var/log/bunkerweb/api.log`
    - Escucha por defecto: `127.0.0.1:8888` con `API_WHITELIST_IPS=127.0.0.1`
    - Archivos de config: `/etc/bunkerweb/api.env` (se crea con defaults comentados al primer arranque) y `/etc/bunkerweb/api.yml`
    - Fuentes de entorno: `api.env`, `variables.env`, `/run/secrets/<VAR>` y luego exportadas al proceso Gunicorn

    Edita `/etc/bunkerweb/api.env` para definir `API_USERNAME`/`API_PASSWORD`, allowlist, TLS, límites de tasa o `API_ROOT_PATH`, luego `systemctl reload bunkerweb-api`.

## Autenticación y autorización

- `/auth` emite tokens Biscuit. Las credenciales pueden venir por Basic auth, campos de formulario, cuerpo JSON o un header Bearer igual a `API_TOKEN` (override admin).
- Los administradores pueden llamar rutas protegidas directamente con HTTP Basic (sin Biscuit).
- Si el Bearer coincide con `API_TOKEN`, el acceso es total/admin. Si no, el guard de Biscuit aplica ACL.
- El payload de Biscuit incluye usuario, tiempo, IP cliente, host, versión, un rol amplio `role("api_user", ["read", "write"])` y `admin(true)` o permisos finos `api_perm(resource_type, resource_id|*, permission)`.
- TTL es `API_BISCUIT_TTL_SECONDS` (0/off desactiva expiración). Las llaves viven en `/var/lib/bunkerweb/.api_biscuit_private_key` y `.api_biscuit_public_key` salvo que se pasen con `BISCUIT_PRIVATE_KEY`/`BISCUIT_PUBLIC_KEY`.
- Los endpoints de auth solo están expuestos cuando existe al menos un usuario de API en la base.

!!! tip "Auth rápido"
    1. Define `API_USERNAME` y `API_PASSWORD` (y `OVERRIDE_API_CREDS=yes` si necesitas resembrar).
    2. Llama a `POST /auth` con Basic; lee `.token` de la respuesta.
    3. Usa `Authorization: Bearer <token>` en las siguientes llamadas.

## Permisos y ACL

- Rol grueso: GET/HEAD/OPTIONS requieren `read`; verbos de escritura requieren `write`.
- ACL fina se aplica cuando las rutas declaran permisos; `admin(true)` omite chequeos.
- Tipos de recurso: `instances`, `global_settings`, `services`, `configs`, `plugins`, `cache`, `bans`, `jobs`.
- Nombres de permisos:
  - `instances_*`: `instances_read`, `instances_update`, `instances_delete`, `instances_create`, `instances_execute`
  - `global_settings_*`: `global_settings_read`, `global_settings_update`
  - `services`: `service_read`, `service_create`, `service_update`, `service_delete`, `service_convert`, `service_export`
  - `configs`: `configs_read`, `config_read`, `config_create`, `config_update`, `config_delete`
  - `plugins`: `plugin_read`, `plugin_create`, `plugin_delete`
  - `cache`: `cache_read`, `cache_delete`
  - `bans`: `ban_read`, `ban_update`, `ban_delete`, `ban_created`
  - `jobs`: `job_read`, `job_run`
- `resource_id` suele ser el segundo componente del path (ej. `/services/{id}`); "*" da acceso global.
- Inicializa usuarios no admin y permisos con `API_ACL_BOOTSTRAP_FILE` o un `/var/lib/bunkerweb/api_acl_bootstrap.json` montado. Contraseñas pueden ser texto plano o hash bcrypt.

??? example "ACL mínima"
    ```json
    {
      "users": {
        "ci": {
          "admin": false,
          "password": "Str0ng&P@ss!",
          "permissions": {
            "services": { "*": { "service_read": true } },
            "configs": { "*": { "config_read": true, "config_update": true } }
          }
        }
      }
    }
    ```

## Limitación de velocidad

Activa por defecto con dos cadenas: `API_RATE_LIMIT` (global, por defecto `100r/m`) y `API_RATE_LIMIT_AUTH` (por defecto `10r/m` u `off`). Acepta notación estilo NGINX (`3r/s`, `40r/m`, `200r/h`) o formas verbosas (`100/minute`, `200 per 30 minutes`). Configura mediante:

- `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`
- `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_HEADERS_ENABLED`
- `API_RATE_LIMIT_RULES` (cadena CSV/JSON/YAML o ruta a archivo)
- `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`
- Almacenamiento en memoria o Redis/Valkey con `USE_REDIS=yes` más ajustes `REDIS_*` (Sentinel soportado).

Estrategias del limitador (proveídas por `limits`):

- `fixed-window` (predeterminado): el bucket se reinicia en cada borde de intervalo; más barato y suficiente para límites gruesos.
- `moving-window`: ventana deslizante real con timestamps precisos; más suave pero más costosa en operaciones de almacenamiento.
- `sliding-window-counter`: híbrido que suaviza con conteos ponderados de la ventana previa; más liviano que moving y más suave que fixed.

Más detalles y trade-offs: [https://limits.readthedocs.io/en/stable/strategies.html](https://limits.readthedocs.io/en/stable/strategies.html)

??? example "CSV en línea"
    ```
    API_RATE_LIMIT_RULES='POST /auth 10r/m, GET /instances* 200r/m, POST|PATCH /services* 40r/m'
    ```

??? example "Archivo YAML"
    ```yaml
    API_RATE_LIMIT: 200r/m
    API_RATE_LIMIT_AUTH: 15r/m
    API_RATE_LIMIT_RULES:
      - path: "/auth"
        methods: "POST"
        rate: "10r/m"
      - path: "/instances*"
        methods: "GET|POST"
        rate: "100r/m"
    ```

## Fuentes de configuración y prioridad

1. Variables de entorno (incluyendo `environment:` de Docker/Compose)
2. Secrets en `/run/secrets/<VAR>` (Docker)
3. YAML en `/etc/bunkerweb/api.yml`
4. Archivo env en `/etc/bunkerweb/api.env`
5. Valores predeterminados

### Tiempo de ejecución y zona horaria

| Setting | Descripción                                                                                           | Valores aceptados                                  | Predeterminado                                  |
| ------- | ----------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------- |
| `TZ`    | Zona horaria para logs de la API y claims basados en tiempo (p. ej. TTL de Biscuit y marcas de tiempo) | Nombre de base TZ (p. ej. `UTC`, `Europe/Paris`)   | unset (default del contenedor, normalmente UTC) |

Desactiva docs o esquema poniendo sus URLs en `off|disabled|none|false|0`. Define `API_SSL_ENABLED=yes` con `API_SSL_CERTFILE` y `API_SSL_KEYFILE` para terminar TLS en la API. Con reverse proxy, define `API_FORWARDED_ALLOW_IPS` a las IPs del proxy para que Gunicorn confíe en los `X-Forwarded-*`.

### Referencia de configuración (power users)

#### Superficie y docs

| Setting                                            | Descripción                                                                                | Valores aceptados           | Predeterminado                       |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------ | --------------------------- | ------------------------------------ |
| `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL` | Rutas para Swagger, ReDoc y OpenAPI; pon `off/disabled/none/false/0` para desactivar       | Ruta o `off`                | `/docs`, `/redoc`, `/openapi.json`   |
| `API_ROOT_PATH`                                    | Prefijo de montaje al usar reverse proxy                                                   | Ruta (ej. `/api`)           | vacío                                 |
| `API_FORWARDED_ALLOW_IPS`                          | IPs de proxy confiables para `X-Forwarded-*`                                               | IPs/CIDRs separadas por comas | `127.0.0.1` (default de paquete)     |

#### Auth, ACL, Biscuit

| Setting                                     | Descripción                                  | Valores aceptados                                                  | Predeterminado              |
| ------------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------ | --------------------------- |
| `API_USERNAME`, `API_PASSWORD`              | Usuario admin inicial                        | Strings; contraseña fuerte requerida fuera de debug                | unset                       |
| `OVERRIDE_API_CREDS`                        | Reaplicar credenciales admin al arranque     | `yes/no/on/off/true/false/0/1`                                      | `no`                        |
| `API_TOKEN`                                 | Bearer de override admin                     | Cadena opaca                                                      | unset                       |
| `API_ACL_BOOTSTRAP_FILE`                    | Ruta JSON para usuarios/permisos             | Ruta o `/var/lib/bunkerweb/api_acl_bootstrap.json` montado          | unset                       |
| `BISCUIT_PRIVATE_KEY`, `BISCUIT_PUBLIC_KEY` | Claves Biscuit (hex) si no se usan archivos  | Cadenas hex                                                       | auto-generadas/persistidas  |
| `API_BISCUIT_TTL_SECONDS`                   | Vida del token; `0/off` desactiva expiración | Entero en segundos o `off/disabled`                                | `3600`                      |
| `CHECK_PRIVATE_IP`                          | Liga Biscuit a la IP cliente (excepto privada) | `yes/no/on/off/true/false/0/1`                                     | `yes`                       |

#### Allowlist

| Setting                 | Descripción                          | Valores aceptados                | Predeterminado             |
| ----------------------- | ------------------------------------ | -------------------------------- | -------------------------- |
| `API_WHITELIST_ENABLED` | Alternar middleware de lista blanca  | `yes/no/on/off/true/false/0/1`   | `yes`                      |
| `API_WHITELIST_IPS`     | IPs/CIDRs separadas por espacio/coma | IPs/CIDRs                        | Rangos RFC1918 en código   |

#### Limitación

| Setting                          | Descripción                                  | Valores aceptados                                           | Predeterminado  |
| -------------------------------- | -------------------------------------------- | ----------------------------------------------------------- | --------------- |
| `API_RATE_LIMIT`                 | Límite global (cadena estilo NGINX)          | `3r/s`, `100/minute`, `500 per 30 minutes`                  | `100r/m`        |
| `API_RATE_LIMIT_AUTH`            | Límite de `/auth` (o `off`)                  | igual que arriba o `off/disabled/none/false/0`              | `10r/m`         |
| `API_RATE_LIMIT_ENABLED`         | Activar limitador                            | `yes/no/on/off/true/false/0/1`                              | `yes`           |
| `API_RATE_LIMIT_HEADERS_ENABLED` | Inyectar headers de límite                   | igual que arriba                                            | `yes`           |
| `API_RATE_LIMIT_RULES`           | Reglas por ruta (CSV/JSON/YAML o ruta)       | Cadena o ruta                                               | unset           |
| `API_RATE_LIMIT_STRATEGY`        | Algoritmo                                    | `fixed-window`, `moving-window`, `sliding-window-counter`   | `fixed-window`  |
| `API_RATE_LIMIT_KEY`             | Selector de clave                            | `ip`, `header:<Name>`                                       | `ip`            |
| `API_RATE_LIMIT_EXEMPT_IPS`      | Saltar límites para estas IPs/CIDRs          | Separadas por espacio/coma                                  | unset           |
| `API_RATE_LIMIT_STORAGE_OPTIONS` | JSON mezclado en la config de almacenamiento | Cadena JSON                                                 | unset           |

#### Redis/Valkey (para rate limits)

| Setting                                              | Descripción             | Valores aceptados                | Predeterminado        |
| ---------------------------------------------------- | ---------------------- | -------------------------------- | --------------------- |
| `USE_REDIS`                                          | Habilitar backend Redis | `yes/no/on/off/true/false/0/1`   | `no`                  |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DATABASE`         | Detalles de conexión   | Host, int, int                   | unset, `6379`, `0`    |
| `REDIS_USERNAME`, `REDIS_PASSWORD`                   | Auth                   | Cadenas                          | unset                 |
| `REDIS_SSL`, `REDIS_SSL_VERIFY`                      | TLS y verificación     | `yes/no/on/off/true/false/0/1`   | `no`, `yes`           |
| `REDIS_TIMEOUT`                                      | Timeout (ms)           | Entero                           | `1000`                |
| `REDIS_KEEPALIVE_POOL`                               | Keepalive de pool      | Entero                           | `10`                  |
| `REDIS_SENTINEL_HOSTS`                               | Hosts de Sentinel      | `host:port` separados por espacio | unset                 |
| `REDIS_SENTINEL_MASTER`                              | Nombre de maestro      | Cadena                           | unset                 |
| `REDIS_SENTINEL_USERNAME`, `REDIS_SENTINEL_PASSWORD` | Auth de Sentinel       | Cadenas                          | unset                 |

!!! info "Redis de la BD"
    Si la config de la base de datos de BunkerWeb incluye Redis/Valkey, la API la reutiliza automáticamente para rate limiting incluso sin `USE_REDIS` en el entorno. Sobrescribe con variables de entorno cuando necesites otro backend.

#### Listener y TLS

| Setting                               | Descripción                       | Valores aceptados                | Predeterminado                          |
| ------------------------------------- | --------------------------------- | -------------------------------- | --------------------------------------- |
| `API_LISTEN_ADDR`, `API_LISTEN_PORT`  | Dirección/puerto de Gunicorn      | IP o hostname, int               | `127.0.0.1`, `8888` (script de paquete) |
| `API_SSL_ENABLED`                     | Activar TLS en la API             | `yes/no/on/off/true/false/0/1`   | `no`                                    |
| `API_SSL_CERTFILE`, `API_SSL_KEYFILE` | Rutas de cert y clave PEM         | Rutas de archivo                 | unset                                   |
| `API_SSL_CA_CERTS`                    | CA/cadena opcional                | Ruta de archivo                  | unset                                   |

#### Logging y runtime (defaults de paquete)

| Setting                         | Descripción                                                                       | Valores aceptados                                 | Predeterminado                                                         |
| ------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Nivel base / override                                                              | `debug`, `info`, `warning`, `error`, `critical`   | `info`                                                                |
| `LOG_TYPES`                     | Destinos                                                                          | `stderr`/`file`/`syslog` separados por espacio     | `stderr`                                                              |
| `LOG_FILE_PATH`                 | Ubicación del log (si `LOG_TYPES` incluye `file` o `CAPTURE_OUTPUT=yes`)           | Ruta de archivo                                   | `/var/log/bunkerweb/api.log` si file/capture, si no unset              |
| `LOG_SYSLOG_ADDRESS`            | Destino syslog (`udp://host:514`, `tcp://host:514`, socket)                        | Host:puerto, host con prefijo proto o ruta socket | unset                                                                 |
| `LOG_SYSLOG_TAG`                | Tag de syslog                                                                     | Cadena                                           | `bw-api`                                                              |
| `MAX_WORKERS`, `MAX_THREADS`    | Workers/hilos de Gunicorn                                                         | Entero o unset para auto                         | unset                                                                 |
| `CAPTURE_OUTPUT`                | Capturar stdout/stderr de Gunicorn hacia los handlers configurados                | `yes` o `no`                                     | `no`                                                                  |

## Superficie de la API (mapa de capacidades)

- **Core**
  - `GET /ping`, `GET /health`: checks de vida de la propia API.
- **Auth**
  - `POST /auth`: emite tokens Biscuit; acepta Basic, formulario, JSON o Bearer de override cuando `API_TOKEN` coincide.
- **Instances**
  - `GET /instances`: lista instancias con metadata de creación/último seen.
  - `POST /instances`: registra una instancia (hostname/port/server_name/method).
  - `GET/PATCH/DELETE /instances/{hostname}`: inspeccionar, actualizar campos mutables o borrar instancias gestionadas por la API.
  - `DELETE /instances`: borrar en masa instancias gestionadas por la API; las ajenas se omiten.
  - Salud/acciones: `GET /instances/ping`, `GET /instances/{hostname}/ping`, `POST /instances/reload?test=yes|no`, `POST /instances/{hostname}/reload`, `POST /instances/stop`, `POST /instances/{hostname}/stop`.
- **Global settings**
  - `GET /global_settings`: por defecto solo no-defaults; añade `full=true` para todos los ajustes, `methods=true` para incluir procedencia.
  - `PATCH /global_settings`: upsert de globals propiedad de la API; claves de solo lectura se rechazan.
- **Services**
  - `GET /services`: lista servicios (incluye borradores por defecto).
  - `GET /services/{service}`: obtiene no-defaults o config completa (`full=true`); `methods=true` incluye procedencia.
  - `POST /services`: crea un servicio (draft u online), define variables y actualiza `SERVER_NAME` de forma atómica.
  - `PATCH /services/{service}`: renombrar, actualizar variables, alternar draft.
  - `DELETE /services/{service}`: eliminar servicio y claves derivadas de config.
  - `POST /services/{service}/convert?convert_to=online|draft`: cambiar rápido entre draft/online.
- **Custom configs**
  - `GET /configs`: lista snippets (servicio por defecto `global`); `with_data=true` incrusta contenido imprimible.
  - `POST /configs`, `POST /configs/upload`: crea snippets vía JSON o subida de archivo.
  - `GET /configs/{service}/{type}/{name}`: obtiene snippet; `with_data=true` para el contenido.
  - `PATCH /configs/{service}/{type}/{name}`, `PATCH .../upload`: actualizar o mover snippets gestionados por la API.
  - `DELETE /configs` o `DELETE /configs/{service}/{type}/{name}`: eliminar snippets gestionados por la API; los gestionados por plantillas se omiten.
  - Tipos soportados: `http`, `server_http`, `default_server_http`, `modsec`, `modsec_crs`, `stream`, `server_stream`, hooks de CRS/plug-in.
- **Bans**
  - `GET /bans`: agrega bans activos desde las instancias.
  - `POST /bans` o `/bans/ban`: aplica uno o varios bans; payload puede ser objeto, array o JSON como string.
  - `POST /bans/unban` o `DELETE /bans`: eliminar bans globalmente o por servicio.
- **Plugins (UI)**
  - `GET /plugins`: lista plugins; `with_data=true` incluye los bytes del paquete cuando están disponibles.
  - `POST /plugins/upload`: instala plugins de UI desde `.zip`, `.tar.gz`, `.tar.xz`.
  - `DELETE /plugins/{id}`: elimina un plugin por ID.
- **Cache (artefactos de jobs)**
  - `GET /cache`: lista archivos de caché con filtros (`service`, `plugin`, `job_name`); `with_data=true` incrusta contenido imprimible.
  - `GET /cache/{service}/{plugin}/{job}/{file}`: obtiene/descarga un archivo de caché específico (`download=true`).
  - `DELETE /cache` o `DELETE /cache/{service}/{plugin}/{job}/{file}`: borra archivos de caché y notifica al scheduler.
- **Jobs**
  - `GET /jobs`: lista jobs, horarios y resúmenes de caché.
  - `POST /jobs/run`: marca plugins como cambiados para disparar los jobs asociados.

## Comportamiento operativo

- Respuestas de error normalizadas a `{"status": "error", "message": "..."}` con códigos HTTP adecuados.
- Las operaciones de escritura se persisten en la base de datos compartida; las instancias consumen cambios vía sincronización del scheduler o tras un reload.
- `API_ROOT_PATH` debe coincidir con la ruta del reverse proxy para que `/docs` y enlaces funcionen.
- El arranque falla si no existe un camino de autenticación (sin claves Biscuit, sin usuario admin y sin `API_TOKEN`); los errores se registran en `/var/tmp/bunkerweb/api.error`.
