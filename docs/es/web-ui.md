# Interfaz Web

## Rol de la interfaz web

La interfaz web es el plano de control visual de BunkerWeb. Administra servicios, ajustes globales, bloqueos, plugins, trabajos, caché, registros y actualizaciones sin usar la CLI. Es una app Flask servida por Gunicorn y normalmente se coloca detrás de un reverse proxy BunkerWeb.

!!! warning "Manténla detrás de BunkerWeb"
    La UI puede cambiar configuración, ejecutar trabajos y desplegar fragmentos personalizados. Ubícala en una red de confianza, enrútala mediante BunkerWeb y protégela con credenciales fuertes y 2FA.

!!! info "Datos rápidos"
    - Escucha por defecto: `0.0.0.0:7000` en contenedores, `127.0.0.1:7000` en paquetes (cambia con `UI_LISTEN_ADDR`/`UI_LISTEN_PORT`)
    - Consciente de reverse proxy: respeta `X-Forwarded-*` via `UI_FORWARDED_ALLOW_IPS`; ajusta `PROXY_NUMBERS` si varios proxies agregan cabeceras
    - Auth: cuenta admin local (política de contraseña aplicada), roles opcionales, 2FA TOTP con `TOTP_ENCRYPTION_KEYS`
    - Sesiones: firmadas con `FLASK_SECRET`, vida útil por defecto 12 h, fijadas a IP y User-Agent; `ALWAYS_REMEMBER` controla cookies persistentes
    - Logs: `/var/log/bunkerweb/ui.log` (+ access log si se captura), UID/GID 101 dentro del contenedor
    - Salud: `GET /healthcheck` opcional si `ENABLE_HEALTHCHECK=yes`
    - Dependencias: lee y escribe la configuración mediante la API; el Scheduler, Worker, broker de jobs y base de datos deben estar disponibles

## Checklist de seguridad

- Ejecuta la UI detrás de BunkerWeb en una red interna; usa un `REVERSE_PROXY_URL` difícil de adivinar y limita IPs de origen.
- Establece `ADMIN_USERNAME` / `ADMIN_PASSWORD` fuertes; usa `OVERRIDE_ADMIN_CREDS=yes` solo cuando quieras forzar un reseteo.
- Proporciona `TOTP_ENCRYPTION_KEYS` y habilita TOTP en cuentas admin; guarda los códigos de recuperación.
- Prefiere passkeys cuando sea posible: define `UI_WEBAUTHN_RP_ID` (o una sola entrada `UI_ALLOWED_HOSTS`) y registra al menos dos por cuenta. Resisten el phishing: no firman para un origen incorrecto.
- Usa TLS (terminado en BunkerWeb o `UI_SSL_ENABLED=yes` con rutas de cert/clave); fija `UI_FORWARDED_ALLOW_IPS` a proxies de confianza.
- Persiste secretos: monta `/var/lib/bunkerweb` para conservar `FLASK_SECRET`, llaves Biscuit y material TOTP entre reinicios.
- Mantén `CHECK_PRIVATE_IP=yes` (por defecto) para ligar sesiones a la IP; deja `ALWAYS_REMEMBER=no` salvo que requieras cookies largas.
- Asegura que `/var/log/bunkerweb` permita escritura a UID/GID 101 (o el UID mapeado en rootless) para que la UI pueda leer logs.

## Puesta en marcha

La interfaz accede a BunkerWeb mediante la API. Ejecútala con Scheduler, Worker, broker dedicado y base de datos, como en los stacks de referencia.

