Das BunkerNet-Plugin ermöglicht den kollektiven Austausch von Bedrohungsdaten zwischen BunkerWeb-Instanzen und schafft so ein leistungsstarkes Schutznetzwerk gegen böswillige Akteure. Durch die Teilnahme an BunkerNet profitiert Ihre Instanz von einer globalen Datenbank bekannter Bedrohungen und trägt gleichzeitig dazu bei, die Sicherheit der gesamten BunkerWeb-Community zu verbessern.

**So funktioniert es:**

1.  Ihre BunkerWeb-Instanz registriert sich automatisch bei der BunkerNet-API, um eine eindeutige Kennung zu erhalten.
2.  Wenn Ihre Instanz eine bösartige IP-Adresse oder ein bösartiges Verhalten erkennt und blockiert, meldet sie die Bedrohung anonym an BunkerNet.
3.  BunkerNet sammelt Bedrohungsdaten von allen teilnehmenden Instanzen und verteilt die konsolidierte Datenbank.
4.  Ihre Instanz lädt regelmäßig eine aktualisierte Datenbank bekannter Bedrohungen von BunkerNet herunter.
5.  Diese kollektive Intelligenz ermöglicht es Ihrer Instanz, proaktiv IP-Adressen zu blockieren, die auf anderen BunkerWeb-Instanzen bösartiges Verhalten gezeigt haben.

!!! success "Wichtige Vorteile"

      1. **Kollektive Verteidigung:** Nutzen Sie die Sicherheitserkenntnisse von Tausenden anderer BunkerWeb-Instanzen weltweit.
      2. **Proaktiver Schutz:** Blockieren Sie böswillige Akteure, bevor sie Ihre Website angreifen können, basierend auf ihrem Verhalten an anderer Stelle.
      3. **Beitrag zur Gemeinschaft:** Helfen Sie, andere BunkerWeb-Benutzer zu schützen, indem Sie anonymisierte Bedrohungsdaten über Angreifer teilen.
      4. **Keine Konfiguration erforderlich:** Funktioniert standardmäßig mit sinnvollen Voreinstellungen und erfordert nur minimale Einrichtung.
      5. **Datenschutzorientiert:** Teilt nur notwendige Bedrohungsinformationen, ohne Ihre Privatsphäre oder die Ihrer Benutzer zu gefährden.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die BunkerNet-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die BunkerNet-Funktion ist standardmäßig aktiviert. Bei Bedarf können Sie dies mit der Einstellung `USE_BUNKERNET` steuern.
2.  **Erstregistrierung:** Beim ersten Start registriert sich Ihre Instanz automatisch bei der BunkerNet-API und erhält eine eindeutige Kennung.
3.  **Automatische Updates:** Ihre Instanz lädt automatisch in regelmäßigen Abständen die neueste Bedrohungsdatenbank herunter.
4.  **Automatisches Melden:** Wenn Ihre Instanz eine bösartige IP-Adresse blockiert, trägt sie diese Daten automatisch zur Gemeinschaft bei.
5.  **Schutz überwachen:** Überprüfen Sie die [Web-Benutzeroberfläche](web-ui.md), um Statistiken zu den von BunkerNet-Informationen blockierten Bedrohungen anzuzeigen.

### Konfigurationseinstellungen

| Einstellung        | Standard                   | Kontext   | Mehrfach | Beschreibung                                                                                       |
| ------------------ | -------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------- |
| `USE_BUNKERNET`    | `yes`                      | multisite | nein     | **BunkerNet aktivieren:** Auf `yes` setzen, um den Austausch von Bedrohungsdaten zu aktivieren.    |
| `BUNKERNET_SERVER` | `https://api.bunkerweb.io` | global    | nein     | **BunkerNet-Server:** Die Adresse des BunkerNet-API-Servers für den Austausch von Bedrohungsdaten. |

!!! tip "Netzwerkschutz"
    Wenn BunkerNet feststellt, dass eine IP-Adresse an bösartigen Aktivitäten auf mehreren BunkerWeb-Instanzen beteiligt war, wird diese IP zu einer kollektiven schwarzen Liste hinzugefügt. Dies bietet eine proaktive Verteidigungsebene, die Ihre Website vor Bedrohungen schützt, bevor sie Sie direkt angreifen können.

!!! info "Anonymes Melden"
    Bei der Meldung von Bedrohungsinformationen an BunkerNet teilt Ihre Instanz nur die zur Identifizierung der Bedrohung erforderlichen Daten: die IP-Adresse, den Grund für die Sperrung und minimale kontextbezogene Daten. Es werden keine persönlichen Informationen über Ihre Benutzer oder sensible Details über Ihre Website weitergegeben.

### Beispielkonfigurationen

=== "Standardkonfiguration (empfohlen)"

    Die Standardkonfiguration aktiviert BunkerNet mit dem offiziellen BunkerWeb-API-Server:

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://api.bunkerweb.io"
    ```

=== "Deaktivierte Konfiguration"

    Wenn Sie nicht am BunkerNet-Bedrohungsdatennetzwerk teilnehmen möchten:

    ```yaml
    USE_BUNKERNET: "no"
    ```

=== "Benutzerdefinierte Serverkonfiguration"

    Für Organisationen, die ihren eigenen BunkerNet-Server betreiben (ungewöhnlich):

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://bunkernet.example.com"
    ```

