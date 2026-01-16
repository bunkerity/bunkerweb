Le plugin ModSecurity intègre le puissant pare-feu applicatif web (WAF) [ModSecurity](https://modsecurity.org) dans BunkerWeb. Cette intégration offre une protection robuste contre un large éventail d'attaques web en s'appuyant sur le [Jeu de Règles de Base OWASP (CRS)](https://coreruleset.org) pour détecter et bloquer des menaces telles que l'injection SQL, le cross-site scripting (XSS), l'inclusion de fichiers locaux, et bien plus encore.

**Comment ça marche :**

1.  Lorsqu'une requête est reçue, ModSecurity l'évalue par rapport au jeu de règles actif.
2.  Le Jeu de Règles de Base OWASP inspecte les en-têtes, les cookies, les paramètres d'URL et le contenu du corps de la requête.
3.  Chaque violation détectée contribue à un score d'anomalie global.
4.  Si ce score dépasse le seuil configuré, la requête est bloquée.
5.  Des journaux détaillés sont créés pour aider à diagnostiquer quelles règles ont été déclenchées et pourquoi.

!!! success "Bénéfices clés"

      1. **Protection standard de l'industrie :** Utilise le pare-feu open-source ModSecurity largement répandu.
      2. **Jeu de Règles de Base OWASP :** Emploie des règles maintenues par la communauté couvrant le Top Dix de l'OWASP et plus encore.
      3. **Niveaux de sécurité configurables :** Ajustez les niveaux de paranoïa pour équilibrer la sécurité avec les faux positifs potentiels.
      4. **Journalisation détaillée :** Fournit des journaux d'audit complets pour l'analyse des attaques.
      5. **Support des plugins :** Étendez la protection avec des plugins CRS optionnels adaptés à vos applications.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser ModSecurity :

1.  **Activer la fonctionnalité :** ModSecurity est activé par défaut. Cela peut être contrôlé via le paramètre `USE_MODSECURITY`.
2.  **Sélectionner une version du CRS :** Choisissez une version du Jeu de Règles de Base OWASP (v3, v4, ou nightly).
3.  **Ajouter des plugins :** Activez optionnellement des plugins CRS pour améliorer la couverture des règles.
4.  **Surveiller et ajuster :** Utilisez les journaux et l'[interface web](web-ui.md) pour identifier les faux positifs et ajuster les paramètres.

### Paramètres de configuration

| Paramètre                             | Défaut         | Contexte  | Multiple | Description                                                                                                                                                                                |
| ------------------------------------- | -------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_MODSECURITY`                     | `yes`          | multisite | no       | **Activer ModSecurity :** Active la protection du pare-feu applicatif web ModSecurity.                                                                                                     |
| `USE_MODSECURITY_CRS`                 | `yes`          | multisite | no       | **Utiliser le Core Rule Set :** Active le Jeu de Règles de Base OWASP pour ModSecurity.                                                                                                    |
| `MODSECURITY_CRS_VERSION`             | `4`            | multisite | no       | **Version du CRS :** La version du Jeu de Règles de Base OWASP à utiliser. Options : `3`, `4`, ou `nightly`.                                                                               |
| `MODSECURITY_SEC_RULE_ENGINE`         | `On`           | multisite | no       | **Moteur de règles :** Contrôle si les règles sont appliquées. Options : `On`, `DetectionOnly`, ou `Off`.                                                                                  |
| `MODSECURITY_SEC_AUDIT_ENGINE`        | `RelevantOnly` | multisite | no       | **Moteur d'audit :** Contrôle le fonctionnement de la journalisation d'audit. Options : `On`, `Off`, ou `RelevantOnly`.                                                                    |
| `MODSECURITY_SEC_AUDIT_LOG_PARTS`     | `ABIJDEFHZ`    | multisite | no       | **Parties du journal d'audit :** Quelles parties des requêtes/réponses inclure dans les journaux d'audit.                                                                                  |
| `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` | `131072`       | multisite | no       | **Limite du corps de requête (sans fichiers) :** Taille maximale pour les corps de requête sans téléversement de fichiers. Accepte les octets bruts ou un suffixe lisible (`k`, `m`, `g`). |
| `USE_MODSECURITY_CRS_PLUGINS`         | `yes`          | multisite | no       | **Activer les plugins CRS :** Active des jeux de règles de plugins supplémentaires pour le Core Rule Set.                                                                                  |
| `MODSECURITY_CRS_PLUGINS`             |                | multisite | no       | **Liste des plugins CRS :** Liste de plugins séparés par des espaces à télécharger et installer (`nom-plugin[/tag]` ou URL).                                                               |
| `USE_MODSECURITY_GLOBAL_CRS`          | `no`           | global    | no       | **CRS Global :** Si activé, applique les règles CRS globalement au niveau HTTP plutôt que par serveur.                                                                                     |

!!! warning "ModSecurity et le Jeu de Règles de Base OWASP"
    **Nous recommandons vivement de garder ModSecurity et le Jeu de Règles de Base OWASP (CRS) activés** pour fournir une protection robuste contre les vulnérabilités web courantes. Bien que des faux positifs occasionnels puissent se produire, ils peuvent être résolus avec un peu d'effort en affinant les règles ou en utilisant des exclusions prédéfinies.

    L'équipe du CRS maintient activement une liste d'exclusions pour des applications populaires telles que WordPress, Nextcloud, Drupal et Cpanel, facilitant ainsi l'intégration sans impacter la fonctionnalité. Les avantages en matière de sécurité l'emportent de loin sur l'effort de configuration minimal requis pour traiter les faux positifs.

### Versions du CRS disponibles

Sélectionnez une version du CRS pour répondre au mieux à vos besoins de sécurité :

- **`3`** : Stable [v3.3.8](https://github.com/coreruleset/coreruleset/releases/tag/v3.3.8).
- **`4`** : Stable [v4.22.0](https://github.com/coreruleset/coreruleset/releases/tag/v4.22.0) (**par défaut**).
- **`nightly`** : [Version de nuit](https://github.com/coreruleset/coreruleset/releases/tag/nightly) offrant les dernières mises à jour de règles.

!!! example "Version de nuit (Nightly Build)"
    La **version de nuit** contient les règles les plus à jour, offrant les dernières protections contre les menaces émergentes. Cependant, comme elle est mise à jour quotidiennement et peut inclure des changements expérimentaux ou non testés, il est recommandé d'utiliser d'abord la version de nuit dans un **environnement de pré-production** avant de la déployer en production.

!!! tip "Niveaux de paranoïa"
    Le Jeu de Règles de Base OWASP utilise des "niveaux de paranoïa" (PL) pour contrôler la rigueur des règles :

    - **PL1 (défaut) :** Protection de base avec un minimum de faux positifs
    - **PL2 :** Sécurité renforcée avec une correspondance de motifs plus stricte
    - **PL3 :** Sécurité améliorée avec une validation plus stricte
    - **PL4 :** Sécurité maximale avec des règles très strictes (peut causer de nombreux faux positifs)

    Vous pouvez définir le niveau de paranoïa en ajoutant un fichier de configuration personnalisé dans `/etc/bunkerweb/configs/modsec-crs/`.

### Configurations personnalisées {#custom-configurations}

L'ajustement de ModSecurity et du Jeu de Règles de Base OWASP (CRS) peut être réalisé grâce à des configurations personnalisées. Celles-ci vous permettent de personnaliser le comportement à des étapes spécifiques du traitement des règles de sécurité :

- **`modsec-crs`** : Appliqué **avant** le chargement du Jeu de Règles de Base OWASP.
- **`modsec`** : Appliqué **après** le chargement du Jeu de Règles de Base OWASP. Également utilisé si le CRS n'est pas chargé du tout.
- **`crs-plugins-before`** : Appliqué **avant** le chargement des plugins CRS.
- **`crs-plugins-after`** : Appliqué **après** le chargement des plugins CRS.

Cette structure offre une grande flexibilité, vous permettant d'affiner les paramètres de ModSecurity et du CRS pour répondre aux besoins spécifiques de votre application tout en maintenant un flux de configuration clair.

#### Ajout d'exclusions CRS avec `modsec-crs`

Vous pouvez utiliser une configuration personnalisée de type `modsec-crs` pour ajouter des exclusions pour des cas d'usage spécifiques, comme l'activation d'exclusions prédéfinies pour WordPress :

```conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"
```

Dans cet exemple :

- L'action est exécutée en **Phase 1** (tôt dans le cycle de vie de la requête).
- Elle active les exclusions spécifiques à WordPress du CRS en définissant la variable `tx.crs_exclusions_wordpress`.

#### Mise à jour des règles CRS avec `modsec`

Pour affiner les règles CRS chargées, vous pouvez utiliser une configuration personnalisée de type `modsec`. Par exemple, vous pouvez supprimer des règles ou des balises spécifiques pour certains chemins de requête :

```conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"
```

Dans cet exemple :

- **Règle 1** : Supprime les règles avec les balises `attack-xss` et `attack-rce` pour les requêtes vers `/wp-admin/admin-ajax.php`.
- **Règle 2** : Supprime les règles avec la balise `attack-xss` pour les requêtes vers `/wp-admin/options.php`.
- **Règle 3** : Supprime une règle spécifique (ID `930120`) pour les requêtes correspondant à `/wp-json/yoast`.

!!! info "Ordre d'exécution"
    L'ordre d'exécution pour ModSecurity dans BunkerWeb est le suivant, assurant une progression claire et logique de l'application des règles :

    1.  **Configuration OWASP CRS** : Configuration de base pour le Jeu de Règles de Base OWASP.
    2.  **Configuration des plugins personnalisés (`crs-plugins-before`)** : Paramètres spécifiques aux plugins, appliqués avant toute règle CRS.
    3.  **Règles des plugins personnalisés (avant les règles CRS) (`crs-plugins-before`)** : Règles personnalisées pour les plugins exécutées avant les règles CRS.
    4.  **Configuration des plugins téléchargés** : Configuration pour les plugins téléchargés en externe.
    5.  **Règles des plugins téléchargés (avant les règles CRS)** : Règles pour les plugins téléchargés exécutées avant les règles CRS.
    6.  **Règles CRS personnalisées (`modsec-crs`)** : Règles définies par l'utilisateur appliquées avant le chargement des règles CRS.
    7.  **Règles OWASP CRS** : Le jeu de règles de sécurité de base fourni par l'OWASP.
    8.  **Règles des plugins personnalisés (après les règles CRS) (`crs-plugins-after`)** : Règles de plugins personnalisés exécutées après les règles CRS.
    9.  **Règles des plugins téléchargés (après les règles CRS)** : Règles pour les plugins téléchargés exécutées après les règles CRS.
    10. **Règles personnalisées (`modsec`)** : Règles définies par l'utilisateur appliquées après toutes les règles CRS et de plugins.

    **Notes clés** :
    - Les personnalisations **pré-CRS** (`crs-plugins-before`, `modsec-crs`) vous permettent de définir des exceptions ou des règles préparatoires avant le chargement des règles CRS de base.
    - Les personnalisations **post-CRS** (`crs-plugins-after`, `modsec`) sont idéales pour outrepasser ou étendre des règles après l'application des règles CRS et de plugins.
    - Cette structure offre une flexibilité maximale, permettant un contrôle précis de l'exécution et de la personnalisation des règles tout en maintenant une base de sécurité solide.

### Plugins OWASP CRS

Le Jeu de Règles de Base OWASP prend également en charge une gamme de **plugins** conçus pour étendre ses fonctionnalités et améliorer la compatibilité avec des applications ou des environnements spécifiques. Ces plugins peuvent aider à affiner le CRS pour une utilisation avec des plateformes populaires telles que WordPress, Nextcloud et Drupal, ou même des configurations personnalisées. Pour plus d'informations et une liste des plugins disponibles, consultez le [registre des plugins OWASP CRS](https://github.com/coreruleset/plugin-registry).

!!! tip "Téléchargement de plugins"
    Le paramètre `MODSECURITY_CRS_PLUGINS` vous permet de télécharger et d'installer des plugins pour étendre les fonctionnalités du Jeu de Règles de Base OWASP (CRS). Ce paramètre accepte une liste de noms de plugins avec des balises ou des URL optionnelles, facilitant l'intégration de fonctionnalités de sécurité supplémentaires adaptées à vos besoins spécifiques.

    Voici une liste non exhaustive des valeurs acceptées pour le paramètre `MODSECURITY_CRS_PLUGINS` :

    *   `fake-bot` - Télécharge la dernière version du plugin.
    *   `wordpress-rule-exclusions/v1.0.0` - Télécharge la version 1.0.0 du plugin.
    *   `https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip` - Télécharge le plugin directement depuis l'URL.

!!! warning "Faux positifs"
    Des paramètres de sécurité plus élevés peuvent bloquer le trafic légitime. Commencez avec les paramètres par défaut et surveillez les journaux avant d'augmenter les niveaux de sécurité. Soyez prêt à ajouter des règles d'exclusion pour les besoins spécifiques de votre application.

### Exemples de configuration

=== "Configuration de base"

    Une configuration standard avec ModSecurity et CRS v4 activés :

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "Mode détection uniquement"

    Configuration pour surveiller les menaces potentielles sans bloquer :

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "DetectionOnly"
    MODSECURITY_SEC_AUDIT_ENGINE: "On"
    MODSECURITY_SEC_AUDIT_LOG_PARTS: "ABIJDEFHZ"
    ```

=== "Configuration avancée avec plugins"

    Configuration avec CRS v4 et des plugins activés pour une protection supplémentaire :

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions fake-bot"
    MODSECURITY_REQ_BODY_NO_FILES_LIMIT: "262144"
    ```

=== "Configuration héritée"

    Configuration utilisant CRS v3 pour la compatibilité avec des installations plus anciennes :

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "3"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "ModSecurity Global"

    Configuration appliquant ModSecurity globalement à toutes les connexions HTTP :

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    USE_MODSECURITY_GLOBAL_CRS: "yes"
    ```

=== "Version de nuit avec plugins personnalisés"

    Configuration utilisant la version de nuit du CRS avec des plugins personnalisés :

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "nightly"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions/v1.0.0 https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip"
    ```

!!! note "Valeurs de taille lisibles"
    Pour les paramètres de taille comme `MODSECURITY_REQ_BODY_NO_FILES_LIMIT`, les suffixes `k`, `m`, et `g` (insensibles à la casse) sont pris en charge et représentent les kibioctets, mébioctets et gibioctets (multiples de 1024). Exemples : `256k` = 262144, `1m` = 1048576, `2g` = 2147483648.
