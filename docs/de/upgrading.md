# Aufrüsten

## Upgrade von 1.6.X

### Vorgehensweise

#### Docker

1. **Sichern Sie die Datenbank**:

    - Bevor Sie mit dem Datenbank-Upgrade fortfahren, stellen Sie sicher, dass Sie eine vollständige Sicherung des aktuellen Zustands der Datenbank durchführen.
    - Verwenden Sie geeignete Werkzeuge, um die gesamte Datenbank zu sichern, einschließlich Daten, Schemata und Konfigurationen.

    ```bash
    docker exec -it -e BACKUP_DIRECTORY=/pfad/zum/sicherungsverzeichnis <scheduler_container> bwcli plugin backup save
    ```

    ```bash
    docker cp <scheduler_container>:/pfad/zum/sicherungsverzeichnis /pfad/zum/sicherungsverzeichnis
    ```

2. **Aktualisieren Sie BunkerWeb**:
    - Aktualisieren Sie BunkerWeb auf die neueste Version.
        1. **Aktualisieren Sie die Docker Compose-Datei**: Aktualisieren Sie die Docker Compose-Datei, um die neue Version des BunkerWeb-Images zu verwenden.
            ```yaml
            services:
                bunkerweb:
                    image: bunkerity/bunkerweb:1.6.7-rc1
                    ...
                bw-scheduler:
                    image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
                    ...
                bw-autoconf:
                    image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
                    ...
                bw-ui:
                    image: bunkerity/bunkerweb-ui:1.6.7-rc1
                    ...
            ```

        2. **Starten Sie die Container neu**: Starten Sie die Container neu, um die Änderungen zu übernehmen.
            ```bash
            docker compose down
            docker compose up -d
            ```

3. **Überprüfen Sie die Protokolle**: Überprüfen Sie die Protokolle des Scheduler-Dienstes, um sicherzustellen, dass die Migration erfolgreich war.

    ```bash
    docker compose logs <scheduler_container>
    ```

4. **Überprüfen Sie die Datenbank**: Überprüfen Sie, ob das Datenbank-Upgrade erfolgreich war, indem Sie die Daten und Konfigurationen im neuen Datenbankcontainer überprüfen.

#### Linux

