Das Backup-Plugin bietet eine automatisierte Backup-Lösung zum Schutz Ihrer BunkerWeb-Daten. Diese Funktion gewährleistet die Sicherheit und Verfügbarkeit Ihrer wichtigen Datenbank, indem sie regelmäßige Backups nach Ihrem bevorzugten Zeitplan erstellt. Backups werden an einem bestimmten Ort gespeichert und können sowohl durch automatisierte Prozesse als auch durch manuelle Befehle einfach verwaltet werden.

**So funktioniert es:**

1.  Ihre Datenbank wird automatisch gemäß dem von Ihnen festgelegten Zeitplan (`daily`, `weekly`, `monthly` oder `hanoi`) gesichert.
2.  Backups werden in einem angegebenen Verzeichnis auf Ihrem System gespeichert.
3.  Vor jedem Backup wird der verfügbare Speicherplatz geprüft.
4.  Jede Backup-ZIP enthält den SQL-Dump und eine SHA-256-Prüfsummendatei (`.sha256`) zur Integritätsprüfung.
5.  Alte Backups werden automatisch rotiert. Der Modus `hanoi` verwendet die Türme-von-Hanoi-Rotation (24 Dateien, ~85 Tage Abdeckung).
6.  Beim Wiederherstellen wird die Prüfsumme verifiziert, bevor die aktive Datenbank verändert wird.
7.  Sie können jederzeit manuell Backups erstellen, auflisten, prüfen oder wiederherstellen.
8.  Vor jeder Wiederherstellung wird der aktuelle Zustand als Sicherheitsmaßnahme automatisch gesichert.

### Wie man es benutzt

1.  **Aktivieren Sie die Funktion:** Die Backup-Funktion ist standardmäßig aktiviert. Bei Bedarf können Sie dies mit der Einstellung `USE_BACKUP` steuern.
2.  **Backup-Zeitplan konfigurieren:** Wählen Sie mit dem Parameter `BACKUP_SCHEDULE`, wie oft Backups durchgeführt werden sollen.
3.  **Aufbewahrungsrichtlinie festlegen:** Geben Sie mit der Einstellung `BACKUP_ROTATION` an, wie viele Backups aufbewahrt werden sollen (wird bei `BACKUP_SCHEDULE=hanoi` ignoriert).
4.  **Speicherort festlegen:** Wählen Sie mit der Einstellung `BACKUP_DIRECTORY`, wo die Backups gespeichert werden sollen.
5.  **CLI-Befehle verwenden:** Verwalten Sie Backups bei Bedarf manuell mit den `bwcli plugin backup`-Befehlen.

### Konfigurationseinstellungen

| Einstellung        | Standard                     | Kontext | Mehrfach | Beschreibung                                                                                                                                               |
| ------------------ | ---------------------------- | ------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global  | nein     | **Backup aktivieren:** Auf `yes` setzen, um automatische Backups zu aktivieren.                                                                            |
| `BACKUP_SCHEDULE`  | `daily`                      | global  | nein     | **Backup-Frequenz:** `daily`, `weekly`, `monthly` oder `hanoi` (stündlich mit Türme-von-Hanoi-Rotation, ~85 Tage Abdeckung).                               |
| `BACKUP_ROTATION`  | `7`                          | global  | nein     | **Backup-Aufbewahrung:** Anzahl der aufzubewahrenden Backup-Dateien. Wird bei `hanoi` ignoriert (Rotation wird automatisch verwaltet).                     |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global  | nein     | **Backup-Speicherort:** Das Verzeichnis, in dem die Backup-Dateien gespeichert werden.                                                                     |
| `BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE` | `no` | global | nein | **Prüfsummenfehler ignorieren:** Bei `yes` wird ein fehlgeschlagener SHA-256-Check die Wiederherstellung nicht abbrechen. Nur als letztes Mittel verwenden. |

### Befehlszeilenschnittstelle

Das Backup-Plugin bietet mehrere CLI-Befehle zur Verwaltung Ihrer Backups:

```bash
# Alle verfügbaren Backups auflisten
bwcli plugin backup list

# SHA-256-Prüfsummen aller Backups prüfen
bwcli plugin backup check

# Ein manuelles Backup erstellen
bwcli plugin backup save

# Ein Backup an einem benutzerdefinierten Ort erstellen
bwcli plugin backup save --directory /pfad/zum/benutzerdefinierten/ort

# Aus dem neuesten Backup wiederherstellen
bwcli plugin backup restore

# Aus einer bestimmten Backup-Datei wiederherstellen
bwcli plugin backup restore /pfad/zum/backup/backup-sqlite-2023-08-15_12-34-56.zip
```

!!! tip "Sicherheit geht vor"
    Vor jeder Wiederherstellung erstellt das Backup-Plugin automatisch ein Backup des aktuellen Zustands Ihrer Datenbank an einem temporären Ort.

!!! info "Integritätsprüfung"
    Jede ZIP enthält eine SHA-256-Prüfsummendatei. Die Prüfsumme wird automatisch vor jeder Wiederherstellung verifiziert. Verwenden Sie `bwcli plugin backup check`, um alle Backups jederzeit zu prüfen.

!!! warning "Datenbankkompatibilität"
    Das Backup-Plugin unterstützt SQLite, MySQL/MariaDB und PostgreSQL-Datenbanken. Oracle-Datenbanken werden derzeit nicht unterstützt.

### Beispielkonfigurationen

=== "Tägliche Backups mit 7-tägiger Aufbewahrung"

    Standardkonfiguration, die tägliche Backups erstellt und die letzten 7 Dateien aufbewahrt:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Türme von Hanoi (~85 Tage)"

    Stündliche Ausführung mit Türme-von-Hanoi-Rotation. Hält 24 Dateien mit ~85 Tagen Abdeckung. `BACKUP_ROTATION` wird ignoriert:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "hanoi"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Wöchentliche Backups mit erweiterter Aufbewahrung"

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Monatliche Backups an einem benutzerdefinierten Speicherort"

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```
