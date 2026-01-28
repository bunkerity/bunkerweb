Das Blacklist-Plugin schützt Ihre Website, indem es den Zugriff basierend auf verschiedenen Client-Attributen blockiert. Diese Funktion wehrt bekannte bösartige Entitäten, Scanner und verdächtige Besucher ab, indem sie den Zugriff basierend auf IP-Adressen, Netzwerken, Reverse-DNS-Einträgen (rDNS), ASNs, User-Agents und spezifischen URI-Mustern verweigert.

**So funktioniert's:**[1][2][3]

1.  Das Plugin überprüft eingehende Anfragen anhand mehrerer Blacklist-Kriterien (IP-Adressen, Netzwerke, rDNS, ASN, User-Agent oder URI-Muster).
2.  Blacklists können direkt in Ihrer Konfiguration angegeben oder von externen URLs geladen werden.
3.  Wenn ein Besucher einer Blacklist-Regel entspricht (und keiner Ignorier-Regel), wird der Zugriff verweigert.
4.  Blacklists werden automatisch in regelmäßigen Abständen von den konfigurierten URLs aktualisiert.[4][5][6][7][8]
5.  Sie können genau anpassen, welche Kriterien überprüft und ignoriert werden, basierend auf Ihren spezifischen Sicherheitsanforderungen.

### So verwenden Sie es

Befolgen Sie diese Schritte, um die Blacklist-Funktion einzurichten und zu verwenden:

1.  **Funktion aktivieren:** Die Blacklist-Funktion ist standardmäßig aktiviert. Bei Bedarf können Sie sie mit dem Parameter `USE_BLACKLIST` steuern.
2.  **Blockierregeln konfigurieren:** Definieren Sie, welche IPs, Netzwerke, rDNS-Muster, ASNs, User-Agents oder URIs blockiert werden sollen.
3.  **Ignorierregeln einrichten:** Geben Sie Ausnahmen an, die die Blacklist-Überprüfungen umgehen sollen.
4.  **Externe Quellen hinzufügen:** Konfigurieren Sie URLs, um Blacklist-Daten automatisch herunterzuladen und zu aktualisieren.[4][5][6][7][8]
5.  **Effektivität überwachen:** Konsultieren Sie die [Web-Oberfläche](web-ui.md), um Statistiken über blockierte Anfragen anzuzeigen.

!!! info "Stream-Modus"
    Im Stream-Modus werden nur Überprüfungen nach IP, rDNS und ASN durchgeführt.

### Konfigurationsparameter[9][10][11][12][13][14][15][16][17]

**Allgemein**

| Parameter                   | Standard                                                | Kontext   | Mehrfach | Beschreibung                                                                                                                                           |
| :-------------------------- | :------------------------------------------------------ | :-------- | :------- | :----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BLACKLIST`             | `yes`                                                   | Multisite | Nein     | **Blacklist aktivieren:** Setzen Sie auf `yes`, um die Blacklist-Funktion zu aktivieren.                                                               |
| `BLACKLIST_COMMUNITY_LISTS` | `ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents` | Multisite | Nein     | **Community-Blacklists:** Wählen Sie vorkonfigurierte und von der Community gepflegte Blacklists aus, die in die Blockierung einbezogen werden sollen. |

=== "Community-Blacklists"
    **Was es bewirkt:** Ermöglicht Ihnen, schnell gut gepflegte und von der Community stammende Blacklists hinzuzufügen, ohne die URLs manuell konfigurieren zu müssen.

    Der Parameter `BLACKLIST_COMMUNITY_LISTS` ermöglicht Ihnen die Auswahl aus ausgewählten Blacklist-Quellen. Die verfügbaren Optionen umfassen:

    | ID                                  | Beschreibung                                                                                                                                                                                                              | Quelle                                                                                                                         |
    | :---------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :----------------------------------------------------------------------------------------------------------------------------- |
    | `ip:danmeuk-tor-exit`               | IP-Adressen von Tor-Exit-Nodes (dan.me.uk)                                                                                                                                                                                | `https://www.dan.me.uk/torlist/?exit`                                                                                          |
    | `ua:mitchellkrogza-bad-user-agents` | Nginx Block Bad Bots, Spam Referrer Blocker, Vulnerability Scanners, User-Agents, Malware, Adware, Ransomware, Malicious Sites, mit Anti-DDOS, Wordpress Theme Detector Blocking und Fail2Ban Jail für Wiederholungstäter | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` |

    **Konfiguration:** Geben Sie mehrere Listen durch Leerzeichen getrennt an. Zum Beispiel:
    ```yaml
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    !!! tip "Community-Listen vs. manuelle Konfiguration"
        Community-Blacklists bieten eine bequeme Möglichkeit, mit bewährten Blacklist-Quellen zu beginnen. Sie können diese parallel zu manuellen URL-Konfigurationen für maximale Flexibilität verwenden.

