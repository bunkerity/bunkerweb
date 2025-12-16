# API

## Rolle der API

Die BunkerWeb API ist die Steuerungsebene zum Verwalten von Instanzen, Diensten, Sperren, Plugins, Jobs und benutzerdefinierten Konfigurationen. Sie läuft als FastAPI-Anwendung hinter Gunicorn und sollte in einem vertrauenswürdigen Netz bleiben. Interaktive Doku unter `/docs` (oder `<API_ROOT_PATH>/docs`); das OpenAPI-Schema unter `/openapi.json`.

!!! warning "Privat halten"
    Exponieren Sie die API nicht direkt ins Internet. Halten Sie sie in einem internen Netz, beschränken Sie Quell-IPs und verlangen Sie Authentifizierung.

!!! info "Kurzinfos"
    - Health-Endpoints: `GET /ping` und `GET /health`
    - Root-Pfad: setzen Sie `API_ROOT_PATH`, wenn per Reverse Proxy auf einem Unterpfad veröffentlicht, damit Docs und OpenAPI-Links funktionieren
    - Auth ist Pflicht: Biscuit-Tokens, Admin-Basic oder ein override-Bearer-Token
    - IP-Allowlist standardmäßig auf RFC1918-Bereiche (`API_WHITELIST_IPS`); nur deaktivieren, wenn Upstream den Zugang kontrolliert
    - Ratenbegrenzung standardmäßig an; `/auth` hat immer eigenes Limit

## Sicherheits-Checkliste

- Netzwerk: Traffic intern halten; an Loopback oder internes Interface binden und Quell-IPs per `API_WHITELIST_IPS` (standardmäßig aktiv) begrenzen.
- Auth vorhanden: `API_USERNAME`/`API_PASSWORD` (Admin) setzen und bei Bedarf `API_ACL_BOOTSTRAP_FILE` für weitere Nutzer/ACLs; ein Override `API_TOKEN` nur als Notfall behalten.
- Pfad verbergen: beim Reverse Proxy einen nicht offensichtlichen `API_ROOT_PATH` wählen und auf dem Proxy spiegeln.
- Ratenbegrenzung: aktiviert lassen, außer eine andere Schicht erzwingt gleichwertige Limits; `/auth` ist immer begrenzt.
- TLS: am Proxy terminieren oder `API_SSL_ENABLED=yes` mit Zertifikat/Key setzen.

## Ausführen

Wählen Sie die Variante, die zu Ihrer Umgebung passt.

=== "Docker"

    Minimaler Compose-ähnlicher Aufbau mit der API hinter BunkerWeb. Versionen und Passwörter vor Nutzung anpassen.

    ```yaml
    x-bw-env: &bw-env
      # Wir nutzen einen Anker, um dieselben Einstellungen nicht doppelt zu schreiben
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Korrekte IP-Range setzen, damit der Scheduler die Konfiguration an die Instanz senden kann (interne BunkerWeb API)
      # Optional: API-Token setzen und in beiden Containern spiegeln (interne BunkerWeb API)
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Stärkeres Datenbank-Passwort setzen

    services:
      bunkerweb:
        # Name, unter dem die Instanz im Scheduler erscheint
        image: bunkerity/bunkerweb:1.6.7-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Für QUIC / HTTP3
        environment:
          <<: *bw-env # Anker wiederverwenden, um Dopplungen zu vermeiden
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Instanznamen korrekt setzen
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
          - bw-storage:/data # Cache und Backups persistent halten
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.7-rc1
        environment:
          <<: *bw-env
          API_USERNAME: "admin"
          API_PASSWORD: "Str0ng&P@ss!"
          # API_TOKEN: "admin-override-token" # optional
          FORWARDED_ALLOW_IPS: "*" # Vorsicht: nur setzen, wenn sicher nur der Reverse Proxy Zugriff hat
          API_ROOT_PATH: "/"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Größeres max allowed packet, um Probleme mit großen Queries zu vermeiden
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Stärkeres DB-Passwort setzen
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis-Service zur Persistenz von Reports/Bans/Stats
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
            - subnet: 10.20.30.0/24 # Korrekte IP-Range setzen, damit der Scheduler die Konfiguration an die Instanz senden kann
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
      bunkerity/bunkerweb-all-in-one:1.6.7-rc1
    ```

