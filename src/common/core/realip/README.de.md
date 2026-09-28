Das Real IP Plugin stellt sicher, dass BunkerWeb die IP-Adresse des Clients auch hinter Proxys korrekt identifiziert. Dies ist unerlässlich für die Anwendung von Sicherheitsregeln, Ratenbegrenzung und zuverlässige Protokolle; andernfalls würden alle Anfragen von der IP des Proxys zu kommen scheinen.

So funktioniert's:

1.  Nach der Aktivierung prüft BunkerWeb die Header (z.B. [`X-Forwarded-For`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Forwarded-For)), die die ursprüngliche IP enthalten.
2.  Es wird überprüft, ob die Quell-IP in `REAL_IP_FROM` (Liste vertrauenswürdiger Proxys) enthalten ist, um nur legitime Proxys zu akzeptieren.
3.  Die Client-IP wird aus dem Header `REAL_IP_HEADER` extrahiert und für die Sicherheitsbewertung und Protokollierung verwendet.
4.  Bei IP-Ketten kann eine rekursive Suche die ursprüngliche IP ermitteln.
5.  Die Unterstützung für das [PROXY-Protokoll](https://netnut.io/what-is-proxy-protocol-and-how-does-it-work/) kann aktiviert werden, um die Client-IP direkt von kompatiblen Proxys (z.B. [HAProxy](https://www.haproxy.org/)) zu empfangen.
6.  Listen mit vertrauenswürdigen Proxy-IPs können automatisch über URLs heruntergeladen werden.

### Verwendung

1.  Aktivieren: Setzen Sie den Parameter `USE_REAL_IP` auf `yes`.
2.  Vertrauenswürdige Proxys: Geben Sie IP/Bereiche in `REAL_IP_FROM` ein.
3.  Header: Geben Sie an, welcher Header die echte IP über `REAL_IP_HEADER` enthält.
4.  Rekursiv: Aktivieren Sie `REAL_IP_RECURSIVE` bei Bedarf.
5.  URL-Quellen: Verwenden Sie `REAL_IP_FROM_URLS`, um Listen herunterzuladen.
6.  PROXY-Protokoll: Aktivieren Sie `USE_PROXY_PROTOCOL`, wenn das Upstream-System es unterstützt.

!!! danger "Warnung PROXY-Protokoll"
    Das Aktivieren von `USE_PROXY_PROTOCOL` ohne ein korrekt konfiguriertes Upstream-System, das es aussendet, führt dazu, dass Ihre Anwendung nicht funktioniert. Stellen Sie sicher, dass Sie es vor der Aktivierung konfiguriert haben.

### Parameter

| Parameter            | Standard                                  | Kontext   | Mehrfach | Beschreibung                                                                                 |
| :------------------- | :---------------------------------------- | :-------- | :------- | :------------------------------------------------------------------------------------------- |
| `USE_REAL_IP`        | `no`                                      | multisite | nein     | Aktiviert die Abfrage der echten IP aus Headern oder dem PROXY-Protokoll.                    |
| `REAL_IP_FROM`       | `192.168.0.0/16 172.16.0.0/12 10.0.0.0/8` | multisite | nein     | Vertrauenswürdige Proxys: Liste von IP/Netzwerken, durch Leerzeichen getrennt.               |
| `REAL_IP_HEADER`     | `X-Forwarded-For`                         | multisite | nein     | Header, der die echte IP enthält, oder der spezielle Wert `proxy_protocol`.                  |
| `REAL_IP_RECURSIVE`  | `yes`                                     | multisite | nein     | Rekursive Suche in einem Header, der mehrere IPs enthält.                                    |
| `REAL_IP_FROM_URLS`  |                                           | multisite | nein     | URLs, die IPs/Netzwerke von vertrauenswürdigen Proxys bereitstellen (unterstützt `file://`). |
| `USE_PROXY_PROTOCOL` | `no`                                      | global    | nein     | Aktiviert die PROXY-Protokoll-Unterstützung für die direkte Proxy→BunkerWeb-Kommunikation.   |

!!! tip "Cloud-Anbieter"
    Fügen Sie die IPs Ihrer Load Balancer (AWS/GCP/Azure…) zu `REAL_IP_FROM` hinzu, um eine korrekte Identifizierung zu gewährleisten.

!!! danger "Sicherheitsaspekte"
    Fügen Sie nur vertrauenswürdige Quellen hinzu, da sonst die Gefahr der IP-Spoofing über manipulierte Header besteht.

!!! info "Mehrere Adressen"
    Mit `REAL_IP_RECURSIVE` wird, wenn der Header mehrere IPs enthält, die erste IP, die nicht als vertrauenswürdiger Proxy aufgeführt ist, als Client-IP verwendet.

### Beispiele

=== "Basis (hinter Reverse Proxy)"

    Einfache Konfiguration für eine Website hinter einem Reverse Proxy:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24 10.0.0.5"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "Cloud Load Balancer"

    Konfiguration für eine Website hinter einem Cloud Load Balancer:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "PROXY-Protokoll"

    Konfiguration mit PROXY-Protokoll und einem kompatiblen Load Balancer:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24"
    REAL_IP_HEADER: "proxy_protocol"
    USE_PROXY_PROTOCOL: "yes"
    ```

=== "Mehrere Proxy-Quellen mit URLs"

    Erweiterte Konfiguration mit automatisch aktualisierten Proxy-IP-Listen:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Real-IP"
    REAL_IP_RECURSIVE: "yes"
    REAL_IP_FROM_URLS: "https://example.com/proxy-ips.txt file:///etc/bunkerweb/custom-proxies.txt"
    ```

=== "CDN-Konfiguration"

    Konfiguration für eine Website hinter einem CDN:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_FROM_URLS: "https://cdn-provider.com/ip-ranges.txt"
    REAL_IP_HEADER: "CF-Connecting-IP"  # Beispiel für Cloudflare
    REAL_IP_RECURSIVE: "no"  # Bei Headern mit einzelner IP nicht erforderlich
    ```

=== "Hinter Cloudflare"

    Konfiguration für eine Website hinter Cloudflare:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "" # Wir vertrauen nur Cloudflare-IPs
    REAL_IP_FROM_URLS: "https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/" # Cloudflare-IPs automatisch herunterladen
    REAL_IP_HEADER: "CF-Connecting-IP"  # Cloudflare-Header für Client-IP
    REAL_IP_RECURSIVE: "yes"
    ```
