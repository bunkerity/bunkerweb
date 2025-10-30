# Fortgeschrittene Nutzungen

Viele Beispiele für reale Anwendungsfälle sind im Ordner [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc1/examples) des GitHub-Repositorys verfügbar.

Wir stellen auch zahlreiche Boilerplates zur Verfügung, wie z. B. YAML-Dateien für verschiedene Integrationen und Datenbanktypen. Diese sind im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc1/misc/integrations) verfügbar.

Dieser Abschnitt konzentriert sich nur auf fortgeschrittene Nutzungen und Sicherheits-Tuning. Informationen zu allen verfügbaren Einstellungen finden Sie im [Features-Abschnitt](features.md) der Dokumentation.

## Anwendungsfälle

!!! tip "Testen"
    Um schnelle Tests durchzuführen, wenn der Multisite-Modus aktiviert ist (und wenn Sie nicht die richtigen DNS-Einträge für die Domains eingerichtet haben), können Sie `curl` mit dem HTTP-Host-Header Ihrer Wahl verwenden:
    ```shell
    curl -H "Host: app1.example.com" http://ip-oder-fqdn-des-servers
    ```

    Wenn Sie HTTPS verwenden, müssen Sie mit SNI spielen:
    ```shell
    curl -H "Host: app1.example.com" --resolve example.com:443:ip-des-servers https://example.com
    ```

### Hinter einem Load Balancer oder Reverse Proxy

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

        Navigieren Sie zur Seite **Globale Konfiguration**, wählen Sie das Plugin **Real IP** und füllen Sie die folgenden Einstellungen aus:

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
            bunkerity/bunkerweb-all-in-one:1.6.6-rc1
        ```

        Bitte beachten Sie, dass Sie, wenn Ihr Container bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen aktualisiert werden.

    === "Docker"

        Sie müssen die Einstellungen zu den Umgebungsvariablen sowohl des BunkerWeb- als auch des Scheduler-Containers hinzufügen:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.6-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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
          image: bunkerity/bunkerweb:1.6.6-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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
          image: bunkerity/bunkerweb:1.6.6-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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

        Navigieren Sie zur Seite **Globale Konfiguration**, wählen Sie das Plugin **Real IP** und füllen Sie die folgenden Einstellungen aus:

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
            bunkerity/bunkerweb-all-in-one:1.6.6-rc1
        ```

        Bitte beachten Sie, dass Sie, wenn Ihr Container bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen aktualisiert werden.

    === "Docker"

        Sie müssen die Einstellungen zu den Umgebungsvariablen sowohl des BunkerWeb- als auch des Scheduler-Containers hinzufügen:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.6-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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
          image: bunkerity/bunkerweb:1.6.6-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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
          image: bunkerity/bunkerweb:1.6.6-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Bitte beachten Sie, dass Sie, wenn Ihr Dienst bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen aktualisiert werden.

### Verwendung benutzerdefinierter DNS-Auflösungsmechanismen

BunkerWebs NGINX-Konfiguration kann angepasst werden, um je nach Ihren Bedürfnissen unterschiedliche DNS-Resolver zu verwenden. Dies kann in verschiedenen Szenarien besonders nützlich sein:

1.  Um Einträge in Ihrer lokalen `/etc/hosts`-Datei zu berücksichtigen
2.  Wenn Sie für bestimmte Domains benutzerdefinierte DNS-Server verwenden müssen
3.  Zur Integration mit lokalen DNS-Caching-Lösungen

#### Verwendung von systemd-resolved

Viele moderne Linux-Systeme verwenden `systemd-resolved` für die DNS-Auflösung. Wenn Sie möchten, dass BunkerWeb den Inhalt Ihrer `/etc/hosts`-Datei respektiert und den DNS-Auflösungsmechanismus des Systems verwendet, können Sie es so konfigurieren, dass es den lokalen systemd-resolved DNS-Dienst verwendet.

Um zu überprüfen, ob systemd-resolved auf Ihrem System läuft, können Sie Folgendes verwenden:

```bash
systemctl status systemd-resolved
```

