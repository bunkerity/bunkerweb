Das Let's Encrypt-Plugin vereinfacht die Verwaltung von SSL/TLS-Zertifikaten durch die Automatisierung der Erstellung, Erneuerung und Konfiguration von kostenlosen Zertifikaten von Let's Encrypt. Diese Funktion ermöglicht sichere HTTPS-Verbindungen für Ihre Websites ohne die Komplexität der manuellen Zertifikatsverwaltung, was sowohl Kosten als auch administrativen Aufwand reduziert.

**Wie es funktioniert:**

1.  Nach der Aktivierung erkennt BunkerWeb automatisch die für Ihre Website konfigurierten Domains.
2.  BunkerWeb beantragt kostenlose SSL/TLS-Zertifikate bei der Zertifizierungsstelle von Let's Encrypt.
3.  Der Domainbesitz wird entweder durch HTTP-Challenges (Nachweis, dass Sie die Website kontrollieren) oder DNS-Challenges (Nachweis, dass Sie die DNS Ihrer Domain kontrollieren) verifiziert.
4.  Zertifikate werden automatisch für Ihre Domains installiert und konfiguriert.
5.  BunkerWeb kümmert sich im Hintergrund um die Erneuerung der Zertifikate vor deren Ablauf und gewährleistet so eine kontinuierliche HTTPS-Verfügbarkeit.
6.  Der gesamte Prozess ist vollständig automatisiert und erfordert nach der Ersteinrichtung nur minimale Eingriffe.

!!! info "Voraussetzungen"
    Um diese Funktion nutzen zu können, stellen Sie sicher, dass für jede Domain korrekte DNS-**A-Einträge** konfiguriert sind, die auf die öffentliche(n) IP(s) verweisen, unter der/denen BunkerWeb erreichbar ist. Ohne korrekte DNS-Konfiguration schlägt der Domain-Verifizierungsprozess fehl.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Let's Encrypt-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Setzen Sie die Einstellung `AUTO_LETS_ENCRYPT` auf `yes`, um die automatische Ausstellung und Erneuerung von Zertifikaten zu aktivieren.
2.  **Kontakt-E-Mail angeben (empfohlen):** Geben Sie Ihre E-Mail-Adresse in der Einstellung `EMAIL_LETS_ENCRYPT` ein, damit Let's Encrypt Sie vor ablaufenden Zertifikaten warnen kann. Wenn Sie das Feld leer lassen, registriert sich BunkerWeb ohne Adresse (Certbot-Option `--register-unsafely-without-email`) – Sie erhalten dann keine Erinnerungen oder Wiederherstellungs-E-Mails.
3.  **Wählen Sie den Challenge-Typ:** Wählen Sie entweder die `http`- oder `dns`-Verifizierung mit der Einstellung `LETS_ENCRYPT_CHALLENGE`.
4.  **DNS-Anbieter konfigurieren:** Wenn Sie DNS-Challenges verwenden, geben Sie Ihren DNS-Anbieter und Ihre Anmeldeinformationen an.
5.  **Zertifikatsprofil auswählen:** Wählen Sie Ihr bevorzugtes Zertifikatsprofil mit der Einstellung `LETS_ENCRYPT_PROFILE` (classic, tlsserver oder shortlived).
6.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration werden Zertifikate automatisch ausgestellt, installiert und bei Bedarf erneuert.

!!! tip "Zertifikatsprofile"
    Let's Encrypt bietet verschiedene Zertifikatsprofile für unterschiedliche Anwendungsfälle:

    - **classic**: Allzweck-Zertifikate mit 90-tägiger Gültigkeit (Standard)
    - **tlsserver**: Optimiert für die TLS-Server-Authentifizierung mit 90-tägiger Gültigkeit und kleinerem Payload
    - **shortlived**: Erhöhte Sicherheit mit 7-tägiger Gültigkeit für automatisierte Umgebungen
    - **custom**: Wenn Ihr ACME-Server ein anderes Profil unterstützt, legen Sie es mit `LETS_ENCRYPT_CUSTOM_PROFILE` fest.

