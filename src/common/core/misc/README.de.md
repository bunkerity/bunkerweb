Das Plugin "Verschiedenes" (Miscellaneous) bietet **wesentliche Grundeinstellungen**, die helfen, die Sicherheit und Funktionalität Ihrer Website aufrechtzuerhalten. Diese Kernkomponente bietet umfassende Kontrollen für:

- **Serververhalten** - Konfigurieren Sie, wie Ihr Server auf verschiedene Anfragen reagiert
- **HTTP-Einstellungen** - Verwalten Sie Methoden, Anforderungsgrößen und Protokolloptionen
- **Dateiverwaltung** - Steuern Sie die Bereitstellung statischer Dateien und optimieren Sie deren Auslieferung
- **Protokollunterstützung** - Aktivieren Sie moderne HTTP-Protokolle für eine bessere Leistung
- **Systemkonfigurationen** - Erweitern Sie die Funktionalität und verbessern Sie die Sicherheit

Ob Sie HTTP-Methoden einschränken, Anforderungsgrößen verwalten, das Datei-Caching optimieren oder steuern müssen, wie Ihr Server auf verschiedene Anfragen reagiert, dieses Plugin gibt Ihnen die Werkzeuge, um **das Verhalten Ihres Webdienstes feinabzustimmen** und gleichzeitig Leistung und Sicherheit zu optimieren.

### Hauptmerkmale

| Funktionskategorie                    | Beschreibung                                                                                                   |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Steuerung der HTTP-Methoden**       | Definieren Sie, welche HTTP-Methoden für Ihre Anwendung zulässig sind                                          |
| **Schutz des Standardservers**        | Verhindern Sie unbefugten Zugriff durch falsche Hostnamen und erzwingen Sie SNI für sichere Verbindungen       |
| **Verwaltung der Anforderungsgröße**  | Legen Sie Grenzwerte für Client-Anforderungskörper und Datei-Uploads fest                                      |
| **Bereitstellung statischer Dateien** | Konfigurieren und optimieren Sie die Auslieferung von statischen Inhalten aus benutzerdefinierten Stammordnern |
| **Datei-Caching**                     | Verbessern Sie die Leistung durch fortschrittliche Caching-Mechanismen für Dateideskriptoren                   |
| **Protokollunterstützung**            | Konfigurieren Sie moderne HTTP-Protokolloptionen (HTTP2/HTTP3) und Alt-Svc-Porteinstellungen                   |
| **Anonyme Berichterstattung**         | Optionale Nutzungsstatistik-Berichterstattung zur Verbesserung von BunkerWeb                                   |
| **Unterstützung für externe Plugins** | Erweitern Sie die Funktionalität durch die Integration externer Plugins über URLs                              |
| **Steuerung des HTTP-Status**         | Konfigurieren Sie, wie Ihr Server bei der Ablehnung von Anfragen reagiert (einschließlich Verbindungsabbruch)  |

### Konfigurationsanleitung

