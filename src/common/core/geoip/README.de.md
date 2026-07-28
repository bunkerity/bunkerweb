Das GeoIP-Plugin verwaltet die Datenbanken im MaxMind-Format (`.mmdb`), mit denen BunkerWeb das **Land**, die **ASN** und optional die **Stadt** jeder Client-IP ermittelt. Diese Abfragen versorgen das [Country](#country)-Plugin, ASN-Regeln für Black- und Greylists, die Berichte in der [Web-UI](web-ui.md) sowie die Protokollvariablen `$bw_country`, `$bw_asn_number`, `$bw_asn_org` und `$bw_city`.

Standardmäßig ist keine Konfiguration erforderlich: Die Länder- und ASN-Datenbanken stammen aus den kostenlosen [DB-IP Lite](https://db-ip.com/db/lite.php)-Editionen und werden täglich aktualisiert. Die Einstellungen dieses Plugins benötigen Sie nur, wenn Sie einen **anderen Anbieter** verwenden möchten — ein MaxMind-Abonnement oder eine selbst bereitgestellte Datenbank.

**Funktionsweise:**

1. Drei tägliche Jobs aktualisieren die Länder-, ASN- und Städtedatenbanken.
2. Jeder Job wählt seine Quelle nach einer einfachen Priorität: zuerst Ihre eigene Datei, dann MaxMind, dann DB-IP.
3. Die heruntergeladene Datei wird entpackt, geöffnet und darauf geprüft, ob sie dem angeforderten Datenbanktyp entspricht.
4. Unterscheidet sie sich von der zwischengespeicherten Kopie, wird sie gespeichert und an jede BunkerWeb-Instanz verteilt, die sie nach einem Reload übernimmt.
5. Eine fehlgeschlagene Abfrage blockiert niemals eine Anfrage: Das Land wird zu `unknown` und der Datenverkehr normal bedient.

### Quellenpriorität

Es gibt keine Einstellung zur Auswahl einer „Quelle“. Die Priorität ergibt sich einfach daraus, welche Einstellungen Sie ausgefüllt haben:

| Priorität | Verwendet, wenn                             | Quelle                                                     |
| --------- | ------------------------------------------- | ---------------------------------------------------------- |
| 1         | `GEOIP_<KIND>_MMDB` gesetzt ist             | Ihre eigene Datei oder URL                                 |
| 2         | `MAXMIND_LICENSE_KEY` gesetzt ist            | MaxMind (kostenloses GeoLite2 oder Ihr GeoIP2-Abonnement)  |
| 3         | Nichts gesetzt ist                           | DB-IP Lite (Standard)                                      |

Durch das Setzen von `MAXMIND_LICENSE_KEY` wechseln **alle drei** Datenbanken zu MaxMind. Anbieter können nicht pro Datenbank gemischt werden; verwenden Sie `GEOIP_<KIND>_MMDB`, wenn eine bestimmte Datenbank aus einer anderen Quelle stammen soll.

### Konfigurationseinstellungen

| Einstellung              | Standard | Kontext | Mehrfach | Beschreibung                                                                                                                                                                           |
| ------------------------ | -------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `MAXMIND_LICENSE_KEY`    |          | global  | nein     | **MaxMind-Lizenzschlüssel:** Wenn gesetzt, werden die Länder-, ASN- und Städtedatenbanken von MaxMind statt von DB-IP heruntergeladen.                                                  |
| `MAXMIND_ACCOUNT_ID`     |          | global  | nein     | **MaxMind-Konto-ID:** Optional, aber empfohlen; ohne sie wird der veraltete Endpunkt nur mit Schlüssel verwendet, der den Schlüssel in der URL überträgt.                               |
| `GEOIP_CITY`             | `no`     | global  | nein     | **Städtedatenbank:** Lädt die Städtedatenbank herunter. Sie ist wesentlich größer als die anderen (125 MB entpackt) und nicht in den Images enthalten.                                  |
| `GEOIP_COUNTRY_MMDB`     |          | global  | nein     | **Benutzerdefinierte Länderdatenbank:** Absoluter, für den Worker lesbarer Pfad oder `http(s)`-URL. Hat Vorrang vor MaxMind und DB-IP.                                                   |
| `GEOIP_ASN_MMDB`         |          | global  | nein     | **Benutzerdefinierte ASN-Datenbank:** Absoluter, für den Worker lesbarer Pfad oder `http(s)`-URL. Hat Vorrang vor MaxMind und DB-IP.                                                    |
| `GEOIP_CITY_MMDB`        |          | global  | nein     | **Benutzerdefinierte Städtedatenbank:** Absoluter, für den Worker lesbarer Pfad oder `http(s)`-URL. Hat Vorrang vor MaxMind und DB-IP.                                                 |

!!! warning "Die Städtedatenbank ist groß"
    DB-IP City Lite ist ein **59 MB großer Download, der entpackt 125 MB belegt**, gegenüber 7.8 MB für Länder und 9.2 MB für ASN. Anders als diese beiden ist sie **nicht in den Images enthalten**: Bis zum ersten erfolgreichen Download stehen keine Daten zur Verfügung, und ein fehlgeschlagener Download lässt `$bw_city` einfach leer.

    Da Job-Caches in der Datenbank gespeichert und an jede Instanz verteilt werden, hat die Aktivierung konkrete Auswirkungen:

    - Erhöhen Sie bei MariaDB und MySQL `max_allowed_packet` auf mehr als 125 MB, sonst schlägt der Job fehl (Standardwert: 64 MB). Der Job weist in seinen Protokollen ausdrücklich darauf hin.
    - Der Worker hält die Datenbank beim Speichern im Arbeitsspeicher. Erhöhen Sie deshalb `WORKER_MAX_MEMORY_KB` und das Speicherlimit des Worker-Containers entsprechend.
    - Bei jeder Konfigurationsänderung wird der Cache erneut an jede Instanz übertragen. Planen Sie daher Bandbreite und Speicherplatz ein.

    MaxMinds `GeoLite2-City` ist deutlich kleiner, wenn Sie einen Lizenzschlüssel besitzen.

!!! info "MaxMind-Lizenzschlüssel beziehen"
    Erstellen Sie ein kostenloses Konto auf [maxmind.com](https://www.maxmind.com/en/geolite2/signup), generieren Sie anschließend einen Lizenzschlüssel **und** notieren Sie Ihre Konto-ID. Beides wird im Kontoportal angezeigt. GeoLite2 wird zweimal pro Woche aktualisiert, DB-IP Lite dagegen einmal pro Monat.

    Es kann einen Moment dauern, bis ein neu erstellter Schlüssel aktiv ist; bis dahin schlagen Downloads mit `401` fehl.

!!! warning "Konto-ID angeben, nicht nur den Schlüssel"
    Die Konto-ID ist nur aus Gründen der Abwärtskompatibilität optional. Sie wegzulassen ist aus zwei Gründen schlechter:

    - MaxMinds Endpunkt nur mit Schlüssel ist **veraltet** und kann eingestellt werden.
    - Er überträgt Ihren Lizenzschlüssel **in der URL-Abfragezeichenfolge**, wo er in den Zugriffsprotokollen jedes Forward-Proxys auf dem Weg landet. Mit einer Konto-ID werden die Zugangsdaten stattdessen in einem `Authorization`-Header übertragen.

    BunkerWeb entfernt den Schlüssel in beiden Fällen aus seinen eigenen Protokollen, auch aus Download-Fehlermeldungen. Aus Protokollen Dritter kann BunkerWeb ihn jedoch nicht entfernen.

!!! info "Eigene Datenbank verwenden"
    Jede `.mmdb` im MaxMind-Format funktioniert, einschließlich kommerzieller GeoIP2-Editionen und interner Datenbanken, sofern sie die Standardfeldnamen (`country.iso_code`, `autonomous_system_number`, `autonomous_system_organization`, `city.names.en`) verwendet.

    Ein lokaler Pfad muss für den **Worker** lesbar sein, nicht für die BunkerWeb-Instanzen: Der Worker liest ihn einmal und verteilt ihn anschließend. Reine `.mmdb`-, `.mmdb.gz`- und `.tar.gz`-Dateien werden akzeptiert.

    Die Datei wird geöffnet und ihr Typ geprüft, **bevor** sie gespeichert oder versendet wird. Verweist eine Einstellung auf den falschen Datenbanktyp — oder auf etwas, das gar keine Datenbank ist —, führt dies zu einem eindeutigen Fehler, statt unbemerkt keine Ergebnisse zu liefern.

    Verwenden Sie für URLs vorzugsweise `https`. Geolokalisierung beeinflusst Zulassungs- und Sperrentscheidungen; eine während der Übertragung ausgetauschte Datenbank kann Datenverkehr so erscheinen lassen, als käme er aus einem von Ihnen zugelassenen Land.

### Beispielkonfigurationen

=== "Standard (DB-IP)"

    Keine Konfiguration erforderlich. Länder und ASN werden täglich aus DB-IP Lite aktualisiert:

    ```yaml
    # no settings needed
    ```

=== "MaxMind GeoLite2"

    Stellen Sie alle Datenbanken auf MaxMind um:

    ```yaml
    MAXMIND_ACCOUNT_ID: "123456"
    MAXMIND_LICENSE_KEY: "your-license-key"
    ```

=== "Städtedaten hinzufügen"

    Aktivieren Sie die Städtedatenbank zusätzlich zu den Standardquellen:

    ```yaml
    GEOIP_CITY: "yes"
    ```

=== "Eigene Datenbank"

    Verwenden Sie eine im Worker eingebundene kommerzielle Datenbank und behalten Sie DB-IP für die übrigen Daten bei:

    ```yaml
    GEOIP_COUNTRY_MMDB: "/data/geoip/GeoIP2-Country.mmdb"
    ```

=== "Interner Spiegelserver"

    Rufen Sie alle Datenbanken von einem internen HTTP-Spiegelserver ab:

    ```yaml
    GEOIP_COUNTRY_MMDB: "https://mirror.example.com/geoip/country.mmdb"
    GEOIP_ASN_MMDB: "https://mirror.example.com/geoip/asn.mmdb"
    GEOIP_CITY: "yes"
    GEOIP_CITY_MMDB: "https://mirror.example.com/geoip/city.mmdb.gz"
    ```

### Lizenzierung

- **DB-IP Lite**-Datenbanken werden unter der Lizenz [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/) veröffentlicht und erfordern eine Namensnennung von DB-IP.com.
- **GeoLite2**-Datenbanken unterliegen MaxMinds Endbenutzer-Lizenzvereinbarung, der Sie beim Erstellen Ihres Schlüssels zustimmen. BunkerWeb verteilt sie niemals weiter: Sie werden mit Ihren eigenen Zugangsdaten heruntergeladen, weshalb keine MaxMind-Datenbank in den Images enthalten ist.
