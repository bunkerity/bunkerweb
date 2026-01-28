Das Reverse-Proxy-Plugin bietet nahtlose Proxy-Funktionen für BunkerWeb, mit denen Sie Anfragen an Backend-Server und -Dienste weiterleiten können. Mit dieser Funktion kann BunkerWeb als sicheres Frontend für Ihre Anwendungen fungieren und gleichzeitig zusätzliche Vorteile wie SSL-Terminierung und Sicherheitsfilterung bieten.

**So funktioniert es:**

1.  Wenn ein Client eine Anfrage an BunkerWeb sendet, leitet das Reverse-Proxy-Plugin die Anfrage an Ihren konfigurierten Backend-Server weiter.
2.  BunkerWeb fügt Sicherheitsheader hinzu, wendet WAF-Regeln an und führt andere Sicherheitsprüfungen durch, bevor die Anfragen an Ihre Anwendung weitergeleitet werden.
3.  Der Backend-Server verarbeitet die Anfrage und gibt eine Antwort an BunkerWeb zurück.
4.  BunkerWeb wendet zusätzliche Sicherheitsmaßnahmen auf die Antwort an, bevor sie an den Client zurückgesendet wird.
5.  Das Plugin unterstützt sowohl HTTP- als auch TCP/UDP-Stream-Proxying und ermöglicht so eine breite Palette von Anwendungen, einschließlich WebSockets und anderen Nicht-HTTP-Protokollen.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Reverse-Proxy-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Setzen Sie die Einstellung `USE_REVERSE_PROXY` auf `yes`, um die Reverse-Proxy-Funktionalität zu aktivieren.
2.  **Konfigurieren Sie Ihre Backend-Server:** Geben Sie die Upstream-Server mit der Einstellung `REVERSE_PROXY_HOST` an.
3.  **Proxy-Einstellungen anpassen:** Optimieren Sie das Verhalten mit optionalen Einstellungen für Zeitüberschreitungen, Puffergrößen und andere Parameter.
4.  **Protokollspezifische Optionen konfigurieren:** Passen Sie für WebSockets oder spezielle HTTP-Anforderungen die entsprechenden Einstellungen an.
5.  **Caching einrichten (optional):** Aktivieren und konfigurieren Sie das Proxy-Caching, um die Leistung für häufig aufgerufene Inhalte zu verbessern.

### Konfigurationsanleitung

