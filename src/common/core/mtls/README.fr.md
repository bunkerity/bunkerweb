Le plugin Mutual TLS (mTLS) protège vos applications sensibles en exigeant que les clients présentent des certificats délivrés par des autorités que vous maîtrisez. Une fois activé, BunkerWeb authentifie les appelants avant que leurs requêtes n’atteignent vos services, ce qui sécurise vos outils internes et intégrations partenaires.

BunkerWeb évalue chaque poignée de main TLS en fonction du bundle d’AC et de la politique que vous définissez. Les clients qui ne répondent pas aux règles sont bloqués, tandis que les connexions conformes peuvent transmettre les détails du certificat aux applications amont pour une autorisation affinée.

**Fonctionnement :**

1. Le plugin surveille les échanges HTTPS du site sélectionné.
2. Pendant l’échange TLS, BunkerWeb inspecte le certificat client et vérifie sa chaîne par rapport à votre magasin de confiance.
3. Le mode de vérification détermine si les clients non authentifiés sont rejetés, acceptés avec tolérance ou autorisés pour des diagnostics.
4. (Optionnel) BunkerWeb expose le résultat via les en-têtes `X-SSL-Client-*` afin que vos applications puissent appliquer leur propre logique d’accès.

!!! success "Avantages clés"

      1. **Contrôle renforcé :** limitez l’accès aux machines et utilisateurs authentifiés.
      2. **Politiques souples :** combinez modes stricts et optionnels pour accompagner vos workflows.
      3. **Visibilité applicative :** transférez empreintes et identités de certificats pour l’audit.
      4. **Défense en profondeur :** associez mTLS aux autres plugins BunkerWeb pour multiplier les protections.

### Mise en œuvre

Suivez ces étapes pour déployer le mutual TLS sereinement :

1. **Activer la fonctionnalité :** positionnez `USE_MTLS` à `yes` sur les sites qui nécessitent l’authentification par certificat.
2. **Fournir le bundle d’AC :** stockez vos autorités de confiance dans un fichier PEM et renseignez `MTLS_CA_CERTIFICATE` avec son chemin absolu.
3. **Choisir le mode de vérification :** sélectionnez `on` pour rendre les certificats obligatoires, `optional` pour offrir un repli ou `optional_no_ca` pour un diagnostic temporaire.
4. **Ajuster la profondeur de chaîne :** adaptez `MTLS_VERIFY_DEPTH` si votre organisation utilise plusieurs intermédiaires.
5. **Transmettre le résultat (optionnel) :** laissez `MTLS_FORWARD_CLIENT_HEADERS` à `yes` si vos services amont doivent inspecter le certificat présenté.
6. **Maintenir la révocation :** si vous publiez une CRL, renseignez `MTLS_CRL` pour que BunkerWeb refuse les certificats révoqués.

### Paramètres de configuration

| Paramètre                     | Valeur par défaut | Contexte | Multiple | Description                                                                                                                                             |
| ----------------------------- | ----------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                    | `no`              | multisite | non      | **Activer le mutual TLS :** active l’authentification par certificat client pour le site courant.                                                       |
| `MTLS_CA_CERTIFICATE`         |                   | multisite | non      | **Bundle d’AC client :** chemin absolu vers le bundle d’AC clients (PEM). Requis lorsque `MTLS_VERIFY_CLIENT` vaut `on` ou `optional`; doit être lisible. |
| `MTLS_VERIFY_CLIENT`          | `on`              | multisite | non      | **Mode de vérification :** choisissez si les certificats sont requis (`on`), optionnels (`optional`) ou acceptés sans validation d’AC (`optional_no_ca`). |
| `MTLS_VERIFY_DEPTH`           | `2`               | multisite | non      | **Profondeur de vérification :** profondeur maximale de chaîne acceptée pour les certificats clients.                                                   |
| `MTLS_FORWARD_CLIENT_HEADERS` | `yes`             | multisite | non      | **Transmettre les en-têtes client :** propage les résultats de vérification (`X-SSL-Client-*` avec statut, DN, émetteur, numéro de série, empreinte, validité). |
| `MTLS_CRL`                    |                   | multisite | non      | **Chemin de la CRL client :** chemin optionnel vers une liste de révocation de certificats encodée en PEM. Appliqué uniquement si le bundle d’AC est chargé avec succès. |

!!! tip "Maintenez les certificats à jour"
    Stockez bundles d’AC et listes de révocation dans un volume monté accessible par le Scheduler pour que chaque redémarrage récupère les ancrages de confiance récents.

!!! warning "Bundle d’AC obligatoire en mode strict"
    Lorsque `MTLS_VERIFY_CLIENT` vaut `on` ou `optional`, le fichier d’AC doit être présent à l’exécution. S’il manque, BunkerWeb ignore les directives mTLS pour éviter un démarrage sur un chemin invalide. Réservez `optional_no_ca` au diagnostic, car ce mode affaiblit l’authentification.

!!! info "Certificat approuvé vs. vérification"
    BunkerWeb réutilise le même bundle d’AC pour vérifier les clients et bâtir la chaîne de confiance, garantissant une cohérence OCSP/CRL et durant le handshake.

### Exemples de configuration

=== "Contrôle d’accès strict"

    Exigez des certificats clients valides émis par votre AC privée et transmettez les informations de vérification au backend :

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Authentification client optionnelle"

    Autorisez les utilisateurs anonymes mais transmettez les détails du certificat lorsqu’un client en présente un :

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Diagnostic sans AC"

    Autorisez les connexions à aboutir même si un certificat ne peut pas être rattaché à un bundle d’AC de confiance. Utile uniquement pour le dépannage :

    ```yaml
    USE_MTLS: "yes"
    MTLS_VERIFY_CLIENT: "optional_no_ca"
    MTLS_FORWARD_CLIENT_HEADERS: "no"
    ```
