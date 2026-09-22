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

!!! tip "Wiederverwendbare Pools von gRPC-Backends"
    Ein `GRPC_HOST` zeigt auf ein einzelnes Backend. Um über mehrere Backends zu verteilen oder dieselben Backends zwischen Diensten zu teilen, deklarieren Sie einen **gRPC-Upstream-Pool** auf der Seite **Upstreams** (oder über die `/upstreams`-API) und hängen ihn an einen Dienst mit einem Pfad an — BunkerWeb schreibt dann `grpc://<pool>` in den passenden `GRPC_HOST` für Sie. Beachten Sie, dass gRPC- und Reverse-Proxy-`location` sich auf einem Dienst einen Pfad-Namensraum teilen: derselbe Pfad kann nicht zweimal belegt werden, gleich welches Plugin ihn bedient. Siehe den Abschnitt *Wiederverwendbare Upstreams* in der Reverse-Proxy-Dokumentation.

!!! tip "Gegenseitiges TLS mit dem gRPC-Backend"
    gRPC hat eine eigene Upstream-Identität, unabhängig vom Reverse Proxy. Verwenden Sie für TLS-Upstreams `grpcs://` und konfigurieren Sie bei Bedarf `GRPC_SSL_SNI` und `GRPC_SSL_SNI_NAME`. Um das Upstream-Zertifikat zu überprüfen, setzen Sie `GRPC_SSL_VERIFY=yes` und stellen Sie ein PEM-CA-Bundle über `GRPC_SSL_TRUSTED_CERTIFICATE` oder `_DATA` bereit, wobei `_PRIORITY` (`file` oder `data`) die Quelle wählt. `GRPC_SSL_VERIFY_DEPTH` ist standardmäßig `1`. Es wird kein CA-Bundle automatisch ausgewählt: ohne zwischengespeicherte CA deaktiviert die generierte Konfiguration die Überprüfung und enthält einen Kommentar zur Konfiguration. Eine CRL ist optional (`GRPC_SSL_CRL` oder `_DATA`) und wird nur angewendet, wenn Überprüfung und eine zwischengespeicherte CA vorhanden sind. `GRPC_SSL_PROTOCOLS` und `GRPC_SSL_CIPHERS` belassen die NGINX-Standardwerte, wenn sie leer sind.

    Für gegenseitiges TLS setzen Sie `GRPC_SSL_CLIENT_CERT` und `GRPC_SSL_CLIENT_KEY` oder deren `_DATA`-Varianten; `GRPC_SSL_CLIENT_CERT_PRIORITY` wählt Dateipfade oder Daten für das Paar. Beide Hälften müssen gültig sein und zusammenpassen — BunkerWeb prüft, ob das Client-Zertifikat des Upstreams zu seinem Schlüssel passt; vorübergehende Lesefehler bei Dateien behalten das zwischengespeicherte TLS-Material und melden einen Job-Fehler, während gelöschte Einstellungen oder ungültiges Material den betroffenen Cache entfernen. Diese Identität gehört zu gRPC; Reverse Proxy und Stream verwenden unabhängig davon `REVERSE_PROXY_SSL_CLIENT_*`. Der gemeinsame `trusted-cert`-Job speichert die gRPC-CA, CRL und das Client-Paar im Reverseproxy-Cache-Verzeichnis zwischen und löst bei Materialänderungen eine Neugenerierung der Konfiguration aus. Es gibt keinen separaten gRPC-Zertifikatsjob. TLS-Einstellungen gelten für den gesamten Dienst einschließlich angehängter Upstream-Pools; sie sind keine Location-spezifischen Einstellungen. Siehe *Gegenseitiges TLS mit dem Upstream* in der Reverse-Proxy-Dokumentation.

### Konfigurationseinstellungen

