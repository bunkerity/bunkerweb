# API

## Descripción general

La API de BunkerWeb es el plano de control utilizado para gestionar las instancias de BunkerWeb de forma programática: listar y gestionar instancias, recargar/detener, manejar baneos, plugins, trabajos, configuraciones y más. Expone una aplicación FastAPI documentada con autenticación fuerte, autorización y limitación de velocidad.

Abre la documentación interactiva en `/docs` (o `<root_path>/docs` si estableciste `API_ROOT_PATH`). El esquema OpenAPI está disponible en `/openapi.json`.

!!! warning "Seguridad"
    La API es un plano de control privilegiado. No la expongas en la Internet pública sin protecciones adicionales.

    Como mínimo, restringe las IP de origen (`API_WHITELIST_IPS`), habilita la autenticación (`API_TOKEN` o usuarios de API + Biscuit), y considera ponerla detrás de BunkerWeb con una ruta difícil de adivinar y controles de acceso adicionales.

## Requisitos previos

El servicio de la API requiere acceso a la base de datos de BunkerWeb (`DATABASE_URI`). Generalmente se despliega junto con el Programador y opcionalmente la Interfaz de Usuario Web. La configuración recomendada es ejecutar BunkerWeb al frente como un proxy inverso y aislar la API en una red interna.

Consulta el asistente de inicio rápido y la guía de arquitectura en la [guía de inicio rápido](quickstart-guide.md).

## Despliegue recomendado (Contenedores dedicados)

