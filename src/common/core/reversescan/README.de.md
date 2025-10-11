Das Reverse Scan-Plugin schützt robust vor Proxy-Umgehungsversuchen, indem es die Ports der Clients scannt, um festzustellen, ob sie Proxyserver oder andere Netzwerkdienste betreiben. Diese Funktion hilft dabei, potenzielle Bedrohungen von Clients zu identifizieren und zu blockieren, die möglicherweise versuchen, ihre wahre Identität oder Herkunft zu verbergen, und verbessert so die Sicherheitslage Ihrer Website.

**So funktioniert es:**

1.  Wenn ein Client eine Verbindung zu Ihrem Server herstellt, versucht BunkerWeb, bestimmte Ports auf der IP-Adresse des Clients zu scannen.
2.  Das Plugin prüft, ob gängige Proxy-Ports (wie 80, 443, 8080 usw.) auf der Client-Seite geöffnet sind.
3.  Wenn offene Ports erkannt werden, was darauf hindeutet, dass der Client möglicherweise einen Proxyserver betreibt, wird die Verbindung verweigert.
4.  Dies fügt eine zusätzliche Sicherheitsebene gegen automatisierte Tools, Bots und böswillige Benutzer hinzu, die versuchen, ihre Identität zu verschleiern.

!!! success "Wichtige Vorteile"

      1. **Erhöhte Sicherheit:** Identifiziert Clients, die potenziell Proxyserver betreiben, die für bösartige Zwecke verwendet werden könnten.
      2. **Proxy-Erkennung:** Hilft bei der Erkennung und Blockierung von Clients, die versuchen, ihre wahre Identität zu verbergen.
      3. **Konfigurierbare Einstellungen:** Passen Sie an, welche Ports basierend auf Ihren spezifischen Sicherheitsanforderungen gescannt werden sollen.
      4. **Leistungsoptimiert:** Intelligentes Scannen mit konfigurierbaren Zeitüberschreitungen, um die Auswirkungen auf legitime Benutzer zu minimieren.
      5. **Nahtlose Integration:** Arbeitet transparent mit Ihren bestehenden Sicherheitsebenen zusammen.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Reverse-Scan-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Setzen Sie die Einstellung `USE_REVERSE_SCAN` auf `yes`, um das Scannen von Client-Ports zu aktivieren.
2.  **Zu scannende Ports konfigurieren:** Passen Sie die Einstellung `REVERSE_SCAN_PORTS` an, um anzugeben, welche Client-Ports überprüft werden sollen.
3.  **Scan-Timeout festlegen:** Passen Sie den `REVERSE_SCAN_TIMEOUT` an, um ein Gleichgewicht zwischen gründlichem Scannen und Leistung zu finden.
4.  **Scan-Aktivität überwachen:** Überprüfen Sie die Protokolle und die [Web-Benutzeroberfläche](web-ui.md), um die Scan-Ergebnisse und potenzielle Sicherheitsvorfälle zu überprüfen.

### Konfigurationseinstellungen

| Einstellung            | Standard                   | Kontext   | Mehrfach | Beschreibung                                                                                        |
| ---------------------- | -------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------- |
| `USE_REVERSE_SCAN`     | `no`                       | multisite | nein     | **Reverse-Scan aktivieren:** Auf `yes` setzen, um das Scannen von Client-Ports zu aktivieren.       |
| `REVERSE_SCAN_PORTS`   | `22 80 443 3128 8000 8080` | multisite | nein     | **Zu scannende Ports:** Leerzeichengetrennte Liste der zu überprüfenden Ports auf der Client-Seite. |
| `REVERSE_SCAN_TIMEOUT` | `500`                      | multisite | nein     | **Scan-Timeout:** Maximale Zeit in Millisekunden, die für das Scannen eines Ports zulässig ist.     |

!!! warning "Leistungsüberlegungen"
    Das Scannen mehrerer Ports kann die Latenz bei Client-Verbindungen erhöhen. Verwenden Sie einen angemessenen Zeitüberschreitungswert und begrenzen Sie die Anzahl der gescannten Ports, um eine gute Leistung aufrechtzuerhalten.

!!! info "Gängige Proxy-Ports"
    Die Standardkonfiguration umfasst gängige Ports, die von Proxyservern (80, 443, 8080, 3128) und SSH (22) verwendet werden. Sie können diese Liste basierend auf Ihrem Bedrohungsmodell anpassen.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine einfache Konfiguration zum Aktivieren des Client-Port-Scannens:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "500"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Umfassendes Scannen"

    Eine gründlichere Konfiguration, die zusätzliche Ports überprüft:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1000"
    REVERSE_SCAN_PORTS: "22 80 443 3128 8080 8000 8888 1080 3333 8081"
    ```

=== "Leistungsoptimierte Konfiguration"

    Konfiguration, die auf eine bessere Leistung abgestimmt ist, indem weniger Ports mit einer geringeren Zeitüberschreitung überprüft werden:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "250"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Hochsicherheitskonfiguration"

    Konfiguration mit Fokus auf maximale Sicherheit mit erweitertem Scannen:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1500"
    REVERSE_SCAN_PORTS: "22 25 80 443 1080 3128 3333 4444 5555 6588 6666 7777 8000 8080 8081 8800 8888 9999"
    ```