=== "Inicio rápido (asistente)"

    Usa las imágenes publicadas y la estructura de la [guía rápida](quickstart-guide.md#__tabbed_1_3)
    para levantar el stack, y completa el asistente en el navegador.

=== "Avanzado (entorno presembrado)"

    Omite el asistente precargando credenciales y red; ejemplo Compose con sidecar syslog:

    ```yaml
    x-service-env: &service-env
      # We anchor the environment variables to avoid duplication
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      API_URL: "http://bw-api:8888"
      API_TOKEN: "changeme" # Replace this shared token before deploying
      CELERY_BROKER_URL: "redis://bw-jobs-broker:6379/0"
      LOG_TYPES: "stderr syslog" # Service logs from supporting components
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.7.0-beta
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *service-env
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        volumes:
          - bw-instance-data:/data
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-api:
        image: bunkerity/bunkerweb-api:1.7.0-beta
        restart: "unless-stopped"
        environment:
          <<: *service-env
          API_USERNAME: "changeme"
          API_PASSWORD: "Ch@ngeme1234"
        networks:
          - bw-universe
          - bw-db

      bw-worker:
        image: bunkerity/bunkerweb-worker:1.7.0-beta
        restart: "unless-stopped"
        depends_on:
          - bw-api
          - bw-jobs-broker
        volumes:
          # Its own volume: DATABASE_URI points at a real server here, so this /data holds
          # nothing but a scratch tree the worker rebuilds from the database -- no reason to
          # share the scheduler's. The SQLite stack (docker.yml) does share it, because there
          # the database IS a file under /data.
          - bw-worker-storage:/data
        environment:
          <<: *service-env
          BUNKERWEB_INSTANCES: "bunkerweb"
        networks:
          - bw-universe
          - bw-db

      bw-jobs-broker:
        image: valkey/valkey:8-alpine
        # noeviction on purpose: a broker that evicts under memory pressure drops queued
        # jobs on the floor, and nothing upstream would notice.
        # appendonly on purpose: a broker restart must not vaporise queued jobs.
        # AOF, not RDB ("--save" stays empty) — a 60s RDB loss window on a job queue
        # means silently dropped work, which is what the at-least-once acks exist to stop.
        command:
          [
            "valkey-server",
            "--save",
            "",
            "--appendonly",
            "yes",
            "--maxmemory",
            "256mb",
            "--maxmemory-policy",
            "noeviction",
          ]
        volumes:
          - bw-jobs-broker-data:/data
        healthcheck:
          test: ["CMD", "valkey-cli", "ping"]
          interval: 5s
          timeout: 3s
          retries: 10
          start_period: 5s
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
        environment:
          <<: *service-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
          ACCESS_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb_access"
          ERROR_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb"
          DISABLE_DEFAULT_SERVER: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Change it to a hard-to-guess URI
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.7.0-beta
        environment:
          <<: *service-env
          ADMIN_USERNAME: "admin"
          ADMIN_PASSWORD: "Str0ng&P@ss!" # Remember to set a stronger password for the admin user
          # TOTP_ENCRYPTION_KEYS: "changeme" # Optional: generated in the bw-ui-data volume when unset; a key must be 43 characters
          UI_FORWARDED_ALLOW_IPS: "10.20.30.0/24"
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - bw-ui-data:/data # This is used to persist the UI secrets (Flask secret, TOTP encryption keys, Biscuit keys)
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # We set the max allowed packet size to avoid issues with large queries
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      bw-syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE  # Bind to low ports
          - NET_BROADCAST  # Send broadcasts
          - NET_RAW  # Use raw sockets
          - DAC_READ_SEARCH  # Read files bypassing permissions
          - DAC_OVERRIDE  # Override file permissions
          - CHOWN  # Change ownership
          - SYSLOG  # Write to system logs
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # This is the syslog-ng configuration file
        restart: "unless-stopped"
        networks:
          - bw-universe

    volumes:
      bw-instance-data:
      bw-worker-storage:
      bw-jobs-broker-data:
      bw-data:
      bw-storage:
      bw-logs:
      bw-ui-data:

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

    Añade `bunkerweb-autoconf` y aplica labels al contenedor de la UI en vez de `BUNKERWEB_INSTANCES`. El scheduler sigue haciendo reverse proxy a la UI mediante la plantilla `ui` y un `REVERSE_PROXY_URL` secreto.

=== "Linux"

    El paquete instala el servicio systemd `bunkerweb-ui`. Se activa automáticamente con easy-install (el asistente también se inicia por defecto). Para ajustar o reconfigurar, edita `/etc/bunkerweb/ui.env` y luego:

    ```bash
    sudo systemctl enable --now bunkerweb-ui
    sudo systemctl restart bunkerweb-ui  # después de cambios
    ```

    Publícalo detrás de BunkerWeb (plantilla `ui`, `REVERSE_PROXY_URL=/changeme`, upstream `http://127.0.0.1:7000`). Monta `/var/lib/bunkerweb` y `/var/log/bunkerweb` para persistir secretos y logs.

### Específicos Linux vs Docker

- Enlaces por defecto: imágenes Docker escuchan en `0.0.0.0:7000`; paquetes Linux en `127.0.0.1:7000`. Cambia con `UI_LISTEN_ADDR` / `UI_LISTEN_PORT`.
- Cabeceras de proxy: `UI_FORWARDED_ALLOW_IPS` por defecto `127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16`; `UI_PROXY_ALLOW_IPS` toma por defecto el valor de `FORWARDED_ALLOW_IPS`. En Linux ajústalos a las IP de tu proxy para endurecer.
- Secretos y estado: `/var/lib/bunkerweb` guarda `FLASK_SECRET`, llaves Biscuit y material TOTP. Móntalo en Docker; en Linux lo gestiona el paquete.
- Logs: `/var/log/bunkerweb` debe ser legible por UID/GID 101 (o el UID mapeado en rootless). Los paquetes crean la ruta; los contenedores necesitan un volumen con permisos adecuados.
- Asistente: easy-install en Linux arranca la UI y el asistente automáticamente; en Docker se accede al asistente vía la URL reverse-proxificada salvo que preselecciones variables de entorno.

## Autenticación y sesiones

- Cuenta admin: créala con el asistente o con `ADMIN_USERNAME` / `ADMIN_PASSWORD`. La contraseña debe incluir minúsculas, mayúsculas, dígito y carácter especial. `OVERRIDE_ADMIN_CREDS=yes` fuerza la resiembra aunque ya exista.
- Límite de longitud de contraseña: bcrypt solo usa los primeros **72 bytes** de un secreto, por lo que las contraseñas se limitan a 72 bytes en todos los lugares donde se configuran (asistente de configuración, página de perfil, `ADMIN_PASSWORD` / `API_PASSWORD`). Un valor más largo se rechaza con un error o registro explicativo en lugar de truncarse silenciosamente. Ten en cuenta que los caracteres no ASCII (acentos, emoji) consumen varios bytes cada uno; una frase de contraseña de "72 caracteres" formada por esos caracteres puede superar el límite. Los valores bcrypt pre-hasheados están exentos (el hash ya codifica el límite).
- Roles: `admin`, `writer` y `reader` se crean automáticamente; las cuentas viven en la base de datos.
- Secretos: `FLASK_SECRET` se guarda en `/var/lib/bunkerweb/.flask_secret`; las llaves Biscuit al lado, opcionalmente vía `BISCUIT_PUBLIC_KEY` / `BISCUIT_PRIVATE_KEY`.
- 2FA: habilita TOTP con `TOTP_ENCRYPTION_KEYS` (separadas por espacios o JSON). Genera una llave:

    ```bash
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    Los códigos de recuperación se muestran una sola vez; si pierdes las llaves de cifrado, se eliminan los secretos TOTP almacenados.
- Passkeys (WebAuthn / FIDO2): al resolver `UI_WEBAUTHN_RP_ID` (ver abajo), la pestaña **Security** del perfil muestra **Passkeys**. Una passkey permite entrar sin usuario ni contraseña: el autenticador verifica localmente, sin pedir TOTP. Puedes registrar varias, cada una con nombre, fecha de creación y último uso. Una llave FIDO2 antigua no descubrible no inicia sesión por sí sola, pero sirve como alternativa a TOTP después de la contraseña.

    Es una vía *alternativa*, no un requisito adicional: registrar una passkey no la exige después
    de la contraseña. No tienen códigos de recuperación y perder el dispositivo podría bloquear
    la cuenta. Contraseña y TOTP siguen funcionando igual; las cuentas sin passkey no cambian.
    Usa TOTP con códigos de recuperación para *exigir* un segundo factor.
- Sesiones: duración de inactividad por defecto 12 h (`SESSION_LIFETIME_HOURS`), refrescada en cada petición. Se aplica un límite absoluto vía `SESSION_ABSOLUTE_HOURS` (por defecto `168` = 7 días) — superado ese tiempo, los usuarios son desconectados aunque sigan activos. Rotación opcional del identificador de sesión (`SESSION_ROLLING_HOURS`, por defecto `0` = deshabilitada) regenera el ID de sesión en ese intervalo. Sesiones fijadas a IP y User-Agent; `CHECK_PRIVATE_IP=no` relaja el control de IP solo en rangos privados. `ALWAYS_REMEMBER=yes` fuerza cookies persistentes.
- Ajusta `PROXY_NUMBERS` si varios proxies añaden `X-Forwarded-*`.

!!! tip "Contraseña de administrador pre-hasheada"
    `ADMIN_PASSWORD` acepta un **hash bcrypt** (`$2a$`/`$2b$`/`$2y$`) y lo almacena tal cual, manteniendo el texto plano fuera de tus archivos de entorno y secretos. Se omite la política de fortaleza (tú eres responsable de la contraseña de origen), pero se **rechaza** un factor de coste inferior a `10`; `10`–`11` registra una advertencia (se recomienda `12`+). Solo en creación por entorno y `OVERRIDE_ADMIN_CREDS`: el asistente y el perfil siguen requiriendo texto plano.

    Genera un hash:

    ```bash
    python3 -c "import bcrypt; print(bcrypt.hashpw(b'Str0ng&P@ss!', bcrypt.gensalt(rounds=13)).decode())"
    ```

!!! warning "Un hash incorrecto te bloquea"
    Usa un hash solo si conoces su texto plano. Un hash válido pero incorrecto en la primera creación no se puede revertir y un reinicio no lo arregla. Recupera con un `ADMIN_PASSWORD` distinto y `OVERRIDE_ADMIN_CREDS=yes`.

!!! warning "El 2FA desaparece al recrear el contenedor"
    Los secretos TOTP se guardan cifrados en la base de datos, pero las claves que los descifran viven **en disco**, no en la base de datos. En cada arranque la interfaz toma la primera fuente disponible: `/var/lib/bunkerweb/.totp_encryption_keys.json`, luego el antiguo `.totp_secrets.json`, y después `TOTP_ENCRYPTION_KEYS` (alias `TOTP_SECRETS`). Si ninguna sirve, genera un conjunto aleatorio nuevo, los secretos almacenados dejan de poder descifrarse, la inscripción del administrador se elimina de la base de datos y todos los usuarios deben inscribirse de nuevo.

    Reiniciar un contenedor es inofensivo. Lo que pierde las claves es perder el sistema de ficheros del contenedor: `docker compose down` y luego `up`, una recreación tras cambiar la imagen o el entorno, `docker rm`, o un pod nuevo. Basta con montar un volumen persistente en `/data` en el contenedor `bw-ui`, y todos los ejemplos de esta página lo hacen — `/var/lib/bunkerweb` es un enlace simbólico a `/data/lib` en la imagen — lo que deja `TOTP_ENCRYPTION_KEYS` como opcional.

    Defina la variable usted mismo solo si ese volumen no puede persistirse, o para controlar la rotación. Si lo hace, atienda a la longitud: un marcador como `changeme` **no** es una clave válida — las claves tienen 43 caracteres, tal como las produce `generate_secret()` de `passlib`. Un valor inválido se descarta y se sustituye por una clave aleatoria y, a diferencia de una variable sin definir, además impide que se restablezca la inscripción del administrador, de modo que el 2FA queda inutilizable hasta que se borre manualmente. La rotación es posible con un mapa JSON: conserve las claves antiguas junto a la nueva y las inscripciones existentes seguirán siendo válidas.

## Fuentes de configuración y prioridad

1. Variables de entorno (incl. `environment:` de Docker/Compose)
2. Secrets en `/run/secrets/<VAR>` (Docker)
3. Archivo env `/etc/bunkerweb/ui.env` (paquetes Linux)
4. Valores por defecto integrados

## Referencia de configuración

### Tiempo de ejecución y zona horaria

| Ajuste | Descripción                                            | Valores aceptados                      | Predeterminado                              |
| ------ | ------------------------------------------------------ | -------------------------------------- | ------------------------------------------- |
| `TZ`   | Zona horaria para logs de la UI y acciones programadas | Nombre TZ (ej. `UTC`, `Europe/Madrid`) | sin definir (normalmente UTC en contenedor) |

### Listener y TLS

| Ajuste                              | Descripción                               | Valores aceptados                    | Predeterminado                                        |
| ----------------------------------- | ----------------------------------------- | ------------------------------------ | ----------------------------------------------------- |
| `UI_LISTEN_ADDR`                    | Dirección de escucha de la UI             | IP o hostname                        | `0.0.0.0` (Docker) / `127.0.0.1` (paquete)            |
| `UI_LISTEN_PORT`                    | Puerto de escucha de la UI                | Entero                               | `7000`                                                |
| `LISTEN_ADDR`, `LISTEN_PORT`        | Alternativas si faltan vars de UI         | IP/hostname, entero                  | `0.0.0.0`, `7000`                                     |
| `UI_SSL_ENABLED`                    | Habilitar TLS en el contenedor UI         | `yes` o `no`                         | `no`                                                  |
| `UI_SSL_CERTFILE`, `UI_SSL_KEYFILE` | Rutas de cert/clave PEM con TLS           | Rutas de archivo                     | sin definir                                           |
| `UI_SSL_CA_CERTS`                   | CA/cadena opcional                        | Ruta de archivo                      | sin definir                                           |
| `UI_FORWARDED_ALLOW_IPS`            | Proxies de confianza para `X-Forwarded-*` | IPs/CIDRs separados por espacio/coma | `127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` |
| `UI_PROXY_ALLOW_IPS`                | Proxies de confianza para protocolo PROXY | IPs/CIDRs separados por espacio/coma | `FORWARDED_ALLOW_IPS`                                 |

### Auth, sesiones y cookies

| Ajuste                                      | Descripción                                                                                                            | Valores aceptados       | Predeterminado            |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ----------------------- | ------------------------- |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`          | Inicializar cuenta admin (política de contraseña; `ADMIN_PASSWORD` también acepta un hash bcrypt, almacenado tal cual) | Cadenas / hash bcrypt   | sin definir               |
| `OVERRIDE_ADMIN_CREDS`                      | Forzar actualización de credenciales admin desde env                                                                   | `yes` o `no`            | `no`                      |
| `FLASK_SECRET`                              | Secreto de firma de sesión (persistido en `/var/lib/bunkerweb/.flask_secret`)                                          | Cadena hex/base64/opaca | generado automáticamente  |
| `TOTP_ENCRYPTION_KEYS` (`TOTP_SECRETS`)     | Claves para cifrar TOTP (espacio o JSON)                                                                               | Cadenas / JSON          | generadas si faltan       |
| `BISCUIT_PUBLIC_KEY`, `BISCUIT_PRIVATE_KEY` | Claves Biscuit (hex) para tokens de UI                                                                                 | Cadenas hex             | autogeneradas y guardadas |
| `SESSION_LIFETIME_HOURS`                    | Duración de inactividad de sesión (TTL deslizante, refrescada por petición)                                            | Número (horas)          | `12`                      |
| `SESSION_ABSOLUTE_HOURS`                    | Límite absoluto de sesión independiente de la actividad                                                                | Número (horas)          | `168`                     |
| `SESSION_ROLLING_HOURS`                     | Intervalo de rotación del ID de sesión (`0` deshabilita la rotación)                                                   | Número (horas)          | `0`                       |
| `ALWAYS_REMEMBER`                           | Activar siempre “remember me”                                                                                          | `yes` o `no`            | `no`                      |
| `CHECK_PRIVATE_IP`                          | Ligar sesión a IP (relaja en redes privadas con `no`)                                                                  | `yes` o `no`            | `yes`                     |
| `PROXY_NUMBERS`                             | Saltos de proxy confiables para `X-Forwarded-*`                                                                        | Entero                  | `1`                       |
| `UI_WEBAUTHN_RP_ID` | Identificador de parte confiable WebAuthn (dominio sin esquema ni puerto). Por defecto, la única entrada no comodín de `UI_ALLOWED_HOSTS`. | Nombre de dominio | derivado; si no, deshabilitado |
| `UI_WEBAUTHN_ORIGINS` | Orígenes exactos aceptados durante la operación. | URLs separadas por espacios/comas | `https://<RP ID>` |

!!! warning "El RP ID forma parte del límite de seguridad"
    Las credenciales WebAuthn están vinculadas criptográficamente al RP ID. Nunca se deduce de
    `Host`, controlable por un atacante. Se usa `UI_WEBAUTHN_RP_ID`; en su ausencia, la única
    entrada de `UI_ALLOWED_HOSTS` si no es comodín (sin `:port`); si no hay ninguna válida, las
    passkeys quedan desactivadas y la interfaz registra el motivo al arrancar.

    **Cambiar el dominio de la interfaz invalida todas las passkeys registradas.** Los usuarios
    deben registrar otras en el nuevo dominio; no se pueden migrar porque el autenticador incorpora
    el RP ID. Conserva TOTP o contraseña como alternativa antes de cambiar el dominio. Estas
    operaciones requieren HTTPS, salvo `localhost` (por eso funciona `http://localhost:7000` en desarrollo).

### Gestor de certificados {#certificate-manager}

| Ajuste | Descripción | Valores aceptados | Predeterminado |
| ------ | ----------- | ----------------- | -------------- |
| `CERTIFICATE_ENCRYPTION_KEYS` | Anillo de claves AES-256-GCM para las claves privadas almacenadas. | Objeto JSON de IDs a claves de 32 bytes en base64 | sin definir |
| `CERTIFICATE_ENCRYPTION_ACTIVE_KEY` | ID de clave para nuevas claves privadas importadas o generadas. | Clave presente en el anillo | sin definir |

Ambas variables son necesarias para crear, importar y renovar certificados autofirmados. Conserva
los IDs antiguos mientras haya certificados que los usen y proporciona el mismo anillo a todos
los procesos API y worker que gestionen certificados. Los endpoints de descarga nunca exponen claves privadas.

La API concentra en `/certificates` el inventario: listado, metadatos, asignaciones, eliminación de
certificados no gestionados y descargas públicas. El ciclo de vida depende del proveedor:
`/selfsigned/certificates` crea y renueva autofirmados, `/customcert/certificates/upload` importa
PEM y `/letsencrypt/certificates` programa ACME y expone la consulta de estados huérfanos. Así los
proveedores siguen siendo extensibles y la interfaz no evita la API.

Las asignaciones del gestor organizan el inventario; no sustituyen los ajustes de Let's Encrypt o
certificados personalizados por servicio que controlan el TLS activo. Los registros Let's Encrypt
se sincronizan desde la caché certbot. La eliminación gestionada por el proveedor no está disponible
hasta que el worker pueda confirmar y reintentar operaciones específicas de caché de forma duradera:
eliminar el estado ACME todavía no elimina automáticamente su registro del inventario.

### Logging

| Ajuste                          | Descripción                                                 | Valores aceptados                               | Predeterminado                              |
| ------------------------------- | ----------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Nivel base / override                                       | `debug`, `info`, `warning`, `error`, `critical` | `info`                                      |
| `LOG_TYPES`                     | Destinos                                                    | `stderr`/`file`/`syslog` separados por espacio  | `stderr`                                    |
| `LOG_FILE_PATH`                 | Ruta para logs a archivo (`file` o `CAPTURE_OUTPUT=yes`)    | Ruta de archivo                                 | `/var/log/bunkerweb/ui.log` si file/capture |
| `CAPTURE_OUTPUT`                | Enviar stdout/stderr de Gunicorn a handlers                 | `yes` o `no`                                    | `no`                                        |
| `LOG_SYSLOG_ADDRESS`            | Destino syslog (`udp://host:514`, `tcp://host:514`, socket) | Host:puerto / URL / socket                      | sin definir                                 |
| `LOG_SYSLOG_TAG`                | Tag/ident syslog                                            | Cadena                                          | `bw-ui`                                     |

### Runtime misceláneo

| Ajuste                          | Descripción                                                                   | Valores aceptados                           | Predeterminado                                        |
| ------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------- |
| `MAX_WORKERS`, `MAX_THREADS`    | Workers/hilos de Gunicorn                                                     | Entero                                      | `cpu_count()-1` (mín 1), `workers*2`                  |
| `MAX_REQUESTS`                  | Solicitudes antes de reciclar el worker Gunicorn (previene exceso de memoria) | Entero                                      | `1000`                                                |
| `ENABLE_HEALTHCHECK`            | Exponer `GET /healthcheck`                                                    | `yes` o `no`                                | `no`                                                  |
| `FORWARDED_ALLOW_IPS`           | Alias para lista de proxies                                                   | IPs/CIDRs                                   | `127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` |
| `PROXY_ALLOW_IPS`               | Alias para lista de PROXY                                                     | IPs/CIDRs                                   | `FORWARDED_ALLOW_IPS`                                 |
| `DISABLE_CONFIGURATION_TESTING` | Saltar reloads de prueba al aplicar config                                    | `yes` o `no`                                | `no`                                                  |
| `IGNORE_REGEX_CHECK`            | Omitir validación regex de ajustes                                            | `yes` o `no`                                | `no`                                                  |
| `MAX_CONTENT_LENGTH`            | Tamaño máximo de subida (Flask `MAX_CONTENT_LENGTH`)                          | Tamaño con unidad (`50M`, `1G`, `52428800`) | `50MB`                                                |

## Acceso a logs

La UI lee logs de NGINX/servicios desde `/var/log/bunkerweb`. Alimenta ese directorio con un demonio syslog o un volumen:

- El UID/GID del contenedor es 101. En el host hazlos legibles: `chown root:101 bw-logs && chmod 770 bw-logs` (ajusta para rootless).
- Envía access/error logs de BunkerWeb vía `ACCESS_LOG` / `ERROR_LOG` al sidecar syslog; logs de componentes con `LOG_TYPES=syslog`.

Ejemplo de `syslog-ng.conf` para escribir logs por programa:

```conf
@version: 4.10
source s_net { udp(ip("0.0.0.0")); };
template t_imp { template("$MSG\n"); template_escape(no); };
destination d_dyna_file {
  file("/var/log/bunkerweb/${PROGRAM}.log"
       template(t_imp) owner("101") group("101")
       dir_owner("root") dir_group("101")
       perm(0440) dir_perm(0770) create_dirs(yes));
};
log { source(s_net); destination(d_dyna_file); };
```

## Capacidades

- Panel para solicitudes, bloqueos, caché y jobs; reinicio/recarga de instancias.
- Crear/actualizar/eliminar servicios y ajustes globales con validación contra esquemas de plugins.
- Subir y gestionar configs personalizadas (NGINX/ModSecurity) y plugins (externos o PRO).
- Ver logs, buscar reportes e inspeccionar artefactos de caché.
- Gestionar usuarios de UI, roles, sesiones y TOTP con códigos de recuperación.
- Actualizar a BunkerWeb PRO y ver estado de licencia en la página dedicada.

### La entrada del servidor predeterminado {#the-default-server-entry}

Con `MULTISITE=yes`, la lista de servicios muestra arriba una entrada fijada **Default server** con una explicación.
Es `default-server`, que responde a peticiones sin servicio coincidente: hostname desconocido, IP
directa o un `Host` no servido. La entrada reservada no existe en modo de sitio único.

Permite configurar certificado, TLS, cabeceras, páginas de error y lista blanca. No ofrece proxy
inverso, gRPC, redirecciones, sesiones, antibot, mTLS, CORS ni autenticación HTTP básica: no tiene
hostname que enrutar ni identidad de servicio a la que vincularlos. Tampoco permite eliminar,
clonar o convertir; es permanente y nunca cuenta para la cuota PRO.

### Registro de instancias {#instance-enrollment}

Una instancia mostrada en la página **Instancias** puede recibir su propia credencial del plano de control en lugar de compartir el `API_TOKEN` global. El botón de llave de la fila (o el menú de historial) emite un código de registro de un solo uso, mostrado una vez, que la instancia canjea al arrancar mediante `INSTANCE_ENROLLMENT_CODE`; a partir de entonces solo responde a la credencial que el plano de control acuñó para ella. La mecánica completa, incluidos los endpoints de la API y la diferencia entre `manual` y `autoconf`, está en la [referencia de la API](api.md#enrollment-an-alternative-to-setting-credential-by-hand).

El registro funciona para una fila creada desde la UI o la API, y para una fila declarada mediante el entorno (`BUNKERWEB_INSTANCES` / `BUNKERWEB_INSTANCE_*`) — la forma predeterminada de un despliegue Docker o Linux. **No** funciona para una fila descubierta por autoconf: esa fila se vuelve a obtener de un orquestador activo en cada reconciliación, lo que devolvería el token del entorno por encima de una credencial acuñada, así que los botones de registrar, rotar y revocar están deshabilitados en ella.

Una instancia que declara su propio `BUNKERWEB_INSTANCE_API_TOKEN_<n>` muestra el mismo chip **Registrada** que una registrada mediante código, porque la página interpreta "tiene una credencial por instancia" y un token declarado se almacena como tal. Los botones no son peligrosos ahí, pero son casi inútiles: el siguiente guardado de configuración del scheduler vuelve a tomar el token declarado, lo que sobrescribe una credencial acuñada y levanta una revocación de todas formas. Elija una u otra opción para una instancia dada — regístrela o declare un token para ella, no ambas cosas.

!!! warning "Dele a la instancia un volumen persistente"
    La credencial vive en `/var/lib/bunkerweb`, que la imagen Docker enlaza simbólicamente a `/data`. Un contenedor recreado **sin** volumen para `/data` pierde la credencial y el marcador que de otro modo detectaría la pérdida: vuelve como una instancia nueva, no registrada, mientras el plano de control sigue creyendo que está registrada, y cada envío de configuración hacia ella se rechaza sin explicar por qué. Con un volumen montado, la instancia detecta la pérdida por sí misma y **se niega a arrancar**, indicando la causa y la solución. Los paquetes Linux ya persisten `/var/lib/bunkerweb`, así que esto es una salvedad exclusiva de contenedores — ver los archivos compose en la [guía de inicio rápido](quickstart-guide.md) y en `misc/integrations/`, que montan todos uno.

!!! note "Una fila `manual` sigue sin poder eliminarse desde aquí"
    Registrar, rotar o revocar una fila declarada en el entorno funciona desde esta página, pero eliminarla no — el siguiente guardado de configuración la vuelve a crear a partir de `BUNKERWEB_INSTANCES` / `BUNKERWEB_INSTANCE_*`. En su lugar, quite el hostname del entorno, lo que también elimina su registro.

### Grupos de recursos {#resource-groups}

En **Configure → Resource groups** mantén listas reutilizables de IP/CIDR, países, ASN, sufijos
DNS inversos, patrones de User-Agent y URI. Cada entrada tiene un tipo y un comentario opcional.
Puedes clonar grupos, exportarlos en JSON y consultar todas sus referencias antes de cambiarlos.

Usa `@alias` en un ajuste compatible, por ejemplo `@office 203.0.113.5`. Las listas de Whitelist,
Blacklist, Greylist, Real IP, DNSBL y Antibot admiten referencias. El token se conserva en la base
y se expande al generar la configuración según el tipo del ajuste: modificar el grupo actualiza
todos sus consumidores en el siguiente envío. Los workflows seleccionan grupos por ID estable.

El alias tiene entre 1 y 64 letras, cifras, guiones o guiones bajos. `@EU`, `@G7` y `@SCHENGEN`
están reservados. Se rechazan grupos inexistentes o sin entradas del tipo requerido y no se puede
eliminar un grupo mientras lo use un ajuste o workflow.

### Upstreams

En **Configure → Upstreams** mantén pools reutilizables HTTP, gRPC o stream y adjúntalos a varios
servicios. Cada pool tiene nombre, protocolo (`http`, `grpc`, `stream`), método de balanceo
(`round_robin`, `least_conn`, `ip_hash`), hasta 64 servidores con peso, max-fails, fail-timeout y
rol primary/backup/down, un número opcional de conexiones keepalive y `backend_ssl`. La asociación
registra la ruta del proxy inverso (`/` por defecto); un pool admite hasta 100 servicios.

La página usa `GET /upstreams`, `POST /upstreams`, `PATCH /upstreams/{id}`, `DELETE /upstreams/{id}`
y `POST/DELETE /upstreams/{id}/attachments[/{service}]` para listar, crear, editar, eliminar y asociar o separar.

### Plantillas {#templates}

En **Configure → Templates** puedes explorar, crear y gestionar plantillas reutilizables: ajustes,
pasos ordenados y configuraciones personalizadas que un servicio adopta mediante `USE_TEMPLATE`.
La galería muestra cuántos servicios, incluidos borradores, usan cada plantilla y sus funciones.
El editor usa el mismo catálogo de ajustes multisitio que los servicios y permite empezar desde
cero o clonar una plantilla. El **Templates catalogue** comunitario ofrece plantillas preparadas.
Instalarlas requiere `admin`, no basta con `write`: pueden contener configuración NGINX guardada
sin validar el contenido. Los ajustes siempre se verifican contra la tabla de ajustes de esta
versión; una plantilla que nombre un ajuste desconocido se rechaza.

Desde 1.7, `USE_TEMPLATE` acepta varias plantillas por servicio, aplicadas en orden; ante un
conflicto gana la última. Esta página permite crear esos bloques reutilizables.

### Gestión de la caché web {#web-cache-management}

**Web cache** gestiona la caché NGINX del proxy inverso. Muestra el estado de informe de cada
instancia, entradas y tamaño en disco, servicios con `USE_PROXY_CACHE` efectivo y contadores
`HIT`, `MISS`, `BYPASS` y `STALE` cuando Metrics los proporciona.

Puedes purgar una URL HTTP(S) absoluta o toda la caché. Para una URL se reconstruye el
`PROXY_CACHE_KEY` exacto; proporciona la plantilla personalizada del servicio si difiere de la
predeterminada. La API admite hasta 100 URLs por petición.

!!! warning "Una purga completa afecta a todos los servicios con caché"
    `scope: "all"` vacía la zona compartida `proxycache` en cada instancia accesible. No se limita
    a un servicio ni recarga NGINX. Una instancia inaccesible se omite sin encolar trabajo:
    comprueba el resultado por instancia antes de dar por terminada la purga de toda la flota.

### Panel de informes {#reports-dashboard}

La página **Reports** cubre peticiones HTTP bloqueadas y sesiones STREAM bloqueadas. **Overview**
muestra la actividad del intervalo seleccionado, **Attack patterns** agrupa reglas ModSecurity y
familias de ataque, **Top offenders** clasifica IP, países y ASN, y **Event log** ofrece búsqueda
en el servidor, filtros, columnas ordenables, detalles y exportación CSV o Excel. Los administradores
pueden bloquear un infractor, filas seleccionadas o todas las IP del resultado filtrado.

Un informe incluye peticiones bloqueadas con 4xx, detecciones bajo `SECURITY_MODE=detect` y sesiones
STREAM bloqueadas. También conserva tres acciones por su motivo aunque no respondan con bloqueo:
un desafío de detección de bots CrowdSec 1.8, servido por BunkerWeb con 200 sin llegar a la aplicación;
una redirección de workflows con 3xx; y un desafío Antibot, servido igual que el de CrowdSec.
Un desafío Antibot se muestra a cualquier visitante no identificado, no solo a
atacantes, y puede llenar el búfer `METRICS_MAX_BLOCKED_REQUESTS` (por worker, `1k` por defecto)
o `METRICS_MAX_BLOCKED_REQUESTS_REDIS` con Redis. El búfer descarta primero lo más antiguo y puede
perder bloqueos reales para guardar desafíos. Aumenta primero ese límite y después dimensiona
`METRICS_RETENTION_DAYS` y `METRICS_RETENTION_MAX_ROWS`. Las pestañas analíticas y el mapa solo
cuentan peticiones bloqueadas o detectadas, nunca desafíos servidos.

La columna **Reason** muestra la decisión registrada por el plugin, por ejemplo
*CrowdSec AppSec: bot-detection challenge*, *CrowdSec LAPI: request blocked (scenario: …)*,
*Antibot challenge (captcha) served* o *Security workflow api-shield: redirect*. Los detalles
conservan los campos originales. Ordenación y filtro siguen usando el valor subyacente: los
filtros guardados mantienen su significado.

`METRICS_PERSIST_TO_DB=yes` es el predeterminado y conserva un historial central, limitado por
`METRICS_RETENTION_DAYS` y `METRICS_RETENTION_MAX_ROWS`. Sin persistencia, los informes quedan en
memoria o Redis y pueden caducar antes. Si falla la API Metrics, el registro usa la consulta
heredada de instancias/Redis y las pestañas analíticas quedan vacías hasta que Metrics se recupere.

### Mapa de amenazas {#threatmap}

**Threatmap** es una vista personal para una pantalla mural de los mismos informes almacenados.
Dibuja arcos del país de origen al centro simbólico (ilustra el origen, no un ataque geolocalizado:
no se recogen coordenadas ni un nombre de servicio tiene posición), colorea países por volumen
bloqueado y muestra principales infractores y eventos recientes. Requiere `METRICS_PERSIST_TO_DB=yes`;
si está desactivado, lo explica. El modo de pantalla completa oculta el marco de la aplicación.
`GET /threatmap/data` refresca las cifras con un retraso aproximado de uno a dos minutos, el
intervalo del job que recopila los informes.

### Tiempos {#timings}

**Timings** muestra `METRICS_COLLECT_TIMINGS`: tiempo consumido por las fases de cada plugin,
agregado en la flota y ordenado por coste total. Los porcentajes usan la duración completa de la
petición que la fase `request` de Metrics registra siempre. `init`, `init_worker(s)`, `timer` y
la API interna no tienen porcentaje porque no se ejecutan una vez por petición. Cuando ninguna
instancia informa, la página distingue la función desactivada (consulta `METRICS_COLLECT_TIMINGS`)
de una API inaccesible, en lugar de presentar una tabla vacía como si no hubiera actividad.

### Ejecuciones de jobs diferidas

La página **Jobs** puede mostrar un tercer resultado de ejecución además de los habituales pills verde de Éxito y rojo de Fallo: **Diferido — esperando a que una instancia esté disponible**, en el color de advertencia, con un icono de reloj. Aparece cuando un job — el caso habitual es `push-configs` al encontrar inalcanzable a toda instancia registrada — se detiene deliberadamente sin aplicar nada, en lugar de fallar: no se envió nada, pero tampoco hay ningún error, y el cambio pendiente se reintenta automáticamente en cuanto una instancia vuelve a responder. Pase el cursor sobre el pill para ver el motivo concreto; la etiqueta corta es también lo que coincide con el filtro de estado de la página.

El primer diferimiento tras una ejecución exitosa también genera un banner de advertencia descartable en la parte superior de cada página, distinto del banner existente (y más grave) de "push fallido", para que una flota que simplemente espera a que una instancia reinicie no parezca averiada.

## Recorrido guiado

Una instalación nueva abre un panel **Primeros pasos** desde el icono del cohete en la barra superior. Enumera lo que queda por hacer, marca cada elemento por su cuenta y desaparece en cuanto todo está listo, o en cuanto lo cierras.

No se guarda nada sobre lo que has *visto*: cada elemento se vuelve a calcular a partir de la configuración en ejecución cada vez que abres el panel. Registra un servicio desde la API o desde una etiqueta de Docker, y la próxima vez que mires el elemento correspondiente ya estará marcado. A la inversa, eliminar tu último servicio hace que su elemento vuelva a aparecer.

Lo que se te muestra depende de tu rol:

| Rol | Qué ofrece el recorrido |
| --- | --- |
| Admin | Instalación, primer servicio, HTTPS, primera solicitud bloqueada, MFA, más los elementos opcionales de workflow y PRO |
| Writer | Lo mismo, sin el elemento PRO exclusivo de admin |
| Reader | Orientación en vez de tareas: dónde están el dashboard, los reports, los bans y los logs, y cómo leerlos |

Los Reader reciben una breve pista en cada una de esas cuatro páginas la primera vez que las visitan; confirmarla con **Entendido** es lo que marca el elemento correspondiente. Cualquier elemento que señale un lugar de la interfaz incluye además un botón **Muéstramelo** que lo resalta en la navegación.

Los elementos opcionales — un workflow de seguridad, PRO — nunca retienen el contador: una instalación Community llega a "todo hecho" sin ellos.

!!! info "¿Lo cerraste sin querer?"
    **Perfil → Recorrido guiado → Reiniciar recorrido** trae de vuelta el panel. En una base de datos de solo lectura el botón está deshabilitado, ya que no se podría guardar nada.

## Novedades tras una actualización

Tras una actualización, la primera página que abres muestra un resumen de lo que cambió entre la versión que usabas antes y la que se ejecuta ahora. Se construye a partir del `CHANGELOG.md` incluido en la imagen — nada se descarga de internet, así que una instalación aislada muestra el mismo resumen que una conectada.

El resumen es por usuario y por versión: cerrarlo marca esa versión como vista solo para tu cuenta. Todo sigue disponible en **/whats-new**, accesible haciendo clic en el número de versión al pie de la barra lateral — cerrar el resumen no pierde nada.

Dos comportamientos que conviene conocer:

- **Una cuenta que nunca ha visto un resumen se marca como al día en silencio.** Activar esta función no recibe a los usuarios existentes con todo el historial; empiezas a ver resúmenes a partir de tu próxima actualización.
- **Los downgrades no muestran nada.** Ejecutar una build más antigua que la registrada no muestra ningún resumen, en vez de anunciar releases que el binario en ejecución no contiene.

En una base de datos de solo lectura no se puede guardar nada, así que el resumen vuelve a aparecer en el siguiente inicio de sesión.

## Actualizar a PRO {#upgrade-to-pro}

!!! tip "Prueba gratis de BunkerWeb PRO"
    Inicia una prueba gratuita de 30 días de BunkerWeb PRO desde el [Panel de BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?language=spanish&utm_campaign=self&utm_source=doc).

Pega tu clave PRO en la página **PRO** de la UI (o precarga `PRO_LICENSE_KEY` para el asistente). Las actualizaciones se descargan en segundo plano por el scheduler; revisa en la UI la caducidad y los límites de servicios tras aplicarlas.

<figure markdown>
  ![PRO upgrade](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>Información de licencia PRO</figcaption>
</figure>

## Traducciones (i18n) {#translations-i18n}

La interfaz web está disponible en varios idiomas gracias a las contribuciones de la comunidad. Las traducciones se almacenan en archivos JSON por idioma (por ejemplo `en.json`, `fr.json`, …). Para cada idioma se documenta claramente si la traducción fue realizada de forma manual o generada mediante IA, así como su estado de revisión.

### Idiomas disponibles y colaboradores

| Idioma               | Locale | Creado por                    | Revisado por             |
| -------------------- | ------ | ----------------------------- | ------------------------ |
| Árabe                | `ar`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Bengalí              | `bn`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Bretón               | `br`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Alemán               | `de`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Inglés               | `en`   | Manual (@TheophileDiot)       | Manual (@TheophileDiot)  |
| Español              | `es`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Francés              | `fr`   | Manual (@TheophileDiot)       | Manual (@TheophileDiot)  |
| Hindi                | `hi`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Italiano             | `it`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Coreano              | `ko`   | Manual (@rayshoo)             | Manual (@rayshoo)        |
| Polaco               | `pl`   | Manual (@tomkolp) vía Weblate | Manual (@tomkolp)        |
| Portugués            | `pt`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Ruso                 | `ru`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Turco                | `tr`   | Manual (@wiseweb-works)       | Manual (@wiseweb-works)  |
| Chino (Tradicional)  | `tw`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Urdu                 | `ur`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Chino (Simplificado) | `zh`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |

> 💡 Algunas traducciones pueden ser parciales. Se recomienda encarecidamente una revisión manual, especialmente para los elementos críticos de la interfaz.

### Cómo contribuir

Las contribuciones de traducción siguen el flujo estándar de contribuciones de BunkerWeb:

1. **Crear o actualizar el archivo de traducción**
   - Copia `src/ui/app/static/locales/en.json` y renómbralo con el código de tu idioma (por ejemplo `de.json`).
   - Traduce **solo los valores**; las claves no deben modificarse.

2. **Registrar el idioma**
   - Añade o actualiza la entrada del idioma en `src/ui/app/lang_config.py` (código del locale, nombre visible, bandera, nombre en inglés).
     Este archivo es la fuente única de verdad para los idiomas compatibles.

3. **Actualizar la documentación y la procedencia**
   - `src/ui/app/static/locales/README.md` → añade el nuevo idioma a la tabla de procedencia (creado por / revisado por).
   - `README.md` → actualiza la documentación general del proyecto para reflejar el nuevo idioma compatible.
   - `docs/web-ui.md` → actualiza la documentación de la interfaz web (esta sección de Traducciones).
   - `docs/*/web-ui.md` → actualiza las versiones traducidas de la documentación de la interfaz web con la misma sección de Traducciones.

4. **Abrir un pull request**
   - Indica claramente si la traducción se realizó de forma manual o con una herramienta de IA.
   - Para cambios importantes (nuevo idioma o actualizaciones grandes), se recomienda abrir primero un issue para su discusión.

Al contribuir con traducciones, ayudas a que BunkerWeb sea accesible para una audiencia internacional más amplia.