Para producción, despliega la API como su propio contenedor junto al plano de datos de BunkerWeb y el scheduler. Mantén la API unida a la red interna del plano de control y publícala únicamente a través de BunkerWeb como un proxy inverso. Esta disposición coincide con la [referencia de integración de Docker](integrations.md#networks) y garantiza que el scheduler, BunkerWeb y la API compartan la misma configuración.

```yaml
x-bw-env: &bw-env
  # Usamos un ancla para evitar repetir la misma configuración en ambos servicios
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Asegúrate de establecer el rango de IP correcto para que el scheduler pueda enviar la configuración a la instancia
  DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda usar una contraseña más fuerte para la base de datos

services:
  bunkerweb:
    # Este es el nombre que se usará para identificar la instancia en el Scheduler
    image: bunkerity/bunkerweb:1.6.6-rc3
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # Para compatibilidad con QUIC / HTTP3
    environment:
      <<: *bw-env # Usamos el ancla para evitar repetir la misma configuración en todos los servicios
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "bunkerweb" # Asegúrate de establecer el nombre correcto de la instancia
      SERVER_NAME: "api.example.com" # Cámbialo si es necesario
      MULTISITE: "yes"
      USE_REDIS: "yes"
      REDIS_HOST: "redis"
      api.example.com_USE_TEMPLATE: "bw-api"
      api.example.com_GENERATE_SELF_SIGNED_SSL: "yes"
      api.example.com_USE_REVERSE_PROXY: "yes"
      api.example.com_REVERSE_PROXY_URL: "/"
      api.example.com_REVERSE_PROXY_HOST: "http://bw-api:8888"
    volumes:
      - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-api:
    image: bunkerity/bunkerweb-api:1.6.6-rc3
    environment:
      <<: *bw-env
      API_USERNAME: "admin"
      API_PASSWORD: "Str0ng&P@ss!" # Recuerda usar una contraseña más fuerte para el usuario administrador
      DEBUG: "1"
    restart: "unless-stopped"
    networks:
      bw-universe:
        aliases:
          - bw-api
      bw-db:
        aliases:
          - bw-api

  bw-db:
    image: mariadb:11
    # Definimos el tamaño máximo de paquete permitido para evitar problemas con consultas grandes
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "changeme" # Recuerda usar una contraseña más fuerte para la base de datos
    volumes:
      - bw-data:/var/lib/mysql
    restart: "unless-stopped"
    networks:
      - bw-db

  redis: # Servicio de Redis para la persistencia de informes/baneos/estadísticas
    image: redis:7-alpine
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
        - subnet: 10.20.30.0/24 # Asegúrate de establecer el rango de IP correcto para que el scheduler pueda enviar la configuración a la instancia
  bw-services:
    name: bw-services
  bw-db:
    name: bw-db
```

Esto aísla la API detrás de BunkerWeb, mantiene el tráfico en redes de confianza y te permite aplicar autenticación, listas blancas y límites de tasa tanto en el plano de control como en el nombre de host expuesto.

## Puntos destacados

- Consciente de las instancias: transmite acciones operativas a las instancias descubiertas.
- Autenticación fuerte: Básica para administradores, anulación de administrador con Bearer, o ACL de Biscuit para permisos detallados.
- Lista blanca de IP y limitación de velocidad flexible por ruta.
- Señales estándar de salud/disponibilidad y comprobaciones de seguridad al inicio.

## Plantillas de Compose

=== "Docker"

    Haz un proxy inverso de la API bajo `/api` con BunkerWeb.

    ```yaml
    x-bw-env: &bw-env
      # Lista blanca compartida del plano de control de instancias para BunkerWeb/Scheduler
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp"  # QUIC
        environment:
          <<: *bw-env
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb"  # Coincide con el nombre del servicio de la instancia
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"
          DISABLE_DEFAULT_SERVER: "yes"
          # Proxy inverso de la API en /api
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/api"
          www.example.com_REVERSE_PROXY_HOST: "http://bw-api:8888"
        volumes:
          - bw-storage:/data
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.6-rc3
        environment:
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"  # Usa una contraseña fuerte
          API_WHITELIST_IPS: "127.0.0.0/8 10.20.30.0/24"                      # Lista blanca de la API
          API_TOKEN: "secret"                                                 # Token de anulación de administrador opcional
          API_ROOT_PATH: "/api"                                               # Coincide con la ruta del proxy inverso
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Evita problemas con consultas grandes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme"  # Usa una contraseña fuerte
        volumes:
          - bw-data:/var/lib/mysql
        restart: unless-stopped
        networks:
          - bw-db

    volumes:
      bw-data:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker Autoconf"

    Lo mismo que arriba pero aprovechando el servicio Autoconf para descubrir y configurar servicios automáticamente. La API se expone bajo `/api` usando etiquetas en el contenedor de la API.

    ```yaml
    x-api-env: &api-env
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"  # Usa una contraseña fuerte

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp"  # QUIC
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
        environment:
          <<: *api-env
          BUNKERWEB_INSTANCES: ""    # Descubierto por Autoconf
          SERVER_NAME: ""            # Rellenado a través de etiquetas
          MULTISITE: "yes"           # Obligatorio con Autoconf
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        volumes:
          - bw-storage:/data
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc3
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          <<: *api-env
          DOCKER_HOST: "tcp://bw-docker:2375"
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.6-rc3
        environment:
          <<: *api-env
          API_WHITELIST_IPS: "127.0.0.0/8 10.20.30.0/24"
          API_TOKEN: "secret"
          API_ROOT_PATH: "/api"
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/api"
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-api:8888"
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme"
        volumes:
          - bw-data:/var/lib/mysql
        restart: unless-stopped
        networks:
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: unless-stopped
        networks:
          - bw-docker

    volumes:
      bw-data:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
      bw-docker:
        name: bw-docker
    ```

!!! warning "Ruta del proxy inverso"
    Mantén la ruta de la API difícil de adivinar y combínala con la lista blanca de la API y la autenticación.

    Si ya expones otra aplicación en el mismo nombre de servidor con una plantilla (p. ej., `USE_TEMPLATE`), prefiere un nombre de host separado para la API para evitar conflictos.

### Todo en Uno

Si utilizas la imagen Todo en Uno, la API se puede habilitar estableciendo `SERVICE_API=yes`:

```bash
docker run -d \
  --name bunkerweb-aio \
  -e SERVICE_API=yes \
  -e API_WHITELIST_IPS="127.0.0.0/8" \
  -p 80:8080/tcp -p 443:8443/tcp -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3
```

## Autenticación

Formas admitidas para autenticar solicitudes:

- Administrador Básico: Cuando las credenciales pertenecen a un usuario de API administrador, los puntos finales protegidos aceptan `Authorization: Basic <base64(nombredeusuario:contraseña)>`.
- Anulación de Administrador con Bearer: Si se configura `API_TOKEN`, `Authorization: Bearer <API_TOKEN>` otorga acceso completo.
- Token Biscuit (recomendado): Obtén un token desde `POST /auth` utilizando credenciales Básicas o un cuerpo JSON/formulario que contenga `username` y `password`. Utiliza el token devuelto como `Authorization: Bearer <token>` en llamadas posteriores.

Ejemplo: obtener un Biscuit, listar instancias y luego recargar todas las instancias.

```bash
# 1) Obtener un token Biscuit con credenciales de administrador
TOKEN=$(curl -s -X POST -u admin:changeme http://api.example.com/auth | jq -r .token)

# 2) Listar instancias
curl -H "Authorization: Bearer $TOKEN" http://api.example.com/instances

# 3) Recargar la configuración en todas las instancias (sin prueba)
curl -X POST -H "Authorization: Bearer $TOKEN" \
     "http://api.example.com/instances/reload?test=no"
```

### Hechos y comprobaciones de Biscuit

Los tokens incorporan hechos como `user(<username>)`, `client_ip(<ip>)`, `domain(<host>)`, y un rol general `role("api_user", ["read", "write"])` derivado de los permisos de la base de datos. Los administradores incluyen `admin(true)` mientras que los no administradores llevan hechos detallados como `api_perm(<resource_type>, <resource_id|*>, <permission>)`.

La autorización mapea la ruta/método a los permisos requeridos; `admin(true)` siempre pasa. Cuando los hechos detallados están ausentes, la guarda recurre al rol general: GET/HEAD/OPTIONS requieren `read`; los verbos de escritura requieren `write`.

Las claves se almacenan en `/var/lib/bunkerweb/.api_biscuit_private_key` y `/var/lib/bunkerweb/.api_biscuit_public_key`. También puedes proporcionar `BISCUIT_PUBLIC_KEY`/`BISCUIT_PRIVATE_KEY` a través de variables de entorno; si no se establecen ni archivos ni variables de entorno, la API genera un par de claves al inicio y lo persiste de forma segura.

## Permisos (ACL)

Esta API soporta dos capas de autorización:

- Rol general: Los tokens llevan `role("api_user", ["read"[, "write"]])` para los puntos finales sin un mapeo detallado. Lectura se mapea a GET/HEAD/OPTIONS; escritura se mapea a POST/PUT/PATCH/DELETE.
- ACL detallada: Los tokens incorporan `api_perm(<resource_type>, <resource_id|*>, <permission>)` y las rutas declaran lo que requieren. `admin(true)` omite todas las comprobaciones.

Tipos de recursos admitidos: `instances`, `global_config`, `services`, `configs`, `plugins`, `cache`, `bans`, `jobs`.

Nombres de permisos por tipo de recurso:

- instances: `instances_read`, `instances_update`, `instances_delete`, `instances_create`, `instances_execute`
- global_config: `global_config_read`, `global_config_update`
- services: `service_read`, `service_create`, `service_update`, `service_delete`, `service_convert`, `service_export`
- configs: `configs_read`, `config_read`, `config_create`, `config_update`, `config_delete`
- plugins: `plugin_read`, `plugin_create`, `plugin_delete`
- cache: `cache_read`, `cache_delete`
- bans: `ban_read`, `ban_update`, `ban_delete`, `ban_created`
- jobs: `job_read`, `job_run`

ID de recursos: Para comprobaciones detalladas, el segundo segmento de la ruta se trata como `resource_id` cuando tiene sentido. Ejemplos: `/services/{service}` -> `{service}`; `/configs/{service}/...` -> `{service}`. Usa `"*"` (u omite) para otorgar globalmente para un tipo de recurso.

Configuración de usuario y ACL:

- Usuario administrador: Establece `API_USERNAME` y `API_PASSWORD` para crear el primer administrador al inicio. Para rotar las credenciales más tarde, establece `OVERRIDE_API_CREDS=yes` (o asegúrate de que el administrador fue creado con el método `manual`). Solo existe un administrador; los intentos adicionales recurren a la creación de no administradores.
- Usuarios no administradores y concesiones: Proporciona `API_ACL_BOOTSTRAP_FILE` apuntando a un archivo JSON, o monta `/var/lib/bunkerweb/api_acl_bootstrap.json`. La API lo lee al inicio para crear/actualizar usuarios y permisos.
- Archivo de caché de ACL: Se escribe un resumen de solo lectura en `/var/lib/bunkerweb/api_acl.json` al inicio para introspección; la autorización evalúa las concesiones respaldadas por la base de datos incorporadas en el token Biscuit.

Ejemplos de JSON de arranque (se admiten ambas formas):

```json
{
  "users": {
    "ci": {
      "admin": false,
      "password": "Str0ng&P@ss!",
      "permissions": {
        "services": {
          "*": { "service_read": true },
          "app-frontend": { "service_update": true, "service_delete": false }
        },
        "configs": {
          "app-frontend": { "config_read": true, "config_update": true }
        }
      }
    },
    "ops": {
      "admin": false,
      "password_hash": "$2b$13$...bcrypt-hash...",
      "permissions": {
        "instances": { "*": { "instances_execute": true } },
        "jobs": { "*": { "job_run": true } }
      }
    }
  }
}
```

O en formato de lista:

```json
{
  "users": [
    {
      "username": "ci",
      "password": "Str0ng&P@ss!",
      "permissions": [
        { "resource_type": "services", "resource_id": "*", "permission": "service_read" },
        { "resource_type": "services", "resource_id": "app-frontend", "permission": "service_update" }
      ]
    }
  ]
}
```

Notas:

- Las contraseñas pueden ser texto plano (`password`) o bcrypt (`password_hash` / `password_bcrypt`). Las contraseñas de texto plano débiles son rechazadas en compilaciones que no son de depuración; si faltan, se genera una aleatoria y se registra una advertencia.
- `resource_id: "*"` (o nulo/vacío) otorga globalmente sobre ese tipo de recurso.
- Las contraseñas de los usuarios existentes pueden actualizarse y se pueden aplicar concesiones adicionales a través del arranque.

## Referencia de características

La API está organizada por enrutadores centrados en recursos. Utiliza las secciones a continuación como un mapa de capacidades; el esquema interactivo en `/docs` documenta los modelos de solicitud/respuesta en detalle.

### Núcleo y autenticación

- `GET /ping`, `GET /health`: sondas de actividad ligeras para el propio servicio de la API.
- `POST /auth`: intercambia credenciales Básicas (o el token de anulación de administrador) por un Biscuit. Acepta JSON, formulario o cabeceras `Authorization`. Los administradores también pueden continuar usando HTTP Basic directamente en rutas protegidas cuando lo deseen.

### Plano de control de instancias

- `GET /instances`: lista las instancias registradas, incluyendo marcas de tiempo de creación/última vez visto, método de registro y metadatos.
- `POST /instances`: registra una nueva instancia gestionada por la API (nombre de host, puerto opcional, nombre de servidor, nombre amigable, método).
- `GET /instances/{hostname}` / `PATCH /instances/{hostname}` / `DELETE /instances/{hostname}`: inspecciona, actualiza campos mutables o elimina instancias gestionadas por la API.
- `DELETE /instances`: eliminación masiva; omite las instancias que no son de la API y las informa en `skipped`.
- `GET /instances/ping` y `GET /instances/{hostname}/ping`: comprobaciones de salud en todas o en instancias individuales.
- `POST /instances/reload?test=yes|no`, `POST /instances/{hostname}/reload`: activa la recarga de la configuración (el modo de prueba realiza una validación de ejecución en seco).
- `POST /instances/stop`, `POST /instances/{hostname}/stop`: retransmite comandos de detención a las instancias.

### Configuración global

- `GET /global_config`: obtiene configuraciones no predeterminadas (usa `full=true` para la configuración completa, `methods=true` para incluir la procedencia).
- `PATCH /global_config`: actualiza o inserta configuraciones globales propiedad de la API (`method="api"`); los errores de validación señalan claves desconocidas o de solo lectura.

### Ciclo de vida del servicio

- `GET /services`: enumera los servicios con metadatos, incluido el estado de borrador y las marcas de tiempo.
- `GET /services/{service}`: recupera las superposiciones no predeterminadas (`full=false`) o la instantánea completa de la configuración (`full=true`) para un servicio.
- `POST /services`: crea servicios, opcionalmente como borrador, y siembra variables con prefijo (`{service}_{KEY}`). Actualiza la lista `SERVER_NAME` atómicamente.
- `PATCH /services/{service}`: renombra servicios, cambia los indicadores de borrador y actualiza las variables con prefijo. Ignora las ediciones directas a `SERVER_NAME` dentro de `variables` por seguridad.
- `DELETE /services/{service}`: elimina un servicio y sus claves de configuración derivadas.
- `POST /services/{service}/convert?convert_to=online|draft`: cambia rápidamente el estado borrador/en línea sin alterar otras variables.

### Fragmentos de configuración personalizados

- `GET /configs`: lista fragmentos de configuración personalizados (HTTP/servidor/stream/ModSecurity/ganchos CRS) para un servicio (`service=global` por defecto). `with_data=true` incrusta contenido UTF-8 cuando es imprimible.
- `POST /configs` y `POST /configs/upload`: crea nuevos fragmentos a partir de cargas útiles JSON o archivos subidos. Los tipos aceptados incluyen `http`, `server_http`, `default_server_http`, `modsec`, `modsec_crs`, `stream`, `server_stream`, y ganchos de plugins CRS. Los nombres deben coincidir con `^[\w_-]{1,255}$`.
- `GET /configs/{service}/{type}/{name}`: recupera un fragmento con contenido opcional (`with_data=true`).
- `PATCH /configs/{service}/{type}/{name}` y `PATCH .../upload`: actualiza o mueve fragmentos gestionados por la API; las entradas gestionadas por plantilla o archivo permanecen de solo lectura.
- `DELETE /configs` y `DELETE /configs/{service}/{type}/{name}`: elimina fragmentos gestionados por la API conservando los gestionados por plantilla, devolviendo una lista `skipped` para las entradas ignoradas.

### Orquestación de baneos

- `GET /bans`: agrega los baneos activos informados por todas las instancias.
- `POST /bans` o `POST /bans/ban`: aplica uno o varios baneos. Las cargas útiles pueden ser objetos JSON, matrices o JSON en formato de cadena. `service` es opcional; cuando se omite, el baneo es global.
- `POST /bans/unban` o `DELETE /bans`: elimina baneos globalmente o por servicio utilizando las mismas cargas útiles flexibles.

### Gestión de plugins

- `GET /plugins?type=all|external|ui|pro`: lista plugins con metadatos; `with_data=true` incluye los bytes empaquetados cuando están disponibles.
- `POST /plugins/upload`: instala plugins de UI desde archivos `.zip`, `.tar.gz` o `.tar.xz`. Los archivos pueden agrupar múltiples plugins siempre que cada uno contenga un `plugin.json`.
- `DELETE /plugins/{id}`: elimina un plugin de UI por ID (`^[\w.-]{4,64}$`).

### Caché y ejecución de trabajos

- `GET /cache`: lista los artefactos en caché producidos por los trabajos del programador, filtrados por servicio, ID de plugin o nombre de trabajo. `with_data=true` incluye contenido de archivo imprimible.
- `GET /cache/{service}/{plugin}/{job}/{file}`: obtiene un archivo de caché específico (`download=true` transmite un archivo adjunto).
- `DELETE /cache` o `DELETE /cache/{service}/{plugin}/{job}/{file}`: elimina archivos de caché y notifica al programador sobre los plugins afectados.
- `GET /jobs`: inspecciona trabajos conocidos, sus metadatos de programación y resúmenes de caché.
- `POST /jobs/run`: solicita la ejecución de un trabajo marcando el(los) plugin(s) asociado(s) como cambiado(s).

### Notas operativas

- Los puntos finales de escritura persisten en la base de datos compartida; las instancias recogen los cambios a través de la sincronización del programador o después de un `/instances/reload`.
- Los errores se normalizan a `{ "status": "error", "message": "..." }` con los códigos de estado HTTP apropiados (422 validación, 404 no encontrado, 403 ACL, 5xx fallos de origen).

## Limitación de velocidad

La limitación de velocidad por cliente es manejada por SlowAPI. Habilítala/deshabilítala y configura los límites a través de variables de entorno o `/etc/bunkerweb/api.yml`.

- `API_RATE_LIMIT_ENABLED` (predeterminado: `yes`)
- Límite predeterminado: `API_RATE_LIMIT_TIMES` por `API_RATE_LIMIT_SECONDS` (p. ej., `100` por `60`)
- `API_RATE_LIMIT_RULES`: JSON/CSV en línea, o una ruta a un archivo YAML/JSON con reglas por ruta
- Backend de almacenamiento: en memoria o Redis/Valkey cuando `USE_REDIS=yes` y se proporcionan las variables `REDIS_*` (compatible con Sentinel)
- Cabeceras: `API_RATE_LIMIT_HEADERS_ENABLED` (predeterminado: `yes`)

Ejemplo de YAML (montado en `/etc/bunkerweb/api.yml`):

```yaml
API_RATE_LIMIT_ENABLED: yes
API_RATE_LIMIT_DEFAULTS: ["200/minute"]
API_RATE_LIMIT_RULES:
  - path: "/auth"
    methods: "POST"
    times: 10
    seconds: 60
  - path: "/instances*"
    methods: "GET|POST"
    times: 100
    seconds: 60```

## Configuración

Puedes configurar la API a través de variables de entorno, secretos de Docker y los archivos opcionales `/etc/bunkerweb/api.yml` o `/etc/bunkerweb/api.env`. Configuraciones clave:

- Documentación y esquema: `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL`, `API_ROOT_PATH`.
- Autenticación básica: `API_TOKEN` (Bearer de anulación de administrador), `API_USERNAME`/`API_PASSWORD` (crear/actualizar administrador), `OVERRIDE_API_CREDS`.
- ACL y usuarios: `API_ACL_BOOTSTRAP_FILE` (ruta JSON).
- Política de Biscuit: `API_BISCUIT_TTL_SECONDS` (0/desactivado deshabilita el TTL), `CHECK_PRIVATE_IP` (vincula el token a la IP del cliente a menos que sea privada).
- Lista blanca de IP: `API_WHITELIST_ENABLED`, `API_WHITELIST_IPS`.
- Limitación de velocidad (núcleo): `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_TIMES`, `API_RATE_LIMIT_SECONDS`, `API_RATE_LIMIT_HEADERS_ENABLED`.
- Limitación de velocidad (avanzado): `API_RATE_LIMIT_AUTH_TIMES`, `API_RATE_LIMIT_AUTH_SECONDS`, `API_RATE_LIMIT_RULES`, `API_RATE_LIMIT_DEFAULTS`, `API_RATE_LIMIT_APPLICATION_LIMITS`, `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`, `API_RATE_LIMIT_STORAGE_OPTIONS`.
- Almacenamiento de limitación de velocidad: en memoria o Redis/Valkey cuando `USE_REDIS=yes` y se establecen configuraciones de Redis como `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DATABASE`, `REDIS_SSL`, o variables de Sentinel. Consulta la tabla de configuraciones de Redis en `docs/features.md`.
- Red/TLS: `API_LISTEN_ADDR`, `API_LISTEN_PORT`, `API_FORWARDED_ALLOW_IPS`, `API_SSL_ENABLED`, `API_SSL_CERTFILE`, `API_SSL_KEYFILE`, `API_SSL_CA_CERTS`.

### Cómo se carga la configuración

Precedencia de mayor a menor:

- Variables de entorno (p. ej., `environment:` del contenedor o variables de shell exportadas)
- Archivos de secretos en `/run/secrets` (secretos de Docker/K8s; los nombres de archivo coinciden con los nombres de las variables)
- Archivo YAML en `/etc/bunkerweb/api.yml`
- Archivo de entorno en `/etc/bunkerweb/api.env` (líneas clave=valor)
- Valores predeterminados incorporados

Notas:

- YAML admite la inserción de archivos de secretos con `<file:relative/path>`; la ruta se resuelve contra `/run/secrets`.
- Establece las URL de la documentación en `off`/`disabled`/`none` para deshabilitar los puntos finales (p. ej., `API_DOCS_URL=off`).
- Si `API_SSL_ENABLED=yes`, también debes establecer `API_SSL_CERTFILE` y `API_SSL_KEYFILE`.
- Si Redis está habilitado (`USE_REDIS=yes`), proporciona los detalles de Redis; consulta la sección de Redis en `docs/features.md`.

### Autenticación y usuarios

- Arranque de administrador: establece `API_USERNAME` y `API_PASSWORD` para crear el primer administrador. Para volver a aplicar más tarde, establece `OVERRIDE_API_CREDS=yes`.
- No administradores y permisos: proporciona `API_ACL_BOOTSTRAP_FILE` con una ruta JSON (o monta en `/var/lib/bunkerweb/api_acl_bootstrap.json`). El archivo puede listar usuarios y concesiones detalladas.
- Claves de Biscuit: establece `BISCUIT_PUBLIC_KEY`/`BISCUIT_PRIVATE_KEY` o monta archivos en `/var/lib/bunkerweb/.api_biscuit_public_key` y `/var/lib/bunkerweb/.api_biscuit_private_key`. Si no se proporciona ninguno, la API genera y persiste un par de claves al inicio.

### TLS y redes

- Dirección/puerto de enlace: `API_LISTEN_ADDR` (predeterminado `0.0.0.0`), `API_LISTEN_PORT` (predeterminado `8888`).
- Proxies inversos: establece `API_FORWARDED_ALLOW_IPS` en las IP del proxy para que Gunicorn confíe en las cabeceras `X-Forwarded-*`.
- Terminación de TLS en la API: `API_SSL_ENABLED=yes` más `API_SSL_CERTFILE` y `API_SSL_KEYFILE`; opcional `API_SSL_CA_CERTS`

### Recetas rápidas de limitación de velocidad

- Deshabilitar globalmente: `API_RATE_LIMIT_ENABLED=no`
- Establecer un límite global simple: `API_RATE_LIMIT_TIMES=100`, `API_RATE_LIMIT_SECONDS=60`
- Reglas por ruta: establece `API_RATE_LIMIT_RULES` en una ruta de archivo JSON/YAML o YAML en línea en `/etc/bunkerweb/api.yml`.

!!! warning "Seguridad de inicio"
    La API se cierra si no hay una ruta de autenticación configurada (sin claves Biscuit, sin usuario administrador y sin `API_TOKEN`). Asegúrate de que al menos un método esté configurado antes de iniciar.

Seguridad de inicio: La API se cierra si no hay una ruta de autenticación disponible (sin claves Biscuit, sin usuario de API administrador y sin `API_TOKEN`). Asegúrate de que al menos una esté configurada.

!!! info "Ruta raíz y proxies"
    Si despliegas la API detrás de BunkerWeb en una subruta, establece `API_ROOT_PATH` en esa ruta para que `/docs` y las rutas relativas funcionen correctamente cuando se usan con un proxy.

## Operaciones

- Salud: `GET /health` devuelve `{"status":"ok"}` cuando el servicio está activo.
- Servicio de Linux: se empaqueta una unidad `systemd` llamada `bunkerweb-api.service`. Personaliza a través de `/etc/bunkerweb/api.env` y gestiona con `systemctl`.
- Seguridad de inicio: la API falla rápidamente cuando no hay una ruta de autenticación disponible (sin claves Biscuit, sin usuario administrador, sin `API_TOKEN`). Los errores se escriben en `/var/tmp/bunkerweb/api.error`.