=== "Einfaches Upgrade mit dem Installationsskript"

    * **Schnellstart**:

        Um zu beginnen, laden Sie das Installationsskript und seine Prüfsumme herunter und überprüfen Sie dann die Integrität des Skripts, bevor Sie es ausführen.

        ```bash
        LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | jq -r .tag_name)

        # Download the script and its checksum
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh.sha256

        # Verify the checksum
        sha256sum -c install-bunkerweb.sh.sha256
        ```

        !!! danger "Sicherheitshinweis"
            **Überprüfen Sie immer die Integrität des Installationsskripts, bevor Sie es ausführen.**

            Laden Sie die Prüfsummendatei herunter und verwenden Sie ein Werkzeug wie `sha256sum`, um zu bestätigen, dass das Skript nicht verändert oder manipuliert wurde.

            Wenn die Überprüfung der Prüfsumme fehlschlägt, **führen Sie das Skript nicht aus** – es könnte unsicher sein.

    * **Wie es funktioniert**:

        Das gleiche vielseitige Installationsskript, das für Neuinstallationen verwendet wird, kann auch ein In-Place-Upgrade durchführen. Wenn es eine bestehende Installation und eine andere Zielversion erkennt, wechselt es in den Upgrade-Modus und wendet den folgenden Arbeitsablauf an:

        1. Erkennung & Validierung
            * Erkennt Betriebssystem / Version und bestätigt die Unterstützungsmatrix.
            * Liest die aktuell installierte BunkerWeb-Version aus `/usr/share/bunkerweb/VERSION`.
        2. Entscheidung über das Upgrade-Szenario
            * Wenn die angeforderte Version der installierten entspricht, wird abgebrochen (es sei denn, Sie führen explizit erneut für den Status aus).
            * Wenn sich die Versionen unterscheiden, wird ein Upgrade markiert.
        3. (Optional) Automatisches Pre-Upgrade-Backup
            * Wenn `bwcli` und der Scheduler verfügbar sind und die automatische Sicherung aktiviert ist, wird eine Sicherung über das integrierte Backup-Plugin erstellt.
            * Ziel: entweder das von Ihnen mit `--backup-dir` angegebene Verzeichnis oder ein generierter Pfad wie `/var/tmp/bunkerweb-backup-YYYYmmdd-HHMMSS`.
            * Sie können dies mit `--no-auto-backup` deaktivieren (die manuelle Sicherung liegt dann in Ihrer Verantwortung).
        4. Dienste stilllegen
            * Stoppt `bunkerweb`, `bunkerweb-ui` und `bunkerweb-scheduler`, um ein konsistentes Upgrade zu gewährleisten (entspricht den Empfehlungen für das manuelle Verfahren).
        5. Entfernen von Paketsperren
            * Entfernt vorübergehend `apt-mark hold` / `dnf versionlock` für `bunkerweb` und `nginx`, damit die Zielversion installiert werden kann.
        6. Upgrade-Ausführung
            * Installiert nur die neue BunkerWeb-Paketversion (NGINX wird im Upgrade-Modus nicht neu installiert, es sei denn, es fehlt – dies vermeidet das Berühren eines korrekt fixierten NGINX).
            * Wendet Holds/Versionlocks erneut an, um die aktualisierten Versionen einzufrieren.
        7. Abschluss & Status
            * Zeigt den systemd-Status für Kerndienste und die nächsten Schritte an.
            * Ihre Konfiguration und Datenbank bleiben unberührt – nur der Anwendungscode und die verwalteten Dateien werden aktualisiert.

        Wichtige Verhaltensweisen / Hinweise:

        * Das Skript ändert NICHT Ihre `/etc/bunkerweb/variables.env` oder den Datenbankinhalt.
        * Wenn die automatische Sicherung fehlgeschlagen ist (oder deaktiviert war), können Sie immer noch eine manuelle Wiederherstellung mit dem Rollback-Abschnitt unten durchführen.
        * Der Upgrade-Modus vermeidet absichtlich die Neuinstallation oder das Downgrade von NGINX außerhalb der unterstützten fixierten Version, die bereits vorhanden ist.
        * Protokolle zur Fehlerbehebung bleiben in `/var/log/bunkerweb/`.

    * **Verhaltensweisen je nach Installationsmodus**:

        - Das Skript verwendet beim Upgrade dieselbe Logik zur Auswahl des Installationstyps: Im Manager-Modus bleibt der Setup-Assistent deaktiviert, die API wird an `0.0.0.0` gebunden und eine freizuschaltende IP ist weiterhin erforderlich (für unbeaufsichtigte Abläufe per `--manager-ip` angeben), während der Worker-Modus die Manager-IP-Liste strikt erzwingt.
        - Manager-Upgrades können festlegen, ob der Web-UI-Dienst gestartet wird, und die Zusammenfassung weist aus, ob der API-Dienst aktiviert wird, sodass Sie ihn gezielt mit `--api` / `--no-api` steuern können.
        - CrowdSec-Optionen bleiben ausschließlich Full-Stack-Upgrades vorbehalten, und das Skript prüft weiterhin Betriebssystem und CPU-Architektur, bevor Pakete verändert werden; nicht unterstützte Kombinationen erfordern nach wie vor `--force`.

        Zusammenfassung des Rollbacks:

        * Verwenden Sie das generierte Sicherungsverzeichnis (oder Ihre manuelle Sicherung) + die Schritte im Rollback-Abschnitt, um die DB wiederherzustellen, installieren Sie dann die vorherige Image-/Paketversion neu und sperren Sie die Pakete erneut.

    * **Befehlszeilenoptionen**:

        Sie können unbeaufsichtigte Upgrades mit den gleichen Flags wie bei der Installation steuern. Die relevantesten für Upgrades:

        | Option                  | Zweck                                                                                                                          |
        | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
        | `-v, --version <X.Y.Z>` | Ziel-BunkerWeb-Version, auf die aktualisiert werden soll.                                                                      |
        | `-y, --yes`             | Nicht-interaktiv (geht von Upgrade-Bestätigung aus und aktiviert die automatische Sicherung, es sei denn, `--no-auto-backup`). |
        | `--backup-dir <PFAD>`   | Ziel für die automatische Pre-Upgrade-Sicherung. Wird erstellt, wenn es fehlt.                                                 |
        | `--no-auto-backup`      | Überspringt die automatische Sicherung (NICHT empfohlen). Sie müssen eine manuelle Sicherung haben.                            |
        | `-q, --quiet`           | Unterdrückt die Ausgabe (mit Protokollierung / Überwachung kombinieren).                                                       |
        | `-f, --force`           | Fährt mit einer ansonsten nicht unterstützten Betriebssystemversion fort.                                                      |
        | `--dry-run`             | Zeigt die erkannte Umgebung, die beabsichtigten Aktionen an und beendet dann, ohne etwas zu ändern.                            |

        Beispiele:

        ```bash
        # Interaktiv auf 1.6.7~rc1 aktualisieren (fragt nach Sicherung)
        sudo ./install-bunkerweb.sh --version 1.6.7~rc1

        # Nicht-interaktives Upgrade mit automatischer Sicherung in ein benutzerdefiniertes Verzeichnis
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 --backup-dir /var/backups/bw-2025-01 -y

        # Stilles unbeaufsichtigtes Upgrade (Protokolle unterdrückt) – verlässt sich auf die standardmäßige automatische Sicherung
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 -y -q

        # Einen Probelauf (Plan) durchführen, ohne Änderungen anzuwenden
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 --dry-run

        # Upgrade unter Überspringen der automatischen Sicherung (NICHT empfohlen)
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 --no-auto-backup -y
        ```

        !!! warning "Überspringen von Sicherungen"
            Die Verwendung von `--no-auto-backup` ohne eine verifizierte manuelle Sicherung kann zu irreversiblem Datenverlust führen, wenn beim Upgrade Probleme auftreten. Halten Sie immer mindestens eine aktuelle, getestete Sicherung bereit.

