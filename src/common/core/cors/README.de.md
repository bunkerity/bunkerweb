Das CORS-Plugin ermöglicht Cross-Origin Resource Sharing (Ressourcenfreigabe zwischen verschiedenen Ursprüngen) für Ihre Website und erlaubt so den kontrollierten Zugriff auf Ihre Ressourcen von verschiedenen Domains aus. Diese Funktion hilft Ihnen, Ihre Inhalte sicher mit vertrauenswürdigen Drittanbieter-Websites zu teilen, während die Sicherheit durch die explizite Definition der erlaubten Ursprünge, Methoden und Header gewährleistet wird.

**So funktioniert es:**

1.  Wenn ein Browser eine Cross-Origin-Anfrage an Ihre Website stellt, sendet er zuerst eine Preflight-Anfrage mit der `OPTIONS`-Methode.
2.  BunkerWeb prüft, ob der anfragende Ursprung basierend auf Ihrer Konfiguration zulässig ist.
3.  Wenn dies der Fall ist, antwortet BunkerWeb mit den entsprechenden CORS-Headern, die definieren, was die anfragende Website tun darf.
4.  Bei nicht zulässigen Ursprüngen kann die Anfrage entweder komplett verweigert oder ohne CORS-Header ausgeliefert werden.
5.  Zusätzliche Cross-Origin-Richtlinien wie [COEP](https://developer.mozilla.org/de/docs/Web/HTTP/Headers/Cross-Origin-Embedder-Policy), [COOP](https://developer.mozilla.org/de/docs/Web/HTTP/Headers/Cross-Origin-Opener-Policy) und [CORP](https://developer.mozilla.org/de/docs/Web/HTTP/Headers/Cross-Origin-Resource-Policy) können konfiguriert werden, um die Sicherheit weiter zu erhöhen.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die CORS-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die CORS-Funktion ist standardmäßig deaktiviert. Setzen Sie die Einstellung `USE_CORS` auf `yes`, um sie zu aktivieren.
2.  **Erlaubte Ursprünge konfigurieren:** Geben Sie mit der Einstellung `CORS_ALLOW_ORIGIN` an, welche Domains auf Ihre Ressourcen zugreifen dürfen.
3.  **Zulässige Methoden festlegen:** Definieren Sie mit `CORS_ALLOW_METHODS`, welche HTTP-Methoden für Cross-Origin-Anfragen erlaubt sind.
4.  **Erlaubte Header konfigurieren:** Geben Sie mit `CORS_ALLOW_HEADERS` an, welche Header in Anfragen verwendet werden dürfen.
5.  **Anmeldeinformationen steuern:** Entscheiden Sie mit `CORS_ALLOW_CREDENTIALS`, ob Cross-Origin-Anfragen Anmeldeinformationen enthalten dürfen.

### Konfigurationseinstellungen

| Einstellung                    | Standard                                                                             | Kontext   | Mehrfach | Beschreibung                                                                                                                              |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CORS`                     | `no`                                                                                 | multisite | nein     | **CORS aktivieren:** Auf `yes` setzen, um Cross-Origin Resource Sharing zu aktivieren.                                                    |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | nein     | **Erlaubte Ursprünge:** PCRE-regulärer Ausdruck für erlaubte Ursprünge; `*` für jeden Ursprung, `self` nur für denselben Ursprung.        |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | nein     | **Erlaubte Methoden:** HTTP-Methoden, die bei Cross-Origin-Anfragen verwendet werden können.                                              |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | nein     | **Erlaubte Header:** HTTP-Header, die bei Cross-Origin-Anfragen verwendet werden können.                                                  |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | nein     | **Anmeldeinformationen erlauben:** Auf `yes` setzen, um Anmeldeinformationen (Cookies, HTTP-Auth) in CORS-Anfragen zu erlauben.           |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | nein     | **Verfügbar gemachte Header:** HTTP-Header, auf die Browser von Cross-Origin-Antworten zugreifen dürfen.                                  |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | nein     | **Cross-Origin-Opener-Policy:** Steuert die Kommunikation zwischen Browser-Kontexten.                                                     |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | nein     | **Cross-Origin-Embedder-Policy:** Steuert, ob ein Dokument Ressourcen von anderen Ursprüngen laden kann.                                  |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | nein     | **Cross-Origin-Resource-Policy:** Steuert, welche Websites Ihre Ressourcen einbetten dürfen.                                              |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | nein     | **Cache-Dauer für Preflight:** Wie lange (in Sekunden) Browser die Preflight-Antwort zwischenspeichern sollen.                            |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | nein     | **Nicht autorisierte Ursprünge ablehnen:** Wenn `yes`, werden Anfragen von nicht autorisierten Ursprüngen mit einem Fehlercode abgelehnt. |

!!! tip "Optimierung von Preflight-Anfragen"
    Die Einstellung `CORS_MAX_AGE` bestimmt, wie lange Browser die Ergebnisse einer Preflight-Anfrage zwischenspeichern. Ein höherer Wert (wie der Standardwert von 86400 Sekunden/24 Stunden) reduziert die Anzahl der Preflight-Anfragen und verbessert die Leistung für häufig aufgerufene Ressourcen.

!!! warning "Sicherheitshinweise"
    Seien Sie vorsichtig, wenn Sie `CORS_ALLOW_ORIGIN` auf `*` (alle Ursprünge) oder `CORS_ALLOW_CREDENTIALS` auf `yes` setzen, da diese Konfigurationen bei unsachgemäßer Verwaltung Sicherheitsrisiken mit sich bringen können. Es ist im Allgemeinen sicherer, vertrauenswürdige Ursprünge explizit aufzulisten und die erlaubten Methoden und Header zu beschränken.

### Beispielkonfigurationen

Hier sind Beispiele für mögliche Werte der Einstellung `CORS_ALLOW_ORIGIN` und deren Verhalten:

- **`*`**: Erlaubt Anfragen von allen Ursprüngen.
- **`self`**: Erlaubt automatisch Anfragen vom selben Ursprung wie der konfigurierte `server_name`.
- **`^https://www\.example\.com$`**: Erlaubt Anfragen nur von `https://www.example.com`.
- **`^https://.+\.example\.com$`**: Erlaubt Anfragen von jeder Subdomain, die auf `.example.com` endet.
- **`^https://(www\.example1\.com|www\.example2\.com)$`**: Erlaubt Anfragen entweder von `https://www.example1.com` oder `https://www.example2.com`.
- **`^https?://www\.example\.com$`**: Erlaubt Anfragen sowohl von `https://www.example.com` als auch von `http://www.example.com`.

=== "Grundlegende Konfiguration"

    Eine einfache Konfiguration, die Cross-Origin-Anfragen von derselben Domain erlaubt:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "self"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Konfiguration für öffentliche API"

    Konfiguration für eine öffentliche API, die von jedem Ursprung aus zugänglich sein muss:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "*"
    CORS_ALLOW_METHODS: "GET, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, X-API-Key"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "3600"
    CORS_DENY_REQUEST: "no"
    ```

=== "Mehrere vertrauenswürdige Domains"

    Konfiguration, die mehrere spezifische Domains mit einem einzigen PCRE-regulären Ausdrucksmuster erlaubt:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(app|api|dashboard)\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, DELETE, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Requested-With"
    CORS_ALLOW_CREDENTIALS: "yes"
    CORS_EXPOSE_HEADERS: "Content-Length, Content-Range, X-RateLimit-Remaining"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Subdomain-Platzhalter"

    Konfiguration, die alle Subdomains einer Hauptdomain mithilfe eines PCRE-regulären Ausdrucksmusters erlaubt:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://.*\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Mehrere Domain-Muster"

    Konfiguration, die Anfragen von mehreren Domain-Mustern mit Alternation erlaubt:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(.*\\.example\\.com|.*\\.trusted-partner\\.org|api\\.third-party\\.net)$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Custom-Header"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```