Um systemd-resolved als Ihren DNS-Resolver in BunkerWeb zu aktivieren, setzen Sie die Einstellung `DNS_RESOLVERS` auf `127.0.0.53`, was die Standard-Listenadresse für systemd-resolved ist:

=== "Web-UI"

    Navigieren Sie zur Seite **Globale Konfiguration** und setzen Sie die DNS-Resolver auf `127.0.0.53`

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

#### Verwendung von dnsmasq

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

        Navigieren Sie zur Seite **Globale Konfiguration**, wählen Sie das **NGINX**-Plugin und setzen Sie die DNS-Resolver auf `127.0.0.1`.

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
        bunkerity/bunkerweb-all-in-one:1.6.6-rc1
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
        image: bunkerity/bunkerweb:1.6.6-rc1
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-services
          - bw-dns

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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

### Benutzerdefinierte Konfigurationen {#custom-configurations}

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

Benutzerdefinierte Konfigurationen können global oder spezifisch für einen bestimmten Server angewendet werden, abhängig vom anwendbaren Kontext und ob der [Multisite-Modus](concepts.md#multisite-mode) aktiviert ist.

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
        bunkerity/bunkerweb-all-in-one:1.6.6-rc1
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
        bunkerity/bunkerweb-all-in-one:1.6.6-rc1
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
      image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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
      image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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
      image: nginxdemos/nginx-hello
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
      image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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

### Viele Dienste in der Produktion betreiben {#running-many-services-in-production}

#### Globales CRS

!!! warning "CRS-Plugins"
    Wenn das CRS global geladen wird, werden **CRS-Plugins nicht unterstützt**. Wenn Sie sie verwenden müssen, müssen Sie das CRS pro Dienst laden.

Wenn Sie BunkerWeb in der Produktion mit einer großen Anzahl von Diensten verwenden und die **ModSecurity-Funktion global** mit CRS-Regeln aktivieren, kann die zum Laden der BunkerWeb-Konfigurationen erforderliche Zeit zu lang werden, was möglicherweise zu einem Timeout führt.

Die Problemumgehung besteht darin, die CRS-Regeln global anstatt pro Dienst zu laden. Dieses Verhalten ist aus Gründen der Abwärtskompatibilität standardmäßig nicht aktiviert und weil es einen Nachteil hat: Wenn Sie das globale Laden von CRS-Regeln aktivieren, **ist es nicht mehr möglich, modsec-crs-Regeln** (die vor den CRS-Regeln ausgeführt werden) pro Dienst zu definieren. Diese Einschränkung kann jedoch umgangen werden, indem globale `modsec-crs`-Ausschlussregeln wie diese geschrieben werden:

```
SecRule REQUEST_FILENAME "@rx ^/somewhere$" "nolog,phase:4,allow,id:1010,chain"
SecRule REQUEST_HEADERS:Host "@rx ^app1\.example\.com$" "nolog"
```

Sie können das globale Laden von CRS-Regeln aktivieren, indem Sie `USE_MODSECURITY_GLOBAL_CRS` auf `yes` setzen.

#### `max_allowed_packet` für MariaDB/MySQL anpassen

Es scheint, dass der Standardwert für den Parameter `max_allowed_packet` in MariaDB- und MySQL-Datenbankservern nicht ausreicht, wenn BunkerWeb mit einer großen Anzahl von Diensten verwendet wird.

Wenn Sie Fehler wie diesen feststellen, insbesondere auf dem Scheduler:

```
[Warning] Aborted connection 5 to db: 'db' user: 'bunkerweb' host: '172.20.0.4' (Got a packet bigger than 'max_allowed_packet' bytes)
```

Sie müssen den `max_allowed_packet` auf Ihrem Datenbankserver erhöhen.

### Persistenz von Sperren und Berichten {#persistence-of-bans-and-reports}

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

### UDP/TCP-Anwendungen schützen

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
        bunkerity/bunkerweb-all-in-one:1.6.6-rc1
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
        image: bunkerity/bunkerweb:1.6.6-rc1
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
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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
        image: bunkerity/bunkerweb:1.6.6-rc1
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
        image: bunkerity/bunkerweb:1.6.6-rc1
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

### PHP

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

    Wenn Sie den [Multisite-Modus](concepts.md#multisite-mode) aktivieren, müssen Sie separate Verzeichnisse für jede Ihrer Anwendungen erstellen. Jedes Unterverzeichnis sollte nach dem ersten Wert von `SERVER_NAME` benannt werden. Hier ist ein Dummy-Beispiel:

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
        bunkerity/bunkerweb-all-in-one:1.6.6-rc1
    ```

    Bitte beachten Sie, dass Sie, wenn Ihr Container bereits erstellt wurde, ihn löschen und neu erstellen müssen, damit die neuen Umgebungsvariablen angewendet werden.

=== "Docker"

    Bei Verwendung der [Docker-Integration](integrations.md#docker) müssen Sie zur Unterstützung von PHP-Anwendungen Folgendes tun:

    -   Mounten Sie Ihre PHP-Dateien in den Ordner `/var/www/html` von BunkerWeb
    -   Richten Sie einen PHP-FPM-Container für Ihre Anwendung ein und mounten Sie den Ordner mit den PHP-Dateien
    -   Verwenden Sie die spezifischen Einstellungen `REMOTE_PHP` und `REMOTE_PHP_PATH` als Umgebungsvariablen beim Starten von BunkerWeb

    Wenn Sie den [Multisite-Modus](concepts.md#multisite-mode) aktivieren, müssen Sie separate Verzeichnisse für jede Ihrer Anwendungen erstellen. Jedes Unterverzeichnis sollte nach dem ersten Wert von `SERVER_NAME` benannt werden. Hier ist ein Dummy-Beispiel:

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
        image: bunkerity/bunkerweb:1.6.6-rc1
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
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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

    Da die Docker-Autoconf die Verwendung des [Multisite-Modus](concepts.md#multisite-mode) impliziert, müssen Sie separate Verzeichnisse für jede Ihrer Anwendungen erstellen. Jedes Unterverzeichnis sollte nach dem ersten Wert von `SERVER_NAME` benannt werden. Hier ist ein Dummy-Beispiel:

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
        image: bunkerity/bunkerweb:1.6.6-rc1
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
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc1
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

    Wenn Sie den [Multisite-Modus](concepts.md#multisite-mode) aktivieren, müssen Sie separate Verzeichnisse für jede Ihrer Anwendungen erstellen. Jedes Unterverzeichnis sollte nach dem ersten Wert von `SERVER_NAME` benannt werden. Hier ist ein Dummy-Beispiel:

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

    Da die Swarm-Integration die Verwendung des [Multisite-Modus](concepts.md#multisite-mode) impliziert, müssen Sie separate Verzeichnisse für jede Ihrer Anwendungen erstellen. Jedes Unterverzeichnis sollte nach dem ersten Wert von `SERVER_NAME` benannt werden. Hier ist ein Dummy-Beispiel:

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
        image: bunkerity/bunkerweb:1.6.6-rc1
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

### IPv6

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
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
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

### Docker Logging Best Practices

Bei der Verwendung von Docker ist es wichtig, die Container-Protokolle zu verwalten, um zu verhindern, dass sie übermäßig viel Speicherplatz beanspruchen. Standardmäßig verwendet Docker den `json-file`-Protokollierungstreiber, der bei fehlender Konfiguration zu sehr großen Protokolldateien führen kann.

Um dies zu vermeiden, können Sie die Protokollrotation konfigurieren. Dies kann für bestimmte Dienste in Ihrer `docker-compose.yml`-Datei oder global für den Docker-Daemon erfolgen.

**Konfiguration pro Dienst**

Sie können den Protokollierungstreiber für Ihre Dienste in Ihrer `docker-compose.yml`-Datei so konfigurieren, dass die Protokolle automatisch rotiert werden. Hier ist ein Beispiel, das bis zu 10 Protokolldateien mit jeweils 20 MB aufbewahrt:

```yaml
services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.6-rc1
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "10"
    ...
```

Diese Konfiguration stellt sicher, dass die Protokolle rotiert werden, und verhindert, dass sie Ihre Festplatte füllen. Sie können dies auf jeden Dienst in Ihrer Docker Compose-Einrichtung anwenden.

**Globale Konfiguration (daemon.json)**

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

Diese globale Konfiguration wird von allen Containern übernommen. Jede pro Dienst in einer `docker-compose.yml`-Datei definierte Protokollierungskonfiguration überschreibt jedoch die globalen Einstellungen in `daemon.json`.

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

#### Überwachung <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

#### Prometheus-Exporter <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

#### Berichterstattung <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

| Einstellung                    | Standard           | Kontext | Beschreibung                                                                                                                             |
| ------------------------------ | ------------------ | ------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | global  | Aktiviert das Senden des Berichts per E-Mail.                                                                                            |
| `USE_REPORTING_WEBHOOK`        | `no`               | global  | Aktiviert das Senden des Berichts per Webhook.                                                                                           |
| `REPORTING_SCHEDULE`           | `weekly`           | global  | Die Häufigkeit, mit der Berichte gesendet werden.                                                                                        |
| `REPORTING_WEBHOOK_URLS`       |                    | global  | Liste der Webhook-URLs, die den Bericht im Markdown-Format erhalten sollen (durch Leerzeichen getrennt).                                 |
| `REPORTING_SMTP_EMAILS`        |                    | global  | Liste der E-Mail-Adressen, die den Bericht im HTML-Format erhalten sollen (durch Leerzeichen getrennt).                                  |
| `REPORTING_SMTP_HOST`          |                    | global  | Der Host-Server, der für den SMTP-Versand verwendet wird.                                                                                |
| `REPORTING_SMTP_PORT`          | `465`              | global  | Der für SMTP verwendete Port. Bitte beachten Sie, dass es je nach Verbindungstyp unterschiedliche Standards gibt (SSL = 465, TLS = 587). |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | global  | Die als Absender verwendete E-Mail-Adresse. Beachten Sie, dass 2FA für diese E-Mail-Adresse deaktiviert sein muss.                       |
| `REPORTING_SMTP_FROM_USER`     |                    | global  | Der Benutzerauthentifizierungswert für das Senden über die Absender-E-Mail-Adresse.                                                      |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | global  | Der Passwortauthentifizierungswert für das Senden über die Absender-E-Mail-Adresse.                                                      |
| `REPORTING_SMTP_SSL`           | `SSL`              | global  | Bestimmt, ob eine sichere Verbindung für SMTP verwendet werden soll oder nicht.                                                          |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | global  | Die Betreffzeile der E-Mail.                                                                                                             |

!!! info "Information und Verhalten"
    - wenn `USE_REPORTING_SMTP` auf `yes` gesetzt ist, muss die Einstellung `REPORTING_SMTP_EMAILS` gesetzt werden.
    - wenn `USE_REPORTING_WEBHOOK` auf `yes` gesetzt ist, muss die Einstellung `REPORTING_WEBHOOK_URLS` gesetzt werden.
    - Akzeptierte Werte für `REPORTING_SCHEDULE` sind `daily`, `weekly` und `monthly`.
    - wenn keine `REPORTING_SMTP_FROM_USER` und `REPORTING_SMTP_FROM_PASSWORD` gesetzt sind, versucht das Plugin, die E-Mail ohne Authentifizierung zu senden.
    - wenn `REPORTING_SMTP_FROM_USER` nicht gesetzt ist, aber `REPORTING_SMTP_FROM_PASSWORD` gesetzt ist, verwendet das Plugin die `REPORTING_SMTP_FROM_EMAIL` als Benutzernamen.
    - wenn der Job fehlschlägt, versucht das Plugin, den Bericht bei der nächsten Ausführung erneut zu senden.

### Sicherung und Wiederherstellung

#### Sicherung S3 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

##### Manuelle Sicherung

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

##### Manuelle Wiederherstellung

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

### Migration <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM-Unterstützung :white_check_mark:

Das Migrations-Plugin **revolutioniert** die Übertragung von BunkerWeb-Konfigurationen zwischen Instanzen mit seiner **benutzerfreundlichen Weboberfläche**, die den gesamten Migrationsprozess vereinfacht. Ob Sie Systeme aufrüsten, die Infrastruktur skalieren oder Umgebungen wechseln, dieses Tool ermöglicht es Ihnen, **Einstellungen, Präferenzen und Daten** mühelos und mit unübertroffener Leichtigkeit und Zuversicht zu übertragen. Verabschieden Sie sich von umständlichen manuellen Prozessen und begrüßen Sie ein **nahtloses, problemloses Migrationserlebnis**.

**Liste der Funktionen**

-   **Mühelose Migration:** Übertragen Sie BunkerWeb-Konfigurationen einfach zwischen Instanzen, ohne die Komplexität manueller Verfahren.

-   **Intuitive Weboberfläche:** Navigieren Sie mühelos durch den Migrationsprozess mit einer benutzerfreundlichen Weboberfläche, die für eine intuitive Bedienung entwickelt wurde.

-   **Datenbankübergreifende Kompatibilität:** Genießen Sie eine nahtlose Migration über verschiedene Datenbankplattformen hinweg, einschließlich SQLite, MySQL, MariaDB und PostgreSQL, und gewährleisten Sie die Kompatibilität mit Ihrer bevorzugten Datenbankumgebung.

#### Eine Migrationsdatei erstellen

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

#### Eine Migration initialisieren

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

#### Funktionen

-   **Echtzeit-Verkehrsanalyse:** Überwacht kontinuierlich eingehende Anfragen, um potenzielle DDoS-Angriffe zu erkennen.
-   **Gleitender Fenstermechanismus:** Verfolgt die jüngsten Anforderungsaktivitäten innerhalb eines konfigurierbaren Zeitfensters.
-   **Konfigurierbare Schwellenwerte:** Ermöglicht die Definition der maximalen Anzahl verdächtiger Anfragen pro IP.
-   **Fortschrittliche Blockierungslogik:** Wertet sowohl die Anzahl der Anfragen pro IP als auch die Anzahl der unterschiedlichen IPs aus, die den Schwellenwert überschreiten.
-   **Flexible Sicherheitsmodi:** Wählen Sie zwischen sofortiger Verbindungsblockierung oder dem reinen Erkennungsmodus (Protokollierung).
-   **Optimierter In-Memory-Datenspeicher:** Gewährleistet Hochgeschwindigkeits-Lookups und effizientes Metrik-Tracking.
-   **Automatische Bereinigung:** Löscht regelmäßig veraltete Daten, um eine optimale Leistung zu gewährleisten.

#### Konfiguration

Passen Sie das Verhalten des Plugins mit den folgenden Einstellungen an:

| Einstellung                  | Standard      | Kontext | Mehrfach | Beschreibung                                                                                                                 |
| ---------------------------- | ------------- | ------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`          | global  | nein     | Aktiviert oder deaktiviert den Anti-DDoS-Schutz. Setzen Sie auf `"yes"`, um das Plugin zu aktivieren.                        |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`         | global  | nein     | Größe des In-Memory-Datenspeichers zur Verfolgung von DDoS-Metriken (z. B. `10M`, `500k`).                                   |
| `ANTIDDOS_THRESHOLD`         | `100`         | global  | nein     | Maximale Anzahl verdächtiger Anfragen pro IP innerhalb des definierten Zeitfensters.                                         |
| `ANTIDDOS_WINDOW_TIME`       | `10`          | global  | nein     | Zeitfenster in Sekunden, in dem verdächtige Anfragen gezählt werden.                                                         |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444` | global  | nein     | HTTP-Statuscodes, die als verdächtig gelten und zur Auslösung von Anti-DDoS-Aktionen verwendet werden.                       |
| `ANTIDDOS_DISTINCT_IP`       | `5`           | global  | nein     | Mindestanzahl unterschiedlicher IPs, die den Schwellenwert überschreiten müssen, bevor der Blockierungsmodus erzwungen wird. |

#### Bewährte Verfahren

-   **Schwellenwert-Tuning:** Passen Sie `ANTIDDOS_THRESHOLD` und `ANTIDDOS_WINDOW_TIME` basierend auf Ihren typischen Verkehrsmustern an.
-   **Statuscode-Überprüfung:** Aktualisieren Sie `ANTIDDOS_STATUS_CODES` regelmäßig, um neue oder sich entwickelnde verdächtige Verhaltensweisen zu erfassen.
-   **Überwachung:** Analysieren Sie Protokolle und Metriken regelmäßig, um die Einstellungen zu optimieren und den Gesamtschutz zu verbessern.

## Benutzer-Manager <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/EIohiUf9Fg4" title="Benutzer-Manager" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Das Benutzerverwaltungs-Plugin bietet eine robuste Schnittstelle zur Verwaltung von Benutzerkonten in Ihrem System.

Mit diesem Plugin können Administratoren mühelos Benutzerkonten erstellen, aktualisieren und deaktivieren, Benutzerrollen verwalten, die Zwei-Faktor-Authentifizierung (2FA) umschalten und detaillierte Benutzerinformationen wie letzte Anmeldezeitstempel und Kontostatus (aktiv oder inaktiv) anzeigen. Dieses Plugin wurde mit Blick auf Sicherheit und Benutzerfreundlichkeit entwickelt und vereinfacht routinemäßige Benutzerverwaltungsaufgaben, während es gleichzeitig die Einhaltung von Vorschriften und die Überprüfbarkeit gewährleistet.

#### Funktionen

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

Das Easy Resolve Plugin ermöglicht es Ihnen, Fehlalarme und wiederkehrende Probleme direkt von der Berichtsseite aus schnell zu beheben. Es wandelt geführte "Resolve"-Aktionen in sichere, bereichsbezogene Konfigurationsupdates um – ohne manuelle Bearbeitung.

#### Funktionen

-   Ein-Klick-Aktionen aus Berichten und Berichtsdetails.
-   Kontextbezogene Vorschläge für ModSecurity, Blacklist und DNSBL.
-   Generiert sichere ModSecurity-Ausschlüsse oder aktualisiert Ignorierlisten.
-   Wendet Änderungen auf Dienst- oder globaler Ebene mit Berechtigungsprüfungen an.
-   Optionales automatisches Öffnen der zugehörigen Konfigurationsseite nach der Anwendung.

<figure markdown>
  ![Übersicht](assets/img/easy-resolve.png){ align=center }
  <figcaption>Berichtsseite - mit Easy Resolve</figcaption>
</figure>

<div class="grid grid-2" markdown>
<figure markdown>
  ![ModSecurity beheben](assets/img/easy-resolve-modsecurity.png){ width="100%" }
  <figcaption>ModSecurity beheben</figcaption>
</figure>
<figure markdown>
  ![DNSBL beheben](assets/img/easy-resolve-dnsbl.png){ width="100%" }
  <figcaption>DNSBL beheben</figcaption>
</figure>
</div>

<div class="grid grid-5" markdown>
<figure markdown>
  ![Blacklist beheben - IP](assets/img/easy-resolve-blacklist-ip.png){ width="100%" }
  <figcaption>Blacklist - IP</figcaption>
</figure>
<figure markdown>
  ![Blacklist beheben - User-Agent](assets/img/easy-resolve-blacklist-ua.png){ width="100%" }
  <figcaption>Blacklist - User-Agent</figcaption>
</figure>
<figure markdown>
  ![Blacklist beheben - rDNS](assets/img/easy-resolve-blacklist-rdns.png){ width="100%" }
  <figcaption>Blacklist - rDNS</figcaption>
</figure>
<figure markdown>
  ![Blacklist beheben - ASN](assets/img/easy-resolve-blacklist-asn.png){ width="100%" }
  <figcaption>Blacklist - ASN</figcaption>
</figure>
<figure markdown>
  ![Blacklist beheben - URI](assets/img/easy-resolve-blacklist-uri.png){ width="100%" }
  <figcaption>Blacklist - URI</figcaption>
</figure>
</div>
