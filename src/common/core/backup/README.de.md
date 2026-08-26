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
3.  **Aufbewahrungsrichtlinie festlegen:** Geben Sie mit der Einstellung `BACKUP_ROTATION` an, wie viele Backups aufbewahrt werden sollen. Welche davon aufbewahrt werden, entscheidet `BACKUP_ROTATION_STRATEGY`, standardmäßig `hanoi`.
4.  **Speicherort festlegen:** Wählen Sie mit der Einstellung `BACKUP_DIRECTORY`, wo die Backups gespeichert werden sollen.
5.  **CLI-Befehle verwenden:** Verwalten Sie Backups bei Bedarf manuell mit den `bwcli plugin backup`-Befehlen.

### Konfigurationseinstellungen

| Einstellung        | Standard                     | Kontext | Mehrfach | Beschreibung                                                                                                         |
| ------------------ | ---------------------------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global  | nein     | **Backup aktivieren:** Auf `yes` setzen, um automatische Backups zu aktivieren.                                      |
| `BACKUP_SCHEDULE`  | `daily`                      | global  | nein     | **Backup-Frequenz:** Wie oft Backups durchgeführt werden sollen. Optionen: `daily`, `weekly` oder `monthly`.         |
| `BACKUP_ROTATION`  | `7`                          | global  | nein     | **Backup-Aufbewahrung:** Die Anzahl der aufzubewahrenden Backup-Dateien. Backups über diese Anzahl hinaus werden automatisch gelöscht. |
| `BACKUP_ROTATION_STRATEGY` | `hanoi`              | global  | nein     | **Rotationsstrategie:** Wie Backups zum Löschen ausgewählt werden, sobald das Limit erreicht ist. `hanoi` behält eine Türme-von-Hanoi-Leiter — fein nahe der Gegenwart, exponentiell gröber weiter zurück; `fifo` behält die neuesten. Beide behalten dieselbe Anzahl an Dateien. |
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

    Ein Backup kann nur in die Datenbank-Engine zurückgespielt werden, aus der es stammt — die Engine ist Teil des Dateinamens (`backup-mariadb-…`), und eine Wiederherstellung in eine andere wird abgelehnt, bevor irgendetwas angefasst wird. Wenn Sie zwischen Engines migriert sind, bleiben beide Backup-Sätze im Verzeichnis: `restore` ohne Argument nimmt die neueste Datei jeder beliebigen Engine, geben Sie den Pfad also ausdrücklich an, um ein älteres Backup Ihrer aktuellen Engine wiederherzustellen.

### Beispielkonfigurationen

=== "Tägliche Backups mit Aufbewahrung von 7 Dateien"

    Standardkonfiguration: tägliche Backups, 7 aufbewahrte Dateien, verteilt durch die Türme-von-Hanoi-Leiter.

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Tägliche Backups, letzte 7 Tage (FIFO)"

    Der bisherige Standard: die 7 neuesten Dateien und nichts Älteres.

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_ROTATION_STRATEGY: "fifo"
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

=== "Tägliche Backups mit größerer Tiefe"

    24 Dateien, durch die Standard-Leiter verteilt, statt nur die letzten 24 Tage abzudecken. Die
    neuesten Backups werden in voller Granularität aufbewahrt, ältere exponentiell ausgedünnt, so
    dass der älteste Wiederherstellungspunkt bei jeder Verdopplung des Alters der Installation
    weiter zurückrückt — ein spät bemerktes Problem bleibt wiederherstellbar:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "24"
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

