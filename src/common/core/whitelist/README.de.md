Das Whitelist-Plugin ermöglicht es Ihnen, eine Liste vertrauenswürdiger IP-Adressen zu definieren, die andere Sicherheitsfilter umgehen.
Um stattdessen unerwünschte Clients zu blockieren, lesen Sie das [Blacklist-Plugin](#blacklist).

Das Whitelist-Plugin bietet einen umfassenden Ansatz, um den Zugriff auf Ihre Website basierend auf verschiedenen Client-Attributen explizit zu erlauben. Diese Funktion bietet einen Sicherheitsmechanismus: Besuchern, die bestimmte Kriterien erfüllen, wird sofortiger Zugriff gewährt, während alle anderen reguläre Sicherheitsprüfungen durchlaufen müssen.

**So funktioniert es:**

1.  Sie definieren Kriterien für Besucher, die auf die "Whitelist" gesetzt werden sollen (_IP-Adressen, Netzwerke, rDNS, ASN, User-Agent oder URI-Muster_).
2.  Wenn ein Besucher versucht, auf Ihre Website zuzugreifen, prüft BunkerWeb, ob er einem dieser Whitelist-Kriterien entspricht.
3.  Wenn ein Besucher einer Whitelist-Regel entspricht (und keiner Ignorier-Regel), wird ihm der Zugriff auf Ihre Website gewährt und er **umgeht alle anderen Sicherheitsprüfungen**.
4.  Wenn ein Besucher keinem Whitelist-Kriterium entspricht, durchläuft er wie gewohnt alle normalen Sicherheitsprüfungen.
5.  Whitelists können in regelmäßigen Abständen automatisch aus externen Quellen aktualisiert werden.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Whitelist-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die Whitelist-Funktion ist standardmäßig deaktiviert. Setzen Sie die Einstellung `USE_WHITELIST` auf `yes`, um sie zu aktivieren.
2.  **Erlaubnisregeln konfigurieren:** Definieren Sie, welche IPs, Netzwerke, rDNS-Muster, ASNs, User-Agents oder URIs auf die Whitelist gesetzt werden sollen.
3.  **Ignorierregeln einrichten:** Geben Sie alle Ausnahmen an, die die Whitelist-Prüfungen umgehen sollen.
4.  **Externe Quellen hinzufügen:** Konfigurieren Sie URLs zum automatischen Herunterladen und Aktualisieren von Whitelist-Daten.
5.  **Zugriff überwachen:** Überprüfen Sie die [Web-Benutzeroberfläche](web-ui.md), um zu sehen, welchen Besuchern der Zugriff gewährt oder verweigert wird.

!!! info "Stream-Modus"
    Im Stream-Modus werden nur IP-, rDNS- und ASN-Prüfungen durchgeführt.

### Konfigurationseinstellungen

**Allgemein**

| Einstellung     | Standard | Kontext   | Mehrfach | Beschreibung                                                                         |
| --------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------ |
| `USE_WHITELIST` | `no`     | multisite | nein     | **Whitelist aktivieren:** Auf `yes` setzen, um die Whitelist-Funktion zu aktivieren. |

=== "IP-Adresse"
    **Was dies bewirkt:** Setzt Besucher basierend auf ihrer IP-Adresse oder ihrem Netzwerk auf die Whitelist. Diese Besucher umgehen alle Sicherheitsprüfungen.

    | Einstellung                | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                              |
    | -------------------------- | -------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_IP`             |          | multisite | nein     | **IP-Whitelist:** Liste von IP-Adressen oder Netzwerken (CIDR-Notation), die erlaubt werden sollen, getrennt durch Leerzeichen.                           |
    | `WHITELIST_IGNORE_IP`      |          | multisite | nein     | **IP-Ignorierliste:** Liste von IP-Adressen oder Netzwerken, die IP-Whitelist-Prüfungen umgehen sollen.                                                   |
    | `WHITELIST_IP_URLS`        |          | multisite | nein     | **IP-Whitelist-URLs:** Liste von URLs, die IP-Adressen oder Netzwerke enthalten, die auf die Whitelist gesetzt werden sollen, getrennt durch Leerzeichen. |
    | `WHITELIST_IGNORE_IP_URLS` |          | multisite | nein     | **IP-Ignorierlisten-URLs:** Liste von URLs, die IP-Adressen oder Netzwerke enthalten, die ignoriert werden sollen.                                        |

=== "Reverse DNS"
    **Was dies bewirkt:** Setzt Besucher basierend auf ihrem Domainnamen (in umgekehrter Reihenfolge) auf die Whitelist. Dies ist nützlich, um Besuchern von bestimmten Organisationen oder Netzwerken den Zugriff nach ihrer Domain zu ermöglichen.

    | Einstellung                  | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                         |
    | ---------------------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_RDNS`             |          | multisite | nein     | **rDNS-Whitelist:** Liste von Reverse-DNS-Suffixen, die erlaubt werden sollen, getrennt durch Leerzeichen.                                           |
    | `WHITELIST_RDNS_GLOBAL`      | `yes`    | multisite | nein     | **Nur globales rDNS:** Führt rDNS-Whitelist-Prüfungen nur für globale IP-Adressen durch, wenn auf `yes` gesetzt.                                     |
    | `WHITELIST_IGNORE_RDNS`      |          | multisite | nein     | **rDNS-Ignorierliste:** Liste von Reverse-DNS-Suffixen, die rDNS-Whitelist-Prüfungen umgehen sollen.                                                 |
    | `WHITELIST_RDNS_URLS`        |          | multisite | nein     | **rDNS-Whitelist-URLs:** Liste von URLs, die Reverse-DNS-Suffixe enthalten, die auf die Whitelist gesetzt werden sollen, getrennt durch Leerzeichen. |
    | `WHITELIST_IGNORE_RDNS_URLS` |          | multisite | nein     | **rDNS-Ignorierlisten-URLs:** Liste von URLs, die Reverse-DNS-Suffixe enthalten, die ignoriert werden sollen.                                        |

=== "ASN"
    **Was dies bewirkt:** Setzt Besucher von bestimmten Netzwerkanbietern mithilfe von Autonomen Systemnummern auf die Whitelist. ASNs identifizieren, zu welchem Anbieter oder welcher Organisation eine IP gehört.

    | Einstellung                 | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                         |
    | --------------------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
    | `WHITELIST_ASN`             |          | multisite | nein     | **ASN-Whitelist:** Liste von Autonomen Systemnummern, die erlaubt werden sollen, getrennt durch Leerzeichen.                         |
    | `WHITELIST_IGNORE_ASN`      |          | multisite | nein     | **ASN-Ignorierliste:** Liste von ASNs, die ASN-Whitelist-Prüfungen umgehen sollen.                                                   |
    | `WHITELIST_ASN_URLS`        |          | multisite | nein     | **ASN-Whitelist-URLs:** Liste von URLs, die ASNs enthalten, die auf die Whitelist gesetzt werden sollen, getrennt durch Leerzeichen. |
    | `WHITELIST_IGNORE_ASN_URLS` |          | multisite | nein     | **ASN-Ignorierlisten-URLs:** Liste von URLs, die ASNs enthalten, die ignoriert werden sollen.                                        |

=== "User-Agent"
    **Was dies bewirkt:** Setzt Besucher basierend darauf auf die Whitelist, welchen Browser oder welches Tool sie angeben zu verwenden. Dies ist effektiv, um den Zugriff auf bestimmte bekannte Tools oder Dienste zu ermöglichen.

    | Einstellung                        | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                 |
    | ---------------------------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_USER_AGENT`             |          | multisite | nein     | **User-Agent-Whitelist:** Liste von User-Agent-Mustern (PCRE-Regex), die erlaubt werden sollen, getrennt durch Leerzeichen.  |
    | `WHITELIST_IGNORE_USER_AGENT`      |          | multisite | nein     | **User-Agent-Ignorierliste:** Liste von User-Agent-Mustern, die User-Agent-Whitelist-Prüfungen umgehen sollen.               |
    | `WHITELIST_USER_AGENT_URLS`        |          | multisite | nein     | **User-Agent-Whitelist-URLs:** Liste von URLs, die User-Agent-Muster enthalten, die auf die Whitelist gesetzt werden sollen. |
    | `WHITELIST_IGNORE_USER_AGENT_URLS` |          | multisite | nein     | **User-Agent-Ignorierlisten-URLs:** Liste von URLs, die User-Agent-Muster enthalten, die ignoriert werden sollen.            |

=== "URI"
    **Was dies bewirkt:** Setzt Anfragen an bestimmte URLs auf Ihrer Website auf die Whitelist. Dies ist hilfreich, um den Zugriff auf bestimmte Endpunkte unabhängig von anderen Faktoren zu ermöglichen.

    | Einstellung                 | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                               |
    | --------------------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
    | `WHITELIST_URI`             |          | multisite | nein     | **URI-Whitelist:** Liste von URI-Mustern (PCRE-Regex), die erlaubt werden sollen, getrennt durch Leerzeichen.                              |
    | `WHITELIST_IGNORE_URI`      |          | multisite | nein     | **URI-Ignorierliste:** Liste von URI-Mustern, die URI-Whitelist-Prüfungen umgehen sollen.                                                  |
    | `WHITELIST_URI_URLS`        |          | multisite | nein     | **URI-Whitelist-URLs:** Liste von URLs, die URI-Muster enthalten, die auf die Whitelist gesetzt werden sollen, getrennt durch Leerzeichen. |
    | `WHITELIST_IGNORE_URI_URLS` |          | multisite | nein     | **URI-Ignorierlisten-URLs:** Liste von URLs, die URI-Muster enthalten, die ignoriert werden sollen.                                        |

!!! info "Unterstützung von URL-Formaten"
    Alle `*_URLS`-Einstellungen unterstützen HTTP/HTTPS-URLs sowie lokale Dateipfade mit dem Präfix `file:///`. Die Basisauthentifizierung wird im Format `http://user:pass@url` unterstützt.

!!! tip "Regelmäßige Aktualisierungen"
    Whitelists von URLs werden stündlich automatisch heruntergeladen und aktualisiert, um sicherzustellen, dass Ihr Schutz mit den neuesten vertrauenswürdigen Quellen auf dem neuesten Stand bleibt.

!!! warning "Sicherheitsumgehung"
    Auf der Whitelist stehende Besucher **umgehen vollständig alle anderen Sicherheitsprüfungen** in BunkerWeb, einschließlich WAF-Regeln, Ratenbegrenzung, Erkennung bösartiger Bots und aller anderen Sicherheitsmechanismen. Verwenden Sie die Whitelist nur für vertrauenswürdige Quellen, bei denen Sie absolut sicher sind.

### Beispielkonfigurationen

=== "Grundlegender Organisationszugriff"

    Eine einfache Konfiguration, die die IP-Adressen des Unternehmensbüros auf die Whitelist setzt:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP: "192.168.1.0/24 10.0.0.0/8 203.0.113.42"
    ```

=== "Erweiterte Konfiguration"

    Eine umfassendere Konfiguration mit mehreren Whitelist-Kriterien:

    ```yaml
    USE_WHITELIST: "yes"

    # Unternehmens- und vertrauenswürdige Partner-Assets
    WHITELIST_IP: "192.168.1.0/24 203.0.113.0/24"
    WHITELIST_RDNS: ".company.com .partner-company.org"
    WHITELIST_ASN: "12345 67890"  # ASNs von Unternehmen und Partnern
    WHITELIST_USER_AGENT: "(?:\b)CompanyBot(?:\b) (?:\b)PartnerCrawler(?:\b)"

    # Externe vertrauenswürdige Quellen
    WHITELIST_IP_URLS: "https://example.com/trusted-networks.txt"
    WHITELIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Verwendung lokaler Dateien"

    Konfiguration mit lokalen Dateien für Whitelists:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP_URLS: "file:///path/to/ip-whitelist.txt"
    WHITELIST_RDNS_URLS: "file:///path/to/rdns-whitelist.txt"
    WHITELIST_ASN_URLS: "file:///path/to/asn-whitelist.txt"
    WHITELIST_USER_AGENT_URLS: "file:///path/to/user-agent-whitelist.txt"
    WHITELIST_URI_URLS: "file:///path/to/uri-whitelist.txt"
    ```

=== "API-Zugriffsmuster"

    Eine Konfiguration, die sich darauf konzentriert, den Zugriff nur auf bestimmte API-Endpunkte zu ermöglichen:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_URI: "^/api/v1/public/ ^/api/v1/status"
    WHITELIST_IP: "192.168.1.0/24"  # Internes Netzwerk für alle Endpunkte
    ```

=== "Bekannte Crawler"

    Eine Konfiguration, die gängige Suchmaschinen- und Social-Media-Crawler auf die Whitelist setzt:

    ```yaml
    USE_WHITELIST: "yes"

    # Verifizierung mit Reverse DNS für zusätzliche Sicherheit
    WHITELIST_RDNS: ".googlebot.com .search.msn.com .crawl.yahoo.net .yandex.com .baidu.com .facebook.com"
    WHITELIST_RDNS_GLOBAL: "yes"  # Nur globale IPs prüfen
    ```

    Diese Konfiguration ermöglicht es legitimen Crawlern, Ihre Website zu indizieren, ohne Ratenbegrenzungen oder anderen Sicherheitsmaßnahmen unterworfen zu sein, die sie blockieren könnten. Die rDNS-Prüfungen helfen zu überprüfen, ob die Crawler tatsächlich von den von ihnen angegebenen Unternehmen stammen.

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
# /etc/bunkerweb/lists/ip-whitelist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-whitelist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
