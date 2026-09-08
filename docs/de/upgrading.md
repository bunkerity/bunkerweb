# Aufrüsten

!!! warning "Ein Neuerstellen des Web-UI-Containers ohne persistentes `/data` kostet die 2FA"
    `docker compose down` und anschließend `up` ersetzt das Dateisystem des Containers `bw-ui`, und dort liegen die Schlüssel, die jedes gespeicherte TOTP-Geheimnis entschlüsseln. Ohne ein Volume auf `/data` wird die Admin-Registrierung verworfen und alle Benutzer müssen sich neu registrieren. Prüfen Sie **vor** dem Upgrade, dass Ihr `bw-ui`-Dienst eines hat — siehe [2FA ist nach dem Neuerstellen des Containers verloren](web-ui.md).

## Upgrade von 1.6.X

### Wichtige Änderungen {#breaking-changes}

!!! warning "`REDIS_SSL_VERIFY` jetzt standardmäßig `yes`"

    Der Redis/Valkey-Client akzeptierte bisher **jedes** Zertifikat, wenn `REDIS_SSL` aktiviert war: Der dokumentierte Standardwert für `REDIS_SSL_VERIFY` war `yes`, der ausgelieferte Standardwert jedoch `no`, sodass TLS ausgehandelt wurde, ohne den Server jemals zu verifizieren. Der Code entspricht jetzt der Dokumentation.

    Dies betrifft Sie nur, wenn **alle** folgenden Bedingungen zutreffen: `REDIS_SSL: "yes"`, der Redis- oder Valkey-Server präsentiert ein selbstsigniertes oder anderweitig nicht vertrauenswürdiges Zertifikat, und Sie haben `REDIS_SSL_VERIFY` nie explizit gesetzt. In diesem Fall schlägt die Verbindung nach dem Upgrade fehl.

    Vertrauen Sie entweder der CA des Servers, oder stellen Sie das vorherige Verhalten explizit wieder her:

    ```yaml
    REDIS_SSL_VERIFY: "no"
    ```

