Das DNSBL (Domain Name System Blacklist) Plugin bietet Schutz vor bekannten bösartigen IP-Adressen, indem es die IP-Adressen von Clients mit externen DNSBL-Servern abgleicht. Diese Funktion schützt Ihre Website vor Spam, Botnetzen und verschiedenen Arten von Cyber-Bedrohungen, indem sie auf von der Community gepflegte Listen problematischer IP-Adressen zurückgreift.

**So funktioniert es:**

1.  Wenn ein Client eine Verbindung zu Ihrer Website herstellt, fragt BunkerWeb die von Ihnen ausgewählten DNSBL-Server über das DNS-Protokoll ab.
2.  Die Überprüfung erfolgt durch Senden einer umgekehrten DNS-Anfrage mit der IP-Adresse des Clients an jeden DNSBL-Server.
3.  Wenn ein DNSBL-Server bestätigt, dass die IP-Adresse des Clients als bösartig aufgeführt ist, wird BunkerWeb den Client automatisch sperren und so verhindern, dass potenzielle Bedrohungen Ihre Anwendung erreichen.
4.  Die Ergebnisse werden zwischengespeichert, um die Leistung bei wiederholten Besuchen von derselben IP-Adresse zu verbessern.
5.  Die Abfragen werden effizient mit asynchronen Abfragen durchgeführt, um die Auswirkungen auf die Ladezeiten der Seite zu minimieren.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die DNSBL-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die DNSBL-Funktion ist standardmäßig deaktiviert. Setzen Sie die Einstellung `USE_DNSBL` auf `yes`, um sie zu aktivieren.
2.  **DNSBL-Server konfigurieren:** Fügen Sie die Domainnamen der DNSBL-Dienste, die Sie verwenden möchten, zur Einstellung `DNSBL_LIST` hinzu.
3.  **Einstellungen anwenden:** Nach der Konfiguration überprüft BunkerWeb eingehende Verbindungen automatisch mit den angegebenen DNSBL-Servern.
4.  **Wirksamkeit überwachen:** Überprüfen Sie die [Web-Benutzeroberfläche](web-ui.md), um Statistiken über Anfragen zu sehen, die durch DNSBL-Prüfungen blockiert wurden.

### Konfigurationseinstellungen

**Allgemein**

| Einstellung  | Standard                                            | Kontext   | Mehrfach | Beschreibung                                                                                      |
| ------------ | --------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------- |
| `USE_DNSBL`  | `no`                                                | multisite | nein     | DNSBL aktivieren: auf `yes` setzen, um DNSBL-Prüfungen für eingehende Verbindungen zu aktivieren. |
| `DNSBL_LIST` | `bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org` | global    | nein     | DNSBL-Server: Liste der zu überprüfenden DNSBL-Server-Domains, durch Leerzeichen getrennt.        |

**Ausnahmelisten**

| Einstellung            | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                            |
| ---------------------- | -------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------- |
| `DNSBL_IGNORE_IP`      | ``       | multisite | ja       | Durch Leerzeichen getrennte IPs/CIDRs, für die DNSBL-Prüfungen übersprungen werden sollen (Whitelist).                  |
| `DNSBL_IGNORE_IP_URLS` | ``       | multisite | ja       | Durch Leerzeichen getrennte URLs, die IPs/CIDRs zum Überspringen bereitstellen. Unterstützt `http(s)://` und `file://`. |

!!! tip "Auswahl von DNSBL-Servern"
Wählen Sie seriöse DNSBL-Anbieter, um Falschmeldungen zu minimieren. Die Standardliste enthält etablierte Dienste, die für die meisten Websites geeignet sind:

    - **bl.blocklist.de:** Listet IPs, die bei Angriffen auf andere Server erkannt wurden.
    - **sbl.spamhaus.org:** Konzentriert sich auf Spam-Quellen und andere bösartige Aktivitäten.
    - **xbl.spamhaus.org:** Zielt auf infizierte Systeme ab, wie z. B. kompromittierte Maschinen oder offene Proxys.

!!! info "Wie DNSBL funktioniert"
DNSBL-Server funktionieren, indem sie auf speziell formatierte DNS-Anfragen antworten. Wenn BunkerWeb eine IP-Adresse überprüft, kehrt es die IP um und hängt den DNSBL-Domainnamen an. Wenn die resultierende DNS-Anfrage eine „Erfolgs“-Antwort zurückgibt, wird die IP als auf der schwarzen Liste stehend betrachtet.

!!! warning "Leistungsüberlegungen"
Obwohl BunkerWeb DNSBL-Abfragen auf Leistung optimiert, könnte das Hinzufügen einer großen Anzahl von DNSBL-Servern potenziell die Antwortzeiten beeinträchtigen. Beginnen Sie mit einigen seriösen DNSBL-Servern und überwachen Sie die Leistung, bevor Sie weitere hinzufügen.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine einfache Konfiguration mit den Standard-DNSBL-Servern:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org"
    ```

=== "Minimale Konfiguration"

    Eine minimale Konfiguration, die sich auf die zuverlässigsten DNSBL-Dienste konzentriert:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    ```

    Diese Konfiguration verwendet nur:

    - **zen.spamhaus.org**: Die kombinierte Liste von Spamhaus wird aufgrund ihrer breiten Abdeckung und ihres Rufs für Genauigkeit oft als eigenständige Lösung als ausreichend angesehen. Sie kombiniert die SBL-, XBL- und PBL-Listen in einer einzigen Abfrage, was sie effizient und umfassend macht.

=== "Ausschluss vertrauenswürdiger IPs"

    Sie können bestimmte Clients von DNSBL-Prüfungen ausschließen, indem Sie statische Werte und/oder entfernte Dateien verwenden:

    - `DNSBL_IGNORE_IP`: Fügen Sie durch Leerzeichen getrennte IPs und CIDR-Bereiche hinzu. Beispiel: `192.0.2.10 203.0.113.0/24 2001:db8::/32`.
    - `DNSBL_IGNORE_IP_URLS`: Geben Sie URLs an, deren Inhalte eine IP/CIDR pro Zeile auflisten. Kommentare, die mit `#` oder `;` beginnen, werden ignoriert. Doppelte Einträge werden entfernt.

    Wenn eine eingehende Client-IP mit der Ausnahmeliste übereinstimmt, überspringt BunkerWeb die DNSBL-Abfragen und speichert das Ergebnis als „ok“ für schnellere nachfolgende Anfragen zwischen.

=== "Verwendung von Remote-URLs"

    Der Job `dnsbl-download` lädt und speichert stündlich zu ignorierende IPs:

    - Protokolle: `https://`, `http://` und lokale `file://`-Pfade.
    - Pro-URL-Cache mit Prüfsumme verhindert redundante Downloads (1 Stunde Toleranz).
    - Pro Dienst zusammengeführte Datei: `/var/cache/bunkerweb/dnsbl/<service>/IGNORE_IP.list`.
    - Wird beim Start geladen und mit `DNSBL_IGNORE_IP` zusammengeführt.

    Beispiel, das statische und URL-Quellen kombiniert:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP: "10.0.0.0/8 192.168.0.0/16 2001:db8::/32"
    DNSBL_IGNORE_IP_URLS: "https://example.com/allow-cidrs.txt file:///etc/bunkerweb/dnsbl/ignore.txt"
    ```

=== "Verwendung lokaler Dateien"

    Laden Sie zu ignorierende IPs aus lokalen Dateien unter Verwendung von `file://`-URLs:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP_URLS: "file:///etc/bunkerweb/dnsbl/ignore.txt file:///opt/data/allow-cidrs.txt"
    ```
