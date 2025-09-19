Das Backup-Plugin bietet eine automatisierte Backup-Lösung zum Schutz Ihrer BunkerWeb-Daten. Diese Funktion gewährleistet die Sicherheit und Verfügbarkeit Ihrer wichtigen Datenbank, indem sie regelmäßige Backups nach Ihrem bevorzugten Zeitplan erstellt. Backups werden an einem bestimmten Ort gespeichert und können sowohl durch automatisierte Prozesse als auch durch manuelle Befehle einfach verwaltet werden.

**So funktioniert es:**

1.  Ihre Datenbank wird automatisch gemäß dem von Ihnen festgelegten Zeitplan (täglich, wöchentlich oder monatlich) gesichert.
2.  Backups werden in einem angegebenen Verzeichnis auf Ihrem System gespeichert.
3.  Alte Backups werden automatisch basierend auf Ihren Aufbewahrungseinstellungen rotiert.
4.  Sie können jederzeit manuell Backups erstellen, vorhandene Backups auflisten oder eine Wiederherstellung aus einem Backup durchführen.
5.  Vor jeder Wiederherstellung wird der aktuelle Zustand als Sicherheitsmaßnahme automatisch gesichert.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Backup-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die Backup-Funktion ist standardmäßig aktiviert. Bei Bedarf können Sie dies mit der Einstellung `USE_BACKUP` steuern.
2.  **Backup-Zeitplan konfigurieren:** Wählen Sie mit dem Parameter `BACKUP_SCHEDULE`, wie oft Backups durchgeführt werden sollen.
3.  **Aufbewahrungsrichtlinie festlegen:** Geben Sie mit der Einstellung `BACKUP_ROTATION` an, wie viele Backups aufbewahrt werden sollen.
4.  **Speicherort festlegen:** Wählen Sie mit der Einstellung `BACKUP_DIRECTORY`, wo die Backups gespeichert werden sollen.
5.  **CLI-Befehle verwenden:** Verwalten Sie Backups bei Bedarf manuell mit den `bwcli plugin backup`-Befehlen.

### Konfigurationseinstellungen

| Einstellung        | Standard                     | Kontext | Mehrfach | Beschreibung                                                                                                         |
| ------------------ | ---------------------------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global  | nein     | **Backup aktivieren:** Auf `yes` setzen, um automatische Backups zu aktivieren.                                      |
| `BACKUP_SCHEDULE`  | `daily`                      | global  | nein     | **Backup-Frequenz:** Wie oft Backups durchgeführt werden sollen. Optionen: `daily`, `weekly` oder `monthly`.         |
| `BACKUP_ROTATION`  | `7`                          | global  | nein     | **Backup-Aufbewahrung:** Die Anzahl der aufzubewahrenden Backup-Dateien. Ältere Backups werden automatisch gelöscht. |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global  | nein     | **Backup-Speicherort:** Das Verzeichnis, in dem die Backup-Dateien gespeichert werden.                               |

### Befehlszeilenschnittstelle

Das Backup-Plugin bietet mehrere CLI-Befehle zur Verwaltung Ihrer Backups:

```bash
# Alle verfügbaren Backups auflisten
bwcli plugin backup list

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
Vor jeder Wiederherstellung erstellt das Backup-Plugin automatisch ein Backup des aktuellen Zustands Ihrer Datenbank an einem temporären Ort. Dies bietet eine zusätzliche Absicherung für den Fall, dass Sie die Wiederherstellung rückgängig machen müssen.

!!! warning "Datenbankkompatibilität"
Das Backup-Plugin unterstützt SQLite, MySQL/MariaDB und PostgreSQL-Datenbanken. Oracle-Datenbanken werden derzeit für Backup- und Wiederherstellungsvorgänge nicht unterstützt.

### Beispielkonfigurationen

=== "Tägliche Backups mit 7-tägiger Aufbewahrung"

    Standardkonfiguration, die tägliche Backups erstellt und die letzten 7 Dateien aufbewahrt:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Wöchentliche Backups mit erweiterter Aufbewahrung"

    Konfiguration für seltenere Backups mit längerer Aufbewahrung:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Monatliche Backups an einem benutzerdefinierten Speicherort"

    Konfiguration für monatliche Backups, die an einem benutzerdefinierten Ort gespeichert werden:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```