!!! info "Profilverfügbarkeit"
    Beachten Sie, dass die Profile `tlsserver` und `shortlived` derzeit möglicherweise nicht in allen Umgebungen oder mit allen ACME-Clients verfügbar sind. Das `classic`-Profil hat die breiteste Kompatibilität und wird für die meisten Benutzer empfohlen. Wenn ein ausgewähltes Profil nicht verfügbar ist, greift das System automatisch auf das `classic`-Profil zurück.

### Konfigurationseinstellungen

| Einstellung                                 | Standard  | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------- | --------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AUTO_LETS_ENCRYPT`                         | `no`      | multisite | nein     | **Let's Encrypt aktivieren:** Auf `yes` setzen, um die automatische Ausstellung und Erneuerung von Zertifikaten zu aktivieren.                                                                                                                                                                                                                                         |
| `LETS_ENCRYPT_PASSTHROUGH`                  | `no`      | multisite | nein     | **Let's Encrypt durchleiten:** Auf `yes` setzen, um Let's Encrypt-Anfragen an den Webserver weiterzuleiten. Dies ist nützlich, wenn BunkerWeb hinter einem anderen Reverse-Proxy mit SSL-Handling steht.                                                                                                                                                               |
| `EMAIL_LETS_ENCRYPT`                        | `-`       | multisite | nein     | **Kontakt-E-Mail:** E-Mail-Adresse für Let's-Encrypt-Erinnerungen. Lassen Sie das Feld nur leer, wenn Sie akzeptieren, dass keine Warnungen oder Wiederherstellungs-E-Mails gesendet werden (Certbot registriert mit `--register-unsafely-without-email`).                                                                                                             |
| `LETS_ENCRYPT_CHALLENGE`                    | `http`    | multisite | nein     | **Challenge-Typ:** Methode zur Überprüfung des Domainbesitzes. Optionen: `http` oder `dns`.                                                                                                                                                                                                                                                                            |
| `LETS_ENCRYPT_DNS_PROVIDER`                 |           | multisite | nein     | **DNS-Anbieter:** Bei Verwendung von DNS-Challenges der zu verwendende DNS-Anbieter (z.B. cloudflare, route53, digitalocean).                                                                                                                                                                                                                                          |
| `LETS_ENCRYPT_DNS_PROPAGATION`              | `default` | multisite | nein     | **DNS-Propagation:** Die Wartezeit für die DNS-Propagation in Sekunden. Wenn kein Wert angegeben wird, wird die Standard-Propagationszeit des Anbieters verwendet.                                                                                                                                                                                                     |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`          |           | multisite | ja       | **Anmeldeinformationselement:** Konfigurationselemente für die Authentifizierung des DNS-Anbieters (z. B. `cloudflare_api_token 123456`). Werte können Rohtext, base64-kodiert oder ein JSON-Objekt sein.                                                                                                                                                              |
| `LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64` | `yes`     | multisite | nein     | **DNS-Anmeldeinformationen Base64 dekodieren:** Dekodiert automatisch base64-kodierte DNS-Anbieter-Anmeldeinformationen, wenn auf `yes` gesetzt. Wenn aktiviert, werden Werte, die dem Base64-Format entsprechen, vor der Verwendung dekodiert (außer beim `rfc2136`-Anbieter). Deaktivieren Sie dies, wenn Ihre Anmeldeinformationen absichtlich Base64-codiert sind. |
| `USE_LETS_ENCRYPT_WILDCARD`                 | `no`      | multisite | nein     | **Wildcard-Zertifikate:** Wenn auf `yes` gesetzt, werden Wildcard-Zertifikate für alle Domains erstellt. Nur mit DNS-Challenges verfügbar.                                                                                                                                                                                                                             |
| `USE_LETS_ENCRYPT_STAGING`                  | `no`      | multisite | nein     | **Staging verwenden:** Wenn auf `yes` gesetzt, wird die Staging-Umgebung von Let's Encrypt zum Testen verwendet. Staging hat höhere Ratenbegrenzungen, aber die Zertifikate sind nicht vertrauenswürdig.                                                                                                                                                               |
| `LETS_ENCRYPT_CLEAR_OLD_CERTS`              | `no`      | global    | nein     | **Alte Zertifikate löschen:** Wenn auf `yes` gesetzt, werden alte Zertifikate, die bei der Erneuerung nicht mehr benötigt werden, entfernt.                                                                                                                                                                                                                            |
| `LETS_ENCRYPT_CONCURRENT_REQUESTS`          | `no`      | global    | nein     | **Parallele Anfragen:** Wenn auf `yes` gesetzt, stellt certbot-new Zertifikatsanfragen parallel. Vorsicht wegen Rate-Limits.                                                                                                                                                                                                                                           |
| `LETS_ENCRYPT_PROFILE`                      | `classic` | multisite | nein     | **Zertifikatsprofil:** Wählen Sie das zu verwendende Zertifikatsprofil aus. Optionen: `classic` (Allzweck), `tlsserver` (optimiert für TLS-Server) oder `shortlived` (7-Tage-Zertifikate).                                                                                                                                                                             |
| `LETS_ENCRYPT_CUSTOM_PROFILE`               |           | multisite | nein     | **Benutzerdefiniertes Zertifikatsprofil:** Geben Sie ein benutzerdefiniertes Zertifikatsprofil ein, wenn Ihr ACME-Server nicht standardmäßige Profile unterstützt. Dies überschreibt `LETS_ENCRYPT_PROFILE`, falls gesetzt.                                                                                                                                            |
| `LETS_ENCRYPT_MAX_RETRIES`                  | `3`       | multisite | nein     | **Maximale Wiederholungen:** Anzahl der Wiederholungsversuche bei der Zertifikatserstellung bei einem Fehler. Auf `0` setzen, um Wiederholungen zu deaktivieren. Nützlich bei temporären Netzwerkproblemen.                                                                                                                                                            |

