Das Errors-Plugin bietet eine anpassbare Verwaltung von HTTP-Fehlern, um das Erscheinungsbild der Fehlerantworten für Ihre Benutzer zu definieren. So können Sie klare and konsistente Fehlerseiten anzeigen, die Ihrer Identität entsprechen, anstatt der technischen Standardseiten des Servers.

**So funktioniert's:**

1.  Wenn ein HTTP-Fehler auftritt (z.B. 400, 404, 500), fängt BunkerWeb die Antwort ab.
2.  Anstelle der Standardseite zeigt BunkerWeb eine angepasste and sorgfältig gestaltete Seite an.
3.  Die Fehlerseiten sind konfigurierbar: Sie können für jeden Fehlercode eine HTML-Datei bereitstellen. Die Dateien müssen in dem durch `ROOT_FOLDER` definierten Verzeichnis abgelegt werden (siehe Misc-Plugin).
    - Standardmäßig ist `ROOT_FOLDER` auf `/var/www/html/{server_name}` gesetzt.
    - Im Multisite-Modus hat jede Site ihren eigenen `ROOT_FOLDER`; platzieren Sie die Fehlerseiten im entsprechenden Ordner für jede Site.
4.  Die Standardseiten erklären das Problem klar and schlagen mögliche Maßnahmen vor.

### Verwendung

1.  **Benutzerdefinierte Seiten definieren:** Verwenden Sie `ERRORS`, um HTTP-Codes mit HTML-Dateien (im `ROOT_FOLDER`) zu verknüpfen.
2.  **Ihre Seiten konfigurieren:** Verwenden Sie die Standardseiten von BunkerWeb oder Ihre eigenen Dateien.
3.  **Abgefangene Codes definieren:** Wählen Sie mit `INTERCEPTED_ERROR_CODES` die Codes aus, die immer von BunkerWeb verwaltet werden sollen.
4.  **Lassen Sie BunkerWeb den Rest erledigen:** Die Fehlerverwaltung wird automatisch angewendet.

### Parameter

| Parameter                 | Standard                                          | Kontext   | Mehrfach | Beschreibung                                                                                                                       |
| :------------------------ | :------------------------------------------------ | :-------- | :------- | :--------------------------------------------------------------------------------------------------------------------------------- |
| `ERRORS`                  |                                                   | Multisite | Nein     | Benutzerdefinierte Fehlerseiten: Paare `CODE=/pfad/seite.html`.                                                                    |
| `INTERCEPTED_ERROR_CODES` | `400 401 403 404 405 413 429 500 501 502 503 504` | Multisite | Nein     | Abgefangene Codes: Liste der Codes, die mit der Standardseite verwaltet werden, wenn keine benutzerdefinierte Seite definiert ist. |

!!! tip "Seiten-Design"
Die Standardseiten sind klar and lehrreich: Fehlerbeschreibung, mögliche Ursachen, vorgeschlagene Maßnahmen and visuelle Anhaltspunkte.

!!! info "Fehlertypen"

- 4xx (Client-seitig): Ungültige Anfragen, nicht existierende Ressource, fehlende Authentifizierung…
- 5xx (Server-seitig): Unmöglichkeit, eine gültige Anfrage zu bearbeiten (interner Fehler, vorübergehende Nichtverfügbarkeit…).

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
