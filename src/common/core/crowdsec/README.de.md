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
    appsec_configs:
      - crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    `appsec_configs` (Plural) ist eine Liste und ergänzt: Weitere AppSec-Konfigurationen erweitern `appsec-default`, statt es zu ersetzen. Das einzelne `appsec_config` nimmt nur einen Namen entgegen und lässt sich nicht mit dem Plural-Schlüssel kombinieren — verwenden Sie die Plural-Form, wenn Sie die Bot-Erkennung aktivieren möchten.

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
        image: bunkerity/bunkerweb:1.7.0-beta
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
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
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
        image: crowdsecurity/crowdsec:v1.7.8 # Verwenden Sie die neueste Version, aber pinnen Sie immer die Version für bessere Stabilität/Sicherheit
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
    appsec_configs:
      - crowdsecurity/appsec-default
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

Wenden Sie die folgenden Umgebungsvariablen (oder Scheduler-Werte) an, damit die BunkerWeb-Instanz mit der CrowdSec Local API kommunizieren kann. Mindestens `USE_CROWDSEC`, `CROWDSEC_API` und `CROWDSEC_API_KEY` mit einem gültigen per `cscli bouncers add` erzeugten Schlüssel werden benötigt.

| Parameter                   | Standardwert           | Kontext   | Mehrfach | Beschreibung                                                                                                                             |
| --------------------------- | ---------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | no       | **CrowdSec aktivieren:** Auf `yes` setzen, um den CrowdSec-Bouncer zu aktivieren.                                                        |
| `CROWDSEC_API`              | `http://crowdsec:8080` | multisite    | no       | **CrowdSec API URL:** Die Adresse des lokalen CrowdSec API-Dienstes.                                                                     |
| `CROWDSEC_API_KEY`          |                        | multisite    | no       | **CrowdSec API-Schlüssel:** Der API-Schlüssel zur Authentifizierung bei der CrowdSec-API, erhalten mit `cscli bouncers add`.             |
| `CROWDSEC_MODE`             | `live`                 | multisite    | no       | **Betriebsmodus:** Entweder `live` (fragt die API für jede Anfrage ab) oder `stream` (cacht alle Entscheidungen periodisch).             |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | multisite    | no       | **Interner Traffic:** Auf `yes` setzen, um den internen Traffic anhand der CrowdSec-Entscheidungen zu überprüfen.                        |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | multisite    | no       | **Anfrage-Timeout:** Timeout in Millisekunden für HTTP-Anfragen an die lokale CrowdSec-API im Live-Modus.                                |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | multisite    | no       | **Ausgeschlossene Orte:** Kommagetrennte Liste von Orten (URIs), die von CrowdSec-Prüfungen ausgeschlossen werden sollen.                |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | multisite    | no       | **Cache-Ablauf:** Die Cache-Ablaufzeit in Sekunden für IP-Entscheidungen im Live-Modus.                                                  |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | multisite    | no       | **Update-Frequenz:** Wie oft (in Sekunden) neue/abgelaufene Entscheidungen von der CrowdSec-API im Stream-Modus abgerufen werden sollen. |

!!! info "Wie `CROWDSEC_EXCLUDE_LOCATION` vergleicht"
    Jeder durch Komma getrennte Eintrag schließt die URI selbst **und alles darunter** aus: `/health` überspringt `/health` und `/health/live`, aber nicht `/healthcheck` — vor dem restlichen Pfad ist immer ein Trennzeichen erforderlich. Der Ausschluss ist vollständig: Eine ausgeschlossene Anfrage erreicht weder die Local API noch die AppSec-Komponente. Schließen Sie deshalb keinen Pfad aus, den Sie weiterhin prüfen lassen wollen. Schließen Sie insbesondere niemals `/crowdsec-internal` aus: Die Bot-Erkennung liefert ihre Challenge-Ressourcen von dort aus, und ein Ausschluss deaktiviert die Challenge stillschweigend.

#### Parameter der Anwendungssicherheitskomponente

