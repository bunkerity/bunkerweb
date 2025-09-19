Das Metrics-Plugin bietet umfassende Überwachungs- und Datenerfassungsfunktionen für Ihre BunkerWeb-Instanz. Mit dieser Funktion können Sie verschiedene Leistungsindikatoren, Sicherheitsereignisse und Systemstatistiken verfolgen und erhalten so wertvolle Einblicke in das Verhalten und den Zustand Ihrer geschützten Websites und Dienste.

**So funktioniert es:**

1.  BunkerWeb erfasst während der Verarbeitung von Anfragen und Antworten wichtige Metriken.
2.  Zu diesen Metriken gehören Zähler für blockierte Anfragen, Leistungsmessungen und verschiedene sicherheitsrelevante Statistiken.
3.  Die Daten werden effizient im Speicher gespeichert, mit konfigurierbaren Grenzwerten, um eine übermäßige Ressourcennutzung zu verhindern.
4.  Für Multi-Instanz-Setups kann Redis zur Zentralisierung und Aggregation von Metrikdaten verwendet werden.
5.  Auf die erfassten Metriken kann über die API zugegriffen oder in der [Web-Benutzeroberfläche](web-ui.md) visualisiert werden.
6.  Diese Informationen helfen Ihnen, Sicherheitsbedrohungen zu identifizieren, Probleme zu beheben und Ihre Konfiguration zu optimieren.

### Technische Umsetzung

Das Metrics-Plugin funktioniert durch:

- Verwendung gemeinsamer Wörterbücher in NGINX, wobei `metrics_datastore` für HTTP und `metrics_datastore_stream` für TCP/UDP-Verkehr verwendet wird
- Nutzung eines LRU-Cache für eine effiziente In-Memory-Speicherung
- Periodische Synchronisierung von Daten zwischen Workern mithilfe von Timern
- Speicherung detaillierter Informationen über blockierte Anfragen, einschließlich der Client-IP-Adresse, des Landes, des Zeitstempels, der Anfragedetails und des Blockierungsgrunds
- Unterstützung von Plugin-spezifischen Metriken über eine gemeinsame Schnittstelle zur Metrikerfassung
- Bereitstellung von API-Endpunkten zur Abfrage erfasster Metriken

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Metrics-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die Metrikerfassung ist standardmäßig aktiviert. Sie können dies mit der Einstellung `USE_METRICS` steuern.
2.  **Speicherzuweisung konfigurieren:** Legen Sie die Speichermenge fest, die für die Metrikspeicherung zugewiesen werden soll, indem Sie die Einstellung `METRICS_MEMORY_SIZE` verwenden.
3.  **Speichergrenzen festlegen:** Definieren Sie, wie viele blockierte Anfragen pro Worker und in Redis mit den entsprechenden Einstellungen gespeichert werden sollen.
4.  **Auf die Daten zugreifen:** Sehen Sie sich die erfassten Metriken über die [Web-Benutzeroberfläche](web-ui.md) oder API-Endpunkte an.
5.  **Informationen analysieren:** Verwenden Sie die gesammelten Daten, um Muster zu erkennen, Sicherheitsprobleme zu identifizieren und Ihre Konfiguration zu optimieren.

### Erfasste Metriken

Das Metrics-Plugin erfasst die folgenden Informationen:

1.  **Blockierte Anfragen**: Für jede blockierte Anfrage werden die folgenden Daten gespeichert:
    - Anfrage-ID und Zeitstempel
    - Client-IP-Adresse und Land (sofern verfügbar)
    - HTTP-Methode und URL
    - HTTP-Statuscode
    - User-Agent
    - Blockierungsgrund und Sicherheitsmodus
    - Servername
    - Zusätzliche Daten im Zusammenhang mit dem Blockierungsgrund

2.  **Plugin-Zähler**: Verschiedene Plugin-spezifische Zähler, die Aktivitäten und Ereignisse verfolgen.

### API-Zugriff

Auf Metrikdaten kann über die internen API-Endpunkte von BunkerWeb zugegriffen werden:

- **Endpunkt**: `/metrics/{filter}`
- **Methode**: GET
- **Beschreibung**: Ruft Metrikdaten basierend auf dem angegebenen Filter ab
- **Antwortformat**: JSON-Objekt, das die angeforderten Metriken enthält

Zum Beispiel gibt `/metrics/requests` Informationen über blockierte Anfragen zurück.

