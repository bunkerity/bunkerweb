# API

## Rolle der API

Die BunkerWeb API ist die Steuerungsebene zum Verwalten von Instanzen, Diensten, Sperren, Jobs, Plugins und Konfigurationen. Sie läuft als FastAPI-Anwendung hinter Gunicorn und sollte auf einem vertrauenswürdigen Netz bleiben. Interaktive Doku: `/docs` (oder `<API_ROOT_PATH>/docs`), OpenAPI: `/openapi.json`.

!!! warning "Privat halten"
    Exponieren Sie die API nicht direkt ins Internet. Halten Sie sie intern, beschränken Sie Quell-IP-Bereiche und verlangen Sie Authentifizierung.

## Sicherheits-Checkliste

- Netzwerk: intern binden, `API_WHITELIST_IPS` gesetzt lassen oder upstream filtern.
- Auth vorhanden: `API_USERNAME`/`API_PASSWORD` setzen, optional `API_TOKEN` als Notfall.
- Pfad verbergen: bei Reverse Proxy `API_ROOT_PATH` spiegeln.
- Ratenbegrenzung: aktiviert lassen, `/auth` hat eigenes Limit.
- TLS: am Proxy terminieren oder `API_SSL_ENABLED=yes` plus Zertifikate.

## Ausführen

- Docker/Compose oder All-in-One wie in der englischen `docs/api.md` beschrieben.
- Linux-Pakete bringen `bunkerweb-api.service`; Logs unter `/var/log/bunkerweb/api.log`.

## Authentifizierung & Berechtigungen

- `/auth` gibt Biscuit-Tokens aus; Basic, Formular, JSON oder Bearer gleich `API_TOKEN`.
- Admin kann auch direkt per Basic arbeiten.
- Biscuit enthält Benutzer, Zeit, Client-IP, Rolle/ACL und TTL (`API_BISCUIT_TTL_SECONDS`, `0/off` deaktiviert).

## Ratenbegrenzung

Standardmäßig aktiv mit zwei Strings: `API_RATE_LIMIT` (global, Standard `100r/m`) und `API_RATE_LIMIT_AUTH` (Standard `10r/m` oder `off`). Raten akzeptieren NGINX-Notation (`3r/s`, `40r/m`, `200r/h`) oder ausgeschrieben (`100/minute`, `200 per 30 minutes`).

- `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`
- `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_HEADERS_ENABLED`
- `API_RATE_LIMIT_RULES` (CSV/JSON/YAML inline oder Dateipfad)
- `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`
- Speicher: In-Memory oder Redis/Valkey bei `USE_REDIS=yes` + `REDIS_*` (auch Sentinel)

Limiter-Strategien (bereitgestellt von `limits`):

- `fixed-window` (Standard): Eimer wird am Intervallgrenzwert zurückgesetzt; günstig und gut für grobe Limits.
- `moving-window`: echtes gleitendes Fenster mit Zeitstempeln; glatter, aber speicherintensiver.
- `sliding-window-counter`: Hybrid mit gewichteten Zählungen aus der vorherigen Periode; leichter als moving, glatter als fixed.

Mehr Details und Abwägungen: <https://limits.readthedocs.io/en/stable/strategies.html>

??? example "Inline CSV"
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

## Konfigurationsquellen (Priorität)

1. Umgebungsvariablen
2. Secrets unter `/run/secrets/<VAR>`
3. YAML `/etc/bunkerweb/api.yml`
4. Env-Datei `/etc/bunkerweb/api.env`
5. Defaults im Code

## Wichtige Einstellungen (Auszug)

- **Docs**: `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL`, `API_ROOT_PATH`
- **Auth**: `API_USERNAME`, `API_PASSWORD`, `API_TOKEN`, `API_ACL_BOOTSTRAP_FILE`
- **Biscuit**: `API_BISCUIT_TTL_SECONDS`, `CHECK_PRIVATE_IP`
- **Whitelist**: `API_WHITELIST_ENABLED`, `API_WHITELIST_IPS`
- **Ratenbegrenzung**: `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`, `API_RATE_LIMIT_RULES`, `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`, `API_RATE_LIMIT_HEADERS_ENABLED`, `API_RATE_LIMIT_STORAGE_OPTIONS`
- **Redis/Valkey**: `USE_REDIS`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_DATABASE`, `REDIS_USERNAME`, `REDIS_PASSWORD`, `REDIS_SSL`, Sentinel-Variablen
- **Netz/TLS**: `API_LISTEN_ADDR`, `API_LISTEN_PORT`, `API_FORWARDED_ALLOW_IPS`, `API_SSL_ENABLED`, `API_SSL_CERTFILE`, `API_SSL_KEYFILE`, `API_SSL_CA_CERTS`
