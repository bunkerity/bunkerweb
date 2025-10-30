Das SSL-Plugin bietet eine robuste SSL/TLS-Verschlüsselung für Ihre durch BunkerWeb geschützten Websites. Es ermöglicht sichere HTTPS-Verbindungen durch die Konfiguration von Protokollen, kryptografischen Suiten und zugehörigen Parametern.

So funktioniert's:

1.  Bei einer HTTPS-Verbindung verwaltet BunkerWeb die SSL/TLS-Aushandlung gemäß Ihren Einstellungen.
2.  Das Plugin erzwingt moderne Protokolle und starke Suiten und deaktiviert anfällige Optionen.
3.  Optimierte Sitzungsparameter verbessern die Leistung, ohne die Sicherheit zu beeinträchtigen.
4.  Die Präsentation der Zertifikate folgt Best Practices für Kompatibilität und Sicherheit.

### Verwendung

1.  **Protokolle**: Wählen Sie die Versionen über `SSL_PROTOCOLS`.
2.  **Suiten**: Wählen Sie ein Niveau über `SSL_CIPHERS_LEVEL` oder benutzerdefinierte Suiten über `SSL_CIPHERS_CUSTOM`.
3.  **Weiterleitungen**: Konfigurieren Sie die HTTP→HTTPS-Weiterleitung mit `AUTO_REDIRECT_HTTP_TO_HTTPS` und/oder `REDIRECT_HTTP_TO_HTTPS`.

### Parameter

| Parameter                     | Standard          | Kontext   | Mehrfach | Beschreibung                                                                    |
| :---------------------------- | :---------------- | :-------- | :------- | :------------------------------------------------------------------------------ |
| `REDIRECT_HTTP_TO_HTTPS`      | `no`              | Multisite | nein     | Leitet alle HTTP-Anfragen zu HTTPS um.                                          |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` | `yes`             | Multisite | nein     | Automatische Weiterleitung, wenn HTTPS erkannt wird.                            |
| `SSL_PROTOCOLS`               | `TLSv1.2 TLSv1.3` | Multisite | nein     | Unterstützte SSL/TLS-Protokolle (durch Leerzeichen getrennt).                   |
| `SSL_CIPHERS_LEVEL`           | `modern`          | Multisite | nein     | Sicherheitsniveau der Suiten (`modern`, `intermediate`, `old`).                 |
| `SSL_CIPHERS_CUSTOM`          |                   | Multisite | nein     | Benutzerdefinierte Suiten (durch `:` getrennte Liste), die das Niveau ersetzen. |

!!! tip "SSL Labs Test"
    Testen Sie Ihre Konfiguration über [Qualys SSL Labs](https://www.ssllabs.com/ssltest/). Eine gut eingestellte BunkerWeb-Konfiguration erreicht in der Regel A+.

!!! warning "Veraltete Protokolle"
    SSLv3, TLSv1.0 und TLSv1.1 sind standardmäßig deaktiviert (bekannte Schwachstellen). Aktivieren Sie diese nur bei Bedarf für ältere Clients.

### Beispiele

=== "Moderne Sicherheit (Standard)"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Maximale Sicherheit"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

=== "Legacy-Kompatibilität"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "old"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Benutzerdefinierte Suiten"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_CUSTOM: "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    ```