=== "Linux"

    Die DEB/RPM-Pakete bringen `bunkerweb-api.service`, verwaltet über `/usr/share/bunkerweb/scripts/bunkerweb-api.sh`.

    - Aktivieren/Starten: `sudo systemctl enable --now bunkerweb-api.service`
    - Reload: `sudo systemctl reload bunkerweb-api.service`
    - Logs: Journal plus `/var/log/bunkerweb/api.log`
    - Standard-Liste: `127.0.0.1:8888` mit `API_WHITELIST_IPS=127.0.0.1`
    - Konfigurationsdateien: `/etc/bunkerweb/api.env` (bei erstem Start mit kommentierten Defaults erzeugt) und `/etc/bunkerweb/api.yml`
    - Umgebungsquellen: `api.env`, `variables.env`, `/run/secrets/<VAR>` und dann exportiert in den Gunicorn-Prozess

    Bearbeiten Sie `/etc/bunkerweb/api.env`, um `API_USERNAME`/`API_PASSWORD`, Allowlist, TLS, Ratenlimits oder `API_ROOT_PATH` zu setzen, dann `systemctl reload bunkerweb-api`.

## Authentifizierung und Autorisierung

- `/auth` gibt Biscuit-Tokens aus. Zugangsdaten können per Basic Auth, Formularfeldern, JSON-Body oder Bearer-Header gleich `API_TOKEN` (Admin-Override) kommen.
- Admins können geschützte Routen auch direkt mit HTTP Basic aufrufen (kein Biscuit nötig).
- Stimmt der Bearer-Token mit `API_TOKEN` überein, besteht voller/Admin-Zugriff. Sonst erzwingt der Biscuit-Guard ACLs.
- Biscuit-Payload enthält Benutzer, Zeit, Client-IP, Host, Version, eine grobe `role("api_user", ["read", "write"])` und entweder `admin(true)` oder feingranulare `api_perm(resource_type, resource_id|*, permission)`.
- TTL: `API_BISCUIT_TTL_SECONDS` (0/off deaktiviert Ablauf). Schlüssel liegen unter `/var/lib/bunkerweb/.api_biscuit_private_key` und `.api_biscuit_public_key`, sofern nicht via `BISCUIT_PRIVATE_KEY`/`BISCUIT_PUBLIC_KEY` gesetzt.
- Auth-Endpoints sind nur verfügbar, wenn mindestens ein API-User in der Datenbank existiert.

!!! tip "Auth-Quickstart"
    1. `API_USERNAME` und `API_PASSWORD` setzen (und `OVERRIDE_API_CREDS=yes`, wenn neu seeds nötig sind).
    2. `POST /auth` mit Basic Auth aufrufen; `.token` aus der Antwort lesen.
    3. `Authorization: Bearer <token>` bei folgenden Aufrufen nutzen.

## Berechtigungen und ACL

- Grobe Rolle: GET/HEAD/OPTIONS brauchen `read`; schreibende Verben brauchen `write`.
- Feingranulare ACL greift, wenn Routen Berechtigungen deklarieren; `admin(true)` umgeht Checks.
- Ressourcentypen: `instances`, `global_settings`, `services`, `configs`, `plugins`, `cache`, `bans`, `jobs`.
- Berechtigungsnamen:
  - `instances_*`: `instances_read`, `instances_update`, `instances_delete`, `instances_create`, `instances_execute`
  - `global_settings_*`: `global_settings_read`, `global_settings_update`
  - `services`: `service_read`, `service_create`, `service_update`, `service_delete`, `service_convert`, `service_export`
  - `configs`: `configs_read`, `config_read`, `config_create`, `config_update`, `config_delete`
  - `plugins`: `plugin_read`, `plugin_create`, `plugin_delete`
  - `cache`: `cache_read`, `cache_delete`
  - `bans`: `ban_read`, `ban_update`, `ban_delete`, `ban_created`
  - `jobs`: `job_read`, `job_run`
- `resource_id` ist meist die zweite Pfadkomponente (z. B. `/services/{id}`); "*" gewährt globalen Zugriff.
- Nicht-Admin-Nutzer und Grants per `API_ACL_BOOTSTRAP_FILE` oder gemounteter `/var/lib/bunkerweb/api_acl_bootstrap.json` bootstrappen. Passwörter dürfen Klartext oder bcrypt-Hashes sein.

