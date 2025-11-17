# Integrationen

## BunkerWeb Cloud

<figure markdown>
  ![Übersicht](assets/img/bunkerweb-cloud.webp){ align=center, width="600" }
  <figcaption>BunkerWeb Cloud</figcaption>
</figure>

BunkerWeb Cloud ist der einfachste Weg, um mit BunkerWeb zu beginnen. Es bietet Ihnen einen vollständig verwalteten BunkerWeb-Dienst ohne Aufwand. Betrachten Sie es als BunkerWeb-as-a-Service!

Probieren Sie unser [BunkerWeb Cloud-Angebot](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=doc) aus und erhalten Sie Zugang zu:

- Eine vollständig verwaltete BunkerWeb-Instanz, die in unserer Cloud gehostet wird
- Alle BunkerWeb-Funktionen, einschließlich der PRO-Funktionen
- Eine Überwachungsplattform mit Dashboards und Warnungen
- Technischer Support zur Unterstützung bei der Konfiguration

Wenn Sie am BunkerWeb Cloud-Angebot interessiert sind, zögern Sie nicht, uns zu [kontaktieren](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc), damit wir Ihre Bedürfnisse besprechen können.

## All-In-One (AIO) Image {#all-in-one-aio-image}

<figure markdown>
  ![AIO Architekturdiagramm Platzhalter](assets/img/aio-graph-placeholder.png){ align=center, width="600" }
  <figcaption>BunkerWeb All-In-One Architektur (AIO)</figcaption>
</figure>

### Bereitstellung {#deployment}

Um den All-in-One-Container bereitzustellen, müssen Sie nur den folgenden Befehl ausführen:

```shell
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3
```

Standardmäßig stellt der Container Folgendes bereit:

- 8080/tcp für HTTP
- 8443/tcp für HTTPS
- 8443/udp für QUIC
- 7000/tcp für den Zugriff auf die Web-UI ohne BunkerWeb davor (nicht für die Produktion empfohlen)
- 8888/tcp für die API, wenn `SERVICE_API=yes` (interne Verwendung; vorzugsweise über BunkerWeb als Reverse-Proxy bereitstellen, anstatt direkt zu veröffentlichen)

Ein benanntes Volume (oder Bind-Mount) ist erforderlich, um die unter `/data` gespeicherten SQLite-Datenbanken, Caches und Backups zu persistieren:

```yaml
services:
  bunkerweb-aio:
    image: bunkerity/bunkerweb-all-in-one:1.6.6-rc3
    volumes:
      - bw-storage:/data
...
volumes:
  bw-storage:
```

