Das Mutual-TLS-Plugin (mTLS) schützt sensible Anwendungen, indem nur Clients mit Zertifikaten akzeptiert werden, die von Ihren vertrauenswürdigen Zertifizierungsstellen ausgestellt wurden. Mit aktivem Plugin authentifiziert BunkerWeb jede Anfrage bereits an der Perimeter-Grenze und hält interne Tools sowie Partner-Integrationen abgeschirmt.

BunkerWeb bewertet jeden TLS-Handshake anhand des von Ihnen bereitgestellten CA-Bundles und Ihrer Richtlinien. Clients, die diese Vorgaben nicht erfüllen, werden abgeblockt, während konforme Verbindungen ihre Zertifikatsdetails an nachgelagerte Anwendungen weitergeben können.

**Funktionsweise:**

1. Das Plugin überwacht die HTTPS-Handshakes der ausgewählten Site.
2. Während des TLS-Austauschs prüft BunkerWeb das Client-Zertifikat und vergleicht die Kette mit Ihrem Vertrauensspeicher.
3. Der gewählte Verifizierungsmodus entscheidet, ob nicht authentifizierte Clients abgewiesen, toleriert oder zu Diagnosezwecken zugelassen werden.
4. (Optional) BunkerWeb stellt die Ergebnisse über `X-SSL-Client-*`-Header bereit, damit Ihre Anwendungen eigene Autorisierungsregeln anwenden können.

!!! success "Wesentliche Vorteile"

      1. **Starker Perimeterschutz:** Nur authentifizierte Maschinen und Benutzer erreichen Ihre sensiblen Routen.
      2. **Flexible Vertrauensrichtlinien:** Kombinieren Sie strikte und optionale Modi passend zu Ihrem Onboarding.
      3. **Transparenz für Anwendungen:** Geben Sie Fingerabdrücke und Identitäten an Downstream-Services weiter.
      4. **Geschichtete Sicherheit:** Ergänzen Sie mTLS mit weiteren BunkerWeb-Plugins wie Rate Limiting oder IP-Filterung.

### Schritt-für-Schritt

Gehen Sie diese Schritte durch, um Mutual TLS kontrolliert einzuführen:

1. **Funktion aktivieren:** Setzen Sie `USE_MTLS` auf `yes` für die Site, die Zertifikatsauthentifizierung benötigt.
2. **CA-Bundle bereitstellen:** Verweisen Sie mit `MTLS_CA_CERTIFICATE` auf eine PEM-Datei, die für den Scheduler lesbar ist, oder übergeben Sie das Bundle direkt als base64/PEM-Daten mit `MTLS_CA_CERTIFICATE_DATA`. Der Scheduler validiert, cached und verteilt das Bundle an jede Instanz, sodass keine Einbindung pro Instanz nötig ist.
3. **Verifizierungsmodus wählen:** Nutzen Sie `on` für verpflichtende Zertifikate, `optional` für fallback-fähige Szenarien oder `optional_no_ca` kurzfristig zur Diagnose.
4. **Kettentiefe anpassen:** Erhöhen oder verringern Sie `MTLS_VERIFY_DEPTH`, falls Ihre PKI mehrere Zwischenstellen nutzt.
5. **Ergebnisse weiterreichen (optional):** Belassen Sie `MTLS_FORWARD_CLIENT_HEADERS` auf `yes`, wenn nachgelagerte Anwendungen Zertifikatsinformationen benötigen.
6. **Revokationslisten pflegen:** Setzen Sie `MTLS_CRL` (oder `MTLS_CRL_DATA`), sobald Sie eine CRL publizieren, damit BunkerWeb widerrufene Zertifikate ablehnt.

### Konfigurationseinstellungen