### Integration der CrowdSec-Konsole

Falls Sie noch nicht mit der CrowdSec-Konsolenintegration vertraut sind: [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) nutzt crowdsourced Intelligence zur Bekämpfung von Cyber-Bedrohungen. Stellen Sie es sich als das „Waze der Cybersicherheit“ vor – wenn ein Server angegriffen wird, werden andere Systeme weltweit alarmiert und vor denselben Angreifern geschützt. Mehr darüber erfahren Sie [hier](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

Durch unsere Partnerschaft mit CrowdSec können Sie Ihre BunkerWeb-Instanzen in Ihre [CrowdSec-Konsole](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration) eintragen. Das bedeutet, dass von BunkerWeb blockierte Angriffe in Ihrer CrowdSec-Konsole neben den von CrowdSec Security Engines blockierten Angriffen sichtbar sind, was Ihnen einen einheitlichen Überblick über Bedrohungen gibt.

Wichtig ist, dass CrowdSec für diese Integration nicht installiert sein muss (obwohl wir dringend empfehlen, es mit dem [CrowdSec-Plugin für BunkerWeb](https://github.com/bunkerity/bunkerweb-plugins/tree/main/crowdsec) auszuprobieren, um die Sicherheit Ihrer Webdienste weiter zu erhöhen). Zusätzlich können Sie Ihre CrowdSec Security Engines in dasselbe Konsolenkonto eintragen, um eine noch größere Synergie zu erzielen.

**Schritt 1: Erstellen Sie Ihr CrowdSec-Konsolenkonto**

Gehen Sie zur [CrowdSec-Konsole](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration) und registrieren Sie sich, falls Sie noch kein Konto haben. Notieren Sie sich anschließend den Anmeldeschlüssel, den Sie unter „Security Engines“ finden, nachdem Sie auf „Add Security Engine“ geklickt haben:

<figure markdown>
  ![Overview](assets/img/crowdity1.png){ align=center }
  <figcaption>Holen Sie sich Ihren CrowdSec-Konsolen-Anmeldeschlüssel</figcaption>
</figure>

**Schritt 2: Holen Sie sich Ihre BunkerNet-ID**

Die Aktivierung der BunkerNet-Funktion (standardmäßig aktiviert) ist obligatorisch, wenn Sie Ihre BunkerWeb-Instanz(en) in Ihrer CrowdSec-Konsole registrieren möchten. Aktivieren Sie sie, indem Sie `USE_BUNKERNET` auf `yes` setzen.

Für Docker erhalten Sie Ihre BunkerNet-ID mit:

```shell
docker exec my-bw-scheduler cat /var/cache/bunkerweb/bunkernet/instance.id
```

Für Linux verwenden Sie:

```shell
cat /var/cache/bunkerweb/bunkernet/instance.id
```

**Schritt 3: Registrieren Sie Ihre Instanz über das Panel**

Sobald Sie Ihre BunkerNet-ID und den CrowdSec-Konsolen-Anmeldeschlüssel haben, [bestellen Sie das kostenlose Produkt „BunkerNet / CrowdSec“ im Panel](https://panel.bunkerweb.io/store/bunkernet?utm_campaign=self&utm_source=doc). Möglicherweise werden Sie aufgefordert, ein Konto zu erstellen, falls Sie noch keines haben.

Sie können nun den Dienst „BunkerNet / CrowdSec“ auswählen und das Formular ausfüllen, indem Sie Ihre BunkerNet-ID und den CrowdSec-Konsolen-Anmeldeschlüssel einfügen:

<figure markdown>
  ![Overview](assets/img/crowdity2.png){ align=center }
  <figcaption>Registrieren Sie Ihre BunkerWeb-Instanz in der CrowdSec-Konsole</figcaption>
</figure>

**Schritt 4: Akzeptieren Sie die neue Security Engine in der Konsole**

Gehen Sie dann zurück zu Ihrer CrowdSec-Konsole und akzeptieren Sie die neue Security Engine:

<figure markdown>
  ![Overview](assets/img/crowdity3.png){ align=center }
  <figcaption>Akzeptieren Sie die Registrierung in der CrowdSec-Konsole</figcaption>
</figure>

**Herzlichen Glückwunsch, Ihre BunkerWeb-Instanz ist jetzt in Ihrer CrowdSec-Konsole registriert!**

Profi-Tipp: Wenn Sie Ihre Warnungen anzeigen, klicken Sie auf die Option „Spalten“ und aktivieren Sie das Kontrollkästchen „Kontext“, um auf BunkerWeb-spezifische Daten zuzugreifen.

<figure markdown>
  ![Overview](assets/img/crowdity4.png){ align=center }
  <figcaption>BunkerWeb-Daten werden in der Kontextspalte angezeigt</figcaption>
</figure>
