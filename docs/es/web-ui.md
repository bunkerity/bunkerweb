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
    - Dependencias: comparte la base de datos de BunkerWeb y habla con la API para recargar, bloquear o consultar instancias

## Checklist de seguridad

- Ejecuta la UI detrás de BunkerWeb en una red interna; usa un `REVERSE_PROXY_URL` difícil de adivinar y limita IPs de origen.
- Establece `ADMIN_USERNAME` / `ADMIN_PASSWORD` fuertes; usa `OVERRIDE_ADMIN_CREDS=yes` solo cuando quieras forzar un reseteo.
- Proporciona `TOTP_ENCRYPTION_KEYS` y habilita TOTP en cuentas admin; guarda los códigos de recuperación.
- Usa TLS (terminado en BunkerWeb o `UI_SSL_ENABLED=yes` con rutas de cert/clave); fija `UI_FORWARDED_ALLOW_IPS` a proxies de confianza.
- Persiste secretos: monta `/var/lib/bunkerweb` para conservar `FLASK_SECRET`, llaves Biscuit y material TOTP entre reinicios.
- Mantén `CHECK_PRIVATE_IP=yes` (por defecto) para ligar sesiones a la IP; deja `ALWAYS_REMEMBER=no` salvo que requieras cookies largas.
- Asegura que `/var/log/bunkerweb` sea legible por UID/GID 101 (o el UID mapeado en rootless) para que la UI pueda leer logs.

## Puesta en marcha

La UI requiere scheduler/API de BunkerWeb/redis/base de datos accesibles.

