Das Client-Cache-Plugin optimiert die Leistung von Websites, indem es steuert, wie Browser statische Inhalte zwischenspeichern. Es reduziert die Bandbreitennutzung, senkt die Serverlast und verbessert die Ladezeiten von Seiten, indem es Browser anweist, statische Assets wie Bilder, CSS- und JavaScript-Dateien lokal zu speichern und wiederzuverwenden, anstatt sie bei jedem Seitenbesuch erneut anzufordern.

**So funktioniert es:**

1.  Wenn aktiviert, fügt BunkerWeb den Antworten für statische Dateien Cache-Control-Header hinzu.
2.  Diese Header teilen den Browsern mit, wie lange sie den Inhalt lokal zwischenspeichern sollen.
3.  Für Dateien mit bestimmten Erweiterungen (wie Bilder, CSS, JavaScript) wendet BunkerWeb die konfigurierte Caching-Richtlinie an.
4.  Die optionale ETag-Unterstützung bietet einen zusätzlichen Validierungsmechanismus, um festzustellen, ob der zwischengespeicherte Inhalt noch aktuell ist.
5.  Wenn Besucher auf Ihre Website zurückkehren, können ihre Browser lokal zwischengespeicherte Dateien verwenden, anstatt sie erneut herunterzuladen, was zu schnelleren Ladezeiten der Seite führt.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Client-Cache-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die Client-Cache-Funktion ist standardmäßig deaktiviert. Setzen Sie die Einstellung `USE_CLIENT_CACHE` auf `yes`, um sie zu aktivieren.
2.  **Dateierweiterungen konfigurieren:** Geben Sie mit der Einstellung `CLIENT_CACHE_EXTENSIONS` an, welche Dateitypen zwischengespeichert werden sollen.
3.  **Cache-Control-Anweisungen festlegen:** Passen Sie mit der Einstellung `CLIENT_CACHE_CONTROL` an, wie Clients Inhalte zwischenspeichern sollen.
4.  **ETag-Unterstützung konfigurieren:** Entscheiden Sie mit der Einstellung `CLIENT_CACHE_ETAG`, ob ETags zur Validierung der Cache-Frische aktiviert werden sollen.
5.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration werden Caching-Header automatisch auf berechtigte Antworten angewendet.

### Konfigurationseinstellungen

| Einstellung               | Standard                                                                  | Kontext   | Mehrfach | Beschreibung                                                                                                      |
| ------------------------- | ------------------------------------------------------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `USE_CLIENT_CACHE`        | `no`                                                                      | multisite | nein     | **Client-Cache aktivieren:** Auf `yes` setzen, um das clientseitige Caching von statischen Dateien zu aktivieren. |
| `CLIENT_CACHE_EXTENSIONS` | `jpg\|jpeg\|png\|bmp\|ico\|svg\|tif\|css\|js\|otf\|ttf\|eot\|woff\|woff2` | global    | nein     | **Cache-fähige Erweiterungen:** Liste der Dateierweiterungen (getrennt durch `                                    | `), die vom Client zwischengespeichert werden sollen. |
| `CLIENT_CACHE_CONTROL`    | `public, max-age=15552000`                                                | multisite | nein     | **Cache-Control-Header:** Wert für den Cache-Control-HTTP-Header zur Steuerung des Caching-Verhaltens.            |
| `CLIENT_CACHE_ETAG`       | `yes`                                                                     | multisite | nein     | **ETags aktivieren:** Auf `yes` setzen, um den HTTP-ETag-Header für statische Ressourcen zu senden.               |

!!! tip "Optimierung der Cache-Einstellungen"
    Für häufig aktualisierte Inhalte sollten Sie kürzere `max-age`-Werte verwenden. Für Inhalte, die sich selten ändern (wie versionierte JavaScript-Bibliotheken oder Logos), verwenden Sie längere Cache-Zeiten. Der Standardwert von 15552000 Sekunden (180 Tage) ist für die meisten statischen Assets angemessen.

!!! info "Browser-Verhalten"
    Unterschiedliche Browser implementieren Caching geringfügig anders, aber alle modernen Browser respektieren die Standard-Cache-Control-Anweisungen. ETags bieten einen zusätzlichen Validierungsmechanismus, der Browsern hilft festzustellen, ob zwischengespeicherte Inhalte noch gültig sind.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine einfache Konfiguration, die das Caching für gängige statische Assets aktiviert:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|gif|css|js|svg|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=86400"  # 1 Tag
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Aggressives Caching"

    Eine für maximales Caching optimierte Konfiguration, geeignet für Websites mit selten aktualisierten statischen Inhalten:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2|pdf|xml|txt"
    CLIENT_CACHE_CONTROL: "public, max-age=31536000, immutable"  # 1 Jahr
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Strategie für gemischte Inhalte"

    Für Websites mit einer Mischung aus häufig und selten aktualisierten Inhalten sollten Sie die Dateiversionierung in Ihrer Anwendung und eine Konfiguration wie diese in Betracht ziehen:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=604800"  # 1 Woche
    CLIENT_CACHE_ETAG: "yes"
    ```
