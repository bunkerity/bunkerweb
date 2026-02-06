# Funktionen

Dieser Abschnitt enthält die vollständige Liste der von BunkerWeb unterstützten Einstellungen. Wenn Sie mit BunkerWeb noch nicht vertraut sind, lesen Sie zuerst den Abschnitt [Konzepte](concepts.md) der Dokumentation. Befolgen Sie anschließend die Anweisungen für Ihre [Integration](integrations.md), um die Einstellungen anzuwenden.

## Globale Einstellungen


STREAM-Unterstützung :warning:

Das Allgemein-Plugin stellt das zentrale Konfigurations-Framework für BunkerWeb bereit und ermöglicht es Ihnen, wesentliche Einstellungen zu definieren, die steuern, wie Ihre Webdienste geschützt und bereitgestellt werden. Dieses grundlegende Plugin verwaltet fundamentale Aspekte wie Sicherheitsmodi, Server-Standardeinstellungen, Protokollierungsverhalten und kritische Betriebsparameter für das gesamte BunkerWeb-Ökosystem.

**So funktioniert es:**

1.  Beim Start von BunkerWeb lädt und wendet das Allgemein-Plugin Ihre zentralen Konfigurationseinstellungen an.
2.  Sicherheitsmodi werden entweder global oder pro Website festgelegt und bestimmen das angewendete Schutzniveau.
3.  Standard-Servereinstellungen legen Fallback-Werte für alle nicht spezifizierten Multisite-Konfigurationen fest.
4.  Protokollierungsparameter steuern, welche Informationen aufgezeichnet und wie sie formatiert werden.
5.  Diese Einstellungen bilden die Grundlage, auf der alle anderen BunkerWeb-Plugins und -Funktionen aufbauen.

### Multisite-Modus {#multisite-mode}

Wenn `MULTISITE` auf `yes` gesetzt ist, kann BunkerWeb mehrere Websites hosten und schützen, jede mit ihrer eigenen einzigartigen Konfiguration. Diese Funktion ist besonders nützlich für Szenarien wie:

- Hosten mehrerer Domains mit unterschiedlichen Konfigurationen
- Betreiben mehrerer Anwendungen mit unterschiedlichen Sicherheitsanforderungen
- Anwenden maßgeschneiderter Sicherheitsrichtlinien auf verschiedene Dienste

Im Multisite-Modus wird jede Website durch einen eindeutigen `SERVER_NAME` identifiziert. Um Einstellungen spezifisch auf eine Website anzuwenden, stellen Sie den primären `SERVER_NAME` dem Einstellungsnamen voran. Zum Beispiel:

- `www.example.com_USE_ANTIBOT=captcha` aktiviert CAPTCHA für `www.example.com`.
- `myapp.example.com_USE_GZIP=yes` aktiviert die GZIP-Komprimierung für `myapp.example.com`.

Dieser Ansatz stellt sicher, dass die Einstellungen in einer Multisite-Umgebung der richtigen Website zugeordnet werden.

### Mehrfacheinstellungen {#multiple-settings}

Einige Einstellungen in BunkerWeb unterstützen mehrere Konfigurationen für dieselbe Funktion. Um mehrere Einstellungsgruppen zu definieren, hängen Sie ein numerisches Suffix an den Einstellungsnamen an. Zum Beispiel:

- `REVERSE_PROXY_URL_1=/subdir` und `REVERSE_PROXY_HOST_1=http://myhost1` konfigurieren den ersten Reverse-Proxy.
- `REVERSE_PROXY_URL_2=/anotherdir` und `REVERSE_PROXY_HOST_2=http://myhost2` konfigurieren den zweiten Reverse-Proxy.

Dieses Muster ermöglicht es Ihnen, mehrere Konfigurationen für Funktionen wie Reverse-Proxys, Ports oder andere Einstellungen zu verwalten, die für unterschiedliche Anwendungsfälle unterschiedliche Werte erfordern.

### Ausführungsreihenfolge der Plugins {#plugin-order}

Sie können die Reihenfolge mit durch Leerzeichen getrennten Listen steuern:

- Globale Phasen: `PLUGINS_ORDER_INIT`, `PLUGINS_ORDER_INIT_WORKER`, `PLUGINS_ORDER_TIMER`.
- Seitenspezifische Phasen: `PLUGINS_ORDER_SET`, `PLUGINS_ORDER_ACCESS`, `PLUGINS_ORDER_SSL_CERTIFICATE`, `PLUGINS_ORDER_HEADER`, `PLUGINS_ORDER_LOG`, `PLUGINS_ORDER_PREREAD`, `PLUGINS_ORDER_LOG_STREAM`, `PLUGINS_ORDER_LOG_DEFAULT`.
- Semantik: aufgelistete Plugins laufen zuerst in der Phase; alle übrigen laufen danach in ihrer normalen Reihenfolge. IDs nur mit Leerzeichen trennen.

### Sicherheitsmodi {#security-modes}

Die Einstellung `SECURITY_MODE` bestimmt, wie BunkerWeb erkannte Bedrohungen behandelt. Diese flexible Funktion ermöglicht es Ihnen, je nach Ihren spezifischen Bedürfnissen zwischen der Überwachung oder dem aktiven Blockieren verdächtiger Aktivitäten zu wählen:

- **`detect`**: Protokolliert potenzielle Bedrohungen, ohne den Zugriff zu blockieren. Dieser Modus ist nützlich, um Falsch-Positive auf sichere und unterbrechungsfreie Weise zu identifizieren und zu analysieren.
- **`block`** (Standard): Blockiert aktiv erkannte Bedrohungen und protokolliert Vorfälle, um unbefugten Zugriff zu verhindern und Ihre Anwendung zu schützen.

Das Umschalten in den `detect`-Modus kann Ihnen helfen, potenzielle Falsch-Positive zu identifizieren und zu beheben, ohne legitime Clients zu stören. Sobald diese Probleme behoben sind, können Sie für vollen Schutz getrost in den `block`-Modus zurückwechseln.

### Konfigurationseinstellungen

=== "Kerneinstellungen"

    | Einstellung           | Standard          | Kontext   | Mehrfach | Beschreibung                                                                                                                  |
    | --------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------- |
    | `SERVER_NAME`         | `www.example.com` | multisite | Nein     | **Primäre Domain:** Der Hauptdomainname für diese Website. Im Multisite-Modus erforderlich.                                   |
    | `BUNKERWEB_INSTANCES` | `127.0.0.1`       | global    | Nein     | **BunkerWeb-Instanzen:** Liste der BunkerWeb-Instanzen, durch Leerzeichen getrennt.                                           |
    | `MULTISITE`           | `no`              | global    | Nein     | **Mehrere Websites:** Auf `yes` setzen, um das Hosten mehrerer Websites mit unterschiedlichen Konfigurationen zu ermöglichen. |
    | `SECURITY_MODE`       | `block`           | multisite | Nein     | **Sicherheitsstufe:** Steuert die Stufe der Sicherheitsdurchsetzung. Optionen: `detect` oder `block`.                         |
    | `SERVER_TYPE`         | `http`            | multisite | Nein     | **Servertyp:** Definiert, ob der Server vom Typ `http` oder `stream` ist.                                                     |

=== "API-Einstellungen"

    | Einstellung        | Standard      | Kontext | Mehrfach | Beschreibung                                                                                                        |
    | ------------------ | ------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
    | `USE_API`          | `yes`         | global  | Nein     | **API aktivieren:** Aktivieren Sie die API, um BunkerWeb zu steuern.                                                |
    | `API_HTTP_PORT`    | `5000`        | global  | Nein     | **API-Port:** Lauschportnummer für die API.                                                                         |
    | `API_HTTPS_PORT`   | `5443`        | global  | Nein     | **API-HTTPS-Port:** Lauschportnummer (TLS) für die API.                                                             |
    | `API_LISTEN_HTTP`  | `yes`         | global  | Nein     | **API-HTTP-Lauschen:** HTTP-Listener für die API aktivieren.                                                        |
    | `API_LISTEN_HTTPS` | `no`          | global  | Nein     | **API-HTTPS-Lauschen:** HTTPS (TLS)-Listener für die API aktivieren.                                                |
    | `API_LISTEN_IP`    | `0.0.0.0`     | global  | Nein     | **API-Lausch-IP:** Lausch-IP-Adresse für die API.                                                                   |
    | `API_SERVER_NAME`  | `bwapi`       | global  | Nein     | **API-Servername:** Servername (virtueller Host) für die API.                                                       |
    | `API_WHITELIST_IP` | `127.0.0.0/8` | global  | Nein     | **API-Whitelist-IP:** Liste der IP/Netzwerke, die die API kontaktieren dürfen.                                      |
    | `API_TOKEN`        |               | global  | Nein     | **API-Zugriffstoken (optional):** Wenn gesetzt, müssen alle API-Anfragen `Authorization: Bearer <token>` enthalten. |

    Hinweis: Aus Bootstrap-Gründen müssen Sie, wenn Sie `API_TOKEN` aktivieren, es in der Umgebung SOWOHL der BunkerWeb-Instanz als auch des Schedulers setzen. Der Scheduler fügt den `Authorization`-Header automatisch hinzu, wenn `API_TOKEN` in seiner Umgebung vorhanden ist. Wenn es nicht gesetzt ist, wird kein Header gesendet und BunkerWeb erzwingt keine Token-Authentifizierung. Sie können die API über HTTPS bereitstellen, indem Sie `API_LISTEN_HTTPS=yes` setzen (Port: `API_HTTPS_PORT`, Standard `5443`).

    Beispieltest mit curl (Token und Host ersetzen):

    ```bash
    curl -H "Host: bwapi" \
     -H "Authorization: Bearer $API_TOKEN" \
     http://<bunkerweb-host>:5000/ping

    curl -H "Host: bwapi" \
     -H "Authorization: Bearer $API_TOKEN" \
     --insecure \
     https://<bunkerweb-host>:5443/ping
    ```

=== "Netzwerk- & Port-Einstellungen"

    | Einstellung     | Standard     | Kontext | Mehrfach | Beschreibung                                                 |
    | --------------- | ------------ | ------- | -------- | ------------------------------------------------------------ |
    | `HTTP_PORT`     | `8080`       | global  | Ja       | **HTTP-Port:** Portnummer für HTTP-Verkehr.                  |
    | `HTTPS_PORT`    | `8443`       | global  | Ja       | **HTTPS-Port:** Portnummer für HTTPS-Verkehr.                |
    | `USE_IPV6`      | `no`         | global  | Nein     | **IPv6-Unterstützung:** IPv6-Konnektivität aktivieren.       |
    | `DNS_RESOLVERS` | `127.0.0.11` | global  | Nein     | **DNS-Resolver:** DNS-Adressen der zu verwendenden Resolver. |

=== "Stream-Server-Einstellungen"

    | Einstellung              | Standard | Kontext   | Mehrfach | Beschreibung                                                          |
    | ------------------------ | -------- | --------- | -------- | --------------------------------------------------------------------- |
    | `LISTEN_STREAM`          | `yes`    | multisite | Nein     | **Stream lauschen:** Lauschen für Nicht-SSL (Passthrough) aktivieren. |
    | `LISTEN_STREAM_PORT`     | `1337`   | multisite | Ja       | **Stream-Port:** Lauschport für Nicht-SSL (Passthrough).              |
    | `LISTEN_STREAM_PORT_SSL` | `4242`   | multisite | Ja       | **Stream-SSL-Port:** Lauschport für SSL (Passthrough).                |
    | `USE_TCP`                | `yes`    | multisite | Nein     | **TCP lauschen:** TCP-Lauschen (Stream) aktivieren.                   |
    | `USE_UDP`                | `no`     | multisite | Nein     | **UDP lauschen:** UDP-Lauschen (Stream) aktivieren.                   |

=== "Worker-Einstellungen"

    | Einstellung            | Standard | Kontext | Mehrfach | Beschreibung                                                                                          |
    | ---------------------- | -------- | ------- | -------- | ----------------------------------------------------------------------------------------------------- |
    | `WORKER_PROCESSES`     | `auto`   | global  | Nein     | **Worker-Prozesse:** Anzahl der Worker-Prozesse. Auf `auto` setzen, um verfügbare Kerne zu verwenden. |
    | `WORKER_CONNECTIONS`   | `1024`   | global  | Nein     | **Worker-Verbindungen:** Maximale Anzahl von Verbindungen pro Worker.                                 |
    | `WORKER_RLIMIT_NOFILE` | `2048`   | global  | Nein     | **Dateideskriptor-Limit:** Maximale Anzahl offener Dateien pro Worker.                                |

=== "Speichereinstellungen"

    | Einstellung                    | Standard | Kontext | Mehrfach | Beschreibung                                                                         |
    | ------------------------------ | -------- | ------- | -------- | ------------------------------------------------------------------------------------ |
    | `WORKERLOCK_MEMORY_SIZE`       | `48k`    | global  | Nein     | **Workerlock-Speichergröße:** Größe des lua_shared_dict für Initialisierungs-Worker. |
    | `DATASTORE_MEMORY_SIZE`        | `64m`    | global  | Nein     | **Datastore-Speichergröße:** Größe des internen Datastores.                          |
    | `CACHESTORE_MEMORY_SIZE`       | `64m`    | global  | Nein     | **Cachestore-Speichergröße:** Größe des internen Cachestores.                        |
    | `CACHESTORE_IPC_MEMORY_SIZE`   | `16m`    | global  | Nein     | **Cachestore-IPC-Speichergröße:** Größe des internen Cachestores (ipc).              |
    | `CACHESTORE_MISS_MEMORY_SIZE`  | `16m`    | global  | Nein     | **Cachestore-Miss-Speichergröße:** Größe des internen Cachestores (miss).            |
    | `CACHESTORE_LOCKS_MEMORY_SIZE` | `16m`    | global  | Nein     | **Cachestore-Locks-Speichergröße:** Größe des internen Cachestores (locks).          |

=== "Protokollierungseinstellungen"

    | Einstellung        | Standard                                                                                                                                   | Kontext | Mehrfach | Beschreibung                                                                                                                                                              |
    | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `LOG_FORMAT`       | `$host $remote_addr - $request_id $remote_user [$time_local] \"$request\" $status $body_bytes_sent \"$http_referer\" \"$http_user_agent\"` | global  | Nein     | **Protokollformat:** Das Format, das für Zugriffsprotokolle verwendet werden soll.                                                                                        |
    | `ACCESS_LOG`       | `/var/log/bunkerweb/access.log`                                                                                                            | global  | Ja       | **Pfad Zugriff-Log:** Datei, `syslog:server=Adresse[:Port][,Parameter=Wert]` oder Shared-Memory `memory:Name:Größe`; setze `off`, um die Protokollierung zu deaktivieren. |
    | `ERROR_LOG`        | `/var/log/bunkerweb/error.log`                                                                                                             | global  | Ja       | **Pfad Fehler-Log:** Datei, `stderr`, `syslog:server=Adresse[:Port][,Parameter=Wert]` oder `memory:Größe`.                                                                |
    | `LOG_LEVEL`        | `notice`                                                                                                                                   | global  | Ja       | **Protokollstufe:** Ausführlichkeitsstufe für Fehlerprotokolle. Optionen: `debug`, `info`, `notice`, `warn`, `error`, `crit`, `alert`, `emerg`.                           |
    | `TIMERS_LOG_LEVEL` | `debug`                                                                                                                                    | global  | Nein     | **Timer-Protokollstufe:** Protokollstufe für Timer. Optionen: `debug`, `info`, `notice`, `warn`, `err`, `crit`, `alert`, `emerg`.                                         |

    !!! tip "Bewährte Praktiken bei der Protokollierung"

    - Verwenden Sie für Produktionsumgebungen die Protokollstufen `notice`, `warn` oder `error`, um das Protokollvolumen zu minimieren.
    - Setzen Sie zur Fehlersuche vorübergehend die Protokollstufe auf `debug`, um detailliertere Informationen zu erhalten.

=== "Integrationseinstellungen"

    | Einstellung              | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                                          |
    | ------------------------ | -------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `AUTOCONF_MODE`          | `no`     | global    | Nein     | **Autoconf-Modus:** Autoconf-Docker-Integration aktivieren.                                                                                                           |
    | `SWARM_MODE`             | `no`     | global    | Nein     | **Swarm-Modus:** Docker-Swarm-Integration aktivieren.                                                                                                                 |
    | `KUBERNETES_MODE`        | `no`     | global    | Nein     | **Kubernetes-Modus:** Kubernetes-Integration aktivieren.                                                                                                              |
    | `KEEP_CONFIG_ON_RESTART` | `no`     | global    | Nein     | **Konfiguration bei Neustart behalten:** Konfiguration bei Neustart beibehalten. Auf 'yes' setzen, um das Zurücksetzen der Konfiguration beim Neustart zu verhindern. |
    | `USE_TEMPLATE`           |          | multisite | Nein     | **Vorlage verwenden:** Konfigurationsvorlage, die die Standardwerte bestimmter Einstellungen überschreibt.                                                            |

=== "Nginx-Einstellungen"

    | Einstellung                     | Standard      | Kontext | Mehrfach | Beschreibung                                                                                |
    | ------------------------------- | ------------- | ------- | -------- | ------------------------------------------------------------------------------------------- |
    | `NGINX_PREFIX`                  | `/etc/nginx/` | global  | Nein     | **Nginx-Präfix:** Wo Nginx nach Konfigurationen suchen wird.                                |
    | `SERVER_NAMES_HASH_BUCKET_SIZE` |               | global  | Nein     | **Server-Namen-Hash-Bucket-Größe:** Wert für die `server_names_hash_bucket_size`-Direktive. |

### Beispielkonfigurationen

=== "Grundlegendes Produktions-Setup"

    Eine Standardkonfiguration für eine Produktionswebsite mit strenger Sicherheit:

    ```yaml
    SECURITY_MODE: "block"
    SERVER_NAME: "example.com"
    LOG_LEVEL: "notice"
    ```

=== "Entwicklungsmodus"

    Konfiguration für eine Entwicklungsumgebung mit zusätzlicher Protokollierung:

    ```yaml
    SECURITY_MODE: "detect"
    SERVER_NAME: "dev.example.com"
    LOG_LEVEL: "debug"
    ```

=== "Multisite-Konfiguration"

    Konfiguration zum Hosten mehrerer Websites:

    ```yaml
    MULTISITE: "yes"

    # Erste Website
    site1.example.com_SERVER_NAME: "site1.example.com"
    site1.example.com_SECURITY_MODE: "block"

    # Zweite Website
    site2.example.com_SERVER_NAME: "site2.example.com"
    site2.example.com_SECURITY_MODE: "detect"
    ```

=== "Stream-Server-Konfiguration"

    Konfiguration für einen TCP/UDP-Server:

    ```yaml
    SERVER_TYPE: "stream"
    SERVER_NAME: "stream.example.com"
    LISTEN_STREAM: "yes"
    LISTEN_STREAM_PORT: "1337"
    USE_TCP: "yes"
    USE_UDP: "no"
    ```

## Anti DDoS <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM-Unterstützung :x:

Provides enhanced protection against DDoS attacks by analyzing and filtering suspicious traffic.

| Einstellung                  | Standardwert  | Kontext | Mehrfach | Beschreibung                                                            |
| ---------------------------- | ------------- | ------- | -------- | ----------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`          | global  | nein     | Enable or disable anti DDoS protection to mitigate high traffic spikes. |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`         | global  | nein     | Size of in-memory storage for DDoS metrics (e.g., 10M, 500k).           |
| `ANTIDDOS_THRESHOLD`         | `100`         | global  | nein     | Maximum suspicious requests allowed from a single IP before blocking.   |
| `ANTIDDOS_WINDOW_TIME`       | `10`          | global  | nein     | Time window (seconds) to detect abnormal request patterns.              |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444` | global  | nein     | HTTP status codes treated as suspicious for DDoS analysis.              |
| `ANTIDDOS_DISTINCT_IP`       | `5`           | global  | nein     | Minimum distinct IP count before enabling anti DDoS measures.           |

## Antibot

STREAM-Unterstützung :x:

Angreifer nutzen oft automatisierte Tools (Bots), um zu versuchen, Ihre Website auszunutzen. Zum Schutz davor enthält BunkerWeb eine „Antibot“-Funktion, die Benutzer auffordert, zu beweisen, dass sie menschlich sind. Wenn ein Benutzer die Herausforderung besteht, erhält er Zugriff auf Ihre Website. Diese Funktion ist standardmäßig deaktiviert.

So funktioniert es:

1. Wenn ein Benutzer Ihre Website besucht, prüft BunkerWeb, ob er bereits eine Antibot-Herausforderung bestanden hat.
2. Andernfalls wird der Benutzer auf eine Herausforderungsseite umgeleitet.
3. Der Benutzer muss die Herausforderung abschließen (z. B. ein CAPTCHA lösen, JavaScript ausführen).
4. Wenn die Herausforderung erfolgreich ist, wird der Benutzer auf die ursprünglich angeforderte Seite umgeleitet und kann normal navigieren.

### So verwenden Sie es

Befolgen Sie diese Schritte, um Antibot zu aktivieren und zu konfigurieren:

1. Wählen Sie einen Herausforderungstyp: Entscheiden Sie sich für den zu verwendenden Mechanismus (z. B. [captcha](#__tabbed_3_3), [hcaptcha](#__tabbed_3_5), [javascript](#__tabbed_3_2)).
2. Aktivieren Sie die Funktion: Setzen Sie den Parameter `USE_ANTIBOT` in Ihrer BunkerWeb-Konfiguration auf den gewählten Typ.
3. Konfigurieren Sie die Einstellungen: Passen Sie bei Bedarf andere `ANTIBOT_*`-Parameter an. Für reCAPTCHA, hCaptcha, Turnstile und mCaptcha erstellen Sie ein Konto beim gewählten Dienst und erhalten Sie API-Schlüssel.
4. Wichtig: Stellen Sie sicher, dass `ANTIBOT_URI` eine eindeutige URL Ihrer Website ist und nirgendwo anders verwendet wird.

!!! important "Über den Parameter `ANTIBOT_URI`"
    Stellen Sie sicher, dass `ANTIBOT_URI` eine eindeutige URL Ihrer Website ist und nirgendwo anders verwendet wird.

!!! warning "Sitzungen in Cluster-Umgebungen"
    Die Antibot-Funktion verwendet Cookies, um zu verfolgen, ob ein Benutzer die Herausforderung abgeschlossen hat. Wenn Sie BunkerWeb in einem Cluster (mehrere Instanzen) betreiben, müssen Sie die Sitzungsverwaltung korrekt konfigurieren: Setzen Sie `SESSIONS_SECRET` und `SESSIONS_NAME` auf allen BunkerWeb-Instanzen auf dieselben Werte. Andernfalls könnten Benutzer aufgefordert werden, die Herausforderung zu wiederholen. Weitere Informationen zur Sitzungskonfiguration finden Sie [hier](#sessions).

### Allgemeine Parameter

Die folgenden Parameter werden von allen Herausforderungsmechanismen gemeinsam genutzt:

| Parameter              | Standardwert | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                       |
| :--------------------- | :----------- | :-------- | :------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_URI`          | `/challenge` | Multisite | nein     | Herausforderungs-URL: Die URL, zu der Benutzer umgeleitet werden, um die Herausforderung abzuschließen. Stellen Sie sicher, dass diese URL nicht für andere Zwecke verwendet wird. |
| `ANTIBOT_TIME_RESOLVE` | `60`         | Multisite | nein     | Herausforderungs-Timeout: Maximale Zeit (in Sekunden) zum Abschließen der Herausforderung. Danach wird eine neue Herausforderung generiert.                                        |
| `ANTIBOT_TIME_VALID`   | `86400`      | Multisite | nein     | Herausforderungs-Gültigkeit: Dauer (in Sekunden), für die eine erfolgreiche Herausforderung gültig bleibt. Nach dieser Zeit wird eine neue Herausforderung erforderlich sein.      |

### Ausschließen von Traffic von Herausforderungen

BunkerWeb ermöglicht es, bestimmte Benutzer, IPs oder Anfragen anzugeben, die die Antibot-Herausforderung vollständig umgehen sollen. Nützlich für vertrauenswürdige Dienste, interne Netzwerke oder Seiten, die immer zugänglich sein sollen:

| Parameter                   | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                              |
| :-------------------------- | :------- | :-------- | :------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_IGNORE_URI`        |          | Multisite | nein     | Ausgeschlossene URLs: Eine durch Leerzeichen getrennte Liste von URI-Regulären Ausdrücken, die die Herausforderung umgehen sollen.                                                        |
| `ANTIBOT_IGNORE_IP`         |          | Multisite | nein     | Ausgeschlossene IPs: Eine durch Leerzeichen getrennte Liste von IP-Adressen oder CIDR-Bereichen, die die Herausforderung umgehen sollen.                                                  |
| `ANTIBOT_IGNORE_RDNS`       |          | Multisite | nein     | Ausgeschlossene rDNS: Eine durch Leerzeichen getrennte Liste von Reverse-DNS-Suffixen, die die Herausforderung umgehen sollen.                                                            |
| `ANTIBOT_RDNS_GLOBAL`       | `yes`    | Multisite | nein     | Nur öffentliche IPs: Wenn `yes`, werden rDNS-Prüfungen nur für öffentliche IPs durchgeführt.                                                                                              |
| `ANTIBOT_IGNORE_ASN`        |          | Multisite | nein     | Ausgeschlossene ASNs: Eine durch Leerzeichen getrennte Liste von ASN-Nummern, die die Herausforderung umgehen sollen.                                                                     |
| `ANTIBOT_IGNORE_USER_AGENT` |          | Multisite | nein     | Ausgeschlossene User-Agents: Eine durch Leerzeichen getrennte Liste von User-Agent-Regex-Mustern, die die Herausforderung umgehen sollen.                                                 |
| `ANTIBOT_IGNORE_COUNTRY`    |          | Multisite | nein     | Ausgeschlossene Länder: Eine durch Leerzeichen getrennte Liste von ISO-3166-1-Alpha-2-Ländercodes, die die Herausforderung umgehen sollen.                                                |
| `ANTIBOT_ONLY_COUNTRY`      |          | Multisite | nein     | Nur Herausforderungs-Länder: Eine durch Leerzeichen getrennte Liste von ISO-3166-1-Alpha-2-Ländercodes, die die Herausforderung erhalten müssen. Alle anderen Länder werden übersprungen. |

!!! note "Verhalten der länderspezifischen Einstellungen"
      - Wenn sowohl `ANTIBOT_IGNORE_COUNTRY` als auch `ANTIBOT_ONLY_COUNTRY` gesetzt sind, hat die Ignore-Liste Vorrang – Länder, die in beiden Listen stehen, umgehen die Herausforderung.
      - Private oder unbekannte IP-Adressen umgehen die Herausforderung, wenn `ANTIBOT_ONLY_COUNTRY` gesetzt ist, da kein Ländercode ermittelt werden kann.

Beispiele:

- `ANTIBOT_IGNORE_URI: "^/api/ ^/webhook/ ^/assets/"`
  Schließt alle URIs aus, die mit `/api/`, `/webhook/` oder `/assets/` beginnen.

- `ANTIBOT_IGNORE_IP: "192.168.1.0/24 10.0.0.1"`
  Schließt das interne Netzwerk `192.168.1.0/24` und die spezifische IP `10.0.0.1` aus.

- `ANTIBOT_IGNORE_RDNS: ".googlebot.com .bingbot.com"`
  Schließt Anfragen von Hosts aus, deren Reverse-DNS auf `googlebot.com` oder `bingbot.com` endet.

- `ANTIBOT_IGNORE_ASN: "15169 8075"`
  Schließt Anfragen von den ASNs 15169 (Google) und 8075 (Microsoft) aus.

- `ANTIBOT_IGNORE_USER_AGENT: "^Mozilla.+Chrome.+Safari"`
  Schließt Anfragen aus, deren User-Agent dem angegebenen Regex-Muster entspricht.

- `ANTIBOT_IGNORE_COUNTRY: "US CA"`
  Umgeht die Antibot-Herausforderung für Besucher aus den USA oder Kanada.

- `ANTIBOT_ONLY_COUNTRY: "CN RU"`
  Stellt nur Besucher aus China oder Russland vor die Herausforderung. Anfragen aus anderen Ländern (oder privaten IP-Bereichen) überspringen die Herausforderung.

### Herausforderungsmechanismen

=== "Cookie"

    Die Cookie-Herausforderung ist ein leichter Mechanismus, der auf der Installation eines Cookies im Browser des Benutzers basiert. Wenn ein Benutzer auf die Website zugreift, sendet der Server ein Cookie an den Client. Bei nachfolgenden Anfragen überprüft der Server das Vorhandensein dieses Cookies, um zu bestätigen, dass der Benutzer legitim ist. Diese Methode ist einfach und effektiv für einen grundlegenden Schutz vor Bots, ohne zusätzliche Benutzerinteraktion zu erfordern.

    **So funktioniert es:**

    1. Der Server generiert ein eindeutiges Cookie und sendet es an den Client.
    2. Der Client muss das Cookie bei nachfolgenden Anfragen zurücksenden.
    3. Wenn das Cookie fehlt oder ungültig ist, wird der Benutzer auf die Herausforderungsseite umgeleitet.

    **Parameter:**

    | Parameter     | Standard | Kontext   | Mehrfach | Beschreibung                                                                  |
    | :------------ | :------- | :-------- | :------- | :---------------------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`     | Multisite | nein     | Antibot aktivieren: Auf `cookie` setzen, um diesen Mechanismus zu aktivieren. |

=== "JavaScript"

    Die JavaScript-Herausforderung fordert den Client auf, eine Rechenaufgabe mithilfe von JavaScript zu lösen. Dieser Mechanismus stellt sicher, dass der Client JavaScript aktiviert hat und den erforderlichen Code ausführen kann, was für die meisten Bots in der Regel nicht möglich ist.

    **So funktioniert es:**

    1. Der Server sendet ein JavaScript-Skript an den Client.
    2. Das Skript führt eine Rechenaufgabe aus (z. B. einen Hash) und übermittelt das Ergebnis an den Server.
    3. Der Server überprüft das Ergebnis, um die Legitimität des Clients zu bestätigen.

    **Hauptmerkmale:**

    - Die Herausforderung generiert dynamisch eine einzigartige Aufgabe für jeden Client.
    - Die Rechenaufgabe beinhaltet ein Hashing mit spezifischen Bedingungen (z. B. das Finden eines Hashes mit einem bestimmten Präfix).

    **Parameter:**

    | Parameter     | Standard | Kontext   | Mehrfach | Beschreibung                                                                      |
    | :------------ | :------- | :-------- | :------- | :-------------------------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`     | Multisite | nein     | Antibot aktivieren: Auf `javascript` setzen, um diesen Mechanismus zu aktivieren. |

=== "Captcha"

    Die Captcha-Herausforderung ist ein hauseigener Mechanismus, der bildbasierte Herausforderungen generiert, die vollständig in Ihrer BunkerWeb-Umgebung gehostet werden. Er testet die Fähigkeit der Benutzer, zufällige Zeichen zu erkennen und zu interpretieren, wodurch sichergestellt wird, dass automatisierte Bots effektiv blockiert werden, ohne auf externe Dienste angewiesen zu sein.

    **So funktioniert es:**

    1. Der Server generiert ein CAPTCHA-Bild mit zufälligen Zeichen.
    2. Der Benutzer muss die im Bild angezeigten Zeichen in ein Textfeld eingeben.
    3. Der Server validiert die Benutzereingabe anhand des generierten CAPTCHAs.

    **Hauptmerkmale:**

    - Vollständig selbst gehostet, wodurch die Notwendigkeit von Drittanbieter-APIs entfällt.
    - Dynamisch generierte Herausforderungen gewährleisten die Einzigartigkeit für jede Benutzersitzung.
    - Verwendet einen anpassbaren Zeichensatz für die CAPTCHA-Generierung.

    **Unterstützte Zeichen:**

    Das CAPTCHA-System unterstützt die folgenden Zeichentypen:

    - **Buchstaben:** Alle Kleinbuchstaben (a-z) und Großbuchstaben (A-Z)
    - **Ziffern:** 2, 3, 4, 5, 6, 7, 8, 9 (schließt 0 und 1 aus, um Verwechslungen zu vermeiden)
    - **Sonderzeichen:** ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„```

    Eine vollständige Liste der unterstützten Zeichen finden Sie in der [Zeichentabelle der für das CAPTCHA verwendeten Schriftart](https://www.dafont.com/moms-typewriter.charmap?back=theme).

    **Parameter:**

    | Parameter                  | Standard                                               | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                                                                                              |
    | :------------------------- | :----------------------------------------------------- | :-------- | :------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                                                   | Multisite | nein     | **Antibot aktivieren:** Auf `captcha` setzen, um diesen Mechanismus zu aktivieren.                                                                                                                                                                        |
    | `ANTIBOT_CAPTCHA_ALPHABET` | `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ` | Multisite | nein     | **Captcha-Alphabet:** Eine Zeichenkette, die zur Generierung des CAPTCHAs verwendet werden soll. Unterstützte Zeichen: alle Buchstaben (a-z, A-Z), die Ziffern 2-9 (schließt 0 und 1 aus) und die Sonderzeichen: ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„``` |

=== "reCAPTCHA"

    Googles reCAPTCHA bietet eine Benutzervalidierung, die im Hintergrund (v3) ausgeführt wird, um eine Verhaltensbewertung zuzuweisen. Eine Bewertung unterhalb des konfigurierten Schwellenwerts löst eine zusätzliche Überprüfung aus oder blockiert die Anfrage. Bei sichtbaren Herausforderungen (v2) müssen Benutzer mit dem reCAPTCHA-Widget interagieren, bevor sie fortfahren können.

    Es gibt jetzt zwei Möglichkeiten, reCAPTCHA zu integrieren:
    - Die klassische Version (Site-/Geheimschlüssel, v2/v3-Verifizierungsendpunkt)
    - Die neue Version mit Google Cloud (Projekt-ID + API-Schlüssel). Die klassische Version bleibt verfügbar und kann mit `ANTIBOT_RECAPTCHA_CLASSIC` aktiviert werden.

    Für die klassische Version erhalten Sie Ihre Site- und Geheimschlüssel über die [Google reCAPTCHA Admin-Konsole](https://www.google.com/recaptcha/admin).
    Für die neue Version erstellen Sie einen reCAPTCHA-Schlüssel in Ihrem Google Cloud-Projekt und verwenden Sie die Projekt-ID sowie einen API-Schlüssel (siehe [Google Cloud reCAPTCHA-Konsole](https://console.cloud.google.com/security/recaptcha)). Ein Site-Schlüssel ist immer erforderlich.

    **Parameter:**

    | Parameter                      | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                     |
    | :----------------------------- | :------- | :-------- | :------- | :------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`                  | `no`     | Multisite | nein     | Antibot aktivieren: Auf `recaptcha` setzen, um diesen Mechanismus zu aktivieren.                                                 |
    | `ANTIBOT_RECAPTCHA_CLASSIC`    | `yes`    | Multisite | nein     | Klassisches reCAPTCHA verwenden. Auf `no` setzen, um die neue Google Cloud-basierte Version zu verwenden.                        |
    | `ANTIBOT_RECAPTCHA_SITEKEY`    |          | Multisite | nein     | reCAPTCHA Site-Schlüssel. Für beide Versionen erforderlich.                                                                      |
    | `ANTIBOT_RECAPTCHA_SECRET`     |          | Multisite | nein     | reCAPTCHA Geheimschlüssel. Nur für die klassische Version erforderlich.                                                          |
    | `ANTIBOT_RECAPTCHA_PROJECT_ID` |          | Multisite | nein     | Google Cloud Projekt-ID. Nur für die neue Version erforderlich.                                                                  |
    | `ANTIBOT_RECAPTCHA_API_KEY`    |          | Multisite | nein     | Google Cloud API-Schlüssel, der zum Aufrufen der reCAPTCHA Enterprise API verwendet wird. Nur für die neue Version erforderlich. |
    | `ANTIBOT_RECAPTCHA_JA3`        |          | Multisite | nein     | Optionaler JA3 TLS-Fingerabdruck, der in Enterprise-Bewertungen enthalten sein soll.                                             |
    | `ANTIBOT_RECAPTCHA_JA4`        |          | Multisite | nein     | Optionaler JA4 TLS-Fingerabdruck, der in Enterprise-Bewertungen enthalten sein soll.                                             |
    | `ANTIBOT_RECAPTCHA_SCORE`      | `0.7`    | Multisite | nein     | Mindestpunktzahl, die zum Bestehen erforderlich ist (gilt für klassische v3 und die neue Version).                               |

=== "hCaptcha"

    Wenn aktiviert, bietet hCaptcha eine effektive Alternative zu reCAPTCHA, indem es Benutzerinteraktionen überprüft, ohne auf einen Bewertungsmechanismus angewiesen zu sein. Es fordert Benutzer mit einem einfachen, interaktiven Test heraus, um ihre Legitimität zu bestätigen.

    Um hCaptcha mit BunkerWeb zu integrieren, müssen Sie die erforderlichen Anmeldeinformationen vom hCaptcha-Dashboard unter [hCaptcha](https://www.hcaptcha.com) abrufen. Diese Informationen umfassen einen Site-Schlüssel und einen Geheimschlüssel.

    **Parameter:**

    | Parameter                  | Standard | Kontext   | Mehrfach | Beschreibung                                                                    |
    | :------------------------- | :------- | :-------- | :------- | :------------------------------------------------------------------------------ |
    | `USE_ANTIBOT`              | `no`     | Multisite | nein     | Antibot aktivieren: Auf `hcaptcha` setzen, um diesen Mechanismus zu aktivieren. |
    | `ANTIBOT_HCAPTCHA_SITEKEY` |          | Multisite | nein     | hCaptcha Site-Schlüssel.                                                        |
    | `ANTIBOT_HCAPTCHA_SECRET`  |          | Multisite | nein     | hCaptcha Geheimschlüssel.                                                       |

=== "Turnstile"

    Turnstile ist ein moderner, datenschutzfreundlicher Herausforderungsmechanismus, der auf der Technologie von Cloudflare basiert, um automatisierten Traffic zu erkennen und zu blockieren. Er validiert Benutzerinteraktionen transparent und im Hintergrund, wodurch die Reibung für legitime Benutzer reduziert und Bots effektiv abgeschreckt werden.

    Um Turnstile mit BunkerWeb zu integrieren, stellen Sie sicher, dass Sie die erforderlichen Anmeldeinformationen von [Cloudflare Turnstile](https://www.cloudflare.com/turnstile) erhalten.

    **Parameter:**

    | Parameter                   | Standard | Kontext   | Mehrfach | Beschreibung                                                                     |
    | :-------------------------- | :------- | :-------- | :------- | :------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`               | `no`     | Multisite | nein     | Antibot aktivieren: Auf `turnstile` setzen, um diesen Mechanismus zu aktivieren. |
    | `ANTIBOT_TURNSTILE_SITEKEY` |          | Multisite | nein     | Turnstile Site-Schlüssel (Cloudflare).                                           |
    | `ANTIBOT_TURNSTILE_SECRET`  |          | Multisite | nein     | Turnstile Geheimschlüssel (Cloudflare).                                          |

=== "mCaptcha"

    mCaptcha ist ein alternativer CAPTCHA-Herausforderungsmechanismus, der die Legitimität von Benutzern überprüft, indem er einen interaktiven Test präsentiert, ähnlich wie andere Antibot-Lösungen. Wenn aktiviert, fordert es Benutzer mit einem von mCaptcha bereitgestellten CAPTCHA heraus, um sicherzustellen, dass nur authentische Benutzer die automatisierten Sicherheitskontrollen umgehen.

    mCaptcha ist datenschutzfreundlich konzipiert. Es ist vollständig DSGVO-konform und stellt sicher, dass alle am Herausforderungsprozess beteiligten Benutzerdaten strenge Datenschutzstandards erfüllen. Darüber hinaus bietet mCaptcha die Flexibilität, selbst gehostet zu werden, sodass Organisationen die volle Kontrolle über ihre Daten und Infrastruktur behalten. Diese Selbsthosting-Fähigkeit verbessert nicht nur den Datenschutz, sondern optimiert auch die Leistung und Anpassung an spezifische Bereitstellungsanforderungen.

    Um mCaptcha mit BunkerWeb zu integrieren, müssen Sie die erforderlichen Anmeldeinformationen von der [mCaptcha-Plattform](https://mcaptcha.org/) oder Ihrem eigenen Anbieter abrufen. Diese Informationen umfassen einen Site-Schlüssel und einen Geheimschlüssel zur Überprüfung.

    **Parameter:**

    | Parameter                  | Standard                    | Kontext   | Mehrfach | Beschreibung                                                                    |
    | :------------------------- | :-------------------------- | :-------- | :------- | :------------------------------------------------------------------------------ |
    | `USE_ANTIBOT`              | `no`                        | Multisite | nein     | Antibot aktivieren: Auf `mcaptcha` setzen, um diesen Mechanismus zu aktivieren. |
    | `ANTIBOT_MCAPTCHA_SITEKEY` |                             | Multisite | nein     | mCaptcha Site-Schlüssel.                                                        |
    | `ANTIBOT_MCAPTCHA_SECRET`  |                             | Multisite | nein     | mCaptcha Geheimschlüssel.                                                       |
    | `ANTIBOT_MCAPTCHA_URL`     | `https://demo.mcaptcha.org` | Multisite | nein     | Zu verwendende Domain für mCaptcha.                                             |

    Siehe Allgemeine Parameter für zusätzliche Optionen.

### Konfigurationsbeispiele

=== "Cookie-Herausforderung"

    ```yaml
    USE_ANTIBOT: "cookie"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "JavaScript-Herausforderung"

    ```yaml
    USE_ANTIBOT: "javascript"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Captcha-Herausforderung"

    ```yaml
    USE_ANTIBOT: "captcha"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ANTIBOT_CAPTCHA_ALPHABET: "23456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ```

    Hinweis: Das obige Beispiel verwendet die Ziffern 2-9 und alle Buchstaben, die häufig für CAPTCHAs verwendet werden. Sie können das Alphabet bei Bedarf anpassen, um Sonderzeichen einzuschließen.

=== "Klassische reCAPTCHA-Herausforderung"

    Beispielkonfiguration für das klassische reCAPTCHA (Site-/Geheimschlüssel):

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "yes"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "reCAPTCHA-Herausforderung (neu)"

    Beispielkonfiguration für das neue Google Cloud-basierte reCAPTCHA (Projekt-ID + API-Schlüssel):

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "no"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_PROJECT_ID: "your-gcp-project-id"
    ANTIBOT_RECAPTCHA_API_KEY: "your-gcp-api-key"
    # Optionale Fingerabdrücke zur Verbesserung der Enterprise-Bewertungen
    # ANTIBOT_RECAPTCHA_JA3: "<ja3-fingerprint>"
    # ANTIBOT_RECAPTCHA_JA4: "<ja4-fingerprint>"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "hCaptcha-Herausforderung"

    ```yaml
    USE_ANTIBOT: "hcaptcha"
    ANTIBOT_HCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_HCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Turnstile-Herausforderung"

    ```yaml
    USE_ANTIBOT: "turnstile"
    ANTIBOT_TURNSTILE_SITEKEY: "your-site-key"
    ANTIBOT_TURNSTILE_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "mCaptcha-Herausforderung"

    ```yaml
    USE_ANTIBOT: "mcaptcha"
    ANTIBOT_MCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_MCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_MCAPTCHA_URL: "https://demo.mcaptcha.org"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

## Auth basic

STREAM-Unterstützung :x:

Das Auth Basic-Plugin bietet eine HTTP-Basisauthentifizierung zum Schutz Ihrer Website oder bestimmter Ressourcen. Diese Funktion fügt eine zusätzliche Sicherheitsebene hinzu, indem sie von den Benutzern die Eingabe eines Benutzernamens und eines Passworts verlangt, bevor sie auf geschützte Inhalte zugreifen können. Diese Art der Authentifizierung ist einfach zu implementieren und wird von den Browsern weitgehend unterstützt.

**So funktioniert es:**

1.  Wenn ein Benutzer versucht, auf einen geschützten Bereich Ihrer Website zuzugreifen, sendet der Server eine Authentifizierungsaufforderung.
2.  Der Browser zeigt ein Anmeldedialogfeld an, in dem der Benutzer zur Eingabe von Benutzername und Passwort aufgefordert wird.
3.  Der Benutzer gibt seine Anmeldedaten ein, die an den Server gesendet werden.
4.  Wenn die Anmeldeinformationen gültig sind, erhält der Benutzer Zugriff auf den angeforderten Inhalt.
5.  Wenn die Anmeldeinformationen ungültig sind, wird dem Benutzer eine Fehlermeldung mit dem Statuscode 401 Unauthorized angezeigt.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Auth Basic-Authentifizierung zu aktivieren und zu konfigurieren:

1.  **Aktivieren Sie die Funktion:** Setzen Sie die Einstellung `USE_AUTH_BASIC` in Ihrer BunkerWeb-Konfiguration auf `yes`.
2.  **Wählen Sie den Schutzumfang:** Entscheiden Sie, ob Sie Ihre gesamte Website oder nur bestimmte URLs schützen möchten, indem Sie die Einstellung `AUTH_BASIC_LOCATION` konfigurieren.
3.  **Anmeldeinformationen definieren:** Richten Sie mindestens ein Paar aus Benutzername und Passwort mit den Einstellungen `AUTH_BASIC_USER` und `AUTH_BASIC_PASSWORD` ein.
4.  **Passen Sie die Nachricht an:** Ändern Sie optional den `AUTH_BASIC_TEXT`, um eine benutzerdefinierte Nachricht in der Anmeldeaufforderung anzuzeigen.

### Konfigurationseinstellungen

| Einstellung           | Standard          | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                                                                                |
| --------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_AUTH_BASIC`      | `no`              | multisite | nein     | **Auth Basic aktivieren:** Auf `yes` setzen, um die Basisauthentifizierung zu aktivieren.                                                                                                                                                   |
| `AUTH_BASIC_LOCATION` | `sitewide`        | multisite | nein     | **Schutzumfang:** Auf `sitewide` setzen, um die gesamte Website zu schützen, oder einen URL-Pfad angeben (z.B. `/admin`), um nur bestimmte Bereiche zu schützen. Sie können auch Nginx-Stil Modifikatoren verwenden (`=`, `~`, `~*`, `^~`). |
| `AUTH_BASIC_USER`     | `changeme`        | multisite | ja       | **Benutzername:** Der für die Authentifizierung erforderliche Benutzername. Sie können mehrere Paare aus Benutzername und Passwort definieren.                                                                                              |
| `AUTH_BASIC_PASSWORD` | `changeme`        | multisite | ja       | **Passwort:** Das für die Authentifizierung erforderliche Passwort. Passwörter werden mit scrypt für maximale Sicherheit gehasht.                                                                                                           |
| `AUTH_BASIC_TEXT`     | `Restricted area` | multisite | nein     | **Aufforderungstext:** Die Nachricht, die in der dem Benutzer angezeigten Authentifizierungsaufforderung erscheint.                                                                                                                         |

!!! warning "Sicherheitshinweise"
    Die HTTP-Basisauthentifizierung überträgt Anmeldeinformationen, die in Base64 kodiert (nicht verschlüsselt) sind. Obwohl dies bei Verwendung über HTTPS akzeptabel ist, sollte es über reines HTTP nicht als sicher angesehen werden. Aktivieren Sie immer SSL/TLS, wenn Sie die Basisauthentifizierung verwenden.

!!! tip "Verwendung mehrerer Anmeldeinformationen"
    Sie können mehrere Paare aus Benutzername/Passwort für den Zugriff konfigurieren. Jede `AUTH_BASIC_USER`-Einstellung sollte eine entsprechende `AUTH_BASIC_PASSWORD`-Einstellung haben.

### Beispielkonfigurationen

=== "Schutz der gesamten Website"

    So schützen Sie Ihre gesamte Website mit einem einzigen Satz von Anmeldeinformationen:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Schutz bestimmter Bereiche"

    Um nur einen bestimmten Pfad zu schützen, wie z.B. ein Admin-Panel:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "/admin/"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Mehrere Benutzer"

    So richten Sie mehrere Benutzer mit unterschiedlichen Anmeldeinformationen ein:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_TEXT: "Staff Area"

    # Erster Benutzer
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "admin_password"

    # Zweiter Benutzer
    AUTH_BASIC_USER_2: "editor"
    AUTH_BASIC_PASSWORD_2: "editor_password"

    # Dritter Benutzer
    AUTH_BASIC_USER_3: "viewer"
    AUTH_BASIC_PASSWORD_3: "viewer_password"
    ```

## Backup

STREAM-Unterstützung :white_check_mark:

Das Backup-Plugin bietet eine automatisierte Backup-Lösung zum Schutz Ihrer BunkerWeb-Daten. Diese Funktion gewährleistet die Sicherheit und Verfügbarkeit Ihrer wichtigen Datenbank, indem sie regelmäßige Backups nach Ihrem bevorzugten Zeitplan erstellt. Backups werden an einem bestimmten Ort gespeichert und können sowohl durch automatisierte Prozesse als auch durch manuelle Befehle einfach verwaltet werden.

**So funktioniert es:**

1.  Ihre Datenbank wird automatisch gemäß dem von Ihnen festgelegten Zeitplan (täglich, wöchentlich oder monatlich) gesichert.
2.  Backups werden in einem angegebenen Verzeichnis auf Ihrem System gespeichert.
3.  Alte Backups werden automatisch basierend auf Ihren Aufbewahrungseinstellungen rotiert.
4.  Sie können jederzeit manuell Backups erstellen, vorhandene Backups auflisten oder eine Wiederherstellung aus einem Backup durchführen.
5.  Vor jeder Wiederherstellung wird der aktuelle Zustand als Sicherheitsmaßnahme automatisch gesichert.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Backup-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die Backup-Funktion ist standardmäßig aktiviert. Bei Bedarf können Sie dies mit der Einstellung `USE_BACKUP` steuern.
2.  **Backup-Zeitplan konfigurieren:** Wählen Sie mit dem Parameter `BACKUP_SCHEDULE`, wie oft Backups durchgeführt werden sollen.
3.  **Aufbewahrungsrichtlinie festlegen:** Geben Sie mit der Einstellung `BACKUP_ROTATION` an, wie viele Backups aufbewahrt werden sollen.
4.  **Speicherort festlegen:** Wählen Sie mit der Einstellung `BACKUP_DIRECTORY`, wo die Backups gespeichert werden sollen.
5.  **CLI-Befehle verwenden:** Verwalten Sie Backups bei Bedarf manuell mit den `bwcli plugin backup`-Befehlen.

### Konfigurationseinstellungen

| Einstellung        | Standard                     | Kontext | Mehrfach | Beschreibung                                                                                                         |
| ------------------ | ---------------------------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global  | nein     | **Backup aktivieren:** Auf `yes` setzen, um automatische Backups zu aktivieren.                                      |
| `BACKUP_SCHEDULE`  | `daily`                      | global  | nein     | **Backup-Frequenz:** Wie oft Backups durchgeführt werden sollen. Optionen: `daily`, `weekly` oder `monthly`.         |
| `BACKUP_ROTATION`  | `7`                          | global  | nein     | **Backup-Aufbewahrung:** Die Anzahl der aufzubewahrenden Backup-Dateien. Ältere Backups werden automatisch gelöscht. |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global  | nein     | **Backup-Speicherort:** Das Verzeichnis, in dem die Backup-Dateien gespeichert werden.                               |

### Befehlszeilenschnittstelle

Das Backup-Plugin bietet mehrere CLI-Befehle zur Verwaltung Ihrer Backups:

```bash
# Alle verfügbaren Backups auflisten
bwcli plugin backup list

# Ein manuelles Backup erstellen
bwcli plugin backup save

# Ein Backup an einem benutzerdefinierten Ort erstellen
bwcli plugin backup save --directory /pfad/zum/benutzerdefinierten/ort

# Aus dem neuesten Backup wiederherstellen
bwcli plugin backup restore

# Aus einer bestimmten Backup-Datei wiederherstellen
bwcli plugin backup restore /pfad/zum/backup/backup-sqlite-2023-08-15_12-34-56.zip
```

!!! tip "Sicherheit geht vor"
    Vor jeder Wiederherstellung erstellt das Backup-Plugin automatisch ein Backup des aktuellen Zustands Ihrer Datenbank an einem temporären Ort. Dies bietet eine zusätzliche Absicherung für den Fall, dass Sie die Wiederherstellung rückgängig machen müssen.

!!! warning "Datenbankkompatibilität"
    Das Backup-Plugin unterstützt SQLite, MySQL/MariaDB und PostgreSQL-Datenbanken. Oracle-Datenbanken werden derzeit für Backup- und Wiederherstellungsvorgänge nicht unterstützt.

### Beispielkonfigurationen

=== "Tägliche Backups mit 7-tägiger Aufbewahrung"

    Standardkonfiguration, die tägliche Backups erstellt und die letzten 7 Dateien aufbewahrt:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Wöchentliche Backups mit erweiterter Aufbewahrung"

    Konfiguration für seltenere Backups mit längerer Aufbewahrung:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Monatliche Backups an einem benutzerdefinierten Speicherort"

    Konfiguration für monatliche Backups, die an einem benutzerdefinierten Ort gespeichert werden:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```

## Backup S3 <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM-Unterstützung :white_check_mark:

Automatically backup your data to an S3 bucket

| Einstellung                   | Standardwert | Kontext | Mehrfach | Beschreibung                                 |
| ----------------------------- | ------------ | ------- | -------- | -------------------------------------------- |
| `USE_BACKUP_S3`               | `no`         | global  | nein     | Enable or disable the S3 backup feature      |
| `BACKUP_S3_SCHEDULE`          | `daily`      | global  | nein     | The frequency of the backup                  |
| `BACKUP_S3_ROTATION`          | `7`          | global  | nein     | The number of backups to keep                |
| `BACKUP_S3_ENDPOINT`          |              | global  | nein     | The S3 endpoint                              |
| `BACKUP_S3_BUCKET`            |              | global  | nein     | The S3 bucket                                |
| `BACKUP_S3_DIR`               |              | global  | nein     | The S3 directory                             |
| `BACKUP_S3_REGION`            |              | global  | nein     | The S3 region                                |
| `BACKUP_S3_ACCESS_KEY_ID`     |              | global  | nein     | The S3 access key ID                         |
| `BACKUP_S3_ACCESS_KEY_SECRET` |              | global  | nein     | The S3 access key secret                     |
| `BACKUP_S3_COMP_LEVEL`        | `6`          | global  | nein     | The compression level of the backup zip file |

## Bad behavior

STREAM-Unterstützung :white_check_mark:

Das Bad Behavior-Plugin schützt Ihre Website, indem es IP-Adressen, die innerhalb eines bestimmten Zeitraums zu viele Fehler oder „schlechte“ HTTP-Statuscodes erzeugen, automatisch erkennt und sperrt. Dies hilft bei der Abwehr von Brute-Force-Angriffen, Web-Scrapern, Schwachstellen-Scannern und anderen böswilligen Aktivitäten, die zahlreiche Fehlerantworten erzeugen könnten.

Angreifer erzeugen oft „verdächtige“ HTTP-Statuscodes, wenn sie nach Schwachstellen suchen oder diese ausnutzen – Codes, die ein typischer Benutzer innerhalb eines bestimmten Zeitrahmens wahrscheinlich nicht auslösen würde. Durch die Erkennung dieses Verhaltens kann BunkerWeb die betreffende IP-Adresse automatisch sperren und den Angreifer zwingen, eine neue IP-Adresse zu verwenden, um seine Versuche fortzusetzen.

**So funktioniert es:**

1.  Das Plugin überwacht die HTTP-Antworten Ihrer Website.
2.  Wenn ein Besucher einen „schlechten“ HTTP-Statuscode (wie 400, 401, 403, 404 usw.) erhält, wird der Zähler für diese IP-Adresse erhöht.
3.  Wenn eine IP-Adresse den konfigurierten Schwellenwert für schlechte Statuscodes innerhalb des angegebenen Zeitraums überschreitet, wird die IP automatisch gesperrt.
4.  Gesperrte IPs können je nach Konfiguration entweder auf Dienstebene (nur für die spezifische Website) oder global (über alle Websites hinweg) blockiert werden.
5.  Sperren laufen automatisch nach der konfigurierten Sperrdauer ab oder bleiben dauerhaft, wenn sie mit `0` konfiguriert sind.

!!! success "Wichtige Vorteile"

      1. **Automatischer Schutz:** Erkennt und blockiert potenziell bösartige Clients ohne manuellen Eingriff.
      2. **Anpassbare Regeln:** Passen Sie genau an, was als „schlechtes Verhalten“ gilt, basierend auf Ihren spezifischen Anforderungen.
      3. **Ressourcenschonung:** Verhindert, dass böswillige Akteure Serverressourcen durch wiederholte ungültige Anfragen verbrauchen.
      4. **Flexibler Geltungsbereich:** Wählen Sie, ob Sperren nur für den aktuellen Dienst oder global für alle Dienste gelten sollen.
      5. **Kontrolle der Sperrdauer:** Legen Sie temporäre Sperren fest, die automatisch nach der konfigurierten Dauer ablaufen, oder permanente Sperren, die bis zur manuellen Aufhebung bestehen bleiben.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Bad Behavior-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die Bad Behavior-Funktion ist standardmäßig aktiviert. Bei Bedarf können Sie dies mit der Einstellung `USE_BAD_BEHAVIOR` steuern.
2.  **Statuscodes konfigurieren:** Definieren Sie mit der Einstellung `BAD_BEHAVIOR_STATUS_CODES`, welche HTTP-Statuscodes als „schlecht“ gelten sollen.
3.  **Schwellenwerte festlegen:** Bestimmen Sie mit der Einstellung `BAD_BEHAVIOR_THRESHOLD`, wie viele „schlechte“ Antworten eine Sperre auslösen sollen.
4.  **Zeiträume konfigurieren:** Geben Sie die Dauer für die Zählung schlechter Antworten und die Sperrdauer mit den Einstellungen `BAD_BEHAVIOR_COUNT_TIME` und `BAD_BEHAVIOR_BAN_TIME` an.
5.  **Sperrbereich wählen:** Entscheiden Sie mit der Einstellung `BAD_BEHAVIOR_BAN_SCOPE`, ob die Sperren nur für den aktuellen Dienst oder global für alle Dienste gelten sollen. Trifft der Traffic auf den Standardserver (Servername `_`), werden Sperren immer global gesetzt, damit die IP überall blockiert wird.

!!! tip "Stream-Modus"
    Im **Stream-Modus** wird nur der Statuscode `444` als „schlecht“ angesehen und löst dieses Verhalten aus.

### Konfigurationseinstellungen

| Einstellung                 | Standard                      | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                      |
| --------------------------- | ----------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BAD_BEHAVIOR`          | `yes`                         | multisite | nein     | **Bad Behavior aktivieren:** Auf `yes` setzen, um die Funktion zur Erkennung und Sperrung von schlechtem Verhalten zu aktivieren.                                                 |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | multisite | nein     | **Schlechte Statuscodes:** Liste der HTTP-Statuscodes, die als „schlechtes“ Verhalten gezählt werden, wenn sie an einen Client zurückgegeben werden.                              |
| `BAD_BEHAVIOR_THRESHOLD`    | `10`                          | multisite | nein     | **Schwellenwert:** Die Anzahl der „schlechten“ Statuscodes, die eine IP innerhalb des Zählzeitraums erzeugen kann, bevor sie gesperrt wird.                                       |
| `BAD_BEHAVIOR_COUNT_TIME`   | `60`                          | multisite | nein     | **Zählzeitraum:** Das Zeitfenster (in Sekunden), in dem schlechte Statuscodes auf den Schwellenwert angerechnet werden.                                                           |
| `BAD_BEHAVIOR_BAN_TIME`     | `86400`                       | multisite | nein     | **Sperrdauer:** Wie lange (in Sekunden) eine IP nach Überschreiten des Schwellenwerts gesperrt bleibt. Standard ist 24 Stunden (86400 Sekunden). `0` für permanente Sperren.      |
| `BAD_BEHAVIOR_BAN_SCOPE`    | `service`                     | global    | nein     | **Sperrbereich:** Legt fest, ob Sperren nur für den aktuellen Dienst (`service`) oder für alle Dienste (`global`) gelten. Auf dem Standardserver (`_`) sind Sperren immer global. |

!!! warning "Falsch-Positive"
    Seien Sie vorsichtig bei der Einstellung des Schwellenwerts und der Zählzeit. Zu niedrige Werte können versehentlich legitime Benutzer sperren, die beim Surfen auf Ihrer Website auf Fehler stoßen.

!!! tip "Anpassen Ihrer Konfiguration"
    Beginnen Sie mit konservativen Einstellungen (höherer Schwellenwert, kürzere Sperrzeit) und passen Sie diese je nach Ihren spezifischen Bedürfnissen und Verkehrsmustern an. Überwachen Sie Ihre Protokolle, um sicherzustellen, dass legitime Benutzer nicht fälschlicherweise gesperrt werden.

### Beispielkonfigurationen

=== "Standardkonfiguration"

    Die Standardkonfiguration bietet einen ausgewogenen Ansatz, der für die meisten Websites geeignet ist:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "86400"
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Strikte Konfiguration"

    Für Hochsicherheitsanwendungen, bei denen Sie potenzielle Bedrohungen aggressiver sperren möchten:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444 500 502 503"
    BAD_BEHAVIOR_THRESHOLD: "5"
    BAD_BEHAVIOR_COUNT_TIME: "120"
    BAD_BEHAVIOR_BAN_TIME: "604800"  # 7 Tage
    BAD_BEHAVIOR_BAN_SCOPE: "global" # Sperre über alle Dienste hinweg
    ```

=== "Nachsichtige Konfiguration"

    Für Websites mit hohem legitimen Datenverkehr, bei denen Sie Falsch-Positive vermeiden möchten:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "401 403 429"  # Nur unautorisierte, verbotene und ratenlimitierte zählen
    BAD_BEHAVIOR_THRESHOLD: "20"
    BAD_BEHAVIOR_COUNT_TIME: "30"
    BAD_BEHAVIOR_BAN_TIME: "3600"  # 1 Stunde
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Konfiguration für permanente Sperren"

    Für Szenarien, in denen erkannte Angreifer dauerhaft gesperrt werden sollen, bis sie manuell entsperrt werden:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "0"  # Permanente Sperre (läuft nie ab)
    BAD_BEHAVIOR_BAN_SCOPE: "global" # Sperre über alle Dienste hinweg
    ```

## Blacklist

STREAM-Unterstützung :warning:

Das Blacklist-Plugin schützt Ihre Website, indem es den Zugriff basierend auf verschiedenen Client-Attributen blockiert. Diese Funktion wehrt bekannte bösartige Entitäten, Scanner und verdächtige Besucher ab, indem sie den Zugriff basierend auf IP-Adressen, Netzwerken, Reverse-DNS-Einträgen (rDNS), ASNs, User-Agents und spezifischen URI-Mustern verweigert.

**So funktioniert's:**

1.  Das Plugin überprüft eingehende Anfragen anhand mehrerer Blacklist-Kriterien (IP-Adressen, Netzwerke, rDNS, ASN, User-Agent oder URI-Muster).
2.  Blacklists können direkt in Ihrer Konfiguration angegeben oder von externen URLs geladen werden.
3.  Wenn ein Besucher einer Blacklist-Regel entspricht (und keiner Ignorier-Regel), wird der Zugriff verweigert.
4.  Blacklists werden automatisch in regelmäßigen Abständen von den konfigurierten URLs aktualisiert.
5.  Sie können genau anpassen, welche Kriterien überprüft und ignoriert werden, basierend auf Ihren spezifischen Sicherheitsanforderungen.

### So verwenden Sie es

Befolgen Sie diese Schritte, um die Blacklist-Funktion einzurichten und zu verwenden:

1.  **Funktion aktivieren:** Die Blacklist-Funktion ist standardmäßig aktiviert. Bei Bedarf können Sie sie mit dem Parameter `USE_BLACKLIST` steuern.
2.  **Blockierregeln konfigurieren:** Definieren Sie, welche IPs, Netzwerke, rDNS-Muster, ASNs, User-Agents oder URIs blockiert werden sollen.
3.  **Ignorierregeln einrichten:** Geben Sie Ausnahmen an, die die Blacklist-Überprüfungen umgehen sollen.
4.  **Externe Quellen hinzufügen:** Konfigurieren Sie URLs, um Blacklist-Daten automatisch herunterzuladen und zu aktualisieren.
5.  **Effektivität überwachen:** Konsultieren Sie die [Web-Oberfläche](web-ui.md), um Statistiken über blockierte Anfragen anzuzeigen.

!!! info "Stream-Modus"
    Im Stream-Modus werden nur Überprüfungen nach IP, rDNS und ASN durchgeführt.

### Konfigurationsparameter

**Allgemein**

| Parameter                   | Standard                                                | Kontext   | Mehrfach | Beschreibung                                                                                                                                           |
| :-------------------------- | :------------------------------------------------------ | :-------- | :------- | :----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BLACKLIST`             | `yes`                                                   | Multisite | Nein     | **Blacklist aktivieren:** Setzen Sie auf `yes`, um die Blacklist-Funktion zu aktivieren.                                                               |
| `BLACKLIST_COMMUNITY_LISTS` | `ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents` | Multisite | Nein     | **Community-Blacklists:** Wählen Sie vorkonfigurierte und von der Community gepflegte Blacklists aus, die in die Blockierung einbezogen werden sollen. |

=== "Community-Blacklists"
    **Was es bewirkt:** Ermöglicht Ihnen, schnell gut gepflegte und von der Community stammende Blacklists hinzuzufügen, ohne die URLs manuell konfigurieren zu müssen.

    Der Parameter `BLACKLIST_COMMUNITY_LISTS` ermöglicht Ihnen die Auswahl aus ausgewählten Blacklist-Quellen. Die verfügbaren Optionen umfassen:

    | ID                                        | Beschreibung                                                                                                                                                                                                              | Quelle                                                                                                                                |
    | :---------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------ |
    | `ip:danmeuk-tor-exit`                     | IP-Adressen von Tor-Exit-Nodes (dan.me.uk)                                                                                                                                                                                | `https://www.dan.me.uk/torlist/?exit`                                                                                                 |
    | `ua:mitchellkrogza-bad-user-agents`       | Nginx Block Bad Bots, Spam Referrer Blocker, Vulnerability Scanners, User-Agents, Malware, Adware, Ransomware, Malicious Sites, mit Anti-DDOS, Wordpress Theme Detector Blocking und Fail2Ban Jail für Wiederholungstäter | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list`        |
    | `ip:laurent-minne-data-shield-aggressive` | Data-Shield IPv4 Blocklist - Laurent M. - Für Web Apps, WordPress, VPS (Apache/Nginx)                                                                                                                                     | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_data-shield_ipv4_blocklist.txt`          |
    | `ip:laurent-minne-data-shield-critical`   | Data-Shield IPv4 Blocklist - Laurent M. - Für DMZs, SaaS, API & Kritische Assets                                                                                                                                          | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_critical_data-shield_ipv4_blocklist.txt` |

    **Konfiguration:** Geben Sie mehrere Listen durch Leerzeichen getrennt an. Zum Beispiel:
    ```yaml
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    !!! tip "Community-Listen vs. manuelle Konfiguration"
        Community-Blacklists bieten eine bequeme Möglichkeit, mit bewährten Blacklist-Quellen zu beginnen. Sie können diese parallel zu manuellen URL-Konfigurationen für maximale Flexibilität verwenden.

    !!! note "Danksagung"
        Vielen Dank an Laurent Minne für den Beitrag der [Data-Shield-Blocklisten](https://duggytuxy.github.io/#)!

=== "IP-Adresse"
    **Was es bewirkt:** Blockiert Besucher basierend auf ihrer IP-Adresse oder ihrem Netzwerk.

    | Parameter                  | Standard                              | Kontext   | Mehrfach | Beschreibung                                                                                                                 |
    | :------------------------- | :------------------------------------ | :-------- | :------- | :--------------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_IP`             |                                       | Multisite | Nein     | **IP-Blacklist:** Liste von IP-Adressen oder Netzwerken (CIDR-Notation) zum Blockieren, durch Leerzeichen getrennt.          |
    | `BLACKLIST_IGNORE_IP`      |                                       | Multisite | Nein     | **IP-Ignorierliste:** Liste von IP-Adressen oder Netzwerken, die IP-Blacklist-Überprüfungen umgehen sollen.                  |
    | `BLACKLIST_IP_URLS`        | `https://www.dan.me.uk/torlist/?exit` | Multisite | Nein     | **IP-Blacklist-URLs:** Liste von URLs, die zu blockierende IP-Adressen oder Netzwerke enthalten, durch Leerzeichen getrennt. |
    | `BLACKLIST_IGNORE_IP_URLS` |                                       | Multisite | Nein     | **IP-Ignorierlisten-URLs:** Liste von URLs, die zu ignorierende IP-Adressen oder Netzwerke enthalten.                        |

    Der Standardparameter `BLACKLIST_IP_URLS` enthält eine URL, die eine **Liste bekannter Tor-Exit-Nodes** bereitstellt. Dies ist eine häufige Quelle für bösartigen Datenverkehr und ein guter Ausgangspunkt für viele Websites.

=== "Reverse DNS"
    **Was es bewirkt:** Blockiert Besucher basierend auf ihrem Reverse-Domain-Namen. Dies ist nützlich, um bekannte Scanner und Crawler basierend auf ihren Organisationsdomänen zu blockieren.

    | Parameter                    | Standard                | Kontext   | Mehrfach | Beschreibung                                                                                               |
    | :--------------------------- | :---------------------- | :-------- | :------- | :--------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_RDNS`             | `.shodan.io .censys.io` | Multisite | Nein     | **rDNS-Blacklist:** Liste von Reverse-DNS-Suffixen zum Blockieren, durch Leerzeichen getrennt.             |
    | `BLACKLIST_RDNS_GLOBAL`      | `yes`                   | Multisite | Nein     | **Nur globales rDNS:** Führt rDNS-Überprüfungen nur für globale IP-Adressen durch, wenn auf `yes` gesetzt. |
    | `BLACKLIST_IGNORE_RDNS`      |                         | Multisite | Nein     | **rDNS-Ignorierliste:** Liste von Reverse-DNS-Suffixen, die rDNS-Blacklist-Überprüfungen umgehen sollen.   |
    | `BLACKLIST_RDNS_URLS`        |                         | Multisite | Nein     | **rDNS-Blacklist-URLs:** Liste von URLs, die zu blockierende Reverse-DNS-Suffixe enthalten.                |
    | `BLACKLIST_IGNORE_RDNS_URLS` |                         | Multisite | Nein     | **rDNS-Ignorierlisten-URLs:** Liste von URLs, die zu ignorierende Reverse-DNS-Suffixe enthalten.           |

    Der Standardparameter `BLACKLIST_RDNS` enthält Domänen gängiger Scanner wie **Shodan** und **Censys**. Diese werden oft von Sicherheitsforschern und Scannern verwendet, um anfällige Websites zu identifizieren.

=== "ASN"
    **Was es bewirkt:** Blockiert Besucher von bestimmten Netzwerkanbietern. ASNs sind wie Postleitzahlen für das Internet – sie identifizieren, zu welchem Anbieter oder welcher Organisation eine IP gehört.

    | Parameter                   | Standard | Kontext   | Mehrfach | Beschreibung                                                                                     |
    | :-------------------------- | :------- | :-------- | :------- | :----------------------------------------------------------------------------------------------- |
    | `BLACKLIST_ASN`             |          | Multisite | Nein     | **ASN-Blacklist:** Liste von autonomen Systemnummern zum Blockieren, durch Leerzeichen getrennt. |
    | `BLACKLIST_IGNORE_ASN`      |          | Multisite | Nein     | **ASN-Ignorierliste:** Liste von ASNs, die ASN-Blacklist-Überprüfungen umgehen sollen.           |
    | `BLACKLIST_ASN_URLS`        |          | Multisite | Nein     | **ASN-Blacklist-URLs:** Liste von URLs, die zu blockierende ASNs enthalten.                      |
    | `BLACKLIST_IGNORE_ASN_URLS` |          | Multisite | Nein     | **ASN-Ignorierlisten-URLs:** Liste von URLs, die zu ignorierende ASNs enthalten.                 |

=== "User-Agent"
    **Was es bewirkt:** Blockiert Besucher basierend auf dem Browser oder Tool, das sie angeblich verwenden. Dies ist effektiv gegen Bots, die sich ehrlich identifizieren (wie "ScannerBot" oder "WebHarvestTool").

    | Parameter                          | Standard                                                                                                                       | Kontext   | Mehrfach | Beschreibung                                                                                                       |
    | :--------------------------------- | :----------------------------------------------------------------------------------------------------------------------------- | :-------- | :------- | :----------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_USER_AGENT`             |                                                                                                                                | Multisite | Nein     | **User-Agent-Blacklist:** Liste von User-Agent-Mustern (PCRE-Regex) zum Blockieren, durch Leerzeichen getrennt.    |
    | `BLACKLIST_IGNORE_USER_AGENT`      |                                                                                                                                | Multisite | Nein     | **User-Agent-Ignorierliste:** Liste von User-Agent-Mustern, die User-Agent-Blacklist-Überprüfungen umgehen sollen. |
    | `BLACKLIST_USER_AGENT_URLS`        | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` | Multisite | Nein     | **User-Agent-Blacklist-URLs:** Liste von URLs, die zu blockierende User-Agent-Muster enthalten.                    |
    | `BLACKLIST_IGNORE_USER_AGENT_URLS` |                                                                                                                                | Multisite | Nein     | **User-Agent-Ignorierlisten-URLs:** Liste von URLs, die zu ignorierende User-Agent-Muster enthalten.               |

    Der Standardparameter `BLACKLIST_USER_AGENT_URLS` enthält eine URL, die eine **Liste bekannter bösartiger User-Agents** bereitstellt. Diese werden oft von bösartigen Bots und Scannern verwendet, um anfällige Websites zu identifizieren.

=== "URI"
    **Was es bewirkt:** Blockiert Anfragen an spezifische URLs auf Ihrer Website. Dies ist nützlich, um Zugriffsversuche auf Admin-Seiten, Anmeldeformulare oder andere sensible Bereiche zu blockieren, die angegriffen werden könnten.

    | Parameter                   | Standard | Kontext   | Mehrfach | Beschreibung                                                                                      |
    | :-------------------------- | :------- | :-------- | :------- | :------------------------------------------------------------------------------------------------ |
    | `BLACKLIST_URI`             |          | Multisite | Nein     | **URI-Blacklist:** Liste von URI-Mustern (PCRE-Regex) zum Blockieren, durch Leerzeichen getrennt. |
    | `BLACKLIST_IGNORE_URI`      |          | Multisite | Nein     | **URI-Ignorierliste:** Liste von URI-Mustern, die URI-Blacklist-Überprüfungen umgehen sollen.     |
    | `BLACKLIST_URI_URLS`        |          | Multisite | Nein     | **URI-Blacklist-URLs:** Liste von URLs, die zu blockierende URI-Muster enthalten.                 |
    | `BLACKLIST_IGNORE_URI_URLS` |          | Multisite | Nein     | **URI-Ignorierlisten-URLs:** Liste von URLs, die zu ignorierende URI-Muster enthalten.            |

!!! info "Unterstützung von URL-Formaten"
    Alle `*_URLS`-Parameter unterstützen HTTP/HTTPS-URLs sowie lokale Dateipfade unter Verwendung des Präfixes `file:///`. Die Basisauthentifizierung wird im Format `http://user:pass@url` unterstützt.

!!! tip "Regelmäßige Updates"
    Blacklists von URLs werden automatisch stündlich heruntergeladen und aktualisiert, um sicherzustellen, dass Ihr Schutz gegen die neuesten Bedrohungen auf dem neuesten Stand bleibt.

### Konfigurationsbeispiele

=== "Grundlegender Schutz durch IP und User-Agent"

    Eine einfache Konfiguration, die bekannte Tor-Exit-Nodes und gängige bösartige User-Agents mithilfe der Community-Blacklists blockiert:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    Alternativ können Sie eine manuelle Konfiguration per URL verwenden:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Erweiterter Schutz mit benutzerdefinierten Regeln"

    Eine umfassendere Konfiguration mit benutzerdefinierten Blacklist-Einträgen und Ausnahmen:

    ```yaml
    USE_BLACKLIST: "yes"

    # Benutzerdefinierte Blacklist-Einträge
    BLACKLIST_IP: "192.168.1.100 203.0.113.0/24"
    BLACKLIST_RDNS: ".shodan.io .censys.io .scanner.com"
    BLACKLIST_ASN: "16509 14618"  # ASN von AWS und Amazon
    BLACKLIST_USER_AGENT: "(?:\b)SemrushBot(?:\b) (?:\b)AhrefsBot(?:\b)"
    BLACKLIST_URI: "^/wp-login\.php$ ^/administrator/"

    # Benutzerdefinierte Ignorierregeln
    BLACKLIST_IGNORE_IP: "192.168.1.200 203.0.113.42"

    # Externe Blacklist-Quellen
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit https://www.spamhaus.org/drop/drop.txt"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Verwendung lokaler Dateien"

    Konfiguration mit lokalen Dateien für Blacklists:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "file:///chemin/vers/ip-blacklist.txt"
    BLACKLIST_RDNS_URLS: "file:///chemin/vers/rdns-blacklist.txt"
    BLACKLIST_ASN_URLS: "file:///chemin/vers/asn-blacklist.txt"
    BLACKLIST_USER_AGENT_URLS: "file:///chemin/vers/user-agent-blacklist.txt"
    BLACKLIST_URI_URLS: "file:///chemin/vers/uri-blacklist.txt"
    ```

### Arbeiten mit lokalen Listendateien

Die `*_URLS`-Einstellungen der Whitelist-, Greylist- und Blacklist-Plugins verwenden denselben Downloader. Wenn Sie eine `file:///`-URL angeben:

- Der Pfad wird innerhalb des **Scheduler**-Containers aufgelöst (bei Docker-Bereitstellungen in der Regel `bunkerweb-scheduler`). Binden Sie die Dateien dort ein und stellen Sie sicher, dass der Scheduler-Benutzer Lesezugriff hat.
- Jede Datei ist eine UTF-8-codierte Textdatei mit einem Eintrag pro Zeile. Leere Zeilen werden ignoriert und Kommentarzeilen müssen mit `#` oder `;` beginnen. `//`-Kommentare werden nicht unterstützt.
- Erwartete Werte je Listentyp:
  - **IP-Listen** akzeptieren IPv4/IPv6-Adressen oder CIDR-Netzwerke (z. B. `192.0.2.10` oder `2001:db8::/48`).
  - **rDNS-Listen** erwarten ein Suffix ohne Leerzeichen (z. B. `.search.msn.com`). Werte werden automatisch in Kleinbuchstaben umgewandelt.
  - **ASN-Listen** können nur die Nummer (`32934`) oder die mit `AS` vorangestellte Nummer (`AS15169`) enthalten.
  - **User-Agent-Listen** werden als PCRE-Muster behandelt und die vollständige Zeile bleibt erhalten (einschließlich Leerzeichen). Schreiben Sie Kommentare in eine eigene Zeile, damit sie nicht als Muster interpretiert werden.
  - **URI-Listen** müssen mit `/` beginnen und dürfen PCRE-Tokens wie `^` oder `$` verwenden.

Beispieldateien im erwarteten Format:

```text
# /etc/bunkerweb/lists/ip-blacklist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-blacklist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```

## Brotli

STREAM-Unterstützung :x:

Das Brotli-Plugin aktiviert die Komprimierung von HTTP-Antworten mit dem Brotli-Algorithmus. Es reduziert die Bandbreitennutzung and beschleunigt das Laden, indem es Inhalte vor dem Senden an den Browser komprimiert.

Im Vergleich zu Gzip erreicht Brotli in der Regel bessere Kompressionsraten, was zu kleineren Dateien and einer schnelleren Bereitstellung führt.

So funktioniert's:

1. Auf Anfrage eines Clients prüft BunkerWeb, ob der Browser Brotli unterstützt.
2. Wenn ja, wird die Antwort auf dem konfigurierten Niveau (`BROTLI_COMP_LEVEL`) komprimiert.
3. Die entsprechenden Header zeigen die Brotli-Komprimierung an.
4. Der Browser dekomprimiert vor der Anzeige.
5. Bandbreite and Ladezeiten nehmen ab.

### So wird's verwendet

1. Aktivieren: `USE_BROTLI: yes` (standardmäßig deaktiviert).
2. MIME-Typen: Definieren Sie die zu komprimierenden Inhalte über `BROTLI_TYPES`.
3. Mindestgröße: `BROTLI_MIN_LENGTH`, um die Komprimierung kleiner Antworten zu vermeiden.
4. Komprimierungsstufe: `BROTLI_COMP_LEVEL` für das Gleichgewicht zwischen Geschwindigkeit and Verhältnis.

### Parameter

| Parameter           | Standard                                                                                                                                                                                                                                                                                                                                                                                                                         | Kontext   | Mehrfach | Beschreibung                                              |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | --------------------------------------------------------- |
| `USE_BROTLI`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | Multisite | nein     | Brotli-Komprimierung aktivieren.                          |
| `BROTLI_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | Multisite | nein     | Komprimierte MIME-Typen.                                  |
| `BROTLI_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | Multisite | nein     | Mindestgröße (Bytes) für die Anwendung der Komprimierung. |
| `BROTLI_COMP_LEVEL` | `6`                                                                                                                                                                                                                                                                                                                                                                                                                              | Multisite | nein     | Stufe 0–11: höher = bessere Komprimierung, aber mehr CPU. |

!!! tip "Komprimierungsstufe"
    `6` bietet einen guten Kompromiss. Für statische Inhalte and verfügbare CPU: 9–11. Für dynamische Inhalte oder bei CPU-Einschränkungen: 4–5.

### Beispiele

=== "Basis"

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json application/xml application/xhtml+xml text/css text/html text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "6"
    ```

=== "Maximale Komprimierung"

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "500"
    BROTLI_COMP_LEVEL: "11"
    ```

=== "Ausgewogene Leistung"

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "4"
    ```

## BunkerNet

STREAM-Unterstützung :white_check_mark:

Das BunkerNet-Plugin ermöglicht den kollektiven Austausch von Bedrohungsdaten zwischen BunkerWeb-Instanzen und schafft so ein leistungsstarkes Schutznetzwerk gegen böswillige Akteure. Durch die Teilnahme an BunkerNet profitiert Ihre Instanz von einer globalen Datenbank bekannter Bedrohungen und trägt gleichzeitig dazu bei, die Sicherheit der gesamten BunkerWeb-Community zu verbessern.

**So funktioniert es:**

1.  Ihre BunkerWeb-Instanz registriert sich automatisch bei der BunkerNet-API, um eine eindeutige Kennung zu erhalten.
2.  Wenn Ihre Instanz eine bösartige IP-Adresse oder ein bösartiges Verhalten erkennt und blockiert, meldet sie die Bedrohung anonym an BunkerNet.
3.  BunkerNet sammelt Bedrohungsdaten von allen teilnehmenden Instanzen und verteilt die konsolidierte Datenbank.
4.  Ihre Instanz lädt regelmäßig eine aktualisierte Datenbank bekannter Bedrohungen von BunkerNet herunter.
5.  Diese kollektive Intelligenz ermöglicht es Ihrer Instanz, proaktiv IP-Adressen zu blockieren, die auf anderen BunkerWeb-Instanzen bösartiges Verhalten gezeigt haben.

!!! success "Wichtige Vorteile"

      1. **Kollektive Verteidigung:** Nutzen Sie die Sicherheitserkenntnisse von Tausenden anderer BunkerWeb-Instanzen weltweit.
      2. **Proaktiver Schutz:** Blockieren Sie böswillige Akteure, bevor sie Ihre Website angreifen können, basierend auf ihrem Verhalten an anderer Stelle.
      3. **Beitrag zur Gemeinschaft:** Helfen Sie, andere BunkerWeb-Benutzer zu schützen, indem Sie anonymisierte Bedrohungsdaten über Angreifer teilen.
      4. **Keine Konfiguration erforderlich:** Funktioniert standardmäßig mit sinnvollen Voreinstellungen und erfordert nur minimale Einrichtung.
      5. **Datenschutzorientiert:** Teilt nur notwendige Bedrohungsinformationen, ohne Ihre Privatsphäre oder die Ihrer Benutzer zu gefährden.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die BunkerNet-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die BunkerNet-Funktion ist standardmäßig aktiviert. Bei Bedarf können Sie dies mit der Einstellung `USE_BUNKERNET` steuern.
2.  **Erstregistrierung:** Beim ersten Start registriert sich Ihre Instanz automatisch bei der BunkerNet-API und erhält eine eindeutige Kennung.
3.  **Automatische Updates:** Ihre Instanz lädt automatisch in regelmäßigen Abständen die neueste Bedrohungsdatenbank herunter.
4.  **Automatisches Melden:** Wenn Ihre Instanz eine bösartige IP-Adresse blockiert, trägt sie diese Daten automatisch zur Gemeinschaft bei.
5.  **Schutz überwachen:** Überprüfen Sie die [Web-Benutzeroberfläche](web-ui.md), um Statistiken zu den von BunkerNet-Informationen blockierten Bedrohungen anzuzeigen.

### Konfigurationseinstellungen

| Einstellung        | Standard                   | Kontext   | Mehrfach | Beschreibung                                                                                       |
| ------------------ | -------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------- |
| `USE_BUNKERNET`    | `yes`                      | multisite | nein     | **BunkerNet aktivieren:** Auf `yes` setzen, um den Austausch von Bedrohungsdaten zu aktivieren.    |
| `BUNKERNET_SERVER` | `https://api.bunkerweb.io` | global    | nein     | **BunkerNet-Server:** Die Adresse des BunkerNet-API-Servers für den Austausch von Bedrohungsdaten. |

!!! tip "Netzwerkschutz"
    Wenn BunkerNet feststellt, dass eine IP-Adresse an bösartigen Aktivitäten auf mehreren BunkerWeb-Instanzen beteiligt war, wird diese IP zu einer kollektiven schwarzen Liste hinzugefügt. Dies bietet eine proaktive Verteidigungsebene, die Ihre Website vor Bedrohungen schützt, bevor sie Sie direkt angreifen können.

!!! info "Anonymes Melden"
    Bei der Meldung von Bedrohungsinformationen an BunkerNet teilt Ihre Instanz nur die zur Identifizierung der Bedrohung erforderlichen Daten: die IP-Adresse, den Grund für die Sperrung und minimale kontextbezogene Daten. Es werden keine persönlichen Informationen über Ihre Benutzer oder sensible Details über Ihre Website weitergegeben.

### Beispielkonfigurationen

=== "Standardkonfiguration (empfohlen)"

    Die Standardkonfiguration aktiviert BunkerNet mit dem offiziellen BunkerWeb-API-Server:

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://api.bunkerweb.io"
    ```

=== "Deaktivierte Konfiguration"

    Wenn Sie nicht am BunkerNet-Bedrohungsdatennetzwerk teilnehmen möchten:

    ```yaml
    USE_BUNKERNET: "no"
    ```

=== "Benutzerdefinierte Serverkonfiguration"

    Für Organisationen, die ihren eigenen BunkerNet-Server betreiben (ungewöhnlich):

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://bunkernet.example.com"
    ```

### Integration der CrowdSec-Konsole

Falls Sie noch nicht mit der CrowdSec-Konsolenintegration vertraut sind: [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) nutzt crowdsourced Intelligence zur Bekämpfung von Cyber-Bedrohungen. Stellen Sie es sich als das „Waze der Cybersicherheit“ vor – wenn ein Server angegriffen wird, werden andere Systeme weltweit alarmiert und vor denselben Angreifern geschützt. Mehr darüber erfahren Sie [hier](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

Durch unsere Partnerschaft mit CrowdSec können Sie Ihre BunkerWeb-Instanzen in Ihre [CrowdSec-Konsole](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration) eintragen. Das bedeutet, dass von BunkerWeb blockierte Angriffe in Ihrer CrowdSec-Konsole neben den von CrowdSec Security Engines blockierten Angriffen sichtbar sind, was Ihnen einen einheitlichen Überblick über Bedrohungen gibt.

Wichtig ist, dass CrowdSec für diese Integration nicht installiert sein muss (obwohl wir dringend empfehlen, es mit dem [CrowdSec-Plugin für BunkerWeb](https://github.com/bunkerity/bunkerweb-plugins/tree/main/crowdsec) auszuprobieren, um die Sicherheit Ihrer Webdienste weiter zu erhöhen). Zusätzlich können Sie Ihre CrowdSec Security Engines in dasselbe Konsolenkonto eintragen, um eine noch größere Synergie zu erzielen.

**Schritt 1: Erstellen Sie Ihr CrowdSec-Konsolenkonto**

Gehen Sie zur [CrowdSec-Konsole](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration) und registrieren Sie sich, falls Sie noch kein Konto haben. Notieren Sie sich anschließend den Anmeldeschlüssel, den Sie unter „Security Engines“ finden, nachdem Sie auf „Add Security Engine“ geklickt haben:

<figure markdown>
  ![Overview](assets/img/crowdity1.png){ align=center }
  <figcaption>Holen Sie sich Ihren CrowdSec-Konsolen-Anmeldeschlüssel</figcaption>
</figure>

**Schritt 2: Holen Sie sich Ihre BunkerNet-ID**

Die Aktivierung der BunkerNet-Funktion (standardmäßig aktiviert) ist obligatorisch, wenn Sie Ihre BunkerWeb-Instanz(en) in Ihrer CrowdSec-Konsole registrieren möchten. Aktivieren Sie sie, indem Sie `USE_BUNKERNET` auf `yes` setzen.

Für Docker erhalten Sie Ihre BunkerNet-ID mit:

```shell
docker exec my-bw-scheduler cat /var/cache/bunkerweb/bunkernet/instance.id
```

Für Linux verwenden Sie:

```shell
cat /var/cache/bunkerweb/bunkernet/instance.id
```

**Schritt 3: Registrieren Sie Ihre Instanz über das Panel**

Sobald Sie Ihre BunkerNet-ID und den CrowdSec-Konsolen-Anmeldeschlüssel haben, [bestellen Sie das kostenlose Produkt „BunkerNet / CrowdSec“ im Panel](https://panel.bunkerweb.io/store/bunkernet?utm_campaign=self&utm_source=doc). Möglicherweise werden Sie aufgefordert, ein Konto zu erstellen, falls Sie noch keines haben.

Sie können nun den Dienst „BunkerNet / CrowdSec“ auswählen und das Formular ausfüllen, indem Sie Ihre BunkerNet-ID und den CrowdSec-Konsolen-Anmeldeschlüssel einfügen:

<figure markdown>
  ![Overview](assets/img/crowdity2.png){ align=center }
  <figcaption>Registrieren Sie Ihre BunkerWeb-Instanz in der CrowdSec-Konsole</figcaption>
</figure>

**Schritt 4: Akzeptieren Sie die neue Security Engine in der Konsole**

Gehen Sie dann zurück zu Ihrer CrowdSec-Konsole und akzeptieren Sie die neue Security Engine:

<figure markdown>
  ![Overview](assets/img/crowdity3.png){ align=center }
  <figcaption>Akzeptieren Sie die Registrierung in der CrowdSec-Konsole</figcaption>
</figure>

**Herzlichen Glückwunsch, Ihre BunkerWeb-Instanz ist jetzt in Ihrer CrowdSec-Konsole registriert!**

Profi-Tipp: Wenn Sie Ihre Warnungen anzeigen, klicken Sie auf die Option „Spalten“ und aktivieren Sie das Kontrollkästchen „Kontext“, um auf BunkerWeb-spezifische Daten zuzugreifen.

<figure markdown>
  ![Overview](assets/img/crowdity4.png){ align=center }
  <figcaption>BunkerWeb-Daten werden in der Kontextspalte angezeigt</figcaption>
</figure>

## CORS

STREAM-Unterstützung :x:

Das CORS-Plugin ermöglicht Cross-Origin Resource Sharing (Ressourcenfreigabe zwischen verschiedenen Ursprüngen) für Ihre Website und erlaubt so den kontrollierten Zugriff auf Ihre Ressourcen von verschiedenen Domains aus. Diese Funktion hilft Ihnen, Ihre Inhalte sicher mit vertrauenswürdigen Drittanbieter-Websites zu teilen, während die Sicherheit durch die explizite Definition der erlaubten Ursprünge, Methoden und Header gewährleistet wird.

**So funktioniert es:**

1.  Wenn ein Browser eine Cross-Origin-Anfrage an Ihre Website stellt, sendet er zuerst eine Preflight-Anfrage mit der `OPTIONS`-Methode.
2.  BunkerWeb prüft, ob der anfragende Ursprung basierend auf Ihrer Konfiguration zulässig ist.
3.  Wenn dies der Fall ist, antwortet BunkerWeb mit den entsprechenden CORS-Headern, die definieren, was die anfragende Website tun darf.
4.  Bei nicht zulässigen Ursprüngen kann die Anfrage entweder komplett verweigert oder ohne CORS-Header ausgeliefert werden.
5.  Zusätzliche Cross-Origin-Richtlinien wie [COEP](https://developer.mozilla.org/de/docs/Web/HTTP/Headers/Cross-Origin-Embedder-Policy), [COOP](https://developer.mozilla.org/de/docs/Web/HTTP/Headers/Cross-Origin-Opener-Policy) und [CORP](https://developer.mozilla.org/de/docs/Web/HTTP/Headers/Cross-Origin-Resource-Policy) können konfiguriert werden, um die Sicherheit weiter zu erhöhen.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die CORS-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die CORS-Funktion ist standardmäßig deaktiviert. Setzen Sie die Einstellung `USE_CORS` auf `yes`, um sie zu aktivieren.
2.  **Erlaubte Ursprünge konfigurieren:** Geben Sie mit der Einstellung `CORS_ALLOW_ORIGIN` an, welche Domains auf Ihre Ressourcen zugreifen dürfen.
3.  **Zulässige Methoden festlegen:** Definieren Sie mit `CORS_ALLOW_METHODS`, welche HTTP-Methoden für Cross-Origin-Anfragen erlaubt sind.
4.  **Erlaubte Header konfigurieren:** Geben Sie mit `CORS_ALLOW_HEADERS` an, welche Header in Anfragen verwendet werden dürfen.
5.  **Anmeldeinformationen steuern:** Entscheiden Sie mit `CORS_ALLOW_CREDENTIALS`, ob Cross-Origin-Anfragen Anmeldeinformationen enthalten dürfen.

### Konfigurationseinstellungen

| Einstellung                    | Standard                                                                             | Kontext   | Mehrfach | Beschreibung                                                                                                                              |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CORS`                     | `no`                                                                                 | multisite | nein     | **CORS aktivieren:** Auf `yes` setzen, um Cross-Origin Resource Sharing zu aktivieren.                                                    |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | nein     | **Erlaubte Ursprünge:** PCRE-regulärer Ausdruck für erlaubte Ursprünge; `*` für jeden Ursprung, `self` nur für denselben Ursprung.        |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | nein     | **Erlaubte Methoden:** HTTP-Methoden, die bei Cross-Origin-Anfragen verwendet werden können.                                              |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | nein     | **Erlaubte Header:** HTTP-Header, die bei Cross-Origin-Anfragen verwendet werden können.                                                  |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | nein     | **Anmeldeinformationen erlauben:** Auf `yes` setzen, um Anmeldeinformationen (Cookies, HTTP-Auth) in CORS-Anfragen zu erlauben.           |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | nein     | **Verfügbar gemachte Header:** HTTP-Header, auf die Browser von Cross-Origin-Antworten zugreifen dürfen.                                  |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | nein     | **Cross-Origin-Opener-Policy:** Steuert die Kommunikation zwischen Browser-Kontexten.                                                     |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | nein     | **Cross-Origin-Embedder-Policy:** Steuert, ob ein Dokument Ressourcen von anderen Ursprüngen laden kann.                                  |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | nein     | **Cross-Origin-Resource-Policy:** Steuert, welche Websites Ihre Ressourcen einbetten dürfen.                                              |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | nein     | **Cache-Dauer für Preflight:** Wie lange (in Sekunden) Browser die Preflight-Antwort zwischenspeichern sollen.                            |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | nein     | **Nicht autorisierte Ursprünge ablehnen:** Wenn `yes`, werden Anfragen von nicht autorisierten Ursprüngen mit einem Fehlercode abgelehnt. |

!!! tip "Optimierung von Preflight-Anfragen"
    Die Einstellung `CORS_MAX_AGE` bestimmt, wie lange Browser die Ergebnisse einer Preflight-Anfrage zwischenspeichern. Ein höherer Wert (wie der Standardwert von 86400 Sekunden/24 Stunden) reduziert die Anzahl der Preflight-Anfragen und verbessert die Leistung für häufig aufgerufene Ressourcen.

!!! warning "Sicherheitshinweise"
    Seien Sie vorsichtig, wenn Sie `CORS_ALLOW_ORIGIN` auf `*` (alle Ursprünge) oder `CORS_ALLOW_CREDENTIALS` auf `yes` setzen, da diese Konfigurationen bei unsachgemäßer Verwaltung Sicherheitsrisiken mit sich bringen können. Es ist im Allgemeinen sicherer, vertrauenswürdige Ursprünge explizit aufzulisten und die erlaubten Methoden und Header zu beschränken.

### Beispielkonfigurationen

Hier sind Beispiele für mögliche Werte der Einstellung `CORS_ALLOW_ORIGIN` und deren Verhalten:

- **`*`**: Erlaubt Anfragen von allen Ursprüngen.
- **`self`**: Erlaubt automatisch Anfragen vom selben Ursprung wie der konfigurierte `server_name`.
- **`^https://www\.example\.com$`**: Erlaubt Anfragen nur von `https://www.example.com`.
- **`^https://.+\.example\.com$`**: Erlaubt Anfragen von jeder Subdomain, die auf `.example.com` endet.
- **`^https://(www\.example1\.com|www\.example2\.com)$`**: Erlaubt Anfragen entweder von `https://www.example1.com` oder `https://www.example2.com`.
- **`^https?://www\.example\.com$`**: Erlaubt Anfragen sowohl von `https://www.example.com` als auch von `http://www.example.com`.

=== "Grundlegende Konfiguration"

    Eine einfache Konfiguration, die Cross-Origin-Anfragen von derselben Domain erlaubt:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "self"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Konfiguration für öffentliche API"

    Konfiguration für eine öffentliche API, die von jedem Ursprung aus zugänglich sein muss:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "*"
    CORS_ALLOW_METHODS: "GET, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, X-API-Key"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "3600"
    CORS_DENY_REQUEST: "no"
    ```

=== "Mehrere vertrauenswürdige Domains"

    Konfiguration, die mehrere spezifische Domains mit einem einzigen PCRE-regulären Ausdrucksmuster erlaubt:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(app|api|dashboard)\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, DELETE, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Requested-With"
    CORS_ALLOW_CREDENTIALS: "yes"
    CORS_EXPOSE_HEADERS: "Content-Length, Content-Range, X-RateLimit-Remaining"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Subdomain-Platzhalter"

    Konfiguration, die alle Subdomains einer Hauptdomain mithilfe eines PCRE-regulären Ausdrucksmusters erlaubt:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://.*\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Mehrere Domain-Muster"

    Konfiguration, die Anfragen von mehreren Domain-Mustern mit Alternation erlaubt:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(.*\\.example\\.com|.*\\.trusted-partner\\.org|api\\.third-party\\.net)$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Custom-Header"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

## Cache <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM-Unterstützung :x:

Provides caching functionality at the reverse proxy level.

| Einstellung                 | Standardwert                      | Kontext   | Mehrfach | Beschreibung                                                                   |
| --------------------------- | --------------------------------- | --------- | -------- | ------------------------------------------------------------------------------ |
| `CACHE_PATH`                |                                   | global    | ja       | Path and parameters for a cache.                                               |
| `CACHE_ZONE`                |                                   | multisite | nein     | Name of cache zone to use (specified in a CACHE_PATH setting).                 |
| `CACHE_HEADER`              | `X-Cache`                         | multisite | nein     | Add header about cache status.                                                 |
| `CACHE_BACKGROUND_UPDATE`   | `no`                              | multisite | nein     | Enable or disable background update of the cache.                              |
| `CACHE_BYPASS`              |                                   | multisite | nein     | List of variables to determine if the cache should be bypassed or not.         |
| `CACHE_NO_CACHE`            | `$http_pragma$http_authorization` | multisite | nein     | Disable caching if variables are set.                                          |
| `CACHE_KEY`                 | `$scheme$proxy_host$request_uri`  | multisite | nein     | Key used to identify cached elements.                                          |
| `CACHE_CONVERT_HEAD_TO_GET` | `yes`                             | multisite | nein     | Convert HEAD requests to GET when caching.                                     |
| `CACHE_LOCK`                | `no`                              | multisite | nein     | Lock concurrent requests when populating the cache.                            |
| `CACHE_LOCK_AGE`            | `5s`                              | multisite | nein     | Pass request to upstream if cache is locked for that time (possible cache).    |
| `CACHE_LOCK_TIMEOUT`        | `5s`                              | multisite | nein     | Pass request to upstream if cache is locked for that time (no cache).          |
| `CACHE_METHODS`             | `GET HEAD`                        | multisite | nein     | Only cache response if corresponding method is present.                        |
| `CACHE_MIN_USES`            | `1`                               | multisite | nein     | Number of requests before we put the corresponding response in cache.          |
| `CACHE_REVALIDATE`          | `no`                              | multisite | nein     | Revalidate expired items using conditional requests to upstream.               |
| `CACHE_USE_STALE`           | `off`                             | multisite | nein     | Determines the use of staled cache response (proxy_cache_use_stale directive). |
| `CACHE_VALID`               | `10m`                             | multisite | ja       | Defines default caching with optional status code.                             |

## Client cache

STREAM-Unterstützung :x:

Das Client-Cache-Plugin optimiert die Leistung von Websites, indem es steuert, wie Browser statische Inhalte zwischenspeichern. Es reduziert die Bandbreitennutzung, senkt die Serverlast und verbessert die Ladezeiten von Seiten, indem es Browser anweist, statische Assets wie Bilder, CSS- und JavaScript-Dateien lokal zu speichern und wiederzuverwenden, anstatt sie bei jedem Seitenbesuch erneut anzufordern.

**So funktioniert es:**

1.  Wenn aktiviert, fügt BunkerWeb den Antworten für statische Dateien Cache-Control-Header hinzu.
2.  Diese Header teilen den Browsern mit, wie lange sie den Inhalt lokal zwischenspeichern sollen.
3.  Für Dateien mit bestimmten Erweiterungen (wie Bilder, CSS, JavaScript) wendet BunkerWeb die konfigurierte Caching-Richtlinie an.
4.  Die optionale ETag-Unterstützung bietet einen zusätzlichen Validierungsmechanismus, um festzustellen, ob der zwischengespeicherte Inhalt noch aktuell ist.
5.  Wenn Besucher auf Ihre Website zurückkehren, können ihre Browser lokal zwischengespeicherte Dateien verwenden, anstatt sie erneut herunterzuladen, was zu schnelleren Ladezeiten der Seite führt.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Client-Cache-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die Client-Cache-Funktion ist standardmäßig deaktiviert. Setzen Sie die Einstellung `USE_CLIENT_CACHE` auf `yes`, um sie zu aktivieren.
2.  **Dateierweiterungen konfigurieren:** Geben Sie mit der Einstellung `CLIENT_CACHE_EXTENSIONS` an, welche Dateitypen zwischengespeichert werden sollen.
3.  **Cache-Control-Anweisungen festlegen:** Passen Sie mit der Einstellung `CLIENT_CACHE_CONTROL` an, wie Clients Inhalte zwischenspeichern sollen.
4.  **ETag-Unterstützung konfigurieren:** Entscheiden Sie mit der Einstellung `CLIENT_CACHE_ETAG`, ob ETags zur Validierung der Cache-Frische aktiviert werden sollen.
5.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration werden Caching-Header automatisch auf berechtigte Antworten angewendet.

### Konfigurationseinstellungen

| Einstellung               | Standard                   | Kontext   | Mehrfach | Beschreibung                                                                                                      |
| ------------------------- | -------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------- | --- |
| `USE_CLIENT_CACHE`        | `no`                       | multisite | nein     | **Client-Cache aktivieren:** Auf `yes` setzen, um das clientseitige Caching von statischen Dateien zu aktivieren. |
| `CLIENT_CACHE_EXTENSIONS` | `jpg                       | jpeg      | png      | bmp                                                                                                               | ico | svg | tif | css | js | otf | ttf | eot | woff | woff2` | global | nein | **Cache-fähige Erweiterungen:** Liste der Dateierweiterungen (getrennt durch ` | `), die vom Client zwischengespeichert werden sollen. |
| `CLIENT_CACHE_CONTROL`    | `public, max-age=15552000` | multisite | nein     | **Cache-Control-Header:** Wert für den Cache-Control-HTTP-Header zur Steuerung des Caching-Verhaltens.            |
| `CLIENT_CACHE_ETAG`       | `yes`                      | multisite | nein     | **ETags aktivieren:** Auf `yes` setzen, um den HTTP-ETag-Header für statische Ressourcen zu senden.               |

!!! tip "Optimierung der Cache-Einstellungen"
    Für häufig aktualisierte Inhalte sollten Sie kürzere `max-age`-Werte verwenden. Für Inhalte, die sich selten ändern (wie versionierte JavaScript-Bibliotheken oder Logos), verwenden Sie längere Cache-Zeiten. Der Standardwert von 15552000 Sekunden (180 Tage) ist für die meisten statischen Assets angemessen.

!!! info "Browser-Verhalten"
    Unterschiedliche Browser implementieren Caching geringfügig anders, aber alle modernen Browser respektieren die Standard-Cache-Control-Anweisungen. ETags bieten einen zusätzlichen Validierungsmechanismus, der Browsern hilft festzustellen, ob zwischengespeicherte Inhalte noch gültig sind.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine einfache Konfiguration, die das Caching für gängige statische Assets aktiviert:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|gif|css|js|svg|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=86400"  # 1 Tag
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Aggressives Caching"

    Eine für maximales Caching optimierte Konfiguration, geeignet für Websites mit selten aktualisierten statischen Inhalten:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2|pdf|xml|txt"
    CLIENT_CACHE_CONTROL: "public, max-age=31536000, immutable"  # 1 Jahr
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Strategie für gemischte Inhalte"

    Für Websites mit einer Mischung aus häufig und selten aktualisierten Inhalten sollten Sie die Dateiversionierung in Ihrer Anwendung und eine Konfiguration wie diese in Betracht ziehen:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=604800"  # 1 Woche
    CLIENT_CACHE_ETAG: "yes"
    ```

## Country

STREAM-Unterstützung :white_check_mark:

Das Länder-Plugin aktiviert Geoblocking und ermöglicht die Einschränkung des Zugriffs basierend auf dem geografischen Standort der Besucher. Dies ist nützlich für die Einhaltung regionaler Vorschriften, zur Begrenzung von Betrug in Risikogebieten und zur Anwendung von Inhaltsbeschränkungen über Ländergrenzen hinweg.

So funktioniert's:

1. Bei jedem Besuch ermittelt BunkerWeb das Herkunftsland über die IP-Adresse.
2. Ihre Konfiguration definiert eine Whitelist (erlaubt) oder Blacklist (blockiert).
3. Bei einer Whitelist: Nur die gelisteten Länder sind zugelassen.
4. Bei einer Blacklist: Die gelisteten Länder werden abgelehnt.
5. Das Ergebnis wird für wiederholte Besuche zwischengespeichert.

### Anwendung

1. Strategie: Wählen Sie eine Whitelist (wenige zugelassene Länder) oder eine Blacklist (bestimmte Länder blockieren).
2. Ländercodes: Fügen Sie ISO 3166-1 Alpha-2 Codes (US, GB, FR) zu `WHITELIST_COUNTRY` oder `BLACKLIST_COUNTRY` hinzu.
3. Anwendung: Nach der Konfiguration gilt die Beschränkung für alle Besucher.
4. Überwachung: Konsultieren Sie die [Web-UI](web-ui.md) für Statistiken nach Ländern.

### Parameter

| Parameter           | Standard | Kontext   | Mehrfach | Beschreibung                                                                                             |
| :------------------ | :------- | :-------- | :------- | :------------------------------------------------------------------------------------------------------- |
| `WHITELIST_COUNTRY` |          | Multisite | Nein     | Whitelist: ISO 3166-1 Alpha-2 Ländercodes, durch Leerzeichen getrennt. Nur diese Länder sind zugelassen. |
| `BLACKLIST_COUNTRY` |          | Multisite | Nein     | Blacklist: ISO 3166-1 Alpha-2 Ländercodes, durch Leerzeichen getrennt. Diese Länder sind blockiert.      |

!!! tip "Whitelist vs. Blacklist"
    Whitelist: Zugriff auf wenige Länder beschränkt. Blacklist: Problematische Regionen blockieren und den Rest zulassen.

!!! warning "Priorität"
    Wenn eine Whitelist und eine Blacklist definiert sind, hat die Whitelist Vorrang: Wenn das Land nicht auf der Whitelist steht, wird der Zugriff verweigert.

!!! info "Ländererkennung"
    BunkerWeb verwendet die mmdb-Datenbank [db-ip lite](https://db-ip.com/db/download/ip-to-country-lite).

### Beispiele

=== "Nur Whitelist"

    ```yaml
    WHITELIST_COUNTRY: "US CA GB"
    ```

=== "Nur Blacklist"

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP"
    ```

=== "Nur EU"

    ```yaml
    WHITELIST_COUNTRY: "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE"
    ```

=== "Blockierung von Risikoländern"

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP IR SY"
    ```

## CrowdSec

STREAM-Unterstützung :x:

<figure markdown>
  ![Overview](assets/img/crowdsec.svg){ align=center, width="600" }
</figure>

Das CrowdSec-Plugin integriert BunkerWeb mit der CrowdSec-Sicherheits-Engine und bietet eine zusätzliche Schutzschicht gegen verschiedene Cyberbedrohungen. Dieses Plugin fungiert als [CrowdSec-Bouncer](https://crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) und lehnt Anfragen basierend auf den Entscheidungen der CrowdSec-API ab.

CrowdSec ist eine moderne Open-Source-Sicherheits-Engine, die bösartige IP-Adressen basierend auf Verhaltensanalyse und der kollektiven Intelligenz ihrer Community erkennt und blockiert. Sie können auch [Szenarien](https://docs.crowdsec.net/docs/concepts?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios) konfigurieren, um IP-Adressen basierend auf verdächtigem Verhalten automatisch zu sperren und so von einer partizipativen Blacklist zu profitieren.

**So funktioniert's:**

1.  Die CrowdSec-Engine analysiert Protokolle und erkennt verdächtige Aktivitäten in Ihrer Infrastruktur.
2.  Wenn eine bösartige Aktivität erkannt wird, erstellt CrowdSec eine Entscheidung, die betreffende IP-Adresse zu blockieren.
3.  BunkerWeb, das als Bouncer fungiert, fragt die lokale CrowdSec-API nach Entscheidungen bezüglich eingehender Anfragen ab.
4.  Wenn die IP-Adresse eines Clients einer aktiven Blockierungsentscheidung unterliegt, verweigert BunkerWeb den Zugriff auf die geschützten Dienste.
5.  Optional kann die Anwendungssicherheitskomponente (Application Security Component) eine eingehende Überprüfung der Anfragen für erhöhte Sicherheit durchführen.

!!! success "Hauptvorteile"

      1.  **Community-Sicherheit:** Profitieren Sie von Bedrohungsinformationen, die von der CrowdSec-Benutzergemeinschaft geteilt werden.
      2.  **Verhaltensanalyse:** Erkennen Sie ausgeklügelte Angriffe basierend auf Verhaltensmustern, nicht nur auf Signaturen.
      3.  **Leichte Integration:** Minimaler Einfluss auf die Leistung Ihrer BunkerWeb-Instanz.
      4.  **Mehrstufiger Schutz:** Kombinieren Sie Perimeterverteidigung (IP-Blockierung) mit Anwendungssicherheit für einen umfassenden Schutz.

### Voraussetzungen

- Eine CrowdSec Local API, die von BunkerWeb erreicht werden kann (typischerweise der Agent auf demselben Host oder im selben Docker-Netzwerk).
- Zugriff auf die BunkerWeb-Zugriffsprotokolle (`/var/log/bunkerweb/access.log` standardmäßig), damit der CrowdSec-Agent Anfragen analysieren kann.
- Zugriff auf `cscli` auf dem CrowdSec-Host, um den BunkerWeb-Bouncer-Schlüssel zu registrieren.

### Integrationsablauf

1. CrowdSec so vorbereiten, dass der Agent die BunkerWeb-Protokolle einliest.
2. BunkerWeb konfigurieren, damit die CrowdSec Local API abgefragt wird.
3. Den Link über die API `/crowdsec/ping` oder die CrowdSec-Kachel im Admin-UI validieren.

Die folgenden Abschnitte führen diese Schritte im Detail durch.

### Schritt&nbsp;1 – CrowdSec auf das Einlesen von BunkerWeb-Protokollen vorbereiten

=== "Docker"
    **Akquisitionsdatei**

    Sie müssen eine CrowdSec-Instanz ausführen und diese so konfigurieren, dass sie die BunkerWeb-Protokolle analysiert. Verwenden Sie den dedizierten Wert `bunkerweb` für den Parameter `type` in Ihrer Akquisitionsdatei (vorausgesetzt, die BunkerWeb-Protokolle werden unverändert ohne zusätzliche Daten gespeichert):

    ```yaml
    filenames:
      - /var/log/bunkerweb.log
    labels:
      type: bunkerweb
    ```

    Wenn die Sammlung im CrowdSec-Container nicht angezeigt wird, führen Sie `docker exec -it <crowdsec-container> cscli hub update` aus und starten Sie anschließend diesen Container neu (`docker restart <crowdsec-container>`), damit die neuen Assets verfügbar werden. Ersetzen Sie `<crowdsec-container>` durch den Namen Ihres CrowdSec-Containers.

    **Anwendungssicherheitskomponente (*optional*)**

    CrowdSec bietet auch eine [Anwendungssicherheitskomponente](https://docs.crowdsec.net/docs/appsec/intro?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs), die zum Schutz Ihrer Anwendung vor Angriffen verwendet werden kann. Wenn Sie diese verwenden möchten, müssen Sie eine weitere Akquisitionsdatei für die AppSec-Komponente erstellen:

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    **Syslog**

    Für containerbasierte Integrationen empfehlen wir, die Protokolle des BunkerWeb-Containers an einen Syslog-Dienst umzuleiten, damit CrowdSec leicht darauf zugreifen kann. Hier ist ein Beispiel für eine syslog-ng-Konfiguration, die die Rohprotokolle von BunkerWeb in einer lokalen Datei `/var/log/bunkerweb.log` speichert:

    ```syslog
    @version: 4.10

    source s_net {
        udp(
            ip("0.0.0.0")
        );
    };

    template t_imp {
        template("$MSG\n");
        template_escape(no);
    };

    destination d_file {
        file("/var/log/bunkerweb.log" template(t_imp) logrotate(enable(yes), size(100MB), rotations(7)));
    };

    log {
        source(s_net);
        destination(d_file);
    };
    ```

    **Docker Compose**

    Hier ist die Docker-Compose-Vorlage, die Sie verwenden können (vergessen Sie nicht, den Bouncer-Schlüssel zu aktualisieren):

    ```yaml
    x-bw-env: &bw-env
      # Wir verwenden einen Anker, um die Wiederholung derselben Parameter für beide Dienste zu vermeiden
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Stellen Sie sicher, dass Sie den richtigen IP-Bereich festlegen, damit der Scheduler die Konfiguration an die Instanz senden kann

    services:
      bunkerweb:
        # Dies ist der Name, der zur Identifizierung der Instanz im Scheduler verwendet wird
        image: bunkerity/bunkerweb:1.6.8
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Für QUIC / HTTP3 Unterstützung
        environment:
          <<: *bw-env # Wir verwenden den Anker, um die Wiederholung derselben Parameter für alle Dienste zu vermeiden
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog # Protokolle an syslog senden
          options:
            syslog-address: "udp://10.20.30.254:514" # Die IP-Adresse des syslog-Dienstes

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Stellen Sie sicher, dass Sie den richtigen Instanznamen festlegen
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Vergessen Sie nicht, ein stärkeres Datenbankpasswort festzulegen
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_CROWDSEC: "yes"
          CROWDSEC_API: "http://crowdsec:8080" # Dies ist die Adresse der CrowdSec-Container-API im selben Netzwerk
          CROWDSEC_APPSEC_URL: "http://crowdsec:7422" # Auskommentieren, wenn Sie die AppSec-Komponente nicht verwenden möchten
          CROWDSEC_API_KEY: "s3cr3tb0unc3rk3y" # Vergessen Sie nicht, einen stärkeren Schlüssel für den Bouncer festzulegen
        volumes:
          - bw-storage:/data # Dies wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Wir legen die maximal zulässige Paketgröße fest, um Probleme mit großen Anfragen zu vermeiden
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Vergessen Sie nicht, ein stärkeres Datenbankpasswort festzulegen
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      crowdsec:
        image: crowdsecurity/crowdsec:v1.7.4 # Verwenden Sie die neueste Version, aber pinnen Sie immer die Version für bessere Stabilität/Sicherheit
        volumes:
          - cs-data:/var/lib/crowdsec/data # Zum Persistieren der CrowdSec-Daten
          - bw-logs:/var/log:ro # Die BunkerWeb-Protokolle, die von CrowdSec analysiert werden sollen
          - ./acquis.yaml:/etc/crowdsec/acquis.yaml # Die Akquisitionsdatei für die BunkerWeb-Protokolle
          - ./appsec.yaml:/etc/crowdsec/acquis.d/appsec.yaml # Auskommentieren, wenn Sie die AppSec-Komponente nicht verwenden möchten
        environment:
          BOUNCER_KEY_bunkerweb: "s3cr3tb0unc3rk3y" # Vergessen Sie nicht, einen stärkeren Schlüssel für den Bouncer festzulegen
          COLLECTIONS: "bunkerity/bunkerweb crowdsecurity/appsec-virtual-patching crowdsecurity/appsec-generic-rules"
          #   COLLECTIONS: "bunkerity/bunkerweb" # Wenn Sie die AppSec-Komponente nicht verwenden möchten, verwenden Sie stattdessen diese Zeile
        networks:
          - bw-universe

      syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE  # An niedrige Ports binden
          - NET_BROADCAST  # Broadcasts senden
          - NET_RAW  # Raw-Sockets verwenden
          - DAC_READ_SEARCH  # Dateien lesen, Berechtigungen umgehen
          - DAC_OVERRIDE  # Dateiberechtigungen überschreiben
          - CHOWN  # Besitzer ändern
          - SYSLOG  # In Systemprotokolle schreiben
        volumes:
          - bw-logs:/var/log/bunkerweb # Dies ist das Volume, das zum Speichern der Protokolle verwendet wird
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # Dies ist die Konfigurationsdatei von syslog-ng
        networks:
            bw-universe:
              ipv4_address: 10.20.30.254

    volumes:
      bw-data:
      bw-storage:
      bw-logs:
      cs-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Stellen Sie sicher, dass Sie den richtigen IP-Bereich festlegen, damit der Scheduler die Konfiguration an die Instanz senden kann
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Linux"
    Sie müssen CrowdSec installieren und so konfigurieren, dass es die BunkerWeb-Protokolle analysiert. Befolgen Sie die [offizielle Dokumentation](https://doc.crowdsec.net/docs/getting_started/install_crowdsec?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios).

    Damit CrowdSec die BunkerWeb-Protokolle analysieren kann, fügen Sie die folgenden Zeilen zu Ihrer Akquisitionsdatei unter `/etc/crowdsec/acquis.yaml` hinzu:

    ```yaml
    filenames:
      - /var/log/bunkerweb/access.log
      - /var/log/bunkerweb/error.log
      - /var/log/bunkerweb/modsec_audit.log
    labels:
        type: bunkerweb
    ```

    Aktualisieren Sie den CrowdSec-Hub und installieren Sie die BunkerWeb-Sammlung:

    ```shell
    sudo cscli hub update
    sudo cscli collections install bunkerity/bunkerweb
    ```

    Fügen Sie nun Ihren benutzerdefinierten Bouncer zur CrowdSec-API hinzu, indem Sie das Tool `cscli` verwenden:

    ```shell
    sudo cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6
    ```

    !!! warning "API-Schlüssel"
        Bewahren Sie den von dem `cscli`-Befehl generierten Schlüssel auf; Sie werden ihn später benötigen.

    Starten Sie anschließend den CrowdSec-Dienst neu:

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Anwendungssicherheitskomponente (*optional*)**

    Wenn Sie die AppSec-Komponente verwenden möchten, müssen Sie eine weitere Akquisitionsdatei dafür erstellen, die sich unter `/etc/crowdsec/acquis.d/appsec.yaml` befindet:

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
        type: appsec
    listen_addr: 127.0.0.1:7422
    source: appsec
    ```

    Sie müssen auch die Sammlungen der AppSec-Komponente installieren:

    ```shell
    sudo cscli collections install crowdsecurity/appsec-virtual-patching
    sudo cscli collections install crowdsecurity/appsec-generic-rules
    ```

    Starten Sie schließlich den CrowdSec-Dienst neu:

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Parameter**

    Konfigurieren Sie das Plugin, indem Sie die folgenden Parameter zu Ihrer BunkerWeb-Konfigurationsdatei hinzufügen:

    ```env
    USE_CROWDSEC=yes
    CROWDSEC_API=http://127.0.0.1:8080
    CROWDSEC_API_KEY=<Der von cscli bereitgestellte Schlüssel>
    # Auskommentieren, wenn Sie die AppSec-Komponente nicht verwenden möchten
    CROWDSEC_APPSEC_URL=http://127.0.0.1:7422
    ```

    Laden Sie schließlich den BunkerWeb-Dienst neu:

    ```shell
    sudo systemctl reload bunkerweb
    ```

=== "All-in-one"
    Das Docker-Image BunkerWeb All-In-One (AIO) wird mit vollständig integriertem CrowdSec geliefert. Sie müssen keine separate CrowdSec-Instanz einrichten oder die Akquisitionsdateien für die BunkerWeb-Protokolle manuell konfigurieren, wenn Sie den internen CrowdSec-Agenten verwenden.

    Beachten Sie die [Integrationsdokumentation des All-In-One (AIO)-Images](integrations.md#crowdsec-integration).

### Schritt&nbsp;2 – BunkerWeb-Einstellungen konfigurieren

Wenden Sie die folgenden Umgebungsvariablen (oder Scheduler-Werte) an, damit die BunkerWeb-Instanz mit der CrowdSec Local API kommunizieren kann. Mindestens `USE_CROWDSEC`, `CROWDSEC_API` und ein gültiger mit `cscli bouncers add` erzeugter Schlüssel werden benötigt.

| Parameter                   | Standardwert           | Kontext   | Mehrfach | Beschreibung                                                                                                                             |
| --------------------------- | ---------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | no       | **CrowdSec aktivieren:** Auf `yes` setzen, um den CrowdSec-Bouncer zu aktivieren.                                                        |
| `CROWDSEC_API`              | `http://crowdsec:8080` | global    | no       | **CrowdSec API URL:** Die Adresse des lokalen CrowdSec API-Dienstes.                                                                     |
| `CROWDSEC_API_KEY`          |                        | global    | no       | **CrowdSec API-Schlüssel:** Der API-Schlüssel zur Authentifizierung bei der CrowdSec-API, erhalten mit `cscli bouncers add`.             |
| `CROWDSEC_MODE`             | `live`                 | global    | no       | **Betriebsmodus:** Entweder `live` (fragt die API für jede Anfrage ab) oder `stream` (cacht alle Entscheidungen periodisch).             |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | global    | no       | **Interner Traffic:** Auf `yes` setzen, um den internen Traffic anhand der CrowdSec-Entscheidungen zu überprüfen.                        |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | global    | no       | **Anfrage-Timeout:** Timeout in Millisekunden für HTTP-Anfragen an die lokale CrowdSec-API im Live-Modus.                                |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | global    | no       | **Ausgeschlossene Orte:** Kommagetrennte Liste von Orten (URIs), die von CrowdSec-Prüfungen ausgeschlossen werden sollen.                |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | global    | no       | **Cache-Ablauf:** Die Cache-Ablaufzeit in Sekunden für IP-Entscheidungen im Live-Modus.                                                  |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | global    | no       | **Update-Frequenz:** Wie oft (in Sekunden) neue/abgelaufene Entscheidungen von der CrowdSec-API im Stream-Modus abgerufen werden sollen. |

#### Parameter der Anwendungssicherheitskomponente

| Parameter                         | Standardwert  | Kontext | Mehrfach | Beschreibung                                                                                                                         |
| --------------------------------- | ------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `CROWDSEC_APPSEC_URL`             |               | global  | no       | **AppSec URL:** Die URL der CrowdSec-Anwendungssicherheitskomponente. Leer lassen, um AppSec zu deaktivieren.                        |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough` | global  | no       | **Aktion bei Fehler:** Aktion, die ausgeführt werden soll, wenn AppSec einen Fehler zurückgibt. Kann `passthrough` oder `deny` sein. |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`         | global  | no       | **Verbindungs-Timeout:** Das Timeout in Millisekunden für die Verbindung zur AppSec-Komponente.                                      |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`         | global  | no       | **Sende-Timeout:** Das Timeout in Millisekunden für das Senden von Daten an die AppSec-Komponente.                                   |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`         | global  | no       | **Verarbeitungs-Timeout:** Das Timeout in Millisekunden für die Verarbeitung der Anfrage in der AppSec-Komponente.                   |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`          | global  | no       | **Immer senden:** Auf `yes` setzen, um Anfragen immer an AppSec zu senden, auch wenn eine Entscheidung auf IP-Ebene vorliegt.        |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`          | global  | no       | **SSL-Verifizierung:** Auf `yes` setzen, um das SSL-Zertifikat der AppSec-Komponente zu überprüfen.                                  |

!!! info "Über die Betriebsmodi" - Der **Live-Modus** fragt die CrowdSec-API für jede eingehende Anfrage ab und bietet Echtzeitschutz auf Kosten einer höheren Latenz. - Der **Stream-Modus** lädt periodisch alle Entscheidungen von der CrowdSec-API herunter und speichert sie lokal im Cache, wodurch die Latenz mit einer leichten Verzögerung bei der Anwendung neuer Entscheidungen reduziert wird.

### Konfigurationsbeispiele

=== "Basiskonfiguration"

    Dies ist eine einfache Konfiguration, wenn CrowdSec auf demselben Host ausgeführt wird:

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "live"
    ```

=== "Erweiterte Konfiguration mit AppSec"

    Eine umfassendere Konfiguration, einschließlich der Anwendungssicherheitskomponente:

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "stream"
    CROWDSEC_UPDATE_FREQUENCY: "30"
    CROWDSEC_EXCLUDE_LOCATION: "/health,/metrics"

    # AppSec-Konfiguration
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_APPSEC_FAILURE_ACTION: "deny"
    CROWDSEC_ALWAYS_SEND_TO_APPSEC: "yes"
    CROWDSEC_APPSEC_SSL_VERIFY: "yes"
    ```

### Schritt&nbsp;3 – Integration validieren

- Suchen Sie in den Scheduler-Protokollen nach den Einträgen `CrowdSec configuration successfully generated` und `CrowdSec bouncer denied request`, um zu überprüfen, dass das Plugin aktiv ist.
- Überwachen Sie auf CrowdSec-Seite `cscli metrics show` oder die CrowdSec-Konsole, um sicherzugehen, dass BunkerWeb-Entscheidungen wie erwartet erscheinen.
- Öffnen Sie in der BunkerWeb-Oberfläche die CrowdSec-Plugin-Seite, um den Status der Integration zu sehen.
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_APPSEC_FAILURE_ACTION: "deny"
    CROWDSEC_ALWAYS_SEND_TO_APPSEC: "yes"
    CROWDSEC_APPSEC_SSL_VERIFY: "yes"
    ```

## Custom Pages <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM-Unterstützung :x:

Tweak BunkerWeb error/antibot/default pages with custom HTML.

| Einstellung                      | Standardwert | Kontext   | Mehrfach | Beschreibung                                                                                                       |
| -------------------------------- | ------------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------ |
| `CUSTOM_ERROR_PAGE`              |              | multisite | nein     | Full path of the custom error page (must be readable by the scheduler) (Can be a lua template).                    |
| `CUSTOM_DEFAULT_SERVER_PAGE`     |              | global    | nein     | Full path of the custom default server page (must be readable by the scheduler) (Can be a lua template).           |
| `CUSTOM_ANTIBOT_CAPTCHA_PAGE`    |              | multisite | nein     | Full path of the custom antibot captcha page (must be readable by the scheduler) (Can be a lua template).          |
| `CUSTOM_ANTIBOT_JAVASCRIPT_PAGE` |              | multisite | nein     | Full path of the custom antibot javascript check page (must be readable by the scheduler) (Can be a lua template). |
| `CUSTOM_ANTIBOT_RECAPTCHA_PAGE`  |              | multisite | nein     | Full path of the custom antibot recaptcha page (must be readable by the scheduler) (Can be a lua template).        |
| `CUSTOM_ANTIBOT_HCAPTCHA_PAGE`   |              | multisite | nein     | Full path of the custom antibot hcaptcha page (must be readable by the scheduler) (Can be a lua template).         |
| `CUSTOM_ANTIBOT_TURNSTILE_PAGE`  |              | multisite | nein     | Full path of the custom antibot turnstile page (must be readable by the scheduler) (Can be a lua template).        |
| `CUSTOM_ANTIBOT_MCAPTCHA_PAGE`   |              | multisite | nein     | Full path of the custom antibot mcaptcha page (must be readable by the scheduler) (Can be a lua template).         |

## Custom SSL certificate

STREAM-Unterstützung :white_check_mark:

Das Plugin für benutzerdefinierte SSL-Zertifikate ermöglicht die Verwendung Ihrer eigenen SSL/TLS-Zertifikate mit BunkerWeb, anstelle der automatisch generierten. Dies ist nützlich, wenn Sie bereits Zertifikate von einer vertrauenswürdigen CA besitzen, spezifische Anforderungen haben oder die Zertifikatsverwaltung zentralisieren.

So funktioniert's:

1.  Sie stellen das Zertifikat und den privaten Schlüssel bereit (Dateipfade oder Daten in base64/PEM).
2.  BunkerWeb validiert das Format und die Verwendbarkeit der Dateien.
3.  Bei einer sicheren Verbindung stellt BunkerWeb Ihr benutzerdefiniertes Zertifikat bereit.
4.  Die Gültigkeit wird überwacht und Warnungen werden vor dem Ablauf ausgegeben.
5.  Sie behalten die volle Kontrolle über den Lebenszyklus der Zertifikate.

!!! info "Automatische Überwachung"
    Mit `USE_CUSTOM_SSL: yes` überwacht BunkerWeb das Zertifikat `CUSTOM_SSL_CERT`, erkennt Änderungen und lädt NGINX bei Bedarf neu.

### Verwendung

1.  Aktivieren: `USE_CUSTOM_SSL: yes`.
2.  Methode: Dateien vs. Daten, Priorität über `CUSTOM_SSL_CERT_PRIORITY`.
3.  Dateien: Geben Sie die Pfade zum Zertifikat und zum privaten Schlüssel an.
4.  Daten: Geben Sie die base64- oder Klartext-PEM-Strings an.

!!! tip "Stream-Modus"
    Im Stream-Modus konfigurieren Sie `LISTEN_STREAM_PORT_SSL` für den SSL/TLS-Port.

### Parameter

| Parameter                  | Standard | Kontext   | Mehrfach | Beschreibung                                                    |
| :------------------------- | :------- | :-------- | :------- | :-------------------------------------------------------------- |
| `USE_CUSTOM_SSL`           | `no`     | multisite | nein     | Aktiviert die Verwendung eines benutzerdefinierten Zertifikats. |
| `CUSTOM_SSL_CERT_PRIORITY` | `file`   | multisite | nein     | Priorität der Quellen: `file` (Dateien) oder `data` (Daten).    |
| `CUSTOM_SSL_CERT`          |          | multisite | nein     | Vollständiger Pfad zum Zertifikat (oder Bundle).                |
| `CUSTOM_SSL_KEY`           |          | multisite | nein     | Vollständiger Pfad zum privaten Schlüssel.                      |
| `CUSTOM_SSL_CERT_DATA`     |          | multisite | nein     | Zertifikatsdaten (base64 oder Klartext-PEM).                    |
| `CUSTOM_SSL_KEY_DATA`      |          | multisite | nein     | Daten des privaten Schlüssels (base64 oder Klartext-PEM).       |

!!! warning "Sicherheit"
    Schützen Sie den privaten Schlüssel (angemessene Berechtigungen, nur vom BunkerWeb-Scheduler lesbar).

!!! tip "Format"
    Zertifikate müssen im PEM-Format vorliegen. Konvertieren Sie bei Bedarf.

!!! info "Zertifikatsketten"
    Wenn eine Zwischenkette erforderlich ist, stellen Sie das vollständige Bundle in der richtigen Reihenfolge bereit (Zertifikat, dann Zwischenzertifikate).

### Beispiele

=== "Dateien"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    ```

=== "Base64-Daten"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR..."
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV..."
    ```

=== "Klartext-PEM"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: |
    -----BEGIN CERTIFICATE-----
    MIIDdzCCAl+gAwIBAgIUJH...certificate content...AAAA
    -----END CERTIFICATE-----
    CUSTOM_SSL_KEY_DATA: |
    -----BEGIN PRIVATE KEY-----
    MIIEvQIBADAN...key content...AAAA
    -----END PRIVATE KEY-----
    ```

=== "Fallback"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR..."
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV..."
    ```

## DNSBL

STREAM-Unterstützung :white_check_mark:

Das DNSBL (Domain Name System Blacklist) Plugin bietet Schutz vor bekannten bösartigen IP-Adressen, indem es die IP-Adressen von Clients mit externen DNSBL-Servern abgleicht. Diese Funktion schützt Ihre Website vor Spam, Botnetzen und verschiedenen Arten von Cyber-Bedrohungen, indem sie auf von der Community gepflegte Listen problematischer IP-Adressen zurückgreift.

**So funktioniert es:**

1.  Wenn ein Client eine Verbindung zu Ihrer Website herstellt, fragt BunkerWeb die von Ihnen ausgewählten DNSBL-Server über das DNS-Protokoll ab.
2.  Die Überprüfung erfolgt durch Senden einer umgekehrten DNS-Anfrage mit der IP-Adresse des Clients an jeden DNSBL-Server.
3.  Wenn ein DNSBL-Server bestätigt, dass die IP-Adresse des Clients als bösartig aufgeführt ist, wird BunkerWeb den Client automatisch sperren und so verhindern, dass potenzielle Bedrohungen Ihre Anwendung erreichen.
4.  Die Ergebnisse werden zwischengespeichert, um die Leistung bei wiederholten Besuchen von derselben IP-Adresse zu verbessern.
5.  Die Abfragen werden effizient mit asynchronen Abfragen durchgeführt, um die Auswirkungen auf die Ladezeiten der Seite zu minimieren.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die DNSBL-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die DNSBL-Funktion ist standardmäßig deaktiviert. Setzen Sie die Einstellung `USE_DNSBL` auf `yes`, um sie zu aktivieren.
2.  **DNSBL-Server konfigurieren:** Fügen Sie die Domainnamen der DNSBL-Dienste, die Sie verwenden möchten, zur Einstellung `DNSBL_LIST` hinzu.
3.  **Einstellungen anwenden:** Nach der Konfiguration überprüft BunkerWeb eingehende Verbindungen automatisch mit den angegebenen DNSBL-Servern.
4.  **Wirksamkeit überwachen:** Überprüfen Sie die [Web-Benutzeroberfläche](web-ui.md), um Statistiken über Anfragen zu sehen, die durch DNSBL-Prüfungen blockiert wurden.

### Konfigurationseinstellungen

**Allgemein**

| Einstellung  | Standard                                            | Kontext   | Mehrfach | Beschreibung                                                                                      |
| ------------ | --------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------- |
| `USE_DNSBL`  | `no`                                                | multisite | nein     | DNSBL aktivieren: auf `yes` setzen, um DNSBL-Prüfungen für eingehende Verbindungen zu aktivieren. |
| `DNSBL_LIST` | `bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org` | global    | nein     | DNSBL-Server: Liste der zu überprüfenden DNSBL-Server-Domains, durch Leerzeichen getrennt.        |

**Ausnahmelisten**

| Einstellung            | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                            |
| ---------------------- | -------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------- |
| `DNSBL_IGNORE_IP`      | ``       | multisite | ja       | Durch Leerzeichen getrennte IPs/CIDRs, für die DNSBL-Prüfungen übersprungen werden sollen (Whitelist).                  |
| `DNSBL_IGNORE_IP_URLS` | ``       | multisite | ja       | Durch Leerzeichen getrennte URLs, die IPs/CIDRs zum Überspringen bereitstellen. Unterstützt `http(s)://` und `file://`. |

!!! tip "Auswahl von DNSBL-Servern"
    Wählen Sie seriöse DNSBL-Anbieter, um Falschmeldungen zu minimieren. Die Standardliste enthält etablierte Dienste, die für die meisten Websites geeignet sind:

    - **bl.blocklist.de:** Listet IPs, die bei Angriffen auf andere Server erkannt wurden.
    - **sbl.spamhaus.org:** Konzentriert sich auf Spam-Quellen und andere bösartige Aktivitäten.
    - **xbl.spamhaus.org:** Zielt auf infizierte Systeme ab, wie z. B. kompromittierte Maschinen oder offene Proxys.

!!! info "Wie DNSBL funktioniert"
    DNSBL-Server funktionieren, indem sie auf speziell formatierte DNS-Anfragen antworten. Wenn BunkerWeb eine IP-Adresse überprüft, kehrt es die IP um und hängt den DNSBL-Domainnamen an. Wenn die resultierende DNS-Anfrage eine „Erfolgs“-Antwort zurückgibt, wird die IP als auf der schwarzen Liste stehend betrachtet.

!!! warning "Leistungsüberlegungen"
    Obwohl BunkerWeb DNSBL-Abfragen auf Leistung optimiert, könnte das Hinzufügen einer großen Anzahl von DNSBL-Servern potenziell die Antwortzeiten beeinträchtigen. Beginnen Sie mit einigen seriösen DNSBL-Servern und überwachen Sie die Leistung, bevor Sie weitere hinzufügen.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine einfache Konfiguration mit den Standard-DNSBL-Servern:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org"
    ```

=== "Minimale Konfiguration"

    Eine minimale Konfiguration, die sich auf die zuverlässigsten DNSBL-Dienste konzentriert:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    ```

    Diese Konfiguration verwendet nur:

    - **zen.spamhaus.org**: Die kombinierte Liste von Spamhaus wird aufgrund ihrer breiten Abdeckung und ihres Rufs für Genauigkeit oft als eigenständige Lösung als ausreichend angesehen. Sie kombiniert die SBL-, XBL- und PBL-Listen in einer einzigen Abfrage, was sie effizient und umfassend macht.

=== "Ausschluss vertrauenswürdiger IPs"

    Sie können bestimmte Clients von DNSBL-Prüfungen ausschließen, indem Sie statische Werte und/oder entfernte Dateien verwenden:

    - `DNSBL_IGNORE_IP`: Fügen Sie durch Leerzeichen getrennte IPs und CIDR-Bereiche hinzu. Beispiel: `192.0.2.10 203.0.113.0/24 2001:db8::/32`.
    - `DNSBL_IGNORE_IP_URLS`: Geben Sie URLs an, deren Inhalte eine IP/CIDR pro Zeile auflisten. Kommentare, die mit `#` oder `;` beginnen, werden ignoriert. Doppelte Einträge werden entfernt.

    Wenn eine eingehende Client-IP mit der Ausnahmeliste übereinstimmt, überspringt BunkerWeb die DNSBL-Abfragen und speichert das Ergebnis als „ok“ für schnellere nachfolgende Anfragen zwischen.

=== "Verwendung von Remote-URLs"

    Der Job `dnsbl-download` lädt und speichert stündlich zu ignorierende IPs:

    - Protokolle: `https://`, `http://` und lokale `file://`-Pfade.
    - Pro-URL-Cache mit Prüfsumme verhindert redundante Downloads (1 Stunde Toleranz).
    - Pro Dienst zusammengeführte Datei: `/var/cache/bunkerweb/dnsbl/<service>/IGNORE_IP.list`.
    - Wird beim Start geladen und mit `DNSBL_IGNORE_IP` zusammengeführt.

    Beispiel, das statische und URL-Quellen kombiniert:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP: "10.0.0.0/8 192.168.0.0/16 2001:db8::/32"
    DNSBL_IGNORE_IP_URLS: "https://example.com/allow-cidrs.txt file:///etc/bunkerweb/dnsbl/ignore.txt"
    ```

=== "Verwendung lokaler Dateien"

    Laden Sie zu ignorierende IPs aus lokalen Dateien unter Verwendung von `file://`-URLs:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP_URLS: "file:///etc/bunkerweb/dnsbl/ignore.txt file:///opt/data/allow-cidrs.txt"
    ```

## Database

STREAM-Unterstützung :white_check_mark:

Das Datenbank-Plugin bietet eine robuste Datenbankintegration für BunkerWeb, indem es die zentrale Speicherung und Verwaltung von Konfigurationsdaten, Protokollen und anderen wichtigen Informationen ermöglicht.

Diese Kernkomponente unterstützt mehrere Datenbank-Engines, darunter SQLite, PostgreSQL, MySQL/MariaDB und Oracle, sodass Sie die Datenbanklösung wählen können, die am besten zu Ihrer Umgebung und Ihren Anforderungen passt.

**So funktioniert es:**

1.  BunkerWeb verbindet sich mit Ihrer konfigurierten Datenbank über die bereitgestellte URI im SQLAlchemy-Format.
2.  Kritische Konfigurationsdaten, Laufzeitinformationen und Job-Protokolle werden sicher in der Datenbank gespeichert.
3.  Automatische Wartungsprozesse optimieren Ihre Datenbank, indem sie das Datenwachstum verwalten und überschüssige Datensätze bereinigen.
4.  Für Hochverfügbarkeitsszenarien können Sie eine schreibgeschützte Datenbank-URI konfigurieren, die sowohl als Failover als auch zur Entlastung von Leseoperationen dient.
5.  Datenbankoperationen werden entsprechend Ihrer angegebenen Protokollierungsstufe protokolliert, um eine angemessene Transparenz der Datenbankinteraktionen zu gewährleisten.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Datenbankfunktion zu konfigurieren und zu verwenden:

1.  **Wählen Sie eine Datenbank-Engine:** Wählen Sie je nach Ihren Anforderungen zwischen SQLite (Standard), PostgreSQL, MySQL/MariaDB oder Oracle.
2.  **Konfigurieren Sie die Datenbank-URI:** Setzen Sie `DATABASE_URI`, um sich mit Ihrer primären Datenbank im SQLAlchemy-Format zu verbinden.
3.  **Optionale schreibgeschützte Datenbank:** Konfigurieren Sie für Hochverfügbarkeits-Setups eine `DATABASE_URI_READONLY` als Fallback oder für Leseoperationen.

### Konfigurationseinstellungen

| Einstellung                     | Standard                                  | Kontext | Mehrfach | Beschreibung                                                                                                                                |
| ------------------------------- | ----------------------------------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URI`                  | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global  | nein     | **Datenbank-URI:** Die primäre Datenbankverbindungszeichenfolge im SQLAlchemy-Format.                                                       |
| `DATABASE_URI_READONLY`         |                                           | global  | nein     | **Schreibgeschützte Datenbank-URI:** Optionale Datenbank für schreibgeschützte Operationen oder als Failover.                               |
| `DATABASE_LOG_LEVEL`            | `warning`                                 | global  | nein     | **Protokollierungsstufe:** Die Ausführlichkeitsstufe für Datenbankprotokolle. Optionen: `debug`, `info`, `warn`, `warning` oder `error`.    |
| `DATABASE_MAX_JOBS_RUNS`        | `10000`                                   | global  | nein     | **Maximale Job-Ausführungen:** Die maximale Anzahl von Job-Ausführungsdatensätzen, die vor der automatischen Bereinigung aufbewahrt werden. |
| `DATABASE_MAX_SESSION_AGE_DAYS` | `14`                                      | global  | nein     | **Sitzungsaufbewahrung:** Das maximale Alter (in Tagen) von UI-Benutzersitzungen, bevor sie automatisch bereinigt werden.                   |

!!! tip "Auswahl der Datenbank" - **SQLite** (Standard): Ideal für Single-Node-Bereitstellungen oder Testumgebungen aufgrund seiner Einfachheit und dateibasierten Natur. - **PostgreSQL**: Empfohlen für Produktionsumgebungen mit mehreren BunkerWeb-Instanzen aufgrund seiner Robustheit und Unterstützung für Gleichzeitigkeit. - **MySQL/MariaDB**: Eine gute Alternative zu PostgreSQL mit ähnlichen produktionsreifen Fähigkeiten. - **Oracle**: Geeignet für Unternehmensumgebungen, in denen Oracle bereits die Standard-Datenbankplattform ist.

!!! info "SQLAlchemy-URI-Format"
    Die Datenbank-URI folgt dem SQLAlchemy-Format:

    - SQLite: `sqlite:////pfad/zur/datenbank.sqlite3`
    - PostgreSQL: `postgresql://benutzername:passwort@hostname:port/datenbank`
    - MySQL/MariaDB: `mysql://benutzername:passwort@hostname:port/datenbank` oder `mariadb://benutzername:passwort@hostname:port/datenbank`
    - Oracle: `oracle://benutzername:passwort@hostname:port/datenbank`

!!! warning "Datenbankwartung"
    Das Plugin führt automatisch tägliche Wartungsjobs aus:

- **Bereinigung überschüssiger Job-Ausführungen:** Entfernt Historien, die über dem Wert von `DATABASE_MAX_JOBS_RUNS` liegen.
- **Bereinigung abgelaufener UI-Sitzungen:** Löscht UI-Benutzersitzungen, die älter sind als `DATABASE_MAX_SESSION_AGE_DAYS`.

Diese Aufgaben verhindern ein unbegrenztes Datenbankwachstum und bewahren gleichzeitig eine nützliche Betriebshistorie.

## Easy Resolve <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM-Unterstützung :x:

Provides a simpler way to fix false positives in reports.

## Errors

STREAM-Unterstützung :x:

Das Errors-Plugin bietet eine anpassbare Verwaltung von HTTP-Fehlern, um das Erscheinungsbild der Fehlerantworten für Ihre Benutzer zu definieren. So können Sie klare and konsistente Fehlerseiten anzeigen, die Ihrer Identität entsprechen, anstatt der technischen Standardseiten des Servers.

**So funktioniert's:**

1.  Wenn ein HTTP-Fehler auftritt (z.B. 400, 404, 500), fängt BunkerWeb die Antwort ab.
2.  Anstelle der Standardseite zeigt BunkerWeb eine angepasste and sorgfältig gestaltete Seite an.
3.  Die Fehlerseiten sind konfigurierbar: Sie können für jeden Fehlercode eine HTML-Datei bereitstellen. Die Dateien müssen in dem durch `ROOT_FOLDER` definierten Verzeichnis abgelegt werden (siehe Misc-Plugin).
    - Standardmäßig ist `ROOT_FOLDER` auf `/var/www/html/{server_name}` gesetzt.
    - Im Multisite-Modus hat jede Site ihren eigenen `ROOT_FOLDER`; platzieren Sie die Fehlerseiten im entsprechenden Ordner für jede Site.
4.  Die Standardseiten erklären das Problem klar and schlagen mögliche Maßnahmen vor.

### Verwendung

1.  **Benutzerdefinierte Seiten definieren:** Verwenden Sie `ERRORS`, um HTTP-Codes mit HTML-Dateien (im `ROOT_FOLDER`) zu verknüpfen.
2.  **Ihre Seiten konfigurieren:** Verwenden Sie die Standardseiten von BunkerWeb oder Ihre eigenen Dateien.
3.  **Abgefangene Codes definieren:** Wählen Sie mit `INTERCEPTED_ERROR_CODES` die Codes aus, die immer von BunkerWeb verwaltet werden sollen.
4.  **Lassen Sie BunkerWeb den Rest erledigen:** Die Fehlerverwaltung wird automatisch angewendet.

### Parameter

| Parameter                 | Standard                                          | Kontext   | Mehrfach | Beschreibung                                                                                                                       |
| :------------------------ | :------------------------------------------------ | :-------- | :------- | :--------------------------------------------------------------------------------------------------------------------------------- |
| `ERRORS`                  |                                                   | Multisite | Nein     | Benutzerdefinierte Fehlerseiten: Paare `CODE=/pfad/seite.html`.                                                                    |
| `INTERCEPTED_ERROR_CODES` | `400 401 403 404 405 413 429 500 501 502 503 504` | Multisite | Nein     | Abgefangene Codes: Liste der Codes, die mit der Standardseite verwaltet werden, wenn keine benutzerdefinierte Seite definiert ist. |

!!! tip "Seiten-Design"
    Die Standardseiten sind klar and lehrreich: Fehlerbeschreibung, mögliche Ursachen, vorgeschlagene Maßnahmen and visuelle Anhaltspunkte.

!!! info "Fehlertypen"

- 4xx (Client-seitig): Ungültige Anfragen, nicht existierende Ressource, fehlende Authentifizierung…
- 5xx (Server-seitig): Unmöglichkeit, eine gültige Anfrage zu bearbeiten (interner Fehler, vorübergehende Nichtverfügbarkeit…).

### Beispiele

=== "Standardverwaltung"

    ```yaml
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Benutzerdefinierte Seiten"

    ```yaml
    ERRORS: "404=/custom/404.html 500=/custom/500.html"
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Selektive Verwaltung"

    ```yaml
    INTERCEPTED_ERROR_CODES: "404 500"
    ```

## Greylist

STREAM-Unterstützung :warning:

Das Greylist-Plugin bietet einen flexiblen Sicherheitsansatz, der Besuchern den Zugriff ermöglicht, während wesentliche Sicherheitsfunktionen weiterhin aktiv bleiben.

Im Gegensatz zu traditionellen [Blacklist](#blacklist)/[Whitelist](#whitelist)-Ansätzen, die den Zugriff vollständig blockieren oder erlauben, schafft die Greylist einen Mittelweg, indem sie bestimmten Besuchern den Zugriff gewährt, sie aber dennoch Sicherheitsprüfungen unterzieht.

**So funktioniert es:**

1.  Sie definieren Kriterien für Besucher, die auf die Greylist gesetzt werden sollen (_IP-Adressen, Netzwerke, rDNS, ASN, User-Agent oder URI-Muster_).
2.  Wenn ein Besucher einem dieser Kriterien entspricht, erhält er Zugriff auf Ihre Website, während die anderen Sicherheitsfunktionen aktiv bleiben.
3.  Wenn ein Besucher keinem Greylist-Kriterium entspricht, wird sein Zugriff verweigert.
4.  Greylist-Daten können in regelmäßigen Abständen automatisch aus externen Quellen aktualisiert werden.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Greylist-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die Greylist-Funktion ist standardmäßig deaktiviert. Setzen Sie die Einstellung `USE_GREYLIST` auf `yes`, um sie zu aktivieren.
2.  **Greylist-Regeln konfigurieren:** Definieren Sie, welche IPs, Netzwerke, rDNS-Muster, ASNs, User-Agents oder URIs auf die Greylist gesetzt werden sollen.
3.  **Externe Quellen hinzufügen:** Konfigurieren Sie optional URLs zum automatischen Herunterladen und Aktualisieren von Greylist-Daten.
4.  **Zugriff überwachen:** Überprüfen Sie die [Web-Benutzeroberfläche](web-ui.md), um zu sehen, welchen Besuchern der Zugriff gewährt oder verweigert wird.

!!! tip "Verhalten der Zugriffskontrolle"
    Wenn die Greylist-Funktion aktiviert ist, indem die Einstellung `USE_GREYLIST` auf `yes` gesetzt wird:

    1. **Greylist-Besucher:** Erhalten Zugriff, unterliegen aber weiterhin allen Sicherheitsprüfungen.
    2. **Nicht-Greylist-Besucher:** Wird der Zugriff vollständig verweigert.

!!! info "Stream-Modus"
    Im Stream-Modus werden nur IP-, rDNS- und ASN-Prüfungen durchgeführt.

### Konfigurationseinstellungen

**Allgemein**

| Einstellung    | Standard | Kontext   | Mehrfach | Beschreibung                                                             |
| -------------- | -------- | --------- | -------- | ------------------------------------------------------------------------ |
| `USE_GREYLIST` | `no`     | multisite | nein     | **Greylist aktivieren:** Auf `yes` setzen, um Greylisting zu aktivieren. |

=== "IP-Adresse"
    **Was dies bewirkt:** Setzt Besucher basierend auf ihrer IP-Adresse oder ihrem Netzwerk auf die Greylist. Diese Besucher erhalten Zugriff, unterliegen aber weiterhin den Sicherheitsprüfungen.

    | Einstellung        | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                            |
    | ------------------ | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_IP`      |          | multisite | nein     | **IP-Greylist:** Liste von IP-Adressen oder Netzwerken (in CIDR-Notation), die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen.      |
    | `GREYLIST_IP_URLS` |          | multisite | nein     | **IP-Greylist-URLs:** Liste von URLs, die IP-Adressen oder Netzwerke enthalten, die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen. |

=== "Reverse DNS"
    **Was dies bewirkt:** Setzt Besucher basierend auf ihrem Domainnamen (in umgekehrter Reihenfolge) auf die Greylist. Nützlich, um Besuchern von bestimmten Organisationen oder Netzwerken bedingten Zugriff zu gewähren.

    | Einstellung            | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                       |
    | ---------------------- | -------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_RDNS`        |          | multisite | nein     | **rDNS-Greylist:** Liste von Reverse-DNS-Suffixen, die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen.                         |
    | `GREYLIST_RDNS_GLOBAL` | `yes`    | multisite | nein     | **Nur globales rDNS:** Führt rDNS-Greylist-Prüfungen nur für globale IP-Adressen durch, wenn auf `yes` gesetzt.                                    |
    | `GREYLIST_RDNS_URLS`   |          | multisite | nein     | **rDNS-Greylist-URLs:** Liste von URLs, die Reverse-DNS-Suffixe enthalten, die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen. |

=== "ASN"
    **Was dies bewirkt:** Setzt Besucher von bestimmten Netzwerkanbietern mithilfe von Autonomen Systemnummern auf die Greylist. ASNs identifizieren, zu welchem Anbieter oder welcher Organisation eine IP gehört.

    | Einstellung         | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                       |
    | ------------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_ASN`      |          | multisite | nein     | **ASN-Greylist:** Liste von Autonomen Systemnummern, die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen.       |
    | `GREYLIST_ASN_URLS` |          | multisite | nein     | **ASN-Greylist-URLs:** Liste von URLs, die ASNs enthalten, die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen. |

=== "User-Agent"
    **Was dies bewirkt:** Setzt Besucher basierend auf dem Browser oder Tool, das sie angeben zu verwenden, auf die Greylist. Dies ermöglicht kontrollierten Zugriff für bestimmte Tools, während die Sicherheitsprüfungen aufrechterhalten werden.

    | Einstellung                | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                |
    | -------------------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_USER_AGENT`      |          | multisite | nein     | **User-Agent-Greylist:** Liste von User-Agent-Mustern (PCRE-Regex), die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen. |
    | `GREYLIST_USER_AGENT_URLS` |          | multisite | nein     | **User-Agent-Greylist-URLs:** Liste von URLs, die User-Agent-Muster enthalten, die auf die Greylist gesetzt werden sollen.                  |

=== "URI"
    **Was dies bewirkt:** Setzt Anfragen an bestimmte URLs auf Ihrer Website auf die Greylist. Dies ermöglicht bedingten Zugriff auf bestimmte Endpunkte, während die Sicherheitsprüfungen aufrechterhalten werden.

    | Einstellung         | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                             |
    | ------------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_URI`      |          | multisite | nein     | **URI-Greylist:** Liste von URI-Mustern (PCRE-Regex), die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen.            |
    | `GREYLIST_URI_URLS` |          | multisite | nein     | **URI-Greylist-URLs:** Liste von URLs, die URI-Muster enthalten, die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen. |

!!! info "Unterstützung von URL-Formaten"
    Alle `*_URLS`-Einstellungen unterstützen HTTP/HTTPS-URLs sowie lokale Dateipfade mit dem Präfix `file:///`. Die Basisauthentifizierung wird im Format `http://user:pass@url` unterstützt.

!!! tip "Regelmäßige Aktualisierungen"
    Greylists von URLs werden stündlich automatisch heruntergeladen und aktualisiert, um sicherzustellen, dass Ihr Schutz mit den neuesten vertrauenswürdigen Quellen auf dem neuesten Stand bleibt.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine einfache Konfiguration, die Greylisting auf das interne Netzwerk eines Unternehmens und einen Crawler anwendet:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP: "192.168.1.0/24 10.0.0.0/8"
    GREYLIST_USER_AGENT: "(?:\b)CompanyCrawler(?:\b)"
    ```

=== "Erweiterte Konfiguration"

    Eine umfassendere Konfiguration mit mehreren Greylist-Kriterien:

    ```yaml
    USE_GREYLIST: "yes"

    # Unternehmensressourcen und genehmigte Crawler
    GREYLIST_IP: "192.168.1.0/24 203.0.113.0/24"
    GREYLIST_RDNS: ".company.com .partner-company.org"
    GREYLIST_ASN: "12345 67890"  # ASNs von Unternehmen und Partnern
    GREYLIST_USER_AGENT: "(?:\b)GoodBot(?:\b) (?:\b)PartnerCrawler(?:\b)"
    GREYLIST_URI: "^/api/v1/"

    # Externe vertrauenswürdige Quellen
    GREYLIST_IP_URLS: "https://example.com/trusted-networks.txt"
    GREYLIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Verwendung lokaler Dateien"

    Konfiguration mit lokalen Dateien für Greylists:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP_URLS: "file:///path/to/ip-greylist.txt"
    GREYLIST_RDNS_URLS: "file:///path/to/rdns-greylist.txt"
    GREYLIST_ASN_URLS: "file:///path/to/asn-greylist.txt"
    GREYLIST_USER_AGENT_URLS: "file:///path/to/user-agent-greylist.txt"
    GREYLIST_URI_URLS: "file:///path/to/uri-greylist.txt"
    ```

=== "Selektiver API-Zugriff"

    Eine Konfiguration, die den Zugriff auf bestimmte API-Endpunkte erlaubt:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_URI: "^/api/v1/public/ ^/api/v1/status"
    GREYLIST_IP: "203.0.113.0/24"  # Externes Partnernetzwerk
    ```

### Arbeiten mit lokalen Listendateien

Die `*_URLS`-Einstellungen der Whitelist-, Greylist- und Blacklist-Plugins verwenden denselben Downloader. Wenn Sie eine `file:///`-URL angeben:

- Der Pfad wird innerhalb des **Scheduler**-Containers aufgelöst (bei Docker-Bereitstellungen in der Regel `bunkerweb-scheduler`). Binden Sie die Dateien dort ein und stellen Sie sicher, dass der Scheduler-Benutzer Lesezugriff hat.
- Jede Datei ist eine UTF-8-codierte Textdatei mit einem Eintrag pro Zeile. Leere Zeilen werden ignoriert und Kommentarzeilen müssen mit `#` oder `;` beginnen. `//`-Kommentare werden nicht unterstützt.
- Erwartete Werte je Listentyp:
  - **IP-Listen** akzeptieren IPv4/IPv6-Adressen oder CIDR-Netzwerke (z. B. `192.0.2.10` oder `2001:db8::/48`).
  - **rDNS-Listen** erwarten ein Suffix ohne Leerzeichen (z. B. `.search.msn.com`). Werte werden automatisch in Kleinbuchstaben umgewandelt.
  - **ASN-Listen** können nur die Nummer (`32934`) oder die mit `AS` vorangestellte Nummer (`AS15169`) enthalten.
  - **User-Agent-Listen** werden als PCRE-Muster behandelt und die vollständige Zeile bleibt erhalten (einschließlich Leerzeichen). Schreiben Sie Kommentare in eine eigene Zeile, damit sie nicht als Muster interpretiert werden.
  - **URI-Listen** müssen mit `/` beginnen und dürfen PCRE-Tokens wie `^` oder `$` verwenden.

Beispieldateien im erwarteten Format:

```text
# /etc/bunkerweb/lists/ip-greylist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-greylist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```

## Gzip

STREAM-Unterstützung :x:

Der GZIP-Plugin komprimiert HTTP-Antworten mit dem GZIP-Algorithmus, um die Bandbreite zu reduzieren und das Laden von Seiten zu beschleunigen.

### Funktionsweise

1. BunkerWeb erkennt, ob der Client GZIP unterstützt.
2. Falls ja, wird die Antwort auf dem konfigurierten Niveau komprimiert.
3. Die Header zeigen die Verwendung von GZIP an.
4. Der Browser dekomprimiert vor der Anzeige.

### Verwendung

1. Aktivieren: `USE_GZIP: yes` (standardmäßig deaktiviert).
2. MIME-Typen: `GZIP_TYPES` definieren.
3. Mindestgröße: `GZIP_MIN_LENGTH`, um sehr kleine Dateien zu vermeiden.
4. Kompressionsstufe: `GZIP_COMP_LEVEL` (1–9).
5. Proxied-Inhalt: `GZIP_PROXIED` anpassen.

### Parameter

| Parameter         | Standard                                                                                                                                                                                                                                                                                                                                                                                                                         | Kontext   | Mehrfach | Beschreibung                                                                                 |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------- |
| `USE_GZIP`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | Multisite | nein     | Aktiviert die GZIP-Kompression.                                                              |
| `GZIP_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | Multisite | nein     | Komprimierte MIME-Typen.                                                                     |
| `GZIP_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | Multisite | nein     | Mindestgröße (Bytes) für die Anwendung der Kompression.                                      |
| `GZIP_COMP_LEVEL` | `5`                                                                                                                                                                                                                                                                                                                                                                                                                              | Multisite | nein     | Stufe 1–9: höher = bessere Kompression, aber mehr CPU.                                       |
| `GZIP_PROXIED`    | `no-cache no-store private expired auth`                                                                                                                                                                                                                                                                                                                                                                                         | Multisite | nein     | Gibt an, welche proxied-Inhalte basierend auf den Antwort-Headern komprimiert werden sollen. |

!!! tip "Kompressionsstufe"
    `5` ist ein guter Kompromiss. Statisch/CPU verfügbar: 7–9. Dynamisch/CPU begrenzt: 1–3.

### Beispiele

=== "Standard"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json application/xml text/css text/html text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "5"
    ```

=== "Maximale Kompression"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "500"
    GZIP_COMP_LEVEL: "9"
    GZIP_PROXIED: "any"
    ```

=== "Ausgewogene Leistung"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "3"
    GZIP_PROXIED: "no-cache no-store private expired"
    ```

=== "Proxied-Inhalt"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "4"
    GZIP_PROXIED: "any"
    ```

## HTML injection

STREAM-Unterstützung :x:

Das HTML-Injection-Plugin ermöglicht es Ihnen, nahtlos benutzerdefinierten HTML-Code zu den Seiten Ihrer Website vor den schließenden `</body>`- oder `</head>`-Tags hinzuzufügen. Diese Funktion ist besonders nützlich, um Analyses-Skripte, Tracking-Pixel, benutzerdefiniertes JavaScript, CSS-Stile oder andere Integrationen von Drittanbietern hinzuzufügen, ohne den Quellcode Ihrer Website ändern zu müssen.

**So funktioniert es:**

1.  Wenn eine Seite von Ihrer Website ausgeliefert wird, untersucht BunkerWeb die HTML-Antwort.
2.  Wenn Sie die Body-Injection konfiguriert haben, fügt BunkerWeb Ihren benutzerdefinierten HTML-Code direkt vor dem schließenden `</body>`-Tag ein.
3.  Wenn Sie die Head-Injection konfiguriert haben, fügt BunkerWeb Ihren benutzerdefinierten HTML-Code direkt vor dem schließenden `</head>`-Tag ein.
4.  Das Einfügen erfolgt automatisch für alle HTML-Seiten, die von Ihrer Website ausgeliefert werden.
5.  Dies ermöglicht es Ihnen, Skripte, Stile oder andere Elemente hinzuzufügen, ohne den Code Ihrer Anwendung ändern zu müssen.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die HTML-Injection-Funktion zu konfigurieren und zu verwenden:

1.  **Bereiten Sie Ihren benutzerdefinierten HTML-Code vor:** Entscheiden Sie, welchen HTML-Code Sie in Ihre Seiten einfügen möchten.
2.  **Wählen Sie die Einfügeorte:** Bestimmen Sie, ob Sie Code im `<head>`-Bereich, im `<body>`-Bereich oder in beiden einfügen müssen.
3.  **Konfigurieren Sie die Einstellungen:** Fügen Sie Ihren benutzerdefinierten HTML-Code zu den entsprechenden Einstellungen (`INJECT_HEAD` und/oder `INJECT_BODY`) hinzu.
4.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration wird der HTML-Code automatisch in alle ausgelieferten HTML-Seiten eingefügt.

### Konfigurationseinstellungen

| Einstellung   | Standard | Kontext   | Mehrfach | Beschreibung                                                                 |
| ------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------- |
| `INJECT_HEAD` |          | multisite | nein     | **Head-HTML-Code:** Der HTML-Code, der vor dem `</head>`-Tag eingefügt wird. |
| `INJECT_BODY` |          | multisite | nein     | **Body-HTML-Code:** Der HTML-Code, der vor dem `</body>`-Tag eingefügt wird. |

!!! tip "Bewährte Praktiken" - Aus Leistungsgründen sollten Sie JavaScript-Dateien am Ende des Body platzieren, um das Rendern nicht zu blockieren. - Platzieren Sie CSS und kritisches JavaScript im Head-Bereich, um ein Aufblitzen von ungestyltem Inhalt zu vermeiden. - Seien Sie vorsichtig mit eingefügtem Inhalt, der die Funktionalität Ihrer Website beeinträchtigen könnte.

!!! info "Häufige Anwendungsfälle" - Hinzufügen von Analyses-Skripten (wie Google Analytics, Matomo) - Integration von Chat-Widgets oder Kundensupport-Tools - Einbinden von Tracking-Pixeln für Marketingkampagnen - Hinzufügen von benutzerdefinierten CSS-Stilen oder JavaScript-Funktionen - Einbinden von Bibliotheken von Drittanbietern, ohne den Anwendungscode zu ändern

### Beispielkonfigurationen

=== "Google Analytics"

    Hinzufügen von Google-Analytics-Tracking zu Ihrer Website:

    ```yaml
    INJECT_HEAD: ""
    INJECT_BODY: "<script async src=\"https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX\"></script><script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag('js', new Date());gtag('config', 'G-XXXXXXXXXX');</script>"
    ```

=== "Benutzerdefinierte Stile"

    Hinzufügen von benutzerdefinierten CSS-Stilen zu Ihrer Website:

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .custom-element { color: blue; }</style>"
    INJECT_BODY: ""
    ```

=== "Mehrere Integrationen"

    Hinzufügen von sowohl benutzerdefinierten Stilen als auch JavaScript:

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .notification-banner { background: #f8f9fa; padding: 10px; text-align: center; }</style>"
    INJECT_BODY: "<script src=\"https://cdn.example.com/js/widget.js\"></script><script>initializeWidget('your-api-key');</script>"
    ```

=== "Cookie-Einwilligungsbanner"

    Hinzufügen eines einfachen Cookie-Einwilligungsbanners:

    ```yaml
    INJECT_HEAD: "<style>.cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #f1f1f1; padding: 20px; text-align: center; z-index: 1000; } .cookie-banner button { background: #4CAF50; border: none; color: white; padding: 10px 20px; cursor: pointer; }</style>"
    INJECT_BODY: "<div id=\"cookie-banner\" class=\"cookie-banner\">Diese Website verwendet Cookies, um sicherzustellen, dass Sie das beste Erlebnis erhalten. <button onclick=\"acceptCookies()\">Akzeptieren</button></div><script>function acceptCookies() { document.getElementById('cookie-banner').style.display = 'none'; localStorage.setItem('cookies-accepted', 'true'); } if(localStorage.getItem('cookies-accepted') === 'true') { document.getElementById('cookie-banner').style.display = 'none'; }</script>"
    ```

## Headers

STREAM-Unterstützung :x:

HTTP-Header spielen eine entscheidende Rolle bei der Sicherheit. Das Headers-Plugin bietet eine robuste Verwaltung von Standard- und benutzerdefinierten HTTP-Headern und verbessert so Sicherheit und Funktionalität. Es wendet dynamisch Sicherheitsmaßnahmen an, wie [HSTS](https://developer.mozilla.org/de/docs/Web/HTTP/Headers/Strict-Transport-Security), [CSP](https://developer.mozilla.org/de/docs/Web/HTTP/CSP) (einschließlich eines reinen Berichtsmodus) und die Injektion benutzerdefinierter Header, während es gleichzeitig Informationslecks verhindert.

**Wie es funktioniert**

1.  Wenn ein Client Inhalte von Ihrer Website anfordert, verarbeitet BunkerWeb die Antwort-Header.
2.  Sicherheits-Header werden gemäß Ihrer Konfiguration angewendet.
3.  Benutzerdefinierte Header können hinzugefügt werden, um Clients zusätzliche Informationen oder Funktionen bereitzustellen.
4.  Unerwünschte Header, die Serverinformationen preisgeben könnten, werden automatisch entfernt.
5.  Cookies werden so geändert, dass sie je nach Ihren Einstellungen die entsprechenden Sicherheitsflags enthalten.
6.  Header von Upstream-Servern können bei Bedarf selektiv beibehalten werden.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Headers-Funktion zu konfigurieren und zu verwenden:

1.  **Sicherheits-Header konfigurieren:** Legen Sie Werte für gängige Header fest.
2.  **Benutzerdefinierte Header hinzufügen:** Definieren Sie beliebige benutzerdefinierte Header mit der Einstellung `CUSTOM_HEADER`.
3.  **Unerwünschte Header entfernen:** Verwenden Sie `REMOVE_HEADERS`, um sicherzustellen, dass Header, die Serverdetails preisgeben könnten, entfernt werden.
4.  **Cookie-Sicherheit einstellen:** Aktivieren Sie eine robuste Cookie-Sicherheit, indem Sie `COOKIE_FLAGS` konfigurieren und `COOKIE_AUTO_SECURE_FLAG` auf `yes` setzen, damit das Secure-Flag bei HTTPS-Verbindungen automatisch hinzugefügt wird.
5.  **Upstream-Header beibehalten:** Geben Sie mit `KEEP_UPSTREAM_HEADERS` an, welche Upstream-Header beibehalten werden sollen.
6.  **Bedingte Header-Anwendung nutzen:** Wenn Sie Richtlinien ohne Unterbrechung testen möchten, aktivieren Sie den [CSP Report-Only-Modus](https://developer.mozilla.org/de/docs/Web/HTTP/Headers/Content-Security-Policy-Report-Only) über `CONTENT_SECURITY_POLICY_REPORT_ONLY`.

### Konfigurationsleitfaden

=== "Sicherheits-Header"

    **Überblick**

    Sicherheits-Header erzwingen eine sichere Kommunikation, schränken das Laden von Ressourcen ein und verhindern Angriffe wie Clickjacking und Injection. Richtig konfigurierte Header bilden eine robuste Verteidigungsschicht für Ihre Website.

    !!! success "Vorteile von Sicherheits-Headern"
        - **HSTS:** Stellt sicher, dass alle Verbindungen verschlüsselt sind, und schützt so vor Protokoll-Downgrade-Angriffen.
        - **CSP:** Verhindert die Ausführung bösartiger Skripte und verringert so das Risiko von XSS-Angriffen.
        - **X-Frame-Options:** Blockiert Clickjacking-Versuche durch die Kontrolle der Iframe-Einbettung.
        - **Referrer Policy:** Begrenzt das Durchsickern sensibler Informationen über Referrer-Header.

    | Einstellung                           | Standard                                                                                            | Kontext   | Mehrfach | Beschreibung                                                                                                                                                    |
    | ------------------------------------- | --------------------------------------------------------------------------------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `STRICT_TRANSPORT_SECURITY`           | `max-age=63072000; includeSubDomains; preload`                                                      | multisite | nein     | **HSTS:** Erzwingt sichere HTTPS-Verbindungen und verringert das Risiko von Man-in-the-Middle-Angriffen.                                                        |
    | `CONTENT_SECURITY_POLICY`             | `object-src 'none'; form-action 'self'; frame-ancestors 'self';`                                    | multisite | nein     | **CSP:** Beschränkt das Laden von Ressourcen auf vertrauenswürdige Quellen und mindert Cross-Site-Scripting- und Dateninjektionsangriffe.                       |
    | `CONTENT_SECURITY_POLICY_REPORT_ONLY` | `no`                                                                                                | multisite | nein     | **CSP-Berichtsmodus:** Meldet Verstöße, ohne Inhalte zu blockieren, und hilft beim Testen von Sicherheitsrichtlinien, während Protokolle erfasst werden.        |
    | `X_FRAME_OPTIONS`                     | `SAMEORIGIN`                                                                                        | multisite | nein     | **X-Frame-Options:** Verhindert Clickjacking, indem es steuert, ob Ihre Website in einem Frame dargestellt werden kann.                                         |
    | `X_CONTENT_TYPE_OPTIONS`              | `nosniff`                                                                                           | multisite | nein     | **X-Content-Type-Options:** Verhindert, dass Browser MIME-Sniffing betreiben, und schützt so vor Drive-by-Download-Angriffen.                                   |
    | `X_DNS_PREFETCH_CONTROL`              | `off`                                                                                               | multisite | nein     | **X-DNS-Prefetch-Control:** Reguliert das DNS-Prefetching, um unbeabsichtigte Netzwerkanfragen zu reduzieren und die Privatsphäre zu verbessern.                |
    | `REFERRER_POLICY`                     | `strict-origin-when-cross-origin`                                                                   | multisite | nein     | **Referrer Policy:** Steuert die Menge der gesendeten Referrer-Informationen und schützt die Privatsphäre der Benutzer.                                         |
    | `PERMISSIONS_POLICY`                  | `accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), ...` | multisite | nein     | **Permissions Policy:** Beschränkt den Zugriff auf Browserfunktionen und reduziert potenzielle Angriffsvektoren.                                                |
    | `KEEP_UPSTREAM_HEADERS`               | `Content-Security-Policy Permissions-Policy X-Frame-Options`                                        | multisite | nein     | **Header beibehalten:** Behält ausgewählte Upstream-Header bei, was die Integration von Altsystemen erleichtert und gleichzeitig die Sicherheit aufrechterhält. |

    !!! tip "Bewährte Praktiken"
        - Überprüfen und aktualisieren Sie Ihre Sicherheits-Header regelmäßig, um sie an die sich entwickelnden Sicherheitsstandards anzupassen.
        - Verwenden Sie Tools wie das [Mozilla Observatory](https://observatory.mozilla.org/), um Ihre Header-Konfiguration zu validieren.
        - Testen Sie CSP im `Report-Only`-Modus, bevor Sie es erzwingen, um zu vermeiden, dass die Funktionalität beeinträchtigt wird.

=== "Cookie-Einstellungen"

    **Überblick**

    Richtige Cookie-Einstellungen gewährleisten sichere Benutzersitzungen, indem sie Hijacking, Fixierung und Cross-Site-Scripting verhindern. Sichere Cookies erhalten die Sitzungsintegrität über HTTPS und verbessern den allgemeinen Schutz der Benutzerdaten.

    !!! success "Vorteile sicherer Cookies"
        - **HttpOnly-Flag:** Verhindert, dass clientseitige Skripte auf Cookies zugreifen, und mindert so XSS-Risiken.
        - **SameSite-Flag:** Reduziert CSRF-Angriffe, indem die Verwendung von Cookies über verschiedene Ursprünge hinweg eingeschränkt wird.
        - **Secure-Flag:** Stellt sicher, dass Cookies nur über verschlüsselte HTTPS-Verbindungen übertragen werden.

    | Einstellung               | Standard                  | Kontext   | Mehrfach | Beschreibung                                                                                                                                                              |
    | ------------------------- | ------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `COOKIE_FLAGS`            | `* HttpOnly SameSite=Lax` | multisite | ja       | **Cookie-Flags:** Fügt automatisch Sicherheitsflags wie HttpOnly und SameSite hinzu und schützt Cookies so vor dem Zugriff durch clientseitige Skripte und CSRF-Angriffe. |
    | `COOKIE_AUTO_SECURE_FLAG` | `yes`                     | multisite | nein     | **Automatisches Secure-Flag:** Stellt sicher, dass Cookies nur über sichere HTTPS-Verbindungen gesendet werden, indem das Secure-Flag automatisch angehängt wird.         |

    !!! tip "Bewährte Praktiken"
        - Verwenden Sie `SameSite=Strict` für sensible Cookies, um den Zugriff über verschiedene Ursprünge hinweg zu verhindern.
        - Überprüfen Sie Ihre Cookie-Einstellungen regelmäßig, um die Einhaltung der Sicherheits- und Datenschutzbestimmungen sicherzustellen.
        - Vermeiden Sie es, Cookies ohne das Secure-Flag in Produktionsumgebungen zu setzen.

=== "Benutzerdefinierte Header"

    **Überblick**

    Benutzerdefinierte Header ermöglichen es Ihnen, spezifische HTTP-Header hinzuzufügen, um Anwendungs- oder Leistungsanforderungen zu erfüllen. Sie bieten Flexibilität, müssen aber sorgfältig konfiguriert werden, um die Preisgabe sensibler Serverdetails zu vermeiden.

    !!! success "Vorteile von benutzerdefinierten Headern"
        - Verbessern Sie die Sicherheit, indem Sie unnötige Header entfernen, die Serverdetails preisgeben könnten.
        - Fügen Sie anwendungsspezifische Header hinzu, um die Funktionalität oder das Debugging zu verbessern.

    | Einstellung      | Standard                                                                             | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                                 |
    | ---------------- | ------------------------------------------------------------------------------------ | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `CUSTOM_HEADER`  |                                                                                      | multisite | ja       | **Benutzerdefinierter Header:** Bietet eine Möglichkeit, benutzerdefinierte Header im Format `HeaderName: HeaderValue` für spezielle Sicherheits- oder Leistungsverbesserungen hinzuzufügen. |
    | `REMOVE_HEADERS` | `Server Expect-CT X-Powered-By X-AspNet-Version X-AspNetMvc-Version Public-Key-Pins` | multisite | nein     | **Header entfernen:** Gibt an, welche Header entfernt werden sollen, um die Wahrscheinlichkeit der Preisgabe interner Serverdetails und bekannter Schwachstellen zu verringern.              |

    !!! warning "Sicherheitsaspekte"
        - Vermeiden Sie die Preisgabe sensibler Informationen durch benutzerdefinierte Header.
        - Überprüfen und aktualisieren Sie benutzerdefinierte Header regelmäßig, um sie an die Anforderungen Ihrer Anwendung anzupassen.

    !!! tip "Bewährte Praktiken"
        - Verwenden Sie `REMOVE_HEADERS`, um Header wie `Server` und `X-Powered-By` zu entfernen und so das Risiko des Fingerprintings zu verringern.
        - Testen Sie benutzerdefinierte Header in einer Staging-Umgebung, bevor Sie sie in der Produktion einsetzen.

### Beispielkonfigurationen

=== "Grundlegende Sicherheits-Header"

    Eine Standardkonfiguration mit wesentlichen Sicherheits-Headern:

    ```yaml
    STRICT_TRANSPORT_SECURITY: "max-age=63072000; includeSubDomains; preload"
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'self'"
    X_FRAME_OPTIONS: "SAMEORIGIN"
    X_CONTENT_TYPE_OPTIONS: "nosniff"
    REFERRER_POLICY: "strict-origin-when-cross-origin"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version"
    ```

=== "Verbesserte Cookie-Sicherheit"

    Konfiguration mit robusten Cookie-Sicherheitseinstellungen:

    ```yaml
    COOKIE_FLAGS: "* HttpOnly SameSite=Strict"
    COOKIE_FLAGS_2: "session_cookie Secure HttpOnly SameSite=Strict"
    COOKIE_FLAGS_3: "auth_cookie Secure HttpOnly SameSite=Strict Max-Age=3600"
    COOKIE_AUTO_SECURE_FLAG: "yes"
    ```

=== "Benutzerdefinierte Header für API"

    Konfiguration für einen API-Dienst mit benutzerdefinierten Headern:

    ```yaml
    CUSTOM_HEADER: "API-Version: 1.2.3"
    CUSTOM_HEADER_2: "Access-Control-Max-Age: 86400"
    CONTENT_SECURITY_POLICY: "default-src 'none'; frame-ancestors 'none'"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version X-Runtime"
    ```

=== "Content Security Policy - Berichtsmodus"

    Konfiguration zum Testen von CSP, ohne die Funktionalität zu beeinträchtigen:

    ```yaml
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self' https://trusted-cdn.example.com; img-src 'self' data: https://*.example.com; style-src 'self' 'unsafe-inline' https://trusted-cdn.example.com; connect-src 'self' https://api.example.com; object-src 'none'; frame-ancestors 'self'; form-action 'self'; base-uri 'self'; report-uri https://example.com/csp-reports"
    CONTENT_SECURITY_POLICY_REPORT_ONLY: "yes"
    ```

## Let's Encrypt

STREAM-Unterstützung :white_check_mark:

Das Let's Encrypt-Plugin vereinfacht die Verwaltung von SSL/TLS-Zertifikaten durch die Automatisierung der Erstellung, Erneuerung und Konfiguration von kostenlosen Zertifikaten von Let's Encrypt. Diese Funktion ermöglicht sichere HTTPS-Verbindungen für Ihre Websites ohne die Komplexität der manuellen Zertifikatsverwaltung, was sowohl Kosten als auch administrativen Aufwand reduziert.

**Wie es funktioniert:**

1.  Nach der Aktivierung erkennt BunkerWeb automatisch die für Ihre Website konfigurierten Domains.
2.  BunkerWeb beantragt kostenlose SSL/TLS-Zertifikate bei der Zertifizierungsstelle von Let's Encrypt.
3.  Der Domainbesitz wird entweder durch HTTP-Challenges (Nachweis, dass Sie die Website kontrollieren) oder DNS-Challenges (Nachweis, dass Sie die DNS Ihrer Domain kontrollieren) verifiziert.
4.  Zertifikate werden automatisch für Ihre Domains installiert und konfiguriert.
5.  BunkerWeb kümmert sich im Hintergrund um die Erneuerung der Zertifikate vor deren Ablauf und gewährleistet so eine kontinuierliche HTTPS-Verfügbarkeit.
6.  Der gesamte Prozess ist vollständig automatisiert und erfordert nach der Ersteinrichtung nur minimale Eingriffe.

!!! info "Voraussetzungen"
    Um diese Funktion nutzen zu können, stellen Sie sicher, dass für jede Domain korrekte DNS-**A-Einträge** konfiguriert sind, die auf die öffentliche(n) IP(s) verweisen, unter der/denen BunkerWeb erreichbar ist. Ohne korrekte DNS-Konfiguration schlägt der Domain-Verifizierungsprozess fehl.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Let's Encrypt-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Setzen Sie die Einstellung `AUTO_LETS_ENCRYPT` auf `yes`, um die automatische Ausstellung und Erneuerung von Zertifikaten zu aktivieren.
2.  **Kontakt-E-Mail angeben (empfohlen):** Geben Sie Ihre E-Mail-Adresse in der Einstellung `EMAIL_LETS_ENCRYPT` ein, damit Let's Encrypt Sie vor ablaufenden Zertifikaten warnen kann. Wenn Sie das Feld leer lassen, registriert sich BunkerWeb ohne Adresse (Certbot-Option `--register-unsafely-without-email`) – Sie erhalten dann keine Erinnerungen oder Wiederherstellungs-E-Mails.
3.  **Wählen Sie den Challenge-Typ:** Wählen Sie entweder die `http`- oder `dns`-Verifizierung mit der Einstellung `LETS_ENCRYPT_CHALLENGE`.
4.  **DNS-Anbieter konfigurieren:** Wenn Sie DNS-Challenges verwenden, geben Sie Ihren DNS-Anbieter und Ihre Anmeldeinformationen an.
5.  **Zertifikatsprofil auswählen:** Wählen Sie Ihr bevorzugtes Zertifikatsprofil mit der Einstellung `LETS_ENCRYPT_PROFILE` (classic, tlsserver oder shortlived).
6.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration werden Zertifikate automatisch ausgestellt, installiert und bei Bedarf erneuert.

!!! tip "Zertifikatsprofile"
    Let's Encrypt bietet verschiedene Zertifikatsprofile für unterschiedliche Anwendungsfälle:

    - **classic**: Allzweck-Zertifikate mit 90-tägiger Gültigkeit (Standard)
    - **tlsserver**: Optimiert für die TLS-Server-Authentifizierung mit 90-tägiger Gültigkeit und kleinerem Payload
    - **shortlived**: Erhöhte Sicherheit mit 7-tägiger Gültigkeit für automatisierte Umgebungen
    - **custom**: Wenn Ihr ACME-Server ein anderes Profil unterstützt, legen Sie es mit `LETS_ENCRYPT_CUSTOM_PROFILE` fest.

!!! info "Profilverfügbarkeit"
    Beachten Sie, dass die Profile `tlsserver` und `shortlived` derzeit möglicherweise nicht in allen Umgebungen oder mit allen ACME-Clients verfügbar sind. Das `classic`-Profil hat die breiteste Kompatibilität und wird für die meisten Benutzer empfohlen. Wenn ein ausgewähltes Profil nicht verfügbar ist, greift das System automatisch auf das `classic`-Profil zurück.

### Konfigurationseinstellungen

| Einstellung                                 | Standard  | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------- | --------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AUTO_LETS_ENCRYPT`                         | `no`      | multisite | nein     | **Let's Encrypt aktivieren:** Auf `yes` setzen, um die automatische Ausstellung und Erneuerung von Zertifikaten zu aktivieren.                                                                                                                                                                                                                                         |
| `LETS_ENCRYPT_PASSTHROUGH`                  | `no`      | multisite | nein     | **Let's Encrypt durchleiten:** Auf `yes` setzen, um Let's Encrypt-Anfragen an den Webserver weiterzuleiten. Dies ist nützlich, wenn BunkerWeb hinter einem anderen Reverse-Proxy mit SSL-Handling steht.                                                                                                                                                               |
| `EMAIL_LETS_ENCRYPT`                        | `-`       | multisite | nein     | **Kontakt-E-Mail:** E-Mail-Adresse für Let's-Encrypt-Erinnerungen. Lassen Sie das Feld nur leer, wenn Sie akzeptieren, dass keine Warnungen oder Wiederherstellungs-E-Mails gesendet werden (Certbot registriert mit `--register-unsafely-without-email`).                                                                                                             |
| `LETS_ENCRYPT_CHALLENGE`                    | `http`    | multisite | nein     | **Challenge-Typ:** Methode zur Überprüfung des Domainbesitzes. Optionen: `http` oder `dns`.                                                                                                                                                                                                                                                                            |
| `LETS_ENCRYPT_DNS_PROVIDER`                 |           | multisite | nein     | **DNS-Anbieter:** Bei Verwendung von DNS-Challenges der zu verwendende DNS-Anbieter (z.B. cloudflare, route53, digitalocean).                                                                                                                                                                                                                                          |
| `LETS_ENCRYPT_DNS_PROPAGATION`              | `default` | multisite | nein     | **DNS-Propagation:** Die Wartezeit für die DNS-Propagation in Sekunden. Wenn kein Wert angegeben wird, wird die Standard-Propagationszeit des Anbieters verwendet.                                                                                                                                                                                                     |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`          |           | multisite | ja       | **Anmeldeinformationselement:** Konfigurationselemente für die Authentifizierung des DNS-Anbieters (z. B. `cloudflare_api_token 123456`). Werte können Rohtext, base64-kodiert oder ein JSON-Objekt sein.                                                                                                                                                              |
| `LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64` | `yes`     | multisite | nein     | **DNS-Anmeldeinformationen Base64 dekodieren:** Dekodiert automatisch base64-kodierte DNS-Anbieter-Anmeldeinformationen, wenn auf `yes` gesetzt. Wenn aktiviert, werden Werte, die dem Base64-Format entsprechen, vor der Verwendung dekodiert (außer beim `rfc2136`-Anbieter). Deaktivieren Sie dies, wenn Ihre Anmeldeinformationen absichtlich Base64-codiert sind. |
| `USE_LETS_ENCRYPT_WILDCARD`                 | `no`      | multisite | nein     | **Wildcard-Zertifikate:** Wenn auf `yes` gesetzt, werden Wildcard-Zertifikate für alle Domains erstellt. Nur mit DNS-Challenges verfügbar.                                                                                                                                                                                                                             |
| `USE_LETS_ENCRYPT_STAGING`                  | `no`      | multisite | nein     | **Staging verwenden:** Wenn auf `yes` gesetzt, wird die Staging-Umgebung von Let's Encrypt zum Testen verwendet. Staging hat höhere Ratenbegrenzungen, aber die Zertifikate sind nicht vertrauenswürdig.                                                                                                                                                               |
| `LETS_ENCRYPT_CLEAR_OLD_CERTS`              | `no`      | global    | nein     | **Alte Zertifikate löschen:** Wenn auf `yes` gesetzt, werden alte Zertifikate, die bei der Erneuerung nicht mehr benötigt werden, entfernt.                                                                                                                                                                                                                            |
| `LETS_ENCRYPT_CONCURRENT_REQUESTS`          | `no`      | global    | nein     | **Parallele Anfragen:** Wenn auf `yes` gesetzt, stellt certbot-new Zertifikatsanfragen parallel. Vorsicht wegen Rate-Limits.                                                                                                                                                                                                                                           |
| `LETS_ENCRYPT_PROFILE`                      | `classic` | multisite | nein     | **Zertifikatsprofil:** Wählen Sie das zu verwendende Zertifikatsprofil aus. Optionen: `classic` (Allzweck), `tlsserver` (optimiert für TLS-Server) oder `shortlived` (7-Tage-Zertifikate).                                                                                                                                                                             |
| `LETS_ENCRYPT_CUSTOM_PROFILE`               |           | multisite | nein     | **Benutzerdefiniertes Zertifikatsprofil:** Geben Sie ein benutzerdefiniertes Zertifikatsprofil ein, wenn Ihr ACME-Server nicht standardmäßige Profile unterstützt. Dies überschreibt `LETS_ENCRYPT_PROFILE`, falls gesetzt.                                                                                                                                            |
| `LETS_ENCRYPT_MAX_RETRIES`                  | `3`       | multisite | nein     | **Maximale Wiederholungen:** Anzahl der Wiederholungsversuche bei der Zertifikatserstellung bei einem Fehler. Auf `0` setzen, um Wiederholungen zu deaktivieren. Nützlich bei temporären Netzwerkproblemen.                                                                                                                                                            |

!!! info "Informationen und Verhalten"
    - Die Einstellung `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` ist eine Mehrfacheinstellung und kann verwendet werden, um mehrere Elemente für den DNS-Anbieter festzulegen. Die Elemente werden als Cache-Datei gespeichert, und Certbot liest die Anmeldeinformationen daraus.
    - Wenn keine `LETS_ENCRYPT_DNS_PROPAGATION`-Einstellung angegeben ist, wird die Standard-Propagationszeit des Anbieters verwendet.
    - Die vollständige Let's Encrypt-Automatisierung mit der `http`-Challenge funktioniert im Stream-Modus, solange Sie den Port `80/tcp` von außen öffnen. Verwenden Sie die Einstellung `LISTEN_STREAM_PORT_SSL`, um Ihren SSL/TLS-Listening-Port zu wählen.
    - Wenn `LETS_ENCRYPT_PASSTHROUGH` auf `yes` gesetzt ist, behandelt BunkerWeb die ACME-Challenge-Anfragen nicht selbst, sondern leitet sie an den Backend-Webserver weiter. Dies ist nützlich in Szenarien, in denen BunkerWeb als Reverse-Proxy vor einem anderen Server fungiert, der für die Verarbeitung von Let's Encrypt-Challenges konfiguriert ist.

!!! tip "HTTP- vs. DNS-Challenges"
    **HTTP-Challenges** sind einfacher einzurichten und funktionieren für die meisten Websites gut:

    - Erfordert, dass Ihre Website öffentlich auf Port 80 erreichbar ist
    - Wird automatisch von BunkerWeb konfiguriert
    - Kann nicht für Wildcard-Zertifikate verwendet werden

    **DNS-Challenges** bieten mehr Flexibilität und sind für Wildcard-Zertifikate erforderlich:

    - Funktioniert auch, wenn Ihre Website nicht öffentlich erreichbar ist
    - Erfordert API-Anmeldeinformationen des DNS-Anbieters
    - Erforderlich für Wildcard-Zertifikate (z. B. *.example.com)
    - Nützlich, wenn Port 80 blockiert oder nicht verfügbar ist

!!! warning "Wildcard-Zertifikate"
    Wildcard-Zertifikate sind nur mit DNS-Challenges verfügbar. Wenn Sie sie verwenden möchten, müssen Sie die Einstellung `USE_LETS_ENCRYPT_WILDCARD` auf `yes` setzen und Ihre DNS-Anbieter-Anmeldeinformationen korrekt konfigurieren.

!!! warning "Ratenbegrenzungen"
    Let's Encrypt hat Ratenbegrenzungen für die Ausstellung von Zertifikaten. Verwenden Sie beim Testen von Konfigurationen die Staging-Umgebung, indem Sie `USE_LETS_ENCRYPT_STAGING` auf `yes` setzen, um zu vermeiden, dass Sie die Produktions-Ratenbegrenzungen erreichen. Staging-Zertifikate sind von Browsern nicht vertrauenswürdig, aber nützlich zur Validierung Ihrer Einrichtung.

### Unterstützte DNS-Anbieter

Das Let's Encrypt-Plugin unterstützt eine breite Palette von DNS-Anbietern für DNS-Challenges. Jeder Anbieter benötigt spezifische Anmeldeinformationen, die über die Einstellung `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` bereitgestellt werden müssen.

| Anbieter          | Beschreibung     | Obligatorische Einstellungen                                                                                 | Optionale Einstellungen                                                                                                                                                                                                                                                      | Dokumentation                                                                                         |
| ----------------- | ---------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `bunny`           | bunny.net        | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/mwt/certbot-dns-bunny/blob/main/README.rst)                        |
| `cloudflare`      | Cloudflare       | entweder `api_token`<br>oder `email` und `api_key`                                                           |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)                             |
| `desec`           | deSEC            | `token`                                                                                                      |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/desec-io/certbot-dns-desec/blob/main/README.md)                    |
| `digitalocean`    | DigitalOcean     | `token`                                                                                                      |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)                           |
| `domainoffensive` | Domain-Offensive | `api_token`                                                                                                  |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/domainoffensive/certbot-dns-domainoffensive/blob/master/README.md) |
| `domeneshop`      | Domeneshop       | `token`<br>`secret`                                                                                          |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/domeneshop/certbot-dns-domeneshop/blob/master/README.rst)          |
| `dnsimple`        | DNSimple         | `token`                                                                                                      |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)                               |
| `dnsmadeeasy`     | DNS Made Easy    | `api_key`<br>`secret_key`                                                                                    |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)                            |
| `duckdns`         | DuckDNS          | `duckdns_token`                                                                                              |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/infinityofspace/certbot_dns_duckdns/blob/main/Readme.md)           |
| `dynu`            | Dynu             | `auth_token`                                                                                                 |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/bikram990/certbot-dns-dynu/blob/main/README.md)                    |
| `gehirn`          | Gehirn DNS       | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                                 |
| `godaddy`         | GoDaddy          | `key`<br>`secret`                                                                                            | `ttl` (Standard: `600`)                                                                                                                                                                                                                                                      | [Dokumentation](https://github.com/miigotu/certbot-dns-godaddy/blob/main/README.md)                   |
| `google`          | Google Cloud     | `project_id`<br>`private_key_id`<br>`private_key`<br>`client_email`<br>`client_id`<br>`client_x509_cert_url` | `type` (Standard: `service_account`)<br>`auth_uri` (Standard: `https://accounts.google.com/o/oauth2/auth`)<br>`token_uri` (Standard: `https://accounts.google.com/o/oauth2/token`)<br>`auth_provider_x509_cert_url` (Standard: `https://www.googleapis.com/oauth2/v1/certs`) | [Dokumentation](https://certbot-dns-google.readthedocs.io/en/stable/)                                 |
| `infomaniak`      | Infomaniak       | `token`                                                                                                      |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/infomaniak/certbot-dns-infomaniak/blob/main/README.rst)            |
| `ionos`           | IONOS            | `prefix`<br>`secret`                                                                                         | `endpoint` (Standard: `https://api.hosting.ionos.com`)                                                                                                                                                                                                                       | [Dokumentation](https://github.com/helgeerbe/certbot-dns-ionos/blob/master/README.md)                 |
| `linode`          | Linode           | `key`                                                                                                        |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-linode.readthedocs.io/en/stable/)                                 |
| `luadns`          | LuaDNS           | `email`<br>`token`                                                                                           |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-luadns.readthedocs.io/en/stable/)                                 |
| `njalla`          | Njalla           | `token`                                                                                                      |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/chaptergy/certbot-dns-njalla/blob/main/README.md)                  |
| `nsone`           | NS1              | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-nsone.readthedocs.io/en/stable/)                                  |
| `ovh`             | OVH              | `application_key`<br>`application_secret`<br>`consumer_key`                                                  | `endpoint` (Standard: `ovh-eu`)                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-ovh.readthedocs.io/en/stable/)                                    |
| `pdns`            | PowerDNS         | `endpoint`<br>`api_key`<br>`server_id` (default: `localhost`)<br>`disable_notify` (default: `false`)         |                                                                                                                                                                                                                                                                              | [Documentation](https://github.com/kaechele/certbot-dns-pdns/blob/main/README.md)                     |
| `rfc2136`         | RFC 2136         | `server`<br>`name`<br>`secret`                                                                               | `port` (Standard: `53`)<br>`algorithm` (Standard: `HMAC-SHA512`)<br>`sign_query` (Standard: `false`)                                                                                                                                                                         | [Dokumentation](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                                |
| `route53`         | Amazon Route 53  | `access_key_id`<br>`secret_access_key`                                                                       |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-route53.readthedocs.io/en/stable/)                                |
| `sakuracloud`     | Sakura Cloud     | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)                            |
| `scaleway`        | Scaleway         | `application_token`                                                                                          |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst)                 |
| `transip`         | TransIP          | `key_file`<br>`username`                                                                                     |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-transip.readthedocs.io/en/stable/)                                |

### Beispielkonfigurationen

=== "Grundlegende HTTP-Challenge"

    Einfache Konfiguration mit HTTP-Challenges für eine einzelne Domain:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ```

=== "Cloudflare DNS mit Wildcard"

    Konfiguration für Wildcard-Zertifikate mit Cloudflare DNS:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "api_token IHR_API_TOKEN"
    USE_LETS_ENCRYPT_WILDCARD: "yes"
    ```

=== "AWS Route53-Konfiguration"

    Konfiguration mit Amazon Route53 für DNS-Challenges:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "route53"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "aws_access_key_id IHR_ZUGRIFFSSCHLUESSEL"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "aws_secret_access_key IHR_GEHEIMSCHLUESSEL"
    ```

=== "Testen mit Staging-Umgebung und Wiederholungen"

    Konfiguration zum Testen der Einrichtung mit der Staging-Umgebung und erweiterten Wiederholungseinstellungen:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    USE_LETS_ENCRYPT_STAGING: "yes"
    LETS_ENCRYPT_MAX_RETRIES: "5"
    ```

=== "DigitalOcean mit benutzerdefinierter Propagationszeit"

    Konfiguration mit DigitalOcean DNS mit einer längeren Propagationswartezeit:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "digitalocean"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "token IHR_API_TOKEN"
    LETS_ENCRYPT_DNS_PROPAGATION: "120"
    ```

=== "Google Cloud DNS"

    Konfiguration mit Google Cloud DNS mit Anmeldeinformationen für ein Dienstkonto:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "google"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "project_id ihre-projekt-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "private_key_id ihre-private-key-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_3: "private_key ihr-private-key"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_4: "client_email ihre-dienstkonto-email"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_5: "client_id ihre-client-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_6: "client_x509_cert_url ihre-zertifikats-url"
    ```

## Limit

STREAM-Unterstützung :warning:

Das Limit-Plugin in BunkerWeb bietet robuste Funktionen zur Durchsetzung von Begrenzungsrichtlinien auf Ihrer Website, um eine faire Nutzung zu gewährleisten und Ihre Ressourcen vor Missbrauch, Denial-of-Service-Angriffen und übermäßigem Ressourcenverbrauch zu schützen. Diese Richtlinien umfassen:

- **Anzahl der Verbindungen pro IP-Adresse** (STREAM-Unterstützung :white_check_mark:)
- **Anzahl der Anfragen pro IP-Adresse und URL innerhalb eines bestimmten Zeitraums** (STREAM-Unterstützung :x:)

### Wie es funktioniert

1.  **Ratenbegrenzung:** Verfolgt die Anzahl der Anfragen von jeder Client-IP-Adresse an bestimmte URLs. Wenn ein Client die konfigurierte Ratenbegrenzung überschreitet, werden nachfolgende Anfragen vorübergehend abgelehnt.
2.  **Verbindungsbegrenzung:** Überwacht und beschränkt die Anzahl der gleichzeitigen Verbindungen von jeder Client-IP-Adresse. Je nach verwendetem Protokoll (HTTP/1, HTTP/2, HTTP/3 oder Stream) können unterschiedliche Verbindungsgrenzen angewendet werden.
3.  In beiden Fällen erhalten Clients, die die definierten Grenzwerte überschreiten, den HTTP-Statuscode **„429 - Too Many Requests“**, was hilft, eine Serverüberlastung zu verhindern.

### Schritte zur Verwendung

1.  **Anforderungsratenbegrenzung aktivieren:** Verwenden Sie `USE_LIMIT_REQ`, um die Anforderungsratenbegrenzung zu aktivieren und URL-Muster zusammen mit ihren entsprechenden Ratenbegrenzungen zu definieren.
2.  **Verbindungsbegrenzung aktivieren:** Verwenden Sie `USE_LIMIT_CONN`, um die Verbindungsbegrenzung zu aktivieren und die maximale Anzahl gleichzeitiger Verbindungen für verschiedene Protokolle festzulegen.
3.  **Granulare Kontrolle anwenden:** Erstellen Sie mehrere Ratenbegrenzungsregeln für verschiedene URLs, um unterschiedliche Schutzniveaus auf Ihrer gesamten Website bereitzustellen.
4.  **Wirksamkeit überwachen:** Verwenden Sie die [Web-Benutzeroberfläche](web-ui.md), um Statistiken über begrenzte Anfragen und Verbindungen anzuzeigen.

### Konfigurationseinstellungen

=== "Anforderungsratenbegrenzung"

    | Einstellung      | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                                             |
    | ---------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
    | `USE_LIMIT_REQ`  | `yes`    | multisite | nein     | **Anforderungsbegrenzung aktivieren:** Auf `yes` setzen, um die Funktion zur Ratenbegrenzung von Anfragen zu aktivieren.                                                 |
    | `LIMIT_REQ_URL`  | `/`      | multisite | ja       | **URL-Muster:** URL-Muster (PCRE-Regex), auf das die Ratenbegrenzung angewendet wird; verwenden Sie `/`, um es für alle Anfragen anzuwenden.                             |
    | `LIMIT_REQ_RATE` | `2r/s`   | multisite | ja       | **Ratenbegrenzung:** Maximale Anfragerate im Format `Nr/t`, wobei N die Anzahl der Anfragen und t die Zeiteinheit ist: s (Sekunde), m (Minute), h (Stunde) oder d (Tag). |

!!! tip "Format der Ratenbegrenzung"
    Das Format der Ratenbegrenzung wird als `Nr/t` angegeben, wobei:

    - `N` die Anzahl der erlaubten Anfragen ist
    - `r` ein literales 'r' ist (für 'requests')
    - `/` ein literaler Schrägstrich ist
    - `t` die Zeiteinheit ist: `s` (Sekunde), `m` (Minute), `h` (Stunde) oder `d` (Tag)

    Zum Beispiel bedeutet `5r/m`, dass 5 Anfragen pro Minute von jeder IP-Adresse erlaubt sind.

=== "Verbindungsbegrenzung"

    | Einstellung             | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                     |
    | ----------------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
    | `USE_LIMIT_CONN`        | `yes`    | multisite | nein     | **Verbindungsbegrenzung aktivieren:** Auf `yes` setzen, um die Funktion zur Verbindungsbegrenzung zu aktivieren. |
    | `LIMIT_CONN_MAX_HTTP1`  | `10`     | multisite | nein     | **HTTP/1.X-Verbindungen:** Maximale Anzahl gleichzeitiger HTTP/1.X-Verbindungen pro IP-Adresse.                  |
    | `LIMIT_CONN_MAX_HTTP2`  | `100`    | multisite | nein     | **HTTP/2-Streams:** Maximale Anzahl gleichzeitiger HTTP/2-Streams pro IP-Adresse.                                |
    | `LIMIT_CONN_MAX_HTTP3`  | `100`    | multisite | nein     | **HTTP/3-Streams:** Maximale Anzahl gleichzeitiger HTTP/3-Streams pro IP-Adresse.                                |
    | `LIMIT_CONN_MAX_STREAM` | `10`     | multisite | nein     | **Stream-Verbindungen:** Maximale Anzahl gleichzeitiger Stream-Verbindungen pro IP-Adresse.                      |

!!! info "Verbindungs- vs. Anforderungsbegrenzung"

- **Verbindungsbegrenzung** beschränkt die Anzahl der gleichzeitigen Verbindungen, die eine einzelne IP-Adresse aufrechterhalten kann.
- **Anforderungsratenbegrenzung** beschränkt die Anzahl der Anfragen, die eine IP-Adresse innerhalb eines definierten Zeitraums stellen kann.

  Die Verwendung beider Methoden bietet einen umfassenden Schutz gegen verschiedene Arten von Missbrauch.

!!! warning "Festlegen angemessener Grenzwerte"
    Zu restriktive Grenzwerte können legitime Benutzer beeinträchtigen, insbesondere bei HTTP/2 und HTTP/3, wo Browser oft mehrere Streams verwenden. Die Standardwerte sind für die meisten Anwendungsfälle ausgewogen, aber erwägen Sie, sie je nach den Bedürfnissen Ihrer Anwendung und dem Benutzerverhalten anzupassen.

### Beispielkonfigurationen

=== "Grundschutz"

    Eine einfache Konfiguration mit Standardeinstellungen zum Schutz Ihrer gesamten Website:

    ```yaml
    USE_LIMIT_REQ: "yes"
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "2r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "Schutz spezifischer Endpunkte"

    Konfiguration mit unterschiedlichen Ratenbegrenzungen für verschiedene Endpunkte:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Standardregel für alle Anfragen
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "10r/s"

    # Strengere Begrenzung für die Anmeldeseite
    LIMIT_REQ_URL_2: "^/login"
    LIMIT_REQ_RATE_2: "1r/s"

    # Strengere Begrenzung für die API
    LIMIT_REQ_URL_3: "^/api/"
    LIMIT_REQ_RATE_3: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "Konfiguration für eine Website mit hohem Verkehrsaufkommen"

    Konfiguration, die für Websites mit hohem Verkehrsaufkommen mit großzügigeren Grenzwerten optimiert ist:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Allgemeine Begrenzung
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "30r/s"

    # Schutz des Admin-Bereichs
    LIMIT_REQ_URL_2: "^/admin/"
    LIMIT_REQ_RATE_2: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "50"
    LIMIT_CONN_MAX_HTTP2: "200"
    LIMIT_CONN_MAX_HTTP3: "200"
    LIMIT_CONN_MAX_STREAM: "30"
    ```

=== "Konfiguration für einen API-Server"

    Konfiguration, die für einen API-Server mit Ratenbegrenzungen in Anfragen pro Minute optimiert ist:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Öffentliche API-Endpunkte
    LIMIT_REQ_URL: "^/api/public/"
    LIMIT_REQ_RATE: "120r/m"

    # Private API-Endpunkte
    LIMIT_REQ_URL_2: "^/api/private/"
    LIMIT_REQ_RATE_2: "300r/m"

    # Authentifizierungsendpunkt
    LIMIT_REQ_URL_3: "^/api/auth"
    LIMIT_REQ_RATE_3: "10r/m"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "20"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "20"
    ```

## Load Balancer <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


<p align='center'><iframe style='display: block;' width='560' height='315' data-src='https://www.youtube-nocookie.com/embed/cOVp0rAt5nw' title='Load Balancer' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe></p>

STREAM-Unterstützung :x:

Provides load balancing feature to group of upstreams with optional healthchecks.

| Einstellung                               | Standardwert  | Kontext | Mehrfach | Beschreibung                                                       |
| ----------------------------------------- | ------------- | ------- | -------- | ------------------------------------------------------------------ |
| `LOADBALANCER_HEALTHCHECK_DICT_SIZE`      | `10m`         | global  | nein     | Shared dict size (datastore for all healthchecks).                 |
| `LOADBALANCER_UPSTREAM_NAME`              |               | global  | ja       | Name of the upstream (used in REVERSE_PROXY_HOST).                 |
| `LOADBALANCER_UPSTREAM_SERVERS`           |               | global  | ja       | List of servers/IPs in the server group.                           |
| `LOADBALANCER_UPSTREAM_MODE`              | `round-robin` | global  | ja       | Load balancing mode (round-robin or sticky).                       |
| `LOADBALANCER_UPSTREAM_STICKY_METHOD`     | `ip`          | global  | ja       | Sticky session method (ip or cookie).                              |
| `LOADBALANCER_UPSTREAM_RESOLVE`           | `no`          | global  | ja       | Dynamically resolve upstream hostnames.                            |
| `LOADBALANCER_UPSTREAM_KEEPALIVE`         |               | global  | ja       | Number of keepalive connections to cache per worker.               |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIMEOUT` | `60s`         | global  | ja       | Keepalive timeout for upstream connections.                        |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIME`    | `1h`          | global  | ja       | Keepalive time for upstream connections.                           |
| `LOADBALANCER_HEALTHCHECK_URL`            | `/status`     | global  | ja       | The healthcheck URL.                                               |
| `LOADBALANCER_HEALTHCHECK_INTERVAL`       | `2000`        | global  | ja       | Healthcheck interval in milliseconds.                              |
| `LOADBALANCER_HEALTHCHECK_TIMEOUT`        | `1000`        | global  | ja       | Healthcheck timeout in milliseconds.                               |
| `LOADBALANCER_HEALTHCHECK_FALL`           | `3`           | global  | ja       | Number of failed healthchecks before marking the server as down.   |
| `LOADBALANCER_HEALTHCHECK_RISE`           | `1`           | global  | ja       | Number of successful healthchecks before marking the server as up. |
| `LOADBALANCER_HEALTHCHECK_VALID_STATUSES` | `200`         | global  | ja       | HTTP status considered valid in healthchecks.                      |
| `LOADBALANCER_HEALTHCHECK_CONCURRENCY`    | `10`          | global  | ja       | Maximum number of concurrent healthchecks.                         |
| `LOADBALANCER_HEALTHCHECK_TYPE`           | `http`        | global  | ja       | Type of healthcheck (http or https).                               |
| `LOADBALANCER_HEALTHCHECK_SSL_VERIFY`     | `yes`         | global  | ja       | Verify SSL certificate in healthchecks.                            |
| `LOADBALANCER_HEALTHCHECK_HOST`           |               | global  | ja       | Host header for healthchecks (useful for HTTPS).                   |

## Metrics

STREAM-Unterstützung :warning:

Das Metrics-Plugin bietet umfassende Überwachungs- und Datenerfassungsfunktionen für Ihre BunkerWeb-Instanz. Mit dieser Funktion können Sie verschiedene Leistungsindikatoren, Sicherheitsereignisse und Systemstatistiken verfolgen und erhalten so wertvolle Einblicke in das Verhalten und den Zustand Ihrer geschützten Websites und Dienste.

**So funktioniert es:**

1.  BunkerWeb erfasst während der Verarbeitung von Anfragen und Antworten wichtige Metriken.
2.  Zu diesen Metriken gehören Zähler für blockierte Anfragen, Leistungsmessungen und verschiedene sicherheitsrelevante Statistiken.
3.  Die Daten werden effizient im Speicher gespeichert, mit konfigurierbaren Grenzwerten, um eine übermäßige Ressourcennutzung zu verhindern.
4.  Für Multi-Instanz-Setups kann Redis zur Zentralisierung und Aggregation von Metrikdaten verwendet werden.
5.  Auf die erfassten Metriken kann über die API zugegriffen oder in der [Web-Benutzeroberfläche](web-ui.md) visualisiert werden.
6.  Diese Informationen helfen Ihnen, Sicherheitsbedrohungen zu identifizieren, Probleme zu beheben und Ihre Konfiguration zu optimieren.

### Technische Umsetzung

Das Metrics-Plugin funktioniert durch:

- Verwendung gemeinsamer Wörterbücher in NGINX, wobei `metrics_datastore` für HTTP und `metrics_datastore_stream` für TCP/UDP-Verkehr verwendet wird
- Nutzung eines LRU-Cache für eine effiziente In-Memory-Speicherung
- Periodische Synchronisierung von Daten zwischen Workern mithilfe von Timern
- Speicherung detaillierter Informationen über blockierte Anfragen, einschließlich der Client-IP-Adresse, des Landes, des Zeitstempels, der Anfragedetails und des Blockierungsgrunds
- Unterstützung von Plugin-spezifischen Metriken über eine gemeinsame Schnittstelle zur Metrikerfassung
- Bereitstellung von API-Endpunkten zur Abfrage erfasster Metriken

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Metrics-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die Metrikerfassung ist standardmäßig aktiviert. Sie können dies mit der Einstellung `USE_METRICS` steuern.
2.  **Speicherzuweisung konfigurieren:** Legen Sie die Speichermenge fest, die für die Metrikspeicherung zugewiesen werden soll, indem Sie die Einstellung `METRICS_MEMORY_SIZE` verwenden.
3.  **Speichergrenzen festlegen:** Definieren Sie, wie viele blockierte Anfragen pro Worker und in Redis mit den entsprechenden Einstellungen gespeichert werden sollen.
4.  **Auf die Daten zugreifen:** Sehen Sie sich die erfassten Metriken über die [Web-Benutzeroberfläche](web-ui.md) oder API-Endpunkte an.
5.  **Informationen analysieren:** Verwenden Sie die gesammelten Daten, um Muster zu erkennen, Sicherheitsprobleme zu identifizieren und Ihre Konfiguration zu optimieren.

### Erfasste Metriken

Das Metrics-Plugin erfasst die folgenden Informationen:

1.  **Blockierte Anfragen**: Für jede blockierte Anfrage werden die folgenden Daten gespeichert:
    - Anfrage-ID und Zeitstempel
    - Client-IP-Adresse und Land (sofern verfügbar)
    - HTTP-Methode und URL
    - HTTP-Statuscode
    - User-Agent
    - Blockierungsgrund und Sicherheitsmodus
    - Servername
    - Zusätzliche Daten im Zusammenhang mit dem Blockierungsgrund

2.  **Plugin-Zähler**: Verschiedene Plugin-spezifische Zähler, die Aktivitäten und Ereignisse verfolgen.

### API-Zugriff

Auf Metrikdaten kann über die internen API-Endpunkte von BunkerWeb zugegriffen werden:

- **Endpunkt**: `/metrics/{filter}`
- **Methode**: GET
- **Beschreibung**: Ruft Metrikdaten basierend auf dem angegebenen Filter ab
- **Antwortformat**: JSON-Objekt, das die angeforderten Metriken enthält

Zum Beispiel gibt `/metrics/requests` Informationen über blockierte Anfragen zurück.

!!! info "Konfiguration des API-Zugriffs"
    Um über die API auf Metriken zuzugreifen, müssen Sie sicherstellen, dass:

    1. Die API-Funktion mit `USE_API: "yes"` aktiviert ist (standardmäßig aktiviert)
    2. Ihre Client-IP in der Einstellung `API_WHITELIST_IP` enthalten ist (Standard ist `127.0.0.0/8`)
    3. Sie auf die API über den konfigurierten Port zugreifen (Standard ist `5000` über die Einstellung `API_HTTP_PORT`)
    4. Sie den korrekten `API_SERVER_NAME`-Wert im Host-Header verwenden (Standard ist `bwapi`)
    5. Wenn `API_TOKEN` konfiguriert ist, fügen Sie `Authorization: Bearer <token>` in die Anfrage-Header ein.

    Typische Anfragen:

    Ohne Token (wenn `API_TOKEN` nicht gesetzt ist):
    ```bash
    curl -H "Host: bwapi" \
         http://ihre-bunkerweb-instanz:5000/metrics/requests
    ```

    Mit Token (wenn `API_TOKEN` gesetzt ist):
    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://ihre-bunkerweb-instanz:5000/metrics/requests
    ```

    Wenn Sie den `API_SERVER_NAME` auf einen anderen Wert als den Standard `bwapi` angepasst haben, verwenden Sie diesen Wert stattdessen im Host-Header.

    Für sichere Produktionsumgebungen beschränken Sie den API-Zugriff auf vertrauenswürdige IPs und aktivieren Sie `API_TOKEN`.

### Konfigurationseinstellungen

| Einstellung                          | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                              |
| ------------------------------------ | -------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_METRICS`                        | `yes`    | multisite | nein     | **Metriken aktivieren:** Auf `yes` setzen, um die Erfassung und den Abruf von Metriken zu aktivieren.                                     |
| `METRICS_MEMORY_SIZE`                | `16m`    | global    | nein     | **Speichergröße:** Größe des internen Speichers für Metriken (z. B. `16m`, `32m`).                                                        |
| `METRICS_MAX_BLOCKED_REQUESTS`       | `1000`   | global    | nein     | **Max. blockierte Anfragen:** Maximale Anzahl blockierter Anfragen, die pro Worker gespeichert werden sollen.                             |
| `METRICS_MAX_BLOCKED_REQUESTS_REDIS` | `100000` | global    | nein     | **Max. Redis-blockierte Anfragen:** Maximale Anzahl blockierter Anfragen, die in Redis gespeichert werden sollen.                         |
| `METRICS_SAVE_TO_REDIS`              | `yes`    | global    | nein     | **Metriken in Redis speichern:** Auf `yes` setzen, um Metriken (Zähler und Tabellen) zur clusterweiten Aggregation in Redis zu speichern. |

!!! tip "Dimensionierung der Speicherzuweisung"
    Die Einstellung `METRICS_MEMORY_SIZE` sollte basierend auf Ihrem Verkehrsaufkommen und der Anzahl der Instanzen angepasst werden. Bei stark frequentierten Websites sollten Sie diesen Wert erhöhen, um sicherzustellen, dass alle Metriken ohne Datenverlust erfasst werden.

!!! info "Redis-Integration"
    Wenn BunkerWeb für die Verwendung von [Redis](#redis) konfiguriert ist, synchronisiert das Metrics-Plugin blockierte Anfragedaten automatisch mit dem Redis-Server. Dies bietet eine zentralisierte Ansicht von Sicherheitsereignissen über mehrere BunkerWeb-Instanzen hinweg.

!!! warning "Leistungsüberlegungen"
    Das Festlegen sehr hoher Werte für `METRICS_MAX_BLOCKED_REQUESTS` oder `METRICS_MAX_BLOCKED_REQUESTS_REDIS` kann den Speicherverbrauch erhöhen. Überwachen Sie Ihre Systemressourcen und passen Sie diese Werte entsprechend Ihren tatsächlichen Bedürfnissen und verfügbaren Ressourcen an.

!!! note "Worker-spezifischer Speicher"
    Jeder NGINX-Worker verwaltet seine eigenen Metriken im Speicher. Beim Zugriff auf Metriken über die API werden die Daten aller Worker automatisch aggregiert, um eine vollständige Ansicht zu erhalten.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Standardkonfiguration, die für die meisten Bereitstellungen geeignet ist:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "16m"
    METRICS_MAX_BLOCKED_REQUESTS: "1000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "100000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Umgebung mit geringen Ressourcen"

    Konfiguration, die für Umgebungen mit begrenzten Ressourcen optimiert ist:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "8m"
    METRICS_MAX_BLOCKED_REQUESTS: "500"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10000"
    METRICS_SAVE_TO_REDIS: "no"
    ```

=== "Umgebung mit hohem Verkehrsaufkommen"

    Konfiguration für Websites mit hohem Verkehrsaufkommen, die mehr Sicherheitsereignisse verfolgen müssen:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "64m"
    METRICS_MAX_BLOCKED_REQUESTS: "5000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "500000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Metriken deaktiviert"

    Konfiguration mit deaktivierter Metrikerfassung:

    ```yaml
    USE_METRICS: "no"
    ```

## Migration <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM-Unterstützung :white_check_mark:

Migration of BunkerWeb configuration between instances made easy via the web UI

## Miscellaneous

STREAM-Unterstützung :warning:

Das Plugin "Verschiedenes" (Miscellaneous) bietet **wesentliche Grundeinstellungen**, die helfen, die Sicherheit und Funktionalität Ihrer Website aufrechtzuerhalten. Diese Kernkomponente bietet umfassende Kontrollen für:

- **Serververhalten** - Konfigurieren Sie, wie Ihr Server auf verschiedene Anfragen reagiert
- **HTTP-Einstellungen** - Verwalten Sie Methoden, Anforderungsgrößen und Protokolloptionen
- **Dateiverwaltung** - Steuern Sie die Bereitstellung statischer Dateien und optimieren Sie deren Auslieferung
- **Protokollunterstützung** - Aktivieren Sie moderne HTTP-Protokolle für eine bessere Leistung
- **Systemkonfigurationen** - Erweitern Sie die Funktionalität und verbessern Sie die Sicherheit

Ob Sie HTTP-Methoden einschränken, Anforderungsgrößen verwalten, das Datei-Caching optimieren oder steuern müssen, wie Ihr Server auf verschiedene Anfragen reagiert, dieses Plugin gibt Ihnen die Werkzeuge, um **das Verhalten Ihres Webdienstes feinabzustimmen** und gleichzeitig Leistung und Sicherheit zu optimieren.

### Hauptmerkmale

| Funktionskategorie                    | Beschreibung                                                                                                   |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Steuerung der HTTP-Methoden**       | Definieren Sie, welche HTTP-Methoden für Ihre Anwendung zulässig sind                                          |
| **Schutz des Standardservers**        | Verhindern Sie unbefugten Zugriff durch falsche Hostnamen und erzwingen Sie SNI für sichere Verbindungen       |
| **Verwaltung der Anforderungsgröße**  | Legen Sie Grenzwerte für Client-Anforderungskörper und Datei-Uploads fest                                      |
| **Bereitstellung statischer Dateien** | Konfigurieren und optimieren Sie die Auslieferung von statischen Inhalten aus benutzerdefinierten Stammordnern |
| **Datei-Caching**                     | Verbessern Sie die Leistung durch fortschrittliche Caching-Mechanismen für Dateideskriptoren                   |
| **Protokollunterstützung**            | Konfigurieren Sie moderne HTTP-Protokolloptionen (HTTP2/HTTP3) und Alt-Svc-Porteinstellungen                   |
| **Anonyme Berichterstattung**         | Optionale Nutzungsstatistik-Berichterstattung zur Verbesserung von BunkerWeb                                   |
| **Unterstützung für externe Plugins** | Erweitern Sie die Funktionalität durch die Integration externer Plugins über URLs                              |
| **Steuerung des HTTP-Status**         | Konfigurieren Sie, wie Ihr Server bei der Ablehnung von Anfragen reagiert (einschließlich Verbindungsabbruch)  |

### Konfigurationsanleitung

=== "Sicherheit des Standardservers"

    **Steuerung des Standardservers**

    In HTTP gibt der `Host`-Header den Zielserver an, aber er kann fehlen oder unbekannt sein, oft aufgrund von Bots, die nach Schwachstellen suchen.

    Um solche Anfragen zu blockieren:

    - Setzen Sie `DISABLE_DEFAULT_SERVER` auf `yes`, um solche Anfragen stillschweigend mit dem [NGINX-Statuscode `444`](https://http.dev/444) abzulehnen.
    - Für eine strengere Sicherheit aktivieren Sie `DISABLE_DEFAULT_SERVER_STRICT_SNI`, um SSL/TLS-Verbindungen ohne gültiges SNI abzulehnen.

    !!! success "Sicherheitsvorteile"
        - Blockiert die Manipulation des Host-Headers und das Scannen von virtuellen Hosts
        - Mindert die Risiken von HTTP-Request-Smuggling
        - Entfernt den Standardserver als Angriffsvektor

    | Einstellung                         | Standard | Kontext | Mehrfach | Beschreibung                                                                                                                               |
    | ----------------------------------- | -------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
    | `DISABLE_DEFAULT_SERVER`            | `no`     | global  | nein     | **Standardserver:** Auf `yes` setzen, um den Standardserver zu deaktivieren, wenn kein Hostname mit der Anfrage übereinstimmt.             |
    | `DISABLE_DEFAULT_SERVER_STRICT_SNI` | `no`     | global  | nein     | **Striktes SNI:** Wenn auf `yes` gesetzt, ist SNI für HTTPS-Verbindungen erforderlich und Verbindungen ohne gültiges SNI werden abgelehnt. |

    !!! warning "SNI-Erzwingung"
        Die Aktivierung der strikten SNI-Validierung bietet eine stärkere Sicherheit, kann jedoch Probleme verursachen, wenn BunkerWeb hinter einem Reverse-Proxy betrieben wird, der HTTPS-Anfragen ohne Beibehaltung der SNI-Informationen weiterleitet. Testen Sie gründlich, bevor Sie dies in Produktionsumgebungen aktivieren.

=== "HTTP-Status bei Ablehnung"

    **Steuerung des HTTP-Status**

    Der erste Schritt bei der Behandlung von verweigertem Client-Zugriff ist die Definition der geeigneten Aktion. Dies kann mit der Einstellung `DENY_HTTP_STATUS` konfiguriert werden. Wenn BunkerWeb eine Anfrage ablehnt, können Sie seine Antwort steuern. Standardmäßig gibt es einen `403 Forbidden`-Status zurück und zeigt dem Client eine Webseite oder benutzerdefinierten Inhalt an.

    Alternativ schließt das Setzen auf `444` die Verbindung sofort, ohne eine Antwort zu senden. Dieser [nicht standardmäßige Statuscode](https://http.dev/444), der spezifisch für NGINX ist, ist nützlich, um unerwünschte Anfragen stillschweigend zu verwerfen.

    | Einstellung        | Standard | Kontext | Mehrfach | Beschreibung                                                                                                                                          |
    | ------------------ | -------- | ------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `DENY_HTTP_STATUS` | `403`    | global  | nein     | **HTTP-Status bei Ablehnung:** HTTP-Statuscode, der gesendet wird, wenn eine Anfrage abgelehnt wird (403 oder 444). Code 444 schließt die Verbindung. |

    !!! warning "Überlegungen zum Statuscode 444"
        Da Clients kein Feedback erhalten, kann die Fehlerbehebung schwieriger sein. Das Setzen von `444` wird nur empfohlen, wenn Sie Falsch-Positive gründlich behandelt haben, mit BunkerWeb erfahren sind und ein höheres Sicherheitsniveau benötigen.

    !!! info "Stream-Modus"
        Im **Stream-Modus** wird diese Einstellung immer als `444` erzwungen, was bedeutet, dass die Verbindung geschlossen wird, unabhängig vom konfigurierten Wert.

=== "HTTP-Methoden"

    **Steuerung der HTTP-Methoden**

    Die Beschränkung der HTTP-Methoden auf nur diejenigen, die von Ihrer Anwendung benötigt werden, ist eine grundlegende Sicherheitsmaßnahme, die dem Prinzip der geringsten Rechte folgt. Indem Sie explizit zulässige HTTP-Methoden definieren, können Sie das Risiko der Ausnutzung durch ungenutzte oder gefährliche Methoden minimieren.

    Diese Funktion wird mit der Einstellung `ALLOWED_METHODS` konfiguriert, wobei die Methoden aufgelistet und durch ein `|` getrennt sind (Standard: `GET|POST|HEAD`). Wenn ein Client versucht, eine nicht aufgelistete Methode zu verwenden, antwortet der Server mit einem **405 - Method Not Allowed**-Status.

    Für die meisten Websites ist der Standardwert `GET|POST|HEAD` ausreichend. Wenn Ihre Anwendung RESTful-APIs verwendet, müssen Sie möglicherweise Methoden wie `PUT` und `DELETE` hinzufügen.

    !!! success "Sicherheitsvorteile"
        - Verhindert die Ausnutzung von ungenutzten oder unnötigen HTTP-Methoden
        - Reduziert die Angriffsfläche durch Deaktivierung potenziell schädlicher Methoden
        - Blockiert von Angreifern verwendete Techniken zur Aufzählung von HTTP-Methoden

    | Einstellung       | Standard | Kontext | Mehrfach | Beschreibung |
    | ----------------- | -------- | ------- | -------- | ------------ |
    | `ALLOWED_METHODS` | `GET     | POST    | HEAD`    | multisite    | nein | **HTTP-Methoden:** Liste der erlaubten HTTP-Methoden, getrennt durch Pipe-Zeichen (` | `). |

    !!! abstract "CORS und Preflight-Anfragen"
        Wenn Ihre Anwendung [Cross-Origin Resource Sharing (CORS)](#cors) unterstützt, sollten Sie die `OPTIONS`-Methode in der `ALLOWED_METHODS`-Einstellung aufnehmen, um Preflight-Anfragen zu bearbeiten. Dies gewährleistet die ordnungsgemäße Funktionalität für Browser, die Cross-Origin-Anfragen stellen.

    !!! danger "Sicherheitsüberlegungen"
        - **Vermeiden Sie die Aktivierung von `TRACE` oder `CONNECT`:** Diese Methoden werden selten benötigt und können erhebliche Sicherheitsrisiken mit sich bringen, wie z. B. die Ermöglichung von Cross-Site-Tracing (XST) oder Tunneling-Angriffen.
        - **Überprüfen Sie regelmäßig die erlaubten Methoden:** Überprüfen Sie die `ALLOWED_METHODS`-Einstellung regelmäßig, um sicherzustellen, dass sie den aktuellen Anforderungen Ihrer Anwendung entspricht.
        - **Testen Sie gründlich vor der Bereitstellung:** Änderungen an den Einschränkungen von HTTP-Methoden können die Anwendungsfunktionalität beeinträchtigen. Validieren Sie Ihre Konfiguration in einer Staging-Umgebung, bevor Sie sie in der Produktion anwenden.

=== "Größenbeschränkungen für Anfragen"

    **Größenbeschränkungen für Anfragen**

    Die maximale Größe des Anforderungskörpers kann mit der Einstellung `MAX_CLIENT_SIZE` gesteuert werden (Standard: `10m`). Akzeptierte Werte folgen der [hier](https://nginx.org/en/docs/syntax.html) beschriebenen Syntax.

    !!! success "Sicherheitsvorteile"
        - Schützt vor Denial-of-Service-Angriffen durch übermäßige Payload-Größen
        - Mildert Pufferüberlauf-Schwachstellen
        - Verhindert Angriffe durch Datei-Uploads
        - Reduziert das Risiko der Erschöpfung von Serverressourcen

    | Einstellung       | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                     |
    | ----------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
    | `MAX_CLIENT_SIZE` | `10m`    | multisite | nein     | **Maximale Anforderungsgröße:** Die maximal zulässige Größe für Client-Anforderungskörper (z. B. Datei-Uploads). |

    !!! tip "Best Practices für die Konfiguration der Anforderungsgröße"
        Wenn Sie einen Anforderungskörper von unbegrenzter Größe zulassen müssen, können Sie den Wert `MAX_CLIENT_SIZE` auf `0` setzen. Dies wird jedoch aufgrund potenzieller Sicherheits- und Leistungsrisiken **nicht empfohlen**.

        **Best Practices:**

        - Konfigurieren Sie `MAX_CLIENT_SIZE` immer auf den kleinstmöglichen Wert, der die legitimen Anforderungen Ihrer Anwendung erfüllt.
        - Überprüfen und passen Sie diese Einstellung regelmäßig an die sich ändernden Bedürfnisse Ihrer Anwendung an.
        - Vermeiden Sie es, `0` zu setzen, es sei denn, es ist absolut notwendig, da dies Ihren Server Denial-of-Service-Angriffen und Ressourcenerschöpfung aussetzen kann.

        Durch sorgfältige Verwaltung dieser Einstellung können Sie optimale Sicherheit und Leistung für Ihre Anwendung gewährleisten.

=== "Protokollunterstützung"

    **HTTP-Protokolleinstellungen**

    Moderne HTTP-Protokolle wie HTTP/2 und HTTP/3 verbessern Leistung und Sicherheit. BunkerWeb ermöglicht eine einfache Konfiguration dieser Protokolle.

    !!! success "Sicherheits- und Leistungsvorteile"
        - **Sicherheitsvorteile:** Moderne Protokolle wie HTTP/2 und HTTP/3 erzwingen standardmäßig TLS/HTTPS, reduzieren die Anfälligkeit für bestimmte Angriffe und verbessern die Privatsphäre durch verschlüsselte Header (HTTP/3).
        - **Leistungsvorteile:** Funktionen wie Multiplexing, Header-Komprimierung, Server-Push und binäre Datenübertragung verbessern Geschwindigkeit und Effizienz.

    | Einstellung          | Standard | Kontext   | Mehrfach | Beschreibung                                                                      |
    | -------------------- | -------- | --------- | -------- | --------------------------------------------------------------------------------- |
    | `LISTEN_HTTP`        | `yes`    | multisite | nein     | **HTTP-Listen:** Auf (unsichere) HTTP-Anfragen antworten, wenn auf `yes` gesetzt. |
    | `HTTP2`              | `yes`    | multisite | nein     | **HTTP2:** Unterstützt das HTTP2-Protokoll, wenn HTTPS aktiviert ist.             |
    | `HTTP3`              | `yes`    | multisite | nein     | **HTTP3:** Unterstützt das HTTP3-Protokoll, wenn HTTPS aktiviert ist.             |
    | `HTTP3_ALT_SVC_PORT` | `443`    | multisite | nein     | **HTTP3 Alt-Svc Port:** Port, der im Alt-Svc-Header für HTTP3 verwendet wird.     |

    !!! example "Über HTTP/3"
        HTTP/3, die neueste Version des Hypertext Transfer Protocol, verwendet QUIC über UDP anstelle von TCP und behebt Probleme wie das Head-of-Line-Blocking für schnellere, zuverlässigere Verbindungen.

        NGINX hat ab Version 1.25.0 experimentelle Unterstützung für HTTP/3 und QUIC eingeführt. Diese Funktion ist jedoch noch experimentell, und bei der Verwendung in der Produktion ist Vorsicht geboten. Weitere Einzelheiten finden Sie in der [offiziellen Dokumentation von NGINX](https://nginx.org/en/docs/quic.html).

        Gründliche Tests werden empfohlen, bevor HTTP/3 in Produktionsumgebungen aktiviert wird.

=== "Bereitstellung statischer Dateien"

    **Konfiguration der Dateibereitstellung**

    BunkerWeb kann statische Dateien direkt bereitstellen oder als Reverse-Proxy zu einem Anwendungsserver fungieren. Standardmäßig werden Dateien aus `/var/www/html/{server_name}` bereitgestellt.

    | Einstellung   | Standard                      | Kontext   | Mehrfach | Beschreibung                                                                                                                           |
    | ------------- | ----------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
    | `SERVE_FILES` | `yes`                         | multisite | nein     | **Dateien bereitstellen:** Wenn auf `yes` gesetzt, stellt BunkerWeb statische Dateien aus dem konfigurierten Stammordner bereit.       |
    | `ROOT_FOLDER` | `/var/www/html/{server_name}` | multisite | nein     | **Stammordner:** Das Verzeichnis, aus dem statische Dateien bereitgestellt werden sollen. Leer bedeutet, den Standardort zu verwenden. |

    !!! tip "Best Practices für die Bereitstellung statischer Dateien"
        - **Direkte Bereitstellung:** Aktivieren Sie die Dateibereitstellung (`SERVE_FILES=yes`), wenn BunkerWeb für die direkte Bereitstellung statischer Dateien verantwortlich ist.
        - **Reverse-Proxy:** Wenn BunkerWeb als Reverse-Proxy fungiert, **deaktivieren Sie die Dateibereitstellung** (`SERVE_FILES=no`), um die Angriffsfläche zu reduzieren und die Exposition unnötiger Verzeichnisse zu vermeiden.
        - **Berechtigungen:** Stellen Sie sicher, dass die Dateiberechtigungen und Pfadkonfigurationen korrekt sind, um unbefugten Zugriff zu verhindern.
        - **Sicherheit:** Vermeiden Sie die Exposition sensibler Verzeichnisse oder Dateien durch Fehlkonfigurationen.

        Durch sorgfältige Verwaltung der Bereitstellung statischer Dateien können Sie die Leistung optimieren und gleichzeitig eine sichere Umgebung aufrechterhalten.

=== "Systemeinstellungen"

    **Plugin- und Systemverwaltung**

    Diese Einstellungen verwalten die Interaktion von BunkerWeb mit externen Systemen und tragen durch optionale anonyme Nutzungsstatistiken zur Verbesserung des Produkts bei.

    **Anonyme Berichterstattung**

    Die anonyme Berichterstattung gibt dem BunkerWeb-Team Einblicke, wie die Software verwendet wird. Dies hilft, Verbesserungsbereiche zu identifizieren und die Entwicklung von Funktionen zu priorisieren. Die Berichte sind rein statistisch und enthalten keine sensiblen oder persönlich identifizierbaren Informationen. Sie umfassen:

    - Aktivierte Funktionen
    - Allgemeine Konfigurationsmuster

    Sie können diese Funktion bei Bedarf deaktivieren, indem Sie `SEND_ANONYMOUS_REPORT` auf `no` setzen.

    **Externe Plugins**

    Externe Plugins ermöglichen es Ihnen, die Funktionalität von BunkerWeb durch die Integration von Drittanbieter-Modulen zu erweitern. Dies ermöglicht zusätzliche Anpassungen und fortgeschrittene Anwendungsfälle.

    !!! danger "Sicherheit externer Plugins"
        **Externe Plugins können Sicherheitsrisiken mit sich bringen, wenn sie nicht ordnungsgemäß überprüft werden.** Befolgen Sie diese Best Practices, um potenzielle Bedrohungen zu minimieren:

        - Verwenden Sie nur Plugins aus vertrauenswürdigen Quellen.
        - Überprüfen Sie die Integrität der Plugins mithilfe von Prüfsummen, sofern verfügbar.
        - Überprüfen und aktualisieren Sie Plugins regelmäßig, um Sicherheit und Kompatibilität zu gewährleisten.

        Weitere Einzelheiten finden Sie in der [Plugin-Dokumentation](plugins.md).

    | Einstellung             | Standard | Kontext | Mehrfach | Beschreibung                                                                                  |
    | ----------------------- | -------- | ------- | -------- | --------------------------------------------------------------------------------------------- |
    | `SEND_ANONYMOUS_REPORT` | `yes`    | global  | nein     | **Anonyme Berichte:** Senden Sie anonyme Nutzungsberichte an die BunkerWeb-Maintainer.        |
    | `EXTERNAL_PLUGIN_URLS`  |          | global  | nein     | **Externe Plugins:** URLs für externe Plugins zum Herunterladen (durch Leerzeichen getrennt). |

=== "Datei-Caching"

    **Optimierung des Datei-Cache**

    Der Cache für offene Dateien verbessert die Leistung, indem er Dateideskriptoren und Metadaten im Speicher speichert und so die Notwendigkeit wiederholter Dateisystemoperationen reduziert.

    !!! success "Vorteile des Datei-Caching"
        - **Leistung:** Reduziert Dateisystem-I/O, verringert die Latenz und senkt die CPU-Auslastung für Dateioperationen.
        - **Sicherheit:** Mildert Timing-Angriffe durch Caching von Fehlerantworten und reduziert die Auswirkungen von DoS-Angriffen auf das Dateisystem.

    | Einstellung                | Standard                | Kontext   | Mehrfach | Beschreibung                                                                                                                |
    | -------------------------- | ----------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------- |
    | `USE_OPEN_FILE_CACHE`      | `no`                    | multisite | nein     | **Cache aktivieren:** Aktivieren Sie das Caching von Dateideskriptoren und Metadaten, um die Leistung zu verbessern.        |
    | `OPEN_FILE_CACHE`          | `max=1000 inactive=20s` | multisite | nein     | **Cache-Konfiguration:** Konfigurieren Sie den Cache für offene Dateien (z. B. maximale Einträge und Inaktivitäts-Timeout). |
    | `OPEN_FILE_CACHE_ERRORS`   | `yes`                   | multisite | nein     | **Fehler zwischenspeichern:** Speichert Fehler bei der Suche nach Dateideskriptoren sowie erfolgreiche Suchen zwischen.     |
    | `OPEN_FILE_CACHE_MIN_USES` | `2`                     | multisite | nein     | **Mindestverwendungen:** Mindestanzahl von Zugriffen während des inaktiven Zeitraums, damit eine Datei im Cache verbleibt.  |
    | `OPEN_FILE_CACHE_VALID`    | `30s`                   | multisite | nein     | **Cache-Gültigkeit:** Zeit, nach der zwischengespeicherte Elemente erneut validiert werden.                                 |

    **Konfigurationsanleitung**

    So aktivieren und konfigurieren Sie das Datei-Caching:
    1. Setzen Sie `USE_OPEN_FILE_CACHE` auf `yes`, um die Funktion zu aktivieren.
    2. Passen Sie die `OPEN_FILE_CACHE`-Parameter an, um die maximale Anzahl von Cache-Einträgen und deren Inaktivitäts-Timeout festzulegen.
    3. Verwenden Sie `OPEN_FILE_CACHE_ERRORS`, um sowohl erfolgreiche als auch fehlgeschlagene Suchen zwischenzuspeichern und so wiederholte Dateisystemoperationen zu reduzieren.
    4. Legen Sie mit `OPEN_FILE_CACHE_MIN_USES` die Mindestanzahl von Zugriffen fest, die erforderlich ist, damit eine Datei im Cache verbleibt.
    5. Definieren Sie die Gültigkeitsdauer des Caches mit `OPEN_FILE_CACHE_VALID`, um zu steuern, wie oft zwischengespeicherte Elemente erneut validiert werden.

    !!! tip "Bewährte Praktiken"
        - Aktivieren Sie das Datei-Caching für Websites mit vielen statischen Dateien, um die Leistung zu verbessern.
        - Überprüfen und optimieren Sie die Cache-Einstellungen regelmäßig, um Leistung und Ressourcenverbrauch auszugleichen.
        - In dynamischen Umgebungen, in denen sich Dateien häufig ändern, sollten Sie die Gültigkeitsdauer des Caches verkürzen oder die Funktion deaktivieren, um die Aktualität der Inhalte zu gewährleisten.

### Beispielkonfigurationen

=== "Sicherheit des Standardservers"

    Beispielkonfiguration zum Deaktivieren des Standardservers und Erzwingen von striktem SNI:

    ```yaml
    DISABLE_DEFAULT_SERVER: "yes"
    DISABLE_DEFAULT_SERVER_STRICT_SNI: "yes"
    ```

=== "HTTP-Status bei Ablehnung"

    Beispielkonfiguration zum stillschweigenden Verwerfen unerwünschter Anfragen:

    ```yaml
    DENY_HTTP_STATUS: "444"
    ```

=== "HTTP-Methoden"

    Beispielkonfiguration zur Beschränkung der HTTP-Methoden auf die für eine RESTful-API erforderlichen:

    ```yaml
    ALLOWED_METHODS: "GET|POST|PUT|DELETE"
    ```

=== "Größenbeschränkungen für Anfragen"

    Beispielkonfiguration zur Begrenzung der maximalen Größe des Anforderungskörpers:

    ```yaml
    MAX_CLIENT_SIZE: "5m"
    ```

=== "Protokollunterstützung"

    Beispielkonfiguration zur Aktivierung von HTTP/2 und HTTP/3 mit einem benutzerdefinierten Alt-Svc-Port:

    ```yaml
    HTTP2: "yes"
    HTTP3: "yes"
    HTTP3_ALT_SVC_PORT: "443"
    ```

=== "Bereitstellung statischer Dateien"

    Beispielkonfiguration zur Bereitstellung statischer Dateien aus einem benutzerdefinierten Stammordner:

    ```yaml
    SERVE_FILES: "yes"
    ROOT_FOLDER: "/var/www/custom-folder"
    ```

=== "Datei-Caching"

    Beispielkonfiguration zur Aktivierung und Optimierung des Datei-Caching:

    ```yaml
    USE_OPEN_FILE_CACHE: "yes"
    OPEN_FILE_CACHE: "max=2000 inactive=30s"
    OPEN_FILE_CACHE_ERRORS: "yes"
    OPEN_FILE_CACHE_MIN_USES: "3"
    OPEN_FILE_CACHE_VALID: "60s"
    ```

## ModSecurity

STREAM-Unterstützung :x:

Das ModSecurity-Plugin integriert die leistungsstarke [ModSecurity](https://modsecurity.org) Web Application Firewall (WAF) in BunkerWeb. Diese Integration bietet robusten Schutz gegen eine Vielzahl von Webangriffen, indem sie das [OWASP Core Rule Set (CRS)](https://coreruleset.org) nutzt, um Bedrohungen wie SQL-Injection, Cross-Site-Scripting (XSS), Local File Inclusion und mehr zu erkennen und zu blockieren.

**So funktioniert es:**

1.  Wenn eine Anfrage empfangen wird, bewertet ModSecurity sie anhand des aktiven Regelsatzes.
2.  Das OWASP Core Rule Set überprüft Header, Cookies, URL-Parameter und den Body-Inhalt.
3.  Jeder erkannte Verstoß trägt zu einem Gesamt-Anomalie-Score bei.
4.  Wenn dieser Score den konfigurierten Schwellenwert überschreitet, wird die Anfrage blockiert.
5.  Detaillierte Protokolle werden erstellt, um zu diagnostizieren, welche Regeln ausgelöst wurden und warum.

!!! success "Wichtige Vorteile"

      1. **Branchenstandard-Schutz:** Verwendet die weit verbreitete Open-Source-Firewall ModSecurity.
      2. **OWASP Core Rule Set:** Verwendet von der Community gepflegte Regeln, die die OWASP Top Ten und mehr abdecken.
      3. **Konfigurierbare Sicherheitsstufen:** Passen Sie die Paranoia-Stufen an, um die Sicherheit mit potenziellen Falsch-Positiven auszugleichen.
      4. **Detaillierte Protokollierung:** Bietet gründliche Audit-Protokolle zur Analyse von Angriffen.
      5. **Plugin-Unterstützung:** Erweitern Sie den Schutz mit optionalen CRS-Plugins, die auf Ihre Anwendungen zugeschnitten sind.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um ModSecurity zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** ModSecurity ist standardmäßig aktiviert. Dies kann mit der Einstellung `USE_MODSECURITY` gesteuert werden.
2.  **Wählen Sie eine CRS-Version:** Wählen Sie eine Version des OWASP Core Rule Set (v3, v4 oder nightly).
3.  **Plugins hinzufügen:** Aktivieren Sie optional CRS-Plugins, um die Regelabdeckung zu verbessern.
4.  **Überwachen und anpassen:** Verwenden Sie Protokolle und die [Web-Benutzeroberfläche](web-ui.md), um Falsch-Positive zu identifizieren und die Einstellungen anzupassen.

### Konfigurationseinstellungen

| Einstellung                           | Standard       | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                    |
| ------------------------------------- | -------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MODSECURITY`                     | `yes`          | multisite | nein     | **ModSecurity aktivieren:** Schalten Sie den Schutz der ModSecurity Web Application Firewall ein.                                                                               |
| `USE_MODSECURITY_CRS`                 | `yes`          | multisite | nein     | **Core Rule Set verwenden:** Aktivieren Sie das OWASP Core Rule Set für ModSecurity.                                                                                            |
| `MODSECURITY_CRS_VERSION`             | `4`            | multisite | nein     | **CRS-Version:** Die Version des zu verwendenden OWASP Core Rule Set. Optionen: `3`, `4` oder `nightly`.                                                                        |
| `MODSECURITY_SEC_RULE_ENGINE`         | `On`           | multisite | nein     | **Regel-Engine:** Steuern Sie, ob Regeln erzwungen werden. Optionen: `On`, `DetectionOnly` oder `Off`.                                                                          |
| `MODSECURITY_SEC_AUDIT_ENGINE`        | `RelevantOnly` | multisite | nein     | **Audit-Engine:** Steuern Sie, wie die Audit-Protokollierung funktioniert. Optionen: `On`, `Off` oder `RelevantOnly`.                                                           |
| `MODSECURITY_SEC_AUDIT_LOG_PARTS`     | `ABIJDEFHZ`    | multisite | nein     | **Audit-Protokoll-Teile:** Welche Teile von Anfragen/Antworten in Audit-Protokolle aufgenommen werden sollen.                                                                   |
| `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` | `131072`       | multisite | nein     | **Anforderungskörper-Limit (keine Dateien):** Maximale Größe für Anforderungskörper ohne Datei-Uploads. Akzeptiert einfache Bytes oder menschenlesbare Suffixe (`k`, `m`, `g`). |
| `USE_MODSECURITY_CRS_PLUGINS`         | `yes`          | multisite | nein     | **CRS-Plugins aktivieren:** Aktivieren Sie zusätzliche Plugin-Regelsätze für das Core Rule Set.                                                                                 |
| `MODSECURITY_CRS_PLUGINS`             |                | multisite | nein     | **CRS-Plugin-Liste:** Leerzeichengetrennte Liste von Plugins zum Herunterladen und Installieren (`plugin-name[/tag]` oder URL).                                                 |
| `USE_MODSECURITY_GLOBAL_CRS`          | `no`           | global    | nein     | **Globales CRS:** Wenn aktiviert, werden CRS-Regeln global auf HTTP-Ebene anstatt pro Server angewendet.                                                                        |

!!! warning "ModSecurity und das OWASP Core Rule Set"
    **Wir empfehlen dringend, sowohl ModSecurity als auch das OWASP Core Rule Set (CRS) aktiviert zu lassen**, um einen robusten Schutz gegen gängige Web-Schwachstellen zu bieten. Obwohl gelegentlich Falsch-Positive auftreten können, können diese mit etwas Aufwand durch Feinabstimmung von Regeln oder die Verwendung vordefinierter Ausschlüsse behoben werden.

    Das CRS-Team pflegt aktiv eine Liste von Ausschlüssen für beliebte Anwendungen wie WordPress, Nextcloud, Drupal und Cpanel, was die Integration erleichtert, ohne die Funktionalität zu beeinträchtigen. Die Sicherheitsvorteile überwiegen bei weitem den minimalen Konfigurationsaufwand, der zur Behebung von Falsch-Positiven erforderlich ist.

### Verfügbare CRS-Versionen

Wählen Sie eine CRS-Version, die Ihren Sicherheitsanforderungen am besten entspricht:

- **`3`**: Stabile [v3.3.8](https://github.com/coreruleset/coreruleset/releases/tag/v3.3.8).
- **`4`**: Stabile [v4.23.0](https://github.com/coreruleset/coreruleset/releases/tag/v4.23.0) (**Standard**).
- **`nightly`**: [Nightly-Build](https://github.com/coreruleset/coreruleset/releases/tag/nightly) mit den neuesten Regel-Updates.

!!! example "Nightly-Build"
    Der **Nightly-Build** enthält die aktuellsten Regeln und bietet den neuesten Schutz gegen aufkommende Bedrohungen. Da er jedoch täglich aktualisiert wird und experimentelle oder ungetestete Änderungen enthalten kann, wird empfohlen, den Nightly-Build zunächst in einer **Staging-Umgebung** zu verwenden, bevor er in der Produktion eingesetzt wird.

!!! tip "Paranoia-Stufen"
    Das OWASP Core Rule Set verwendet "Paranoia-Stufen" (PL), um die Strenge der Regeln zu steuern:

    - **PL1 (Standard):** Grundlegender Schutz mit minimalen Falsch-Positiven
    - **PL2:** Strengere Sicherheit mit strengerem Musterabgleich
    - **PL3:** Erhöhte Sicherheit mit strengerer Validierung
    - **PL4:** Maximale Sicherheit mit sehr strengen Regeln (kann viele Falsch-Positive verursachen)

    Sie können die Paranoia-Stufe festlegen, indem Sie eine benutzerdefinierte Konfigurationsdatei in `/etc/bunkerweb/configs/modsec-crs/` hinzufügen.

### Benutzerdefinierte Konfigurationen {#custom-configurations}

Die Feinabstimmung von ModSecurity und dem OWASP Core Rule Set (CRS) kann durch benutzerdefinierte Konfigurationen erreicht werden. Diese Konfigurationen ermöglichen es Ihnen, das Verhalten in bestimmten Phasen der Verarbeitung von Sicherheitsregeln anzupassen:

- **`modsec-crs`**: Wird **vor** dem Laden des OWASP Core Rule Set angewendet.
- **`modsec`**: Wird **nach** dem Laden des OWASP Core Rule Set angewendet. Dies wird auch verwendet, wenn das CRS überhaupt nicht geladen wird.
- **`crs-plugins-before`**: Wird **vor** dem Laden der CRS-Plugins angewendet.
- **`crs-plugins-after`**: Wird **nach** dem Laden der CRS-Plugins angewendet.

Diese Struktur bietet Flexibilität und ermöglicht es Ihnen, die Einstellungen von ModSecurity und CRS an die spezifischen Anforderungen Ihrer Anwendung anzupassen, während ein klarer Konfigurationsfluss beibehalten wird.

#### Hinzufügen von CRS-Ausschlüssen mit `modsec-crs`

Sie können eine benutzerdefinierte Konfiguration vom Typ `modsec-crs` verwenden, um Ausschlüsse für bestimmte Anwendungsfälle hinzuzufügen, z. B. das Aktivieren vordefinierter Ausschlüsse für WordPress:

```conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"
```

In diesem Beispiel:

- Die Aktion wird in **Phase 1** (früh im Anfrage-Lebenszyklus) ausgeführt.
- Sie aktiviert WordPress-spezifische CRS-Ausschlüsse, indem sie die Variable `tx.crs_exclusions_wordpress` setzt.

#### Aktualisieren von CRS-Regeln mit `modsec`

Um die geladenen CRS-Regeln zu optimieren, können Sie eine benutzerdefinierte Konfiguration vom Typ `modsec` verwenden. Sie können beispielsweise bestimmte Regeln oder Tags für bestimmte Anfragepfade entfernen:

```conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"
```

In diesem Beispiel:

- **Regel 1**: Entfernt Regeln mit den Tags `attack-xss` und `attack-rce` für Anfragen an `/wp-admin/admin-ajax.php`.
- **Regel 2**: Entfernt Regeln mit dem Tag `attack-xss` für Anfragen an `/wp-admin/options.php`.
- **Regel 3**: Entfernt eine bestimmte Regel (ID `930120`) für Anfragen, die auf `/wp-json/yoast` passen.

!!! info "Reihenfolge der Ausführung"
    Die Ausführungsreihenfolge für ModSecurity in BunkerWeb ist wie folgt, um eine klare und logische Abfolge der Regelanwendung zu gewährleisten:

    1.  **OWASP CRS-Konfiguration**: Basiskonfiguration für das OWASP Core Rule Set.
    2.  **Konfiguration benutzerdefinierter Plugins (`crs-plugins-before`)**: Einstellungen, die für Plugins spezifisch sind und vor allen CRS-Regeln angewendet werden.
    3.  **Regeln benutzerdefinierter Plugins (vor CRS-Regeln) (`crs-plugins-before`)**: Benutzerdefinierte Regeln für Plugins, die vor den CRS-Regeln ausgeführt werden.
    4.  **Konfiguration heruntergeladener Plugins**: Konfiguration für extern heruntergeladene Plugins.
    5.  **Regeln heruntergeladener Plugins (vor CRS-Regeln)**: Regeln für heruntergeladene Plugins, die vor den CRS-Regeln ausgeführt werden.
    6.  **Benutzerdefinierte CRS-Regeln (`modsec-crs`)**: Benutzerdefinierte Regeln, die vor dem Laden der CRS-Regeln angewendet werden.
    7.  **OWASP CRS-Regeln**: Der Kernsatz von Sicherheitsregeln, der von OWASP bereitgestellt wird.
    8.  **Regeln benutzerdefinierter Plugins (nach CRS-Regeln) (`crs-plugins-after`)**: Benutzerdefinierte Plugin-Regeln, die nach den CRS-Regeln ausgeführt werden.
    9.  **Regeln heruntergeladener Plugins (nach CRS-Regeln)**: Regeln für heruntergeladene Plugins, die nach den CRS-Regeln ausgeführt werden.
    10. **Benutzerdefinierte Regeln (`modsec`)**: Benutzerdefinierte Regeln, die nach allen CRS- und Plugin-Regeln angewendet werden.

    **Wichtige Hinweise**:

    -   **Pre-CRS-Anpassungen** (`crs-plugins-before`, `modsec-crs`) ermöglichen es Ihnen, Ausnahmen oder vorbereitende Regeln zu definieren, bevor die Kern-CRS-Regeln geladen werden.
    -   **Post-CRS-Anpassungen** (`crs-plugins-after`, `modsec`) sind ideal, um Regeln zu überschreiben oder zu erweitern, nachdem CRS- und Plugin-Regeln angewendet wurden.
    -   Diese Struktur bietet maximale Flexibilität und ermöglicht eine präzise Steuerung der Regelausführung und -anpassung bei gleichzeitiger Aufrechterhaltung einer starken Sicherheitsgrundlage.

### OWASP CRS-Plugins

Das OWASP Core Rule Set unterstützt auch eine Reihe von **Plugins**, die entwickelt wurden, um seine Funktionalität zu erweitern und die Kompatibilität mit bestimmten Anwendungen oder Umgebungen zu verbessern. Diese Plugins können dabei helfen, das CRS für die Verwendung mit beliebten Plattformen wie WordPress, Nextcloud und Drupal oder sogar benutzerdefinierten Setups zu optimieren. Weitere Informationen und eine Liste der verfügbaren Plugins finden Sie im [OWASP CRS Plugin-Verzeichnis](https://github.com/coreruleset/plugin-registry).

!!! tip "Plugin-Download"
    Die Einstellung `MODSECURITY_CRS_PLUGINS` ermöglicht es Ihnen, Plugins herunterzuladen und zu installieren, um die Funktionalität des OWASP Core Rule Set (CRS) zu erweitern. Diese Einstellung akzeptiert eine Liste von Plugin-Namen mit optionalen Tags oder URLs, was es einfach macht, zusätzliche Sicherheitsfunktionen zu integrieren, die auf Ihre spezifischen Bedürfnisse zugeschnitten sind.

    Hier ist eine nicht erschöpfende Liste der akzeptierten Werte für die Einstellung `MODSECURITY_CRS_PLUGINS`:

    *   `fake-bot` - Lädt die neueste Version des Plugins herunter.
    *   `wordpress-rule-exclusions/v1.0.0` - Lädt die Version 1.0.0 des Plugins herunter.
    *   `https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip` - Lädt das Plugin direkt von der URL herunter.

!!! warning "Falsch-Positive"
    Höhere Sicherheitseinstellungen können legitimen Verkehr blockieren. Beginnen Sie mit den Standardeinstellungen und überwachen Sie die Protokolle, bevor Sie die Sicherheitsstufen erhöhen. Seien Sie bereit, Ausnahmeregeln für die spezifischen Anforderungen Ihrer Anwendung hinzuzufügen.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine Standardkonfiguration mit aktiviertem ModSecurity und CRS v4:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "Nur-Erkennungsmodus"

    Konfiguration zur Überwachung potenzieller Bedrohungen ohne Blockierung:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "DetectionOnly"
    MODSECURITY_SEC_AUDIT_ENGINE: "On"
    MODSECURITY_SEC_AUDIT_LOG_PARTS: "ABIJDEFHZ"
    ```

=== "Erweiterte Konfiguration mit Plugins"

    Konfiguration mit CRS v4 und aktivierten Plugins für zusätzlichen Schutz:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions fake-bot"
    MODSECURITY_REQ_BODY_NO_FILES_LIMIT: "262144"
    ```

=== "Legacy-Konfiguration"

    Konfiguration mit CRS v3 zur Kompatibilität mit älteren Setups:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "3"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "Globales ModSecurity"

    Konfiguration, die ModSecurity global auf alle HTTP-Verbindungen anwendet:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    USE_MODSECURITY_GLOBAL_CRS: "yes"
    ```

=== "Nightly-Build mit benutzerdefinierten Plugins"

    Konfiguration mit dem Nightly-Build von CRS mit benutzerdefinierten Plugins:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "nightly"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions/v1.0.0 https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip"
    ```

!!! note "Menschenlesbare Größenwerte"
    Für Größeneinstellungen wie `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` werden die Suffixe `k`, `m` und `g` (Groß- und Kleinschreibung wird nicht beachtet) unterstützt und stehen für Kibibyte, Mebibyte und Gibibyte (Vielfache von 1024). Beispiele: `256k` = 262144, `1m` = 1048576, `2g` = 2147483648.

## Monitoring <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM-Unterstützung :x:

BunkerWeb monitoring pro system. This plugin is a prerequisite for some other plugins.

| Einstellung                    | Standardwert | Kontext | Mehrfach | Beschreibung                                                                |
| ------------------------------ | ------------ | ------- | -------- | --------------------------------------------------------------------------- |
| `USE_MONITORING`               | `yes`        | global  | nein     | Enable monitoring of BunkerWeb.                                             |
| `MONITORING_METRICS_DICT_SIZE` | `10M`        | global  | nein     | Size of the dict to store monitoring metrics.                               |
| `MONITORING_IGNORE_URLS`       |              | global  | nein     | List of URLs to ignore when monitoring separated with spaces (e.g. /health) |

## Mutual TLS

STREAM-Unterstützung :white_check_mark:

Das Mutual-TLS-Plugin (mTLS) schützt sensible Anwendungen, indem nur Clients mit Zertifikaten akzeptiert werden, die von Ihren vertrauenswürdigen Zertifizierungsstellen ausgestellt wurden. Mit aktivem Plugin authentifiziert BunkerWeb jede Anfrage bereits an der Perimeter-Grenze und hält interne Tools sowie Partner-Integrationen abgeschirmt.

BunkerWeb bewertet jeden TLS-Handshake anhand des von Ihnen bereitgestellten CA-Bundles und Ihrer Richtlinien. Clients, die diese Vorgaben nicht erfüllen, werden abgeblockt, während konforme Verbindungen ihre Zertifikatsdetails an nachgelagerte Anwendungen weitergeben können.

**Funktionsweise:**

1. Das Plugin überwacht die HTTPS-Handshakes der ausgewählten Site.
2. Während des TLS-Austauschs prüft BunkerWeb das Client-Zertifikat und vergleicht die Kette mit Ihrem Vertrauensspeicher.
3. Der gewählte Verifizierungsmodus entscheidet, ob nicht authentifizierte Clients abgewiesen, toleriert oder zu Diagnosezwecken zugelassen werden.
4. (Optional) BunkerWeb stellt die Ergebnisse über `X-SSL-Client-*`-Header bereit, damit Ihre Anwendungen eigene Autorisierungsregeln anwenden können.

!!! success "Wesentliche Vorteile"

      1. **Starker Perimeterschutz:** Nur authentifizierte Maschinen und Benutzer erreichen Ihre sensiblen Routen.
      2. **Flexible Vertrauensrichtlinien:** Kombinieren Sie strikte und optionale Modi passend zu Ihrem Onboarding.
      3. **Transparenz für Anwendungen:** Geben Sie Fingerabdrücke und Identitäten an Downstream-Services weiter.
      4. **Geschichtete Sicherheit:** Ergänzen Sie mTLS mit weiteren BunkerWeb-Plugins wie Rate Limiting oder IP-Filterung.

### Schritt-für-Schritt

Gehen Sie diese Schritte durch, um Mutual TLS kontrolliert einzuführen:

1. **Funktion aktivieren:** Setzen Sie `USE_MTLS` auf `yes` für die Site, die Zertifikatsauthentifizierung benötigt.
2. **CA-Bundle bereitstellen:** Legen Sie Ihre vertrauenswürdigen Aussteller in einer PEM-Datei ab und verweisen Sie mit `MTLS_CA_CERTIFICATE` auf den absoluten Pfad.
3. **Verifizierungsmodus wählen:** Nutzen Sie `on` für verpflichtende Zertifikate, `optional` für fallback-fähige Szenarien oder `optional_no_ca` kurzfristig zur Diagnose.
4. **Kettentiefe anpassen:** Erhöhen oder verringern Sie `MTLS_VERIFY_DEPTH`, falls Ihre PKI mehrere Zwischenstellen nutzt.
5. **Ergebnisse weiterreichen (optional):** Belassen Sie `MTLS_FORWARD_CLIENT_HEADERS` auf `yes`, wenn nachgelagerte Anwendungen Zertifikatsinformationen benötigen.
6. **Revokationslisten pflegen:** Verknüpfen Sie `MTLS_CRL`, sobald Sie eine CRL publizieren, damit BunkerWeb widerrufene Zertifikate ablehnt.

### Konfigurationseinstellungen

| Einstellung                   | Standardwert | Kontext   | Mehrfach | Beschreibung                                                                                                                                                            |
| ----------------------------- | ------------ | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                    | `no`         | multisite | nein     | **Mutual TLS verwenden:** Aktiviert die Client-Zertifikatsauthentifizierung für die aktuelle Site.                                                                      |
| `MTLS_CA_CERTIFICATE`         |              | multisite | nein     | **Client-CA-Bundle:** Absoluter Pfad zum vertrauenswürdigen Client-CA-Bundle (PEM). Erforderlich, wenn `MTLS_VERIFY_CLIENT` `on` oder `optional` ist; muss lesbar sein. |
| `MTLS_VERIFY_CLIENT`          | `on`         | multisite | nein     | **Verifizierungsmodus:** Legen Sie fest, ob Zertifikate erforderlich sind (`on`), optional (`optional`) oder ohne CA-Prüfung akzeptiert werden (`optional_no_ca`).      |
| `MTLS_VERIFY_DEPTH`           | `2`          | multisite | nein     | **Verifizierungstiefe:** Maximale akzeptierte Zertifikatskettentiefe für Client-Zertifikate.                                                                            |
| `MTLS_FORWARD_CLIENT_HEADERS` | `yes`        | multisite | nein     | **Client-Header weiterleiten:** Gibt Verifizierungsergebnisse (`X-SSL-Client-*`-Header mit Status, DN, Aussteller, Seriennummer, Fingerabdruck, Gültigkeit) weiter.     |
| `MTLS_CRL`                    |              | multisite | nein     | **Client-CRL-Pfad:** Optionaler Pfad zu einer PEM-codierten Sperrliste. Wird nur angewendet, wenn das CA-Bundle erfolgreich geladen wurde.                              |

!!! tip "Zertifikate aktuell halten"
    Speichern Sie CA-Bundles und Sperrlisten in einem eingehängten Volume, das der Scheduler lesen kann, damit Neustarts die neuesten Vertrauensanker übernehmen.

!!! warning "CA-Bundle für strenge Modi obligatorisch"
    Sobald `MTLS_VERIFY_CLIENT` auf `on` oder `optional` steht, muss die CA-Datei zur Laufzeit vorhanden sein. Fehlt sie, ignoriert BunkerWeb die mTLS-Direktiven, um keinen Dienst mit ungültigem Pfad zu starten. Verwenden Sie `optional_no_ca` nur zur Fehlersuche – dieser Modus schwächt die Client-Authentifizierung.

!!! info "Vertrauensquelle und Verifizierung"
    BunkerWeb nutzt dasselbe CA-Bundle sowohl für die Client-Prüfung als auch für den Aufbau der Vertrauenskette, damit OCSP/CRL-Checks konsistent bleiben.

### Konfigurationsbeispiele

=== "Strikte Zugriffskontrolle"

    Verlangen Sie gültige Client-Zertifikate Ihrer privaten CA und leiten Sie die Verifizierungsergebnisse an das Backend weiter:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Optionale Client-Authentifizierung"

    Erlauben Sie anonyme Nutzer, übermitteln Sie aber Zertifikatsdetails, sobald ein Client eines präsentiert:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Diagnose ohne CA"

    Lassen Sie Verbindungen auch dann zu, wenn ein Zertifikat nicht zu einem vertrauenswürdigen CA-Bundle verknüpft werden kann. Nur für Fehlersuche geeignet:

    ```yaml
    USE_MTLS: "yes"
    MTLS_VERIFY_CLIENT: "optional_no_ca"
    MTLS_FORWARD_CLIENT_HEADERS: "no"
    ```

## OpenAPI Validator <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM-Unterstützung :x:

Validates incoming HTTP requests against an OpenAPI / Swagger specification.

| Einstellung                  | Standardwert                        | Kontext   | Mehrfach | Beschreibung                                                                                    |
| ---------------------------- | ----------------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------- |
| `USE_OPENAPI_VALIDATOR`      | `no`                                | multisite | nein     | Enable OpenAPI route validation for this site.                                                  |
| `OPENAPI_SPEC`               |                                     | multisite | nein     | Absolute path or HTTP(S) URL to the OpenAPI (swagger) document in JSON/YAML format.             |
| `OPENAPI_BASE_PATH`          |                                     | multisite | nein     | Optional base path prefix to prepend to every path in the spec (overrides servers[*].url path). |
| `OPENAPI_ALLOW_UNSPECIFIED`  | `no`                                | multisite | nein     | Allow requests to paths not listed in the specification (otherwise they are denied).            |
| `OPENAPI_ALLOW_INSECURE_URL` | `no`                                | multisite | nein     | Allow fetching the OpenAPI spec over plain HTTP (not recommended).                              |
| `OPENAPI_IGNORE_URLS`        | `^/docs$ ^/redoc$ ^/openapi\.json$` | multisite | nein     | List of URL regexes to bypass OpenAPI validation (space separated).                             |
| `OPENAPI_MAX_SPEC_SIZE`      | `2M`                                | global    | nein     | Maximum allowed size of the OpenAPI document (accepts suffix k/M/G).                            |
| `OPENAPI_VALIDATE_PARAMS`    | `yes`                               | multisite | nein     | Validate query, header, cookie, and path parameters against the OpenAPI specification.          |

## OpenID Connect <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM-Unterstützung :x:

OpenID Connect authentication plugin providing SSO capabilities with identity providers.

| Einstellung                               | Standardwert           | Kontext   | Mehrfach | Beschreibung                                                                                                                                            |
| ----------------------------------------- | ---------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_OPENIDC`                             | `no`                   | multisite | nein     | Enable or disable OpenID Connect authentication.                                                                                                        |
| `OPENIDC_DISCOVERY`                       |                        | multisite | nein     | OpenID Connect discovery URL (e.g. https://idp.example.com/.well-known/openid-configuration).                                                           |
| `OPENIDC_CLIENT_ID`                       |                        | multisite | nein     | OAuth 2.0 client identifier registered with the IdP.                                                                                                    |
| `OPENIDC_CLIENT_SECRET`                   |                        | multisite | nein     | OAuth 2.0 client secret registered with the IdP.                                                                                                        |
| `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD`      | `basic`                | multisite | nein     | Token endpoint auth method: basic (recommended, HTTP Basic), post (POST body), secret_jwt (JWT with client secret), private_key_jwt (JWT with RSA key). |
| `OPENIDC_CLIENT_RSA_PRIVATE_KEY`          |                        | multisite | nein     | PEM-encoded RSA private key for private_key_jwt authentication.                                                                                         |
| `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID`       |                        | multisite | nein     | Optional key ID (kid) for private_key_jwt authentication.                                                                                               |
| `OPENIDC_CLIENT_JWT_ASSERTION_EXPIRES_IN` |                        | multisite | nein     | JWT assertion lifetime in seconds (empty to use library default).                                                                                       |
| `OPENIDC_REDIRECT_URI`                    | `/callback`            | multisite | nein     | URI path where the IdP redirects after authentication.                                                                                                  |
| `OPENIDC_SCOPE`                           | `openid email profile` | multisite | nein     | Space-separated list of OAuth 2.0 scopes to request.                                                                                                    |
| `OPENIDC_AUTHORIZATION_PARAMS`            |                        | multisite | nein     | Additional authorization params as comma-separated key=value pairs (e.g. audience=api,resource=xyz). URL-encode values if needed.                       |
| `OPENIDC_USE_NONCE`                       | `yes`                  | multisite | nein     | Use nonce in authentication requests to prevent replay attacks.                                                                                         |
| `OPENIDC_USE_PKCE`                        | `no`                   | multisite | nein     | Use PKCE (Proof Key for Code Exchange) for authorization code flow.                                                                                     |
| `OPENIDC_FORCE_REAUTHORIZE`               | `no`                   | multisite | nein     | Force re-authorization on every request (not recommended for production).                                                                               |
| `OPENIDC_REFRESH_SESSION_INTERVAL`        |                        | multisite | nein     | Interval in seconds to silently re-authenticate (empty to disable).                                                                                     |
| `OPENIDC_IAT_SLACK`                       | `120`                  | multisite | nein     | Allowed clock skew in seconds for token validation.                                                                                                     |
| `OPENIDC_ACCESS_TOKEN_EXPIRES_IN`         | `3600`                 | multisite | nein     | Default access token lifetime (seconds) if not provided by IdP.                                                                                         |
| `OPENIDC_RENEW_ACCESS_TOKEN_ON_EXPIRY`    | `yes`                  | multisite | nein     | Automatically renew access token using refresh token when expired.                                                                                      |
| `OPENIDC_ACCEPT_UNSUPPORTED_ALG`          | `no`                   | multisite | nein     | Accept tokens signed with unsupported algorithms (not recommended).                                                                                     |
| `OPENIDC_LOGOUT_PATH`                     | `/logout`              | multisite | nein     | URI path for logout requests.                                                                                                                           |
| `OPENIDC_REVOKE_TOKENS_ON_LOGOUT`         | `no`                   | multisite | nein     | Revoke tokens at the IdP when logging out.                                                                                                              |
| `OPENIDC_REDIRECT_AFTER_LOGOUT_URI`       |                        | multisite | nein     | URI to redirect after logout (leave empty for IdP default).                                                                                             |
| `OPENIDC_POST_LOGOUT_REDIRECT_URI`        |                        | multisite | nein     | URI to redirect after IdP logout is complete.                                                                                                           |
| `OPENIDC_TIMEOUT_CONNECT`                 | `10000`                | multisite | nein     | Connection timeout in milliseconds for IdP requests.                                                                                                    |
| `OPENIDC_TIMEOUT_SEND`                    | `10000`                | multisite | nein     | Send timeout in milliseconds for IdP requests.                                                                                                          |
| `OPENIDC_TIMEOUT_READ`                    | `10000`                | multisite | nein     | Read timeout in milliseconds for IdP requests.                                                                                                          |
| `OPENIDC_SSL_VERIFY`                      | `yes`                  | multisite | nein     | Verify SSL certificates when communicating with the IdP.                                                                                                |
| `OPENIDC_KEEPALIVE`                       | `yes`                  | multisite | nein     | Enable HTTP keepalive for connections to the IdP.                                                                                                       |
| `OPENIDC_HTTP_PROXY`                      |                        | multisite | nein     | HTTP proxy URL for IdP connections (e.g. http://proxy:8080).                                                                                            |
| `OPENIDC_HTTPS_PROXY`                     |                        | multisite | nein     | HTTPS proxy URL for IdP connections (e.g. http://proxy:8080).                                                                                           |
| `OPENIDC_USER_HEADER`                     | `X-User`               | multisite | nein     | Header to pass user info to upstream (empty to disable).                                                                                                |
| `OPENIDC_USER_HEADER_CLAIM`               | `sub`                  | multisite | nein     | ID token claim to use for the user header (e.g. sub, email, preferred_username).                                                                        |
| `OPENIDC_DISPLAY_CLAIM`                   | `preferred_username`   | multisite | nein     | Claim to use for display in logs and metrics (e.g. preferred_username, name, email). Falls back to User Header Claim if not found.                      |
| `OPENIDC_DISCOVERY_DICT_SIZE`             | `1m`                   | global    | nein     | Size of the shared dictionary to cache discovery data.                                                                                                  |
| `OPENIDC_JWKS_DICT_SIZE`                  | `1m`                   | global    | nein     | Size of the shared dictionary to cache JWKS data.                                                                                                       |

## PHP

STREAM-Unterstützung :x:

Das PHP-Plugin bietet eine nahtlose Integration mit PHP-FPM für BunkerWeb und ermöglicht die dynamische PHP-Verarbeitung für Ihre Websites. Diese Funktion unterstützt sowohl lokale PHP-FPM-Instanzen, die auf derselben Maschine laufen, als auch entfernte PHP-FPM-Server, was Ihnen Flexibilität bei der Konfiguration Ihrer PHP-Umgebung gibt.

**So funktioniert es:**

1.  Wenn ein Client eine PHP-Datei von Ihrer Website anfordert, leitet BunkerWeb die Anfrage an die konfigurierte PHP-FPM-Instanz weiter.
2.  Bei lokalem PHP-FPM kommuniziert BunkerWeb mit dem PHP-Interpreter über eine Unix-Socket-Datei.
3.  Bei entferntem PHP-FPM leitet BunkerWeb Anfragen an den angegebenen Host und Port über das FastCGI-Protokoll weiter.
4.  PHP-FPM verarbeitet das Skript und gibt den generierten Inhalt an BunkerWeb zurück, das ihn dann an den Client ausliefert.
5.  Die URL-Umschreibung wird automatisch konfiguriert, um gängige PHP-Frameworks und Anwendungen zu unterstützen, die "schöne URLs" verwenden.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die PHP-Funktion zu konfigurieren und zu verwenden:

1.  **Wählen Sie Ihr PHP-FPM-Setup:** Entscheiden Sie, ob Sie eine lokale oder eine entfernte PHP-FPM-Instanz verwenden möchten.
2.  **Konfigurieren Sie die Verbindung:** Geben Sie für lokales PHP den Socket-Pfad an; für entferntes PHP geben Sie den Hostnamen und den Port an.
3.  **Legen Sie das Dokumentenstammverzeichnis fest:** Konfigurieren Sie den Stammordner, der Ihre PHP-Dateien enthält, mit der entsprechenden Pfadeinstellung.
4.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration leitet BunkerWeb PHP-Anfragen automatisch an Ihre PHP-FPM-Instanz weiter.

### Konfigurationseinstellungen

| Einstellung       | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                        |
| ----------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
| `REMOTE_PHP`      |          | multisite | nein     | **Entfernter PHP-Host:** Hostname der entfernten PHP-FPM-Instanz. Leer lassen, um lokales PHP zu verwenden.         |
| `REMOTE_PHP_PATH` |          | multisite | nein     | **Entfernter Pfad:** Stammordner mit Dateien in der entfernten PHP-FPM-Instanz.                                     |
| `REMOTE_PHP_PORT` | `9000`   | multisite | nein     | **Entfernter Port:** Port der entfernten PHP-FPM-Instanz.                                                           |
| `LOCAL_PHP`       |          | multisite | nein     | **Lokaler PHP-Socket:** Pfad zur PHP-FPM-Socket-Datei. Leer lassen, um eine entfernte PHP-FPM-Instanz zu verwenden. |
| `LOCAL_PHP_PATH`  |          | multisite | nein     | **Lokaler Pfad:** Stammordner mit Dateien in der lokalen PHP-FPM-Instanz.                                           |

!!! tip "Lokales vs. entferntes PHP-FPM"
    Wählen Sie das Setup, das am besten zu Ihrer Infrastruktur passt:

    - **Lokales PHP-FPM** bietet aufgrund der Socket-basierten Kommunikation eine bessere Leistung und ist ideal, wenn PHP auf derselben Maschine wie BunkerWeb läuft.
    - **Entferntes PHP-FPM** bietet mehr Flexibilität und Skalierbarkeit, indem die PHP-Verarbeitung auf separaten Servern erfolgen kann.

!!! warning "Pfadkonfiguration"
    Der `REMOTE_PHP_PATH` oder `LOCAL_PHP_PATH` muss mit dem tatsächlichen Dateisystempfad übereinstimmen, in dem Ihre PHP-Dateien gespeichert sind; andernfalls tritt ein "Datei nicht gefunden"-Fehler auf.

!!! info "URL-Umschreibung"
    Das PHP-Plugin konfiguriert automatisch die URL-Umschreibung, um moderne PHP-Anwendungen zu unterstützen. Anfragen für nicht existierende Dateien werden an `index.php` weitergeleitet, wobei die ursprüngliche Anfrage-URI als Abfrageparameter verfügbar ist.

### Beispielkonfigurationen

=== "Lokale PHP-FPM-Konfiguration"

    Konfiguration für die Verwendung einer lokalen PHP-FPM-Instanz:

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html"
    ```

=== "Entfernte PHP-FPM-Konfiguration"

    Konfiguration für die Verwendung einer entfernten PHP-FPM-Instanz:

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9000"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "Konfiguration mit benutzerdefiniertem Port"

    Konfiguration für die Verwendung von PHP-FPM auf einem nicht standardmäßigen Port:

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9001"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "WordPress-Konfiguration"

    Für WordPress optimierte Konfiguration:

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html/wordpress"
    ```

## Pro

STREAM-Unterstützung :x:

Das Pro-Plugin bündelt erweiterte Funktionen und Verbesserungen für Unternehmensbereitstellungen von BunkerWeb. Es schaltet zusätzliche Funktionen, Premium-Plugins und erweiterte Funktionalität frei, die die Kernplattform von BunkerWeb ergänzen. Es bietet verbesserte Sicherheit, Leistung und Verwaltungsoptionen für unternehmenstaugliche Bereitstellungen.

**So funktioniert es:**

1.  Mit einem gültigen Pro-Lizenzschlüssel verbindet sich BunkerWeb mit dem Pro-API-Server, um Ihr Abonnement zu validieren.
2.  Nach der Authentifizierung lädt das Plugin automatisch Pro-exklusive Plugins und Erweiterungen herunter und installiert sie.
3.  Ihr Pro-Status wird regelmäßig überprüft, um den fortgesetzten Zugriff auf Premium-Funktionen sicherzustellen.
4.  Premium-Plugins werden nahtlos in Ihre bestehende BunkerWeb-Konfiguration integriert.
5.  Alle Pro-Funktionen arbeiten harmonisch mit dem Open-Source-Kern zusammen und erweitern die Funktionalität, anstatt sie zu ersetzen.

!!! success "Wichtige Vorteile"

      1. **Premium-Erweiterungen:** Zugriff auf exklusive Plugins und Funktionen, die in der Community-Edition nicht verfügbar sind.
      2. **Verbesserte Leistung:** Optimierte Konfigurationen und fortschrittliche Caching-Mechanismen.
      3. **Unternehmens-Support:** Vorrangige Unterstützung und dedizierte Support-Kanäle.
      4. **Nahtlose Integration:** Pro-Funktionen arbeiten ohne Konfigurationskonflikte neben den Community-Funktionen.
      5. **Automatische Updates:** Premium-Plugins werden automatisch heruntergeladen und auf dem neuesten Stand gehalten.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Pro-Funktionen zu konfigurieren und zu verwenden:

1.  **Lizenzschlüssel erhalten:** Kaufen Sie eine Pro-Lizenz im [BunkerWeb Panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc).
2.  **Lizenzschlüssel konfigurieren:** Verwenden Sie die Einstellung `PRO_LICENSE_KEY`, um Ihre Lizenz zu konfigurieren.
3.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration mit einer gültigen Lizenz werden Pro-Plugins automatisch heruntergeladen und aktiviert.
4.  **Überwachen Sie Ihren Pro-Status:** Überprüfen Sie die Zustandsindikatoren in der [Web-Benutzeroberfläche](web-ui.md), um Ihren Pro-Abonnementstatus zu bestätigen.

### Konfigurationseinstellungen

| Einstellung       | Standard | Kontext | Mehrfach | Beschreibung                                                                      |
| ----------------- | -------- | ------- | -------- | --------------------------------------------------------------------------------- |
| `PRO_LICENSE_KEY` |          | global  | nein     | **Pro-Lizenzschlüssel:** Ihr BunkerWeb Pro-Lizenzschlüssel zur Authentifizierung. |

!!! tip "Lizenzverwaltung"
    Ihre Pro-Lizenz ist an Ihre spezifische Bereitstellungsumgebung gebunden. Wenn Sie Ihre Lizenz übertragen müssen oder Fragen zu Ihrem Abonnement haben, wenden Sie sich bitte über das [BunkerWeb Panel](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) an den Support.

!!! info "Pro-Funktionen"
    Die spezifischen verfügbaren Pro-Funktionen können sich im Laufe der Zeit weiterentwickeln, wenn neue Funktionen hinzugefügt werden. Das Pro-Plugin übernimmt automatisch die Installation und Konfiguration aller verfügbaren Funktionen.

!!! warning "Netzwerkanforderungen"
    Das Pro-Plugin benötigt ausgehenden Internetzugang, um sich zur Lizenzüberprüfung mit der BunkerWeb-API zu verbinden und Premium-Plugins herunterzuladen. Stellen Sie sicher, dass Ihre Firewall Verbindungen zu `api.bunkerweb.io` auf Port 443 (HTTPS) zulässt.

### Häufig gestellte Fragen

**F: Was passiert, wenn meine Pro-Lizenz abläuft?**

A: Wenn Ihre Pro-Lizenz abläuft, wird der Zugriff auf Premium-Funktionen und -Plugins deaktiviert. Ihre BunkerWeb-Installation wird jedoch weiterhin mit allen Funktionen der Community-Edition betrieben. Um wieder Zugriff auf die Pro-Funktionen zu erhalten, erneuern Sie einfach Ihre Lizenz.

**F: Werden die Pro-Funktionen meine bestehende Konfiguration stören?**

A: Nein, die Pro-Funktionen sind so konzipiert, dass sie sich nahtlos in Ihr aktuelles BunkerWeb-Setup integrieren. Sie erweitern die Funktionalität, ohne Ihre bestehende Konfiguration zu verändern oder zu stören, und gewährleisten so ein reibungsloses und zuverlässiges Erlebnis.

**F: Kann ich die Pro-Funktionen vor dem Kauf ausprobieren?**

A: Auf jeden Fall! BunkerWeb bietet zwei Pro-Pläne, die Ihren Bedürfnissen entsprechen:

- **BunkerWeb PRO Standard:** Voller Zugriff auf die Pro-Funktionen ohne technischen Support.
- **BunkerWeb PRO Enterprise:** Voller Zugriff auf die Pro-Funktionen mit dediziertem technischen Support.

Sie können die Pro-Funktionen mit einer kostenlosen 1-monatigen Testversion erkunden, indem Sie den Promo-Code `freetrial` verwenden. Besuchen Sie das [BunkerWeb Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc), um Ihre Testversion zu aktivieren und mehr über flexible Preisoptionen basierend auf der Anzahl der von BunkerWeb PRO geschützten Dienste zu erfahren.

## Prometheus exporter <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM-Unterstützung :x:

Prometheus exporter for BunkerWeb internal metrics.

| Einstellung                    | Standardwert                                          | Kontext | Mehrfach | Beschreibung                                                             |
| ------------------------------ | ----------------------------------------------------- | ------- | -------- | ------------------------------------------------------------------------ |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | global  | nein     | Enable the Prometheus export.                                            |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | global  | nein     | Listening IP of the Prometheus exporter.                                 |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | global  | nein     | Listening port of the Prometheus exporter.                               |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | global  | nein     | HTTP URL of the Prometheus exporter.                                     |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | global  | nein     | List of IP/networks allowed to contact the Prometheus exporter endpoint. |

## Real IP

STREAM-Unterstützung :warning:

Das Real IP Plugin stellt sicher, dass BunkerWeb die IP-Adresse des Clients auch hinter Proxys korrekt identifiziert. Dies ist unerlässlich für die Anwendung von Sicherheitsregeln, Ratenbegrenzung and zuverlässige Protokolle; andernfalls würden alle Anfragen von der IP des Proxys zu kommen scheinen.

So funktioniert's:

1.  Nach der Aktivierung prüft BunkerWeb die Header (z.B. [`X-Forwarded-For`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Forwarded-For)), die die ursprüngliche IP enthalten.
2.  Es wird überprüft, ob die Quell-IP in `REAL_IP_FROM` (Liste vertrauenswürdiger Proxys) enthalten ist, um nur legitime Proxys zu akzeptieren.
3.  Die Client-IP wird aus dem Header `REAL_IP_HEADER` extrahiert and für die Sicherheitsbewertung and Protokollierung verwendet.
4.  Bei IP-Ketten kann eine rekursive Suche über `REAL_IP_RECURSIVE` die ursprüngliche IP ermitteln.
5.  Die Unterstützung für das [PROXY-Protokoll](https://netnut.io/what-is-proxy-protocol-and-how-does-it-work/) kann aktiviert werden, um die Client-IP direkt von kompatiblen Proxys (z.B. [HAProxy](https://www.haproxy.org/)) zu empfangen.
6.  Listen mit vertrauenswürdigen Proxy-IPs können automatisch über URLs heruntergeladen werden.

### Verwendung

1.  Aktivieren: `USE_REAL_IP: yes`.
2.  Vertrauenswürdige Proxys: Geben Sie IP/Bereiche in `REAL_IP_FROM` ein.
3.  Header: Geben Sie an, welcher Header die echte IP über `REAL_IP_HEADER` enthält.
4.  Rekursiv: Aktivieren Sie `REAL_IP_RECURSIVE` bei Bedarf.
5.  URL-Quellen: Verwenden Sie `REAL_IP_FROM_URLS`, um Listen herunterzuladen.
6.  PROXY-Protokoll: Aktivieren Sie `USE_PROXY_PROTOCOL`, wenn das Upstream-System es unterstützt.

!!! danger "Warnung PROXY-Protokoll"
    Das Aktivieren von `USE_PROXY_PROTOCOL` ohne ein korrekt konfiguriertes Upstream-System, das es aussendet, führt dazu, dass Ihre Anwendung nicht funktioniert. Stellen Sie sicher, dass Sie es vor der Aktivierung konfiguriert haben.

### Parameter

| Parameter            | Standard                                  | Kontext   | Mehrfach | Beschreibung                                                                                 |
| :------------------- | :---------------------------------------- | :-------- | :------- | :------------------------------------------------------------------------------------------- |
| `USE_REAL_IP`        | `no`                                      | multisite | nein     | Aktiviert die Abfrage der echten IP aus Headern oder dem PROXY-Protokoll.                    |
| `REAL_IP_FROM`       | `192.168.0.0/16 172.16.0.0/12 10.0.0.0/8` | multisite | nein     | Vertrauenswürdige Proxys: Liste von IP/Netzwerken, durch Leerzeichen getrennt.               |
| `REAL_IP_HEADER`     | `X-Forwarded-For`                         | multisite | nein     | Header, der die echte IP enthält, oder der spezielle Wert `proxy_protocol`.                  |
| `REAL_IP_RECURSIVE`  | `yes`                                     | multisite | nein     | Rekursive Suche in einem Header, der mehrere IPs enthält.                                    |
| `REAL_IP_FROM_URLS`  |                                           | multisite | nein     | URLs, die IPs/Netzwerke von vertrauenswürdigen Proxys bereitstellen (unterstützt `file://`). |
| `USE_PROXY_PROTOCOL` | `no`                                      | global    | nein     | Aktiviert die PROXY-Protokoll-Unterstützung für die direkte Proxy→BunkerWeb-Kommunikation.   |

!!! tip "Cloud-Anbieter"
    Fügen Sie die IPs Ihrer Load Balancer (AWS/GCP/Azure…) zu `REAL_IP_FROM` hinzu, um eine korrekte Identifizierung zu gewährleisten.

!!! danger "Sicherheitsaspekte"
    Fügen Sie nur vertrauenswürdige Quellen hinzu, da sonst die Gefahr der IP-Spoofing über manipulierte Header besteht.

!!! info "Mehrere Adressen"
    Mit `REAL_IP_RECURSIVE` wird, wenn der Header mehrere IPs enthält, die erste IP, die nicht als vertrauenswürdiger Proxy aufgeführt ist, als Client-IP verwendet.

### Beispiele

=== "Basis (hinter Reverse Proxy)"

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24 10.0.0.5"
    REAL_IP_HEADER: "X-Forwarded-For"
    ```

## Redirect

STREAM-Unterstützung :x:

Das Redirect-Plugin bietet einfache und effiziente HTTP-Umleitungsfunktionen für Ihre von BunkerWeb geschützten Websites. Mit dieser Funktion können Sie Besucher problemlos von einer URL zu einer anderen umleiten und dabei sowohl Umleitungen für die gesamte Domain als auch für bestimmte Pfade mit Beibehaltung des Pfades unterstützen.

**So funktioniert es:**

1.  Wenn ein Besucher auf Ihre Website zugreift, überprüft BunkerWeb, ob eine Umleitung konfiguriert ist.
2.  Wenn aktiviert, leitet BunkerWeb den Besucher an die angegebene Ziel-URL weiter.
3.  Sie können konfigurieren, ob der ursprüngliche Anfragepfad beibehalten (automatisch an die Ziel-URL angehängt) oder direkt zur exakten Ziel-URL umgeleitet werden soll.
4.  Der für die Umleitung verwendete HTTP-Statuscode kann zwischen permanenten (301) und temporären (302) Umleitungen angepasst werden.
5.  Diese Funktionalität ist ideal für Domain-Migrationen, die Einrichtung kanonischer Domains oder die Umleitung veralteter URLs.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Umleitungsfunktion zu konfigurieren und zu verwenden:

1.  **Quellpfad festlegen:** Konfigurieren Sie den Pfad, von dem umgeleitet werden soll, mit der Einstellung `REDIRECT_FROM` (z. B. `/`, `/old-page`).
2.  **Ziel-URL festlegen:** Konfigurieren Sie die Ziel-URL, zu der Besucher umgeleitet werden sollen, mit der Einstellung `REDIRECT_TO`.
3.  **Umleitungstyp wählen:** Entscheiden Sie mit der Einstellung `REDIRECT_TO_REQUEST_URI`, ob der ursprüngliche Anfragepfad beibehalten werden soll.
4.  **Statuscode auswählen:** Legen Sie den entsprechenden HTTP-Statuscode mit der Einstellung `REDIRECT_TO_STATUS_CODE` fest, um eine permanente oder temporäre Umleitung anzuzeigen.
5.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration werden alle Anfragen an die Website automatisch basierend auf Ihren Einstellungen umgeleitet.

### Konfigurationseinstellungen

| Einstellung               | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                |
| ------------------------- | -------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_FROM`           | `/`      | multisite | ja       | **Pfad, von dem umgeleitet wird:** Der Pfad, der umgeleitet wird.                                                           |
| `REDIRECT_TO`             |          | multisite | ja       | **Ziel-URL:** Die Ziel-URL, zu der Besucher umgeleitet werden. Leer lassen, um die Umleitung zu deaktivieren.               |
| `REDIRECT_TO_REQUEST_URI` | `no`     | multisite | ja       | **Pfad beibehalten:** Wenn auf `yes` gesetzt, wird die ursprüngliche Anfrage-URI an die Ziel-URL angehängt.                 |
| `REDIRECT_TO_STATUS_CODE` | `301`    | multisite | ja       | **HTTP-Statuscode:** Der für die Umleitung zu verwendende HTTP-Statuscode. Optionen: `301`, `302`, `303`, `307` oder `308`. |

!!! tip "Wahl des richtigen Statuscodes"
    - **`301` (Moved Permanently):** Permanente Umleitung, wird von Browsern zwischengespeichert. Kann POST zu GET ändern. Ideal für Domain-Migrationen.
    - **`302` (Found):** Temporäre Umleitung. Kann POST zu GET ändern.
    - **`303` (See Other):** Leitet immer mit GET-Methode um. Nützlich nach Formularübermittlungen.
    - **`307` (Temporary Redirect):** Temporäre Umleitung, die die HTTP-Methode beibehält. Ideal für API-Umleitungen.
    - **`308` (Permanent Redirect):** Permanente Umleitung, die die HTTP-Methode beibehält. Für permanente API-Migrationen.

!!! info "Beibehaltung des Pfades"
    Wenn `REDIRECT_TO_REQUEST_URI` auf `yes` gesetzt ist, behält BunkerWeb den ursprünglichen Anfragepfad bei. Wenn ein Benutzer beispielsweise `https://old-domain.com/blog/post-1` besucht und Sie eine Umleitung zu `https://new-domain.com` eingerichtet haben, wird er zu `https://new-domain.com/blog/post-1` umgeleitet.

### Beispielkonfigurationen

=== "Umleitung mehrerer Pfade"

    Eine Konfiguration, die mehrere Pfade an verschiedene Ziele umleitet:

    ```yaml
    # Leitet /blog zu einer neuen Blog-Domain um
    REDIRECT_FROM: "/blog/"
    REDIRECT_TO: "https://blog.example.com/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"

    # Leitet /shop zu einer anderen Domain um
    REDIRECT_FROM_2: "/shop/"
    REDIRECT_TO_2: "https://shop.example.com/"
    REDIRECT_TO_REQUEST_URI_2: "no"
    REDIRECT_TO_STATUS_CODE_2: "301"

    # Leitet den Rest der Website um
    REDIRECT_FROM_3: "/"
    REDIRECT_TO_3: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI_3: "no"
    REDIRECT_TO_STATUS_CODE_3: "301"
    ```

=== "Einfache Domain-Umleitung"

    Eine Konfiguration, die alle Besucher auf eine neue Domain umleitet:

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Pfadbeibehaltende Umleitung"

    Eine Konfiguration, die Besucher auf eine neue Domain umleitet und dabei den angeforderten Pfad beibehält:

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Temporäre Umleitung"

    Eine Konfiguration für eine temporäre Umleitung zu einer Wartungsseite:

    ```yaml
    REDIRECT_TO: "https://maintenance.example.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "302"
    ```

=== "Subdomain-Konsolidierung"

    Eine Konfiguration zur Umleitung einer Subdomain auf einen bestimmten Pfad der Hauptdomain:

    ```yaml
    REDIRECT_TO: "https://example.com/support"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "API-Endpunkt-Migration"

    Eine Konfiguration für die permanente Umleitung eines API-Endpunkts unter Beibehaltung der HTTP-Methode:

    ```yaml
    REDIRECT_FROM: "/api/v1/"
    REDIRECT_TO: "https://api.example.com/v2/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "308"
    ```

=== "Nach Formularübermittlung"

    Eine Konfiguration zur Umleitung nach einer Formularübermittlung mit GET-Methode:

    ```yaml
    REDIRECT_TO: "https://example.com/danke"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "303"
    ```

## Redis

STREAM-Unterstützung :white_check_mark:

Der Redis-Plugin integriert [Redis](https://redis.io/) oder [Valkey](https://valkey.io/) in BunkerWeb zur Zwischenspeicherung and für schnellen Datenzugriff. Dies ist unerlässlich in Hochverfügbarkeitsumgebungen, um Sitzungen, Metriken and andere Informationen zwischen mehreren Knoten zu teilen.

**Funktionsweise:**

1.  Nach der Aktivierung verbindet sich BunkerWeb mit dem konfigurierten Redis-/Valkey-Server.
2.  Kritische Daten (Sitzungen, Metriken, Sicherheit) werden dort gespeichert.
3.  Mehrere Instanzen teilen diese Daten für ein reibungsloses Clustering.
4.  Unterstützt Standalone-Bereitstellungen, passwortbasierte Authentifizierung, SSL/TLS and Redis Sentinel.
5.  Automatische Wiederverbindung and konfigurierbare Timeouts sorgen für Robustheit.

### Verwendung

1.  **Aktivieren:** `USE_REDIS: yes`.
2.  **Verbindung:** Host/IP and Port.
3.  **Sicherheit:** Anmeldeinformationen, falls erforderlich.
4.  **Erweitert:** Datenbank, SSL and Timeouts.
5.  **Hochverfügbarkeit:** Konfigurieren Sie Sentinel, falls verwendet.

### Parameter

| Parameter                 | Standard   | Kontext | Mehrfach | Beschreibung                                                  |
| :------------------------ | :--------- | :------ | :------- | :------------------------------------------------------------ |
| `USE_REDIS`               | `no`       | global  | nein     | Aktiviert die Redis-/Valkey-Integration (Cluster-Modus).      |
| `REDIS_HOST`              |            | global  | nein     | Host/IP des Redis-/Valkey-Servers.                            |
| `REDIS_PORT`              | `6379`     | global  | nein     | Redis-/Valkey-Port.                                           |
| `REDIS_DATABASE`          | `0`        | global  | nein     | Datenbanknummer (0–15).                                       |
| `REDIS_SSL`               | `no`       | global  | nein     | Aktiviert SSL/TLS.                                            |
| `REDIS_SSL_VERIFY`        | `yes`      | global  | nein     | Überprüft das SSL-Zertifikat des Servers.                     |
| `REDIS_TIMEOUT`           | `5`        | global  | nein     | Timeout (Sekunden).                                           |
| `REDIS_USERNAME`          |            | global  | nein     | Benutzername (Redis ≥ 6.0).                                   |
| `REDIS_PASSWORD`          |            | global  | nein     | Passwort.                                                     |
| `REDIS_SENTINEL_HOSTS`    |            | global  | nein     | Sentinel-Hosts (durch Leerzeichen getrennt, `host:port`).     |
| `REDIS_SENTINEL_USERNAME` |            | global  | nein     | Sentinel-Benutzer.                                            |
| `REDIS_SENTINEL_PASSWORD` |            | global  | nein     | Sentinel-Passwort.                                            |
| `REDIS_SENTINEL_MASTER`   | `mymaster` | global  | nein     | Name des Sentinel-Masters.                                    |
| `REDIS_KEEPALIVE_IDLE`    | `300`      | global  | nein     | TCP-Keepalive-Intervall (Sekunden) für inaktive Verbindungen. |
| `REDIS_KEEPALIVE_POOL`    | `3`        | global  | nein     | Maximale Anzahl der im Pool gehaltenen Verbindungen.          |

!!! tip "Hochverfügbarkeit"
    Konfigurieren Sie Redis Sentinel für ein automatisches Failover in der Produktion.

!!! warning "Sicherheit"

- Verwenden Sie starke Passwörter für Redis und Sentinel.
- Erwägen Sie die Verwendung von SSL/TLS.
- Setzen Sie Redis nicht dem Internet aus.
- Beschränken Sie den Zugriff auf den Redis-Port (Firewall, Segmentierung).

!!! info "Cluster-Anforderungen"
    Bei der Bereitstellung von BunkerWeb in einem Cluster:

    - Alle BunkerWeb-Instanzen sollten sich mit demselben Redis- oder Valkey-Server oder Sentinel-Cluster verbinden
    - Konfigurieren Sie dieselbe Datenbanknummer auf allen Instanzen
    - Stellen Sie die Netzwerkkonnektivität zwischen allen BunkerWeb-Instanzen und den Redis-/Valkey-Servern sicher

### Beispiele

=== "Basiskonfiguration"

    Eine einfache Konfiguration für die Verbindung zu einem Redis- oder Valkey-Server auf dem lokalen Computer:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "localhost"
    REDIS_PORT: "6379"
    ```

=== "Sichere Konfiguration"

    Konfiguration mit Passwortauthentifizierung und aktiviertem SSL:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_SSL: "yes"
    REDIS_SSL_VERIFY: "yes"
    ```

=== "Redis Sentinel"

    Konfiguration für Hochverfügbarkeit mit Redis Sentinel:

    ```yaml
    USE_REDIS: "yes"
    REDIS_SENTINEL_HOSTS: "sentinel1:26379 sentinel2:26379 sentinel3:26379"
    REDIS_SENTINEL_MASTER: "mymaster"
    REDIS_SENTINEL_PASSWORD: "sentinel-password"
    REDIS_PASSWORD: "redis-password"
    ```

=== "Erweitertes Tuning"

    Konfiguration mit erweiterten Verbindungsparametern zur Leistungsoptimierung:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_DATABASE: "3"
    REDIS_TIMEOUT: "3"
    REDIS_KEEPALIVE_IDLE: "60"
    REDIS_KEEPALIVE_POOL: "5"
    ```

### Redis Best Practices

Berücksichtigen Sie bei der Verwendung von Redis oder Valkey mit BunkerWeb diese Best Practices, um optimale Leistung, Sicherheit und Zuverlässigkeit zu gewährleisten:

#### Speicherverwaltung
- **Speichernutzung überwachen:** Konfigurieren Sie Redis mit geeigneten `maxmemory`-Einstellungen, um Fehler wegen unzureichendem Speicher zu vermeiden
- **Verdrängungsrichtlinie festlegen:** Verwenden Sie eine für Ihren Anwendungsfall geeignete `maxmemory-policy` (z. B. `volatile-lru` oder `allkeys-lru`)
- **Große Schlüssel vermeiden:** Stellen Sie sicher, dass einzelne Redis-Schlüssel eine angemessene Größe behalten, um Leistungseinbußen zu vermeiden

#### Datenpersistenz
- **RDB-Snapshots aktivieren:** Konfigurieren Sie regelmäßige Snapshots für die Datenpersistenz ohne signifikante Leistungseinbußen
- **AOF in Betracht ziehen:** Aktivieren Sie für kritische Daten die AOF-Persistenz (Append-Only File) mit einer geeigneten fsync-Richtlinie
- **Backup-Strategie:** Implementieren Sie regelmäßige Redis-Backups als Teil Ihres Disaster-Recovery-Plans

#### Leistungsoptimierung
- **Connection Pooling:** BunkerWeb implementiert dies bereits, aber stellen Sie sicher, dass andere Anwendungen dieser Praxis folgen
- **Pipelining:** Verwenden Sie, wenn möglich, Pipelining für Massenoperationen, um den Netzwerk-Overhead zu reduzieren
- **Teure Operationen vermeiden:** Seien Sie vorsichtig mit Befehlen wie KEYS in Produktionsumgebungen
- **Benchmarken Sie Ihre Arbeitslast:** Verwenden Sie redis-benchmark, um Ihre spezifischen Arbeitslastmuster zu testen

### Weitere Ressourcen

- [Redis-Dokumentation](https://redis.io/documentation)
- [Redis-Sicherheitsleitfaden](https://redis.io/topics/security)
- [Redis-Hochverfügbarkeit](https://redis.io/topics/sentinel)
- [Redis-Persistenz](https://redis.io/topics/persistence)

## Reporting <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM-Unterstützung :x:

Regular reporting of important data from BunkerWeb (global, attacks, bans, requests, reasons, AS...). Monitoring pro plugin needed to work.

| Einstellung                    | Standardwert       | Kontext | Mehrfach | Beschreibung                                                                                                                       |
| ------------------------------ | ------------------ | ------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | global  | nein     | Enable sending the report via email.                                                                                               |
| `USE_REPORTING_WEBHOOK`        | `no`               | global  | nein     | Enable sending the report via webhook.                                                                                             |
| `REPORTING_SCHEDULE`           | `weekly`           | global  | nein     | The frequency at which reports are sent.                                                                                           |
| `REPORTING_WEBHOOK_URLS`       |                    | global  | nein     | List of webhook URLs to receive the report in Markdown (separated by spaces).                                                      |
| `REPORTING_SMTP_EMAILS`        |                    | global  | nein     | List of email addresses to receive the report in HTML format (separated by spaces).                                                |
| `REPORTING_SMTP_HOST`          |                    | global  | nein     | The host server used for SMTP sending.                                                                                             |
| `REPORTING_SMTP_PORT`          | `465`              | global  | nein     | The port used for SMTP. Please note that there are different standards depending on the type of connection (SSL = 465, TLS = 587). |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | global  | nein     | The email address used as the sender. Note that 2FA must be disabled for this email address.                                       |
| `REPORTING_SMTP_FROM_USER`     |                    | global  | nein     | The user authentication value for sending via the from email address.                                                              |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | global  | nein     | The password authentication value for sending via the from email address.                                                          |
| `REPORTING_SMTP_SSL`           | `SSL`              | global  | nein     | Determine whether or not to use a secure connection for SMTP.                                                                      |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | global  | nein     | The subject line of the email.                                                                                                     |

## Reverse proxy

STREAM-Unterstützung :warning:

Das Reverse-Proxy-Plugin bietet nahtlose Proxy-Funktionen für BunkerWeb, mit denen Sie Anfragen an Backend-Server und -Dienste weiterleiten können. Mit dieser Funktion kann BunkerWeb als sicheres Frontend für Ihre Anwendungen fungieren und gleichzeitig zusätzliche Vorteile wie SSL-Terminierung und Sicherheitsfilterung bieten.

**So funktioniert es:**

1.  Wenn ein Client eine Anfrage an BunkerWeb sendet, leitet das Reverse-Proxy-Plugin die Anfrage an Ihren konfigurierten Backend-Server weiter.
2.  BunkerWeb fügt Sicherheitsheader hinzu, wendet WAF-Regeln an und führt andere Sicherheitsprüfungen durch, bevor die Anfragen an Ihre Anwendung weitergeleitet werden.
3.  Der Backend-Server verarbeitet die Anfrage und gibt eine Antwort an BunkerWeb zurück.
4.  BunkerWeb wendet zusätzliche Sicherheitsmaßnahmen auf die Antwort an, bevor sie an den Client zurückgesendet wird.
5.  Das Plugin unterstützt sowohl HTTP- als auch TCP/UDP-Stream-Proxying und ermöglicht so eine breite Palette von Anwendungen, einschließlich WebSockets und anderen Nicht-HTTP-Protokollen.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Reverse-Proxy-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Setzen Sie die Einstellung `USE_REVERSE_PROXY` auf `yes`, um die Reverse-Proxy-Funktionalität zu aktivieren.
2.  **Konfigurieren Sie Ihre Backend-Server:** Geben Sie die Upstream-Server mit der Einstellung `REVERSE_PROXY_HOST` an.
3.  **Proxy-Einstellungen anpassen:** Optimieren Sie das Verhalten mit optionalen Einstellungen für Zeitüberschreitungen, Puffergrößen und andere Parameter.
4.  **Protokollspezifische Optionen konfigurieren:** Passen Sie für WebSockets oder spezielle HTTP-Anforderungen die entsprechenden Einstellungen an.
5.  **Caching einrichten (optional):** Aktivieren und konfigurieren Sie das Proxy-Caching, um die Leistung für häufig aufgerufene Inhalte zu verbessern.

### Konfigurationsanleitung

=== "Grundlegende Konfiguration"

    **Kerneinstellungen**

    Die wesentlichen Konfigurationseinstellungen aktivieren und steuern die Grundfunktionalität der Reverse-Proxy-Funktion.

    !!! success "Vorteile des Reverse-Proxy"
        - **Sicherheitsverbesserung:** Der gesamte Datenverkehr durchläuft die Sicherheitsschichten von BunkerWeb, bevor er Ihre Anwendungen erreicht
        - **SSL-Terminierung:** Verwalten Sie SSL/TLS-Zertifikate zentral, während Backend-Dienste unverschlüsselte Verbindungen verwenden können
        - **Protokollbehandlung:** Unterstützung für HTTP, HTTPS, WebSockets und andere Protokolle
        - **Fehlerabfang:** Passen Sie Fehlerseiten für ein einheitliches Benutzererlebnis an

    | Einstellung                       | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                      |
    | --------------------------------- | -------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------- |
    | `USE_REVERSE_PROXY`               | `no`     | multisite | nein     | **Reverse-Proxy aktivieren:** Auf `yes` setzen, um die Reverse-Proxy-Funktionalität zu aktivieren.                |
    | `REVERSE_PROXY_HOST`              |          | multisite | ja       | **Backend-Host:** Vollständige URL der weitergeleiteten Ressource (proxy_pass).                                   |
    | `REVERSE_PROXY_URL`               | `/`      | multisite | ja       | **Standort-URL:** Pfad, der zum Backend-Server weitergeleitet wird.                                               |
    | `REVERSE_PROXY_BUFFERING`         | `yes`    | multisite | ja       | **Antwort-Pufferung:** Aktiviert oder deaktiviert die Pufferung von Antworten von der weitergeleiteten Ressource. |
    | `REVERSE_PROXY_REQUEST_BUFFERING` | `yes`    | multisite | ja       | **Anfrage-Pufferung:** Aktiviert oder deaktiviert die Pufferung von Anfragen an die weitergeleitete Ressource.    |
    | `REVERSE_PROXY_KEEPALIVE`         | `no`     | multisite | ja       | **Keep-Alive:** Aktiviert oder deaktiviert Keep-Alive-Verbindungen mit der weitergeleiteten Ressource.            |
    | `REVERSE_PROXY_CUSTOM_HOST`       |          | multisite | nein     | **Benutzerdefinierter Host:** Überschreibt den an den Upstream-Server gesendeten Host-Header.                     |
    | `REVERSE_PROXY_INTERCEPT_ERRORS`  | `yes`    | multisite | nein     | **Fehler abfangen:** Ob Fehlerantworten vom Backend abgefangen und neu geschrieben werden sollen.                 |

    !!! tip "Bewährte Praktiken"
        - Geben Sie in `REVERSE_PROXY_HOST` immer die vollständige URL an, einschließlich des Protokolls (http:// oder https://)
        - Verwenden Sie `REVERSE_PROXY_INTERCEPT_ERRORS`, um konsistente Fehlerseiten für alle Ihre Dienste bereitzustellen
        - Verwenden Sie bei der Konfiguration mehrerer Backends das nummerierte Suffixformat (z. B. `REVERSE_PROXY_HOST_2`, `REVERSE_PROXY_URL_2`)

    !!! warning "Verhalten der Anfrage-Pufferung"
        Das Deaktivieren von `REVERSE_PROXY_REQUEST_BUFFERING` hat nur Wirkung, wenn ModSecurity deaktiviert ist, da die Anfrage-Pufferung ansonsten erzwungen wird.

=== "Verbindungseinstellungen"

    **Konfiguration von Verbindungen und Zeitüberschreitungen**

    Diese Einstellungen steuern das Verbindungsverhalten, die Pufferung und die Zeitüberschreitungswerte für die weitergeleiteten Verbindungen.

    !!! success "Vorteile"
        - **Optimierte Leistung:** Passen Sie Puffergrößen und Verbindungseinstellungen an die Bedürfnisse Ihrer Anwendung an
        - **Ressourcenmanagement:** Kontrollieren Sie die Speichernutzung durch geeignete Pufferkonfigurationen
        - **Zuverlässigkeit:** Konfigurieren Sie geeignete Zeitüberschreitungen, um langsame Verbindungen oder Backend-Probleme zu bewältigen

    | Einstellung                     | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                             |
    | ------------------------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
    | `REVERSE_PROXY_CONNECT_TIMEOUT` | `60s`    | multisite | ja       | **Verbindungs-Timeout:** Maximale Zeit zum Herstellen einer Verbindung zum Backend-Server.                               |
    | `REVERSE_PROXY_READ_TIMEOUT`    | `60s`    | multisite | ja       | **Lese-Timeout:** Maximale Zeit zwischen der Übertragung von zwei aufeinanderfolgenden Paketen vom Backend-Server.       |
    | `REVERSE_PROXY_SEND_TIMEOUT`    | `60s`    | multisite | ja       | **Sende-Timeout:** Maximale Zeit zwischen der Übertragung von zwei aufeinanderfolgenden Paketen zum Backend-Server.      |
    | `PROXY_BUFFERS`                 |          | multisite | nein     | **Puffer:** Anzahl und Größe der Puffer zum Lesen der Antwort vom Backend-Server.                                        |
    | `PROXY_BUFFER_SIZE`             |          | multisite | nein     | **Puffergröße:** Größe des Puffers zum Lesen des ersten Teils der Antwort vom Backend-Server.                            |
    | `PROXY_BUSY_BUFFERS_SIZE`       |          | multisite | nein     | **Größe der belegten Puffer:** Größe der Puffer, die mit dem Senden einer Antwort an den Client beschäftigt sein können. |

    !!! warning "Überlegungen zu Zeitüberschreitungen"
        - Zu kurze Zeitüberschreitungen können legitime, aber langsame Verbindungen unterbrechen
        - Zu lange Zeitüberschreitungen können Verbindungen unnötig offen lassen und möglicherweise Ressourcen erschöpfen
        - Bei WebSocket-Anwendungen sollten Sie die Lese- und Sende-Timeouts deutlich erhöhen (300s oder mehr empfohlen)

=== "SSL/TLS-Konfiguration"

    **SSL/TLS-Einstellungen für Backend-Verbindungen**

    Diese Einstellungen steuern, wie BunkerWeb sichere Verbindungen zu Backend-Servern herstellt.

    !!! success "Vorteile"
        - **Ende-zu-Ende-Verschlüsselung:** Behalten Sie verschlüsselte Verbindungen vom Client zum Backend bei
        - **Zertifikatsvalidierung:** Kontrollieren Sie, wie Backend-Serverzertifikate validiert werden
        - **SNI-Unterstützung:** Geben Sie die Server Name Indication für Backends an, die mehrere Websites hosten

    | Einstellung                  | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                  |
    | ---------------------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_SSL_SNI`      | `no`     | multisite | nein     | **SSL SNI:** Aktiviert oder deaktiviert das Senden von SNI (Server Name Indication) an den Upstream.          |
    | `REVERSE_PROXY_SSL_SNI_NAME` |          | multisite | nein     | **SSL SNI-Name:** Legt den SNI-Hostnamen fest, der an den Upstream gesendet wird, wenn SSL SNI aktiviert ist. |

    !!! info "SNI erklärt"
        Server Name Indication (SNI) ist eine TLS-Erweiterung, die es einem Client ermöglicht, den Hostnamen anzugeben, mit dem er während des Handshake-Prozesses eine Verbindung herstellen möchte. Dies ermöglicht es Servern, mehrere Zertifikate auf derselben IP-Adresse und demselben Port zu präsentieren, sodass mehrere sichere (HTTPS-)Websites von einer einzigen IP-Adresse aus bedient werden können, ohne dass alle diese Websites dasselbe Zertifikat verwenden müssen.

=== "Protokollunterstützung"

    **Protokollspezifische Konfiguration**

    Konfigurieren Sie die Behandlung spezieller Protokolle, insbesondere für WebSockets und andere Nicht-HTTP-Protokolle.

    !!! success "Vorteile"
        - **Protokollflexibilität:** Die Unterstützung für WebSockets ermöglicht Echtzeitanwendungen
        - **Moderne Webanwendungen:** Aktivieren Sie interaktive Funktionen, die eine bidirektionale Kommunikation erfordern

    | Einstellung        | Standard | Kontext   | Mehrfach | Beschreibung                                                                      |
    | ------------------ | -------- | --------- | -------- | --------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_WS` | `no`     | multisite | ja       | **WebSocket-Unterstützung:** Aktiviert das WebSocket-Protokoll für die Ressource. |

    !!! tip "WebSocket-Konfiguration"
        - Bei der Aktivierung von WebSockets mit `REVERSE_PROXY_WS: "yes"` sollten Sie die Zeitüberschreitungswerte erhöhen
        - WebSocket-Verbindungen bleiben länger offen als typische HTTP-Verbindungen
        - Für WebSocket-Anwendungen wird folgende Konfiguration empfohlen:
          ```yaml
          REVERSE_PROXY_WS: "yes"
          REVERSE_PROXY_READ_TIMEOUT: "300s"
          REVERSE_PROXY_SEND_TIMEOUT: "300s"
          ```

=== "Header-Verwaltung"

    **HTTP-Header-Konfiguration**

    Kontrollieren Sie, welche Header an Backend-Server und Clients gesendet werden, und ermöglichen Sie das Hinzufügen, Ändern oder Beibehalten von HTTP-Headern.

    !!! success "Vorteile"
        - **Informationskontrolle:** Verwalten Sie genau, welche Informationen zwischen Clients und Backends ausgetauscht werden
        - **Sicherheitsverbesserung:** Fügen Sie sicherheitsrelevante Header hinzu oder entfernen Sie Header, die sensible Informationen preisgeben könnten
        - **Integrationsunterstützung:** Stellen Sie die für die Authentifizierung und den ordnungsgemäßen Backend-Betrieb erforderlichen Header bereit

    | Einstellung                            | Standard  | Kontext   | Mehrfach | Beschreibung                                                                                                        |
    | -------------------------------------- | --------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_HEADERS`                |           | multisite | ja       | **Benutzerdefinierte Header:** HTTP-Header, die durch Semikolons getrennt an das Backend gesendet werden.           |
    | `REVERSE_PROXY_HIDE_HEADERS`           | `Upgrade` | multisite | ja       | **Header ausblenden:** HTTP-Header, die vor Clients verborgen werden sollen, wenn sie vom Backend empfangen werden. |
    | `REVERSE_PROXY_HEADERS_CLIENT`         |           | multisite | ja       | **Client-Header:** HTTP-Header, die durch Semikolons getrennt an den Client gesendet werden.                        |
    | `REVERSE_PROXY_UNDERSCORES_IN_HEADERS` | `no`      | multisite | nein     | **Unterstriche in Headern:** Aktiviert oder deaktiviert die `underscores_in_headers`-Direktive.                     |

    !!! warning "Sicherheitsüberlegungen"
        Seien Sie bei der Verwendung der Reverse-Proxy-Funktion vorsichtig, welche Header Sie an Ihre Backend-Anwendungen weiterleiten. Bestimmte Header können sensible Informationen über Ihre Infrastruktur preisgeben oder Sicherheitskontrollen umgehen.

    !!! example "Beispiele für Header-Formate"
        Benutzerdefinierte Header an Backend-Server:
        ```
        REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"
        ```

        Benutzerdefinierte Header an Clients:
        ```
        REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
        ```

=== "Authentifizierung"

    **Konfiguration der externen Authentifizierung**

    Integrieren Sie externe Authentifizierungssysteme, um die Autorisierungslogik für Ihre Anwendungen zu zentralisieren.

    !!! success "Vorteile"
        - **Zentralisierte Authentifizierung:** Implementieren Sie einen einzigen Authentifizierungspunkt für mehrere Anwendungen
        - **Konsistente Sicherheit:** Wenden Sie einheitliche Authentifizierungsrichtlinien für verschiedene Dienste an
        - **Verbesserte Kontrolle:** Leiten Sie Authentifizierungsdetails über Header oder Variablen an Backend-Anwendungen weiter

    | Einstellung                             | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                    |
    | --------------------------------------- | -------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_AUTH_REQUEST`            |          | multisite | ja       | **Authentifizierungsanforderung:** Aktiviert die Authentifizierung über einen externen Anbieter.                |
    | `REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` |          | multisite | ja       | **Anmelde-URL:** Leitet Clients bei fehlgeschlagener Authentifizierung zur Anmelde-URL weiter.                  |
    | `REVERSE_PROXY_AUTH_REQUEST_SET`        |          | multisite | ja       | **Authentifizierungsanforderungssatz:** Variablen, die vom Authentifizierungsanbieter festgelegt werden sollen. |

    !!! tip "Authentifizierungsintegration"
        - Die Authentifizierungsanforderungsfunktion ermöglicht die Implementierung zentralisierter Authentifizierungsmikrodienste
        - Ihr Authentifizierungsdienst sollte bei erfolgreicher Authentifizierung einen 200-Statuscode oder bei einem Fehler 401/403 zurückgeben
        - Verwenden Sie die auth_request_set-Direktive, um Informationen vom Authentifizierungsdienst zu extrahieren und weiterzuleiten

=== "Erweiterte Konfiguration"

    **Zusätzliche Konfigurationsoptionen**

    Diese Einstellungen bieten eine weitere Anpassung des Reverse-Proxy-Verhaltens für spezielle Szenarien.

    !!! success "Vorteile"
        - **Anpassung:** Fügen Sie zusätzliche Konfigurationsausschnitte für komplexe Anforderungen hinzu
        - **Leistungsoptimierung:** Optimieren Sie die Anforderungsbehandlung für bestimmte Anwendungsfälle
        - **Flexibilität:** Passen Sie sich mit speziellen Konfigurationen an einzigartige Anwendungsanforderungen an

    | Einstellung                       | Standard | Kontext   | Mehrfach | Beschreibung                                                                                              |
    | --------------------------------- | -------- | --------- | -------- | --------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_INCLUDES`          |          | multisite | ja       | **Zusätzliche Konfigurationen:** Fügen Sie zusätzliche Konfigurationen in den Standortblock ein.          |
    | `REVERSE_PROXY_PASS_REQUEST_BODY` | `yes`    | multisite | ja       | **Anforderungskörper weiterleiten:** Aktiviert oder deaktiviert das Weiterleiten des Anforderungskörpers. |

    !!! warning "Sicherheitsüberlegungen"
        Seien Sie vorsichtig, wenn Sie benutzerdefinierte Konfigurationsausschnitte einfügen, da diese die Sicherheitseinstellungen von BunkerWeb überschreiben oder bei unsachgemäßer Konfiguration Schwachstellen einführen können.

=== "Caching-Konfiguration"

    **Einstellungen für das Caching von Antworten**

    Verbessern Sie die Leistung durch das Caching von Antworten von Backend-Servern, wodurch die Last reduziert und die Antwortzeiten verbessert werden.

    !!! success "Vorteile"
        - **Leistung:** Reduzieren Sie die Last auf Backend-Servern, indem Sie zwischengespeicherte Inhalte bereitstellen
        - **Reduzierte Latenz:** Schnellere Antwortzeiten für häufig angeforderte Inhalte
        - **Bandbreiteneinsparungen:** Minimieren Sie den internen Netzwerkverkehr durch das Caching von Antworten
        - **Anpassung:** Konfigurieren Sie genau, was, wann und wie Inhalte zwischengespeichert werden

    | Einstellung                  | Standard                           | Kontext   | Mehrfach | Beschreibung                                                                                                                                         |
    | ---------------------------- | ---------------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_PROXY_CACHE`            | `no`                               | multisite | nein     | **Caching aktivieren:** Auf `yes` setzen, um das Caching von Backend-Antworten zu aktivieren.                                                        |
    | `PROXY_CACHE_PATH_LEVELS`    | `1:2`                              | global    | nein     | **Cache-Pfad-Ebenen:** Wie die Hierarchie des Cache-Verzeichnisses strukturiert werden soll.                                                         |
    | `PROXY_CACHE_PATH_ZONE_SIZE` | `10m`                              | global    | nein     | **Cache-Zonengröße:** Größe des gemeinsam genutzten Speicherbereichs, der für Cache-Metadaten verwendet wird.                                        |
    | `PROXY_CACHE_PATH_PARAMS`    | `max_size=100m`                    | global    | nein     | **Cache-Pfad-Parameter:** Zusätzliche Parameter für den Cache-Pfad.                                                                                  |
    | `PROXY_CACHE_METHODS`        | `GET HEAD`                         | multisite | nein     | **Cache-Methoden:** HTTP-Methoden, die zwischengespeichert werden können.                                                                            |
    | `PROXY_CACHE_MIN_USES`       | `2`                                | multisite | nein     | **Mindestverwendungen für Cache:** Mindestanzahl von Anfragen, bevor eine Antwort zwischengespeichert wird.                                          |
    | `PROXY_CACHE_KEY`            | `$scheme$host$request_uri`         | multisite | nein     | **Cache-Schlüssel:** Der Schlüssel, der zur eindeutigen Identifizierung einer zwischengespeicherten Antwort verwendet wird.                          |
    | `PROXY_CACHE_VALID`          | `200=24h 301=1h 302=24h`           | multisite | nein     | **Cache-Gültigkeit:** Wie lange bestimmte Antwortcodes zwischengespeichert werden sollen.                                                            |
    | `PROXY_NO_CACHE`             | `$http_pragma $http_authorization` | multisite | nein     | **Kein Cache:** Bedingungen, unter denen Antworten nicht zwischengespeichert werden, auch wenn sie normalerweise zwischengespeichert werden könnten. |
    | `PROXY_CACHE_BYPASS`         | `0`                                | multisite | nein     | **Cache-Umgehung:** Bedingungen, unter denen der Cache umgangen werden soll.                                                                         |

    !!! tip "Bewährte Praktiken für das Caching"
        - Speichern Sie nur Inhalte zwischen, die sich nicht häufig ändern oder nicht personalisiert sind
        - Verwenden Sie je nach Inhaltstyp geeignete Cache-Dauern (statische Assets können länger zwischengespeichert werden)
        - Konfigurieren Sie `PROXY_NO_CACHE`, um das Zwischenspeichern sensibler oder personalisierter Inhalte zu vermeiden
        - Überwachen Sie die Cache-Trefferquoten und passen Sie die Einstellungen entsprechend an

!!! danger "Docker Compose-Benutzer - NGINX-Variablen"
    Wenn Sie Docker Compose mit NGINX-Variablen in Ihren Konfigurationen verwenden, müssen Sie das Dollarzeichen (`$`) durch doppelte Dollarzeichen (`$$`) maskieren. Dies gilt für alle Einstellungen, die NGINX-Variablen wie `$remote_addr`, `$proxy_add_x_forwarded_for` usw. enthalten.

    Ohne diese Maskierung versucht Docker Compose, diese Variablen durch Umgebungsvariablen zu ersetzen, die normalerweise nicht existieren, was zu leeren Werten in Ihrer NGINX-Konfiguration führt.

### Beispielkonfigurationen

=== "Grundlegender HTTP-Proxy"

    Eine einfache Konfiguration zum Weiterleiten von HTTP-Anfragen an einen Backend-Anwendungsserver:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "60s"
    REVERSE_PROXY_READ_TIMEOUT: "60s"
    ```

=== "WebSocket-Anwendung"

    Konfiguration, die für eine WebSocket-Anwendung mit längeren Zeitüberschreitungen optimiert ist:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://websocket-app:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_WS: "yes"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "300s"
    REVERSE_PROXY_READ_TIMEOUT: "300s"
    ```

=== "Mehrere Standorte"

    Konfiguration zum Weiterleiten verschiedener Pfade an verschiedene Backend-Dienste:

    ```yaml
    USE_REVERSE_PROXY: "yes"

    # API-Backend
    REVERSE_PROXY_HOST: "http://api-server:8080"
    REVERSE_PROXY_URL: "/api/"

    # Admin-Backend
    REVERSE_PROXY_HOST_2: "http://admin-server:8080"
    REVERSE_PROXY_URL_2: "/admin/"

    # Frontend-App
    REVERSE_PROXY_HOST_3: "http://frontend:3000"
    REVERSE_PROXY_URL_3: "/"
    ```

=== "Caching-Konfiguration"

    Konfiguration mit aktiviertem Proxy-Caching für eine bessere Leistung:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    USE_PROXY_CACHE: "yes"
    PROXY_CACHE_VALID: "200=24h 301=1h 302=24h"
    PROXY_CACHE_METHODS: "GET HEAD"
    PROXY_NO_CACHE: "$http_authorization"
    ```

=== "Erweiterte Header-Verwaltung"

    Konfiguration mit benutzerdefinierter Header-Manipulation:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Benutzerdefinierte Header an das Backend
    REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"

    # Benutzerdefinierte Header an den Client
    REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
    ```

=== "Authentifizierungsintegration"

    Konfiguration mit externer Authentifizierung:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Authentifizierungskonfiguration
    REVERSE_PROXY_AUTH_REQUEST: "/auth"
    REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: "https://login.example.com"
    REVERSE_PROXY_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_role $upstream_http_x_role"

    # Backend des Authentifizierungsdienstes
    REVERSE_PROXY_HOST_2: "http://auth-service:8080"
    REVERSE_PROXY_URL_2: "/auth"
    ```

## Reverse scan

STREAM-Unterstützung :white_check_mark:

Das Reverse Scan-Plugin schützt robust vor Proxy-Umgehungsversuchen, indem es die Ports der Clients scannt, um festzustellen, ob sie Proxyserver oder andere Netzwerkdienste betreiben. Diese Funktion hilft dabei, potenzielle Bedrohungen von Clients zu identifizieren und zu blockieren, die möglicherweise versuchen, ihre wahre Identität oder Herkunft zu verbergen, und verbessert so die Sicherheitslage Ihrer Website.

**So funktioniert es:**

1.  Wenn ein Client eine Verbindung zu Ihrem Server herstellt, versucht BunkerWeb, bestimmte Ports auf der IP-Adresse des Clients zu scannen.
2.  Das Plugin prüft, ob gängige Proxy-Ports (wie 80, 443, 8080 usw.) auf der Client-Seite geöffnet sind.
3.  Wenn offene Ports erkannt werden, was darauf hindeutet, dass der Client möglicherweise einen Proxyserver betreibt, wird die Verbindung verweigert.
4.  Dies fügt eine zusätzliche Sicherheitsebene gegen automatisierte Tools, Bots und böswillige Benutzer hinzu, die versuchen, ihre Identität zu verschleiern.

!!! success "Wichtige Vorteile"

      1. **Erhöhte Sicherheit:** Identifiziert Clients, die potenziell Proxyserver betreiben, die für bösartige Zwecke verwendet werden könnten.
      2. **Proxy-Erkennung:** Hilft bei der Erkennung und Blockierung von Clients, die versuchen, ihre wahre Identität zu verbergen.
      3. **Konfigurierbare Einstellungen:** Passen Sie an, welche Ports basierend auf Ihren spezifischen Sicherheitsanforderungen gescannt werden sollen.
      4. **Leistungsoptimiert:** Intelligentes Scannen mit konfigurierbaren Zeitüberschreitungen, um die Auswirkungen auf legitime Benutzer zu minimieren.
      5. **Nahtlose Integration:** Arbeitet transparent mit Ihren bestehenden Sicherheitsebenen zusammen.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Reverse-Scan-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Setzen Sie die Einstellung `USE_REVERSE_SCAN` auf `yes`, um das Scannen von Client-Ports zu aktivieren.
2.  **Zu scannende Ports konfigurieren:** Passen Sie die Einstellung `REVERSE_SCAN_PORTS` an, um anzugeben, welche Client-Ports überprüft werden sollen.
3.  **Scan-Timeout festlegen:** Passen Sie den `REVERSE_SCAN_TIMEOUT` an, um ein Gleichgewicht zwischen gründlichem Scannen und Leistung zu finden.
4.  **Scan-Aktivität überwachen:** Überprüfen Sie die Protokolle und die [Web-Benutzeroberfläche](web-ui.md), um die Scan-Ergebnisse und potenzielle Sicherheitsvorfälle zu überprüfen.

### Konfigurationseinstellungen

| Einstellung            | Standard                   | Kontext   | Mehrfach | Beschreibung                                                                                        |
| ---------------------- | -------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------- |
| `USE_REVERSE_SCAN`     | `no`                       | multisite | nein     | **Reverse-Scan aktivieren:** Auf `yes` setzen, um das Scannen von Client-Ports zu aktivieren.       |
| `REVERSE_SCAN_PORTS`   | `22 80 443 3128 8000 8080` | multisite | nein     | **Zu scannende Ports:** Leerzeichengetrennte Liste der zu überprüfenden Ports auf der Client-Seite. |
| `REVERSE_SCAN_TIMEOUT` | `500`                      | multisite | nein     | **Scan-Timeout:** Maximale Zeit in Millisekunden, die für das Scannen eines Ports zulässig ist.     |

!!! warning "Leistungsüberlegungen"
    Das Scannen mehrerer Ports kann die Latenz bei Client-Verbindungen erhöhen. Verwenden Sie einen angemessenen Zeitüberschreitungswert und begrenzen Sie die Anzahl der gescannten Ports, um eine gute Leistung aufrechtzuerhalten.

!!! info "Gängige Proxy-Ports"
    Die Standardkonfiguration umfasst gängige Ports, die von Proxyservern (80, 443, 8080, 3128) und SSH (22) verwendet werden. Sie können diese Liste basierend auf Ihrem Bedrohungsmodell anpassen.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine einfache Konfiguration zum Aktivieren des Client-Port-Scannens:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "500"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Umfassendes Scannen"

    Eine gründlichere Konfiguration, die zusätzliche Ports überprüft:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1000"
    REVERSE_SCAN_PORTS: "22 80 443 3128 8080 8000 8888 1080 3333 8081"
    ```

=== "Leistungsoptimierte Konfiguration"

    Konfiguration, die auf eine bessere Leistung abgestimmt ist, indem weniger Ports mit einer geringeren Zeitüberschreitung überprüft werden:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "250"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Hochsicherheitskonfiguration"

    Konfiguration mit Fokus auf maximale Sicherheit mit erweitertem Scannen:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1500"
    REVERSE_SCAN_PORTS: "22 25 80 443 1080 3128 3333 4444 5555 6588 6666 7777 8000 8080 8081 8800 8888 9999"
    ```

## Robots.txt

STREAM-Unterstützung :white_check_mark:

Das Robots.txt-Plugin verwaltet die Datei [robots.txt](https://www.robotstxt.org/) für Ihre Website. Diese Datei teilt Web-Crawlern und Robotern mit, auf welche Teile Ihrer Website sie zugreifen dürfen und auf welche nicht.

**So funktioniert es:**

Wenn aktiviert, generiert BunkerWeb dynamisch die `/robots.txt`-Datei im Stammverzeichnis Ihrer Website. Die Regeln in dieser Datei werden in der folgenden Reihenfolge aus mehreren Quellen zusammengefasst:

1.  **DarkVisitors-API:** Wenn `ROBOTSTXT_DARKVISITORS_TOKEN` angegeben ist, werden Regeln von der [DarkVisitors](https://darkvisitors.com/)-API abgerufen, was eine dynamische Blockierung bösartiger Bots und KI-Crawler basierend auf konfigurierten Agententypen und nicht zugelassenen Benutzeragenten ermöglicht.
2.  **Community-Listen:** Regeln aus vordefinierten, von der Community gepflegten `robots.txt`-Listen (angegeben durch `ROBOTSTXT_COMMUNITY_LISTS`) werden einbezogen.
3.  **Benutzerdefinierte URLs:** Regeln werden von vom Benutzer bereitgestellten URLs abgerufen (angegeben durch `ROBOTSTXT_URLS`).
4.  **Manuelle Regeln:** Regeln, die direkt über `ROBOTSTXT_RULE`-Umgebungsvariablen definiert werden, werden hinzugefügt.

Alle Regeln aus diesen Quellen werden kombiniert. Nach der Aggregation werden `ROBOTSTXT_IGNORE_RULE` angewendet, um unerwünschte Regeln mit PCRE-Regex-Mustern herauszufiltern. Wenn nach diesem gesamten Prozess keine Regeln mehr übrig sind, wird automatisch eine Standardregel `User-agent: *` und `Disallow: /` angewendet, um einen grundlegenden Schutz zu gewährleisten. Optionale Sitemap-URLs (angegeben durch `ROBOTSTXT_SITEMAP`) werden ebenfalls in die endgültige `robots.txt`-Ausgabe aufgenommen.

### Dynamische Bot-Umgehung mit der DarkVisitors-API

[DarkVisitors](https://darkvisitors.com/) ist ein Dienst, der eine dynamische `robots.txt`-Datei bereitstellt, um bekannte bösartige Bots und KI-Crawler zu blockieren. Durch die Integration mit DarkVisitors kann BunkerWeb automatisch eine aktuelle `robots.txt` abrufen und bereitstellen, die Ihre Website vor unerwünschtem automatisiertem Datenverkehr schützt.

Um dies zu aktivieren, müssen Sie sich bei [darkvisitors.com](https://darkvisitors.com/docs/robots-txt) anmelden und ein Bearer-Token erhalten.

### Wie man es benutzt

1.  **Aktivieren Sie die Funktion:** Setzen Sie die Einstellung `USE_ROBOTSTXT` auf `yes`.
2.  **Regeln konfigurieren:** Wählen Sie eine oder mehrere Methoden, um Ihre `robots.txt`-Regeln zu definieren:
    - **DarkVisitors-API:** Geben Sie `ROBOTSTXT_DARKVISITORS_TOKEN` und optional `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` und `ROBOTSTXT_DARKVISITORS_DISALLOW` an.
    - **Community-Listen:** Geben Sie `ROBOTSTXT_COMMUNITY_LISTS` an (durch Leerzeichen getrennte IDs).
    - **Benutzerdefinierte URLs:** Geben Sie `ROBOTSTXT_URLS` an (durch Leerzeichen getrennte URLs).
    - **Manuelle Regeln:** Verwenden Sie `ROBOTSTXT_RULE` für einzelne Regeln (mehrere Regeln können mit `ROBOTSTXT_RULE_N` angegeben werden).
3.  **Regeln filtern (optional):** Verwenden Sie `ROBOTSTXT_IGNORE_RULE_N`, um bestimmte Regeln nach Regex-Muster auszuschließen.
4.  **Sitemaps hinzufügen (optional):** Verwenden Sie `ROBOTSTXT_SITEMAP_N` für Sitemap-URLs.
5.  **Die generierte robots.txt-Datei abrufen:** Sobald BunkerWeb mit den obigen Einstellungen läuft, können Sie auf die dynamisch generierte `robots.txt`-Datei zugreifen, indem Sie eine HTTP-GET-Anfrage an `http(s)://your-domain.com/robots.txt` senden.

### Konfigurationseinstellungen

| Einstellung                          | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                     |
| ------------------------------------ | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_ROBOTSTXT`                      | `no`     | multisite | Nein     | Aktiviert oder deaktiviert die `robots.txt`-Funktion.                                                                                            |
| `ROBOTSTXT_DARKVISITORS_TOKEN`       |          | multisite | Nein     | Bearer-Token für die DarkVisitors-API.                                                                                                           |
| `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` |          | multisite | Nein     | Kommagetrennte Liste von Agententypen (z. B. `AI Data Scraper`), die von DarkVisitors einbezogen werden sollen.                                  |
| `ROBOTSTXT_DARKVISITORS_DISALLOW`    | `/`      | multisite | Nein     | Ein String, der angibt, welche URLs nicht erlaubt sind. Dieser Wert wird als Disallow-Feld gesendet, wenn die DarkVisitors-API kontaktiert wird. |
| `ROBOTSTXT_COMMUNITY_LISTS`          |          | multisite | Nein     | Leerzeichengetrennte Liste von von der Community gepflegten Regelsatz-IDs, die einbezogen werden sollen.                                         |
| `ROBOTSTXT_URLS`                     |          | multisite | Nein     | Leerzeichengetrennte Liste von URLs, von denen zusätzliche `robots.txt`-Regeln abgerufen werden sollen. Unterstützt `file://` und Basic-Auth.    |
| `ROBOTSTXT_RULE`                     |          | multisite | Ja       | Eine einzelne Regel für `robots.txt`.                                                                                                            |
| `ROBOTSTXT_HEADER`                   |          | multisite | Ja       | Kopfzeile für die `robots.txt`-Datei (vor den Regeln). Kann Base64-kodiert sein.                                                                 |
| `ROBOTSTXT_FOOTER`                   |          | multisite | Ja       | Fußzeile für die `robots.txt`-Datei (nach den Regeln). Kann Base64-kodiert sein.                                                                 |
| `ROBOTSTXT_IGNORE_RULE`              |          | multisite | Ja       | Ein einzelnes PCRE-Regex-Muster zum Ignorieren von Regeln.                                                                                       |
| `ROBOTSTXT_SITEMAP`                  |          | multisite | Ja       | Eine einzelne Sitemap-URL.                                                                                                                       |

### Beispielkonfigurationen

**Grundlegende manuelle Regeln**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**Verwendung dynamischer Quellen (DarkVisitors & Community-Liste)**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "ihr-darkvisitors-token-hier"
ROBOTSTXT_DARKVISITORS_AGENT_TYPES: "AI Data Scraper"
ROBOTSTXT_COMMUNITY_LISTS: "robots-disallowed"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
```

**Kombinierte Konfiguration**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "ihr-darkvisitors-token-hier"
ROBOTSTXT_COMMUNITY_LISTS: "ai-robots-txt"
ROBOTSTXT_URLS: "https://example.com/my-custom-rules.txt"
ROBOTSTXT_RULE: "User-agent: MyOwnBot"
ROBOTSTXT_RULE_1: "Disallow: /admin"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**Mit Kopf- und Fußzeile**

````yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_HEADER: "# Dies ist eine benutzerdefinierte Kopfzeile"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_FOOTER: "# Dies ist eine benutzerdefinierte Fußzeile"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"```

---

Weitere Informationen finden Sie in der [robots.txt-Dokumentation](https://www.robotstxt.org/robotstxt.html).
````

## SSL

STREAM-Unterstützung :white_check_mark:

Das SSL-Plugin bietet eine robuste SSL/TLS-Verschlüsselung für Ihre durch BunkerWeb geschützten Websites. Es ermöglicht sichere HTTPS-Verbindungen durch die Konfiguration von Protokollen, kryptografischen Suiten und zugehörigen Parametern.

So funktioniert's:

1.  Bei einer HTTPS-Verbindung verwaltet BunkerWeb die SSL/TLS-Aushandlung gemäß Ihren Einstellungen.
2.  Das Plugin erzwingt moderne Protokolle und starke Suiten und deaktiviert anfällige Optionen.
3.  Optimierte Sitzungsparameter verbessern die Leistung, ohne die Sicherheit zu beeinträchtigen.
4.  Die Präsentation der Zertifikate folgt Best Practices für Kompatibilität und Sicherheit.

### Verwendung

1.  **Protokolle**: Wählen Sie die Versionen über `SSL_PROTOCOLS`.
2.  **Suiten**: Wählen Sie ein Niveau über `SSL_CIPHERS_LEVEL` oder benutzerdefinierte Suiten über `SSL_CIPHERS_CUSTOM`.
3.  **Weiterleitungen**: Konfigurieren Sie die HTTP→HTTPS-Weiterleitung mit `AUTO_REDIRECT_HTTP_TO_HTTPS` und/oder `REDIRECT_HTTP_TO_HTTPS`.

### Parameter

| Parameter                     | Standard          | Kontext   | Mehrfach | Beschreibung                                                                                                                               |
| :---------------------------- | :---------------- | :-------- | :------- | :----------------------------------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_HTTP_TO_HTTPS`      | `no`              | Multisite | nein     | Leitet alle HTTP-Anfragen zu HTTPS um.                                                                                                     |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` | `yes`             | Multisite | nein     | Automatische Weiterleitung, wenn HTTPS erkannt wird.                                                                                       |
| `SSL_PROTOCOLS`               | `TLSv1.2 TLSv1.3` | Multisite | nein     | Unterstützte SSL/TLS-Protokolle (durch Leerzeichen getrennt).                                                                              |
| `SSL_CIPHERS_LEVEL`           | `modern`          | Multisite | nein     | Sicherheitsniveau der Suiten (`modern`, `intermediate`, `old`).                                                                            |
| `SSL_CIPHERS_CUSTOM`          |                   | Multisite | nein     | Benutzerdefinierte Suiten (durch `:` getrennte Liste), die das Niveau ersetzen.                                                            |
| `SSL_ECDH_CURVE`              | `auto`            | Multisite | nein     | **SSL-ECDH-Kurven:** Durch `:` getrennte Liste von ECDH-Kurven (TLS-Gruppen) oder `auto` fuer intelligente Auswahl (PQC mit OpenSSL 3.5+). |
| `SSL_SESSION_CACHE_SIZE`      | `10m`             | Multisite | nein     | Größe des SSL-Sitzungscaches (z.B. `10m`, `512k`). Auf `off` oder `none` setzen zum Deaktivieren.                                          |

!!! tip "SSL Labs Test"
    Testen Sie Ihre Konfiguration über [Qualys SSL Labs](https://www.ssllabs.com/ssltest/). Eine gut eingestellte BunkerWeb-Konfiguration erreicht in der Regel A+.

!!! warning "Veraltete Protokolle"
    SSLv3, TLSv1.0 und TLSv1.1 sind standardmäßig deaktiviert (bekannte Schwachstellen). Aktivieren Sie diese nur bei Bedarf für ältere Clients.

### Beispiele

=== "Moderne Sicherheit (Standard)"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Maximale Sicherheit"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

=== "Legacy-Kompatibilität"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "old"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Benutzerdefinierte Suiten"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_CUSTOM: "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

## Security.txt

STREAM-Unterstützung :white_check_mark:

Das Security.txt-Plugin implementiert den [Security.txt](https://securitytxt.org/)-Standard ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116)) für Ihre Website. Diese Funktion erleichtert Sicherheitsforschern den Zugriff auf Ihre Sicherheitsrichtlinien und bietet eine standardisierte Möglichkeit, Sicherheitslücken zu melden, die sie in Ihren Systemen entdecken.

**So funktioniert es:**

1.  Nach der Aktivierung erstellt BunkerWeb eine `/.well-known/security.txt`-Datei im Stammverzeichnis Ihrer Website.
2.  Diese Datei enthält Informationen zu Ihren Sicherheitsrichtlinien, Kontakten und anderen relevanten Details.
3.  Sicherheitsforscher und automatisierte Tools können diese Datei leicht am Standardort finden.
4.  Der Inhalt wird über einfache Einstellungen konfiguriert, mit denen Sie Kontaktinformationen, Verschlüsselungsschlüssel, Richtlinien und Danksagungen angeben können.
5.  BunkerWeb formatiert die Datei automatisch gemäß RFC 9116.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Security.txt-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Setzen Sie die Einstellung `USE_SECURITYTXT` auf `yes`, um die security.txt-Datei zu aktivieren.
2.  **Kontaktinformationen konfigurieren:** Geben Sie mindestens eine Kontaktmethode mit der Einstellung `SECURITYTXT_CONTACT` an.
3.  **Zusätzliche Informationen festlegen:** Konfigurieren Sie optionale Felder wie Ablaufdatum, Verschlüsselung, Danksagungen und Richtlinien-URLs.
4.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration erstellt und stellt BunkerWeb die security.txt-Datei automatisch am Standardort bereit.

### Konfigurationseinstellungen

| Einstellung                    | Standard                    | Kontext   | Mehrfach | Beschreibung                                                                                                                    |
| ------------------------------ | --------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `USE_SECURITYTXT`              | `no`                        | multisite | nein     | **Security.txt aktivieren:** Auf `yes` setzen, um die security.txt-Datei zu aktivieren.                                         |
| `SECURITYTXT_URI`              | `/.well-known/security.txt` | multisite | nein     | **Security.txt-URI:** Gibt die URI an, unter der die security.txt-Datei zugänglich sein wird.                                   |
| `SECURITYTXT_CONTACT`          |                             | multisite | ja       | **Kontaktinformationen:** Wie Sicherheitsforscher Sie kontaktieren können (z. B. `mailto:security@example.com`).                |
| `SECURITYTXT_EXPIRES`          |                             | multisite | nein     | **Ablaufdatum:** Wann diese security.txt-Datei als abgelaufen betrachtet werden soll (ISO 8601-Format).                         |
| `SECURITYTXT_ENCRYPTION`       |                             | multisite | ja       | **Verschlüsselung:** URL, die auf Verschlüsselungsschlüssel für die sichere Kommunikation verweist.                             |
| `SECURITYTXT_ACKNOWLEDGEMENTS` |                             | multisite | ja       | **Danksagungen:** URL, unter der Sicherheitsforscher für ihre Berichte anerkannt werden.                                        |
| `SECURITYTXT_POLICY`           |                             | multisite | ja       | **Sicherheitsrichtlinie:** URL, die auf die Sicherheitsrichtlinie verweist, die beschreibt, wie Schwachstellen gemeldet werden. |
| `SECURITYTXT_HIRING`           |                             | multisite | ja       | **Sicherheitsjobs:** URL, die auf sicherheitsrelevante Stellenangebote verweist.                                                |
| `SECURITYTXT_CANONICAL`        |                             | multisite | ja       | **Kanonische URL:** Die kanonische(n) URI(s) für diese security.txt-Datei.                                                      |
| `SECURITYTXT_PREFERRED_LANG`   | `en`                        | multisite | nein     | **Bevorzugte Sprache:** Die in der Kommunikation verwendete(n) Sprache(n). Angegeben als ISO 639-1-Sprachcode.                  |
| `SECURITYTXT_CSAF`             |                             | multisite | ja       | **CSAF:** Link zur provider-metadata.json Ihres Common Security Advisory Framework-Anbieters.                                   |

!!! warning "Ablaufdatum erforderlich"
    Gemäß RFC 9116 ist das Feld `Expires` erforderlich. Wenn Sie keinen Wert für `SECURITYTXT_EXPIRES` angeben, setzt BunkerWeb das Ablaufdatum automatisch auf ein Jahr ab dem aktuellen Datum.

!!! info "Kontaktinformationen sind unerlässlich"
    Das Feld `Contact` ist der wichtigste Teil der security.txt-Datei. Sie sollten mindestens eine Möglichkeit für Sicherheitsforscher angeben, Sie zu kontaktieren. Dies kann eine E-Mail-Adresse, ein Webformular, eine Telefonnummer oder eine andere Methode sein, die für Ihre Organisation funktioniert.

!!! warning "URLs müssen HTTPS verwenden"
    Gemäß RFC 9116 MÜSSEN alle URLs in der security.txt-Datei (außer `mailto:`- und `tel:`-Links) HTTPS verwenden. Nicht-HTTPS-URLs werden von BunkerWeb automatisch in HTTPS konvertiert, um die Einhaltung des Standards zu gewährleisten.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine minimale Konfiguration mit nur Kontaktinformationen:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    ```

=== "Umfassende Konfiguration"

    Eine vollständigere Konfiguration mit allen Feldern:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "https://example.com/security-contact-form"
    SECURITYTXT_EXPIRES: "2023-12-31T23:59:59+00:00"
    SECURITYTXT_ENCRYPTION: "https://example.com/pgp-key.txt"
    SECURITYTXT_ACKNOWLEDGEMENTS: "https://example.com/hall-of-fame"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_HIRING: "https://example.com/jobs/security"
    SECURITYTXT_CANONICAL: "https://example.com/.well-known/security.txt"
    SECURITYTXT_PREFERRED_LANG: "en"
    SECURITYTXT_CSAF: "https://example.com/provider-metadata.json"
    ```

=== "Konfiguration mit mehreren Kontakten"

    Konfiguration mit mehreren Kontaktmethoden:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "tel:+1-201-555-0123"
    SECURITYTXT_CONTACT_3: "https://example.com/security-form"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_EXPIRES: "2024-06-30T23:59:59+00:00"
    ```

## Self-signed certificate

STREAM-Unterstützung :white_check_mark:

Das Plugin "Selbstsigniertes Zertifikat" generiert und verwaltet automatisch SSL/TLS-Zertifikate direkt in BunkerWeb, um HTTPS ohne externe Zertifizierungsstelle zu aktivieren. Ideal für die Entwicklung, interne Netzwerke oder schnelle HTTPS-Bereitstellungen.

So funktioniert's:

1.  Nach der Aktivierung generiert BunkerWeb ein selbstsigniertes Zertifikat für Ihre konfigurierten Domains.
2.  Das Zertifikat enthält alle definierten Servernamen, um eine korrekte Validierung zu gewährleisten.
3.  Die Zertifikate werden sicher gespeichert und verschlüsseln den gesamten HTTPS-Verkehr.
4.  Die Verlängerung erfolgt automatisch vor dem Ablaufdatum.

!!! warning "Browser-Warnungen"
    Browser zeigen Sicherheitswarnungen an, da ein selbstsigniertes Zertifikat nicht von einer vertrauenswürdigen CA ausgestellt wurde. Verwenden Sie in der Produktion vorzugsweise [Let's Encrypt](#lets-encrypt).

### Verwendung

1.  Aktivieren: `GENERATE_SELF_SIGNED_SSL: yes`.
2.  Algorithmus: Wählen Sie über `SELF_SIGNED_SSL_ALGORITHM`.
3.  Gültigkeit: Dauer in Tagen über `SELF_SIGNED_SSL_EXPIRY`.
4.  Betreff: Betrefffeld über `SELF_SIGNED_SSL_SUBJ`.

!!! tip "Stream-Modus"
    Im Stream-Modus konfigurieren Sie `LISTEN_STREAM_PORT_SSL`, um den SSL/TLS-Listening-Port zu definieren.

### Parameter

| Parameter                   | Standard               | Kontext   | Mehrfach | Beschreibung                                                          |
| :-------------------------- | :--------------------- | :-------- | :------- | :-------------------------------------------------------------------- |
| `GENERATE_SELF_SIGNED_SSL`  | `no`                   | Multisite | nein     | Aktiviert die automatische Generierung selbstsignierter Zertifikate.  |
| `SELF_SIGNED_SSL_ALGORITHM` | `ec-prime256v1`        | Multisite | nein     | Algorithmus: `ec-prime256v1`, `ec-secp384r1`, `rsa-2048`, `rsa-4096`. |
| `SELF_SIGNED_SSL_EXPIRY`    | `365`                  | Multisite | nein     | Gültigkeit (Tage).                                                    |
| `SELF_SIGNED_SSL_SUBJ`      | `/CN=www.example.com/` | Multisite | nein     | Betreff des Zertifikats (identifiziert die Domain).                   |

### Beispiele

=== "Standard"

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=mysite.local/"
    ```

=== "Kurzzeit-Zertifikate"

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "90"
    SELF_SIGNED_SSL_SUBJ: "/CN=dev.example.com/"
    ```

=== "Test in RSA"

    ```yaml
    SERVER_NAME: "test.example.com"
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "rsa-4096"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=test.example.com/"
    ```

## Sessions

STREAM-Unterstützung :white_check_mark:

Das Sessions-Plugin bietet eine robuste HTTP-Sitzungsverwaltung für BunkerWeb und ermöglicht eine sichere und zuverlässige Verfolgung von Benutzersitzungen über Anfragen hinweg. Diese Kernfunktion ist unerlässlich für die Aufrechterhaltung des Benutzerstatus, die Persistenz der Authentifizierung und die Unterstützung anderer Funktionen, die eine Kontinuität der Identität erfordern, wie z. B. der [Anti-Bot-Schutz](#antibot) und Benutzerauthentifizierungssysteme.

**So funktioniert es:**

1.  Wenn ein Benutzer zum ersten Mal mit Ihrer Website interagiert, erstellt BunkerWeb eine eindeutige Sitzungs-ID.
2.  Diese ID wird sicher in einem Cookie im Browser des Benutzers gespeichert.
3.  Bei nachfolgenden Anfragen ruft BunkerWeb die Sitzungs-ID aus dem Cookie ab und verwendet sie, um auf die Sitzungsdaten des Benutzers zuzugreifen.
4.  Sitzungsdaten können lokal oder in [Redis](#redis) für verteilte Umgebungen mit mehreren BunkerWeb-Instanzen gespeichert werden.
5.  Sitzungen werden automatisch mit konfigurierbaren Zeitüberschreitungen verwaltet, um die Sicherheit bei gleichzeitiger Benutzerfreundlichkeit zu gewährleisten.
6.  Die kryptografische Sicherheit von Sitzungen wird durch einen geheimen Schlüssel gewährleistet, der zum Signieren von Sitzungs-Cookies verwendet wird.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Sessions-Funktion zu konfigurieren und zu verwenden:

1.  **Sitzungssicherheit konfigurieren:** Legen Sie einen starken, eindeutigen `SESSIONS_SECRET` fest, um sicherzustellen, dass Sitzungs-Cookies nicht gefälscht werden können. (Der Standardwert ist "random", wodurch BunkerWeb einen zufälligen geheimen Schlüssel generiert.)
2.  **Sitzungsnamen wählen:** Passen Sie optional den `SESSIONS_NAME` an, um zu definieren, wie Ihr Sitzungs-Cookie im Browser heißen soll. (Der Standardwert ist "random", wodurch BunkerWeb einen zufälligen Namen generiert.)
3.  **Sitzungs-Timeouts festlegen:** Konfigurieren Sie mit den Timeout-Einstellungen (`SESSIONS_IDLING_TIMEOUT`, `SESSIONS_ROLLING_TIMEOUT`, `SESSIONS_ABSOLUTE_TIMEOUT`), wie lange Sitzungen gültig bleiben.
4.  **Redis-Integration konfigurieren:** Setzen Sie für verteilte Umgebungen `USE_REDIS` auf "yes" und konfigurieren Sie Ihre [Redis-Verbindung](#redis), um Sitzungsdaten über mehrere BunkerWeb-Knoten hinweg zu teilen.
5.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration erfolgt die Sitzungsverwaltung für Ihre Website automatisch.

### Konfigurationseinstellungen

| Einstellung                 | Standard | Kontext | Mehrfach | Beschreibung                                                                                                                                                               |
| --------------------------- | -------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SESSIONS_SECRET`           | `random` | global  | nein     | **Sitzungsgeheimnis:** Kryptografischer Schlüssel zum Signieren von Sitzungs-Cookies. Sollte eine starke, zufällige Zeichenfolge sein, die für Ihre Website eindeutig ist. |
| `SESSIONS_NAME`             | `random` | global  | nein     | **Cookie-Name:** Der Name des Cookies, in dem die Sitzungs-ID gespeichert wird.                                                                                            |
| `SESSIONS_IDLING_TIMEOUT`   | `1800`   | global  | nein     | **Leerlauf-Timeout:** Maximale Zeit (in Sekunden) der Inaktivität, bevor die Sitzung ungültig wird.                                                                        |
| `SESSIONS_ROLLING_TIMEOUT`  | `3600`   | global  | nein     | **Rollierendes Timeout:** Maximale Zeit (in Sekunden), bevor eine Sitzung erneuert werden muss.                                                                            |
| `SESSIONS_ABSOLUTE_TIMEOUT` | `86400`  | global  | nein     | **Absolutes Timeout:** Maximale Zeit (in Sekunden), bevor eine Sitzung unabhängig von der Aktivität zerstört wird.                                                         |
| `SESSIONS_CHECK_IP`         | `yes`    | global  | nein     | **IP prüfen:** Wenn auf `yes` gesetzt, wird die Sitzung zerstört, wenn sich die IP-Adresse des Clients ändert.                                                             |
| `SESSIONS_CHECK_USER_AGENT` | `yes`    | global  | nein     | **User-Agent prüfen:** Wenn auf `yes` gesetzt, wird die Sitzung zerstört, wenn sich der User-Agent des Clients ändert.                                                     |

!!! warning "Sicherheitshinweise"
    Die Einstellung `SESSIONS_SECRET` ist für die Sicherheit von entscheidender Bedeutung. In Produktionsumgebungen:

    1. Verwenden Sie einen starken, zufälligen Wert (mindestens 32 Zeichen)
    2. Halten Sie diesen Wert vertraulich
    3. Verwenden Sie denselben Wert für alle BunkerWeb-Instanzen in einem Cluster
    4. Erwägen Sie die Verwendung von Umgebungsvariablen oder Geheimnisverwaltung, um die Speicherung im Klartext zu vermeiden

!!! tip "Cluster-Umgebungen"
    Wenn Sie mehrere BunkerWeb-Instanzen hinter einem Load Balancer betreiben:

    1. Setzen Sie `USE_REDIS` auf `yes` und konfigurieren Sie Ihre Redis-Verbindung
    2. Stellen Sie sicher, dass alle Instanzen genau denselben `SESSIONS_SECRET` und `SESSIONS_NAME` verwenden
    3. Dies stellt sicher, dass Benutzer ihre Sitzung beibehalten, unabhängig davon, welche BunkerWeb-Instanz ihre Anfragen bearbeitet

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine einfache Konfiguration für eine einzelne BunkerWeb-Instanz:

    ```yaml
    SESSIONS_SECRET: "ihr-starker-zufälliger-geheimschlüssel-hier"
    SESSIONS_NAME: "meineappsitzung"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    ```

=== "Erhöhte Sicherheit"

    Konfiguration mit erhöhten Sicherheitseinstellungen:

    ```yaml
    SESSIONS_SECRET: "ihr-sehr-starker-zufälliger-geheimschlüssel-hier"
    SESSIONS_NAME: "sicheresitzung"
    SESSIONS_IDLING_TIMEOUT: "900"  # 15 Minuten
    SESSIONS_ROLLING_TIMEOUT: "1800"  # 30 Minuten
    SESSIONS_ABSOLUTE_TIMEOUT: "43200"  # 12 Stunden
    SESSIONS_CHECK_IP: "yes"
    SESSIONS_CHECK_USER_AGENT: "yes"
    ```

=== "Cluster-Umgebung mit Redis"

    Konfiguration für mehrere BunkerWeb-Instanzen, die Sitzungsdaten gemeinsam nutzen:

    ```yaml
    SESSIONS_SECRET: "ihr-starker-zufälliger-geheimschlüssel-hier"
    SESSIONS_NAME: "clustersitzung"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    USE_REDIS: "yes"
    # Stellen Sie sicher, dass die Redis-Verbindung korrekt konfiguriert ist
    ```

=== "Langlebige Sitzungen"

    Konfiguration für Anwendungen, die eine erweiterte Sitzungspersistenz erfordern:

    ```yaml
    SESSIONS_SECRET: "ihr-starker-zufälliger-geheimschlüssel-hier"
    SESSIONS_NAME: "persistentesitzung"
    SESSIONS_IDLING_TIMEOUT: "86400"  # 1 Tag
    SESSIONS_ROLLING_TIMEOUT: "172800"  # 2 Tage
    SESSIONS_ABSOLUTE_TIMEOUT: "604800"  # 7 Tage
    ```

## UI

STREAM-Unterstützung :x:

Integrate easily the BunkerWeb UI.

| Einstellung | Standardwert | Kontext   | Mehrfach | Beschreibung                                 |
| ----------- | ------------ | --------- | -------- | -------------------------------------------- |
| `USE_UI`    | `no`         | multisite | nein     | Use UI                                       |
| `UI_HOST`   |              | global    | nein     | Address of the web UI used for initial setup |

## User Manager <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


<p align='center'><iframe style='display: block;' width='560' height='315' data-src='https://www.youtube-nocookie.com/embed/EIohiUf9Fg4' title='Benutzer-Manager' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe></p>

STREAM-Unterstützung :x:

Add the possibility to manage users on the web interface

| Einstellung         | Standardwert | Kontext | Mehrfach | Beschreibung                                    |
| ------------------- | ------------ | ------- | -------- | ----------------------------------------------- |
| `USERS_REQUIRE_2FA` | `no`         | global  | nein     | Require two-factor authentication for all users |

## Whitelist

STREAM-Unterstützung :warning:

Das Whitelist-Plugin ermöglicht es Ihnen, eine Liste vertrauenswürdiger IP-Adressen zu definieren, die andere Sicherheitsfilter umgehen.
Um stattdessen unerwünschte Clients zu blockieren, lesen Sie das [Blacklist-Plugin](#blacklist).

Das Whitelist-Plugin bietet einen umfassenden Ansatz, um den Zugriff auf Ihre Website basierend auf verschiedenen Client-Attributen explizit zu erlauben. Diese Funktion bietet einen Sicherheitsmechanismus: Besuchern, die bestimmte Kriterien erfüllen, wird sofortiger Zugriff gewährt, während alle anderen reguläre Sicherheitsprüfungen durchlaufen müssen.

**So funktioniert es:**

1.  Sie definieren Kriterien für Besucher, die auf die "Whitelist" gesetzt werden sollen (_IP-Adressen, Netzwerke, rDNS, ASN, User-Agent oder URI-Muster_).
2.  Wenn ein Besucher versucht, auf Ihre Website zuzugreifen, prüft BunkerWeb, ob er einem dieser Whitelist-Kriterien entspricht.
3.  Wenn ein Besucher einer Whitelist-Regel entspricht (und keiner Ignorier-Regel), wird ihm der Zugriff auf Ihre Website gewährt und er **umgeht alle anderen Sicherheitsprüfungen**.
4.  Wenn ein Besucher keinem Whitelist-Kriterium entspricht, durchläuft er wie gewohnt alle normalen Sicherheitsprüfungen.
5.  Whitelists können in regelmäßigen Abständen automatisch aus externen Quellen aktualisiert werden.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Whitelist-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die Whitelist-Funktion ist standardmäßig deaktiviert. Setzen Sie die Einstellung `USE_WHITELIST` auf `yes`, um sie zu aktivieren.
2.  **Erlaubnisregeln konfigurieren:** Definieren Sie, welche IPs, Netzwerke, rDNS-Muster, ASNs, User-Agents oder URIs auf die Whitelist gesetzt werden sollen.
3.  **Ignorierregeln einrichten:** Geben Sie alle Ausnahmen an, die die Whitelist-Prüfungen umgehen sollen.
4.  **Externe Quellen hinzufügen:** Konfigurieren Sie URLs zum automatischen Herunterladen und Aktualisieren von Whitelist-Daten.
5.  **Zugriff überwachen:** Überprüfen Sie die [Web-Benutzeroberfläche](web-ui.md), um zu sehen, welchen Besuchern der Zugriff gewährt oder verweigert wird.

!!! info "Stream-Modus"
    Im Stream-Modus werden nur IP-, rDNS- und ASN-Prüfungen durchgeführt.

### Konfigurationseinstellungen

**Allgemein**

| Einstellung     | Standard | Kontext   | Mehrfach | Beschreibung                                                                         |
| --------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------ |
| `USE_WHITELIST` | `no`     | multisite | nein     | **Whitelist aktivieren:** Auf `yes` setzen, um die Whitelist-Funktion zu aktivieren. |

=== "IP-Adresse"
    **Was dies bewirkt:** Setzt Besucher basierend auf ihrer IP-Adresse oder ihrem Netzwerk auf die Whitelist. Diese Besucher umgehen alle Sicherheitsprüfungen.

    | Einstellung                | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                              |
    | -------------------------- | -------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_IP`             |          | multisite | nein     | **IP-Whitelist:** Liste von IP-Adressen oder Netzwerken (CIDR-Notation), die erlaubt werden sollen, getrennt durch Leerzeichen.                           |
    | `WHITELIST_IGNORE_IP`      |          | multisite | nein     | **IP-Ignorierliste:** Liste von IP-Adressen oder Netzwerken, die IP-Whitelist-Prüfungen umgehen sollen.                                                   |
    | `WHITELIST_IP_URLS`        |          | multisite | nein     | **IP-Whitelist-URLs:** Liste von URLs, die IP-Adressen oder Netzwerke enthalten, die auf die Whitelist gesetzt werden sollen, getrennt durch Leerzeichen. |
    | `WHITELIST_IGNORE_IP_URLS` |          | multisite | nein     | **IP-Ignorierlisten-URLs:** Liste von URLs, die IP-Adressen oder Netzwerke enthalten, die ignoriert werden sollen.                                        |

=== "Reverse DNS"
    **Was dies bewirkt:** Setzt Besucher basierend auf ihrem Domainnamen (in umgekehrter Reihenfolge) auf die Whitelist. Dies ist nützlich, um Besuchern von bestimmten Organisationen oder Netzwerken den Zugriff nach ihrer Domain zu ermöglichen.

    | Einstellung                  | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                         |
    | ---------------------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_RDNS`             |          | multisite | nein     | **rDNS-Whitelist:** Liste von Reverse-DNS-Suffixen, die erlaubt werden sollen, getrennt durch Leerzeichen.                                           |
    | `WHITELIST_RDNS_GLOBAL`      | `yes`    | multisite | nein     | **Nur globales rDNS:** Führt rDNS-Whitelist-Prüfungen nur für globale IP-Adressen durch, wenn auf `yes` gesetzt.                                     |
    | `WHITELIST_IGNORE_RDNS`      |          | multisite | nein     | **rDNS-Ignorierliste:** Liste von Reverse-DNS-Suffixen, die rDNS-Whitelist-Prüfungen umgehen sollen.                                                 |
    | `WHITELIST_RDNS_URLS`        |          | multisite | nein     | **rDNS-Whitelist-URLs:** Liste von URLs, die Reverse-DNS-Suffixe enthalten, die auf die Whitelist gesetzt werden sollen, getrennt durch Leerzeichen. |
    | `WHITELIST_IGNORE_RDNS_URLS` |          | multisite | nein     | **rDNS-Ignorierlisten-URLs:** Liste von URLs, die Reverse-DNS-Suffixe enthalten, die ignoriert werden sollen.                                        |

=== "ASN"
    **Was dies bewirkt:** Setzt Besucher von bestimmten Netzwerkanbietern mithilfe von Autonomen Systemnummern auf die Whitelist. ASNs identifizieren, zu welchem Anbieter oder welcher Organisation eine IP gehört.

    | Einstellung                 | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                         |
    | --------------------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
    | `WHITELIST_ASN`             |          | multisite | nein     | **ASN-Whitelist:** Liste von Autonomen Systemnummern, die erlaubt werden sollen, getrennt durch Leerzeichen.                         |
    | `WHITELIST_IGNORE_ASN`      |          | multisite | nein     | **ASN-Ignorierliste:** Liste von ASNs, die ASN-Whitelist-Prüfungen umgehen sollen.                                                   |
    | `WHITELIST_ASN_URLS`        |          | multisite | nein     | **ASN-Whitelist-URLs:** Liste von URLs, die ASNs enthalten, die auf die Whitelist gesetzt werden sollen, getrennt durch Leerzeichen. |
    | `WHITELIST_IGNORE_ASN_URLS` |          | multisite | nein     | **ASN-Ignorierlisten-URLs:** Liste von URLs, die ASNs enthalten, die ignoriert werden sollen.                                        |

=== "User-Agent"
    **Was dies bewirkt:** Setzt Besucher basierend darauf auf die Whitelist, welchen Browser oder welches Tool sie angeben zu verwenden. Dies ist effektiv, um den Zugriff auf bestimmte bekannte Tools oder Dienste zu ermöglichen.

    | Einstellung                        | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                 |
    | ---------------------------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_USER_AGENT`             |          | multisite | nein     | **User-Agent-Whitelist:** Liste von User-Agent-Mustern (PCRE-Regex), die erlaubt werden sollen, getrennt durch Leerzeichen.  |
    | `WHITELIST_IGNORE_USER_AGENT`      |          | multisite | nein     | **User-Agent-Ignorierliste:** Liste von User-Agent-Mustern, die User-Agent-Whitelist-Prüfungen umgehen sollen.               |
    | `WHITELIST_USER_AGENT_URLS`        |          | multisite | nein     | **User-Agent-Whitelist-URLs:** Liste von URLs, die User-Agent-Muster enthalten, die auf die Whitelist gesetzt werden sollen. |
    | `WHITELIST_IGNORE_USER_AGENT_URLS` |          | multisite | nein     | **User-Agent-Ignorierlisten-URLs:** Liste von URLs, die User-Agent-Muster enthalten, die ignoriert werden sollen.            |

=== "URI"
    **Was dies bewirkt:** Setzt Anfragen an bestimmte URLs auf Ihrer Website auf die Whitelist. Dies ist hilfreich, um den Zugriff auf bestimmte Endpunkte unabhängig von anderen Faktoren zu ermöglichen.

    | Einstellung                 | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                               |
    | --------------------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
    | `WHITELIST_URI`             |          | multisite | nein     | **URI-Whitelist:** Liste von URI-Mustern (PCRE-Regex), die erlaubt werden sollen, getrennt durch Leerzeichen.                              |
    | `WHITELIST_IGNORE_URI`      |          | multisite | nein     | **URI-Ignorierliste:** Liste von URI-Mustern, die URI-Whitelist-Prüfungen umgehen sollen.                                                  |
    | `WHITELIST_URI_URLS`        |          | multisite | nein     | **URI-Whitelist-URLs:** Liste von URLs, die URI-Muster enthalten, die auf die Whitelist gesetzt werden sollen, getrennt durch Leerzeichen. |
    | `WHITELIST_IGNORE_URI_URLS` |          | multisite | nein     | **URI-Ignorierlisten-URLs:** Liste von URLs, die URI-Muster enthalten, die ignoriert werden sollen.                                        |

!!! info "Unterstützung von URL-Formaten"
    Alle `*_URLS`-Einstellungen unterstützen HTTP/HTTPS-URLs sowie lokale Dateipfade mit dem Präfix `file:///`. Die Basisauthentifizierung wird im Format `http://user:pass@url` unterstützt.

!!! tip "Regelmäßige Aktualisierungen"
    Whitelists von URLs werden stündlich automatisch heruntergeladen und aktualisiert, um sicherzustellen, dass Ihr Schutz mit den neuesten vertrauenswürdigen Quellen auf dem neuesten Stand bleibt.

!!! warning "Sicherheitsumgehung"
    Auf der Whitelist stehende Besucher **umgehen vollständig alle anderen Sicherheitsprüfungen** in BunkerWeb, einschließlich WAF-Regeln, Ratenbegrenzung, Erkennung bösartiger Bots und aller anderen Sicherheitsmechanismen. Verwenden Sie die Whitelist nur für vertrauenswürdige Quellen, bei denen Sie absolut sicher sind.

### Beispielkonfigurationen

=== "Grundlegender Organisationszugriff"

    Eine einfache Konfiguration, die die IP-Adressen des Unternehmensbüros auf die Whitelist setzt:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP: "192.168.1.0/24 10.0.0.0/8 203.0.113.42"
    ```

=== "Erweiterte Konfiguration"

    Eine umfassendere Konfiguration mit mehreren Whitelist-Kriterien:

    ```yaml
    USE_WHITELIST: "yes"

    # Unternehmens- und vertrauenswürdige Partner-Assets
    WHITELIST_IP: "192.168.1.0/24 203.0.113.0/24"
    WHITELIST_RDNS: ".company.com .partner-company.org"
    WHITELIST_ASN: "12345 67890"  # ASNs von Unternehmen und Partnern
    WHITELIST_USER_AGENT: "(?:\b)CompanyBot(?:\b) (?:\b)PartnerCrawler(?:\b)"

    # Externe vertrauenswürdige Quellen
    WHITELIST_IP_URLS: "https://example.com/trusted-networks.txt"
    WHITELIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Verwendung lokaler Dateien"

    Konfiguration mit lokalen Dateien für Whitelists:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP_URLS: "file:///path/to/ip-whitelist.txt"
    WHITELIST_RDNS_URLS: "file:///path/to/rdns-whitelist.txt"
    WHITELIST_ASN_URLS: "file:///path/to/asn-whitelist.txt"
    WHITELIST_USER_AGENT_URLS: "file:///path/to/user-agent-whitelist.txt"
    WHITELIST_URI_URLS: "file:///path/to/uri-whitelist.txt"
    ```

=== "API-Zugriffsmuster"

    Eine Konfiguration, die sich darauf konzentriert, den Zugriff nur auf bestimmte API-Endpunkte zu ermöglichen:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_URI: "^/api/v1/public/ ^/api/v1/status"
    WHITELIST_IP: "192.168.1.0/24"  # Internes Netzwerk für alle Endpunkte
    ```

=== "Bekannte Crawler"

    Eine Konfiguration, die gängige Suchmaschinen- und Social-Media-Crawler auf die Whitelist setzt:

    ```yaml
    USE_WHITELIST: "yes"

    # Verifizierung mit Reverse DNS für zusätzliche Sicherheit
    WHITELIST_RDNS: ".googlebot.com .search.msn.com .crawl.yahoo.net .yandex.com .baidu.com .facebook.com"
    WHITELIST_RDNS_GLOBAL: "yes"  # Nur globale IPs prüfen
    ```

    Diese Konfiguration ermöglicht es legitimen Crawlern, Ihre Website zu indizieren, ohne Ratenbegrenzungen oder anderen Sicherheitsmaßnahmen unterworfen zu sein, die sie blockieren könnten. Die rDNS-Prüfungen helfen zu überprüfen, ob die Crawler tatsächlich von den von ihnen angegebenen Unternehmen stammen.

### Arbeiten mit lokalen Listendateien

Die `*_URLS`-Einstellungen der Whitelist-, Greylist- und Blacklist-Plugins verwenden denselben Downloader. Wenn Sie eine `file:///`-URL angeben:

- Der Pfad wird innerhalb des **Scheduler**-Containers aufgelöst (bei Docker-Bereitstellungen in der Regel `bunkerweb-scheduler`). Binden Sie die Dateien dort ein und stellen Sie sicher, dass der Scheduler-Benutzer Lesezugriff hat.
- Jede Datei ist eine UTF-8-codierte Textdatei mit einem Eintrag pro Zeile. Leere Zeilen werden ignoriert und Kommentarzeilen müssen mit `#` oder `;` beginnen. `//`-Kommentare werden nicht unterstützt.
- Erwartete Werte je Listentyp:
  - **IP-Listen** akzeptieren IPv4/IPv6-Adressen oder CIDR-Netzwerke (z. B. `192.0.2.10` oder `2001:db8::/48`).
  - **rDNS-Listen** erwarten ein Suffix ohne Leerzeichen (z. B. `.search.msn.com`). Werte werden automatisch in Kleinbuchstaben umgewandelt.
  - **ASN-Listen** können nur die Nummer (`32934`) oder die mit `AS` vorangestellte Nummer (`AS15169`) enthalten.
  - **User-Agent-Listen** werden als PCRE-Muster behandelt und die vollständige Zeile bleibt erhalten (einschließlich Leerzeichen). Schreiben Sie Kommentare in eine eigene Zeile, damit sie nicht als Muster interpretiert werden.
  - **URI-Listen** müssen mit `/` beginnen und dürfen PCRE-Tokens wie `^` oder `$` verwenden.

Beispieldateien im erwarteten Format:

```text
# /etc/bunkerweb/lists/ip-whitelist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-whitelist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
