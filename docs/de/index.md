# Einführung

## Übersicht

<figure markdown>
  ![Übersicht](assets/img/intro-overview.svg){ align=center, width="800" }
  <figcaption>Machen Sie Ihre Webdienste standardmäßig sicher!</figcaption>
</figure>

BunkerWeb ist eine Open-Source-Webanwendungs-Firewall (WAF) der nächsten Generation.

Als vollwertiger Webserver (basierend auf [NGINX](https://nginx.org/) im Hintergrund) schützt es Ihre Webdienste, um sie "standardmäßig sicher" zu machen. BunkerWeb lässt sich nahtlos in Ihre bestehenden Umgebungen integrieren ([Linux](integrations.md#linux), [Docker](integrations.md#docker), [Swarm](integrations.md#swarm), [Kubernetes](integrations.md#kubernetes), …) als Reverse-Proxy und ist vollständig konfigurierbar (keine Panik, es gibt eine [großartige Weboberfläche](web-ui.md), wenn Sie die CLI nicht mögen), um Ihre spezifischen Anwendungsfälle zu erfüllen. Mit anderen Worten, Cybersicherheit ist kein Aufwand mehr.

BunkerWeb enthält primäre [Sicherheitsfunktionen](advanced.md#security-tuning) als Teil des Kerns, kann aber dank eines [Pluginsystems](plugins.md) leicht um zusätzliche erweitert werden.

## Warum BunkerWeb?

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/oybLtyhWJIo" title="BunkerWeb-Übersicht" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

- **Einfache Integration in bestehende Umgebungen**: Integrieren Sie BunkerWeb nahtlos in verschiedene Umgebungen wie Linux, Docker, Swarm, Kubernetes und mehr. Genießen Sie einen reibungslosen Übergang und eine problemlose Implementierung.

- **Hochgradig anpassbar**: Passen Sie BunkerWeb mühelos an Ihre spezifischen Anforderungen an. Aktivieren, deaktivieren und konfigurieren Sie Funktionen mühelos, sodass Sie die Sicherheitseinstellungen an Ihren einzigartigen Anwendungsfall anpassen können.

- **Standardmäßig sicher**: BunkerWeb bietet eine sofort einsatzbereite, problemlose minimale Sicherheit für Ihre Webdienste. Erleben Sie von Anfang an Sorgenfreiheit und verbesserten Schutz.

- **Großartige Weboberfläche**: Steuern Sie BunkerWeb effizienter mit der außergewöhnlichen Web-Benutzeroberfläche (UI). Navigieren Sie mühelos durch Einstellungen und Konfigurationen über eine benutzerfreundliche grafische Oberfläche, sodass die Befehlszeilenschnittstelle (CLI) nicht mehr erforderlich ist.

- **Pluginsystem**: Erweitern Sie die Funktionen von BunkerWeb, um Ihre eigenen Anwendungsfälle zu erfüllen. Integrieren Sie nahtlos zusätzliche Sicherheitsmaßnahmen und passen Sie die Funktionalität von BunkerWeb an Ihre spezifischen Anforderungen an.

- **Frei wie in "Freiheit"**: BunkerWeb ist unter der freien [AGPLv3-Lizenz](https://www.gnu.org/licenses/agpl-3.0.en.html) lizenziert und folgt den Prinzipien von Freiheit und Offenheit. Genießen Sie die Freiheit, die Software zu verwenden, zu ändern und zu verbreiten, unterstützt von einer unterstützenden Community.

- **Professionelle Dienstleistungen**: Erhalten Sie technischen Support, maßgeschneiderte Beratung und kundenspezifische Entwicklung direkt von den Betreuern von BunkerWeb. Besuchen Sie das [BunkerWeb Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc) für weitere Informationen.

## Sicherheitsfunktionen

Entdecken Sie die beeindruckende Auswahl an Sicherheitsfunktionen, die BunkerWeb bietet. Obwohl nicht vollständig, hier einige bemerkenswerte Highlights:

- **HTTPS**-Unterstützung mit transparenter **Let's Encrypt**-Automatisierung: Sichern Sie Ihre Webdienste einfach mit automatisierter Let's Encrypt-Integration und gewährleisten Sie eine verschlüsselte Kommunikation zwischen Clients und Ihrem Server.

- **Modernste Websicherheit**: Profitieren Sie von modernsten Websicherheitsmaßnahmen, einschließlich umfassender HTTP-Sicherheitsheader, Verhinderung von Datenlecks und TLS-Härtungstechniken.

- Integrierte **ModSecurity WAF** mit dem **OWASP Core Rule Set**: Genießen Sie einen verbesserten Schutz vor Webanwendungsangriffen durch die Integration von ModSecurity, verstärkt durch das renommierte OWASP Core Rule Set.

- **Automatisches Sperren** von seltsamem Verhalten basierend auf HTTP-Statuscodes: BunkerWeb identifiziert und blockiert intelligent verdächtige Aktivitäten, indem es Verhaltensweisen, die anormale HTTP-Statuscodes auslösen, automatisch sperrt.

- **Anwenden von Verbindungs- und Anforderungslimits** für Clients: Setzen Sie Limits für die Anzahl der Verbindungen und Anfragen von Clients, um eine Ressourcenerschöpfung zu verhindern und eine faire Nutzung der Serverressourcen zu gewährleisten.

- **Blockieren von Bots** mit **herausforderungsbasierter Überprüfung**: Halten Sie bösartige Bots in Schach, indem Sie sie herausfordern, Rätsel wie Cookies, JavaScript-Tests, Captchas, hCaptcha, reCAPTCHA oder Turnstile zu lösen, und so unbefugten Zugriff effektiv blockieren.

- **Blockieren bekannter bösartiger IPs** mit externen Blacklists und **DNSBL**: Nutzen Sie externe Blacklists und DNS-basierte Blackhole-Listen (DNSBL), um bekannte bösartige IP-Adressen proaktiv zu blockieren und Ihre Verteidigung gegen potenzielle Bedrohungen zu stärken.

- **Und vieles mehr...**: BunkerWeb ist mit einer Fülle zusätzlicher Sicherheitsfunktionen ausgestattet, die über diese Liste hinausgehen und Ihnen umfassenden Schutz und Sorgenfreiheit bieten.

Um tiefer in die Kernsicherheitsfunktionen einzutauchen, laden wir Sie ein, den Abschnitt [Sicherheits-Tuning](advanced.md#security-tuning) der Dokumentation zu erkunden. Entdecken Sie, wie BunkerWeb Sie befähigt, Sicherheitsmaßnahmen entsprechend Ihren spezifischen Bedürfnissen zu optimieren.

## Demo

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/ZhYV-QELzA4" title="Automatisierte Tools und Scanner täuschen" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Eine mit BunkerWeb geschützte Demo-Website ist unter [demo.bunkerweb.io](https://demo.bunkerweb.io/?utm_campaign=self&utm_source=doc) verfügbar. Besuchen Sie sie gerne und führen Sie einige Sicherheitstests durch.

## Web-Benutzeroberfläche

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/tGS3pzquEjY" title="BunkerWeb-Web-UI" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

BunkerWeb bietet eine optionale [Benutzeroberfläche](web-ui.md) zur Verwaltung Ihrer Instanzen und deren Konfigurationen. Eine schreibgeschützte Online-Demo ist unter [demo-ui.bunkerweb.io](https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=doc) verfügbar. Testen Sie sie gerne selbst.

## BunkerWeb Cloud

<figure markdown>
  ![Übersicht](assets/img/bunkerweb-cloud.webp){ align=center, width="600" }
  <figcaption>BunkerWeb Cloud</figcaption>
</figure>

Möchten Sie Ihre eigene(n) BunkerWeb-Instanz(en) nicht selbst hosten und verwalten? Dann könnte Sie BunkerWeb Cloud interessieren, unser vollständig verwaltetes SaaS-Angebot für BunkerWeb.

Bestellen Sie Ihre [BunkerWeb Cloud-Instanz](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=doc) und erhalten Sie Zugang zu:

- Eine vollständig verwaltete BunkerWeb-Instanz, die in unserer Cloud gehostet wird
- Alle BunkerWeb-Funktionen, einschließlich der PRO-Funktionen
- Eine Überwachungsplattform mit Dashboards und Warnungen
- Technischer Support zur Unterstützung bei der Konfiguration

Wenn Sie am BunkerWeb Cloud-Angebot interessiert sind, zögern Sie nicht, uns zu [kontaktieren](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc), damit wir Ihre Bedürfnisse besprechen können.

## PRO-Version

!!! tip "Kostenlose Testversion von BunkerWeb PRO"
    Möchten Sie BunkerWeb PRO einen Monat lang schnell testen? Verwenden Sie den Code `freetrial` bei Ihrer Bestellung im [BunkerWeb Panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) oder klicken Sie [hier](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc), um den Promo-Code direkt anzuwenden (wird an der Kasse wirksam).

Bei der Verwendung von BunkerWeb haben Sie die Wahl zwischen der Open-Source- oder der PRO-Version.

Ob verbesserte Sicherheit, ein bereichertes Benutzererlebnis oder technische Überwachung, die BunkerWeb PRO-Version ermöglicht es Ihnen, BunkerWeb in vollem Umfang zu nutzen und Ihre beruflichen Anforderungen zu erfüllen.

In der Dokumentation oder der Benutzeroberfläche sind PRO-Funktionen mit einer Krone <img src="../../assets/img/pro-icon.svg" alt="Kronen-Pro-Symbol" height="32px" width="32px"> gekennzeichnet, um sie von denen der Open-Source-Version zu unterscheiden.

Sie können jederzeit einfach von der Open-Source-Version auf die PRO-Version upgraden. Der Vorgang ist unkompliziert:

- Fordern Sie Ihre [kostenlose Testversion im BunkerWeb-Panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) an, indem Sie den Promo-Code `freetrial` an der Kasse verwenden.
- Sobald Sie im Kundenbereich angemeldet sind, kopieren Sie Ihren PRO-Lizenzschlüssel.
- Fügen Sie Ihren privaten Schlüssel in BunkerWeb über die [Web-UI](web-ui.md#upgrade-to-pro) oder eine [spezifische Einstellung](features.md#pro) ein.

Zögern Sie nicht, das [BunkerWeb-Panel](https://panel.bunkerweb.io/knowledgebase?utm_campaign=self&utm_source=doc) zu besuchen oder uns zu [kontaktieren](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc), wenn Sie Fragen zur PRO-Version haben.

## Professionelle Dienstleistungen

Holen Sie das Beste aus BunkerWeb heraus, indem Sie professionelle Dienstleistungen direkt von den Betreuern des Projekts in Anspruch nehmen. Von technischem Support über maßgeschneiderte Beratung bis hin zur Entwicklung sind wir hier, um Sie bei der Sicherung Ihrer Webdienste zu unterstützen.

Weitere Informationen finden Sie im [BunkerWeb Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc), unserer dedizierten Plattform für professionelle Dienstleistungen.

Zögern Sie nicht, uns zu [kontaktieren](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc), wenn Sie Fragen haben. Wir freuen uns, auf Ihre Bedürfnisse einzugehen.

## Ökosystem, Community und Ressourcen

Offizielle Websites, Tools und Ressourcen zu BunkerWeb:

- [**Website**](https://www.bunkerweb.io/?utm_campaign=self&utm_source=doc): Erhalten Sie weitere Informationen, Neuigkeiten und Artikel über BunkerWeb.
- [**Panel**](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc): Eine dedizierte Plattform zur Bestellung und Verwaltung professioneller Dienstleistungen (z. B. technischer Support) rund um BunkerWeb.
- [**Dokumentation**](https://docs.bunkerweb.io): Technische Dokumentation der BunkerWeb-Lösung.
- [**Demo**](https://demo.bunkerweb.io/?utm_campaign=self&utm_source=doc): Demonstrationswebsite von BunkerWeb. Zögern Sie nicht, Angriffe zu versuchen, um die Robustheit der Lösung zu testen.
- [**Web-UI**](https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=doc): Schreibgeschützte Online-Demo der Web-UI von BunkerWeb.
- [**Threatmap**](https://www.bunkerweb.io/threatmap/?utm_campaign=self&utm_source=doc): Live-Cyberangriffe, die von BunkerWeb-Instanzen auf der ganzen Welt blockiert werden.
- [**Status**](https://status.bunkerweb.io/?utm_campaign=self&utm_source=doc): Live-Status- und Verfügbarkeitsupdates für BunkerWeb-Dienste.

Community und soziale Netzwerke:

- [**Discord**](https://discord.com/invite/fTf46FmtyD)
- [**LinkedIn**](https://www.linkedin.com/company/bunkerity/)
- [**X (ehemals Twitter)**](https://x.com/bunkerity)
- [**Reddit**](https://www.reddit.com/r/BunkerWeb/)
