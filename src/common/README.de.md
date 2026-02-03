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

    | Einstellung       | Standard | Kontext   | Mehrfach | Beschreibung                                                                                               |
    | ----------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------- |
    | `AUTOCONF_MODE`   | `no`     | global    | Nein     | **Autoconf-Modus:** Autoconf-Docker-Integration aktivieren.                                                |
    | `SWARM_MODE`      | `no`     | global    | Nein     | **Swarm-Modus:** Docker-Swarm-Integration aktivieren.                                                      |
    | `KUBERNETES_MODE` | `no`     | global    | Nein     | **Kubernetes-Modus:** Kubernetes-Integration aktivieren.                                                   |
    | `KEEP_CONFIG_ON_RESTART` | `no` | global | Nein | **Konfiguration bei Neustart behalten:** Konfiguration bei Neustart beibehalten. Auf 'yes' setzen, um das Zurücksetzen der Konfiguration beim Neustart zu verhindern. |
    | `USE_TEMPLATE`    |          | multisite | Nein     | **Vorlage verwenden:** Konfigurationsvorlage, die die Standardwerte bestimmter Einstellungen überschreibt. |

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
