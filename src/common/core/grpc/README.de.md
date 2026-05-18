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

| Einstellung                  | Standard | Kontext   | Mehrfach | Beschreibung                                                                                          |
| ---------------------------- | -------- | --------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `USE_GRPC`                   | `no`     | multisite | nein     | **gRPC aktivieren:** Auf `yes` setzen, um gRPC-Proxying zu aktivieren.                                |
| `GRPC_HOST`                  |          | multisite | ja       | **gRPC-Upstream:** Wert für `grpc_pass` (z. B. `grpc://service:50051` oder `grpcs://...`).            |
| `GRPC_URL`                   | `/`      | multisite | ja       | **Location-URL:** Pfad, der an das gRPC-Upstream weitergeleitet wird.                                 |
| `GRPC_CUSTOM_HOST`           |          | multisite | nein     | **Eigener Host-Header:** Überschreibt den an das Upstream gesendeten `Host`-Header.                   |
| `GRPC_HEADERS`               |          | multisite | ja       | **Zusätzliche Upstream-Header:** Semikolon-getrennte Liste von `grpc_set_header`-Werten.              |
| `GRPC_HIDE_HEADERS`          |          | multisite | ja       | **Versteckte Antwort-Header:** Leerzeichen-getrennte Liste von `grpc_hide_header`-Werten.             |
| `GRPC_INTERCEPT_ERRORS`      | `yes`    | multisite | nein     | **Fehler abfangen:** Aktiviert/deaktiviert `grpc_intercept_errors`.                                   |
| `GRPC_CONNECT_TIMEOUT`       | `60s`    | multisite | ja       | **Connect-Timeout:** Timeout für den Verbindungsaufbau zum Upstream.                                  |
| `GRPC_READ_TIMEOUT`          | `60s`    | multisite | ja       | **Read-Timeout:** Timeout für das Lesen vom Upstream.                                                 |
| `GRPC_SEND_TIMEOUT`          | `60s`    | multisite | ja       | **Send-Timeout:** Timeout für das Senden an das Upstream.                                             |
| `GRPC_SOCKET_KEEPALIVE`      | `off`    | multisite | ja       | **Socket Keepalive:** Aktiviert/deaktiviert Keepalive auf Upstream-Sockets.                           |
| `GRPC_SSL_SNI`               | `no`     | multisite | nein     | **SSL SNI:** Aktiviert/deaktiviert SNI für TLS-Upstreams.                                             |
| `GRPC_SSL_SNI_NAME`          |          | multisite | nein     | **SSL-SNI-Name:** SNI-Name, der gesendet wird, wenn `GRPC_SSL_SNI=yes`.                               |
| `GRPC_NEXT_UPSTREAM`         |          | multisite | ja       | **Next-Upstream-Bedingungen:** Wert für `grpc_next_upstream`.                                         |
| `GRPC_NEXT_UPSTREAM_TIMEOUT` |          | multisite | ja       | **Next-Upstream-Timeout:** Wert für `grpc_next_upstream_timeout`.                                     |
| `GRPC_NEXT_UPSTREAM_TRIES`   |          | multisite | ja       | **Next-Upstream-Versuche:** Wert für `grpc_next_upstream_tries`.                                      |
| `GRPC_INCLUDES`              |          | multisite | ja       | **Zusätzliche Includes:** Leerzeichen-getrennte Include-Dateien innerhalb des gRPC-`location`-Blocks. |

!!! warning "ModSecurity in gRPC-Location-Blöcken"
    ModSecurity wird aktuell in den von diesem Plugin generierten gRPC-`location`-Blöcken automatisch deaktiviert, da ModSecurity gRPC-Verkehrsmuster nicht zuverlässig unterstützt.

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
