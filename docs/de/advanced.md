# Fortgeschrittene Nutzungen

Viele Beispiele für reale Anwendungsfälle sind im Ordner [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/examples) des GitHub-Repositorys verfügbar.

Wir stellen auch zahlreiche Boilerplates zur Verfügung, wie z. B. YAML-Dateien für verschiedene Integrationen und Datenbanktypen. Diese sind im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/misc/integrations) verfügbar.

Dieser Abschnitt konzentriert sich nur auf fortgeschrittene Nutzungen und Sicherheits-Tuning. Informationen zu allen verfügbaren Einstellungen finden Sie im [Features-Abschnitt](features.md) der Dokumentation.

!!! tip "Testen"
    Um schnelle Tests durchzuführen, wenn der Multisite-Modus aktiviert ist (und wenn Sie nicht die richtigen DNS-Einträge für die Domains eingerichtet haben), können Sie `curl` mit dem HTTP-Host-Header Ihrer Wahl verwenden:
    ```shell
    curl -H "Host: app1.example.com" http://ip-oder-fqdn-des-servers
    ```

    Wenn Sie HTTPS verwenden, müssen Sie mit SNI spielen:
    ```shell
    curl -H "Host: app1.example.com" --resolve example.com:443:ip-des-servers https://example.com
    ```

## Hinter einem Load Balancer oder Reverse Proxy {#behind-load-balancer-or-reverse-proxy}

!!! info "Echte IP"

    Wenn BunkerWeb selbst hinter einem Load Balancer oder einem Reverse Proxy steht, müssen Sie es so konfigurieren, dass es die echte IP-Adresse der Clients erhält. **Wenn Sie dies nicht tun, werden die Sicherheitsfunktionen die IP-Adresse des Load Balancers oder Reverse Proxys anstelle der des Clients blockieren**.

BunkerWeb unterstützt tatsächlich zwei Methoden, um die echte IP-Adresse des Clients abzurufen:

- Verwendung des `PROXY-Protokolls`
- Verwendung eines HTTP-Headers wie `X-Forwarded-For`

Die folgenden Einstellungen können verwendet werden:

- `USE_REAL_IP`: Aktivieren/Deaktivieren des Abrufs der echten IP
- `USE_PROXY_PROTOCOL`: Aktivieren/Deaktivieren der Unterstützung des PROXY-Protokolls.
- `REAL_IP_FROM`: Liste der vertrauenswürdigen IP-/Netzwerkadressen, die uns die "echte IP" senden dürfen
- `REAL_IP_HEADER`: Der HTTP-Header, der die echte IP enthält, oder der spezielle Wert `proxy_protocol` bei Verwendung des PROXY-Protokolls

Weitere Einstellungen zur echten IP finden Sie im [Features-Abschnitt](features.md#real-ip) der Dokumentation.

=== "HTTP-Header"

    Wir gehen von Folgendem bezüglich der Load Balancer oder Reverse Proxys aus (Sie müssen die Einstellungen entsprechend Ihrer Konfiguration anpassen):

    - Sie verwenden den `X-Forwarded-For`-Header, um die echte IP festzulegen
    - Sie haben IPs in den Netzwerken `1.2.3.0/24` und `100.64.0.0/10`

    === "Web-UI"

        Navigieren Sie zur Seite **Globale Einstellungen**, wählen Sie das Plugin **Real IP** und füllen Sie die folgenden Einstellungen aus:

        <figure markdown>![Real IP Einstellungen (Header) mit Web-UI](assets/img/advanced-proxy1.png){ align=center }<figcaption>Real IP Einstellungen (Header) mit Web-UI</figcaption></figure>

        Bitte beachten Sie, dass es empfohlen wird, BunkerWeb neu zu starten, wenn Sie Einstellungen im Zusammenhang mit der echten IP ändern.

    === "Linux"

        Sie müssen die Einstellungen zur Datei `/etc/bunkerweb/variables.env` hinzufügen:

        ```conf
        ...
        USE_REAL_IP=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=X-Forwarded-For
        ...
        ```

        Bitte beachten Sie, dass es empfohlen wird, einen Neustart anstelle eines Neuladens durchzuführen, wenn Sie Einstellungen im Zusammenhang mit der echten IP konfigurieren:

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "All-in-one"

        Sie müssen die Einstellungen zu den Umgebungsvariablen hinzufügen, wenn Sie den All-in-one-Container ausführen:

        ```bash
        docker run -d \
            --name bunkerweb-aio \
            -v bw-storage:/data \
            -e USE_REAL_IP="yes" \
            -e REAL_IP_FROM="1.2.3.0/24 100.64.0.0/10" \
            -e REAL_IP_HEADER="X-Forwarded-For" \
            -p 80:8080/tcp \
            -p 443:8443/tcp \
            -p 443:8443/udp \
            bunkerity/bunkerweb-all-in-one:1.6.8-rc3
        ```

        Bitte beachten Sie, dass Sie, wenn Ihr Container bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen aktualisiert werden.

    === "Docker"

        Sie müssen die Einstellungen zu den Umgebungsvariablen sowohl des BunkerWeb- als auch des Scheduler-Containers hinzufügen:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Bitte beachten Sie, dass Sie, wenn Ihr Container bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen aktualisiert werden.

    === "Docker autoconf"

        Sie müssen die Einstellungen zu den Umgebungsvariablen sowohl des BunkerWeb- als auch des Scheduler-Containers hinzufügen:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Bitte beachten Sie, dass Sie, wenn Ihr Container bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen aktualisiert werden.

    === "Kubernetes"

        Sie müssen die Einstellungen zu den Umgebungsvariablen sowohl der BunkerWeb- als auch der Scheduler-Pods hinzufügen.

        Hier ist der entsprechende Teil Ihrer `values.yaml`-Datei, den Sie verwenden können:

        ```yaml
        bunkerweb:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "X-Forwarded-For"
        scheduler:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "X-Forwarded-For"
        ```

    === "Swarm"

        !!! warning "Veraltet"
            Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](integrations.md#kubernetes).

            **Weitere Informationen finden Sie in der [Swarm-Integrationsdokumentation](integrations.md#swarm).**

        Sie müssen die Einstellungen zu den Umgebungsvariablen sowohl der BunkerWeb- als auch der Scheduler-Dienste hinzufügen:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Bitte beachten Sie, dass Sie, wenn Ihr Dienst bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen aktualisiert werden.

=== "Proxy-Protokoll"

    !!! warning "Sorgfältig lesen"

        Verwenden Sie das PROXY-Protokoll nur, wenn Sie sicher sind, dass Ihr Load Balancer oder Reverse Proxy es sendet. **Wenn Sie es aktivieren und es nicht verwendet wird, erhalten Sie Fehler**.

    Wir gehen von Folgendem bezüglich der Load Balancer oder Reverse Proxys aus (Sie müssen die Einstellungen entsprechend Ihrer Konfiguration anpassen):

    - Sie verwenden das `PROXY-Protokoll` v1 oder v2, um die echte IP festzulegen
    - Sie haben IPs in den Netzwerken `1.2.3.0/24` und `100.64.0.0/10`

    === "Web-UI"

        Navigieren Sie zur Seite **Globale Einstellungen**, wählen Sie das Plugin **Real IP** und füllen Sie die folgenden Einstellungen aus:

        <figure markdown>![Real IP Einstellungen (PROXY-Protokoll) mit Web-UI](assets/img/advanced-proxy2.png){ align=center }<figcaption>Real IP Einstellungen (PROXY-Protokoll) mit Web-UI</figcaption></figure>

        Bitte beachten Sie, dass es empfohlen wird, BunkerWeb neu zu starten, wenn Sie Einstellungen im Zusammenhang mit der echten IP ändern.

    === "Linux"

        Sie müssen die Einstellungen zur Datei `/etc/bunkerweb/variables.env` hinzufügen:

        ```conf
        ...
        USE_REAL_IP=yes
        USE_PROXY_PROTOCOL=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=proxy_protocol
        ...
        ```

        Bitte beachten Sie, dass es empfohlen wird, einen Neustart anstelle eines Neuladens durchzuführen, wenn Sie Einstellungen im Zusammenhang mit Proxy-Protokollen konfigurieren:

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "All-in-one"

        Sie müssen die Einstellungen zu den Umgebungsvariablen hinzufügen, wenn Sie den All-in-one-Container ausführen:

        ```bash
        docker run -d \
            --name bunkerweb-aio \
            -v bw-storage:/data \
            -e USE_REAL_IP="yes" \
            -e USE_PROXY_PROTOCOL="yes" \
            -e REAL_IP_FROM="1.2.3.0/24 100.64.0.0/10" \
            -e REAL_IP_HEADER="proxy_protocol" \
            -p 80:8080/tcp \
            -p 443:8443/tcp \
            -p 443:8443/udp \
            bunkerity/bunkerweb-all-in-one:1.6.8-rc3
        ```

        Bitte beachten Sie, dass Sie, wenn Ihr Container bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen aktualisiert werden.

    === "Docker"

        Sie müssen die Einstellungen zu den Umgebungsvariablen sowohl des BunkerWeb- als auch des Scheduler-Containers hinzufügen:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Bitte beachten Sie, dass Sie, wenn Ihr Container bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen aktualisiert werden.

    === "Docker autoconf"

        Sie müssen die Einstellungen zu den Umgebungsvariablen sowohl des BunkerWeb- als auch des Scheduler-Containers hinzufügen:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Bitte beachten Sie, dass Sie, wenn Ihr Container bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen aktualisiert werden.

    === "Kubernetes"

        Sie müssen die Einstellungen zu den Umgebungsvariablen sowohl der BunkerWeb- als auch der Scheduler-Pods hinzufügen.

        Hier ist der entsprechende Teil Ihrer `values.yaml`-Datei, den Sie verwenden können:

        ```yaml
        bunkerweb:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: USE_PROXY_PROTOCOL
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "proxy_protocol"
        scheduler:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: USE_PROXY_PROTOCOL
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "proxy_protocol"
        ```

    === "Swarm"

        !!! warning "Veraltet"
            Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](integrations.md#kubernetes).

            **Weitere Informationen finden Sie in der [Swarm-Integrationsdokumentation](integrations.md#swarm).**

        Sie müssen die Einstellungen zu den Umgebungsvariablen sowohl der BunkerWeb- als auch der Scheduler-Dienste hinzufügen.

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Bitte beachten Sie, dass Sie, wenn Ihr Dienst bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen aktualisiert werden.

## Hochverfügbarkeit und Load Balancing

Damit Ihre Anwendungen auch bei einem Serverausfall erreichbar bleiben, können Sie BunkerWeb als **HA-Cluster** bereitstellen. Die Architektur besteht aus einem **Manager** (Scheduler), der die Konfiguration orchestriert, und mehreren **Workern** (BunkerWeb-Instanzen), die den Verkehr verarbeiten.

```mermaid
flowchart LR

  %% ================ Styles =================
  classDef manager     fill:#eef2ff,stroke:#4c1d95,stroke-width:1px,rx:6px,ry:6px;
  classDef component     fill:#f9fafb,stroke:#6b7280,stroke-width:1px,rx:4px,ry:4px;
  classDef lb            fill:#e0f2fe,stroke:#0369a1,stroke-width:1px,rx:6px,ry:6px;
  classDef database fill:#d1fae5,stroke:#059669,stroke-width:1px,rx:4px,ry:4px;
  classDef datastore     fill:#fee2e2,stroke:#b91c1c,stroke-width:1px,rx:4px,ry:4px;
  classDef backend       fill:#ede9fe,stroke:#7c3aed,stroke-width:1px,rx:4px,ry:4px;
  classDef client        fill:#e5e7eb,stroke:#4b5563,stroke-width:1px,rx:4px,ry:4px;

  %% Container styles
  style CLUSTER fill:#f3f4f6,stroke:#d1d5db,stroke-width:1px,stroke-dasharray:6 3;
  style WORKERS fill:none,stroke:#9ca3af,stroke-width:1px,stroke-dasharray:4 2;

  %% ============== Outside left =============
  Client["Client"]:::client
  LB["Load Balancer"]:::lb

  %% ============== Cluster ==================
  subgraph CLUSTER[" "]
    direction TB

    %% ---- Top row: Manager + Redis ----
    subgraph TOP["Manager & Data Stores"]
      direction LR
      Manager["Manager<br/>(Scheduler)"]:::manager
      BDD["BDD"]:::database
      Redis["Redis/Valkey"]:::datastore
      UI["Weboberfläche"]:::manager
    end

    %% ---- Middle: Workers ----
    subgraph WORKERS["Workers (BunkerWeb)"]
      direction TB
      Worker1["Worker 1"]:::component
      WorkerN["Worker N"]:::component
    end

    %% ---- Bottom: App ----
    App["App"]:::backend
  end

  %% ============ Outside right ============
  Admin["Admin"]:::client

  %% ============ Traffic & control ===========
  %% Manager / control plane
  Manager -->|API 5000| Worker1
  Manager -->|API 5000| WorkerN
  Manager -->|bwcli| Redis
  Manager -->|Config| BDD

  %% User interface (UI)
  UI -->|Config| BDD
  UI -->|Reports / Bans| Redis
  BDD --- UI
  Redis --- UI
  linkStyle 6 stroke-width:0px;
  linkStyle 7 stroke-width:0px;

  %% Workers <-> Redis
  Worker1 -->|Gemeinsamer Cache| Redis
  WorkerN -->|Gemeinsamer Cache| Redis

  %% Workers -> App
  Worker1 -->|Legitimer Verkehr| App
  WorkerN -->|Legitimer Verkehr| App

  %% Client (right side) -> Load balancer -> Workers -> App
  Client -->|Request| LB
  LB -->|HTTP/TCP| Worker1
  LB -->|HTTP/TCP| WorkerN

  %% Admin -> UI
  UI --- Admin
  Admin -->|HTTP| UI
  linkStyle 15 stroke-width:0px;
```

!!! info "BunkerWeb APIs verstehen"
    BunkerWeb unterscheidet zwei API-Konzepte:

    - Eine **interne API**, die Manager und Worker automatisch für die Orchestrierung verbindet. Sie ist immer aktiv und benötigt keine manuelle Konfiguration.
    - Einen optionalen **API-Dienst** (`bunkerweb-api`), der eine öffentliche REST-Schnittstelle für Automatisierungstools (bwcli, CI/CD usw.) bereitstellt. Er ist auf Linux-Installationen standardmäßig deaktiviert und unabhängig von der internen Kommunikation zwischen Manager und Workern.

### Voraussetzungen

Stellen Sie vor dem Aufbau eines Clusters sicher, dass Sie Folgendes haben:

- **Mindestens 2 Linux-Hosts** mit Root-/Sudo-Zugriff.
- **Netzwerkkonnektivität** zwischen den Hosts (insbesondere TCP-Port 5000 für die interne API).
- **IP oder Hostname** der zu schützenden Anwendung.
- *(Optional)* **Load Balancer** (z. B. HAProxy), um den Verkehr auf die Worker zu verteilen.

### 1. Manager installieren

Der Manager ist das Gehirn des Clusters. Er führt den Scheduler, die Datenbank und optional die Weboberfläche aus.

!!! warning "Sicherheit der Weboberfläche"
    Die Weboberfläche lauscht auf einem eigenen Port (Standard 7000) und sollte nur Administratoren zugänglich sein. Wenn Sie die UI ins Internet exponieren, **empfehlen wir dringend**, sie vor einen BunkerWeb zu stellen.

=== "Linux"

    1. **Installationsskript herunterladen und ausführen** auf dem Manager-Host:

        ```bash
        # Skript und Checksumme laden
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.8-rc3/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.8-rc3/install-bunkerweb.sh.sha256

        # Prüfsumme verifizieren
        sha256sum -c install-bunkerweb.sh.sha256

        # Installer ausführen
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh
        ```

        !!! danger "Sicherheitshinweis"
            Überprüfen Sie immer die Integrität des Skripts mit der bereitgestellten Prüfsumme, bevor Sie es ausführen.

    2. **Option 2) Manager** wählen und den Anweisungen folgen:

        | Eingabe                   | Aktion                                                                                                               |
        | :------------------------ | :------------------------------------------------------------------------------------------------------------------- |
        | **BunkerWeb-Instanzen**   | Geben Sie die IPs Ihrer Worker-Knoten mit Leerzeichen getrennt an (z. B. `192.168.10.11 192.168.10.12`).             |
        | **Whitelist IP**          | Übernehmen Sie die erkannte IP oder geben Sie ein Subnetz ein (z. B. `192.168.10.0/24`), um API-Zugriff zu erlauben. |
        | **DNS-Resolver**          | Drücken Sie `N` für den Standardwert oder geben Sie eigene an.                                                       |
        | **HTTPS für interne API** | **Empfohlen:** `Y`, um Zertifikate zu erzeugen und die Manager-Worker-Kommunikation zu sichern.                      |
        | **Web-UI-Dienst**         | `Y`, um die Weboberfläche zu aktivieren (stark empfohlen).                                                           |
        | **API-Dienst**            | `N`, sofern Sie die öffentliche REST-API nicht benötigen.                                                            |

    #### UI absichern und bereitstellen

    Wenn Sie die Weboberfläche aktiviert haben, sollten Sie sie absichern. Sie kann auf dem Manager oder auf einem separaten Host laufen.

    === "Auf dem Manager gehostet"

        1. Bearbeiten Sie `/etc/bunkerweb/ui.env`, um starke Zugangsdaten zu setzen:

        ```ini
        # OVERRIDE_ADMIN_CREDS=no
        ADMIN_USERNAME=admin
        ADMIN_PASSWORD=changeme
        # FLASK_SECRET=changeme
        # TOTP_ENCRYPTION_KEYS=changeme
        LISTEN_ADDR=0.0.0.0
        # LISTEN_PORT=7000
        FORWARDED_ALLOW_IPS=127.0.0.1,::1
        # ENABLE_HEALTHCHECK=no
        ```

        !!! warning "Standardzugangsdaten ändern"
            Ersetzen Sie `admin` und `changeme` durch starke Zugangsdaten, bevor Sie den UI-Dienst produktiv starten.

        2. UI neu starten:

        ```bash
        sudo systemctl restart bunkerweb-ui
        ```

    === "Externer Host"

        Für bessere Isolation können Sie die UI auf einem separaten Knoten installieren.

        1. Führen Sie den Installer aus und wählen Sie **Option 5) Web UI Only**.
        2. Bearbeiten Sie `/etc/bunkerweb/ui.env`, um die Verbindung zur Manager-Datenbank herzustellen:

            ```ini
            # Datenbank-Konfiguration (muss zur Manager-Datenbank passen)
            DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@db-host:3306/bunkerweb
            # Für PostgreSQL: postgresql://bunkerweb:changeme@db-host:5432/bunkerweb
            # Für MySQL: mysql+pymysql://bunkerweb:changeme@db-host:3306/bunkerweb

            # Redis-Konfiguration (falls Redis/Valkey für Persistenz genutzt wird)
            # Wenn nicht angegeben, wird sie automatisch aus der Datenbank übernommen
            # REDIS_HOST=redis-host

            # Sicherheits-Zugangsdaten
            ADMIN_USERNAME=admin
            ADMIN_PASSWORD=changeme

            # Netzwerk-Einstellungen
            LISTEN_ADDR=0.0.0.0
            # LISTEN_PORT=7000
            ```

        3. Dienst neu starten:

            ```bash
            sudo systemctl restart bunkerweb-ui
            ```

        !!! tip "Firewall-Konfiguration"
            Stellen Sie sicher, dass der UI-Host die Datenbank- und Redis-Ports erreichen kann. Gegebenenfalls müssen Sie Firewall-Regeln auf UI- und DB/Redis-Hosts anpassen.

=== "Docker"

    Erstellen Sie eine `docker-compose.yml` auf dem Manager-Host:

    ```yaml title="docker-compose.yml"
    x-ui-env: &bw-ui-env
      # Wir verwenden einen Anchor, um die Umgebungsvariablen nicht zu duplizieren
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Verwenden Sie ein stärkeres Passwort

    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: "192.168.1.11 192.168.1.12" # Ersetzen durch die IPs Ihrer Worker
          API_WHITELIST_IP: "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16" # Lokale Netze erlauben
          # API_LISTEN_HTTPS: "yes" # Empfohlen zur Absicherung der internen API
          # API_TOKEN: "my_secure_token" # Optional: zusätzliches Token
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # Persistenz für Cache und Backups
        restart: "unless-stopped"
        networks:
          - bw-db
          - bw-redis

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.8-rc3
        ports:
          - "7000:7000" # UI-Port veröffentlichen
        environment:
          <<: *bw-ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Bitte stärkeres Passwort setzen
          TOTP_ENCRYPTION_KEYS: "mysecret" # Stärkeren Schlüssel setzen (siehe Voraussetzungen)
        restart: "unless-stopped"
        networks:
          - bw-db
          - bw-redis

      bw-db:
        image: mariadb:11
        # Maximale Paketgröße setzen, um Probleme mit großen Queries zu vermeiden
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Bitte stärkeres Passwort setzen
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis zur Persistenz von Reports/Bans/Stats
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
          - bw-redis

    volumes:
      bw-data:
      bw-storage:
      redis-data:

    networks:
      bw-db:
        name: bw-db
      bw-redis:
        name: bw-redis
    ```

    Manager-Stack starten:

    ```bash
    docker compose up -d
    ```

### 2. Worker installieren

Worker sind die Knoten, die den eingehenden Verkehr verarbeiten.

=== "Linux"

    1. **Führen Sie den Installer** auf jedem Worker aus (gleiche Befehle wie beim Manager).
    2. **Option 3) Worker** auswählen und konfigurieren:

        | Eingabe                   | Aktion                                                   |
        | :------------------------ | :------------------------------------------------------- |
        | **Manager-IP**            | IP des Managers eingeben (z. B. `192.168.10.10`).        |
        | **HTTPS für interne API** | Muss zur Einstellung des Managers passen (`Y` oder `N`). |

    Der Worker registriert sich automatisch beim Manager.

