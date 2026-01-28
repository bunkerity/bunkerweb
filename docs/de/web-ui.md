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
    - Abhängigkeiten: nutzt die BunkerWeb-Datenbank und spricht mit der API zum Reloaden, Bannen oder Abfragen von Instanzen

## Sicherheits-Checkliste

- UI hinter BunkerWeb im internen Netz betreiben; schwer zu ratenden `REVERSE_PROXY_URL` wählen und Quell-IP einschränken.
- Starke `ADMIN_USERNAME` / `ADMIN_PASSWORD` setzen; `OVERRIDE_ADMIN_CREDS=yes` nur bei bewusstem Reset verwenden.
- `TOTP_ENCRYPTION_KEYS` bereitstellen und TOTP für Admins aktivieren; Recovery-Codes sicher aufbewahren.
- TLS nutzen (an BunkerWeb terminieren oder `UI_SSL_ENABLED=yes` mit Zert-/Key-Pfaden); `UI_FORWARDED_ALLOW_IPS` auf vertrauenswürdige Proxies setzen.
- Secrets persistieren: `/var/lib/bunkerweb` einbinden, damit `FLASK_SECRET`, Biscuit-Keys und TOTP-Daten Neustarts überleben.
- `CHECK_PRIVATE_IP=yes` (Standard) beibehalten, um Sessions an die Client-IP zu binden; `ALWAYS_REMEMBER=no` lassen, außer bei explizitem Bedarf an langen Cookies.
- Sicherstellen, dass `/var/log/bunkerweb` für UID/GID 101 (oder gemappte UID im Rootless-Setup) lesbar ist, damit die UI Logs lesen kann.

## In Betrieb nehmen

Die UI erwartet, dass Scheduler/(BunkerWeb-)API/Redis/DB erreichbar sind.