!!! info "Konfiguration des API-Zugriffs"
Um über die API auf Metriken zuzugreifen, müssen Sie sicherstellen, dass:

    1. Die API-Funktion mit `USE_API: "yes"` aktiviert ist (standardmäßig aktiviert)
    2. Ihre Client-IP in der Einstellung `API_WHITELIST_IP` enthalten ist (Standard ist `127.0.0.0/8`)
    3. Sie auf die API über den konfigurierten Port zugreifen (Standard ist `5000` über die Einstellung `API_HTTP_PORT`)
    4. Sie den korrekten `API_SERVER_NAME`-Wert im Host-Header verwenden (Standard ist `bwapi`)
    5. Wenn `API_TOKEN` konfiguriert ist, fügen Sie `Authorization: Bearer <token>` in die Anfrage-Header ein.

    Typische Anfragen:

    Ohne Token (wenn `API_TOKEN` nicht gesetzt ist):
    ```bash
    curl -H "Host: bwapi" \
         http://ihre-bunkerweb-instanz:5000/metrics/requests
    ```

    Mit Token (wenn `API_TOKEN` gesetzt ist):
    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://ihre-bunkerweb-instanz:5000/metrics/requests
    ```

    Wenn Sie den `API_SERVER_NAME` auf einen anderen Wert als den Standard `bwapi` angepasst haben, verwenden Sie diesen Wert stattdessen im Host-Header.

    Für sichere Produktionsumgebungen beschränken Sie den API-Zugriff auf vertrauenswürdige IPs und aktivieren Sie `API_TOKEN`.

### Konfigurationseinstellungen

| Einstellung                          | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                              |
| ------------------------------------ | -------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_METRICS`                        | `yes`    | multisite | nein     | **Metriken aktivieren:** Auf `yes` setzen, um die Erfassung und den Abruf von Metriken zu aktivieren.                                     |
| `METRICS_MEMORY_SIZE`                | `16m`    | global    | nein     | **Speichergröße:** Größe des internen Speichers für Metriken (z. B. `16m`, `32m`).                                                        |
| `METRICS_MAX_BLOCKED_REQUESTS`       | `1000`   | global    | nein     | **Max. blockierte Anfragen:** Maximale Anzahl blockierter Anfragen, die pro Worker gespeichert werden sollen.                             |
| `METRICS_MAX_BLOCKED_REQUESTS_REDIS` | `100000` | global    | nein     | **Max. Redis-blockierte Anfragen:** Maximale Anzahl blockierter Anfragen, die in Redis gespeichert werden sollen.                         |
| `METRICS_SAVE_TO_REDIS`              | `yes`    | global    | nein     | **Metriken in Redis speichern:** Auf `yes` setzen, um Metriken (Zähler und Tabellen) zur clusterweiten Aggregation in Redis zu speichern. |

!!! tip "Dimensionierung der Speicherzuweisung"
Die Einstellung `METRICS_MEMORY_SIZE` sollte basierend auf Ihrem Verkehrsaufkommen und der Anzahl der Instanzen angepasst werden. Bei stark frequentierten Websites sollten Sie diesen Wert erhöhen, um sicherzustellen, dass alle Metriken ohne Datenverlust erfasst werden.

!!! info "Redis-Integration"
Wenn BunkerWeb für die Verwendung von [Redis](#redis) konfiguriert ist, synchronisiert das Metrics-Plugin blockierte Anfragedaten automatisch mit dem Redis-Server. Dies bietet eine zentralisierte Ansicht von Sicherheitsereignissen über mehrere BunkerWeb-Instanzen hinweg.

!!! warning "Leistungsüberlegungen"
Das Festlegen sehr hoher Werte für `METRICS_MAX_BLOCKED_REQUESTS` oder `METRICS_MAX_BLOCKED_REQUESTS_REDIS` kann den Speicherverbrauch erhöhen. Überwachen Sie Ihre Systemressourcen und passen Sie diese Werte entsprechend Ihren tatsächlichen Bedürfnissen und verfügbaren Ressourcen an.

!!! note "Worker-spezifischer Speicher"
Jeder NGINX-Worker verwaltet seine eigenen Metriken im Speicher. Beim Zugriff auf Metriken über die API werden die Daten aller Worker automatisch aggregiert, um eine vollständige Ansicht zu erhalten.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Standardkonfiguration, die für die meisten Bereitstellungen geeignet ist:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "16m"
    METRICS_MAX_BLOCKED_REQUESTS: "1000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "100000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Umgebung mit geringen Ressourcen"

    Konfiguration, die für Umgebungen mit begrenzten Ressourcen optimiert ist:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "8m"
    METRICS_MAX_BLOCKED_REQUESTS: "500"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10000"
    METRICS_SAVE_TO_REDIS: "no"
    ```

=== "Umgebung mit hohem Verkehrsaufkommen"

    Konfiguration für Websites mit hohem Verkehrsaufkommen, die mehr Sicherheitsereignisse verfolgen müssen:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "64m"
    METRICS_MAX_BLOCKED_REQUESTS: "5000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "500000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Metriken deaktiviert"

    Konfiguration mit deaktivierter Metrikerfassung:

    ```yaml
    USE_METRICS: "no"
    ```