| Parameter                         | Standardwert  | Kontext | Mehrfach | Beschreibung                                                                                                                         |
| --------------------------------- | ------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `CROWDSEC_APPSEC_URL`             |               | multisite  | no       | **AppSec URL:** Die URL der CrowdSec-Anwendungssicherheitskomponente. Leer lassen, um AppSec zu deaktivieren.                        |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough` | multisite  | no       | **Aktion bei Fehler:** Aktion, die ausgeführt werden soll, wenn AppSec einen Fehler zurückgibt. Kann `passthrough` oder `deny` sein. |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`         | multisite  | no       | **Verbindungs-Timeout:** Das Timeout in Millisekunden für die Verbindung zur AppSec-Komponente.                                      |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`         | multisite  | no       | **Sende-Timeout:** Das Timeout in Millisekunden für das Senden von Daten an die AppSec-Komponente.                                   |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`         | multisite  | no       | **Verarbeitungs-Timeout:** Das Timeout in Millisekunden für die Verarbeitung der Anfrage in der AppSec-Komponente.                   |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`          | multisite  | no       | **Immer senden:** Auf `yes` setzen, um Anfragen immer an AppSec zu senden, auch wenn eine Entscheidung auf IP-Ebene vorliegt.        |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`          | multisite  | no       | **SSL-Verifizierung:** Auf `yes` setzen, um das SSL-Zertifikat der AppSec-Komponente zu überprüfen.                                  |

!!! info "Über die Betriebsmodi"
    - Der **Live-Modus** fragt die CrowdSec-API für jede eingehende Anfrage ab und bietet Echtzeitschutz auf Kosten einer höheren Latenz.
    - Der **Stream-Modus** lädt periodisch alle Entscheidungen von der CrowdSec-API herunter und speichert sie lokal im Cache, wodurch die Latenz mit einer leichten Verzögerung bei der Anwendung neuer Entscheidungen reduziert wird.

#### Per-Service-Endpunkte

Da die Endpunkte `multisite` sind, können Dienste auf derselben Instanz unterschiedliche CrowdSec-Komponenten verwenden, oder nur einen Teil davon. Die beiden Funktionen sind unabhängig voneinander:

- **Entscheidungsabfragen** sind aktiv, wenn `CROWDSEC_API` gesetzt ist. Setzen Sie es für einen Dienst auf einen leeren String, um die Local API vollständig zu überspringen.
- **AppSec-Inspektion** ist aktiv, wenn `CROWDSEC_APPSEC_URL` gesetzt ist. Setzen Sie es für einen Dienst auf einen leeren String, um die tiefgehende Anfrageprüfung zu überspringen.

Ein Dienst mit `USE_CROWDSEC` auf `yes` und beiden URLs leer prüft nichts, und die Instanz protokolliert, dass kein Endpunkt definiert ist.

!!! warning "Ein Entscheidungscache pro Instanz"
    Zwischengespeicherte Entscheidungen leben in einer einzigen gemeinsamen Speicherzone für die gesamte Instanz, indiziert nach der Local API, von der sie stammen. Dienste, die auf dieselbe `CROWDSEC_API` zeigen, nutzen gegenseitig ihre zwischengespeicherten Entscheidungen, was die Abfrage günstig hält. Dienste, die auf unterschiedliche Local APIs zeigen, sehen die Entscheidungen der jeweils anderen nie. Die Größe dieser Zone gilt instanzweit, sodass sich eine Flotte mit vielen unterschiedlichen Local APIs und großen Entscheidungslisten ein Budget teilt.

!!! info "Bouncer-Schlüssel pro Local API"
    `CROWDSEC_API_KEY` wird pro Dienst wie jede andere Einstellung aufgelöst. Wenn Dienste auf unterschiedliche Local APIs zielen, geben Sie jedem den mit `cscli bouncers add` auf seinem eigenen CrowdSec-Host registrierten Schlüssel, sonst werden die Abfragen als nicht authentifiziert abgelehnt.

### Bot-Erkennung (CrowdSec 1.8+)

CrowdSec 1.8 ergänzt die AppSec-Komponente um eine Bot-Erkennung. Statt einen verdächtigen Client sofort zu sperren, kann die AppSec-Komponente mit einer **Challenge** antworten: einer eigenständigen Seite, die den Browser mit einem Fingerabdruck versieht und ihn einen Proof of Work lösen lässt; das Ergebnis wird anschließend auf CrowdSec-Seite bewertet. BunkerWeb liefert diese Seite exakt so aus, wie CrowdSec sie erzeugt hat — gleicher Status, gleiche Header, gleiches Cookie, auf der ursprünglichen URI — und leitet die Anfrage niemals an Ihre Anwendung weiter. Ein Client, der scheitert, wird weiterhin über die eigene Sperrseite von BunkerWeb abgewiesen; am Sperr-Erlebnis ändert sich also nichts.

