# API

## Übersicht

Die BunkerWeb API ist die Steuerungsebene, die zur programmatischen Verwaltung von BunkerWeb-Instanzen verwendet wird: Auflisten und Verwalten von Instanzen, Neuladen/Stoppen, Handhabung von Sperren, Plugins, Jobs, Konfigurationen und mehr. Sie stellt eine dokumentierte FastAPI-Anwendung mit starker Authentifizierung, Autorisierung und Ratenbegrenzung bereit.

Öffnen Sie die interaktive Dokumentation unter `/docs` (oder `<root_path>/docs`, wenn Sie `API_ROOT_PATH` gesetzt haben). Das OpenAPI-Schema ist unter `/openapi.json` verfügbar.

!!! warning "Sicherheit"
    Die API ist eine privilegierte Steuerungsebene. Setzen Sie sie nicht ohne zusätzliche Schutzmaßnahmen im öffentlichen Internet aus.

    Beschränken Sie mindestens die Quell-IPs (`API_WHITELIST_IPS`), aktivieren Sie die Authentifizierung (`API_TOKEN` oder API-Benutzer + Biscuit) und erwägen Sie, sie hinter BunkerWeb mit einem nicht erratbaren Pfad und zusätzlichen Zugriffskontrollen zu platzieren.

## Voraussetzungen

Der API-Dienst benötigt Zugriff auf die BunkerWeb-Datenbank (`DATABASE_URI`). Er wird in der Regel zusammen mit dem Scheduler und optional der Web-UI bereitgestellt. Die empfohlene Einrichtung besteht darin, BunkerWeb als Reverse-Proxy davor zu schalten und die API in einem internen Netzwerk zu isolieren.

Siehe den Schnellstart-Assistenten und die Architekturhinweise im [Schnellstart-Leitfaden](quickstart-guide.md).

## Highlights

- Instanz-bewusst: sendet operative Aktionen an entdeckte Instanzen.
- Starke Authentifizierung: Basic für Admins, Bearer-Admin-Überschreibung oder Biscuit-ACL für feingranulare Berechtigungen.
- IP-Zulassungsliste und flexible Ratenbegrenzung pro Route.
- Standardmäßige Zustands-/Bereitschaftssignale und Sicherheitsprüfungen beim Start.

## Compose-Vorlagen

=== "Docker"

    Reverse-Proxy der API unter `/api` mit BunkerWeb.

    ```yaml
    x-bw-env: &bw-env
      # Geteilte Zulassungsliste der Instanz-Steuerungsebene für BunkerWeb/Scheduler
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc4
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
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc4
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb"  # Entspricht dem Dienstnamen der Instanz
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"
          DISABLE_DEFAULT_SERVER: "yes"
          # Reverse-Proxy der API auf /api
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
        image: bunkerity/bunkerweb-api:1.6.5-rc4
        environment:
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"  # Verwenden Sie ein starkes Passwort
          API_WHITELIST_IPS: "127.0.0.0/8 10.20.30.0/24"                      # API-Zulassungsliste
          API_TOKEN: "secret"                                                 # Optionaler Admin-Überschreibungstoken
          API_ROOT_PATH: "/api"                                               # Entspricht dem Reverse-Proxy-Pfad
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Probleme mit großen Abfragen vermeiden
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme"  # Verwenden Sie ein starkes Passwort
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

    Dasselbe wie oben, aber unter Nutzung des Autoconf-Dienstes, um Dienste automatisch zu entdecken und zu konfigurieren. Die API wird unter `/api` über Labels auf dem API-Container bereitgestellt.

    ```yaml
    x-api-env: &api-env
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"  # Verwenden Sie ein starkes Passwort

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc4
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
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc4
        environment:
          <<: *api-env
          BUNKERWEB_INSTANCES: ""    # Von Autoconf entdeckt
          SERVER_NAME: ""            # Über Labels gefüllt
          MULTISITE: "yes"           # Mit Autoconf obligatorisch
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        volumes:
          - bw-storage:/data
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.5-rc4
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
        image: bunkerity/bunkerweb-api:1.6.5-rc4
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

!!! warning "Reverse-Proxy-Pfad"
    Halten Sie den API-Pfad unerratbar und kombinieren Sie ihn mit der API-Zulassungsliste und Authentifizierung.

    Wenn Sie bereits eine andere App auf demselben Servernamen mit einer Vorlage (z. B. `USE_TEMPLATE`) bereitstellen, bevorzugen Sie einen separaten Hostnamen für die API, um Konflikte zu vermeiden.