| Einstellung                     | Standardwert | Kontext   | Mehrfach | Beschreibung                                                                                                                                                        |
| -------------------------------- | ------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                      | `no`          | multisite | nein     | **Mutual TLS verwenden:** Aktiviert die Client-Zertifikatsauthentifizierung für die aktuelle Site.                                                                   |
| `MTLS_CA_CERTIFICATE_PRIORITY`  | `file`        | multisite | nein     | **Priorität des Client-CA-Bundles:** Quelle des Client-CA-Bundles: `file` (Pfad) oder `data` (base64/PEM).                                                          |
| `MTLS_CA_CERTIFICATE`           |               | multisite | nein     | **Client-CA-Bundle-Pfad:** Pfad zum vertrauenswürdigen Client-CA-Bundle (PEM), lesbar für den Scheduler. Erforderlich, wenn `MTLS_VERIFY_CLIENT` `on` oder `optional` ist. |
| `MTLS_CA_CERTIFICATE_DATA`      |               | multisite | nein     | **Client-CA-Bundle-Daten:** Vertrauenswürdiges Client-CA-Bundle direkt als base64 oder PEM (z. B. über die Web-UI).                                                 |
| `MTLS_VERIFY_CLIENT`            | `on`          | multisite | nein     | **Verifizierungsmodus:** Legen Sie fest, ob Zertifikate erforderlich sind (`on`), optional (`optional`) oder ohne CA-Prüfung akzeptiert werden (`optional_no_ca`).   |
| `MTLS_URL`                      |               | multisite | ja       | **mTLS-URL:** Regex, der gegen die Anfrage-URI geprüft wird, um nur auf passenden Pfaden ein gültiges Client-Zertifikat zu verlangen (nur HTTP). Erfordert `MTLS_VERIFY_CLIENT` auf `optional` oder `optional_no_ca`. Leer lassen, um mTLS für die gesamte Site zu erzwingen. |
| `MTLS_VERIFY_DEPTH`             | `2`           | multisite | nein     | **Verifizierungstiefe:** Maximale akzeptierte Zertifikatskettentiefe für Client-Zertifikate.                                                                        |
| `MTLS_FORWARD_CLIENT_HEADERS`   | `yes`         | multisite | nein     | **Client-Header weiterleiten:** Gibt Verifizierungsergebnisse (`X-SSL-Client-*`-Header mit Status, DN, Aussteller, Seriennummer, Fingerabdruck, Gültigkeit) weiter. |
| `MTLS_CRL_PRIORITY`             | `file`        | multisite | nein     | **Priorität der Client-CRL:** Quelle der CRL: `file` (Pfad) oder `data` (base64/PEM).                                                                                |
| `MTLS_CRL`                      |               | multisite | nein     | **Client-CRL-Pfad:** Optionaler Pfad zu einer PEM-codierten Sperrliste, lesbar für den Scheduler. Wird nur angewendet, wenn das CA-Bundle erfolgreich geladen wurde. NGINX benötigt in der CRL-Datei eine Sperrliste für jede CA in der Verifizierungskette. |
| `MTLS_CRL_DATA`                 |               | multisite | nein     | **Client-CRL-Daten:** Sperrliste direkt als base64 oder PEM.                                                                                                        |

!!! tip "Einmal konfigurieren, überall verteilt"
    CA-Bundles und Sperrlisten müssen nicht in die BunkerWeb-Container eingehängt werden. Stellen Sie sie nur dem Scheduler bereit, als Dateipfad oder als Inline-Daten; der Scheduler validiert sie, cached sie und verteilt sie an jede Instanz. Aktualisierungen werden beim nächsten Job-Lauf automatisch übernommen und neu verteilt.

!!! warning "CA-Bundle für strenge Modi obligatorisch"
    Sobald `MTLS_VERIFY_CLIENT` auf `on` oder `optional` steht, muss der Scheduler ein Client-CA-Bundle validieren und cachen können. Ist keines verfügbar, überspringt BunkerWeb die mTLS-Direktiven auf jeder Instanz, damit der Dienst nicht mit einer ungültigen oder fehlenden Zertifikatsreferenz läuft. Verwenden Sie `optional_no_ca` nur zur Fehlersuche – dieser Modus schwächt die Client-Authentifizierung. Nach einem Neustart des Schedulers mit einem nicht persistenten `/var/cache/bunkerweb` bleibt mTLS deaktiviert, bis der erste Job-Lauf abgeschlossen ist und das CA-Bundle neu verteilt hat; verwenden Sie deshalb ein persistentes Cache-Volume, wenn eine strikte Durchsetzung erforderlich ist.

