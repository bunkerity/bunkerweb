Das Redirect-Plugin bietet einfache und effiziente HTTP-Umleitungsfunktionen für Ihre von BunkerWeb geschützten Websites. Mit dieser Funktion können Sie Besucher problemlos von einer URL zu einer anderen umleiten und dabei sowohl Umleitungen für die gesamte Domain als auch für bestimmte Pfade mit Beibehaltung des Pfades unterstützen.

**So funktioniert es:**

1.  Wenn ein Besucher auf Ihre Website zugreift, überprüft BunkerWeb, ob eine Umleitung konfiguriert ist.
2.  Wenn aktiviert, leitet BunkerWeb den Besucher an die angegebene Ziel-URL weiter.
3.  Sie können konfigurieren, ob der ursprüngliche Anfragepfad beibehalten (automatisch an die Ziel-URL angehängt) oder direkt zur exakten Ziel-URL umgeleitet werden soll.
4.  Der für die Umleitung verwendete HTTP-Statuscode kann zwischen permanenten (301) und temporären (302) Umleitungen angepasst werden.
5.  Diese Funktionalität ist ideal für Domain-Migrationen, die Einrichtung kanonischer Domains oder die Umleitung veralteter URLs.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Umleitungsfunktion zu konfigurieren und zu verwenden:

1.  **Quellpfad festlegen:** Konfigurieren Sie den Pfad, von dem umgeleitet werden soll, mit der Einstellung `REDIRECT_FROM` (z. B. `/`, `/old-page`).
2.  **Ziel-URL festlegen:** Konfigurieren Sie die Ziel-URL, zu der Besucher umgeleitet werden sollen, mit der Einstellung `REDIRECT_TO`.
3.  **Umleitungstyp wählen:** Entscheiden Sie mit der Einstellung `REDIRECT_TO_REQUEST_URI`, ob der ursprüngliche Anfragepfad beibehalten werden soll.
4.  **Statuscode auswählen:** Legen Sie den entsprechenden HTTP-Statuscode mit der Einstellung `REDIRECT_TO_STATUS_CODE` fest, um eine permanente oder temporäre Umleitung anzuzeigen.
5.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration werden alle Anfragen an die Website automatisch basierend auf Ihren Einstellungen umgeleitet.

### Konfigurationseinstellungen

| Einstellung               | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                |
| ------------------------- | -------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_FROM`           | `/`      | multisite | ja       | **Pfad, von dem umgeleitet wird:** Der Pfad, der umgeleitet wird.                                                           |
| `REDIRECT_TO`             |          | multisite | ja       | **Ziel-URL:** Die Ziel-URL, zu der Besucher umgeleitet werden. Leer lassen, um die Umleitung zu deaktivieren.               |
| `REDIRECT_TO_REQUEST_URI` | `no`     | multisite | ja       | **Pfad beibehalten:** Wenn auf `yes` gesetzt, wird die ursprüngliche Anfrage-URI an die Ziel-URL angehängt.                 |
| `REDIRECT_TO_STATUS_CODE` | `301`    | multisite | ja       | **HTTP-Statuscode:** Der für die Umleitung zu verwendende HTTP-Statuscode. Optionen: `301`, `302`, `303`, `307` oder `308`. |

!!! tip "Wahl des richtigen Statuscodes"
    - **`301` (Moved Permanently):** Permanente Umleitung, wird von Browsern zwischengespeichert. Kann POST zu GET ändern. Ideal für Domain-Migrationen.
    - **`302` (Found):** Temporäre Umleitung. Kann POST zu GET ändern.
    - **`303` (See Other):** Leitet immer mit GET-Methode um. Nützlich nach Formularübermittlungen.
    - **`307` (Temporary Redirect):** Temporäre Umleitung, die die HTTP-Methode beibehält. Ideal für API-Umleitungen.
    - **`308` (Permanent Redirect):** Permanente Umleitung, die die HTTP-Methode beibehält. Für permanente API-Migrationen.

!!! info "Beibehaltung des Pfades"
    Wenn `REDIRECT_TO_REQUEST_URI` auf `yes` gesetzt ist, behält BunkerWeb den ursprünglichen Anfragepfad bei. Wenn ein Benutzer beispielsweise `https://old-domain.com/blog/post-1` besucht und Sie eine Umleitung zu `https://new-domain.com` eingerichtet haben, wird er zu `https://new-domain.com/blog/post-1` umgeleitet.

### Beispielkonfigurationen

=== "Umleitung mehrerer Pfade"

    Eine Konfiguration, die mehrere Pfade an verschiedene Ziele umleitet:

    ```yaml
    # Leitet /blog zu einer neuen Blog-Domain um
    REDIRECT_FROM: "/blog/"
    REDIRECT_TO: "https://blog.example.com/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"

    # Leitet /shop zu einer anderen Domain um
    REDIRECT_FROM_2: "/shop/"
    REDIRECT_TO_2: "https://shop.example.com/"
    REDIRECT_TO_REQUEST_URI_2: "no"
    REDIRECT_TO_STATUS_CODE_2: "301"

    # Leitet den Rest der Website um
    REDIRECT_FROM_3: "/"
    REDIRECT_TO_3: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI_3: "no"
    REDIRECT_TO_STATUS_CODE_3: "301"
    ```

=== "Einfache Domain-Umleitung"

    Eine Konfiguration, die alle Besucher auf eine neue Domain umleitet:

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Pfadbeibehaltende Umleitung"

    Eine Konfiguration, die Besucher auf eine neue Domain umleitet und dabei den angeforderten Pfad beibehält:

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Temporäre Umleitung"

    Eine Konfiguration für eine temporäre Umleitung zu einer Wartungsseite:

    ```yaml
    REDIRECT_TO: "https://maintenance.example.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "302"
    ```

=== "Subdomain-Konsolidierung"

    Eine Konfiguration zur Umleitung einer Subdomain auf einen bestimmten Pfad der Hauptdomain:

    ```yaml
    REDIRECT_TO: "https://example.com/support"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "API-Endpunkt-Migration"

    Eine Konfiguration für die permanente Umleitung eines API-Endpunkts unter Beibehaltung der HTTP-Methode:

    ```yaml
    REDIRECT_FROM: "/api/v1/"
    REDIRECT_TO: "https://api.example.com/v2/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "308"
    ```

=== "Nach Formularübermittlung"

    Eine Konfiguration zur Umleitung nach einer Formularübermittlung mit GET-Methode:

    ```yaml
    REDIRECT_TO: "https://example.com/danke"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "303"
    ```
