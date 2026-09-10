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

## Hintergrundjobs laufen nie {#background-jobs}

Seit 1.7 versendet der Scheduler Jobs über die API an einen Celery-Worker. Fehlt die API, der Worker
oder der Job-Broker, fällt der Stack ohne deutlichen Fehler aus: Der Scheduler generiert weiter
Konfigurationen und die Instanzen bleiben gesund, aber es werden weder Zertifikate erneuert noch
Sperrlisten aktualisiert oder Backups erstellt.

Erkennbar ist das am **letzten Lauf**, der auf der **Jobs**-Seite der Web-UI oder in der API nicht
mehr fortschreitet:

```bash
# Container-Stacks: API-Dienstname; unter Linux: http://127.0.0.1:8888
curl -H "Authorization: Bearer $API_TOKEN" http://bw-api:8888/jobs
```

### Der Worker läuft nicht

Nach einem Upgrade von 1.6 fehlt häufig der Worker: Das bloße Ändern der Image-Tags ergänzt weder
`bw-api` noch `bw-worker` oder `bw-jobs-broker`. Siehe [Upgrade-Hinweise](upgrading.md#breaking-changes);
setzen Sie den Stack anhand der Referenz Ihrer Integration neu auf.

=== "Docker"

    ```shell
    docker compose ps bw-api bw-worker bw-jobs-broker
    docker compose logs bw-worker
    ```

    „No such service“ bedeutet, dass der Stack vor 1.7 entstand. Ergänzen Sie die drei Dienste,
    `API_URL`, `API_TOKEN` und `CELERY_BROKER_URL` und erstellen Sie die Container neu.

=== "Linux"

    ```shell
    systemctl is-enabled bunkerweb-worker; systemctl is-active bunkerweb-worker
    journalctl -u bunkerweb-worker --no-pager -n 100
    ```

    `bunkerweb-worker` ist eine neue Unit in 1.7, die das Paket auf jedem Host installiert.
    Die Antwort lautet daher `enabled`/`disabled`, nie „not found“.

    **Prüfen Sie dies auf dem Host mit `bunkerweb-scheduler`.** Dort sind `enabled` und `active`
    richtig. `systemctl enable --now bunkerweb-worker` aktiviert ihn und zieht die Broker-Unit
    automatisch nach. Bleibt er trotz aktivem Zustand untätig, prüfen Sie als Nächstes den Broker.

    **Auf einem reinen BunkerWeb-Instanzknoten** — einer `--worker`-Installation im Sinne des
    Installers, also „Instanz ohne Control Plane“ — ist `disabled` richtig und beabsichtigt:
    Dieser Host besitzt keine Jobs. Aktivieren Sie ihn dort nicht.

    !!! info "Upgrades vor 1.7.0 können ihn auf einem reinen Instanzknoten aktiviert gelassen haben"
        Das Paket entscheidet anhand von `WORKER_MODE`/`MANAGER_MODE`/`SERVICE_*` in seiner eigenen
        Umgebung über die Host-Rolle, und kein Upgrade setzt diese Variablen: weder ein direktes
        `apt install bunkerweb=...` noch `install-bunkerweb.sh`, dessen Upgrade-Pfad vorher endet.
        Seit 1.7.0 ermittelt das Paket die Topologie selbst: Es liest den bei der letzten deklarierten
        Installation hinterlegten Installationstyp, und auf einem Host, der älter als diese Markierung
        ist, fällt es zurück auf die Frage „läuft auf diesem Host `bunkerweb-scheduler`?“. Auf einem
        Knoten, der das verneint, wird weder ein Broker noch `bunkerweb-worker` aktiviert. Frühere
        Upgrades behandelten einen solchen Host als Einzelinstallation und **aktivierten und starteten**
        `bunkerweb-worker` sowie die erste gefundene Redis-Unit — auf einem Knoten wie diesem das
        Distributions-`redis-server` (oder `valkey`/`redis`), da dort kein `bunkerweb-broker`
        bereitgestellt wird. Ist Ihr Knoten von einem solchen Upgrade betroffen, räumen Sie ihn
        einmalig mit den folgenden Befehlen auf.

        Für Jobs ist das zunächst harmlos: Der Worker fällt auf `redis://127.0.0.1:6379/0` zurück,
        an das keine Control Plane Aufträge sendet. Eine Ausnahme besteht, wenn `CELERY_BROKER_URL`
        dieses Knotens auf einen **erreichbaren entfernten** Broker gesetzt wurde, etwa aus einer
        `--broker-url`-Installation kopiert oder von Hand. Dann übernimmt der verbliebene Worker
        tatsächlich Jobs. Eine vom Installer bereitgestellte URL tut dies nicht: Der dedizierte Broker
        bindet `127.0.0.1`, und die URL zeigt dort auf den eigenen Loopback des Knotens. Der Worker
        wiederholt lediglich erfolglose Verbindungsversuche. Wenn er weg soll:
        `systemctl disable --now bunkerweb-worker`. Ab 1.7.0 genügt das einmal — das nächste Upgrade
        sieht einen Host ohne Scheduler und lässt ihn in Ruhe.

        **Lassen Sie die Redis-Unit unangetastet, solange nicht feststeht, dass sie kein WAF-Datastore
        ist.** `USE_REDIS` und `REDIS_HOST` sind *flottenweite* Einstellungen auf der Control Plane:
        Web-UI → **Globale Einstellungen** → Redis oder `/etc/bunkerweb/variables.env` des
        Scheduler-Hosts. Die eigene `variables.env` des Instanzknotens ignoriert diese Schlüssel;
        eine Suche darin beweist nichts. Nach mindestens einem Push enthält jedoch die gerenderte
        Konfiguration die Werte, sodass sie lokal lesbar sind:

        ```bash
        grep -E '^(USE_REDIS|REDIS_HOST)=' /etc/nginx/variables.env
        ```

        Vor dem ersten Push verwendet der Knoten seine Start-Standardwerte; nur die Control Plane
        kennt die Flottenwerte. Prüfen Sie diese dort. Zeigt `REDIS_HOST` auf **diesen** Host — etwa
        dessen LAN-Adresse, nicht zwingend `127.0.0.1` —, hält er gemeinsame Sperren und
        Ratenlimit-Zähler. Sein Abschalten löscht diese und beendet ihre gemeinsame Nutzung.
        Erst nach dieser Prüfung: `systemctl disable --now redis-server` (oder `valkey` oder `redis`).

        Auf einem solchen Host kann der verbliebene Worker endlos `NOAUTH` protokollieren, wenn
        der Datastore auf `127.0.0.1:6379` passwortgeschützt ist. Das ist dessen untätiger Worker,
        keine defekte Job-Pipeline. Der folgende Abschnitt diagnostiziert den **Scheduler**-Host.

### Der Broker lehnt die Verbindung ab (`NOAUTH`)

Ist der Broker passwortgeschützt, aber `CELERY_BROKER_URL` enthält keine Zugangsdaten, antwortet
er mit `NOAUTH Authentication required`. Der Worker bleibt `active`, ohne Aufträge zu übernehmen;
`POST /jobs/dispatch` antwortet mit `502`.

```bash
journalctl -u bunkerweb-worker | grep -i 'NOAUTH\|AuthenticationError'   # Linux
docker compose logs bw-worker | grep -i 'NOAUTH\|AuthenticationError'    # Docker
```

Prüfen Sie zuerst, dass der Endpunkt ein dedizierter Job-Broker mit `maxmemory-policy noeviction`
ist. Dient Port `6379` einem WAF-Datastore mit Schlüsselverdrängung, stellen Sie über den
[Linux-Installer](integrations.md#einfaches-installationsskript) einen separaten Broker bereit oder
konfigurieren Sie selbst einen. Verwenden Sie dann dessen tatsächliche Adresse und Port.
Die Behebung von `NOAUTH` allein schützt Jobs und Leases nicht vor Verdrängung.

Geben Sie dem Broker danach eigene Zugangsdaten. Unter Linux genügt ein Eintrag in
`/etc/bunkerweb/variables.env`, weil Worker und API diese Datei vor ihrer eigenen Umgebung lesen.
In Container-Stacks setzen Sie den Wert auf beiden Diensten:

```bash
CELERY_BROKER_URL=redis://:<password>@127.0.0.1:6379/0     # Linux: dediziertes Distributions-Redis mit noeviction
CELERY_BROKER_URL=redis://:<password>@bw-jobs-broker:6379/0 # Container-Stack
```

Prüfen Sie vor Änderungen `/etc/bunkerweb/broker.conf`. Existiert diese Datei, hat der Installer
einen dedizierten `bunkerweb-broker` bereitgestellt, und `CELERY_BROKER_URL` zeigt bereits **mit
Passwort** darauf. Bearbeiten Sie die vorhandene Zeile, statt eine weitere anzulegen, und lesen Sie
den Port daraus: `6380` ist nur der Standard; bei Belegung sucht der Installer aufwärts weiter.
Ohne diese Datei gilt Ihr gesetzter Wert oder, falls keiner gesetzt ist, unter Linux für Worker und
API `redis://127.0.0.1:6379/0`; dann passt die obige Lösung. Der Installer provisioniert den Broker
nur bei einer frischen Installation oder einem Upgrade mit `requirepass` oder verdrängendem
`maxmemory`. Ein Upgrade mit unverändertem Distributions-Redis oder eine Installation mit
`--no-broker` beziehungsweise `--broker-url` besitzt daher keine `broker.conf`.

Starten Sie danach beide neu: `systemctl restart bunkerweb-worker bunkerweb-api`, oder erstellen
Sie `bw-worker` und `bw-api` neu.

!!! warning "Der Broker ist nicht der WAF-Datastore"
    Der Job-Broker benötigt `maxmemory-policy noeviction`: Er hält die Leases, die gleichzeitige
    Konfigurations-Pushes zweier Worker verhindern. Diese Schlüssel haben eine TTL und könnten durch
    jede `volatile-*`-Policy mitten im Betrieb verdrängt werden. Ein Datastore ist dagegen üblicherweise
    begrenzt und darf Schlüssel verdrängen: Flüchtige Zähler zu verlieren ist günstiger, als
    Schreibvorgänge abzulehnen. `maxmemory-policy` gilt pro Server, nie pro Datenbank. Unterschiedliche
    Datenbanknummern desselben Servers trennen die Rollen **nicht**. Siehe
    [Upgrade-Hinweise](upgrading.md#breaking-changes).

## Eine registrierte Instanz startet nicht {#lost-instance-credential}

Nach dem Einlösen eines Registrierungscodes speichert eine Instanz ihre Zugangsdaten in
`/var/lib/bunkerweb/instance-credential.json`. Danach akzeptiert sie **nur** diese und fällt nie auf
das gemeinsame `API_TOKEN` zurück. Geht die Datei verloren, während die Registrierungsmarkierung
erhalten bleibt, verweigert sie den Start, statt ohne Verbindung zur Control Plane hochzufahren:

```
This instance was enrolled but its credential is gone (/var/lib/bunkerweb/instance-credential.json
is missing or contains no usable credential) [...] Refusing to start.
```

Der Auslöser ist bewusst eng gefasst: Die Markierung existiert, nutzbare Zugangsdaten fehlen. Die
Datei wurde gelöscht, gekürzt, bei der Wiederherstellung ausgelassen oder enthält keine Zugangsdaten
mehr. Eine vorhandene, aber *unlesbare* Datei — etwa nach einem Upgrade im Besitz von root — lässt
die Frage offen: Die Instanz startet, verweigert jedoch alle Pushes, bis die Dateirechte korrigiert
sind. Stellen Sie dann die Rechte wieder her, statt sie neu zu registrieren.

Zwei benachbarte Fälle starten normal und scheitern erst bei der Control Plane: ein Container ganz
**ohne** `/data`-Volume (Markierung und Zugangsdaten gehen gemeinsam verloren; er startet als neue,
unregistrierte Instanz) und eine Wiederherstellung aus einem Snapshot von *vor* der Registrierung
(beide Dateien fehlen). Die Instanz meldet je Aufruf lediglich `can't validate API token from IP …`,
ohne die verlorene Registrierung zu nennen. Die Diagnose liegt auf der Control Plane.

Zwei Wege beheben die Startverweigerung:

- **Registrierung beibehalten**: Erstellen Sie einen neuen Code über die Schlüsselschaltfläche auf
  der **Instanzen**-Seite oder `POST /instances/{hostname}/enroll` und geben Sie ihn beim nächsten
  Start als `INSTANCE_ENROLLMENT_CODE` an.
- **Zum gemeinsamen Token zurückkehren**: Beide Seiten müssen geändert werden. Löschen Sie auf
  der Instanz `/var/lib/bunkerweb/instance-enrolled` **und** `instance-credential.json`. Eine leere
  oder gekürzte Restdatei lässt die Instanz jedes Token verweigern, auch das gemeinsame. Damit startet
  sie auf `API_TOKEN`, aber die Control Plane verwendet weiterhin die gespeicherten individuellen
  Zugangsdaten und jeder Push wird abgelehnt. Leeren Sie diese auch am Eintrag:

    ```bash
    curl -X PATCH -H "Authorization: Bearer $API_TOKEN" -H 'Content-Type: application/json' \
      -d '{"credential": ""}' http://bw-api:8888/instances/<hostname>
    ```

    Ein leeres `credential` entfernt den gespeicherten Wert unabhängig von der Methode der Instanz.
    Die Control Plane verwendet wieder `API_TOKEN`. Das geht nur über die API: Die **Instanzen**-Seite
    bietet Rotation und Widerruf, kein Leeren.

    **Ein Widerruf wird dadurch nicht aufgehoben.** Wurde die Instanz zuerst widerrufen, bleibt das
    Leeren wirkungslos; der Eintrag bleibt gesperrt. Zwei Dinge heben den Widerruf auf: ein neuer
    Registrierungscode oder, bei einem eigenen deklarierten Token (`BUNKERWEB_INSTANCE_API_TOKEN[_n]`
    in der gruppierten Form `BUNKERWEB_INSTANCE_HOST_n`, nicht in der flachen Liste
    `BUNKERWEB_INSTANCES`), der nächste Konfigurationsspeichervorgang des Schedulers. Dieser übernimmt
    das Token erneut aus der Umgebung und hebt den Widerruf auf. Das deklarierte Token muss sich
    **vom globalen `API_TOKEN` unterscheiden**. Das gemeinsame Token erneut zu deklarieren zählt
    nicht: Es gibt weder Aufhebung noch Logmeldung. Bei tatsächlicher Aufhebung protokolliert der
    Scheduler dies. Für alle anderen Einträge ist erneutes Registrieren der einzige Weg.
    Ohne API-Aufruf können **UI- oder API-registrierte** Instanzen auf der **Instanzen**-Seite
    (oder mit `DELETE /instances/{hostname}`) gelöscht und neu angelegt werden. **Per Umgebung**
    deklarierte Instanzen (`BUNKERWEB_INSTANCES`) können aus der Liste entfernt, nach einem
    Konfigurationsspeichervorgang des Schedulers erneut deklariert werden. Dieser löscht den Eintrag
    einschließlich UI-seitigem TLS-Pinning und Namen. Beide Wege verwerfen mehr als `PATCH`.

    Von Autoconf, Kubernetes oder Swarm **entdeckte** Instanzen sind hiervon nie betroffen: Die
    Control Plane erzeugt für Orchestrator-Einträge keine individuellen Zugangsdaten.

    **Erneutes Registrieren ist der unterstützte und bevorzugte Wiederherstellungsweg.**

!!! tip "Persistentes `/data` für die Instanz"
    Deshalb mounten die Referenzstacks `bw-instance-data` auf dem Dienst `bunkerweb`. Ohne Volume
    verwirft jedes `docker compose down` gefolgt von `up` die Zugangsdaten. Die Instanz startet
    unregistriert und ohne Warnung; fehlgeschlagene Pushes zeigen das Problem auf der Control Plane.
    Siehe [Instanzregistrierung](web-ui.md#instance-enrollment).

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

### Auf die Datenbank zugreifen {#access-database}

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
        Für All-in-one gehen wir davon aus, dass die Datenbank `db.sqlite3` im persistenten `/data/lib`-Volume (`/data/lib/db.sqlite3`) liegt.

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