=== "Manuell"

    1. **Sichern Sie die Datenbank**:

        - Bevor Sie mit dem Datenbank-Upgrade fortfahren, stellen Sie sicher, dass Sie eine vollständige Sicherung des aktuellen Zustands der Datenbank durchführen.
        - Verwenden Sie geeignete Werkzeuge, um die gesamte Datenbank zu sichern, einschließlich Daten, Schemata und Konfigurationen.

        ??? warning "Informationen für Benutzer von Red Hat Enterprise Linux (RHEL) 8.10"
            Wenn Sie **RHEL 8.10** verwenden und eine **externe Datenbank** nutzen möchten, müssen Sie das Paket `mysql-community-client` installieren, um sicherzustellen, dass der Befehl `mysqldump` verfügbar ist. Sie können das Paket mit den folgenden Befehlen installieren:

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

                4. **Installieren Sie das PostgreSQL-Repository-Konfigurationspaket**

                    ```bash
                    dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                    ```

                5. **Installieren Sie den PostgreSQL-Client**

                    ```bash
                    dnf install postgresql<version>
                    ```

        ```bash
        BACKUP_DIRECTORY=/pfad/zum/sicherungsverzeichnis bwcli plugin backup save
        ```

    1. **Aktualisieren Sie BunkerWeb**:
        - Aktualisieren Sie BunkerWeb auf die neueste Version.

            1. **Stoppen Sie die Dienste**:
                ```bash
                sudo systemctl stop bunkerweb
                sudo systemctl stop bunkerweb-ui
                sudo systemctl stop bunkerweb-scheduler
                ```

            2. **Aktualisieren Sie BunkerWeb**:

                === "Debian/Ubuntu"

                    Wenn Sie das BunkerWeb-Paket zuvor gehalten haben, heben Sie die Sperre auf:

                    Sie können eine Liste der gehaltenen Pakete mit `apt-mark showhold` anzeigen

                    ```shell
                    sudo apt-mark unhold bunkerweb nginx
                    ```

                    Dann können Sie das BunkerWeb-Paket aktualisieren:

                    ```shell
                    sudo apt update && \
                    sudo apt install -y --allow-downgrades bunkerweb=1.6.7~rc1
                    ```

                    Um zu verhindern, dass das BunkerWeb-Paket bei der Ausführung von `apt upgrade` aktualisiert wird, können Sie den folgenden Befehl verwenden:

                    ```shell
                    sudo apt-mark hold bunkerweb nginx
                    ```

                    Weitere Details auf der Seite [Integration Linux](integrations.md#__tabbed_1_1).

                === "Fedora/RedHat"

                    Wenn Sie das BunkerWeb-Paket zuvor gehalten haben, heben Sie die Sperre auf:

                    Sie können eine Liste der gehaltenen Pakete mit `dnf versionlock list` anzeigen

                    ```shell
                    sudo dnf versionlock delete package bunkerweb && \
                    sudo dnf versionlock delete package nginx
                    ```

                    Dann können Sie das BunkerWeb-Paket aktualisieren:

                    ```shell
                    sudo dnf makecache && \
                    sudo dnf install -y --allowerasing bunkerweb-1.6.7~rc1
                    ```

                    Um zu verhindern, dass das BunkerWeb-Paket bei der Ausführung von `dnf upgrade` aktualisiert wird, können Sie den folgenden Befehl verwenden:

                    ```shell
                    sudo dnf versionlock add bunkerweb && \
                    sudo dnf versionlock add nginx
                    ```

                    Weitere Details auf der Seite [Integration Linux](integrations.md#__tabbed_1_3).

            3. **Starten Sie die Dienste**:
                    ```bash
                    sudo systemctl start bunkerweb
                    sudo systemctl start bunkerweb-ui
                    sudo systemctl start bunkerweb-scheduler
                    ```
                    Oder starten Sie das System neu:
                    ```bash
                    sudo reboot
                    ```


    3. **Überprüfen Sie die Protokolle**: Überprüfen Sie die Protokolle des Scheduler-Dienstes, um sicherzustellen, dass die Migration erfolgreich war.

        ```bash
        journalctl -u bunkerweb --no-pager
        ```

    4. **Überprüfen Sie die Datenbank**: Überprüfen Sie, ob das Datenbank-Upgrade erfolgreich war, indem Sie die Daten und Konfigurationen im neuen Datenbankcontainer überprüfen.

### Rollback

!!! failure "Bei Problemen"

    Wenn während des Upgrades Probleme auftreten, können Sie auf die vorherige Version der Datenbank zurückgreifen, indem Sie die in [Schritt 1](#__tabbed_1_1) erstellte Sicherung wiederherstellen.

    Holen Sie sich Unterstützung und weitere Informationen:

    - [Professionellen Support bestellen](https://panel.bunkerweb.io/?utm_source=doc&utm_campaign=self)
    - [Ein Issue auf GitHub erstellen](https://github.com/bunkerity/bunkerweb/issues)
    - [Treten Sie dem BunkerWeb Discord-Server bei](https://discord.bunkerity.com)

=== "Docker"

    1. **Entpacken Sie die Sicherung, falls sie gezippt ist**.

        Entpacken Sie zuerst die Sicherungs-Zip-Datei:

        ```bash
        unzip /pfad/zum/sicherungsverzeichnis/backup.zip -d /pfad/zum/sicherungsverzeichnis/
        ```

    2. **Stellen Sie die Sicherung wieder her**.

        === "SQLite"

            1. **Entfernen Sie die vorhandene Datenbankdatei.**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2. **Stellen Sie die Sicherung wieder her.**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

            3. **Korrigieren Sie die Berechtigungen.**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4. **Stoppen Sie den Stack.**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1. **Stellen Sie die Sicherung wieder her.**

                ```bash
                docker exec -e MYSQL_PWD=<ihr_passwort> -i <database_container> mysql -u <username> <database_name> < /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

            2. **Stoppen Sie den Stack.**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1. **Entfernen Sie die vorhandene Datenbank.**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2. **Erstellen Sie die Datenbank neu.**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3. **Stellen Sie die Sicherung wieder her.**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

            4. **Stoppen Sie den Stack.**

                ```bash
                docker compose down
                ```

    3. **Downgrade von BunkerWeb**.

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<alte_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<alte_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<alte_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<alte_version>
                ...
        ```

    4. **Starten Sie die Container**.

        ```bash
        docker compose up -d
        ```

=== "Linux"

    4. **Entpacken Sie die Sicherung, falls sie gezippt ist**.

        Entpacken Sie zuerst die Sicherungs-Zip-Datei:

        ```bash
        unzip /pfad/zum/sicherungsverzeichnis/backup.zip -d /pfad/zum/sicherungsverzeichnis/
        ```

    5. **Stoppen Sie die Dienste**.

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    6. **Stellen Sie die Sicherung wieder her**.

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /pfad/zum/sicherungsverzeichnis/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /pfad/zum/sicherungsverzeichnis/backup.sql
            ```

        === "PostgreSQL"

            1. **Entfernen Sie die vorhandene Datenbank.**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2. **Erstellen Sie die Datenbank neu.**

                ```bash
                createdb -U <username> <database_name>
                ```

            3. **Stellen Sie die Sicherung wieder her.**

                ```bash
                psql -U <username> -d <database_name> < /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

    7. **Starten Sie die Dienste**.

        ```bash
        sudo systemctl start bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    8. **Downgrade von BunkerWeb**.
        - Führen Sie ein Downgrade von BunkerWeb auf die vorherige Version durch, indem Sie die gleichen Schritte wie beim Upgrade von BunkerWeb auf der Seite [Integration Linux](integrations.md#linux) befolgen.

## Upgrade von 1.5.X

### Was hat sich geändert?

#### Scheduler

Im Gegensatz zu den 1.5.X-Versionen verwendet der Scheduler-Dienst **nicht mehr den *Docker-Socket-Proxy*, um BunkerWeb-Instanzen abzurufen**. Stattdessen verwendet er die neue Umgebungsvariable `BUNKERWEB_INSTANCES`.

!!! info "Über die Umgebungsvariable `BUNKERWEB_INSTANCES`"

    Diese neue Variable ist eine durch Leerzeichen getrennte Liste von BunkerWeb-Instanzen in diesem Format: `http://bunkerweb:5000 bunkerweb1:5000 bunkerweb2:5000 ...`. Der Scheduler verwendet dann diese Liste, um die Konfiguration der Instanzen abzurufen und die Konfiguration an sie zu senden.

    * Der Präfix `http://` ist optional.
    * Der Port ist optional und standardmäßig der Wert der Umgebungsvariable `API_HTTP_PORT`.
    * Der Standardwert der Umgebungsvariable `BUNKERWEB_INSTANCES` ist `127.0.0.1`.

Mit anderen Worten, das neue System ist vollständig agnostisch und generisch: Der Scheduler ist für die Verwaltung einer Liste von BunkerWeb-Instanzen zuständig und muss sich nicht um die Umgebung kümmern.

!!! tip "Autoconf/Kubernetes/Swarm-Integrationen"

    Wenn Sie die Integrationen `Autoconf`, `Kubernetes` oder `Swarm` verwenden, können Sie die Umgebungsvariable `BUNKERWEB_INSTANCES` auf eine leere Zeichenfolge setzen (damit nicht versucht wird, die Konfiguration an die Standardinstanz `127.0.0.1` zu senden).

    **Die Instanzen werden automatisch vom Controller abgerufen**. Sie können auch benutzerdefinierte Instanzen zur Liste hinzufügen, die möglicherweise nicht vom Controller erfasst werden.

Seit `1.6` verfügt der Scheduler auch über ein neues [integriertes System zur Zustandsprüfung](concepts.md), das den Zustand der Instanzen überprüft. Wenn eine Instanz ungesund wird, sendet der Scheduler die Konfiguration nicht mehr an sie. Wenn die Instanz wieder gesund wird, beginnt der Scheduler wieder, die Konfiguration an sie zu senden.

#### BunkerWeb-Container

Eine weitere wichtige Änderung ist, dass die **Einstellungen**, die zuvor im BunkerWeb-Container deklariert wurden, **jetzt im Scheduler deklariert werden**. Das bedeutet, dass Sie Ihre Einstellungen vom BunkerWeb-Container in den Scheduler-Container verschieben müssen.

Obwohl die Einstellungen jetzt im Scheduler-Container deklariert werden, **müssen Sie immer noch API-bezogene obligatorische Einstellungen im BunkerWeb-Container deklarieren**, wie die Einstellung `API_WHITELIST_IP`, die verwendet wird, um die IP-Adresse des Schedulers auf die Whitelist zu setzen, damit er die Konfiguration an die Instanz senden kann. Wenn Sie `API_TOKEN` verwenden, müssen Sie es auch im BunkerWeb-Container setzen (und im Scheduler spiegeln), um authentifizierte API-Aufrufe zu ermöglichen.

!!! warning "Einstellungen des BunkerWeb-Containers"

    Jede API-bezogene Einstellung, die Sie im BunkerWeb-Container deklarieren, **muss im Scheduler-Container gespiegelt werden**, damit sie weiterhin funktioniert, da die Konfiguration durch die vom Scheduler generierte Konfiguration überschrieben wird.

#### Standardwerte und neue Einstellungen

Wir haben unser Bestes getan, um die Standardwerte nicht zu ändern, aber wir haben viele andere Einstellungen hinzugefügt. Es wird dringend empfohlen, die Abschnitte [Sicherheits-Tuning](advanced.md#security-tuning) und [Einstellungen](features.md) der Dokumentation zu lesen.

#### Vorlagen

Wir haben eine neue Funktion namens **Vorlagen** hinzugefügt. Vorlagen bieten einen strukturierten und standardisierten Ansatz zur Definition von Einstellungen und benutzerdefinierten Konfigurationen. Weitere Informationen finden Sie im Abschnitt [Konzepte/Vorlagen](concepts.md#templates).

#### Autoconf-Namespaces

Wir haben eine **Namespace**-Funktion zu den Autoconf-Integrationen hinzugefügt. Mit Namespaces können Sie Ihre Instanzen gruppieren und Einstellungen nur auf sie anwenden. Weitere Informationen finden Sie in den folgenden Abschnitten entsprechend Ihrer Integration:

- [Autoconf/Namespaces](integrations.md#namespaces)
- [Kubernetes/Namespaces](integrations.md#namespaces_1)
- [Swarm/Namespaces](integrations.md#namespaces_2)

### Vorgehensweise

1. **Sichern Sie die Datenbank**:
      - Bevor Sie mit dem Datenbank-Upgrade fortfahren, stellen Sie sicher, dass Sie eine vollständige Sicherung des aktuellen Zustands der Datenbank durchführen.
      - Verwenden Sie geeignete Werkzeuge, um die gesamte Datenbank zu sichern, einschließlich Daten, Schemata und Konfigurationen.

    === "1.5.7 und später"

        === "Docker"

            ```bash
            docker exec -it -e BACKUP_DIRECTORY=/pfad/zum/sicherungsverzeichnis <scheduler_container> bwcli plugin backup save
            ```

            ```bash
            docker cp <scheduler_container>:/pfad/zum/sicherungsverzeichnis /pfad/zum/sicherungsverzeichnis
            ```

        === "Linux"

            ??? warning "Informationen für Benutzer von Red Hat Enterprise Linux (RHEL) 8.10"
                Wenn Sie **RHEL 8.10** verwenden und eine **externe Datenbank** nutzen möchten, müssen Sie das Paket `mysql-community-client` installieren, um sicherzustellen, dass der Befehl `mysqldump` verfügbar ist. Sie können das Paket mit den folgenden Befehlen installieren:

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

                    4. **Installieren Sie das PostgreSQL-Repository-Konfigurationspaket**

                        ```bash
                        dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                        ```

                    5. **Installieren Sie den PostgreSQL-Client**

                        ```bash
                        dnf install postgresql<version>
                        ```

            ```bash
            BACKUP_DIRECTORY=/pfad/zum/sicherungsverzeichnis bwcli plugin backup save
            ```

    === "1.5.6 und früher"

        === "SQLite"

            === "Docker"

                Zuerst müssen wir das `sqlite`-Paket im Container installieren.

                ```bash
                docker exec -u 0 -it <scheduler_container> apk add sqlite
                ```

                Dann sichern Sie die Datenbank.

                ```bash
                docker exec -it <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

            === "Linux"

                ```bash
                sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

        === "MariaDB"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mariadb-dump -u <username> <database_name> > /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mariadb-dump -u <username> <database_name> > /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

        === "MySQL"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mysqldump -u <username> <database_name> > /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mysqldump -u <username> <database_name> > /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

        === "PostgreSQL"

            === "Docker"

                ```bash
                docker exec -it -e PGPASSWORD=<database_password> <database_container> pg_dump -U <username> -d <database_name> > /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

            === "Linux"

                ```bash
                PGPASSWORD=<database_password> pg_dump -U <username> -d <database_name> > /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

2. **Aktualisieren Sie BunkerWeb**:
      - Aktualisieren Sie BunkerWeb auf die neueste Version.

        === "Docker"

            1. **Aktualisieren Sie die Docker Compose-Datei**: Aktualisieren Sie die Docker Compose-Datei, um die neue Version des BunkerWeb-Images zu verwenden.
                ```yaml
                services:
                    bunkerweb:
                        image: bunkerity/bunkerweb:1.6.7-rc1
                        ...
                    bw-scheduler:
                        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
                        ...
                    bw-autoconf:
                        image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
                        ...
                    bw-ui:
                        image: bunkerity/bunkerweb-ui:1.6.7-rc1
                        ...
                ```

            2. **Starten Sie die Container neu**: Starten Sie die Container neu, um die Änderungen zu übernehmen.
                ```bash
                docker compose down
                docker compose up -d
                ```

        === "Linux"

            3. **Stoppen Sie die Dienste**:
                ```bash
                sudo systemctl stop bunkerweb
                sudo systemctl stop bunkerweb-ui
                sudo systemctl stop bunkerweb-scheduler
                ```

            4. **Aktualisieren Sie BunkerWeb**:

                === "Debian/Ubuntu"

                    Wenn Sie das BunkerWeb-Paket zuvor gehalten haben, heben Sie die Sperre auf:

                    Sie können eine Liste der gehaltenen Pakete mit `apt-mark showhold` anzeigen

                    ```shell
                    sudo apt-mark unhold bunkerweb nginx
                    ```

                    Dann können Sie das BunkerWeb-Paket aktualisieren:

                    ```shell
                    sudo apt update && \
                    sudo apt install -y --allow-downgrades bunkerweb=1.6.7~rc1
                    ```

                    Um zu verhindern, dass das BunkerWeb-Paket bei der Ausführung von `apt upgrade` aktualisiert wird, können Sie den folgenden Befehl verwenden:

                    ```shell
                    sudo apt-mark hold bunkerweb nginx
                    ```

                    Weitere Details auf der Seite [Integration Linux](integrations.md#__tabbed_1_1).

                === "Fedora/RedHat"

                    Wenn Sie das BunkerWeb-Paket zuvor gehalten haben, heben Sie die Sperre auf:

                    Sie können eine Liste der gehaltenen Pakete mit `dnf versionlock list` anzeigen

                    ```shell
                    sudo dnf versionlock delete package bunkerweb && \
                    sudo dnf versionlock delete package nginx
                    ```

                    Dann können Sie das BunkerWeb-Paket aktualisieren:

                    ```shell
                    sudo dnf makecache && \
                    sudo dnf install -y --allowerasing bunkerweb-1.6.7~rc1
                    ```

                    Um zu verhindern, dass das BunkerWeb-Paket bei der Ausführung von `dnf upgrade` aktualisiert wird, können Sie den folgenden Befehl verwenden:

                    ```shell
                    sudo dnf versionlock add bunkerweb && \
                    sudo dnf versionlock add nginx
                    ```

                    Weitere Details auf der Seite [Integration Linux](integrations.md#__tabbed_1_3).

            5. **Starten Sie die Dienste**:
                    ```bash
                    sudo systemctl start bunkerweb
                    sudo systemctl start bunkerweb-ui
                    sudo systemctl start bunkerweb-scheduler
                    ```
                    Oder starten Sie das System neu:
                    ```bash
                    sudo reboot
                    ```


3. **Überprüfen Sie die Protokolle**: Überprüfen Sie die Protokolle des Scheduler-Dienstes, um sicherzustellen, dass die Migration erfolgreich war.

    === "Docker"

        ```bash
        docker compose logs <scheduler_container>
        ```

    === "Linux"

        ```bash
        journalctl -u bunkerweb --no-pager
        ```

4. **Überprüfen Sie die Datenbank**: Überprüfen Sie, ob das Datenbank-Upgrade erfolgreich war, indem Sie die Daten und Konfigurationen im neuen Datenbankcontainer überprüfen.

### Rollback

!!! failure "Bei Problemen"

    Wenn während des Upgrades Probleme auftreten, können Sie auf die vorherige Version der Datenbank zurückgreifen, indem Sie die in [Schritt 1](#__tabbed_1_1) erstellte Sicherung wiederherstellen.

    Holen Sie sich Unterstützung und weitere Informationen:

    - [Professionellen Support bestellen](https://panel.bunkerweb.io/?utm_source=doc&utm_campaign=self)
    - [Ein Issue auf GitHub erstellen](https://github.com/bunkerity/bunkerweb/issues)
    - [Treten Sie dem BunkerWeb Discord-Server bei](https://discord.bunkerity.com)

=== "Docker"

    1. **Entpacken Sie die Sicherung, falls sie gezippt ist**.

        Entpacken Sie zuerst die Sicherungs-Zip-Datei:

        ```bash
        unzip /pfad/zum/sicherungsverzeichnis/backup.zip -d /pfad/zum/sicherungsverzeichnis/
        ```

    2. **Stellen Sie die Sicherung wieder her**.

        === "SQLite"

            1. **Entfernen Sie die vorhandene Datenbankdatei.**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2. **Stellen Sie die Sicherung wieder her.**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

            3. **Korrigieren Sie die Berechtigungen.**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4. **Stoppen Sie den Stack.**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1. **Stellen Sie die Sicherung wieder her.**

                ```bash
                docker exec -e MYSQL_PWD=<ihr_passwort> -i <database_container> mysql -u <username> <database_name> < /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

            2. **Stoppen Sie den Stack.**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1. **Entfernen Sie die vorhandene Datenbank.**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2. **Erstellen Sie die Datenbank neu.**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3. **Stellen Sie die Sicherung wieder her.**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

            4. **Stoppen Sie den Stack.**

                ```bash
                docker compose down
                ```

    3. **Downgrade von BunkerWeb**.

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<alte_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<alte_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<alte_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<alte_version>
                ...
        ```

    4. **Starten Sie die Container**.

        ```bash
        docker compose up -d
        ```

=== "Linux"

    4. **Entpacken Sie die Sicherung, falls sie gezippt ist**.

        Entpacken Sie zuerst die Sicherungs-Zip-Datei:

        ```bash
        unzip /pfad/zum/sicherungsverzeichnis/backup.zip -d /pfad/zum/sicherungsverzeichnis/
        ```

    5. **Stoppen Sie die Dienste**.

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    6. **Stellen Sie die Sicherung wieder her**.

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /pfad/zum/sicherungsverzeichnis/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /pfad/zum/sicherungsverzeichnis/backup.sql
            ```

        === "PostgreSQL"

            1. **Entfernen Sie die vorhandene Datenbank.**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2. **Erstellen Sie die Datenbank neu.**

                ```bash
                createdb -U <username> <database_name>
                ```

            3. **Stellen Sie die Sicherung wieder her.**

                ```bash
                psql -U <username> -d <database_name> < /pfad/zum/sicherungsverzeichnis/backup.sql
                ```

    7. **Starten Sie die Dienste**.

        ```bash
        sudo systemctl start bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    8. **Downgrade von BunkerWeb**.
        - Führen Sie ein Downgrade von BunkerWeb auf die vorherige Version durch, indem Sie die gleichen Schritte wie beim Upgrade von BunkerWeb auf der Seite [Integration Linux](integrations.md#linux) befolgen.