=== "Schnellstart (Wizard)"

    Verwenden Sie die veröffentlichten Images und das Layout aus dem [Quickstart-Guide](quickstart-guide.md#__tabbed_1_3). Stack starten, dann den Wizard im Browser abschließen.

    ```bash
    docker compose -f https://raw.githubusercontent.com/bunkerity/bunkerweb/v1.6.8~rc3-rc1/misc/integrations/docker-compose.yml up -d
    ```

    Öffnen Sie den Scheduler-Host (z. B. `https://www.example.com/changeme`) und führen Sie den `/setup`-Wizard aus, um UI, Scheduler und Instanz zu konfigurieren.

=== "Fortgeschritten (vorgefüllte Umgebungsvariablen)"

    Überspringen Sie den Wizard, indem Sie Zugangsdaten und Netzwerk vorab setzen; Beispiel-Compose mit Syslog-Sidecar:

    ```yaml
    x-service-env: &service-env
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"
      LOG_TYPES: "stderr syslog"
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp"
        environment:
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        restart: "unless-stopped"
        networks: [bw-universe, bw-services]

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
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
        image: bunkerity/bunkerweb-ui:1.6.8-rc3
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
- Proxy-Header: `UI_FORWARDED_ALLOW_IPS` ist standardmäßig `*`; bei Linux-Installationen auf die Proxy-IP(s) setzen für strengere Defaults.
- Secrets/State: `/var/lib/bunkerweb` enthält `FLASK_SECRET`, Biscuit-Keys und TOTP-Daten. In Docker mounten; unter Linux vom Paket verwaltet.
- Logs: `/var/log/bunkerweb` muss für UID/GID 101 (oder gemappte UID im Rootless-Betrieb) lesbar sein. Pakete legen den Pfad an; Container brauchen ein Volume mit passenden Rechten.
- Wizard: easy-install unter Linux startet UI und Wizard automatisch; in Docker erreicht man den Wizard über die reverse-proxied URL, sofern nicht per Env vorbelegt.

## Authentifizierung und Sessions

- Admin-Konto: per Wizard oder über `ADMIN_USERNAME` / `ADMIN_PASSWORD`. Passwort muss Klein-, Großbuchstaben, Zahl und Sonderzeichen enthalten. `OVERRIDE_ADMIN_CREDS=yes` erzwingt Neu-Initialisierung auch bei bestehendem Konto.
- Rollen: `admin`, `writer` und `reader` werden automatisch angelegt; Konten liegen in der Datenbank.
- Secrets: `FLASK_SECRET` liegt in `/var/lib/bunkerweb/.flask_secret`; Biscuit-Keys daneben, optional per `BISCUIT_PUBLIC_KEY` / `BISCUIT_PRIVATE_KEY`.
- 2FA: TOTP mit `TOTP_ENCRYPTION_KEYS` (leerzeichengetrennt oder JSON-Map) aktivieren. Schlüssel generieren:

    ```bash
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    Recovery-Codes werden einmalig angezeigt; gehen die Verschlüsselungs-Keys verloren, werden gespeicherte TOTP-Secrets verworfen.
- Sessions: Standard-Lebensdauer 12 h (`SESSION_LIFETIME_HOURS`). Sessions an IP und User-Agent gebunden; `CHECK_PRIVATE_IP=no` lockert die IP-Prüfung nur für private Netze. `ALWAYS_REMEMBER=yes` erzwingt persistente Cookies.
- `PROXY_NUMBERS` setzen, wenn mehrere Proxies `X-Forwarded-*` anhängen.

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

| Setting                             | Beschreibung                                  | Erlaubte Werte                         | Standard                                 |
| ----------------------------------- | --------------------------------------------- | -------------------------------------- | ---------------------------------------- |
| `UI_LISTEN_ADDR`                    | Bind-Adresse der UI                           | IP oder Hostname                       | `0.0.0.0` (Docker) / `127.0.0.1` (Paket) |
| `UI_LISTEN_PORT`                    | Bind-Port der UI                              | Integer                                | `7000`                                   |
| `LISTEN_ADDR`, `LISTEN_PORT`        | Fallbacks, falls UI-Variablen fehlen          | IP/Hostname, Integer                   | `0.0.0.0`, `7000`                        |
| `UI_SSL_ENABLED`                    | TLS in der UI aktivieren                      | `yes` oder `no`                        | `no`                                     |
| `UI_SSL_CERTFILE`, `UI_SSL_KEYFILE` | PEM-Zertifikat/Key bei TLS                    | Dateipfade                             | unset                                    |
| `UI_SSL_CA_CERTS`                   | Optionale CA/Chain                            | Dateipfad                              | unset                                    |
| `UI_FORWARDED_ALLOW_IPS`            | Vertrauenswürdige Proxies für `X-Forwarded-*` | IPs/CIDRs (Leer- oder Komma-separiert) | `*`                                      |

### Auth, Sessions, Cookies

| Setting                                     | Beschreibung                                                               | Erlaubte Werte    | Standard                     |
| ------------------------------------------- | -------------------------------------------------------------------------- | ----------------- | ---------------------------- |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`          | Admin-Konto initial befüllen (Passwortrichtlinie)                          | Strings           | unset                        |
| `OVERRIDE_ADMIN_CREDS`                      | Admin-Zugang aus Env erzwingen                                             | `yes` oder `no`   | `no`                         |
| `FLASK_SECRET`                              | Session-Signing-Secret (persistiert in `/var/lib/bunkerweb/.flask_secret`) | Hex/Base64/opaque | auto-generiert               |
| `TOTP_ENCRYPTION_KEYS` (`TOTP_SECRETS`)     | Verschlüsselungs-Keys für TOTP (Leerzeichen oder JSON)                     | Strings / JSON    | auto-generiert falls fehlend |
| `BISCUIT_PUBLIC_KEY`, `BISCUIT_PRIVATE_KEY` | Biscuit-Keys (hex) für UI-Tokens                                           | Hex-Strings       | auto-generiert & gespeichert |
| `SESSION_LIFETIME_HOURS`                    | Session-Lebensdauer                                                        | Zahl (Stunden)    | `12`                         |
| `ALWAYS_REMEMBER`                           | „Remember me“-Cookies immer setzen                                         | `yes` oder `no`   | `no`                         |
| `CHECK_PRIVATE_IP`                          | Sessions an IP binden (locker für private Netze bei `no`)                  | `yes` oder `no`   | `yes`                        |
| `PROXY_NUMBERS`                             | Anzahl vertrauenswürdiger Proxy-Hops für `X-Forwarded-*`                   | Integer           | `1`                          |

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

| Setting                         | Beschreibung                                | Erlaubte Werte  | Standard                             |
| ------------------------------- | ------------------------------------------- | --------------- | ------------------------------------ |
| `MAX_WORKERS`, `MAX_THREADS`    | Gunicorn-Worker/Threads                     | Integer         | `cpu_count()-1` (min 1), `workers*2` |
| `ENABLE_HEALTHCHECK`            | `GET /healthcheck` bereitstellen            | `yes` oder `no` | `no`                                 |
| `FORWARDED_ALLOW_IPS`           | Veralteter Alias für Proxy-Allowlist        | IPs/CIDRs       | `*`                                  |
| `DISABLE_CONFIGURATION_TESTING` | Test-Reloads beim Push skippen              | `yes` oder `no` | `no`                                 |
| `IGNORE_REGEX_CHECK`            | Regex-Validierung der Settings überspringen | `yes` oder `no` | `no`                                 |

## Log-Zugriff

Die UI liest NGINX/Service-Logs aus `/var/log/bunkerweb`. Speisen Sie das Verzeichnis per Syslog-Daemon oder Volume:

- Container-UID/GID ist 101. Auf dem Host Leserechte setzen: `chown root:101 bw-logs && chmod 770 bw-logs` (für Rootless anpassen).
- BunkerWeb Access/Error-Logs via `ACCESS_LOG` / `ERROR_LOG` an den Syslog-Sidecar senden; Komponenten-Logs mit `LOG_TYPES=syslog`.

Beispiel `syslog-ng.conf` für programmbezogene Logs:

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

## Fähigkeiten

- Dashboard für Requests, Bans, Cache und Jobs; Instanzen neu starten/reloaden.
- Dienste und globale Einstellungen anlegen/ändern/löschen mit Validierung gegen Plugin-Schemata.
- Eigene Konfigurationen (NGINX/ModSecurity) und Plugins (extern oder PRO) hochladen und verwalten.
- Logs einsehen, Reports durchsuchen, Cache-Artefakte inspizieren.
- UI-User, Rollen, Sessions und TOTP samt Recovery-Codes verwalten.
- Upgrade auf BunkerWeb PRO und Lizenzstatus in der dedizierten Seite einsehen.

## Upgrade auf PRO {#upgrade-to-pro}

!!! tip "BunkerWeb PRO Gratistest"
    Code `freetrial` im [BunkerWeb-Panel](https://panel.bunkerweb.io/store/bunkerweb-pro?language=german&utm_campaign=self&utm_source=doc) für einen Monat Test.

Fügen Sie den PRO-Lizenzschlüssel in der Seite **PRO** der UI ein (oder setzen Sie `PRO_LICENSE_KEY` vorab für den Wizard). Upgrades werden im Hintergrund vom Scheduler geladen; prüfen Sie Ablaufdatum und Service-Limits in der UI nach Anwendung.

<figure markdown>
  ![PRO upgrade](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>PRO-Lizenzinformationen</figcaption>
</figure>

## Übersetzungen (i18n)

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