| Setting                                 | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                              |
| ---------------------------------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GRPC`                              | `no`     | multisite | nein     | **gRPC aktivieren:** Auf `yes` setzen, um gRPC-Proxying zu aktivieren.                                                                     |
| `GRPC_HOST`                             |          | multisite | ja       | **gRPC-Upstream:** Wert für `grpc_pass` (z. B. `grpc://service:50051` oder `grpcs://...`).                                                 |
| `GRPC_URL`                              | `/`      | multisite | ja       | **Location-URL:** Pfad, der an das gRPC-Upstream weitergeleitet wird. Ein Wert, der mit `^` beginnt oder mit `$` endet, wird als Regex-Location behandelt. Optional kann ein Präfix `~`, `~*`, `=` oder `^~` gefolgt von einem Leerzeichen den nginx-Location-Modifikator explizit setzen; an anderer Stelle im Wert sind keine Leerzeichen, `;`, `{` oder `}` erlaubt. |
| `GRPC_CUSTOM_HOST`                      |          | multisite | nein     | **Eigener Host-Header:** Überschreibt den an das Upstream gesendeten `Host`-Header.                                                        |
| `GRPC_HEADERS`                          |          | multisite | ja       | **Upstream-Header:** Semikolon-getrennte `grpc_set_header`-Werte; passende generierte Header werden ohne Berücksichtigung der Groß-/Kleinschreibung ersetzt. |
| `GRPC_HIDE_HEADERS`                     |          | multisite | ja       | **Versteckte Antwort-Header:** Leerzeichen-getrennte Liste von `grpc_hide_header`-Werten.                                                  |
| `GRPC_HEADERS_CLIENT`                   |          | multisite | ja       | **Client-Antwort-Header:** Semikolon-getrennte Liste von `add_header`-Werten, die an den Client gesendet werden.                           |
| `GRPC_PASS_HEADERS`                     |          | multisite | ja       | **Durchgereichte Antwort-Header:** Leerzeichen-getrennte Liste von `grpc_pass_header`-Werten, um standardmäßig versteckte Header weiterzugeben. |
| `GRPC_IGNORE_HEADERS`                   |          | multisite | ja       | **Ignorierte Antwort-Header:** Leerzeichen-getrennte Liste von `grpc_ignore_headers`-Werten, damit NGINX sie nicht verarbeitet.             |
| `GRPC_UNDERSCORES_IN_HEADERS`           | `no`     | multisite | nein     | **Unterstriche in Headern erlauben:** Aktiviert/deaktiviert `underscores_in_headers`. Serverweit mit den Plugins Reverse Proxy und misc geteilt: aktiviert ein Dienst sie für eine Location, gilt sie für den gesamten Dienst. |
| `GRPC_INTERCEPT_ERRORS`                 | `yes`    | multisite | nein     | **Fehler abfangen:** Aktiviert/deaktiviert `grpc_intercept_errors`.                                                                        |
| `GRPC_BUFFER_SIZE`                      |          | multisite | ja       | **Puffergröße:** Wert für `grpc_buffer_size` (Puffer zum Lesen der Upstream-Antwort).                                                      |
| `GRPC_CONNECT_TIMEOUT`                  | `60s`    | multisite | ja       | **Connect-Timeout:** Timeout für den Verbindungsaufbau zum Upstream.                                                                       |
| `GRPC_READ_TIMEOUT`                     | `60s`    | multisite | ja       | **Read-Timeout:** Timeout für das Lesen vom Upstream.                                                                                      |
| `GRPC_SEND_TIMEOUT`                     | `60s`    | multisite | ja       | **Send-Timeout:** Timeout für das Senden an das Upstream.                                                                                  |
| `GRPC_SOCKET_KEEPALIVE`                 | `off`    | multisite | ja       | **Socket Keepalive:** Aktiviert/deaktiviert Keepalive auf Upstream-Sockets.                                                                |
| `GRPC_SSL_SNI`                          | `no`     | multisite | nein     | **SSL SNI:** Aktiviert/deaktiviert SNI für TLS-Upstreams.                                                                                  |
| `GRPC_SSL_SNI_NAME`                     |          | multisite | nein     | **SSL-SNI-Name:** SNI-Name, der gesendet wird, wenn `GRPC_SSL_SNI=yes`.                                                                    |
| `GRPC_SSL_VERIFY`                       | `no`     | multisite | nein     | **SSL-Überprüfung:** Aktiviert/deaktiviert die Überprüfung des gRPC-Upstream-Zertifikats.                                                  |
| `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY` | `file`   | multisite | nein     | **Priorität des vertrauenswürdigen Zertifikats:** Quelle des CA-Bundles, `file` oder `data`.                                               |
| `GRPC_SSL_TRUSTED_CERTIFICATE`          |          | multisite | nein     | **Pfad des vertrauenswürdigen Zertifikats:** Pfad zu einem PEM-CA-Bundle, lesbar für den Scheduler (Priorität `file`).                     |
| `GRPC_SSL_TRUSTED_CERTIFICATE_DATA`     |          | multisite | nein     | **Daten des vertrauenswürdigen Zertifikats:** CA-Bundle als Base64 oder Klartext-PEM (Priorität `data`).                                   |
| `GRPC_SSL_VERIFY_DEPTH`                 | `1`      | multisite | nein     | **SSL-Überprüfungstiefe:** Prüftiefe in der Upstream-Zertifikatskette.                                                                     |
| `GRPC_SSL_CLIENT_CERT_PRIORITY`         | `file`   | multisite | nein     | **Priorität des Client-Zertifikats:** Quelle von Client-Zertifikat und -Schlüssel, `file` oder `data`.                                     |
| `GRPC_SSL_CLIENT_CERT`                  |          | multisite | nein     | **Pfad des Client-Zertifikats:** PEM-Client-Zertifikat, das dem Upstream für gegenseitiges TLS präsentiert wird (Priorität `file`).        |
| `GRPC_SSL_CLIENT_CERT_DATA`             |          | multisite | nein     | **Daten des Client-Zertifikats:** Client-Zertifikat als Base64 oder Klartext-PEM (Priorität `data`).                                       |
| `GRPC_SSL_CLIENT_KEY`                   |          | multisite | nein     | **Pfad des Client-Schlüssels:** PEM-Privatschlüssel, der zum Client-Zertifikat passt (Priorität `file`). Er darf nicht verschlüsselt sein. |
| `GRPC_SSL_CLIENT_KEY_DATA`              |          | multisite | nein     | **Daten des Client-Schlüssels:** Privater Client-Schlüssel als Base64 oder Klartext-PEM (Priorität `data`).                                |
| `GRPC_SSL_CRL`                          |          | multisite | nein     | **CRL-Pfad:** PEM-Sperrliste, die bei der Überprüfung des Upstreams angewendet wird; wird nur angewendet, wenn `GRPC_SSL_VERIFY=yes` ist. Hat Vorrang vor der CRL-Daten-Einstellung; ein gesetzter, aber fehlender Pfad ist ein Fehler, die Daten-Einstellung wird nicht als Fallback verwendet. |
| `GRPC_SSL_CRL_DATA`                     |          | multisite | nein     | **CRL-Daten:** Sperrliste als Base64 oder Klartext-PEM. Wird nur verwendet, wenn der CRL-Pfad leer ist.                                    |
| `GRPC_SSL_PROTOCOLS`                    |          | multisite | nein     | **Upstream-SSL-Protokolle:** Dem Upstream angebotene TLS-Versionen. Leer belässt den NGINX-Standard.                                       |
| `GRPC_SSL_CIPHERS`                      |          | multisite | nein     | **Upstream-SSL-Ciphers:** Dem Upstream angebotene Cipher-Suite-Zeichenkette. Leer belässt den NGINX-Standard.                              |
| `GRPC_NEXT_UPSTREAM`                    |          | multisite | ja       | **Next-Upstream-Bedingungen:** Wert für `grpc_next_upstream`.                                                                              |
| `GRPC_NEXT_UPSTREAM_TIMEOUT`            |          | multisite | ja       | **Next-Upstream-Timeout:** Wert für `grpc_next_upstream_timeout`.                                                                          |
| `GRPC_NEXT_UPSTREAM_TRIES`              |          | multisite | ja       | **Next-Upstream-Versuche:** Wert für `grpc_next_upstream_tries`.                                                                           |
| `GRPC_AUTH_REQUEST`                     |          | multisite | ja       | **Auth Request:** Wert für `auth_request`, um über einen externen Provider zu authentifizieren.                                            |
| `GRPC_AUTH_REQUEST_SIGNIN_URL`          |          | multisite | ja       | **Auth-Request-Signin-URL:** Weiterleitungsziel, wenn der Auth Request 401 zurückgibt. Fragmente (`#`) werden unterstützt.                 |
| `GRPC_AUTH_REQUEST_SET`                 |          | multisite | ja       | **Auth Request Set:** Semikolon-getrennte Liste von `auth_request_set`-Werten.                                                             |
| `GRPC_INCLUDES`                         |          | multisite | ja       | **Zusätzliche Includes:** Leerzeichen-getrennte Include-Dateien innerhalb des gRPC-`location`-Blocks.                                      |
| `GRPC_MAX_CLIENT_SIZE`                  |          | multisite | ja       | **Maximale Body-Größe:** Wert für `client_max_body_size` in dieser Location (`0` für unbegrenzt). Fällt auf die dienstweite `MAX_CLIENT_SIZE` zurück. |

