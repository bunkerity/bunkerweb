Das Plugin für benutzerdefinierte SSL-Zertifikate ermöglicht die Verwendung Ihrer eigenen SSL/TLS-Zertifikate mit BunkerWeb, anstelle der automatisch generierten. Dies ist nützlich, wenn Sie bereits Zertifikate von einer vertrauenswürdigen CA besitzen, spezifische Anforderungen haben oder die Zertifikatsverwaltung zentralisieren.

So funktioniert's:

1.  Sie stellen das Zertifikat und den privaten Schlüssel bereit (Dateipfade oder Daten in base64/PEM).
2.  BunkerWeb validiert das Format und die Verwendbarkeit der Dateien.
3.  Bei einer sicheren Verbindung stellt BunkerWeb Ihr benutzerdefiniertes Zertifikat bereit.
4.  Die Gültigkeit wird überwacht und Warnungen werden vor dem Ablauf ausgegeben.
5.  Sie behalten die volle Kontrolle über den Lebenszyklus der Zertifikate.

!!! info "Automatische Überwachung"
Mit `USE_CUSTOM_SSL: yes` überwacht BunkerWeb das Zertifikat `CUSTOM_SSL_CERT`, erkennt Änderungen und lädt NGINX bei Bedarf neu.

### Verwendung

1.  Aktivieren: `USE_CUSTOM_SSL: yes`.
2.  Methode: Dateien vs. Daten, Priorität über `CUSTOM_SSL_CERT_PRIORITY`.
3.  Dateien: Geben Sie die Pfade zum Zertifikat und zum privaten Schlüssel an.
4.  Daten: Geben Sie die base64- oder Klartext-PEM-Strings an.

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
