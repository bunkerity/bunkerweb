Der Redis-Plugin integriert [Redis](https://redis.io/) oder [Valkey](https://valkey.io/) in BunkerWeb zur Zwischenspeicherung and für schnellen Datenzugriff. Dies ist unerlässlich in Hochverfügbarkeitsumgebungen, um Sitzungen, Metriken and andere Informationen zwischen mehreren Knoten zu teilen.

**Funktionsweise:**

1.  Nach der Aktivierung verbindet sich BunkerWeb mit dem konfigurierten Redis-/Valkey-Server.
2.  Kritische Daten (Sitzungen, Metriken, Sicherheit) werden dort gespeichert.
3.  Mehrere Instanzen teilen diese Daten für ein reibungsloses Clustering.
4.  Unterstützt Standalone-Bereitstellungen, passwortbasierte Authentifizierung, SSL/TLS and Redis Sentinel.
5.  Automatische Wiederverbindung and konfigurierbare Timeouts sorgen für Robustheit.

### Verwendung

1.  **Aktivieren:** `USE_REDIS: yes`.
2.  **Verbindung:** Host/IP and Port.
3.  **Sicherheit:** Anmeldeinformationen, falls erforderlich.
4.  **Erweitert:** Datenbank, SSL and Timeouts.
5.  **Hochverfügbarkeit:** Konfigurieren Sie Sentinel, falls verwendet.

### Parameter

| Parameter                 | Standard   | Kontext | Mehrfach | Beschreibung                                                  |
| :------------------------ | :--------- | :------ | :------- | :------------------------------------------------------------ |
| `USE_REDIS`               | `no`       | global  | nein     | Aktiviert die Redis-/Valkey-Integration (Cluster-Modus).      |
| `REDIS_HOST`              |            | global  | nein     | Host/IP des Redis-/Valkey-Servers.                            |
| `REDIS_PORT`              | `6379`     | global  | nein     | Redis-/Valkey-Port.                                           |
| `REDIS_DATABASE`          | `0`        | global  | nein     | Datenbanknummer (0–15).                                       |
| `REDIS_SSL`               | `no`       | global  | nein     | Aktiviert SSL/TLS.                                            |
| `REDIS_SSL_VERIFY`        | `yes`      | global  | nein     | Überprüft das SSL-Zertifikat des Servers.                     |
| `REDIS_TIMEOUT`           | `5`        | global  | nein     | Timeout (Sekunden).                                           |
| `REDIS_USERNAME`          |            | global  | nein     | Benutzername (Redis ≥ 6.0).                                   |
| `REDIS_PASSWORD`          |            | global  | nein     | Passwort.                                                     |
| `REDIS_SENTINEL_HOSTS`    |            | global  | nein     | Sentinel-Hosts (durch Leerzeichen getrennt, `host:port`).     |
| `REDIS_SENTINEL_USERNAME` |            | global  | nein     | Sentinel-Benutzer.                                            |
| `REDIS_SENTINEL_PASSWORD` |            | global  | nein     | Sentinel-Passwort.                                            |
| `REDIS_SENTINEL_MASTER`   | `mymaster` | global  | nein     | Name des Sentinel-Masters.                                    |
| `REDIS_KEEPALIVE_IDLE`    | `300`      | global  | nein     | TCP-Keepalive-Intervall (Sekunden) für inaktive Verbindungen. |
| `REDIS_KEEPALIVE_POOL`    | `3`        | global  | nein     | Maximale Anzahl der im Pool gehaltenen Verbindungen.          |

!!! tip "Hochverfügbarkeit"
    Konfigurieren Sie Redis Sentinel für ein automatisches Failover in der Produktion.

!!! warning "Sicherheit"

- Verwenden Sie starke Passwörter für Redis and Sentinel.
- Erwägen Sie die Verwendung von SSL/TLS.
- Setzen Sie Redis nicht dem Internet aus.
- Beschränken Sie den Zugriff auf den Redis-Port (Firewall, Segmentierung).

### Beispiele

=== "Basiskonfiguration"

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "localhost"
    REDIS_PORT: "6379"
    ```

=== "Sichere Konfiguration"

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_SSL: "yes"
    REDIS_SSL_VERIFY: "yes"
    ```

=== "Redis Sentinel"

    ```yaml
    USE_REDIS: "yes"
    REDIS_SENTINEL_HOSTS: "sentinel1:26379 sentinel2:26379 sentinel3:26379"
    REDIS_SENTINEL_MASTER: "mymaster"
    REDIS_SENTINEL_PASSWORD: "sentinel-password"
    REDIS_PASSWORD: "redis-password"
    ```

=== "Erweitertes Tuning"

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_DATABASE: "3"
    REDIS_TIMEOUT: "3"
    REDIS_KEEPALIVE_IDLE: "60"
    REDIS_KEEPALIVE_POOL: "5"
    ```
