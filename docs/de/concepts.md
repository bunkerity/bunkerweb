# Konzepte

## Architektur

<figure markdown>
  ![Übersicht](assets/img/concepts.svg){ align=center, width="600" }
</figure>

Innerhalb Ihrer Infrastruktur agiert BunkerWeb als Reverse-Proxy vor Ihren Webdiensten. Die typische Architektur beinhaltet den Zugriff auf BunkerWeb aus dem Internet, das dann Anfragen an den entsprechenden Anwendungsdienst in einem sicheren Netzwerk weiterleitet.

Die Verwendung von BunkerWeb auf diese Weise (klassische Reverse-Proxy-Architektur) mit TLS-Offloading und zentralisierten Sicherheitsrichtlinien verbessert die Leistung durch Reduzierung des Verschlüsselungsaufwands auf den Backend-Servern und gewährleistet gleichzeitig eine konsistente Zugriffskontrolle, Bedrohungsabwehr und Einhaltung von Vorschriften für alle Dienste.

## Integrationen

Das erste Konzept ist die Integration von BunkerWeb in die Zielumgebung. Wir bevorzugen das Wort "Integration" anstelle von "Installation", da eines der Ziele von BunkerWeb darin besteht, sich nahtlos in bestehende Umgebungen zu integrieren.

Die folgenden Integrationen werden offiziell unterstützt:

- [Docker](integrations.md#docker)
- [Linux](integrations.md#linux)
- [Docker Autoconf](integrations.md#docker-autoconf)
- [Kubernetes](integrations.md#kubernetes)
- [Swarm](integrations.md#swarm)

Wenn Sie der Meinung sind, dass eine neue Integration unterstützt werden sollte, zögern Sie nicht, ein [neues Issue](https://github.com/bunkerity/bunkerweb/issues) im GitHub-Repository zu eröffnen.

!!! info "Weiterführende Informationen"

    Die technischen Details aller BunkerWeb-Integrationen sind im [Integrations-Abschnitt](integrations.md) der Dokumentation verfügbar.

## Einstellungen

!!! tip "BunkerWeb PRO Einstellungen"
    Einige Plugins sind der **PRO-Version** vorbehalten. Möchten Sie BunkerWeb PRO einen Monat lang schnell testen? Verwenden Sie den Code `freetrial` bei Ihrer Bestellung im [BunkerWeb Panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) oder klicken Sie [hier](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc), um den Promo-Code direkt anzuwenden (wird an der Kasse wirksam).

Sobald BunkerWeb in Ihre Umgebung integriert ist, müssen Sie es konfigurieren, um Ihre Webanwendungen bereitzustellen und zu schützen.

Die Konfiguration von BunkerWeb erfolgt über sogenannte "Einstellungen" oder "Variablen". Jede Einstellung wird durch einen Namen wie `AUTO_LETS_ENCRYPT` oder `USE_ANTIBOT` identifiziert. Sie können diesen Einstellungen Werte zuweisen, um BunkerWeb zu konfigurieren.

Hier ist ein Dummy-Beispiel für eine BunkerWeb-Konfiguration:

```conf
SERVER_NAME=www.example.com
AUTO_LETS_ENCRYPT=yes
USE_ANTIBOT=captcha
REFERRER_POLICY=no-referrer
USE_MODSECURITY=no
USE_GZIP=yes
USE_BROTLI=no
```

Bitte beachten Sie, dass bei Verwendung der Web-Benutzeroberfläche die Einstellungsnamen zusätzlich zu einem "menschenfreundlichen" Label angezeigt werden:

<figure markdown>
  ![Übersicht](assets/img/settings-ui1.png){ align=center, width="800" }
  <figcaption>Einstellungsname in der Web-UI</figcaption>
</figure>

Sie können auch die Suchleiste verwenden und direkt einen Einstellungsnamen angeben:

<figure markdown>
  ![Übersicht](assets/img/settings-ui2.png){ align=center, width="600" }
  <figcaption>Einstellungssuche in der Web-UI</figcaption>
</figure>

!!! info "Weiterführende Informationen"

    Die vollständige Liste der verfügbaren Einstellungen mit Beschreibungen und möglichen Werten ist im [Feature-Abschnitt](features.md) der Dokumentation verfügbar.

## Multisite-Modus {#multisite-mode}

Das Verständnis des Multisite-Modus ist bei der Nutzung von BunkerWeb unerlässlich. Da unser Hauptaugenmerk auf dem Schutz von Webanwendungen liegt, ist unsere Lösung eng mit dem Konzept der "virtuellen Hosts" oder "vhosts" verbunden (weitere Informationen [hier](https://en.wikipedia.org/wiki/Virtual_hosting)). Diese virtuellen Hosts ermöglichen die Bereitstellung mehrerer Webanwendungen von einer einzigen Instanz oder einem Cluster aus.

Standardmäßig ist der Multisite-Modus in BunkerWeb deaktiviert. Das bedeutet, dass nur eine Webanwendung bereitgestellt wird und alle Einstellungen darauf angewendet werden. Diese Einrichtung ist ideal, wenn Sie eine einzelne Anwendung zu schützen haben, da Sie sich nicht um Multisite-Konfigurationen kümmern müssen.

Wenn der Multisite-Modus jedoch aktiviert ist, kann BunkerWeb mehrere Webanwendungen bereitstellen und schützen. Jede Webanwendung wird durch einen eindeutigen Servernamen identifiziert und hat ihre eigenen Einstellungen. Dieser Modus ist vorteilhaft, wenn Sie mehrere Anwendungen zu sichern haben und eine einzige Instanz (oder einen Cluster) von BunkerWeb verwenden möchten.

Die Aktivierung des Multisite-Modus wird durch die Einstellung `MULTISITE` gesteuert, die auf `yes` gesetzt werden kann, um ihn zu aktivieren, oder auf `no`, um ihn deaktiviert zu lassen (Standardwert).

Jede Einstellung in BunkerWeb hat einen spezifischen Kontext, der bestimmt, wo sie angewendet werden kann. Wenn der Kontext auf "global" gesetzt ist, kann die Einstellung nicht pro Server oder Site angewendet werden, sondern wird auf die gesamte Konfiguration als Ganzes angewendet. Wenn der Kontext andererseits "multisite" ist, kann die Einstellung global und pro Server angewendet werden. Um eine Multisite-Einstellung für einen bestimmten Server zu definieren, fügen Sie einfach den Servernamen als Präfix zum Einstellungsnamen hinzu. Zum Beispiel sind `app1.example.com_AUTO_LETS_ENCRYPT` oder `app2.example.com_USE_ANTIBOT` Beispiele für Einstellungsnamen mit Servernamenpräfixen. Wenn eine Multisite-Einstellung global ohne Serverpräfix definiert ist, erben alle Server diese Einstellung. Einzelne Server können die Einstellung jedoch immer noch überschreiben, wenn dieselbe Einstellung mit einem Servernamenpräfix definiert ist.

Das Verständnis der Feinheiten des Multisite-Modus und der zugehörigen Einstellungen ermöglicht es Ihnen, das Verhalten von BunkerWeb an Ihre spezifischen Anforderungen anzupassen und einen optimalen Schutz für Ihre Webanwendungen zu gewährleisten.

Hier ist ein Dummy-Beispiel für eine Multisite-BunkerWeb-Konfiguration:

```conf
MULTISITE=yes
SERVER_NAME=app1.example.com app2.example.com app3.example.com
AUTO_LETS_ENCRYPT=yes
USE_GZIP=yes
USE_BROTLI=yes
app1.example.com_USE_ANTIBOT=javascript
app1.example.com_USE_MODSECURITY=no
app2.example.com_USE_ANTIBOT=cookie
app2.example.com_WHITELIST_COUNTRY=FR
app3.example.com_USE_BAD_BEHAVIOR=no
```

Bitte beachten Sie, dass der Multisite-Modus bei Verwendung der Web-Benutzeroberfläche implizit ist. Sie haben die Möglichkeit, Konfigurationen direkt auf Ihre Dienste anzuwenden oder globale Einstellungen festzulegen, die auf alle Ihre Dienste angewendet werden (Sie können immer noch Ausnahmen direkt auf bestimmte Dienste anwenden):

<figure markdown>
  ![Übersicht](assets/img/ui-multisite.png){ align=center, width="600" }
  <figcaption>Anwenden einer Einstellung auf alle Dienste über die Web-UI</figcaption>
</figure>

!!! info "Weiterführende Informationen"

    Konkrete Beispiele für den Multisite-Modus finden Sie in den [fortgeschrittenen Nutzungen](advanced.md) der Dokumentation und im [Beispiele](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/examples)-Verzeichnis des Repositorys.

## Benutzerdefinierte Konfigurationen {#custom-configurations}

Um einzigartige Herausforderungen zu bewältigen und spezifische Anwendungsfälle zu bedienen, bietet BunkerWeb die Flexibilität von benutzerdefinierten Konfigurationen. Während die bereitgestellten Einstellungen und [externen Plugins](plugins.md) eine breite Palette von Szenarien abdecken, kann es Situationen geben, die zusätzliche Anpassungen erfordern.

BunkerWeb basiert auf dem renommierten NGINX-Webserver, der ein leistungsstarkes Konfigurationssystem bietet. Das bedeutet, dass Sie die Konfigurationsmöglichkeiten von NGINX nutzen können, um Ihre spezifischen Anforderungen zu erfüllen. Benutzerdefinierte NGINX-Konfigurationen können in verschiedenen [Kontexten](https://docs.nginx.com/nginx/admin-guide/basic-functionality/managing-configuration-files/#contexts) wie HTTP oder Server eingebunden werden, sodass Sie das Verhalten von BunkerWeb entsprechend Ihren Anforderungen feinabstimmen können. Ob Sie globale Einstellungen anpassen oder Konfigurationen auf bestimmte Serverblöcke anwenden müssen, BunkerWeb ermöglicht es Ihnen, sein Verhalten zu optimieren, um es perfekt auf Ihren Anwendungsfall abzustimmen.

Ein weiterer integraler Bestandteil von BunkerWeb ist die ModSecurity Web Application Firewall. Mit benutzerdefinierten Konfigurationen haben Sie die Flexibilität, auf Fehlalarme zu reagieren oder benutzerdefinierte Regeln hinzuzufügen, um den von ModSecurity bereitgestellten Schutz weiter zu verbessern. Diese benutzerdefinierten Konfigurationen ermöglichen es Ihnen, das Verhalten der Firewall feinabzustimmen und sicherzustellen, dass es den spezifischen Anforderungen Ihrer Webanwendungen entspricht.

Durch die Nutzung benutzerdefinierter Konfigurationen erschließen Sie eine Welt von Möglichkeiten, um das Verhalten und die Sicherheitsmaßnahmen von BunkerWeb genau auf Ihre Bedürfnisse abzustimmen. Ob es sich um die Anpassung von NGINX-Konfigurationen oder die Feinabstimmung von ModSecurity handelt, BunkerWeb bietet die Flexibilität, um Ihre einzigartigen Herausforderungen effektiv zu meistern.

Die Verwaltung benutzerdefinierter Konfigurationen über die Web-Benutzeroberfläche erfolgt über das Menü **Konfigurationen**:

<figure markdown>
  ![Übersicht](assets/img/configs-ui.png){ align=center, width="800" }
  <figcaption>Benutzerdefinierte Konfigurationen über die Web-UI verwalten</figcaption>
</figure>

!!! info "Weiterführende Informationen"

    Konkrete Beispiele für benutzerdefinierte Konfigurationen finden Sie in den [fortgeschrittenen Nutzungen](advanced.md#custom-configurations) der Dokumentation und im [Beispiele](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/examples)-Verzeichnis des Repositorys.

## Datenbank

BunkerWeb speichert seine aktuelle Konfiguration sicher in einer Backend-Datenbank, die wesentliche Daten für einen reibungslosen Betrieb enthält. Die folgenden Informationen werden in der Datenbank gespeichert:

-   **Einstellungen für alle Dienste**: Die Datenbank enthält die definierten Einstellungen für alle von BunkerWeb bereitgestellten Dienste. Dadurch wird sichergestellt, dass Ihre Konfigurationen und Präferenzen erhalten bleiben und leicht zugänglich sind.

-   **Benutzerdefinierte Konfigurationen**: Alle von Ihnen erstellten benutzerdefinierten Konfigurationen werden ebenfalls in der Backend-Datenbank gespeichert. Dies umfasst personalisierte Einstellungen und Änderungen, die auf Ihre spezifischen Anforderungen zugeschnitten sind.

-   **BunkerWeb-Instanzen**: Informationen über BunkerWeb-Instanzen, einschließlich ihrer Einrichtung und relevanter Details, werden in der Datenbank gespeichert. Dies ermöglicht eine einfache Verwaltung und Überwachung mehrerer Instanzen, falls zutreffend.

-   **Metadaten zur Job-Ausführung**: Die Datenbank speichert Metadaten im Zusammenhang mit der Ausführung verschiedener Jobs in BunkerWeb. Dies umfasst Informationen zu geplanten Aufgaben, Wartungsprozessen und anderen automatisierten Aktivitäten.

-   **Gecachte Dateien**: BunkerWeb verwendet Caching-Mechanismen für eine verbesserte Leistung. Die Datenbank enthält gecachte Dateien, die ein effizientes Abrufen und Bereitstellen häufig aufgerufener Ressourcen gewährleisten.

Im Hintergrund speichert BunkerWeb bei jeder Bearbeitung einer Einstellung oder Hinzufügung einer neuen Konfiguration die Änderungen automatisch in der Datenbank und gewährleistet so Datenpersistenz und -konsistenz. BunkerWeb unterstützt mehrere Backend-Datenbankoptionen, darunter SQLite, MariaDB, MySQL und PostgreSQL.

!!! tip
    Wenn Sie die Weboberfläche für die tägliche Administration nutzen, empfehlen wir den Wechsel zu einer externen Datenbank-Engine (PostgreSQL oder MySQL/MariaDB) anstatt bei SQLite zu bleiben. Externe Engines verarbeiten gleichzeitige Anfragen und langfristiges Datenwachstum deutlich robuster, insbesondere in Mehrbenutzer-Umgebungen.

Die Konfiguration der Datenbank ist einfach über die Einstellung `DATABASE_URI` möglich, die den angegebenen Formaten für jede unterstützte Datenbank folgt:

!!! warning
    Bei Verwendung der Docker-Integration müssen Sie die Umgebungsvariable `DATABASE_URI` in allen BunkerWeb-Containern (außer dem BunkerWeb-Container selbst) festlegen, um sicherzustellen, dass alle Komponenten auf die Datenbank zugreifen können. Dies ist entscheidend für die Aufrechterhaltung der Integrität und Funktionalität des Systems.

    Stellen Sie in allen Fällen sicher, dass `DATABASE_URI` vor dem Start von BunkerWeb festgelegt ist, da es für den ordnungsgemäßen Betrieb erforderlich ist.

-   **SQLite**: `sqlite:///var/lib/bunkerweb/db.sqlite3`
-   **MariaDB**: `mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db`
-   **MySQL**: `mysql+pymysql://bunkerweb:changeme@bw-db:3306/db`
-   **PostgreSQL**: `postgresql://bunkerweb:changeme@bw-db:5432/db`

Durch Angabe des entsprechenden Datenbank-URI in der Konfiguration können Sie BunkerWeb nahtlos in Ihr bevorzugtes Datenbank-Backend integrieren und so eine effiziente und zuverlässige Speicherung Ihrer Konfigurationsdaten gewährleisten.

### Datenbank-Kompatibilitätsmatrix

| Integration      | PostgreSQL                               | MariaDB              | MySQL                | SQLite        |
| :--------------- | :--------------------------------------- | :------------------- | :------------------- | :------------ |
| **Docker**       | ✅ `v18` und früher (all-in-one: ✅ `v17`) | ✅ `v11` und früher   | ✅ `v9` und früher    | ✅ Unterstützt |
| **Kubernetes**   | ✅ `v18` und früher                       | ✅ `v11` und früher   | ✅ `v9` und früher    | ✅ Unterstützt |
| **Autoconf**     | ✅ `v18` und früher                       | ✅ `v11` und früher   | ✅ `v9` und früher    | ✅ Unterstützt |
| **Linux-Pakete** | Siehe Hinweise unten                      | Siehe Hinweise unten | Siehe Hinweise unten | ✅ Unterstützt |

!!! info "Hinweise"
    - **PostgreSQL**: Alpine-basierte Pakete enthalten jetzt den `v18`-Client, daher werden `v18` und frühere Versionen standardmäßig unterstützt; das all-in-one-Image enthält weiterhin den `v17`-Client, daher wird `v18` dort nicht unterstützt.
    - **Linux**: Die Unterstützung hängt von den Paketen Ihrer Distribution ab. Bei Bedarf können Sie Datenbank-Clients manuell aus den Hersteller-Repositorys installieren (dies ist bei RHEL normalerweise erforderlich).
    - **SQLite**: Wird mit den Paketen ausgeliefert und ist sofort einsatzbereit.

Hilfreiche externe Ressourcen zur Installation von Datenbankclients:

- [PostgreSQL Download- und Repository-Anleitung](https://www.postgresql.org/download/)
- [MariaDB Repository-Konfiguration](https://mariadb.org/download/?t=repo-config)
- [MySQL Repository-Setup](https://dev.mysql.com/doc/mysql-yum-repo-quick-guide/en/)
- [SQLite Download-Seite](https://www.sqlite.org/download.html)

<figure markdown>
  ![Übersicht](assets/img/bunkerweb_db.svg){ align=center, width="800" }
  <figcaption>Datenbankschema</figcaption>
</figure>

## Scheduler {#scheduler}

Für eine nahtlose Koordination und Automatisierung verwendet BunkerWeb einen spezialisierten Dienst, der als Scheduler bekannt ist. Der Scheduler spielt eine entscheidende Rolle bei der Gewährleistung eines reibungslosen Betriebs, indem er die folgenden Aufgaben ausführt:

-   **Speichern von Einstellungen und benutzerdefinierten Konfigurationen**: Der Scheduler ist für das Speichern aller Einstellungen und benutzerdefinierten Konfigurationen in der Backend-Datenbank verantwortlich. Dies zentralisiert die Konfigurationsdaten und macht sie leicht zugänglich und verwaltbar.

-   **Ausführen verschiedener Aufgaben (Jobs)**: Der Scheduler übernimmt die Ausführung verschiedener Aufgaben, die als Jobs bezeichnet werden. Diese Jobs umfassen eine Reihe von Aktivitäten wie regelmäßige Wartung, geplante Updates oder andere von BunkerWeb benötigte automatisierte Aufgaben.

-   **Generieren der BunkerWeb-Konfiguration**: Der Scheduler generiert eine Konfiguration, die von BunkerWeb leicht verstanden wird. Diese Konfiguration wird aus den gespeicherten Einstellungen und benutzerdefinierten Konfigurationen abgeleitet und gewährleistet, dass das gesamte System kohäsiv arbeitet.

-   **Fungieren als Vermittler für andere Dienste**: Der Scheduler fungiert als Vermittler und erleichtert die Kommunikation und Koordination zwischen verschiedenen Komponenten von BunkerWeb. Er interagiert mit Diensten wie der Web-UI oder Autoconf und sorgt für einen nahtlosen Informations- und Datenaustausch.

Im Wesentlichen dient der Scheduler als das Gehirn von BunkerWeb, das verschiedene Operationen orchestriert und das reibungslose Funktionieren des Systems gewährleistet.

Je nach Integrationsansatz kann die Ausführungsumgebung des Schedulers unterschiedlich sein. Bei containerbasierten Integrationen wird der Scheduler in seinem eigenen dedizierten Container ausgeführt, was Isolation und Flexibilität bietet. Bei Linux-basierten Integrationen ist der Scheduler hingegen in den BunkerWeb-Dienst integriert, was die Bereitstellung und Verwaltung vereinfacht.

Durch den Einsatz des Schedulers optimiert BunkerWeb die Automatisierung und Koordination wesentlicher Aufgaben und ermöglicht einen effizienten und zuverlässigen Betrieb des gesamten Systems.

Wenn Sie die Web-Benutzeroberfläche verwenden, können Sie Scheduler-Jobs verwalten, indem Sie im Menü auf **Jobs** klicken:

<figure markdown>
  ![Übersicht](assets/img/jobs-ui.png){ align=center, width="800" }
  <figcaption>Jobs über die Web-UI verwalten</figcaption>
</figure>

### Zustandsprüfung der Instanzen

Seit Version 1.6.0 verfügt der Scheduler über ein integriertes System zur Zustandsprüfung, das den Zustand der Instanzen überwacht. Wenn eine Instanz ungesund wird, sendet der Scheduler die Konfiguration nicht mehr an sie. Wenn die Instanz wieder gesund wird, sendet der Scheduler die Konfiguration wieder.

Das Intervall für die Zustandsprüfung wird durch die Umgebungsvariable `HEALTHCHECK_INTERVAL` festgelegt, mit einem Standardwert von `30`, was bedeutet, dass der Scheduler den Zustand der Instanzen alle 30 Sekunden überprüft.

## Vorlagen {#templates}

BunkerWeb nutzt die Leistungsfähigkeit von Vorlagen, um den Konfigurationsprozess zu vereinfachen und die Flexibilität zu erhöhen. Vorlagen bieten einen strukturierten und standardisierten Ansatz zur Definition von Einstellungen und benutzerdefinierten Konfigurationen, der Konsistenz und Benutzerfreundlichkeit gewährleistet.

-   **Vordefinierte Vorlagen**: Die Community-Version bietet drei vordefinierte Vorlagen, die gängige benutzerdefinierte Konfigurationen und Einstellungen zusammenfassen. Diese Vorlagen dienen als Ausgangspunkt für die Konfiguration von BunkerWeb und ermöglichen eine schnelle Einrichtung und Bereitstellung. Die vordefinierten Vorlagen sind die folgenden:
    -   **low**: Eine grundlegende Vorlage, die wesentliche Einstellungen für den Schutz von Webanwendungen bietet.
    -   **medium**: Eine ausgewogene Vorlage, die eine Mischung aus Sicherheitsfunktionen und Leistungsoptimierungen bietet.
    -   **high**: Eine erweiterte Vorlage, die sich auf robuste Sicherheitsmaßnahmen und umfassenden Schutz konzentriert.

-   **Benutzerdefinierte Vorlagen**: Zusätzlich zu den vordefinierten Vorlagen ermöglicht BunkerWeb den Benutzern, benutzerdefinierte Vorlagen zu erstellen, die auf ihre spezifischen Anforderungen zugeschnitten sind. Benutzerdefinierte Vorlagen ermöglichen die Feinabstimmung von Einstellungen und benutzerdefinierten Konfigurationen und stellen sicher, dass BunkerWeb perfekt auf die Bedürfnisse des Benutzers abgestimmt ist.

Mit der Web-Benutzeroberfläche sind Vorlagen über den **Einfachmodus** verfügbar, wenn Sie einen Dienst hinzufügen oder bearbeiten:

<figure markdown>
  ![Übersicht](assets/img/templates-ui.png){ align=center, width="800" }
  <figcaption>Verwendung von Vorlagen über die Web-UI</figcaption>
</figure>

**Erstellen benutzerdefinierter Vorlagen**

Das Erstellen einer benutzerdefinierten Vorlage ist ein unkomplizierter Prozess, bei dem die gewünschten Einstellungen, benutzerdefinierten Konfigurationen und Schritte in einem strukturierten Format definiert werden.

*   **Vorlagenstruktur**: Eine benutzerdefinierte Vorlage besteht aus einem Namen, einer Reihe von Einstellungen, benutzerdefinierten Konfigurationen und optionalen Schritten. Die Vorlagenstruktur wird in einer JSON-Datei definiert, die dem angegebenen Format entspricht. Die Schlüsselkomponenten einer benutzerdefinierten Vorlage umfassen:
    *   **Einstellungen**: Eine Einstellung wird mit einem Namen und einem entsprechenden Wert definiert. Dieser Wert überschreibt den Standardwert der Einstellung. **Es werden nur Multisite-Einstellungen unterstützt.**
    *   **Konfigurationen**: Eine benutzerdefinierte Konfiguration ist ein Pfad zu einer NGINX-Konfigurationsdatei, die als benutzerdefinierte Konfiguration eingebunden wird. Um zu wissen, wo die benutzerdefinierte Konfigurationsdatei platziert werden muss, verweisen Sie auf das Beispiel eines Plugin-Baums unten. **Es werden nur Multisite-Konfigurationstypen unterstützt.**
    *   **Schritte**: Ein Schritt enthält einen Titel, einen Untertitel, Einstellungen und benutzerdefinierte Konfigurationen. Jeder Schritt stellt einen Konfigurationsschritt dar, dem der Benutzer folgen kann, um BunkerWeb gemäß der benutzerdefinierten Vorlage in der Web-UI einzurichten.

!!! info "Spezifikationen zu Schritten"

    Wenn Schritte deklariert sind, **ist es nicht zwingend erforderlich, alle Einstellungen und benutzerdefinierten Konfigurationen in den Abschnitten "Einstellungen" und "Konfigurationen" aufzunehmen**. Beachten Sie, dass, wenn eine Einstellung oder eine benutzerdefinierte Konfiguration in einem Schritt deklariert ist, der Benutzer sie in der Web-UI bearbeiten kann.

*   **Vorlagendatei**: Die benutzerdefinierte Vorlage wird in einer JSON-Datei in einem `templates`-Ordner im Plugin-Verzeichnis definiert, die der angegebenen Struktur entspricht. Die Vorlagendatei enthält einen Namen, die Einstellungen, benutzerdefinierten Konfigurationen und Schritte, die erforderlich sind, um BunkerWeb gemäß den Präferenzen des Benutzers zu konfigurieren.

*   **Auswählen einer Vorlage**: Sobald die benutzerdefinierte Vorlage definiert ist, können Benutzer sie während des Einfachmodus-Konfigurationsprozesses eines Dienstes in der Web-UI auswählen. Eine Vorlage kann auch mit der Einstellung `USE_TEMPLATE` in der Konfiguration ausgewählt werden. Der Name der Vorlagendatei (ohne die `.json`-Erweiterung) sollte als Wert der Einstellung `USE_TEMPLATE` angegeben werden.

Beispiel für eine benutzerdefinierte Vorlagendatei:
```json
{
    "name": "Vorlagenname",
	// optional
    "settings": {
        "EINSTELLUNG_1": "Wert",
        "EINSTELLUNG_2": "Wert"
    },
	// optional
    "configs": [
        "modsec/false_positives.conf",
        "modsec/non_editable.conf",
		"modsec-crs/custom_rules.conf"
    ],
	// optional
    "steps": [
        {
            "title": "Titel 1",
            "subtitle": "Untertitel 1",
            "settings": [
                "EINSTELLUNG_1"
            ],
            "configs": [
                "modsec-crs/custom_rules.conf"
            ]
        },
        {
            "title": "Titel 2",
            "subtitle": "Untertitel 2",
            "settings": [
                "EINSTELLUNG_2"
            ],
            "configs": [
                "modsec/false_positives.conf"
            ]
        }
    ]
}
```

Beispiel für einen Plugin-Baum mit benutzerdefinierten Vorlagen:
```tree
.
├── plugin.json
└── templates
    ├── meine_andere_vorlage.json
    ├── meine_vorlage
    │   └── configs
    │       ├── modsec
    │       │   ├── false_positives.conf
    │       │   └── non_editable.conf
    │       └── modsec-crs
    │           └── custom_rules.conf
    └── meine_vorlage.json
```