=== "Docker"

    Erstellen Sie eine `docker-compose.yml` auf jedem Worker:

    ```yaml title="docker-compose.yml"
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC / HTTP3 Unterstützung
          - "5000:5000/tcp" # Port der internen API
        environment:
          API_WHITELIST_IP: "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"
          # API_LISTEN_HTTPS: "yes" # Empfohlen, muss zur Manager-Einstellung passen
          # API_TOKEN: "my_secure_token" # Optional: Token, muss zum Manager passen
        restart: "unless-stopped"
    ```

    Worker starten:

    ```bash
    docker compose up -d
    ```

### 3. Worker verwalten

Sie können später weitere Worker über die Weboberfläche oder CLI hinzufügen.

=== "Über die Weboberfläche"

    1. **Zum Reiter Instances gehen**.
    2. **Auf Add instance klicken**.
    3. **IP/Hostname des Workers eintragen** und speichern.

    <div class="grid grid-2" markdown style="display:grid; align-items:center;">
    <figure markdown style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%;">
      ![BunkerWeb UI - Instanz anlegen](assets/img/ui-ha-create-instance.webp){ width="100%" }
      <figcaption>BunkerWeb UI - Instanz anlegen</figcaption>
    </figure>
    <figure markdown style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%;">
      ![BunkerWeb UI - Instanzformular](assets/img/ui-ha-create-instance-form.webp){ width="100%" }
      <figcaption>BunkerWeb UI - Instanzformular</figcaption>
    </figure>
    </div>

=== "Per Konfiguration"

    === "Linux"

        1. **Bearbeiten** Sie `/etc/bunkerweb/variables.env` auf dem Manager:

            ```bash
            BUNKERWEB_INSTANCES=192.168.10.11 192.168.10.12 192.168.10.13
            ```

        2. **Scheduler neu starten**:

            ```bash
            sudo systemctl restart bunkerweb-scheduler
            ```

    === "Docker"

        1. **Bearbeiten** Sie die `docker-compose.yml` auf dem Manager und aktualisieren Sie `BUNKERWEB_INSTANCES`.

        2. **Scheduler-Container neu erstellen**:

            ```bash
            docker compose up -d bw-scheduler
            ```

### 4. Einrichtung prüfen

=== "Linux"

    1. **Status prüfen**: Melden Sie sich an der UI an (`http://<manager-ip>:7000`) und öffnen Sie den Tab **Instances**. Alle Worker sollten **Up** sein.
    2. **Failover testen**: Stoppen Sie BunkerWeb auf einem Worker (`sudo systemctl stop bunkerweb`) und prüfen Sie, ob der Verkehr weiterläuft.

=== "Docker"

    1. **Status prüfen**: Melden Sie sich an der UI an (`http://<manager-ip>:7000`) und öffnen Sie den Tab **Instances**. Alle Worker sollten **Up** sein.
    2. **Failover testen**: Stoppen Sie BunkerWeb auf einem Worker (`docker compose stop bunkerweb`) und prüfen Sie, ob der Verkehr weiterläuft.

### 5. Load Balancing

Um den Verkehr über Ihre Worker zu verteilen, verwenden Sie einen Load Balancer. Empfohlen ist ein Layer-4-(TCP)-Load-Balancer mit **PROXY protocol**, um die Client-IP beizubehalten.

=== "HAProxy - Layer 4 (TCP)"

    Beispielkonfiguration für **HAProxy** im TCP-Modus mit **PROXY protocol** zur Weitergabe der Client-IP.

    ```cfg title="haproxy.cfg"
    defaults
        timeout connect 5s
        timeout client 5s
        timeout server 5s

    frontend http_front
        mode tcp
        bind *:80
        default_backend http_back

    frontend https_front
        mode tcp
        bind *:443
        default_backend https_back

    backend http_back
        mode tcp
        balance roundrobin
        server worker01 192.168.10.11:80 check send-proxy-v2
        server worker02 192.168.10.12:80 check send-proxy-v2

    backend https_back
        mode tcp
        balance roundrobin
        server worker01 192.168.10.11:443 check send-proxy-v2
        server worker02 192.168.10.12:443 check send-proxy-v2
    ```

=== "HAProxy - Layer 7 (HTTP)"

    Beispielkonfiguration für **HAProxy** im Layer-7-(HTTP)-Modus. Sie fügt den Header `X-Forwarded-For` hinzu, damit BunkerWeb die Client-IP erhält.

    ```cfg title="haproxy.cfg"
    defaults
        timeout connect 5s
        timeout client 5s
        timeout server 5s

    frontend http_front
        mode http
        bind *:80
        default_backend http_back

    frontend https_front
        mode http
        bind *:443
        default_backend https_back

    backend http_back
        mode http
        balance roundrobin
        option forwardfor
        server worker01 192.168.10.11:80 check
        server worker02 192.168.10.12:80 check

    backend https_back
        mode http
        balance roundrobin
        option forwardfor
        server worker01 192.168.10.11:443 check
        server worker02 192.168.10.12:443 check
    ```

HAProxy neu laden, nachdem die Konfiguration gespeichert wurde:

```bash
sudo systemctl restart haproxy
```

Weitere Informationen finden Sie in der [offiziellen HAProxy-Dokumentation](http://docs.haproxy.org/).

!!! tip "Echte IP konfigurieren"
    Vergessen Sie nicht, BunkerWeb so zu konfigurieren, dass die echte Client-IP ankommt (PROXY protocol oder X-Forwarded-For).

    Siehe Abschnitt [Hinter einem Load Balancer oder Reverse Proxy](#behind-load-balancer-or-reverse-proxy), um sicherzustellen, dass Sie die richtige Client-IP erhalten.

    Prüfen Sie `/var/log/bunkerweb/access.log` auf jedem Worker, ob Anfragen aus dem PROXY-protocol-Netz kommen und beide Worker Last erhalten. Ihr BunkerWeb-Cluster ist nun bereit für produktive Hochverfügbarkeit.

## Verwendung benutzerdefinierter DNS-Auflösungsmechanismen

BunkerWebs NGINX-Konfiguration kann angepasst werden, um je nach Ihren Bedürfnissen unterschiedliche DNS-Resolver zu verwenden. Dies kann in verschiedenen Szenarien besonders nützlich sein:

1.  Um Einträge in Ihrer lokalen `/etc/hosts`-Datei zu berücksichtigen
2.  Wenn Sie für bestimmte Domains benutzerdefinierte DNS-Server verwenden müssen
3.  Zur Integration mit lokalen DNS-Caching-Lösungen

### Verwendung von systemd-resolved

Viele moderne Linux-Systeme verwenden `systemd-resolved` für die DNS-Auflösung. Wenn Sie möchten, dass BunkerWeb den Inhalt Ihrer `/etc/hosts`-Datei respektiert und den DNS-Auflösungsmechanismus des Systems verwendet, können Sie es so konfigurieren, dass es den lokalen systemd-resolved DNS-Dienst verwendet.

Um zu überprüfen, ob systemd-resolved auf Ihrem System läuft, können Sie Folgendes verwenden:

```bash
systemctl status systemd-resolved
```

Um systemd-resolved als Ihren DNS-Resolver in BunkerWeb zu aktivieren, setzen Sie die Einstellung `DNS_RESOLVERS` auf `127.0.0.53`, was die Standard-Listenadresse für systemd-resolved ist:

=== "Web-UI"

    Navigieren Sie zur Seite **Globale Einstellungen** und setzen Sie die DNS-Resolver auf `127.0.0.53`

    <figure markdown>![DNS-Resolver-Einstellung mit Web-UI](assets/img/advanced-dns-resolvers.png){ align=center }<figcaption>DNS-Resolver-Einstellung mit Web-UI</figcaption></figure>

=== "Linux"

    Sie müssen die Datei `/etc/bunkerweb/variables.env` ändern:

    ```conf
    ...
    DNS_RESOLVERS=127.0.0.53
    ...
    ```

    Nach dieser Änderung laden Sie den Scheduler neu, um die Konfiguration anzuwenden:

    ```shell
    sudo systemctl reload bunkerweb-scheduler
    ```

### Verwendung von dnsmasq

[dnsmasq](http://www.thekelleys.org.uk/dnsmasq/doc.html) ist ein leichtgewichtiger DNS-, DHCP- und TFTP-Server, der häufig für lokales DNS-Caching und Anpassungen verwendet wird. Er ist besonders nützlich, wenn Sie mehr Kontrolle über Ihre DNS-Auflösung benötigen, als systemd-resolved bietet.

=== "Linux"

    Installieren und konfigurieren Sie zuerst dnsmasq auf Ihrem Linux-System:

    === "Debian/Ubuntu"

        ```bash
        # dnsmasq installieren
        sudo apt-get update && sudo apt-get install dnsmasq

        # dnsmasq so konfigurieren, dass es nur auf localhost lauscht
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # Bei Bedarf benutzerdefinierte DNS-Einträge hinzufügen
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # dnsmasq neu starten
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    === "RHEL/Fedora"

        ```bash
        # dnsmasq installieren
        sudo dnf install dnsmasq

        # dnsmasq so konfigurieren, dass es nur auf localhost lauscht
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # Bei Bedarf benutzerdefinierte DNS-Einträge hinzufügen
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # dnsmasq neu starten
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    Konfigurieren Sie dann BunkerWeb, um dnsmasq zu verwenden, indem Sie `DNS_RESOLVERS` auf `127.0.0.1` setzen:

    === "Web-UI"

        Navigieren Sie zur Seite **Globale Einstellungen**, wählen Sie das **NGINX**-Plugin und setzen Sie die DNS-Resolver auf `127.0.0.1`.

        <figure markdown>![DNS-Resolver-Einstellung mit Web-UI](assets/img/advanced-dns-resolvers2.png){ align=center }<figcaption>DNS-Resolver-Einstellung mit Web-UI</figcaption></figure>

    === "Linux"

        Sie müssen die Datei `/etc/bunkerweb/variables.env` ändern:

        ```conf
        ...
        DNS_RESOLVERS=127.0.0.1
        ...
        ```

        Nach dieser Änderung laden Sie den Scheduler neu:

        ```shell
        sudo systemctl reload bunkerweb-scheduler
        ```

=== "All-in-one"

    Wenn Sie den All-in-one-Container verwenden, führen Sie dnsmasq in einem separaten Container aus und konfigurieren Sie BunkerWeb, um ihn zu verwenden:

    ```bash
    # Ein benutzerdefiniertes Netzwerk für die DNS-Kommunikation erstellen
    docker network create bw-dns

    # dnsmasq-Container mit dockurr/dnsmasq und Quad9 DNS ausführen
    # Quad9 bietet sicherheitsorientierte DNS-Auflösung mit Malware-Blockierung
    docker run -d \
        --name dnsmasq \
        --network bw-dns \
        -e DNS1="9.9.9.9" \
        -e DNS2="149.112.112.112" \
        -p 53:53/udp \
        -p 53:53/tcp \
        --cap-add=NET_ADMIN \
        --restart=always \
        dockurr/dnsmasq

    # BunkerWeb All-in-one mit dnsmasq DNS-Resolver ausführen
    docker run -d \
        --name bunkerweb-aio \
        --network bw-dns \
        -v bw-storage:/data \
        -e DNS_RESOLVERS="dnsmasq" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

=== "Docker"

    Fügen Sie einen dnsmasq-Dienst zu Ihrer docker-compose-Datei hinzu und konfigurieren Sie BunkerWeb, um ihn zu verwenden:

    ```yaml
    services:
      dnsmasq:
        image: dockurr/dnsmasq
        container_name: dnsmasq
        environment:
          # Verwendung von Quad9 DNS-Servern für verbesserte Sicherheit und Datenschutz
          # Primär: 9.9.9.9 (Quad9 mit Malware-Blockierung)
          # Sekundär: 149.112.112.112 (Quad9 Backup-Server)
          DNS1: "9.9.9.9"
          DNS2: "149.112.112.112"
        ports:
          - 53:53/udp
          - 53:53/tcp
        cap_add:
          - NET_ADMIN
        restart: always
        networks:
          - bw-dns

      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-services
          - bw-dns

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-dns

    networks:
      # ...vorhandene Netzwerke...
      bw-dns:
        name: bw-dns
    ```

## Benutzerdefinierte Konfigurationen {#custom-configurations}

Um benutzerdefinierte Konfigurationen zu BunkerWeb hinzuzufügen und anzupassen, können Sie die NGINX-Grundlage nutzen. Benutzerdefinierte NGINX-Konfigurationen können in verschiedenen NGINX-Kontexten hinzugefügt werden, einschließlich Konfigurationen für die ModSecurity Web Application Firewall (WAF), die eine Kernkomponente von BunkerWeb ist. Weitere Details zu ModSecurity-Konfigurationen finden Sie [hier](features.md#custom-configurations).

Hier sind die verfügbaren Typen von benutzerdefinierten Konfigurationen:

-   **http**: Konfigurationen auf der HTTP-Ebene von NGINX.
-   **server-http**: Konfigurationen auf der HTTP/Server-Ebene von NGINX.
-   **default-server-http**: Konfigurationen auf der Server-Ebene von NGINX, speziell für den "default server", wenn der angegebene Client-Name mit keinem Servernamen in `SERVER_NAME` übereinstimmt.
-   **modsec-crs**: Konfigurationen, die angewendet werden, bevor das OWASP Core Rule Set geladen wird.
-   **modsec**: Konfigurationen, die angewendet werden, nachdem das OWASP Core Rule Set geladen wurde, oder die verwendet werden, wenn das Core Rule Set nicht geladen ist.
-   **crs-plugins-before**: Konfigurationen für die CRS-Plugins, die angewendet werden, bevor die CRS-Plugins geladen werden.
-   **crs-plugins-after**: Konfigurationen für die CRS-Plugins, die angewendet werden, nachdem die CRS-Plugins geladen wurden.
-   **stream**: Konfigurationen auf der Stream-Ebene von NGINX.
-   **server-stream**: Konfigurationen auf der Stream/Server-Ebene von NGINX.

Benutzerdefinierte Konfigurationen können global oder spezifisch für einen bestimmten Server angewendet werden, abhängig vom anwendbaren Kontext und ob der [Multisite-Modus](features.md#multisite-mode) aktiviert ist.

Die Methode zum Anwenden benutzerdefinierter Konfigurationen hängt von der verwendeten Integration ab. Der zugrunde liegende Prozess besteht jedoch darin, Dateien mit der `.conf`-Endung zu bestimmten Ordnern hinzuzufügen. Um eine benutzerdefinierte Konfiguration für einen bestimmten Server anzuwenden, sollte die Datei in einem Unterordner platziert werden, der nach dem primären Servernamen benannt ist.

Einige Integrationen bieten bequemere Möglichkeiten zum Anwenden von Konfigurationen, wie z. B. die Verwendung von [Configs](https://docs.docker.com/engine/swarm/configs/) in Docker Swarm oder [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) in Kubernetes. Diese Optionen bieten einfachere Ansätze zur Verwaltung und Anwendung von Konfigurationen.

=== "Web-UI"

    Navigieren Sie zur Seite **Konfigurationen**, klicken Sie auf **Neue benutzerdefinierte Konfiguration erstellen**, Sie können dann wählen, ob es sich um eine globale oder eine für einen Dienst spezifische Konfiguration handelt, den Konfigurationstyp und den Konfigurationsnamen:

    <figure markdown>![Benutzerdefinierte Konfigurationen mit Web-UI](assets/img/advanced-config.png){ align=center }<figcaption>Benutzerdefinierte Konfigurationen mit Web-UI</figcaption></figure>

    Vergessen Sie nicht, auf die Schaltfläche `💾 Speichern` zu klicken.

=== "Linux"

    Bei Verwendung der [Linux-Integration](integrations.md#linux) müssen benutzerdefinierte Konfigurationen in den Ordner `/etc/bunkerweb/configs` geschrieben werden.

    Hier ist ein Beispiel für `server-http/hello-world.conf`:

    ```nginx
    location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }
    ```

    Da BunkerWeb als unprivilegierter Benutzer (nginx:nginx) läuft, müssen Sie die Berechtigungen bearbeiten:

    ```shell
    chown -R root:nginx /etc/bunkerweb/configs && \
    chmod -R 770 /etc/bunkerweb/configs
    ```

    Überprüfen wir nun den Status des Schedulers:

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    Wenn er bereits läuft, können wir ihn neu laden:

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Andernfalls müssen wir ihn starten:

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "All-in-one"

    Bei Verwendung des [All-in-one-Images](integrations.md#all-in-one-aio-image) haben Sie zwei Möglichkeiten, benutzerdefinierte Konfigurationen hinzuzufügen:

    -   Verwendung spezifischer Einstellungen `*_CUSTOM_CONF_*` als Umgebungsvariablen beim Ausführen des Containers (empfohlen).
    -   Schreiben von `.conf`-Dateien in das Verzeichnis `/data/configs/` innerhalb des an `/data` gemounteten Volumes.

    **Verwendung von Einstellungen (Umgebungsvariablen)**

    Die zu verwendenden Einstellungen müssen dem Muster `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` folgen:

    -   `<SITE>`: Optionaler primärer Servername, wenn der Multisite-Modus aktiviert ist und die Konfiguration auf einen bestimmten Dienst angewendet werden soll.
    -   `<TYPE>`: Der Typ der Konfiguration, akzeptierte Werte sind `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER`, `STREAM` und `SERVER_STREAM`.
    -   `<NAME>`: Der Name der Konfiguration ohne die `.conf`-Endung.

    Hier ist ein Dummy-Beispiel beim Ausführen des All-in-one-Containers:

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -e "CUSTOM_CONF_SERVER_HTTP_hello-world=location /hello { \
            default_type 'text/plain'; \
            content_by_lua_block { \
              ngx.say('world'); \
            } \
          }" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

    Bitte beachten Sie, dass Sie, wenn Ihr Container bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen angewendet werden.

    **Verwendung von Dateien**

    Als Erstes müssen Sie die Ordner erstellen:

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    Sie können nun Ihre Konfigurationen schreiben:

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Da der Scheduler als unprivilegierter Benutzer mit UID und GID 101 läuft, müssen Sie die Berechtigungen bearbeiten:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Beim Starten des Scheduler-Containers müssen Sie den Ordner an `/data` mounten:

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v ./bw-data:/data \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

=== "Docker"

    Bei Verwendung der [Docker-Integration](integrations.md#docker) haben Sie zwei Möglichkeiten, benutzerdefinierte Konfigurationen hinzuzufügen:

    -   Verwendung spezifischer Einstellungen `*_CUSTOM_CONF_*` als Umgebungsvariablen (empfohlen)
    -   Schreiben von `.conf`-Dateien in das an `/data` des Schedulers gemountete Volume

    **Verwendung von Einstellungen**

    Die zu verwendenden Einstellungen müssen dem Muster `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` folgen:

    -   `<SITE>`: Optionaler primärer Servername, wenn der Multisite-Modus aktiviert ist und die Konfiguration auf einen bestimmten Dienst angewendet werden soll
    -   `<TYPE>`: Der Typ der Konfiguration, akzeptierte Werte sind `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER`, `STREAM` und `SERVER_STREAM`
    -   `<NAME>`: Der Name der Konfiguration ohne die `.conf`-Endung

    Hier ist ein Dummy-Beispiel mit einer `docker-compose`-Datei:

    ```yaml
    ...
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
      environment:
        - |
          CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
              ngx.say('world')
            }
          }
      ...
    ```

    **Verwendung von Dateien**

    Als Erstes müssen Sie die Ordner erstellen:

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    Sie können nun Ihre Konfigurationen schreiben:

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Da der Scheduler als unprivilegierter Benutzer mit UID und GID 101 läuft, müssen Sie die Berechtigungen bearbeiten:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Beim Starten des Scheduler-Containers müssen Sie den Ordner an `/data` mounten:

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Docker autoconf"

    Bei Verwendung der [Docker-Autoconf-Integration](integrations.md#docker-autoconf) haben Sie zwei Möglichkeiten, benutzerdefinierte Konfigurationen hinzuzufügen:

    -   Verwendung spezifischer Einstellungen `*_CUSTOM_CONF_*` als Labels (am einfachsten)
    -   Schreiben von `.conf`-Dateien in das an `/data` des Schedulers gemountete Volume

    **Verwendung von Labels**

    !!! warning "Einschränkungen bei der Verwendung von Labels"
        Bei der Verwendung von Labels mit der Docker-Autoconf-Integration können Sie nur benutzerdefinierte Konfigurationen für den entsprechenden Webdienst anwenden. Das Anwenden von **http**-, **default-server-http**-, **stream**- oder globalen Konfigurationen (wie **server-http** oder **server-stream** für alle Dienste) ist nicht möglich: Dafür müssen Sie Dateien mounten.

    Die zu verwendenden Labels müssen dem Muster `bunkerweb.CUSTOM_CONF_<TYPE>_<NAME>` folgen:

    -   `<TYPE>`: Der Typ der Konfiguration, akzeptierte Werte sind `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER` und `SERVER_STREAM`
    -   `<NAME>`: Der Name der Konfiguration ohne die `.conf`-Endung

    Hier ist ein Dummy-Beispiel mit einer `docker-compose`-Datei:

    ```yaml
    myapp:
      image: bunkerity/bunkerweb-hello:v1.0
      labels:
        - |
          bunkerweb.CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
                ngx.say('world')
            }
          }
      ...
    ```

    **Verwendung von Dateien**

    Als Erstes müssen Sie die Ordner erstellen:

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    Sie können nun Ihre Konfigurationen schreiben:

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Da der Scheduler als unprivilegierter Benutzer mit UID und GID 101 läuft, müssen Sie die Berechtigungen bearbeiten:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Beim Starten des Scheduler-Containers müssen Sie den Ordner an `/data` mounten:

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Kubernetes"

    Bei Verwendung der [Kubernetes-Integration](integrations.md#kubernetes)
    werden benutzerdefinierte Konfigurationen über [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) verwaltet.

    Sie müssen die ConfigMap nicht in einen Pod einbinden (z. B. als Umgebungsvariable oder Volume).
    Der Autoconf-Pod lauscht auf ConfigMap-Ereignisse und aktualisiert die Konfiguration, sobald Änderungen erkannt werden.

    Annotieren Sie jede ConfigMap, die vom Ingress-Controller verwaltet werden soll:

    - `bunkerweb.io/CONFIG_TYPE`: Pflichtfeld. Wählen Sie einen unterstützten Typ (`http`, `server-http`, `default-server-http`, `modsec`,
      `modsec-crs`, `crs-plugins-before`, `crs-plugins-after`, `stream`, `server-stream` oder `settings`).
    - `bunkerweb.io/CONFIG_SITE`: Optional. Setzen Sie den primären Servernamen (wie in Ihrem `Ingress` deklariert),
      um die Konfiguration auf diesen Dienst zu beschränken; lassen Sie den Wert weg, um sie global anzuwenden.

    Hier ist das Beispiel:

    ```yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: cfg-bunkerweb-all-server-http
      annotations:
        bunkerweb.io/CONFIG_TYPE: "server-http"
    data:
      myconf: |
      location /hello {
        default_type 'text/plain';
        content_by_lua_block {
          ngx.say('world')
        }
      }
    ```

    !!! info "So funktioniert die Synchronisierung"
        - Der Ingress-Controller überwacht fortlaufend alle annotierten ConfigMaps.
        - Wenn die Umgebungsvariable `NAMESPACES` gesetzt ist, werden nur ConfigMaps aus diesen Namespaces berücksichtigt.
        - Beim Erstellen oder Aktualisieren einer verwalteten ConfigMap wird die Konfiguration sofort neu geladen.
        - Das Löschen der ConfigMap – oder das Entfernen der Annotation `bunkerweb.io/CONFIG_TYPE` – entfernt die zugehörige benutzerdefinierte Konfiguration.
        - Wenn `bunkerweb.io/CONFIG_SITE` gesetzt ist, muss der referenzierte Dienst bereits existieren;
          andernfalls wird die ConfigMap ignoriert, bis der Dienst verfügbar ist.

    !!! tip "Benutzerdefinierte zusätzliche Konfiguration"
        Seit Version `1.6.0` können Sie Einstellungen hinzufügen oder überschreiben, indem Sie eine ConfigMap mit `bunkerweb.io/CONFIG_TYPE=settings` annotieren.
        Der Autoconf-Ingress-Controller liest jeden Eintrag unter `data` und behandelt ihn wie eine Umgebungsvariable:

        - Ohne `bunkerweb.io/CONFIG_SITE` werden alle Schlüssel global angewendet.
        - Wenn `bunkerweb.io/CONFIG_SITE` gesetzt ist, fügt der Controller nicht bereits spezifischen Schlüsseln automatisch das Präfix `<Servername>_` hinzu (alle `/` werden dabei durch `_` ersetzt). Fügen Sie das Präfix selbst hinzu, wenn Sie globale und dienstspezifische Schlüssel in derselben ConfigMap mischen möchten.
        - Ungültige Namen oder Werte werden übersprungen und als Warnung in den Autoconf-Protokollen ausgegeben.

        Hier ist ein Beispiel:

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: cfg-bunkerweb-extra-settings
          annotations:
            bunkerweb.io/CONFIG_TYPE: "settings"
        data:
          USE_ANTIBOT: "captcha" # Multisite-Einstellung, die auf alle Dienste angewendet wird, die sie nicht überschreiben
          USE_REDIS: "yes" # Globale Einstellung, die global angewendet wird
          ...
        ```

