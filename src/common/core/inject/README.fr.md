Le plugin d’injection HTML permet d’ajouter du code HTML personnalisé dans les pages de votre site juste avant `</body>` ou `</head>`. Idéal pour intégrer des scripts d’analytics, pixels de tracking, JS/CSS personnalisés ou des intégrations tierces sans modifier le code source de votre application.

Comment ça marche :

1. À la livraison d’une page, BunkerWeb inspecte la réponse HTML.
2. Si l’injection « body » est configurée, il insère votre HTML juste avant `</body>`.
3. Si l’injection « head » est configurée, il insère votre HTML juste avant `</head>`.
4. L’insertion s’applique automatiquement à toutes les pages HTML servies.

### Comment l’utiliser

1. Préparez votre HTML personnalisé.
2. Choisissez l’emplacement : `<head>`, `<body>`, ou les deux.
3. Renseignez `INJECT_HEAD` et/ou `INJECT_BODY` avec votre code.

### Paramètres

| Paramètre     | Défaut | Contexte  | Multiple | Description                        |
| ------------- | ------ | --------- | -------- | ---------------------------------- |
| `INJECT_HEAD` |        | multisite | non      | Code HTML injecté avant `</head>`. |
| `INJECT_BODY` |        | multisite | non      | Code HTML injecté avant `</body>`. |

!!! tip "Bonnes pratiques" - Placez de préférence les scripts JS en fin de body pour éviter de bloquer le rendu. - Mettez le CSS et le JS critique dans le head pour éviter le flash de contenu non stylé. - Attention au contenu injecté qui pourrait casser le site.

### Exemples

=== "Google Analytics"

    ```yaml
    INJECT_HEAD: ""
    INJECT_BODY: '<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script><script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag(''js'', new Date());gtag(''config'', ''G-XXXXXXXXXX'');</script>'
    ```

=== "Styles personnalisés"

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .custom-element { color: blue; }</style>"
    INJECT_BODY: ""
    ```

=== "Intégrations multiples"

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .notification-banner { background: #f8f9fa; padding: 10px; text-align: center; }</style>"
    INJECT_BODY: '<script src="https://cdn.example.com/js/widget.js"></script><script>initializeWidget(''your-api-key'');</script>'
    ```

=== "Bandeau cookies"

    ```yaml
    INJECT_HEAD: "<style>.cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #f1f1f1; padding: 20px; text-align: center; z-index: 1000; } .cookie-banner button { background: #4CAF50; border: none; color: white; padding: 10px 20px; cursor: pointer; }</style>"
    INJECT_BODY: '<div id="cookie-banner" class="cookie-banner">This website uses cookies to ensure you get the best experience. <button onclick="acceptCookies()">Accept</button></div><script>function acceptCookies() { document.getElementById(''cookie-banner'').style.display = ''none''; localStorage.setItem(''cookies-accepted'', ''true''); } if(localStorage.getItem(''cookies-accepted'') === ''true'') { document.getElementById(''cookie-banner'').style.display = ''none''; }</script>'
    ```
