Das PHP-Plugin bietet eine nahtlose Integration mit PHP-FPM für BunkerWeb und ermöglicht die dynamische PHP-Verarbeitung für Ihre Websites. Diese Funktion unterstützt sowohl lokale PHP-FPM-Instanzen, die auf derselben Maschine laufen, als auch entfernte PHP-FPM-Server, was Ihnen Flexibilität bei der Konfiguration Ihrer PHP-Umgebung gibt.

**So funktioniert es:**

1.  Wenn ein Client eine PHP-Datei von Ihrer Website anfordert, leitet BunkerWeb die Anfrage an die konfigurierte PHP-FPM-Instanz weiter.
2.  Bei lokalem PHP-FPM kommuniziert BunkerWeb mit dem PHP-Interpreter über eine Unix-Socket-Datei.
3.  Bei entferntem PHP-FPM leitet BunkerWeb Anfragen an den angegebenen Host und Port über das FastCGI-Protokoll weiter.
4.  PHP-FPM verarbeitet das Skript und gibt den generierten Inhalt an BunkerWeb zurück, das ihn dann an den Client ausliefert.
5.  Die URL-Umschreibung wird automatisch konfiguriert, um gängige PHP-Frameworks und Anwendungen zu unterstützen, die "schöne URLs" verwenden.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die PHP-Funktion zu konfigurieren und zu verwenden:

1.  **Wählen Sie Ihr PHP-FPM-Setup:** Entscheiden Sie, ob Sie eine lokale oder eine entfernte PHP-FPM-Instanz verwenden möchten.
2.  **Konfigurieren Sie die Verbindung:** Geben Sie für lokales PHP den Socket-Pfad an; für entferntes PHP geben Sie den Hostnamen und den Port an.
3.  **Legen Sie das Dokumentenstammverzeichnis fest:** Konfigurieren Sie den Stammordner, der Ihre PHP-Dateien enthält, mit der entsprechenden Pfadeinstellung.
4.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration leitet BunkerWeb PHP-Anfragen automatisch an Ihre PHP-FPM-Instanz weiter.

### Konfigurationseinstellungen

| Einstellung       | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                        |
| ----------------- | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
| `REMOTE_PHP`      |          | multisite | nein     | **Entfernter PHP-Host:** Hostname der entfernten PHP-FPM-Instanz. Leer lassen, um lokales PHP zu verwenden.         |
| `REMOTE_PHP_PATH` |          | multisite | nein     | **Entfernter Pfad:** Stammordner mit Dateien in der entfernten PHP-FPM-Instanz.                                     |
| `REMOTE_PHP_PORT` | `9000`   | multisite | nein     | **Entfernter Port:** Port der entfernten PHP-FPM-Instanz.                                                           |
| `LOCAL_PHP`       |          | multisite | nein     | **Lokaler PHP-Socket:** Pfad zur PHP-FPM-Socket-Datei. Leer lassen, um eine entfernte PHP-FPM-Instanz zu verwenden. |
| `LOCAL_PHP_PATH`  |          | multisite | nein     | **Lokaler Pfad:** Stammordner mit Dateien in der lokalen PHP-FPM-Instanz.                                           |

!!! tip "Lokales vs. entferntes PHP-FPM"
Wählen Sie das Setup, das am besten zu Ihrer Infrastruktur passt:

    - **Lokales PHP-FPM** bietet aufgrund der Socket-basierten Kommunikation eine bessere Leistung und ist ideal, wenn PHP auf derselben Maschine wie BunkerWeb läuft.
    - **Entferntes PHP-FPM** bietet mehr Flexibilität und Skalierbarkeit, indem die PHP-Verarbeitung auf separaten Servern erfolgen kann.

!!! warning "Pfadkonfiguration"
Der `REMOTE_PHP_PATH` oder `LOCAL_PHP_PATH` muss mit dem tatsächlichen Dateisystempfad übereinstimmen, in dem Ihre PHP-Dateien gespeichert sind; andernfalls tritt ein "Datei nicht gefunden"-Fehler auf.

!!! info "URL-Umschreibung"
Das PHP-Plugin konfiguriert automatisch die URL-Umschreibung, um moderne PHP-Anwendungen zu unterstützen. Anfragen für nicht existierende Dateien werden an `index.php` weitergeleitet, wobei die ursprüngliche Anfrage-URI als Abfrageparameter verfügbar ist.

### Beispielkonfigurationen

=== "Lokale PHP-FPM-Konfiguration"

    Konfiguration für die Verwendung einer lokalen PHP-FPM-Instanz:

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html"
    ```

=== "Entfernte PHP-FPM-Konfiguration"

    Konfiguration für die Verwendung einer entfernten PHP-FPM-Instanz:

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9000"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "Konfiguration mit benutzerdefiniertem Port"

    Konfiguration für die Verwendung von PHP-FPM auf einem nicht standardmäßigen Port:

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9001"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "WordPress-Konfiguration"

    Für WordPress optimierte Konfiguration:

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html/wordpress"
    ```
