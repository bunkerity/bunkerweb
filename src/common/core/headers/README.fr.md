Les en-têtes HTTP jouent un rôle crucial dans la sécurité. Le plugin Headers offre une gestion robuste des en-têtes HTTP standards et personnalisés, améliorant ainsi la sécurité et les fonctionnalités. Il applique dynamiquement des mesures de sécurité, telles que [HSTS](https://developer.mozilla.org/fr/docs/Web/HTTP/Headers/Strict-Transport-Security), [CSP](https://developer.mozilla.org/fr/docs/Web/HTTP/Headers/Content-Security-Policy) (y compris un mode de rapport seul), et l'injection d'en-têtes personnalisés, tout en empêchant les fuites d'informations.

**Comment ça marche**

1. Lorsqu'un client demande du contenu depuis votre site web, BunkerWeb traite les en-têtes de la réponse.
2. Les en-têtes de sécurité sont appliqués conformément à votre configuration.
3. Des en-têtes personnalisés peuvent être ajoutés pour fournir des informations ou des fonctionnalités supplémentaires aux clients.
4. Les en-têtes indésirables qui pourraient révéler des informations sur le serveur sont automatiquement supprimés.
5. Les cookies sont modifiés pour inclure les attributs de sécurité appropriés en fonction de vos paramètres.
6. Les en-têtes des serveurs en amont peuvent être préservés de manière sélective lorsque cela est nécessaire.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Headers :

1.  **Configurer les en-têtes de sécurité :** Définissez des valeurs pour les en-têtes courants.
2.  **Ajouter des en-têtes personnalisés :** Définissez les en-têtes personnalisés à l'aide du paramètre `CUSTOM_HEADER`.
3.  **Supprimer les en-têtes indésirables :** Utilisez `REMOVE_HEADERS` pour vous assurer que les en-têtes qui pourraient exposer des détails sur le serveur sont supprimés.
4.  **Définir la sécurité des cookies :** Activez une sécurité robuste des cookies en configurant `COOKIE_FLAGS` et en réglant `COOKIE_AUTO_SECURE_FLAG` sur `yes` pour que l'attribut Secure soit automatiquement ajouté sur les connexions HTTPS.
5.  **Préserver les en-têtes en amont :** Spécifiez les en-têtes en amont à conserver en utilisant `KEEP_UPSTREAM_HEADERS`.
6.  **Tirer parti de l'application conditionnelle des en-têtes :** Si vous souhaitez tester des politiques sans interruption, activez le mode [CSP Report-Only](https://developer.mozilla.org/fr/docs/Web/HTTP/Headers/Content-Security-Policy-Report-Only) via `CONTENT_SECURITY_POLICY_REPORT_ONLY`.

### Guide de configuration

=== "En-têtes de sécurité"

    **Aperçu**

    Les en-têtes de sécurité renforcent la communication sécurisée, restreignent le chargement des ressources et préviennent les attaques comme le clickjacking et l'injection. Des en-têtes correctement configurés créent une couche de défense robuste pour votre site web.

    !!! success "Avantages des en-têtes de sécurité"
        - **HSTS :** Assure que toutes les connexions sont chiffrées, protégeant contre les attaques de rétrogradation de protocole.
        - **CSP :** Empêche l'exécution de scripts malveillants, réduisant le risque d'attaques XSS.
        - **X-Frame-Options :** Bloque les tentatives de clickjacking en contrôlant l'intégration des iframes.
        - **Referrer Policy :** Limite les fuites d'informations sensibles via les en-têtes referrer.

    | Paramètre                             | Défaut                                                                                              | Contexte  | Multiple | Description                                                                                                                                               |
    | ------------------------------------- | --------------------------------------------------------------------------------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `STRICT_TRANSPORT_SECURITY`           | `max-age=63072000; includeSubDomains; preload`                                                      | multisite | non      | **HSTS :** Force les connexions HTTPS sécurisées, réduisant les risques d'attaques de type "man-in-the-middle".                                           |
    | `CONTENT_SECURITY_POLICY`             | `object-src 'none'; form-action 'self'; frame-ancestors 'self';`                                    | multisite | non      | **CSP :** Restreint le chargement des ressources aux sources de confiance, atténuant les attaques de type cross-site scripting et d'injection de données. |
    | `CONTENT_SECURITY_POLICY_REPORT_ONLY` | `no`                                                                                                | multisite | non      | **Mode rapport CSP :** Signale les violations sans bloquer le contenu, aidant à tester les politiques de sécurité tout en capturant les journaux.         |
    | `X_FRAME_OPTIONS`                     | `SAMEORIGIN`                                                                                        | multisite | non      | **X-Frame-Options :** Empêche le clickjacking en contrôlant si votre site peut être intégré dans une frame.                                               |
    | `X_CONTENT_TYPE_OPTIONS`              | `nosniff`                                                                                           | multisite | non      | **X-Content-Type-Options :** Empêche les navigateurs de "MIME-sniffer", protégeant contre les attaques de type "drive-by download".                       |
    | `X_DNS_PREFETCH_CONTROL`              | `off`                                                                                               | multisite | non      | **X-DNS-Prefetch-Control :** Régule le préchargement DNS pour réduire les requêtes réseau involontaires et améliorer la confidentialité.                  |
    | `REFERRER_POLICY`                     | `strict-origin-when-cross-origin`                                                                   | multisite | non      | **Politique de Referrer :** Contrôle la quantité d'informations de référent envoyées, protégeant la vie privée de l'utilisateur.                          |
    | `PERMISSIONS_POLICY`                  | `accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), ...` | multisite | non      | **Politique de permissions :** Restreint l'accès aux fonctionnalités du navigateur, réduisant les vecteurs d'attaque potentiels.                          |
    | `KEEP_UPSTREAM_HEADERS`               | `Content-Security-Policy Permissions-Policy X-Frame-Options`                                        | multisite | non      | **Conserver les en-têtes :** Préserve les en-têtes en amont sélectionnés, facilitant l'intégration héritée tout en maintenant la sécurité.                |

    !!! tip "Bonnes pratiques"
        - Révisez et mettez à jour régulièrement vos en-têtes de sécurité pour vous conformer aux normes de sécurité en constante évolution.
        - Utilisez des outils comme [Mozilla Observatory](https://observatory.mozilla.org/) pour valider la configuration de vos en-têtes.
        - Testez la CSP en mode `Report-Only` avant de l'appliquer pour éviter de casser des fonctionnalités.

=== "Paramètres des cookies"

    **Aperçu**

    Des paramètres de cookies appropriés garantissent la sécurité des sessions utilisateur en empêchant le détournement, la fixation et le cross-site scripting. Les cookies sécurisés maintiennent l'intégrité de la session sur HTTPS et améliorent la protection globale des données des utilisateurs.

    !!! success "Avantages des cookies sécurisés"
        - **Attribut HttpOnly :** Empêche les scripts côté client d'accéder aux cookies, atténuant les risques XSS.
        - **Attribut SameSite :** Réduit les attaques CSRF en restreignant l'utilisation des cookies inter-origines.
        - **Attribut Secure :** Assure que les cookies ne sont transmis que sur des connexions HTTPS chiffrées.

    | Paramètre                 | Défaut                    | Contexte  | Multiple | Description                                                                                                                                                                                   |
    | ------------------------- | ------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `COOKIE_FLAGS`            | `* HttpOnly SameSite=Lax` | multisite | oui      | **Attributs de cookie :** Ajoute automatiquement des attributs de sécurité tels que HttpOnly et SameSite, protégeant les cookies de l'accès par des scripts côté client et des attaques CSRF. |
    | `COOKIE_AUTO_SECURE_FLAG` | `yes`                     | multisite | non      | **Attribut Secure automatique :** Assure que les cookies ne sont envoyés que sur des connexions HTTPS sécurisées en ajoutant automatiquement l'attribut Secure.                               |

    !!! tip "Bonnes pratiques"
        - Utilisez `SameSite=Strict` pour les cookies sensibles afin d'empêcher l'accès inter-origines.
        - Auditez régulièrement vos paramètres de cookies pour assurer la conformité avec les réglementations de sécurité et de confidentialité.
        - Évitez de définir des cookies sans l'attribut Secure dans les environnements de production.

=== "En-têtes personnalisés"

    **Aperçu**

    Les en-têtes personnalisés vous permettent d'ajouter des en-têtes HTTP spécifiques pour répondre aux exigences de l'application ou de performance. Ils offrent de la flexibilité mais doivent être configurés avec soin pour éviter d'exposer des détails sensibles du serveur.

    !!! success "Avantages des en-têtes personnalisés"
        - Améliorez la sécurité en supprimant les en-têtes inutiles qui pourraient divulguer des détails sur le serveur.
        - Ajoutez des en-têtes spécifiques à l'application pour améliorer la fonctionnalité ou le débogage.

    | Paramètre        | Défaut                                                                               | Contexte  | Multiple | Description                                                                                                                                                                             |
    | ---------------- | ------------------------------------------------------------------------------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `CUSTOM_HEADER`  |                                                                                      | multisite | oui      | **En-tête personnalisé :** Permet d'ajouter des en-têtes définis par l'utilisateur au format NomEnTete: ValeurEnTete pour des améliorations de sécurité ou de performance spécialisées. |
    | `REMOVE_HEADERS` | `Server Expect-CT X-Powered-By X-AspNet-Version X-AspNetMvc-Version Public-Key-Pins` | multisite | non      | **Supprimer les en-têtes :** Spécifie les en-têtes à supprimer, réduisant ainsi le risque d'exposer des détails internes du serveur et des vulnérabilités connues.                      |

    !!! warning "Considérations de sécurité"
        - Évitez d'exposer des informations sensibles via des en-têtes personnalisés.
        - Révisez et mettez à jour régulièrement les en-têtes personnalisés pour les aligner sur les exigences de votre application.

    !!! tip "Bonnes pratiques"
        - Utilisez `REMOVE_HEADERS` pour supprimer les en-têtes comme `Server` et `X-Powered-By` afin de réduire les risques de prise d'empreintes.
        - Testez les en-têtes personnalisés dans un environnement de pré-production avant de les déployer en production.

### Exemples de configuration

=== "En-têtes de sécurité de base"

    Une configuration standard avec les en-têtes de sécurité essentiels :

    ```yaml
    STRICT_TRANSPORT_SECURITY: "max-age=63072000; includeSubDomains; preload"
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'self'"
    X_FRAME_OPTIONS: "SAMEORIGIN"
    X_CONTENT_TYPE_OPTIONS: "nosniff"
    REFERRER_POLICY: "strict-origin-when-cross-origin"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version"
    ```

=== "Sécurité des cookies renforcée"

    Configuration avec des paramètres de sécurité des cookies robustes :

    ```yaml
    COOKIE_FLAGS: "* HttpOnly SameSite=Strict"
    COOKIE_FLAGS_2: "session_cookie Secure HttpOnly SameSite=Strict"
    COOKIE_FLAGS_3: "auth_cookie Secure HttpOnly SameSite=Strict Max-Age=3600"
    COOKIE_AUTO_SECURE_FLAG: "yes"
    ```

=== "En-têtes personnalisés pour API"

    Configuration pour un service API avec des en-têtes personnalisés :

    ```yaml
    CUSTOM_HEADER: "API-Version: 1.2.3"
    CUSTOM_HEADER_2: "Access-Control-Max-Age: 86400"
    CONTENT_SECURITY_POLICY: "default-src 'none'; frame-ancestors 'none'"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version X-Runtime"
    ```

=== "Content Security Policy - Mode rapport"

    Configuration pour tester la CSP sans casser les fonctionnalités :

    ```yaml
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self' https://trusted-cdn.example.com; img-src 'self' data: https://*.example.com; style-src 'self' 'unsafe-inline' https://trusted-cdn.example.com; connect-src 'self' https://api.example.com; object-src 'none'; frame-ancestors 'self'; form-action 'self'; base-uri 'self'; report-uri https://example.com/csp-reports"
    CONTENT_SECURITY_POLICY_REPORT_ONLY: "yes"
    ```