!!! warning "Verwendung eines lokalen Ordners für persistente Daten"
    Der All-In-One-Container führt seine Dienste als **unprivilegierter Benutzer mit der UID 101 und GID 101** aus. Das erhöht die Sicherheit: Selbst wenn eine Komponente kompromittiert wird, erhält sie keine Root-Rechte (UID/GID 0) auf dem Host.

    Wenn Sie einen **lokalen Ordner** einbinden, stellen Sie sicher, dass die Verzeichnisberechtigungen es diesem unprivilegierten Benutzer erlauben, darin zu schreiben:

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    Oder, falls der Ordner bereits existiert:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Bei Verwendung von [Docker im rootless-Modus](https://docs.docker.com/engine/security/rootless) oder [Podman](https://podman.io/) werden Container-UIDs/GIDs auf andere Werte des Hosts abgebildet. Prüfen Sie daher zuerst Ihre subuid-/subgid-Bereiche:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    Beginnt der Bereich beispielsweise bei **100000**, lautet die zugeordnete UID/GID **100100** (100000 + 100):

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    Oder, wenn der Ordner bereits existiert:

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

Das All-In-One-Image enthält mehrere integrierte Dienste, die über Umgebungsvariablen gesteuert werden können:

- `SERVICE_UI=yes` (Standard) - Aktiviert den Web-UI-Dienst
- `SERVICE_SCHEDULER=yes` (Standard) - Aktiviert den Scheduler-Dienst
- `SERVICE_API=no` (Standard) - Aktiviert den API-Dienst (FastAPI-Steuerungsebene)
- `AUTOCONF_MODE=no` (Standard) - Aktiviert den Autoconf-Dienst
- `USE_REDIS=yes` (Standard) - Aktiviert die integrierte [Redis-Instanz](#redis-integration)
- `USE_CROWDSEC=no` (Standard) - Die [CrowdSec-Integration](#crowdsec-integration) ist standardmäßig deaktiviert
- `HIDE_SERVICE_LOGS=` (optional) - Kommagetrennte Liste von Diensten, deren Ausgaben in den Container-Logs unterdrückt werden. Unterstützte Werte: `api`, `autoconf`, `bunkerweb`, `crowdsec`, `redis`, `scheduler`, `ui`, `nginx.access`, `nginx.error`, `modsec`. Die Dateien in `/var/log/bunkerweb/<service>.log` werden weiterhin beschrieben.

### API-Integration

Das All-In-One-Image enthält die BunkerWeb-API. Sie ist standardmäßig deaktiviert und kann durch Setzen von `SERVICE_API=yes` aktiviert werden.

!!! warning "Sicherheit"
    Die API ist eine privilegierte Steuerungsebene. Setzen Sie sie nicht direkt dem Internet aus. Halten Sie sie in einem internen Netzwerk, beschränken Sie die Quell-IPs mit `API_WHITELIST_IPS`, erfordern Sie eine Authentifizierung (`API_TOKEN` oder API-Benutzer + Biscuit) und greifen Sie vorzugsweise über BunkerWeb als Reverse-Proxy auf einem nicht erratbaren Pfad darauf zu.

Schnelle Aktivierung (eigenständig) — veröffentlicht den API-Port; nur zu Testzwecken:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e SERVICE_API=yes \
  -e API_WHITELIST_IPS="127.0.0.0/8" \
  -e API_USERNAME=changeme \
  -e API_PASSWORD=StrongP@ssw0rd \
  -p 80:8080/tcp -p 443:8443/tcp -p 443:8443/udp \
  -p 8888:8888/tcp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3
```

Empfohlen (hinter BunkerWeb) — veröffentlichen Sie `8888` nicht; verwenden Sie stattdessen einen Reverse-Proxy:

```yaml
services:
  bunkerweb-aio:
    image: bunkerity/bunkerweb-all-in-one:1.6.6-rc3
    container_name: bunkerweb-aio
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp"
    environment:
      SERVER_NAME: "api.example.com"
      MULTISITE: "yes"
      DISABLE_DEFAULT_SERVER: "yes"
      api.example.com_USE_TEMPLATE: "bw-api"
      api.example.com_USE_REVERSE_PROXY: "yes"
      api.example.com_REVERSE_PROXY_URL: "/api-<unguessable>"
      api.example.com_REVERSE_PROXY_HOST: "http://127.0.0.1:8888" # Interner API-Endpunkt

      # API-Einstellungen
      SERVICE_API: "yes"
      # Verwenden Sie starke Zugangsdaten und erlauben Sie nur vertrauenswürdige IPs/Netze (Details unten)
      API_USERNAME: "changeme"
      API_PASSWORD: "StrongP@ssw0rd"
      API_ROOT_PATH: "/api-<unguessable>" # Muss mit REVERSE_PROXY_URL übereinstimmen

      # Wir deaktivieren die UI – zum Aktivieren auf "yes" setzen
      SERVICE_UI: "no"
    volumes:
      - bw-storage:/data
    networks:
      - bw-universe

volumes:
  bw-storage:

networks:
  bw-universe:
    name: bw-universe
```

Details zu Authentifizierung, Berechtigungen (ACL), Ratenbegrenzung, TLS und Konfigurationsoptionen finden Sie in der [API-Dokumentation](api.md).

### Zugriff auf den Einrichtungsassistenten

Standardmäßig wird der Einrichtungsassistent automatisch gestartet, wenn Sie den AIO-Container zum ersten Mal ausführen. Um darauf zuzugreifen, führen Sie die folgenden Schritte aus:

1. **Starten Sie den AIO-Container** wie [oben](#deployment) beschrieben und stellen Sie sicher, dass `SERVICE_UI=yes` (Standard) ist.
2. **Greifen Sie auf die UI** über Ihren Haupt-BunkerWeb-Endpunkt zu, z. B. `https://ihre-domain`.

> Folgen Sie den nächsten Schritten im [Schnellstart-Leitfaden](quickstart-guide.md#complete-the-setup-wizard), um die Web-UI einzurichten.

### Redis-Integration {#redis-integration}

Das BunkerWeb **All-In-One**-Image enthält standardmäßig Redis für die [Persistenz von Sperren und Berichten](advanced.md#persistence-of-bans-and-reports). Beachten Sie dabei:

- Der eingebettete Redis-Dienst startet nur, wenn `USE_REDIS=yes` **und** `REDIS_HOST` auf dem Standardwert (`127.0.0.1`/`localhost`) bleibt.
- Er lauscht auf dem Loopback-Interface des Containers und ist daher nur aus dem Container heraus erreichbar – nicht von anderen Containern oder vom Host.
- Überschreiben Sie `REDIS_HOST` nur, wenn ein externer Redis-/Valkey-Endpunkt verfügbar ist; andernfalls wird die eingebettete Instanz nicht gestartet.
- Um Redis vollständig zu deaktivieren, setzen Sie `USE_REDIS=no`.
- Redis-Protokolle erscheinen mit dem Präfix `[REDIS]` in den Docker-Protokollen sowie in `/var/log/bunkerweb/redis.log`.

### CrowdSec-Integration {#crowdsec-integration}

Das BunkerWeb **All-In-One**-Docker-Image wird mit vollständig integriertem CrowdSec geliefert – keine zusätzlichen Container oder manuelle Einrichtung erforderlich. Befolgen Sie die nachstehenden Schritte, um CrowdSec in Ihrer Bereitstellung zu aktivieren, zu konfigurieren und zu erweitern.

Standardmäßig ist CrowdSec **deaktiviert**. Um es zu aktivieren, fügen Sie einfach die Umgebungsvariable `USE_CROWDSEC` hinzu:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3```

* Wenn `USE_CROWDSEC=yes`, wird das Einstiegsskript:

    1. Den lokalen CrowdSec-Agenten **registrieren** und **starten** (über `cscli`).
    2. Standard-Sammlungen und -Parser **installieren oder aktualisieren**.
    3. Den Bouncer `crowdsec-bunkerweb-bouncer/v1.6` **konfigurieren**.

---

#### Standard-Sammlungen & Parser

Beim ersten Start (oder nach einem Upgrade) werden diese Assets automatisch installiert und auf dem neuesten Stand gehalten:

| Typ          | Name                                    | Zweck                                                                                                                                                                                                                                              |
| ------------ | --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Sammlung** | `bunkerity/bunkerweb`                   | Verteidigt Nginx-Server gegen eine breite Palette von HTTP-basierten Angriffen, von Brute-Force- bis zu Injektionsversuchen.                                                                                                                       |
| **Sammlung** | `crowdsecurity/appsec-virtual-patching` | Liefert einen dynamisch aktualisierten WAF-artigen Regelsatz, der auf bekannte CVEs abzielt und täglich automatisch gepatcht wird, um Webanwendungen vor neu entdeckten Schwachstellen zu schützen.                                                |
| **Sammlung** | `crowdsecurity/appsec-generic-rules`    | Ergänzt `crowdsecurity/appsec-virtual-patching` mit Heuristiken für generische Angriffsmuster auf Anwendungsebene – wie Enumeration, Pfad-Traversal und automatisierte Sonden – und füllt Lücken, wo CVE-spezifische Regeln noch nicht existieren. |
| **Parser**   | `crowdsecurity/geoip-enrich`            | Bereichert Ereignisse mit GeoIP-Kontext                                                                                                                                                                                                            |

<details>
<summary><strong>Wie es intern funktioniert</strong></summary>

Das Einstiegsskript ruft auf:

```bash
cscli hub update
cscli install collection bunkerity/bunkerweb
cscli install collection crowdsecurity/appsec-virtual-patching
cscli install collection crowdsecurity/appsec-generic-rules
cscli install parser     crowdsecurity/geoip-enrich
```

</details>

!!! info "Sammlung fehlt in Docker?"
    Wenn `cscli collections list` im Container `bunkerity/bunkerweb` weiterhin nicht anzeigt, führen Sie `docker exec -it bunkerweb-aio cscli hub update` aus und starten Sie anschließend den Container neu (`docker restart bunkerweb-aio`), um den lokalen Hub-Cache zu aktualisieren.

---

#### Hinzufügen zusätzlicher Sammlungen

Benötigen Sie mehr Abdeckung? Definieren Sie `CROWDSEC_EXTRA_COLLECTIONS` mit einer durch Leerzeichen getrennten Liste von Hub-Sammlungen:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_EXTRA_COLLECTIONS="crowdsecurity/apache2 crowdsecurity/mysql" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3
```

!!! info "Wie es intern funktioniert"

    Das Skript durchläuft jeden Namen und installiert oder aktualisiert ihn nach Bedarf – keine manuellen Schritte erforderlich.

---

#### Deaktivieren bestimmter Parser

Wenn Sie die Standardeinrichtung beibehalten, aber einen oder mehrere Parser explizit deaktivieren möchten, geben Sie eine durch Leerzeichen getrennte Liste über `CROWDSEC_DISABLED_PARSERS` an:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_DISABLED_PARSERS="crowdsecurity/geoip-enrich foo/bar-parser" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3
```

Hinweise:
- Die Liste wird angewendet, nachdem die erforderlichen Elemente installiert/aktualisiert wurden; nur die von Ihnen aufgelisteten Parser werden entfernt.
- Verwenden Sie Hub-Slugs, wie sie von `cscli parsers list` angezeigt werden (z. B. `crowdsecurity/geoip-enrich`).

---

#### AppSec-Umschalter

CrowdSec [AppSec](https://docs.crowdsec.net/docs/appsec/intro/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs)-Funktionen – angetrieben durch die Sammlungen `appsec-virtual-patching` und `appsec-generic-rules` – sind **standardmäßig aktiviert**.

Um alle AppSec-Funktionen (WAF/virtuelles Patchen) zu **deaktivieren**, setzen Sie:

```bash
-e CROWDSEC_APPSEC_URL=""
```

Dies schaltet den AppSec-Endpunkt effektiv aus, sodass keine Regeln angewendet werden.

---

#### Externe CrowdSec-API

Wenn Sie eine entfernte CrowdSec-Instanz betreiben, verweisen Sie den Container auf Ihre API:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_API="https://crowdsec.example.com:8000" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3
```

* Die **lokale Registrierung** wird übersprungen, wenn `CROWDSEC_API` nicht `127.0.0.1` oder `localhost` ist.
* **AppSec** ist standardmäßig deaktiviert, wenn eine externe API verwendet wird. Um es zu aktivieren, setzen Sie `CROWDSEC_APPSEC_URL` auf Ihren gewünschten Endpunkt.
* Die Bouncer-Registrierung erfolgt weiterhin gegen die entfernte API.
* Um einen vorhandenen Bouncer-Schlüssel wiederzuverwenden, geben Sie `CROWDSEC_API_KEY` mit Ihrem vorab generierten Token an.

---

!!! tip "Weitere Optionen"
    Eine vollständige Übersicht über alle CrowdSec-Optionen (benutzerdefinierte Szenarien, Protokolle, Fehlerbehebung und mehr) finden Sie in der [BunkerWeb CrowdSec-Plugin-Dokumentation](features.md#crowdsec) oder besuchen Sie die [offizielle CrowdSec-Website](https://www.crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs).

## Docker

<figure markdown>
  ![Übersicht](assets/img/integration-docker.svg){ align=center, width="600" }
  <figcaption>Docker-Integration</figcaption>
</figure>

Die Verwendung von BunkerWeb als [Docker](https://www.docker.com/)-Container bietet einen bequemen und unkomplizierten Ansatz zum Testen und Nutzen der Lösung, insbesondere wenn Sie bereits mit der Docker-Technologie vertraut sind.

Um Ihre Docker-Bereitstellung zu erleichtern, stellen wir auf [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb) vorgefertigte Images zur Verfügung, die mehrere Architekturen unterstützen. Diese vorgefertigten Images sind für die Verwendung auf den folgenden Architekturen optimiert und vorbereitet:

- x64 (64-Bit)
- x86
- armv8 (ARM 64-Bit)
- armv7 (ARM 32-Bit)

Durch den Zugriff auf diese vorgefertigten Images von Docker Hub können Sie BunkerWeb schnell in Ihrer Docker-Umgebung ziehen und ausführen, wodurch umfangreiche Konfigurations- oder Einrichtungsprozesse entfallen. Dieser optimierte Ansatz ermöglicht es Ihnen, sich auf die Nutzung der Funktionen von BunkerWeb zu konzentrieren, ohne unnötige Komplexität.

```shell
docker pull bunkerity/bunkerweb:1.6.6-rc3
```

Docker-Images sind auch auf [GitHub-Paketen](https://github.com/orgs/bunkerity/packages?repo_name=bunkerweb) verfügbar und können über die Repository-Adresse `ghcr.io` heruntergeladen werden:

```shell
docker pull ghcr.io/bunkerity/bunkerweb:1.6.6-rc3
```

Schlüsselkonzepte für die Docker-Integration sind:

- **Umgebungsvariablen**: Konfigurieren Sie BunkerWeb einfach über Umgebungsvariablen. Mit diesen Variablen können Sie verschiedene Aspekte des Verhaltens von BunkerWeb anpassen, z. B. Netzwerkeinstellungen, Sicherheitsoptionen und andere Parameter.
- **Scheduler-Container**: Verwalten Sie die Konfiguration und führen Sie Jobs mit einem dedizierten Container namens [Scheduler](concepts.md#scheduler) aus.
- **Netzwerke**: Docker-Netzwerke spielen eine wichtige Rolle bei der Integration von BunkerWeb. Diese Netzwerke dienen zwei Hauptzwecken: dem Bereitstellen von Ports für Clients und dem Verbinden mit Upstream-Webdiensten. Durch das Bereitstellen von Ports kann BunkerWeb eingehende Anfragen von Clients annehmen und ihnen den Zugriff auf die geschützten Webdienste ermöglichen. Darüber hinaus kann BunkerWeb durch die Verbindung mit Upstream-Webdiensten den Datenverkehr effizient weiterleiten und verwalten und so eine verbesserte Sicherheit und Leistung bieten.

!!! info "Datenbank-Backend"
    Bitte beachten Sie, dass unsere Anweisungen davon ausgehen, dass Sie SQLite als Standard-Datenbank-Backend verwenden, wie durch die Einstellung `DATABASE_URI` konfiguriert. Es werden jedoch auch andere Datenbank-Backends unterstützt. Weitere Informationen finden Sie in den docker-compose-Dateien im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc3/misc/integrations) des Repositorys.

### Umgebungsvariablen

Einstellungen werden dem Scheduler über Docker-Umgebungsvariablen übergeben:

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    environment:
      - MY_SETTING=value
      - ANOTHER_SETTING=another value
    volumes:
      - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
...
```

!!! info "Vollständige Liste"
    Die vollständige Liste der Umgebungsvariablen finden Sie im [Einstellungsbereich](features.md) der Dokumentation.

!!! tip "Beschriftete Container überspringen"
    Wenn ein Container von autoconf ignoriert werden soll, setzen Sie `DOCKER_IGNORE_LABELS` auf dem Controller. Geben Sie eine durch Leerzeichen oder Kommas getrennte Liste von Label-Schlüsseln an (zum Beispiel `bunkerweb.SERVER_NAME`) oder nur das Suffix (`SERVER_NAME`). Jeder Container oder jede benutzerdefinierte Konfigurationsquelle mit einem übereinstimmenden Label wird bei der Erkennung übersprungen, und das Label wird bei der Übersetzung der Einstellungen ignoriert.

### Verwendung von Docker-Secrets

Anstatt sensible Einstellungen über Umgebungsvariablen zu übergeben, können Sie sie als Docker-Secrets speichern. Erstellen Sie für jede Einstellung, die Sie sichern möchten, ein Docker-Secret mit dem Namen, der dem Einstellungsschlüssel entspricht (in Großbuchstaben). Die Einstiegsskripte von BunkerWeb laden Secrets automatisch aus `/run/secrets` und exportieren sie als Umgebungsvariablen.

Beispiel:
```bash
# Ein Docker-Secret für ADMIN_PASSWORD erstellen
echo "S3cr3tP@ssw0rd" | docker secret create ADMIN_PASSWORD -
```

Mounten Sie die Secrets bei der Bereitstellung:
```yaml
services:
  bw-ui:
    secrets:
      - ADMIN_PASSWORD
...
secrets:
  ADMIN_PASSWORD:
    external: true
```

Dadurch wird sichergestellt, dass sensible Einstellungen aus der Umgebung und den Protokollen herausgehalten werden.

### Scheduler

Der [Scheduler](concepts.md#scheduler) läuft in seinem eigenen Container, der auch auf Docker Hub verfügbar ist:

```shell
docker pull bunkerity/bunkerweb-scheduler:1.6.6-rc3
```

!!! info "BunkerWeb-Einstellungen"

    Seit Version `1.6.0` ist der Scheduler-Container der Ort, an dem Sie die Einstellungen für BunkerWeb definieren. Der Scheduler pusht die Konfiguration dann an den BunkerWeb-Container.

    ⚠ **Wichtig**: Alle API-bezogenen Einstellungen (wie `API_HTTP_PORT`, `API_LISTEN_IP`, `API_SERVER_NAME`, `API_WHITELIST_IP` und `API_TOKEN`, wenn Sie es verwenden) **müssen auch im BunkerWeb-Container definiert werden**. Die Einstellungen müssen in beiden Containern gespiegelt werden; andernfalls akzeptiert der BunkerWeb-Container keine API-Anfragen vom Scheduler.

    ```yaml
    x-bw-api-env: &bw-api-env
      # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für beide Container zu vermeiden
      API_HTTP_PORT: "5000" # Standardwert
      API_LISTEN_IP: "0.0.0.0" # Standardwert
      API_SERVER_NAME: "bwapi" # Standardwert
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24" # Setzen Sie dies entsprechend Ihren Netzwerkeinstellungen
      # Optionaler Token; wenn gesetzt, sendet der Scheduler Authorization: Bearer <token>
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc3
        environment:
          # Dies setzt die API-Einstellungen für den BunkerWeb-Container
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
        environment:
          # Dies setzt die API-Einstellungen für den Scheduler-Container
          <<: *bw-api-env
        volumes:
          - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
        restart: "unless-stopped"
        networks:
          - bw-universe
    ...
    ```

Ein Volume wird benötigt, um die vom Scheduler verwendete SQLite-Datenbank und Backups zu speichern:

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    volumes:
      - bw-storage:/data
...
volumes:
  bw-storage:
```

!!! warning "Verwendung eines lokalen Ordners für persistente Daten"
    Der Scheduler läuft als **unprivilegierter Benutzer mit UID 101 und GID 101** im Container. Dies erhöht die Sicherheit: Im Falle einer ausgenutzten Schwachstelle hat der Angreifer keine vollen Root-Rechte (UID/GID 0).

    Wenn Sie jedoch einen **lokalen Ordner für persistente Daten** verwenden, müssen Sie **die richtigen Berechtigungen festlegen**, damit der unprivilegierte Benutzer Daten darin schreiben kann. Zum Beispiel:

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    Alternativ, wenn der Ordner bereits existiert:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Wenn Sie [Docker im rootless-Modus](https://docs.docker.com/engine/security/rootless) oder [Podman](https://podman.io/) verwenden, werden UIDs und GIDs im Container auf andere auf dem Host abgebildet. Sie müssen zuerst Ihre anfängliche subuid und subgid überprüfen:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    Wenn Sie beispielsweise einen Wert von **100000** haben, ist die abgebildete UID/GID **100100** (100000 + 100):

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    Oder wenn der Ordner bereits existiert:

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

### Netzwerke

Standardmäßig lauscht der BunkerWeb-Container (innerhalb des Containers) auf **8080/tcp** für **HTTP**, **8443/tcp** für **HTTPS** und **8443/udp** für **QUIC**.

!!! warning "Privilegierte Ports im rootless-Modus oder bei Verwendung von Podman"
    Wenn Sie [Docker im rootless-Modus](https://docs.docker.com/engine/security/rootless) verwenden und privilegierte Ports (< 1024) wie 80 und 443 an BunkerWeb weiterleiten möchten, beachten Sie bitte die Voraussetzungen [hier](https://docs.docker.com/engine/security/rootless/#exposing-privileged-ports).

    Wenn Sie [Podman](https://podman.io/) verwenden, können Sie die Mindestanzahl für unprivilegierte Ports senken:
    ```shell
    sudo sysctl net.ipv4.ip_unprivileged_port_start=1
    ```

Der typische BunkerWeb-Stack bei Verwendung der Docker-Integration enthält die folgenden Container:

- BunkerWeb
- Scheduler
- Ihre Dienste

Aus Gründen der Tiefenverteidigung empfehlen wir dringend, mindestens drei verschiedene Docker-Netzwerke zu erstellen:

- `bw-services`: für BunkerWeb und Ihre Webdienste
- `bw-universe`: für BunkerWeb und den Scheduler
- `bw-db`: für die Datenbank (wenn Sie eine verwenden)

Um die Kommunikation zwischen dem Scheduler und der BunkerWeb-API zu sichern, **autorisieren Sie API-Aufrufe**. Verwenden Sie die Einstellung `API_WHITELIST_IP`, um zulässige IP-Adressen und Subnetze anzugeben. Für einen stärkeren Schutz setzen Sie `API_TOKEN` in beiden Containern; der Scheduler wird automatisch `Authorization: Bearer <token>` einschließen.

**Es wird dringend empfohlen, ein statisches Subnetz für das `bw-universe`-Netzwerk zu verwenden**, um die Sicherheit zu erhöhen. Durch die Umsetzung dieser Maßnahmen können Sie sicherstellen, dass nur autorisierte Quellen auf die BunkerWeb-API zugreifen können, was das Risiko von unbefugtem Zugriff oder böswilligen Aktivitäten verringert:

```yaml
x-bw-api-env: &bw-api-env
  # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für beide Container zu vermeiden
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
  API_TOKEN: "" # Optionaler API-Token
  # Optionaler API-Token für authentifizierten API-Zugriff
  API_TOKEN: ""

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.6-rc3
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    environment:
      <<: *bw-api-env
    restart: "unless-stopped"
    networks:
      - bw-services
      - bw-universe
...
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # Diese Einstellung ist obligatorisch, um die BunkerWeb-Instanz anzugeben
    volumes:
      - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
    restart: "unless-stopped"
    networks:
      - bw-universe
...
volumes:
  bw-storage:

networks:
  bw-universe:
    name: bw-universe
    ipam:
      driver: default
      config:
        - subnet: 10.20.30.0/24 # Statisches Subnetz, damit nur autorisierte Quellen auf die BunkerWeb-API zugreifen können
  bw-services:
    name: bw-services
```

### Vollständige Compose-Datei

```yaml
x-bw-api-env: &bw-api-env
  # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für beide Container zu vermeiden
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.6-rc3
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    environment:
      <<: *bw-api-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    depends_on:
      - bunkerweb
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # Diese Einstellung ist obligatorisch, um die BunkerWeb-Instanz anzugeben
      SERVER_NAME: "www.example.com"
    volumes:
      - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
    restart: "unless-stopped"
    networks:
      - bw-universe

volumes:
  bw-storage:

networks:
  bw-universe:
    name: bw-universe
    ipam:
      driver: default
      config:
        - subnet: 10.20.30.0/24 # Statisches Subnetz, damit nur autorisierte Quellen auf die BunkerWeb-API zugreifen können
  bw-services:
    name: bw-services
```

### Aus dem Quellcode erstellen

Alternativ, wenn Sie einen praxisorientierteren Ansatz bevorzugen, haben Sie die Möglichkeit, das Docker-Image direkt aus dem [Quellcode](https://github.com/bunkerity/bunkerweb) zu erstellen. Das Erstellen des Images aus dem Quellcode gibt Ihnen mehr Kontrolle und Anpassungsmöglichkeiten über den Bereitstellungsprozess. Bitte beachten Sie jedoch, dass diese Methode je nach Ihrer Hardwarekonfiguration einige Zeit in Anspruch nehmen kann (Sie können bei Bedarf einen Kaffee ☕ trinken).

```shell
git clone https://github.com/bunkerity/bunkerweb.git && \
cd bunkerweb && \
docker build -t bw -f src/bw/Dockerfile . && \
docker build -t bw-scheduler -f src/scheduler/Dockerfile . && \
docker build -t bw-autoconf -f src/autoconf/Dockerfile . && \
docker build -t bw-ui -f src/ui/Dockerfile .
```

## Linux

<figure markdown>
  ![Übersicht](assets/img/integration-linux.svg){ align=center, width="600" }
  <figcaption>Linux-Integration</figcaption>
</figure>

Unterstützte Linux-Distributionen für BunkerWeb (amd64/x86_64 und arm64/aarch64 Architekturen) sind:

- Debian 12 "Bookworm"
- Debian 13 "Trixie"
- Ubuntu 22.04 "Jammy"
- Ubuntu 24.04 "Noble"
- Fedora 41 und 42
- Red Hat Enterprise Linux (RHEL) 8, 9 und 10

### Einfaches Installationsskript

Für eine vereinfachte Installation bietet BunkerWeb ein einfaches Installationsskript, das den gesamten Einrichtungsprozess automatisch abwickelt, einschließlich NGINX-Installation, Repository-Konfiguration und Service-Setup.

#### Schnellstart

Um zu beginnen, laden Sie das Installationsskript und seine Prüfsumme herunter und überprüfen Sie dann die Integrität des Skripts, bevor Sie es ausführen.

```bash
# Skript und Prüfsumme herunterladen
wget https://github.com/bunkerity/bunkerweb/releases/download/v1.6.6-rc3/install-bunkerweb.sh
wget https://github.com/bunkerity/bunkerweb/releases/download/v1.6.6-rc3/install-bunkerweb.sh.sha256

# Prüfsumme überprüfen
sha256sum -c install-bunkerweb.sh.sha256

# Wenn die Überprüfung erfolgreich ist, Skript ausführen
chmod +x install-bunkerweb.sh
sudo ./install-bunkerweb.sh
```

!!! danger "Sicherheitshinweis"
    **Überprüfen Sie immer die Integrität des Installationsskripts, bevor Sie es ausführen.**

    Laden Sie die Prüfsummendatei herunter und verwenden Sie ein Werkzeug wie `sha256sum`, um zu bestätigen, dass das Skript nicht verändert oder manipuliert wurde.

    Wenn die Überprüfung der Prüfsumme fehlschlägt, **führen Sie das Skript nicht aus** – es könnte unsicher sein.

#### Wie es funktioniert

Das einfache Installationsskript ist ein leistungsstarkes Werkzeug, das entwickelt wurde, um die Einrichtung von BunkerWeb auf einem frischen Linux-System zu optimieren. Es automatisiert die folgenden wichtigen Schritte:

1.  **Systemanalyse**: Erkennt Ihr Betriebssystem und überprüft es anhand der Liste der unterstützten Distributionen.
2.  **Anpassung der Installation**: Im interaktiven Modus werden Sie aufgefordert, einen Installationstyp (All-In-One, Manager, Worker usw.) auszuwählen und zu entscheiden, ob der webbasierte Einrichtungsassistent aktiviert werden soll.
3.  **Optionale Integrationen**: Bietet an, die [CrowdSec Security Engine](#crowdsec-integration-with-the-script) automatisch zu installieren und zu konfigurieren.
4.  **Abhängigkeitsmanagement**: Installiert die korrekte Version von NGINX, die von BunkerWeb benötigt wird, aus offiziellen Quellen und sperrt die Version, um unbeabsichtigte Upgrades zu verhindern.
5.  **BunkerWeb-Installation**: Fügt das BunkerWeb-Paket-Repository hinzu, installiert die erforderlichen Pakete und sperrt die Version.
6.  **Dienstkonfiguration**: Richtet die `systemd`-Dienste entsprechend dem von Ihnen gewählten Installationstyp ein und aktiviert sie.
7.  **Anleitung nach der Installation**: Bietet klare nächste Schritte, um Ihnen den Einstieg in Ihre neue BunkerWeb-Instanz zu erleichtern.

#### Interaktive Installation

Wenn das Skript ohne Optionen ausgeführt wird, wechselt es in einen interaktiven Modus, der Sie durch den Einrichtungsprozess führt. Sie werden gebeten, die folgenden Entscheidungen zu treffen:

1.  **Installationstyp**: Wählen Sie die Komponenten aus, die Sie installieren möchten.
    *   **Full Stack (Standard)**: Eine All-in-One-Installation mit BunkerWeb, dem Scheduler und der Web-UI.
    *   **Manager**: Installiert den Scheduler und die Web-UI, um einen oder mehrere entfernte BunkerWeb-Worker zu verwalten.
    *   **Worker**: Installiert nur die BunkerWeb-Instanz, die von einem entfernten Manager verwaltet werden kann.
    *   **Nur Scheduler**: Installiert nur die Scheduler-Komponente.
    *   **Nur Web-UI**: Installiert nur die Web-UI-Komponente.
2.  **Einrichtungsassistent**: Wählen Sie, ob der webbasierte Konfigurationsassistent aktiviert werden soll. Dies wird für Erstanwender dringend empfohlen.
3.  **CrowdSec-Integration**: Entscheiden Sie sich für die Installation der CrowdSec-Sicherheits-Engine für erweiterten Echtzeit-Bedrohungsschutz.
4.  **CrowdSec AppSec**: Wenn Sie sich für die Installation von CrowdSec entscheiden, können Sie auch die Application Security (AppSec)-Komponente aktivieren, die WAF-Funktionen hinzufügt.
5.  **API-Dienst**: Wählen Sie, ob der optionale BunkerWeb-API-Dienst aktiviert werden soll. Er ist bei Linux-Installationen standardmäßig deaktiviert.

!!! info "Manager- und Scheduler-Installationen"
    Wenn Sie den Installationstyp **Manager** oder **Nur Scheduler** wählen, werden Sie auch aufgefordert, die IP-Adressen oder Hostnamen Ihrer BunkerWeb-Worker-Instanzen anzugeben.

#### Befehlszeilenoptionen

Für nicht-interaktive oder automatisierte Setups kann das Skript mit Befehlszeilen-Flags gesteuert werden:

**Allgemeine Optionen:**

| Option                  | Beschreibung                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------------- |
| `-v, --version VERSION` | Gibt die zu installierende BunkerWeb-Version an (z. B. `1.6.6-rc3`).                        |
| `-w, --enable-wizard`   | Aktiviert den Einrichtungsassistenten.                                                      |
| `-n, --no-wizard`       | Deaktiviert den Einrichtungsassistenten.                                                    |
| `-y, --yes`             | Führt im nicht-interaktiven Modus mit Standardantworten für alle Eingabeaufforderungen aus. |
| `-f, --force`           | Erzwingt die Installation, auch auf einer nicht unterstützten Betriebssystemversion.        |
| `-q, --quiet`           | Stille Installation (unterdrückt die Ausgabe).                                              |
| `--api`, `--enable-api` | Aktiviert den API (FastAPI) systemd-Dienst (standardmäßig deaktiviert).                     |
| `--no-api`              | Deaktiviert den API-Dienst explizit.                                                        |
| `-h, --help`            | Zeigt die Hilfenachricht mit allen verfügbaren Optionen an.                                 |
| `--dry-run`             | Zeigt an, was installiert würde, ohne es zu tun.                                            |

**Installationstypen:**

| Option             | Beschreibung                                                                       |
| ------------------ | ---------------------------------------------------------------------------------- |
| `--full`           | Vollständige Stack-Installation (BunkerWeb, Scheduler, UI). Dies ist der Standard. |
| `--manager`        | Installiert den Scheduler und die UI zur Verwaltung von Remote-Workern.            |
| `--worker`         | Installiert nur die BunkerWeb-Instanz.                                             |
| `--scheduler-only` | Installiert nur die Scheduler-Komponente.                                          |
| `--ui-only`        | Installiert nur die Web-UI-Komponente.                                             |

**Sicherheitsintegrationen:**

| Option              | Beschreibung                                                                    |
| ------------------- | ------------------------------------------------------------------------------- |
| `--crowdsec`        | Installiert und konfiguriert die CrowdSec-Sicherheits-Engine.                   |
| `--no-crowdsec`     | Überspringt die CrowdSec-Installation.                                          |
| `--crowdsec-appsec` | Installiert CrowdSec mit der AppSec-Komponente (einschließlich WAF-Funktionen). |

**Erweiterte Optionen:**

| Option                  | Beschreibung                                                                                          |
| ----------------------- | ----------------------------------------------------------------------------------------------------- |
| `--instances "IP1 IP2"` | Durch Leerzeichen getrennte Liste von BunkerWeb-Instanzen (erforderlich für Manager-/Scheduler-Modi). |

**Beispielverwendung:**

```bash
# Im interaktiven Modus ausführen (für die meisten Benutzer empfohlen)
sudo ./install-bunkerweb.sh

# Nicht-interaktive Installation mit Standardeinstellungen (vollständiger Stack, Assistent aktiviert)
sudo ./install-bunkerweb.sh --yes

# Einen Worker-Knoten ohne Einrichtungsassistent installieren
sudo ./install-bunkerweb.sh --worker --no-wizard

# Eine bestimmte Version installieren
sudo ./install-bunkerweb.sh --version 1.6.6-rc3

# Manager-Setup mit entfernten Worker-Instanzen (Instanzen erforderlich)
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11"

# Vollständige Installation mit CrowdSec und AppSec
sudo ./install-bunkerweb.sh --crowdsec-appsec

# Stille nicht-interaktive Installation
sudo ./install-bunkerweb.sh --quiet --yes

# Installationsvorschau ohne Ausführung
sudo ./install-bunkerweb.sh --dry-run

# API während der einfachen Installation aktivieren (nicht-interaktiv)
sudo ./install-bunkerweb.sh --yes --api

# Fehler: CrowdSec kann nicht mit Worker-Installationen verwendet werden
# sudo ./install-bunkerweb.sh --worker --crowdsec  # Dies schlägt fehl

# Fehler: Instanzen für Manager im nicht-interaktiven Modus erforderlich
# sudo ./install-bunkerweb.sh --manager --yes  # Dies schlägt ohne --instances fehl
```

!!! warning "Wichtige Hinweise zur Optionskompatibilität"

    **CrowdSec-Einschränkungen:**
    - CrowdSec-Optionen (`--crowdsec`, `--crowdsec-appsec`) sind nur mit den Installationstypen `--full` (Standard) und `--manager` kompatibel
    - Sie können nicht mit den Installationen `--worker`, `--scheduler-only` oder `--ui-only` verwendet werden

    **Anforderungen für Instanzen:**
    - Die Option `--instances` ist nur mit den Installationstypen `--manager` und `--scheduler-only` gültig
    - Bei Verwendung von `--manager` oder `--scheduler-only` mit `--yes` (nicht-interaktiver Modus) ist die Option `--instances` obligatorisch
    - Format: `--instances "192.168.1.10 192.168.1.11 192.168.1.12"`

    **Interaktiv vs. Nicht-interaktiv:**
    - Der interaktive Modus (Standard) fordert zur Eingabe fehlender erforderlicher Werte auf
    - Der nicht-interaktive Modus (`--yes`) erfordert, dass alle erforderlichen Optionen über die Befehlszeile bereitgestellt werden

#### CrowdSec-Integration mit dem Skript {#crowdsec-integration-with-the-script}

Wenn Sie sich für die Installation von CrowdSec während der interaktiven Einrichtung entscheiden, automatisiert das Skript die Integration mit BunkerWeb vollständig:

- Es fügt das offizielle CrowdSec-Repository hinzu und installiert den Agenten.
- Es erstellt eine neue Erfassungsdatei, damit CrowdSec die Protokolle von BunkerWeb (`access.log`, `error.log` und `modsec_audit.log`) parsen kann.
- Es installiert wesentliche Sammlungen (`bunkerity/bunkerweb`) und Parser (`crowdsecurity/geoip-enrich`).
- Es registriert einen Bouncer für BunkerWeb und konfiguriert den API-Schlüssel automatisch in `/etc/bunkerweb/variables.env`.
- Wenn Sie auch die **AppSec-Komponente** auswählen, installiert es die Sammlungen `appsec-virtual-patching` und `appsec-generic-rules` und konfiguriert den AppSec-Endpunkt für BunkerWeb.

Dies bietet eine nahtlose, sofort einsatzbereite Integration für einen leistungsstarken Einbruchschutz.

#### RHEL-Überlegungen

!!! warning "Unterstützung externer Datenbanken auf RHEL-basierten Systemen"
    Wenn Sie eine externe Datenbank verwenden möchten (empfohlen für die Produktion), müssen Sie das entsprechende Datenbank-Client-Paket installieren:

    ```bash
    # Für MariaDB
    sudo dnf install mariadb

    # Für MySQL
    sudo dnf install mysql

    # Für PostgreSQL
    sudo dnf install postgresql
    ```

    Dies ist erforderlich, damit der BunkerWeb-Scheduler eine Verbindung zu Ihrer externen Datenbank herstellen kann.

#### Nach der Installation

Abhängig von Ihren Entscheidungen während der Installation:

**Mit aktiviertem Einrichtungsassistenten:**

1. Greifen Sie auf den Einrichtungsassistenten unter `https://ihre-server-ip/setup` zu
2. Befolgen Sie die geführte Konfiguration, um Ihren ersten geschützten Dienst einzurichten
3. Konfigurieren Sie SSL/TLS-Zertifikate und andere Sicherheitseinstellungen

**Ohne Einrichtungsassistent:**

1. Bearbeiten Sie `/etc/bunkerweb/variables.env`, um BunkerWeb manuell zu konfigurieren
2. Fügen Sie Ihre Servereinstellungen und geschützten Dienste hinzu
3. Starten Sie den Scheduler neu: `sudo systemctl restart bunkerweb-scheduler`

### Installation über den Paketmanager

Bitte stellen Sie sicher, dass Sie **NGINX 1.28.0 installiert haben, bevor Sie BunkerWeb installieren**. Für alle Distributionen außer Fedora ist es zwingend erforderlich, vorgefertigte Pakete aus dem [offiziellen NGINX-Repository](https://nginx.org/en/linux_packages.html) zu verwenden. Das Kompilieren von NGINX aus dem Quellcode oder die Verwendung von Paketen aus verschiedenen Repositories funktioniert nicht mit den offiziellen vorgefertigten Paketen von BunkerWeb. Sie haben jedoch die Möglichkeit, BunkerWeb aus dem Quellcode zu erstellen.

=== "Debian Bookworm/Trixie"

    Der erste Schritt ist das Hinzufügen des offiziellen NGINX-Repositorys:

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release debian-archive-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/debian `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    Sie sollten jetzt NGINX 1.28.0 installieren können:

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "Testing/dev-Version"
        Wenn Sie die `testing`- oder `dev`-Version verwenden, müssen Sie die Direktive `force-bad-version` zu Ihrer `/etc/dpkg/dpkg.cfg`-Datei hinzufügen, bevor Sie BunkerWeb installieren.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Einrichtungsassistenten deaktivieren"
        Wenn Sie den Einrichtungsassistenten der Web-UI bei der Installation von BunkerWeb nicht verwenden möchten, exportieren Sie die folgende Variable:

        ```shell
        export UI_WIZARD=no
        ```

    Und installieren Sie schließlich BunkerWeb 1.6.6-rc3:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.6-rc3
    ```

    Um ein Upgrade der NGINX- und/oder BunkerWeb-Pakete bei der Ausführung von `apt upgrade` zu verhindern, können Sie den folgenden Befehl verwenden:

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Ubuntu"

    Der erste Schritt ist das Hinzufügen des offiziellen NGINX-Repositorys:

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    Sie sollten jetzt NGINX 1.28.0 installieren können:

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "Testing/dev-Version"
        Wenn Sie die `testing`- oder `dev`-Version verwenden, müssen Sie die Direktive `force-bad-version` zu Ihrer `/etc/dpkg/dpkg.cfg`-Datei hinzufügen, bevor Sie BunkerWeb installieren.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Einrichtungsassistenten deaktivieren"
        Wenn Sie den Einrichtungsassistenten der Web-UI bei der Installation von BunkerWeb nicht verwenden möchten, exportieren Sie die folgende Variable:

        ```shell
        export UI_WIZARD=no
        ```

    Und installieren Sie schließlich BunkerWeb 1.6.6-rc3:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.6-rc3
    ```

    Um ein Upgrade der NGINX- und/oder BunkerWeb-Pakete bei der Ausführung von `apt upgrade` zu verhindern, können Sie den folgenden Befehl verwenden:

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Fedora"

    !!! info "Fedora Update Testing"
        Wenn Sie die NGINX-Version nicht im stabilen Repository finden können, können Sie das `updates-testing`-Repository aktivieren:

        ```shell
        sudo dnf config-manager setopt updates-testing.enabled=1
        ```

    Fedora stellt bereits NGINX 1.28.0 zur Verfügung, das wir unterstützen

    ```shell
    sudo dnf install -y --allowerasing nginx-1.28.0
    ```

    !!! example "Einrichtungsassistenten deaktivieren"
        Wenn Sie den Einrichtungsassistenten der Web-UI bei der Installation von BunkerWeb nicht verwenden möchten, exportieren Sie die folgende Variable:

        ```shell
        export UI_WIZARD=no
        ```

    Und installieren Sie schließlich BunkerWeb 1.6.6-rc3:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
  	sudo dnf makecache && \
  	sudo -E dnf install -y --allowerasing bunkerweb-1.6.6-rc3
    ```

    Um ein Upgrade der NGINX- und/oder BunkerWeb-Pakete bei der Ausführung von `dnf upgrade` zu verhindern, können Sie den folgenden Befehl verwenden:

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

=== "RedHat"

    Der erste Schritt ist das Hinzufügen des offiziellen NGINX-Repositorys. Erstellen Sie die folgende Datei unter `/etc/yum.repos.d/nginx.repo`:

    ```conf
    [nginx-stable]
    name=nginx stable repo
    baseurl=http://nginx.org/packages/centos/$releasever/$basearch/
    gpgcheck=1
    enabled=1
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true

    [nginx-mainline]
    name=nginx mainline repo
    baseurl=http://nginx.org/packages/mainline/centos/$releasever/$basearch/
    gpgcheck=1
    enabled=0
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true
    ```

    Sie sollten jetzt NGINX 1.28.0 installieren können:

    ```shell
    sudo dnf install --allowerasing nginx-1.28.0
    ```

    !!! example "Einrichtungsassistenten deaktivieren"
        Wenn Sie den Einrichtungsassistenten der Web-UI bei der Installation von BunkerWeb nicht verwenden möchten, exportieren Sie die folgende Variable:

        ```shell
        export UI_WIZARD=no
        ```

    Und installieren Sie schließlich BunkerWeb 1.6.6-rc3:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo -E dnf install -y --allowerasing bunkerweb-1.6.6-rc3
    ```

    Um ein Upgrade der NGINX- und/oder BunkerWeb-Pakete bei der Ausführung von `dnf upgrade` zu verhindern, können Sie den folgenden Befehl verwenden:

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

### Konfiguration und Dienst

Die manuelle Konfiguration von BunkerWeb erfolgt durch Bearbeiten der Datei `/etc/bunkerweb/variables.env`:

```conf
MEINE_EINSTELLUNG_1=wert1
MEINE_EINSTELLUNG_2=wert2
...```

Bei der Installation wird BunkerWeb mit drei Diensten `bunkerweb`, `bunkerweb-scheduler` und `bunkerweb-ui` geliefert, die Sie mit `systemctl` verwalten können.

Wenn Sie die BunkerWeb-Konfiguration manuell über `/etc/bunkerweb/variables.env` bearbeiten, reicht ein Neustart des `bunkerweb-scheduler`-Dienstes aus, um die Konfiguration ohne Ausfallzeit zu generieren und neu zu laden. In bestimmten Fällen (z. B. bei Änderung der lauschenden Ports) müssen Sie jedoch möglicherweise den `bunkerweb`-Dienst neu starten.

### Hochverfügbarkeit

Der Scheduler kann von der BunkerWeb-Instanz getrennt werden, um eine hohe Verfügbarkeit zu gewährleisten. In diesem Fall wird der Scheduler auf einem separaten Server installiert und kann mehrere BunkerWeb-Instanzen verwalten.

#### Manager

Um nur den Scheduler auf einem Server zu installieren, können Sie die folgenden Variablen exportieren, bevor Sie die BunkerWeb-Installation ausführen:

```shell
export MANAGER_MODE=yes
export UI_WIZARD=no
```

Alternativ können Sie auch die folgenden Variablen exportieren, um nur den Scheduler zu aktivieren:

```shell
export SERVICE_SCHEDULER=yes
export SERVICE_BUNKERWEB=no
export SERVICE_UI=no
```

#### Worker

Um nur BunkerWeb auf einem anderen Server zu installieren, können Sie die folgenden Variablen exportieren, bevor Sie die BunkerWeb-Installation ausführen:

```shell
export WORKER_MODE=yes
```

Alternativ können Sie auch die folgenden Variablen exportieren, um nur BunkerWeb zu aktivieren:

```shell
export SERVICE_BUNKERWEB=yes
export SERVICE_SCHEDULER=no
export SERVICE_UI=no
```

#### Web-UI

Die Web-UI kann auf einem separaten Server installiert werden, um eine dedizierte Schnittstelle zur Verwaltung von BunkerWeb-Instanzen bereitzustellen. Um nur die Web-UI zu installieren, können Sie die folgenden Variablen exportieren, bevor Sie die BunkerWeb-Installation ausführen:

```shell
export SERVICE_BUNKERWEB=no
export SERVICE_SCHEDULER=no
export SERVICE_UI=yes
```

## Docker Autoconf

<figure markdown>
  ![Übersicht](assets/img/integration-autoconf.svg){ align=center, width="600" }
  <figcaption>Docker Autoconf-Integration</figcaption>
</figure>

!!! info "Docker-Integration"
    Die Docker Autoconf-Integration ist eine "Weiterentwicklung" der Docker-Integration. Bitte lesen Sie bei Bedarf zuerst den [Docker-Integrationsabschnitt](#docker).

Ein alternativer Ansatz ist verfügbar, um die Unannehmlichkeit zu beheben, den Container bei jedem Update neu erstellen zu müssen. Durch die Verwendung eines anderen Images namens **autoconf** können Sie die Echtzeit-Rekonfiguration von BunkerWeb automatisieren, ohne dass eine Neuerstellung des Containers erforderlich ist.

Um diese Funktionalität zu nutzen, können Sie anstelle von Umgebungsvariablen für den BunkerWeb-Container **Labels** zu Ihren Webanwendungs-Containern hinzufügen. Das **autoconf**-Image lauscht dann auf Docker-Ereignisse und übernimmt nahtlos die Konfigurationsupdates für BunkerWeb.

Dieser "*automagische*" Prozess vereinfacht die Verwaltung von BunkerWeb-Konfigurationen. Durch das Hinzufügen von Labels zu Ihren Webanwendungs-Containern können Sie die Rekonfigurationsaufgaben an **autoconf** delegieren, ohne den manuellen Eingriff der Neuerstellung des Containers. Dies optimiert den Aktualisierungsprozess und erhöht den Komfort.

Durch die Übernahme dieses Ansatzes können Sie eine Echtzeit-Rekonfiguration von BunkerWeb ohne den Aufwand der Neuerstellung von Containern genießen, was es effizienter und benutzerfreundlicher macht.

!!! info "Multisite-Modus"
    Die Docker Autoconf-Integration impliziert die Verwendung des **Multisite-Modus**. Weitere Informationen finden Sie im [Multisite-Abschnitt](concepts.md#multisite-mode) der Dokumentation.

!!! info "Datenbank-Backend"
    Bitte beachten Sie, dass unsere Anweisungen davon ausgehen, dass Sie MariaDB als Standard-Datenbank-Backend verwenden, wie durch die Einstellung `DATABASE_URI` konfiguriert. Wir verstehen jedoch, dass Sie möglicherweise alternative Backends für Ihre Docker-Integration bevorzugen. In diesem Fall können Sie sicher sein, dass auch andere Datenbank-Backends möglich sind. Weitere Informationen finden Sie in den docker-compose-Dateien im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc3/misc/integrations) des Repositorys.

Um automatisierte Konfigurationsupdates zu ermöglichen, fügen Sie einen zusätzlichen Container namens `bw-autoconf` zum Stack hinzu. Dieser Container hostet den Autoconf-Dienst, der dynamische Konfigurationsänderungen für BunkerWeb verwaltet.

Um diese Funktionalität zu unterstützen, verwenden Sie ein dediziertes "echtes" Datenbank-Backend (z. B. MariaDB, MySQL oder PostgreSQL) zur synchronisierten Konfigurationsspeicherung. Durch die Integration von `bw-autoconf` und einem geeigneten Datenbank-Backend schaffen Sie die Infrastruktur für eine nahtlose automatisierte Konfigurationsverwaltung in BunkerWeb.

```yaml
x-bw-env: &bw-env
  # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für beide Container zu vermeiden
  AUTOCONF_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.6-rc3
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    labels:
      - "bunkerweb.INSTANCE=yes" # Obligatorisches Label für den Autoconf-Dienst, um die BunkerWeb-Instanz zu identifizieren
    environment:
      <<: *bw-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # Wir müssen die BunkerWeb-Instanz hier nicht angeben, da sie automatisch vom Autoconf-Dienst erkannt werden
      SERVER_NAME: "" # Der Servername wird mit Dienst-Labels gefüllt
      MULTISITE: "yes" # Obligatorische Einstellung für Autoconf
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
    volumes:
      - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.6-rc3
    depends_on:
      - bunkerweb
      - bw-docker
    environment:
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
      DOCKER_HOST: "tcp://bw-docker:2375" # Der Docker-Socket
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-docker
      - bw-db

  bw-docker:
    image: tecnativa/docker-socket-proxy:nightly
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      CONTAINERS: "1"
      LOG_LEVEL: "warning"
    restart: "unless-stopped"
    networks:
      - bw-docker

  bw-db:
    image: mariadb:11
    # Wir setzen die maximal zulässige Paketgröße, um Probleme mit großen Abfragen zu vermeiden
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "changeme" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
    volumes:
      - bw-data:/var/lib/mysql
    restart: "unless-stopped"
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
  bw-docker:
    name: bw-docker
  bw-db:
    name: bw-db
```

!!! info "Datenbank im `bw-db`-Netzwerk"
    Der Datenbankcontainer ist absichtlich nicht im `bw-universe`-Netzwerk enthalten. Er wird von den Containern `bw-autoconf` und `bw-scheduler` und nicht direkt von BunkerWeb verwendet. Daher ist der Datenbankcontainer Teil des `bw-db`-Netzwerks, was die Sicherheit erhöht, indem der externe Zugriff auf die Datenbank erschwert wird. **Diese bewusste Designentscheidung hilft, die Datenbank zu schützen und die allgemeine Sicherheitsperspektive des Systems zu stärken**.

!!! warning "Verwendung von Docker im rootless-Modus"
    Wenn Sie [Docker im rootless-Modus](https://docs.docker.com/engine/security/rootless) verwenden, müssen Sie den Mount des Docker-Sockets durch den folgenden Wert ersetzen: `$XDG_RUNTIME_DIR/docker.sock:/var/run/docker.sock:ro`.

### Autoconf-Dienste

Sobald der Stack eingerichtet ist, können Sie den Webanwendungs-Container erstellen und die Einstellungen als Labels mit dem Präfix "bunkerweb" hinzufügen, um BunkerWeb automatisch einzurichten:

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    labels:
      - "bunkerweb.MY_SETTING_1=value1"
      - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

### Namespaces {#namespaces}

Ab Version `1.6.0` unterstützen die Autoconf-Stacks von BunkerWeb Namespaces. Mit dieser Funktion können Sie mehrere "*Cluster*" von BunkerWeb-Instanzen und -Diensten auf demselben Docker-Host verwalten. Um Namespaces zu nutzen, setzen Sie einfach das `NAMESPACE`-Label auf Ihre Dienste. Hier ist ein Beispiel:

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    labels:
      - "bunkerweb.NAMESPACE=my-namespace" # Setzen Sie den Namespace für den Dienst
      - "bunkerweb.MY_SETTING_1=value1"
      - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "Namespace-Verhalten"

    Standardmäßig lauschen alle Autoconf-Stacks auf alle Namespaces. Wenn Sie einen Stack auf bestimmte Namespaces beschränken möchten, können Sie die Umgebungsvariable `NAMESPACES` im `bw-autoconf`-Dienst setzen:

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc3
        labels:
          - "bunkerweb.INSTANCE=yes"
          - "bunkerweb.NAMESPACE=my-namespace" # Setzen Sie den Namespace für die BunkerWeb-Instanz, damit der Autoconf-Dienst sie erkennen kann
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc3
        environment:
          ...
          NAMESPACES: "my-namespace my-other-namespace" # Lauschen Sie nur auf diese Namespaces
    ...
    ```

    Beachten Sie, dass die Umgebungsvariable `NAMESPACES` eine durch Leerzeichen getrennte Liste von Namespaces ist.

!!! warning "Namespace-Spezifikationen"

    Es kann nur **eine Datenbank** und **ein Scheduler** pro Namespace geben. Wenn Sie versuchen, mehrere Datenbanken oder Scheduler im selben Namespace zu erstellen, kommt es zu Konfigurationskonflikten.

    Der Scheduler benötigt das `NAMESPACE`-Label nicht, um ordnungsgemäß zu funktionieren. Er benötigt nur die korrekt konfigurierte Einstellung `DATABASE_URI`, damit er auf dieselbe Datenbank wie der Autoconf-Dienst zugreifen kann.

## Kubernetes

<figure markdown>
  ![Übersicht](assets/img/integration-kubernetes.svg){ align=center, width="600" }
  <figcaption>Kubernetes-Integration</figcaption>
</figure>

Um die Konfiguration von BunkerWeb-Instanzen in einer Kubernetes-Umgebung zu automatisieren,
dient der Autoconf-Dienst als [Ingress-Controller](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/).
Er konfiguriert die BunkerWeb-Instanzen basierend auf [Ingress-Ressourcen](https://kubernetes.io/docs/concepts/services-networking/ingress/)
und überwacht auch andere Kubernetes-Objekte wie [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/)
für benutzerdefinierte Konfigurationen.

!!! info "ConfigMap-Abgleich"
    - Der Ingress-Controller verwaltet nur ConfigMaps, die die Annotation `bunkerweb.io/CONFIG_TYPE` enthalten.
    - Ergänzen Sie `bunkerweb.io/CONFIG_SITE`, wenn die Konfiguration auf einen einzelnen Dienst eingeschränkt werden soll
      (der Servername muss bereits existieren); lassen Sie die Annotation weg, um sie global anzuwenden.
    - Wird die Annotation entfernt oder die ConfigMap gelöscht, verschwindet die zugehörige benutzerdefinierte Konfiguration in BunkerWeb.

Für eine optimale Einrichtung wird empfohlen, BunkerWeb als **[DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)** zu definieren, was sicherstellt, dass auf allen Knoten ein Pod erstellt wird, während **Autoconf und Scheduler** als **einzeln repliziertes [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)** definiert werden.

Angesichts des Vorhandenseins mehrerer BunkerWeb-Instanzen ist es erforderlich, einen gemeinsamen Datenspeicher zu implementieren, der als [Redis](https://redis.io/)- oder [Valkey](https://valkey.io/)-Dienst realisiert wird. Dieser Dienst wird von den Instanzen genutzt, um Daten zwischen ihnen zu cachen und zu teilen. Weitere Informationen zu den Redis/Valkey-Einstellungen finden Sie [hier](features.md#redis).

!!! info "Datenbank-Backend"
    Bitte beachten Sie, dass unsere Anweisungen davon ausgehen, dass Sie MariaDB als Standard-Datenbank-Backend verwenden, wie durch die Einstellung `DATABASE_URI` konfiguriert. Wir verstehen jedoch, dass Sie möglicherweise alternative Backends für Ihre Docker-Integration bevorzugen. In diesem Fall können Sie sicher sein, dass auch andere Datenbank-Backends möglich sind. Weitere Informationen finden Sie in den docker-compose-Dateien im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc3/misc/integrations) des Repositorys.

    Die Einrichtung von geclusterten Datenbank-Backends liegt außerhalb des Geltungsbereichs dieser Dokumentation.

Bitte stellen Sie sicher, dass die Autoconf-Dienste Zugriff auf die Kubernetes-API haben. Es wird empfohlen, hierfür die [RBAC-Autorisierung](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) zu verwenden.

!!! warning "Benutzerdefinierte CA für die Kubernetes-API"
    Wenn Sie eine benutzerdefinierte CA für Ihre Kubernetes-API verwenden, können Sie eine Bundle-Datei mit Ihren Zwischen- und Stammzertifikaten auf dem Ingress-Controller mounten und den Umgebungswert `KUBERNETES_SSL_CA_CERT` auf den Pfad des Bundles im Container setzen. Alternativ können Sie, auch wenn es nicht empfohlen wird, die Zertifikatsüberprüfung deaktivieren, indem Sie die Umgebungsvariable `KUBERNETES_SSL_VERIFY` des Ingress-Controllers auf `no` setzen (Standard ist `yes`).

Darüber hinaus **ist es entscheidend, die Umgebungsvariable `KUBERNETES_MODE` auf `yes` zu setzen, wenn die Kubernetes-Integration verwendet wird**. Diese Variable ist für die ordnungsgemäße Funktionalität obligatorisch.

### Installationsmethoden

#### Verwendung des Helm-Charts (empfohlen)

Die empfohlene Methode zur Installation von Kubernetes ist die Verwendung des Helm-Charts, das unter `https://repo.bunkerweb.io/charts` verfügbar ist:

```shell
helm repo add bunkerweb https://repo.bunkerweb.io/charts
```

Sie können dann das BunkerWeb-Helm-Chart aus diesem Repository verwenden:

```shell
helm install -f myvalues.yaml mybunkerweb bunkerweb/bunkerweb
```

Die vollständige Liste der Werte ist in der Datei [charts/bunkerweb/values.yaml](https://github.com/bunkerity/bunkerweb-helm/blob/main/charts/bunkerweb/values.yaml) des [bunkerity/bunkerweb-helm-Repositorys](https://github.com/bunkerity/bunkerweb-helm) aufgeführt.

#### Vollständige YAML-Dateien

Anstatt das Helm-Chart zu verwenden, können Sie auch die YAML-Vorlagen im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc3/misc/integrations) des GitHub-Repositorys verwenden. Bitte beachten Sie, dass wir dringend empfehlen, stattdessen das Helm-Chart zu verwenden.

### Ingress-Ressourcen

Sobald der BunkerWeb-Kubernetes-Stack erfolgreich eingerichtet und betriebsbereit ist (weitere Informationen finden Sie in den Autoconf-Protokollen), können Sie mit der Bereitstellung von Webanwendungen im Cluster fortfahren und Ihre Ingress-Ressource deklarieren.

Es ist wichtig zu beachten, dass die BunkerWeb-Einstellungen als Annotationen für die Ingress-Ressource angegeben werden müssen. Für den Domain-Teil verwenden Sie bitte den speziellen Wert **`bunkerweb.io`**. Durch das Einfügen der entsprechenden Annotationen können Sie BunkerWeb entsprechend für die Ingress-Ressource konfigurieren.

!!! tip "Störende Annotationen ignorieren"
    Wenn einige Annotationen autoconf nicht beeinflussen sollen, setzen Sie `KUBERNETES_IGNORE_ANNOTATIONS` auf dem Controller-Deployment. Geben Sie eine durch Leerzeichen oder Kommas getrennte Liste von Annotationsschlüsseln an (zum Beispiel `bunkerweb.io/EXTRA_FOO`) oder nur das Suffix (`EXTRA_FOO`). Übereinstimmende Annotationen werden aus den vom Ingress abgeleiteten Einstellungen entfernt, und Pods, die sie tragen, werden bei der Instanzerkennung vollständig übersprungen.

!!! info "TLS-Unterstützung"
    Der BunkerWeb-Ingress-Controller unterstützt vollständig benutzerdefinierte HTTPS-Zertifikate unter Verwendung der TLS-Spezifikation, wie im Beispiel gezeigt. Die Konfiguration von Lösungen wie `cert-manager` zur automatischen Generierung von TLS-Secrets liegt außerhalb des Geltungsbereichs dieser Dokumentation.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    # Wird auf alle Hosts in diesem Ingress angewendet
    bunkerweb.io/MY_SETTING: "value"
    # Wird nur auf den Host www.example.com angewendet
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  # TLS ist optional, Sie können beispielsweise auch das integrierte Let's Encrypt verwenden
  # tls:
  #   - hosts:
  #       - www.example.com
  #     secretName: secret-example-tls
  rules:
    - host: www.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: svc-my-app
                port:
                  number: 8000
...
```

### Namespaces {#namespaces_1}

Ab Version `1.6.0` unterstützen die Autoconf-Stacks von BunkerWeb Namespaces. Mit dieser Funktion können Sie mehrere Cluster von BunkerWeb-Instanzen und -Diensten auf demselben Kubernetes-Cluster verwalten. Um Namespaces zu nutzen, setzen Sie einfach das Metadatenfeld `namespace` auf Ihre BunkerWeb-Instanzen und -Dienste. Hier ist ein Beispiel:

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: bunkerweb
  namespace: my-namespace # Setzen Sie den Namespace für die BunkerWeb-Instanz
...
```

!!! info "Namespace-Verhalten"

    Standardmäßig lauschen alle Autoconf-Stacks auf alle Namespaces. Wenn Sie einen Stack auf bestimmte Namespaces beschränken möchten, können Sie die Umgebungsvariable `NAMESPACES` im `bunkerweb-controller`-Deployment setzen:

    ```yaml
    ...
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-controller
      namespace: my-namespace # Setzen Sie den Namespace für den Controller
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-controller
      template:
        metadata:
          labels:
            app: bunkerweb-controller
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            - name: bunkerweb-controller
              image: bunkerity/bunkerweb-autoconf:1.6.6-rc3
              imagePullPolicy: Always
              env:
                - name: NAMESPACES
                  value: "my-namespace my-other-namespace" # Lauschen Sie nur auf diese Namespaces
                ...
    ...
    ```

    Beachten Sie, dass die Umgebungsvariable `NAMESPACES` eine durch Leerzeichen getrennte Liste von Namespaces ist.

!!! warning "Namespace-Spezifikationen"

    Es kann nur **eine Datenbank** und **ein Scheduler** pro Namespace geben. Wenn Sie versuchen, mehrere Datenbanken oder Scheduler im selben Namespace zu erstellen, kommt es zu Konfigurationskonflikten.

    Der Scheduler benötigt die `NAMESPACE`-Annotation nicht, um ordnungsgemäß zu funktionieren. Er benötigt nur die korrekt konfigurierte Einstellung `DATABASE_URI`, damit er auf dieselbe Datenbank wie der Autoconf-Dienst zugreifen kann.

### Ingress-Klasse

Bei der Installation mit den offiziellen Methoden in der Dokumentation wird BunkerWeb mit der folgenden `IngressClass`-Definition geliefert:

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: bunkerweb
spec:
  controller: bunkerweb.io/ingress-controller
```

Um die vom Ingress-Controller überwachten `Ingress`-Ressourcen einzuschränken, können Sie die Umgebungsvariable `KUBERNETES_INGRESS_CLASS` auf den Wert `bunkerweb` setzen. Dann können Sie die Direktive `ingressClassName` in Ihren `Ingress`-Definitionen nutzen:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    bunkerweb.io/MY_SETTING: "value"
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  ingressClassName: bunkerweb
  rules:
    - host: www.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: svc-my-app
                port:
                  number: 8000
```

### Benutzerdefinierter Domainname

Wenn Sie für Ihren Kubernetes-Cluster einen benutzerdefinierten Domainnamen anstelle des standardmäßigen `kubernetes.local` verwenden, können Sie den Wert über die Umgebungsvariable `KUBERNETES_DOMAIN_NAME` auf dem Scheduler-Container festlegen.

### Verwendung mit einem vorhandenen Ingress-Controller

!!! info "Beibehaltung des vorhandenen Ingress-Controllers und von BunkerWeb"

    Dies ist ein Anwendungsfall, bei dem Sie einen vorhandenen Ingress-Controller wie den Nginx-Controller beibehalten möchten. Der typische Datenfluss wird sein: Load Balancer => Ingress Controller => BunkerWeb => Anwendung.

#### Nginx-Ingress-Controller-Installation

Installieren Sie das Nginx-Ingress-Helm-Repo:

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
```

Installieren Sie den Nginx-Ingress-Controller mit Standardwerten (funktioniert möglicherweise nicht auf Ihrem eigenen Cluster sofort, bitte überprüfen Sie die [Dokumentation](https://kubernetes.github.io/ingress-nginx/)):

```bash
helm install --namespace nginx --create-namespace nginx ingress-nginx/ingress-nginx
```

Extrahieren Sie die IP-Adresse des LB:

```bash
kubectl get svc nginx-ingress-nginx-controller -n nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Richten Sie DNS-Einträge auf die IP-Adresse des LB ein (z. B. `bunkerweb`-Subdomain für die BW-UI und `myapp` für die Anwendung):

```bash
$ nslookup bunkerweb.example.com
Server:         172.26.112.1
Address:        172.26.112.1#53

Non-authoritative answer:
Name:   bunkerweb.example.com
Address: 1.2.3.4
$ nslookup myapp.example.com
Server:         172.26.112.1
Address:        172.26.112.1#53

Non-authoritative answer:
Name:   myapp.example.com
Address: 1.2.3.4
```

**BunkerWeb-Installation**

Installieren Sie das BunkerWeb-Helm-Repo:

```bash
helm repo add bunkerweb https://repo.bunkerweb.io/charts
helm repo update
```

Erstellen Sie die Datei `values.yaml`:

```yaml
# Hier richten wir die Werte ein, die für die Einrichtung von BunkerWeb hinter einem vorhandenen Ingress-Controller erforderlich sind
# Datenfluss mit BW: LB => vorhandener Ingress Controller => BunkerWeb => Dienst
# Datenfluss ohne BW: LB => vorhandener Ingress Controller => Dienst

# Globale Einstellungen
settings:
  misc:
    # Ersetzen Sie dies durch Ihren DNS-Resolver
    # um ihn zu erhalten: kubectl exec in einem zufälligen Pod, dann cat /etc/resolv.conf
    # wenn Sie eine IP als Nameserver haben, führen Sie eine umgekehrte DNS-Suche durch: nslookup <IP>
    # meistens ist es coredns.kube-system.svc.cluster.local oder kube-dns.kube-system.svc.cluster.local
    dnsResolvers: "kube-dns.kube-system.svc.cluster.local"
  kubernetes:
    # Wir berücksichtigen nur Ingress-Ressourcen mit ingressClass bunkerweb, um Konflikte mit dem vorhandenen Ingress-Controller zu vermeiden
    ingressClass: "bunkerweb"
    # Optional: Sie können Namespace(s) auswählen, in denen BunkerWeb auf Ingress/ConfigMap-Änderungen lauschen wird
    # Standard (leerer Wert) sind alle Namespaces
    namespaces: ""

# Überschreiben Sie den Diensttyp bunkerweb-external auf ClusterIP
# Da wir ihn nicht nach außen verfügbar machen müssen
# Wir werden den vorhandenen Ingress-Controller verwenden, um den Datenverkehr an BunkerWeb weiterzuleiten
service:
  type: ClusterIP

# BunkerWeb-Einstellungen
bunkerweb:
  tag: 1.6.6-rc3

# Scheduler-Einstellungen
scheduler:
  tag: 1.6.6-rc3
  extraEnvs:
    # Aktivieren Sie das Real-IP-Modul, um die echte IP der Clients zu erhalten
    - name: USE_REAL_IP
      value: "yes"

# Controller-Einstellungen
controller:
  tag: 1.6.6-rc3

# UI-Einstellungen
ui:
  tag: 1.6.6-rc3
```

Installieren Sie BunkerWeb mit benutzerdefinierten Werten:

```bash
helm install --namespace bunkerweb --create-namespace -f values.yaml bunkerweb bunkerweb/bunkerweb
```

Überprüfen Sie die Protokolle und warten Sie, bis alles bereit ist.

**Web-UI-Installation**

Richten Sie den folgenden Ingress ein (vorausgesetzt, der Nginx-Controller ist installiert):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ui-bunkerweb
  # Ersetzen Sie dies bei Bedarf durch Ihren Namespace von BW
  namespace: bunkerweb
  annotations:
    # HTTPS ist für die Web-UI obligatorisch, auch wenn der Datenverkehr intern ist
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    # Wir müssen SNI setzen, damit BW den richtigen vhost bedienen kann
    # Ersetzen Sie dies durch Ihre Domain
    nginx.ingress.kubernetes.io/proxy-ssl-name: "bunkerweb.example.com"
    nginx.ingress.kubernetes.io/proxy-ssl-server-name: "on"
spec:
  # Wird nur vom Nginx-Controller und nicht von BW bedient
  ingressClassName: nginx
  # Entkommentieren und bearbeiten, wenn Sie Ihr eigenes Zertifikat verwenden möchten
  # tls:
  # - hosts:
  #   - bunkerweb.example.com
  #   secretName: tls-secret
  rules:
  # Ersetzen Sie dies durch Ihre Domain
  - host: bunkerweb.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # Erstellt vom Helm-Chart
            name: bunkerweb-external
            port:
              # Die Verwendung des HTTPS-Ports ist für die UI obligatorisch
              number: 443
```

Und Sie können nun zum Einrichtungsassistenten gehen, indem Sie zu `https://bunkerweb.example.com/setup` navigieren.

**Schutz einer bestehenden Anwendung**

**Zuerst müssen Sie zu Global Config gehen, das SSL-Plugin auswählen und dann die automatische Weiterleitung von HTTP zu HTTPS deaktivieren. Bitte beachten Sie, dass Sie dies nur einmal tun müssen.**

Nehmen wir an, Sie haben eine Anwendung im Namespace `myapp`, die über den Dienst `myapp-service` auf Port `5000` zugänglich ist.

Sie müssen einen neuen Dienst in der Web-UI hinzufügen und die erforderlichen Informationen ausfüllen:

- Servername: die öffentlich zugängliche Domain Ihrer Anwendung (z. B. `myapp.example.com`)
- SSL/TLS: Ihr Ingress-Controller kümmert sich um diesen Teil, also aktivieren Sie es nicht auf BunkerWeb, da der Datenverkehr innerhalb des Clusters intern ist
- Reverse-Proxy-Host: die vollständige URL Ihrer Anwendung innerhalb des Clusters (z. B. `http://myapp-service.myapp.svc.cluster.local:5000`)

Sobald der neue Dienst hinzugefügt wurde, können Sie nun eine Ingress-Ressource für diesen Dienst deklarieren und ihn an den BunkerWeb-Dienst auf dem HTTP-Port weiterleiten:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  # Ersetzen Sie dies bei Bedarf durch Ihren Namespace von BW
  namespace: bunkerweb
spec:
  # Wird nur vom Nginx-Controller und nicht von BW bedient
  ingressClassName: nginx
  # Entkommentieren und bearbeiten, wenn Sie Ihr eigenes Zertifikat verwenden möchten
  # tls:
  # - hosts:
  #   - myapp.example.com
  #   secretName: tls-secret
  rules:
  # Ersetzen Sie dies durch Ihre Domain
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # Erstellt vom Helm-Chart
            name: bunkerweb-external
            port:
              number: 80
```

Sie können `http(s)://myapp.example.com` besuchen, das jetzt mit BunkerWeb geschützt ist 🛡️

## Swarm

<figure markdown>
  ![Übersicht](assets/img/integration-swarm.svg){ align=center, width="600" }
  <figcaption>Docker Swarm-Integration</figcaption>
</figure>

!!! warning "Veraltet"
    Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](#kubernetes).

!!! tip "PRO-Unterstützung"
    **Wenn Sie Swarm-Unterstützung benötigen**, kontaktieren Sie uns bitte unter [contact@bunkerity.com](mailto:contact@bunkerity.com) oder über das [Kontaktformular](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc).

!!! info "Docker Autoconf"
    Die Swarm-Integration ähnelt der Docker Autoconf-Integration (jedoch mit Diensten anstelle von Containern). Bitte lesen Sie bei Bedarf zuerst den [Docker Autoconf-Integrationsabschnitt](#docker-autoconf).

Um die automatische Konfiguration von BunkerWeb-Instanzen zu ermöglichen, benötigt der **autoconf**-Dienst Zugriff auf die Docker-API. Dieser Dienst lauscht auf Docker Swarm-Ereignisse wie die Erstellung oder Löschung von Diensten und konfiguriert die **BunkerWeb-Instanzen** nahtlos in Echtzeit ohne Ausfallzeiten. Er überwacht auch andere Swarm-Objekte wie [Konfigurationen](https://docs.docker.com/engine/swarm/configs/) für benutzerdefinierte Konfigurationen.

Ähnlich wie bei der [Docker Autoconf-Integration](#docker-autoconf) wird die Konfiguration für Webdienste über Labels definiert, die mit dem Präfix **bunkerweb** beginnen.

Für eine optimale Einrichtung wird empfohlen, den **BunkerWeb-Dienst** als ***globalen Dienst*** auf allen Knoten zu planen, während die **autoconf-, Scheduler- und Docker-API-Proxy-Dienste** als ***einzeln replizierte Dienste*** geplant werden sollten. Bitte beachten Sie, dass der Docker-API-Proxy-Dienst auf einem Manager-Knoten geplant werden muss, es sei denn, Sie konfigurieren ihn für die Verwendung einer Remote-API (was in der Dokumentation nicht behandelt wird).

Da mehrere Instanzen von BunkerWeb ausgeführt werden, muss ein gemeinsamer Datenspeicher implementiert als [Redis](https://redis.io/)- oder [Valkey](https://valkey.io/)-Dienst erstellt werden. Diese Instanzen nutzen den Redis/Valkey-Dienst, um Daten zu cachen und zu teilen. Weitere Details zu den Redis/Valkey-Einstellungen finden Sie [hier](features.md#redis).

Was das Datenbank-Volume betrifft, so gibt die Dokumentation keinen spezifischen Ansatz vor. Die Wahl eines freigegebenen Ordners oder eines bestimmten Treibers für das Datenbank-Volume hängt von Ihrem einzigartigen Anwendungsfall ab und bleibt dem Leser als Übung überlassen.

!!! info "Datenbank-Backend"
    Bitte beachten Sie, dass unsere Anweisungen davon ausgehen, dass Sie MariaDB als Standard-Datenbank-Backend verwenden, wie durch die Einstellung `DATABASE_URI` konfiguriert. Wir verstehen jedoch, dass Sie möglicherweise alternative Backends für Ihre Docker-Integration bevorzugen. In diesem Fall können Sie sicher sein, dass auch andere Datenbank-Backends möglich sind. Weitere Informationen finden Sie in den docker-compose-Dateien im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc3/misc/integrations) des Repositorys.

    Die Einrichtung von geclusterten Datenbank-Backends liegt außerhalb des Geltungsbereichs dieser Dokumentation.

Hier ist die Stack-Vorlage, die Sie mit `docker stack deploy` bereitstellen können:

```yaml
x-bw-env: &bw-env
  # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für beide Dienste zu vermeiden
  SWARM_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.6-rc3
    ports:
      - published: 80
        target: 8080
        mode: host
        protocol: tcp
      - published: 443
        target: 8443
        mode: host
        protocol: tcp
      - published: 443
        target: 8443
        mode: host
        protocol: udp # QUIC
    environment:
      <<: *bw-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services
    deploy:
      mode: global
      placement:
        constraints:
          - "node.role == worker"
      labels:
        - "bunkerweb.INSTANCE=yes" # Obligatorisches Label für den Autoconf-Dienst, um die BunkerWeb-Instanz zu identifizieren

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # Wir müssen die BunkerWeb-Instanz hier nicht angeben, da sie automatisch vom Autoconf-Dienst erkannt werden
      SERVER_NAME: "" # Der Servername wird mit Dienst-Labels gefüllt
      MULTISITE: "yes" # Obligatorische Einstellung für Autoconf
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
      USE_REDIS: "yes"
      REDIS_HOST: "bw-redis"
    volumes:
      - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.6-rc3
    environment:
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
      DOCKER_HOST: "tcp://bw-docker:2375" # Der Docker-Socket
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-docker
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-docker:
    image: tecnativa/docker-socket-proxy:nightly
    environment:
      CONFIGS: "1"
      CONTAINERS: "1"
      SERVICES: "1"
      SWARM: "1"
      TASKS: "1"
      LOG_LEVEL: "warning"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: "unless-stopped"
    networks:
      - bw-docker
    deploy:
      placement:
        constraints:
          - "node.role == manager"

  bw-db:
    image: mariadb:11
    # Wir setzen die maximal zulässige Paketgröße, um Probleme mit großen Abfragen zu vermeiden
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "changeme" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
    volumes:
      - bw-data:/var/lib/mysql
    restart: "unless-stopped"
    networks:
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-redis:
    image: redis:7-alpine
    restart: "unless-stopped"
    networks:
      - bw-universe
    deploy:
      placement:
        constraints:
          - "node.role == worker"

volumes:
  bw-data:
  bw-storage:

networks:
  bw-universe:
    name: bw-universe
    driver: overlay
    attachable: true
    ipam:
      config:
        - subnet: 10.20.30.0/24
  bw-services:
    name: bw-services
    driver: overlay
    attachable: true
  bw-docker:
    name: bw-docker
    driver: overlay
    attachable: true
  bw-db:
    name: bw-db
    driver: overlay
    attachable: true
```

!!! info "Obligatorische Swarm-Einstellung"
    Bitte beachten Sie, dass die Umgebungsvariable `SWARM_MODE: "yes"` bei Verwendung der Swarm-Integration obligatorisch ist.

!!! tip "Beschriftete Dienste überspringen"
    Müssen Sie einen Swarm-Dienst von autoconf ausschließen? Setzen Sie `SWARM_IGNORE_LABELS` auf dem Controller. Geben Sie eine durch Leerzeichen oder Kommas getrennte Liste von Label-Schlüsseln an (z.B. `bunkerweb.SERVER_NAME`) oder Suffixen (`SERVER_NAME`), und jeder Dienst mit diesen Labels wird bei der Erkennung ignoriert.

### Swarm-Dienste

Sobald der BunkerWeb-Swarm-Stack eingerichtet ist und läuft (weitere Informationen finden Sie in den Autoconf- und Scheduler-Protokollen), können Sie Webanwendungen im Cluster bereitstellen und Labels verwenden, um BunkerWeb dynamisch zu konfigurieren:

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerweb.MY_SETTING_1=value1"
        - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

### Namespaces {#namespaces_2}

Ab Version `1.6.0` unterstützen die Autoconf-Stacks von BunkerWeb Namespaces. Mit dieser Funktion können Sie mehrere "*Cluster*" von BunkerWeb-Instanzen und -Diensten auf demselben Docker-Host verwalten. Um Namespaces zu nutzen, setzen Sie einfach das `NAMESPACE`-Label auf Ihre Dienste. Hier ist ein Beispiel:

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerweb.NAMESPACE=my-namespace" # Setzen Sie den Namespace für den Dienst
        - "bunkerweb.MY_SETTING_1=value1"
        - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "Namespace-Verhalten"

    Standardmäßig lauschen alle Autoconf-Stacks auf alle Namespaces. Wenn Sie einen Stack auf bestimmte Namespaces beschränken möchten, können Sie die Umgebungsvariable `NAMESPACES` im `bw-autoconf`-Dienst setzen:

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc3
        ...
        deploy:
          mode: global
          placement:
            constraints:
              - "node.role == worker"
          labels:
            - "bunkerweb.INSTANCE=yes"
            - "bunkerweb.NAMESPACE=my-namespace" # Setzen Sie den Namespace für die BunkerWeb-Instanz
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc3
        environment:
          NAMESPACES: "my-namespace my-other-namespace" # Lauschen Sie nur auf diese Namespaces
          ...
        deploy:
          placement:
            constraints:
              - "node.role == worker"
    ...
    ```

    Beachten Sie, dass die Umgebungsvariable `NAMESPACES` eine durch Leerzeichen getrennte Liste von Namespaces ist.

!!! warning "Namespace-Spezifikationen"

    Es kann nur **eine Datenbank** und **ein Scheduler** pro Namespace geben. Wenn Sie versuchen, mehrere Datenbanken oder Scheduler im selben Namespace zu erstellen, kommt es zu Konfigurationskonflikten.

    Der Scheduler benötigt das `NAMESPACE`-Label nicht, um ordnungsgemäß zu funktionieren. Er benötigt nur die korrekt konfigurierte Einstellung `DATABASE_URI`, damit er auf dieselbe Datenbank wie der Autoconf-Dienst zugreifen kann.

## Microsoft Azure

<figure markdown>
  ![Übersicht](assets/img/integration-azure.webp){ align=center, width="600" }
  <figcaption>Azure-Integration</figcaption>
</figure>

!!! info "Empfohlene VM-Größe"
    Bitte beachten Sie bei der Wahl der VM-SKU. Sie müssen eine SKU auswählen, die mit Gen2-VMs kompatibel ist, und wir empfehlen, mit der B2s- oder Ds2-Serie für eine optimale Nutzung zu beginnen.

Sie können BunkerWeb auf verschiedene Weisen einfach in Ihrem Azure-Abonnement bereitstellen:

- Azure CLI in der Cloud Shell
- Azure ARM-Vorlage
- Azure-Portal über den Marketplace

=== "Cloud Shell"

    Erstellen Sie eine Ressourcengruppe. Ersetzen Sie den Wert `RG_NAME`

    ```bash
    az group create --name "RG_NAME" --location "LOCATION"
    ```

    Erstellen Sie eine VM mit der SKU `Standard_B2s` am Standort der Ressourcengruppe. Ersetzen Sie die Werte `RG_NAME`, `VM_NAME`, `VNET_NAME`, `SUBNET_NAME`

    ```bash

    az vm create --resource-group "RG_NAME" --name "VM_NAME" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --vnet-name "VNET_NAME" --size Standard_B2s --subnet "SUBNET_NAME"
    ```

    Vollständiger Befehl. Ersetzen Sie die Werte `RG_NAME`, `VM_NAME`, `LOCATION`, `HOSTNAME`, `USERNAME`, `PUBLIC_IP`, `VNET_NAME`, `SUBNET_NAME`, `NSG_NAME`

    ```bash
    az vm create --resource-group "RG_NAME" --name "VM_NAME" --location "LOCATION" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --computer-name "HOSTNAME" --admin-username "USERNAME" --public-ip-address "PUBLIC_IP" --public-ip-address-allocation Static --size Standard_B2s --public-ip-sku Standard --os-disk-delete-option Delete --nic-delete-option Delete --vnet-name "VNET_NAME" --subnet "SUBNET_NAME" --nsg "NSG_NAME"
    ```

=== "ARM-Vorlage"

    !!! info "Berechtigungsanforderung"
        Um eine ARM-Vorlage bereitzustellen, benötigen Sie Schreibzugriff auf die Ressourcen, die Sie bereitstellen, und Zugriff auf alle Operationen auf dem Ressourcentyp Microsoft.Resources/deployments.
        Um eine virtuelle Maschine bereitzustellen, benötigen Sie die Berechtigungen Microsoft.Compute/virtualMachines/write und Microsoft.Resources/deployments/*. Die What-if-Operation hat dieselben Berechtigungsanforderungen.

    Stellen Sie die ARM-Vorlage bereit:

    [![Bereitstellen in Azure](assets/img/integration-azure-deploy.svg)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fbunkerity%2Fbunkerweb%2Fmaster%2Fmisc%2Fintegrations%2Fazure-arm-template.json){:target="_blank"}

=== "Marketplace"

    Melden Sie sich im [Azure-Portal](https://portal.azure.com){:target="_blank"} an.

    Holen Sie sich BunkerWeb über das Menü [Ressource erstellen](https://portal.azure.com/#view/Microsoft_Azure_Marketplace/GalleryItemDetailsBladeNopdl/id/bunkerity.bunkerweb){:target="_blank"}.

    Sie können auch über den [Marketplace](https://azuremarketplace.microsoft.com/fr-fr/marketplace/apps/bunkerity.bunkerweb?tab=Overview){:target="_blank"} gehen.

Sie können auf den Einrichtungsassistenten zugreifen, indem Sie die URI `https://ihre-ip-adresse/setup` Ihrer virtuellen Maschine aufrufen.