Die Bot-Erkennung ist **standardmäßig nicht aktiviert**: Der Bouncer leitet eine Challenge weiter, sobald die Engine eine ausstellt, aber die Engine stellt erst dann eine aus, wenn Sie die Sammlung installieren und ihre Konfiguration laden.

**Aktivierung auf einer eigenständigen CrowdSec-Engine**

```shell
cscli collections install crowdsecurity/appsec-bot-challenge
```

Fügen Sie anschließend die installierten Konfigurationen neben `appsec-default` in die AppSec-Akquisitionsdatei ein:

```yaml
appsec_configs:
  - crowdsecurity/appsec-default
  - crowdsecurity/appsec-bot-*
labels:
  type: appsec
listen_addr: 0.0.0.0:7422
source: appsec
```

Starten Sie CrowdSec neu und prüfen Sie die Ablehnungen anschließend mit `cscli alerts list --kind bot-detection`.

Drei fertige Bundles legen die Ablehnungsschwelle fest: `crowdsecurity/appsec-bot-challenge` lehnt ab einem Score von 75 ab, `crowdsecurity/appsec-bot-challenge-strict` ab 45 und `crowdsecurity/appsec-bot-challenge-permissive` ab 100. Installieren Sie genau das gewünschte — sie sind Alternativen, keine Ebenen.

**Aktivierung im All-In-One-Image**

Setzen Sie `CROWDSEC_EXTRA_COLLECTIONS` am Container und starten Sie ihn neu; das Entrypoint-Skript installiert die Sammlung und trägt ihre Konfigurationen in die AppSec-Akquisitionsdatei ein:

```shell
docker run -d --name bunkerweb-aio \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_APPSEC_URL=http://127.0.0.1:7422 \
  -e CROWDSEC_EXTRA_COLLECTIONS="crowdsecurity/appsec-bot-challenge" \
  bunkerity/bunkerweb-all-in-one:1.7.0-beta
```

Beim ersten Aktivieren der Bot-Erkennung leitet der Entrypoint außerdem ein stabiles `master_secret`
für die Challenge-Laufzeit ab und speichert es unter `/var/lib/bunkerweb` im gemeinsamen AIO-Volume.
Ohne diesen Wert erzeugt CrowdSec ihn bei jedem Neustart neu und macht sämtliche noch gültigen
Challenge-Cookies ungültig. Geben Sie dem Container ein persistentes `/data`-Volume, damit das
Secret und die übrige Instanzidentität ein Neuerstellen überstehen.

!!! warning "Herausgeforderte Clients brauchen JavaScript und Cookies"
    Die Challenge-Seite führt ein Skript aus und legt das Ergebnis in einem Cookie ab. Jeder legitime Client ohne beides — API-Konsumenten, Monitoring-Sonden, Feed-Reader, die meisten Kommandozeilenwerkzeuge — kann sie nicht lösen und wird immer wieder herausgefordert. Schließen Sie diese **auf CrowdSec-Seite** aus oder setzen Sie sie dort auf die Zulassungsliste (das Bundle liefert Ausnahmen für Suchmaschinen, Monitoring, Feeds, statische Dateien und API-Pfade mit) — nicht über `CROWDSEC_EXCLUDE_LOCATION`, das für diesen Pfad jede CrowdSec-Prüfung abschaltet und nicht nur die Challenge.

!!! warning "Der CrowdSec-Host braucht ausführbaren Speicher"
    Die Challenge wird serverseitig von einer WebAssembly-Laufzeit verschleiert, die CrowdSec ausschließlich im Compiler-Modus betreibt — einen Interpreter-Fallback gibt es nicht. Der **Host, auf dem CrowdSec läuft**, benötigt deshalb SSE4.1 auf amd64 (arm64 hat diese Anforderung nicht) und einen Kernel, der eine beschreibbare Speicherzuordnung ausführbar machen darf. Auf einem mit W^X gehärteten Host oder unter einer restriktiven seccomp- oder SELinux-Richtlinie protokolliert CrowdSec beim Start `failed to create wasm runtime in compiler mode` oder `the kernel likely denied an executable memory mapping`, und die Bot-Erkennung bleibt aus. Das ist eine Anforderung an den Host der Engine, nicht an die Browser Ihrer Besucher.