### All-in-One

Wenn Sie das All-in-One-Image verwenden, kann die API durch Setzen von `SERVICE_API=yes` aktiviert werden:

```bash
docker run -d \
  --name bunkerweb-aio \
  -e SERVICE_API=yes \
  -e API_WHITELIST_IPS="127.0.0.0/8" \
  -p 80:8080/tcp -p 443:8443/tcp -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.5-rc4
```

## Authentifizierung

Unterstützte Wege zur Authentifizierung von Anfragen:

- Basic admin: Wenn Anmeldeinformationen zu einem Admin-API-Benutzer gehören, akzeptieren geschützte Endpunkte `Authorization: Basic <base64(username:password)>`.
- Admin Bearer override: Wenn `API_TOKEN` konfiguriert ist, gewährt `Authorization: Bearer <API_TOKEN>` vollen Zugriff.
- Biscuit-Token (empfohlen): Erhalten Sie ein Token von `POST /auth` unter Verwendung von Basic-Anmeldeinformationen oder einem JSON-/Formular-Body, der `username` und `password` enthält. Verwenden Sie das zurückgegebene Token als `Authorization: Bearer <token>` bei nachfolgenden Aufrufen.

Beispiel: Holen Sie sich ein Biscuit, listen Sie Instanzen auf und laden Sie dann alle Instanzen neu.

```bash
# 1) Holen Sie sich ein Biscuit-Token mit Admin-Anmeldeinformationen
TOKEN=$(curl -s -X POST -u admin:changeme http://api.example.com/auth | jq -r .token)

# 2) Instanzen auflisten
curl -H "Authorization: Bearer $TOKEN" http://api.example.com/instances

# 3) Konfiguration über alle Instanzen hinweg neu laden (kein Test)
curl -X POST -H "Authorization: Bearer $TOKEN" \
     "http://api.example.com/instances/reload?test=no"
```

### Biscuit Fakten und Prüfungen

Tokens enthalten Fakten wie `user(<username>)`, `client_ip(<ip>)`, `domain(<host>)` und eine grobe Rolle `role("api_user", ["read", "write"])`, die von den DB-Berechtigungen abgeleitet ist. Admins enthalten `admin(true)`, während Nicht-Admins feingranulare Fakten wie `api_perm(<resource_type>, <resource_id|*>, <permission>)` tragen.

Die Autorisierung ordnet die Route/Methode den erforderlichen Berechtigungen zu; `admin(true)` wird immer akzeptiert. Wenn feingranulare Fakten fehlen, greift der Wächter auf die grobe Rolle zurück: GET/HEAD/OPTIONS erfordern `read`; Schreibverben erfordern `write`.

Schlüssel werden unter `/var/lib/bunkerweb/.api_biscuit_private_key` und `/var/lib/bunkerweb/.api_biscuit_public_key` gespeichert. Sie können `BISCUIT_PUBLIC_KEY`/`BISCUIT_PRIVATE_KEY` auch über Umgebungsvariablen bereitstellen; wenn weder Dateien noch Umgebungsvariablen gesetzt sind, generiert die API beim Start ein Schlüsselpaar und speichert es sicher.

## Berechtigungen (ACL)

Diese API unterstützt zwei Autorisierungsebenen:

-   Grobe Rolle: Tokens tragen `role("api_user", ["read"[, "write"]])` für Endpunkte ohne feingranulare Zuordnung. Lesen wird auf GET/HEAD/OPTIONS abgebildet; Schreiben wird auf POST/PUT/PATCH/DELETE abgebildet.
-   Feingranulare ACL: Tokens enthalten `api_perm(<resource_type>, <resource_id|*>, <permission>)` und Routen deklarieren, was sie benötigen. `admin(true)` umgeht alle Prüfungen.

Unterstützte Ressourcentypen: `instances`, `global_config`, `services`, `configs`, `plugins`, `cache`, `bans`, `jobs`.

Berechtigungsnamen nach Ressourcentyp:

-   instances: `instances_read`, `instances_update`, `instances_delete`, `instances_create`, `instances_execute`
-   global_config: `global_config_read`, `global_config_update`
-   services: `service_read`, `service_create`, `service_update`, `service_delete`, `service_convert`, `service_export`
-   configs: `configs_read`, `config_read`, `config_create`, `config_update`, `config_delete`
-   plugins: `plugin_read`, `plugin_create`, `plugin_delete`
-   cache: `cache_read`, `cache_delete`
-   bans: `ban_read`, `ban_update`, `ban_delete`, `ban_created`
-   jobs: `job_read`, `job_run`