=== "Swarm"

    !!! warning "Veraltet"
        Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](integrations.md#kubernetes).

        **Weitere Informationen finden Sie in der [Swarm-Integrationsdokumentation](integrations.md#swarm).**

    Bei Verwendung der [Swarm-Integration](integrations.md#swarm) werden benutzerdefinierte Konfigurationen über [Docker Configs](https://docs.docker.com/engine/swarm/configs/) verwaltet.

    Um es einfach zu halten, müssen Sie die Config nicht einmal an einen Dienst anhängen: Der Autoconf-Dienst lauscht auf Config-Ereignisse und aktualisiert die benutzerdefinierten Konfigurationen bei Bedarf.

    Beim Erstellen einer Config müssen Sie spezielle Labels hinzufügen:

    *   **bunkerweb.CONFIG_TYPE**: Muss auf einen gültigen Typ für benutzerdefinierte Konfigurationen gesetzt werden (http, server-http, default-server-http, modsec, modsec-crs, crs-plugins-before, crs-plugins-after, stream, server-stream oder settings)
    *   **bunkerweb.CONFIG_SITE**: Auf einen Servernamen setzen, um die Konfiguration auf diesen spezifischen Server anzuwenden (optional, wird global angewendet, wenn nicht gesetzt)

    Hier ist das Beispiel:

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" | docker config create -l bunkerweb.CONFIG_TYPE=server-http my-config -
    ```

    Es gibt keinen Aktualisierungsmechanismus: Die Alternative besteht darin, eine vorhandene Konfiguration mit `docker config rm` zu entfernen und sie dann neu zu erstellen.

## Viele Dienste in der Produktion betreiben {#running-many-services-in-production}

### Globales CRS

!!! warning "CRS-Plugins"
    Wenn das CRS global geladen wird, werden **CRS-Plugins nicht unterstützt**. Wenn Sie sie verwenden müssen, müssen Sie das CRS pro Dienst laden.

Wenn Sie BunkerWeb in der Produktion mit einer großen Anzahl von Diensten verwenden und die **ModSecurity-Funktion global** mit CRS-Regeln aktivieren, kann die zum Laden der BunkerWeb-Konfigurationen erforderliche Zeit zu lang werden, was möglicherweise zu einem Timeout führt.

Die Problemumgehung besteht darin, die CRS-Regeln global anstatt pro Dienst zu laden. Dieses Verhalten ist aus Gründen der Abwärtskompatibilität standardmäßig nicht aktiviert und weil es einen Nachteil hat: Wenn Sie das globale Laden von CRS-Regeln aktivieren, **ist es nicht mehr möglich, modsec-crs-Regeln** (die vor den CRS-Regeln ausgeführt werden) pro Dienst zu definieren. Diese Einschränkung kann jedoch umgangen werden, indem globale `modsec-crs`-Ausschlussregeln wie diese geschrieben werden:

```
SecRule REQUEST_FILENAME "@rx ^/somewhere$" "nolog,phase:4,allow,id:1010,chain"
SecRule REQUEST_HEADERS:Host "@rx ^app1\.example\.com$" "nolog"
```

Sie können das globale Laden von CRS-Regeln aktivieren, indem Sie `USE_MODSECURITY_GLOBAL_CRS` auf `yes` setzen.

### `max_allowed_packet` für MariaDB/MySQL anpassen

Es scheint, dass der Standardwert für den Parameter `max_allowed_packet` in MariaDB- und MySQL-Datenbankservern nicht ausreicht, wenn BunkerWeb mit einer großen Anzahl von Diensten verwendet wird.

Wenn Sie Fehler wie diesen feststellen, insbesondere auf dem Scheduler:

```
[Warning] Aborted connection 5 to db: 'db' user: 'bunkerweb' host: '172.20.0.4' (Got a packet bigger than 'max_allowed_packet' bytes)
```

Sie müssen den `max_allowed_packet` auf Ihrem Datenbankserver erhöhen.

## Persistenz von Sperren und Berichten {#persistence-of-bans-and-reports}

Standardmäßig speichert BunkerWeb Sperren und Berichte in einem lokalen Lua-Datenspeicher. Obwohl dies einfach und effizient ist, bedeutet diese Einrichtung, dass Daten verloren gehen, wenn die Instanz neu gestartet wird. Um sicherzustellen, dass Sperren und Berichte über Neustarts hinweg bestehen bleiben, können Sie BunkerWeb so konfigurieren, dass ein entfernter [Redis](https://redis.io/)- oder [Valkey](https://valkey.io/)-Server verwendet wird.

**Warum Redis/Valkey verwenden?**

Redis und Valkey sind leistungsstarke In-Memory-Datenspeicher, die häufig als Datenbanken, Caches und Message Broker verwendet werden. Sie sind hoch skalierbar und unterstützen eine Vielzahl von Datenstrukturen, darunter:

-   **Strings**: Grundlegende Schlüssel-Wert-Paare.
-   **Hashes**: Feld-Wert-Paare innerhalb eines einzelnen Schlüssels.
-   **Listen**: Geordnete Sammlungen von Zeichenketten.
-   **Mengen**: Ungeordnete Sammlungen von eindeutigen Zeichenketten.
-   **Sortierte Mengen**: Geordnete Sammlungen mit Bewertungen.

Durch die Nutzung von Redis oder Valkey kann BunkerWeb Sperren, Berichte und Cache-Daten dauerhaft speichern und so Haltbarkeit und Skalierbarkeit gewährleisten.

**Aktivieren der Redis/Valkey-Unterstützung**

Um die Unterstützung für Redis oder Valkey zu aktivieren, konfigurieren Sie die folgenden Einstellungen in Ihrer BunkerWeb-Konfigurationsdatei:

```conf
# Redis/Valkey-Unterstützung aktivieren
USE_REDIS=yes

# Redis/Valkey-Server-Hostname oder IP-Adresse
REDIS_HOST=<hostname>

# Redis/Valkey-Server-Portnummer (Standard: 6379)
REDIS_PORT=6379

# Redis/Valkey-Datenbanknummer (Standard: 0)
REDIS_DATABASE=0
```

-   **`USE_REDIS`**: Auf `yes` setzen, um die Redis/Valkey-Integration zu aktivieren.
-   **`REDIS_HOST`**: Geben Sie den Hostnamen oder die IP-Adresse des Redis/Valkey-Servers an.
-   **`REDIS_PORT`**: Geben Sie die Portnummer für den Redis/Valkey-Server an. Standard ist `6379`.
-   **`REDIS_DATABASE`**: Geben Sie die zu verwendende Redis/Valkey-Datenbanknummer an. Standard ist `0`.

Wenn Sie erweiterte Einstellungen wie Authentifizierung, SSL/TLS-Unterstützung oder den Sentinel-Modus benötigen, finden Sie detaillierte Anleitungen in der [Dokumentation zu den Redis-Plugin-Einstellungen](features.md#redis).

## UDP/TCP-Anwendungen schützen

!!! example "Experimentelles Feature"

      Dieses Feature ist nicht produktionsreif. Fühlen Sie sich frei, es zu testen und uns Fehler über [Issues](https://github.com/bunkerity/bunkerweb/issues) im GitHub-Repository zu melden.

BunkerWeb bietet die Möglichkeit, als **generischer UDP/TCP-Reverse-Proxy** zu fungieren, sodass Sie alle netzwerkbasierten Anwendungen schützen können, die mindestens auf Schicht 4 des OSI-Modells arbeiten. Anstelle des "klassischen" HTTP-Moduls verwendet BunkerWeb das [Stream-Modul](https://nginx.org/en/docs/stream/ngx_stream_core_module.html) von NGINX.

Es ist wichtig zu beachten, dass **nicht alle Einstellungen und Sicherheitsfunktionen bei Verwendung des Stream-Moduls verfügbar sind**. Weitere Informationen hierzu finden Sie in den [Features](features.md)-Abschnitten der Dokumentation.

Die Konfiguration eines einfachen Reverse-Proxys ist der HTTP-Einrichtung sehr ähnlich, da dieselben Einstellungen verwendet werden: `USE_REVERSE_PROXY=yes` und `REVERSE_PROXY_HOST=myapp:9000`. Selbst wenn BunkerWeb hinter einem Load Balancer positioniert ist, bleiben die Einstellungen gleich (wobei das **PROXY-Protokoll** aus offensichtlichen Gründen die unterstützte Option ist).

Darüber hinaus werden die folgenden spezifischen Einstellungen verwendet:

-   `SERVER_TYPE=stream`: aktiviert den `stream`-Modus (generisches UDP/TCP) anstelle des `http`-Modus (Standard)
-   `LISTEN_STREAM_PORT=4242`: der lauschende "einfache" (ohne SSL/TLS) Port, auf dem BunkerWeb lauschen wird
-   `LISTEN_STREAM_PORT_SSL=4343`: der lauschende "ssl/tls"-Port, auf dem BunkerWeb lauschen wird
-   `USE_UDP=no`: lauscht auf UDP-Pakete und leitet sie anstelle von TCP weiter

Eine vollständige Liste der Einstellungen für den `stream`-Modus finden Sie im Abschnitt [Features](features.md) der Dokumentation.

!!! tip "mehrere lauschende Ports"

    Seit Version `1.6.0` unterstützt BunkerWeb mehrere lauschende Ports für den `stream`-Modus. Sie können sie mit den Einstellungen `LISTEN_STREAM_PORT` und `LISTEN_STREAM_PORT_SSL` angeben.

    Hier ist ein Beispiel:

    ```conf
    ...
    LISTEN_STREAM_PORT=4242
    LISTEN_STREAM_PORT_SSL=4343
    LISTEN_STREAM_PORT_1=4244
    LISTEN_STREAM_PORT_SSL_1=4344
    ...
    ```

=== "All-in-one"

    Sie müssen die Einstellungen zu den Umgebungsvariablen hinzufügen, wenn Sie den All-in-one-Container ausführen. Sie müssen auch die Stream-Ports freigeben.

    Dieses Beispiel konfiguriert BunkerWeb, um zwei Stream-basierte Anwendungen, `app1.example.com` und `app2.example.com`, zu proxieren.

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -e SERVICE_UI="no" \
        -e SERVER_NAME="app1.example.com app2.example.com" \
        -e MULTISITE="yes" \
        -e USE_REVERSE_PROXY="yes" \
        -e SERVER_TYPE="stream" \
        -e app1.example.com_REVERSE_PROXY_HOST="myapp1:9000" \
        -e app1.example.com_LISTEN_STREAM_PORT="10000" \
        -e app2.example.com_REVERSE_PROXY_HOST="myapp2:9000" \
        -e app2.example.com_LISTEN_STREAM_PORT="20000" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        -p 10000:10000/tcp \
        -p 20000:20000/tcp \
        bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

    Bitte beachten Sie, dass Sie, wenn Ihr Container bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen angewendet werden.

    Ihre Anwendungen (`myapp1`, `myapp2`) sollten in separaten Containern laufen (oder anderweitig erreichbar sein) und ihre Hostnamen/IPs (z. B. `myapp1`, `myapp2`, die in `_REVERSE_PROXY_HOST` verwendet werden) müssen vom `bunkerweb-aio`-Container aus auflösbar und erreichbar sein. Dies geschieht typischerweise, indem sie mit einem gemeinsamen Docker-Netzwerk verbunden werden.

    !!! note "UI-Dienst deaktivieren"
        Es wird empfohlen, den UI-Dienst zu deaktivieren (z. B. durch Setzen von `SERVICE_UI=no` als Umgebungsvariable), da die Web-UI nicht mit `SERVER_TYPE=stream` kompatibel ist.

=== "Docker"

    Bei Verwendung der Docker-Integration ist der einfachste Weg, bestehende Netzwerkanwendungen zu schützen, die Dienste zum `bw-services`-Netzwerk hinzuzufügen:

    ```yaml
    x-bw-api-env: &bw-api-env
      # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für alle Dienste zu vermeiden
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
      # Optionaler API-Token für authentifizierte API-Aufrufe
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080" # Behalten, wenn Sie die Let's Encrypt-Automatisierung mit dem http-Challenge-Typ verwenden möchten
          - "10000:10000" # app1
          - "20000:20000" # app2
        labels:
          - "bunkerweb.INSTANCE=yes"
        environment:
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Diese Einstellung ist obligatorisch, um die BunkerWeb-Instanz anzugeben
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          USE_REVERSE_PROXY: "yes" # Wird auf alle Dienste angewendet
          SERVER_TYPE: "stream" # Wird auf alle Dienste angewendet
          app1.example.com_REVERSE_PROXY_HOST: "myapp1:9000"
          app1.example.com_LISTEN_STREAM_PORT: "10000"
          app2.example.com_REVERSE_PROXY_HOST: "myapp2:9000"
          app2.example.com_LISTEN_STREAM_PORT: "20000"
        volumes:
          - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
        restart: "unless-stopped"
        networks:
          - bw-universe

      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services

    volumes:
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
    ```

=== "Docker autoconf"

    Bevor Sie den [Docker-Autoconf-Integrations](integrations.md#docker-autoconf)-Stack auf Ihrer Maschine ausführen, müssen Sie die Ports bearbeiten:

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080" # Behalten, wenn Sie die Let's Encrypt-Automatisierung mit dem http-Challenge-Typ verwenden möchten
          - "10000:10000" # app1
          - "20000:20000" # app2
    ...
    ```

    Sobald der Stack läuft, können Sie Ihre bestehenden Anwendungen mit dem `bw-services`-Netzwerk verbinden und BunkerWeb mit Labels konfigurieren:

    ```yaml
    services:
      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        labels:
          - "bunkerweb.SERVER_NAME=app1.example.com"
          - "bunkerweb.SERVER_TYPE=stream"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        labels:
          - "bunkerweb.SERVER_NAME=app2.example.com"
          - "bunkerweb.SERVER_TYPE=stream"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    !!! example "Experimentelles Feature"

        Im Moment unterstützen [Ingresses](https://kubernetes.io/docs/concepts/services-networking/ingress/) den `stream`-Modus nicht. **Was wir hier tun, ist ein Workaround, um es zum Laufen zu bringen.**

        Fühlen Sie sich frei, es zu testen und uns Fehler über [Issues](https://github.com/bunkerity/bunkerweb/issues) im GitHub-Repository zu melden.

    Bevor Sie den [Kubernetes-Integrations](integrations.md#kubernetes)-Stack auf Ihrer Maschine ausführen, müssen Sie die Ports an Ihrem Load Balancer öffnen:

    ```yaml
    apiVersion: v1
    kind: Service
    metadata:
      name: lb
    spec:
      type: LoadBalancer
      ports:
        - name: http # Behalten, wenn Sie die Let's Encrypt-Automatisierung mit dem http-Challenge-Typ verwenden möchten
          port: 80
          targetPort: 8080
        - name: app1
          port: 10000
          targetPort: 10000
        - name: app2
          port: 20000
          targetPort: 20000
      selector:
        app: bunkerweb
    ```

    Sobald der Stack läuft, können Sie Ihre Ingress-Ressourcen erstellen:

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      namespace: services
      annotations:
        bunkerweb.io/SERVER_TYPE: "stream" # Wird auf alle Dienste angewendet
        bunkerweb.io/app1.example.com_LISTEN_STREAM_PORT: "10000"
        bunkerweb.io/app2.example.com_LISTEN_STREAM_PORT: "20000"
    spec:
      rules:
        - host: app1.example.com
          http:
            paths:
              - path: / # Wird im Stream-Modus nicht verwendet, ist aber erforderlich
                pathType: Prefix
                backend:
                  service:
                    name: svc-app1
                    port:
                      number: 9000
        - host: app2.example.com
          http:
            paths:
              - path: / # Wird im Stream-Modus nicht verwendet, ist aber erforderlich
                pathType: Prefix
                backend:
                  service:
                    name: svc-app2
                    port:
                      number: 9000
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app1
      namespace: services
      labels:
        app: app1
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: app1
      template:
        metadata:
          labels:
            app: app1
        spec:
          containers:
            - name: app1
              image: istio/tcp-echo-server:1.3
              args: ["9000", "app1"]
              ports:
                - containerPort: 9000
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app1
      namespace: services
    spec:
      selector:
        app: app1
      ports:
        - protocol: TCP
          port: 9000
          targetPort: 9000
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app2
      namespace: services
      labels:
        app: app2
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: app2
      template:
        metadata:
          labels:
            app: app2
        spec:
          containers:
            - name: app2
              image: istio/tcp-echo-server:1.3
              args: ["9000", "app2"]
              ports:
                - containerPort: 9000
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app2
      namespace: services
    spec:
      selector:
        app: app2
      ports:
        - protocol: TCP
          port: 9000
          targetPort: 9000
    ```

=== "Linux"

    Sie müssen die Einstellungen zur Datei `/etc/bunkerweb/variables.env` hinzufügen:

    ```conf
    ...
    SERVER_NAME=app1.example.com app2.example.com
    MULTISITE=yes
    USE_REVERSE_PROXY=yes
    SERVER_TYPE=stream
    app1.example.com_REVERSE_PROXY_HOST=myapp1.domain.or.ip:9000
    app1.example.com_LISTEN_STREAM_PORT=10000
    app2.example.com_REVERSE_PROXY_HOST=myapp2.domain.or.ip:9000
    app2.example.com_LISTEN_STREAM_PORT=20000
    ...
    ```

    Überprüfen wir nun den Status des Schedulers:

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    Wenn er bereits läuft, können wir ihn neu laden:

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Andernfalls müssen wir ihn starten:

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "Veraltet"
        Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](integrations.md#kubernetes).

        **Weitere Informationen finden Sie in der [Swarm-Integrationsdokumentation](integrations.md#swarm).**

    Bevor Sie den [Swarm-Integrations](integrations.md#swarm)-Stack auf Ihrer Maschine ausführen, müssen Sie die Ports bearbeiten:

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          # Behalten, wenn Sie die Let's Encrypt-Automatisierung mit dem http-Challenge-Typ verwenden möchten
          - published: 80
            target: 8080
            mode: host
            protocol: tcp
          # app1
          - published: 10000
            target: 10000
            mode: host
            protocol: tcp
          # app2
          - published: 20000
            target: 20000
            mode: host
            protocol: tcp
    ...
    ```

    Sobald der Stack läuft, können Sie Ihre bestehenden Anwendungen mit dem `bw-services`-Netzwerk verbinden und BunkerWeb mit Labels konfigurieren:

    ```yaml
    services:

      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.SERVER_TYPE=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.SERVER_TYPE=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

## PHP

!!! example "Experimentelles Feature"
	  Im Moment ist die PHP-Unterstützung mit BunkerWeb noch in der Beta-Phase und wir empfehlen Ihnen, wenn möglich eine Reverse-Proxy-Architektur zu verwenden. Übrigens wird PHP für einige Integrationen wie Kubernetes überhaupt nicht unterstützt.

BunkerWeb unterstützt PHP über externe oder entfernte [PHP-FPM](https://www.php.net/manual/en/install.fpm.php)-Instanzen. Wir gehen davon aus, dass Sie bereits mit der Verwaltung solcher Dienste vertraut sind.

 Die folgenden Einstellungen können verwendet werden:

- `REMOTE_PHP` : Hostname der entfernten PHP-FPM-Instanz.
- `REMOTE_PHP_PATH` : Stammordner mit Dateien in der entfernten PHP-FPM-Instanz.
- `REMOTE_PHP_PORT` : Port der entfernten PHP-FPM-Instanz (*Standard ist 9000*).
- `LOCAL_PHP` : Pfad zur lokalen Socket-Datei der PHP-FPM-Instanz.
- `LOCAL_PHP_PATH` : Stammordner mit Dateien in der lokalen PHP-FPM-Instanz.

=== "All-in-one"

    Bei Verwendung des [All-in-one-Images](integrations.md#all-in-one-aio-image) müssen Sie zur Unterstützung von PHP-Anwendungen Folgendes tun:

    -   Mounten Sie Ihre PHP-Dateien in den Ordner `/var/www/html` von BunkerWeb.
    -   Richten Sie einen PHP-FPM-Container für Ihre Anwendung ein und mounten Sie den Ordner mit den PHP-Dateien.
    -   Verwenden Sie die spezifischen Einstellungen `REMOTE_PHP` und `REMOTE_PHP_PATH` als Umgebungsvariablen beim Ausführen von BunkerWeb.

    Wenn Sie den [Multisite-Modus](features.md#multisite-mode) aktivieren, müssen Sie separate Verzeichnisse für jede Ihrer Anwendungen erstellen. Jedes Unterverzeichnis sollte nach dem ersten Wert von `SERVER_NAME` benannt werden. Hier ist ein Dummy-Beispiel:

    ```
    www
    ├── app1.example.com
    │   └── index.php
    └── app2.example.com
        └── index.php

    2 Verzeichnisse, 2 Dateien
    ```

    Wir gehen davon aus, dass sich Ihre PHP-Apps in einem Ordner namens `www` befinden. Bitte beachten Sie, dass Sie die Berechtigungen korrigieren müssen, damit BunkerWeb (UID/GID 101) zumindest Dateien lesen und Ordner auflisten kann und PHP-FPM (UID/GID 33, wenn Sie das `php:fpm`-Image verwenden) der Eigentümer der Dateien und Ordner ist:

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    Sie können nun BunkerWeb ausführen, es für Ihre PHP-Anwendung konfigurieren und auch die PHP-Apps ausführen. Sie müssen ein benutzerdefiniertes Docker-Netzwerk erstellen, damit BunkerWeb mit Ihren PHP-FPM-Containern kommunizieren kann.

    ```bash
    # Ein benutzerdefiniertes Netzwerk erstellen
    docker network create php-network

    # PHP-FPM-Container ausführen
    docker run -d --name myapp1-php --network php-network -v ./www/app1.example.com:/app php:fpm
    docker run -d --name myapp2-php --network php-network -v ./www/app2.example.com:/app php:fpm

    # BunkerWeb All-in-one ausführen
    docker run -d \
        --name bunkerweb-aio \
        --network php-network \
        -v ./www:/var/www/html \
        -v bw-storage:/data \
        -e SERVER_NAME="app1.example.com app2.example.com" \
        -e MULTISITE="yes" \
        -e REMOTE_PHP_PATH="/app" \
        -e app1.example.com_REMOTE_PHP="myapp1-php" \
        -e app2.example.com_REMOTE_PHP="myapp2-php" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

    Bitte beachten Sie, dass Sie, wenn Ihr Container bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen angewendet werden.

=== "Docker"

    Bei Verwendung der [Docker-Integration](integrations.md#docker) müssen Sie zur Unterstützung von PHP-Anwendungen Folgendes tun:

    -   Mounten Sie Ihre PHP-Dateien in den Ordner `/var/www/html` von BunkerWeb
    -   Richten Sie einen PHP-FPM-Container für Ihre Anwendung ein und mounten Sie den Ordner mit den PHP-Dateien
    -   Verwenden Sie die spezifischen Einstellungen `REMOTE_PHP` und `REMOTE_PHP_PATH` als Umgebungsvariablen beim Starten von BunkerWeb

    Wenn Sie den [Multisite-Modus](features.md#multisite-mode) aktivieren, müssen Sie separate Verzeichnisse für jede Ihrer Anwendungen erstellen. Jedes Unterverzeichnis sollte nach dem ersten Wert von `SERVER_NAME` benannt werden. Hier ist ein Dummy-Beispiel:

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 Verzeichnisse, 3 Dateien
    ```

    Wir gehen davon aus, dass sich Ihre PHP-Apps in einem Ordner namens `www` befinden. Bitte beachten Sie, dass Sie die Berechtigungen korrigieren müssen, damit BunkerWeb (UID/GID 101) zumindest Dateien lesen und Ordner auflisten kann und PHP-FPM (UID/GID 33, wenn Sie das `php:fpm`-Image verwenden) der Eigentümer der Dateien und Ordner ist:

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    Sie können nun BunkerWeb ausführen, es für Ihre PHP-Anwendung konfigurieren und auch die PHP-Apps ausführen:

    ```yaml
    x-bw-api-env: &bw-api-env
      # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für alle Dienste zu vermeiden
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *bw-api-env
        volumes:
          - ./www:/var/www/html
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Diese Einstellung ist obligatorisch, um die BunkerWeb-Instanz anzugeben
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          REMOTE_PHP_PATH: "/app" # Wird dank der MULTISITE-Einstellung auf alle Dienste angewendet
          app1.example.com_REMOTE_PHP: "myapp1"
          app2.example.com_REMOTE_PHP: "myapp2"
          app3.example.com_REMOTE_PHP: "myapp3"
        volumes:
          - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
        restart: "unless-stopped"
        networks:
          - bw-universe

      myapp1:
        image: php:fpm
        volumes:
          - ./www/app1.example.com:/app
        networks:
          - bw-services

      myapp2:
        image: php:fpm
        volumes:
          - ./www/app2.example.com:/app
        networks:
          - bw-services

      myapp3:
        image: php:fpm
        volumes:
          - ./www/app3.example.com:/app
        networks:
          - bw-services

    volumes:
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
    ```

=== "Docker autoconf"

    !!! info "Multisite-Modus aktiviert"
        Die [Docker-Autoconf-Integration](integrations.md#docker-autoconf) impliziert die Verwendung des Multisite-Modus: Das Schützen einer PHP-Anwendung ist dasselbe wie das Schützen mehrerer.

    Bei Verwendung der [Docker-Autoconf-Integration](integrations.md#docker-autoconf) müssen Sie zur Unterstützung von PHP-Anwendungen Folgendes tun:

    -   Mounten Sie Ihre PHP-Dateien in den Ordner `/var/www/html` von BunkerWeb
    -   Richten Sie PHP-FPM-Container für Ihre Anwendungen ein und mounten Sie den Ordner mit den PHP-Apps
    -   Verwenden Sie die spezifischen Einstellungen `REMOTE_PHP` und `REMOTE_PHP_PATH` als Labels für Ihren PHP-FPM-Container

    Da die Docker-Autoconf die Verwendung des [Multisite-Modus](features.md#multisite-mode) impliziert, müssen Sie separate Verzeichnisse für jede Ihrer Anwendungen erstellen. Jedes Unterverzeichnis sollte nach dem ersten Wert von `SERVER_NAME` benannt werden. Hier ist ein Dummy-Beispiel:

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 Verzeichnisse, 3 Dateien
    ```

    Sobald die Ordner erstellt sind, kopieren Sie Ihre Dateien und korrigieren Sie die Berechtigungen, damit BunkerWeb (UID/GID 101) zumindest Dateien lesen und Ordner auflisten kann und PHP-FPM (UID/GID 33, wenn Sie das `php:fpm`-Image verwenden) der Eigentümer der Dateien und Ordner ist:

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    Wenn Sie den BunkerWeb-Autoconf-Stack starten, mounten Sie den Ordner `www` in `/var/www/html` für den **Scheduler**-Container:

    ```yaml
    x-bw-api-env: &bw-api-env
      # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für alle Dienste zu vermeiden
      AUTOCONF_MODE: "yes"
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        labels:
          - "bunkerweb.INSTANCE=yes"
        environment:
          <<: *bw-api-env
        volumes:
          - ./www:/var/www/html
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "" # Wir müssen die BunkerWeb-Instanz hier nicht angeben, da sie automatisch vom Autoconf-Dienst erkannt werden
          SERVER_NAME: "" # Der Servername wird über Dienst-Labels gefüllt
          MULTISITE: "yes" # Obligatorische Einstellung für Autoconf
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
        volumes:
          - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.8-rc3
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
      bw-docker:
        name: bw-docker
    ```

    Sie können nun Ihre PHP-FPM-Container erstellen, die richtigen Unterordner mounten und Labels verwenden, um BunkerWeb zu konfigurieren:

    ```yaml
    services:
      myapp1:
          image: php:fpm
          volumes:
            - ./www/app1.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp1
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.REMOTE_PHP=myapp1"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp2:
          image: php:fpm
          volumes:
            - ./www/app2.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp2
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.REMOTE_PHP=myapp2"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp3:
          image: php:fpm
          volumes:
            - ./www/app3.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp3
          labels:
            - "bunkerweb.SERVER_NAME=app3.example.com"
            - "bunkerweb.REMOTE_PHP=myapp3"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    !!! warning "PHP wird für Kubernetes nicht unterstützt"
        Die Kubernetes-Integration ermöglicht die Konfiguration über [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) und der BunkerWeb-Controller unterstützt im Moment nur HTTP-Anwendungen.

=== "Linux"

    Wir gehen davon aus, dass Sie bereits den [Linux-Integrations](integrations.md#linux)-Stack auf Ihrer Maschine laufen haben.

    Standardmäßig sucht BunkerWeb nach Web-Dateien im Ordner `/var/www/html`. Sie können ihn verwenden, um Ihre PHP-Anwendungen zu speichern. Bitte beachten Sie, dass Sie Ihren PHP-FPM-Dienst so konfigurieren müssen, dass er den Benutzer/die Gruppe der laufenden Prozesse und die UNIX-Socket-Datei, die zur Kommunikation mit BunkerWeb verwendet wird, abruft oder festlegt.

    Zunächst müssen Sie sicherstellen, dass Ihre PHP-FPM-Instanz auf die Dateien im Ordner `/var/www/html` zugreifen kann und dass BunkerWeb auf die UNIX-Socket-Datei zugreifen kann, um mit PHP-FPM zu kommunizieren. Wir empfehlen, einen anderen Benutzer wie `www-data` für den PHP-FPM-Dienst festzulegen und der `nginx`-Gruppe Zugriff auf die UNIX-Socket-Datei zu geben. Hier ist die entsprechende PHP-FPM-Konfiguration:

    ```ini
    ...
    [www]
    user = www-data
    group = www-data
    listen = /run/php/php-fpm.sock
    listen.owner = www-data
    listen.group = nginx
    listen.mode = 0660
    ...
    ```

    Vergessen Sie nicht, Ihren PHP-FPM-Dienst neu zu starten:

    ```shell
    systemctl restart php-fpm
    ```

    Wenn Sie den [Multisite-Modus](features.md#multisite-mode) aktivieren, müssen Sie separate Verzeichnisse für jede Ihrer Anwendungen erstellen. Jedes Unterverzeichnis sollte nach dem ersten Wert von `SERVER_NAME` benannt werden. Hier ist ein Dummy-Beispiel:

    ```
    /var/www/html
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 Verzeichnisse, 3 Dateien
    ```

    Bitte beachten Sie, dass Sie die Berechtigungen korrigieren müssen, damit BunkerWeb (Gruppe `nginx`) zumindest Dateien lesen und Ordner auflisten kann und PHP-FPM (Benutzer `www-data`, kann je nach System unterschiedlich sein) der Eigentümer der Dateien und Ordner ist:

    ```shell
    chown -R www-data:nginx /var/www/html && \
    find /var/www/html -type f -exec chmod 0640 {} \; && \
    find /var/www/html -type d -exec chmod 0750 {} \;
    ```

    Sie können nun die Datei `/etc/bunkerweb/variable.env` bearbeiten:

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4
    API_LISTEN_IP=127.0.0.1
    MULTISITE=yes
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app1.example.com_LOCAL_PHP_PATH=/var/www/html/app1.example.com
    app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app2.example.com_LOCAL_PHP_PATH=/var/www/html/app2.example.com
    app3.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app3.example.com_LOCAL_PHP_PATH=/var/www/html/app3.example.com
    ```

    Überprüfen wir nun den Status des Schedulers:

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    Wenn er bereits läuft, können wir ihn neu laden:

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Andernfalls müssen wir ihn starten:

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "Veraltet"
        Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](integrations.md#kubernetes).

        **Weitere Informationen finden Sie in der [Swarm-Integrationsdokumentation](integrations.md#swarm).**

    !!! info "Multisite-Modus aktiviert"
        Die [Swarm-Integration](integrations.md#docker-autoconf) impliziert die Verwendung des Multisite-Modus: Das Schützen einer PHP-Anwendung ist dasselbe wie das Schützen mehrerer.

    !!! info "Geteiltes Volume"
        Die Verwendung von PHP mit der Docker Swarm-Integration erfordert ein geteiltes Volume zwischen allen BunkerWeb- und PHP-FPM-Instanzen, was in dieser Dokumentation nicht behandelt wird.

    Bei Verwendung von [Swarm](integrations.md#swarm) müssen Sie zur Unterstützung von PHP-Anwendungen Folgendes tun:

    -   Mounten Sie Ihre PHP-Dateien in den Ordner `/var/www/html` von BunkerWeb
    -   Richten Sie PHP-FPM-Container für Ihre Anwendungen ein und mounten Sie den Ordner mit den PHP-Apps
    -   Verwenden Sie die spezifischen Einstellungen `REMOTE_PHP` und `REMOTE_PHP_PATH` als Labels für Ihren PHP-FPM-Container

    Da die Swarm-Integration die Verwendung des [Multisite-Modus](features.md#multisite-mode) impliziert, müssen Sie separate Verzeichnisse für jede Ihrer Anwendungen erstellen. Jedes Unterverzeichnis sollte nach dem ersten Wert von `SERVER_NAME` benannt werden. Hier ist ein Dummy-Beispiel:

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 Verzeichnisse, 3 Dateien
    ```

    Als Beispiel gehen wir davon aus, dass Sie einen freigegebenen Ordner auf Ihren Worker-Knoten am Endpunkt `/shared` gemountet haben.

    Sobald die Ordner erstellt sind, kopieren Sie Ihre Dateien und korrigieren Sie die Berechtigungen, damit BunkerWeb (UID/GID 101) zumindest Dateien lesen und Ordner auflisten kann und PHP-FPM (UID/GID 33, wenn Sie das `php:fpm`-Image verwenden) der Eigentümer der Dateien und Ordner ist:

    ```shell
    chown -R 33:101 /shared/www && \
    find /shared/www -type f -exec chmod 0640 {} \; && \
    find /shared/www -type d -exec chmod 0750 {} \;
    ```

    Wenn Sie den BunkerWeb-Stack starten, mounten Sie den Ordner `/shared/www` in `/var/www/html` für den **Scheduler**-Container:

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        volumes:
          - /shared/www:/var/www/html
    ...
    ```

    Sie können nun Ihre PHP-FPM-Dienste erstellen, die richtigen Unterordner mounten und Labels verwenden, um BunkerWeb zu konfigurieren:

    ```yaml
    services:
      myapp1:
          image: php:fpm
          volumes:
            - ./www/app1.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp1
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app1.example.com"
              - "bunkerweb.REMOTE_PHP=myapp1"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp2:
          image: php:fpm
          volumes:
            - ./www/app2.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp2
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app2.example.com"
              - "bunkerweb.REMOTE_PHP=myapp2"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp3:
          image: php:fpm
          volumes:
            - ./www/app3.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp3
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app3.example.com"
              - "bunkerweb.REMOTE_PHP=myapp3"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

## IPv6

!!! example "Experimentelles Feature"

    Dieses Feature ist nicht produktionsreif. Fühlen Sie sich frei, es zu testen und uns Fehler über [Issues](https://github.com/bunkerity/bunkerweb/issues) im GitHub-Repository zu melden.

Standardmäßig lauscht BunkerWeb nur auf IPv4-Adressen und verwendet kein IPv6 für die Netzwerkkommunikation. Wenn Sie die IPv6-Unterstützung aktivieren möchten, müssen Sie `USE_IPV6=yes` setzen. Bitte beachten Sie, dass die IPv6-Konfiguration Ihres Netzwerks und Ihrer Umgebung außerhalb des Geltungsbereichs dieser Dokumentation liegt.

=== "Docker / Autoconf / Swarm"

    Zunächst müssen Sie Ihren Docker-Daemon so konfigurieren, dass er die IPv6-Unterstützung für Container aktiviert und bei Bedarf ip6tables verwendet. Hier ist eine Beispielkonfiguration für Ihre `/etc/docker/daemon.json`-Datei:

    ```json
    {
      "experimental": true,
      "ipv6": true,
      "ip6tables": true,
      "fixed-cidr-v6": "fd00:dead:beef::/48"
    }
    ```

    Sie können nun den Docker-Dienst neu starten, um die Änderungen zu übernehmen:

    ```shell
    systemctl restart docker
    ```

    Sobald Docker für die Unterstützung von IPv6 eingerichtet ist, können Sie die Einstellung `USE_IPV6` hinzufügen und die `bw-services` für IPv6 konfigurieren:

    ```yaml
    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          USE_IPv6: "yes"

    ...

    networks:
      bw-services:
        name: bw-services
        enable_ipv6: true
        ipam:
          config:
            - subnet: fd00:13:37::/48
              gateway: fd00:13:37::1

    ...
    ```

=== "Linux"

    Sie müssen die Einstellungen zur Datei `/etc/bunkerweb/variables.env` hinzufügen:

    ```conf
    ...
    USE_IPV6=yes
    ...
    ```

    Überprüfen wir den Status von BunkerWeb:

    ```shell
    systemctl status bunkerweb
    ```

    Wenn er bereits läuft, können wir ihn neu starten:

    ```shell
    systemctl restart bunkerweb
    ```

    Andernfalls müssen wir ihn starten:

    ```shell
    systemctl start bunkerweb
    ```

## Protokollierungsoptionen

BunkerWeb bietet flexible Protokollierungsoptionen, mit denen Sie Protokolle gleichzeitig an mehrere Ziele (z. B. Dateien, stdout/stderr oder Syslog) senden können. Dies ist besonders nützlich, um die Integration mit externen Log-Collector-Diensten zu ermöglichen und gleichzeitig lokale Protokolle für die Web-UI beizubehalten.

Es gibt zwei Hauptkategorien von Protokollen, die konfiguriert werden können:

1. **Service-Protokolle**: Protokolle, die von BunkerWeb-Komponenten erzeugt werden (Scheduler, UI, Autoconf usw.). Pro Service steuerbar über `LOG_TYPES` (und optional `LOG_FILE_PATH`, `LOG_SYSLOG_ADDRESS`, `LOG_SYSLOG_TAG`).
2. **Zugriffs- & Fehlerprotokolle**: HTTP-Zugriffs- und Fehlerprotokolle, die von NGINX erzeugt werden. Diese betreffen ausschließlich den `bunkerweb`-Dienst (`ACCESS_LOG` / `ERROR_LOG` / `LOG_LEVEL`).

### Service-Protokolle

Service-Protokolle werden durch die Einstellung `LOG_TYPES` gesteuert, die mehrere Werte mit Leerzeichen getrennt akzeptiert (z. B. `LOG_TYPES="stderr syslog"`).

| Wert     | Beschreibung                                                                                            |
| :------- | :------------------------------------------------------------------------------------------------------ |
| `file`   | Schreibt Protokolle in eine Datei. Erforderlich für den Protokollanzeiger der Web-UI.                   |
| `stderr` | Schreibt Protokolle in Standardfehlerausgabe. Standard für containerisierte Umgebungen (`docker logs`). |
| `syslog` | Sendet Protokolle an einen Syslog-Server. Erfordert, dass `LOG_SYSLOG_ADDRESS` gesetzt ist.             |

Wenn Sie `syslog` verwenden, sollten Sie zusätzlich konfigurieren:

- `LOG_SYSLOG_ADDRESS`: Adresse des Syslog-Servers (z. B. `udp://bw-syslog:514` oder `/dev/log`).
- `LOG_SYSLOG_TAG`: Ein eindeutiger Tag für den Dienst (z. B. `bw-scheduler`), damit Einträge unterschieden werden können.
- `LOG_FILE_PATH`: Pfad für die Dateiausgabe, wenn `LOG_TYPES` `file` enthält (z. B. `/var/log/bunkerweb/scheduler.log`).

### Zugriffs- und Fehlerprotokolle

Dies sind Standard-NGINX-Protokolle, die ausschließlich über den `bunkerweb`-Dienst konfiguriert werden. Sie unterstützen mehrere Ziele, indem Sie die Einstellung mit nummerierten Suffixen versehen (z. B. `ACCESS_LOG`, `ACCESS_LOG_1` und die passenden `LOG_FORMAT`, `LOG_FORMAT_1` bzw. `ERROR_LOG`, `ERROR_LOG_1` und die entsprechenden `LOG_LEVEL`, `LOG_LEVEL_1`).

- `ACCESS_LOG`: Ziel für Zugriffsprotokolle (Standard: `/var/log/bunkerweb/access.log`). Akzeptiert Dateipfade, `syslog:server=host[:port][,param=value]`, Shared-Buffer `memory:name:size` oder `off`, um zu deaktivieren. Siehe [NGINX access_log Dokumentation](https://nginx.org/en/docs/http/ngx_http_log_module.html#access_log) für Details.
- `ERROR_LOG`: Ziel für Fehlerprotokolle (Standard: `/var/log/bunkerweb/error.log`). Akzeptiert Dateipfade, `stderr`, `syslog:server=host[:port][,param=value]` oder Shared-Buffer `memory:size`. Siehe [NGINX error_log Dokumentation](https://nginx.org/en/docs/ngx_core_module.html#error_log) für Details.
- `LOG_LEVEL`: Detailstufe der Fehlerprotokolle (Standard: `notice`).

Diese Einstellungen akzeptieren die üblichen NGINX-Werte (Dateipfade, `stderr`, `syslog:server=...`, Shared-Memory-Puffer). Sie unterstützen mehrere Ziele über nummerierte Suffixe (siehe [Multiple-Settings-Konvention](features.md#multiple-settings)). Andere Dienste (Scheduler, UI, Autoconf usw.) nutzen ausschließlich `LOG_TYPES`/`LOG_FILE_PATH`/`LOG_SYSLOG_*`.

**Beispiel mit mehreren Access-/Error-Logs (nur `bunkerweb`, nummerierte Suffixe):**

```conf
ACCESS_LOG=/var/log/bunkerweb/access.log
ACCESS_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
LOG_FORMAT=$host $remote_addr - $request_id $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
LOG_FORMAT_1=$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent
ERROR_LOG=/var/log/bunkerweb/error.log
ERROR_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
LOG_LEVEL=notice
LOG_LEVEL_1=error
```

### Integrations-Defaults & Beispiele

=== "Linux"

    **Standardverhalten**: `LOG_TYPES="file"`. Protokolle werden unter `/var/log/bunkerweb/*.log` geschrieben.

    **Beispiel**: Lokale Dateien behalten (für die Web-UI) und zusätzlich an den System-Syslog spiegeln.

    ```conf
      # Service-Protokolle (in /etc/bunkerweb/variables.env oder in spezifischen Dienst-Umgebungsdateien setzen)
      LOG_TYPES="file syslog"
      LOG_SYSLOG_ADDRESS=/dev/log
      SCHEDULER_LOG_FILE_PATH=/var/log/bunkerweb/scheduler.log
      UI_LOG_FILE_PATH=/var/log/bunkerweb/ui.log
      # ...
      # LOG_SYSLOG_TAG wird automatisch pro Dienst gesetzt (bei Bedarf dienstspezifisch überschreiben)

      # NGINX-Protokolle (nur bunkerweb-Dienst; in /etc/bunkerweb/variables.env setzen)
      ACCESS_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb_access
      ERROR_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
    ```

=== "Docker / Autoconf / Swarm"

    **Standardverhalten**: `LOG_TYPES="stderr"`. Protokolle sind über `docker logs` sichtbar.

    **Beispiel (Adaptation aus dem Quickstart-Guide)**: Behalten Sie `docker logs` (stderr) BEI und senden Sie zusätzlich an einen zentralen Syslog-Container (benötigt für Web UI und CrowdSec).

    ```yaml
    x-bw-env:
      &bw-env # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für beide Dienste zu vermeiden
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Stellen Sie sicher, dass Sie den richtigen IP-Bereich setzen, damit der Scheduler die Konfiguration an die Instanz senden kann
      # Optional: einen API-Token setzen und ihn in beiden Containern spiegeln
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank zu setzen
      # Service-Protokolle
      LOG_TYPES: "stderr syslog"
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"
      # LOG_SYSLOG_TAG wird automatisch pro Dienst gesetzt (bei Bedarf dienstspezifisch überschreiben)
      # NGINX-Protokolle: An Syslog senden (nur bunkerweb)
      ACCESS_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb_access"
      ERROR_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb"

    services:
      bunkerweb:
        # Dies ist der Name, der zur Identifikation der Instanz im Scheduler verwendet wird
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Für QUIC / HTTP3-Unterstützung
        environment:
          <<: *bw-env # Wir verwenden den Anker, um dieselben Einstellungen für alle Dienste zu vermeiden
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Stellen Sie sicher, dass Sie den richtigen Instanznamen setzen
          SERVER_NAME: ""
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # Bei Bedarf anpassen
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.8-rc3
        environment:
          <<: *bw-env
        volumes:
          - bw-logs:/var/log/bunkerweb # Wird verwendet, um die Syslog-Protokolle in der Web-UI zu lesen
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Wir setzen die max_allowed_packet-Größe, um Probleme mit großen Abfragen zu vermeiden
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Denken Sie daran, ein stärkeres Passwort für die Datenbank zu setzen
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis-Dienst zur Persistenz von Reports/Sperren/Statistiken
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

      bw-syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE # Bind an niedrige Ports
          - NET_BROADCAST # Sende Broadcasts
          - NET_RAW # Verwenden von Raw-Sockets
          - DAC_READ_SEARCH # Dateien bypassen, um lesen zu können
          - DAC_OVERRIDE # Dateirechte überschreiben
          - CHOWN # Eigentümer ändern
          - SYSLOG # Schreiben in Systemlogs
        volumes:
          - bw-logs:/var/log/bunkerweb # Laufwerk, das zur Speicherung der Protokolle genutzt wird
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # Syslog-ng-Konfigurationsdatei
        restart: "unless-stopped"
        networks:
          - bw-universe

    volumes:
      bw-data:
      bw-storage:
      redis-data:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
      ipam:
        driver: default
        config:
          - subnet: 10.20.30.0/24 # Stellen Sie sicher, dass Sie den richtigen IP-Bereich setzen, damit der Scheduler die Konfiguration an die Instanz senden kann
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

### Syslog-ng-Konfiguration

Hier ein Beispiel für eine `syslog-ng.conf`-Datei, die Sie verwenden können, um die Protokolle in eine Datei weiterzuleiten:

```conf
@version: 4.10

# Quelle konfigurieren, um Logs von BunkerWeb-Diensten zu empfangen (ACCESS_LOG / ERROR_LOG und LOG_TYPES=syslog)
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# Template zur Formatierung der Lognachrichten
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# Zielkonfiguration, um Logs in dynamisch benannten Dateien zu schreiben
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

# Logpfad zur Weiterleitung der Logs in dynamisch benannte Dateien
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Docker Logging Best Practices

Bei der Verwendung von Docker ist es wichtig, die Container-Protokolle zu verwalten, um zu verhindern, dass sie übermäßig viel Speicherplatz beanspruchen. Standardmäßig verwendet Docker den `json-file`-Protokollierungstreiber, der bei fehlender Konfiguration zu sehr großen Protokolldateien führen kann.

Um dies zu vermeiden, können Sie die Protokollrotation konfigurieren. Dies kann für bestimmte Dienste in Ihrer `docker-compose.yml`-Datei oder global für den Docker-Daemon erfolgen.

**Konfiguration pro Dienst**

Sie können den Protokollierungstreiber für Ihre Dienste in Ihrer `docker-compose.yml`-Datei so konfigurieren, dass die Protokolle automatisch rotiert werden. Hier ist ein Beispiel, das bis zu 10 Protokolldateien mit jeweils 20 MB aufbewahrt:

```yaml
services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.8-rc3
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "10"
    ...
```

Diese Konfiguration stellt sicher, dass die Protokolle rotiert werden, und verhindert, dass sie Ihre Festplatte füllen. Sie können dies auf jeden Dienst in Ihrer Docker Compose-Einrichtung anwenden.

**Globale Einstellungen (daemon.json)**

Wenn Sie diese Protokollierungseinstellungen standardmäßig auf alle Container auf dem Host anwenden möchten, können Sie den Docker-Daemon konfigurieren, indem Sie die Datei `/etc/docker/daemon.json` bearbeiten (oder erstellen):

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "20m",
    "max-file": "10"
  }
}
```

Nachdem Sie `daemon.json` geändert haben, müssen Sie den Docker-Daemon neu starten, damit die Änderungen wirksam werden:

```shell
sudo systemctl restart docker
```

Diese globalen Einstellungen werden von allen Containern übernommen. Jede pro Dienst in einer `docker-compose.yml`-Datei definierte Protokollierungskonfiguration überschreibt jedoch die globalen Einstellungen in `daemon.json`.

## Sicherheits-Tuning {#security-tuning}

BunkerWeb bietet viele Sicherheitsfunktionen, die Sie mit [Features](features.md) konfigurieren können. Auch wenn die Standardwerte der Einstellungen eine minimale "Sicherheit von Haus aus" gewährleisten, empfehlen wir dringend, sie anzupassen. Dadurch können Sie das Sicherheitsniveau Ihrer Wahl sicherstellen und auch Fehlalarme verwalten.

!!! tip "Andere Funktionen"
    Dieser Abschnitt konzentriert sich nur auf das Sicherheits-Tuning, siehe den Abschnitt [Features](features.md) der Dokumentation für andere Einstellungen.

<figure markdown>
  ![Übersicht](assets/img/core-order.svg){ align=center }
  <figcaption>Übersicht und Reihenfolge der Kern-Sicherheits-Plugins</figcaption>
</figure>

## CrowdSec Console-Integration

Wenn Sie noch nicht mit der CrowdSec Console-Integration vertraut sind, [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) nutzt crowdsourced Intelligenz, um Cyber-Bedrohungen zu bekämpfen. Stellen Sie es sich wie das "Waze der Cybersicherheit" vor – wenn ein Server angegriffen wird, werden andere Systeme weltweit alarmiert und vor denselben Angreifern geschützt. Mehr darüber erfahren Sie [hier](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

**Herzlichen Glückwunsch, Ihre BunkerWeb-Instanz ist jetzt in Ihrer CrowdSec Console registriert!**

Pro-Tipp: Wenn Sie Ihre Warnungen anzeigen, klicken Sie auf die Option "Spalten" und aktivieren Sie das Kontrollkästchen "Kontext", um auf BunkerWeb-spezifische Daten zuzugreifen.

<figure markdown>
  ![Übersicht](assets/img/crowdity4.png){ align=center }
  <figcaption>BunkerWeb-Daten, die in der Kontextspalte angezeigt werden</figcaption>
</figure>

## Überwachung und Berichterstattung

### Überwachung <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM-Unterstützung :x:

Das Überwachungs-Plugin ermöglicht es Ihnen, Metriken über BunkerWeb zu sammeln und abzurufen. Durch die Aktivierung beginnen Ihre Instanz(en), verschiedene Daten zu Angriffen, Anfragen und Leistung zu sammeln. Sie können sie dann durch Aufrufen des API-Endpunkts `/monitoring` regelmäßig abrufen oder andere Plugins wie den Prometheus-Exporter verwenden.

**Liste der Funktionen**

-   Aktivierung der Sammlung verschiedener BunkerWeb-Metriken
-   Abrufen von Metriken von der API
-   Verwendung in Kombination mit anderen Plugins (z. B. Prometheus-Exporter)
-   Dedizierte UI-Seite zur Überwachung Ihrer Instanz(en)

**Liste der Einstellungen**

| Einstellung                    | Standard | Kontext | Mehrfach | Beschreibung                                                 |
| ------------------------------ | -------- | ------- | -------- | ------------------------------------------------------------ |
| `USE_MONITORING`               | `yes`    | global  | nein     | Aktiviert die Überwachung von BunkerWeb.                     |
| `MONITORING_METRICS_DICT_SIZE` | `10M`    | global  | nein     | Größe des Diktionärs zum Speichern von Überwachungsmetriken. |

### Prometheus-Exporter <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM-Unterstützung :x:

Das Prometheus-Exporter-Plugin fügt einen [Prometheus-Exporter](https://prometheus.io/docs/instrumenting/exporters/) zu Ihrer/n BunkerWeb-Instanz(en) hinzu. Wenn aktiviert, können Sie Ihre Prometheus-Instanz(en) so konfigurieren, dass sie einen bestimmten Endpunkt auf BunkerWeb abrufen und interne Metriken sammeln.

Wir stellen auch ein [Grafana-Dashboard](https://grafana.com/grafana/dashboards/20755-bunkerweb/) zur Verfügung, das Sie in Ihre eigene Instanz importieren und mit Ihrer eigenen Prometheus-Datenquelle verbinden können.

**Bitte beachten Sie, dass die Verwendung des Prometheus-Exporter-Plugins die Aktivierung des Überwachungs-Plugins erfordert (`USE_MONITORING=yes`)**

**Liste der Funktionen**

-   Prometheus-Exporter, der interne BunkerWeb-Metriken bereitstellt
-   Dedizierter und konfigurierbarer Port, lauschende IP und URL
-   Whitelist-IP/Netzwerk für maximale Sicherheit

**Liste der Einstellungen**

| Einstellung                    | Standard                                              | Kontext | Mehrfach | Beschreibung                                                                      |
| ------------------------------ | ----------------------------------------------------- | ------- | -------- | --------------------------------------------------------------------------------- |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | global  | nein     | Aktiviert den Prometheus-Export.                                                  |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | global  | nein     | Lauschende IP des Prometheus-Exporters.                                           |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | global  | nein     | Lauschender Port des Prometheus-Exporters.                                        |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | global  | nein     | HTTP-URL des Prometheus-Exporters.                                                |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | global  | nein     | Liste der IP/Netzwerke, die den Prometheus-Exporter-Endpunkt kontaktieren dürfen. |

### Berichterstattung <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM-Unterstützung :x:

!!! warning "Überwachungs-Plugin erforderlich"
    Dieses Plugin erfordert, dass das Monitoring Pro-Plugin installiert und mit der Einstellung `USE_MONITORING` auf `yes` gesetzt ist.

Das Reporting-Plugin bietet eine umfassende Lösung für die regelmäßige Berichterstattung wichtiger Daten aus BunkerWeb, einschließlich globaler Statistiken, Angriffe, Sperren, Anfragen, Gründe und AS-Informationen. Es bietet eine breite Palette von Funktionen, einschließlich automatischer Berichterstellung, Anpassungsoptionen und nahtloser Integration mit dem Monitoring Pro-Plugin. Mit dem Reporting-Plugin können Sie Berichte einfach erstellen und verwalten, um die Leistung und Sicherheit Ihrer Anwendung zu überwachen.

**Liste der Funktionen**

-   Regelmäßige Berichterstattung wichtiger Daten aus BunkerWeb, einschließlich globaler Statistiken, Angriffe, Sperren, Anfragen, Gründe und AS-Informationen.
-   Integration mit dem Monitoring Pro-Plugin für nahtlose Integration und erweiterte Berichtsfunktionen.
-   Unterstützung für Webhooks (klassisch, Discord und Slack) für Echtzeit-Benachrichtigungen.
-   Unterstützung für SMTP für E-Mail-Benachrichtigungen.
-   Konfigurationsoptionen zur Anpassung und Flexibilität.

**Liste der Einstellungen**

| Einstellung                    | Standard           | Kontext | Beschreibung                                                                                 |
| ------------------------------ | ------------------ | ------- | -------------------------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | global  | Versand des Berichts per E-Mail (HTML) aktivieren.                                           |
| `USE_REPORTING_WEBHOOK`        | `no`               | global  | Versand des Berichts über Webhook (Markdown) aktivieren.                                     |
| `REPORTING_SCHEDULE`           | `weekly`           | global  | Berichtszyklus: `daily`, `weekly` oder `monthly`.                                            |
| `REPORTING_WEBHOOK_URLS`       |                    | global  | Mit Leerzeichen getrennte Webhook-URLs; Discord und Slack werden automatisch erkannt.        |
| `REPORTING_SMTP_EMAILS`        |                    | global  | Mit Leerzeichen getrennte E-Mail-Empfänger.                                                  |
| `REPORTING_SMTP_HOST`          |                    | global  | SMTP-Servername oder IP.                                                                     |
| `REPORTING_SMTP_PORT`          | `465`              | global  | SMTP-Port. Verwende `465` für SSL, `587` für TLS.                                            |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | global  | Absenderadresse (2FA falls nötig deaktivieren).                                              |
| `REPORTING_SMTP_FROM_USER`     |                    | global  | SMTP-Benutzername (fällt auf die Absenderadresse zurück, wenn nur das Passwort gesetzt ist). |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | global  | SMTP-Passwort.                                                                               |
| `REPORTING_SMTP_SSL`           | `SSL`              | global  | Verbindungssicherheit: `no`, `SSL` oder `TLS`.                                               |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | global  | Betreffzeile für den E-Mail-Versand.                                                         |

!!! info "Information und Verhalten"
    - `REPORTING_SMTP_EMAILS` ist erforderlich, wenn SMTP aktiviert ist; `REPORTING_WEBHOOK_URLS` ist erforderlich, wenn Webhooks aktiviert sind.
    - Wenn Webhooks und SMTP fehlschlagen, erfolgt der nächste Zustellversuch beim nächsten geplanten Lauf.
    - Die HTML- und Markdown-Vorlagen liegen in `reporting/files/`; nur vorsichtig anpassen, damit Platzhalter erhalten bleiben.

## Sicherung und Wiederherstellung

### Sicherung S3 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM-Unterstützung :white_check_mark:

Das Backup S3-Tool automatisiert nahtlos den Datenschutz, ähnlich dem Community-Backup-Plugin. Es zeichnet sich jedoch dadurch aus, dass es Backups direkt und sicher in einem S3-Bucket speichert.

Durch die Aktivierung dieser Funktion schützen Sie proaktiv die **Integrität Ihrer Daten**. Das Speichern von Backups **remote** schützt wichtige Informationen vor Bedrohungen wie **Hardwareausfällen**, **Cyberangriffen** oder **Naturkatastrophen**. Dies gewährleistet sowohl **Sicherheit** als auch **Verfügbarkeit**, ermöglicht eine schnelle Wiederherstellung bei **unerwarteten Ereignissen**, bewahrt die **betriebliche Kontinuität** und sorgt für **Sorgenfreiheit**.

??? warning "Informationen für Benutzer von Red Hat Enterprise Linux (RHEL) 8.9"
    Wenn Sie **RHEL 8.9** verwenden und eine **externe Datenbank** nutzen möchten, müssen Sie das Paket `mysql-community-client` installieren, um sicherzustellen, dass der Befehl `mysqldump` verfügbar ist. Sie können das Paket mit den folgenden Befehlen installieren:

    === "MySQL/MariaDB"

        1. **Installieren Sie das MySQL-Repository-Konfigurationspaket**

            ```bash
            sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
            ```

        2. **Aktivieren Sie das MySQL-Repository**

            ```bash
            sudo dnf config-manager --enable mysql80-community
            ```

        3. **Installieren Sie den MySQL-Client**

            ```bash
            sudo dnf install mysql-community-client
            ```

    === "PostgreSQL"

        1. **Installieren Sie das PostgreSQL-Repository-Konfigurationspaket**

            ```bash
            dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
            ```

        2. **Installieren Sie den PostgreSQL-Client**

            ```bash
            dnf install postgresql<version>
            ```

**Liste der Funktionen**

-   Automatische Datensicherung in einem S3-Bucket
-   Flexible Planungsoptionen: täglich, wöchentlich oder monatlich
-   Rotationsmanagement zur Steuerung der Anzahl der aufzubewahrenden Backups
-   Anpassbarer Komprimierungsgrad für Backup-Dateien

**Liste der Einstellungen**

| Einstellung                   | Standard | Kontext | Beschreibung                                      |
| ----------------------------- | -------- | ------- | ------------------------------------------------- |
| `USE_BACKUP_S3`               | `no`     | global  | Aktiviert oder deaktiviert die S3-Backup-Funktion |
| `BACKUP_S3_SCHEDULE`          | `daily`  | global  | Die Häufigkeit des Backups                        |
| `BACKUP_S3_ROTATION`          | `7`      | global  | Die Anzahl der aufzubewahrenden Backups           |
| `BACKUP_S3_ENDPOINT`          |          | global  | Der S3-Endpunkt                                   |
| `BACKUP_S3_BUCKET`            |          | global  | Der S3-Bucket                                     |
| `BACKUP_S3_DIR`               |          | global  | Das S3-Verzeichnis                                |
| `BACKUP_S3_REGION`            |          | global  | Die S3-Region                                     |
| `BACKUP_S3_ACCESS_KEY_ID`     |          | global  | Die S3-Zugriffsschlüssel-ID                       |
| `BACKUP_S3_ACCESS_KEY_SECRET` |          | global  | Das S3-Zugriffsschlüsselgeheimnis                 |
| `BACKUP_S3_COMP_LEVEL`        | `6`      | global  | Der Komprimierungsgrad der Backup-Zip-Datei       |

#### Manuelle Sicherung

Um eine Sicherung manuell zu starten, führen Sie den folgenden Befehl aus:

=== "Linux"

    ```bash
    bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 save
    ```

Dieser Befehl erstellt eine Sicherung Ihrer Datenbank und speichert sie im S3-Bucket, der in der Einstellung `BACKUP_S3_BUCKET` angegeben ist.

Sie können auch einen benutzerdefinierten S3-Bucket für die Sicherung angeben, indem Sie die Umgebungsvariable `BACKUP_S3_BUCKET` bei der Ausführung des Befehls bereitstellen:

=== "Linux"

    ```bash
    BACKUP_S3_BUCKET=your-bucket-name bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it -e BACKUP_S3_BUCKET=your-bucket-name <scheduler_container> bwcli plugin backup_s3 save
    ```

!!! note "Spezifikationen für MariaDB/MySQL"

    Falls Sie MariaDB/MySQL verwenden, kann beim Versuch, Ihre Datenbank zu sichern, der folgende Fehler auftreten:

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    Um dieses Problem zu lösen, können Sie den folgenden Befehl ausführen, um das Authentifizierungs-Plugin auf `mysql_native_password` zu ändern:

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    Wenn Sie die Docker-Integration verwenden, können Sie den folgenden Befehl zur `docker-compose.yml`-Datei hinzufügen, um das Authentifizierungs-Plugin automatisch zu ändern:

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

#### Manuelle Wiederherstellung

Um eine Wiederherstellung manuell zu starten, führen Sie den folgenden Befehl aus:

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
    ```

Dieser Befehl erstellt eine temporäre Sicherung Ihrer Datenbank im S3-Bucket, der in der Einstellung `BACKUP_S3_BUCKET` angegeben ist, und stellt Ihre Datenbank auf die neueste im Bucket verfügbare Sicherung wieder her.

Sie können auch eine benutzerdefinierte Sicherungsdatei für die Wiederherstellung angeben, indem Sie den Pfad dazu als Argument bei der Ausführung des Befehls angeben:

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore s3_backup_file.zip
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup restore s3_backup_file.zip
    ```

!!! example "Im Falle eines Fehlers"

    Machen Sie sich keine Sorgen, wenn die Wiederherstellung fehlschlägt, Sie können Ihre Datenbank jederzeit auf den vorherigen Zustand zurücksetzen, indem Sie den Befehl erneut ausführen, da vor der Wiederherstellung eine Sicherung erstellt wird:

    === "Linux"

        ```bash
        bwcli plugin backup_s3 restore
        ```

    === "Docker"

        ```bash
        docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
        ```

## Migration <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM-Unterstützung :white_check_mark:

Das Migrations-Plugin **revolutioniert** die Übertragung von BunkerWeb-Konfigurationen zwischen Instanzen mit seiner **benutzerfreundlichen Weboberfläche**, die den gesamten Migrationsprozess vereinfacht. Ob Sie Systeme aufrüsten, die Infrastruktur skalieren oder Umgebungen wechseln, dieses Tool ermöglicht es Ihnen, **Einstellungen, Präferenzen und Daten** mühelos und mit unübertroffener Leichtigkeit und Zuversicht zu übertragen. Verabschieden Sie sich von umständlichen manuellen Prozessen und begrüßen Sie ein **nahtloses, problemloses Migrationserlebnis**.

**Liste der Funktionen**

-   **Mühelose Migration:** Übertragen Sie BunkerWeb-Konfigurationen einfach zwischen Instanzen, ohne die Komplexität manueller Verfahren.

-   **Intuitive Weboberfläche:** Navigieren Sie mühelos durch den Migrationsprozess mit einer benutzerfreundlichen Weboberfläche, die für eine intuitive Bedienung entwickelt wurde.

-   **Datenbankübergreifende Kompatibilität:** Genießen Sie eine nahtlose Migration über verschiedene Datenbankplattformen hinweg, einschließlich SQLite, MySQL, MariaDB und PostgreSQL, und gewährleisten Sie die Kompatibilität mit Ihrer bevorzugten Datenbankumgebung.

### Eine Migrationsdatei erstellen

Um eine Migrationsdatei manuell zu erstellen, führen Sie den folgenden Befehl aus:

=== "Linux"

    ```bash
    bwcli plugin migration create /pfad/zur/migrations/datei
    ```

=== "Docker"

    1.  Eine Migrationsdatei erstellen:

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration create /pfad/zur/migrations/datei
        ```

    2.  Kopieren Sie die Migrationsdatei auf Ihren lokalen Rechner:

        ```bash
        docker cp <scheduler_container>:/pfad/zur/migrations/datei /pfad/zur/migrations/datei
        ```

Dieser Befehl erstellt eine Sicherung Ihrer Datenbank und speichert sie im im Befehl angegebenen Sicherungsverzeichnis.

!!! note "Spezifikationen für MariaDB/MySQL"

    Falls Sie MariaDB/MySQL verwenden, kann beim Versuch, Ihre Datenbank zu sichern, der folgende Fehler auftreten:

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    Um dieses Problem zu lösen, können Sie den folgenden Befehl ausführen, um das Authentifizierungs-Plugin auf `mysql_native_password` zu ändern:

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    Wenn Sie die Docker-Integration verwenden, können Sie den folgenden Befehl zur `docker-compose.yml`-Datei hinzufügen, um das Authentifizierungs-Plugin automatisch zu ändern:

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

### Eine Migration initialisieren

Um eine Migration manuell zu initialisieren, führen Sie den folgenden Befehl aus:

=== "Linux"

    ```bash
    bwcli plugin migration migrate /pfad/zur/migrations/datei
    ```

=== "Docker"

    1.  Kopieren Sie die Migrationsdatei in den Container:

        ```bash
        docker cp /pfad/zur/migrations/datei <scheduler_container>:/pfad/zur/migrations/datei
        ```

    2.  Initialisieren Sie die Migration:

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration migrate /pfad/zur/migrations/datei
        ```

=== "All-in-one"

    1.  Kopieren Sie die Migrationsdatei in den Container:

        ```bash
        docker cp /pfad/zur/migrations/datei bunkerweb-aio:/pfad/zur/migrations/datei
        ```

    2.  Initialisieren Sie die Migration:

        ```bash
        docker exec -it bunkerweb-aio bwcli plugin migration migrate /pfad/zur/migrations/datei
        ```

Dieser Befehl migriert Ihre BunkerWeb-Daten nahtlos, um genau der in der Migrationsdatei beschriebenen Konfiguration zu entsprechen.

## Anti-DDoS <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM-Unterstützung :x:

Das **Anti-DDoS**-Plugin bietet fortschrittlichen Schutz gegen Distributed Denial of Service (DDoS)-Angriffe, indem es verdächtigen Verkehr in Echtzeit überwacht, analysiert und filtert.

Durch die Verwendung eines **gleitenden Fenstermechanismus** unterhält das Plugin ein In-Memory-Wörterbuch mit Zeitstempeln von Anfragen, um anormale Verkehrsspitzen von einzelnen IP-Adressen zu erkennen. Basierend auf dem konfigurierten Sicherheitsmodus kann es entweder die beleidigenden Verbindungen blockieren oder die verdächtige Aktivität zur weiteren Überprüfung protokollieren.

### Funktionen

-   **Echtzeit-Verkehrsanalyse:** Überwacht kontinuierlich eingehende Anfragen, um potenzielle DDoS-Angriffe zu erkennen.
-   **Gleitender Fenstermechanismus:** Verfolgt die jüngsten Anforderungsaktivitäten innerhalb eines konfigurierbaren Zeitfensters.
-   **Konfigurierbare Schwellenwerte:** Ermöglicht die Definition der maximalen Anzahl verdächtiger Anfragen pro IP.
-   **Fortschrittliche Blockierungslogik:** Wertet sowohl die Anzahl der Anfragen pro IP als auch die Anzahl der unterschiedlichen IPs aus, die den Schwellenwert überschreiten.
-   **Flexible Sicherheitsmodi:** Wählen Sie zwischen sofortiger Verbindungsblockierung oder dem reinen Erkennungsmodus (Protokollierung).
-   **Optimierter In-Memory-Datenspeicher:** Gewährleistet Hochgeschwindigkeits-Lookups und effizientes Metrik-Tracking.
-   **Automatische Bereinigung:** Löscht regelmäßig veraltete Daten, um eine optimale Leistung zu gewährleisten.

### Konfiguration

Passen Sie das Verhalten des Plugins mit den folgenden Einstellungen an:

| Einstellung                  | Standard      | Kontext | Mehrfach | Beschreibung                                                                                                                 |
| ---------------------------- | ------------- | ------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`          | global  | nein     | Aktiviert oder deaktiviert den Anti-DDoS-Schutz. Setzen Sie auf `"yes"`, um das Plugin zu aktivieren.                        |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`         | global  | nein     | Größe des In-Memory-Datenspeichers zur Verfolgung von DDoS-Metriken (z. B. `10M`, `500k`).                                   |
| `ANTIDDOS_THRESHOLD`         | `100`         | global  | nein     | Maximale Anzahl verdächtiger Anfragen pro IP innerhalb des definierten Zeitfensters.                                         |
| `ANTIDDOS_WINDOW_TIME`       | `10`          | global  | nein     | Zeitfenster in Sekunden, in dem verdächtige Anfragen gezählt werden.                                                         |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444` | global  | nein     | HTTP-Statuscodes, die als verdächtig gelten und zur Auslösung von Anti-DDoS-Aktionen verwendet werden.                       |
| `ANTIDDOS_DISTINCT_IP`       | `5`           | global  | nein     | Mindestanzahl unterschiedlicher IPs, die den Schwellenwert überschreiten müssen, bevor der Blockierungsmodus erzwungen wird. |

### Bewährte Verfahren

-   **Schwellenwert-Tuning:** Passen Sie `ANTIDDOS_THRESHOLD` und `ANTIDDOS_WINDOW_TIME` basierend auf Ihren typischen Verkehrsmustern an.
-   **Statuscode-Überprüfung:** Aktualisieren Sie `ANTIDDOS_STATUS_CODES` regelmäßig, um neue oder sich entwickelnde verdächtige Verhaltensweisen zu erfassen.
-   **Überwachung:** Analysieren Sie Protokolle und Metriken regelmäßig, um die Einstellungen zu optimieren und den Gesamtschutz zu verbessern.

## Benutzer-Manager <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/EIohiUf9Fg4" title="Benutzer-Manager" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Das Benutzerverwaltungs-Plugin bietet eine robuste Schnittstelle zur Verwaltung von Benutzerkonten in Ihrem System.

Mit diesem Plugin können Administratoren mühelos Benutzerkonten erstellen, aktualisieren und deaktivieren, Benutzerrollen verwalten, die Zwei-Faktor-Authentifizierung (2FA) umschalten und detaillierte Benutzerinformationen wie letzte Anmeldezeitstempel und Kontostatus (aktiv oder inaktiv) anzeigen. Dieses Plugin wurde mit Blick auf Sicherheit und Benutzerfreundlichkeit entwickelt und vereinfacht routinemäßige Benutzerverwaltungsaufgaben, während es gleichzeitig die Einhaltung von Vorschriften und die Überprüfbarkeit gewährleistet.

### Funktionen

-   **Benutzerkonto-Operationen:** Importieren im CSV/XSLX-Format, Erstellen, Bearbeiten und Löschen von Benutzerkonten mit Leichtigkeit.
-   **Rollenbasierte Zugriffskontrolle:** Weisen Sie Benutzerrollen zu und ändern Sie sie, um Berechtigungen und Zugriffsebenen zu verwalten.
-   **2FA-Verwaltung:** Deaktivieren Sie die Zwei-Faktor-Authentifizierung basierend auf administrativen Entscheidungen.
-   **Umfassende Benutzereinblicke:** Überwachen Sie wichtige Benutzerdaten, einschließlich letzter Anmeldezeiten, Kontoerstellungsdaten und Aktiv/Inaktiv-Status.
-   **Audit-Protokollierung:** Führen Sie eine Audit-Spur für alle Benutzerverwaltungsaktionen für verbesserte Sicherheit und Compliance.

<figure markdown>
  ![Übersicht](assets/img/user-manager.png){ align=center }
  <figcaption>Benutzer-Manager-Seite</figcaption>
</figure>

<figure markdown>
  ![Benutzererstellungsformular](assets/img/user-manager-create.png){ align=center }
  <figcaption>Benutzer-Manager - Benutzererstellungsformular</figcaption>
</figure>

<figure markdown>
  ![Aktivitätenseite](assets/img/user-manager-activities.png){ align=center }
  <figcaption>Benutzer-Manager - Aktivitätenseite</figcaption>
</figure>

## Easy Resolve <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/45vX0WJqjxo" title="Easy Resolve" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Das Easy Resolve Plugin ermöglicht es Ihnen, Fehlalarme und wiederkehrende Probleme direkt von der Berichtsseite aus schnell zu beheben. Es wandelt geführte "Resolve"-Aktionen in sichere, bereichsbezogene Konfigurationsupdates um – ohne manuelle Bearbeitung.

### Funktionen

- Ein-Klick-Aktionen aus Berichten und Berichtsdetails.
- Kontextbezogene Vorschläge für ModSecurity, Blacklist, DNSBL, Ratenbegrenzung, erlaubte HTTP-Methoden und Whitelisted/Blacklisted Länder.
- Generiert sichere ModSecurity-Ausschlüsse oder aktualisiert Ignorierlisten.
- Wendet Änderungen auf Dienst- oder globaler Ebene mit Berechtigungsprüfungen an.
- Optionales automatisches Öffnen der zugehörigen Konfigurationsseite nach der Anwendung.

<figure markdown>
  ![Übersicht](assets/img/easy-resolve.png){ align=center }
  <figcaption>Berichtsseite - mit Easy Resolve</figcaption>
</figure>

## Load Balancer <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/cOVp0rAt5nw?si=iVhDio8o8S4F_uag" title="Load Balancer" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Das Load Balancer Plugin verwandelt BunkerWeb in einen Traffic-Director mit Schutzvorrichtungen. Deklarieren Sie Upstream-Pools einmal, leiten Sie Ihren Reverse-Proxy darauf und lassen Sie das health-aware Balancing die Benutzer auf reaktionsfähigen Backends halten. Der Sticky-Cookie-Modus gibt automatisch einen `BWLBID`-Cookie aus, damit Sitzungen dort verankert bleiben, wo Sie möchten.

### Features

- Per-Upstream-Blöcke: Pools benennen und über Reverse-Proxy-Hosts wiederverwenden.
- Flexibles Balancing: Round-Robin standardmäßig oder Sticky über IP oder signiertem Cookie.
- Smarte Ziele: Optionale DNS-Auflösung für Hostname-Backends plus Keepalive-Tuning.
- Eingebaute Gesundheit: HTTP/HTTPS-Probes mit benutzerdefinierten Pfaden, Intervallen, Statuscodes und SSL-Checks.
- Sitzungskontinuität: Automatischer `BWLBID`-Cookie bei Aktivierung des Sticky-Cookie-Modus.

### Konfiguration

**Upstream-Definition**

| Einstellung                               | Standard      | Kontext | Mehrfach | Beschreibung                                                                           |
| ----------------------------------------- | ------------- | ------- | -------- | -------------------------------------------------------------------------------------- |
| `LOADBALANCER_UPSTREAM_NAME`              |               | global  | ja       | Upstream-Bezeichner (referenziert von `REVERSE_PROXY_HOST`).                           |
| `LOADBALANCER_UPSTREAM_SERVERS`           |               | global  | ja       | Leerzeichen-getrennte Liste von Backend-Adressen (z.B. `10.0.0.1:8080 10.0.0.2:8080`). |
| `LOADBALANCER_UPSTREAM_MODE`              | `round-robin` | global  | ja       | Balancing-Strategie (`round-robin` oder `sticky`).                                     |
| `LOADBALANCER_UPSTREAM_STICKY_METHOD`     | `ip`          | global  | ja       | Sticky-Methode (`ip` oder `cookie`). Cookie-Modus gibt `BWLBID` aus.                   |
| `LOADBALANCER_UPSTREAM_RESOLVE`           | `no`          | global  | ja       | Upstream-Hostnamen über DNS auflösen.                                                  |
| `LOADBALANCER_UPSTREAM_KEEPALIVE`         |               | global  | ja       | Keepalive-Verbindungen pro Worker.                                                     |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIMEOUT` | `60s`         | global  | ja       | Idle-Timeout für Keepalive-Verbindungen.                                               |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIME`    | `1h`          | global  | ja       | Maximale Lebensdauer für Keepalive-Verbindungen.                                       |

**Gesundheitsprüfungen**

| Einstellung                               | Standard  | Kontext | Mehrfach | Beschreibung                                                    |
| ----------------------------------------- | --------- | ------- | -------- | --------------------------------------------------------------- |
| `LOADBALANCER_HEALTHCHECK_DICT_SIZE`      | `10m`     | global  | nein     | Shared Dictionary-Größe für Gesundheitsprüfungsstatus.          |
| `LOADBALANCER_HEALTHCHECK_URL`            | `/status` | global  | ja       | Pfad zum Sondieren auf jedem Backend.                           |
| `LOADBALANCER_HEALTHCHECK_INTERVAL`       | `2000`    | global  | ja       | Intervall zwischen Prüfungen (ms).                              |
| `LOADBALANCER_HEALTHCHECK_TIMEOUT`        | `1000`    | global  | ja       | Timeout pro Prüfung (ms).                                       |
| `LOADBALANCER_HEALTHCHECK_FALL`           | `3`       | global  | ja       | Aufeinanderfolgende Fehler vor dem Markieren als down.          |
| `LOADBALANCER_HEALTHCHECK_RISE`           | `1`       | global  | ja       | Aufeinanderfolgende Erfolge vor dem Markieren als up.           |
| `LOADBALANCER_HEALTHCHECK_VALID_STATUSES` | `200`     | global  | ja       | Leerzeichen-getrennte Liste gültiger HTTP-Statuscodes.          |
| `LOADBALANCER_HEALTHCHECK_CONCURRENCY`    | `10`      | global  | ja       | Maximale gleichzeitige Sonden.                                  |
| `LOADBALANCER_HEALTHCHECK_TYPE`           | `http`    | global  | ja       | Protokoll für Gesundheitsprüfungen (`http` oder `https`).       |
| `LOADBALANCER_HEALTHCHECK_SSL_VERIFY`     | `yes`     | global  | ja       | TLS-Zertifikate bei HTTPS-Prüfungen verifizieren.               |
| `LOADBALANCER_HEALTHCHECK_HOST`           |           | global  | ja       | Host-Header während Prüfungen überschreiben (nützlich für SNI). |

### Schnellstart

1. Definieren Sie Ihren Pool: Setzen Sie `LOADBALANCER_UPSTREAM_NAME=my-app` und listen Sie Ziele in `LOADBALANCER_UPSTREAM_SERVERS` (z.B. `10.0.0.1:8080 10.0.0.2:8080`).
2. Leiten Sie Traffic: Setzen Sie `REVERSE_PROXY_HOST=http://my-app`, damit der Reverse-Proxy den benannten Upstream verwendet.
3. Wählen Sie einen Modus: Behalten Sie das Standard-Round-Robin bei oder setzen Sie `LOADBALANCER_UPSTREAM_MODE=sticky` mit `LOADBALANCER_UPSTREAM_STICKY_METHOD=cookie` oder `ip`.
4. Fügen Sie Gesundheit hinzu: Behalten Sie `/status` bei oder passen Sie URLs, Intervalle und gültige Statuscodes an, um Ihr App-Verhalten widerzuspiegeln.
5. Stimmen Sie Verbindungen ab: Konfigurieren Sie Keepalive-Werte, um Backend-Verbindungen wiederzuverwenden und Handshake-Overhead zu reduzieren.

### Nutzungstipps

- Passen Sie `REVERSE_PROXY_HOST` an `LOADBALANCER_UPSTREAM_NAME` an, wenn Sie Sticky-Cookies verwenden, damit Clients an den richtigen Pool gebunden werden.
- Halten Sie Gesundheitsprüfungsintervalle und Timeouts ausgewogen, um Flattern auf langsamen Links zu vermeiden.
- Aktivieren Sie `LOADBALANCER_UPSTREAM_RESOLVE`, wenn Sie auf Hostnamen zeigen, die sich über DNS ändern können.
- Stimmen Sie Keepalive-Werte ab, um Backend-Kapazität und Ziele für die Wiederverwendung von Verbindungen widerzuspiegeln.

## Custom Pages <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Das Custom Pages Plugin ermöglicht es Ihnen, die eingebauten Seiten von BunkerWeb (Fehlerseiten, Standard-Server-Seite und Antibot-Challenge-Seiten) durch Ihre eigenen benutzerdefinierten HTML- oder Lua-Vorlagen zu ersetzen. Dies ermöglicht es Ihnen, ein einheitliches Branding auf allen benutzerseitigen Seiten von BunkerWeb beizubehalten.

### Funktionen

- **Benutzerdefinierte Fehlerseiten pro Service** und **Antibot-Challenge-Seiten** (Captcha, JavaScript-Prüfung, reCAPTCHA, hCaptcha, Turnstile, mCaptcha).
- **Globale benutzerdefinierte Standard-Server-Seite** für den Fallback/Standard-vhost.
- **HTML-Parsing und Lua-Vorlagen-Tag-Balanceprüfungen** bevor eine Vorlage akzeptiert wird.
- **Automatisches Caching** nach `/var/cache/bunkerweb/custom_pages` mit Änderungserkennung für Neuladen.
- **Pro-Site oder globale Konfiguration** über Einstellungen/UI oder Umgebungsvariablen.

### Wie es funktioniert

1. Beim Start (oder wenn sich Einstellungen ändern) liest der `custom-pages.py`-Job die konfigurierten Vorlagenpfade.
2. Jede Datei muss existieren und vom Scheduler lesbar sein; der Job validiert HTML-Struktur und ausgeglichene Lua-Vorlagen-Tags (`{% %}`, `{{ }}`, `{* *}`).
3. Akzeptierte Dateien werden unter `/var/cache/bunkerweb/custom_pages/<type>.html` zwischengespeichert; fehlende/leere Einstellungen entfernen die gecachte Datei.
4. NGINX wird über `$template_root` auf das Cache-Verzeichnis verwiesen, wenn mindestens eine gecachte Seite existiert, sodass Ihre Vorlagen anstelle der Standardseiten ausgeliefert werden.

### Konfigurationseinstellungen

| Einstellung                      | Standard | Kontext   | Beschreibung                                                            |
| -------------------------------- | -------- | --------- | ----------------------------------------------------------------------- |
| `CUSTOM_ERROR_PAGE`              |          | multisite | Absoluter Pfad zur benutzerdefinierten Fehlerseiten-Vorlage.            |
| `CUSTOM_DEFAULT_SERVER_PAGE`     |          | global    | Absoluter Pfad zur benutzerdefinierten Standard-Server-Seiten-Vorlage.  |
| `CUSTOM_ANTIBOT_CAPTCHA_PAGE`    |          | multisite | Absoluter Pfad zur benutzerdefinierten Antibot-CAPTCHA-Challenge-Seite. |
| `CUSTOM_ANTIBOT_JAVASCRIPT_PAGE` |          | multisite | Absoluter Pfad zur benutzerdefinierten Antibot-JavaScript-Prüfseite.    |
| `CUSTOM_ANTIBOT_RECAPTCHA_PAGE`  |          | multisite | Absoluter Pfad zur benutzerdefinierten Antibot-reCAPTCHA-Seite.         |
| `CUSTOM_ANTIBOT_HCAPTCHA_PAGE`   |          | multisite | Absoluter Pfad zur benutzerdefinierten Antibot-hCaptcha-Seite.          |
| `CUSTOM_ANTIBOT_TURNSTILE_PAGE`  |          | multisite | Absoluter Pfad zur benutzerdefinierten Antibot-Turnstile-Seite.         |
| `CUSTOM_ANTIBOT_MCAPTCHA_PAGE`   |          | multisite | Absoluter Pfad zur benutzerdefinierten Antibot-mCaptcha-Seite.          |

### Vorlagenvariablen-Referenz

BunkerWeb-Vorlagen verwenden die [lua-resty-template](https://github.com/bungle/lua-resty-template) Engine. Die folgenden Variablen sind je nach Seitentyp verfügbar:

#### Fehlerseiten-Variablen

Diese Variablen sind in benutzerdefinierten Fehlerseiten-Vorlagen (`CUSTOM_ERROR_PAGE`) verfügbar:

| Variable         | Typ    | Beschreibung                                                |
| ---------------- | ------ | ----------------------------------------------------------- |
| `title`          | string | Vollständiger Seitentitel (z.B. `403                        | Forbidden`) |
| `error_title`    | string | Fehlertiteltext (z.B. `Forbidden`)                          |
| `error_code`     | string | HTTP-Statuscode (z.B. `403`, `404`, `500`)                  |
| `error_text`     | string | Beschreibende Fehlermeldung                                 |
| `error_type`     | string | Fehlerkategorie: `client` (4xx) oder `server` (5xx)         |
| `error_solution` | string | Vorgeschlagener Lösungstext                                 |
| `nonce_script`   | string | Nonce-Wert für Inline-`<script>`-Tags (CSP-Konformität)     |
| `nonce_style`    | string | Nonce-Wert für Inline-`<style>`-Tags (CSP-Konformität)      |
| `request_id`     | string | Eindeutige Request-ID für Debugging                         |
| `client_ip`      | string | IP-Adresse des Clients                                      |
| `request_time`   | string | Zeitstempel der Anfrage (Format: `YYYY-MM-DD HH:MM:SS UTC`) |

#### Standard-Server-Seiten-Variablen

Diese Variablen sind in benutzerdefinierten Standard-Server-Seiten-Vorlagen (`CUSTOM_DEFAULT_SERVER_PAGE`) verfügbar:

| Variable      | Typ    | Beschreibung                                           |
| ------------- | ------ | ------------------------------------------------------ |
| `nonce_style` | string | Nonce-Wert für Inline-`<style>`-Tags (CSP-Konformität) |

#### Antibot-Challenge-Seiten-Variablen

Diese Variablen sind in Antibot-Challenge-Seiten-Vorlagen verfügbar:

**Gemeinsame Variablen (alle Antibot-Seiten):**

| Variable       | Typ    | Beschreibung                                            |
| -------------- | ------ | ------------------------------------------------------- |
| `antibot_uri`  | string | Formular-Action-URI zum Absenden der Challenge          |
| `nonce_script` | string | Nonce-Wert für Inline-`<script>`-Tags (CSP-Konformität) |
| `nonce_style`  | string | Nonce-Wert für Inline-`<style>`-Tags (CSP-Konformität)  |

**JavaScript-Challenge (`CUSTOM_ANTIBOT_JAVASCRIPT_PAGE`):**

| Variable | Typ    | Beschreibung                               |
| -------- | ------ | ------------------------------------------ |
| `random` | string | Zufälliger String für Proof-of-Work-Lösung |

**Captcha (`CUSTOM_ANTIBOT_CAPTCHA_PAGE`):**

| Variable  | Typ    | Beschreibung                                |
| --------- | ------ | ------------------------------------------- |
| `captcha` | string | Base64-kodiertes Captcha-Bild (JPEG-Format) |

**reCAPTCHA (`CUSTOM_ANTIBOT_RECAPTCHA_PAGE`):**

| Variable            | Typ     | Beschreibung                                     |
| ------------------- | ------- | ------------------------------------------------ |
| `recaptcha_sitekey` | string  | Ihr reCAPTCHA-Site-Key                           |
| `recaptcha_classic` | boolean | `true` bei klassischem reCAPTCHA, `false` für v3 |

**hCaptcha (`CUSTOM_ANTIBOT_HCAPTCHA_PAGE`):**

| Variable           | Typ    | Beschreibung          |
| ------------------ | ------ | --------------------- |
| `hcaptcha_sitekey` | string | Ihr hCaptcha-Site-Key |

**Turnstile (`CUSTOM_ANTIBOT_TURNSTILE_PAGE`):**

| Variable            | Typ    | Beschreibung                      |
| ------------------- | ------ | --------------------------------- |
| `turnstile_sitekey` | string | Ihr Cloudflare Turnstile-Site-Key |

**mCaptcha (`CUSTOM_ANTIBOT_MCAPTCHA_PAGE`):**

| Variable           | Typ    | Beschreibung          |
| ------------------ | ------ | --------------------- |
| `mcaptcha_sitekey` | string | Ihr mCaptcha-Site-Key |
| `mcaptcha_url`     | string | Ihre mCaptcha-URL     |

### Vorlagensyntax

Vorlagen verwenden Lua-Vorlagensyntax mit den folgenden Trennzeichen:

- `{{ variable }}` – Variable ausgeben (HTML-escaped)
- `{* variable *}` – Variable ausgeben (roh, nicht escaped)
- `{% lua_code %}` – Lua-Code ausführen (Bedingungen, Schleifen, etc.)
- `{-raw-}` ... `{-raw-}` – Rohblock (keine Verarbeitung)

**Wichtig**: Verwenden Sie immer Nonce-Attribute für Inline-Skripte und Styles, um die Content Security Policy (CSP) einzuhalten:

```html
<style nonce="{*nonce_style*}">
  /* Ihr CSS hier */
</style>
<script nonce="{*nonce_script*}">
  // Ihr JavaScript hier
</script>
```

### Beispiele

=== "Benutzerdefinierte Fehlerseite"

    Erstellen Sie eine benutzerdefinierte Fehlerseiten-Vorlage unter `/etc/bunkerweb/templates/error.html`:

    ```html
    {-raw-}<!doctype html>
    <html lang="de">
      <head>
        <meta charset="utf-8" />
        <title>{{ title }}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {-raw-}
        <style nonce="{*nonce_style*}">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #f5f5f5;
            color: #333;
          }
          .container {
            text-align: center;
            padding: 2rem;
          }
          .error-code {
            font-size: 6rem;
            font-weight: bold;
            color: {% if error_type == "server" %}#dc3545{% else %}#ffc107{% end %};
            margin: 0;
          }
          .error-title {
            font-size: 1.5rem;
            margin: 1rem 0;
          }
          .error-text {
            color: #666;
            margin-bottom: 1rem;
          }
          .request-info {
            font-size: 0.8rem;
            color: #999;
            margin-top: 2rem;
          }
        </style>
        {-raw-}
      </head>
      <body>
        <div class="container">
          <p class="error-code">{{ error_code }}</p>
          <h1 class="error-title">{{ error_title }}</h1>
          <p class="error-text">{{ error_text }}</p>
          <p class="error-text">{{ error_solution }}</p>
          <div class="request-info">
            {% if request_id %}
            <p>Anfrage-ID: <code>{{ request_id }}</code></p>
            {% end %}
            {% if request_time %}
            <p>Zeit: {{ request_time }}</p>
            {% end %}
          </div>
        </div>
      </body>
    </html>
    {-raw-}
    ```

=== "Benutzerdefinierte Captcha-Seite"

    Erstellen Sie eine benutzerdefinierte Captcha-Challenge-Seite unter `/etc/bunkerweb/templates/captcha.html`:

    ```html
    {-raw-}<!doctype html>
    <html lang="de">
      <head>
        <meta charset="utf-8" />
        <title>Sicherheitsprüfung</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {-raw-}
        <style nonce="{*nonce_style*}">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          }
          .card {
            background: white;
            padding: 2rem;
            border-radius: 1rem;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            text-align: center;
            max-width: 400px;
          }
          h1 {
            color: #333;
            margin-bottom: 1rem;
          }
          .captcha-img {
            margin: 1rem 0;
            border-radius: 0.5rem;
          }
          input[type="text"] {
            width: 100%;
            padding: 0.75rem;
            font-size: 1.2rem;
            border: 2px solid #ddd;
            border-radius: 0.5rem;
            text-align: center;
            box-sizing: border-box;
          }
          button {
            margin-top: 1rem;
            padding: 0.75rem 2rem;
            font-size: 1rem;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 0.5rem;
            cursor: pointer;
          }
          button:hover {
            background: #5a6fd6;
          }
        </style>
        {-raw-}
      </head>
      <body>
        <div class="card">
          <h1>🔒 Sicherheitsprüfung</h1>
          <p>Bitte geben Sie den Text ein, den Sie unten sehen, um fortzufahren.</p>
          {-raw-}
          <form method="POST" action="{*antibot_uri*}">
            <img class="captcha-img" src="data:image/jpeg;base64,{*captcha*}" alt="Captcha" />
            {-raw-}
            <input type="text" name="captcha" placeholder="Code eingeben" required autocomplete="off" />
            <button type="submit">Verifizieren</button>
          </form>
        </div>
      </body>
    </html>
    {-raw-}
    ```

=== "Benutzerdefinierte Standard-Server-Seite"

    Erstellen Sie eine benutzerdefinierte Standard-Server-Seite unter `/etc/bunkerweb/templates/default.html`:

    ```html
    {-raw-}<!doctype html>
    <html lang="de">
      <head>
        <meta charset="utf-8" />
        <title>Willkommen</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {-raw-}
        <style nonce="{*nonce_style*}">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #1a1a2e;
            color: #eee;
          }
          .container {
            text-align: center;
          }
          h1 {
            font-size: 3rem;
            margin-bottom: 0.5rem;
          }
          p {
            color: #888;
          }
        </style>
        {-raw-}
      </head>
      <body>
        <div class="container">
          <h1>🛡️ Geschützt durch BunkerWeb</h1>
          <p>Dieser Server ist sicher und bereit.</p>
        </div>
      </body>
    </html>
    {-raw-}
    ```

### Bereitstellungsbeispiele

=== "Linux"

    1. Erstellen Sie Ihre Vorlagendateien in einem Verzeichnis Ihrer Wahl (z.B. `/opt/bunkerweb/templates/`):

        ```bash
        sudo mkdir -p /opt/bunkerweb/templates
        sudo nano /opt/bunkerweb/templates/error.html
        # Fügen Sie Ihre benutzerdefinierte Fehlerseiten-Vorlage ein
        ```

    2. Konfigurieren Sie BunkerWeb durch Bearbeiten von `/etc/bunkerweb/variables.env`:

        ```conf
        # Benutzerdefinierte Fehlerseite für alle Dienste (oder pro Dienst mit Präfix)
        CUSTOM_ERROR_PAGE=/opt/bunkerweb/templates/error.html

        # Benutzerdefinierte Standard-Server-Seite (nur global)
        CUSTOM_DEFAULT_SERVER_PAGE=/opt/bunkerweb/templates/default.html

        # Benutzerdefinierte Captcha-Seite (pro Dienst oder global)
        CUSTOM_ANTIBOT_CAPTCHA_PAGE=/opt/bunkerweb/templates/captcha.html
        ```

    3. BunkerWeb neu laden:

        ```bash
        sudo systemctl reload bunkerweb
        ```

=== "Docker"

    Der **Scheduler** ist für das Lesen, Validieren und Cachen Ihrer benutzerdefinierten Vorlagen verantwortlich. Nur der Scheduler benötigt Zugriff auf die Vorlagendateien—BunkerWeb erhält die validierte Konfiguration automatisch.

    1. Erstellen Sie Ihre Vorlagendateien in einem lokalen Verzeichnis (z.B. `./templates/`) und setzen Sie die korrekten Berechtigungen:

        ```bash
        mkdir templates && \
        chown root:101 templates && \
        chmod 770 templates
        ```

        !!! info "Warum UID/GID 101?"
            Der Scheduler-Container läuft als **unprivilegierter Benutzer mit UID 101 und GID 101**. Das Verzeichnis muss für diesen Benutzer lesbar sein, damit der Scheduler auf Ihre Vorlagen zugreifen kann.

        Wenn der Ordner bereits existiert:

        ```bash
        chown -R root:101 templates && \
        chmod -R 770 templates
        ```

        Bei Verwendung von [Docker im Rootless-Modus](https://docs.docker.com/engine/security/rootless) oder [Podman](https://podman.io/) werden Container-UIDs/GIDs neu zugeordnet. Überprüfen Sie Ihre subuid/subgid-Bereiche:

        ```bash
        grep ^$(whoami): /etc/subuid && \
        grep ^$(whoami): /etc/subgid
        ```

        Wenn der Bereich beispielsweise bei **100000** beginnt, wird die effektive GID zu **100100** (100000 + 100):

        ```bash
        mkdir templates && \
        sudo chgrp 100100 templates && \
        chmod 770 templates
        ```

    2. Mounten Sie das Vorlagenverzeichnis zum **Scheduler** und konfigurieren Sie die Einstellungen am Scheduler (der Scheduler fungiert als Manager und verteilt die Konfiguration an BunkerWeb-Worker). Sie können die Vorlagen an jeden beliebigen Pfad im Container mounten:

        ```yaml
        services:
          bunkerweb:
            image: bunkerity/bunkerweb:1.6.8-rc3
            # ... andere Einstellungen (keine Umgebungsvariablen für Custom Pages hier benötigt)

          bw-scheduler:
            image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
            volumes:
              - ./templates:/custom_templates:ro
            environment:
              - CUSTOM_ERROR_PAGE=/custom_templates/error.html
              - CUSTOM_DEFAULT_SERVER_PAGE=/custom_templates/default.html
              - CUSTOM_ANTIBOT_CAPTCHA_PAGE=/custom_templates/captcha.html
              # ... andere Einstellungen
        ```

    !!! warning "Scheduler-Zugriff erforderlich"
        Wenn der Scheduler die Vorlagendateien nicht lesen kann (wegen fehlendem Mount oder falschen Berechtigungen), werden die Vorlagen stillschweigend ignoriert und die Standardseiten stattdessen verwendet. Überprüfen Sie die Scheduler-Logs auf Validierungsfehler.

=== "Kubernetes"

    Der **Scheduler** ist für das Lesen, Validieren und Cachen Ihrer benutzerdefinierten Vorlagen verantwortlich. Sie müssen die Vorlagen zum Scheduler-Pod mounten.

    1. Erstellen Sie eine ConfigMap mit Ihren Vorlagen:

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: bunkerweb-custom-templates
        data:
          error.html: |
            {-raw-}<!doctype html>
            <html lang="de">
              <head>
                <meta charset="utf-8" />
                <title>{{ title }}</title>
                {-raw-}
                <style nonce="{*nonce_style*}">
                  body { font-family: sans-serif; text-align: center; padding: 2rem; }
                  .error-code { font-size: 4rem; color: #dc3545; }
                </style>
                {-raw-}
              </head>
              <body>
                <p class="error-code">{{ error_code }}</p>
                <h1>{{ error_title }}</h1>
                <p>{{ error_text }}</p>
              </body>
            </html>
            {-raw-}
          captcha.html: |
            {-raw-}<!doctype html>
            <html lang="de">
              <head>
                <meta charset="utf-8" />
                <title>Sicherheitsprüfung</title>
                {-raw-}
                <style nonce="{*nonce_style*}">
                  body { font-family: sans-serif; text-align: center; padding: 2rem; }
                </style>
                {-raw-}
              </head>
              <body>
                <h1>Bitte bestätigen Sie, dass Sie ein Mensch sind</h1>
                {-raw-}
                <form method="POST" action="{*antibot_uri*}">
                  <img src="data:image/jpeg;base64,{*captcha*}" alt="Captcha" />
                  {-raw-}
                  <input type="text" name="captcha" placeholder="Code eingeben" required />
                  <button type="submit">Verifizieren</button>
                </form>
              </body>
            </html>
            {-raw-}
        ```

    2. Mounten Sie die Vorlagen-ConfigMap zum **Scheduler**-Pod und konfigurieren Sie die Einstellungen als Umgebungsvariablen:

        ```yaml
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: bunkerweb-scheduler
        spec:
          template:
            spec:
              containers:
                - name: bunkerweb-scheduler
                  image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
                  env:
                    - name: CUSTOM_ERROR_PAGE
                      value: "/custom_templates/error.html"
                    - name: CUSTOM_ANTIBOT_CAPTCHA_PAGE
                      value: "/custom_templates/captcha.html"
                    # ... andere Einstellungen
                  volumeMounts:
                    - name: custom-templates
                      mountPath: /custom_templates
                      readOnly: true
                  # ... andere Container-Einstellungen
              volumes:
                - name: custom-templates
                  configMap:
                    name: bunkerweb-custom-templates
              # ... andere Pod-Einstellungen
        ```

    !!! tip "Verwendung des BunkerWeb Ingress Controllers"
        Wenn Sie den BunkerWeb Ingress Controller verwenden, ist der Scheduler im Controller eingebettet. Mounten Sie die ConfigMap stattdessen zum Controller-Pod.

### Hinweise und Fehlerbehebung

- **Pfade müssen absolut sein** und mit einem Dateinamen enden; leere Werte deaktivieren die entsprechende benutzerdefinierte Seite und entfernen ihren Cache.
- **Wenn die Validierung fehlschlägt** (fehlerhaftes HTML oder unausgeglichene Lua-Tags), wird die Vorlage übersprungen und die Standardseite bleibt aktiv. Überprüfen Sie die Scheduler-Logs für Details.
- **Gecachte Dateien** befinden sich in `/var/cache/bunkerweb/custom_pages`; das Aktualisieren der Quelldatei reicht aus—der Job erkennt den neuen Hash und lädt NGINX automatisch neu.
- **CSP-Konformität**: Verwenden Sie immer die Variablen `nonce_script` und `nonce_style` für Inline-Skripte und Styles, um eine ordnungsgemäße Content Security Policy-Handhabung sicherzustellen.
- **Vorlagen testen**: Sie können Ihre Vorlagen lokal mit einer Lua-Template-Engine rendern, bevor Sie sie in BunkerWeb bereitstellen.

## OpenID Connect <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
  <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/0e4lcXTIIfs" title="OpenID Connect" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Das **OpenID Connect**-Plugin (PRO) fügt Single Sign-On (SSO) vor Ihrer Anwendung hinzu, indem es den standardisierten OAuth 2.0 / OIDC-Flow **Authorization Code** verwendet.

Es läuft innerhalb von BunkerWeb (NGINX/Lua) und erzwingt die Authentifizierung in der **access phase**, sodass nicht authentifizierte Anfragen gestoppt werden, *bevor* sie Ihren Upstream erreichen.

### Wie der Request-Flow funktioniert

Wenn ein Browser eine geschützte URL anfordert:

1. Wenn keine gültige Session vorhanden ist, leitet BunkerWeb den Benutzer zum Identity Provider (IdP) um.
2. Der IdP authentifiziert den Benutzer und leitet mit einem Authorization Code zurück zu BunkerWeb auf `OPENIDC_REDIRECT_URI` (Standard: `/callback`).
3. BunkerWeb tauscht den Code am Token-Endpoint des IdP gegen Tokens.
4. Tokens werden validiert (Issuer, Audience, Ablaufzeit, `iat` mit Toleranz sowie Signatur über JWKS).
5. Eine Session wird erstellt und der Browser wird zurück zur ursprünglichen URL umgeleitet.

```mermaid
sequenceDiagram
  participant B as Browser
  participant BW as BunkerWeb (OpenIDC)
  participant IdP as Identitätsanbieter
  participant Up as Upstream

  B->>BW: GET /protected
  alt Nicht authentifiziert
  BW-->>B: 302 Redirect zum Autorisierungs-Endpoint des IdP
  B->>IdP: Autorisierungsanfrage (Nonce/PKCE optional)
  IdP-->>B: 302 Redirect zu /callback?code=...
  B->>BW: GET /callback?code=...
  BW->>IdP: Token-Anfrage (Code Exchange)
  IdP-->>BW: ID Token + Access Token (+ Refresh Token)
  BW-->>B: 302 Redirect zurück zur ursprünglichen URL
  end
  B->>BW: GET /protected (authentifiziert)
  BW->>Up: Request weiterleiten (+ optionaler Identity-Header)
  Up-->>BW: Antwort
  BW-->>B: Antwort
```

!!! warning "Callback-URL muss mit der IdP-Client-Konfiguration übereinstimmen"
    Registrieren Sie die vollständige Callback-URL beim IdP (Schema + Host + Pfad). Zum Beispiel mit Standardwerten: `https://app.example.com/callback`.

### Einstellungen (erklärt)

!!! info "Erforderliche Einstellungen"
    Mindestens `OPENIDC_DISCOVERY` und `OPENIDC_CLIENT_ID` müssen gesetzt sein, damit das Plugin funktionieren kann.

#### Grundlegende Aktivierung

- `USE_OPENIDC` (Standard: `no`): OpenID Connect-Authentifizierung für die Site aktivieren oder deaktivieren.

#### Identity Provider (IdP) + Client-Registrierung

- `OPENIDC_DISCOVERY`: Discovery-URL (z. B. `https://idp.example.com/.well-known/openid-configuration`).
- `OPENIDC_CLIENT_ID`: OAuth 2.0 Client-ID, die beim IdP registriert ist.
- `OPENIDC_CLIENT_SECRET`: OAuth 2.0 Client-Secret (verwendet von `basic`, `post` und `secret_jwt`).

#### Callback / Redirect

- `OPENIDC_REDIRECT_URI` (Standard: `/callback`): Callback-Pfad, den der IdP nach erfolgreicher Authentifizierung aufruft (muss beim IdP registriert sein).

#### Scopes und Authorization-Parameter

- `OPENIDC_SCOPE` (Standard: `openid email profile`): durch Leerzeichen getrennte Liste der anzufordernden Scopes.
- `OPENIDC_AUTHORIZATION_PARAMS`: zusätzliche Authorization-Parameter als kommagetrennte `key=value` Paare.

#### Security-Härtung

- `OPENIDC_USE_NONCE` (Standard: `yes`): Nonce zu Authorization-Anfragen hinzufügen.
- `OPENIDC_USE_PKCE` (Standard: `no`): PKCE für den Authorization-Code-Flow aktivieren.
- `OPENIDC_IAT_SLACK` (Standard: `120`): erlaubte Uhrzeitabweichung (Sekunden) bei der Token-Validierung.
- `OPENIDC_ACCEPT_UNSUPPORTED_ALG` (Standard: `no`): Tokens mit nicht unterstützten Algorithmen akzeptieren (nicht empfohlen).
- `OPENIDC_FORCE_REAUTHORIZE` (Standard: `no`): bei jeder Anfrage Re-Authorization erzwingen (nur Debug).

#### Session-/Token-Lebenszyklus

- `OPENIDC_REFRESH_SESSION_INTERVAL`: Intervall in Sekunden, um die Session still zu erneuern (leer = deaktiviert).
- `OPENIDC_ACCESS_TOKEN_EXPIRES_IN` (Standard: `3600`): Standard-Lebensdauer des Access Tokens, wenn der IdP nichts liefert.
- `OPENIDC_RENEW_ACCESS_TOKEN_ON_EXPIRY` (Standard: `yes`): Access Token bei Ablauf via Refresh Token erneuern.

#### Token-Endpoint-Authentifizierungseinstellungen

- `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD` (Standard: `basic`): `basic`, `post`, `secret_jwt`, `private_key_jwt`.
- `OPENIDC_CLIENT_RSA_PRIVATE_KEY`: erforderlich bei `private_key_jwt`.
- `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID`: optionales `kid` für `private_key_jwt`.
- `OPENIDC_CLIENT_JWT_ASSERTION_EXPIRES_IN`: Lebensdauer der JWT-Assertion in Sekunden.

#### Logout-Verhalten

- `OPENIDC_LOGOUT_PATH` (Standard: `/logout`): lokaler Logout-Pfad, der von BunkerWeb verarbeitet wird.
- `OPENIDC_REVOKE_TOKENS_ON_LOGOUT` (Standard: `no`): Tokens beim IdP beim Logout widerrufen.
- `OPENIDC_REDIRECT_AFTER_LOGOUT_URI`: Redirect nach lokalem Logout (leer = IdP-Default).
- `OPENIDC_POST_LOGOUT_REDIRECT_URI`: Redirect nach abgeschlossenem IdP-Logout (falls unterstützt).

#### Konnektivität und TLS zum IdP

- `OPENIDC_TIMEOUT_CONNECT|SEND|READ` (Standard: jeweils `10000` ms): Timeouts für HTTP-Aufrufe zum IdP.
- `OPENIDC_SSL_VERIFY` (Standard: `yes`): TLS-Zertifikate des IdP prüfen.
- `OPENIDC_KEEPALIVE` (Standard: `yes`): Keepalive für IdP-Verbindungen.
- `OPENIDC_HTTP_PROXY` / `OPENIDC_HTTPS_PROXY`: Proxys für IdP-Aufrufe.

#### Weitergabe der Identität an Upstreams

- `OPENIDC_USER_HEADER` (Standard: `X-User`): Header zur Weitergabe der Identität an den Upstream (leer = deaktiviert).
- `OPENIDC_USER_HEADER_CLAIM` (Standard: `sub`): Claim, der für den User-Header extrahiert wird.
- `OPENIDC_DISPLAY_CLAIM` (Standard: `preferred_username`): Claim für Anzeige in Logs/Metriken.

#### Caching

- `OPENIDC_DISCOVERY_DICT_SIZE` (Standard: `1m`): Shared-Dict-Größe für Discovery-Cache.
- `OPENIDC_JWKS_DICT_SIZE` (Standard: `1m`): Shared-Dict-Größe für JWKS-Cache.

!!! tip "Redis Session Storage"
    Wenn `USE_REDIS=yes` global in BunkerWeb konfiguriert ist, speichert das OpenIDC-Plugin Sessions in Redis statt in Cookies (mit automatischem Fallback auf Cookies, falls Redis nicht verfügbar ist). Das ist der empfohlene Modus für Multi-Instance-/HA-Deployments.

### Discovery + JWKS-Caching

Das Plugin verwendet `OPENIDC_DISCOVERY` (die IdP `.well-known/openid-configuration` URL), um Endpoints zu entdecken, und lädt anschließend JWKS-Keys, um Token-Signaturen zu validieren.

Discovery- und JWKS-Daten werden in NGINX Shared Dictionaries gecacht. Wenn Sie viele Tenants/IdPs oder große Key-Sets haben, erhöhen Sie:

- `OPENIDC_DISCOVERY_DICT_SIZE` (global)
- `OPENIDC_JWKS_DICT_SIZE` (global)

### Sessions (Cookies vs Redis)

Standardmäßig werden Sessions als sichere Cookies gespeichert, die von der OpenID-Connect-Bibliothek verwaltet werden.

Wenn `USE_REDIS=yes` global aktiviert ist und Redis konfiguriert wurde, wechselt das Plugin automatisch zu **Redis-basierten Sessions** (mit automatischem Fallback auf Cookie-Sessions, wenn Redis vorübergehend nicht verfügbar ist). Das ist für Load Balancing / HA empfehlenswert und vermeidet Cookie-Größenlimits bei großen Token-Payloads.

### Weitergabe der Benutzeridentität an den Upstream

Wenn `OPENIDC_USER_HEADER` gesetzt ist (Standard: `X-User`), injiziert das Plugin einen Header-Wert aus einem Claim (Standard: `OPENIDC_USER_HEADER_CLAIM=sub`).

Wichtiges Security-Verhalten:

- Das Plugin **löscht eingehende** Header mit dem Namen `OPENIDC_USER_HEADER`, um Spoofing zu verhindern.
- Fehlt der konfigurierte Claim, wird der Header nicht gesetzt.
- Setzen Sie `OPENIDC_USER_HEADER` auf einen leeren Wert, um die Identitätsweitergabe zu deaktivieren.

!!! tip "Claim auswählen"
    Bevorzugen Sie stabile Identifier, die in Tokens vorhanden sind (z. B. `sub`, `email`, `preferred_username`). Claims werden zuerst aus dem ID Token gelesen, danach aus userinfo (falls vorhanden).

### Logout

Logout-Anfragen werden auf `OPENIDC_LOGOUT_PATH` (Standard: `/logout`) verarbeitet.

- Um Tokens beim IdP beim Logout zu widerrufen, setzen Sie `OPENIDC_REVOKE_TOKENS_ON_LOGOUT=yes`.
- Verwenden Sie `OPENIDC_REDIRECT_AFTER_LOGOUT_URI` und `OPENIDC_POST_LOGOUT_REDIRECT_URI`, um Redirects nach dem Logout zu steuern.

### Token-Endpoint-Authentifizierung

Die meisten IdPs funktionieren mit dem Standard `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD=basic` (Client Secret via HTTP Basic Auth). Zusätzlich werden unterstützt:

- `post`
- `secret_jwt`
- `private_key_jwt` (erfordert `OPENIDC_CLIENT_RSA_PRIVATE_KEY`, optional `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID`)

### Minimale Konfigurationsbeispiele

Minimale erforderliche Einstellungen pro geschütztem Service:

- `USE_OPENIDC=yes`
- `OPENIDC_DISCOVERY=...`
- `OPENIDC_CLIENT_ID=...`
- `OPENIDC_CLIENT_SECRET=...` (oder JWT-Key-Konfiguration für `private_key_jwt`)

Häufige Hardening-/Tuning-Optionen:

- `OPENIDC_USE_NONCE=yes` (Standard)
- `OPENIDC_USE_PKCE=yes`
- `OPENIDC_IAT_SLACK=...` bei Clock Skew
- `OPENIDC_TIMEOUT_CONNECT|SEND|READ` passend zur IdP-Latenz
- `OPENIDC_SSL_VERIFY=yes` (Standard)

### Fehlerbehebung

- **403 mit "Authentication failed"**: meist falsche Discovery-URL, Callback-URL-Mismatch in der IdP-Client-Konfiguration oder IdP nicht erreichbar.
- **Clock skew / "token not yet valid"**: NTP aktivieren; `OPENIDC_IAT_SLACK` bei Bedarf anpassen.
- **Kein User-Header gesetzt**: prüfen, ob der Claim aus `OPENIDC_USER_HEADER_CLAIM` im ID Token/userinfo vorhanden ist.
- **Multi-Instance-Deployments**: `USE_REDIS=yes` aktivieren und `REDIS_HOST` (oder Sentinel) konfigurieren, damit Sessions geteilt werden.
