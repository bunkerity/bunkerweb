Das HTML-Injection-Plugin ermöglicht es Ihnen, nahtlos benutzerdefinierten HTML-Code zu den Seiten Ihrer Website vor den schließenden `</body>`- oder `</head>`-Tags hinzuzufügen. Diese Funktion ist besonders nützlich, um Analyses-Skripte, Tracking-Pixel, benutzerdefiniertes JavaScript, CSS-Stile oder andere Integrationen von Drittanbietern hinzuzufügen, ohne den Quellcode Ihrer Website ändern zu müssen.

**So funktioniert es:**

1.  Wenn eine Seite von Ihrer Website ausgeliefert wird, untersucht BunkerWeb die HTML-Antwort.
2.  Wenn Sie die Body-Injection konfiguriert haben, fügt BunkerWeb Ihren benutzerdefinierten HTML-Code direkt vor dem schließenden `</body>`-Tag ein.
3.  Wenn Sie die Head-Injection konfiguriert haben, fügt BunkerWeb Ihren benutzerdefinierten HTML-Code direkt vor dem schließenden `</head>`-Tag ein.
4.  Das Einfügen erfolgt automatisch für alle HTML-Seiten, die von Ihrer Website ausgeliefert werden.
5.  Dies ermöglicht es Ihnen, Skripte, Stile oder andere Elemente hinzuzufügen, ohne den Code Ihrer Anwendung ändern zu müssen.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die HTML-Injection-Funktion zu konfigurieren und zu verwenden:

1.  **Bereiten Sie Ihren benutzerdefinierten HTML-Code vor:** Entscheiden Sie, welchen HTML-Code Sie in Ihre Seiten einfügen möchten.
2.  **Wählen Sie die Einfügeorte:** Bestimmen Sie, ob Sie Code im `<head>`-Bereich, im `<body>`-Bereich oder in beiden einfügen müssen.
3.  **Konfigurieren Sie die Einstellungen:** Fügen Sie Ihren benutzerdefinierten HTML-Code zu den entsprechenden Einstellungen (`INJECT_HEAD` und/oder `INJECT_BODY`) hinzu.
4.  **Lassen Sie BunkerWeb den Rest erledigen:** Nach der Konfiguration wird der HTML-Code automatisch in alle ausgelieferten HTML-Seiten eingefügt.

### Konfigurationseinstellungen

| Einstellung   | Standard | Kontext   | Mehrfach | Beschreibung                                                                 |
| ------------- | -------- | --------- | -------- | ---------------------------------------------------------------------------- |
| `INJECT_HEAD` |          | multisite | nein     | **Head-HTML-Code:** Der HTML-Code, der vor dem `</head>`-Tag eingefügt wird. |
| `INJECT_BODY` |          | multisite | nein     | **Body-HTML-Code:** Der HTML-Code, der vor dem `</body>`-Tag eingefügt wird. |

!!! tip "Bewährte Praktiken" - Aus Leistungsgründen sollten Sie JavaScript-Dateien am Ende des Body platzieren, um das Rendern nicht zu blockieren. - Platzieren Sie CSS und kritisches JavaScript im Head-Bereich, um ein Aufblitzen von ungestyltem Inhalt zu vermeiden. - Seien Sie vorsichtig mit eingefügtem Inhalt, der die Funktionalität Ihrer Website beeinträchtigen könnte.

!!! info "Häufige Anwendungsfälle" - Hinzufügen von Analyses-Skripten (wie Google Analytics, Matomo) - Integration von Chat-Widgets oder Kundensupport-Tools - Einbinden von Tracking-Pixeln für Marketingkampagnen - Hinzufügen von benutzerdefinierten CSS-Stilen oder JavaScript-Funktionen - Einbinden von Bibliotheken von Drittanbietern, ohne den Anwendungscode zu ändern

### Beispielkonfigurationen

=== "Google Analytics"

    Hinzufügen von Google-Analytics-Tracking zu Ihrer Website:

    ```yaml
    INJECT_HEAD: ""
    INJECT_BODY: "<script async src=\"https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX\"></script><script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag('js', new Date());gtag('config', 'G-XXXXXXXXXX');</script>"
    ```

=== "Benutzerdefinierte Stile"

    Hinzufügen von benutzerdefinierten CSS-Stilen zu Ihrer Website:

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .custom-element { color: blue; }</style>"
    INJECT_BODY: ""
    ```

=== "Mehrere Integrationen"

    Hinzufügen von sowohl benutzerdefinierten Stilen als auch JavaScript:

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .notification-banner { background: #f8f9fa; padding: 10px; text-align: center; }</style>"
    INJECT_BODY: "<script src=\"https://cdn.example.com/js/widget.js\"></script><script>initializeWidget('your-api-key');</script>"
    ```

=== "Cookie-Einwilligungsbanner"

    Hinzufügen eines einfachen Cookie-Einwilligungsbanners:

    ```yaml
    INJECT_HEAD: "<style>.cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #f1f1f1; padding: 20px; text-align: center; z-index: 1000; } .cookie-banner button { background: #4CAF50; border: none; color: white; padding: 10px 20px; cursor: pointer; }</style>"
    INJECT_BODY: "<div id=\"cookie-banner\" class=\"cookie-banner\">Diese Website verwendet Cookies, um sicherzustellen, dass Sie das beste Erlebnis erhalten. <button onclick=\"acceptCookies()\">Akzeptieren</button></div><script>function acceptCookies() { document.getElementById('cookie-banner').style.display = 'none'; localStorage.setItem('cookies-accepted', 'true'); } if(localStorage.getItem('cookies-accepted') === 'true') { document.getElementById('cookie-banner').style.display = 'none'; }</script>"
    ```
