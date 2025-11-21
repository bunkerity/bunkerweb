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
2. **CA-Bundle bereitstellen:** Legen Sie Ihre vertrauenswürdigen Aussteller in einer PEM-Datei ab und verweisen Sie mit `MTLS_CA_CERTIFICATE` auf den absoluten Pfad.
3. **Verifizierungsmodus wählen:** Nutzen Sie `on` für verpflichtende Zertifikate, `optional` für fallback-fähige Szenarien oder `optional_no_ca` kurzfristig zur Diagnose.
4. **Kettentiefe anpassen:** Erhöhen oder verringern Sie `MTLS_VERIFY_DEPTH`, falls Ihre PKI mehrere Zwischenstellen nutzt.
5. **Ergebnisse weiterreichen (optional):** Belassen Sie `MTLS_FORWARD_CLIENT_HEADERS` auf `yes`, wenn nachgelagerte Anwendungen Zertifikatsinformationen benötigen.
6. **Revokationslisten pflegen:** Verknüpfen Sie `MTLS_CRL`, sobald Sie eine CRL publizieren, damit BunkerWeb widerrufene Zertifikate ablehnt.

### Konfigurationseinstellungen

| Einstellung                    | Standardwert | Kontext   | Mehrfach | Beschreibung                                                                                                                                                        |
| ----------------------------- | ------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                    | `no`          | multisite | nein     | **Mutual TLS verwenden:** Aktiviert die Client-Zertifikatsauthentifizierung für die aktuelle Site.                                                                   |
| `MTLS_CA_CERTIFICATE`         |               | multisite | nein     | **Client-CA-Bundle:** Absoluter Pfad zum vertrauenswürdigen Client-CA-Bundle (PEM). Erforderlich, wenn `MTLS_VERIFY_CLIENT` `on` oder `optional` ist; muss lesbar sein. |
| `MTLS_VERIFY_CLIENT`          | `on`          | multisite | nein     | **Verifizierungsmodus:** Legen Sie fest, ob Zertifikate erforderlich sind (`on`), optional (`optional`) oder ohne CA-Prüfung akzeptiert werden (`optional_no_ca`).   |
| `MTLS_VERIFY_DEPTH`           | `2`           | multisite | nein     | **Verifizierungstiefe:** Maximale akzeptierte Zertifikatskettentiefe für Client-Zertifikate.                                                                        |
| `MTLS_FORWARD_CLIENT_HEADERS` | `yes`         | multisite | nein     | **Client-Header weiterleiten:** Gibt Verifizierungsergebnisse (`X-SSL-Client-*`-Header mit Status, DN, Aussteller, Seriennummer, Fingerabdruck, Gültigkeit) weiter. |
| `MTLS_CRL`                    |               | multisite | nein     | **Client-CRL-Pfad:** Optionaler Pfad zu einer PEM-codierten Sperrliste. Wird nur angewendet, wenn das CA-Bundle erfolgreich geladen wurde.                          |

!!! tip "Zertifikate aktuell halten"
    Speichern Sie CA-Bundles und Sperrlisten in einem eingehängten Volume, das der Scheduler lesen kann, damit Neustarts die neuesten Vertrauensanker übernehmen.

!!! warning "CA-Bundle für strenge Modi obligatorisch"
    Sobald `MTLS_VERIFY_CLIENT` auf `on` oder `optional` steht, muss die CA-Datei zur Laufzeit vorhanden sein. Fehlt sie, ignoriert BunkerWeb die mTLS-Direktiven, um keinen Dienst mit ungültigem Pfad zu starten. Verwenden Sie `optional_no_ca` nur zur Fehlersuche – dieser Modus schwächt die Client-Authentifizierung.

!!! info "Vertrauensquelle und Verifizierung"
    BunkerWeb nutzt dasselbe CA-Bundle sowohl für die Client-Prüfung als auch für den Aufbau der Vertrauenskette, damit OCSP/CRL-Checks konsistent bleiben.

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
