Das Länder-Plugin aktiviert Geoblocking und ermöglicht die Einschränkung des Zugriffs basierend auf dem geografischen Standort der Besucher. Dies ist nützlich für die Einhaltung regionaler Vorschriften, zur Begrenzung von Betrug in Risikogebieten und zur Anwendung von Inhaltsbeschränkungen über Ländergrenzen hinweg.

So funktioniert's:

1. Bei jedem Besuch ermittelt BunkerWeb das Herkunftsland über die IP-Adresse.
2. Ihre Konfiguration definiert eine Whitelist (erlaubt) oder Blacklist (blockiert).
3. Bei einer Whitelist: Nur die gelisteten Länder sind zugelassen.
4. Bei einer Blacklist: Die gelisteten Länder werden abgelehnt.
5. Das Ergebnis wird für wiederholte Besuche zwischengespeichert.

### Anwendung

1. Strategie: Wählen Sie eine Whitelist (wenige zugelassene Länder) oder eine Blacklist (bestimmte Länder blockieren).
2. Ländercodes: Fügen Sie ISO 3166-1 Alpha-2 Codes (US, GB, FR) zu `WHITELIST_COUNTRY` oder `BLACKLIST_COUNTRY` hinzu.
3. Anwendung: Nach der Konfiguration gilt die Beschränkung für alle Besucher.
4. Überwachung: Konsultieren Sie die [Web-UI](web-ui.md) für Statistiken nach Ländern.

### Parameter

| Parameter           | Standard | Kontext   | Mehrfach | Beschreibung                                                                                             |
| :------------------ | :------- | :-------- | :------- | :------------------------------------------------------------------------------------------------------- |
| `WHITELIST_COUNTRY` |          | Multisite | Nein     | Whitelist: ISO 3166-1 Alpha-2 Ländercodes, durch Leerzeichen getrennt. Nur diese Länder sind zugelassen. |
| `BLACKLIST_COUNTRY` |          | Multisite | Nein     | Blacklist: ISO 3166-1 Alpha-2 Ländercodes, durch Leerzeichen getrennt. Diese Länder sind blockiert.      |

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
    WHITELIST_COUNTRY: "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE"
    ```

=== "Blockierung von Risikoländern"

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP IR SY"
    ```