`GRPC_HOST`, `GRPC_URL`, `GRPC_HEADERS`, `GRPC_HIDE_HEADERS`, `GRPC_HEADERS_CLIENT`, `GRPC_PASS_HEADERS`, `GRPC_IGNORE_HEADERS`, `GRPC_BUFFER_SIZE`, `GRPC_CONNECT_TIMEOUT`, `GRPC_READ_TIMEOUT`, `GRPC_SEND_TIMEOUT`, `GRPC_SOCKET_KEEPALIVE`, `GRPC_NEXT_UPSTREAM{,_TIMEOUT,_TRIES}`, `GRPC_AUTH_REQUEST{,_SIGNIN_URL,_SET}`, `GRPC_INCLUDES` und `GRPC_MAX_CLIENT_SIZE` unterstützen numerische Suffixe für mehrere Upstreams/Locations (`GRPC_HOST_2`, `GRPC_URL_2`, ...). `GRPC_HEADERS_CLIENT` folgt der NGINX-`add_header`-Semantik (bei Bedarf `always` anhängen). Auth-Signin-URLs unterstützen weiterhin Fragmente (`#`). ModSecurity bleibt in gRPC-Locations deaktiviert.

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
    GRPC_NEXT_UPSTREAM: "error timeout http_502"
    GRPC_NEXT_UPSTREAM_TIMEOUT: "15s"
    GRPC_NEXT_UPSTREAM_TRIES: "3"
    ```