=== "IP-Adresse"[18][19][20][21][22]
    **Was es bewirkt:** Blockiert Besucher basierend auf ihrer IP-Adresse oder ihrem Netzwerk.

    | Parameter                  | Standard                              | Kontext   | Mehrfach | Beschreibung                                                                                                                 |
    | :------------------------- | :------------------------------------ | :-------- | :------- | :--------------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_IP`             |                                       | Multisite | Nein     | **IP-Blacklist:** Liste von IP-Adressen oder Netzwerken (CIDR-Notation) zum Blockieren, durch Leerzeichen getrennt.          |
    | `BLACKLIST_IGNORE_IP`      |                                       | Multisite | Nein     | **IP-Ignorierliste:** Liste von IP-Adressen oder Netzwerken, die IP-Blacklist-Überprüfungen umgehen sollen.                  |
    | `BLACKLIST_IP_URLS`        | `https://www.dan.me.uk/torlist/?exit` | Multisite | Nein     | **IP-Blacklist-URLs:** Liste von URLs, die zu blockierende IP-Adressen oder Netzwerke enthalten, durch Leerzeichen getrennt. |
    | `BLACKLIST_IGNORE_IP_URLS` |                                       | Multisite | Nein     | **IP-Ignorierlisten-URLs:** Liste von URLs, die zu ignorierende IP-Adressen oder Netzwerke enthalten.                        |

    Der Standardparameter `BLACKLIST_IP_URLS` enthält eine URL, die eine **Liste bekannter Tor-Exit-Nodes** bereitstellt. Dies ist eine häufige Quelle für bösartigen Datenverkehr und ein guter Ausgangspunkt für viele Websites.

