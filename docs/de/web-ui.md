# Web-UI

## Rolle der Web-UI

Die Web-UI ist die visuelle Steuerungsebene von BunkerWeb. Sie verwaltet Dienste, globale Einstellungen, Bans, Plugins, Jobs, Cache, Logs und Upgrades ohne CLI. Sie läuft als Flask-App hinter Gunicorn und steht in der Regel hinter einem BunkerWeb-Reverse-Proxy.

!!! warning "Hinter BunkerWeb betreiben"
    Die UI kann Konfigurationen ändern, Jobs ausführen und eigene Snippets ausrollen. Platzieren Sie sie im vertrauenswürdigen Netz, leiten Sie sie durch BunkerWeb und sichern Sie sie mit starken Anmeldedaten und 2FA.

!!! info "Kurzinfos"
    - Standard-Listener: `0.0.0.0:7000` in Containern, `127.0.0.1:7000` in Paketen (änderbar via `UI_LISTEN_ADDR`/`UI_LISTEN_PORT`)
    - Reverse-Proxy: beachtet `X-Forwarded-*` über `UI_FORWARDED_ALLOW_IPS`; setzen Sie `PROXY_NUMBERS`, wenn mehrere Proxies Header hinzufügen
    - Auth: lokales Admin-Konto (Passwortrichtlinie erzwungen), optionale Rollen, TOTP-2FA mit `TOTP_ENCRYPTION_KEYS`
    - Sessions: signiert mit `FLASK_SECRET`, Standard-Lebensdauer 12 h, an IP und User-Agent gebunden; `ALWAYS_REMEMBER` steuert persistente Cookies
    - Logs: `/var/log/bunkerweb/ui.log` (+ Access-Log bei Capture), UID/GID 101 im Container
    - Health: optional `GET /healthcheck` bei `ENABLE_HEALTHCHECK=yes`
    - Abhängigkeiten: liest und schreibt Konfigurationen über die API; Scheduler, Worker, Job-Broker und Datenbank müssen verfügbar sein

## Sicherheits-Checkliste

- UI hinter BunkerWeb im internen Netz betreiben; schwer zu ratenden `REVERSE_PROXY_URL` wählen und Quell-IP einschränken.
- Starke `ADMIN_USERNAME` / `ADMIN_PASSWORD` setzen; `OVERRIDE_ADMIN_CREDS=yes` nur bei bewusstem Reset verwenden.
- `TOTP_ENCRYPTION_KEYS` bereitstellen und TOTP für Admins aktivieren; Recovery-Codes sicher aufbewahren.
- Passkeys bevorzugen: `UI_WEBAUTHN_RP_ID` setzen (oder einen einzelnen `UI_ALLOWED_HOSTS`-Eintrag) und mindestens zwei je Konto registrieren, damit ein verlorenes Gerät nicht aussperrt. Ein Passkey signiert nicht für einen falschen Origin und schützt so vor Phishing.

- TLS nutzen (an BunkerWeb terminieren oder `UI_SSL_ENABLED=yes` mit Zert-/Key-Pfaden); `UI_FORWARDED_ALLOW_IPS` auf vertrauenswürdige Proxies setzen.
- Secrets persistieren: `/var/lib/bunkerweb` einbinden, damit `FLASK_SECRET`, Biscuit-Keys und TOTP-Daten Neustarts überleben.
- `CHECK_PRIVATE_IP=yes` (Standard) beibehalten, um Sessions an die Client-IP zu binden; `ALWAYS_REMEMBER=no` lassen, außer bei explizitem Bedarf an langen Cookies.
- Sicherstellen, dass `/var/log/bunkerweb` für UID/GID 101 (oder gemappte UID im Rootless-Setup) lesbar ist, damit die UI Logs lesen kann.

## In Betrieb nehmen

Die UI erwartet eine erreichbare API sowie Scheduler, Worker, Job-Broker und Datenbank.

