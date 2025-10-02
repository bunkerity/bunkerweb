Das Limit-Plugin in BunkerWeb bietet robuste Funktionen zur Durchsetzung von Begrenzungsrichtlinien auf Ihrer Website, um eine faire Nutzung zu gewährleisten und Ihre Ressourcen vor Missbrauch, Denial-of-Service-Angriffen und übermäßigem Ressourcenverbrauch zu schützen. Diese Richtlinien umfassen:

- **Anzahl der Verbindungen pro IP-Adresse** (STREAM-Unterstützung :white_check_mark:)
- **Anzahl der Anfragen pro IP-Adresse und URL innerhalb eines bestimmten Zeitraums** (STREAM-Unterstützung :x:)

### Wie es funktioniert

1.  **Ratenbegrenzung:** Verfolgt die Anzahl der Anfragen von jeder Client-IP-Adresse an bestimmte URLs. Wenn ein Client die konfigurierte Ratenbegrenzung überschreitet, werden nachfolgende Anfragen vorübergehend abgelehnt.
2.  **Verbindungsbegrenzung:** Überwacht und beschränkt die Anzahl der gleichzeitigen Verbindungen von jeder Client-IP-Adresse. Je nach verwendetem Protokoll (HTTP/1, HTTP/2, HTTP/3 oder Stream) können unterschiedliche Verbindungsgrenzen angewendet werden.
3.  In beiden Fällen erhalten Clients, die die definierten Grenzwerte überschreiten, den HTTP-Statuscode **„429 - Too Many Requests“**, was hilft, eine Serverüberlastung zu verhindern.

### Schritte zur Verwendung

1.  **Anforderungsratenbegrenzung aktivieren:** Verwenden Sie `USE_LIMIT_REQ`, um die Anforderungsratenbegrenzung zu aktivieren und URL-Muster zusammen mit ihren entsprechenden Ratenbegrenzungen zu definieren.
2.  **Verbindungsbegrenzung aktivieren:** Verwenden Sie `USE_LIMIT_CONN`, um die Verbindungsbegrenzung zu aktivieren und die maximale Anzahl gleichzeitiger Verbindungen für verschiedene Protokolle festzulegen.
3.  **Granulare Kontrolle anwenden:** Erstellen Sie mehrere Ratenbegrenzungsregeln für verschiedene URLs, um unterschiedliche Schutzniveaus auf Ihrer gesamten Website bereitzustellen.
4.  **Wirksamkeit überwachen:** Verwenden Sie die [Web-Benutzeroberfläche](web-ui.md), um Statistiken über begrenzte Anfragen und Verbindungen anzuzeigen.

### Konfigurationseinstellungen

=== "Anforderungsratenbegrenzung"

    | Einstellung      | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                                             |
    | ---------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
    | `USE_LIMIT_REQ`  | `yes`    | multisite | nein     | **Anforderungsbegrenzung aktivieren:** Auf `yes` setzen, um die Funktion zur Ratenbegrenzung von Anfragen zu aktivieren.                                                 |
    | `LIMIT_REQ_URL`  | `/`      | multisite | ja       | **URL-Muster:** URL-Muster (PCRE-Regex), auf das die Ratenbegrenzung angewendet wird; verwenden Sie `/`, um es für alle Anfragen anzuwenden.                             |
    | `LIMIT_REQ_RATE` | `2r/s`   | multisite | ja       | **Ratenbegrenzung:** Maximale Anfragerate im Format `Nr/t`, wobei N die Anzahl der Anfragen und t die Zeiteinheit ist: s (Sekunde), m (Minute), h (Stunde) oder d (Tag). |

!!! tip "Format der Ratenbegrenzung"
Das Format der Ratenbegrenzung wird als `Nr/t` angegeben, wobei:

    - `N` die Anzahl der erlaubten Anfragen ist
    - `r` ein literales 'r' ist (für 'requests')
    - `/` ein literaler Schrägstrich ist
    - `t` die Zeiteinheit ist: `s` (Sekunde), `m` (Minute), `h` (Stunde) oder `d` (Tag)

    Zum Beispiel bedeutet `5r/m`, dass 5 Anfragen pro Minute von jeder IP-Adresse erlaubt sind.

