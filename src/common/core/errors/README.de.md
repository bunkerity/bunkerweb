Das Errors-Plugin bietet eine anpassbare Verwaltung von HTTP-Fehlern, um das Erscheinungsbild der Fehlerantworten für Ihre Benutzer zu definieren. So können Sie klare und konsistente Fehlerseiten anzeigen, die Ihrer Identität entsprechen, anstatt der technischen Standardseiten des Servers.

**So funktioniert's:**

1.  Wenn ein HTTP-Fehler auftritt (z.B. 400, 404, 500), fängt BunkerWeb die Antwort ab.
2.  Anstelle der Standardseite zeigt BunkerWeb eine angepasste und sorgfältig gestaltete Seite an.
3.  Die Fehlerseiten sind konfigurierbar: Sie können für jeden Fehlercode eine HTML-Datei bereitstellen. Die Dateien müssen in dem durch `ROOT_FOLDER` definierten Verzeichnis abgelegt werden (siehe Misc-Plugin).
    - Standardmäßig ist `ROOT_FOLDER` auf `/var/www/html/{server_name}` gesetzt.
    - Im Multisite-Modus hat jede Site ihren eigenen `ROOT_FOLDER`; platzieren Sie die Fehlerseiten im entsprechenden Ordner für jede Site.
4.  Die Standardseiten erklären das Problem klar und schlagen mögliche Maßnahmen vor.

### Verwendung

1.  **Benutzerdefinierte Seiten definieren:** Verwenden Sie `ERRORS`, um HTTP-Codes mit HTML-Dateien (im `ROOT_FOLDER`) zu verknüpfen.
2.  **Ihre Seiten konfigurieren:** Verwenden Sie die Standardseiten von BunkerWeb oder Ihre eigenen Dateien (im passenden `ROOT_FOLDER`).
3.  **Abgefangene Codes definieren:** Wählen Sie mit `INTERCEPTED_ERROR_CODES` die Codes aus, die immer von BunkerWeb verwaltet werden sollen.
4.  **Lassen Sie BunkerWeb den Rest erledigen:** Die Fehlerverwaltung wird automatisch angewendet.

### Parameter

| Parameter                 | Standard                                          | Kontext   | Mehrfach | Beschreibung                                                                                                                       |
| :------------------------ | :------------------------------------------------ | :-------- | :------- | :--------------------------------------------------------------------------------------------------------------------------------- |
| `ERRORS`                  |                                                   | Multisite | Nein     | Benutzerdefinierte Fehlerseiten: Paare `CODE=/pfad/seite.html`.                                                                    |
| `INTERCEPTED_ERROR_CODES` | `400 401 403 404 405 413 429 500 501 502 503 504` | Multisite | Nein     | Abgefangene Codes: Liste der Codes, die mit der Standardseite verwaltet werden, wenn keine benutzerdefinierte Seite definiert ist. |

!!! tip "Seiten-Design"
    Die Standard-Fehlerseiten von BunkerWeb sind informativ, benutzerfreundlich und professionell gestaltet. Sie enthalten:

    - Klare Fehlerbeschreibungen
    - Informationen zu möglichen Ursachen des Fehlers
    - Vorgeschlagene Maßnahmen zur Behebung des Problems
    - Visuelle Hinweise, die erkennen lassen, ob das Problem client- oder serverseitig ist

!!! info "Fehlertypen"
    Fehlercodes werden nach Typ kategorisiert:

    - **4xx-Fehler (Client-seitig):** Ungültige Anfragen, nicht existierende Ressource, fehlende Authentifizierung…
    - **5xx-Fehler (Server-seitig):** Unmöglichkeit, eine gültige Anfrage zu bearbeiten (interner Fehler, vorübergehende Nichtverfügbarkeit…).

### Beispiele

=== "Standardverwaltung"

    ```yaml
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Benutzerdefinierte Seiten"

    ```yaml
    ERRORS: "404=/custom/404.html 500=/custom/500.html"
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Selektive Verwaltung"

    ```yaml
    INTERCEPTED_ERROR_CODES: "404 500"
    ```

### Fehlerantworten von Upstream-APIs beibehalten

Standardmäßig ersetzt BunkerWeb 400-Antworten des Upstreams durch seine eigene Fehlerseite, was JSON-API- oder OIDC-Clients stören kann. Um Upstream-Fehler für einen Dienst durchzureichen, entfernen Sie entweder den Code aus der Liste dieses Dienstes, zum Beispiel `app.example.com_INTERCEPTED_ERROR_CODES=401 403 404 405 413 429 500 501 502 503 504` (behalten Sie die Codes, die weiterhin abgefangen werden sollen), oder setzen Sie `app.example.com_REVERSE_PROXY_INTERCEPT_ERRORS=no`, um jeden Upstream-Fehler durchzureichen. Fehler, die BunkerWeb selbst erzeugt (zum Beispiel eine WAF-Sperre), werden weiterhin von BunkerWeb behandelt.

Um Upstream-Fehler nur für eine Location beizubehalten, legen Sie eine Datei mit dem Inhalt `proxy_intercept_errors off;` an und tragen Sie sie in der Einstellung `REVERSE_PROXY_INCLUDES` dieser Location ein (zum Beispiel `app.example.com_REVERSE_PROXY_INCLUDES=/opt/keep-errors.conf`, mit demselben numerischen Suffix wie `REVERSE_PROXY_HOST` der Location). Die Datei muss in den BunkerWeb-Containern vorhanden sein. Die übrigen Locations des Dienstes fangen Fehler weiterhin ab.
