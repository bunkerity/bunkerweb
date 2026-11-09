Das Zstandard-Plugin komprimiert HTTP-Antworten mit dem Zstandard-Algorithmus (zstd). Es reduziert die Bandbreitennutzung bei Clients, die `Accept-Encoding: zstd` senden.

### So wird's verwendet

1. Aktivieren: Setzen Sie den Parameter `USE_ZSTD` auf `yes` (standardmäßig deaktiviert).
2. MIME-Typen und Mindestgröße: Definieren Sie die zu komprimierenden Inhalte über `ZSTD_TYPES` und die Mindestgröße einer Antwort über `ZSTD_MIN_LENGTH`.
3. Komprimierungsstufe: Setzen Sie `ZSTD_COMP_LEVEL` zwischen `1` (am schnellsten) und `19` (höchste unterstützte Komprimierung). Der Standardwert ist `3`.

Clients mit zstd-Unterstützung erhalten `Content-Encoding: zstd` und `Vary: Accept-Encoding`. Clients ohne zstd-Unterstützung, auch solche, die `zstd;q=0` senden, können Brotli oder gzip erhalten, sofern diese Plugins aktiviert sind. Andernfalls erhalten sie unkomprimierte Antworten.

Sind mehrere Komprimierungs-Plugins aktiviert, gilt die Server-Präferenz zstd, dann Brotli, dann gzip. Jede Codierung beachtet ihr eigenes `q=0`; positive Gewichtungen werden zwischen den Komprimierungs-Plugins nicht verglichen.

### Parameter

| Parameter         | Standard                                                                                                                                                                                                                                                                                                                                                                                                                         | Kontext   | Mehrfach | Beschreibung                                                                                          |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `USE_ZSTD`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | Multisite | nein     | Zstandard-Komprimierung von Antworten aktivieren.                                                     |
| `ZSTD_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | Multisite | nein     | Zu komprimierende MIME-Typen, zusätzlich zu `text/html`, das immer enthalten ist.                     |
| `ZSTD_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | Multisite | nein     | Mindestgröße einer Antwort in Bytes. Antworten unbekannter Länge können ebenfalls komprimiert werden. |
| `ZSTD_COMP_LEVEL` | `3`                                                                                                                                                                                                                                                                                                                                                                                                                              | Multisite | nein     | Komprimierungsstufe von `1` bis `19`. Höhere Stufen benötigen mehr CPU und Arbeitsspeicher.           |

!!! tip "Komprimierungsstufe"
    Beginnen Sie mit Stufe `3`. Höhere Stufen erhöhen den CPU- und Speicherbedarf pro Anfrage; halten Sie Kapazität für gleichzeitige Anfragen frei. Die Stufen sind auf `19` begrenzt, damit das 8-MB-zstd-Fenster-Limit für HTTP eingehalten wird.

!!! warning "Sensible Antworten"
    Die Komprimierung kann Geheimnisse über Unterschiede in der Antwortgröße offenlegen, wenn eine Antwort sowohl Geheimnisse als auch vom Angreifer kontrollierte Eingaben enthält. Deaktivieren Sie die Komprimierung für sensible Dienste oder begegnen Sie diesem Risiko in der Anwendung. `text/html` kommt bei aktiviertem zstd immer für die Komprimierung in Frage, auch wenn es in `ZSTD_TYPES` fehlt.

!!! info "Komprimierung durch den Upstream"
    Antworten, die der Upstream bereits komprimiert hat, werden nicht erneut komprimiert. Das Inject-Plugin benötigt eine unkomprimierte Upstream-Antwort, um HTML zu verändern; konfigurieren Sie den Upstream entsprechend, wenn Sie beide Funktionen nutzen.

### Beispielkonfiguration

Zstd mit Brotli- und gzip-Fallback aktivieren:

```yaml
USE_ZSTD: "yes"
ZSTD_MIN_LENGTH: "1000"
ZSTD_COMP_LEVEL: "3"
USE_BROTLI: "yes"
USE_GZIP: "yes"
```
