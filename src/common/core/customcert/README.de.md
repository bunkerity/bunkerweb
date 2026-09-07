Das Plugin für benutzerdefinierte SSL-Zertifikate ermöglicht die Verwendung Ihrer eigenen SSL/TLS-Zertifikate mit BunkerWeb, anstelle der automatisch generierten. Dies ist nützlich, wenn Sie bereits Zertifikate von einer vertrauenswürdigen CA besitzen, spezifische Anforderungen haben oder die Zertifikatsverwaltung zentralisieren.

So funktioniert's:

1.  Sie stellen das Zertifikat und den privaten Schlüssel bereit (Dateipfade oder Daten in base64/PEM).
2.  BunkerWeb validiert das Format und die Verwendbarkeit der Dateien.
3.  Bei einer sicheren Verbindung stellt BunkerWeb Ihr benutzerdefiniertes Zertifikat bereit.
4.  Die Gültigkeit wird überwacht und Warnungen werden vor dem Ablauf ausgegeben.
5.  Sie behalten die volle Kontrolle über den Lebenszyklus der Zertifikate.

!!! info "Automatische Überwachung"
    Wenn Sie den Parameter `USE_CUSTOM_SSL` auf `yes` setzen, überwacht BunkerWeb das Zertifikat `CUSTOM_SSL_CERT`, erkennt Änderungen und lädt NGINX bei Bedarf neu.

### Verwendung

1.  Aktivieren: Setzen Sie den Parameter `USE_CUSTOM_SSL` auf `yes`.
2.  Methode: Dateien vs. Daten, Priorität über `CUSTOM_SSL_CERT_PRIORITY`.
3.  Dateien: Geben Sie die Pfade zum Zertifikat und zum privaten Schlüssel an.
4.  Daten: Geben Sie die base64- oder Klartext-PEM-Strings an.
5.  BunkerWeb den Rest erledigen lassen: Nach der Konfiguration werden Ihre benutzerdefinierten Zertifikate automatisch für HTTPS-Verbindungen verwendet.

!!! tip "Stream-Modus"
    Im Stream-Modus konfigurieren Sie `LISTEN_STREAM_PORT_SSL` für den SSL/TLS-Port.

### Parameter

| Parameter                  | Standard | Kontext   | Mehrfach | Beschreibung                                                    |
| :------------------------- | :------- | :-------- | :------- | :-------------------------------------------------------------- |
| `USE_CUSTOM_SSL`           | `no`     | multisite | nein     | Aktiviert die Verwendung eines benutzerdefinierten Zertifikats. |
| `CUSTOM_SSL_CERT_PRIORITY` | `file`   | multisite | nein     | Priorität der Quellen: `file` (Dateien) oder `data` (Daten).    |
| `CUSTOM_SSL_CERT`          |          | multisite | nein     | Vollständiger Pfad zum Zertifikat (oder Bundle).                |
| `CUSTOM_SSL_KEY`           |          | multisite | nein     | Vollständiger Pfad zum privaten Schlüssel.                      |
| `CUSTOM_SSL_CERT_DATA`     |          | multisite | nein     | Zertifikatsdaten (base64 oder Klartext-PEM).                    |
| `CUSTOM_SSL_KEY_DATA`      |          | multisite | nein     | Daten des privaten Schlüssels (base64 oder Klartext-PEM).       |

### Standardserver-Zertifikat

Der **Standardserver** ist der Block, der Anfragen ohne passenden konfigurierten Dienst beantwortet: eine unbekannte SNI, eine Verbindung zu einer rohen IP-Adresse, ein `Host`, den niemand bedient. Das einzige Zertifikat, das er bisher präsentieren konnte, war das interne, beim Start generierte selbstsignierte Zertifikat – weshalb ein Browser, der einen unbekannten Hostnamen auf Ihrer Instanz erreicht, eine Namensabweichungswarnung sieht.

