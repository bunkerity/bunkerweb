Der GZIP-Plugin komprimiert HTTP-Antworten mit dem GZIP-Algorithmus, um die Bandbreite zu reduzieren und das Laden von Seiten zu beschleunigen.

### Funktionsweise

1. BunkerWeb erkennt, ob der Client GZIP unterstützt.
2. Falls ja, wird die Antwort auf dem konfigurierten Niveau komprimiert.
3. Die Header zeigen die Verwendung von GZIP an.
4. Der Browser dekomprimiert vor der Anzeige.

### Verwendung

1. Aktivieren: `USE_GZIP: yes` (standardmäßig deaktiviert).
2. MIME-Typen: `GZIP_TYPES` definieren.
3. Mindestgröße: `GZIP_MIN_LENGTH`, um sehr kleine Dateien zu vermeiden.
4. Kompressionsstufe: `GZIP_COMP_LEVEL` (1–9).
5. Proxied-Inhalt: `GZIP_PROXIED` anpassen.

### Parameter

| Parameter         | Standard                                                                                                                                                                                                                                                                                                                                                                                                                         | Kontext   | Mehrfach | Beschreibung                                                                                 |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------- |
| `USE_GZIP`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | Multisite | nein     | Aktiviert die GZIP-Kompression.                                                              |
| `GZIP_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | Multisite | nein     | Komprimierte MIME-Typen.                                                                     |
| `GZIP_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | Multisite | nein     | Mindestgröße (Bytes) für die Anwendung der Kompression.                                      |
| `GZIP_COMP_LEVEL` | `5`                                                                                                                                                                                                                                                                                                                                                                                                                              | Multisite | nein     | Stufe 1–9: höher = bessere Kompression, aber mehr CPU.                                       |
| `GZIP_PROXIED`    | `no-cache no-store private expired auth`                                                                                                                                                                                                                                                                                                                                                                                         | Multisite | nein     | Gibt an, welche proxied-Inhalte basierend auf den Antwort-Headern komprimiert werden sollen. |

!!! tip "Kompressionsstufe"
    `5` ist ein guter Kompromiss. Statisch/CPU verfügbar: 7–9. Dynamisch/CPU begrenzt: 1–3.

### Beispiele

=== "Standard"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json application/xml text/css text/html text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "5"
    ```

=== "Maximale Kompression"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "500"
    GZIP_COMP_LEVEL: "9"
    GZIP_PROXIED: "any"
    ```

=== "Ausgewogene Leistung"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "3"
    GZIP_PROXIED: "no-cache no-store private expired"
    ```

=== "Proxied-Inhalt"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "4"
    GZIP_PROXIED: "any"
    ```