=== "Verbindungsbegrenzung"

    | Einstellung             | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                     |
    | ----------------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
    | `USE_LIMIT_CONN`        | `yes`    | multisite | nein     | **Verbindungsbegrenzung aktivieren:** Auf `yes` setzen, um die Funktion zur Verbindungsbegrenzung zu aktivieren. |
    | `LIMIT_CONN_MAX_HTTP1`  | `10`     | multisite | nein     | **HTTP/1.X-Verbindungen:** Maximale Anzahl gleichzeitiger HTTP/1.X-Verbindungen pro IP-Adresse.                  |
    | `LIMIT_CONN_MAX_HTTP2`  | `100`    | multisite | nein     | **HTTP/2-Streams:** Maximale Anzahl gleichzeitiger HTTP/2-Streams pro IP-Adresse.                                |
    | `LIMIT_CONN_MAX_HTTP3`  | `100`    | multisite | nein     | **HTTP/3-Streams:** Maximale Anzahl gleichzeitiger HTTP/3-Streams pro IP-Adresse.                                |
    | `LIMIT_CONN_MAX_STREAM` | `10`     | multisite | nein     | **Stream-Verbindungen:** Maximale Anzahl gleichzeitiger Stream-Verbindungen pro IP-Adresse.                      |

!!! info "Verbindungs- vs. Anforderungsbegrenzung"

- **Verbindungsbegrenzung** beschränkt die Anzahl der gleichzeitigen Verbindungen, die eine einzelne IP-Adresse aufrechterhalten kann.
- **Anforderungsratenbegrenzung** beschränkt die Anzahl der Anfragen, die eine IP-Adresse innerhalb eines definierten Zeitraums stellen kann.

  Die Verwendung beider Methoden bietet einen umfassenden Schutz gegen verschiedene Arten von Missbrauch.

!!! warning "Festlegen angemessener Grenzwerte"
Zu restriktive Grenzwerte können legitime Benutzer beeinträchtigen, insbesondere bei HTTP/2 und HTTP/3, wo Browser oft mehrere Streams verwenden. Die Standardwerte sind für die meisten Anwendungsfälle ausgewogen, aber erwägen Sie, sie je nach den Bedürfnissen Ihrer Anwendung und dem Benutzerverhalten anzupassen.

### Beispielkonfigurationen

=== "Grundschutz"

    Eine einfache Konfiguration mit Standardeinstellungen zum Schutz Ihrer gesamten Website:

    ```yaml
    USE_LIMIT_REQ: "yes"
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "2r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "Schutz spezifischer Endpunkte"

    Konfiguration mit unterschiedlichen Ratenbegrenzungen für verschiedene Endpunkte:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Standardregel für alle Anfragen
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "10r/s"

    # Strengere Begrenzung für die Anmeldeseite
    LIMIT_REQ_URL_2: "^/login"
    LIMIT_REQ_RATE_2: "1r/s"

    # Strengere Begrenzung für die API
    LIMIT_REQ_URL_3: "^/api/"
    LIMIT_REQ_RATE_3: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "Konfiguration für eine Website mit hohem Verkehrsaufkommen"

    Konfiguration, die für Websites mit hohem Verkehrsaufkommen mit großzügigeren Grenzwerten optimiert ist:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Allgemeine Begrenzung
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "30r/s"

    # Schutz des Admin-Bereichs
    LIMIT_REQ_URL_2: "^/admin/"
    LIMIT_REQ_RATE_2: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "50"
    LIMIT_CONN_MAX_HTTP2: "200"
    LIMIT_CONN_MAX_HTTP3: "200"
    LIMIT_CONN_MAX_STREAM: "30"
    ```

=== "Konfiguration für einen API-Server"

    Konfiguration, die für einen API-Server mit Ratenbegrenzungen in Anfragen pro Minute optimiert ist:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Öffentliche API-Endpunkte
    LIMIT_REQ_URL: "^/api/public/"
    LIMIT_REQ_RATE: "120r/m"

    # Private API-Endpunkte
    LIMIT_REQ_URL_2: "^/api/private/"
    LIMIT_REQ_RATE_2: "300r/m"

    # Authentifizierungsendpunkt
    LIMIT_REQ_URL_3: "^/api/auth"
    LIMIT_REQ_RATE_3: "10r/m"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "20"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "20"
    ```