=== "Inicio rápido (asistente)"

    Usa las imágenes publicadas y el layout del [guía rápida](quickstart-guide.md#__tabbed_1_3) para levantar el stack, luego completa el asistente en el navegador.

    ```bash
    docker compose -f https://raw.githubusercontent.com/bunkerity/bunkerweb/v1.6.7-rc1/misc/integrations/docker-compose.yml up -d
    ```

    Visita el hostname del scheduler (ej. `https://www.example.com/changeme`) y ejecuta el asistente `/setup` para configurar la UI, el scheduler y la instancia.

=== "Avanzado (entorno presembrado)"

    Omite el asistente precargando credenciales y red; ejemplo Compose con sidecar syslog:

    ```yaml
    x-service-env: &service-env
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"
      LOG_TYPES: "stderr syslog"
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp"
        environment:
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        restart: "unless-stopped"
        networks: [bw-universe, bw-services]

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
        environment:
          <<: *service-env
          BUNKERWEB_INSTANCES: "bunkerweb"
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
          ACCESS_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb_access"
          ERROR_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb"
          DISABLE_DEFAULT_SERVER: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme"
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
        volumes:
          - bw-storage:/data
        restart: "unless-stopped"
        networks: [bw-universe, bw-db]

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.7-rc1
        environment:
          <<: *service-env
          ADMIN_USERNAME: "admin"
          ADMIN_PASSWORD: "Str0ng&P@ss!"
          TOTP_ENCRYPTION_KEYS: "set-me"
          UI_FORWARDED_ALLOW_IPS: "10.20.30.0/24"
        volumes:
          - bw-logs:/var/log/bunkerweb
        restart: "unless-stopped"
        networks: [bw-universe, bw-db]

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
        restart: "unless-stopped"
        networks: [bw-db]

      bw-syslog:
        image: balabit/syslog-ng:4.10.2
        volumes:
          - bw-logs:/var/log/bunkerweb
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf
        restart: "unless-stopped"
        networks: [bw-universe]

    volumes:
      bw-data:
      bw-storage:
      bw-logs:
      bw-lib:

    networks:
      bw-universe:
        ipam:
          config: [{ subnet: 10.20.30.0/24 }]
      bw-services:
      bw-db:
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
- Cabeceras de proxy: `UI_FORWARDED_ALLOW_IPS` por defecto `*`; en Linux ajústalo a las IP de tu proxy para endurecer.
- Secretos y estado: `/var/lib/bunkerweb` guarda `FLASK_SECRET`, llaves Biscuit y material TOTP. Móntalo en Docker; en Linux lo gestiona el paquete.
- Logs: `/var/log/bunkerweb` debe ser legible por UID/GID 101 (o el UID mapeado en rootless). Los paquetes crean la ruta; los contenedores necesitan un volumen con permisos adecuados.
- Asistente: easy-install en Linux arranca la UI y el asistente automáticamente; en Docker se accede al asistente vía la URL reverse-proxificada salvo que preselecciones variables de entorno.

## Autenticación y sesiones

- Cuenta admin: créala con el asistente o con `ADMIN_USERNAME` / `ADMIN_PASSWORD`. La contraseña debe incluir minúsculas, mayúsculas, dígito y carácter especial. `OVERRIDE_ADMIN_CREDS=yes` fuerza la resiembra aunque ya exista.
- Roles: `admin`, `writer` y `reader` se crean automáticamente; las cuentas viven en la base de datos.
- Secretos: `FLASK_SECRET` se guarda en `/var/lib/bunkerweb/.flask_secret`; las llaves Biscuit al lado, opcionalmente vía `BISCUIT_PUBLIC_KEY` / `BISCUIT_PRIVATE_KEY`.
- 2FA: habilita TOTP con `TOTP_ENCRYPTION_KEYS` (separadas por espacios o JSON). Genera una llave:

    ```bash
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    Los códigos de recuperación se muestran una sola vez; si pierdes las llaves de cifrado, se eliminan los secretos TOTP almacenados.
- Sesiones: duración por defecto 12 h (`SESSION_LIFETIME_HOURS`). Sesiones fijadas a IP y User-Agent; `CHECK_PRIVATE_IP=no` relaja el control de IP solo en rangos privados. `ALWAYS_REMEMBER=yes` fuerza cookies persistentes.
- Ajusta `PROXY_NUMBERS` si varios proxies añaden `X-Forwarded-*`.

## Fuentes de configuración y prioridad

1. Variables de entorno (incl. `environment:` de Docker/Compose)
2. Secrets en `/run/secrets/<VAR>` (Docker)
3. Archivo env `/etc/bunkerweb/ui.env` (paquetes Linux)
4. Valores por defecto integrados

## Referencia de configuración

### Tiempo de ejecución y zona horaria

| Ajuste | Descripción | Valores aceptados | Predeterminado |
| --- | --- | --- | --- |
| `TZ` | Zona horaria para logs de la UI y acciones programadas | Nombre TZ (ej. `UTC`, `Europe/Madrid`) | sin definir (normalmente UTC en contenedor) |

### Listener y TLS

| Ajuste | Descripción | Valores aceptados | Predeterminado |
| --- | --- | --- | --- |
| `UI_LISTEN_ADDR` | Dirección de escucha de la UI | IP o hostname | `0.0.0.0` (Docker) / `127.0.0.1` (paquete) |
| `UI_LISTEN_PORT` | Puerto de escucha de la UI | Entero | `7000` |
| `LISTEN_ADDR`, `LISTEN_PORT` | Alternativas si faltan vars de UI | IP/hostname, entero | `0.0.0.0`, `7000` |
| `UI_SSL_ENABLED` | Habilitar TLS en el contenedor UI | `yes` o `no` | `no` |
| `UI_SSL_CERTFILE`, `UI_SSL_KEYFILE` | Rutas de cert/clave PEM con TLS | Rutas de archivo | sin definir |
| `UI_SSL_CA_CERTS` | CA/cadena opcional | Ruta de archivo | sin definir |
| `UI_FORWARDED_ALLOW_IPS` | Proxies de confianza para `X-Forwarded-*` | IPs/CIDRs separados por espacio/coma | `*` |

### Auth, sesiones y cookies

| Ajuste | Descripción | Valores aceptados | Predeterminado |
| --- | --- | --- | --- |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Inicializar cuenta admin (política de contraseña) | Cadenas | sin definir |
| `OVERRIDE_ADMIN_CREDS` | Forzar actualización de credenciales admin desde env | `yes` o `no` | `no` |
| `FLASK_SECRET` | Secreto de firma de sesión (persistido en `/var/lib/bunkerweb/.flask_secret`) | Cadena hex/base64/opaca | generado automáticamente |
| `TOTP_ENCRYPTION_KEYS` (`TOTP_SECRETS`) | Claves para cifrar TOTP (espacio o JSON) | Cadenas / JSON | generadas si faltan |
| `BISCUIT_PUBLIC_KEY`, `BISCUIT_PRIVATE_KEY` | Claves Biscuit (hex) para tokens de UI | Cadenas hex | autogeneradas y guardadas |
| `SESSION_LIFETIME_HOURS` | Duración de sesión | Número (horas) | `12` |
| `ALWAYS_REMEMBER` | Activar siempre “remember me” | `yes` o `no` | `no` |
| `CHECK_PRIVATE_IP` | Ligar sesión a IP (relaja en redes privadas con `no`) | `yes` o `no` | `yes` |
| `PROXY_NUMBERS` | Saltos de proxy confiables para `X-Forwarded-*` | Entero | `1` |

### Logging

| Ajuste | Descripción | Valores aceptados | Predeterminado |
| --- | --- | --- | --- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Nivel base / override | `debug`, `info`, `warning`, `error`, `critical` | `info` |
| `LOG_TYPES` | Destinos | `stderr`/`file`/`syslog` separados por espacio | `stderr` |
| `LOG_FILE_PATH` | Ruta para logs a archivo (`file` o `CAPTURE_OUTPUT=yes`) | Ruta de archivo | `/var/log/bunkerweb/ui.log` si file/capture |
| `CAPTURE_OUTPUT` | Enviar stdout/stderr de Gunicorn a handlers | `yes` o `no` | `no` |
| `LOG_SYSLOG_ADDRESS` | Destino syslog (`udp://host:514`, `tcp://host:514`, socket) | Host:puerto / URL / socket | sin definir |
| `LOG_SYSLOG_TAG` | Tag/ident syslog | Cadena | `bw-ui` |

### Runtime misceláneo

| Ajuste | Descripción | Valores aceptados | Predeterminado |
| --- | --- | --- | --- |
| `MAX_WORKERS`, `MAX_THREADS` | Workers/hilos de Gunicorn | Entero | `cpu_count()-1` (mín 1), `workers*2` |
| `ENABLE_HEALTHCHECK` | Exponer `GET /healthcheck` | `yes` o `no` | `no` |
| `FORWARDED_ALLOW_IPS` | Alias obsoleto para lista de proxies | IPs/CIDRs | `*` |
| `DISABLE_CONFIGURATION_TESTING` | Saltar reloads de prueba al aplicar config | `yes` o `no` | `no` |
| `IGNORE_REGEX_CHECK` | Omitir validación regex de ajustes | `yes` o `no` | `no` |

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

## Actualizar a PRO {#upgrade-to-pro}

!!! tip "Prueba gratis de BunkerWeb PRO"
    Usa el código `freetrial` en el [Panel BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?language=spanish&utm_campaign=self&utm_source=doc) para un mes de prueba.

Pega tu clave PRO en la página **PRO** de la UI (o precarga `PRO_LICENSE_KEY` para el asistente). Las actualizaciones se descargan en segundo plano por el scheduler; revisa en la UI la caducidad y los límites de servicios tras aplicarlas.

<figure markdown>
  ![PRO upgrade](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>Información de licencia PRO</figcaption>
</figure>