!!! tip "Content-Security-Policy der Challenge-Seite beibehalten"
    CrowdSec hängt der Challenge-Seite immer eine Content-Security-Policy an, und die Seite benötigt sie zur Ausführung. BunkerWeb behält sie bei, weil `Content-Security-Policy` in der Vorgabe von `KEEP_UPSTREAM_HEADERS` enthalten ist. Zwei Einstellungen umgehen diese Liste und würden die Challenge zerstören: ein `CUSTOM_HEADER`, der `Content-Security-Policy` selbst setzt, und die Aufnahme in `REMOVE_HEADERS`. Verwenden Sie eine davon, protokolliert die Instanz beim Start eine Warnung mit dem Namen der Einstellung.

**Das CrowdSec-Urteil auf der Berichtsseite lesen**

Jede CrowdSec-Gegenmaßnahme wird als Bericht erfasst, und der Bericht benennt jetzt das Urteil, statt nur `crowdsec` anzugeben. Die Seite **Berichte** liest es als Satz — *CrowdSec AppSec: bot-detection challenge*, *CrowdSec LAPI: request blocked (scenario: crowdsecurity/http-probing)* — und die Berichtsdetails behalten darunter die Rohfelder: `source` (`appsec` oder `lapi`), `action` (`ban`, `captcha` oder `challenge`), `http_status` (der Status, den die Gegenmaßnahme *deklariert* hat — nicht immer der ausgelieferte: ein LAPI-Ban trägt keinen, und ein AppSec-Ban deklariert 403, während BunkerWeb mit `DENY_HTTP_STATUS` antwortet) sowie `scenario`, `origin` und `duration`, wenn die Entscheidung von der lokalen API stammt.

Eine ausgelieferte Challenge antwortet mit einer 200 statt mit einem Blockier-Code, und der Berichtsfilter behält 4xx-, `detect`- und Stream-Zeilen — allein anhand ihres Status würde die Challenge also verworfen. Der Filter behält eine CrowdSec-Gegenmaßnahme jetzt stattdessen anhand ihres **Grundes**, gleich mit welchem Status sie endete, sodass die Challenge angezeigt wird. Mit `SECURITY_MODE=detect` wird nichts ausgeliefert, und das Urteil benennt die Gegenmaßnahme, die angewendet *worden wäre* — sonst ist sie unsichtbar, denn die Alarmzeilen des Bouncers werden nur auf den Pfaden ausgelöst, die eine Antwort erzeugen.

!!! info "Das Szenario steht nur bei einer frischen Entscheidung dabei"
    Eine Entscheidung der lokalen API führt ihr Szenario nur bei einer Live-Abfrage mit. Sobald die Gegenmaßnahme zwischengespeichert ist, speichert der Cache nur noch die Gegenmaßnahme, sodass die folgenden Anfragen desselben Clients die Aktion ohne Szenario melden. AppSec-Urteile führen nie eines mit: Sie stammen überhaupt nicht aus einer Entscheidung.

### Captcha-Remediation (vom BunkerWeb-Antibot dargestellt)

Eine CrowdSec-Entscheidung vom Typ `captcha` bedeutet *beweise, dass du ein Mensch bist*, nicht *verschwinde*. BunkerWeb beantwortet sie mit seiner **eigenen Antibot-Challenge** statt mit der Captcha-Seite von CrowdSec: ein einheitliches Erscheinungsbild für jede Challenge Ihrer Website, kein zweiter Satz Captcha-Schlüssel und die Anbieter, die CrowdSec nicht kennt — `javascript`, `cookie`, `mcaptcha`, `capjs` — stehen auch für eine CrowdSec-Entscheidung zur Verfügung.

| Einstellung                 | Standard  | Kontext   | Mehrfach | Beschreibung                                                                                                                                  |
| --------------------------- | --------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `CROWDSEC_CAPTCHA_PROVIDER` | `captcha` | multisite | nein     | **Captcha-Challenge:** Welche Antibot-Challenge angezeigt wird, wenn CrowdSec ein Captcha verlangt. Auf `no` setzen, um Captcha-Entscheidungen zu ignorieren. |

