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
- Ámbitos de ACL: los permisos de **escritura** de config, service, plugin y global settings son equivalentes a admin (su contenido se renderiza tal cual como NGINX/Lua, es decir, ejecución de código): concédelos solo a usuarios de plena confianza. `instances_create` e `instances_update` también lo son, por otra vía: las llamadas a una instancia registrada llevan el override de admin `API_TOKEN`, y el scheduler envía la configuración generada y la caché (claves privadas TLS incluidas) a cada instancia registrada. Ver [Permisos y ACL](#permisos-y-acl).
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
        image: bunkerity/bunkerweb:1.7.0-beta
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
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
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
        image: bunkerity/bunkerweb-api:1.7.0-beta
        environment:
          <<: *bw-env
          API_USERNAME: "admin"
          API_PASSWORD: "Str0ng&P@ss!"
          # API_TOKEN: "admin-override-token" # opcional
          FORWARDED_ALLOW_IPS: "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16" # Cuidado: solo úsalo si el reverse proxy es la única vía
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
          --maxmemory-policy volatile-lru
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
      bunkerity/bunkerweb-all-in-one:1.7.0-beta
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
- Tipos de recurso: `instances`, `global_config`, `services`, `configs`, `plugins`, `cache`, `bans`, `jobs`.
- Nombres de permisos:
  - `instances_*`: `instances_read`, `instances_update`, `instances_delete`, `instances_create`, `instances_execute`
  - `global_config_*`: `global_config_read`, `global_config_update`
  - `services`: `service_read`, `service_create`, `service_update`, `service_delete`, `service_convert`, `service_export`
  - `configs`: `configs_read`, `config_read`, `config_create`, `config_update`, `config_delete`
  - `plugins`: `plugin_read`, `plugin_create`, `plugin_delete`
  - `cache`: `cache_read`, `cache_delete`
  - `bans`: `ban_read`, `ban_update`, `ban_delete`, `ban_created`
  - `jobs`: `job_read`, `job_run`
- `resource_id` suele ser el segundo componente del path (ej. `/services/{id}`); "*" da acceso global.
- Inicializa usuarios no admin y permisos con `API_ACL_BOOTSTRAP_FILE` o un `/var/lib/bunkerweb/api_acl_bootstrap.json` montado. Cada usuario admite una `password` en texto plano o un `password_hash`/`password_bcrypt` pre-hasheado (ver el consejo a continuación).

!!! danger "Estos permisos de escritura equivalen a acceso de administrador"
    Las configuraciones personalizadas, variables de servicio (como `REVERSE_PROXY_URL`), plugins
    y ajustes globales se generan **literalmente** como configuración NGINX/OpenResty Lua que
    ejecutan los workers y el scheduler. Un token con estos permisos puede ejecutar código como
    el usuario del proceso BunkerWeb. Los permisos de escritura de instancias también equivalen
    a administrador: cada llamada lleva el `API_TOKEN` administrativo y el scheduler envía a toda
    instancia registrada la configuración y caché, incluidas claves privadas TLS. Registrar un
    endpoint permite recibir todo ello:

    - `instances`: `instances_create`, `instances_update`
    - `configs`: `config_create`, `config_update`, `config_delete` (y `POST /configs/upload`)
    - `services`: `service_create`, `service_update`, `service_convert`
    - `plugins`: `plugin_create`
    - `global_config`: `global_config_update`

    **Nunca los concedas a alguien a quien no confiarías acceso de administrador.** Reserva
    ámbitos de lectura (`*_read`, `service_export`, `cache_read`, …) para tokens limitados o de
    automatización. Conceder estos permisos a un usuario no administrador registra una advertencia.

!!! tip "Contraseñas de arranque pre-hasheadas"
    Reemplaza la `password` en texto plano de un usuario por un **hash bcrypt** mediante `password_hash` (o `password_bcrypt`) para que las credenciales nunca queden en el archivo como texto plano. El hash debe ser un hash bcrypt válido (`$2a$`/`$2b$`/`$2y$`) cuyo factor de coste sea al menos `10` (se recomienda `12`+). Un hash malformado o demasiado débil se **ignora**: el cargador recurre a la `password` en texto plano del usuario si existe; de lo contrario, un usuario nuevo recibe una contraseña aleatoria segura que no conocerás, y un usuario existente conserva la suya actual. Una `password` en texto plano se somete a una comprobación de robustez (8+ caracteres con mayúsculas/minúsculas/dígito/carácter especial). La variable de entorno `API_PASSWORD` del admin solo acepta texto plano — el pre-hasheo se aplica a estos usuarios de la ACL.

    Genera un hash:

    ```bash
    python3 -c "import bcrypt; print(bcrypt.hashpw(b'Str0ng&P@ss!', bcrypt.gensalt(rounds=13)).decode())"
    ```

    Luego úsalo en el archivo de arranque en lugar de `password`:

    ```json
    "password_hash": "$2b$13$replace-with-the-hash-printed-above"
    ```

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

!!! warning "El ejemplo anterior concede un permiso equivalente a administrador"
    `config_update` permite ejecutar código; el usuario `ci` tiene poder de administrador para
    escribir configuración. Emite ese token solo para automatizaciones de plena confianza. Para
    solo lectura, quita `config_update` y conserva los ámbitos `*_read`.

## Credenciales por instancia y fijación TLS

Cada registro de instancia puede sustituir el `API_TOKEN` global usado para las llamadas del plano de control. Define `credential` en `POST /instances` o `PATCH /instances/{hostname}`. La API lo almacena con el llavero AES-256-GCM compartido y nunca devuelve el texto en claro: `GET /instances` solo expone `credential_set` y `credential_updated_at`. La credencial por instancia tiene prioridad en el fan-out de la API, las acciones de los Workers, los envíos de configuración y caché, y el `API_TOKEN` escrito en la configuración generada para esa instancia. Envía un `credential` vacío en un PATCH para volver al token global.

Las integraciones automatizadas pueden declarar los mismos campos con variables de entorno agrupadas. Inicia un grupo con `BUNKERWEB_INSTANCE_HOST` y usa `BUNKERWEB_INSTANCE_API_TOKEN`, `BUNKERWEB_INSTANCE_LISTEN_HTTPS`, `BUNKERWEB_INSTANCE_HTTPS_PORT`, `BUNKERWEB_INSTANCE_SERVER_NAME`, `BUNKERWEB_INSTANCE_TLS_MODE` y `BUNKERWEB_INSTANCE_TLS_FINGERPRINT`. Añade el mismo sufijo numérico a todas las claves para más instancias, por ejemplo `_1` y `_2`. La lista anterior `BUNKERWEB_INSTANCES` sigue usando los ajustes globales de la API para todos los hosts.

La confianza TLS también se almacena por instancia:

- `tls_mode: "off"` conserva el comportamiento de compatibilidad. Una instancia con `listen_https: true` usa HTTPS sin verificar el certificado y reintenta por HTTP en claro después de un error de conexión TLS.
- `tls_mode: "pinned"` compara el certificado hoja con el resumen SHA-256 de `tls_fingerprint`. Se aceptan dos puntos y hexadecimales en mayúsculas, que se normalizan. Una huella ausente o distinta hace fallar la llamada, y BunkerWeb nunca rebaja esa instancia a HTTP.

!!! warning "La fijación es el único modo TLS verificado"
    No existe un modo de validación por CA para cada instancia. `off` no verifica el certificado, incluso cuando el endpoint usa HTTPS. `pinned` sobre un endpoint HTTP no tiene certificado que comprobar, así que úsalo con `listen_https: true`. Actualiza la huella almacenada cuando rote el certificado de la instancia o fallarán las llamadas del plano de control a esa instancia.

### Registro: alternativa a configurar `credential` manualmente {#enrollment-an-alternative-to-setting-credential-by-hand}

Una instancia registrada desde la interfaz, la API o el entorno (`method="manual"`) puede obtener
su credencial mediante un código de un solo uso. El operador emite el código con
`POST /instances/{hostname}/enroll`: solo se muestra una vez; `ttl_seconds` es opcional, con valor
predeterminado de 900 s y máximo de 3600 s. La instancia lo canjea al arrancar mediante
`POST /instances/enroll` (cuerpo `{hostname, code}`). Es la única ruta de este router sin guardia
de autenticación, porque todavía no existe una credencial: la protegen el uso único, el TTL, el
hash SHA-512 almacenado, el limitador compartido y la lista de IP permitidas de la API. Desde ese
momento la instancia guarda y acepta solo su propia credencial; el operador nunca necesita verla
ni definirla. `POST /instances/{hostname}/rotate`/`revoke` la rotan o revocan; una instancia revocada
se rechaza en el punto común de conexión de todas las llamadas del plano de control. Si pierde el
*archivo* persistente de credencial tras registrarse, se niega a arrancar en lugar de volver al
`API_TOKEN` global. Recrearla sin volumen de datos queda fuera de esa protección, porque también
se pierde el marcador de registro. El registro y una `credential` explícita son independientes:
usa lo que encaje con el aprovisionamiento de la instancia.

## Limitación de velocidad

Activa por defecto con dos cadenas: `API_RATE_LIMIT` (global, por defecto `100r/m`) y `API_RATE_LIMIT_AUTH` (por defecto `10r/m` u `off`). Acepta notación estilo NGINX (`3r/s`, `40r/m`, `200r/h`) o formas verbosas (`100/minute`, `200 per 30 minutes`). Configura mediante:

- `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`
- `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_HEADERS_ENABLED`
- `API_RATE_LIMIT_RULES` (cadena CSV/JSON/YAML o ruta a archivo)
- `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`
- Almacenamiento en memoria o Redis/Valkey con `USE_REDIS=yes` más ajustes `REDIS_*` (Sentinel soportado).

Las solicitudes autenticadas con el `API_TOKEN` de administrador están exentas, sin importar los límites configurados. Ese token ya concede acceso administrativo completo. Los componentes de BunkerWeb (Web UI, Scheduler y Worker) lo usan desde la misma red, por lo que un límite por IP contaría todo el plano de control como un solo cliente. Un token Bearer distinto sigue limitado como cualquier otro cliente.

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

| Setting | Descripción                                                                                            | Valores aceptados                                | Predeterminado                                  |
| ------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------ | ----------------------------------------------- |
| `TZ`    | Zona horaria para logs de la API y claims basados en tiempo (p. ej. TTL de Biscuit y marcas de tiempo) | Nombre de base TZ (p. ej. `UTC`, `Europe/Paris`) | unset (default del contenedor, normalmente UTC) |

Desactiva docs o esquema poniendo sus URLs en `off|disabled|none|false|0`. Define `API_SSL_ENABLED=yes` con `API_SSL_CERTFILE` y `API_SSL_KEYFILE` para terminar TLS en la API. Con reverse proxy, define `API_FORWARDED_ALLOW_IPS` a las IPs del proxy para que Gunicorn confíe en los `X-Forwarded-*`.

### Referencia de configuración (power users)

#### Superficie y docs

| Setting                                            | Descripción                                                                          | Valores aceptados             | Predeterminado                       |
| -------------------------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------- | ------------------------------------ |
| `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL` | Rutas para Swagger, ReDoc y OpenAPI; pon `off/disabled/none/false/0` para desactivar | Ruta o `off`                  | `/docs`, `/redoc`, `/openapi.json`   |
| `API_ROOT_PATH`                                    | Prefijo de montaje al usar reverse proxy                                             | Ruta (ej. `/api`)             | vacío                                |
| `API_FORWARDED_ALLOW_IPS`                          | IPs de proxy confiables para `X-Forwarded-*`                                         | IPs/CIDRs separadas por comas | `127.0.0.1,::1` (default de paquete) |
| `API_PROXY_ALLOW_IPS`                              | IPs de proxy confiables para el protocolo PROXY                                      | IPs/CIDRs separadas por comas | `FORWARDED_ALLOW_IPS`                |

#### Auth, ACL, Biscuit

| Setting                                     | Descripción                                    | Valores aceptados                                          | Predeterminado             |
| ------------------------------------------- | ---------------------------------------------- | ---------------------------------------------------------- | -------------------------- |
| `API_USERNAME`, `API_PASSWORD`              | Usuario admin inicial                          | Strings; contraseña fuerte requerida fuera de debug        | unset                      |
| `OVERRIDE_API_CREDS`                        | Reaplicar credenciales admin al arranque       | `yes/no/on/off/true/false/0/1`                             | `no`                       |
| `API_TOKEN`                                 | Bearer de override admin                       | Cadena opaca                                               | unset                      |
| `API_ACL_BOOTSTRAP_FILE`                    | Ruta JSON para usuarios/permisos               | Ruta o `/var/lib/bunkerweb/api_acl_bootstrap.json` montado | unset                      |
| `BISCUIT_PRIVATE_KEY`, `BISCUIT_PUBLIC_KEY` | Claves Biscuit (hex) si no se usan archivos    | Cadenas hex                                                | auto-generadas/persistidas |
| `API_BISCUIT_TTL_SECONDS`                   | Vida del token; `0/off` desactiva expiración   | Entero en segundos o `off/disabled`                        | `3600`                     |
| `CHECK_PRIVATE_IP`                          | Liga Biscuit a la IP cliente (excepto privada) | `yes/no/on/off/true/false/0/1`                             | `yes`                      |

#### Allowlist

| Setting                 | Descripción                          | Valores aceptados              | Predeterminado           |
| ----------------------- | ------------------------------------ | ------------------------------ | ------------------------ |
| `API_WHITELIST_ENABLED` | Alternar middleware de lista blanca  | `yes/no/on/off/true/false/0/1` | `yes`                    |
| `API_WHITELIST_IPS`     | IPs/CIDRs separadas por espacio/coma | IPs/CIDRs                      | Rangos RFC1918 en código |

#### Limitación

| Setting                          | Descripción                                  | Valores aceptados                                         | Predeterminado |
| -------------------------------- | -------------------------------------------- | --------------------------------------------------------- | -------------- |
| `API_RATE_LIMIT`                 | Límite global (cadena estilo NGINX)          | `3r/s`, `100/minute`, `500 per 30 minutes`                | `100r/m`       |
| `API_RATE_LIMIT_AUTH`            | Límite de `/auth` (o `off`)                  | igual que arriba o `off/disabled/none/false/0`            | `10r/m`        |
| `API_RATE_LIMIT_ENABLED`         | Activar limitador                            | `yes/no/on/off/true/false/0/1`                            | `yes`          |
| `API_RATE_LIMIT_HEADERS_ENABLED` | Inyectar headers de límite                   | igual que arriba                                          | `yes`          |
| `API_RATE_LIMIT_RULES`           | Reglas por ruta (CSV/JSON/YAML o ruta)       | Cadena o ruta                                             | unset          |
| `API_RATE_LIMIT_STRATEGY`        | Algoritmo                                    | `fixed-window`, `moving-window`, `sliding-window-counter` | `fixed-window` |
| `API_RATE_LIMIT_KEY`             | Selector de clave                            | `ip`, `header:<Name>`                                     | `ip`           |
| `API_RATE_LIMIT_EXEMPT_IPS`      | Saltar límites para estas IPs/CIDRs (además del `API_TOKEN` de administrador, siempre exento) | Separadas por espacio/coma                                | unset          |
| `API_RATE_LIMIT_STORAGE_OPTIONS` | JSON mezclado en la config de almacenamiento | Cadena JSON                                               | unset          |

#### Redis/Valkey (para rate limits)

| Setting                                              | Descripción             | Valores aceptados                 | Predeterminado     |
| ---------------------------------------------------- | ----------------------- | --------------------------------- | ------------------ |
| `USE_REDIS`                                          | Habilitar backend Redis | `yes/no/on/off/true/false/0/1`    | `no`               |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DATABASE`         | Detalles de conexión    | Host, int, int                    | unset, `6379`, `0` |
| `REDIS_USERNAME`, `REDIS_PASSWORD`                   | Auth                    | Cadenas                           | unset              |
| `REDIS_SSL`, `REDIS_SSL_VERIFY`                      | TLS y verificación      | `yes/no/on/off/true/false/0/1`    | `no`, `yes`        |
| `REDIS_TIMEOUT`                                      | Timeout (ms)            | Entero                            | `1000`             |
| `REDIS_KEEPALIVE_POOL`                               | Keepalive de pool       | Entero                            | `10`               |
| `REDIS_SENTINEL_HOSTS`                               | Hosts de Sentinel       | `host:port` separados por espacio | unset              |
| `REDIS_SENTINEL_MASTER`                              | Nombre de maestro       | Cadena                            | unset              |
| `REDIS_SENTINEL_USERNAME`, `REDIS_SENTINEL_PASSWORD` | Auth de Sentinel        | Cadenas                           | unset              |

!!! info "Redis de la BD"
    Si la config de la base de datos de BunkerWeb incluye Redis/Valkey, la API la reutiliza automáticamente para rate limiting incluso sin `USE_REDIS` en el entorno. Sobrescribe con variables de entorno cuando necesites otro backend.

!!! warning "Sin Redis, el límite se aplica por Worker"
    El almacenamiento de respaldo vive en la memoria de proceso de cada Worker de Gunicorn. Cada Worker aplica el límite configurado por separado: con `MAX_WORKERS=4` y `API_RATE_LIMIT_AUTH=10r/m`, un cliente repartido entre los Workers puede obtener hasta 40 intentos por minuto. Usa Redis/Valkey o un solo Worker cuando el límite sea un control de seguridad.

#### Listener y TLS

| Setting                               | Descripción                  | Valores aceptados              | Predeterminado                          |
| ------------------------------------- | ---------------------------- | ------------------------------ | --------------------------------------- |
| `API_LISTEN_ADDR`, `API_LISTEN_PORT`  | Dirección/puerto de Gunicorn | IP o hostname, int             | `127.0.0.1`, `8888` (script de paquete) |
| `API_SSL_ENABLED`                     | Activar TLS en la API        | `yes/no/on/off/true/false/0/1` | `no`                                    |
| `API_SSL_CERTFILE`, `API_SSL_KEYFILE` | Rutas de cert y clave PEM    | Rutas de archivo               | unset                                   |
| `API_SSL_CA_CERTS`                    | CA/cadena opcional           | Ruta de archivo                | unset                                   |

#### Logging y runtime (defaults de paquete)

| Setting                         | Descripción                                                                   | Valores aceptados                                 | Predeterminado                                            |
| ------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Nivel base / override                                                         | `debug`, `info`, `warning`, `error`, `critical`   | `info`                                                    |
| `LOG_TYPES`                     | Destinos                                                                      | `stderr`/`file`/`syslog` separados por espacio    | `stderr`                                                  |
| `LOG_FILE_PATH`                 | Ubicación del log (si `LOG_TYPES` incluye `file` o `CAPTURE_OUTPUT=yes`)      | Ruta de archivo                                   | `/var/log/bunkerweb/api.log` si file/capture, si no unset |
| `LOG_SYSLOG_ADDRESS`            | Destino syslog (`udp://host:514`, `tcp://host:514`, socket)                   | Host:puerto, host con prefijo proto o ruta socket | unset                                                     |
| `LOG_SYSLOG_TAG`                | Tag de syslog                                                                 | Cadena                                            | `bw-api`                                                  |
| `MAX_WORKERS`, `MAX_THREADS`    | Workers/hilos de Gunicorn                                                     | Entero o unset para auto                          | unset                                                     |
| `MAX_REQUESTS`                  | Solicitudes antes de reciclar el worker Gunicorn (previene exceso de memoria) | Entero                                            | `1000`                                                    |
| `CAPTURE_OUTPUT`                | Capturar stdout/stderr de Gunicorn hacia los handlers configurados            | `yes` o `no`                                      | `no`                                                      |

## Superficie de la API (mapa de capacidades) {#api-surface-capability-map}

- **Core**
  - `GET /ping`, `GET /health`: checks de vida de la propia API.
- **Auth**
  - `POST /auth`: emite tokens Biscuit; acepta Basic, formulario, JSON o Bearer de override cuando `API_TOKEN` coincide.
- **Instances**
  - `GET /instances`: lista instancias con metadata de creación/último seen.
  - `POST /instances`: registra una instancia (hostname/port/server_name/method).
  - `GET/PATCH/DELETE /instances/{hostname}`: inspeccionar, actualizar campos mutables o borrar instancias gestionadas por la API.
  - `DELETE /instances`: borrar en masa instancias gestionadas por la API; las ajenas se omiten.
  - `PUT /instances/bulk`: reconcilia instancias en bloque por `method` (autoconf). Rechaza `method="ui"` y `method="manual"`, que eliminarían y recrearían las filas registradas y borrarían sus credenciales.
  - Registro: `POST /instances/{hostname}/enroll` requiere `instances_enroll` y emite un código de uso único y duración limitada, mostrado una vez, con `ttl_seconds` opcional. `POST /instances/enroll`, cuerpo `{hostname, code}`, es la única ruta sin `Depends(guard)`; la instancia lo canjea para recibir su credencial. La protegen el uso único, TTL y hash del código, además del limitador compartido y la lista de IP permitidas. Después solo acepta su credencial, nunca el `API_TOKEN` global. `POST /instances/{hostname}/rotate` y `POST /instances/{hostname}/revoke` requieren `instances_rotate`: la rotación tiene dos fases y responde `502` si la instancia no es accesible; las conexiones posteriores a una instancia revocada se rechazan.
  - `PATCH /instances/{hostname}/status`: establece directamente el estado `up`/`down`/`failover` (usado por el bucle de salud del scheduler).
  - Salud/acciones: `GET /instances/ping`, `GET /instances/{hostname}/ping`, `GET /instances/{hostname}/health`, `POST /instances/reload?test=yes|no`, `POST /instances/{hostname}/reload`, `POST /instances/stop`, `POST /instances/{hostname}/stop`.
  - `GET /instances/{hostname}/health` transmite el estado de la instancia: `ok`, `loading` o `reloading`. `ping` solo responde si es accesible. Tras reiniciarse, una instancia permanece en `loading` hasta recibir una configuración; sus plugins temporizados están desactivados en ese estado. El Scheduler usa esta información para decidir si debe reenviar la configuración. Ambas rutas requieren `instances_read`.
  - Un reload contra una instancia ocupada se reintenta en lugar de reportarse como fallido, así que la latencia en el peor caso de `POST /instances/{hostname}/reload` (y del `POST /instances/reload` para toda la flota) es de ~54s, no los ~35s que sugeriría un lock de duración fija — un llamador con un timeout más corto puede ver uno reportado como fallido cuando solo es lento.
- **Global settings**
  - `GET /global_settings`: por defecto solo no-defaults; añade `full=true` para todos los ajustes, `methods=true` para incluir procedencia.
  - `PATCH /global_settings`: upsert de globals propiedad de la API; las claves de solo lectura se rechazan. Un ajuste propiedad de otra fuente (`scheduler`, es decir, una variable de entorno, además de `autoconf`, `manual` o `wizard`) no puede transferirse a la API: se rechaza toda la carga con `409`, indicando cada clave y su propietario. Reenviar el valor que ya tiene una clave ajena no crea un conflicto.
  - `GET /global_config`, `PATCH /global_config`: alias de `GET`/`PATCH /global_settings` por compatibilidad.
  - `POST /global_settings/validate`: valida un nombre de ajuste y, opcionalmente, un valor con `is_valid_setting`, sin guardar nada.
  - `PUT /global_settings/config`: sustituye el entorno completo de configuración (autoconf y el editor de configuración de la interfaz). El payload ES todo el estado deseado: se elimina cada clave dentro de su ámbito que no aparezca. Rechaza con `400` una configuración que deje sin ruta el desafío http-01 de un servicio, salvo con `method="autoconf"`, donde registra el conflicto y guarda igualmente para no dejar sin configurar al resto de la flota.
- **Services**
  - `GET /services`: lista servicios (incluye borradores por defecto).
  - `GET /services/{service}`: obtiene no-defaults o config completa (`full=true`); `methods=true` incluye procedencia.
  - `POST /services`: crea un servicio (draft u online), define variables y actualiza `SERVER_NAME` de forma atómica.
  - `PATCH /services/{service}`: renombrar, actualizar variables, alternar draft.
  - `DELETE /services/{service}`: eliminar servicio y claves derivadas de config.
  - `POST /services/{service}/convert?convert_to=online|draft&mode=standard|redirect_only`: cambia draft/online y/o declara el modo del servicio — los dos ejes son independientes, se requiere al menos uno, y una llamada sin ninguno de los dos responde `400` (antes `422`, cuando `convert_to` era un parámetro obligatorio). `mode=redirect_only` responde `409` con un array `reasons` cuando el servicio todavía tiene algo que la lista de permitidos redirect-only prohíbe; `mode=standard` siempre se acepta. Se rechaza con `403` para el `default-server` reservado, como cualquier otra conversión sobre él.
  - `GET /services/redirect-candidates` (requiere `service_read`): cada servicio no borrador, salvo el `default-server` reservado, que todavía no está declarado `redirect_only`, con `would_qualify` y `blocking_reasons` (vacío si califica), como `{"status": "success", "candidates": [{"service": ..., "would_qualify": ..., "blocking_reasons": [...]}]}`. Solo lectura: no cambia nada y no factura nada.
  - El servicio reservado `default-server` aparece en `GET /services` con `reserved: true` **solo con `MULTISITE=yes`**; con `MULTISITE=no` no existe esa fila y el servidor predeterminado se comporta como en 1.6. Responde a peticiones sin servicio coincidente (hostname desconocido o IP directa) y permite configurar su certificado, TLS, cabeceras y páginas de error. Es permanente: crearlo con `POST /services`, borrarlo con `DELETE /services/default-server`, renombrarlo o renombrar otro servicio hacia él, pasarlo a borrador por `PATCH` o con `POST /services/default-server/convert?convert_to=draft` devuelve `403` con la explicación. Configúralo con `PATCH /services/default-server` y `variables`; nunca cuenta para la cuota PRO. Dos claves de `variables` se rechazan con `400`: `SERVER_TYPE`, incluso si coincide con el almacenado (no tiene un bloque `server{}` de ningún tipo para cambiar; los clientes que leen y reenvían deben quitarla), y cualquier entrada de `DEFAULT_SERVER_STREAM_PORTS_SSL` ausente de `DEFAULT_SERVER_STREAM_PORTS`.
- **Custom configs**
  - `GET /configs`: lista snippets (servicio por defecto `global`); `with_data=true` incrusta contenido imprimible.
  - `POST /configs`, `POST /configs/upload`: crea snippets vía JSON o subida de archivo.
  - `GET /configs/{service}/{type}/{name}`: obtiene snippet; `with_data=true` para el contenido.
  - `PATCH /configs/{service}/{type}/{name}`, `PATCH .../upload`: actualizar o mover snippets gestionados por la API.
  - `DELETE /configs` o `DELETE /configs/{service}/{type}/{name}`: eliminar snippets gestionados por la API; los gestionados por plantillas se omiten.
  - `PUT /configs/bulk`: sustituye todas las configuraciones personalizadas con una etiqueta `method` dada (sincronización de autoconf). Un aviso sin fallo real, con filas ya guardadas, responde `200`; un rechazo real responde `400`, nunca `500`, porque el cliente HTTP descarta el cuerpo de un `5xx`.
  - Tipos soportados: `http`, `server_http`, `default_server_http`, `modsec`, `modsec_crs`, `stream`, `server_stream`, hooks de CRS/plug-in.
- **Bans**
  - `GET /bans`: lista los bans activos de la base de datos (la lista duradera). **Cambio en 1.7**: antes agregaba los bans en memoria de las instancias, lo que omitía entradas después de un reinicio.
  - `GET /bans/instances`: conserva el comportamiento anterior en un endpoint propio y muestra lo que aplica cada instancia en ese momento.
  - `GET /bans/timeseries?start=...&end=...&bucket=hour`: ocupación de bloqueos activos por intervalo en `[start, end)`. `bw_bans` conserva una fila por `(ip, ban_scope, service_id)` y volver a bloquear reescribe `created_at`: mide ocupación en el tiempo, no un historial de eventos o creaciones.
  - `POST /bans` o `/bans/ban`: aplica uno o varios bans; la carga puede ser un objeto, un array o JSON como string. El ban se guarda y después se envía a las instancias.
  - `POST /bans/unban` o `DELETE /bans`: elimina bans globalmente o por servicio. Se rechaza una revocación que no pueda guardarse, ya que una instancia que no la recibió podría volver a enseñar el ban a la flota.
- **Plugins (UI)**
  - `GET /plugins`: lista plugins; `with_data=true` incluye los bytes del paquete cuando están disponibles.
  - `POST /plugins/upload`: instala plugins de UI desde `.zip`, `.tar.gz`, `.tar.xz`.
  - `PUT /plugins/external`: sustituye en bloque plugins externos/PRO en la base de datos (`delete_missing` elimina los omitidos); los archivos viajan en base64 sobre JSON.
  - `DELETE /plugins/{id}`: elimina un plugin por ID.
  - `GET /plugins/{id}/page`: datos de la página del plugin como `tar.gz`; `404` si no existe.
  - `GET /plugins/{id}/icon`: archivo de icono del plugin; solo lo tiene un marcador `@file/<name>`. Un nombre de recurso estático, una clase boxicon o la ausencia de icono devuelve `404`. Se sirve con `Content-Security-Policy: default-src 'none'; sandbox`, `X-Content-Type-Options: nosniff` y `Content-Disposition: inline` entrecomillado para impedir que un SVG ejecute scripts al abrirse directamente. Los archivos mayores de 512 KB devuelven `413`.
- **Cache (artefactos de jobs)**
  - `GET /cache`: lista archivos de caché con filtros (`service`, `plugin`, `job_name`); `with_data=true` incrusta contenido imprimible.
  - `GET /cache/{service}/{plugin}/{job}/{file}`: obtiene/descarga un archivo de caché específico (`download=true`).
  - `DELETE /cache` o `DELETE /cache/{service}/{plugin}/{job}/{file}`: borra archivos de caché y notifica al scheduler.
- **Jobs**
  - `GET /jobs`: lista jobs, horarios y resúmenes de caché.
  - `GET /jobs/{name}/last-run`: última ejecución persistida de un job.
  - `POST /jobs/run`: marca plugins como cambiados para disparar los jobs asociados.

  - `POST /jobs/dispatch`: envía jobs directamente a los workers Celery, sin pasar por el disparador del scheduler; devuelve `503` si no hay broker configurado. El `run_id` de cada job es un token de correlación que aparece al inicio de sus líneas de log, no un identificador consultable. No hay endpoint de resultados de los jobs enviados porque no se usa backend de resultados Celery.
  - `GET /jobs/queue`: estado actual de las colas Celery (`503` sin broker).
- **Caché web**
  - `GET /web-cache/status`, `GET /web-cache/metrics`: estado y métricas de caché del proxy inverso por servicio.
  - `POST /web-cache/purge`: purga una URL o toda la caché de un servicio.
- **Sistema**
  - `GET /system/readonly`: indica si la base de datos está en solo lectura/failover.
  - `POST /system/checked-changes`: confirma indicadores de cambios procesados.
- **Usuarios** (cuentas de la interfaz, no clientes de la API)
  - `GET/POST /users`, `GET/PATCH /users/{username}`: gestión de cuentas.
  - `GET/DELETE /users/{username}/sessions`, `POST /users/{username}/login`: listado/revocación de sesiones e inicio de sesión.
  - `POST /users/{username}/recovery-codes/refresh|use`: códigos de recuperación TOTP.
  - `POST /users/{username}/totp/use`: consume un contador TOTP una sola vez para impedir repetir el código en otro worker de interfaz. Un rechazo es la defensa contra repetición, no un error: se distingue de una caída mediante `consumed: false` en la respuesta `200`.
  - `GET/POST /users/{username}/webauthn-credentials`, `GET /users/webauthn-credentials/{id}`, `PATCH/DELETE /users/{username}/webauthn-credentials/{id}`: credenciales passkey/WebAuthn.
  - `GET/PATCH /users/{username}/preferences/{key}`, `POST /users/{username}/access`, `GET /users/{username}/permissions`: preferencias clave-valor por usuario e introspección de ACL.
- **Plantillas**
  - `GET /templates`, `GET /templates/{id}`: lista u obtiene una plantilla reutilizable.
  - `POST /templates`, `PATCH /templates/{id}`, `DELETE /templates/{id}`: crea, modifica o elimina una plantilla.
- **Grupos de recursos**
  - `GET /resource_groups`, `GET /resource_groups/{id}`, `GET /resource_groups/{id}/references`: lista u obtiene un alias reutilizable de recursos tipados y consulta sus referencias antes de eliminarlo.
  - `POST /resource_groups`, `PATCH /resource_groups/{id}`, `DELETE /resource_groups/{id}`, `POST /resource_groups/{id}/clone`: gestión de grupos.
- **Metadatos**
  - `GET /metadata`, `PATCH /metadata`: licencia PRO e indicadores del scheduler. No permite sobrescribir el anillo de claves de cifrado de certificados/credenciales.
- **Certificados**
  - `GET /certificates`, `GET /certificates/sources`, `GET /certificates/{id}`, `GET /certificates/{id}/download`: inventario central y fuentes declaradas por los plugins.
  - `PATCH /certificates/{id}`, `POST /certificates/{id}/revoke`, `DELETE /certificates/{id}`: ciclo de vida del certificado.
  - `POST /certificates/{id}/attachments`, `DELETE /certificates/{id}/attachments/{service}`: adjunta o separa un certificado de un servicio.
- **Redirecciones** / **Upstreams** — recursos reutilizables y adjuntables
  - `GET/POST /redirects`, `GET/PATCH/DELETE /redirects/{id}`, `POST/DELETE /redirects/{id}/attachments[/{service}]`: reglas de redirección HTTP adjuntables a varios servicios.
  - `GET/POST /upstreams`, `GET/PATCH/DELETE /upstreams/{id}`, `POST/DELETE /upstreams/{id}/attachments[/{service}]`: pools HTTP, gRPC o stream, adjuntables a una ruta del proxy inverso o a un servicio stream completo.
- **Métricas**
  - `GET /metrics/timings`: tiempos agregados por plugin y fase entre instancias (`METRICS_COLLECT_TIMINGS`).
  - `GET /metrics/requests`, `GET /metrics/requests/timeseries`, `GET /metrics/requests/top-offenders`, `GET /metrics/requests/top-rules`: datos persistidos del panel Reports, filtrables por `protocol` (`http`, `tcp`, `udp`) y otras facetas.
  - `GET /metrics/threatmap`: flujo de tráfico bloqueado casi en tiempo real del mapa personal de amenazas.
- **Fuentes de certificados** (aportadas por plugins)
  - `GET /bunkernet/effectiveness`, `GET /bunkernet/stats`: eficacia y uso de la inteligencia comunitaria BunkerNet.
  - `POST /customcert/certificates/upload`: registra un certificado aportado por el operador.
  - `POST /letsencrypt/certificates`, `POST /letsencrypt/certificates/renew-due`, `GET /letsencrypt/certificates/orphans`: emisión, renovación en bloque de certificados próximos a vencer y listado de huérfanos.
  - `POST /selfsigned/certificates`, `POST /selfsigned/certificates/renew-due`, `POST /selfsigned/certificates/{certificate_id}/renew`: emisión, renovación en bloque o renovación por ID.
- **Workflows** (plugin montado en `/workflows`)
  - `GET /workflows`, `POST /workflows`, `GET/PATCH/DELETE /workflows/{id}`, `POST /workflows/{id}/clone`: cadenas de reglas condicionales de seguridad.
  - `GET/PUT /workflows/{id}/definition`: lee o sustituye la definición compilada de reglas.
  - `POST /workflows/validate`, `POST /workflows/{id}/test`: valida una definición o la prueba con una petición de ejemplo antes de guardar.
  - `POST /workflows/{id}/attachments`, `DELETE /workflows/{id}/attachments/{service}`: adjunta o separa un workflow de un servicio.

## Comportamiento operativo

- Respuestas de error normalizadas a `{"status": "error", "message": "..."}` con códigos HTTP adecuados.
- Las operaciones de escritura se persisten en la base de datos compartida; las instancias consumen cambios vía sincronización del scheduler o tras un reload.
- `API_ROOT_PATH` debe coincidir con la ruta del reverse proxy para que `/docs` y enlaces funcionen.
- El arranque falla si no existe un camino de autenticación (sin claves Biscuit, sin usuario admin y sin `API_TOKEN`); los errores se registran en `/var/tmp/bunkerweb/api.error`.
