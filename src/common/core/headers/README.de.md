HTTP-Header spielen eine entscheidende Rolle bei der Sicherheit. Das Headers-Plugin bietet eine robuste Verwaltung von Standard- und benutzerdefinierten HTTP-Headern und verbessert so Sicherheit und Funktionalität. Es wendet dynamisch Sicherheitsmaßnahmen an, wie [HSTS](https://developer.mozilla.org/de/docs/Web/HTTP/Headers/Strict-Transport-Security), [CSP](https://developer.mozilla.org/de/docs/Web/HTTP/CSP) (einschließlich eines reinen Berichtsmodus) und die Injektion benutzerdefinierter Header, während es gleichzeitig Informationslecks verhindert.

**Wie es funktioniert**

1.  Wenn ein Client Inhalte von Ihrer Website anfordert, verarbeitet BunkerWeb die Antwort-Header.
2.  Sicherheits-Header werden gemäß Ihrer Konfiguration angewendet.
3.  Benutzerdefinierte Header können hinzugefügt werden, um Clients zusätzliche Informationen oder Funktionen bereitzustellen.
4.  Unerwünschte Header, die Serverinformationen preisgeben könnten, werden automatisch entfernt.
5.  Cookies werden so geändert, dass sie je nach Ihren Einstellungen die entsprechenden Sicherheitsflags enthalten.
6.  Header von Upstream-Servern können bei Bedarf selektiv beibehalten werden.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Headers-Funktion zu konfigurieren und zu verwenden:

1.  **Sicherheits-Header konfigurieren:** Legen Sie Werte für gängige Header fest.
2.  **Benutzerdefinierte Header hinzufügen:** Definieren Sie beliebige benutzerdefinierte Header mit der Einstellung `CUSTOM_HEADER`.
3.  **Unerwünschte Header entfernen:** Verwenden Sie `REMOVE_HEADERS`, um sicherzustellen, dass Header, die Serverdetails preisgeben könnten, entfernt werden.
4.  **Cookie-Sicherheit einstellen:** Aktivieren Sie eine robuste Cookie-Sicherheit, indem Sie `COOKIE_FLAGS` konfigurieren und `COOKIE_AUTO_SECURE_FLAG` auf `yes` setzen, damit das Secure-Flag bei HTTPS-Verbindungen automatisch hinzugefügt wird.
5.  **Upstream-Header beibehalten:** Geben Sie mit `KEEP_UPSTREAM_HEADERS` an, welche Upstream-Header beibehalten werden sollen.
6.  **Bedingte Header-Anwendung nutzen:** Wenn Sie Richtlinien ohne Unterbrechung testen möchten, aktivieren Sie den [CSP Report-Only-Modus](https://developer.mozilla.org/de/docs/Web/HTTP/Headers/Content-Security-Policy-Report-Only) über `CONTENT_SECURITY_POLICY_REPORT_ONLY`.

### Konfigurationsleitfaden

=== "Sicherheits-Header"

    **Überblick**

    Sicherheits-Header erzwingen eine sichere Kommunikation, schränken das Laden von Ressourcen ein und verhindern Angriffe wie Clickjacking und Injection. Richtig konfigurierte Header bilden eine robuste Verteidigungsschicht für Ihre Website.

    !!! success "Vorteile von Sicherheits-Headern"
        - **HSTS:** Stellt sicher, dass alle Verbindungen verschlüsselt sind, und schützt so vor Protokoll-Downgrade-Angriffen.
        - **CSP:** Verhindert die Ausführung bösartiger Skripte und verringert so das Risiko von XSS-Angriffen.
        - **X-Frame-Options:** Blockiert Clickjacking-Versuche durch die Kontrolle der Iframe-Einbettung.
        - **Referrer Policy:** Begrenzt das Durchsickern sensibler Informationen über Referrer-Header.

    | Einstellung                           | Standard                                                                                            | Kontext   | Mehrfach | Beschreibung                                                                                                                                                    |
    | ------------------------------------- | --------------------------------------------------------------------------------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `STRICT_TRANSPORT_SECURITY`           | `max-age=63072000; includeSubDomains; preload`                                                      | multisite | nein     | **HSTS:** Erzwingt sichere HTTPS-Verbindungen und verringert das Risiko von Man-in-the-Middle-Angriffen.                                                        |
    | `CONTENT_SECURITY_POLICY`             | `object-src 'none'; form-action 'self'; frame-ancestors 'self';`                                    | multisite | nein     | **CSP:** Beschränkt das Laden von Ressourcen auf vertrauenswürdige Quellen und mindert Cross-Site-Scripting- und Dateninjektionsangriffe.                       |
    | `CONTENT_SECURITY_POLICY_REPORT_ONLY` | `no`                                                                                                | multisite | nein     | **CSP-Berichtsmodus:** Meldet Verstöße, ohne Inhalte zu blockieren, und hilft beim Testen von Sicherheitsrichtlinien, während Protokolle erfasst werden.        |
    | `X_FRAME_OPTIONS`                     | `SAMEORIGIN`                                                                                        | multisite | nein     | **X-Frame-Options:** Verhindert Clickjacking, indem es steuert, ob Ihre Website in einem Frame dargestellt werden kann.                                         |
    | `X_CONTENT_TYPE_OPTIONS`              | `nosniff`                                                                                           | multisite | nein     | **X-Content-Type-Options:** Verhindert, dass Browser MIME-Sniffing betreiben, und schützt so vor Drive-by-Download-Angriffen.                                   |
    | `X_DNS_PREFETCH_CONTROL`              | `off`                                                                                               | multisite | nein     | **X-DNS-Prefetch-Control:** Reguliert das DNS-Prefetching, um unbeabsichtigte Netzwerkanfragen zu reduzieren und die Privatsphäre zu verbessern.                |
    | `REFERRER_POLICY`                     | `strict-origin-when-cross-origin`                                                                   | multisite | nein     | **Referrer Policy:** Steuert die Menge der gesendeten Referrer-Informationen und schützt die Privatsphäre der Benutzer.                                         |
    | `PERMISSIONS_POLICY`                  | `accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), ...` | multisite | nein     | **Permissions Policy:** Beschränkt den Zugriff auf Browserfunktionen und reduziert potenzielle Angriffsvektoren.                                                |
    | `KEEP_UPSTREAM_HEADERS`               | `Content-Security-Policy Permissions-Policy X-Frame-Options`                                        | multisite | nein     | **Header beibehalten:** Behält ausgewählte Upstream-Header bei, was die Integration von Altsystemen erleichtert und gleichzeitig die Sicherheit aufrechterhält. |

    !!! tip "Bewährte Praktiken"
        - Überprüfen und aktualisieren Sie Ihre Sicherheits-Header regelmäßig, um sie an die sich entwickelnden Sicherheitsstandards anzupassen.
        - Verwenden Sie Tools wie das [Mozilla Observatory](https://observatory.mozilla.org/), um Ihre Header-Konfiguration zu validieren.
        - Testen Sie CSP im `Report-Only`-Modus, bevor Sie es erzwingen, um zu vermeiden, dass die Funktionalität beeinträchtigt wird.

=== "Cookie-Einstellungen"

    **Überblick**

    Richtige Cookie-Einstellungen gewährleisten sichere Benutzersitzungen, indem sie Hijacking, Fixierung und Cross-Site-Scripting verhindern. Sichere Cookies erhalten die Sitzungsintegrität über HTTPS und verbessern den allgemeinen Schutz der Benutzerdaten.

    !!! success "Vorteile sicherer Cookies"
        - **HttpOnly-Flag:** Verhindert, dass clientseitige Skripte auf Cookies zugreifen, und mindert so XSS-Risiken.
        - **SameSite-Flag:** Reduziert CSRF-Angriffe, indem die Verwendung von Cookies über verschiedene Ursprünge hinweg eingeschränkt wird.
        - **Secure-Flag:** Stellt sicher, dass Cookies nur über verschlüsselte HTTPS-Verbindungen übertragen werden.

    | Einstellung               | Standard                  | Kontext   | Mehrfach | Beschreibung                                                                                                                                                              |
    | ------------------------- | ------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `COOKIE_FLAGS`            | `* HttpOnly SameSite=Lax` | multisite | ja       | **Cookie-Flags:** Fügt automatisch Sicherheitsflags wie HttpOnly und SameSite hinzu und schützt Cookies so vor dem Zugriff durch clientseitige Skripte und CSRF-Angriffe. |
    | `COOKIE_AUTO_SECURE_FLAG` | `yes`                     | multisite | nein     | **Automatisches Secure-Flag:** Stellt sicher, dass Cookies nur über sichere HTTPS-Verbindungen gesendet werden, indem das Secure-Flag automatisch angehängt wird.         |

    !!! tip "Bewährte Praktiken"
        - Verwenden Sie `SameSite=Strict` für sensible Cookies, um den Zugriff über verschiedene Ursprünge hinweg zu verhindern.
        - Überprüfen Sie Ihre Cookie-Einstellungen regelmäßig, um die Einhaltung der Sicherheits- und Datenschutzbestimmungen sicherzustellen.
        - Vermeiden Sie es, Cookies ohne das Secure-Flag in Produktionsumgebungen zu setzen.

=== "Benutzerdefinierte Header"

    **Überblick**

    Benutzerdefinierte Header ermöglichen es Ihnen, spezifische HTTP-Header hinzuzufügen, um Anwendungs- oder Leistungsanforderungen zu erfüllen. Sie bieten Flexibilität, müssen aber sorgfältig konfiguriert werden, um die Preisgabe sensibler Serverdetails zu vermeiden.

    !!! success "Vorteile von benutzerdefinierten Headern"
        - Verbessern Sie die Sicherheit, indem Sie unnötige Header entfernen, die Serverdetails preisgeben könnten.
        - Fügen Sie anwendungsspezifische Header hinzu, um die Funktionalität oder das Debugging zu verbessern.

    | Einstellung      | Standard                                                                             | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                                 |
    | ---------------- | ------------------------------------------------------------------------------------ | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `CUSTOM_HEADER`  |                                                                                      | multisite | ja       | **Benutzerdefinierter Header:** Bietet eine Möglichkeit, benutzerdefinierte Header im Format `HeaderName: HeaderValue` für spezielle Sicherheits- oder Leistungsverbesserungen hinzuzufügen. |
    | `REMOVE_HEADERS` | `Server Expect-CT X-Powered-By X-AspNet-Version X-AspNetMvc-Version Public-Key-Pins` | multisite | nein     | **Header entfernen:** Gibt an, welche Header entfernt werden sollen, um die Wahrscheinlichkeit der Preisgabe interner Serverdetails und bekannter Schwachstellen zu verringern.              |

    !!! warning "Sicherheitsaspekte"
        - Vermeiden Sie die Preisgabe sensibler Informationen durch benutzerdefinierte Header.
        - Überprüfen und aktualisieren Sie benutzerdefinierte Header regelmäßig, um sie an die Anforderungen Ihrer Anwendung anzupassen.

    !!! tip "Bewährte Praktiken"
        - Verwenden Sie `REMOVE_HEADERS`, um Header wie `Server` und `X-Powered-By` zu entfernen und so das Risiko des Fingerprintings zu verringern.
        - Testen Sie benutzerdefinierte Header in einer Staging-Umgebung, bevor Sie sie in der Produktion einsetzen.

### Beispielkonfigurationen

=== "Grundlegende Sicherheits-Header"

    Eine Standardkonfiguration mit wesentlichen Sicherheits-Headern:

    ```yaml
    STRICT_TRANSPORT_SECURITY: "max-age=63072000; includeSubDomains; preload"
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'self'"
    X_FRAME_OPTIONS: "SAMEORIGIN"
    X_CONTENT_TYPE_OPTIONS: "nosniff"
    REFERRER_POLICY: "strict-origin-when-cross-origin"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version"
    ```

=== "Verbesserte Cookie-Sicherheit"

    Konfiguration mit robusten Cookie-Sicherheitseinstellungen:

    ```yaml
    COOKIE_FLAGS: "* HttpOnly SameSite=Strict"
    COOKIE_FLAGS_2: "session_cookie Secure HttpOnly SameSite=Strict"
    COOKIE_FLAGS_3: "auth_cookie Secure HttpOnly SameSite=Strict Max-Age=3600"
    COOKIE_AUTO_SECURE_FLAG: "yes"
    ```

=== "Benutzerdefinierte Header für API"

    Konfiguration für einen API-Dienst mit benutzerdefinierten Headern:

    ```yaml
    CUSTOM_HEADER: "API-Version: 1.2.3"
    CUSTOM_HEADER_2: "Access-Control-Max-Age: 86400"
    CONTENT_SECURITY_POLICY: "default-src 'none'; frame-ancestors 'none'"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version X-Runtime"
    ```

=== "Content Security Policy - Berichtsmodus"

    Konfiguration zum Testen von CSP, ohne die Funktionalität zu beeinträchtigen:

    ```yaml
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self' https://trusted-cdn.example.com; img-src 'self' data: https://*.example.com; style-src 'self' 'unsafe-inline' https://trusted-cdn.example.com; connect-src 'self' https://api.example.com; object-src 'none'; frame-ancestors 'self'; form-action 'self'; base-uri 'self'; report-uri https://example.com/csp-reports"
    CONTENT_SECURITY_POLICY_REPORT_ONLY: "yes"
    ```
