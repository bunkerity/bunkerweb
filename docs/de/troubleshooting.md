# Fehlerbehebung

!!! info "BunkerWeb Panel"
    Wenn Sie Ihr Problem nicht lösen können, können Sie [uns direkt über unser Panel kontaktieren](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc). Dies zentralisiert alle Anfragen zur BunkerWeb-Lösung.

## Protokolle

Bei der Fehlerbehebung sind Protokolle Ihre besten Freunde. Wir geben unser Bestes, um benutzerfreundliche Protokolle bereitzustellen, damit Sie verstehen, was passiert.

Bitte beachten Sie, dass Sie `LOG_LEVEL` auf `info` (Standard: `notice`) setzen können, um die Ausführlichkeit von BunkerWeb zu erhöhen.

Hier erfahren Sie, wie Sie je nach Integration auf die Protokolle zugreifen können:

=== "Docker"

    !!! tip "Container auflisten"
        Um die laufenden Container aufzulisten, können Sie den folgenden Befehl verwenden:
        ```shell
        docker ps
        ```

    Sie können den Befehl `docker logs` verwenden (ersetzen Sie `bunkerweb` durch den Namen Ihres Containers):
    ```shell
    docker logs bunkerweb
    ```

    Hier ist das Docker-Compose-Äquivalent (ersetzen Sie `bunkerweb` durch den Namen der in der `docker-compose.yml`-Datei deklarierten Dienste):
    ```shell
    docker-compose logs bunkerweb
    ```

=== "Docker Autoconf"

    !!! tip "Container auflisten"
        Um die laufenden Container aufzulisten, können Sie den folgenden Befehl verwenden:
        ```shell
        docker ps
        ```

    Sie können den Befehl `docker logs` verwenden (ersetzen Sie `bunkerweb` und `bw-autoconf` durch die Namen Ihrer Container):
    ```shell
    docker logs bunkerweb
    docker logs bw-autoconf
    ```

    Hier ist das Docker-Compose-Äquivalent (ersetzen Sie `bunkerweb` und `bw-autoconf` durch die Namen der in der `docker-compose.yml`-Datei deklarierten Dienste):
    ```shell
    docker-compose logs bunkerweb
    docker-compose logs bw-autoconf
    ```

=== "All-in-one"

    !!! tip "Container-Name"
        Der Standard-Container-Name für das All-in-one-Image ist `bunkerweb-aio`. Wenn Sie einen anderen Namen verwendet haben, passen Sie den Befehl bitte entsprechend an.

    Sie können den Befehl `docker logs` verwenden:
    ```shell
    docker logs bunkerweb-aio
    ```

