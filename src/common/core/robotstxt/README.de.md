Das Robots.txt-Plugin verwaltet die Datei [robots.txt](https://www.robotstxt.org/) für Ihre Website. Diese Datei teilt Web-Crawlern und Robotern mit, auf welche Teile Ihrer Website sie zugreifen dürfen und auf welche nicht.

**So funktioniert es:**

Wenn aktiviert, generiert BunkerWeb dynamisch die `/robots.txt`-Datei im Stammverzeichnis Ihrer Website. Die Regeln in dieser Datei werden in der folgenden Reihenfolge aus mehreren Quellen zusammengefasst:

1.  **DarkVisitors-API:** Wenn `ROBOTSTXT_DARKVISITORS_TOKEN` angegeben ist, werden Regeln von der [DarkVisitors](https://darkvisitors.com/)-API abgerufen, was eine dynamische Blockierung bösartiger Bots und KI-Crawler basierend auf konfigurierten Agententypen und nicht zugelassenen Benutzeragenten ermöglicht.
2.  **Community-Listen:** Regeln aus vordefinierten, von der Community gepflegten `robots.txt`-Listen (angegeben durch `ROBOTSTXT_COMMUNITY_LISTS`) werden einbezogen.
3.  **Benutzerdefinierte URLs:** Regeln werden von vom Benutzer bereitgestellten URLs abgerufen (angegeben durch `ROBOTSTXT_URLS`).
4.  **Manuelle Regeln:** Regeln, die direkt über `ROBOTSTXT_RULE`-Umgebungsvariablen definiert werden, werden hinzugefügt.

Alle Regeln aus diesen Quellen werden kombiniert. Nach der Aggregation werden `ROBOTSTXT_IGNORE_RULE` angewendet, um unerwünschte Regeln mit PCRE-Regex-Mustern herauszufiltern. Wenn nach diesem gesamten Prozess keine Regeln mehr übrig sind, wird automatisch eine Standardregel `User-agent: *` und `Disallow: /` angewendet, um einen grundlegenden Schutz zu gewährleisten. Optionale Sitemap-URLs (angegeben durch `ROBOTSTXT_SITEMAP`) werden ebenfalls in die endgültige `robots.txt`-Ausgabe aufgenommen.

### Dynamische Bot-Umgehung mit der DarkVisitors-API

[DarkVisitors](https://darkvisitors.com/) ist ein Dienst, der eine dynamische `robots.txt`-Datei bereitstellt, um bekannte bösartige Bots und KI-Crawler zu blockieren. Durch die Integration mit DarkVisitors kann BunkerWeb automatisch eine aktuelle `robots.txt` abrufen und bereitstellen, die Ihre Website vor unerwünschtem automatisiertem Datenverkehr schützt.

Um dies zu aktivieren, müssen Sie sich bei [darkvisitors.com](https://darkvisitors.com/docs/robots-txt) anmelden und ein Bearer-Token erhalten.

### Wie man es benutzt

1.  **Aktivieren Sie die Funktion:** Setzen Sie die Einstellung `USE_ROBOTSTXT` auf `yes`.
2.  **Regeln konfigurieren:** Wählen Sie eine oder mehrere Methoden, um Ihre `robots.txt`-Regeln zu definieren:
    - **DarkVisitors-API:** Geben Sie `ROBOTSTXT_DARKVISITORS_TOKEN` und optional `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` und `ROBOTSTXT_DARKVISITORS_DISALLOW` an.
    - **Community-Listen:** Geben Sie `ROBOTSTXT_COMMUNITY_LISTS` an (durch Leerzeichen getrennte IDs).
    - **Benutzerdefinierte URLs:** Geben Sie `ROBOTSTXT_URLS` an (durch Leerzeichen getrennte URLs).
    - **Manuelle Regeln:** Verwenden Sie `ROBOTSTXT_RULE` für einzelne Regeln (mehrere Regeln können mit `ROBOTSTXT_RULE_N` angegeben werden).
3.  **Regeln filtern (optional):** Verwenden Sie `ROBOTSTXT_IGNORE_RULE_N`, um bestimmte Regeln nach Regex-Muster auszuschließen.
4.  **Sitemaps hinzufügen (optional):** Verwenden Sie `ROBOTSTXT_SITEMAP_N` für Sitemap-URLs.
5.  **Die generierte robots.txt-Datei abrufen:** Sobald BunkerWeb mit den obigen Einstellungen läuft, können Sie auf die dynamisch generierte `robots.txt`-Datei zugreifen, indem Sie eine HTTP-GET-Anfrage an `http(s)://your-domain.com/robots.txt` senden.

### Konfigurationseinstellungen

| Einstellung                          | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                                     |
| ------------------------------------ | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_ROBOTSTXT`                      | `no`     | multisite | Nein     | Aktiviert oder deaktiviert die `robots.txt`-Funktion.                                                                                            |
| `ROBOTSTXT_DARKVISITORS_TOKEN`       |          | multisite | Nein     | Bearer-Token für die DarkVisitors-API.                                                                                                           |
| `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` |          | multisite | Nein     | Kommagetrennte Liste von Agententypen (z. B. `AI Data Scraper`), die von DarkVisitors einbezogen werden sollen.                                  |
| `ROBOTSTXT_DARKVISITORS_DISALLOW`    | `/`      | multisite | Nein     | Ein String, der angibt, welche URLs nicht erlaubt sind. Dieser Wert wird als Disallow-Feld gesendet, wenn die DarkVisitors-API kontaktiert wird. |
| `ROBOTSTXT_COMMUNITY_LISTS`          |          | multisite | Nein     | Leerzeichengetrennte Liste von von der Community gepflegten Regelsatz-IDs, die einbezogen werden sollen.                                         |
| `ROBOTSTXT_URLS`                     |          | multisite | Nein     | Leerzeichengetrennte Liste von URLs, von denen zusätzliche `robots.txt`-Regeln abgerufen werden sollen. Unterstützt `file://` und Basic-Auth.    |
| `ROBOTSTXT_RULE`                     |          | multisite | Ja       | Eine einzelne Regel für `robots.txt`.                                                                                                            |
| `ROBOTSTXT_HEADER`                   |          | multisite | Ja       | Kopfzeile für die `robots.txt`-Datei (vor den Regeln). Kann Base64-kodiert sein.                                                                 |
| `ROBOTSTXT_FOOTER`                   |          | multisite | Ja       | Fußzeile für die `robots.txt`-Datei (nach den Regeln). Kann Base64-kodiert sein.                                                                 |
| `ROBOTSTXT_IGNORE_RULE`              |          | multisite | Ja       | Ein einzelnes PCRE-Regex-Muster zum Ignorieren von Regeln.                                                                                       |
| `ROBOTSTXT_SITEMAP`                  |          | multisite | Ja       | Eine einzelne Sitemap-URL.                                                                                                                       |

### Beispielkonfigurationen

**Grundlegende manuelle Regeln**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**Verwendung dynamischer Quellen (DarkVisitors & Community-Liste)**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "ihr-darkvisitors-token-hier"
ROBOTSTXT_DARKVISITORS_AGENT_TYPES: "AI Data Scraper"
ROBOTSTXT_COMMUNITY_LISTS: "robots-disallowed"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
```

**Kombinierte Konfiguration**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "ihr-darkvisitors-token-hier"
ROBOTSTXT_COMMUNITY_LISTS: "ai-robots-txt"
ROBOTSTXT_URLS: "https://example.com/my-custom-rules.txt"
ROBOTSTXT_RULE: "User-agent: MyOwnBot"
ROBOTSTXT_RULE_1: "Disallow: /admin"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**Mit Kopf- und Fußzeile**

````yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_HEADER: "# Dies ist eine benutzerdefinierte Kopfzeile"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_FOOTER: "# Dies ist eine benutzerdefinierte Fußzeile"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"```

---

Weitere Informationen finden Sie in der [robots.txt-Dokumentation](https://www.robotstxt.org/robotstxt.html).
````