Sie nimmt dieselben Werte an wie `USE_ANTIBOT`: `cookie`, `javascript`, `captcha`, `recaptcha`, `hcaptcha`, `turnstile`, `mcaptcha`, `capjs`. Die Drittanbieter lesen ihre Schlüssel aus den `ANTIBOT_*`-Einstellungen des Antibots, es ist also nichts doppelt zu konfigurieren.

!!! warning "Der Antibot muss auf dem Dienst aktiviert sein"
    Die Challenge-Seite existiert nur auf einem Dienst, dessen `USE_ANTIBOT` auf etwas anderes als `no` gesetzt ist (oder der eine Workflow-Challenge-Regel hat). Auf einem Dienst ohne dies wird eine `captcha`-Entscheidung **gebannt** statt gefordert, und die Instanz protokolliert eine Zeile, die beide Einstellungen nennt. `USE_ANTIBOT: "cookie"` ist der günstigste Weg, es einzuschalten: ein gewöhnlicher Besucher wird in einem Roundtrip durchgelassen, während einem von CrowdSec markierten Client stattdessen die `CROWDSEC_CAPTCHA_PROVIDER`-Challenge gezeigt wird.

!!! warning "Dies ändert das Verhalten beim Upgrade"
    Bisher hat BunkerWeb nur auf `ban`-Entscheidungen reagiert, eine `captcha`-Entscheidung Ihrer Local API wurde also nie abgerufen und hatte keinerlei Wirkung. Sie wird jetzt abgerufen, zwischengespeichert und berücksichtigt und stellt die oben beschriebene Challenge dar. Um das vorherige Verhalten beizubehalten, setzen Sie `CROWDSEC_CAPTCHA_PROVIDER: "no"`: Captcha-Entscheidungen werden dann genau wie zuvor ignoriert. Beachten Sie, dass der erweiterte Filter `BOUNCING_ON_TYPE=all` lautet und kein `ban`+`captcha`-Paar ist — der Bouncer akzeptiert nur einen Wert —, sodass eine Entscheidung **jedes anderen** Typs, den Ihre CrowdSec-Profile ausgeben, jetzt ebenfalls berücksichtigt und, da dem Bouncer unbekannt, als Bann angewendet wird. Und der Opt-out stellt das vorherige Verhalten **nur dann vollständig her, wenn jeder Dienst, der dieselbe CrowdSec Local API teilt, ihn setzt**: der Entscheidungs-Cache ist pro Local API partitioniert, nicht pro Dienst (`cache_partition.lua`), sodass ein Nachbardienst mit dem Standardwert die Captcha-Entscheidung zwischenspeichert und der aussteigende Dienst sie zurückliest und darauf bannt.

!!! tip "`cookie` beweist hier nichts"
    Der `cookie`-Anbieter löst sich selbst auf, ohne den Besucher irgendetwas zu fragen. Als `USE_ANTIBOT`-Wert ist er günstig und sinnvoll, als `CROWDSEC_CAPTCHA_PROVIDER` kostet er zwei Weiterleitungen und gewährt einen sitzungslangen Freifahrtschein für eine Entscheidung, die *beweise, dass du ein Mensch bist* bedeutet. Bevorzugen Sie `captcha`, `javascript` oder `capjs`.

!!! info "CrowdSec erfährt nie, dass das Captcha gelöst wurde"
    Die Challenge wird gegen BunkerWeb gelöst, nicht gegen die Engine. Daher zählt `cscli metrics` kein Captcha, `CAPTCHA_EXPIRATION` gilt nicht, und ein anderer Bouncer an derselben Local API fordert denselben Client weiterhin. Die Antwort hält die BunkerWeb-Sitzung des Besuchers: einmal gelöst, wird dieser Browser für die Lebensdauer seiner Sitzung nicht erneut gefordert — auch dann nicht, wenn zwischenzeitlich eine **neue** Captcha-Entscheidung für dieselbe Adresse eintrifft. Jeder Client ohne diese Sitzung (ein anderer Browser, ein anderes Gerät, ein geleerter Cookie-Speicher) wird normal gefordert.

### Das Urteil an einen Security-Workflow übergeben