??? example "Minimales ACL-Bootstrap"
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

## Ratenbegrenzung

Standardmäßig aktiv mit zwei Strings: `API_RATE_LIMIT` (global, Standard `100r/m`) und `API_RATE_LIMIT_AUTH` (Standard `10r/m` oder `off`). Raten akzeptieren NGINX-Notation (`3r/s`, `40r/m`, `200r/h`) oder ausgeschriebene Formen (`100/minute`, `200 per 30 minutes`). Konfigurieren über:

- `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`
- `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_HEADERS_ENABLED`
- `API_RATE_LIMIT_RULES` (CSV/JSON/YAML-String oder Dateipfad)
- `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`
- Speicherung: In-Memory oder Redis/Valkey bei `USE_REDIS=yes` plus `REDIS_*` (Sentinel unterstützt).

Limiter-Strategien (bereitgestellt von `limits`):

- `fixed-window` (Standard): Bucket wird an jeder Intervallgrenze zurückgesetzt; am günstigsten und ausreichend für grobe Limits.
- `moving-window`: echtes gleitendes Fenster mit präzisen Zeitstempeln; glatter, aber speicherintensiver in den Operationen.
- `sliding-window-counter`: Hybrid, der mit gewichteten Zählungen des vorherigen Fensters glättet; leichter als moving, glatter als fixed.