Ressourcen-IDs: Für feingranulare Prüfungen wird das zweite Pfadsegment als `resource_id` behandelt, wenn es sinnvoll ist. Beispiele: `/services/{service}` -> `{service}`; `/configs/{service}/...` -> `{service}`. Verwenden Sie `"*"` (oder lassen Sie es weg), um global für einen Ressourcentyp zu gewähren.

Benutzer- und ACL-Konfiguration:

-   Admin-Benutzer: Setzen Sie `API_USERNAME` und `API_PASSWORD`, um den ersten Admin beim Start zu erstellen. Um Anmeldeinformationen später zu rotieren, setzen Sie `OVERRIDE_API_CREDS=yes` (oder stellen Sie sicher, dass der Admin mit der Methode `manual` erstellt wurde). Es gibt nur einen Admin; zusätzliche Versuche fallen auf die Erstellung von Nicht-Admin-Benutzern zurück.
-   Nicht-Admin-Benutzer und Berechtigungen: Geben Sie `API_ACL_BOOTSTRAP_FILE` an, das auf eine JSON-Datei verweist, oder mounten Sie `/var/lib/bunkerweb/api_acl_bootstrap.json`. Die API liest sie beim Start, um Benutzer und Berechtigungen zu erstellen/aktualisieren.
-   ACL-Cache-Datei: Eine schreibgeschützte Zusammenfassung wird beim Start unter `/var/lib/bunkerweb/api_acl.json` zur Introspektion geschrieben; die Autorisierung wertet DB-gestützte Berechtigungen aus, die in das Biscuit-Token eingebettet sind.

Bootstrap-JSON-Beispiele (beide Formen werden unterstützt):

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

Oder Listenform:

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

Hinweise:

-   Passwörter können im Klartext (`password`) oder bcrypt (`password_hash` / `password_bcrypt`) sein. Schwache Klartext-Passwörter werden in Nicht-Debug-Builds abgelehnt; wenn sie fehlen, wird ein zufälliges generiert und eine Warnung protokolliert.
-   `resource_id: "*"` (oder null/leer) gewährt global für diesen Ressourcentyp.
-   Bestehende Benutzer können Passwörter aktualisieren und zusätzliche Berechtigungen über Bootstrap erhalten.

## Funktionsreferenz

Die API ist nach ressourcenorientierten Routern organisiert. Verwenden Sie die folgenden Abschnitte als Fähigkeitskarte; das interaktive Schema unter `/docs` dokumentiert Anfrage-/Antwortmodelle im Detail.

### Kern und Authentifizierung

-   `GET /ping`, `GET /health`: leichtgewichtige Liveness-Probes für den API-Dienst selbst.
-   `POST /auth`: tauschen Sie Basic-Anmeldeinformationen (oder den Admin-Überschreibungstoken) gegen ein Biscuit. Akzeptiert JSON-, Formular- oder `Authorization`-Header. Admins können bei Bedarf auch weiterhin HTTP Basic direkt auf geschützten Routen verwenden.

### Instanzen-Steuerungsebene

-   `GET /instances`: listet registrierte Instanzen auf, einschließlich Erstellungs-/Zuletzt-gesehen-Zeitstempel, Registrierungsmethode und Metadaten.
-   `POST /instances`: registriert eine neue API-verwaltete Instanz (Hostname, optionaler Port, Servername, Anzeigename, Methode).
-   `GET /instances/{hostname}` / `PATCH /instances/{hostname}` / `DELETE /instances/{hostname}`: inspizieren, aktualisieren Sie veränderbare Felder oder entfernen Sie API-verwaltete Instanzen.
-   `DELETE /instances`: Massenentfernung; überspringt Nicht-API-Instanzen und meldet sie in `skipped`.
-   `GET /instances/ping` und `GET /instances/{hostname}/ping`: Zustandsprüfungen über alle oder einzelne Instanzen hinweg.
-   `POST /instances/reload?test=yes|no`, `POST /instances/{hostname}/reload`: löst Konfigurationsneuladungen aus (Testmodus führt eine Trockenlaufvalidierung durch).
-   `POST /instances/stop`, `POST /instances/{hostname}/stop`: leitet Stopp-Befehle an Instanzen weiter.

### Globale Konfiguration