=== "Swarm"

    !!! warning "Veraltet"
        Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](integrations.md#kubernetes).

        **Weitere Informationen finden Sie in der [Swarm-Integrationsdokumentation](integrations.md#swarm).**

    !!! tip "Dienste auflisten"
        Um die Dienste aufzulisten, können Sie den folgenden Befehl verwenden:
        ```shell
        docker service ls
        ```

    Sie können den Befehl `docker service logs` verwenden (ersetzen Sie `bunkerweb` und `bw-autoconf` durch die Namen Ihrer Dienste):
    ```shell
    docker service logs bunkerweb
    docker service logs bw-autoconf
    ```

=== "Kubernetes"

    !!! tip "Pods auflisten"
        Um die Pods aufzulisten, können Sie den folgenden Befehl verwenden:
        ```shell
        kubectl get pods
        ```

    Sie können den Befehl `kubectl logs` verwenden (ersetzen Sie `bunkerweb` und `bunkerweb-controler` durch die Namen Ihrer Pods):
    ```shell
    kubectl logs bunkerweb
    kubectl logs bunkerweb-controler
    ```

=== "Linux"

    Bei Fehlern im Zusammenhang mit BunkerWeb-Diensten (z. B. wenn sie nicht starten) können Sie `journalctl` verwenden:
    ```shell
    journalctl -u bunkerweb --no-pager
    ```

    Allgemeine Protokolle befinden sich im Verzeichnis `/var/log/bunkerweb`:
    ```shell
    cat /var/log/bunkerweb/error.log
    cat /var/log/bunkerweb/access.log
    ```

## Berechtigungen

Vergessen Sie nicht, dass BunkerWeb aus offensichtlichen Sicherheitsgründen als unprivilegierter Benutzer ausgeführt wird. Überprüfen Sie die Berechtigungen von Dateien und Ordnern, die von BunkerWeb verwendet werden, insbesondere wenn Sie benutzerdefinierte Konfigurationen verwenden (weitere Informationen [hier](advanced.md#custom-configurations)). Sie müssen mindestens **_RW_**-Rechte für Dateien und **_RWX_** für Ordner festlegen.

## IP-Entsperrung

Sie können eine IP manuell entsperren, was bei Tests nützlich ist, damit Sie die interne API von BunkerWeb kontaktieren können (ersetzen Sie `1.2.3.4` durch die zu entsperrende IP-Adresse):

=== "Docker / Docker Autoconf"

    Sie können den Befehl `docker exec` verwenden (ersetzen Sie `bw-scheduler` durch den Namen Ihres Containers):
    ```shell
    docker exec bw-scheduler bwcli unban 1.2.3.4
    ```

    Hier ist das Docker-Compose-Äquivalent (ersetzen Sie `bw-scheduler` durch den Namen der in der `docker-compose.yml`-Datei deklarierten Dienste):
    ```shell
    docker-compose exec bw-scheduler bwcli unban 1.2.3.4
    ```

=== "All-in-one"

    !!! tip "Container-Name"
        Der Standard-Container-Name für das All-in-one-Image ist `bunkerweb-aio`. Wenn Sie einen anderen Namen verwendet haben, passen Sie den Befehl bitte entsprechend an.

    Sie können den Befehl `docker exec` verwenden:
    ```shell
    docker exec bunkerweb-aio bwcli unban 1.2.3.4
    ```

=== "Swarm"

    !!! warning "Veraltet"
        Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](integrations.md#kubernetes).

        **Weitere Informationen finden Sie in der [Swarm-Integrationsdokumentation](integrations.md#swarm).**

    Sie können den Befehl `docker exec` verwenden (ersetzen Sie `bw-scheduler` durch den Namen Ihres Dienstes):
    ```shell
    docker exec $(docker ps -q -f name=bw-scheduler) bwcli unban 1.2.3.4
    ```

=== "Kubernetes"

    Sie können den Befehl `kubectl exec` verwenden (ersetzen Sie `bunkerweb-scheduler` durch den Namen Ihres Pods):
    ```shell
    kubectl exec bunkerweb-scheduler bwcli unban 1.2.3.4
    ```

=== "Linux"

    Sie können den Befehl `bwcli` (als Root) verwenden:
    ```shell
    sudo bwcli unban 1.2.3.4
    ```

## Falschmeldungen

### Nur-Erkennen-Modus

Zu Debugging-/Testzwecken können Sie BunkerWeb in den [Nur-Erkennen-Modus](features.md#security-modes) versetzen, sodass Anfragen nicht blockiert werden und es sich wie ein klassischer Reverse-Proxy verhält.

### ModSecurity

Die Standardkonfiguration von ModSecurity in BunkerWeb lädt das Core Rule Set im Anomalie-Bewertungsmodus mit einer Paranoia-Stufe (PL) von 1:

- Jede übereinstimmende Regel erhöht eine Anomalie-Punktzahl (so können viele Regeln auf eine einzelne Anfrage zutreffen)
- PL1 enthält Regeln mit geringerer Wahrscheinlichkeit von Falschmeldungen (aber weniger Sicherheit als PL4)
- der Standardschwellenwert für die Anomalie-Punktzahl beträgt 5 für Anfragen und 4 für Antworten

Nehmen wir die folgenden Protokolle als Beispiel für eine ModSecurity-Erkennung mit der Standardkonfiguration (zur besseren Lesbarkeit formatiert):

```log
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `lfi-os-files.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-930-APPLICATION-ATTACK-LFI.conf"]
	[line "78"]
	[id "930120"]
	[rev ""]
	[msg "OS File Access Attempt"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-lfi"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/255/153/126"]
	[tag "PCI/6.5.4"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:utf8toUnicode,t:urlDecodeUni,t:normalizePathWin,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `unix-shell.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf"]
	[line "480"]
	[id "932160"]
	[rev ""]
	[msg "Remote Command Execution: Unix Shell Code Found"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-shell"]
	[tag "platform-unix"]
	[tag "attack-rce"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/152/248/88"]
	[tag "PCI/6.5.2"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:urlDecodeUni,t:cmdLine,t:normalizePath,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [error] 85#85: *11 [client 172.17.0.1] ModSecurity: Access denied with code 403 (phase 2). Matched "Operator `Ge' with parameter `5' against variable `TX:ANOMALY_SCORE' (Value: `10' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-949-BLOCKING-EVALUATION.conf"]
	[line "80"]
	[id "949110"]
	[rev ""]
	[msg "Inbound Anomaly Score Exceeded (Total Score: 10)"]
	[data ""]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-generic"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref ""],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
```

Wie wir sehen können, gibt es 3 verschiedene Protokolle:

1. Regel **930120** stimmte überein
2. Regel **932160** stimmte überein
3. Zugriff verweigert (Regel **949110**)

Eine wichtige Sache zu verstehen ist, dass Regel **949110** keine "echte" Regel ist: Es ist diejenige, die die Anfrage verweigert, weil der Anomalie-Schwellenwert erreicht ist (in diesem Beispiel **10**). Sie sollten die Regel **949110** niemals entfernen!

Wenn es sich um eine Falschmeldung handelt, sollten Sie sich auf die Regeln **930120** und **932160** konzentrieren. Das Tuning von ModSecurity und/oder CRS liegt außerhalb des Rahmens dieser Dokumentation, aber vergessen Sie nicht, dass Sie benutzerdefinierte Konfigurationen vor und nach dem Laden des CRS anwenden können (weitere Informationen [hier](advanced.md#custom-configurations)).

### Schlechtes Verhalten

Ein häufiger Fall von Falschmeldungen ist, wenn der Client aufgrund der Funktion "schlechtes Verhalten" gesperrt wird, was bedeutet, dass innerhalb eines Zeitraums zu viele verdächtige HTTP-Statuscodes generiert wurden (weitere Informationen [hier](features.md#bad-behavior)). Sie sollten damit beginnen, die Einstellungen zu überprüfen und sie dann entsprechend Ihrer Webanwendung(en) zu bearbeiten, z. B. einen verdächtigen HTTP-Code entfernen, die Zählzeit verringern, den Schwellenwert erhöhen usw.

### Whitelisting

Wenn Sie Bots (oder Administratoren) haben, die auf Ihre Website zugreifen müssen, ist die empfohlene Vorgehensweise, um Falschmeldungen zu vermeiden, sie mit der [Whitelisting-Funktion](features.md#whitelist) auf die Whitelist zu setzen. Wir empfehlen nicht, die Einstellungen `WHITELIST_URI*` oder `WHITELIST_USER_AGENT*` zu verwenden, es sei denn, sie sind auf geheime und unvorhersehbare Werte gesetzt. Gängige Anwendungsfälle sind:

- Healthcheck / Status-Bot
- Callback wie IPN oder Webhook
- Social-Media-Crawler

## Häufige Fehler

### Upstream hat zu großen Header gesendet

Wenn Sie den Fehler `upstream sent too big header while reading response header from upstream` in den Protokollen sehen, müssen Sie die verschiedenen Proxy-Puffergrößen mit den folgenden Einstellungen anpassen:

- `PROXY_BUFFERS`
- `PROXY_BUFFER_SIZE`
- `PROXY_BUSY_BUFFERS_SIZE`

### Konnte server_names_hash nicht erstellen

Wenn Sie den Fehler `could not build server_names_hash, you should increase server_names_hash_bucket_size` in den Protokollen sehen, müssen Sie die Einstellung `SERVER_NAMES_HASH_BUCKET_SIZE` anpassen.

## Zeitzone

Bei Verwendung von containerbasierten Integrationen kann die Zeitzone des Containers von der des Host-Rechners abweichen. Um dies zu beheben, können Sie die Umgebungsvariable `TZ` auf die Zeitzone Ihrer Wahl in Ihren Containern setzen (z. B. `TZ=Europe/Paris`). Eine Liste der Zeitzonen-Identifikatoren finden Sie [hier](https://de.wikipedia.org/wiki/Liste_der_Zeitzonen-Datenbank-Zeitzonen#Liste).

## Alte Instanzen aus der Datenbank bereinigen {#clear-old-instances-db}

BunkerWeb speichert bekannte Instanzen in der Tabelle `bw_instances` (Primärschlüssel: `hostname`).
Wenn du häufig neu ausrollst, können alte Zeilen bestehen bleiben (z. B. Instanzen, die sich seit langer Zeit nicht mehr gemeldet haben) – dann möchtest du sie ggf. löschen.

!!! warning "Zuerst ein Backup"
    Bevor du die Datenbank manuell bearbeitest, erstelle ein Backup (SQLite-Volume snapshotten oder die Backup-Tools deiner DB-Engine verwenden).

!!! warning "Schreibende Komponenten stoppen"
    Um Race-Conditions beim Löschen zu vermeiden, stoppe (oder skaliere herunter) Komponenten, die Instanzen aktualisieren können
    (typischerweise Scheduler / Autoconf – abhängig von deinem Deployment), führe die Bereinigung aus und starte sie anschließend wieder.

### Tabelle und Spalten (Referenz)

Das Instanzmodell ist definiert als:

- Tabelle: `bw_instances`
- Primärschlüssel: `hostname`
- „Zuletzt gesehen“-Zeitstempel: `last_seen`
- Enthält außerdem:
  `name`, `port`, `listen_https`, `https_port`,
  `server_name`, `type`, `status`, `method`,
  `creation_date`

### 1 - Mit der Datenbank verbinden

Nutze den bestehenden Abschnitt [Datenbankzugriff](#access-database), um dich zu verbinden
(SQLite / MariaDB / PostgreSQL).

### 2 - Dry-Run: Veraltete Instanzen auflisten

Wähle ein Aufbewahrungsfenster (Beispiel: 90 Tage) und prüfe, was gelöscht würde.

=== "SQLite"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < datetime('now', '-90 days')
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

=== "MariaDB / MySQL"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 90 DAY)
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

=== "PostgreSQL"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < NOW() - INTERVAL '90 days'
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

### 3 - Veraltete Instanzen löschen

Nach der Prüfung kannst du die Zeilen löschen.

=== "SQLite"

    ```sql
    BEGIN;

    DELETE FROM bw_instances
    WHERE last_seen < datetime('now', '-90 days');

    COMMIT;
    ```

=== "MariaDB / MySQL"

    ```sql
    START TRANSACTION;

    DELETE FROM bw_instances
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 90 DAY);

    COMMIT;
    ```

=== "PostgreSQL"

    ```sql
    BEGIN;

    DELETE FROM bw_instances
    WHERE last_seen < NOW() - INTERVAL '90 days';

    COMMIT;
    ```

!!! tip "Löschen nach Hostname"
    Um eine bestimmte Instanz zu löschen, verwende ihren Hostname (Primärschlüssel).

    ```sql
    DELETE FROM bw_instances WHERE hostname = '<hostname>';
    ```

### 4 - Instanzen als geändert markieren (optional)

BunkerWeb verfolgt Instanzänderungen in der Tabelle `bw_metadata`
(`instances_changed`, `last_instances_change`).

Wenn die UI nach der manuellen Bereinigung nicht wie erwartet aktualisiert,
kannst du ein „Change Marker“-Update erzwingen:

=== "SQLite / PostgreSQL"

    ```sql
    UPDATE bw_metadata
    SET instances_changed = 1,
        last_instances_change = CURRENT_TIMESTAMP
    WHERE id = 1;
    ```

=== "MariaDB / MySQL"

    ```sql
    UPDATE bw_metadata
    SET instances_changed = 1,
        last_instances_change = NOW()
    WHERE id = 1;
    ```

### 5 - Speicherplatz freigeben (optional)

=== "SQLite"

    ```sql
    VACUUM;
    ```

=== "PostgreSQL"

    ```sql
    VACUUM (ANALYZE);
    ```

=== "MariaDB / MySQL"

    ```sql
    OPTIMIZE TABLE bw_instances;
    ```

## Web-UI {#web-ui}

Falls Sie Ihre UI-Anmeldeinformationen vergessen haben oder Probleme mit 2FA haben, können Sie sich mit der Datenbank verbinden, um wieder Zugriff zu erhalten.

### Auf die Datenbank zugreifen

=== "SQLite"

    === "Linux"

        Installieren Sie SQLite (Debian/Ubuntu):

        ```shell
        sudo apt install sqlite3
        ```

        Installieren Sie SQLite (Fedora/RedHat):

        ```shell
        sudo dnf install sqlite
        ```

    === "Docker"

        Holen Sie sich eine Shell in Ihren Scheduler-Container:

        !!! note "Docker-Argumente"
            - die Option `-u 0` ist, um den Befehl als Root auszuführen (obligatorisch)
            - die Optionen `-it` sind, um den Befehl interaktiv auszuführen (obligatorisch)
            - `<bunkerweb_scheduler_container>`: der Name oder die ID Ihres Scheduler-Containers

        ```shell
        docker exec -u 0 -it <bunkerweb_scheduler_container> bash
        ```

        Installieren Sie SQLite:

        ```bash
        apk add sqlite
        ```

    === "All-in-one"

        Holen Sie sich eine Shell in Ihren All-in-one-Container:

        !!! note "Docker-Argumente"
            - die Option `-u 0` ist, um den Befehl als Root auszuführen (obligatorisch).
            - die Optionen `-it` sind, um den Befehl interaktiv auszuführen (obligatorisch).
            - `bunkerweb-aio` ist der Standard-Container-Name; passen Sie ihn an, wenn Sie einen benutzerdefinierten Namen verwendet haben.

        ```shell
        docker exec -u 0 -it bunkerweb-aio bash
        ```

    Greifen Sie auf Ihre Datenbank zu:

    !!! note "Datenbankpfad"
        Wir gehen davon aus, dass Sie den Standard-Datenbankpfad verwenden. Wenn Sie einen benutzerdefinierten Pfad verwenden, müssen Sie den Befehl anpassen.
        Für All-in-one gehen wir davon aus, dass die Datenbank `db.sqlite3` im persistenten `/data`-Volume (`/data/db.sqlite3`) liegt.

    ```bash
    sqlite3 /var/lib/bunkerweb/db.sqlite3
    ```

    Sie sollten etwas Ähnliches wie das Folgende sehen:

    ```text
    SQLite version <VER> <DATE>
    Enter ".help" for usage hints.
    sqlite>
    ```

=== "MariaDB / MySQL"

    !!! note "Nur MariaDB / MySQL"
        Die folgenden Schritte sind nur für MariaDB / MySQL-Datenbanken gültig. Wenn Sie eine andere Datenbank verwenden, lesen Sie bitte die Dokumentation Ihrer Datenbank.

    !!! note "Anmeldeinformationen und Datenbankname"
        Sie müssen dieselben Anmeldeinformationen und denselben Datenbanknamen verwenden, die in der Einstellung `DATABASE_URI` verwendet werden.

    === "Linux"

        Greifen Sie auf Ihre lokale Datenbank zu:

        ```bash
        mysql -u <user> -p <database>
        ```

        Geben Sie dann das Passwort des Datenbankbenutzers ein, und Sie sollten auf Ihre Datenbank zugreifen können.

    === "Docker"

        Greifen Sie auf Ihren Datenbankcontainer zu:

        !!! note "Docker-Argumente"
            - die Option `-u 0` ist, um den Befehl als Root auszuführen (obligatorisch)
            - die Optionen `-it` sind, um den Befehl interaktiv auszuführen (obligatorisch)
            - `<bunkerweb_db_container>`: der Name oder die ID Ihres Datenbankcontainers
            - `<user>`: der Datenbankbenutzer
            - `<database>`: der Datenbankname

        ```shell
        docker exec -u 0 -it <bunkerweb_db_container> mysql -u <user> -p <database>
        ```

        Geben Sie dann das Passwort des Datenbankbenutzers ein, und Sie sollten auf Ihre Datenbank zugreifen können.

    === "All-in-one"

        Das All-in-One-Image enthält keinen MariaDB/MySQL-Server. Wenn Sie das AIO so konfiguriert haben, dass es eine externe MariaDB/MySQL-Datenbank verwendet (indem Sie die Umgebungsvariable `DATABASE_URI` setzen), sollten Sie sich direkt mit dieser Datenbank mit Standard-MySQL-Client-Tools verbinden.

        Die Verbindungsmethode wäre ähnlich wie im Tab "Linux" (wenn Sie sich vom Host verbinden, auf dem AIO läuft, oder von einem anderen Rechner) oder indem Sie einen MySQL-Client in einem separaten Docker-Container ausführen, der auf den Host und die Anmeldeinformationen Ihrer externen Datenbank abzielt.

=== "PostgreSQL"

    !!! note "Nur PostgreSQL"
        Die folgenden Schritte sind nur für PostgreSQL-Datenbanken gültig. Wenn Sie eine andere Datenbank verwenden, lesen Sie bitte die Dokumentation Ihrer Datenbank.

    !!! note "Anmeldeinformationen, Host und Datenbankname"
        Sie müssen dieselben Anmeldeinformationen (Benutzer/Passwort), denselben Host und denselben Datenbanknamen verwenden, die in der Einstellung `DATABASE_URI` verwendet werden.

    === "Linux"

        Greifen Sie auf Ihre lokale Datenbank zu:

        ```bash
        psql -U <user> -d <database>
        ```

        Wenn sich Ihre Datenbank auf einem anderen Host befindet, geben Sie den Hostnamen/die IP und den Port an:

        ```bash
        psql -h <host> -p 5432 -U <user> -d <database>
        ```

        Geben Sie dann das Passwort des Datenbankbenutzers ein, und Sie sollten auf Ihre Datenbank zugreifen können.

    === "Docker"

        Greifen Sie auf Ihren Datenbankcontainer zu:

        !!! note "Docker-Argumente"
            - die Option `-u 0` ist, um den Befehl als Root auszuführen (obligatorisch)
            - die Optionen `-it` sind, um den Befehl interaktiv auszuführen (obligatorisch)
            - `<bunkerweb_db_container>`: der Name oder die ID Ihres Datenbankcontainers
            - `<user>`: der Datenbankbenutzer
            - `<database>`: der Datenbankname

        ```shell
        docker exec -u 0 -it <bunkerweb_db_container> psql -U <user> -d <database>
        ```

        Wenn die Datenbank an anderer Stelle gehostet wird, fügen Sie die Optionen `-h <host>` und `-p 5432` entsprechend hinzu.

    === "All-in-one"

        Das All-in-One-Image enthält keinen PostgreSQL-Server. Wenn Sie das AIO so konfiguriert haben, dass es eine externe PostgreSQL-Datenbank verwendet (indem Sie die Umgebungsvariable `DATABASE_URI` setzen), sollten Sie sich direkt mit dieser Datenbank mit Standard-PostgreSQL-Client-Tools verbinden.

        Die Verbindungsmethode wäre ähnlich wie im Tab "Linux" (wenn Sie sich vom Host verbinden, auf dem AIO läuft, oder von einem anderen Rechner) oder indem Sie einen PostgreSQL-Client in einem separaten Docker-Container ausführen, der auf den Host und die Anmeldeinformationen Ihrer externen Datenbank abzielt.

### Maßnahmen zur Fehlerbehebung

!!! info "Tabellenschema"
    Das Schema der Tabelle `bw_ui_users` ist wie folgt:

    | Feld          | Typ                                                 | Null | Schlüssel | Standard | Extra |
    | ------------- | --------------------------------------------------- | ---- | --------- | -------- | ----- |
    | username      | varchar(256)                                        | NO   | PRI       | NULL     |       |
    | email         | varchar(256)                                        | YES  | UNI       | NULL     |       |
    | password      | varchar(60)                                         | NO   |           | NULL     |       |
    | method        | enum('ui','scheduler','autoconf','manual','wizard') | NO   |           | NULL     |       |
    | admin         | tinyint(1)                                          | NO   |           | NULL     |       |
    | theme         | enum('light','dark')                                | NO   |           | NULL     |       |
    | language      | varchar(2)                                          | NO   |           | NULL     |       |
    | totp_secret   | varchar(256)                                        | YES  |           | NULL     |       |
    | creation_date | datetime                                            | NO   |           | NULL     |       |
    | update_date   | datetime                                            | NO   |           | NULL     |       |

=== "Benutzernamen abrufen"

    Führen Sie den folgenden Befehl aus, um Daten aus der Tabelle `bw_ui_users` zu extrahieren:

    ```sql
    SELECT * FROM bw_ui_users;
    ```

    Sie sollten etwas Ähnliches wie das Folgende sehen:

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | -------- | ----- | -------- | ------ | ----- | ----- | ----------- | ------------- | ----------- |
    | ***      | ***   | ***      | manual | 1     | light | ***         | ***           | ***         |

=== "Admin-Benutzerpasswort aktualisieren"

    Zuerst müssen Sie das neue Passwort mit dem bcrypt-Algorithmus hashen.

    Installieren Sie die Python-bcrypt-Bibliothek:

    ```shell
    pip install bcrypt
    ```

    Generieren Sie Ihren Hash (ersetzen Sie `meinpasswort` durch Ihr eigenes Passwort):

    ```shell
    python3 -c 'from bcrypt import hashpw, gensalt ; print(hashpw(b"""meinpasswort""", gensalt(rounds=10)).decode("utf-8"))'
    ```

    Sie können Ihren Benutzernamen / Ihr Passwort aktualisieren, indem Sie diesen Befehl ausführen:

    ```sql
    UPDATE bw_ui_users SET password = '<password_hash>' WHERE admin = 1;
    ```

    Wenn Sie Ihre Tabelle `bw_ui_users` nach diesem Befehl erneut überprüfen:

    ```sql
    SELECT * FROM bw_ui_users WHERE admin = 1;
    ```

    Sie sollten etwas Ähnliches wie das Folgende sehen:

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | -------- | ----- | -------- | ------ | ----- | ----- | ----------- | ------------- | ----------- |
    | ***      | ***   | ***      | manual | 1     | light | ***         | ***           | ***         |

    Sie sollten nun in der Lage sein, die neuen Anmeldeinformationen zu verwenden, um sich in der Web-UI anzumelden.

=== "2FA-Authentifizierung für Admin-Benutzer deaktivieren"

    Sie können 2FA deaktivieren, indem Sie diesen Befehl ausführen:

    ```sql
    UPDATE bw_ui_users SET totp_secret = NULL WHERE admin = 1;
    ```

    Wenn Sie Ihre Tabelle `bw_ui_users` nach diesem Befehl erneut überprüfen:

    ```sql
    SELECT * FROM bw_ui_users WHERE admin = 1;
    ```

    Sie sollten etwas Ähnliches wie das Folgende sehen:

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | -------- | ----- | -------- | ------ | ----- | ----- | ----------- | ------------- | ----------- |
    | ***      | ***   | ***      | manual | 1     | light | NULL        | ***           | ***         |

    Sie sollten sich nun nur mit Ihrem Benutzernamen und Passwort ohne 2FA in der Web-UI anmelden können.

=== "2FA-Wiederherstellungscodes aktualisieren"

    Die Wiederherstellungscodes können auf Ihrer **Profilseite** der Web-UI unter dem Tab `Sicherheit` aktualisiert werden.

=== "Konfiguration und anonymisierte Protokolle exportieren"

    Verwenden Sie die **Support-Seite** in der Web-UI, um schnell Konfigurationen und Protokolle zur Fehlerbehebung zu sammeln.

    - Öffnen Sie die Web-UI und gehen Sie zur Support-Seite.
    - Wählen Sie den Geltungsbereich: Exportieren Sie die globalen Einstellungen oder wählen Sie einen bestimmten Dienst aus.
    - Klicken Sie, um das Konfigurationsarchiv für den ausgewählten Geltungsbereich herunterzuladen.
    - Laden Sie optional Protokolle herunter: Die exportierten Protokolle werden automatisch anonymisiert (alle IP-Adressen und Domains werden maskiert).

### Plugin hochladen

Es ist möglicherweise nicht möglich, ein Plugin in bestimmten Situationen von der Benutzeroberfläche hochzuladen:

-   Fehlendes Paket zur Verwaltung komprimierter Dateien in Ihrer Integration, in diesem Fall müssen Sie die erforderlichen Pakete hinzufügen
-   Safari-Browser: Der "Sicherheitsmodus" kann Sie daran hindern, ein Plugin hinzuzufügen. Sie müssen die erforderlichen Änderungen auf Ihrem Computer vornehmen