Mehr Details und Abwägungen: [https://limits.readthedocs.io/en/stable/strategies.html](https://limits.readthedocs.io/en/stable/strategies.html)

??? example "Inline-CSV"
    ```
    API_RATE_LIMIT_RULES='POST /auth 10r/m, GET /instances* 200r/m, POST|PATCH /services* 40r/m'
    ```

??? example "YAML-Datei"
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

## Konfigurationsquellen und Priorität

1. Umgebungsvariablen (inkl. Docker/Compose `environment:`)
2. Secrets in `/run/secrets/<VAR>` (Docker)
3. YAML unter `/etc/bunkerweb/api.yml`
4. Env-Datei unter `/etc/bunkerweb/api.env`
5. Eingebaute Defaults

### Laufzeit & Zeitzone

| Setting | Beschreibung                                                                                    | Akzeptierte Werte                                 | Standard                                      |
| ------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------- | --------------------------------------------- |
| `TZ`    | Zeitzone für API-Logs und zeitbasierte Claims (z. B. Biscuit-TTL-Auswertung und Log-Zeitstempel) | TZ-Datenbank-Name (z. B. `UTC`, `Europe/Paris`)   | unset (Container-Default, meist UTC)          |

Docs oder Schema deaktivieren, indem die zugehörigen URLs auf `off|disabled|none|false|0` gesetzt werden. Setzen Sie `API_SSL_ENABLED=yes` mit `API_SSL_CERTFILE` und `API_SSL_KEYFILE`, um TLS direkt in der API zu terminieren. Beim Reverse-Proxy `API_FORWARDED_ALLOW_IPS` auf die Proxy-IPs setzen, damit Gunicorn `X-Forwarded-*` vertraut.

### Konfigurationsreferenz (Power User)

#### Oberfläche & Docs

| Setting                                            | Beschreibung                                                                               | Akzeptierte Werte           | Standard                           |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------ | --------------------------- | ---------------------------------- |
| `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL` | Pfade für Swagger, ReDoc und OpenAPI; auf `off/disabled/none/false/0` setzen zum Deaktivieren | Pfad oder `off`             | `/docs`, `/redoc`, `/openapi.json` |
| `API_ROOT_PATH`                                    | Mount-Prefix bei Reverse Proxy                                                             | Pfad (z. B. `/api`)         | leer                               |
| `API_FORWARDED_ALLOW_IPS`                          | Vertrauenswürdige Proxy-IPs für `X-Forwarded-*`                                            | Kommagetrennte IPs/CIDRs    | `127.0.0.1` (Package-Default)      |

#### Auth, ACL, Biscuit

| Setting                                     | Beschreibung                                 | Akzeptierte Werte                                                  | Standard                 |
| ------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------ | ------------------------ |
| `API_USERNAME`, `API_PASSWORD`              | Bootstrap-Admin-Nutzer                        | Strings; starkes Passwort außerhalb Debug erforderlich              | unset                    |
| `OVERRIDE_API_CREDS`                        | Admin-Creds beim Start erneut anwenden        | `yes/no/on/off/true/false/0/1`                                      | `no`                     |
| `API_TOKEN`                                 | Admin-Override-Bearer-Token                   | Opaquer String                                                     | unset                    |
| `API_ACL_BOOTSTRAP_FILE`                    | Pfad zu JSON für Nutzer/Berechtigungen        | Dateipfad oder gemountetes `/var/lib/bunkerweb/api_acl_bootstrap.json` | unset                    |
| `BISCUIT_PRIVATE_KEY`, `BISCUIT_PUBLIC_KEY` | Biscuit-Schlüssel (Hex), falls keine Dateien  | Hex-Strings                                                       | auto-generiert/persistent |
| `API_BISCUIT_TTL_SECONDS`                   | Token-Lebensdauer; `0/off` deaktiviert Ablauf | Integer Sekunden oder `off/disabled`                                | `3600`                   |
| `CHECK_PRIVATE_IP`                          | Biscuit an Client-IP binden (außer private)   | `yes/no/on/off/true/false/0/1`                                      | `yes`                    |

#### Allowlist

| Setting                 | Beschreibung                        | Akzeptierte Werte                | Standard                |
| ----------------------- | ----------------------------------- | -------------------------------- | ----------------------- |
| `API_WHITELIST_ENABLED` | IP-Allowlist-Middleware umschalten  | `yes/no/on/off/true/false/0/1`   | `yes`                   |
| `API_WHITELIST_IPS`     | Leer- oder kommagetrennte IPs/CIDRs | IPs/CIDRs                        | RFC1918-Bereiche im Code |

#### Ratenbegrenzung

| Setting                          | Beschreibung                                   | Akzeptierte Werte                                           | Standard       |
| -------------------------------- | ----------------------------------------------- | ----------------------------------------------------------- | -------------- |
| `API_RATE_LIMIT`                 | Globales Limit (NGINX-String)                   | `3r/s`, `100/minute`, `500 per 30 minutes`                  | `100r/m`       |
| `API_RATE_LIMIT_AUTH`            | `/auth`-Limit (oder `off`)                      | wie oben oder `off/disabled/none/false/0`                   | `10r/m`        |
| `API_RATE_LIMIT_ENABLED`         | Limiter aktivieren                              | `yes/no/on/off/true/false/0/1`                              | `yes`          |
| `API_RATE_LIMIT_HEADERS_ENABLED` | Rate-Limit-Header injizieren                    | wie oben                                                   | `yes`          |
| `API_RATE_LIMIT_RULES`           | Pfadregeln (CSV/JSON/YAML oder Dateipfad)       | String oder Pfad                                            | unset          |
| `API_RATE_LIMIT_STRATEGY`        | Algorithmus                                    | `fixed-window`, `moving-window`, `sliding-window-counter`   | `fixed-window` |
| `API_RATE_LIMIT_KEY`             | Schlüssel-Selektion                             | `ip`, `header:<Name>`                                       | `ip`           |
| `API_RATE_LIMIT_EXEMPT_IPS`      | Limits für diese IPs/CIDRs überspringen         | Leer- oder kommagetrennt                                    | unset          |
| `API_RATE_LIMIT_STORAGE_OPTIONS` | JSON, das in die Storage-Konfig gemerged wird   | JSON-String                                                 | unset          |

#### Redis/Valkey (für Rate Limits)

| Setting                                              | Beschreibung              | Akzeptierte Werte                | Standard            |
| ---------------------------------------------------- | ------------------------ | -------------------------------- | ------------------- |
| `USE_REDIS`                                          | Redis-Backend aktivieren | `yes/no/on/off/true/false/0/1`   | `no`                |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DATABASE`         | Verbindungsdetails       | Host, int, int                   | unset, `6379`, `0`  |
| `REDIS_USERNAME`, `REDIS_PASSWORD`                   | Auth                     | Strings                          | unset               |
| `REDIS_SSL`, `REDIS_SSL_VERIFY`                      | TLS und Verifizierung    | `yes/no/on/off/true/false/0/1`   | `no`, `yes`         |
| `REDIS_TIMEOUT`                                      | Timeout (ms)             | Integer                          | `1000`              |
| `REDIS_KEEPALIVE_POOL`                               | Pool-Keepalive           | Integer                          | `10`                |
| `REDIS_SENTINEL_HOSTS`                               | Sentinel-Hosts           | Leerzeichen-getrennte `host:port` | unset               |
| `REDIS_SENTINEL_MASTER`                              | Sentinel-Mastername      | String                           | unset               |
| `REDIS_SENTINEL_USERNAME`, `REDIS_SENTINEL_PASSWORD` | Sentinel-Auth            | Strings                          | unset               |

!!! info "DB-Redis"
    Wenn Redis/Valkey-Einstellungen in der BunkerWeb-Datenbank vorhanden sind, nutzt die API sie automatisch fürs Rate Limiting, auch ohne `USE_REDIS` in der Umgebung. Bei Bedarf per Umgebungsvariablen überschreiben.

#### Listener & TLS

| Setting                               | Beschreibung                     | Akzeptierte Werte                | Standard                              |
| ------------------------------------- | -------------------------------- | -------------------------------- | ------------------------------------- |
| `API_LISTEN_ADDR`, `API_LISTEN_PORT`  | Bind-Adresse/Port für Gunicorn   | IP oder Hostname, int            | `127.0.0.1`, `8888` (Package-Skript)  |
| `API_SSL_ENABLED`                     | TLS in der API aktivieren        | `yes/no/on/off/true/false/0/1`   | `no`                                  |
| `API_SSL_CERTFILE`, `API_SSL_KEYFILE` | PEM-Zertifikat und -Schlüssel    | Dateipfade                       | unset                                 |
| `API_SSL_CA_CERTS`                    | Optionale CA/Chain               | Dateipfad                        | unset                                 |

#### Logging & Laufzeit (Package-Defaults)

| Setting                         | Beschreibung                                                                       | Akzeptierte Werte                                 | Standard                                                            |
| ------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Basis-Log-Level / Override                                                          | `debug`, `info`, `warning`, `error`, `critical`   | `info`                                                             |
| `LOG_TYPES`                     | Ziele                                                                               | Leerzeichen-getrennt `stderr`/`file`/`syslog`     | `stderr`                                                           |
| `LOG_FILE_PATH`                 | Log-Dateipfad (bei `LOG_TYPES` mit `file` oder `CAPTURE_OUTPUT=yes` genutzt)        | Dateipfad                                         | `/var/log/bunkerweb/api.log`, falls file/capture aktiv, sonst unset |
| `LOG_SYSLOG_ADDRESS`            | Syslog-Ziel (`udp://host:514`, `tcp://host:514`, Socket)                           | Host:Port, Protokoll-präfixter Host oder Socket   | unset                                                              |
| `LOG_SYSLOG_TAG`                | Syslog-Tag                                                                          | String                                            | `bw-api`                                                           |
| `MAX_WORKERS`, `MAX_THREADS`    | Gunicorn-Worker/Threads                                                             | Integer oder unset für Auto                       | unset                                                              |
| `CAPTURE_OUTPUT`                | Gunicorn stdout/stderr in die konfigurierten Handler umlenken                      | `yes` oder `no`                                   | `no`                                                               |

## API-Fläche (Capabilities)

- **Core**
  - `GET /ping`, `GET /health`: Liveness-Checks für die API selbst.
- **Auth**
  - `POST /auth`: Biscuit-Tokens ausgeben; akzeptiert Basic, Formular, JSON oder Bearer-Override bei passendem `API_TOKEN`.
- **Instances**
  - `GET /instances`: Instanzen mit Erstellungs-/Last-seen-Metadaten auflisten.
  - `POST /instances`: Instanz registrieren (hostname/port/server_name/method).
  - `GET/PATCH/DELETE /instances/{hostname}`: inspizieren, veränderbare Felder updaten oder API-gemanagte Instanzen löschen.
  - `DELETE /instances`: API-gemanagte Instanzen en masse löschen; Einträge außerhalb der API werden übersprungen.
  - Health/Aktionen: `GET /instances/ping`, `GET /instances/{hostname}/ping`, `POST /instances/reload?test=yes|no`, `POST /instances/{hostname}/reload`, `POST /instances/stop`, `POST /instances/{hostname}/stop`.
- **Global settings**
  - `GET /global_settings`: standardmäßig nur Nicht-Defaults; `full=true` für alle Settings, `methods=true` für Herkunft.
  - `PATCH /global_settings`: API-eigene Globals upserten; read-only Keys werden abgelehnt.
- **Services**
  - `GET /services`: Dienste auflisten (Drafts standardmäßig enthalten).
  - `GET /services/{service}`: Nicht-Defaults oder volle Config holen (`full=true`); `methods=true` fügt Herkunft hinzu.
  - `POST /services`: Dienst anlegen (Draft oder online), Variablen setzen und `SERVER_NAME`-Roster atomar aktualisieren.
  - `PATCH /services/{service}`: umbenennen, Variablen updaten, Draft toggeln.
  - `DELETE /services/{service}`: Dienst und abgeleitete Config-Keys entfernen.
  - `POST /services/{service}/convert?convert_to=online|draft`: Draft/Online schnell umschalten.
- **Custom configs**
  - `GET /configs`: Snippets auflisten (Default-Service `global`); `with_data=true` bettet druckbaren Inhalt ein.
  - `POST /configs`, `POST /configs/upload`: Snippets via JSON oder File-Upload erstellen.
  - `GET /configs/{service}/{type}/{name}`: Snippet holen; `with_data=true` für Inhalt.
  - `PATCH /configs/{service}/{type}/{name}`, `PATCH .../upload`: API-gemanagte Snippets aktualisieren oder verschieben.
  - `DELETE /configs` oder `DELETE /configs/{service}/{type}/{name}`: API-gemanagte Snippets löschen; template-gemanagte werden übersprungen.
  - Unterstützte Typen: `http`, `server_http`, `default_server_http`, `modsec`, `modsec_crs`, `stream`, `server_stream`, CRS/Plugin-Hooks.
- **Bans**
  - `GET /bans`: aktive Bans aus Instanzen aggregieren.
  - `POST /bans` oder `/bans/ban`: einen oder mehrere Bans anwenden; Payload darf Objekt, Array oder JSON-String sein.
  - `POST /bans/unban` oder `DELETE /bans`: Bans global oder pro Service entfernen.
- **Plugins (UI-Plugins)**
  - `GET /plugins`: Plugins auflisten; `with_data=true` enthält Paket-Bytes, sofern verfügbar.
  - `POST /plugins/upload`: UI-Plugins aus `.zip`, `.tar.gz`, `.tar.xz` installieren.
  - `DELETE /plugins/{id}`: Plugin per ID entfernen.
- **Cache (Job-Artefakte)**
  - `GET /cache`: Cache-Dateien mit Filtern (`service`, `plugin`, `job_name`) auflisten; `with_data=true` bettet druckbaren Inhalt ein.
  - `GET /cache/{service}/{plugin}/{job}/{file}`: spezifische Cache-Datei holen/herunterladen (`download=true`).
  - `DELETE /cache` oder `DELETE /cache/{service}/{plugin}/{job}/{file}`: Cache-Dateien löschen und Scheduler benachrichtigen.
- **Jobs**
  - `GET /jobs`: Jobs, Zeitpläne und Cache-Zusammenfassungen auflisten.
  - `POST /jobs/run`: Plugins als geändert markieren, um zugehörige Jobs auszulösen.

## Betriebsverhalten

- Fehlermeldungen sind normalisiert zu `{"status": "error", "message": "..."}` mit passenden HTTP-Statuscodes.
- Schreiboperationen landen in der gemeinsamen Datenbank; Instanzen übernehmen Änderungen per Scheduler-Sync oder nach einem Reload.
- `API_ROOT_PATH` muss dem Reverse-Proxy-Pfad entsprechen, damit `/docs` und Links funktionieren.
- Start schlägt fehl, wenn kein Auth-Pfad existiert (keine Biscuit-Schlüssel, kein Admin-User und kein `API_TOKEN`); Fehler werden in `/var/tmp/bunkerweb/api.error` geloggt.