-   `GET /global_config`: ruft nicht standardmäßige Einstellungen ab (verwenden Sie `full=true` für die gesamte Konfiguration, `methods=true`, um die Herkunft einzuschließen).
-   `PATCH /global_config`: aktualisiert oder fügt API-eigene (`method="api"`) globale Einstellungen ein; Validierungsfehler weisen auf unbekannte oder schreibgeschützte Schlüssel hin.

### Dienstlebenszyklus

-   `GET /services`: listet Dienste mit Metadaten auf, einschließlich Entwurfsstatus und Zeitstempeln.
-   `GET /services/{service}`: ruft nicht standardmäßige Overlays (`full=false`) oder den vollständigen Konfigurations-Snapshot (`full=true`) für einen Dienst ab.
-   `POST /services`: erstellt Dienste, optional als Entwurf, und initialisiert präfixierte Variablen (`{service}_{KEY}`). Aktualisiert die `SERVER_NAME`-Liste atomar.
-   `PATCH /services/{service}`: benennt Dienste um, schaltet Entwurfs-Flags um und aktualisiert präfixierte Variablen. Ignoriert aus Sicherheitsgründen direkte Bearbeitungen von `SERVER_NAME` innerhalb von `variables`.
-   `DELETE /services/{service}`: entfernt einen Dienst und seine abgeleiteten Konfigurationsschlüssel.
-   `POST /services/{service}/convert?convert_to=online|draft`: wechselt schnell zwischen Entwurfs-/Online-Status, ohne andere Variablen zu ändern.

### Benutzerdefinierte Konfigurations-Snippets

-   `GET /configs`: listet benutzerdefinierte Konfigurationsfragmente (HTTP/Server/Stream/ModSecurity/CRS-Hooks) für einen Dienst auf (`service=global` standardmäßig). `with_data=true` bettet UTF-8-Inhalt ein, wenn er druckbar ist.
-   `POST /configs` und `POST /configs/upload`: erstellt neue Snippets aus JSON-Payloads oder hochgeladenen Dateien. Akzeptierte Typen sind `http`, `server_http`, `default_server_http`, `modsec`, `modsec_crs`, `stream`, `server_stream` und CRS-Plugin-Hooks. Namen müssen mit `^[\w_-]{1,64}$` übereinstimmen.
-   `GET /configs/{service}/{type}/{name}`: ruft ein Snippet mit optionalem Inhalt ab (`with_data=true`).
-   `PATCH /configs/{service}/{type}/{name}` und `PATCH .../upload`: aktualisiert oder verschiebt API-verwaltete Snippets; vorlagen- oder dateiverwaltete Einträge bleiben schreibgeschützt.
-   `DELETE /configs` und `DELETE /configs/{service}/{type}/{name}`: entfernt API-verwaltete Snippets unter Beibehaltung von vorlagenverwalteten, wobei eine `skipped`-Liste für ignorierte Einträge zurückgegeben wird.

### Sperren-Orchestrierung

-   `GET /bans`: aggregiert aktive Sperren, die von allen Instanzen gemeldet werden.
-   `POST /bans` oder `POST /bans/ban`: wendet eine oder mehrere Sperren an. Payloads können JSON-Objekte, Arrays oder stringifizierte JSON sein. `service` ist optional; wenn es weggelassen wird, ist die Sperre global.
-   `POST /bans/unban` oder `DELETE /bans`: entfernt Sperren global oder pro Dienst unter Verwendung derselben flexiblen Payloads.

### Plugin-Verwaltung

-   `GET /plugins?type=all|external|ui|pro`: listet Plugins mit Metadaten auf; `with_data=true` schließt verpackte Bytes ein, wenn verfügbar.
-   `POST /plugins/upload`: installiert UI-Plugins aus `.zip`, `.tar.gz` oder `.tar.xz` Archiven. Archive können mehrere Plugins bündeln, solange jedes eine `plugin.json` enthält.
-   `DELETE /plugins/{id}`: entfernt ein UI-Plugin nach ID (`^[\w.-]{4,64}$`).

### Job-Cache und Ausführung

-   `GET /cache`: listet gecachte Artefakte auf, die von Scheduler-Jobs erstellt wurden, gefiltert nach Dienst, Plugin-ID oder Job-Namen. `with_data=true` schließt druckbaren Dateiinhalt ein.
-   `GET /cache/{service}/{plugin}/{job}/{file}`: ruft eine bestimmte Cache-Datei ab (`download=true` streamt einen Anhang).
-   `DELETE /cache` oder `DELETE /cache/{service}/{plugin}/{job}/{file}`: löscht Cache-Dateien und benachrichtigt den Scheduler über betroffene Plugins.
-   `GET /jobs`: inspiziert bekannte Jobs, ihre Zeitplan-Metadaten und Cache-Zusammenfassungen.
-   `POST /jobs/run`: fordert die Ausführung eines Jobs an, indem die zugehörigen Plugins als geändert markiert werden.