=== "Sicherheit des Standardservers"

    **Steuerung des Standardservers**

    In HTTP gibt der `Host`-Header den Zielserver an, aber er kann fehlen oder unbekannt sein, oft aufgrund von Bots, die nach Schwachstellen suchen.

    Um solche Anfragen zu blockieren:

    - Setzen Sie `DISABLE_DEFAULT_SERVER` auf `yes`, um solche Anfragen stillschweigend mit dem [NGINX-Statuscode `444`](https://http.dev/444) abzulehnen.
    - Für eine strengere Sicherheit aktivieren Sie `DISABLE_DEFAULT_SERVER_STRICT_SNI`, um SSL/TLS-Verbindungen ohne gültiges SNI abzulehnen.

    !!! success "Sicherheitsvorteile"
        - Blockiert die Manipulation des Host-Headers und das Scannen von virtuellen Hosts
        - Mindert die Risiken von HTTP-Request-Smuggling
        - Entfernt den Standardserver als Angriffsvektor

    | Einstellung                         | Standard | Kontext | Mehrfach | Beschreibung                                                                                                                               |
    | ----------------------------------- | -------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
    | `DISABLE_DEFAULT_SERVER`            | `no`     | global  | nein     | **Standardserver:** Auf `yes` setzen, um den Standardserver zu deaktivieren, wenn kein Hostname mit der Anfrage übereinstimmt.             |
    | `DISABLE_DEFAULT_SERVER_STRICT_SNI` | `no`     | global  | nein     | **Striktes SNI:** Wenn auf `yes` gesetzt, ist SNI für HTTPS-Verbindungen erforderlich und Verbindungen ohne gültiges SNI werden abgelehnt. |

    !!! warning "SNI-Erzwingung"
        Die Aktivierung der strikten SNI-Validierung bietet eine stärkere Sicherheit, kann jedoch Probleme verursachen, wenn BunkerWeb hinter einem Reverse-Proxy betrieben wird, der HTTPS-Anfragen ohne Beibehaltung der SNI-Informationen weiterleitet. Testen Sie gründlich, bevor Sie dies in Produktionsumgebungen aktivieren.

=== "HTTP-Status bei Ablehnung"

    **Steuerung des HTTP-Status**

    Der erste Schritt bei der Behandlung von verweigertem Client-Zugriff ist die Definition der geeigneten Aktion. Dies kann mit der Einstellung `DENY_HTTP_STATUS` konfiguriert werden. Wenn BunkerWeb eine Anfrage ablehnt, können Sie seine Antwort steuern. Standardmäßig gibt es einen `403 Forbidden`-Status zurück und zeigt dem Client eine Webseite oder benutzerdefinierten Inhalt an.

    Alternativ schließt das Setzen auf `444` die Verbindung sofort, ohne eine Antwort zu senden. Dieser [nicht standardmäßige Statuscode](https://http.dev/444), der spezifisch für NGINX ist, ist nützlich, um unerwünschte Anfragen stillschweigend zu verwerfen.

    | Einstellung        | Standard | Kontext | Mehrfach | Beschreibung                                                                                                                                          |
    | ------------------ | -------- | ------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `DENY_HTTP_STATUS` | `403`    | global  | nein     | **HTTP-Status bei Ablehnung:** HTTP-Statuscode, der gesendet wird, wenn eine Anfrage abgelehnt wird (403 oder 444). Code 444 schließt die Verbindung. |

    !!! warning "Überlegungen zum Statuscode 444"
        Da Clients kein Feedback erhalten, kann die Fehlerbehebung schwieriger sein. Das Setzen von `444` wird nur empfohlen, wenn Sie Falsch-Positive gründlich behandelt haben, mit BunkerWeb erfahren sind und ein höheres Sicherheitsniveau benötigen.

    !!! info "Stream-Modus"
        Im **Stream-Modus** wird diese Einstellung immer als `444` erzwungen, was bedeutet, dass die Verbindung geschlossen wird, unabhängig vom konfigurierten Wert.

=== "HTTP-Methoden"

    **Steuerung der HTTP-Methoden**

    Die Beschränkung der HTTP-Methoden auf nur diejenigen, die von Ihrer Anwendung benötigt werden, ist eine grundlegende Sicherheitsmaßnahme, die dem Prinzip der geringsten Rechte folgt. Indem Sie explizit zulässige HTTP-Methoden definieren, können Sie das Risiko der Ausnutzung durch ungenutzte oder gefährliche Methoden minimieren.

    Diese Funktion wird mit der Einstellung `ALLOWED_METHODS` konfiguriert, wobei die Methoden aufgelistet und durch ein `|` getrennt sind (Standard: `GET|POST|HEAD`). Wenn ein Client versucht, eine nicht aufgelistete Methode zu verwenden, antwortet der Server mit einem **405 - Method Not Allowed**-Status.

    Für die meisten Websites ist der Standardwert `GET|POST|HEAD` ausreichend. Wenn Ihre Anwendung RESTful-APIs verwendet, müssen Sie möglicherweise Methoden wie `PUT` und `DELETE` hinzufügen.

    !!! success "Sicherheitsvorteile"
        - Verhindert die Ausnutzung von ungenutzten oder unnötigen HTTP-Methoden
        - Reduziert die Angriffsfläche durch Deaktivierung potenziell schädlicher Methoden
        - Blockiert von Angreifern verwendete Techniken zur Aufzählung von HTTP-Methoden

    | Einstellung       | Standard          | Kontext   | Mehrfach | Beschreibung                                                                         |
    | ----------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------ |
    | `ALLOWED_METHODS` | `GET\|POST\|HEAD` | multisite | nein     | **HTTP-Methoden:** Liste der erlaubten HTTP-Methoden, getrennt durch Pipe-Zeichen (` | `). |

    !!! abstract "CORS und Preflight-Anfragen"
        Wenn Ihre Anwendung [Cross-Origin Resource Sharing (CORS)](#cors) unterstützt, sollten Sie die `OPTIONS`-Methode in der `ALLOWED_METHODS`-Einstellung aufnehmen, um Preflight-Anfragen zu bearbeiten. Dies gewährleistet die ordnungsgemäße Funktionalität für Browser, die Cross-Origin-Anfragen stellen.

    !!! danger "Sicherheitsüberlegungen"
        - **Vermeiden Sie die Aktivierung von `TRACE` oder `CONNECT`:** Diese Methoden werden selten benötigt und können erhebliche Sicherheitsrisiken mit sich bringen, wie z. B. die Ermöglichung von Cross-Site-Tracing (XST) oder Tunneling-Angriffen.
        - **Überprüfen Sie regelmäßig die erlaubten Methoden:** Überprüfen Sie die `ALLOWED_METHODS`-Einstellung regelmäßig, um sicherzustellen, dass sie den aktuellen Anforderungen Ihrer Anwendung entspricht.
        - **Testen Sie gründlich vor der Bereitstellung:** Änderungen an den Einschränkungen von HTTP-Methoden können die Anwendungsfunktionalität beeinträchtigen. Validieren Sie Ihre Konfiguration in einer Staging-Umgebung, bevor Sie sie in der Produktion anwenden.

=== "Inhaltstypen"

    **Steuerung der Inhaltstypen**

    Die Beschränkung der Inhaltstypen auf nur diejenigen, die von Ihrer Anwendung benötigt werden, ist eine wichtige Sicherheitsmaßnahme, die hilft, Ausnutzung durch unerwartete Inhaltstypen zu verhindern. Indem Sie explizit zulässige Inhaltstypen definieren, können Sie das Risiko von Angriffen minimieren, die auf unerwarteten oder bösartigen Content-Type-Headern beruhen.

    Diese Funktion wird mit der Einstellung `ALLOWED_CONTENT_TYPES` konfiguriert, wobei die Inhaltstypen aufgelistet und durch Leerzeichen getrennt sind (Standard: `application/x-www-form-urlencoded multipart/form-data text/xml application/xml application/soap+xml application/json application/reports+json application/csp-report`). Wenn ein Client eine Anfrage mit einem nicht aufgelisteten Inhaltstyp sendet, antwortet der Server mit einem **415 - Unsupported Media Type**-Status.

    Der Standardsatz von Inhaltstypen deckt gängige Anforderungen von Webanwendungen ab, einschließlich Formularübermittlungen, Datei-Uploads, XML/SOAP-Anfragen und JSON-APIs.

    !!! success "Sicherheitsvorteile"
        - Verhindert Ausnutzung durch unerwartete oder bösartige Inhaltstypen
        - Reduziert die Angriffsfläche durch Ablehnung ungewöhnlicher Inhaltstypen
        - Blockiert Angriffe durch Content-Type-Manipulation
        - Bietet Defense-in-Depth zusammen mit ModSecurity-Regeln

    | Einstellung             | Standard                                                                                                                                                               | Kontext   | Mehrfach | Beschreibung                                                                    |
    | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------- |
    | `ALLOWED_CONTENT_TYPES` | `application/x-www-form-urlencoded multipart/form-data text/xml application/xml application/soap+xml application/json application/reports+json application/csp-report` | multisite | nein     | **Inhaltstypen:** Liste der erlaubten Inhaltstypen, getrennt durch Leerzeichen. |

    !!! info "Content-Type-Prüfung"
        - Die Content-Type-Prüfung gilt nur, wenn ein `Content-Type`-Header in der Anfrage vorhanden ist
        - Der Basis-Inhaltstyp wird extrahiert (z.B. `application/json` aus `application/json; charset=utf-8`)
        - GET- und HEAD-Anfragen enthalten normalerweise keinen Content-Type-Header und unterliegen daher nicht dieser Prüfung

    !!! danger "Sicherheitsüberlegungen"
        - **Überprüfen Sie die Anforderungen Ihrer Anwendung:** Stellen Sie sicher, dass die erlaubten Inhaltstypen den tatsächlichen Anforderungen Ihrer Anwendung entsprechen
        - **Seien Sie vorsichtig mit ungewöhnlichen Typen:** Fügen Sie nur Inhaltstypen hinzu, die tatsächlich von Ihrer Anwendung benötigt werden
        - **Testen Sie gründlich vor der Bereitstellung:** Änderungen an den Content-Type-Beschränkungen können die Anwendungsfunktionalität beeinträchtigen. Validieren Sie Ihre Konfiguration in einer Staging-Umgebung
        - **Berücksichtigen Sie die ModSecurity-Integration:** Diese Prüfung arbeitet zusammen mit ModSecurity-Regeln für eine umfassende Content-Type-Validierung

=== "Größenbeschränkungen für Anfragen"

    **Größenbeschränkungen für Anfragen**

    Die maximale Größe des Anforderungskörpers kann mit der Einstellung `MAX_CLIENT_SIZE` gesteuert werden (Standard: `10m`). Akzeptierte Werte folgen der [hier](https://nginx.org/en/docs/syntax.html) beschriebenen Syntax.

    !!! success "Sicherheitsvorteile"
        - Schützt vor Denial-of-Service-Angriffen durch übermäßige Payload-Größen
        - Mildert Pufferüberlauf-Schwachstellen
        - Verhindert Angriffe durch Datei-Uploads
        - Reduziert das Risiko der Erschöpfung von Serverressourcen

    | Einstellung       | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                     |
    | ----------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
    | `MAX_CLIENT_SIZE` | `10m`    | multisite | nein     | **Maximale Anforderungsgröße:** Die maximal zulässige Größe für Client-Anforderungskörper (z. B. Datei-Uploads). |

    !!! tip "Best Practices für die Konfiguration der Anforderungsgröße"
        Wenn Sie einen Anforderungskörper von unbegrenzter Größe zulassen müssen, können Sie den Wert `MAX_CLIENT_SIZE` auf `0` setzen. Dies wird jedoch aufgrund potenzieller Sicherheits- und Leistungsrisiken **nicht empfohlen**.

        **Best Practices:**

        - Konfigurieren Sie `MAX_CLIENT_SIZE` immer auf den kleinstmöglichen Wert, der die legitimen Anforderungen Ihrer Anwendung erfüllt.
        - Überprüfen und passen Sie diese Einstellung regelmäßig an die sich ändernden Bedürfnisse Ihrer Anwendung an.
        - Vermeiden Sie es, `0` zu setzen, es sei denn, es ist absolut notwendig, da dies Ihren Server Denial-of-Service-Angriffen und Ressourcenerschöpfung aussetzen kann.

        Durch sorgfältige Verwaltung dieser Einstellung können Sie optimale Sicherheit und Leistung für Ihre Anwendung gewährleisten.

=== "Protokollunterstützung"

    **HTTP-Protokolleinstellungen**

    Moderne HTTP-Protokolle wie HTTP/2 und HTTP/3 verbessern Leistung und Sicherheit. BunkerWeb ermöglicht eine einfache Konfiguration dieser Protokolle.

    !!! success "Sicherheits- und Leistungsvorteile"
        - **Sicherheitsvorteile:** Moderne Protokolle wie HTTP/2 und HTTP/3 erzwingen standardmäßig TLS/HTTPS, reduzieren die Anfälligkeit für bestimmte Angriffe und verbessern die Privatsphäre durch verschlüsselte Header (HTTP/3).
        - **Leistungsvorteile:** Funktionen wie Multiplexing, Header-Komprimierung, Server-Push und binäre Datenübertragung verbessern Geschwindigkeit und Effizienz.

    | Einstellung          | Standard | Kontext   | Mehrfach | Beschreibung                                                                      |
    | -------------------- | -------- | --------- | -------- | --------------------------------------------------------------------------------- |
    | `LISTEN_HTTP`        | `yes`    | multisite | nein     | **HTTP-Listen:** Auf (unsichere) HTTP-Anfragen antworten, wenn auf `yes` gesetzt. |
    | `HTTP2`              | `yes`    | multisite | nein     | **HTTP2:** Unterstützt das HTTP2-Protokoll, wenn HTTPS aktiviert ist.             |
    | `HTTP3`              | `yes`    | multisite | nein     | **HTTP3:** Unterstützt das HTTP3-Protokoll, wenn HTTPS aktiviert ist.             |
    | `HTTP3_ALT_SVC_PORT` | `443`    | multisite | nein     | **HTTP3 Alt-Svc Port:** Port, der im Alt-Svc-Header für HTTP3 verwendet wird.     |

    !!! example "Über HTTP/3"
        HTTP/3, die neueste Version des Hypertext Transfer Protocol, verwendet QUIC über UDP anstelle von TCP und behebt Probleme wie das Head-of-Line-Blocking für schnellere, zuverlässigere Verbindungen.

        NGINX hat ab Version 1.25.0 experimentelle Unterstützung für HTTP/3 und QUIC eingeführt. Diese Funktion ist jedoch noch experimentell, und bei der Verwendung in der Produktion ist Vorsicht geboten. Weitere Einzelheiten finden Sie in der [offiziellen Dokumentation von NGINX](https://nginx.org/en/docs/quic.html).

        Gründliche Tests werden empfohlen, bevor HTTP/3 in Produktionsumgebungen aktiviert wird.

=== "Bereitstellung statischer Dateien"

    **Konfiguration der Dateibereitstellung**

    BunkerWeb kann statische Dateien direkt bereitstellen oder als Reverse-Proxy zu einem Anwendungsserver fungieren. Standardmäßig werden Dateien aus `/var/www/html/{server_name}` bereitgestellt.

    | Einstellung   | Standard                      | Kontext   | Mehrfach | Beschreibung                                                                                                                           |
    | ------------- | ----------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
    | `SERVE_FILES` | `yes`                         | multisite | nein     | **Dateien bereitstellen:** Wenn auf `yes` gesetzt, stellt BunkerWeb statische Dateien aus dem konfigurierten Stammordner bereit.       |
    | `ROOT_FOLDER` | `/var/www/html/{server_name}` | multisite | nein     | **Stammordner:** Das Verzeichnis, aus dem statische Dateien bereitgestellt werden sollen. Leer bedeutet, den Standardort zu verwenden. |

    !!! tip "Best Practices für die Bereitstellung statischer Dateien"
        - **Direkte Bereitstellung:** Aktivieren Sie die Dateibereitstellung (`SERVE_FILES=yes`), wenn BunkerWeb für die direkte Bereitstellung statischer Dateien verantwortlich ist.
        - **Reverse-Proxy:** Wenn BunkerWeb als Reverse-Proxy fungiert, **deaktivieren Sie die Dateibereitstellung** (`SERVE_FILES=no`), um die Angriffsfläche zu reduzieren und die Exposition unnötiger Verzeichnisse zu vermeiden.
        - **Berechtigungen:** Stellen Sie sicher, dass die Dateiberechtigungen und Pfadkonfigurationen korrekt sind, um unbefugten Zugriff zu verhindern.
        - **Sicherheit:** Vermeiden Sie die Exposition sensibler Verzeichnisse oder Dateien durch Fehlkonfigurationen.

        Durch sorgfältige Verwaltung der Bereitstellung statischer Dateien können Sie die Leistung optimieren und gleichzeitig eine sichere Umgebung aufrechterhalten.

=== "Systemeinstellungen"

    **Plugin- und Systemverwaltung**

    Diese Einstellungen verwalten die Interaktion von BunkerWeb mit externen Systemen und tragen durch optionale anonyme Nutzungsstatistiken zur Verbesserung des Produkts bei.

    **Anonyme Berichterstattung**

    Die anonyme Berichterstattung gibt dem BunkerWeb-Team Einblicke, wie die Software verwendet wird. Dies hilft, Verbesserungsbereiche zu identifizieren und die Entwicklung von Funktionen zu priorisieren. Die Berichte sind rein statistisch und enthalten keine sensiblen oder persönlich identifizierbaren Informationen. Sie umfassen:

    - Aktivierte Funktionen
    - Allgemeine Konfigurationsmuster

    Sie können diese Funktion bei Bedarf deaktivieren, indem Sie `SEND_ANONYMOUS_REPORT` auf `no` setzen.

    **Externe Plugins**

    Externe Plugins ermöglichen es Ihnen, die Funktionalität von BunkerWeb durch die Integration von Drittanbieter-Modulen zu erweitern. Dies ermöglicht zusätzliche Anpassungen und fortgeschrittene Anwendungsfälle.

    !!! danger "Sicherheit externer Plugins"
        **Externe Plugins können Sicherheitsrisiken mit sich bringen, wenn sie nicht ordnungsgemäß überprüft werden.** Befolgen Sie diese Best Practices, um potenzielle Bedrohungen zu minimieren:

        - Verwenden Sie nur Plugins aus vertrauenswürdigen Quellen.
        - Überprüfen Sie die Integrität der Plugins mithilfe von Prüfsummen, sofern verfügbar.
        - Überprüfen und aktualisieren Sie Plugins regelmäßig, um Sicherheit und Kompatibilität zu gewährleisten.

        Weitere Einzelheiten finden Sie in der [Plugin-Dokumentation](plugins.md).

    | Einstellung             | Standard | Kontext | Mehrfach | Beschreibung                                                                                  |
    | ----------------------- | -------- | ------- | -------- | --------------------------------------------------------------------------------------------- |
    | `SEND_ANONYMOUS_REPORT` | `yes`    | global  | nein     | **Anonyme Berichte:** Senden Sie anonyme Nutzungsberichte an die BunkerWeb-Maintainer.        |
    | `EXTERNAL_PLUGIN_URLS`  |          | global  | nein     | **Externe Plugins:** URLs für externe Plugins zum Herunterladen (durch Leerzeichen getrennt). |

=== "Datei-Caching"

    **Optimierung des Datei-Cache**

    Der Cache für offene Dateien verbessert die Leistung, indem er Dateideskriptoren und Metadaten im Speicher speichert und so die Notwendigkeit wiederholter Dateisystemoperationen reduziert.

    !!! success "Vorteile des Datei-Caching"
        - **Leistung:** Reduziert Dateisystem-I/O, verringert die Latenz und senkt die CPU-Auslastung für Dateioperationen.
        - **Sicherheit:** Mildert Timing-Angriffe durch Caching von Fehlerantworten und reduziert die Auswirkungen von DoS-Angriffen auf das Dateisystem.

    | Einstellung                | Standard                | Kontext   | Mehrfach | Beschreibung                                                                                                                |
    | -------------------------- | ----------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------- |
    | `USE_OPEN_FILE_CACHE`      | `no`                    | multisite | nein     | **Cache aktivieren:** Aktivieren Sie das Caching von Dateideskriptoren und Metadaten, um die Leistung zu verbessern.        |
    | `OPEN_FILE_CACHE`          | `max=1000 inactive=20s` | multisite | nein     | **Cache-Konfiguration:** Konfigurieren Sie den Cache für offene Dateien (z. B. maximale Einträge und Inaktivitäts-Timeout). |
    | `OPEN_FILE_CACHE_ERRORS`   | `yes`                   | multisite | nein     | **Fehler zwischenspeichern:** Speichert Fehler bei der Suche nach Dateideskriptoren sowie erfolgreiche Suchen zwischen.     |
    | `OPEN_FILE_CACHE_MIN_USES` | `2`                     | multisite | nein     | **Mindestverwendungen:** Mindestanzahl von Zugriffen während des inaktiven Zeitraums, damit eine Datei im Cache verbleibt.  |
    | `OPEN_FILE_CACHE_VALID`    | `30s`                   | multisite | nein     | **Cache-Gültigkeit:** Zeit, nach der zwischengespeicherte Elemente erneut validiert werden.                                 |

    **Konfigurationsanleitung**

    So aktivieren und konfigurieren Sie das Datei-Caching:
    1. Setzen Sie `USE_OPEN_FILE_CACHE` auf `yes`, um die Funktion zu aktivieren.
    2. Passen Sie die `OPEN_FILE_CACHE`-Parameter an, um die maximale Anzahl von Cache-Einträgen und deren Inaktivitäts-Timeout festzulegen.
    3. Verwenden Sie `OPEN_FILE_CACHE_ERRORS`, um sowohl erfolgreiche als auch fehlgeschlagene Suchen zwischenzuspeichern und so wiederholte Dateisystemoperationen zu reduzieren.
    4. Legen Sie mit `OPEN_FILE_CACHE_MIN_USES` die Mindestanzahl von Zugriffen fest, die erforderlich ist, damit eine Datei im Cache verbleibt.
    5. Definieren Sie die Gültigkeitsdauer des Caches mit `OPEN_FILE_CACHE_VALID`, um zu steuern, wie oft zwischengespeicherte Elemente erneut validiert werden.

    !!! tip "Bewährte Praktiken"
        - Aktivieren Sie das Datei-Caching für Websites mit vielen statischen Dateien, um die Leistung zu verbessern.
        - Überprüfen und optimieren Sie die Cache-Einstellungen regelmäßig, um Leistung und Ressourcenverbrauch auszugleichen.
        - In dynamischen Umgebungen, in denen sich Dateien häufig ändern, sollten Sie die Gültigkeitsdauer des Caches verkürzen oder die Funktion deaktivieren, um die Aktualität der Inhalte zu gewährleisten.

### Beispielkonfigurationen

=== "Sicherheit des Standardservers"

    Beispielkonfiguration zum Deaktivieren des Standardservers und Erzwingen von striktem SNI:

    ```yaml
    DISABLE_DEFAULT_SERVER: "yes"
    DISABLE_DEFAULT_SERVER_STRICT_SNI: "yes"
    ```

=== "HTTP-Status bei Ablehnung"

    Beispielkonfiguration zum stillschweigenden Verwerfen unerwünschter Anfragen:

    ```yaml
    DENY_HTTP_STATUS: "444"
    ```

=== "HTTP-Methoden"

    Beispielkonfiguration zur Beschränkung der HTTP-Methoden auf die für eine RESTful-API erforderlichen:

    ```yaml
    ALLOWED_METHODS: "GET|POST|PUT|DELETE"
    ```

=== "Inhaltstypen"

    Beispielkonfiguration zur Beschränkung der Inhaltstypen nur auf JSON für eine API:

    ```yaml
    ALLOWED_CONTENT_TYPES: "application/json"
    ```

    Beispielkonfiguration für eine Standard-Webanwendung mit Datei-Uploads:

    ```yaml
    ALLOWED_CONTENT_TYPES: "application/x-www-form-urlencoded multipart/form-data application/json"
    ```

=== "Größenbeschränkungen für Anfragen"

    Beispielkonfiguration zur Begrenzung der maximalen Größe des Anforderungskörpers:

    ```yaml
    MAX_CLIENT_SIZE: "5m"
    ```

=== "Protokollunterstützung"

    Beispielkonfiguration zur Aktivierung von HTTP/2 und HTTP/3 mit einem benutzerdefinierten Alt-Svc-Port:

    ```yaml
    HTTP2: "yes"
    HTTP3: "yes"
    HTTP3_ALT_SVC_PORT: "443"
    ```

=== "Bereitstellung statischer Dateien"

    Beispielkonfiguration zur Bereitstellung statischer Dateien aus einem benutzerdefinierten Stammordner:

    ```yaml
    SERVE_FILES: "yes"
    ROOT_FOLDER: "/var/www/custom-folder"
    ```

=== "Datei-Caching"

    Beispielkonfiguration zur Aktivierung und Optimierung des Datei-Caching:

    ```yaml
    USE_OPEN_FILE_CACHE: "yes"
    OPEN_FILE_CACHE: "max=2000 inactive=30s"
    OPEN_FILE_CACHE_ERRORS: "yes"
    OPEN_FILE_CACHE_MIN_USES: "3"
    OPEN_FILE_CACHE_VALID: "60s"
    ```
