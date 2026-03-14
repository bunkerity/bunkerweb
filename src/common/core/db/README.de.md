Das Datenbank-Plugin bietet eine robuste Datenbankintegration für BunkerWeb, indem es die zentrale Speicherung und Verwaltung von Konfigurationsdaten, Protokollen und anderen wichtigen Informationen ermöglicht.

Diese Kernkomponente unterstützt mehrere Datenbank-Engines, darunter SQLite, PostgreSQL, MySQL/MariaDB und Oracle, sodass Sie die Datenbanklösung wählen können, die am besten zu Ihrer Umgebung und Ihren Anforderungen passt.

**So funktioniert es:**

1.  BunkerWeb verbindet sich mit Ihrer konfigurierten Datenbank über die bereitgestellte URI im SQLAlchemy-Format.
2.  Kritische Konfigurationsdaten, Laufzeitinformationen und Job-Protokolle werden sicher in der Datenbank gespeichert.
3.  Automatische Wartungsprozesse optimieren Ihre Datenbank, indem sie das Datenwachstum verwalten und überschüssige Datensätze bereinigen.
4.  Für Hochverfügbarkeitsszenarien können Sie eine schreibgeschützte Datenbank-URI konfigurieren, die sowohl als Failover als auch zur Entlastung von Leseoperationen dient.
5.  Datenbankoperationen werden entsprechend Ihrer angegebenen Protokollierungsstufe protokolliert, um eine angemessene Transparenz der Datenbankinteraktionen zu gewährleisten.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Datenbankfunktion zu konfigurieren und zu verwenden:

1.  **Wählen Sie eine Datenbank-Engine:** Wählen Sie je nach Ihren Anforderungen zwischen SQLite (Standard), PostgreSQL, MySQL/MariaDB oder Oracle.
2.  **Konfigurieren Sie die Datenbank-URI:** Setzen Sie `DATABASE_URI`, um sich mit Ihrer primären Datenbank im SQLAlchemy-Format zu verbinden.
3.  **Optionale schreibgeschützte Datenbank:** Konfigurieren Sie für Hochverfügbarkeits-Setups eine `DATABASE_URI_READONLY` als Fallback oder für Leseoperationen.

### Konfigurationseinstellungen