### Betriebshinweise

-   Schreibendpunkte persistieren in der gemeinsamen Datenbank; Instanzen übernehmen Änderungen über Scheduler-Sync oder nach einem `/instances/reload`.
-   Fehler werden auf `{ "status": "error", "message": "..." }` normalisiert mit entsprechenden HTTP-Statuscodes (422 Validierung, 404 nicht gefunden, 403 ACL, 5xx Upstream-Fehler).

## Ratenbegrenzung

Die Ratenbegrenzung pro Client wird von SlowAPI gehandhabt. Aktivieren/deaktivieren Sie sie und gestalten Sie die Limits über Umgebungsvariablen oder `/etc/bunkerweb/api.yml`.

-   `API_RATE_LIMIT_ENABLED` (Standard: `yes`)
-   Standardlimit: `API_RATE_LIMIT_TIMES` pro `API_RATE_LIMIT_SECONDS` (z. B. `100` pro `60`)
-   `API_RATE_LIMIT_RULES`: inline JSON/CSV oder ein Pfad zu einer YAML/JSON-Datei mit Regeln pro Route
-   Speicher-Backend: In-Memory oder Redis/Valkey, wenn `USE_REDIS=yes` und `REDIS_*`-Variablen bereitgestellt werden (Sentinel unterstützt)
-   Header: `API_RATE_LIMIT_HEADERS_ENABLED` (Standard: `yes`)

Beispiel YAML (gemountet unter `/etc/bunkerweb/api.yml`):

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
    seconds: 60
