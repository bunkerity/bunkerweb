Das Greylist-Plugin bietet einen flexiblen Sicherheitsansatz, der Besuchern den Zugriff ermöglicht, während wesentliche Sicherheitsfunktionen weiterhin aktiv bleiben.

Im Gegensatz zu traditionellen [Blacklist](#blacklist)/[Whitelist](#whitelist)-Ansätzen, die den Zugriff vollständig blockieren oder erlauben, schafft die Greylist einen Mittelweg, indem sie bestimmten Besuchern den Zugriff gewährt, sie aber dennoch Sicherheitsprüfungen unterzieht.

**So funktioniert es:**

1.  Sie definieren Kriterien für Besucher, die auf die Greylist gesetzt werden sollen (_IP-Adressen, Netzwerke, rDNS, ASN, User-Agent oder URI-Muster_).
2.  Wenn ein Besucher einem dieser Kriterien entspricht, erhält er Zugriff auf Ihre Website, während die anderen Sicherheitsfunktionen aktiv bleiben.
3.  Wenn ein Besucher keinem Greylist-Kriterium entspricht, wird sein Zugriff verweigert.
4.  Greylist-Daten können in regelmäßigen Abständen automatisch aus externen Quellen aktualisiert werden.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Greylist-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die Greylist-Funktion ist standardmäßig deaktiviert. Setzen Sie die Einstellung `USE_GREYLIST` auf `yes`, um sie zu aktivieren.
2.  **Greylist-Regeln konfigurieren:** Definieren Sie, welche IPs, Netzwerke, rDNS-Muster, ASNs, User-Agents oder URIs auf die Greylist gesetzt werden sollen.
3.  **Externe Quellen hinzufügen:** Konfigurieren Sie optional URLs zum automatischen Herunterladen und Aktualisieren von Greylist-Daten.
4.  **Zugriff überwachen:** Überprüfen Sie die [Web-Benutzeroberfläche](web-ui.md), um zu sehen, welchen Besuchern der Zugriff gewährt oder verweigert wird.

!!! tip "Verhalten der Zugriffskontrolle"
    Wenn die Greylist-Funktion aktiviert ist, indem die Einstellung `USE_GREYLIST` auf `yes` gesetzt wird:

    1. **Greylist-Besucher:** Erhalten Zugriff, unterliegen aber weiterhin allen Sicherheitsprüfungen.
    2. **Nicht-Greylist-Besucher:** Wird der Zugriff vollständig verweigert.

!!! info "Stream-Modus"
    Im Stream-Modus werden nur IP-, rDNS- und ASN-Prüfungen durchgeführt.

### Konfigurationseinstellungen

**Allgemein**

| Einstellung    | Standard | Kontext   | Mehrfach | Beschreibung                                                             |
| -------------- | -------- | --------- | -------- | ------------------------------------------------------------------------ |
| `USE_GREYLIST` | `no`     | multisite | nein     | **Greylist aktivieren:** Auf `yes` setzen, um Greylisting zu aktivieren. |

=== "IP-Adresse"
    **Was dies bewirkt:** Setzt Besucher basierend auf ihrer IP-Adresse oder ihrem Netzwerk auf die Greylist. Diese Besucher erhalten Zugriff, unterliegen aber weiterhin den Sicherheitsprüfungen.

    | Einstellung        | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                            |
    | ------------------ | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_IP`      |          | multisite | nein     | **IP-Greylist:** Liste von IP-Adressen oder Netzwerken (in CIDR-Notation), die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen.      |
    | `GREYLIST_IP_URLS` |          | multisite | nein     | **IP-Greylist-URLs:** Liste von URLs, die IP-Adressen oder Netzwerke enthalten, die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen. |

=== "Reverse DNS"
    **Was dies bewirkt:** Setzt Besucher basierend auf ihrem Domainnamen (in umgekehrter Reihenfolge) auf die Greylist. Nützlich, um Besuchern von bestimmten Organisationen oder Netzwerken bedingten Zugriff zu gewähren.

    | Einstellung            | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                       |
    | ---------------------- | -------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_RDNS`        |          | multisite | nein     | **rDNS-Greylist:** Liste von Reverse-DNS-Suffixen, die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen.                         |
    | `GREYLIST_RDNS_GLOBAL` | `yes`    | multisite | nein     | **Nur globales rDNS:** Führt rDNS-Greylist-Prüfungen nur für globale IP-Adressen durch, wenn auf `yes` gesetzt.                                    |
    | `GREYLIST_RDNS_URLS`   |          | multisite | nein     | **rDNS-Greylist-URLs:** Liste von URLs, die Reverse-DNS-Suffixe enthalten, die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen. |

=== "ASN"
    **Was dies bewirkt:** Setzt Besucher von bestimmten Netzwerkanbietern mithilfe von Autonomen Systemnummern auf die Greylist. ASNs identifizieren, zu welchem Anbieter oder welcher Organisation eine IP gehört.

    | Einstellung         | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                       |
    | ------------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_ASN`      |          | multisite | nein     | **ASN-Greylist:** Liste von Autonomen Systemnummern, die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen.       |
    | `GREYLIST_ASN_URLS` |          | multisite | nein     | **ASN-Greylist-URLs:** Liste von URLs, die ASNs enthalten, die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen. |

=== "User-Agent"
    **Was dies bewirkt:** Setzt Besucher basierend auf dem Browser oder Tool, das sie angeben zu verwenden, auf die Greylist. Dies ermöglicht kontrollierten Zugriff für bestimmte Tools, während die Sicherheitsprüfungen aufrechterhalten werden.

    | Einstellung                | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                |
    | -------------------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_USER_AGENT`      |          | multisite | nein     | **User-Agent-Greylist:** Liste von User-Agent-Mustern (PCRE-Regex), die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen. |
    | `GREYLIST_USER_AGENT_URLS` |          | multisite | nein     | **User-Agent-Greylist-URLs:** Liste von URLs, die User-Agent-Muster enthalten, die auf die Greylist gesetzt werden sollen.                  |

=== "URI"
    **Was dies bewirkt:** Setzt Anfragen an bestimmte URLs auf Ihrer Website auf die Greylist. Dies ermöglicht bedingten Zugriff auf bestimmte Endpunkte, während die Sicherheitsprüfungen aufrechterhalten werden.

    | Einstellung         | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                             |
    | ------------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_URI`      |          | multisite | nein     | **URI-Greylist:** Liste von URI-Mustern (PCRE-Regex), die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen.            |
    | `GREYLIST_URI_URLS` |          | multisite | nein     | **URI-Greylist-URLs:** Liste von URLs, die URI-Muster enthalten, die auf die Greylist gesetzt werden sollen, getrennt durch Leerzeichen. |

!!! info "Unterstützung von URL-Formaten"
    Alle `*_URLS`-Einstellungen unterstützen HTTP/HTTPS-URLs sowie lokale Dateipfade mit dem Präfix `file:///`. Die Basisauthentifizierung wird im Format `http://user:pass@url` unterstützt.

!!! tip "Regelmäßige Aktualisierungen"
    Greylists von URLs werden stündlich automatisch heruntergeladen und aktualisiert, um sicherzustellen, dass Ihr Schutz mit den neuesten vertrauenswürdigen Quellen auf dem neuesten Stand bleibt.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine einfache Konfiguration, die Greylisting auf das interne Netzwerk eines Unternehmens und einen Crawler anwendet:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP: "192.168.1.0/24 10.0.0.0/8"
    GREYLIST_USER_AGENT: "(?:\b)CompanyCrawler(?:\b)"
    ```

=== "Erweiterte Konfiguration"

    Eine umfassendere Konfiguration mit mehreren Greylist-Kriterien:

    ```yaml
    USE_GREYLIST: "yes"

    # Unternehmensressourcen und genehmigte Crawler
    GREYLIST_IP: "192.168.1.0/24 203.0.113.0/24"
    GREYLIST_RDNS: ".company.com .partner-company.org"
    GREYLIST_ASN: "12345 67890"  # ASNs von Unternehmen und Partnern
    GREYLIST_USER_AGENT: "(?:\b)GoodBot(?:\b) (?:\b)PartnerCrawler(?:\b)"
    GREYLIST_URI: "^/api/v1/"

    # Externe vertrauenswürdige Quellen
    GREYLIST_IP_URLS: "https://example.com/trusted-networks.txt"
    GREYLIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Verwendung lokaler Dateien"

    Konfiguration mit lokalen Dateien für Greylists:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP_URLS: "file:///path/to/ip-greylist.txt"
    GREYLIST_RDNS_URLS: "file:///path/to/rdns-greylist.txt"
    GREYLIST_ASN_URLS: "file:///path/to/asn-greylist.txt"
    GREYLIST_USER_AGENT_URLS: "file:///path/to/user-agent-greylist.txt"
    GREYLIST_URI_URLS: "file:///path/to/uri-greylist.txt"
    ```

=== "Selektiver API-Zugriff"

    Eine Konfiguration, die den Zugriff auf bestimmte API-Endpunkte erlaubt:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_URI: "^/api/v1/public/ ^/api/v1/status"
    GREYLIST_IP: "203.0.113.0/24"  # Externes Partnernetzwerk
    ```

### Arbeiten mit lokalen Listendateien

Die `*_URLS`-Einstellungen der Whitelist-, Greylist- und Blacklist-Plugins verwenden denselben Downloader. Wenn Sie eine `file:///`-URL angeben:

- Der Pfad wird innerhalb des **Scheduler**-Containers aufgelöst (bei Docker-Bereitstellungen in der Regel `bunkerweb-scheduler`). Binden Sie die Dateien dort ein und stellen Sie sicher, dass der Scheduler-Benutzer Lesezugriff hat.
- Jede Datei ist eine UTF-8-codierte Textdatei mit einem Eintrag pro Zeile. Leere Zeilen werden ignoriert und Kommentarzeilen müssen mit `#` oder `;` beginnen. `//`-Kommentare werden nicht unterstützt.
- Erwartete Werte je Listentyp:
  - **IP-Listen** akzeptieren IPv4/IPv6-Adressen oder CIDR-Netzwerke (z. B. `192.0.2.10` oder `2001:db8::/48`).
  - **rDNS-Listen** erwarten ein Suffix ohne Leerzeichen (z. B. `.search.msn.com`). Werte werden automatisch in Kleinbuchstaben umgewandelt.
  - **ASN-Listen** können nur die Nummer (`32934`) oder die mit `AS` vorangestellte Nummer (`AS15169`) enthalten.
  - **User-Agent-Listen** werden als PCRE-Muster behandelt und die vollständige Zeile bleibt erhalten (einschließlich Leerzeichen). Schreiben Sie Kommentare in eine eigene Zeile, damit sie nicht als Muster interpretiert werden.
  - **URI-Listen** müssen mit `/` beginnen und dürfen PCRE-Tokens wie `^` oder `$` verwenden.

Beispieldateien im erwarteten Format:

```text
# /etc/bunkerweb/lists/ip-greylist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-greylist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