!!! warning "Der Job-Broker ist jetzt eine separate Instanz vom WAF-Datastore"

    BunkerWeb verwendet Redis/Valkey für zwei voneinander unabhängige Aufgaben, die widersprüchliche Einstellungen benötigen:

    | Rolle | Einstellung | Warum |
    |------|---------|-----|
    | **Job-Broker** (`CELERY_BROKER_URL`) | `maxmemory-policy noeviction` | Er hält die Correctness-Leases, die verhindern, dass zwei Worker gleichzeitig Configs pushen. Es sind Schlüssel *mit* TTL, sodass jede `volatile-*`-Policy sie mitten im Flug verwerfen kann. |
    | **WAF-Datastore** (`USE_REDIS` / `REDIS_*`) | `maxmemory-policy volatile-lru` *(empfohlen)* | Begrenzen Sie den Speicher und erlauben Sie das Verwerfen von Schlüsseln: Flüchtige Zähler zu verlieren ist günstiger, als Schreibvorgänge abzulehnen. Das ist keine Pflicht — ein unbegrenztes Redis verwirft nichts und ist ebenfalls geeignet —, aber die übliche Form eines Datastores, die der Broker nicht haben darf. |

    `maxmemory-policy` ist eine Server-, nie eine Datenbank-Einstellung, daher kann eine Instanz nicht
    beides — die beiden Rollen auf unterschiedliche Datenbanknummern desselben Servers zu legen, trennt sie nicht.
    Die Stacks mit mehreren Containern betreiben einen dedizierten `bw-jobs-broker`; das AIO-Image
    überwacht einen separaten Loopback-Broker auf Port `6380`, und der Linux-Installer kann
    einen Dienst `bunkerweb-broker` ab Port `6380` bereitstellen.

    **Wenn Sie mit dem Installer aufrüsten, wird dies für Sie erledigt.** Er stellt den Broker bereit,
    schreibt `CELERY_BROKER_URL` in `/etc/bunkerweb/variables.env` und lässt ein unverändertes
    Distro-Redis unangetastet (ohne gesetztes `maxmemory` wird nie etwas verworfen, es war also nie kaputt).

    **Wenn Sie mit reinem `apt`/`dnf` aufrüsten und von Hand ein Redis-Passwort gesetzt haben**, sind Sie
    betroffen, und Hintergrund-Jobs schlagen bereits fehl — stillschweigend. Worker und API greifen
    standardmäßig auf ein unauthentifiziertes `redis://127.0.0.1:6379/0` zu, sodass ein passwortgeschützter
    Server mit `NOAUTH` antwortet: `POST /jobs/dispatch` liefert 502, und der Worker bleibt `active`, ohne
    etwas zu konsumieren. In diesem Zustand gibt es keine Zertifikatserneuerung, keine Sperrlisten-Aktualisierung
    und kein Backup. Prüfen Sie darauf mit:

    ```bash
    journalctl -u bunkerweb-worker | grep -i 'NOAUTH\|AuthenticationError'
    ```

    Dieselbe Diagnose, auch für Container, finden Sie unter
    [Hintergrundjobs laufen nie](troubleshooting.md#background-jobs).

    **Prüfen Sie vor der Authentifizierungskorrektur, dass dies ein dedizierter Job-Broker ohne Schlüsselverdrängung ist.**
    Dient Port `6379` einem WAF-Datastore mit Schlüsselverdrängung, stellen Sie über den
    [Linux-Installer](integrations.md#einfaches-installationsskript) einen separaten Broker bereit oder
    konfigurieren Sie selbst einen mit `maxmemory-policy noeviction`. Verwenden Sie dessen tatsächliche
    Adresse und Port. Das folgende Beispiel mit `6379` gilt nur für ein dediziertes Distributions-Redis,
    das für Jobs konfiguriert ist. Ein Passwort macht einen verdrängenden Datastore nicht zu einem
    sicheren Broker.

    Geben Sie dem Broker danach eigene Anmeldeinformationen in `/etc/bunkerweb/variables.env`
    — ein Schreibvorgang deckt beide Komponenten ab, da Worker und API beide diese Datei vor
    ihrer eigenen lesen:

    ```bash
    CELERY_BROKER_URL=redis://:<password>@127.0.0.1:6379/0
    ```

    ```bash
    systemctl restart bunkerweb-worker bunkerweb-api
    ```

    TLS wird über das Schema `rediss://` unterstützt. **Setzen Sie `ssl_cert_reqs` explizit** — eine
    bloße `rediss://`-URL handelt TLS aus, ohne das Zertifikat des Servers zu verifizieren:

    ```bash
    CELERY_BROKER_URL=rediss://:<password>@broker.example.com:6379/0?ssl_cert_reqs=required
    ```

!!! warning "Der Celery-Worker war bei manchen Installationen nicht aktiviert"

    `bunkerweb-worker` führt jeden vom Scheduler versendeten Job aus. Bei Installationen, bei denen der
    Installer den Dienststart verzögerte — `--redis`, eine externe Datenbank, CrowdSec, benutzerdefinierte
    DNS-Resolver und jede `--manager`-Installation — wurde er nie aktiviert, sodass der Stack gesund
    hochfuhr und überhaupt keine Hintergrund-Jobs ausführte. Der Installer aktiviert ihn jetzt auf diesen
    Pfaden zusammen mit dem Scheduler. Prüfen Sie nach dem Upgrade:

    ```bash
    systemctl is-enabled bunkerweb-worker; systemctl is-active bunkerweb-worker
    ```

    Falls der Worker fehlt oder untätig bleibt, siehe
    [Hintergrundjobs laufen nie](troubleshooting.md#background-jobs).

!!! warning "Die Docker-, Autoconf- und Kubernetes-Stacks benötigen drei neue Komponenten"

    Ein 1.6-Stack enthält `bunkerweb` und `bw-scheduler`. 1.7 benötigt außerdem eine **API**, einen
    **Worker** und einen **Job-Broker**: `bw-api`, `bw-worker` und `bw-jobs-broker` in Compose-Stacks,
    `bunkerweb-api`, `bunkerweb-worker` und `bunkerweb-jobs-broker` in Kubernetes-Stacks. Der Worker
    führt alle Jobs aus, die zuvor im Scheduler-Prozess liefen; der Broker überträgt die Aufträge.
    Jede BunkerWeb-Komponente erhält `API_URL`, `API_TOKEN` und `CELERY_BROKER_URL`, und die
    Instanz `bunkerweb` erhält ein Volume `bw-instance-data` auf `/data`.

    Nur die Image-Tags zu ändern hinterlässt einen Stack, der als gesund erscheint und **keinen
    einzigen Hintergrundjob** ausführt — keine Zertifikatserneuerung, keine Listenaktualisierung,
    kein Backup ([Diagnose](troubleshooting.md#background-jobs)). Setzen Sie ihn anhand des
    1.7-Referenzstacks Ihrer Integration neu auf:
    [Docker](integrations.md#docker), [Docker autoconf](integrations.md#docker-autoconf),
    [Kubernetes](integrations.md#kubernetes) oder [Swarm](integrations.md#swarm). Alle Stacks liegen
    im Repository unter
    [`misc/integrations`](https://github.com/bunkerity/bunkerweb/tree/v1.7.0-beta/misc/integrations),
    mit einer Datei pro Datenbank-Engine.

    **Das All-In-One-Image ist nicht betroffen**: Es überwacht API und Worker im selben Container
    und vermittelt deren Jobs über ein dediziertes eingebettetes Redis. Der Austausch des Containers
    unter Beibehaltung von `/data` reicht für das Upgrade aus; weitere Komponenten sind nicht nötig.

!!! warning "PostgreSQL: Bei Datenbanken von vor 1.6.0 zuerst auf 1.6.x wechseln"

    Eine **PostgreSQL**-Datenbank, die vor 1.6.0 erstellt oder zuletzt migriert wurde, kann nicht
    direkt auf 1.7 wechseln. Die gesamte Migrationskette läuft in einer einzigen Transaktion. Die
    Revision für 1.6.1 öffnet eine *zweite* Verbindung, um eine Constraint einer Tabelle zu löschen,
    auf der die erste Verbindung bereits eine exklusive Sperre hält. Die zweite Verbindung wartet
    auf deren Freigabe beim Ende der Migration; diese kann wiederum erst enden, wenn die zweite
    Verbindung fertig ist. PostgreSQL erkennt keinen Deadlock, weil der Sperrinhaber auf einen
    Client-Socket statt auf eine Sperre wartet. Es gibt weder Timeout noch Fehler: Der Scheduler
    beendet seinen Start einfach nie.

    Betroffen sind Installationen, die noch nie eine 1.6.x-Version ausgeführt haben. Lesen Sie den
    Versionsstempel mit:

    ```bash
    psql -d <database> -c 'SELECT version_num FROM alembic_version;'
    ```

    `f85e36780e55` ist die Revision von 1.6.0; alle vorher erreichten Revisionen sind betroffen.
    Installieren Sie zuerst 1.6.14 und lassen Sie den Scheduler starten und seine Migration
    abschließen. Wechseln Sie danach auf 1.7. SQLite, MariaDB und MySQL sind nicht betroffen:
    Nur die PostgreSQL-Revision öffnet diese zweite Verbindung.

!!! danger "Location-Werte mit Leerraum, `;`, `{` oder `}` werden jetzt abgelehnt — mit Rückfall auf `/`"

    `REVERSE_PROXY_URL`, `GRPC_URL` und `REDIRECT_FROM` akzeptierten in 1.6 beliebige Werte. Jetzt
    lehnen sie Zeichen ab, mit denen ein Wert aus dem gerenderten `location`-Block ausbrechen könnte.
    Ein führendes `~ `, `~* `, `^~ ` oder `= ` bleibt als NGINX-Location-Modifikator zulässig.
    Dieses eine Leerzeichen ist jedoch der einzige erlaubte Leerraum, auch am Ende des Werts;
    `;`, `{` und `}` sind immer verboten.

    Ein abgelehnter Wert bricht das Rendern nicht ab. BunkerWeb protokolliert eine Warnung
    (`Ignoring variable REVERSE_PROXY_URL_1 : ...`) und behält den Standardwert der Einstellung bei:
    bei allen drei `/`. Die Regel gilt damit für die Wurzel der Website statt für den konfigurierten
    Pfad. Ein häufiger Fall ist eine Regex-Location mit einem Quantifizierer wie `^/v[0-9]{1,3}/`.

    Suchen Sie vor dem Upgrade in Ihren Compose-Dateien, `variables.env`, Container-Labels und
    Kubernetes-Annotationen:

    ```bash
    grep -rInE '(REVERSE_PROXY_URL|GRPC_URL|REDIRECT_FROM)[A-Z_0-9]*[:=].*[;{}]' .
    ```

    Das findet Werte mit `;`, `{` und `}`, die typischen Stolperstellen einer 1.6-Konfiguration.
    Leerzeichen sind ebenfalls verboten, außer dem einen zwischen einem führenden `~`, `~*`, `^~`
    oder `=` und dem Pfad. Prüfen Sie diese wenigen Fälle von Hand.

    Die Suche ist bewusst auf Dateien begrenzt. Werte aus Web-UI oder API liegen in der Datenbank
    und werden weder beim Rendern noch beim Speichern einer anderen Einstellung erneut validiert.
    Sie funktionieren deshalb nach dem Upgrade weiter, **ohne jeden Hinweis**. Sobald Sie diesen
    Dienst bearbeiten, unterscheiden sich drei Fälle:

    - **JSON-Nutzdaten mit Einstellungen werden vollständig validiert.** `POST`/`PATCH /services`
      und `PATCH /global_settings` prüfen **jeden** übergebenen Schlüssel, auch unveränderte. Ein
      Lesen-Ändern-Zurückschreiben, das den gespeicherten Wert erneut sendet, wird daher mit `400`
      und dem Schlüsselnamen abgelehnt. Die Schlüssel tragen hier kein Dienstpräfix:
      `REVERSE_PROXY_URL_1`, nicht `www.example.com_REVERSE_PROXY_URL_1`. Bei `MULTISITE=no` sind
      diese drei Einstellungen global; betroffen ist dann `PATCH /global_settings`.
    - **Beim Speichern der gesamten Konfiguration werden unveränderte Schlüssel übersprungen**:
      auf den Dienst- und globalen Einstellungsseiten der Web-UI, in Autoconf, beim Umgebungsabgleich
      des Schedulers und bei `PUT /global_settings/config`. Ein unveränderter gespeicherter Wert wird
      nicht geprüft; bloßes Öffnen und Speichern der Dienstseite deckt das Problem **nicht** auf.
      Werte aus *Labels* oder `variables.env` sind anders: Autoconf und Configurator lesen ihre
      Quelle bei jedem Durchlauf vollständig neu. Ungültige Werte werden mit einer Logmeldung
      verworfen und fallen auf den Standard zurück — deshalb ist die obige Suche wichtig.
    - **Wenn die UI das Feld prüft**, weil Sie es bearbeitet haben, lehnt sie das Speichern nicht ab.
      Sie setzt dieses Feld auf den gespeicherten Wert zurück, zeigt `Variable <key> is not valid.`,
      speichert den Rest und meldet weiterhin Erfolg. Lesen Sie die Meldungen: Neben der grünen
      Erfolgsmeldung steht eine einzelne rote Fehlermeldung.

    Keiner dieser Schritte findet gespeicherte Werte automatisch. Prüfen Sie `REVERSE_PROXY_URL`,
    `GRPC_URL` und `REDIRECT_FROM` Ihrer UI-verwalteten Dienste von Hand.

!!! warning "`GET /bans` antwortet jetzt aus der Datenbank"

    Sperren werden in 1.7 in der Datenbank gespeichert und überstehen Neustarts. `GET /bans` der
    Control Plane liefert daher diese dauerhafte Liste. Die bisherige Antwort — die aktuell im
    gemeinsamen Speicher jeder Instanz durchgesetzten Sperren — ist unverändert unter
    `GET /bans/instances` verfügbar. Eine 1.6-Automatisierung mit `GET /bans` erhält keinen Fehler,
    aber eine Antwort mit anderer Bedeutung. Passen Sie den Endpunkt bewusst an.

!!! info "`HTTP_PORT` und `HTTPS_PORT` gelten jetzt pro Dienst"

    Ihr Kontext wechselt von `global` zu `multisite`: `www.example.com_HTTPS_PORT=9443` wird jetzt
    akzeptiert, während 1.6 „context of ... isn't multisite“ meldete. Bestehende Konfigurationen
    werden unverändert gerendert: Ein globaler Wert bleibt der Standard für alle Dienste. Neu ist,
    dass ein Dienst eine eigene Liste angeben kann. Sie **ersetzt** dessen globale Liste, statt sie
    zu erweitern.

!!! warning "Swarm: `NAMESPACES` filtert jetzt auch Custom Configs"

    Vor 1.7 filterte `NAMESPACES` den Ereignispfad und die Service-Erkennung des Swarm-Controllers,
    aber **nicht** die Config-Erkennung: Ein globales `docker config`-Objekt wurde von jedem
    Autoconf auf dem Daemon erfasst, unabhängig vom Namespace. 1.7 wendet den Filter nun auch auf
    Configs an, was der Docker-Integration schon immer entsprach. Wenn Sie `NAMESPACES` setzen und
    Ihre Config-Objekte kein `bunkerweb.NAMESPACE`-Label tragen, werden diese Configs **nach dem
    Upgrade nicht mehr angewendet, ohne Fehlermeldung** — ein Custom-Snippet mit einem
    Allow-/Deny-Block verschwindet einfach aus der generierten Konfiguration.

    Versehen Sie jedes Config-Objekt, das angewendet werden soll, mit einem Label. Swarm-Configs
    sind unveränderlich — `docker config` kennt kein `update` — daher muss jedes unter einem neuen
    Namen neu erstellt und mit `docker service update --config-rm/--config-add` neu zugewiesen
    werden. Ermitteln Sie vor dem Upgrade die betroffenen Objekte mit:

    ```bash
    docker config ls -q | xargs -r docker config inspect --format '{{.Spec.Name}} {{.Spec.Labels}}'
    ```

!!! info "Docker Swarm wird in 1.7 wieder unterstützt"

    Die Swarm-Integration wurde in 1.6 als veraltet markiert und wird in 1.7 wieder unterstützt.
    Der für 1.6 veröffentlichte Stack startet unter 1.7 **nicht**: Er enthält weder `bw-api` noch
    `bw-worker`, sodass `bw-autoconf` endlos auf eine nie gestartete API wartet und kein
    Hintergrundjob jemals läuft. Setzen Sie den [1.7-Referenzstack](integrations.md#swarm) neu auf,
    statt den alten zu bearbeiten, und beachten Sie die drei neuen Anforderungen: ein
    `bw-state=true`-Node-Label für die Dienste, die Volumes besitzen, `mode: global` beim
    `bunkerweb`-Dienst und `mode: host` bei der Portveröffentlichung.

### Wechsel eines älteren AIO-Job-Brokers {#aio-broker-upgrade}

Dies betrifft eine **bestehende 1.7-AIO-Bereitstellung**, nicht eine 1.6-Installation ohne Celery-Jobwarteschlange. Frühere 1.7-Images leiteten den Broker aus `REDIS_*` ab. Der Standard ist jetzt `redis://127.0.0.1:6380/0`: ein separates Redis mit `noeviction` und AOF-Persistenz in `/data/broker`. Der WAF-Datastore behält seine eigenen Einstellungen und Dateien.

Ein ausdrücklich gesetztes `CELERY_BROKER_URL` bleibt erhalten. Wenn Sie den Broker bisher über `REDIS_HOST`, `REDIS_PASSWORD` oder die Redis-TLS-Einstellungen ausgewählt haben, betreffen diese jetzt nur noch den WAF-Datastore. Um einen externen Job-Broker weiterzuverwenden, setzen Sie dessen vollständige `CELERY_BROKER_URL` einschließlich Zugangsdaten und TLS-Prüfparametern ausdrücklich. Ein leerer Wert wird bei aktiviertem Worker abgelehnt.

Vor dem Brokerwechsel einer laufenden 1.7-Bereitstellung:

1. Stoppen Sie direkte API-Schreiber, einschließlich Automatisierungen und anderer Operatoren. Halten Sie mit dem bestehenden [Backup-Ruheverfahren](#rolling-back-to-1614) Scheduler-Dispatch, Autoconf und UI-Schreibzugriffe an und warten Sie, bis Warteschlangen, laufende Arbeiten und ausstehende Reload-Bestätigungen abgearbeitet sind. Aktivieren Sie nur die Haltesperre; führen Sie keine Downgrade-Schritte aus. Das Ziel benennt die Haltesperre und fordert keine Migration an.
2. Führen Sie diesen Ruhe-Befehl gegen den **alten** Broker und die alte API aus. Bei älteren AIO-Images erbt eine neue Shell nicht die vom Entrypoint exportierte URL: Geben Sie dieser Shell die tatsächliche alte `CELERY_BROKER_URL` und die API-Zugangsdaten. Wenn die API die Haltesperre nicht beachtet oder das Leeren das Zeitlimit überschreitet, beheben Sie das vor dem Wechsel.
3. Halten Sie die Sperre bis zum Stoppen des alten Containers aktiv. Erstellen Sie den Container mit demselben `/data`-Volume und dem neuen Standard oder Ihrer expliziten externen Broker-URL neu. Warteschlangenschlüssel werden nicht zwischen Brokern kopiert; die alten WAF-Redis-Daten werden nicht gelöscht.
4. Prüfen Sie den Containerzustand und auf der Jobs-Seite den erfolgreichen Abschluss eines versendeten Jobs, bevor Sie API-Automatisierungen fortsetzen. Eine alte Haltesperre auf einem externen Broker lässt sich über den bestehenden Ruhe-Befehl lösen oder läuft von selbst ab.

Der neue Broker startet vor dem Worker und stoppt nach ihm. Seine AOF-Datei übersteht bei beibehaltenem `/data` einen Containerneustart; Persistenz überträgt keine auf dem alten Broker verbliebenen Jobs.

### Nach dem Upgrade {#after-the-upgrade}

Die folgenden Änderungen verhindern das Upgrade nicht und verlangen keine Schritte zu seinem Abschluss. Sie ändern jedoch die Ansicht in 1.7.

!!! info "Ein reservierter Dienst `default-server` erscheint bei Multisite-Installationen"

    Mit `MULTISITE=yes` ist der Block für Anfragen ohne passenden Dienst — unbekannter Hostname,
    direkte IP-Adresse oder nicht bedienter `Host` — jetzt ein permanenter reservierter Diensteintrag.
    Er erscheint in der Dienstliste der Web-UI und in `GET /services` mit `reserved: true`, kann
    weder gelöscht, umbenannt noch zum Entwurf gemacht werden und zählt nie zum PRO-Dienstkontingent.
    Er lässt sich nun mit eigenem Zertifikat, TLS-Einstellungen, Antwort-Headern und Fehlerseiten
    konfigurieren. Siehe [API-Referenz](api.md#api-surface-capability-map) und
    [Web-UI](web-ui.md#the-default-server-entry).

    Bei `MULTISITE=no` wird kein Eintrag angelegt; der Standardserver wird wie unter 1.6 gerendert.

!!! info "Die Instanzregistrierung ist verfügbar und optional"

    Eine Instanz kann einen einmaligen, zeitlich begrenzten Code gegen eigene Zugangsdaten zur
    Control Plane eintauschen, statt das globale `API_TOKEN` zu teilen. Ohne Registrierung bleibt
    alles wie unter 1.6. Danach akzeptiert sie nur noch die eigenen Zugangsdaten, ohne Rückfall auf
    das gemeinsame Token. Ein In-place-Downgrade zerstört gespeicherte Zugangsdaten. Stellen Sie
    die Instanz vor dem Rollback auf das gemeinsame `API_TOKEN` zurück oder registrieren Sie sie
    danach neu. Siehe [Instanzregistrierung](web-ui.md#instance-enrollment)
    und [Registrierte Instanz startet nicht](troubleshooting.md#lost-instance-credential): Fehlt die
    Zugangsdaten-Datei bei erhaltenem restlichem Zustand, verweigert sie bis zur erneuten Registrierung
    den Start.

!!! info "Neue Funktionen in 1.7 zum Ausprobieren"

    - **Zusammengesetzte AND-Regeln** für alle drei Zugriffslisten: `BLACKLIST_RULE_1`,
      `GREYLIST_RULE_1`, `WHITELIST_RULE_1` und weitere Regeln treffen nur zu, wenn jeder Term zutrifft
      (`country:FR AND NOT ua:GoodBot`).
    - **Ein eigenes GeoIP-Plugin.** Ohne Konfiguration stammen Länder- und ASN-Datenbanken weiterhin
      aus den kostenlosen DB-IP-Lite-Ausgaben. Neu sind eine MaxMind-Subscription
      (`MAXMIND_LICENSE_KEY`, `MAXMIND_ACCOUNT_ID`), eine Stadtdatenbank (`GEOIP_CITY`) und eigene
      `.mmdb`-Dateien. Siehe [GeoIP](features.md#geoip).
    - **`BACKUP_ROTATION_STRATEGY`** bestimmt, *welche* Sicherungen erhalten bleiben, nicht wie viele.
      Standard ist `hanoi`, das durch Ausdünnen neuerer Sicherungen ältere Wiederherstellungspunkte
      erhält. `fifo` behält die Auswahl von 1.6 bei. `BACKUP_ROTATION` ändert sich nicht.
    - **Mehrere Vorlagen pro Dienst**: `USE_TEMPLATE` ist eine geordnete, durch Leerzeichen getrennte
      Liste. Spätere Vorlagen überschreiben frühere.
    - **Eine serverseitig übersetzte Web-UI** mit Sprachauswahl. Siehe
      [Übersetzungen](web-ui.md#translations-i18n).

### Zurückstufung auf 1.6.14 {#rolling-back-to-1614}

Eine Zurückstufung ist nicht die Umkehrung eines Upgrades. Es gibt zwei Wege, und BunkerWeb sagt
Ihnen, welcher für Ihre Installation gilt, statt Sie raten zu lassen.

**Wiederherstellung aus einer Sicherung** funktioniert überall und ist der unterstützte Weg. Sie
spielt eine Sicherung, die *vor* dem Upgrade erstellt wurde, über eine geleerte Datenbank ein,
sodass alles seit dem Upgrade Geschriebene verloren geht. Das manuelle Verfahren pro Datenbank
finden Sie weiter unten unter [Rollback](#rollback).

**Zurückstufung ohne Neuaufsetzen** wird nur für Versions-/Engine-Kombinationen angeboten, die
nachweislich verlustfrei sind, und nur zur unmittelbar vorhergehenden Version. Für 1.7.0 bedeutet
das 1.6.14, nur unter **SQLite und PostgreSQL**. Bei MariaDB und MySQL lässt sich die
1.7-Migration nicht rückwärts abspielen — sie bricht mittendrin ab und hinterlässt ein Schema, das
keiner der beiden Versionen entspricht — solche Installationen müssen aus einer Sicherung
wiederhergestellt werden.

Drei Befehle, in dieser Reihenfolge:

```bash
# 1. Kann diese Installation zurückgestuft werden? Nur lesend: legt keine Datenbank an, schreibt nichts.
bwcli plugin backup preflight 1.6.14

# 2. Schreiber anhalten. Bleibt im Vordergrund, bis Sie Strg-C drücken.
bwcli plugin backup quiesce 1.6.14

# 3. In einer zweiten Shell, während Schritt 2 noch hält:
bwcli plugin backup downgrade 1.6.14            # Bericht; ändert nichts
bwcli plugin backup downgrade 1.6.14 --execute  # fragt nach Bestätigung, migriert dann
```

Schritt 3 verweigert die Ausführung, sofern nicht das Anhalten aus Schritt 2 für dieselbe Version
aktiv ist, der von ihm selbst erneut ausgeführte Preflight sauber durchläuft und das
Kompatibilitäts-Manifest das Paar als getestet ausweist. Er erstellt dann sofort vor der Migration
eine eigene Sicherung und stellt sie wieder her, falls etwas schiefgeht.

Stoppen oder blockieren Sie vor dem Start alles, was direkt in die API schreibt. Das Anhalten
lässt die API dem Rest der Flotte *melden*, sie sei schreibgeschützt — darauf reagieren Scheduler,
Autoconf und die UI; ein Schreibzugriff direkt über die API mit einem gültigen Token wird dadurch
nicht blockiert.

!!! danger "Was eine Zurückstufung ohne Neuaufsetzen zerstört"
    Jedes zentral gespeicherte Zertifikat, jede anhängbare Ressource (Redirects, Upstream-Pools,
    Workflows, Ressourcengruppen), alle Anfragemetriken und die Bedrohungskarte, jeder
    registrierte Passkey und jedes gespeicherte Instanz-Credential — enrollte Instanzen müssen
    danach erneut gegen das globale `API_TOKEN` registriert werden. Benutzerspezifische
    UI-Einstellungen bleiben erhalten, verlieren aber ihre Bedeutung: 1.6.14 liest sie alle als
    Spaltenlayouts pro Tabelle. Bans sind der einzige weiche Verlust: Der `sync-bans`-Job lernt sie
    von den Instanzen neu, nur ihre verbleibende Dauer geht verloren.

    Der Preflight zählt, was Ihre Installation tatsächlich enthält, und verweigert eine
    Zurückstufung ohne Neuaufsetzen, solange noch etwas Unersetzliches vorhanden ist — die Antwort
    bezieht sich also auf Ihre Daten, nicht auf das Release im Abstrakten.

**Außerhalb der Datenbank.** Job-Caches und PRO-Plugins werden beim nächsten Lauf neu aufgebaut.
Custom Configs, `www`-Inhalte, Let's-Encrypt-Status und Backup-Archive bleiben zwischen den beiden
Versionen unverändert. Externe Plugins, die eine 1.7-API benötigen, sind unter 1.6.14 unbrauchbar
und müssen entfernt oder ebenfalls zurückgestuft werden.

### Vorgehensweise

=== "Docker"

    === "Einfaches Upgrade mit dem Installationsskript"

        Dasselbe Skript, das Docker-Installationen erstellt, führt auch das Upgrade
        eines von ihm erzeugten Stacks durch. Führen Sie es in dem Verzeichnis aus,
        das Ihre `docker-compose.yml` und `.env` enthält (oder geben Sie es mit
        `--compose-dir` an):

        ```bash
        LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')

        # Skript und Prüfsumme herunterladen
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh.sha256

        # Prüfsumme überprüfen
        sha256sum -c install-bunkerweb.sh.sha256

        # Bei erfolgreicher Prüfung das Skript ausführen
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh --docker --compose-dir /path/to/your/stack
        ```

        !!! danger "Sicherheitshinweis"
            **Überprüfen Sie immer die Integrität des Installationsskripts, bevor Sie es ausführen.**

            Laden Sie die Prüfsummendatei herunter und bestätigen Sie mit einem Werkzeug wie `sha256sum`, dass das Skript nicht verändert oder manipuliert wurde.

            Schlägt die Überprüfung fehl, **führen Sie das Skript nicht aus** — es könnte unsicher sein.

        !!! warning "Nur für Stacks, die dieses Skript erstellt hat"
            Der Upgrade-Pfad erkennt einen Stack an der Kopfzeile
            `generated by install-bunkerweb.sh` in seiner `.env`-Datei. Eine von Hand
            geschriebene `docker-compose.yml`, ein All-In-One-Container oder eine
            Swarm-/Kubernetes-Bereitstellung wird vom Skript nicht aktualisiert —
            verwenden Sie dafür den Reiter **Manuell**.

        * **Funktionsweise**:

            1. Erkennung
                * Liest den Installationstyp (full, manager, worker, scheduler, ui, api) aus der `.env` zurück, sodass Sie Ihre Topologie nie erneut angeben müssen.
                * Übernimmt Geheimnisse, Host-Ports, Worker-Liste und Compose-Projektnamen aus der `.env`. Ein Upgrade kann so weder das Datenbankpasswort rotieren noch gespeicherte 2FA-Geheimnisse ungültig machen oder Ihre veröffentlichten Ports verschieben.
                * Liest die tatsächlich laufende Version aus dem Container statt dem Image-Tag zu vertrauen. So werden ein gleitender Tag (`latest`, `testing`) und ein zuvor abgebrochenes Upgrade zuverlässig erkannt.
            2. Upgrade-Entscheidung
                * Gleiche Version läuft bereits: Der Status wird ausgegeben und das Skript beendet sich.
                * Ältere Zielversion: **Abbruch**. Das Installationsskript besitzt selbst keine Downgrade-Automatik, und ein Start des Schedulers gegen ein älteres Paket mit bereits migrierter Datenbank schlägt fehl und endet in einer Neustartschleife. Siehe [Zurückstufung auf 1.6.14](#rolling-back-to-1614), um zunächst die Datenbank zurückzuholen, und führen Sie das Installationsskript danach erneut mit der älteren Version aus.
                * Sonst: Rückfrage zur Bestätigung (oder direkter Ablauf mit `-y`).
            3. Sicherung vor dem Upgrade
                * Führt `bwcli plugin backup save` im Scheduler-Container aus und kopiert das Archiv auf den Host.
                * Ziel: `--backup-dir` oder ein erzeugter Pfad wie `/var/tmp/bunkerweb-backup-YYYYmmdd-HHMMSS`.
                * Bricht das Upgrade ab, wenn die Sicherung fehlschlägt — es sei denn, Sie übergeben `--no-auto-backup`.
                * Entfällt bei `worker`-, `ui`- und `api`-Stacks, die keine eigene Datenbank besitzen.
            4. Dateiaktualisierung
                * Die `.env` wird mit dem neuen Image-Tag neu geschrieben; von Hand ergänzte Einträge werden übernommen.
                * Die `docker-compose.yml` wird nur neu erzeugt, wenn sie noch dem entspricht, was das Skript geschrieben hat — lokale Änderungen bleiben also erhalten. Mit `--overwrite-compose` wird sie trotzdem neu erzeugt. Eine Kopie `.bak.<Zeitstempel>` wird in beiden Fällen angelegt.
            5. Anwenden und Überprüfen
                * `docker compose pull`, danach `docker compose up -d` — nur Container mit geändertem Image werden neu erstellt, die Ausfallzeit ist also kürzer als bei einem vollständigen `down`/`up`.
                * Schlägt der Pull fehl, wird nichts neu erstellt, der vorherige Tag in der `.env` wiederhergestellt und der laufende Stack bleibt unberührt.
                * Anschließend liest das Skript die Version erneut aus dem Container und prüft, ob der Scheduler in eine Neustartschleife geraten ist — so zeigt sich eine fehlgeschlagene Datenbankmigration.

        * **Nützliche Optionen**:

            | Option                  | Wirkung                                                                                           |
            | ----------------------- | ------------------------------------------------------------------------------------------------- |
            | `--compose-dir PATH`    | Verzeichnis des Stacks (Standard: aktuelles Verzeichnis)                                          |
            | `-v, --version VERSION` | Zielversion; der Image-Tag wird daraus abgeleitet                                                 |
            | `--image-tag TAG`       | Ziel-Image-Tag direkt angeben, statt ihn abzuleiten                                               |
            | `--backup-dir PATH`     | Ablageort der Sicherung vor dem Upgrade                                                           |
            | `--no-auto-backup`      | Automatische Sicherung überspringen (die manuelle Sicherung liegt dann bei Ihnen)                 |
            | `--overwrite-compose`   | `docker-compose.yml` auch dann neu erzeugen, wenn sie lokal bearbeitet wurde                      |
            | `--force-type-change`   | Topologiewechsel des Stacks zulassen (destruktiv)                                                 |
            | `--no-pull`             | Images vor dem Neuerstellen nicht herunterladen                                                   |
            | `-y, --yes`             | Unbeaufsichtigter Lauf; per Pipe gestartete Aufrufe ohne diese Option brechen mit einem Fehler ab |

    === "Manuell"

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
                1. **Aktualisieren Sie die Docker-Compose-Datei**: Von 1.6 aus genügt ein Tag-Wechsel
                   nicht. Ergänzt werden müssen `bw-api`, `bw-worker`, `bw-jobs-broker`, die Variablen
                   `API_URL`, `API_TOKEN`, `CELERY_BROKER_URL` auf jeder Komponente sowie das Volume
                   `bw-instance-data` auf `bunkerweb`. Siehe
                   [Drei neue Komponenten für Docker, Autoconf und Kubernetes](#breaking-changes).
                   Erstellen Sie Ihre `docker-compose.yml` anhand des 1.7-Referenzstacks Ihrer
                   Integration ([Docker](integrations.md#docker),
                   [Docker autoconf](integrations.md#docker-autoconf)) neu und übernehmen Sie Ihre
                   Einstellungen, Volumes und veröffentlichten Ports.

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

=== "All-In-One (AIO)"

    Das [All-In-One-Image](integrations.md#all-in-one-aio-image) bündelt BunkerWeb, den Scheduler, die Weboberfläche und optional API, Redis und CrowdSec in einem **einzigen Container**, der standardmäßig `bunkerweb-aio` heißt. Der gesamte persistente Zustand — SQLite-Datenbank, Cache, benutzerdefinierte Konfigurationen, Plugins, Sicherungen und Redis-/CrowdSec-Daten — liegt im Volume `/data`; beim Upgrade wird daher der Container ersetzt, während dieses Volume erhalten bleibt.

    1. **Voraussetzungen**:

        - Notieren Sie den aktuell verwendeten Image-Tag und den Namen des `/data`-Volumes (oder Bind-Mounts), damit Sie nach dem Upgrade exakt dasselbe wiederverwenden.

        !!! warning "Volume `/data` beibehalten"
            **Entfernen Sie das Volume `/data` während eines Upgrades niemals.** Es enthält die Datenbank, den eingebetteten Redis- und CrowdSec-Zustand, Ihre benutzerdefinierten Konfigurationen und Ihre Sicherungen. Den Container zu ersetzen ist sicher; das Volume zu löschen nicht.

        !!! tip "Externe Datenbanken"
            Wenn Sie AIO mit einer externen Datenbank betreiben (`DATABASE_URI` zeigt auf MySQL/MariaDB/PostgreSQL), wird die SQLite-Datei unter `/data` nicht verwendet — sichern Sie diese externe Datenbank ebenfalls mit Ihren üblichen Werkzeugen.

    2. **Sichern Sie die Datenbank**:

        - Bevor Sie mit dem Datenbank-Upgrade fortfahren, stellen Sie sicher, dass Sie eine vollständige Sicherung des aktuellen Zustands der Datenbank durchführen. Der Scheduler läuft im Container `bunkerweb-aio`, daher wird der Sicherungsbefehl dort direkt ausgeführt.

        ```bash
        docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory bunkerweb-aio bwcli plugin backup save
        ```

        ```bash
        docker cp bunkerweb-aio:/path/to/backup/directory /path/to/backup/directory
        ```

    3. **Aktualisieren Sie BunkerWeb**:

        === "docker run"

            3. **Stoppen und entfernen Sie den aktuellen Container** (das `/data`-Volume bleibt erhalten):
                ```bash
                docker stop bunkerweb-aio
                docker rm bunkerweb-aio
                ```

            4. **Laden Sie das neue Image herunter**:
                ```bash
                docker pull bunkerity/bunkerweb-all-in-one:1.7.0-beta
                ```

            5. **Erstellen Sie den Container neu** mit denselben Optionen und verwenden Sie dasselbe `/data`-Volume, dieselben Ports und dieselben Umgebungsvariablen wie zuvor:
                ```bash
                docker run -d \
                --name bunkerweb-aio \
                -v bw-storage:/data \
                -p 80:8080/tcp \
                -p 443:8443/tcp \
                -p 443:8443/udp \
                bunkerity/bunkerweb-all-in-one:1.7.0-beta
                ```

        === "Docker Compose"

            6. **Aktualisieren Sie die Docker Compose-Datei**: Aktualisieren Sie die Docker Compose-Datei, um die neue Version des All-In-One-Images zu verwenden.
                ```yaml
                services:
                    bunkerweb-aio:
                        image: bunkerity/bunkerweb-all-in-one:1.7.0-beta
                        ...
                ```

            7. **Starten Sie den Container neu**: Starten Sie den Container neu, um die Änderungen zu übernehmen. Das `/data`-Volume wird automatisch wieder angehängt.
                ```bash
                docker compose down
                docker compose up -d
                ```

    4. **Überprüfen Sie die Protokolle**: Überprüfen Sie die Container-Protokolle, um sicherzustellen, dass die vom eingebetteten Scheduler ausgeführte Migration erfolgreich war.

        ```bash
        docker logs bunkerweb-aio
        ```

    5. **Überprüfen Sie das Upgrade**:
        - Bestätigen Sie, dass der Container läuft und gesund ist:
            ```bash
            docker ps --filter name=bunkerweb-aio
            ```
            Die Spalte `STATUS` sollte `(healthy)` anzeigen, sobald die Startprüfungen abgeschlossen sind.
        - Bestätigen Sie die laufende Version:
            ```bash
            docker exec bunkerweb-aio cat /usr/share/bunkerweb/VERSION
            ```
            Die Version kann auch in der Weboberfläche unter *Support* geprüft werden.
        - Prüfen Sie in der Weboberfläche, dass Ihre Dienste, Einstellungen und benutzerdefinierten Konfigurationen intakt sind und Ihre Sites weiterhin über HTTP/HTTPS ausgeliefert werden.

=== "Linux"

    === "Einfaches Upgrade mit dem Installationsskript"

        * **Schnellstart**:

            Um zu beginnen, laden Sie das Installationsskript und seine Prüfsumme herunter und überprüfen Sie dann die Integrität des Skripts, bevor Sie es ausführen.

            ```bash
            LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')

            # Skript und Prüfsumme herunterladen
            curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh
            curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh.sha256

            # Prüfsumme prüfen
            sha256sum -c install-bunkerweb.sh.sha256

            # Nach erfolgreicher Prüfung das Skript ausführen
            chmod +x install-bunkerweb.sh
            sudo ./install-bunkerweb.sh
            ```

            !!! danger "Sicherheitshinweis"
                **Überprüfen Sie immer die Integrität des Installationsskripts, bevor Sie es ausführen.**

                Laden Sie die Prüfsummendatei herunter und verwenden Sie ein Werkzeug wie `sha256sum`, um zu bestätigen, dass das Skript nicht verändert oder manipuliert wurde.

                Wenn die Überprüfung der Prüfsumme fehlschlägt, **führen Sie das Skript nicht aus** – es könnte unsicher sein.

        !!! tip "Interaktive Upgrade-Oberfläche"
            Der Upgrade-Ablauf verwendet dieselbe TUI wie Neuinstallationen: Inline-Eingabeaufforderungen mit [gum](https://github.com/charmbracelet/gum), mit Rückfall auf `whiptail`-Dialogboxen und schließlich auf Klartext-Eingaben, falls gum nicht bezogen werden kann. Das `gum`-Binary wird aus der offiziellen [GitHub-Release](https://github.com/charmbracelet/gum/releases) heruntergeladen (SHA256-gepinnt, cosign-verifiziert, wenn cosign installiert ist) und aus einem Temp-Verzeichnis ausgeführt, das beim Beenden entfernt wird — es wird kein Systempaket installiert und keine apt/dnf-Quelle hinzugefügt. Übergeben Sie `--no-tui` (oder setzen Sie `BW_INSTALL_TUI=no`), um alle TUI-Ebenen zu überspringen, oder `--tui`, um eine funktionierende TUI zu erzwingen. Für vollständig unbeaufsichtigte Upgrades übergeben Sie `-y` / `--yes` mit den entsprechenden Flags – Pipe-Aufrufe (`curl … | bash`) brechen mit einer klaren Fehlermeldung ab, statt jede Vorgabe stillschweigend zu übernehmen. **Air-gapped-Upgrades**: kombinieren Sie `--no-tui --yes`, damit für die TUI-Schicht kein Netzwerkaufruf ausgeführt wird.

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
            | `--tui`                 | Erzwingt eine TUI (gum oder whiptail). Bricht ab, wenn keine installiert werden kann.                                          |
            | `--no-tui`              | Überspringt alle TUI-Ebenen und verwendet Klartext-Eingaben. Entspricht `BW_INSTALL_TUI=no`.                                   |
            | `--backup-dir <PFAD>`   | Ziel für die automatische Pre-Upgrade-Sicherung. Wird erstellt, wenn es fehlt.                                                 |
            | `--no-auto-backup`      | Überspringt die automatische Sicherung (NICHT empfohlen). Sie müssen eine manuelle Sicherung haben.                            |
            | `-q, --quiet`           | Unterdrückt die Ausgabe (mit Protokollierung / Überwachung kombinieren).                                                       |
            | `-f, --force`           | Fährt mit einer ansonsten nicht unterstützten Betriebssystemversion fort.                                                      |
            | `--dry-run`             | Zeigt die erkannte Umgebung, die beabsichtigten Aktionen an und beendet dann, ohne etwas zu ändern.                            |

            Beispiele:

            ```bash
            # Interaktiv auf 1.7.0~beta aktualisieren (fragt nach Sicherung)
            sudo ./install-bunkerweb.sh --version 1.7.0~beta

            # Nicht-interaktives Upgrade mit automatischer Sicherung in ein benutzerdefiniertes Verzeichnis
            sudo ./install-bunkerweb.sh -v 1.7.0~beta --backup-dir /var/backups/bw-2025-01 -y

            # Stilles unbeaufsichtigtes Upgrade (Protokolle unterdrückt) – verlässt sich auf die standardmäßige automatische Sicherung
            sudo ./install-bunkerweb.sh -v 1.7.0~beta -y -q

            # Einen Probelauf (Plan) durchführen, ohne Änderungen anzuwenden
            sudo ./install-bunkerweb.sh -v 1.7.0~beta --dry-run

            # Upgrade unter Überspringen der automatischen Sicherung (NICHT empfohlen)
            sudo ./install-bunkerweb.sh -v 1.7.0~beta --no-auto-backup -y
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
                    sudo systemctl stop bunkerweb-api
                    sudo systemctl stop bunkerweb-worker
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
                        sudo apt install -y --allow-downgrades bunkerweb=1.7.0~beta
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
                        sudo dnf install -y --allowerasing bunkerweb-1.7.0~beta
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
                        sudo systemctl start bunkerweb-api
                        sudo systemctl start bunkerweb-worker
                        sudo systemctl start bunkerweb-scheduler
                        sudo systemctl start bunkerweb-ui
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

=== "All-In-One (AIO)"

    Der Scheduler läuft im Container `bunkerweb-aio`, daher werden die Wiederherstellungsbefehle direkt dort ausgeführt. Das Volume `/data` (Datenbank, Konfigurationen, Plugins, Sicherungen) bleibt währenddessen erhalten — nur das Container-Image wird zurückgerollt.

    !!! tip "Externe Datenbanken"
        Wenn Sie AIO mit einer externen Datenbank betreiben (`DATABASE_URI` zeigt auf MySQL/MariaDB/PostgreSQL), wird die SQLite-Datei unter `/data` nicht verwendet. Stellen Sie diese externe Datenbank mit Ihren üblichen Werkzeugen wieder her — oder mit den MySQL/MariaDB/PostgreSQL-Befehlen im **Docker**-Tab, auf Ihren Datenbankhost gerichtet — und überspringen Sie die SQLite-Schritte unten.

    1. **Entpacken Sie die Sicherung, falls sie gezippt ist**.

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Stellen Sie die Sicherung wieder her** (eingebettetes SQLite):

        1. **Entfernen Sie die vorhandene Datenbankdatei.**

            ```bash
            docker exec -u 0 -i bunkerweb-aio rm -f /var/lib/bunkerweb/db.sqlite3
            ```

        2. **Stellen Sie die Sicherung wieder her.**

            ```bash
            docker exec -i bunkerweb-aio sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            ```

        3. **Korrigieren Sie die Berechtigungen.**

            ```bash
            docker exec -u 0 -i bunkerweb-aio chown root:nginx /var/lib/bunkerweb/db.sqlite3
            docker exec -u 0 -i bunkerweb-aio chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

    3. **Rollen Sie das Image zurück** und verwenden Sie dasselbe `/data`-Volume wieder:

        === "docker run"

            3. **Stoppen und entfernen Sie den aktuellen Container** (das `/data`-Volume bleibt erhalten):
                ```bash
                docker stop bunkerweb-aio
                docker rm bunkerweb-aio
                ```

            4. **Laden Sie das vorherige Image herunter**:
                ```bash
                docker pull bunkerity/bunkerweb-all-in-one:<old_version>
                ```

            5. **Erstellen Sie den Container neu** mit denselben Optionen, Ports und demselben `/data`-Volume wie zuvor:
                ```bash
                docker run -d \
                --name bunkerweb-aio \
                -v bw-storage:/data \
                -p 80:8080/tcp \
                -p 443:8443/tcp \
                -p 443:8443/udp \
                bunkerity/bunkerweb-all-in-one:<old_version>
                ```

        === "Docker Compose"

            6. **Aktualisieren Sie die Docker Compose-Datei**, um das vorherige All-In-One-Image zu verwenden:
                ```yaml
                services:
                    bunkerweb-aio:
                        image: bunkerity/bunkerweb-all-in-one:<old_version>
                        ...
                ```

            7. **Starten Sie den Container neu**. Das `/data`-Volume wird automatisch wieder angehängt:
                ```bash
                docker compose down
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
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler bunkerweb-api bunkerweb-worker
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
        sudo systemctl start bunkerweb bunkerweb-api bunkerweb-worker bunkerweb-scheduler bunkerweb-ui
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
                        image: bunkerity/bunkerweb:1.7.0-beta
                        ...
                    bw-scheduler:
                        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
                        ...
                    bw-autoconf:
                        image: bunkerity/bunkerweb-autoconf:1.7.0-beta
                        ...
                    bw-ui:
                        image: bunkerity/bunkerweb-ui:1.7.0-beta
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
                sudo systemctl stop bunkerweb-api
                sudo systemctl stop bunkerweb-worker
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
                    sudo apt install -y --allow-downgrades bunkerweb=1.7.0~beta
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
                    sudo dnf install -y --allowerasing bunkerweb-1.7.0~beta
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
                    sudo systemctl start bunkerweb-api
                    sudo systemctl start bunkerweb-worker
                    sudo systemctl start bunkerweb-scheduler
                    sudo systemctl start bunkerweb-ui
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
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler bunkerweb-api bunkerweb-worker
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
        sudo systemctl start bunkerweb bunkerweb-api bunkerweb-worker bunkerweb-scheduler bunkerweb-ui
        ```

    8. **Downgrade von BunkerWeb**.
        - Führen Sie ein Downgrade von BunkerWeb auf die vorherige Version durch, indem Sie die gleichen Schritte wie beim Upgrade von BunkerWeb auf der Seite [Integration Linux](integrations.md#linux) befolgen.
