Das gRPC-Plugin ermöglicht BunkerWeb, gRPC-Dienste über HTTP/2 mit `grpc_pass` zu proxien. Es ist für Multisite-Setups konzipiert, bei denen jeder virtuelle Host einen oder mehrere gRPC-Backends unter bestimmten Pfaden bereitstellen kann.

!!! example "Experimentelle Funktion"
    Diese Funktion ist noch nicht produktionsreif. Testen Sie sie gerne und melden Sie uns Fehler über [Issues](https://github.com/bunkerity/bunkerweb/issues) im GitHub-Repository.

**Funktionsweise:**

1. Ein Client sendet eine HTTP/2-Anfrage an BunkerWeb.
2. Das gRPC-Plugin gleicht eine konfigurierte `location` (`GRPC_URL`) ab und leitet die Anfrage mit `grpc_pass` an das konfigurierte Upstream (`GRPC_HOST`) weiter.
3. BunkerWeb fügt Forwarding-Header hinzu und wendet Timeout-/Retry-Einstellungen für Upstreams an.
4. Der gRPC-Upstream antwortet und BunkerWeb leitet die Antwort an den Client zurück.

### Verwendung

1. **Funktion aktivieren:** Setzen Sie `USE_GRPC` auf `yes`.
2. **Upstream(s) konfigurieren:** Setzen Sie mindestens `GRPC_HOST` (optional zusätzlich `GRPC_HOST_2`, `GRPC_HOST_3`, ...).
3. **Pfad(e) zuordnen:** Setzen Sie `GRPC_URL` pro Upstream (bei mehreren Einträgen mit passenden Suffixen).
4. **Verhalten abstimmen:** Konfigurieren Sie bei Bedarf Timeouts, Retries, Header und TLS-SNI-Optionen.

### Konfigurationseinstellungen

| Einstellung                             | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                           |
| --------------------------------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_GRPC`                              | `no`     | multisite | nein     | **gRPC aktivieren:** Auf `yes` setzen, um gRPC-Proxying zu aktivieren.                                                                                 |
| `GRPC_HOST`                             |          | multisite | ja       | **gRPC-Upstream:** Wert für `grpc_pass` (z. B. `grpc://service:50051` oder `grpcs://...`).                                                             |
| `GRPC_URL`                              | `/`      | multisite | ja       | **Location-URL:** Pfad, der an das gRPC-Upstream weitergeleitet wird.                                                                                  |
| `GRPC_CUSTOM_HOST`                      |          | multisite | nein     | **Eigener Host-Header:** Überschreibt den an das Upstream gesendeten `Host`-Header.                                                                    |
| `GRPC_HEADERS`                          |          | multisite | ja       | **Zusätzliche Upstream-Header:** Semikolon-getrennte Liste von `grpc_set_header`-Werten.                                                               |
| `GRPC_HIDE_HEADERS`                     |          | multisite | ja       | **Versteckte Antwort-Header:** Leerzeichen-getrennte Liste von `grpc_hide_header`-Werten.                                                              |
| `GRPC_HEADERS_CLIENT`                   |          | multisite | ja       | **Antwort-Header für Clients:** Semikolon-getrennte Liste von `add_header`-Werten, die an den Client gesendet werden.                                  |
| `GRPC_PASS_HEADERS`                     |          | multisite | ja       | **Durchgereichte Antwort-Header:** Leerzeichen-getrennte Liste von `grpc_pass_header`-Werten, um standardmäßig verborgene Header weiterzugeben.        |
| `GRPC_IGNORE_HEADERS`                   |          | multisite | ja       | **Ignorierte Antwort-Header:** Leerzeichen-getrennte Liste von `grpc_ignore_headers`-Werten, damit NGINX sie nicht verarbeitet.                        |
| `GRPC_UNDERSCORES_IN_HEADERS`           | `no`     | multisite | nein     | **Unterstriche in Headern:** Aktiviert/deaktiviert `underscores_in_headers`.                                                                           |
| `GRPC_INTERCEPT_ERRORS`                 | `yes`    | multisite | nein     | **Fehler abfangen:** Aktiviert/deaktiviert `grpc_intercept_errors`.                                                                                    |
| `GRPC_BUFFER_SIZE`                      |          | multisite | ja       | **Puffergröße:** Wert für `grpc_buffer_size` (Puffer zum Lesen der Upstream-Antwort).                                                                  |
| `GRPC_CONNECT_TIMEOUT`                  | `60s`    | multisite | ja       | **Connect-Timeout:** Timeout für den Verbindungsaufbau zum Upstream.                                                                                   |
| `GRPC_READ_TIMEOUT`                     | `60s`    | multisite | ja       | **Read-Timeout:** Timeout für das Lesen vom Upstream.                                                                                                  |
| `GRPC_SEND_TIMEOUT`                     | `60s`    | multisite | ja       | **Send-Timeout:** Timeout für das Senden an das Upstream.                                                                                              |
| `GRPC_SOCKET_KEEPALIVE`                 | `off`    | multisite | ja       | **Socket Keepalive:** Aktiviert/deaktiviert Keepalive auf Upstream-Sockets.                                                                            |
| `GRPC_SSL_SNI`                          | `no`     | multisite | nein     | **SSL SNI:** Aktiviert/deaktiviert SNI für TLS-Upstreams.                                                                                              |
| `GRPC_SSL_SNI_NAME`                     |          | multisite | nein     | **SSL-SNI-Name:** SNI-Name, der gesendet wird, wenn `GRPC_SSL_SNI=yes`.                                                                                |
| `GRPC_SSL_VERIFY`                       | `no`     | multisite | nein     | **SSL-Prüfung:** Aktiviert/deaktiviert die Prüfung des gRPC-Upstream-Zertifikats.                                                                      |
| `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY` | `file`   | multisite | nein     | **Priorität des vertrauenswürdigen Zertifikats:** Quelle des CA-Bundles, `file` oder `data`.                                                           |
| `GRPC_SSL_TRUSTED_CERTIFICATE`          |          | multisite | nein     | **Pfad des vertrauenswürdigen Zertifikats:** Pfad zu einem PEM-CA-Bundle, das der Scheduler lesen kann (Priorität `file`).                             |
| `GRPC_SSL_TRUSTED_CERTIFICATE_DATA`     |          | multisite | nein     | **Daten des vertrauenswürdigen Zertifikats:** CA-Bundle als base64 oder Klartext-PEM (Priorität `data`).                                               |
| `GRPC_SSL_VERIFY_DEPTH`                 | `1`      | multisite | nein     | **SSL-Prüftiefe:** Prüftiefe in der Upstream-Zertifikatskette.                                                                                         |
| `GRPC_SSL_CERT_PRIORITY`                | `file`   | multisite | nein     | **Priorität des Client-Zertifikats:** Quelle von Zertifikat und Schlüssel, `file` oder `data`.                                                         |
| `GRPC_SSL_CERT`                         |          | multisite | nein     | **Pfad des Client-Zertifikats:** PEM-Client-Zertifikat, das dem Upstream für gegenseitiges TLS vorgelegt wird (Priorität `file`).                      |
| `GRPC_SSL_CERT_DATA`                    |          | multisite | nein     | **Daten des Client-Zertifikats:** Client-Zertifikat als base64 oder Klartext-PEM (Priorität `data`).                                                   |
| `GRPC_SSL_KEY`                          |          | multisite | nein     | **Pfad des Client-Schlüssels:** Zum Client-Zertifikat passender privater PEM-Schlüssel (Priorität `file`). Er darf nicht verschlüsselt sein.           |
| `GRPC_SSL_KEY_DATA`                     |          | multisite | nein     | **Daten des Client-Schlüssels:** Privater Client-Schlüssel als base64 oder Klartext-PEM (Priorität `data`).                                            |
| `GRPC_SSL_CRL`                          |          | multisite | nein     | **CRL-Pfad:** PEM-Sperrliste, die bei der Upstream-Prüfung angewendet wird. Hat Vorrang vor den CRL-Daten.                                             |
| `GRPC_SSL_CRL_DATA`                     |          | multisite | nein     | **CRL-Daten:** Sperrliste als base64 oder Klartext-PEM. Wird nur verwendet, wenn der CRL-Pfad leer ist.                                                |
| `GRPC_SSL_PROTOCOLS`                    |          | multisite | nein     | **Upstream-SSL-Protokolle:** Dem Upstream angebotene TLS-Versionen. Leer behält den NGINX-Standard bei.                                                |
| `GRPC_SSL_CIPHERS`                      |          | multisite | nein     | **Upstream-SSL-Chiffren:** Dem Upstream angebotene Cipher-Suite. Leer behält den NGINX-Standard bei.                                                   |
| `GRPC_NEXT_UPSTREAM`                    |          | multisite | ja       | **Next-Upstream-Bedingungen:** Wert für `grpc_next_upstream`.                                                                                          |
| `GRPC_NEXT_UPSTREAM_TIMEOUT`            |          | multisite | ja       | **Next-Upstream-Timeout:** Wert für `grpc_next_upstream_timeout`.                                                                                      |
| `GRPC_NEXT_UPSTREAM_TRIES`              |          | multisite | ja       | **Next-Upstream-Versuche:** Wert für `grpc_next_upstream_tries`.                                                                                       |
| `GRPC_AUTH_REQUEST`                     |          | multisite | ja       | **Auth Request:** Wert für `auth_request`, um über einen externen Anbieter zu authentifizieren.                                                        |
| `GRPC_AUTH_REQUEST_SIGNIN_URL`          |          | multisite | ja       | **Auth-Request-Anmelde-URL:** Weiterleitungsziel, wenn der Auth-Request 401 zurückgibt.                                                                |
| `GRPC_AUTH_REQUEST_SET`                 |          | multisite | ja       | **Auth Request Set:** Semikolon-getrennte Liste von `auth_request_set`-Werten.                                                                         |
| `GRPC_INCLUDES`                         |          | multisite | ja       | **Zusätzliche Includes:** Leerzeichen-getrennte Include-Dateien innerhalb des gRPC-`location`-Blocks.                                                  |
| `GRPC_MAX_CLIENT_SIZE`                  |          | multisite | ja       | **Maximale Body-Größe:** Wert für `client_max_body_size` in diesem Location-Block (`0` für unbegrenzt). Ohne Wert gilt `MAX_CLIENT_SIZE` des Dienstes. |

!!! tip "Gegenseitiges TLS zum Upstream"
    Client-Zertifikat und Schlüssel müssen beide angegeben werden, und der Schlüssel darf nicht verschlüsselt sein. Der Scheduler prüft das Paar, legt es im Cache ab und verteilt es an die Instanzen; ist es ungültig, werden die Zertifikatsdirektiven schlicht nicht erzeugt. Eine CRL wird nur angewendet, solange die Upstream-Prüfung aktiv ist.

!!! warning "ModSecurity in gRPC-Location-Blöcken"
    ModSecurity wird aktuell in den von diesem Plugin generierten gRPC-`location`-Blöcken automatisch deaktiviert, da ModSecurity gRPC-Verkehrsmuster nicht zuverlässig unterstützt.

!!! tip "Upstream-Zertifikat prüfen"
    `GRPC_SSL_VERIFY` wirkt erst, wenn ein CA-Bundle verfügbar ist. Stellen Sie es über `GRPC_SSL_TRUSTED_CERTIFICATE` (ein für den Scheduler lesbarer Pfad) oder `GRPC_SSL_TRUSTED_CERTIFICATE_DATA` (base64 oder Klartext-PEM) bereit und wählen Sie die Quelle mit `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY`. Der Scheduler prüft das Bundle, legt es im Cache ab und verteilt es an die Instanzen. Ohne nutzbares Bundle bleibt die Prüfung deaktiviert.

!!! warning "Lang laufende Streams und Core-Timeouts"
    Lang laufende oder Streaming-RPCs benötigen eventuell höhere generische NGINX-Timeouts als die globalen Standardwerte. Am häufigsten werden `CLIENT_BODY_TIMEOUT` und `CLIENT_HEADER_TIMEOUT` in den Einstellungen des General-Plugins angepasst.

!!! tip "Mehrere gRPC-Backends"
    Nutzen Sie suffixierte Einstellungen für mehrere Routen:
    - `GRPC_HOST`, `GRPC_URL`
    - `GRPC_HOST_2`, `GRPC_URL_2`
    - `GRPC_HOST_3`, `GRPC_URL_3`

### Beispielkonfigurationen

=== "Grundlegender gRPC-Proxy"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_CONNECT_TIMEOUT: "10s"
    GRPC_READ_TIMEOUT: "300s"
    GRPC_SEND_TIMEOUT: "300s"
    ```

=== "TLS-Upstream (grpcs + SNI)"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpcs://internal-grpc.example.net:443"
    GRPC_URL: "/"
    GRPC_SSL_SNI: "yes"
    GRPC_SSL_SNI_NAME: "internal-grpc.example.net"
    ```

=== "Mehrere Pfade / Backends"

    ```yaml
    USE_GRPC: "yes"

    GRPC_HOST: "grpc://user-service:50051"
    GRPC_URL: "/users.UserService/"

    GRPC_HOST_2: "grpc://billing-service:50052"
    GRPC_URL_2: "/billing.BillingService/"

    GRPC_HOST_3: "grpc://inventory-service:50053"
    GRPC_URL_3: "/inventory.InventoryService/"
    ```

=== "Header und Retry-Richtlinie"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_HEADERS: "x-request-source bunkerweb;x-env production"
    GRPC_NEXT_UPSTREAM: "error timeout unavailable"
    GRPC_NEXT_UPSTREAM_TIMEOUT: "15s"
    GRPC_NEXT_UPSTREAM_TRIES: "3"
    ```

=== "Geprüftes TLS-Upstream"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpcs://internal-grpc.example.net:443"
    GRPC_URL: "/"
    GRPC_SSL_SNI: "yes"
    GRPC_SSL_SNI_NAME: "internal-grpc.example.net"
    GRPC_SSL_VERIFY: "yes"
    GRPC_SSL_TRUSTED_CERTIFICATE: "/etc/ssl/certs/ca-certificates.crt"
    GRPC_SSL_VERIFY_DEPTH: "2"
    ```

=== "Externe Authentifizierung"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_AUTH_REQUEST: "/auth"
    GRPC_AUTH_REQUEST_SIGNIN_URL: "https://sso.example.com/login"
    GRPC_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_email $upstream_http_x_email"
    GRPC_HEADERS: "x-forwarded-user $auth_user"
    ```
