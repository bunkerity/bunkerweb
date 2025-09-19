Les attaquants utilisent souvent des outils automatisés (bots) pour tenter d’exploiter votre site. Pour s’en protéger, BunkerWeb inclut une fonctionnalité « Antibot » qui demande aux utilisateurs de prouver qu’ils sont humains. Si un utilisateur réussit le défi, il obtient l’accès à votre site. Cette fonctionnalité est désactivée par défaut.

Comment ça marche :

1. Lorsqu’un utilisateur visite votre site, BunkerWeb vérifie s’il a déjà réussi un défi antibot.
2. Sinon, l’utilisateur est redirigé vers une page de défi.
3. L’utilisateur doit compléter le défi (ex. résoudre un CAPTCHA, exécuter du JavaScript).
4. Si le défi est réussi, l’utilisateur est redirigé vers la page initialement demandée et peut naviguer normalement.

### Comment l’utiliser

Suivez ces étapes pour activer et configurer Antibot :

1. Choisir un type de défi : décidez du mécanisme à utiliser (ex. [captcha](#__tabbed_3_3), [hcaptcha](#__tabbed_3_5), [javascript](#__tabbed_3_2)).
2. Activer la fonctionnalité : définissez le paramètre `USE_ANTIBOT` sur le type choisi dans votre configuration BunkerWeb.
3. Configurer les paramètres : ajustez les autres paramètres `ANTIBOT_*` si nécessaire. Pour reCAPTCHA, hCaptcha, Turnstile et mCaptcha, créez un compte auprès du service choisi et obtenez des clés API.
4. Important : assurez‑vous que `ANTIBOT_URI` est une URL unique de votre site et qu’elle n’est pas utilisée ailleurs.

!!! important "À propos du paramètre `ANTIBOT_URI`"
Assurez‑vous que `ANTIBOT_URI` est une URL unique de votre site et qu’elle n’est pas utilisée ailleurs.

!!! warning "Sessions en environnement cluster"
La fonction antibot utilise des cookies pour suivre si un utilisateur a complété le défi. Si vous exécutez BunkerWeb en cluster (plusieurs instances), vous devez configurer correctement la gestion des sessions : définissez `SESSIONS_SECRET` et `SESSIONS_NAME` avec les mêmes valeurs sur toutes les instances BunkerWeb. Sinon, les utilisateurs pourront être invités à répéter le défi. Plus d’informations sur la configuration des sessions [ici](#sessions).

### Paramètres communs

Les paramètres suivants sont partagés par tous les mécanismes de défi :

| Paramètre              | Valeur par défaut | Contexte  | Multiple | Description                                                                                                                                                 |
| ---------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_URI`          | `/challenge`      | multisite | non      | URL du défi : l’URL vers laquelle les utilisateurs sont redirigés pour compléter le défi. Veillez à ce que cette URL ne soit pas utilisée pour autre chose. |
| `ANTIBOT_TIME_RESOLVE` | `60`              | multisite | non      | Délai du défi : temps maximum (en secondes) pour compléter le défi. Au‑delà, un nouveau défi est généré.                                                    |
| `ANTIBOT_TIME_VALID`   | `86400`           | multisite | non      | Validité du défi : durée (en secondes) pendant laquelle un défi réussi reste valide. Passé ce délai, un nouveau défi sera requis.                           |

### Exclure du trafic des défis

BunkerWeb permet d’indiquer certains utilisateurs, IP ou requêtes qui doivent contourner totalement le défi antibot. Utile pour des services de confiance, réseaux internes ou des pages à laisser toujours accessibles :

| Paramètre                   | Défaut | Contexte  | Multiple | Description                                                                                                     |
| --------------------------- | ------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_IGNORE_URI`        |        | multisite | non      | URL exclues : liste d’expressions régulières d’URI séparées par des espaces qui doivent contourner le défi.     |
| `ANTIBOT_IGNORE_IP`         |        | multisite | non      | IP exclues : liste d’adresses IP ou de plages CIDR séparées par des espaces qui doivent contourner le défi.     |
| `ANTIBOT_IGNORE_RDNS`       |        | multisite | non      | rDNS exclu : liste de suffixes de DNS inversés séparés par des espaces qui doivent contourner le défi.          |
| `ANTIBOT_RDNS_GLOBAL`       | `yes`  | multisite | non      | IP publiques uniquement : si `yes`, ne faire des vérifications rDNS que sur des IP publiques.                   |
| `ANTIBOT_IGNORE_ASN`        |        | multisite | non      | ASN exclus : liste de numéros d’ASN séparés par des espaces qui doivent contourner le défi.                     |
| `ANTIBOT_IGNORE_USER_AGENT` |        | multisite | non      | User‑Agents exclus : liste de motifs regex d’User‑Agent séparés par des espaces qui doivent contourner le défi. |

Exemples :

- `ANTIBOT_IGNORE_URI: "^/api/ ^/webhook/ ^/assets/"`
  Exclut toutes les URI commençant par `/api/`, `/webhook/` ou `/assets/`.

- `ANTIBOT_IGNORE_IP: "192.168.1.0/24 10.0.0.1"`
  Exclut le réseau interne `192.168.1.0/24` et l’IP spécifique `10.0.0.1`.

- `ANTIBOT_IGNORE_RDNS: ".googlebot.com .bingbot.com"`
  Exclut les requêtes provenant d’hôtes dont le DNS inversé se termine par `googlebot.com` ou `bingbot.com`.

- `ANTIBOT_IGNORE_ASN: "15169 8075"`
  Exclut les requêtes des ASN 15169 (Google) et 8075 (Microsoft).

- `ANTIBOT_IGNORE_USER_AGENT: "^Mozilla.+Chrome.+Safari"`
  Exclut les requêtes dont le User-Agent correspond au motif regex spécifié.

### Mécanismes de défi

=== "Cookie"

    Le défi Cookie est un mécanisme léger qui repose sur l’installation d’un cookie dans le navigateur de l’utilisateur. Lorsqu’un utilisateur accède au site, le serveur envoie un cookie au client. Lors des requêtes suivantes, le serveur vérifie la présence de ce cookie pour confirmer que l’utilisateur est légitime. Cette méthode est simple et efficace pour une protection de base contre les bots sans nécessiter d’interaction supplémentaire de l’utilisateur.

    **Comment ça marche :**

    1. Le serveur génère un cookie unique et l’envoie au client.
    2. Le client doit renvoyer le cookie dans les requêtes suivantes.
    3. Si le cookie est manquant ou invalide, l’utilisateur est redirigé vers la page de défi.

    **Paramètres :**

    | Paramètre     | Défaut | Contexte  | Multiple | Description                                                       |
    | ------------- | ------ | --------- | -------- | ----------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`   | multisite | non      | Activer Antibot : définir sur `cookie` pour activer ce mécanisme. |

=== "JavaScript"

    Le défi JavaScript demande au client de résoudre une tâche de calcul en utilisant JavaScript. Ce mécanisme garantit que le client a activé JavaScript et peut exécuter le code requis, ce qui est généralement hors de portée de la plupart des bots.

    **Comment ça marche :**

    1. Le serveur envoie un script JavaScript au client.
    2. Le script effectue une tâche de calcul (par exemple, un hachage) et soumet le résultat au serveur.
    3. Le serveur vérifie le résultat pour confirmer la légitimité du client.

    **Fonctionnalités clés :**

    - Le défi génère dynamiquement une tâche unique pour chaque client.
    - La tâche de calcul implique un hachage avec des conditions spécifiques (par exemple, trouver un hachage avec un certain préfixe).

    **Paramètres :**

    | Paramètre     | Défaut | Contexte  | Multiple | Description                                                           |
    | ------------- | ------ | --------- | -------- | --------------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`   | multisite | non      | Activer Antibot : définir sur `javascript` pour activer ce mécanisme. |

=== "Captcha"

    Le défi Captcha est un mécanisme maison qui génère des défis basés sur des images, entièrement hébergés dans votre environnement BunkerWeb. Il teste la capacité des utilisateurs à reconnaître et interpréter des caractères aléatoires, garantissant que les bots automatisés sont bloqués efficacement sans dépendre de services externes.

    **Comment ça marche :**

    1. Le serveur génère une image CAPTCHA contenant des caractères aléatoires.
    2. L’utilisateur doit saisir les caractères affichés dans l’image dans un champ de texte.
    3. Le serveur valide la saisie de l’utilisateur par rapport au CAPTCHA généré.

    **Fonctionnalités clés :**

    - Entièrement auto-hébergé, éliminant le besoin d’API tierces.
    - Les défis générés dynamiquement assurent l’unicité pour chaque session utilisateur.
    - Utilise un jeu de caractères personnalisable pour la génération du CAPTCHA.

    **Caractères pris en charge :**

    Le système CAPTCHA prend en charge les types de caractères suivants :

    - **Lettres :** Toutes les lettres minuscules (a-z) et majuscules (A-Z)
    - **Chiffres :** 2, 3, 4, 5, 6, 7, 8, 9 (exclut 0 et 1 pour éviter toute confusion)
    - **Caractères spéciaux :** ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„```

    Pour obtenir la liste complète des caractères pris en charge, consultez la [table des caractères de la police](https://www.dafont.com/moms-typewriter.charmap?back=theme) utilisée pour le CAPTCHA.

    **Paramètres :**

    | Paramètre                  | Défaut                                                 | Contexte  | Multiple | Description                                                                                                                                                                                                                                               |
    | -------------------------- | ------------------------------------------------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                                                   | multisite | non      | **Activer Antibot :** définir sur `captcha` pour activer ce mécanisme.                                                                                                                                                                                    |
    | `ANTIBOT_CAPTCHA_ALPHABET` | `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ` | multisite | non      | **Alphabet du Captcha :** une chaîne de caractères à utiliser pour générer le CAPTCHA. Caractères pris en charge : toutes les lettres (a-z, A-Z), les chiffres 2-9 (exclut 0 et 1), et les caractères spéciaux : ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„``` |

=== "reCAPTCHA"

    reCAPTCHA de Google propose une validation des utilisateurs qui s’exécute en arrière‑plan (v3) pour attribuer un score basé sur le comportement. Un score inférieur au seuil configuré déclenchera une vérification supplémentaire ou bloquera la requête. Pour les défis visibles (v2), les utilisateurs doivent interagir avec le widget reCAPTCHA avant de continuer.

    Il existe désormais deux manières d’intégrer reCAPTCHA :
    - La version classique (clés site/secret, point de terminaison de vérification v2/v3)
    - La nouvelle version utilisant Google Cloud (ID de projet + clé API). La version classique reste disponible et peut être activée avec `ANTIBOT_RECAPTCHA_CLASSIC`.

    Pour la version classique, obtenez vos clés de site et secrète depuis la [console d’administration de Google reCAPTCHA](https://www.google.com/recaptcha/admin).
    Pour la nouvelle version, créez une clé reCAPTCHA dans votre projet Google Cloud et utilisez l’ID du projet ainsi qu’une clé API (voir la [console reCAPTCHA de Google Cloud](https://console.cloud.google.com/security/recaptcha)). Une clé de site est toujours requise.

    **Paramètres :**

    | Paramètre                      | Défaut | Contexte  | Multiple | Description                                                                                                         |
    | ------------------------------ | ------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`                  | `no`   | multisite | non      | Activer Antibot : définir sur `recaptcha` pour activer ce mécanisme.                                                |
    | `ANTIBOT_RECAPTCHA_CLASSIC`    | `yes`  | multisite | non      | Utiliser reCAPTCHA classique. Mettre à `no` pour utiliser la nouvelle version basée sur Google Cloud.               |
    | `ANTIBOT_RECAPTCHA_SITEKEY`    |        | multisite | non      | Clé de site reCAPTCHA. Requise pour les deux versions.                                                              |
    | `ANTIBOT_RECAPTCHA_SECRET`     |        | multisite | non      | Clé secrète reCAPTCHA. Requise pour la version classique uniquement.                                                |
    | `ANTIBOT_RECAPTCHA_PROJECT_ID` |        | multisite | non      | ID de projet Google Cloud. Requis pour la nouvelle version uniquement.                                              |
    | `ANTIBOT_RECAPTCHA_API_KEY`    |        | multisite | non      | Clé API Google Cloud utilisée pour appeler l’API reCAPTCHA Enterprise. Requise pour la nouvelle version uniquement. |
    | `ANTIBOT_RECAPTCHA_JA3`        |        | multisite | non      | Empreinte TLS JA3 optionnelle à inclure dans les évaluations Enterprise.                                            |
    | `ANTIBOT_RECAPTCHA_JA4`        |        | multisite | non      | Empreinte TLS JA4 optionnelle à inclure dans les évaluations Enterprise.                                            |
    | `ANTIBOT_RECAPTCHA_SCORE`      | `0.7`  | multisite | non      | Score minimum requis pour passer (s’applique à la v3 classique et à la nouvelle version).                           |

=== "hCaptcha"

    Lorsqu’il est activé, hCaptcha offre une alternative efficace à reCAPTCHA en vérifiant les interactions des utilisateurs sans reposer sur un mécanisme de score. Il met les utilisateurs au défi avec un test simple et interactif pour confirmer leur légitimité.

    Pour intégrer hCaptcha avec BunkerWeb, vous devez obtenir les informations d’identification nécessaires depuis le tableau de bord hCaptcha sur [hCaptcha](https://www.hcaptcha.com). Ces informations incluent une clé de site et une clé secrète.

    **Paramètres :**

    | Paramètre                  | Défaut | Contexte  | Multiple | Description                                                         |
    | -------------------------- | ------ | --------- | -------- | ------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`   | multisite | non      | Activer Antibot : définir sur `hcaptcha` pour activer ce mécanisme. |
    | `ANTIBOT_HCAPTCHA_SITEKEY` |        | multisite | non      | Clé site hCaptcha.                                                  |
    | `ANTIBOT_HCAPTCHA_SECRET`  |        | multisite | non      | Clé secrète hCaptcha.                                               |

=== "Turnstile"

    Turnstile est un mécanisme de défi moderne et respectueux de la vie privée qui s’appuie sur la technologie de Cloudflare pour détecter et bloquer le trafic automatisé. Il valide les interactions des utilisateurs de manière transparente et en arrière-plan, réduisant les frictions pour les utilisateurs légitimes tout en décourageant efficacement les bots.

    Pour intégrer Turnstile avec BunkerWeb, assurez-vous d’obtenir les informations d’identification nécessaires depuis [Cloudflare Turnstile](https://www.cloudflare.com/turnstile).

    **Paramètres :**

    | Paramètre                   | Défaut | Contexte  | Multiple | Description                                                          |
    | --------------------------- | ------ | --------- | -------- | -------------------------------------------------------------------- |
    | `USE_ANTIBOT`               | `no`   | multisite | non      | Activer Antibot : définir sur `turnstile` pour activer ce mécanisme. |
    | `ANTIBOT_TURNSTILE_SITEKEY` |        | multisite | non      | Clé site Turnstile (Cloudflare).                                     |
    | `ANTIBOT_TURNSTILE_SECRET`  |        | multisite | non      | Clé secrète Turnstile (Cloudflare).                                  |

=== "mCaptcha"

    mCaptcha est un mécanisme de défi CAPTCHA alternatif qui vérifie la légitimité des utilisateurs en présentant un test interactif similaire à d’autres solutions antibot. Lorsqu’il est activé, il met les utilisateurs au défi avec un CAPTCHA fourni par mCaptcha, s’assurant que seuls les utilisateurs authentiques contournent les contrôles de sécurité automatisés.

    mCaptcha est conçu dans le respect de la vie privée. Il est entièrement conforme au RGPD, garantissant que toutes les données des utilisateurs impliquées dans le processus de défi respectent des normes strictes de protection des données. De plus, mCaptcha offre la flexibilité d’être auto-hébergé, permettant aux organisations de garder un contrôle total sur leurs données et leur infrastructure. Cette capacité d’auto-hébergement améliore non seulement la confidentialité, mais optimise également les performances et la personnalisation pour répondre aux besoins spécifiques de déploiement.

    Pour intégrer mCaptcha avec BunkerWeb, vous devez obtenir les informations d’identification nécessaires depuis la plateforme [mCaptcha](https://mcaptcha.org/) ou votre propre fournisseur. Ces informations incluent une clé de site et une clé secrète pour la vérification.

    **Paramètres :**

    | Paramètre                  | Défaut                      | Contexte  | Multiple | Description                                                         |
    | -------------------------- | --------------------------- | --------- | -------- | ------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                        | multisite | non      | Activer Antibot : définir sur `mcaptcha` pour activer ce mécanisme. |
    | `ANTIBOT_MCAPTCHA_SITEKEY` |                             | multisite | non      | Clé site mCaptcha.                                                  |
    | `ANTIBOT_MCAPTCHA_SECRET`  |                             | multisite | non      | Clé secrète mCaptcha.                                               |
    | `ANTIBOT_MCAPTCHA_URL`     | `https://demo.mcaptcha.org` | multisite | non      | Domaine à utiliser pour mCaptcha.                                   |

Reportez‑vous aux Paramètres communs pour les options supplémentaires.

### Exemples de configuration

=== "Défi Cookie"

```yaml
USE_ANTIBOT: "cookie"
ANTIBOT_URI: "/challenge"
ANTIBOT_TIME_RESOLVE: "60"
ANTIBOT_TIME_VALID: "86400"
```

=== "Défi JavaScript"

```yaml
USE_ANTIBOT: "javascript"
ANTIBOT_URI: "/challenge"
ANTIBOT_TIME_RESOLVE: "60"
ANTIBOT_TIME_VALID: "86400"
```

=== "Défi Captcha"

```yaml
USE_ANTIBOT: "captcha"
ANTIBOT_URI: "/challenge"
ANTIBOT_TIME_RESOLVE: "60"
ANTIBOT_TIME_VALID: "86400"
ANTIBOT_CAPTCHA_ALPHABET: "23456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
```

Remarque : l’exemple ci‑dessus utilise les chiffres 2‑9 et toutes les lettres, fréquemment utilisés pour les CAPTCHA. Vous pouvez personnaliser l’alphabet pour inclure des caractères spéciaux si nécessaire.

=== "Défi reCAPTCHA Classique"

    Exemple de configuration pour le reCAPTCHA classique (clés site/secret) :

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

=== "Défi reCAPTCHA (nouveau)"

    Exemple de configuration pour le nouveau reCAPTCHA basé sur Google Cloud (ID de projet + clé API) :

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "no"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_PROJECT_ID: "your-gcp-project-id"
    ANTIBOT_RECAPTCHA_API_KEY: "your-gcp-api-key"
    # Empreintes optionnelles pour améliorer les évaluations Enterprise
    # ANTIBOT_RECAPTCHA_JA3: "<empreinte-ja3>"
    # ANTIBOT_RECAPTCHA_JA4: "<empreinte-ja4>"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Défi hCaptcha"

```yaml
USE_ANTIBOT: "hcaptcha"
ANTIBOT_HCAPTCHA_SITEKEY: "your-site-key"
ANTIBOT_HCAPTCHA_SECRET: "your-secret-key"
ANTIBOT_URI: "/challenge"
ANTIBOT_TIME_RESOLVE: "60"
ANTIBOT_TIME_VALID: "86400"
```

=== "Défi Turnstile"

```yaml
USE_ANTIBOT: "turnstile"
ANTIBOT_TURNSTILE_SITEKEY: "your-site-key"
ANTIBOT_TURNSTILE_SECRET: "your-secret-key"
ANTIBOT_URI: "/challenge"
ANTIBOT_TIME_RESOLVE: "60"
ANTIBOT_TIME_VALID: "86400"
```

=== "Défi mCaptcha"

```yaml
USE_ANTIBOT: "mcaptcha"
ANTIBOT_MCAPTCHA_SITEKEY: "your-site-key"
ANTIBOT_MCAPTCHA_SECRET: "your-secret-key"
ANTIBOT_MCAPTCHA_URL: "https://demo.mcaptcha.org"
ANTIBOT_URI: "/challenge"
ANTIBOT_TIME_RESOLVE: "60"
ANTIBOT_TIME_VALID: "86400"
```
