# Web-UI

## Übersicht

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/tGS3pzquEjY" title="BunkerWeb Web UI" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Die "Web-UI" ist eine Webanwendung, die Ihnen hilft, Ihre BunkerWeb-Instanz über eine benutzerfreundliche Oberfläche zu verwalten, anstatt sich ausschließlich auf die Befehlszeile zu verlassen.

Hier ist eine Liste der von der Web-UI angebotenen Funktionen:

-   Einen umfassenden Überblick über blockierte Angriffe erhalten
-   Ihre BunkerWeb-Instanz starten, stoppen, neu starten und neu laden
-   Einstellungen für Ihre Webanwendungen hinzufügen, bearbeiten und löschen
-   Benutzerdefinierte Konfigurationen für NGINX und ModSecurity hinzufügen, bearbeiten und löschen
-   Externe Plugins installieren und deinstallieren
-   Zwischengespeicherte Dateien erkunden
-   Die Ausführung von Jobs überwachen und bei Bedarf neu starten
-   Protokolle anzeigen und nach Mustern suchen

## Voraussetzungen {#prerequisites}

Da die Web-UI eine Webanwendung ist, besteht die empfohlene Architektur darin, BunkerWeb als Reverse-Proxy davor zu betreiben. Das empfohlene Installationsverfahren ist die Verwendung des Einrichtungsassistenten, der Sie Schritt für Schritt führt, wie im [Schnellstart-Leitfaden](quickstart-guide.md) beschrieben.