Diese vier globalen Parameter ersetzen es. Leer lassen, um das interne Zertifikat zu behalten. Seine übrigen Einstellungen – TLS, Header, Fehlerseiten – werden am reservierten `default-server`-Dienst bearbeitet, siehe [Konfiguration des Standardservers](#miscellaneous).

| Parameter                      | Standard | Kontext | Mehrfach | Beschreibung                                                                                                                          |
| :------------------------------ | :------- | :------ | :------- | :-------------------------------------------------------------------------------------------------------------------------------------- |
| `DEFAULT_SERVER_SSL_CERT`      |          | global  | nein     | Vollständiger Pfad zum Zertifikat (oder Bundle), das für Anfragen ohne passenden Dienst bereitgestellt wird. Wird nur dort bereitgestellt, wo ein Standardserver-Block existiert: Multisite-Modus (`MULTISITE=yes`) oder `DISABLE_DEFAULT_SERVER=yes` im Single-Site-Modus. |
| `DEFAULT_SERVER_SSL_KEY`       |          | global  | nein     | Vollständiger Pfad zum passenden privaten Schlüssel.                                                                                  |
| `DEFAULT_SERVER_SSL_CERT_DATA` |          | global  | nein     | Dasselbe Zertifikat als base64 oder Klartext-PEM. Wird nur verwendet, wenn der Pfad-Parameter leer ist. Wird nur dort bereitgestellt, wo ein Standardserver-Block existiert: Multisite-Modus (`MULTISITE=yes`) oder `DISABLE_DEFAULT_SERVER=yes` im Single-Site-Modus. |
| `DEFAULT_SERVER_SSL_KEY_DATA`  |          | global  | nein     | Derselbe private Schlüssel als base64 oder Klartext-PEM. Wird nur verwendet, wenn der Pfad-Parameter leer ist.                        |

Die Überschreibung wird **zuletzt** konsultiert, und nur innerhalb des Standardservers: Ein Dienst, der sein eigenes Zertifikat auflöst – über das Zertifikatsinventar, `USE_CUSTOM_SSL`, Let's Encrypt oder den Self-Signed-Provider – behält dieses immer.

!!! warning "Ein Zertifikat, das einen Ihrer Dienste abdeckt, wird abgelehnt"
    Der Standardserver beantwortet *jeden* Hostnamen. Würde sein Zertifikat auch `www.example.com` abdecken, könnte ein Client eine Verbindung mit unbekannter SNI öffnen, dieses Zertifikat erhalten und dieselbe Verbindung dann für `Host: www.example.com` wiederverwenden – ein Zertifikat, das dieser Dienst nie autorisiert hat, nun für ihn nutzbar (HTTP/2-Connection-Coalescing). Der `custom-cert`-Job lehnt daher ein Zertifikat ab, dessen SANs oder Common Name einen Hostnamen eines konfigurierten Dienstes abdecken, Wildcards eingeschlossen, und protokolliert den Hostnamen, für den es abgelehnt wurde. Verwenden Sie ein Zertifikat, das keinen Hostnamen eines konfigurierten Dienstes abdeckt, oder binden Sie es stattdessen über `USE_CUSTOM_SSL` an den Dienst.

!!! info "Eine Ablehnung entfernt nie, was bereits bereitgestellt wird"
    Ungültiges Material, ein nicht zusammenpassendes Paar und ein abgedeckter Hostname lassen den Job jeweils laut fehlschlagen und belassen das zuvor bereitgestellte Zertifikat, statt den Standardserver auf nichts zu setzen. Der Ablauf löst aus demselben Grund nur eine Warnung aus. Das Leeren beider Parameter entfernt die Überschreibung und bringt das interne Zertifikat zurück.

!!! tip "Wirkungslos bei striktem SNI"
    Ist `DISABLE_DEFAULT_SERVER_STRICT_SNI` auf `yes` gesetzt, wird eine unbekannte SNI bereits während des TLS-Handshakes geschlossen, bevor ein Zertifikat gewählt wird – die Überschreibung wird also nie erreicht. Lassen Sie es deaktiviert, wenn unbekannte Hostnamen mit Ihrem eigenen Zertifikat beantwortet werden sollen.

!!! warning "Sicherheit"
    Schützen Sie den privaten Schlüssel (angemessene Berechtigungen, nur vom BunkerWeb-Scheduler lesbar).

!!! tip "Format"
    Zertifikate müssen im PEM-Format vorliegen. Konvertieren Sie bei Bedarf.

!!! info "Zertifikatsketten"
    Wenn eine Zwischenkette erforderlich ist, stellen Sie das vollständige Bundle in der richtigen Reihenfolge bereit (Zertifikat, dann Zwischenzertifikate).

### Beispiele

=== "Dateien"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    ```

=== "Base64-Daten"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR..."
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV..."
    ```

=== "Klartext-PEM"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: |
    -----BEGIN CERTIFICATE-----
    MIIDdzCCAl+gAwIBAgIUJH...certificate content...AAAA
    -----END CERTIFICATE-----
    CUSTOM_SSL_KEY_DATA: |
    -----BEGIN PRIVATE KEY-----
    MIIEvQIBADAN...key content...AAAA
    -----END PRIVATE KEY-----
    ```

=== "Fallback"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR..."
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV..."
    ```
