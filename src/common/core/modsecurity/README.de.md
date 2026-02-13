Das ModSecurity-Plugin integriert die leistungsstarke [ModSecurity](https://modsecurity.org) Web Application Firewall (WAF) in BunkerWeb. Diese Integration bietet robusten Schutz gegen eine Vielzahl von Webangriffen, indem sie das [OWASP Core Rule Set (CRS)](https://coreruleset.org) nutzt, um Bedrohungen wie SQL-Injection, Cross-Site-Scripting (XSS), Local File Inclusion und mehr zu erkennen und zu blockieren.

**So funktioniert es:**

1.  Wenn eine Anfrage empfangen wird, bewertet ModSecurity sie anhand des aktiven Regelsatzes.
2.  Das OWASP Core Rule Set überprüft Header, Cookies, URL-Parameter und den Body-Inhalt.
3.  Jeder erkannte Verstoß trägt zu einem Gesamt-Anomalie-Score bei.
4.  Wenn dieser Score den konfigurierten Schwellenwert überschreitet, wird die Anfrage blockiert.
5.  Detaillierte Protokolle werden erstellt, um zu diagnostizieren, welche Regeln ausgelöst wurden und warum.

!!! success "Wichtige Vorteile"

      1. **Branchenstandard-Schutz:** Verwendet die weit verbreitete Open-Source-Firewall ModSecurity.
      2. **OWASP Core Rule Set:** Verwendet von der Community gepflegte Regeln, die die OWASP Top Ten und mehr abdecken.
      3. **Konfigurierbare Sicherheitsstufen:** Passen Sie die Paranoia-Stufen an, um die Sicherheit mit potenziellen Falsch-Positiven auszugleichen.
      4. **Detaillierte Protokollierung:** Bietet gründliche Audit-Protokolle zur Analyse von Angriffen.
      5. **Plugin-Unterstützung:** Erweitern Sie den Schutz mit optionalen CRS-Plugins, die auf Ihre Anwendungen zugeschnitten sind.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um ModSecurity zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** ModSecurity ist standardmäßig aktiviert. Dies kann mit der Einstellung `USE_MODSECURITY` gesteuert werden.
2.  **Wählen Sie eine CRS-Version:** Wählen Sie eine Version des OWASP Core Rule Set (v3, v4 oder nightly).
3.  **Plugins hinzufügen:** Aktivieren Sie optional CRS-Plugins, um die Regelabdeckung zu verbessern.
4.  **Überwachen und anpassen:** Verwenden Sie Protokolle und die [Web-Benutzeroberfläche](web-ui.md), um Falsch-Positive zu identifizieren und die Einstellungen anzupassen.

### Konfigurationseinstellungen

| Einstellung                           | Standard       | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                    |
| ------------------------------------- | -------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MODSECURITY`                     | `yes`          | multisite | nein     | **ModSecurity aktivieren:** Schalten Sie den Schutz der ModSecurity Web Application Firewall ein.                                                                               |
| `USE_MODSECURITY_CRS`                 | `yes`          | multisite | nein     | **Core Rule Set verwenden:** Aktivieren Sie das OWASP Core Rule Set für ModSecurity.                                                                                            |
| `MODSECURITY_CRS_VERSION`             | `4`            | multisite | nein     | **CRS-Version:** Die Version des zu verwendenden OWASP Core Rule Set. Optionen: `3`, `4` oder `nightly`.                                                                        |
| `MODSECURITY_SEC_RULE_ENGINE`         | `On`           | multisite | nein     | **Regel-Engine:** Steuern Sie, ob Regeln erzwungen werden. Optionen: `On`, `DetectionOnly` oder `Off`.                                                                          |
| `MODSECURITY_SEC_AUDIT_ENGINE`        | `RelevantOnly` | multisite | nein     | **Audit-Engine:** Steuern Sie, wie die Audit-Protokollierung funktioniert. Optionen: `On`, `Off` oder `RelevantOnly`.                                                           |
| `MODSECURITY_SEC_AUDIT_LOG_PARTS`     | `ABIJDEFHZ`    | multisite | nein     | **Audit-Protokoll-Teile:** Welche Teile von Anfragen/Antworten in Audit-Protokolle aufgenommen werden sollen.                                                                   |
| `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` | `131072`       | multisite | nein     | **Anforderungskörper-Limit (keine Dateien):** Maximale Größe für Anforderungskörper ohne Datei-Uploads. Akzeptiert einfache Bytes oder menschenlesbare Suffixe (`k`, `m`, `g`). |
| `USE_MODSECURITY_CRS_PLUGINS`         | `yes`          | multisite | nein     | **CRS-Plugins aktivieren:** Aktivieren Sie zusätzliche Plugin-Regelsätze für das Core Rule Set.                                                                                 |
| `MODSECURITY_CRS_PLUGINS`             |                | multisite | nein     | **CRS-Plugin-Liste:** Leerzeichengetrennte Liste von Plugins zum Herunterladen und Installieren (`plugin-name[/tag]` oder URL).                                                 |
| `USE_MODSECURITY_GLOBAL_CRS`          | `no`           | global    | nein     | **Globales CRS:** Wenn aktiviert, werden CRS-Regeln global auf HTTP-Ebene anstatt pro Server angewendet.                                                                        |

!!! warning "ModSecurity und das OWASP Core Rule Set"
    **Wir empfehlen dringend, sowohl ModSecurity als auch das OWASP Core Rule Set (CRS) aktiviert zu lassen**, um einen robusten Schutz gegen gängige Web-Schwachstellen zu bieten. Obwohl gelegentlich Falsch-Positive auftreten können, können diese mit etwas Aufwand durch Feinabstimmung von Regeln oder die Verwendung vordefinierter Ausschlüsse behoben werden.

    Das CRS-Team pflegt aktiv eine Liste von Ausschlüssen für beliebte Anwendungen wie WordPress, Nextcloud, Drupal und Cpanel, was die Integration erleichtert, ohne die Funktionalität zu beeinträchtigen. Die Sicherheitsvorteile überwiegen bei weitem den minimalen Konfigurationsaufwand, der zur Behebung von Falsch-Positiven erforderlich ist.

### Verfügbare CRS-Versionen

Wählen Sie eine CRS-Version, die Ihren Sicherheitsanforderungen am besten entspricht:

- **`3`**: Stabile [v3.3.8](https://github.com/coreruleset/coreruleset/releases/tag/v3.3.8).
- **`4`**: Stabile [v4.23.0](https://github.com/coreruleset/coreruleset/releases/tag/v4.23.0) (**Standard**).
- **`nightly`**: [Nightly-Build](https://github.com/coreruleset/coreruleset/releases/tag/nightly) mit den neuesten Regel-Updates.

!!! example "Nightly-Build"
    Der **Nightly-Build** enthält die aktuellsten Regeln und bietet den neuesten Schutz gegen aufkommende Bedrohungen. Da er jedoch täglich aktualisiert wird und experimentelle oder ungetestete Änderungen enthalten kann, wird empfohlen, den Nightly-Build zunächst in einer **Staging-Umgebung** zu verwenden, bevor er in der Produktion eingesetzt wird.

!!! tip "Paranoia-Stufen"
    Das OWASP Core Rule Set verwendet "Paranoia-Stufen" (PL), um die Strenge der Regeln zu steuern:

    - **PL1 (Standard):** Grundlegender Schutz mit minimalen Falsch-Positiven
    - **PL2:** Strengere Sicherheit mit strengerem Musterabgleich
    - **PL3:** Erhöhte Sicherheit mit strengerer Validierung
    - **PL4:** Maximale Sicherheit mit sehr strengen Regeln (kann viele Falsch-Positive verursachen)

    Sie können die Paranoia-Stufe festlegen, indem Sie eine benutzerdefinierte Konfigurationsdatei in `/etc/bunkerweb/configs/modsec-crs/` hinzufügen.

### Benutzerdefinierte Konfigurationen {#custom-configurations}

Die Feinabstimmung von ModSecurity und dem OWASP Core Rule Set (CRS) kann durch benutzerdefinierte Konfigurationen erreicht werden. Diese Konfigurationen ermöglichen es Ihnen, das Verhalten in bestimmten Phasen der Verarbeitung von Sicherheitsregeln anzupassen:

- **`modsec-crs`**: Wird **vor** dem Laden des OWASP Core Rule Set angewendet.
- **`modsec`**: Wird **nach** dem Laden des OWASP Core Rule Set angewendet. Dies wird auch verwendet, wenn das CRS überhaupt nicht geladen wird.
- **`crs-plugins-before`**: Wird **vor** dem Laden der CRS-Plugins angewendet.
- **`crs-plugins-after`**: Wird **nach** dem Laden der CRS-Plugins angewendet.

Diese Struktur bietet Flexibilität und ermöglicht es Ihnen, die Einstellungen von ModSecurity und CRS an die spezifischen Anforderungen Ihrer Anwendung anzupassen, während ein klarer Konfigurationsfluss beibehalten wird.

#### Hinzufügen von CRS-Ausschlüssen mit `modsec-crs`

Sie können eine benutzerdefinierte Konfiguration vom Typ `modsec-crs` verwenden, um Ausschlüsse für bestimmte Anwendungsfälle hinzuzufügen, z. B. das Aktivieren vordefinierter Ausschlüsse für WordPress:

```conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"
```

In diesem Beispiel:

- Die Aktion wird in **Phase 1** (früh im Anfrage-Lebenszyklus) ausgeführt.
- Sie aktiviert WordPress-spezifische CRS-Ausschlüsse, indem sie die Variable `tx.crs_exclusions_wordpress` setzt.

#### Aktualisieren von CRS-Regeln mit `modsec`

Um die geladenen CRS-Regeln zu optimieren, können Sie eine benutzerdefinierte Konfiguration vom Typ `modsec` verwenden. Sie können beispielsweise bestimmte Regeln oder Tags für bestimmte Anfragepfade entfernen:

```conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"
```

In diesem Beispiel:

- **Regel 1**: Entfernt Regeln mit den Tags `attack-xss` und `attack-rce` für Anfragen an `/wp-admin/admin-ajax.php`.
- **Regel 2**: Entfernt Regeln mit dem Tag `attack-xss` für Anfragen an `/wp-admin/options.php`.
- **Regel 3**: Entfernt eine bestimmte Regel (ID `930120`) für Anfragen, die auf `/wp-json/yoast` passen.

!!! info "Reihenfolge der Ausführung"
    Die Ausführungsreihenfolge für ModSecurity in BunkerWeb ist wie folgt, um eine klare und logische Abfolge der Regelanwendung zu gewährleisten:

    1.  **OWASP CRS-Konfiguration**: Basiskonfiguration für das OWASP Core Rule Set.
    2.  **Konfiguration benutzerdefinierter Plugins (`crs-plugins-before`)**: Einstellungen, die für Plugins spezifisch sind und vor allen CRS-Regeln angewendet werden.
    3.  **Regeln benutzerdefinierter Plugins (vor CRS-Regeln) (`crs-plugins-before`)**: Benutzerdefinierte Regeln für Plugins, die vor den CRS-Regeln ausgeführt werden.
    4.  **Konfiguration heruntergeladener Plugins**: Konfiguration für extern heruntergeladene Plugins.
    5.  **Regeln heruntergeladener Plugins (vor CRS-Regeln)**: Regeln für heruntergeladene Plugins, die vor den CRS-Regeln ausgeführt werden.
    6.  **Benutzerdefinierte CRS-Regeln (`modsec-crs`)**: Benutzerdefinierte Regeln, die vor dem Laden der CRS-Regeln angewendet werden.
    7.  **OWASP CRS-Regeln**: Der Kernsatz von Sicherheitsregeln, der von OWASP bereitgestellt wird.
    8.  **Regeln benutzerdefinierter Plugins (nach CRS-Regeln) (`crs-plugins-after`)**: Benutzerdefinierte Plugin-Regeln, die nach den CRS-Regeln ausgeführt werden.
    9.  **Regeln heruntergeladener Plugins (nach CRS-Regeln)**: Regeln für heruntergeladene Plugins, die nach den CRS-Regeln ausgeführt werden.
    10. **Benutzerdefinierte Regeln (`modsec`)**: Benutzerdefinierte Regeln, die nach allen CRS- und Plugin-Regeln angewendet werden.

    **Wichtige Hinweise**:

    -   **Pre-CRS-Anpassungen** (`crs-plugins-before`, `modsec-crs`) ermöglichen es Ihnen, Ausnahmen oder vorbereitende Regeln zu definieren, bevor die Kern-CRS-Regeln geladen werden.
    -   **Post-CRS-Anpassungen** (`crs-plugins-after`, `modsec`) sind ideal, um Regeln zu überschreiben oder zu erweitern, nachdem CRS- und Plugin-Regeln angewendet wurden.
    -   Diese Struktur bietet maximale Flexibilität und ermöglicht eine präzise Steuerung der Regelausführung und -anpassung bei gleichzeitiger Aufrechterhaltung einer starken Sicherheitsgrundlage.

### OWASP CRS-Plugins

Das OWASP Core Rule Set unterstützt auch eine Reihe von **Plugins**, die entwickelt wurden, um seine Funktionalität zu erweitern und die Kompatibilität mit bestimmten Anwendungen oder Umgebungen zu verbessern. Diese Plugins können dabei helfen, das CRS für die Verwendung mit beliebten Plattformen wie WordPress, Nextcloud und Drupal oder sogar benutzerdefinierten Setups zu optimieren. Weitere Informationen und eine Liste der verfügbaren Plugins finden Sie im [OWASP CRS Plugin-Verzeichnis](https://github.com/coreruleset/plugin-registry).

!!! tip "Plugin-Download"
    Die Einstellung `MODSECURITY_CRS_PLUGINS` ermöglicht es Ihnen, Plugins herunterzuladen und zu installieren, um die Funktionalität des OWASP Core Rule Set (CRS) zu erweitern. Diese Einstellung akzeptiert eine Liste von Plugin-Namen mit optionalen Tags oder URLs, was es einfach macht, zusätzliche Sicherheitsfunktionen zu integrieren, die auf Ihre spezifischen Bedürfnisse zugeschnitten sind.

    Hier ist eine nicht erschöpfende Liste der akzeptierten Werte für die Einstellung `MODSECURITY_CRS_PLUGINS`:

    *   `fake-bot` - Lädt die neueste Version des Plugins herunter.
    *   `wordpress-rule-exclusions/v1.0.0` - Lädt die Version 1.0.0 des Plugins herunter.
    *   `https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip` - Lädt das Plugin direkt von der URL herunter.

!!! warning "Falsch-Positive"
    Höhere Sicherheitseinstellungen können legitimen Verkehr blockieren. Beginnen Sie mit den Standardeinstellungen und überwachen Sie die Protokolle, bevor Sie die Sicherheitsstufen erhöhen. Seien Sie bereit, Ausnahmeregeln für die spezifischen Anforderungen Ihrer Anwendung hinzuzufügen.

### Beispielkonfigurationen

=== "Grundlegende Konfiguration"

    Eine Standardkonfiguration mit aktiviertem ModSecurity und CRS v4:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "Nur-Erkennungsmodus"

    Konfiguration zur Überwachung potenzieller Bedrohungen ohne Blockierung:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "DetectionOnly"
    MODSECURITY_SEC_AUDIT_ENGINE: "On"
    MODSECURITY_SEC_AUDIT_LOG_PARTS: "ABIJDEFHZ"
    ```

=== "Erweiterte Konfiguration mit Plugins"

    Konfiguration mit CRS v4 und aktivierten Plugins für zusätzlichen Schutz:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions fake-bot"
    MODSECURITY_REQ_BODY_NO_FILES_LIMIT: "262144"
    ```

=== "Legacy-Konfiguration"

    Konfiguration mit CRS v3 zur Kompatibilität mit älteren Setups:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "3"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "Globales ModSecurity"

    Konfiguration, die ModSecurity global auf alle HTTP-Verbindungen anwendet:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    USE_MODSECURITY_GLOBAL_CRS: "yes"
    ```

=== "Nightly-Build mit benutzerdefinierten Plugins"

    Konfiguration mit dem Nightly-Build von CRS mit benutzerdefinierten Plugins:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "nightly"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions/v1.0.0 https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip"
    ```

!!! note "Menschenlesbare Größenwerte"
    Für Größeneinstellungen wie `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` werden die Suffixe `k`, `m` und `g` (Groß- und Kleinschreibung wird nicht beachtet) unterstützt und stehen für Kibibyte, Mebibyte und Gibibyte (Vielfache von 1024). Beispiele: `256k` = 262144, `1m` = 1048576, `2g` = 2147483648.