!!! info "Welche Backups aufbewahrt werden"
    `hanoi` ist der Standard. Beide Strategien löschen dieselbe **Anzahl** an Dateien — `hanoi`
    entfernt nie mehr Backups als `fifo` es täte — aber sie löschen nicht dieselben, und der
    Unterschied liegt nicht nur am alten Ende. Die Leiter erkauft ihre Tiefe damit, dass sie auch
    das jüngste Fenster ausdünnt: bei täglichem Zeitplan und dem Standard `BACKUP_ROTATION: "7"`
    behält ein eingelaufenes Archiv je ein Backup aus den Fenstern der letzten etwa 1, 2, 4, 8, 16
    und 32 Tage — Alter von rund 0, 1, 2–3, 4–7, 8–15, 16–31 und 32–63 Tagen, wobei das genaue
    Alter davon abhängt, wo der aktuelle Tag auf dem festen Raster der Leiter liegt — während
    `fifo` die letzten 7 Tage behält. **Drei oder vier der letzten sieben Tage werden aufgegeben**,
    im Tausch gegen diese älteren Wiederherstellungspunkte.
    Das neueste Backup wird immer behalten; bei einem Backup pro Tag und einem `BACKUP_ROTATION`
    von mindestens 2 auch die beiden neuesten Tage. Der Tausch fällt milder aus, je größer
    `BACKUP_ROTATION` ist — bei `"24"` bleiben etwa die letzten drei Wochen zusammenhängend, eine
    Spanne, die mit dem Alter des Archivs langsam schrumpft.

    **Mehrere Backups desselben Tages zählen als ein Wiederherstellungspunkt, und die
    überzähligen sind die ersten Dateien, die eine Rotation aufgibt** — noch vor allem Älteren. Nur
    das neueste Backup jedes Tages überlebt, sobald das Dateibudget aufgebraucht ist. Ein manuelles
    Backup vor einer riskanten Änderung ist also nur bis zum nächsten Backup desselben Tages
    sicher, und indem es zum neuesten dieses Tages wird, verdrängt es das geplante Backup des
    Tages, das dann gelöscht wird. Mit `fifo` hätten Sie beide behalten.

    Nichts, was bereits auf der Platte liegt, wird durch das Upgrade selbst gelöscht — die
    Änderung greift bei der nächsten Rotation. Setzen Sie `BACKUP_ROTATION_STRATEGY: "fifo"` für
    das bisherige Verhalten. Jede Löschung wird mit dem Grund protokolliert, aus dem die Datei
    ausgewählt wurde.

!!! info "Wie die Leiter aufgebaut ist"
    Die Leiter zählt in **Perioden**, und eine Periode ist ein `BACKUP_SCHEDULE`: ein Tag bei
    `daily`, sieben bei `weekly`, achtundzwanzig (vier Wochen, kein Kalendermonat) bei `monthly`.
    Alle Backups innerhalb einer Periode sind derselbe Wiederherstellungspunkt, und das neueste
    davon vertritt ihn.

    `BACKUP_ROTATION` ist zugleich das Dateibudget und die Tiefe der Leiter: sie baut
    `BACKUP_ROTATION - 1` Ebenen, wobei Ebene `k` die Zeitachse in feste Blöcke von `2^k` Perioden
    schneidet und das älteste Backup ihrer beiden jüngsten nicht leeren Blöcke behält, mit dem
    neuesten Backup stets obenauf angeheftet. Jede Ebene kostet höchstens eine Datei mehr als die
    darunter, so dass die ganze Leiter ins Budget passt — während ihre Reichweite sich mit jeder
    Ebene verdoppelt. Ihre tiefsten Blöcke sind `2^(BACKUP_ROTATION - 2)` Perioden breit, so dass
    der älteste Wiederherstellungspunkt bei täglichem Zeitplan zwischen **32 und 63 Tagen** zurück
    liegt (Standard `BACKUP_ROTATION: "7"`) und zwischen **1024 und 2047 Tagen** bei `"12"` — die
    Zahl der Dateien wächst linear, die Tiefe exponentiell. `fifo` reicht bei gleichem Budget nie
    weiter zurück als `BACKUP_ROTATION` Perioden.

    Die Blöcke liegen auf einem absoluten Raster statt auf Fenstern, die von heute zurück gemessen
    werden, und genau das macht eine Löschung sicher: ein Backup, das die Leiter fahren lässt, kann
    nie wieder gebraucht werden, weshalb die tiefen Ebenen sich mit der Zeit nicht leeren. Es heißt
    aber auch, dass die Leiter sich **mit dem Alter des Archivs füllt** — Ebene `k` zu erreichen
    dauert `2^k` Perioden, eine junge Installation behält also alles, was sie hat, und die tiefen
    Wiederherstellungspunkte entstehen erst mit der Zeit. Bis dahin geht das nicht ausgeschöpfte
    Budget an die neuesten Backups, in voller Granularität.

!!! info "Wie Backups datiert werden"
    Die Rotation liest den Zeitstempel im Namen jedes Archivs. Ein Archiv, dessen Name keinen
    brauchbaren trägt — eine von Hand hineinkopierte oder umbenannte Datei — wird stattdessen über
    seine Änderungszeit datiert, unter beiden Strategien.