Ein CrowdSec-Urteil kann von Ihren eigenen **Security-Workflows** beantwortet werden statt von CrowdSecs eigener Remediation: Eine Regel mit einer *CrowdSec-Urteil*-Bedingung kann eine markierte Anfrage nach Ihren Vorgaben herausfordern, umleiten oder blockieren.

| Einstellung                   | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                          |
| ----------------------------- | -------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `CROWDSEC_DEFER_TO_WORKFLOWS` | `no`     | multisite | nein     | **Security-Workflows entscheiden lassen:** das Urteil an die Workflows dieses Dienstes übergeben, statt es hier anzuwenden.            |

Die Bedingung liest zwei Fakten: die **Quelle** des Urteils (`appsec` oder `lapi`) und die von CrowdSec verlangte **Remediation** (`ban` oder `captcha`; ein `challenge` wird von CrowdSec selbst ausgeliefert, bevor die Workflows laufen, und wird daher nicht angeboten). Eine Anfrage, die CrowdSec nicht beurteilt hat, lässt die Bedingung unentschieden, was nie zutrifft; eine Anfrage, die CrowdSec beurteilt hat und gegen die nichts vorlag, macht sie falsch.

!!! warning "Standardmäßig wird nichts geöffnet"
    Mit `no` — dem Standard — wendet CrowdSec sein Urteil wie bisher selbst an. Mit `yes` wird das Urteil unverändert angewendet, sobald keine Workflow-Regel zutrifft, und die Instanz protokolliert eine Zeile mit beiden Einstellungen, wenn dem Dienst überhaupt kein Workflow zugeordnet ist.

!!! info "Drei Antworten kommen weiterhin von BunkerWeb, während das Urteil wartet"
    Der CORS-Preflight (`204`), `/robots.txt` und `/security.txt` werden von BunkerWeb vor den Workflows erzeugt, ein markierter Client kann diese drei also weiterhin erhalten. Keine davon erreicht Ihre Anwendung, und jede Anfrage, die das täte, durchläuft zuerst die Workflow-Kette.

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

=== "Konfiguration pro Dienst"

    AppSec auf jedem öffentlichen Dienst, Entscheidungsabfragen nur bei einer Teilmenge und ein Dienst komplett ausgenommen. Die unpräfigierten Werte sind die flottenweite Baseline, und jeder Dienst überschreibt nur das, was abweicht:

    ```yaml
    MULTISITE: "yes"
    SERVER_NAME: "app1.example.com app2.example.com intranet.example.com"

    # Baseline für jeden Dienst
    USE_CROWDSEC: "yes"
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_API: "" # Keine Entscheidungsabfrage, außer ein Dienst fordert sie an
    CROWDSEC_API_KEY: ""

    # app1 ergänzt die Local-API-Entscheidungsabfrage zusätzlich zu AppSec
    app1.example.com_CROWDSEC_API: "http://crowdsec:8080"
    app1.example.com_CROWDSEC_API_KEY: "your-api-key-here"

    # app2 behält nur AppSec und erbt die leere CROWDSEC_API-Baseline

    # intranet wird überhaupt nicht geprüft
    intranet.example.com_USE_CROWDSEC: "no"
    ```

    Ein Dienst kann auch auf einen ganz anderen CrowdSec-Host zeigen, mit eigenem Bouncer-Schlüssel:

    ```yaml
    app2.example.com_CROWDSEC_API: "http://crowdsec-dmz:8080"
    app2.example.com_CROWDSEC_API_KEY: "dmz-bouncer-key"
    app2.example.com_CROWDSEC_APPSEC_URL: "http://crowdsec-dmz:7422"
    ```

### Schritt&nbsp;3 – Integration validieren

- Suchen Sie in den Scheduler-Protokollen nach den Einträgen `CrowdSec configuration successfully generated` und `CrowdSec bouncer denied request`, um zu überprüfen, dass das Plugin aktiv ist.
- Überwachen Sie auf CrowdSec-Seite `cscli metrics show` oder die CrowdSec-Konsole, um sicherzugehen, dass BunkerWeb-Entscheidungen wie erwartet erscheinen.
- Öffnen Sie in der BunkerWeb-Oberfläche die CrowdSec-Plugin-Seite, um den Status der Integration zu sehen.