!!! info "Informationen und Verhalten"
    - Die Einstellung `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` ist eine Mehrfacheinstellung und kann verwendet werden, um mehrere Elemente für den DNS-Anbieter festzulegen. Die Elemente werden als Cache-Datei gespeichert, und Certbot liest die Anmeldeinformationen daraus.
    - Wenn keine `LETS_ENCRYPT_DNS_PROPAGATION`-Einstellung angegeben ist, wird die Standard-Propagationszeit des Anbieters verwendet.
    - Die vollständige Let's Encrypt-Automatisierung mit der `http`-Challenge funktioniert im Stream-Modus, solange Sie den Port `80/tcp` von außen öffnen. Verwenden Sie die Einstellung `LISTEN_STREAM_PORT_SSL`, um Ihren SSL/TLS-Listening-Port zu wählen.
    - Wenn `LETS_ENCRYPT_PASSTHROUGH` auf `yes` gesetzt ist, behandelt BunkerWeb die ACME-Challenge-Anfragen nicht selbst, sondern leitet sie an den Backend-Webserver weiter. Dies ist nützlich in Szenarien, in denen BunkerWeb als Reverse-Proxy vor einem anderen Server fungiert, der für die Verarbeitung von Let's Encrypt-Challenges konfiguriert ist.

!!! tip "HTTP- vs. DNS-Challenges"
    **HTTP-Challenges** sind einfacher einzurichten und funktionieren für die meisten Websites gut:

    - Erfordert, dass Ihre Website öffentlich auf Port 80 erreichbar ist
    - Wird automatisch von BunkerWeb konfiguriert
    - Kann nicht für Wildcard-Zertifikate verwendet werden

    **DNS-Challenges** bieten mehr Flexibilität und sind für Wildcard-Zertifikate erforderlich:

    - Funktioniert auch, wenn Ihre Website nicht öffentlich erreichbar ist
    - Erfordert API-Anmeldeinformationen des DNS-Anbieters
    - Erforderlich für Wildcard-Zertifikate (z. B. *.example.com)
    - Nützlich, wenn Port 80 blockiert oder nicht verfügbar ist