!!! info "Vertrauensquelle und Verifizierung"
    BunkerWeb nutzt dasselbe CA-Bundle sowohl für die Client-Prüfung als auch für den Aufbau der Vertrauenskette, damit OCSP/CRL-Checks konsistent bleiben.

!!! warning "Pfadbezogenes mTLS erfordert den optionalen Modus"
    Die NGINX-Direktive `ssl_verify_client` ist nur im `server`-Kontext gültig – sie kann nicht in einem `location`-Block stehen. Um ein Zertifikat nur auf bestimmten Pfaden zu verlangen, setzen Sie `MTLS_VERIFY_CLIENT` auf `optional` (oder `optional_no_ca`), damit der Handshake für jeden Pfad abgeschlossen wird, und listen Sie die geschützten Pfade in `MTLS_URL_n` auf. BunkerWeb erzwingt das Zertifikat dann pro Anfrage in Lua auf den passenden URLs. Belassen Sie `MTLS_VERIFY_CLIENT` auf `on`, während Sie `MTLS_URL_n` setzen, weist NGINX Clients ohne Zertifikat bereits beim Handshake ab, bevor die pfadbezogene Logik greift – die Erzwingung bleibt dann site-weit.

!!! info "Browser-Zertifikatsabfragen im optionalen Modus"
    Der TLS-Handshake erfolgt, bevor NGINX die angeforderte URL kennt; im Modus `optional` sendet NGINX daher weiterhin bei jeder Verbindung einen `CertificateRequest`. Die Erzwingung wird pfadbezogen, die Einladung auf Handshake-Ebene jedoch nicht – Browser fragen unter Umständen auch auf ungeschützten Pfaden nach einem Zertifikat (Verhalten je nach Browser unterschiedlich). Auf diesen Pfaden lässt BunkerWeb die Anfrage zu, ob ein Zertifikat vorgelegt wird oder nicht.

### Konfigurationsbeispiele

=== "Strikte Zugriffskontrolle"

    Verlangen Sie gültige Client-Zertifikate Ihrer privaten CA und leiten Sie die Verifizierungsergebnisse an das Backend weiter:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Optionale Client-Authentifizierung"

    Erlauben Sie anonyme Nutzer, übermitteln Sie aber Zertifikatsdetails, sobald ein Client eines präsentiert:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Diagnose ohne CA"

    Lassen Sie Verbindungen auch dann zu, wenn ein Zertifikat nicht zu einem vertrauenswürdigen CA-Bundle verknüpft werden kann. Nur für Fehlersuche geeignet:

    ```yaml
    USE_MTLS: "yes"
    MTLS_VERIFY_CLIENT: "optional_no_ca"
    MTLS_FORWARD_CLIENT_HEADERS: "no"
    ```

=== "Pfadbezogenes mTLS (z. B. nur `/login`)"

    Verlangen Sie Client-Zertifikate nur auf ausgewählten Pfaden und lassen Sie den Rest der Site offen. Die Verifizierung läuft im Modus `optional`, damit der Handshake auf nicht authentifizierten Pfaden abgeschlossen wird; BunkerWeb erzwingt das Zertifikat anschließend pro Anfrage auf URLs, die zu `MTLS_URL_n` passen (eine Regex pro Eintrag):

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_URL_1: "^/login"
    MTLS_URL_2: "^/admin"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

    | Anfrage          | Zertifikat            | Ergebnis                                 |
    | ---------------- | --------------------- | ---------------------------------------- |
    | `GET /`          | keines                | Erlaubt (Pfad ohne mTLS)                 |
    | `GET /login`     | keines                | Abgelehnt (`403`)                        |
    | `GET /login`     | gültig                | Erlaubt, `X-SSL-Client-*` weitergeleitet |
    | `GET /login`     | ungültig / abgelaufen | Abgelehnt (`403`)                        |