```

## Konfiguration

Sie können die API über Umgebungsvariablen, Docker-Secrets und die optionalen Dateien `/etc/bunkerweb/api.yml` oder `/etc/bunkerweb/api.env` konfigurieren. Wichtige Einstellungen:

-   Dokumentation & Schema: `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL`, `API_ROOT_PATH`.
-   Grundlagen der Authentifizierung: `API_TOKEN` (Admin-Überschreibung Bearer), `API_USERNAME`/`API_PASSWORD` (Admin erstellen/aktualisieren), `OVERRIDE_API_CREDS`.
-   ACL und Benutzer: `API_ACL_BOOTSTRAP_FILE` (JSON-Pfad).
-   Biscuit-Richtlinie: `API_BISCUIT_TTL_SECONDS` (0/off deaktiviert TTL), `CHECK_PRIVATE_IP` (bindet Token an Client-IP, es sei denn, es ist privat).
-   IP-Zulassungsliste: `API_WHITELIST_ENABLED`, `API_WHITELIST_IPS`.
-   Ratenbegrenzung (Kern): `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_TIMES`, `API_RATE_LIMIT_SECONDS`, `API_RATE_LIMIT_HEADERS_ENABLED`.
-   Ratenbegrenzung (fortgeschritten): `API_RATE_LIMIT_AUTH_TIMES`, `API_RATE_LIMIT_AUTH_SECONDS`, `API_RATE_LIMIT_RULES`, `API_RATE_LIMIT_DEFAULTS`, `API_RATE_LIMIT_APPLICATION_LIMITS`, `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`, `API_RATE_LIMIT_STORAGE_OPTIONS`.
-   Speicher für Ratenbegrenzung: In-Memory oder Redis/Valkey, wenn `USE_REDIS=yes` und Redis-Einstellungen wie `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DATABASE`, `REDIS_SSL` oder Sentinel-Variablen gesetzt sind. Siehe die Redis-Einstellungstabelle in `docs/features.md`.
-   Netzwerk/TLS: `API_LISTEN_ADDR`, `API_LISTEN_PORT`, `API_FORWARDED_ALLOW_IPS`, `API_SSL_ENABLED`, `API_SSL_CERTFILE`, `API_SSL_KEYFILE`, `API_SSL_CA_CERTS`.

### Wie die Konfiguration geladen wird

Priorität von höchster zu niedrigster:

-   Umgebungsvariablen (z. B. `environment:` im Container oder exportierte Shell-Variablen)
-   Secrets-Dateien unter `/run/secrets` (Docker/K8s-Secrets; Dateinamen entsprechen Variablennamen)
-   YAML-Datei unter `/etc/bunkerweb/api.yml`
-   Env-Datei unter `/etc/bunkerweb/api.env` (key=value Zeilen)
-   Eingebaute Standardwerte

Hinweise:

-   YAML unterstützt das Einbetten von Secret-Dateien mit `<file:relative/path>`; der Pfad wird relativ zu `/run/secrets` aufgelöst.
-   Setzen Sie Doc-URLs auf `off`/`disabled`/`none`, um Endpunkte zu deaktivieren (z. B. `API_DOCS_URL=off`).
-   Wenn `API_SSL_ENABLED=yes`, müssen Sie auch `API_SSL_CERTFILE` und `API_SSL_KEYFILE` setzen.
-   Wenn Redis aktiviert ist (`USE_REDIS=yes`), geben Sie Redis-Details an; siehe Redis-Abschnitt in `docs/features.md`.

### Authentifizierung und Benutzer

-   Admin-Bootstrap: Setzen Sie `API_USERNAME` und `API_PASSWORD`, um den ersten Admin zu erstellen. Um später erneut anzuwenden, setzen Sie `OVERRIDE_API_CREDS=yes`.
-   Nicht-Admins und Berechtigungen: Geben Sie `API_ACL_BOOTSTRAP_FILE` mit einem JSON-Pfad an (oder mounten Sie auf `/var/lib/bunkerweb/api_acl_bootstrap.json`). Die Datei kann Benutzer und feingranulare Berechtigungen auflisten.
-   Biscuit-Schlüssel: Setzen Sie entweder `BISCUIT_PUBLIC_KEY`/`BISCUIT_PRIVATE_KEY` oder mounten Sie Dateien unter `/var/lib/bunkerweb/.api_biscuit_public_key` und `/var/lib/bunkerweb/.api_biscuit_private_key`. Wenn keine bereitgestellt werden, generiert und speichert die API beim Start ein Schlüsselpaar.

### TLS und Netzwerk

-   Bindungsadresse/-port: `API_LISTEN_ADDR` (Standard `0.0.0.0`), `API_LISTEN_PORT` (Standard `8888`).
-   Reverse-Proxys: Setzen Sie `API_FORWARDED_ALLOW_IPS` auf die Proxy-IPs, damit Gunicorn `X-Forwarded-*`-Headern vertraut.
-   TLS-Terminierung in der API: `API_SSL_ENABLED=yes` plus `API_SSL_CERTFILE` und `API_SSL_KEYFILE`; optional `API_SSL_CA_CERTS`

### Schnelle Rezepte zur Ratenbegrenzung

-   Global deaktivieren: `API_RATE_LIMIT_ENABLED=no`
-   Einfaches globales Limit setzen: `API_RATE_LIMIT_TIMES=100`, `API_RATE_LIMIT_SECONDS=60`
-   Regeln pro Route: Setzen Sie `API_RATE_LIMIT_RULES` auf einen JSON/YAML-Dateipfad oder inline YAML in `/etc/bunkerweb/api.yml`.

!!! warning "Startsicherheit"
    Die API wird beendet, wenn kein Authentifizierungspfad konfiguriert ist (keine Biscuit-Schlüssel, kein Admin-Benutzer und kein `API_TOKEN`). Stellen Sie sicher, dass mindestens eine Methode vor dem Start festgelegt ist.

Startsicherheit: Die API wird beendet, wenn kein Authentifizierungspfad verfügbar ist (keine Biscuit-Schlüssel, kein Admin-API-Benutzer und kein `API_TOKEN`). Stellen Sie sicher, dass mindestens einer konfiguriert ist.

!!! info "Root-Pfad und Proxys"
    Wenn Sie die API hinter BunkerWeb auf einem Unterpfad bereitstellen, setzen Sie `API_ROOT_PATH` auf diesen Pfad, damit `/docs` und relative Routen bei der Proxy-Weiterleitung korrekt funktionieren.

## Betrieb

-   Zustand: `GET /health` gibt `{"status":"ok"}` zurück, wenn der Dienst betriebsbereit ist.
-   Linux-Dienst: eine `systemd`-Einheit namens `bunkerweb-api.service` ist enthalten. Passen Sie sie über `/etc/bunkerweb/api.env` an und verwalten Sie sie mit `systemctl`.
-   Startsicherheit: Die API schlägt schnell fehl, wenn kein Authentifizierungspfad verfügbar ist (keine Biscuit-Schlüssel, kein Admin-Benutzer, kein `API_TOKEN`). Fehler werden nach `/var/tmp/bunkerweb/api.error` geschrieben.
