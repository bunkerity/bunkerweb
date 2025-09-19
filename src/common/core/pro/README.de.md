Das Pro-Plugin bündelt erweiterte Funktionen und Verbesserungen für Unternehmensbereitstellungen von BunkerWeb. Es schaltet zusätzliche Funktionen, Premium-Plugins und erweiterte Funktionalität frei, die die Kernplattform von BunkerWeb ergänzen. Es bietet verbesserte Sicherheit, Leistung und Verwaltungsoptionen für unternehmenstaugliche Bereitstellungen.

**So funktioniert es:**

1.  Mit einem gültigen Pro-Lizenzschlüssel verbindet sich BunkerWeb mit dem Pro-API-Server, um Ihr Abonnement zu validieren.
2.  Nach der Authentifizierung lädt das Plugin automatisch Pro-exklusive Plugins und Erweiterungen herunter und installiert sie.
3.  Ihr Pro-Status wird regelmäßig überprüft, um den fortgesetzten Zugriff auf Premium-Funktionen sicherzustellen.
4.  Premium-Plugins werden nahtlos in Ihre bestehende BunkerWeb-Konfiguration integriert.
5.  Alle Pro-Funktionen arbeiten harmonisch mit dem Open-Source-Kern zusammen und erweitern die Funktionalität, anstatt sie zu ersetzen.

!!! success "Wichtige Vorteile"

      1. **Premium-Erweiterungen:** Zugriff auf exklusive Plugins und Funktionen, die in der Community-Edition nicht verfügbar sind.
      2. **Verbesserte Leistung:** Optimierte Konfigurationen und fortschrittliche Caching-Mechanismen.
      3. **Unternehmens-Support:** Vorrangige Unterstützung und dedizierte Support-Kanäle.
      4. **Nahtlose Integration:** Pro-Funktionen arbeiten ohne Konfigurationskonflikte neben den Community-Funktionen.
      5. **Automatische Updates:** Premium-Plugins werden automatisch heruntergeladen und auf dem neuesten Stand gehalten.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Pro-Funktionen zu konfigurieren und zu verwenden:

1.  **Lizenzschlüssel erhalten:** Kaufen Sie eine Pro-Lizenz im [BunkerWeb Panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc).
2.  **Lizenzschlüssel konfigurieren:** Verwenden Sie die Einstellung `PRO_LICENSE_KEY`, um Ihre Lizenz zu konfigurieren.
3.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration mit einer gültigen Lizenz werden Pro-Plugins automatisch heruntergeladen und aktiviert.
4.  **Überwachen Sie Ihren Pro-Status:** Überprüfen Sie die Zustandsindikatoren in der [Web-Benutzeroberfläche](web-ui.md), um Ihren Pro-Abonnementstatus zu bestätigen.

### Konfigurationseinstellungen

| Einstellung       | Standard | Kontext | Mehrfach | Beschreibung                                                                      |
| ----------------- | -------- | ------- | -------- | --------------------------------------------------------------------------------- |
| `PRO_LICENSE_KEY` |          | global  | nein     | **Pro-Lizenzschlüssel:** Ihr BunkerWeb Pro-Lizenzschlüssel zur Authentifizierung. |

!!! tip "Lizenzverwaltung"
Ihre Pro-Lizenz ist an Ihre spezifische Bereitstellungsumgebung gebunden. Wenn Sie Ihre Lizenz übertragen müssen oder Fragen zu Ihrem Abonnement haben, wenden Sie sich bitte über das [BunkerWeb Panel](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) an den Support.

!!! info "Pro-Funktionen"
Die spezifischen verfügbaren Pro-Funktionen können sich im Laufe der Zeit weiterentwickeln, wenn neue Funktionen hinzugefügt werden. Das Pro-Plugin übernimmt automatisch die Installation und Konfiguration aller verfügbaren Funktionen.

!!! warning "Netzwerkanforderungen"
Das Pro-Plugin benötigt ausgehenden Internetzugang, um sich zur Lizenzüberprüfung mit der BunkerWeb-API zu verbinden und Premium-Plugins herunterzuladen. Stellen Sie sicher, dass Ihre Firewall Verbindungen zu `api.bunkerweb.io` auf Port 443 (HTTPS) zulässt.

### Häufig gestellte Fragen

**F: Was passiert, wenn meine Pro-Lizenz abläuft?**

A: Wenn Ihre Pro-Lizenz abläuft, wird der Zugriff auf Premium-Funktionen und -Plugins deaktiviert. Ihre BunkerWeb-Installation wird jedoch weiterhin mit allen Funktionen der Community-Edition betrieben. Um wieder Zugriff auf die Pro-Funktionen zu erhalten, erneuern Sie einfach Ihre Lizenz.

**F: Werden die Pro-Funktionen meine bestehende Konfiguration stören?**

A: Nein, die Pro-Funktionen sind so konzipiert, dass sie sich nahtlos in Ihr aktuelles BunkerWeb-Setup integrieren. Sie erweitern die Funktionalität, ohne Ihre bestehende Konfiguration zu verändern oder zu stören, und gewährleisten so ein reibungsloses und zuverlässiges Erlebnis.

**F: Kann ich die Pro-Funktionen vor dem Kauf ausprobieren?**

A: Auf jeden Fall! BunkerWeb bietet zwei Pro-Pläne, die Ihren Bedürfnissen entsprechen:

- **BunkerWeb PRO Standard:** Voller Zugriff auf die Pro-Funktionen ohne technischen Support.
- **BunkerWeb PRO Enterprise:** Voller Zugriff auf die Pro-Funktionen mit dediziertem technischen Support.

Sie können die Pro-Funktionen mit einer kostenlosen 1-monatigen Testversion erkunden, indem Sie den Promo-Code `freetrial` verwenden. Besuchen Sie das [BunkerWeb Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc), um Ihre Testversion zu aktivieren und mehr über flexible Preisoptionen basierend auf der Anzahl der von BunkerWeb PRO geschützten Dienste zu erfahren.