=== "Reverse DNS"[23][24][25][26][27]
    **Was es bewirkt:** Blockiert Besucher basierend auf ihrem Reverse-Domain-Namen. Dies ist nützlich, um bekannte Scanner und Crawler basierend auf ihren Organisationsdomänen zu blockieren.

    | Parameter                    | Standard                | Kontext   | Mehrfach | Beschreibung                                                                                               |
    | :--------------------------- | :---------------------- | :-------- | :------- | :--------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_RDNS`             | `.shodan.io .censys.io` | Multisite | Nein     | **rDNS-Blacklist:** Liste von Reverse-DNS-Suffixen zum Blockieren, durch Leerzeichen getrennt.             |
    | `BLACKLIST_RDNS_GLOBAL`      | `yes`                   | Multisite | Nein     | **Nur globales rDNS:** Führt rDNS-Überprüfungen nur für globale IP-Adressen durch, wenn auf `yes` gesetzt. |
    | `BLACKLIST_IGNORE_RDNS`      |                         | Multisite | Nein     | **rDNS-Ignorierliste:** Liste von Reverse-DNS-Suffixen, die rDNS-Blacklist-Überprüfungen umgehen sollen.   |
    | `BLACKLIST_RDNS_URLS`        |                         | Multisite | Nein     | **rDNS-Blacklist-URLs:** Liste von URLs, die zu blockierende Reverse-DNS-Suffixe enthalten.                |
    | `BLACKLIST_IGNORE_RDNS_URLS` |                         | Multisite | Nein     | **rDNS-Ignorierlisten-URLs:** Liste von URLs, die zu ignorierende Reverse-DNS-Suffixe enthalten.           |

    Der Standardparameter `BLACKLIST_RDNS` enthält Domänen gängiger Scanner wie **Shodan** und **Censys**. Diese werden oft von Sicherheitsforschern und Scannern verwendet, um anfällige Websites zu identifizieren.

=== "ASN"
    **Was es bewirkt:** Blockiert Besucher von bestimmten Netzwerkanbietern. ASNs sind wie Postleitzahlen für das Internet – sie identifizieren, zu welchem Anbieter oder welcher Organisation eine IP gehört.

    | Parameter                   | Standard | Kontext   | Mehrfach | Beschreibung                                                                                     |
    | :-------------------------- | :------- | :-------- | :------- | :----------------------------------------------------------------------------------------------- |
    | `BLACKLIST_ASN`             |          | Multisite | Nein     | **ASN-Blacklist:** Liste von autonomen Systemnummern zum Blockieren, durch Leerzeichen getrennt. |
    | `BLACKLIST_IGNORE_ASN`      |          | Multisite | Nein     | **ASN-Ignorierliste:** Liste von ASNs, die ASN-Blacklist-Überprüfungen umgehen sollen.           |
    | `BLACKLIST_ASN_URLS`        |          | Multisite | Nein     | **ASN-Blacklist-URLs:** Liste von URLs, die zu blockierende ASNs enthalten.                      |
    | `BLACKLIST_IGNORE_ASN_URLS` |          | Multisite | Nein     | **ASN-Ignorierlisten-URLs:** Liste von URLs, die zu ignorierende ASNs enthalten.                 |

=== "User-Agent"[28][29][30][31][32]
    **Was es bewirkt:** Blockiert Besucher basierend auf dem Browser oder Tool, das sie angeblich verwenden. Dies ist effektiv gegen Bots, die sich ehrlich identifizieren (wie "ScannerBot" oder "WebHarvestTool").

    | Parameter                          | Standard                                                                                                                       | Kontext   | Mehrfach | Beschreibung                                                                                                       |
    | :--------------------------------- | :----------------------------------------------------------------------------------------------------------------------------- | :-------- | :------- | :----------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_USER_AGENT`             |                                                                                                                                | Multisite | Nein     | **User-Agent-Blacklist:** Liste von User-Agent-Mustern (PCRE-Regex) zum Blockieren, durch Leerzeichen getrennt.    |
    | `BLACKLIST_IGNORE_USER_AGENT`      |                                                                                                                                | Multisite | Nein     | **User-Agent-Ignorierliste:** Liste von User-Agent-Mustern, die User-Agent-Blacklist-Überprüfungen umgehen sollen. |
    | `BLACKLIST_USER_AGENT_URLS`        | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` | Multisite | Nein     | **User-Agent-Blacklist-URLs:** Liste von URLs, die zu blockierende User-Agent-Muster enthalten.                    |
    | `BLACKLIST_IGNORE_USER_AGENT_URLS` |                                                                                                                                | Multisite | Nein     | **User-Agent-Ignorierlisten-URLs:** Liste von URLs, die zu ignorierende User-Agent-Muster enthalten.               |

    Der Standardparameter `BLACKLIST_USER_AGENT_URLS` enthält eine URL, die eine **Liste bekannter bösartiger User-Agents** bereitstellt. Diese werden oft von bösartigen Bots und Scannern verwendet, um anfällige Websites zu identifizieren.

=== "URI"[33][34][35][36][37]
    **Was es bewirkt:** Blockiert Anfragen an spezifische URLs auf Ihrer Website. Dies ist nützlich, um Zugriffsversuche auf Admin-Seiten, Anmeldeformulare oder andere sensible Bereiche zu blockieren, die angegriffen werden könnten.

    | Parameter                   | Standard | Kontext   | Mehrfach | Beschreibung                                                                                      |
    | :-------------------------- | :------- | :-------- | :------- | :------------------------------------------------------------------------------------------------ |
    | `BLACKLIST_URI`             |          | Multisite | Nein     | **URI-Blacklist:** Liste von URI-Mustern (PCRE-Regex) zum Blockieren, durch Leerzeichen getrennt. |
    | `BLACKLIST_IGNORE_URI`      |          | Multisite | Nein     | **URI-Ignorierliste:** Liste von URI-Mustern, die URI-Blacklist-Überprüfungen umgehen sollen.     |
    | `BLACKLIST_URI_URLS`        |          | Multisite | Nein     | **URI-Blacklist-URLs:** Liste von URLs, die zu blockierende URI-Muster enthalten.                 |
    | `BLACKLIST_IGNORE_URI_URLS` |          | Multisite | Nein     | **URI-Ignorierlisten-URLs:** Liste von URLs, die zu ignorierende URI-Muster enthalten.            |

!!! info "Unterstützung von URL-Formaten"
    Alle `*_URLS`-Parameter unterstützen HTTP/HTTPS-URLs sowie lokale Dateipfade unter Verwendung des Präfixes `file:///`. Die Basisauthentifizierung wird im Format `http://user:pass@url` unterstützt.