| Einstellung                     | Standard                                  | Kontext | Mehrfach | Beschreibung                                                                                                                                |
| ------------------------------- | ----------------------------------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URI`                    | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global  | nein     | **Datenbank-URI:** Die primäre Datenbankverbindungszeichenfolge im SQLAlchemy-Format.                                                                                                                          |
| `DATABASE_URI_READONLY`           |                                           | global  | nein     | **Schreibgeschützte Datenbank-URI:** Optionale Datenbank für schreibgeschützte Operationen oder als Failover.                                                                                                  |
| `DATABASE_LOG_LEVEL`              | `warning`                                 | global  | nein     | **Protokollierungsstufe:** Die Ausführlichkeitsstufe für Datenbankprotokolle. Optionen: `debug`, `info`, `warn`, `warning` oder `error`.                                                                       |
| `DATABASE_MAX_JOBS_RUNS`          | `10000`                                   | global  | nein     | **Maximale Job-Ausführungen:** Die maximale Anzahl von Job-Ausführungsdatensätzen, die vor der automatischen Bereinigung aufbewahrt werden.                                                                    |
| `DATABASE_MAX_SESSION_AGE_DAYS`   | `14`                                      | global  | nein     | **Sitzungsaufbewahrung:** Das maximale Alter (in Tagen) von UI-Benutzersitzungen, bevor sie automatisch bereinigt werden.                                                                                      |
| `DATABASE_POOL_SIZE`              | `40`                                      | global  | nein     | **Pool-Größe:** Die Anzahl der Verbindungen im Datenbankverbindungspool.                                                                                                                                       |
| `DATABASE_POOL_MAX_OVERFLOW`      | `20`                                      | global  | nein     | **Maximaler Pool-Überlauf:** Die maximale Anzahl zusätzlicher Verbindungen über die Pool-Größe hinaus. `-1` für unbegrenzt.                                                                                    |
| `DATABASE_POOL_TIMEOUT`           | `5`                                       | global  | nein     | **Pool-Zeitlimit:** Die Anzahl der Sekunden, die auf eine Verbindung aus dem Pool gewartet wird.                                                                                                               |
| `DATABASE_POOL_RECYCLE`           | `1800`                                    | global  | nein     | **Pool-Recycling:** Die Anzahl der Sekunden, nach denen eine Verbindung automatisch recycelt wird. `-1` zum Deaktivieren.                                                                                      |
| `DATABASE_POOL_PRE_PING`          | `yes`                                     | global  | nein     | **Pool-Pre-Ping:** Ob Verbindungen bei jeder Entnahme aus dem Pool auf Erreichbarkeit getestet werden.                                                                                                         |
| `DATABASE_POOL_RESET_ON_RETURN`   |                                           | global  | nein     | **Pool-Reset bei Rückgabe:** Wie Verbindungen bei der Rückgabe in den Pool zurückgesetzt werden. Leer = automatisch (`none` für MySQL/MariaDB, `rollback` für andere). Optionen: `rollback`, `commit`, `none`.  |
| `DATABASE_RETRY_TIMEOUT`          | `60`                                      | global  | nein     | **Wiederholungs-Zeitlimit:** Die maximale Wartezeit in Sekunden auf die Verfügbarkeit der Datenbank beim Start.                                                                                                |
| `DATABASE_REQUEST_RETRY_ATTEMPTS` | `2`                                       | global  | nein     | **Wiederholungsversuche:** Die Anzahl der Wiederholungsversuche bei vorübergehenden Datenbankfehlern.                                                                                                          |
| `DATABASE_REQUEST_RETRY_DELAY`    | `0.25`                                    | global  | nein     | **Wiederholungsverzögerung:** Die Verzögerung in Sekunden zwischen Wiederholungsversuchen bei vorübergehenden Datenbankfehlern.                                                                                |

!!! tip "Auswahl der Datenbank" - **SQLite** (Standard): Ideal für Single-Node-Bereitstellungen oder Testumgebungen aufgrund seiner Einfachheit und dateibasierten Natur. - **PostgreSQL**: Empfohlen für Produktionsumgebungen mit mehreren BunkerWeb-Instanzen aufgrund seiner Robustheit und Unterstützung für Gleichzeitigkeit. - **MySQL/MariaDB**: Eine gute Alternative zu PostgreSQL mit ähnlichen produktionsreifen Fähigkeiten. - **Oracle**: Geeignet für Unternehmensumgebungen, in denen Oracle bereits die Standard-Datenbankplattform ist.

!!! info "SQLAlchemy-URI-Format"
    Die Datenbank-URI folgt dem SQLAlchemy-Format:

    - SQLite: `sqlite:////pfad/zur/datenbank.sqlite3`
    - PostgreSQL: `postgresql://benutzername:passwort@hostname:port/datenbank`
    - MySQL/MariaDB: `mysql://benutzername:passwort@hostname:port/datenbank` oder `mariadb://benutzername:passwort@hostname:port/datenbank`
    - Oracle: `oracle://benutzername:passwort@hostname:port/datenbank`

!!! warning "Datenbankwartung"
    Das Plugin führt automatisch tägliche Wartungsjobs aus:

- **Bereinigung überschüssiger Job-Ausführungen:** Entfernt Historien, die über dem Wert von `DATABASE_MAX_JOBS_RUNS` liegen.
- **Bereinigung abgelaufener UI-Sitzungen:** Löscht UI-Benutzersitzungen, die älter sind als `DATABASE_MAX_SESSION_AGE_DAYS`.

Diese Aufgaben verhindern ein unbegrenztes Datenbankwachstum und bewahren gleichzeitig eine nützliche Betriebshistorie.
