Das Sessions-Plugin bietet eine robuste HTTP-Sitzungsverwaltung für BunkerWeb und ermöglicht eine sichere und zuverlässige Verfolgung von Benutzersitzungen über Anfragen hinweg. Diese Kernfunktion ist unerlässlich für die Aufrechterhaltung des Benutzerstatus, die Persistenz der Authentifizierung und die Unterstützung anderer Funktionen, die eine Kontinuität der Identität erfordern, wie z. B. der [Anti-Bot-Schutz](#antibot) und Benutzerauthentifizierungssysteme.

**So funktioniert es:**

1.  Wenn ein Benutzer zum ersten Mal mit Ihrer Website interagiert, erstellt BunkerWeb eine eindeutige Sitzungs-ID.
2.  Diese ID wird sicher in einem Cookie im Browser des Benutzers gespeichert.
3.  Bei nachfolgenden Anfragen ruft BunkerWeb die Sitzungs-ID aus dem Cookie ab und verwendet sie, um auf die Sitzungsdaten des Benutzers zuzugreifen.
4.  Sitzungsdaten können lokal oder in [Redis](#redis) für verteilte Umgebungen mit mehreren BunkerWeb-Instanzen gespeichert werden.
5.  Sitzungen werden automatisch mit konfigurierbaren Zeitüberschreitungen verwaltet, um die Sicherheit bei gleichzeitiger Benutzerfreundlichkeit zu gewährleisten.
6.  Die kryptografische Sicherheit von Sitzungen wird durch einen geheimen Schlüssel gewährleistet, der zum Signieren von Sitzungs-Cookies verwendet wird.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Sessions-Funktion zu konfigurieren und zu verwenden:

1.  **Sitzungssicherheit konfigurieren:** Legen Sie einen starken, eindeutigen `SESSIONS_SECRET` fest, um sicherzustellen, dass Sitzungs-Cookies nicht gefälscht werden können. (Der Standardwert ist "random", wodurch BunkerWeb einen zufälligen geheimen Schlüssel generiert.)
2.  **Sitzungsnamen wählen:** Passen Sie optional den `SESSIONS_NAME` an, um zu definieren, wie Ihr Sitzungs-Cookie im Browser heißen soll. (Der Standardwert ist "random", wodurch BunkerWeb einen zufälligen Namen generiert.)
3.  **Sitzungs-Timeouts festlegen:** Konfigurieren Sie mit den Timeout-Einstellungen (`SESSIONS_IDLING_TIMEOUT`, `SESSIONS_ROLLING_TIMEOUT`, `SESSIONS_ABSOLUTE_TIMEOUT`), wie lange Sitzungen gültig bleiben.
4.  **Redis-Integration konfigurieren:** Setzen Sie für verteilte Umgebungen `USE_REDIS` auf "yes" und konfigurieren Sie Ihre [Redis-Verbindung](#redis), um Sitzungsdaten über mehrere BunkerWeb-Knoten hinweg zu teilen.
5.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration erfolgt die Sitzungsverwaltung für Ihre Website automatisch.

### Konfigurationseinstellungen

| Einstellung                 | Standard | Kontext | Mehrfach | Beschreibung                                                                                                                                                               |
| --------------------------- | -------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SESSIONS_SECRET`           | `random` | global  | nein     | **Sitzungsgeheimnis:** Kryptografischer Schlüssel zum Signieren von Sitzungs-Cookies. Sollte eine starke, zufällige Zeichenfolge sein, die für Ihre Website eindeutig ist. |
| `SESSIONS_NAME`             | `random` | global  | nein     | **Cookie-Name:** Der Name des Cookies, in dem die Sitzungs-ID gespeichert wird.                                                                                            |
| `SESSIONS_IDLING_TIMEOUT`   | `1800`   | global  | nein     | **Leerlauf-Timeout:** Maximale Zeit (in Sekunden) der Inaktivität, bevor die Sitzung ungültig wird.                                                                        |
| `SESSIONS_ROLLING_TIMEOUT`  | `3600`   | global  | nein     | **Rollierendes Timeout:** Maximale Zeit (in Sekunden), bevor eine Sitzung erneuert werden muss.                                                                            |
| `SESSIONS_ABSOLUTE_TIMEOUT` | `86400`  | global  | nein     | **Absolutes Timeout:** Maximale Zeit (in Sekunden), bevor eine Sitzung unabhängig von der Aktivität zerstört wird.                                                         |
| `SESSIONS_CHECK_IP`         | `yes`    | global  | nein     | **IP prüfen:** Wenn auf `yes` gesetzt, wird die Sitzung zerstört, wenn sich die IP-Adresse des Clients ändert.                                                             |
| `SESSIONS_CHECK_USER_AGENT` | `yes`    | global  | nein     | **User-Agent prüfen:** Wenn auf `yes` gesetzt, wird die Sitzung zerstört, wenn sich der User-Agent des Clients ändert.                                                     |

!!! warning "Sicherheitshinweise"
    Die Einstellung `SESSIONS_SECRET` ist für die Sicherheit von entscheidender Bedeutung. In Produktionsumgebungen:

    1. Verwenden Sie einen starken, zufälligen Wert (mindestens 32 Zeichen)
    2. Halten Sie diesen Wert vertraulich
    3. Verwenden Sie denselben Wert für alle BunkerWeb-Instanzen in einem Cluster
    4. Erwägen Sie die Verwendung von Umgebungsvariablen oder Geheimnisverwaltung, um die Speicherung im Klartext zu vermeiden

!!! tip "Cluster-Umgebungen"
    Wenn Sie mehrere BunkerWeb-Instanzen hinter einem Load Balancer betreiben:

    1. Setzen Sie `USE_REDIS` auf `yes` und konfigurieren Sie Ihre Redis-Verbindung
    2. Stellen Sie sicher, dass alle Instanzen genau denselben `SESSIONS_SECRET` und `SESSIONS_NAME` verwenden
    3. Dies stellt sicher, dass Benutzer ihre Sitzung beibehalten, unabhängig davon, welche BunkerWeb-Instanz ihre Anfragen bearbeitet

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine einfache Konfiguration für eine einzelne BunkerWeb-Instanz:

    ```yaml
    SESSIONS_SECRET: "ihr-starker-zufälliger-geheimschlüssel-hier"
    SESSIONS_NAME: "meineappsitzung"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    ```

=== "Erhöhte Sicherheit"

    Konfiguration mit erhöhten Sicherheitseinstellungen:

    ```yaml
    SESSIONS_SECRET: "ihr-sehr-starker-zufälliger-geheimschlüssel-hier"
    SESSIONS_NAME: "sicheresitzung"
    SESSIONS_IDLING_TIMEOUT: "900"  # 15 Minuten
    SESSIONS_ROLLING_TIMEOUT: "1800"  # 30 Minuten
    SESSIONS_ABSOLUTE_TIMEOUT: "43200"  # 12 Stunden
    SESSIONS_CHECK_IP: "yes"
    SESSIONS_CHECK_USER_AGENT: "yes"
    ```

=== "Cluster-Umgebung mit Redis"

    Konfiguration für mehrere BunkerWeb-Instanzen, die Sitzungsdaten gemeinsam nutzen:

    ```yaml
    SESSIONS_SECRET: "ihr-starker-zufälliger-geheimschlüssel-hier"
    SESSIONS_NAME: "clustersitzung"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    USE_REDIS: "yes"
    # Stellen Sie sicher, dass die Redis-Verbindung korrekt konfiguriert ist
    ```

=== "Langlebige Sitzungen"

    Konfiguration für Anwendungen, die eine erweiterte Sitzungspersistenz erfordern:

    ```yaml
    SESSIONS_SECRET: "ihr-starker-zufälliger-geheimschlüssel-hier"
    SESSIONS_NAME: "persistentesitzung"
    SESSIONS_IDLING_TIMEOUT: "86400"  # 1 Tag
    SESSIONS_ROLLING_TIMEOUT: "172800"  # 2 Tage
    SESSIONS_ABSOLUTE_TIMEOUT: "604800"  # 7 Tage
    ```
