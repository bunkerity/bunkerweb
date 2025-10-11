Angreifer nutzen oft automatisierte Tools (Bots), um zu versuchen, Ihre Website auszunutzen. Zum Schutz davor enthält BunkerWeb eine „Antibot“-Funktion, die Benutzer auffordert, zu beweisen, dass sie menschlich sind. Wenn ein Benutzer die Herausforderung besteht, erhält er Zugriff auf Ihre Website. Diese Funktion ist standardmäßig deaktiviert.

So funktioniert es:

1. Wenn ein Benutzer Ihre Website besucht, prüft BunkerWeb, ob er bereits eine Antibot-Herausforderung bestanden hat.
2. Andernfalls wird der Benutzer auf eine Herausforderungsseite umgeleitet.
3. Der Benutzer muss die Herausforderung abschließen (z. B. ein CAPTCHA lösen, JavaScript ausführen).
4. Wenn die Herausforderung erfolgreich ist, wird der Benutzer auf die ursprünglich angeforderte Seite umgeleitet und kann normal navigieren.

### So verwenden Sie es

Befolgen Sie diese Schritte, um Antibot zu aktivieren und zu konfigurieren:

1. Wählen Sie einen Herausforderungstyp: Entscheiden Sie sich für den zu verwendenden Mechanismus (z. B. [captcha](#__tabbed_3_3), [hcaptcha](#__tabbed_3_5), [javascript](#__tabbed_3_2)).
2. Aktivieren Sie die Funktion: Setzen Sie den Parameter `USE_ANTIBOT` in Ihrer BunkerWeb-Konfiguration auf den gewählten Typ.
3. Konfigurieren Sie die Einstellungen: Passen Sie bei Bedarf andere `ANTIBOT_*`-Parameter an. Für reCAPTCHA, hCaptcha, Turnstile und mCaptcha erstellen Sie ein Konto beim gewählten Dienst und erhalten Sie API-Schlüssel.
4. Wichtig: Stellen Sie sicher, dass `ANTIBOT_URI` eine eindeutige URL Ihrer Website ist und nirgendwo anders verwendet wird.

!!! important "Über den Parameter `ANTIBOT_URI`"
    Stellen Sie sicher, dass `ANTIBOT_URI` eine eindeutige URL Ihrer Website ist und nirgendwo anders verwendet wird.

!!! warning "Sitzungen in Cluster-Umgebungen"
    Die Antibot-Funktion verwendet Cookies, um zu verfolgen, ob ein Benutzer die Herausforderung abgeschlossen hat. Wenn Sie BunkerWeb in einem Cluster (mehrere Instanzen) betreiben, müssen Sie die Sitzungsverwaltung korrekt konfigurieren: Setzen Sie `SESSIONS_SECRET` und `SESSIONS_NAME` auf allen BunkerWeb-Instanzen auf dieselben Werte. Andernfalls könnten Benutzer aufgefordert werden, die Herausforderung zu wiederholen. Weitere Informationen zur Sitzungskonfiguration finden Sie [hier](#sessions).

### Allgemeine Parameter

Die folgenden Parameter werden von allen Herausforderungsmechanismen gemeinsam genutzt:

| Parameter              | Standardwert | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                       |
| :--------------------- | :----------- | :-------- | :------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_URI`          | `/challenge` | Multisite | nein     | Herausforderungs-URL: Die URL, zu der Benutzer umgeleitet werden, um die Herausforderung abzuschließen. Stellen Sie sicher, dass diese URL nicht für andere Zwecke verwendet wird. |
| `ANTIBOT_TIME_RESOLVE` | `60`         | Multisite | nein     | Herausforderungs-Timeout: Maximale Zeit (in Sekunden) zum Abschließen der Herausforderung. Danach wird eine neue Herausforderung generiert.                                        |
| `ANTIBOT_TIME_VALID`   | `86400`      | Multisite | nein     | Herausforderungs-Gültigkeit: Dauer (in Sekunden), für die eine erfolgreiche Herausforderung gültig bleibt. Nach dieser Zeit wird eine neue Herausforderung erforderlich sein.      |

### Ausschließen von Traffic von Herausforderungen

BunkerWeb ermöglicht es, bestimmte Benutzer, IPs oder Anfragen anzugeben, die die Antibot-Herausforderung vollständig umgehen sollen. Nützlich für vertrauenswürdige Dienste, interne Netzwerke oder Seiten, die immer zugänglich sein sollen:

| Parameter                   | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                                              |
| :-------------------------- | :------- | :-------- | :------- | :---------------------------------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_IGNORE_URI`        |          | Multisite | nein     | Ausgeschlossene URLs: Eine durch Leerzeichen getrennte Liste von URI-Regulären Ausdrücken, die die Herausforderung umgehen sollen.        |
| `ANTIBOT_IGNORE_IP`         |          | Multisite | nein     | Ausgeschlossene IPs: Eine durch Leerzeichen getrennte Liste von IP-Adressen oder CIDR-Bereichen, die die Herausforderung umgehen sollen.  |
| `ANTIBOT_IGNORE_RDNS`       |          | Multisite | nein     | Ausgeschlossene rDNS: Eine durch Leerzeichen getrennte Liste von Reverse-DNS-Suffixen, die die Herausforderung umgehen sollen.            |
| `ANTIBOT_RDNS_GLOBAL`       | `yes`    | Multisite | nein     | Nur öffentliche IPs: Wenn `yes`, werden rDNS-Prüfungen nur für öffentliche IPs durchgeführt.                                              |
| `ANTIBOT_IGNORE_ASN`        |          | Multisite | nein     | Ausgeschlossene ASNs: Eine durch Leerzeichen getrennte Liste von ASN-Nummern, die die Herausforderung umgehen sollen.                     |
| `ANTIBOT_IGNORE_USER_AGENT` |          | Multisite | nein     | Ausgeschlossene User-Agents: Eine durch Leerzeichen getrennte Liste von User-Agent-Regex-Mustern, die die Herausforderung umgehen sollen. |

Beispiele:

- `ANTIBOT_IGNORE_URI: "^/api/ ^/webhook/ ^/assets/"`
  Schließt alle URIs aus, die mit `/api/`, `/webhook/` oder `/assets/` beginnen.

- `ANTIBOT_IGNORE_IP: "192.168.1.0/24 10.0.0.1"`
  Schließt das interne Netzwerk `192.168.1.0/24` und die spezifische IP `10.0.0.1` aus.

- `ANTIBOT_IGNORE_RDNS: ".googlebot.com .bingbot.com"`
  Schließt Anfragen von Hosts aus, deren Reverse-DNS auf `googlebot.com` oder `bingbot.com` endet.

- `ANTIBOT_IGNORE_ASN: "15169 8075"`
  Schließt Anfragen von den ASNs 15169 (Google) und 8075 (Microsoft) aus.

- `ANTIBOT_IGNORE_USER_AGENT: "^Mozilla.+Chrome.+Safari"`
  Schließt Anfragen aus, deren User-Agent dem angegebenen Regex-Muster entspricht.

### Herausforderungsmechanismen

=== "Cookie"

    Die Cookie-Herausforderung ist ein leichter Mechanismus, der auf der Installation eines Cookies im Browser des Benutzers basiert. Wenn ein Benutzer auf die Website zugreift, sendet der Server ein Cookie an den Client. Bei nachfolgenden Anfragen überprüft der Server das Vorhandensein dieses Cookies, um zu bestätigen, dass der Benutzer legitim ist. Diese Methode ist einfach und effektiv für einen grundlegenden Schutz vor Bots, ohne zusätzliche Benutzerinteraktion zu erfordern.

    **So funktioniert es:**

    1. Der Server generiert ein eindeutiges Cookie und sendet es an den Client.
    2. Der Client muss das Cookie bei nachfolgenden Anfragen zurücksenden.
    3. Wenn das Cookie fehlt oder ungültig ist, wird der Benutzer auf die Herausforderungsseite umgeleitet.

    **Parameter:**

    | Parameter     | Standard | Kontext   | Mehrfach | Beschreibung                                                       |
    | :------------ | :------- | :-------- | :------- | :----------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`     | Multisite | nein     | Antibot aktivieren: Auf `cookie` setzen, um diesen Mechanismus zu aktivieren. |

=== "JavaScript"

    Die JavaScript-Herausforderung fordert den Client auf, eine Rechenaufgabe mithilfe von JavaScript zu lösen. Dieser Mechanismus stellt sicher, dass der Client JavaScript aktiviert hat und den erforderlichen Code ausführen kann, was für die meisten Bots in der Regel nicht möglich ist.

    **So funktioniert es:**

    1. Der Server sendet ein JavaScript-Skript an den Client.
    2. Das Skript führt eine Rechenaufgabe aus (z. B. einen Hash) und übermittelt das Ergebnis an den Server.
    3. Der Server überprüft das Ergebnis, um die Legitimität des Clients zu bestätigen.

    **Hauptmerkmale:**

    - Die Herausforderung generiert dynamisch eine einzigartige Aufgabe für jeden Client.
    - Die Rechenaufgabe beinhaltet ein Hashing mit spezifischen Bedingungen (z. B. das Finden eines Hashes mit einem bestimmten Präfix).

    **Parameter:**

    | Parameter     | Standard | Kontext   | Mehrfach | Beschreibung                                                           |
    | :------------ | :------- | :-------- | :------- | :--------------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`     | Multisite | nein     | Antibot aktivieren: Auf `javascript` setzen, um diesen Mechanismus zu aktivieren. |

=== "Captcha"

    Die Captcha-Herausforderung ist ein hauseigener Mechanismus, der bildbasierte Herausforderungen generiert, die vollständig in Ihrer BunkerWeb-Umgebung gehostet werden. Er testet die Fähigkeit der Benutzer, zufällige Zeichen zu erkennen und zu interpretieren, wodurch sichergestellt wird, dass automatisierte Bots effektiv blockiert werden, ohne auf externe Dienste angewiesen zu sein.

    **So funktioniert es:**

    1. Der Server generiert ein CAPTCHA-Bild mit zufälligen Zeichen.
    2. Der Benutzer muss die im Bild angezeigten Zeichen in ein Textfeld eingeben.
    3. Der Server validiert die Benutzereingabe anhand des generierten CAPTCHAs.

    **Hauptmerkmale:**

    - Vollständig selbst gehostet, wodurch die Notwendigkeit von Drittanbieter-APIs entfällt.
    - Dynamisch generierte Herausforderungen gewährleisten die Einzigartigkeit für jede Benutzersitzung.
    - Verwendet einen anpassbaren Zeichensatz für die CAPTCHA-Generierung.

    **Unterstützte Zeichen:**

    Das CAPTCHA-System unterstützt die folgenden Zeichentypen:

    - **Buchstaben:** Alle Kleinbuchstaben (a-z) und Großbuchstaben (A-Z)
    - **Ziffern:** 2, 3, 4, 5, 6, 7, 8, 9 (schließt 0 und 1 aus, um Verwechslungen zu vermeiden)
    - **Sonderzeichen:** ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„```

    Eine vollständige Liste der unterstützten Zeichen finden Sie in der [Zeichentabelle der für das CAPTCHA verwendeten Schriftart](https://www.dafont.com/moms-typewriter.charmap?back=theme).

    **Parameter:**

    | Parameter                  | Standard                                                 | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                                                                                               |
    | :------------------------- | :------------------------------------------------------- | :-------- | :------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                                                     | Multisite | nein     | **Antibot aktivieren:** Auf `captcha` setzen, um diesen Mechanismus zu aktivieren.                                                                                                                                                                                    |
    | `ANTIBOT_CAPTCHA_ALPHABET` | `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ` | Multisite | nein     | **Captcha-Alphabet:** Eine Zeichenkette, die zur Generierung des CAPTCHAs verwendet werden soll. Unterstützte Zeichen: alle Buchstaben (a-z, A-Z), die Ziffern 2-9 (schließt 0 und 1 aus) und die Sonderzeichen: ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„``` |

=== "reCAPTCHA"

    Googles reCAPTCHA bietet eine Benutzervalidierung, die im Hintergrund (v3) ausgeführt wird, um eine Verhaltensbewertung zuzuweisen. Eine Bewertung unterhalb des konfigurierten Schwellenwerts löst eine zusätzliche Überprüfung aus oder blockiert die Anfrage. Bei sichtbaren Herausforderungen (v2) müssen Benutzer mit dem reCAPTCHA-Widget interagieren, bevor sie fortfahren können.

    Es gibt jetzt zwei Möglichkeiten, reCAPTCHA zu integrieren:
    - Die klassische Version (Site-/Geheimschlüssel, v2/v3-Verifizierungsendpunkt)
    - Die neue Version mit Google Cloud (Projekt-ID + API-Schlüssel). Die klassische Version bleibt verfügbar und kann mit `ANTIBOT_RECAPTCHA_CLASSIC` aktiviert werden.

    Für die klassische Version erhalten Sie Ihre Site- und Geheimschlüssel über die [Google reCAPTCHA Admin-Konsole](https://www.google.com/recaptcha/admin).
    Für die neue Version erstellen Sie einen reCAPTCHA-Schlüssel in Ihrem Google Cloud-Projekt und verwenden Sie die Projekt-ID sowie einen API-Schlüssel (siehe [Google Cloud reCAPTCHA-Konsole](https://console.cloud.google.com/security/recaptcha)). Ein Site-Schlüssel ist immer erforderlich.

    **Parameter:**

    | Parameter                      | Standard | Kontext   | Mehrfach | Beschreibung                                                                                                         |
    | :----------------------------- | :------- | :-------- | :------- | :------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`                  | `no`     | Multisite | nein     | Antibot aktivieren: Auf `recaptcha` setzen, um diesen Mechanismus zu aktivieren.                                                |
    | `ANTIBOT_RECAPTCHA_CLASSIC`    | `yes`    | Multisite | nein     | Klassisches reCAPTCHA verwenden. Auf `no` setzen, um die neue Google Cloud-basierte Version zu verwenden.               |
    | `ANTIBOT_RECAPTCHA_SITEKEY`    |          | Multisite | nein     | reCAPTCHA Site-Schlüssel. Für beide Versionen erforderlich.                                                              |
    | `ANTIBOT_RECAPTCHA_SECRET`     |          | Multisite | nein     | reCAPTCHA Geheimschlüssel. Nur für die klassische Version erforderlich.                                                |
    | `ANTIBOT_RECAPTCHA_PROJECT_ID` |          | Multisite | nein     | Google Cloud Projekt-ID. Nur für die neue Version erforderlich.                                              |
    | `ANTIBOT_RECAPTCHA_API_KEY`    |          | Multisite | nein     | Google Cloud API-Schlüssel, der zum Aufrufen der reCAPTCHA Enterprise API verwendet wird. Nur für die neue Version erforderlich. |
    | `ANTIBOT_RECAPTCHA_JA3`        |          | Multisite | nein     | Optionaler JA3 TLS-Fingerabdruck, der in Enterprise-Bewertungen enthalten sein soll.                                            |
    | `ANTIBOT_RECAPTCHA_JA4`        |          | Multisite | nein     | Optionaler JA4 TLS-Fingerabdruck, der in Enterprise-Bewertungen enthalten sein soll.                                            |
    | `ANTIBOT_RECAPTCHA_SCORE`      | `0.7`    | Multisite | nein     | Mindestpunktzahl, die zum Bestehen erforderlich ist (gilt für klassische v3 und die neue Version).                           |

=== "hCaptcha"

    Wenn aktiviert, bietet hCaptcha eine effektive Alternative zu reCAPTCHA, indem es Benutzerinteraktionen überprüft, ohne auf einen Bewertungsmechanismus angewiesen zu sein. Es fordert Benutzer mit einem einfachen, interaktiven Test heraus, um ihre Legitimität zu bestätigen.

    Um hCaptcha mit BunkerWeb zu integrieren, müssen Sie die erforderlichen Anmeldeinformationen vom hCaptcha-Dashboard unter [hCaptcha](https://www.hcaptcha.com) abrufen. Diese Informationen umfassen einen Site-Schlüssel und einen Geheimschlüssel.

    **Parameter:**

    | Parameter                  | Standard | Kontext   | Mehrfach | Beschreibung                                                         |
    | :------------------------- | :------- | :-------- | :------- | :------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`     | Multisite | nein     | Antibot aktivieren: Auf `hcaptcha` setzen, um diesen Mechanismus zu aktivieren. |
    | `ANTIBOT_HCAPTCHA_SITEKEY` |          | Multisite | nein     | hCaptcha Site-Schlüssel.                                                  |
    | `ANTIBOT_HCAPTCHA_SECRET`  |          | Multisite | nein     | hCaptcha Geheimschlüssel.                                               |

=== "Turnstile"

    Turnstile ist ein moderner, datenschutzfreundlicher Herausforderungsmechanismus, der auf der Technologie von Cloudflare basiert, um automatisierten Traffic zu erkennen und zu blockieren. Er validiert Benutzerinteraktionen transparent und im Hintergrund, wodurch die Reibung für legitime Benutzer reduziert und Bots effektiv abgeschreckt werden.

    Um Turnstile mit BunkerWeb zu integrieren, stellen Sie sicher, dass Sie die erforderlichen Anmeldeinformationen von [Cloudflare Turnstile](https://www.cloudflare.com/turnstile) erhalten.

    **Parameter:**

    | Parameter                   | Standard | Kontext   | Mehrfach | Beschreibung                                                          |
    | :-------------------------- | :------- | :-------- | :------- | :-------------------------------------------------------------------- |
    | `USE_ANTIBOT`               | `no`     | Multisite | nein     | Antibot aktivieren: Auf `turnstile` setzen, um diesen Mechanismus zu aktivieren. |
    | `ANTIBOT_TURNSTILE_SITEKEY` |          | Multisite | nein     | Turnstile Site-Schlüssel (Cloudflare).                                     |
    | `ANTIBOT_TURNSTILE_SECRET`  |          | Multisite | nein     | Turnstile Geheimschlüssel (Cloudflare).                                  |

=== "mCaptcha"

    mCaptcha ist ein alternativer CAPTCHA-Herausforderungsmechanismus, der die Legitimität von Benutzern überprüft, indem er einen interaktiven Test präsentiert, ähnlich wie andere Antibot-Lösungen. Wenn aktiviert, fordert es Benutzer mit einem von mCaptcha bereitgestellten CAPTCHA heraus, um sicherzustellen, dass nur authentische Benutzer die automatisierten Sicherheitskontrollen umgehen.

    mCaptcha ist datenschutzfreundlich konzipiert. Es ist vollständig DSGVO-konform und stellt sicher, dass alle am Herausforderungsprozess beteiligten Benutzerdaten strenge Datenschutzstandards erfüllen. Darüber hinaus bietet mCaptcha die Flexibilität, selbst gehostet zu werden, sodass Organisationen die volle Kontrolle über ihre Daten und Infrastruktur behalten. Diese Selbsthosting-Fähigkeit verbessert nicht nur den Datenschutz, sondern optimiert auch die Leistung und Anpassung an spezifische Bereitstellungsanforderungen.

    Um mCaptcha mit BunkerWeb zu integrieren, müssen Sie die erforderlichen Anmeldeinformationen von der [mCaptcha-Plattform](https://mcaptcha.org/) oder Ihrem eigenen Anbieter abrufen. Diese Informationen umfassen einen Site-Schlüssel und einen Geheimschlüssel zur Überprüfung.

    **Parameter:**

    | Parameter                  | Standard                      | Kontext   | Mehrfach | Beschreibung                                                         |
    | :------------------------- | :---------------------------- | :-------- | :------- | :------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                          | Multisite | nein     | Antibot aktivieren: Auf `mcaptcha` setzen, um diesen Mechanismus zu aktivieren. |
    | `ANTIBOT_MCAPTCHA_SITEKEY` |                               | Multisite | nein     | mCaptcha Site-Schlüssel.                                                  |
    | `ANTIBOT_MCAPTCHA_SECRET`  |                               | Multisite | nein     | mCaptcha Geheimschlüssel.                                               |
    | `ANTIBOT_MCAPTCHA_URL`     | `https://demo.mcaptcha.org` | Multisite | nein     | Zu verwendende Domain für mCaptcha.                                   |

    Siehe Allgemeine Parameter für zusätzliche Optionen.

### Konfigurationsbeispiele

=== "Cookie-Herausforderung"

    ```yaml
    USE_ANTIBOT: "cookie"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "JavaScript-Herausforderung"

    ```yaml
    USE_ANTIBOT: "javascript"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Captcha-Herausforderung"

    ```yaml
    USE_ANTIBOT: "captcha"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ANTIBOT_CAPTCHA_ALPHABET: "23456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ```

    Hinweis: Das obige Beispiel verwendet die Ziffern 2-9 und alle Buchstaben, die häufig für CAPTCHAs verwendet werden. Sie können das Alphabet bei Bedarf anpassen, um Sonderzeichen einzuschließen.

=== "Klassische reCAPTCHA-Herausforderung"

    Beispielkonfiguration für das klassische reCAPTCHA (Site-/Geheimschlüssel):

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "yes"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "reCAPTCHA-Herausforderung (neu)"

    Beispielkonfiguration für das neue Google Cloud-basierte reCAPTCHA (Projekt-ID + API-Schlüssel):

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "no"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_PROJECT_ID: "your-gcp-project-id"
    ANTIBOT_RECAPTCHA_API_KEY: "your-gcp-api-key"
    # Optionale Fingerabdrücke zur Verbesserung der Enterprise-Bewertungen
    # ANTIBOT_RECAPTCHA_JA3: "<ja3-fingerprint>"
    # ANTIBOT_RECAPTCHA_JA4: "<ja4-fingerprint>"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "hCaptcha-Herausforderung"

    ```yaml
    USE_ANTIBOT: "hcaptcha"
    ANTIBOT_HCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_HCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Turnstile-Herausforderung"

    ```yaml
    USE_ANTIBOT: "turnstile"
    ANTIBOT_TURNSTILE_SITEKEY: "your-site-key"
    ANTIBOT_TURNSTILE_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "mCaptcha-Herausforderung"

    ```yaml
    USE_ANTIBOT: "mcaptcha"
    ANTIBOT_MCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_MCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_MCAPTCHA_URL: "https://demo.mcaptcha.org"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```