=== "Grundlegende Konfiguration"

    **Kerneinstellungen**

    Die wesentlichen Konfigurationseinstellungen aktivieren und steuern die Grundfunktionalität der Reverse-Proxy-Funktion.

    !!! success "Vorteile des Reverse-Proxy"
        - **Sicherheitsverbesserung:** Der gesamte Datenverkehr durchläuft die Sicherheitsschichten von BunkerWeb, bevor er Ihre Anwendungen erreicht
        - **SSL-Terminierung:** Verwalten Sie SSL/TLS-Zertifikate zentral, während Backend-Dienste unverschlüsselte Verbindungen verwenden können
        - **Protokollbehandlung:** Unterstützung für HTTP, HTTPS, WebSockets und andere Protokolle
        - **Fehlerabfang:** Passen Sie Fehlerseiten für ein einheitliches Benutzererlebnis an

    | Einstellung                      | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                      |
    | -------------------------------- | -------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------- |
    | `USE_REVERSE_PROXY`              | `no`     | multisite | nein     | **Reverse-Proxy aktivieren:** Auf `yes` setzen, um die Reverse-Proxy-Funktionalität zu aktivieren.                |
    | `REVERSE_PROXY_HOST`             |          | multisite | ja       | **Backend-Host:** Vollständige URL der weitergeleiteten Ressource (proxy_pass).                                   |
    | `REVERSE_PROXY_URL`              | `/`      | multisite | ja       | **Standort-URL:** Pfad, der zum Backend-Server weitergeleitet wird.                                               |
    | `REVERSE_PROXY_BUFFERING`        | `yes`    | multisite | ja       | **Antwort-Pufferung:** Aktiviert oder deaktiviert die Pufferung von Antworten von der weitergeleiteten Ressource. |
    | `REVERSE_PROXY_REQUEST_BUFFERING`| `yes`    | multisite | ja       | **Anfrage-Pufferung:** Aktiviert oder deaktiviert die Pufferung von Anfragen an die weitergeleitete Ressource.    |
    | `REVERSE_PROXY_KEEPALIVE`        | `no`     | multisite | ja       | **Keep-Alive:** Aktiviert oder deaktiviert Keep-Alive-Verbindungen mit der weitergeleiteten Ressource.            |
    | `REVERSE_PROXY_CUSTOM_HOST`      |          | multisite | nein     | **Benutzerdefinierter Host:** Überschreibt den an den Upstream-Server gesendeten Host-Header.                     |
    | `REVERSE_PROXY_INTERCEPT_ERRORS` | `yes`    | multisite | nein     | **Fehler abfangen:** Ob Fehlerantworten vom Backend abgefangen und neu geschrieben werden sollen.                 |

    !!! tip "Bewährte Praktiken"
        - Geben Sie in `REVERSE_PROXY_HOST` immer die vollständige URL an, einschließlich des Protokolls (http:// oder https://)
        - Verwenden Sie `REVERSE_PROXY_INTERCEPT_ERRORS`, um konsistente Fehlerseiten für alle Ihre Dienste bereitzustellen
        - Verwenden Sie bei der Konfiguration mehrerer Backends das nummerierte Suffixformat (z. B. `REVERSE_PROXY_HOST_2`, `REVERSE_PROXY_URL_2`)

    !!! warning "Verhalten der Anfrage-Pufferung"
        Das Deaktivieren von `REVERSE_PROXY_REQUEST_BUFFERING` hat nur Wirkung, wenn ModSecurity deaktiviert ist, da die Anfrage-Pufferung ansonsten erzwungen wird.

=== "Verbindungseinstellungen"

    **Konfiguration von Verbindungen und Zeitüberschreitungen**

    Diese Einstellungen steuern das Verbindungsverhalten, die Pufferung und die Zeitüberschreitungswerte für die weitergeleiteten Verbindungen.

    !!! success "Vorteile"
        - **Optimierte Leistung:** Passen Sie Puffergrößen und Verbindungseinstellungen an die Bedürfnisse Ihrer Anwendung an
        - **Ressourcenmanagement:** Kontrollieren Sie die Speichernutzung durch geeignete Pufferkonfigurationen
        - **Zuverlässigkeit:** Konfigurieren Sie geeignete Zeitüberschreitungen, um langsame Verbindungen oder Backend-Probleme zu bewältigen

    | Einstellung                     | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                             |
    | ------------------------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
    | `REVERSE_PROXY_CONNECT_TIMEOUT` | `60s`    | multisite | ja       | **Verbindungs-Timeout:** Maximale Zeit zum Herstellen einer Verbindung zum Backend-Server.                               |
    | `REVERSE_PROXY_READ_TIMEOUT`    | `60s`    | multisite | ja       | **Lese-Timeout:** Maximale Zeit zwischen der Übertragung von zwei aufeinanderfolgenden Paketen vom Backend-Server.       |
    | `REVERSE_PROXY_SEND_TIMEOUT`    | `60s`    | multisite | ja       | **Sende-Timeout:** Maximale Zeit zwischen der Übertragung von zwei aufeinanderfolgenden Paketen zum Backend-Server.      |
    | `PROXY_BUFFERS`                 |          | multisite | nein     | **Puffer:** Anzahl und Größe der Puffer zum Lesen der Antwort vom Backend-Server.                                        |
    | `PROXY_BUFFER_SIZE`             |          | multisite | nein     | **Puffergröße:** Größe des Puffers zum Lesen des ersten Teils der Antwort vom Backend-Server.                            |
    | `PROXY_BUSY_BUFFERS_SIZE`       |          | multisite | nein     | **Größe der belegten Puffer:** Größe der Puffer, die mit dem Senden einer Antwort an den Client beschäftigt sein können. |

    !!! warning "Überlegungen zu Zeitüberschreitungen"
        - Zu kurze Zeitüberschreitungen können legitime, aber langsame Verbindungen unterbrechen
        - Zu lange Zeitüberschreitungen können Verbindungen unnötig offen lassen und möglicherweise Ressourcen erschöpfen
        - Bei WebSocket-Anwendungen sollten Sie die Lese- und Sende-Timeouts deutlich erhöhen (300s oder mehr empfohlen)

=== "SSL/TLS-Konfiguration"

    **SSL/TLS-Einstellungen für Backend-Verbindungen**

    Diese Einstellungen steuern, wie BunkerWeb sichere Verbindungen zu Backend-Servern herstellt.

    !!! success "Vorteile"
        - **Ende-zu-Ende-Verschlüsselung:** Behalten Sie verschlüsselte Verbindungen vom Client zum Backend bei
        - **Zertifikatsvalidierung:** Kontrollieren Sie, wie Backend-Serverzertifikate validiert werden
        - **SNI-Unterstützung:** Geben Sie die Server Name Indication für Backends an, die mehrere Websites hosten

    | Einstellung                  | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                  |
    | ---------------------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_SSL_SNI`      | `no`     | multisite | nein     | **SSL SNI:** Aktiviert oder deaktiviert das Senden von SNI (Server Name Indication) an den Upstream.          |
    | `REVERSE_PROXY_SSL_SNI_NAME` |          | multisite | nein     | **SSL SNI-Name:** Legt den SNI-Hostnamen fest, der an den Upstream gesendet wird, wenn SSL SNI aktiviert ist. |

    !!! info "SNI erklärt"
        Server Name Indication (SNI) ist eine TLS-Erweiterung, die es einem Client ermöglicht, den Hostnamen anzugeben, mit dem er während des Handshake-Prozesses eine Verbindung herstellen möchte. Dies ermöglicht es Servern, mehrere Zertifikate auf derselben IP-Adresse und demselben Port zu präsentieren, sodass mehrere sichere (HTTPS-)Websites von einer einzigen IP-Adresse aus bedient werden können, ohne dass alle diese Websites dasselbe Zertifikat verwenden müssen.

=== "Protokollunterstützung"

    **Protokollspezifische Konfiguration**

    Konfigurieren Sie die Behandlung spezieller Protokolle, insbesondere für WebSockets und andere Nicht-HTTP-Protokolle.

    !!! success "Vorteile"
        - **Protokollflexibilität:** Die Unterstützung für WebSockets ermöglicht Echtzeitanwendungen
        - **Moderne Webanwendungen:** Aktivieren Sie interaktive Funktionen, die eine bidirektionale Kommunikation erfordern

    | Einstellung        | Standard | Kontext   | Mehrfach | Beschreibung                                                                      |
    | ------------------ | -------- | --------- | -------- | --------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_WS` | `no`     | multisite | ja       | **WebSocket-Unterstützung:** Aktiviert das WebSocket-Protokoll für die Ressource. |

    !!! tip "WebSocket-Konfiguration"
        - Bei der Aktivierung von WebSockets mit `REVERSE_PROXY_WS: "yes"` sollten Sie die Zeitüberschreitungswerte erhöhen
        - WebSocket-Verbindungen bleiben länger offen als typische HTTP-Verbindungen
        - Für WebSocket-Anwendungen wird folgende Konfiguration empfohlen:
          ```yaml
          REVERSE_PROXY_WS: "yes"
          REVERSE_PROXY_READ_TIMEOUT: "300s"
          REVERSE_PROXY_SEND_TIMEOUT: "300s"
          ```

=== "Header-Verwaltung"

    **HTTP-Header-Konfiguration**

    Kontrollieren Sie, welche Header an Backend-Server und Clients gesendet werden, und ermöglichen Sie das Hinzufügen, Ändern oder Beibehalten von HTTP-Headern.

    !!! success "Vorteile"
        - **Informationskontrolle:** Verwalten Sie genau, welche Informationen zwischen Clients und Backends ausgetauscht werden
        - **Sicherheitsverbesserung:** Fügen Sie sicherheitsrelevante Header hinzu oder entfernen Sie Header, die sensible Informationen preisgeben könnten
        - **Integrationsunterstützung:** Stellen Sie die für die Authentifizierung und den ordnungsgemäßen Backend-Betrieb erforderlichen Header bereit

    | Einstellung                            | Standard  | Kontext   | Mehrfach | Beschreibung                                                                                                        |
    | -------------------------------------- | --------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_HEADERS`                |           | multisite | ja       | **Benutzerdefinierte Header:** HTTP-Header, die durch Semikolons getrennt an das Backend gesendet werden.           |
    | `REVERSE_PROXY_HIDE_HEADERS`           | `Upgrade` | multisite | ja       | **Header ausblenden:** HTTP-Header, die vor Clients verborgen werden sollen, wenn sie vom Backend empfangen werden. |
    | `REVERSE_PROXY_HEADERS_CLIENT`         |           | multisite | ja       | **Client-Header:** HTTP-Header, die durch Semikolons getrennt an den Client gesendet werden.                        |
    | `REVERSE_PROXY_UNDERSCORES_IN_HEADERS` | `no`      | multisite | nein     | **Unterstriche in Headern:** Aktiviert oder deaktiviert die `underscores_in_headers`-Direktive.                     |

    !!! warning "Sicherheitsüberlegungen"
        Seien Sie bei der Verwendung der Reverse-Proxy-Funktion vorsichtig, welche Header Sie an Ihre Backend-Anwendungen weiterleiten. Bestimmte Header können sensible Informationen über Ihre Infrastruktur preisgeben oder Sicherheitskontrollen umgehen.

    !!! example "Beispiele für Header-Formate"
        Benutzerdefinierte Header an Backend-Server:
        ```
        REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"
        ```

        Benutzerdefinierte Header an Clients:
        ```
        REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
        ```

=== "Authentifizierung"

    **Konfiguration der externen Authentifizierung**

    Integrieren Sie externe Authentifizierungssysteme, um die Autorisierungslogik für Ihre Anwendungen zu zentralisieren.

    !!! success "Vorteile"
        - **Zentralisierte Authentifizierung:** Implementieren Sie einen einzigen Authentifizierungspunkt für mehrere Anwendungen
        - **Konsistente Sicherheit:** Wenden Sie einheitliche Authentifizierungsrichtlinien für verschiedene Dienste an
        - **Verbesserte Kontrolle:** Leiten Sie Authentifizierungsdetails über Header oder Variablen an Backend-Anwendungen weiter

    | Einstellung                             | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                    |
    | --------------------------------------- | -------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_AUTH_REQUEST`            |          | multisite | ja       | **Authentifizierungsanforderung:** Aktiviert die Authentifizierung über einen externen Anbieter.                |
    | `REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` |          | multisite | ja       | **Anmelde-URL:** Leitet Clients bei fehlgeschlagener Authentifizierung zur Anmelde-URL weiter.                  |
    | `REVERSE_PROXY_AUTH_REQUEST_SET`        |          | multisite | ja       | **Authentifizierungsanforderungssatz:** Variablen, die vom Authentifizierungsanbieter festgelegt werden sollen. |

    !!! tip "Authentifizierungsintegration"
        - Die Authentifizierungsanforderungsfunktion ermöglicht die Implementierung zentralisierter Authentifizierungsmikrodienste
        - Ihr Authentifizierungsdienst sollte bei erfolgreicher Authentifizierung einen 200-Statuscode oder bei einem Fehler 401/403 zurückgeben
        - Verwenden Sie die auth_request_set-Direktive, um Informationen vom Authentifizierungsdienst zu extrahieren und weiterzuleiten

=== "Erweiterte Konfiguration"

    **Zusätzliche Konfigurationsoptionen**

    Diese Einstellungen bieten eine weitere Anpassung des Reverse-Proxy-Verhaltens für spezielle Szenarien.

    !!! success "Vorteile"
        - **Anpassung:** Fügen Sie zusätzliche Konfigurationsausschnitte für komplexe Anforderungen hinzu
        - **Leistungsoptimierung:** Optimieren Sie die Anforderungsbehandlung für bestimmte Anwendungsfälle
        - **Flexibilität:** Passen Sie sich mit speziellen Konfigurationen an einzigartige Anwendungsanforderungen an

    | Einstellung                       | Standard | Kontext   | Mehrfach | Beschreibung                                                                                              |
    | --------------------------------- | -------- | --------- | -------- | --------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_INCLUDES`          |          | multisite | ja       | **Zusätzliche Konfigurationen:** Fügen Sie zusätzliche Konfigurationen in den Standortblock ein.          |
    | `REVERSE_PROXY_PASS_REQUEST_BODY` | `yes`    | multisite | ja       | **Anforderungskörper weiterleiten:** Aktiviert oder deaktiviert das Weiterleiten des Anforderungskörpers. |

    !!! warning "Sicherheitsüberlegungen"
        Seien Sie vorsichtig, wenn Sie benutzerdefinierte Konfigurationsausschnitte einfügen, da diese die Sicherheitseinstellungen von BunkerWeb überschreiben oder bei unsachgemäßer Konfiguration Schwachstellen einführen können.

=== "Caching-Konfiguration"

    **Einstellungen für das Caching von Antworten**

    Verbessern Sie die Leistung durch das Caching von Antworten von Backend-Servern, wodurch die Last reduziert und die Antwortzeiten verbessert werden.

    !!! success "Vorteile"
        - **Leistung:** Reduzieren Sie die Last auf Backend-Servern, indem Sie zwischengespeicherte Inhalte bereitstellen
        - **Reduzierte Latenz:** Schnellere Antwortzeiten für häufig angeforderte Inhalte
        - **Bandbreiteneinsparungen:** Minimieren Sie den internen Netzwerkverkehr durch das Caching von Antworten
        - **Anpassung:** Konfigurieren Sie genau, was, wann und wie Inhalte zwischengespeichert werden

    | Einstellung                  | Standard                           | Kontext   | Mehrfach | Beschreibung                                                                                                                                         |
    | ---------------------------- | ---------------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_PROXY_CACHE`            | `no`                               | multisite | nein     | **Caching aktivieren:** Auf `yes` setzen, um das Caching von Backend-Antworten zu aktivieren.                                                        |
    | `PROXY_CACHE_PATH_LEVELS`    | `1:2`                              | global    | nein     | **Cache-Pfad-Ebenen:** Wie die Hierarchie des Cache-Verzeichnisses strukturiert werden soll.                                                         |
    | `PROXY_CACHE_PATH_ZONE_SIZE` | `10m`                              | global    | nein     | **Cache-Zonengröße:** Größe des gemeinsam genutzten Speicherbereichs, der für Cache-Metadaten verwendet wird.                                        |
    | `PROXY_CACHE_PATH_PARAMS`    | `max_size=100m`                    | global    | nein     | **Cache-Pfad-Parameter:** Zusätzliche Parameter für den Cache-Pfad.                                                                                  |
    | `PROXY_CACHE_METHODS`        | `GET HEAD`                         | multisite | nein     | **Cache-Methoden:** HTTP-Methoden, die zwischengespeichert werden können.                                                                            |
    | `PROXY_CACHE_MIN_USES`       | `2`                                | multisite | nein     | **Mindestverwendungen für Cache:** Mindestanzahl von Anfragen, bevor eine Antwort zwischengespeichert wird.                                          |
    | `PROXY_CACHE_KEY`            | `$scheme$host$request_uri`         | multisite | nein     | **Cache-Schlüssel:** Der Schlüssel, der zur eindeutigen Identifizierung einer zwischengespeicherten Antwort verwendet wird.                          |
    | `PROXY_CACHE_VALID`          | `200=24h 301=1h 302=24h`           | multisite | nein     | **Cache-Gültigkeit:** Wie lange bestimmte Antwortcodes zwischengespeichert werden sollen.                                                            |
    | `PROXY_NO_CACHE`             | `$http_pragma $http_authorization` | multisite | nein     | **Kein Cache:** Bedingungen, unter denen Antworten nicht zwischengespeichert werden, auch wenn sie normalerweise zwischengespeichert werden könnten. |
    | `PROXY_CACHE_BYPASS`         | `0`                                | multisite | nein     | **Cache-Umgehung:** Bedingungen, unter denen der Cache umgangen werden soll.                                                                         |

    !!! tip "Bewährte Praktiken für das Caching"
        - Speichern Sie nur Inhalte zwischen, die sich nicht häufig ändern oder nicht personalisiert sind
        - Verwenden Sie je nach Inhaltstyp geeignete Cache-Dauern (statische Assets können länger zwischengespeichert werden)
        - Konfigurieren Sie `PROXY_NO_CACHE`, um das Zwischenspeichern sensibler oder personalisierter Inhalte zu vermeiden
        - Überwachen Sie die Cache-Trefferquoten und passen Sie die Einstellungen entsprechend an

!!! danger "Docker Compose-Benutzer - NGINX-Variablen"
    Wenn Sie Docker Compose mit NGINX-Variablen in Ihren Konfigurationen verwenden, müssen Sie das Dollarzeichen (`$`) durch doppelte Dollarzeichen (`$$`) maskieren. Dies gilt für alle Einstellungen, die NGINX-Variablen wie `$remote_addr`, `$proxy_add_x_forwarded_for` usw. enthalten.

    Ohne diese Maskierung versucht Docker Compose, diese Variablen durch Umgebungsvariablen zu ersetzen, die normalerweise nicht existieren, was zu leeren Werten in Ihrer NGINX-Konfiguration führt.

### Beispielkonfigurationen

=== "Grundlegender HTTP-Proxy"

    Eine einfache Konfiguration zum Weiterleiten von HTTP-Anfragen an einen Backend-Anwendungsserver:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "60s"
    REVERSE_PROXY_READ_TIMEOUT: "60s"
    ```

=== "WebSocket-Anwendung"

    Konfiguration, die für eine WebSocket-Anwendung mit längeren Zeitüberschreitungen optimiert ist:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://websocket-app:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_WS: "yes"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "300s"
    REVERSE_PROXY_READ_TIMEOUT: "300s"
    ```

=== "Mehrere Standorte"

    Konfiguration zum Weiterleiten verschiedener Pfade an verschiedene Backend-Dienste:

    ```yaml
    USE_REVERSE_PROXY: "yes"

    # API-Backend
    REVERSE_PROXY_HOST: "http://api-server:8080"
    REVERSE_PROXY_URL: "/api/"

    # Admin-Backend
    REVERSE_PROXY_HOST_2: "http://admin-server:8080"
    REVERSE_PROXY_URL_2: "/admin/"

    # Frontend-App
    REVERSE_PROXY_HOST_3: "http://frontend:3000"
    REVERSE_PROXY_URL_3: "/"
    ```

=== "Caching-Konfiguration"

    Konfiguration mit aktiviertem Proxy-Caching für eine bessere Leistung:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    USE_PROXY_CACHE: "yes"
    PROXY_CACHE_VALID: "200=24h 301=1h 302=24h"
    PROXY_CACHE_METHODS: "GET HEAD"
    PROXY_NO_CACHE: "$http_authorization"
    ```

=== "Erweiterte Header-Verwaltung"

    Konfiguration mit benutzerdefinierter Header-Manipulation:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Benutzerdefinierte Header an das Backend
    REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"

    # Benutzerdefinierte Header an den Client
    REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
    ```

=== "Authentifizierungsintegration"

    Konfiguration mit externer Authentifizierung:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Authentifizierungskonfiguration
    REVERSE_PROXY_AUTH_REQUEST: "/auth"
    REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: "https://login.example.com"
    REVERSE_PROXY_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_role $upstream_http_x_role"

    # Backend des Authentifizierungsdienstes
    REVERSE_PROXY_HOST_2: "http://auth-service:8080"
    REVERSE_PROXY_URL_2: "/auth"
    ```
