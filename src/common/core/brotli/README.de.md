Das Brotli-Plugin aktiviert die Komprimierung von HTTP-Antworten mit dem Brotli-Algorithmus. Es reduziert die Bandbreitennutzung and beschleunigt das Laden, indem es Inhalte vor dem Senden an den Browser komprimiert.

Im Vergleich zu Gzip erreicht Brotli in der Regel bessere Kompressionsraten, was zu kleineren Dateien and einer schnelleren Bereitstellung führt.

So funktioniert's:

1. Auf Anfrage eines Clients prüft BunkerWeb, ob der Browser Brotli unterstützt.
2. Wenn ja, wird die Antwort auf dem konfigurierten Niveau (`BROTLI_COMP_LEVEL`) komprimiert.
3. Die entsprechenden Header zeigen die Brotli-Komprimierung an.
4. Der Browser dekomprimiert vor der Anzeige.
5. Bandbreite and Ladezeiten nehmen ab.

### So wird's verwendet

1. Aktivieren: `USE_BROTLI: yes` (standardmäßig deaktiviert).
2. MIME-Typen: Definieren Sie die zu komprimierenden Inhalte über `BROTLI_TYPES`.
3. Mindestgröße: `BROTLI_MIN_LENGTH`, um die Komprimierung kleiner Antworten zu vermeiden.
4. Komprimierungsstufe: `BROTLI_COMP_LEVEL` für das Gleichgewicht zwischen Geschwindigkeit and Verhältnis.

### Parameter

| Parameter           | Standard                                                                                                                                                                                                                                                                                                                                                                                                                         | Kontext   | Mehrfach | Beschreibung                                              |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | --------------------------------------------------------- |
| `USE_BROTLI`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | Multisite | nein     | Brotli-Komprimierung aktivieren.                          |
| `BROTLI_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | Multisite | nein     | Komprimierte MIME-Typen.                                  |
| `BROTLI_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | Multisite | nein     | Mindestgröße (Bytes) für die Anwendung der Komprimierung. |
| `BROTLI_COMP_LEVEL` | `6`                                                                                                                                                                                                                                                                                                                                                                                                                              | Multisite | nein     | Stufe 0–11: höher = bessere Komprimierung, aber mehr CPU. |

!!! tip "Komprimierungsstufe"
`6` bietet einen guten Kompromiss. Für statische Inhalte and verfügbare CPU: 9–11. Für dynamische Inhalte oder bei CPU-Einschränkungen: 4–5.

### Beispiele

=== "Basis"

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json application/xml application/xhtml+xml text/css text/html text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "6"
    ```

=== "Maximale Komprimierung"

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "500"
    BROTLI_COMP_LEVEL: "11"
    ```

=== "Ausgewogene Leistung"

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "4"
    ```