!!! warning "Wildcard-Zertifikate"
    Wildcard-Zertifikate sind nur mit DNS-Challenges verfügbar. Wenn Sie sie verwenden möchten, müssen Sie die Einstellung `USE_LETS_ENCRYPT_WILDCARD` auf `yes` setzen und Ihre DNS-Anbieter-Anmeldeinformationen korrekt konfigurieren.

!!! warning "Ratenbegrenzungen"
    Let's Encrypt hat Ratenbegrenzungen für die Ausstellung von Zertifikaten. Verwenden Sie beim Testen von Konfigurationen die Staging-Umgebung, indem Sie `USE_LETS_ENCRYPT_STAGING` auf `yes` setzen, um zu vermeiden, dass Sie die Produktions-Ratenbegrenzungen erreichen. Staging-Zertifikate sind von Browsern nicht vertrauenswürdig, aber nützlich zur Validierung Ihrer Einrichtung.

### Unterstützte DNS-Anbieter

Das Let's Encrypt-Plugin unterstützt eine breite Palette von DNS-Anbietern für DNS-Challenges. Jeder Anbieter benötigt spezifische Anmeldeinformationen, die über die Einstellung `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` bereitgestellt werden müssen.

| Anbieter          | Beschreibung     | Obligatorische Einstellungen                                                                                 | Optionale Einstellungen                                                                                                                                                                                                                                                      | Dokumentation                                                                                         |
| ----------------- | ---------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `bunny`           | bunny.net        | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/mwt/certbot-dns-bunny/blob/main/README.rst)                        |
| `cloudflare`      | Cloudflare       | entweder `api_token`<br>oder `email` und `api_key`                                                           |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)                             |
| `desec`           | deSEC            | `token`                                                                                                      |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/desec-io/certbot-dns-desec/blob/main/README.md)                    |
| `digitalocean`    | DigitalOcean     | `token`                                                                                                      |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)                           |
| `domainoffensive` | Domain-Offensive | `api_token`                                                                                                  |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/domainoffensive/certbot-dns-domainoffensive/blob/master/README.md) |
| `domeneshop`      | Domeneshop       | `token`<br>`secret`                                                                                          |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/domeneshop/certbot-dns-domeneshop/blob/master/README.rst)          |
| `dnsimple`        | DNSimple         | `token`                                                                                                      |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)                               |
| `dnsmadeeasy`     | DNS Made Easy    | `api_key`<br>`secret_key`                                                                                    |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)                            |
| `duckdns`         | DuckDNS          | `duckdns_token`                                                                                              |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/infinityofspace/certbot_dns_duckdns/blob/main/Readme.md)           |
| `dynu`            | Dynu             | `auth_token`                                                                                                 |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/bikram990/certbot-dns-dynu/blob/main/README.md)                    |
| `gehirn`          | Gehirn DNS       | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                                 |
| `godaddy`         | GoDaddy          | `key`<br>`secret`                                                                                            | `ttl` (Standard: `600`)                                                                                                                                                                                                                                                      | [Dokumentation](https://github.com/miigotu/certbot-dns-godaddy/blob/main/README.md)                   |
| `google`          | Google Cloud     | `project_id`<br>`private_key_id`<br>`private_key`<br>`client_email`<br>`client_id`<br>`client_x509_cert_url` | `type` (Standard: `service_account`)<br>`auth_uri` (Standard: `https://accounts.google.com/o/oauth2/auth`)<br>`token_uri` (Standard: `https://accounts.google.com/o/oauth2/token`)<br>`auth_provider_x509_cert_url` (Standard: `https://www.googleapis.com/oauth2/v1/certs`) | [Dokumentation](https://certbot-dns-google.readthedocs.io/en/stable/)                                 |
| `infomaniak`      | Infomaniak       | `token`                                                                                                      |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/infomaniak/certbot-dns-infomaniak/blob/main/README.rst)            |
| `ionos`           | IONOS            | `prefix`<br>`secret`                                                                                         | `endpoint` (Standard: `https://api.hosting.ionos.com`)                                                                                                                                                                                                                       | [Dokumentation](https://github.com/helgeerbe/certbot-dns-ionos/blob/master/README.md)                 |
| `linode`          | Linode           | `key`                                                                                                        |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-linode.readthedocs.io/en/stable/)                                 |
| `luadns`          | LuaDNS           | `email`<br>`token`                                                                                           |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-luadns.readthedocs.io/en/stable/)                                 |
| `njalla`          | Njalla           | `token`                                                                                                      |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/chaptergy/certbot-dns-njalla/blob/main/README.md)                  |
| `nsone`           | NS1              | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-nsone.readthedocs.io/en/stable/)                                  |
| `ovh`             | OVH              | `application_key`<br>`application_secret`<br>`consumer_key`                                                  | `endpoint` (Standard: `ovh-eu`)                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-ovh.readthedocs.io/en/stable/)                                    |
| `pdns`            | PowerDNS         | `endpoint`<br>`api_key`<br>`server_id` (default: `localhost`)<br>`disable_notify` (default: `false`)         |                                                                                                                                                                                                                                                                              | [Documentation](https://github.com/kaechele/certbot-dns-pdns/blob/main/README.md)                     |
| `rfc2136`         | RFC 2136         | `server`<br>`name`<br>`secret`                                                                               | `port` (Standard: `53`)<br>`algorithm` (Standard: `HMAC-SHA512`)<br>`sign_query` (Standard: `false`)                                                                                                                                                                         | [Dokumentation](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                                |
| `route53`         | Amazon Route 53  | `access_key_id`<br>`secret_access_key`                                                                       |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-route53.readthedocs.io/en/stable/)                                |
| `sakuracloud`     | Sakura Cloud     | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)                            |
| `scaleway`        | Scaleway         | `application_token`                                                                                          |                                                                                                                                                                                                                                                                              | [Dokumentation](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst)                 |
| `transip`         | TransIP          | `key_file`<br>`username`                                                                                     |                                                                                                                                                                                                                                                                              | [Dokumentation](https://certbot-dns-transip.readthedocs.io/en/stable/)                                |

### Beispielkonfigurationen

=== "Grundlegende HTTP-Challenge"

    Einfache Konfiguration mit HTTP-Challenges für eine einzelne Domain:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ```

=== "Cloudflare DNS mit Wildcard"

    Konfiguration für Wildcard-Zertifikate mit Cloudflare DNS:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "api_token IHR_API_TOKEN"
    USE_LETS_ENCRYPT_WILDCARD: "yes"
    ```

=== "AWS Route53-Konfiguration"

    Konfiguration mit Amazon Route53 für DNS-Challenges:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "route53"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "aws_access_key_id IHR_ZUGRIFFSSCHLUESSEL"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "aws_secret_access_key IHR_GEHEIMSCHLUESSEL"
    ```

=== "Testen mit Staging-Umgebung und Wiederholungen"

    Konfiguration zum Testen der Einrichtung mit der Staging-Umgebung und erweiterten Wiederholungseinstellungen:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    USE_LETS_ENCRYPT_STAGING: "yes"
    LETS_ENCRYPT_MAX_RETRIES: "5"
    ```

=== "DigitalOcean mit benutzerdefinierter Propagationszeit"

    Konfiguration mit DigitalOcean DNS mit einer längeren Propagationswartezeit:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "digitalocean"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "token IHR_API_TOKEN"
    LETS_ENCRYPT_DNS_PROPAGATION: "120"
    ```

=== "Google Cloud DNS"

    Konfiguration mit Google Cloud DNS mit Anmeldeinformationen für ein Dienstkonto:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "google"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "project_id ihre-projekt-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "private_key_id ihre-private-key-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_3: "private_key ihr-private-key"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_4: "client_email ihre-dienstkonto-email"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_5: "client_id ihre-client-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_6: "client_x509_cert_url ihre-zertifikats-url"
    ```
