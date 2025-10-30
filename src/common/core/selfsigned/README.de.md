Das Plugin "Selbstsigniertes Zertifikat" generiert und verwaltet automatisch SSL/TLS-Zertifikate direkt in BunkerWeb, um HTTPS ohne externe Zertifizierungsstelle zu aktivieren. Ideal für die Entwicklung, interne Netzwerke oder schnelle HTTPS-Bereitstellungen.

So funktioniert's:

1.  Nach der Aktivierung generiert BunkerWeb ein selbstsigniertes Zertifikat für Ihre konfigurierten Domains.
2.  Das Zertifikat enthält alle definierten Servernamen, um eine korrekte Validierung zu gewährleisten.
3.  Die Zertifikate werden sicher gespeichert und verschlüsseln den gesamten HTTPS-Verkehr.
4.  Die Verlängerung erfolgt automatisch vor dem Ablaufdatum.

!!! warning "Browser-Warnungen"
    Browser zeigen Sicherheitswarnungen an, da ein selbstsigniertes Zertifikat nicht von einer vertrauenswürdigen CA ausgestellt wurde. Verwenden Sie in der Produktion vorzugsweise [Let's Encrypt](#lets-encrypt).

### Verwendung

1.  Aktivieren: `GENERATE_SELF_SIGNED_SSL: yes`.
2.  Algorithmus: Wählen Sie über `SELF_SIGNED_SSL_ALGORITHM`.
3.  Gültigkeit: Dauer in Tagen über `SELF_SIGNED_SSL_EXPIRY`.
4.  Betreff: Betrefffeld über `SELF_SIGNED_SSL_SUBJ`.

!!! tip "Stream-Modus"
    Im Stream-Modus konfigurieren Sie `LISTEN_STREAM_PORT_SSL`, um den SSL/TLS-Listening-Port zu definieren.

### Parameter

| Parameter                   | Standard               | Kontext   | Mehrfach | Beschreibung                                                          |
| :-------------------------- | :--------------------- | :-------- | :------- | :-------------------------------------------------------------------- |
| `GENERATE_SELF_SIGNED_SSL`  | `no`                   | Multisite | nein     | Aktiviert die automatische Generierung selbstsignierter Zertifikate.  |
| `SELF_SIGNED_SSL_ALGORITHM` | `ec-prime256v1`        | Multisite | nein     | Algorithmus: `ec-prime256v1`, `ec-secp384r1`, `rsa-2048`, `rsa-4096`. |
| `SELF_SIGNED_SSL_EXPIRY`    | `365`                  | Multisite | nein     | Gültigkeit (Tage).                                                    |
| `SELF_SIGNED_SSL_SUBJ`      | `/CN=www.example.com/` | Multisite | nein     | Betreff des Zertifikats (identifiziert die Domain).                   |

### Beispiele

=== "Standard"

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=mysite.local/"
    ```

=== "Kurzzeit-Zertifikate"

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "90"
    SELF_SIGNED_SSL_SUBJ: "/CN=dev.example.com/"
    ```

=== "Test in RSA"

    ```yaml
    SERVER_NAME: "test.example.com"
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "rsa-4096"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=test.example.com/"
    ```
