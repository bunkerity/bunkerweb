Das Security.txt-Plugin implementiert den [Security.txt](https://securitytxt.org/)-Standard ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116)) für Ihre Website. Diese Funktion erleichtert Sicherheitsforschern den Zugriff auf Ihre Sicherheitsrichtlinien und bietet eine standardisierte Möglichkeit, Sicherheitslücken zu melden, die sie in Ihren Systemen entdecken.

**So funktioniert es:**

1.  Nach der Aktivierung erstellt BunkerWeb eine `/.well-known/security.txt`-Datei im Stammverzeichnis Ihrer Website.
2.  Diese Datei enthält Informationen zu Ihren Sicherheitsrichtlinien, Kontakten und anderen relevanten Details.
3.  Sicherheitsforscher und automatisierte Tools können diese Datei leicht am Standardort finden.
4.  Der Inhalt wird über einfache Einstellungen konfiguriert, mit denen Sie Kontaktinformationen, Verschlüsselungsschlüssel, Richtlinien und Danksagungen angeben können.
5.  BunkerWeb formatiert die Datei automatisch gemäß RFC 9116.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Security.txt-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Setzen Sie die Einstellung `USE_SECURITYTXT` auf `yes`, um die security.txt-Datei zu aktivieren.
2.  **Kontaktinformationen konfigurieren:** Geben Sie mindestens eine Kontaktmethode mit der Einstellung `SECURITYTXT_CONTACT` an.
3.  **Zusätzliche Informationen festlegen:** Konfigurieren Sie optionale Felder wie Ablaufdatum, Verschlüsselung, Danksagungen und Richtlinien-URLs.
4.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration erstellt und stellt BunkerWeb die security.txt-Datei automatisch am Standardort bereit.

### Konfigurationseinstellungen

| Einstellung                    | Standard                    | Kontext   | Mehrfach | Beschreibung                                                                                                                    |
| ------------------------------ | --------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `USE_SECURITYTXT`              | `no`                        | multisite | nein     | **Security.txt aktivieren:** Auf `yes` setzen, um die security.txt-Datei zu aktivieren.                                         |
| `SECURITYTXT_URI`              | `/.well-known/security.txt` | multisite | nein     | **Security.txt-URI:** Gibt die URI an, unter der die security.txt-Datei zugänglich sein wird.                                   |
| `SECURITYTXT_CONTACT`          |                             | multisite | ja       | **Kontaktinformationen:** Wie Sicherheitsforscher Sie kontaktieren können (z. B. `mailto:security@example.com`).                |
| `SECURITYTXT_EXPIRES`          |                             | multisite | nein     | **Ablaufdatum:** Wann diese security.txt-Datei als abgelaufen betrachtet werden soll (ISO 8601-Format).                         |
| `SECURITYTXT_ENCRYPTION`       |                             | multisite | ja       | **Verschlüsselung:** URL, die auf Verschlüsselungsschlüssel für die sichere Kommunikation verweist.                             |
| `SECURITYTXT_ACKNOWLEDGEMENTS` |                             | multisite | ja       | **Danksagungen:** URL, unter der Sicherheitsforscher für ihre Berichte anerkannt werden.                                        |
| `SECURITYTXT_POLICY`           |                             | multisite | ja       | **Sicherheitsrichtlinie:** URL, die auf die Sicherheitsrichtlinie verweist, die beschreibt, wie Schwachstellen gemeldet werden. |
| `SECURITYTXT_HIRING`           |                             | multisite | ja       | **Sicherheitsjobs:** URL, die auf sicherheitsrelevante Stellenangebote verweist.                                                |
| `SECURITYTXT_CANONICAL`        |                             | multisite | ja       | **Kanonische URL:** Die kanonische(n) URI(s) für diese security.txt-Datei.                                                      |
| `SECURITYTXT_PREFERRED_LANG`   | `en`                        | multisite | nein     | **Bevorzugte Sprache:** Die in der Kommunikation verwendete(n) Sprache(n). Angegeben als ISO 639-1-Sprachcode.                  |
| `SECURITYTXT_CSAF`             |                             | multisite | ja       | **CSAF:** Link zur provider-metadata.json Ihres Common Security Advisory Framework-Anbieters.                                   |

!!! warning "Ablaufdatum erforderlich"
    Gemäß RFC 9116 ist das Feld `Expires` erforderlich. Wenn Sie keinen Wert für `SECURITYTXT_EXPIRES` angeben, setzt BunkerWeb das Ablaufdatum automatisch auf ein Jahr ab dem aktuellen Datum.

!!! info "Kontaktinformationen sind unerlässlich"
    Das Feld `Contact` ist der wichtigste Teil der security.txt-Datei. Sie sollten mindestens eine Möglichkeit für Sicherheitsforscher angeben, Sie zu kontaktieren. Dies kann eine E-Mail-Adresse, ein Webformular, eine Telefonnummer oder eine andere Methode sein, die für Ihre Organisation funktioniert.

!!! warning "URLs müssen HTTPS verwenden"
    Gemäß RFC 9116 MÜSSEN alle URLs in der security.txt-Datei (außer `mailto:`- und `tel:`-Links) HTTPS verwenden. Nicht-HTTPS-URLs werden von BunkerWeb automatisch in HTTPS konvertiert, um die Einhaltung des Standards zu gewährleisten.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine minimale Konfiguration mit nur Kontaktinformationen:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    ```

=== "Umfassende Konfiguration"

    Eine vollständigere Konfiguration mit allen Feldern:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "https://example.com/security-contact-form"
    SECURITYTXT_EXPIRES: "2023-12-31T23:59:59+00:00"
    SECURITYTXT_ENCRYPTION: "https://example.com/pgp-key.txt"
    SECURITYTXT_ACKNOWLEDGEMENTS: "https://example.com/hall-of-fame"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_HIRING: "https://example.com/jobs/security"
    SECURITYTXT_CANONICAL: "https://example.com/.well-known/security.txt"
    SECURITYTXT_PREFERRED_LANG: "en"
    SECURITYTXT_CSAF: "https://example.com/provider-metadata.json"
    ```

=== "Konfiguration mit mehreren Kontakten"

    Konfiguration mit mehreren Kontaktmethoden:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "tel:+1-201-555-0123"
    SECURITYTXT_CONTACT_3: "https://example.com/security-form"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_EXPIRES: "2024-06-30T23:59:59+00:00"
    ```
