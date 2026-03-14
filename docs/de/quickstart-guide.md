# Schnellstart-Anleitung

!!! info "Voraussetzungen"

    Wir gehen davon aus, dass Sie bereits mit den [Grundkonzepten](concepts.md) vertraut sind und die [Integrationsanweisungen](integrations.md) für Ihre Umgebung befolgt haben.

    Diese Schnellstart-Anleitung setzt voraus, dass BunkerWeb aus dem Internet erreichbar ist und dass Sie mindestens zwei Domains konfiguriert haben: eine für die Web-UI und eine für Ihren Webdienst.

    **Systemanforderungen**

    Die empfohlenen Mindestspezifikationen für BunkerWeb sind eine Maschine mit 2 (v)CPUs und 8 GB RAM. Bitte beachten Sie, dass dies für Testumgebungen oder Setups mit sehr wenigen Diensten ausreichend sein sollte.

    Für Produktionsumgebungen mit vielen zu schützenden Diensten empfehlen wir mindestens 4 (v)CPUs und 16 GB RAM. Die Ressourcen sollten an Ihren Anwendungsfall, den Netzwerkverkehr und potenzielle DDoS-Angriffe, denen Sie ausgesetzt sein könnten, angepasst werden.

    Es wird dringend empfohlen, das globale Laden von CRS-Regeln zu aktivieren (indem der Parameter `USE_MODSECURITY_GLOBAL_CRS` auf `yes` gesetzt wird), wenn Sie in Umgebungen mit begrenztem RAM oder in der Produktion mit vielen Diensten arbeiten. Weitere Details finden Sie im Abschnitt [Erweiterte Nutzungen](advanced.md#running-many-services-in-production) der Dokumentation.

Diese Schnellstart-Anleitung hilft Ihnen, BunkerWeb schnell zu installieren und einen Webdienst über die Web-Benutzeroberfläche zu sichern.

Der Schutz bestehender Webanwendungen, die bereits über das HTTP(S)-Protokoll erreichbar sind, ist das Hauptziel von BunkerWeb: Es fungiert als klassischer [Reverse-Proxy](https://de.wikipedia.org/wiki/Reverse_Proxy) mit zusätzlichen Sicherheitsfunktionen.

Im [Beispielordner](https://github.com/bunkerity/bunkerweb/tree/v1.6.9/examples) des Repositorys finden Sie Beispiele aus der Praxis.

## Grundlegende Einrichtung

=== "All-in-one"

    Um den All-in-One-Container bereitzustellen, führen Sie den folgenden Befehl aus:

    ```shell
    docker run -d \
      --name bunkerweb-aio \
      -v bw-storage:/data \
      -p 80:8080/tcp \
      -p 443:8443/tcp \
      -p 443:8443/udp \
      bunkerity/bunkerweb-all-in-one:1.6.9
    ```

    Standardmäßig stellt der Container Folgendes bereit:

    * 8080/tcp für HTTP
    * 8443/tcp für HTTPS
    * 8443/udp für QUIC
    * 7000/tcp für den Zugriff auf die Web-UI ohne BunkerWeb davor (nicht für die Produktion empfohlen)

    Das All-In-One-Image enthält mehrere integrierte Dienste, die über Umgebungsvariablen gesteuert werden können. Weitere Details finden Sie im Abschnitt [All-In-One (AIO) Image](integrations.md#all-in-one-aio-image) der Integrationsseite.

=== "Linux"

    Verwenden Sie das Easy Install-Skript, um BunkerWeb auf unterstützten Linux-Distributionen einzurichten. Es installiert und konfiguriert NGINX automatisch, fügt das BunkerWeb-Repository hinzu und richtet die erforderlichen Dienste ein.

    ```bash
    # Laden Sie das Skript und seine Prüfsumme herunter
    curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.9/install-bunkerweb.sh
    curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.9/install-bunkerweb.sh.sha256

    # Überprüfen Sie die Prüfsumme
    sha256sum -c install-bunkerweb.sh.sha256

    # Wenn die Überprüfung erfolgreich ist, führen Sie das Skript aus
    chmod +x install-bunkerweb.sh
    sudo ./install-bunkerweb.sh
    ```

    !!! danger "Sicherheitshinweis"
        Überprüfen Sie immer die Integrität des Skripts mit der bereitgestellten Prüfsumme, bevor Sie es ausführen.

    #### Highlights des Easy-Install-Skripts

    - Erkennt Ihre Linux-Distribution und CPU-Architektur im Voraus und warnt, wenn Sie sich außerhalb der unterstützten Matrix befinden, bevor Änderungen vorgenommen werden.
    - Der interaktive Ablauf lässt Sie das Installationsprofil auswählen (Full Stack, Manager, Worker usw.); im Manager-Modus wird die API immer auf `0.0.0.0` gebunden, der Setup-Assistent deaktiviert und nach der freizuschaltenden IP gefragt (in nicht-interaktiven Läufen per `--manager-ip` übergeben), während der Worker-Modus die Manager-IP(s) für seine Whitelist erzwingt.
    - Manager-Installationen können weiterhin entscheiden, ob der Web-UI-Dienst gestartet werden soll, obwohl der Assistent deaktiviert bleibt.
    - Die Zusammenfassung zeigt an, ob der FastAPI-Dienst gestartet wird, sodass Sie ihn bewusst mit `--api` / `--no-api` aktivieren oder deaktivieren können.
    - CrowdSec-Optionen stehen nur für Full-Stack-Installationen zur Verfügung; Manager-/Worker-Modi überspringen sie automatisch, damit sich der Ablauf auf die Fernverwaltung konzentriert.

    Weitere Installationsmethoden (Paketmanager, Installationstypen, nicht-interaktive Flags, CrowdSec-Integration usw.) finden Sie unter [Linux-Integration](integrations.md#linux).

=== "Docker"

    Hier ist die vollständige Docker-Compose-Datei, die Sie verwenden können; bitte beachten Sie, dass wir später den Webdienst mit dem `bw-services`-Netzwerk verbinden werden:

    ```yaml
    x-bw-env: &bw-env
      # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für beide Dienste zu vermeiden
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Stellen Sie sicher, dass Sie den richtigen IP-Bereich festlegen, damit der Scheduler die Konfiguration an die Instanz senden kann
      # Optional: Legen Sie einen API-Token fest und spiegeln Sie ihn in beiden Containern
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen

    services:
      bunkerweb:
        # Dies ist der Name, der zur Identifizierung der Instanz im Scheduler verwendet wird
        image: bunkerity/bunkerweb:1.6.9
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Für QUIC / HTTP3-Unterstützung
        environment:
          <<: *bw-env # Wir verwenden den Anker, um die Wiederholung derselben Einstellungen für alle Dienste zu vermeiden
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.9
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Stellen Sie sicher, dass Sie den richtigen Instanznamen festlegen
          SERVER_NAME: ""
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # Ändern Sie dies bei Bedarf
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # Dies wird verwendet, um den Cache und andere Daten wie die Backups zu persistieren
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.9
        environment:
          <<: *bw-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

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

      redis: # Redis-Dienst für die Persistenz von Berichten/Sperren/Statistiken
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

    volumes:
      bw-data:
      bw-storage:
      redis-data:

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

=== "Docker Autoconf"

    Hier ist die vollständige Docker-Compose-Datei, die Sie verwenden können; bitte beachten Sie, dass wir später den Webdienst mit dem `bw-services`-Netzwerk verbinden werden:

    ```yaml
    x-ui-env: &bw-ui-env
      # Wir verankern die Umgebungsvariablen, um Duplikate zu vermeiden
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.9
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Für QUIC / HTTP3-Unterstützung
        labels:
          - "bunkerweb.INSTANCE=yes" # Wir setzen das Instanz-Label, damit die Autoconf die Instanz erkennen kann
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.9
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # Ändern Sie dies bei Bedarf
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # Dies wird verwendet, um den Cache und andere Daten wie die Backups zu persistieren
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.9
        depends_on:
          - bw-docker
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.9
        environment:
          <<: *bw-ui-env
          TOTP_ENCRYPTION_KEYS: "mysecret" # Denken Sie daran, einen stärkeren geheimen Schlüssel festzulegen (siehe Abschnitt Voraussetzungen)
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

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

      redis: # Redis-Dienst für die Persistenz von Berichten/Sperren/Statistiken
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

    volumes:
      bw-data:
      bw-storage:
      redis-data:

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

=== "Kubernetes"

    Die empfohlene Methode zur Installation von Kubernetes ist die Verwendung des Helm-Charts, das unter `https://repo.bunkerweb.io/charts` verfügbar ist:

    ```shell
    helm repo add bunkerweb https://repo.bunkerweb.io/charts
    ```

    Sie können dann das `bunkerweb`-Helm-Chart aus diesem Repository verwenden:

    ```shell
    helm install mybw bunkerweb/bunkerweb --namespace bunkerweb --create-namespace
    ```

    Nach der Installation können Sie die IP-Adresse des `LoadBalancer` abrufen, um Ihre Domains einzurichten:

    ```shell
    kubectl -n bunkerweb get svc mybw-external -o=jsonpath='{.status.loadBalancer.ingress[0].ip}'
    ```

=== "Swarm"

    !!! warning "Veraltet"
        Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](integrations.md#kubernetes).

        **Weitere Informationen finden Sie in der [Swarm-Integrationsdokumentation](integrations.md#swarm).**

    Hier ist die vollständige Docker-Compose-Stack-Datei, die Sie verwenden können; bitte beachten Sie, dass wir später den Webdienst mit dem `bw-services`-Netzwerk verbinden werden:

    ```yaml
    x-ui-env: &bw-ui-env
      # Wir verankern die Umgebungsvariablen, um Duplikate zu vermeiden
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.9
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
            protocol: udp # Für QUIC / HTTP3-Unterstützung
        environment:
          SWARM_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
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
            - "bunkerweb.INSTANCE=yes"

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.9
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "bw-redis"
          UI_HOST: "http://bw-ui:7000" # Ändern Sie dies bei Bedarf
        volumes:
          - bw-storage:/data # Dies wird verwendet, um den Cache und andere Daten wie die Backups zu persistieren
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.9
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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
          CONFIGS: "1"
          CONTAINERS: "1"
          SERVICES: "1"
          SWARM: "1"
          TASKS: "1"
          LOG_LEVEL: "warning"
        networks:
          - bw-docker
        deploy:
          placement:
            constraints:
              - "node.role == manager"

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.9
        environment:
          <<: *bw-ui-env
          TOTP_ENCRYPTION_KEYS: "mysecret" # Denken Sie daran, einen stärkeren geheimen Schlüssel festzulegen (siehe Abschnitt Voraussetzungen)
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

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

      bw-redis:
        image: redis:8-alpine
        networks:
          - bw-universe

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

## Den Einrichtungsassistenten abschließen {#complete-the-setup-wizard}

!!! tip "Zugriff auf den Einrichtungsassistenten"

    Sie können auf den Einrichtungsassistenten zugreifen, indem Sie die URI `https://ihre-fqdn-oder-ip-adresse/setup` Ihres Servers aufrufen.

### Ein Administratorkonto erstellen

Sie sollten eine Einrichtungsseite wie diese sehen:
<figure markdown>
  ![Setup Wizard Landing Page](assets/img/ui-wizard-step1.png){ align=center }
  <figcaption>Setup Wizard Landing Page</figcaption>
</figure>

Sobald Sie auf der Einrichtungsseite sind, können Sie den **Administrator-Benutzernamen, die E-Mail-Adresse und das Passwort** eingeben und auf die Schaltfläche "Weiter" klicken.

### Den Reverse-Proxy, HTTPS und andere erweiterte Einstellungen konfigurieren

=== "Grundlegende Einrichtung"

    Im nächsten Schritt werden Sie aufgefordert, den **Servernamen** (Domain/FQDN) einzugeben, den die Web-UI verwenden wird.

    Sie können auch [Let's Encrypt](features.md#lets-encrypt) aktivieren.

    <figure markdown>
      ![Setup Wizard Schritt 2](assets/img/ui-wizard-step2.png){ align=center }
      <figcaption>Setup Wizard Schritt 2</figcaption>
    </figure>

=== "Erweiterte Einrichtung"

    Im nächsten Schritt werden Sie aufgefordert, den **Servernamen** (Domain/FQDN) einzugeben, den die Web-UI verwenden wird.

    Sie können auch [Let's Encrypt](features.md#lets-encrypt) aktivieren.

    Wenn Sie den Abschnitt `Erweiterte Einstellungen` erweitern, können Sie auch die folgenden Optionen konfigurieren:

    * **Reverse-Proxy**: Passen Sie die Reverse-Proxy-Einstellungen für Ihre Administratoroberfläche an (z. B. wenn Sie einen Pfad verwenden möchten).
    * [**Echte IP**](features.md#real-ip): Konfigurieren Sie die Einstellungen für die echte IP, um die IP-Adresse des Clients korrekt zu identifizieren (z. B. wenn Sie sich hinter einem Load Balancer oder einem CDN befinden).
    * [**Benutzerdefiniertes Zertifikat**](features.md#custom-ssl-certificate): Laden Sie ein benutzerdefiniertes TLS-Zertifikat hoch, wenn Sie Let's Encrypt nicht verwenden möchten.

    <figure markdown>
      ![Setup Wizard Schritt 2](assets/img/ui-wizard-step2-advanced.png){ align=center }
      <figcaption>Setup Wizard Schritt 2 (erweitert)</figcaption>
    </figure>

### PRO-Aktivierung

Wenn Sie eine PRO-Lizenz haben, können Sie sie aktivieren, indem Sie Ihren Lizenzschlüssel im Abschnitt `Upgrade auf PRO` eingeben. Dadurch werden die PRO-Funktionen von BunkerWeb aktiviert.

<figure markdown>
  ![Setup Wizard PRO-Schritt](assets/img/ui-wizard-step3.png){ align=center }
  <figcaption>Setup Wizard PRO-Schritt</figcaption>
</figure>

### Übersicht über Ihre Einstellungen

Der letzte Schritt gibt Ihnen einen Überblick über die von Ihnen eingegebenen Einstellungen. Sie können auf die Schaltfläche "Einrichten" klicken, um die Einrichtung abzuschließen.

<figure markdown>
  ![Setup Wizard letzter Schritt](assets/img/ui-wizard-step4.png){ align=center }
  <figcaption>Setup Wizard letzter Schritt</figcaption>
</figure>

## Zugriff auf die Weboberfläche

Sie können nun auf die Weboberfläche zugreifen, indem Sie die im vorherigen Schritt konfigurierte Domain und die URI aufrufen, falls Sie sie geändert haben (Standard ist `https://ihre-domain/`).

<figure markdown>
  ![Weboberfläche Anmeldeseite](assets/img/ui-login.png){ align=center }
  <figcaption>Weboberfläche Anmeldeseite</figcaption>
</figure>

Sie können sich nun mit dem während des Einrichtungsassistenten erstellten Administratorkonto anmelden.

<figure markdown>
  ![Weboberfläche Startseite](assets/img/ui-home.png){ align=center }
  <figcaption>Weboberfläche Startseite</figcaption>
</figure>

## Erstellen eines neuen Dienstes

=== "Web-UI"

    Sie können einen neuen Dienst erstellen, indem Sie zum Abschnitt `Dienste` der Weboberfläche navigieren und auf die Schaltfläche `➕ Neuen Dienst erstellen` klicken.

    Es gibt mehrere Möglichkeiten, einen Dienst über die Weboberfläche zu erstellen:

    * Der **Einfache Modus** führt Sie durch den Prozess der Erstellung eines neuen Dienstes.
    * Der **Erweiterte Modus** ermöglicht es Ihnen, den Dienst mit mehr Optionen zu konfigurieren.
    * Der **Rohmodus** ermöglicht es Ihnen, die Konfiguration direkt einzugeben, als ob Sie die Datei `variables.env` bearbeiten würden.

    !!! tip "Entwurfsdienst"

        Sie können einen Entwurfsdienst erstellen, um Ihren Fortschritt zu speichern und später darauf zurückzukommen. Klicken Sie einfach auf die Schaltfläche `🌐 Online`, um den Dienst in den Entwurfsmodus zu schalten.

    === "Einfacher Modus"

        In diesem Modus können Sie aus den verfügbaren Vorlagen wählen und die erforderlichen Felder ausfüllen.

        <figure markdown>
          ![Weboberfläche Dienst erstellen einfach](assets/img/ui-create-service-easy.png){ align=center }
          <figcaption>Weboberfläche Dienst erstellen einfach</figcaption>
        </figure>

        * Sobald Sie die Vorlage ausgewählt haben, können Sie die erforderlichen Felder ausfüllen und den Anweisungen folgen, um den Dienst zu erstellen.
        * Wenn Sie mit der Konfiguration des Dienstes fertig sind, können Sie auf die Schaltfläche `💾 Speichern` klicken, um die Konfiguration zu speichern.

    === "Erweiterter Modus"

        In diesem Modus können Sie den Dienst mit mehr Optionen konfigurieren und dabei alle verfügbaren Einstellungen aus allen verschiedenen Plugins sehen.

        <figure markdown>
          ![Weboberfläche Dienst erstellen erweitert](assets/img/ui-create-service-advanced.png){ align=center }
          <figcaption>Weboberfläche Dienst erstellen erweitert</figcaption>
        </figure>

        * Um zwischen den verschiedenen Plugins zu navigieren, können Sie das Navigationsmenü auf der linken Seite der Seite verwenden.
        * Jede Einstellung enthält eine kleine Information, die Ihnen hilft zu verstehen, was sie bewirkt.
        * Wenn Sie mit der Konfiguration des Dienstes fertig sind, können Sie auf die Schaltfläche `💾 Speichern` klicken, um die Konfiguration zu speichern.

    === "Rohmodus"

        In diesem Modus können Sie die Konfiguration direkt eingeben, als ob Sie die Datei `variables.env` bearbeiten würden.

        <figure markdown>
          ![Weboberfläche Dienst erstellen ROH](assets/img/ui-create-service-raw.png){ align=center }
          <figcaption>Weboberfläche Dienst erstellen ROH</figcaption>
        </figure>

        * Wenn Sie mit der Konfiguration des Dienstes fertig sind, können Sie auf die Schaltfläche `💾 Speichern` klicken, um die Konfiguration zu speichern.

    🚀 Sobald Sie die Konfiguration gespeichert haben, sollten Sie Ihren neuen Dienst in der Liste der Dienste sehen.

    <figure markdown>
      ![Weboberfläche Diensteseite](assets/img/ui-services.png){ align=center }
      <figcaption>Weboberfläche Diensteseite</figcaption>
    </figure>

    Wenn Sie den Dienst bearbeiten möchten, können Sie auf den Dienstnamen oder die Schaltfläche `📝 Bearbeiten` klicken.

=== "All-in-one"

    Bei Verwendung des All-in-One-Images werden neue Dienste durch Hinzufügen von Umgebungsvariablen zum `docker run`-Befehl für den `bunkerweb-aio`-Container konfiguriert. Wenn der Container bereits läuft, müssen Sie ihn stoppen und entfernen und dann mit den aktualisierten Umgebungsvariablen erneut ausführen.

    Angenommen, Sie möchten eine Anwendung `myapp` schützen (die in einem anderen Container läuft und von BunkerWeb als `http://myapp:8080` erreichbar ist) und sie unter `www.example.com` verfügbar machen. Sie würden die folgenden Umgebungsvariablen in Ihrem `docker run`-Befehl hinzufügen oder ändern:

    ```shell
    # Zuerst den vorhandenen Container stoppen und entfernen, falls er läuft:
    # docker stop bunkerweb-aio
    # docker rm bunkerweb-aio

    # Dann den bunkerweb-aio-Container mit zusätzlichen/aktualisierten Umgebungsvariablen erneut ausführen:
    docker run -d \
      --name bunkerweb-aio \
      -v bw-storage:/data \
      -p 80:8080/tcp \
      -p 443:8443/tcp \
      -p 443:8443/udp \
      # --- Fügen Sie diese Umgebungsvariablen für Ihren neuen Dienst hinzu/ändern Sie sie ---
      -e MULTISITE=yes \
      -e SERVER_NAME="www.example.com" \
      -e "www.example.com_USE_REVERSE_PROXY=yes" \
      -e "www.example.com_REVERSE_PROXY_HOST=http://myapp:8080" \
      -e "www.example.com_REVERSE_PROXY_URL=/" \
      # --- Fügen Sie alle anderen vorhandenen Umgebungsvariablen für UI, Redis, CrowdSec usw. hinzu ---
      bunkerity/bunkerweb-all-in-one:1.6.9
    ```

    Ihr Anwendungscontainer (`myapp`) und der `bunkerweb-aio`-Container müssen sich im selben Docker-Netzwerk befinden, damit BunkerWeb ihn über den Hostnamen `myapp` erreichen kann.

    **Beispiel für die Netzwerkeinrichtung:**
    ```shell
    # 1. Erstellen Sie ein benutzerdefiniertes Docker-Netzwerk (falls noch nicht geschehen):
    docker network create my-app-network

    # 2. Führen Sie Ihren Anwendungscontainer in diesem Netzwerk aus:
    docker run -d --name myapp --network my-app-network your-app-image

    # 3. Fügen Sie --network my-app-network zum docker run-Befehl von bunkerweb-aio hinzu:
    docker run -d \
      --name bunkerweb-aio \
      --network my-app-network \
      -v bw-storage:/data \
      -p 80:8080/tcp \
      -p 443:8443/tcp \
      -p 443:8443/udp \
    #   ... (alle anderen relevanten Umgebungsvariablen wie im Hauptbeispiel oben gezeigt) ...
      bunkerity/bunkerweb-all-in-one:1.6.9
    ```

    Stellen Sie sicher, dass Sie `myapp` durch den tatsächlichen Namen oder die IP Ihres Anwendungscontainers und `http://myapp:8080` durch dessen korrekte Adresse und Port ersetzen.

=== "Linux variables.env-Datei"

    Wir gehen davon aus, dass Sie die [Grundlegende Einrichtung](#__tabbed_1_2) befolgt haben und dass die Linux-Integration auf Ihrer Maschine läuft.

    Sie können einen neuen Dienst erstellen, indem Sie die Datei `variables.env` im Verzeichnis `/etc/bunkerweb/` bearbeiten.

    ```shell
    nano /etc/bunkerweb/variables.env
    ```

    Sie können dann die folgende Konfiguration hinzufügen:

    ```shell
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/
    www.example.com_REVERSE_PROXY_HOST=http://myapp:8080
    ```

    Sie können dann den `bunkerweb-scheduler`-Dienst neu laden, um die Änderungen zu übernehmen.

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

=== "Docker"

    Wir gehen davon aus, dass Sie die [Grundlegende Einrichtung](#__tabbed_1_3) befolgt haben und dass die Docker-Integration auf Ihrer Maschine läuft.

    Sie müssen ein Netzwerk namens `bw-services` haben, damit Sie Ihre bestehende Anwendung verbinden und BunkerWeb konfigurieren können:

    ```yaml
    services:
      myapp:
    	  image: bunkerity/bunkerweb-hello:v1.0
    	  networks:
    	    - bw-services

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

    Danach können Sie den Dienst manuell in der im vorherigen Schritt erstellten Docker-Compose-Datei hinzufügen:

    ```yaml
    ...

    services:
      ...
      bw-scheduler:
        ...
        environment:
          ...
          SERVER_NAME: "www.example.com" # Bei Verwendung der Docker-Integration können Sie die Konfiguration direkt im Scheduler festlegen. Stellen Sie sicher, dass Sie den richtigen Domainnamen festlegen
          MULTISITE: "yes" # Aktivieren Sie den Multisite-Modus, damit Sie mehrere Dienste hinzufügen können
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/"
          www.example.com_REVERSE_PROXY_HOST: "http://myapp:8080"
          ...
    ```

    Sie können dann den `bw-scheduler`-Dienst neu starten, um die Änderungen zu übernehmen.

    ```shell
    docker compose down bw-scheduler && docker compose up -d bw-scheduler
    ```

=== "Docker Autoconf-Labels"

    Wir gehen davon aus, dass Sie die [Grundlegende Einrichtung](#__tabbed_1_4) befolgt haben und dass die Docker-Autoconf-Integration auf Ihrer Maschine läuft.

    Sie müssen ein Netzwerk namens `bw-services` haben, damit Sie Ihre bestehende Anwendung verbinden und BunkerWeb mit Labels konfigurieren können:

    ```yaml
    services:
      myapp:
    	  image: bunkerity/bunkerweb-hello:v1.0
    	  networks:
    	    - bw-services
    	  labels:
    	    - "bunkerweb.SERVER_NAME=www.example.com"
    	    - "bunkerweb.USE_REVERSE_PROXY=yes"
    	    - "bunkerweb.REVERSE_PROXY_URL=/"
    	    - "bunkerweb.REVERSE_PROXY_HOST=http://myapp:8080"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

    Dadurch wird automatisch ein neuer Dienst mit den bereitgestellten Labels als Konfiguration erstellt.

=== "Kubernetes-Annotationen"

    Wir gehen davon aus, dass Sie die [Grundlegende Einrichtung](#__tabbed_1_5) befolgt haben und dass der Kubernetes-Stack auf Ihrem Cluster läuft.

    Nehmen wir an, Sie haben ein typisches Deployment mit einem Service, um auf die Webanwendung aus dem Cluster zuzugreifen:

    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app
      labels:
    	app: app
    spec:
      replicas: 1
      selector:
    	matchLabels:
    	  app: app
      template:
    	metadata:
    	  labels:
    		app: app
    	spec:
    	  containers:
    	  - name: app
    		image: bunkerity/bunkerweb-hello:v1.0
    		ports:
    		- containerPort: 8080
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app
    spec:
      selector:
    	app: app
      ports:
    	- protocol: TCP
    	  port: 80
    	  targetPort: 8080
    ```

    Hier ist die entsprechende Ingress-Definition, um die Webanwendung bereitzustellen und zu schützen:

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      annotations:
        bunkerweb.io/DUMMY_SETTING: "value"
    spec:
      rules:
        - host: www.example.com
          http:
            paths:
              - path: /
                pathType: Prefix
                backend:
                  service:
                  name: svc-app
                  port:
                    number: 80
    ```

=== "Swarm-Labels"

    !!! warning "Veraltet"
        Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](integrations.md#kubernetes).

        **Weitere Informationen finden Sie in der [Swarm-Integrationsdokumentation](integrations.md#swarm).**

    Wir gehen davon aus, dass Sie die [Grundlegende Einrichtung](#__tabbed_1_5) befolgt haben und dass der Swarm-Stack auf Ihrem Cluster läuft und mit einem Netzwerk namens `bw-services` verbunden ist, sodass Sie Ihre bestehende Anwendung verbinden und BunkerWeb mit Labels konfigurieren können:

    ```yaml
    services:
      myapp:
        image: bunkerity/bunkerweb-hello:v1.0
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/"
          - "bunkerweb.REVERSE_PROXY_HOST=http://myapp:8080"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

## Weiterführende Informationen

Herzlichen Glückwunsch! Sie haben gerade BunkerWeb installiert und Ihren ersten Webdienst gesichert. Bitte beachten Sie, dass BunkerWeb viel mehr bietet, sowohl in Bezug auf die Sicherheit als auch in Bezug auf die Integration mit anderen Systemen und Lösungen. Hier ist eine Liste von Ressourcen und Aktionen, die Ihnen helfen können, Ihr Wissen über die Lösung weiter zu vertiefen:

- Treten Sie der Bunker-Community bei: [Discord](https://discord.com/invite/fTf46FmtyD), [LinkedIn](https://www.linkedin.com/company/bunkerity/), [GitHub](https://github.com/bunkerity), [X (ehemals Twitter)](https://x.com/bunkerity)
- Schauen Sie sich den [offiziellen Blog](https://www.bunkerweb.io/blog?utm_campaign=self&utm_source=doc) an
- Erkunden Sie [fortgeschrittene Anwendungsfälle](advanced.md) in der Dokumentation
- [Nehmen Sie Kontakt mit uns auf](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc), um die Bedürfnisse Ihrer Organisation zu besprechen