=== "Schnellstart (Wizard)"

    Verwenden Sie die veröffentlichten Images und das Layout aus dem [Quickstart-Guide](quickstart-guide.md#__tabbed_1_3). Stack starten, dann den Wizard im Browser abschließen.



=== "Fortgeschritten (vorgefüllte Umgebungsvariablen)"

    Überspringen Sie den Wizard, indem Sie Zugangsdaten und Netzwerk vorab setzen; Beispiel-Compose mit Syslog-Sidecar:

    ```yaml
    x-service-env: &service-env
      # We anchor the environment variables to avoid duplication
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Ein stärkeres Passwort für die Datenbank setzen
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
          # Eigenes Volume: DATABASE_URI zeigt hier auf einen Datenbankserver; /data enthält
          # nur temporäre Dateien, die der Worker aus der Datenbank neu erzeugt. Das Volume
          # muss nur im SQLite-Stack (docker.yml) mit dem Scheduler geteilt werden, weil dort
          # die Datenbank selbst eine Datei unter /data ist.
          - bw-worker-storage:/data
        environment:
          <<: *service-env
          BUNKERWEB_INSTANCES: "bunkerweb"
        networks:
          - bw-universe
          - bw-db

      bw-jobs-broker:
        image: valkey/valkey:8-alpine
        # noeviction ist nötig: Ein Broker, der bei Speicherdruck Schlüssel verdrängt, verliert
        # wartende Jobs, ohne dass die sendenden Komponenten dies bemerken.
        # appendonly ist nötig: Ein Broker-Neustart darf keine wartenden Jobs verlieren.
        # AOF statt RDB ("--save" bleibt leer): Ein RDB-Verlustfenster von 60s würde
        # Jobs unbemerkt verwerfen; genau das sollen die At-least-once-Bestätigungen verhindern.
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
          MYSQL_PASSWORD: "changeme" # Ein stärkeres Passwort für die Datenbank setzen
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

    `bunkerweb-autoconf` hinzufügen und Labels auf dem UI-Container statt `BUNKERWEB_INSTANCES` setzen. Der Scheduler reverse-proxiet die UI weiterhin über das Template `ui` und einen geheimen `REVERSE_PROXY_URL`.

=== "Linux"

    Das Paket liefert den systemd-Dienst `bunkerweb-ui`. Er wird über easy-install automatisch aktiviert (der Wizard startet standardmäßig). Zum Anpassen `/etc/bunkerweb/ui.env` bearbeiten, dann:

    ```bash
    sudo systemctl enable --now bunkerweb-ui
    sudo systemctl restart bunkerweb-ui  # nach Änderungen
    ```

    Reverse-Proxy über BunkerWeb (Template `ui`, `REVERSE_PROXY_URL=/changeme`, Upstream `http://127.0.0.1:7000`). `/var/lib/bunkerweb` und `/var/log/bunkerweb` einbinden, damit Secrets und Logs erhalten bleiben.

### Unterschiede Linux vs Docker

- Bind-Defaults: Docker-Images hören auf `0.0.0.0:7000`; Linux-Pakete auf `127.0.0.1:7000`. Anpassung via `UI_LISTEN_ADDR` / `UI_LISTEN_PORT`.
- Proxy-Header: `UI_FORWARDED_ALLOW_IPS` ist standardmäßig `127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16`; `UI_PROXY_ALLOW_IPS` übernimmt standardmäßig den Wert von `FORWARDED_ALLOW_IPS`. Bei Linux-Installationen auf die Proxy-IP(s) setzen für strengere Defaults.
- Secrets/State: `/var/lib/bunkerweb` enthält `FLASK_SECRET`, Biscuit-Keys und TOTP-Daten. In Docker mounten; unter Linux vom Paket verwaltet.
- Logs: `/var/log/bunkerweb` muss für UID/GID 101 (oder gemappte UID im Rootless-Betrieb) lesbar sein. Pakete legen den Pfad an; Container brauchen ein Volume mit passenden Rechten.
- Wizard: easy-install unter Linux startet UI und Wizard automatisch; in Docker erreicht man den Wizard über die reverse-proxied URL, sofern nicht per Env vorbelegt.

## Authentifizierung und Sessions

- Admin-Konto: per Wizard oder über `ADMIN_USERNAME` / `ADMIN_PASSWORD`. Passwort muss Klein-, Großbuchstaben, Zahl und Sonderzeichen enthalten. `OVERRIDE_ADMIN_CREDS=yes` erzwingt Neu-Initialisierung auch bei bestehendem Konto.
- Passwortlängenbegrenzung: bcrypt verwendet nur die ersten **72 Bytes** eines Secrets; Passwörter sind daher überall, wo sie gesetzt werden (Setup-Assistent, Profilseite, `ADMIN_PASSWORD` / `API_PASSWORD`), auf 72 Bytes begrenzt. Ein längerer Wert wird mit einer erklärenden Fehlermeldung oder einem Logeintrag abgelehnt, statt stillschweigend abgeschnitten zu werden. Beachten Sie, dass Nicht-ASCII-Zeichen (Akzente, Emoji) jeweils mehrere Bytes belegen; eine aus solchen Zeichen bestehende "72-Zeichen"-Passphrase kann daher die Grenze überschreiten. Vorgehashte bcrypt-Werte sind ausgenommen (der Hash kodiert die Grenze bereits).
- Rollen: `admin`, `writer` und `reader` werden automatisch angelegt; Konten liegen in der Datenbank.
- Secrets: `FLASK_SECRET` liegt in `/var/lib/bunkerweb/.flask_secret`; Biscuit-Keys daneben, optional per `BISCUIT_PUBLIC_KEY` / `BISCUIT_PRIVATE_KEY`.
- 2FA: TOTP mit `TOTP_ENCRYPTION_KEYS` (leerzeichengetrennt oder JSON-Map) aktivieren. Schlüssel generieren:

    ```bash
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    Recovery-Codes werden einmalig angezeigt; gehen die Verschlüsselungs-Keys verloren, werden gespeicherte TOTP-Secrets verworfen.
- Passkeys (WebAuthn / FIDO2): Sobald `UI_WEBAUTHN_RP_ID` aufgelöst werden kann (siehe unten), erscheint im Profil unter **Sicherheit** die Karte **Passkeys**. Ein registrierter Passkey meldet Sie ohne Benutzername und Passwort an; der Authenticator prüft Sie lokal, daher folgt auch keine TOTP-Abfrage. Sie können beliebig viele registrieren, etwa einen pro Gerät. Jeder hat einen Namen, ein Erstellungsdatum und die letzte Verwendung. Ein älterer, nicht auffindbarer FIDO2-Sicherheitsschlüssel kann allein keine Sitzung öffnen, funktioniert jedoch nach dem Passwort als TOTP-Alternative.

    Ein Passkey ist ein *alternativer* Zugang, keine zusätzliche Hürde: Seine Registrierung verlangt ihn **nicht** nach dem Passwort, da Passkeys keine Wiederherstellungscodes besitzen und ein verlorenes Gerät sonst dauerhaft aussperren könnte. Passwort und TOTP funktionieren unverändert; Konten ohne Passkey bleiben unverändert. Wenn Sie einen zweiten Faktor *verlangen* möchten, verwenden Sie TOTP mit Wiederherstellungscodes.

- Sessions: Standard-Leerlauf-Lebensdauer 12 h (`SESSION_LIFETIME_HOURS`), bei jeder Anfrage erneuert. Ein hartes Absolutlimit gilt über `SESSION_ABSOLUTE_HOURS` (Standard `168` = 7 Tage) — danach werden Nutzer unabhängig von Aktivität ausgeloggt. Optionale Session-ID-Rotation (`SESSION_ROLLING_HOURS`, Standard `0` = deaktiviert) erzeugt in diesem Intervall eine neue Session-ID. Sessions an IP und User-Agent gebunden; `CHECK_PRIVATE_IP=no` lockert die IP-Prüfung nur für private Netze. `ALWAYS_REMEMBER=yes` erzwingt persistente Cookies.
- `PROXY_NUMBERS` setzen, wenn mehrere Proxies `X-Forwarded-*` anhängen.

!!! tip "Vorgehashtes Admin-Passwort"
    `ADMIN_PASSWORD` akzeptiert einen **bcrypt-Hash** (`$2a$`/`$2b$`/`$2y$`) und speichert ihn unverändert, sodass der Klartext aus Env-Dateien und Secrets bleibt. Die Stärke-Richtlinie entfällt (Sie verantworten das Quell-Passwort); ein Kostenfaktor unter `10` wird **abgelehnt**; `10`–`11` erzeugt eine Warnung (`12`+ empfohlen). Nur env-Erstellung und `OVERRIDE_ADMIN_CREDS`; Wizard und Profilseite brauchen weiter Klartext.

    Hash generieren:

    ```bash
    python3 -c "import bcrypt; print(bcrypt.hashpw(b'Str0ng&P@ss!', bcrypt.gensalt(rounds=13)).decode())"
    ```

!!! warning "Ein falscher Hash sperrt Sie aus"
    Verwenden Sie einen Hash nur, wenn Sie dessen Klartext kennen. Ein gültiger, aber falscher Hash bei der Erst-Erstellung ist nicht umkehrbar und ein Neustart behebt das nicht. Wiederherstellung über ein anderes `ADMIN_PASSWORD` mit `OVERRIDE_ADMIN_CREDS=yes`.

!!! warning "2FA ist nach dem Neuerstellen des Containers verloren"
    TOTP-Geheimnisse liegen verschlüsselt in der Datenbank, die Schlüssel zu ihrer Entschlüsselung jedoch **auf der Festplatte**. Bei jedem Start nimmt die UI die erste verfügbare Quelle: `/var/lib/bunkerweb/.totp_encryption_keys.json`, dann die alte `.totp_secrets.json`, dann `TOTP_ENCRYPTION_KEYS` (Alias `TOTP_SECRETS`). Ist keine brauchbar, erzeugt sie einen neuen Zufallssatz, die gespeicherten Geheimnisse lassen sich nicht mehr entschlüsseln, die Admin-Registrierung wird aus der Datenbank entfernt und alle Benutzer müssen sich neu registrieren.

    Ein Neustart des Containers ist harmlos. Verloren gehen die Schlüssel erst mit dem Container-Dateisystem: `docker compose down` und dann `up`, ein Neuerstellen nach einer Image- oder Umgebungsänderung, `docker rm` oder ein neuer Pod. Ein persistentes Volume auf `/data` im Container `bw-ui` genügt, und jedes Beispiel auf dieser Seite tut das — `/var/lib/bunkerweb` ist im Image ein Symlink auf `/data/lib` — womit `TOTP_ENCRYPTION_KEYS` optional bleibt.

    Setzen Sie die Variable nur selbst, wenn dieses Volume nicht persistiert werden kann oder Sie die Rotation steuern wollen. Dann gilt: ein Platzhalter wie `changeme` ist **kein** gültiger Schlüssel — Schlüssel haben 43 Zeichen, wie von `generate_secret()` aus `passlib` erzeugt. Ein ungültiger Wert wird verworfen und durch einen zufälligen ersetzt, und anders als eine nicht gesetzte Variable verhindert er zugleich das Zurücksetzen der Admin-Registrierung, sodass 2FA unbrauchbar bleibt, bis sie manuell entfernt wird. Rotation ist über eine JSON-Map möglich: Behalten Sie die alten Schlüssel neben dem neuen, dann bleiben bestehende Registrierungen gültig.

## Konfigurationsquellen und Priorität

1. Umgebungsvariablen (inkl. Docker/Compose `environment:`)
2. Secrets in `/run/secrets/<VAR>` (Docker)
3. Env-Datei `/etc/bunkerweb/ui.env` (Linux-Pakete)
4. Eingebaute Defaults

## Konfigurationsreferenz

### Laufzeit & Zeitzone

| Setting | Beschreibung                               | Erlaubte Werte                                  | Standard                             |
| ------- | ------------------------------------------ | ----------------------------------------------- | ------------------------------------ |
| `TZ`    | Zeitzone für UI-Logs und geplante Aktionen | TZ-Datenbankname (z. B. `UTC`, `Europe/Berlin`) | unset (Container-Default, meist UTC) |

### Listener & TLS

| Setting                             | Beschreibung                                  | Erlaubte Werte                         | Standard                                              |
| ----------------------------------- | --------------------------------------------- | -------------------------------------- | ----------------------------------------------------- |
| `UI_LISTEN_ADDR`                    | Bind-Adresse der UI                           | IP oder Hostname                       | `0.0.0.0` (Docker) / `127.0.0.1` (Paket)              |
| `UI_LISTEN_PORT`                    | Bind-Port der UI                              | Integer                                | `7000`                                                |
| `LISTEN_ADDR`, `LISTEN_PORT`        | Fallbacks, falls UI-Variablen fehlen          | IP/Hostname, Integer                   | `0.0.0.0`, `7000`                                     |
| `UI_SSL_ENABLED`                    | TLS in der UI aktivieren                      | `yes` oder `no`                        | `no`                                                  |
| `UI_SSL_CERTFILE`, `UI_SSL_KEYFILE` | PEM-Zertifikat/Key bei TLS                    | Dateipfade                             | unset                                                 |
| `UI_SSL_CA_CERTS`                   | Optionale CA/Chain                            | Dateipfad                              | unset                                                 |
| `UI_FORWARDED_ALLOW_IPS`            | Vertrauenswürdige Proxies für `X-Forwarded-*` | IPs/CIDRs (Leer- oder Komma-separiert) | `127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` |
| `UI_PROXY_ALLOW_IPS`                | Vertrauenswürdige Proxies für PROXY-Protokoll | IPs/CIDRs (Leer- oder Komma-separiert) | `FORWARDED_ALLOW_IPS`                                 |

### Auth, Sessions, Cookies

| Setting                                     | Beschreibung                                                                                                                   | Erlaubte Werte        | Standard                     |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------------------- | ---------------------------- |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`          | Admin-Konto initial befüllen (Passwortrichtlinie; `ADMIN_PASSWORD` akzeptiert auch einen bcrypt-Hash, unverändert gespeichert) | Strings / bcrypt-Hash | unset                        |
| `OVERRIDE_ADMIN_CREDS`                      | Admin-Zugang aus Env erzwingen                                                                                                 | `yes` oder `no`       | `no`                         |
| `FLASK_SECRET`                              | Session-Signing-Secret (persistiert in `/var/lib/bunkerweb/.flask_secret`)                                                     | Hex/Base64/opaque     | auto-generiert               |
| `TOTP_ENCRYPTION_KEYS` (`TOTP_SECRETS`)     | Verschlüsselungs-Keys für TOTP (Leerzeichen oder JSON)                                                                         | Strings / JSON        | auto-generiert falls fehlend |
| `BISCUIT_PUBLIC_KEY`, `BISCUIT_PRIVATE_KEY` | Biscuit-Keys (hex) für UI-Tokens                                                                                               | Hex-Strings           | auto-generiert & gespeichert |
| `SESSION_LIFETIME_HOURS`                    | Leerlauf-Lebensdauer der Session (gleitende TTL, pro Anfrage erneuert)                                                         | Zahl (Stunden)        | `12`                         |
| `SESSION_ABSOLUTE_HOURS`                    | Absolute Obergrenze der Session unabhängig von Aktivität                                                                       | Zahl (Stunden)        | `168`                        |
| `SESSION_ROLLING_HOURS`                     | Intervall für Session-ID-Rotation (`0` deaktiviert die Rotation)                                                               | Zahl (Stunden)        | `0`                          |
| `ALWAYS_REMEMBER`                           | „Remember me“-Cookies immer setzen                                                                                             | `yes` oder `no`       | `no`                         |
| `CHECK_PRIVATE_IP`                          | Sessions an IP binden (locker für private Netze bei `no`)                                                                      | `yes` oder `no`       | `yes`                        |
| `PROXY_NUMBERS`                             | Anzahl vertrauenswürdiger Proxy-Hops für `X-Forwarded-*`                                                                       | Integer               | `1`                          |
| `UI_WEBAUTHN_RP_ID` | WebAuthn-Relying-Party-ID: reine Domain ohne Schema oder Port. Standard ist der einzige nicht mit Wildcard versehene Eintrag in `UI_ALLOWED_HOSTS`. | Domainname | abgeleitet, sonst deaktiviert |
| `UI_WEBAUTHN_ORIGINS` | Exakte bei einer WebAuthn-Zeremonie akzeptierte Origins | Durch Leerzeichen oder Kommas getrennte URLs | `https://<RP ID>` |

!!! warning "Die RP-ID gehört zur Sicherheitsgrenze"
    WebAuthn-Zugangsdaten sind kryptografisch an die Relying-Party-ID gebunden. Sie wird daher
    nie aus dem vom Angreifer kontrollierbaren `Host`-Header abgeleitet; eine falsche RP-ID macht
    alle Passkeys unbemerkt ungültig. Reihenfolge:

    1. `UI_WEBAUTHN_RP_ID`, falls gesetzt;
    2. der einzige Eintrag von `UI_ALLOWED_HOSTS`, wenn genau einer vorhanden und keine Wildcard
       enthalten ist (ein `:port` wird entfernt);
    3. kein Wert: Passkeys bleiben deaktiviert und die UI protokolliert beim Start den Grund.

    **Ein Domainwechsel der UI macht alle registrierten Passkeys ungültig.** Benutzer müssen
    auf der neuen Domain neue registrieren. Die alten lassen sich nicht migrieren, weil der
    Authenticator die RP-ID fest eingebunden hat. Halten Sie vor dem Wechsel TOTP oder Passwort
    als Ausweichmöglichkeit bereit.

    WebAuthn benötigt einen sicheren Kontext: HTTPS außer auf `localhost`, das die Spezifikation
    ausnimmt. Deshalb funktioniert der Entwicklungsstack auf `http://localhost:7000`.

### Zertifikatsverwaltung {#certificate-manager}

| Einstellung | Beschreibung | Zulässige Werte | Standard |
| ----------- | ------------ | --------------- | -------- |
| `CERTIFICATE_ENCRYPTION_KEYS` | Schlüsselbund zur AES-256-GCM-Verschlüsselung gespeicherter privater Zertifikatsschlüssel | JSON-Objekt aus Schlüssel-IDs und base64-kodierten 32-Byte-Schlüsseln | nicht gesetzt |
| `CERTIFICATE_ENCRYPTION_ACTIVE_KEY` | Schlüssel-ID für neu importierte oder generierte private Schlüssel | Eine ID aus dem Schlüsselbund | nicht gesetzt |

Beide Variablen sind für Erstellung, Import und Erneuerung selbstsignierter Zertifikate erforderlich.
Behalten Sie alte Schlüssel-IDs, solange gespeicherte Zertifikate sie verwenden, und geben Sie allen
API- und Worker-Prozessen für Zertifikate denselben Schlüsselbund. Private Schlüssel sind über
Zertifikats-Download-Endpunkte nie abrufbar.

Die API hält gemeinsame Inventaroperationen unter `/certificates`: Liste, Metadaten, Zuordnungen,
Löschen unverwalteter Einträge und öffentliche Downloads. Den Lebenszyklus übernehmen die Provider-Plugins:
`/selfsigned/certificates` erstellt und erneuert selbstsignierte Zertifikate,
`/customcert/certificates/upload` importiert PEM-Material, `/letsencrypt/certificates` plant ACME-Jobs
und bietet lesenden Zugriff auf verwaiste Zustände. So bleibt das Provider-Verhalten erweiterbar,
ohne dass die UI die API umgeht.

Dienstzuordnungen in der Zertifikatsverwaltung organisieren das zentrale Inventar; sie ersetzen
nicht die bestehenden Let's-Encrypt- oder Custom-Certificate-Einstellungen für die aktive TLS-Bereitstellung.

Let's-Encrypt-Inventareinträge werden aus dem Certbot-Cache synchronisiert. Das Löschen durch den
Provider bleibt gesperrt, bis der Zertifikats-Worker gezielte Cache-Operationen dauerhaft bestätigen
und wiederholen kann. Das Entfernen von ACME-Zustand löscht daher seinen verwalteten Inventareintrag
noch nicht automatisch.


### Logging

| Setting                         | Beschreibung                                             | Erlaubte Werte                                  | Standard                                     |
| ------------------------------- | -------------------------------------------------------- | ----------------------------------------------- | -------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Basis-Log-Level / Override                               | `debug`, `info`, `warning`, `error`, `critical` | `info`                                       |
| `LOG_TYPES`                     | Ziele                                                    | Leerzeichengetrennt `stderr`/`file`/`syslog`    | `stderr`                                     |
| `LOG_FILE_PATH`                 | Pfad für File-Logging (`file` oder `CAPTURE_OUTPUT=yes`) | Dateipfad                                       | `/var/log/bunkerweb/ui.log` bei File/Capture |
| `CAPTURE_OUTPUT`                | Gunicorn stdout/stderr an Log-Handler senden             | `yes` oder `no`                                 | `no`                                         |
| `LOG_SYSLOG_ADDRESS`            | Syslog-Ziel (`udp://host:514`, `tcp://host:514`, Socket) | Host:Port / URL / Socketpfad                    | unset                                        |
| `LOG_SYSLOG_TAG`                | Syslog-Tag/Ident                                         | String                                          | `bw-ui`                                      |

### Sonstiges Runtime

| Setting                         | Beschreibung                                                      | Erlaubte Werte                              | Standard                                              |
| ------------------------------- | ----------------------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------- |
| `MAX_WORKERS`, `MAX_THREADS`    | Gunicorn-Worker/Threads                                           | Integer                                     | `cpu_count()-1` (min 1), `workers*2`                  |
| `MAX_REQUESTS`                  | Anfragen vor Gunicorn-Worker-Recycling (verhindert Speicherbloat) | Integer                                     | `1000`                                                |
| `ENABLE_HEALTHCHECK`            | `GET /healthcheck` bereitstellen                                  | `yes` oder `no`                             | `no`                                                  |
| `FORWARDED_ALLOW_IPS`           | Alias für Proxy-Allowlist                                         | IPs/CIDRs                                   | `127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` |
| `PROXY_ALLOW_IPS`               | Alias für PROXY-Allowlist                                         | IPs/CIDRs                                   | `FORWARDED_ALLOW_IPS`                                 |
| `DISABLE_CONFIGURATION_TESTING` | Test-Reloads beim Push skippen                                    | `yes` oder `no`                             | `no`                                                  |
| `IGNORE_REGEX_CHECK`            | Regex-Validierung der Settings überspringen                       | `yes` oder `no`                             | `no`                                                  |
| `MAX_CONTENT_LENGTH`            | Maximale Upload-Größe (Flask `MAX_CONTENT_LENGTH`)                | Größe mit Einheit (`50M`, `1G`, `52428800`) | `50MB`                                                |

## Log-Zugriff

Die UI liest NGINX/Service-Logs aus `/var/log/bunkerweb`. Speisen Sie das Verzeichnis per Syslog-Daemon oder Volume:

- Container-UID/GID ist 101. Auf dem Host Leserechte setzen: `chown root:101 bw-logs && chmod 770 bw-logs` (für Rootless anpassen).
- BunkerWeb Access/Error-Logs via `ACCESS_LOG` / `ERROR_LOG` an den Syslog-Sidecar senden; Komponenten-Logs mit `LOG_TYPES=syslog`.

Beispiel `syslog-ng.conf` für programmbezogene Logs:

```conf
@version: 4.10

# Quelle zum Empfang von Protokollen der Docker-Container
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# Vorlage für Protokollmeldungen
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# Ziel für Protokolle in dynamisch benannten Dateien
destination d_dyna_file {
  file(
    "/var/log/bunkerweb/${PROGRAM}.log"
    template(t_imp)
    owner("101")
    group("101")
    dir_owner("root")
    dir_group("101")
    perm(0440)
    dir_perm(0770)
    create_dirs(yes)
    logrotate(
      enable(yes),
      size(100MB),
      rotations(7)
    )
  );
};

# Protokollpfad zu dynamisch benannten Dateien
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Fähigkeiten

- Dashboard für Requests, Bans, Cache und Jobs; Instanzen neu starten/reloaden.
- Dienste und globale Einstellungen anlegen/ändern/löschen mit Validierung gegen Plugin-Schemata.
- Eigene Konfigurationen (NGINX/ModSecurity) und Plugins (extern oder PRO) hochladen und verwalten.
- Logs einsehen, Reports durchsuchen, Cache-Artefakte inspizieren.
- UI-User, Rollen, Sessions und TOTP samt Recovery-Codes verwalten.
- Upgrade auf BunkerWeb PRO und Lizenzstatus in der dedizierten Seite einsehen.

### Der Standardserver-Eintrag {#the-default-server-entry}

Mit `MULTISITE=yes` zeigt die Dienstliste oben einen angehefteten Eintrag **Standardserver** mit einer kurzen Erklärung. Bei `MULTISITE=no` existiert dieser Eintrag nicht.
Dies ist der reservierte Dienst `default-server`: Er beantwortet Anfragen ohne passenden Dienst,
etwa an einen unbekannten Hostnamen, eine direkte IP-Adresse oder einen nicht bedienten `Host`.

Hier konfigurieren Sie sein Zertifikat, TLS-Einstellungen, Antwort-Header, Fehlerseiten und Whitelist.
Nur diese gelten: Reverse Proxy, gRPC, Weiterleitungen, Sessions, Antibot, mTLS, CORS und HTTP Basic
Auth werden nicht angeboten, weil der Block weder einen routbaren Hostnamen noch eine Dienstidentität
besitzt. Löschen, Klonen und Umwandeln sind ebenfalls nicht möglich: Der Eintrag ist permanent und
zählt nie zum PRO-Dienstkontingent.

### Instanzregistrierung {#instance-enrollment}

Eine auf der Seite **Instanzen** angezeigte Instanz kann anstelle des gemeinsam genutzten globalen `API_TOKEN` ihre eigene Anmeldeinformation der Steuerungsebene erhalten. Über die Schlüssel-Schaltfläche der Zeile (oder das Verlaufsmenü) wird ein einmal verwendbarer Registrierungscode ausgestellt, der nur einmal angezeigt wird; die Instanz löst ihn beim Start mit `INSTANCE_ENROLLMENT_CODE` ein. Danach reagiert sie nur noch auf die von der Steuerungsebene für sie ausgestellte Anmeldeinformation. Die vollständige Funktionsweise, einschließlich der API-Endpunkte und der Unterscheidung zwischen `manual` und `autoconf`, steht in der [API-Referenz](api.md#enrollment-an-alternative-to-setting-credential-by-hand).

Die Registrierung funktioniert für eine über die UI oder die API erstellte Zeile sowie für eine über die Umgebung deklarierte Zeile (`BUNKERWEB_INSTANCES` / `BUNKERWEB_INSTANCE_*`) – die Standardform eines Docker- oder Linux-Deployments. Sie funktioniert **nicht** für eine von Autoconf entdeckte Zeile: Diese wird bei jedem Reconcile erneut von einem laufenden Orchestrator bezogen, was das Token der Umgebung wieder über eine ausgestellte Anmeldeinformation legen würde – deshalb sind die Schaltflächen zum Registrieren, Rotieren und Widerrufen dort deaktiviert.

Eine Instanz, die ihr eigenes `BUNKERWEB_INSTANCE_API_TOKEN_<n>` deklariert, zeigt denselben Chip **Registriert** wie eine über einen Code registrierte, da die Seite „hat eine instanzspezifische Anmeldeinformation" liest und ein deklariertes Token als eine solche gespeichert wird. Die Schaltflächen sind dort nicht gefährlich, aber nahezu wirkungslos: Das nächste Speichern der Scheduler-Konfiguration bezieht das deklarierte Token erneut, überschreibt dabei eine ausgestellte Anmeldeinformation und hebt in jedem Fall einen Widerruf auf. Entscheiden Sie sich für eine Instanz für das eine oder das andere – registrieren oder ein Token deklarieren, nicht beides.

!!! warning "Der Instanz ein persistentes Volume geben"
    Die Anmeldeinformation liegt unter `/var/lib/bunkerweb`, was das Docker-Image nach `/data` verlinkt. Ein Container, der ohne Volume für `/data` neu erstellt wird, verliert die Anmeldeinformation und die Markierung, die den Verlust sonst erkennen würde: Er kommt als frische, nicht registrierte Instanz zurück, während die Steuerungsebene sie weiterhin für registriert hält, und jeder Konfigurations-Push an ihn wird abgelehnt, ohne dass der Grund erkennbar ist. Mit eingebundenem Volume erkennt die Instanz den Verlust selbst und **verweigert den Start**, wobei sie Ursache und Abhilfe benennt. Linux-Pakete persistieren `/var/lib/bunkerweb` bereits, daher betrifft dies nur Container – siehe die Compose-Dateien im [Schnellstart-Leitfaden](quickstart-guide.md) und unter `misc/integrations/`, die alle eines einbinden.

!!! note "Eine `manual`-Zeile lässt sich hier weiterhin nicht löschen"
    Registrieren, Rotieren oder Widerrufen einer in der Umgebung deklarierten Zeile funktioniert auf dieser Seite, das Löschen jedoch nicht – das nächste Konfigurations-Speichern erstellt sie erneut aus `BUNKERWEB_INSTANCES` / `BUNKERWEB_INSTANCE_*`. Entfernen Sie stattdessen den Hostnamen aus der Umgebung, wodurch auch die Registrierung entfällt.

### Ressourcengruppen {#resource-groups}

Öffnen Sie **Konfigurieren → Ressourcengruppen**, um wiederverwendbare Listen aus IP-Adressen oder
CIDRs, Ländern, ASNs, Reverse-DNS-Suffixen, User-Agent- und URI-Mustern zu pflegen. Jeder Eintrag hat
einen Typ und optional einen Kommentar. Sie können Gruppen klonen, als JSON exportieren und vor einer
Änderung alle Referenzen prüfen.

Referenzieren Sie eine Gruppe in unterstützten Listeneinstellungen über `@alias`, etwa
`@office 203.0.113.5`. Whitelist, Blacklist, Greylist, Real IP, DNSBL und Antibot unterstützen diese
Referenzen. BunkerWeb behält das Token in der Datenbank und erweitert beim Generieren die Einträge
des passenden Typs. Gruppenänderungen erreichen beim nächsten Konfigurations-Push alle Verbraucher.
Workflows wählen Gruppen im Editor und speichern eine stabile Gruppen-ID.

Der Alias besteht aus 1 bis 64 Buchstaben, Ziffern, Unterstrichen oder Bindestrichen. Eingebaute
Länder-Aliase wie `@EU`, `@G7` und `@SCHENGEN` sind reserviert. Verweise auf nicht vorhandene Gruppen
oder Gruppen ohne Einträge des benötigten Typs werden abgelehnt. Verwendet eine Einstellung oder ein
Workflow eine Gruppe, lässt sie sich nicht löschen.

### Upstreams

Unter **Konfigurieren → Upstreams** pflegen Sie wiederverwendbare HTTP-, gRPC- oder Stream-Backend-Pools,
die mehreren Diensten gleichzeitig zugewiesen werden können. Ein Pool besitzt einen Namen, ein
Protokoll (`http`, `grpc` oder `stream`), ein Lastverteilungsverfahren (`round_robin`, `least_conn`
oder `ip_hash`), bis zu 64 Server (mit Gewicht, max-fails, fail-timeout und Rolle primary/backup/down),
optional eine Anzahl von Keepalive-Verbindungen sowie einen Schalter `backend_ssl`. Die Zuordnung
zu einem Dienst legt den Reverse-Proxy-Pfad fest (Standard `/`); ein Pool kann bis zu 100 Diensten
zugewiesen werden.

Die Seite verwendet die API-Familie `/upstreams`: `GET /upstreams` zum Auflisten, `POST /upstreams`
zum Anlegen, `PATCH /upstreams/{id}` zum Bearbeiten, `DELETE /upstreams/{id}` zum Löschen und
`POST/DELETE /upstreams/{id}/attachments[/{service}]` zum Zuordnen oder Entfernen eines Dienstes.

### Vorlagen {#templates}

Unter **Konfigurieren → Vorlagen** durchsuchen, erstellen und verwalten Sie wiederverwendbare
Dienstvorlagen: Einstellungen, geordnete Konfigurationsschritte und benutzerdefinierte Konfigurationen,
die ein Dienst durch `USE_TEMPLATE` übernimmt. Die Galerie zeigt die Anzahl referenzierender Dienste
einschließlich Entwürfen sowie abgeleitete Funktionskennzeichen. Der Editor verwendet denselben
Multisite-Einstellungskatalog wie die Dienste; Sie können leer beginnen oder eine Vorlage klonen.
Ein gemeinschaftlicher **Vorlagenkatalog** bietet kuratierte Vorlagen. Die Installation benötigt
`admin` statt lediglich `write`, weil Vorlagen benutzerdefinierten Konfigurationstext enthalten
können, der ohne Inhaltsvalidierung gespeichert und auf Instanzen als NGINX-Konfiguration verwendet
wird. Jede Einstellung einer installierten oder gespeicherten Vorlage wird dennoch gegen die aktive
Einstellungstabelle geprüft; unbekannte Einstellungen werden abgelehnt.

Seit 1.7 akzeptiert `USE_TEMPLATE` mehrere Vorlagen pro Dienst in der angegebenen Reihenfolge.
Bei widersprüchlichen Einstellungen gewinnt die letzte Vorlage. Diese Bausteine erstellen Sie auf
der Vorlagenseite.

### Web-Cache-Verwaltung {#web-cache-management}

Die Seite **Web-Cache** verwaltet den NGINX-Antwortcache des Reverse Proxys. Sie zeigt den Meldestatus
jeder Instanz, Anzahl und Größe der Einträge auf dem Datenträger, Dienste mit effektiv aktiviertem
`USE_PROXY_CACHE` sowie Cache-Zähler wie `HIT`, `MISS`, `BYPASS` und `STALE`, sofern das Metrics-Plugin
sie meldet.

Sie können eine absolute HTTP(S)-URL oder den gesamten Cache leeren. URL-Löschungen rekonstruieren
den genauen `PROXY_CACHE_KEY`; geben Sie bei Abweichungen vom Standard die eigene Schlüsselvorlage
des Dienstes an. Die API akzeptiert höchstens 100 URLs pro Anfrage.

!!! warning "Vollständiges Leeren betrifft jeden gecachten Dienst"
    `scope: "all"` leert die gemeinsame Zone `proxycache` auf jeder erreichbaren Instanz, nicht nur
    für einen Dienst, und löst keinen NGINX-Reload aus. Unerreichbare Instanzen werden übersprungen;
    es wird nichts für sie vorgemerkt. Prüfen Sie die Ergebnisse je Instanz, bevor Sie von einer
    vollständig geleerten Flotte ausgehen.

### Berichts-Dashboard {#reports-dashboard}

Die Seite **Berichte** umfasst blockierte HTTP-Anfragen und STREAM-Sessions. **Übersicht** zeigt
Aktivität im gewählten Zeitraum, **Angriffsmuster** gruppiert ModSecurity-Regeln und Angriffsfamilien,
**Häufigste Verursacher** ordnet Client-IPs, Länder und ASNs, und **Ereignisprotokoll** bietet
serverseitige Suche, Filter, sortierbare Spalten, Vorfalldetails sowie CSV- oder Excel-Export.
Administratoren können einen Verursacher, ausgewählte Zeilen oder alle IPs im gefilterten Ergebnis sperren.

Berichte erfassen jede durch ein Plugin blockierte Anfrage (4xx), jede unter `SECURITY_MODE=detect`
nur erkannte Anfrage und jede blockierte STREAM-Session. Drei Sicherheitsaktionen werden trotz
anderem Status anhand ihres Grundes gespeichert: CrowdSec-1.8-Bot-Challenges, die BunkerWeb selbst
mit 200 beantwortet, statt die Anfrage weiterzuleiten; Weiterleitungen von `workflows` mit 3xx;
und ebenso ausgelieferte Antibot-Challenges. Antibot zeigt jedem unbekannten Besucher eines geschützten
Dienstes eine Challenge, nicht nur Angreifern; bei viel Verkehr entsteht daher ein Bericht je
Challenge. Zuerst füllt sich `METRICS_MAX_BLOCKED_REQUESTS` (In-Memory-Puffer je Worker, Standard `1k`,
beziehungsweise `METRICS_MAX_BLOCKED_REQUESTS_REDIS` bei Redis). Der volle Puffer verdrängt die
ältesten Einträge, also auch echte blockierte Anfragen zugunsten von Challenges. Erhöhen Sie zunächst
dieses Limit und dimensionieren Sie dann `METRICS_RETENTION_DAYS` und `METRICS_RETENTION_MAX_ROWS`
für den gespeicherten Verlauf. Die analytischen Ansichten bleiben unverändert: **Übersicht**,
**Häufigste Verursacher** und Threatmap zählen nur blockierte und erkannte Anfragen, keine Challenges.

Wenn ein Plugin seine Entscheidung protokolliert, zeigt die Spalte **Grund** einen Satz statt nur
des Plugin-Namens: etwa *CrowdSec AppSec: Bot-Erkennungs-Challenge*, *CrowdSec LAPI: Anfrage blockiert
(Szenario: …)*, *Antibot-Challenge (captcha) ausgeliefert* oder *Sicherheits-Workflow api-shield:
Weiterleitung* statt nur `crowdsec`, `antibot` oder `workflows`. Die Rohfelder bleiben in den
Vorfalldetails verfügbar. Sortierung und Grundfilter verwenden weiterhin den zugrunde liegenden Wert;
gespeicherte Filter behalten ihre Bedeutung.

`METRICS_PERSIST_TO_DB=yes` ist Standard und gibt dem Ereignisprotokoll eine dauerhafte, zentral
abfragbare Quelle. `METRICS_RETENTION_DAYS` und `METRICS_RETENTION_MAX_ROWS` begrenzen den Verlauf.
Ohne Persistenz bleiben Berichte im Instanzspeicher oder Redis und können früher verfallen. Ist die
Metrics-API nicht erreichbar, nutzt das Ereignisprotokoll die bisherige Instanz-/Redis-Abfrage;
analytische Dashboard-Tabs zeigen bis zur Rückkehr der Metriken einen Leerzustand.

### Threatmap

Die persönliche Seite **Threatmap** bereitet dieselben gespeicherten Berichte für eine dauerhafte
Bildschirmanzeige auf: eine Weltkarte mit Bögen vom Herkunftsland blockierter Anfragen zu einem
symbolischen Zentrum, eine Länderkarte nach blockiertem Verkehrsvolumen, Verursacher-Übersichten und
einen Ereignisticker. Die Bögen illustrieren die Herkunft, keinen geolokalisierten Angriff: Es werden
keine Koordinaten erfasst, und ein Dienstname besitzt keine Position. Die Seite benötigt
`METRICS_PERSIST_TO_DB=yes` und erklärt bei deaktivierter Persistenz den Grund statt einer leeren
Karte. Der Vollbildmodus blendet die App-Bedienelemente aus. `GET /threatmap/data` aktualisiert die
Zahlen mit ungefähr ein bis zwei Minuten Verzögerung zum realen Verkehr, entsprechend dem Intervall
des Scrape-Jobs, der die Berichte füllt.

### Laufzeiten {#timings}

Die Seite **Laufzeiten** zeigt `METRICS_COLLECT_TIMINGS`: den Zeitverbrauch der Plugin-Phasen je
Anfrage, über die Flotte nach Plugin und Phase aggregiert und nach Gesamtkosten sortiert. Prozentwerte
beziehen sich auf die Gesamtdauer der Anfrage, die die Phase `request` des Metrics-Plugins immer
erfasst. Phasen ohne genau einen Durchlauf je Anfrage (`init`, `init_worker(s)`, `timer`, interne API)
erhalten keinen Prozentwert, weil sich ihre Kosten keiner Anfrage zuverlässig zurechnen lassen.
Wenn keine Instanz meldet, unterscheidet die Seite zwischen deaktivierter Funktion (Prüfung von
`METRICS_COLLECT_TIMINGS`) und unerreichbarer API, statt eine leere Tabelle als untätige Flotte darzustellen.

### Verzögerte Job-Läufe

Die Seite **Jobs** kann neben den gewöhnlichen grünen Erfolgs- und roten Fehler-Pills ein drittes Laufergebnis anzeigen: **Verzögert – wartet auf eine startende Instanz**, in der Warnfarbe, mit einem Uhr-Symbol. Es erscheint, wenn ein Job – häufigster Fall ist `push-configs`, wenn keine registrierte Instanz erreichbar ist – bewusst stoppt, ohne etwas anzuwenden, statt fehlzuschlagen: Es wurde nichts gepusht, aber es ist auch nichts falsch, und die ausstehende Änderung wird automatisch erneut versucht, sobald eine Instanz wieder antwortet. Bewegen Sie den Mauszeiger über die Pill für den genauen Grund; das kurze Label ist auch das, worauf der Statusfilter der Seite abgleicht.

Die erste Verzögerung nach einem erfolgreichen Lauf löst zudem ein schließbares Warnbanner am oberen Rand jeder Seite aus, getrennt vom bestehenden (und schwerwiegenderen) „Push fehlgeschlagen"-Banner, damit eine Flotte, die lediglich auf den Neustart einer Instanz wartet, nicht als defekt erscheint.

## Geführte Einführung

Eine neue Installation öffnet über das Raketensymbol in der oberen Leiste eine **Erste Schritte**-Schublade. Sie listet auf, was noch zu tun ist, hakt jeden Punkt eigenständig ab und verschwindet, sobald alles erledigt ist – oder sobald Sie sie schließen.

Es wird nichts darüber gespeichert, was Sie *gesehen* haben: Jeder Punkt wird bei jedem Öffnen der Schublade neu aus der laufenden Konfiguration abgeleitet. Registrieren Sie einen Dienst über die API oder ein Docker-Label, ist der passende Punkt beim nächsten Blick bereits abgehakt. Umgekehrt kehrt der Punkt zurück, wenn Sie Ihren letzten Dienst löschen.

Was Ihnen gezeigt wird, hängt von Ihrer Rolle ab:

| Rolle | Was die Einführung bietet |
| --- | --- |
| Admin | Installation, erster Dienst, HTTPS, erste blockierte Anfrage, MFA, plus optionale Workflow- und PRO-Punkte |
| Writer | Dasselbe, ohne den Admin-exklusiven PRO-Punkt |
| Reader | Orientierung statt Aufgaben: wo Dashboard, Reports, Bans und Logs zu finden sind und wie man sie liest |

Reader erhalten beim ersten Besuch auf jeder dieser vier Seiten einen kurzen Hinweis; das Bestätigen mit **Verstanden** hakt den passenden Punkt ab. Jeder Punkt, der auf eine Stelle in der Oberfläche verweist, trägt zudem eine Schaltfläche **Zeig's mir**, die sie in der Navigation hervorhebt.

Optionale Punkte – ein Security-Workflow, PRO – halten den Zähler nie zurück: Eine Community-Installation erreicht „alles erledigt" auch ohne sie.

!!! info "Versehentlich geschlossen?"
    **Profil → Geführte Einführung → Einführung neu starten** holt die Schublade zurück. Bei einer schreibgeschützten Datenbank ist die Schaltfläche deaktiviert, da nichts gespeichert werden könnte.

## Neuerungen nach einem Upgrade

Nach einem Upgrade zeigt die erste geöffnete Seite eine Zusammenfassung dessen, was sich zwischen der zuletzt genutzten und der jetzt laufenden Version geändert hat. Sie wird aus der im Image mitgelieferten `CHANGELOG.md` erzeugt – nichts wird aus dem Internet geladen, sodass eine Installation ohne Internetzugang dieselbe Zusammenfassung zeigt wie eine verbundene.

Die Zusammenfassung ist pro Benutzer und pro Version: Sie zu schließen markiert diese Version nur für Ihr Konto als gesehen. Sie bleibt vollständig unter **/whats-new** verfügbar, erreichbar über einen Klick auf die Versionsnummer am unteren Rand der Seitenleiste – das Schließen der Zusammenfassung verliert nichts.

Zwei Verhaltensweisen sind wissenswert:

- **Ein Konto, das noch nie eine Zusammenfassung gesehen hat, wird stillschweigend als aktuell markiert.** Das Aktivieren dieser Funktion begrüßt bestehende Benutzer nicht mit der gesamten Historie; Sie sehen Zusammenfassungen erst ab Ihrem nächsten Upgrade.
- **Downgrades zeigen nichts.** Läuft ein älterer Build als der zuletzt erfasste, wird keine Zusammenfassung angezeigt, statt Releases anzukündigen, die die laufende Binärdatei nicht enthält.

Bei einer schreibgeschützten Datenbank kann nichts gespeichert werden, sodass die Zusammenfassung bei der nächsten Anmeldung erneut erscheint.

## Upgrade auf PRO {#upgrade-to-pro}

!!! tip "BunkerWeb PRO Gratistest"
    Starten Sie eine 30-tägige kostenlose Testversion von BunkerWeb PRO im [BunkerWeb Panel](https://panel.bunkerweb.io/store/bunkerweb-pro?language=german&utm_campaign=self&utm_source=doc).

Fügen Sie den PRO-Lizenzschlüssel in der Seite **PRO** der UI ein (oder setzen Sie `PRO_LICENSE_KEY` vorab für den Wizard). Upgrades werden im Hintergrund vom Scheduler geladen; prüfen Sie Ablaufdatum und Service-Limits in der UI nach Anwendung.

<figure markdown>
  ![PRO upgrade](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>PRO-Lizenzinformationen</figcaption>
</figure>

## Übersetzungen (i18n) {#translations-i18n}

Die Web-Oberfläche ist dank Beiträgen aus der Community in mehreren Sprachen verfügbar. Die Übersetzungen werden als sprachspezifische JSON-Dateien gespeichert (z. B. `en.json`, `fr.json`, …). Für jede Sprache ist klar dokumentiert, ob sie manuell oder mithilfe von KI erstellt wurde und wie ihr Prüfstatus aussieht.

### Verfügbare Sprachen und Mitwirkende

| Sprache                   | Locale | Erstellt von                   | Geprüft von              |
| ------------------------- | ------ | ------------------------------ | ------------------------ |
| Arabisch                  | `ar`   | KI (Google:Gemini-2.5-pro)     | KI (Google:Gemini-3-pro) |
| Bengalisch                | `bn`   | KI (Google:Gemini-2.5-pro)     | KI (Google:Gemini-3-pro) |
| Bretonisch                | `br`   | KI (Google:Gemini-2.5-pro)     | KI (Google:Gemini-3-pro) |
| Deutsch                   | `de`   | KI (Google:Gemini-2.5-pro)     | KI (Google:Gemini-3-pro) |
| Englisch                  | `en`   | Manuell (@TheophileDiot)       | Manuell (@TheophileDiot) |
| Spanisch                  | `es`   | KI (Google:Gemini-2.5-pro)     | KI (Google:Gemini-3-pro) |
| Französisch               | `fr`   | Manuell (@TheophileDiot)       | Manuell (@TheophileDiot) |
| Hindi                     | `hi`   | KI (Google:Gemini-2.5-pro)     | KI (Google:Gemini-3-pro) |
| Italienisch               | `it`   | KI (Google:Gemini-2.5-pro)     | KI (Google:Gemini-3-pro) |
| Koreanisch                | `ko`   | Manuell (@rayshoo)             | Manuell (@rayshoo)       |
| Polnisch                  | `pl`   | Manuell (@tomkolp) via Weblate | Manuell (@tomkolp)       |
| Portugiesisch             | `pt`   | KI (Google:Gemini-2.5-pro)     | KI (Google:Gemini-3-pro) |
| Russisch                  | `ru`   | KI (Google:Gemini-2.5-pro)     | KI (Google:Gemini-3-pro) |
| Türkisch                  | `tr`   | Manuell (@wiseweb-works)       | Manuell (@wiseweb-works) |
| Chinesisch (Traditionell) | `tw`   | KI (Google:Gemini-2.5-pro)     | KI (Google:Gemini-3-pro) |
| Urdu                      | `ur`   | KI (Google:Gemini-2.5-pro)     | KI (Google:Gemini-3-pro) |
| Chinesisch (Vereinfacht)  | `zh`   | KI (Google:Gemini-2.5-pro)     | KI (Google:Gemini-3-pro) |

> 💡 Einige Übersetzungen können unvollständig sein. Eine manuelle Überprüfung wird insbesondere für kritische UI-Elemente dringend empfohlen.

### Wie man beitragen kann

Beiträge zu Übersetzungen folgen dem allgemeinen Beitrags-Workflow von BunkerWeb:

1. **Neue Übersetzungsdatei erstellen oder bestehende aktualisieren**
   - Kopiere `src/ui/app/static/locales/en.json` und benenne die Datei nach dem gewünschten Locale-Code (z. B. `de.json`).
   - Übersetze **nur die Werte**; die Schlüssel dürfen nicht geändert werden.

2. **Sprache registrieren**
   - Ergänze oder aktualisiere den Spracheintrag in `src/ui/app/lang_config.py` (Locale-Code, Anzeigename, Flagge, englischer Name).
     Diese Datei ist die maßgebliche Quelle für unterstützte Sprachen.

3. **Dokumentation und Herkunft aktualisieren**
   - `src/ui/app/static/locales/README.md` → neue Sprache in der Herkunftstabelle eintragen (erstellt von / geprüft von).
   - `README.md` → Projektweite Dokumentation um die neue unterstützte Sprache ergänzen.
   - `docs/web-ui.md` → Dokumentation der Web-Oberfläche (diesen Abschnitt zu Übersetzungen).
   - `docs/*/web-ui.md` → Entsprechende übersetzte Web-UI-Dokumentationen mit demselben Übersetzungsabschnitt aktualisieren.

4. **Pull Request öffnen**
   - Gib klar an, ob die Übersetzung manuell oder mit einem KI-Tool erstellt wurde.
   - Bei größeren Änderungen (neue Sprache oder umfangreiche Updates) empfiehlt es sich, vorab ein Issue zur Diskussion zu eröffnen.

Durch deine Beiträge zu Übersetzungen hilfst du dabei, BunkerWeb für ein internationales Publikum zugänglich zu machen.