!!! tip "Regelmäßige Updates"[4][5][6][7][8]
    Blacklists von URLs werden automatisch stündlich heruntergeladen und aktualisiert, um sicherzustellen, dass Ihr Schutz gegen die neuesten Bedrohungen auf dem neuesten Stand bleibt.

### Konfigurationsbeispiele[38]

=== "Grundlegender Schutz durch IP und User-Agent"

    Eine einfache Konfiguration, die bekannte Tor-Exit-Nodes und gängige bösartige User-Agents mithilfe der Community-Blacklists blockiert:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    Alternativ können Sie eine manuelle Konfiguration per URL verwenden:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Erweiterter Schutz mit benutzerdefinierten Regeln"

    Eine umfassendere Konfiguration mit benutzerdefinierten Blacklist-Einträgen und Ausnahmen:

    ```yaml
    USE_BLACKLIST: "yes"

    # Benutzerdefinierte Blacklist-Einträge
    BLACKLIST_IP: "192.168.1.100 203.0.113.0/24"
    BLACKLIST_RDNS: ".shodan.io .censys.io .scanner.com"
    BLACKLIST_ASN: "16509 14618"  # ASN von AWS und Amazon
    BLACKLIST_USER_AGENT: "(?:\b)SemrushBot(?:\b) (?:\b)AhrefsBot(?:\b)"
    BLACKLIST_URI: "^/wp-login\.php$ ^/administrator/"

    # Benutzerdefinierte Ignorierregeln
    BLACKLIST_IGNORE_IP: "192.168.1.200 203.0.113.42"

    # Externe Blacklist-Quellen
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit https://www.spamhaus.org/drop/drop.txt"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Verwendung lokaler Dateien"

    Konfiguration mit lokalen Dateien für Blacklists:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "file:///chemin/vers/ip-blacklist.txt"
    BLACKLIST_RDNS_URLS: "file:///chemin/vers/rdns-blacklist.txt"
    BLACKLIST_ASN_URLS: "file:///chemin/vers/asn-blacklist.txt"
    BLACKLIST_USER_AGENT_URLS: "file:///chemin/vers/user-agent-blacklist.txt"
    BLACKLIST_URI_URLS: "file:///chemin/vers/uri-blacklist.txt"
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
# /etc/bunkerweb/lists/ip-blacklist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-blacklist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
