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
        image: bunkerity/bunkerweb:1.6.8-rc3
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
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
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
