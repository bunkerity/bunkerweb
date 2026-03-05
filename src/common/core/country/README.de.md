Das Länder-Plugin aktiviert Geoblocking und ermöglicht die Einschränkung des Zugriffs basierend auf dem geografischen Standort der Besucher. Dies ist nützlich für die Einhaltung regionaler Vorschriften, zur Begrenzung von Betrug in Risikogebieten und zur Anwendung von Inhaltsbeschränkungen über Ländergrenzen hinweg.

So funktioniert's:

1. Bei jedem Besuch ermittelt BunkerWeb das Herkunftsland über die IP-Adresse.
2. Ihre Konfiguration definiert eine Whitelist (erlaubt) oder Blacklist (blockiert).
3. Bei einer Whitelist: Nur die gelisteten Länder sind zugelassen.
4. Bei einer Blacklist: Die gelisteten Länder werden abgelehnt.
5. Das Ergebnis wird für wiederholte Besuche zwischengespeichert.

### Anwendung

1. Strategie: Wählen Sie eine Whitelist (wenige zugelassene Länder) oder eine Blacklist (bestimmte Länder blockieren).
2. Länder oder Gruppen: Fügen Sie ISO 3166-1 Alpha-2 Codes (US, GB, FR) und/oder unterstützte Gruppentokens (wie `@EU`, `@SCHENGEN`) zu `WHITELIST_COUNTRY` oder `BLACKLIST_COUNTRY` hinzu.
3. Anwendung: Nach der Konfiguration gilt die Beschränkung für alle Besucher.
4. Überwachung: Konsultieren Sie die [Web-UI](web-ui.md) für Statistiken nach Ländern.

### Parameter

| Parameter           | Standard | Kontext   | Mehrfach | Beschreibung                                                                                             |
| :------------------ | :------- | :-------- | :------- | :------------------------------------------------------------------------------------------------------- |
| `WHITELIST_COUNTRY` |          | Multisite | Nein     | Whitelist: Ländercodes und/oder Gruppentokens, durch Leerzeichen getrennt. Nur diese Länder sind zugelassen. |
| `BLACKLIST_COUNTRY` |          | Multisite | Nein     | Blacklist: Ländercodes und/oder Gruppentokens, durch Leerzeichen getrennt. Diese Länder sind blockiert.      |

### Unterstützte Ländergruppen

Sie können Gruppentokens mit `@` verwenden. Diese werden serverseitig in Mitgliedsländer aufgelöst:

- `@EU`: Mitgliedstaaten der Europäischen Union.
- `@SCHENGEN`: Länder des Schengen-Raums.
- `@EEA`: Europäischer Wirtschaftsraum (`@EU` + Island, Liechtenstein, Norwegen).
- `@BENELUX`: Belgien, Niederlande, Luxemburg.
- `@DACH`: deutschsprachiger Kernraum (Deutschland, Österreich, Schweiz).
- `@NORDICS`: nordische Länder (Dänemark, Finnland, Island, Norwegen, Schweden).
- `@USMCA`: USMCA-Wirtschaftsraum (USA, Kanada, Mexiko).
- `@FIVE_EYES`: Länder der Five-Eyes-Geheimdienstallianz.
- `@ASEAN`: ASEAN-Mitgliedstaaten in Südostasien.
- `@GCC`: Mitgliedstaaten des Golf-Kooperationsrats.
- `@G7`: Staaten der Gruppe der Sieben.
- `@LATAM`: in diesem Plugin verwendete Lateinamerika-Gruppe.

!!! tip "Whitelist vs. Blacklist"
    Whitelist: Zugriff auf wenige Länder beschränkt. Blacklist: Problematische Regionen blockieren und den Rest zulassen.

!!! warning "Priorität"
    Wenn eine Whitelist und eine Blacklist definiert sind, hat die Whitelist Vorrang: Wenn das Land nicht auf der Whitelist steht, wird der Zugriff verweigert.

!!! info "Ländererkennung"
    BunkerWeb verwendet die mmdb-Datenbank [db-ip lite](https://db-ip.com/db/download/ip-to-country-lite).

### Beispiele

=== "Nur Whitelist"

    ```yaml
    WHITELIST_COUNTRY: "US CA GB"
    ```

=== "Nur Blacklist"

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP"
    ```

=== "Nur EU"

    ```yaml
    WHITELIST_COUNTRY: "@EU"
    ```

=== "Gruppe + explizite Länder"

    ```yaml
    WHITELIST_COUNTRY: "@SCHENGEN GB"
    ```

=== "Blockierung von Risikoländern"

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP IR SY"
    ```