!!! warning "Sicherheitsaspekte"

    Die Sicherheit der Web-UI ist äußerst wichtig. Wenn eine unbefugte Person Zugriff auf die Anwendung erhält, kann sie nicht nur Ihre Konfigurationen bearbeiten, sondern möglicherweise auch Code im Kontext von BunkerWeb ausführen (z. B. über eine benutzerdefinierte Konfiguration mit LUA-Code). Wir empfehlen dringend, dass Sie minimale Sicherheits-Best Practices befolgen, wie z. B.:

    * Wählen Sie ein starkes Passwort für die Anmeldung (**mindestens 8 Zeichen, einschließlich 1 Kleinbuchstabe, 1 Großbuchstabe, 1 Ziffer und 1 Sonderzeichen**)
    * Platzieren Sie die Web-UI unter einer "schwer zu erratenden" URI
    * Aktivieren Sie die Zwei-Faktor-Authentifizierung (2FA)
    * Stellen Sie die Web-UI nicht ohne zusätzliche Einschränkungen im Internet zur Verfügung
    * Wenden Sie die im Abschnitt [Erweiterte Nutzungen](advanced.md#security-tuning) der Dokumentation aufgeführten Best Practices je nach Ihrem Anwendungsfall an

## Upgrade auf PRO {#upgrade-to-pro}

!!! tip "Kostenlose Testversion von BunkerWeb PRO"
    Möchten Sie BunkerWeb PRO einen Monat lang schnell testen? Verwenden Sie den Code `freetrial` bei Ihrer Bestellung im [BunkerWeb-Panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) oder klicken Sie [hier](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc), um den Promo-Code direkt anzuwenden (wird an der Kasse wirksam).

Sobald Sie Ihren PRO-Lizenzschlüssel vom [BunkerWeb-Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc) haben, können Sie ihn auf der PRO-Seite der Web-UI einfügen.

<figure markdown>
  ![PRO-Upgrade](assets/img/pro-ui-upgrade.png){ align=center, width="700" }
  <figcaption>Upgrade auf PRO über die Web-UI</figcaption>
</figure>

!!! warning "Upgrade-Zeit"
    Die PRO-Version wird im Hintergrund vom Scheduler heruntergeladen, es kann einige Zeit dauern, bis das Upgrade abgeschlossen ist.

Wenn Ihre BunkerWeb-Instanz auf die PRO-Version aktualisiert wurde, sehen Sie Ihr Lizenzablaufdatum und die maximale Anzahl der Dienste, die Sie schützen können.

<figure markdown>
  ![PRO-Upgrade](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>PRO-Lizenzinformationen</figcaption>
</figure>

## Zugriff auf Protokolle

Ab Version `1.6` hat sich die Methode zum Zugriff auf Protokolle geändert. Dieses Update betrifft insbesondere containerbasierte Integrationen: Die Web-UI liest die Protokolldateien nun aus dem Verzeichnis `/var/log/bunkerweb`.

Um die Protokolle über die Web-UI zugänglich zu halten, empfehlen wir die Verwendung eines Syslog-Servers wie `syslog-ng`, um die Protokolle zu lesen und die entsprechenden Dateien im Verzeichnis `/var/log/bunkerweb` zu erstellen.

!!! warning "Verwendung eines lokalen Ordners für Protokolle"
    Die Web-UI läuft als **unprivilegierter Benutzer mit UID 101 und GID 101** im Container aus Sicherheitsgründen: Im Falle einer ausgenutzten Schwachstelle hat der Angreifer keine vollen Root-Rechte (UID/GID 0).

    Es gibt jedoch einen Nachteil: Wenn Sie einen **lokalen Ordner für Protokolle** verwenden, müssen Sie **die richtigen Berechtigungen festlegen**, damit der unprivilegierte Benutzer die Protokolldateien lesen kann. Zum Beispiel:

    ```shell
    mkdir bw-logs && \
    chown root:101 bw-logs && \
    chmod 770 bw-logs
    ```

    Alternativ, wenn der Ordner bereits existiert:

    ```shell
    chown -R root:101 bw-logs && \
    chmod -R 770 bw-logs
    ```

    Wenn Sie [Docker im rootless-Modus](https://docs.docker.com/engine/security/rootless) oder [podman](https://podman.io/) verwenden, werden UIDs und GIDs im Container auf andere auf dem Host abgebildet. Sie müssen zuerst Ihre anfängliche subuid und subgid überprüfen:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    Wenn Sie beispielsweise einen Wert von **100000** haben, ist die abgebildete UID/GID **100100** (100000 + 100):

    ```shell
    mkdir bw-logs && \
    sudo chgrp 100100 bw-logs && \
    chmod 770 bw-logs
    ```

    Oder wenn der Ordner bereits existiert:

    ```shell
    sudo chgrp -R 100100 bw-logs && \
    sudo chmod -R 770 bw-logs
    ```

### Compose-Vorlagen

=== "Docker"

    Um die Protokolle bei der Docker-Integration korrekt in das Verzeichnis `/var/log/bunkerweb` weiterzuleiten, müssen Sie die Protokolle mit `syslog-ng` in eine Datei streamen. Hier ist ein Beispiel, wie das geht:

    ```yaml
    x-bw-env: &bw-env
      # Wir verankern die Umgebungsvariablen, um Duplikate zu vermeiden
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
      # Optionaler API-Token bei der Sicherung des API-Zugriffs
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc2
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *bw-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog
          options:
            tag: "bunkerweb" # Dies ist das Tag, das von syslog-ng verwendet wird, um die Protokolldatei zu erstellen
            syslog-address: "udp://10.20.30.254:514" # Dies ist die Adresse des syslog-ng-Containers

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc2
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Stellen Sie sicher, dass Sie den richtigen Instanznamen festlegen
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
          SERVE_FILES: "no"
          DISABLE_DEFAULT_SERVER: "yes"
          USE_CLIENT_CACHE: "yes"
          USE_GZIP: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Ändern Sie dies in eine schwer zu erratende URI
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
        volumes:
          - bw-storage:/data # Dies wird verwendet, um den Cache und andere Daten wie die Backups zu persistieren
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-scheduler" # Dies ist das Tag, das von syslog-ng verwendet wird, um die Protokolldatei zu erstellen
            syslog-address: "udp://10.20.30.254:514" # Dies ist die Adresse des syslog-ng-Containers

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6-rc2
        environment:
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Denken Sie daran, ein stärkeres Passwort für den Admin-Benutzer festzulegen
          TOTP_ENCRYPTION_KEYS: "mysecret" # Denken Sie daran, einen stärkeren geheimen Schlüssel festzulegen (siehe Abschnitt Voraussetzungen)
        volumes:
          - bw-logs:/var/log/bunkerweb # Dies ist das Volume, das zum Speichern der Protokolle verwendet wird
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-ui" # Dies ist das Tag, das von syslog-ng verwendet wird, um die Protokolldatei zu erstellen
            syslog-address: "udp://10.20.30.254:514" # Dies ist die Adresse des syslog-ng-Containers

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

      bw-syslog:
        image: balabit/syslog-ng:4.9.0
        cap_add:
          - NET_BIND_SERVICE  # An niedrige Ports binden
          - NET_BROADCAST  # Broadcasts senden
          - NET_RAW  # Raw-Sockets verwenden
          - DAC_READ_SEARCH  # Dateien unter Umgehung von Berechtigungen lesen
          - DAC_OVERRIDE  # Dateiberechtigungen überschreiben
          - CHOWN  # Eigentümer ändern
          - SYSLOG  # In Systemprotokolle schreiben
        volumes:
          - bw-logs:/var/log/bunkerweb # Dies ist das Volume, das zum Speichern der Protokolle verwendet wird
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # Dies ist die syslog-ng-Konfigurationsdatei
        networks:
          bw-universe:
            ipv4_address: 10.20.30.254 # Stellen Sie sicher, dass Sie die richtige IP-Adresse festlegen

    volumes:
      bw-data:
      bw-storage:
      bw-logs:

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

    Um die Protokolle bei der Autoconf-Integration korrekt in das Verzeichnis `/var/log/bunkerweb` weiterzuleiten, müssen Sie die Protokolle mit `syslog-ng` in eine Datei streamen. Hier ist ein Beispiel, wie das geht:

    ```yaml
    x-ui-env: &bw-ui-env
      # Wir verankern die Umgebungsvariablen, um Duplikate zu vermeiden
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc2
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog
          options:
            tag: "bunkerweb" # Dies ist das Tag, das von syslog-ng verwendet wird, um die Protokolldatei zu erstellen
            syslog-address: "udp://10.20.30.254:514" # Dies ist die Adresse des syslog-ng-Containers

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc2
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: "" # Wir müssen die BunkerWeb-Instanz hier nicht angeben, da sie automatisch vom Autoconf-Dienst erkannt werden
          SERVER_NAME: "" # Der Servername wird mit Dienst-Labels gefüllt
          MULTISITE: "yes" # Obligatorische Einstellung für Autoconf / UI
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        volumes:
          - bw-storage:/data # Dies wird verwendet, um den Cache und andere Daten wie die Backups zu persistieren
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-scheduler" # Dies ist das Tag, das von syslog-ng verwendet wird, um die Protokolldatei zu erstellen
            syslog-address: "udp://10.20.30.254:514" # Dies ist die Adresse des syslog-ng-Containers

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc2
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375" # Dies ist die Adresse des Docker-Sockets
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-docker
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-autoconf" # Dies ist das Tag, das von syslog-ng verwendet wird, um die Protokolldatei zu erstellen
            syslog-address: "udp://10.20.30.254:514" # Dies ist die Adresse des syslog-ng-Containers

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6-rc2
        environment:
          <<: *bw-ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Denken Sie daran, ein stärkeres Passwort für den Admin-Benutzer festzulegen
          TOTP_ENCRYPTION_KEYS: "mysecret" # Denken Sie daran, einen stärkeren geheimen Schlüssel festzulegen (siehe Abschnitt Voraussetzungen)
        volumes:
          - bw-logs:/var/log/bunkerweb
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_TEMPLATE=ui"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme" # Ändern Sie dies in eine schwer zu erratende URI
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
        logging:
          driver: syslog
          options:
            tag: "bw-ui" # Dies ist das Tag, das von syslog-ng verwendet wird, um die Protokolldatei zu erstellen
            syslog-address: "udp://10.20.30.254:514" # Dies ist die Adresse des syslog-ng-Containers

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

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: "unless-stopped"
        networks:
          - bw-docker

      bw-syslog:
        image: balabit/syslog-ng:4.9.0
        cap_add:
          - NET_BIND_SERVICE  # An niedrige Ports binden
          - NET_BROADCAST  # Broadcasts senden
          - NET_RAW  # Raw-Sockets verwenden
          - DAC_READ_SEARCH  # Dateien unter Umgehung von Berechtigungen lesen
          - DAC_OVERRIDE  # Dateiberechtigungen überschreiben
          - CHOWN  # Eigentümer ändern
          - SYSLOG  # In Systemprotokolle schreiben
        volumes:
          - bw-logs:/var/log/bunkerweb # Dies ist das Volume, das zum Speichern der Protokolle verwendet wird
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # Dies ist die syslog-ng-Konfigurationsdatei
        networks:
          bw-universe:
            ipv4_address: 10.20.30.254 # Stellen Sie sicher, dass Sie die richtige IP-Adresse festlegen

    volumes:
      bw-data:
      bw-storage:
      bw-logs:

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
      bw-docker:
        name: bw-docker
    ```

### Syslog-ng-Konfiguration

Hier ist ein Beispiel für eine `syslog-ng.conf`-Datei, die Sie verwenden können, um die Protokolle in eine Datei weiterzuleiten:

```conf
@version: 4.8

# Quellkonfiguration zum Empfang von Protokollen von Docker-Containern
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# Vorlage zum Formatieren von Protokollnachrichten
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# Zielkonfiguration zum Schreiben von Protokollen in dynamisch benannte Dateien
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
  );
};

# Protokollpfad zum Weiterleiten von Protokollen an dynamisch benannte Dateien
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Kontoverwaltung

Sie können auf die Kontoverwaltungsseite zugreifen, indem Sie auf das Profilbild in der oberen rechten Ecke klicken:

<figure markdown>
  ![Übersicht](assets/img/manage-account.png){ align=center, width="400" }
  <figcaption>Zugriff auf die Kontoseite von der oberen rechten Ecke</figcaption>
</figure>

### Benutzername / Passwort

!!! warning "Passwort/Benutzername verloren"

    Falls Sie Ihre UI-Anmeldeinformationen vergessen haben, können Sie sie von der CLI aus zurücksetzen, indem Sie [den in der Fehlerbehebungssektion beschriebenen Schritten folgen](troubleshooting.md#web-ui).

Sie können Ihren Benutzernamen oder Ihr Passwort aktualisieren, indem Sie die entsprechenden Formulare im Tab **Sicherheit** ausfüllen. Aus Sicherheitsgründen müssen Sie Ihr aktuelles Passwort eingeben, auch wenn Sie angemeldet sind.

Bitte beachten Sie, dass Sie nach der Aktualisierung Ihres Benutzernamens oder Passworts von der Web-UI abgemeldet werden, um sich erneut anzumelden.

<figure markdown>
  ![Übersicht](assets/img/profile-username-password.png){ align=center }
  <figcaption>Benutzername-/Passwort-Formular</figcaption>
</figure>

### Zwei-Faktor-Authentifizierung

!!! tip "Obligatorische Verschlüsselungsschlüssel"

    Wenn Sie 2FA aktivieren, müssen Sie mindestens einen Verschlüsselungsschlüssel angeben. Dieser Schlüssel wird verwendet, um Ihre TOTP-Geheimnisse zu verschlüsseln.

    Die empfohlene Methode zur Generierung eines gültigen Schlüssels ist die Verwendung des `passlib`-Pakets:

    ```shell
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    Setzen Sie den generierten Schlüssel in der Umgebungsvariable `TOTP_ENCRYPTION_KEYS` der Web-UI. Sie können auch mehrere durch Leerzeichen getrennte Schlüssel oder ein Wörterbuch festlegen (aus Gründen der Abwärtskompatibilität).

!!! warning "Geheimschlüssel verloren"

    Falls Sie Ihren Geheimschlüssel verlieren, stehen zwei Optionen zur Verfügung:

    - Sie können Ihr Konto mit einem der Wiederherstellungscodes wiederherstellen, die Sie bei der Aktivierung von 2FA erhalten haben (ein Wiederherstellungscode kann nur einmal verwendet werden).
    - Sie können 2FA von der CLI aus deaktivieren, indem Sie [den in der Fehlerbehebungssektion beschriebenen Schritten folgen](troubleshooting.md#web-ui).

Sie können Ihre Anmeldesicherheit durch Hinzufügen einer **Zwei-Faktor-Authentifizierung (2FA)** zu Ihrem Konto erhöhen. Dadurch wird zusätzlich zu Ihrem Passwort ein zusätzlicher Code benötigt.

Die Web-UI verwendet [zeitbasiertes Einmalkennwort (TOTP)](https://de.wikipedia.org/wiki/Time-based_One-time_Password_Algorithm) als 2FA-Implementierung: Mit einem **geheimen Schlüssel** generiert der Algorithmus **Einmalkennwörter, die nur für einen kurzen Zeitraum gültig sind**.

Jeder TOTP-Client wie Google Authenticator, Authy, FreeOTP usw. kann verwendet werden, um den geheimen Schlüssel zu speichern und die Codes zu generieren. Bitte beachten Sie, dass Sie den geheimen Schlüssel nach der Aktivierung von TOTP **nicht mehr von der Web-UI abrufen können**.

Die folgenden Schritte sind erforderlich, um die TOTP-Funktion in der Web-UI zu aktivieren:

- Kopieren Sie den geheimen Schlüssel oder verwenden Sie den QR-Code in Ihrer Authentifizierungs-App
- Geben Sie den aktuellen TOTP-Code in das 2FA-Eingabefeld ein
- Geben Sie Ihr aktuelles Passwort ein

!!! info "Aktualisierung des Geheimschlüssels"
    Ein neuer geheimer Schlüssel wird **jedes Mal generiert**, wenn Sie die Seite besuchen oder das Formular absenden. Falls etwas schiefgeht (z. B. abgelaufener TOTP-Code), müssen Sie den neuen geheimen Schlüssel in Ihre Authentifizierungs-App kopieren, bis 2FA erfolgreich aktiviert ist.

!!! tip "Wiederherstellungscodes"

    Wenn Sie 2FA aktivieren, erhalten Sie **5 Wiederherstellungscodes**. Diese Codes können verwendet werden, um Ihr Konto wiederherzustellen, falls Sie Ihren TOTP-Geheimschlüssel verloren haben. Jeder Code kann nur einmal verwendet werden. **Diese Codes werden nur einmal angezeigt, also stellen Sie sicher, dass Sie sie an einem sicheren Ort aufbewahren**.

    Wenn Sie Ihre Wiederherstellungscodes verlieren, **können Sie sie über den TOTP-Abschnitt der Kontoverwaltungsseite aktualisieren**. Bitte beachten Sie, dass die alten Wiederherstellungscodes ungültig werden.

Sie können 2FA im Tab **Sicherheit** aktivieren oder deaktivieren und auch die Wiederherstellungscodes aktualisieren:

<figure markdown>
  ![Übersicht](assets/img/profile-totp.png){ align=center }
  <figcaption>Formulare zum Aktivieren/Deaktivieren/Aktualisieren von TOTP-Wiederherstellungscodes</figcaption>
</figure>

Nach einer erfolgreichen Kombination aus Login und Passwort werden Sie aufgefordert, Ihren TOTP-Code einzugeben:

<figure markdown>
  ![Übersicht](assets/img/profile-2fa.png){ align=center, width="400" }
  <figcaption>2FA auf der Anmeldeseite</figcaption>
</figure>

### Aktuelle Sitzungen

Im Tab **Sitzung** können Sie aktuelle Sitzungen auflisten und widerrufen:

<figure markdown>
  ![Übersicht](assets/img/sessions.png){ align=center }
  <figcaption>Sitzungen verwalten</figcaption>
</figure>

## Erweiterte Installation

Die Web-UI kann auch ohne den Einrichtungsassistenten bereitgestellt und konfiguriert werden: Die Konfiguration erfolgt über Umgebungsvariablen, die direkt zu den Containern oder bei einer Linux-Integration in die Datei `/etc/bunkerweb/ui.env` hinzugefügt werden können.

!!! tip "Spezifische Umgebungsvariablen der Web-UI"

    Die Web-UI verwendet die folgenden Umgebungsvariablen:

    - `OVERRIDE_ADMIN_CREDS`: auf `yes` setzen, um die Überschreibung zu aktivieren, auch wenn die Admin-Anmeldeinformationen bereits festgelegt sind (Standard ist `no`).
    - `ADMIN_USERNAME`: Benutzername für den Zugriff auf die Web-UI.
    - `ADMIN_PASSWORD`: Passwort für den Zugriff auf die Web-UI.
    - `FLASK_SECRET`: ein geheimer Schlüssel, der zum Verschlüsseln des Sitzungs-Cookies verwendet wird (wenn nicht festgelegt, wird ein zufälliger Schlüssel generiert).
    - `TOTP_ENCRYPTION_KEYS` (oder `TOTP_SECRETS`): eine Liste von TOTP-Verschlüsselungsschlüsseln, die durch Leerzeichen getrennt sind, oder ein Wörterbuch (z. B. `{"1": "meingeheimschlüssel"}` oder `meingeheimschlüssel` oder `meingeheimschlüssel meingeheimschlüssel1`). **Wir empfehlen dringend, diese Variable zu setzen, wenn Sie 2FA verwenden möchten, da sie zur Verschlüsselung der TOTP-Geheimschlüssel verwendet wird** (wenn nicht festgelegt, wird eine zufällige Anzahl von Geheimschlüsseln generiert). Weitere Informationen finden Sie in der [passlib-Dokumentation](https://passlib.readthedocs.io/en/stable/narr/totp-tutorial.html#application-secrets).
    - `UI_LISTEN_ADDR` (bevorzugt): die Adresse, an der die Web-UI lauschen wird (Standard ist `0.0.0.0` in **Docker-Images** und `127.0.0.1` bei **Linux-Installationen**). Fällt auf `LISTEN_ADDR` zurück, wenn nicht gesetzt.
    - `UI_LISTEN_PORT` (bevorzugt): der Port, an dem die Web-UI lauschen wird (Standard ist `7000`). Fällt auf `LISTEN_PORT` zurück, wenn nicht gesetzt.
    - `MAX_WORKERS`: die Anzahl der von der Web-UI verwendeten Worker (Standard ist die Anzahl der CPUs).
    - `MAX_THREADS`: die Anzahl der von der Web-UI verwendeten Threads (Standard ist `MAX_WORKERS` * 2).
    - `FORWARDED_ALLOW_IPS`: eine Liste von IP-Adressen oder Netzwerken, die im `X-Forwarded-For`-Header verwendet werden dürfen (Standard ist `*` in **Docker-Images** und `127.0.0.1` bei **Linux-Installationen**).
    - `CHECK_PRIVATE_IP`: auf `yes` setzen, um Benutzer nicht zu trennen, deren IP-Adresse sich während einer Sitzung ändert, wenn sie sich in einem privaten Netzwerk befinden (Standard ist `yes`). (Nicht-private IP-Adressen werden immer überprüft).
    - `ENABLE_HEALTHCHECK`: auf `yes` setzen, um den `/healthcheck`-Endpunkt zu aktivieren, der eine einfache JSON-Antwort mit Statusinformationen zurückgibt (Standard ist `no`).

    Die Web-UI verwendet diese Variablen, um Sie zu authentifizieren und die 2FA-Funktion zu handhaben.

!!! example "Empfohlene Geheimnisse generieren"

    Um ein gültiges **ADMIN_PASSWORD** zu generieren, empfehlen wir die **Verwendung eines Passwort-Managers** oder eines **Passwort-Generators**.

    Sie können ein gültiges **FLASK_SECRET** mit dem folgenden Befehl generieren:

    ```shell
    python3 -c "import secrets; print(secrets.token_hex(64))"
    ```

    Sie können gültige, durch Leerzeichen getrennte **TOTP_ENCRYPTION_KEYS** mit dem folgenden Befehl generieren (Sie benötigen das `passlib`-Paket):

    ```shell
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

=== "Linux"

    Die Installation der Web-UI über die [Linux-Integration](integrations.md#linux) ist ziemlich unkompliziert, da sie mit BunkerWeb installiert wird.

    Die Web-UI wird als systemd-Dienst namens `bunkerweb-ui` geliefert. Bitte stellen Sie sicher, dass er aktiviert ist:

    ```shell
    sudo systemctl enable bunkerweb-ui && \
    sudo systemctl status bunkerweb-ui
    ```

    Eine dedizierte Umgebungsdatei unter `/etc/bunkerweb/ui.env` wird zur Konfiguration der Web-UI verwendet:

    ```conf
    ADMIN_USERNAME=changeme
    ADMIN_PASSWORD=changeme
    TOTP_ENCRYPTION_KEYS=mysecret
    ```

    Ersetzen Sie die `changeme`-Daten durch Ihre eigenen Werte.

    Denken Sie daran, einen stärkeren geheimen Schlüssel für `TOTP_ENCRYPTION_KEYS` festzulegen.

    Jedes Mal, wenn Sie die Datei `/etc/bunkerweb/ui.env` bearbeiten, müssen Sie den Dienst neu starten:

    ```shell
    systemctl restart bunkerweb-ui
    ```

    Der Zugriff auf die Web-UI über BunkerWeb ist eine klassische [Reverse-Proxy-Einrichtung](quickstart-guide.md). Bitte beachten Sie, dass die Web-UI auf Port `7000` und nur auf der Loopback-Schnittstelle lauscht.

    Hier ist die `/etc/bunkerweb/variables.env`-Vorlage, die Sie verwenden können:

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4
    API_LISTEN_IP=127.0.0.1
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_TEMPLATE=ui
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/changeme
    www.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:7000
    ```

    Vergessen Sie nicht, den `bunkerweb`-Dienst neu zu laden:

    ```shell
    systemctl reload bunkerweb
    ```

=== "Docker"

    Die Web-UI kann über einen dedizierten Container bereitgestellt werden, der auf [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) verfügbar ist:

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternativ können Sie es auch selbst erstellen:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    Der Zugriff auf die Web-UI über BunkerWeb ist eine klassische [Reverse-Proxy-Einrichtung](quickstart-guide.md). Wir empfehlen Ihnen, BunkerWeb und die Web-UI über ein dediziertes Netzwerk (wie `bw-universe`, das auch vom Scheduler verwendet wird) zu verbinden, damit es aus offensichtlichen Sicherheitsgründen nicht im selben Netzwerk wie Ihre Webdienste liegt. Bitte beachten Sie, dass der Web-UI-Container auf Port `7000` lauscht.

    !!! info "Datenbank-Backend"

        Wenn Sie ein anderes Datenbank-Backend als MariaDB wünschen, lesen Sie bitte die docker-compose-Dateien im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc2/misc/integrations) des Repositorys.

    Hier ist die docker-compose-Vorlage, die Sie verwenden können (vergessen Sie nicht, die `changeme`-Daten zu bearbeiten):

    ```yaml
    x-ui-env: &ui-env
      # Wir verankern die Umgebungsvariablen, um Duplikate zu vermeiden
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc2
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Für QUIC / HTTP3-Unterstützung
        environment:
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Stellen Sie sicher, dass Sie den richtigen IP-Bereich festlegen, damit der Scheduler die Konfiguration an die Instanz senden kann
          API_TOKEN: "" # Spiegeln Sie API_TOKEN, wenn Sie es verwenden
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc2
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Stellen Sie sicher, dass Sie den richtigen Instanznamen festlegen
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Wir spiegeln die API_WHITELIST_IP vom bunkerweb-Dienst
          API_TOKEN: "" # Spiegeln Sie API_TOKEN, wenn Sie es verwenden
          SERVE_FILES: "no"
          DISABLE_DEFAULT_SERVER: "yes"
          USE_CLIENT_CACHE: "yes"
          USE_GZIP: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Denken Sie daran, eine stärkere URI festzulegen
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000" # Der Web-UI-Container lauscht standardmäßig auf Port 7000
        volumes:
          - bw-storage:/data # Dies wird verwendet, um den Cache und andere Daten wie die Backups zu persistieren
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6-rc2
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Denken Sie daran, ein stärkeres Passwort für den changeme-Benutzer festzulegen
          TOTP_ENCRYPTION_KEYS: "mysecret" # Denken Sie daran, einen stärkeren geheimen Schlüssel festzulegen (siehe Abschnitt Voraussetzungen)
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
      bw-db:
        name: bw-db
    ```

=== "Docker autoconf"

    Die Web-UI kann über einen dedizierten Container bereitgestellt werden, der auf [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) verfügbar ist:

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternativ können Sie es auch selbst erstellen:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    !!! tip "Umgebungsvariablen"

        Bitte lesen Sie den Abschnitt [Voraussetzungen](#prerequisites), um alle Umgebungsvariablen zu sehen, die Sie zur Anpassung der Web-UI festlegen können.

    Der Zugriff auf die Web-UI über BunkerWeb ist eine klassische [Reverse-Proxy-Einrichtung](quickstart-guide.md). Wir empfehlen Ihnen, BunkerWeb und die Web-UI über ein dediziertes Netzwerk (wie `bw-universe`, das auch vom Scheduler und Autoconf verwendet wird) zu verbinden, damit es aus offensichtlichen Sicherheitsgründen nicht im selben Netzwerk wie Ihre Webdienste liegt. Bitte beachten Sie, dass der Web-UI-Container auf Port `7000` lauscht.

    !!! info "Datenbank-Backend"

        Wenn Sie ein anderes Datenbank-Backend als MariaDB wünschen, lesen Sie bitte die docker-compose-Dateien im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc2/misc/integrations) des Repositorys.

    Hier ist die docker-compose-Vorlage, die Sie verwenden können (vergessen Sie nicht, die `changeme`-Daten zu bearbeiten):

    ```yaml
    x-ui-env: &ui-env
      # Wir verankern die Umgebungsvariablen, um Duplikate zu vermeiden
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc2
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Für QUIC / HTTP3-Unterstützung
        labels:
          - "bunkerweb.INSTANCE=yes" # Wir setzen das Instanz-Label, damit die Autoconf die Instanz erkennen kann
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc2
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
        volumes:
          - bw-storage:/data # Dies wird verwendet, um den Cache und andere Daten wie die Backups zu persistieren
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc2
        depends_on:
          - bw-docker
        environment:
          <<: *ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6-rc2
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Denken Sie daran, ein stärkeres Passwort für den changeme-Benutzer festzulegen
          TOTP_ENCRYPTION_KEYS: "mysecret" # Denken Sie daran, einen stärkeren geheimen Schlüssel festzulegen (siehe Abschnitt Voraussetzungen)
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_TEMPLATE=ui"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme"
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
        networks:
          - bw-universe
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

=== "Kubernetes"

    Die Web-UI kann über einen dedizierten Container bereitgestellt werden, der auf [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) verfügbar ist, und Sie können ihn als Standard-[Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) bereitstellen.

    Der Zugriff auf die Web-UI über BunkerWeb ist eine klassische [Reverse-Proxy-Einrichtung](quickstart-guide.md). Die Netzwerksegmentierung zwischen der Web-UI und den Webdiensten wird in dieser Dokumentation nicht behandelt. Bitte beachten Sie, dass der Web-UI-Container auf Port `7000` lauscht.

    !!! info "Datenbank-Backend"

        Wenn Sie ein anderes Datenbank-Backend als MariaDB wünschen, lesen Sie bitte die YAML-Dateien im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc2/misc/integrations) des Repositorys.

    Hier ist der entsprechende Teil Ihrer `values.yaml`-Datei, den Sie verwenden können:

    ```yaml
    settings:
      # Verwenden Sie ein vorhandenes Secret namens bunkerweb, das die folgenden Werte enthält:
      # - admin-username
      # - admin-password
      # - flask-secret
      # - totp-secrets
      existingSecret: "secret-bunkerweb"
    ui:
      wizard: false
      ingress:
        enabled: true
        serverName: "www.example.com"
        serverPath: "/admin"
      overrideAdminCreds: "yes"
    ```

=== "Swarm"

    !!! warning "Veraltet"
        Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](integrations.md#kubernetes).

        **Weitere Informationen finden Sie in der [Swarm-Integrationsdokumentation](integrations.md#swarm).**

    Die Web-UI kann über einen dedizierten Container bereitgestellt werden, der auf [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) verfügbar ist:

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternativ können Sie es auch selbst erstellen:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    Der Zugriff auf die Web-UI über BunkerWeb ist eine klassische [Reverse-Proxy-Einrichtung](quickstart-guide.md). Wir empfehlen Ihnen, BunkerWeb und die Web-UI über ein dediziertes Netzwerk (wie `bw-universe`, das auch vom Scheduler und Autoconf verwendet wird) zu verbinden, damit es aus offensichtlichen Sicherheitsgründen nicht im selben Netzwerk wie Ihre Webdienste liegt. Bitte beachten Sie, dass der Web-UI-Container auf Port `7000` lauscht.

    !!! info "Datenbank-Backend"

        Wenn Sie ein anderes Datenbank-Backend als MariaDB wünschen, lesen Sie bitte die Stack-Dateien im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc2/misc/integrations) des Repositorys.

    Hier ist die Stack-Vorlage, die Sie verwenden können (vergessen Sie nicht, die `changeme`-Daten zu bearbeiten):

    ```yaml
    x-ui-env: &ui-env
      # Wir verankern die Umgebungsvariablen, um Duplikate zu vermeiden
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc2
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
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc2
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "bw-redis"
        volumes:
          - bw-storage:/data # Dies wird verwendet, um den Cache und andere Daten wie die Backups zu persistieren
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc2
        environment:
          <<: *ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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
          - bw-db

      bw-redis:
        image: redis:7-alpine
        networks:
          - bw-universe

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6-rc2
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Denken Sie daran, ein stärkeres Passwort für den changeme-Benutzer festzulegen
          TOTP_ENCRYPTION_KEYS: "mysecret" # Denken Sie daran, einen stärkeren geheimen Schlüssel festzulegen (siehe Abschnitt Voraussetzungen)
        networks:
          - bw-universe
          - bw-db
        deploy:
          labels:
            - "bunkerweb.SERVER_NAME=www.example.com"
            - "bunkerweb.USE_TEMPLATE=ui"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_URL=/changeme"
            - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"

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

## Sprachunterstützung & Lokalisierung

Die BunkerWeb-Benutzeroberfläche unterstützt mehrere Sprachen. Die Übersetzungen werden im Verzeichnis `src/ui/app/static/locales` verwaltet. Derzeit sind die folgenden Sprachen verfügbar:

- Englisch (en)
- Französisch (fr)
- Arabisch (ar)
- Bengali (bn)
- Spanisch (es)
- Hindi (hi)
- Portugiesisch (pt)
- Russisch (ru)
- Urdu (ur)
- Chinesisch (zh)
- Deutsch (de)
- Italienisch (it)

Weitere Informationen zur Herkunft und zum Überprüfungsstatus der Übersetzungen finden Sie in der [locales/README.md](https://github.com/bunkerity/bunkerweb/raw/v1.6.6-rc2/src/ui/app/static/locales/README.md).

### Beitragen von Übersetzungen

Wir freuen uns über Beiträge zur Verbesserung oder zum Hinzufügen neuer Lokalisierungsdateien!

**Wie man eine Übersetzung beisteuert:**

1. Bearbeiten Sie die Datei `src/ui/app/lang_config.py`, um Ihre Sprache hinzuzufügen (Code, Name, Flagge, englischer Name).
2. Kopieren Sie `en.json` als Vorlage in `src/ui/app/static/locales/` und benennen Sie es in Ihren Sprachcode um (z. B. `de.json` für Deutsch).
3. Übersetzen Sie die Werte in Ihrer neuen Datei.
4. Aktualisieren Sie die Tabelle in `locales/README.md`, um Ihre Sprache hinzuzufügen und anzugeben, wer sie erstellt/überprüft hat.
5. Senden Sie einen Pull-Request.

Für Aktualisierungen bearbeiten Sie die entsprechende Datei und aktualisieren Sie die Herkunftstabelle nach Bedarf.

Weitere Richtlinien finden Sie in der [locales/README.md](https://github.com/bunkerity/bunkerweb/raw/v1.6.6-rc2/src/ui/app/static/locales/README.md).
