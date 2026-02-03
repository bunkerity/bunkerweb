Le plugin Let’s Encrypt simplifie la gestion des certificats SSL/TLS en automatisant la création, le renouvellement et la configuration de certificats gratuits de Let's Encrypt. Cette fonctionnalité active les connexions HTTPS sécurisées pour vos sites web sans la complexité de la gestion manuelle des certificats, réduisant ainsi les coûts et la charge administrative.

**Comment ça marche :**

1.  Une fois activé, BunkerWeb détecte automatiquement les domaines configurés pour votre site.
2.  BunkerWeb demande des certificats SSL/TLS gratuits à l'autorité de certification de Let's Encrypt.
3.  La propriété du domaine est vérifiée par des défis HTTP (prouvant que vous contrôlez le site) ou des défis DNS (prouvant que vous contrôlez le DNS de votre domaine).
4.  Les certificats sont automatiquement installés et configurés pour vos domaines.
5.  BunkerWeb gère les renouvellements de certificats en arrière-plan avant leur expiration, assurant une disponibilité HTTPS continue.
6.  L'ensemble du processus est entièrement automatisé, ne nécessitant qu'une intervention minimale après la configuration initiale.

!!! info "Prérequis"
    Pour utiliser cette fonctionnalité, assurez-vous que des enregistrements DNS **A** corrects sont configurés pour chaque domaine, pointant vers la ou les IP publiques où BunkerWeb est accessible. Sans une configuration DNS correcte, le processus de vérification de domaine échouera.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Let's Encrypt :

1.  **Activer la fonctionnalité :** Mettez le paramètre `AUTO_LETS_ENCRYPT` à `yes` pour activer l'émission et le renouvellement automatiques des certificats.
2.  **Fournir un e-mail de contact (recommandé) :** Saisissez votre adresse e-mail dans le paramètre `EMAIL_LETS_ENCRYPT` pour que Let's Encrypt puisse vous prévenir avant l'expiration d'un certificat. Si vous laissez ce champ vide, BunkerWeb s'enregistrera sans adresse (option Certbot `--register-unsafely-without-email`) et vous ne recevrez aucun rappel ni e-mail de récupération.
3.  **Choisir le type de défi :** Sélectionnez la vérification `http` ou `dns` avec le paramètre `LETS_ENCRYPT_CHALLENGE`.
4.  **Configurer le fournisseur DNS :** Si vous utilisez les défis DNS, spécifiez votre fournisseur DNS et vos identifiants.
5.  **Sélectionner un profil de certificat :** Choisissez votre profil de certificat préféré avec le paramètre `LETS_ENCRYPT_PROFILE` (classic, tlsserver ou shortlived).
6.  **Laissez BunkerWeb s'occuper du reste :** Une fois configuré, les certificats sont automatiquement émis, installés et renouvelés selon les besoins.

!!! tip "Profils de certificat"
    Let's Encrypt propose différents profils de certificat pour différents cas d'usage :

    - **classic** : Certificats à usage général avec une validité de 90 jours (par défaut)
    - **tlsserver** : Optimisé pour l'authentification de serveur TLS avec une validité de 90 jours et une charge utile plus petite
    - **shortlived** : Sécurité renforcée avec une validité de 7 jours pour les environnements automatisés
    - **custom** : Si votre serveur ACME prend en charge un profil différent, définissez-le avec `LETS_ENCRYPT_CUSTOM_PROFILE`.

!!! info "Disponibilité des profils"
    Notez que les profils `tlsserver` et `shortlived` peuvent ne pas être disponibles dans tous les environnements ou avec tous les clients ACME pour le moment. Le profil `classic` a la compatibilité la plus large et est recommandé pour la plupart des utilisateurs. Si un profil sélectionné n'est pas disponible, le système basculera automatiquement sur le profil `classic`.

### Paramètres de configuration

| Paramètre                                   | Défaut    | Contexte  | Multiple | Description                                                                                                                                                                                                                                                                                                                  |
| ------------------------------------------- | --------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AUTO_LETS_ENCRYPT`                         | `no`      | multisite | no       | **Activer Let's Encrypt :** Mettre à `yes` pour activer l'émission et le renouvellement automatiques des certificats.                                                                                                                                                                                                        |
| `LETS_ENCRYPT_PASSTHROUGH`                  | `no`      | multisite | no       | **Passer à travers Let's Encrypt :** Mettre à `yes` pour passer les requêtes Let's Encrypt au serveur web. Utile si BunkerWeb est derrière un autre reverse proxy gérant le SSL.                                                                                                                                             |
| `EMAIL_LETS_ENCRYPT`                        | `-`       | multisite | no       | **E-mail de contact :** Adresse e-mail utilisée pour les rappels Let's Encrypt. Ne laissez ce champ vide que si vous acceptez de ne recevoir aucun avertissement ni e-mail de récupération (Certbot s'enregistre avec `--register-unsafely-without-email`).                                                                  |
| `LETS_ENCRYPT_CHALLENGE`                    | `http`    | multisite | no       | **Type de défi :** Méthode utilisée pour vérifier la propriété du domaine. Options : `http` ou `dns`.                                                                                                                                                                                                                        |
| `LETS_ENCRYPT_DNS_PROVIDER`                 |           | multisite | no       | **Fournisseur DNS :** Pour les défis DNS, le fournisseur à utiliser (ex. : cloudflare, route53, digitalocean).                                                                                                                                                                                                               |
| `LETS_ENCRYPT_DNS_PROPAGATION`              | `default` | multisite | no       | **Propagation DNS :** Le temps d'attente en secondes pour la propagation DNS. Si aucune valeur n'est fournie, le temps par défaut du fournisseur est utilisé.                                                                                                                                                                |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`          |           | multisite | yes      | **Élément d'identification :** Éléments de configuration pour l'authentification du fournisseur DNS (ex. : `cloudflare_api_token 123456`). Les valeurs peuvent être du texte brut, encodées en base64 ou un objet JSON.                                                                                                      |
| `LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64` | `yes`     | multisite | no       | **Décoder les identifiants DNS Base64 :** Décoder automatiquement les identifiants du fournisseur DNS encodés en base64 lorsqu'il est défini sur `yes`. Les valeurs au format base64 sont décodées avant utilisation (sauf pour le fournisseur `rfc2136`). Désactivez si vos identifiants sont intentionnellement en base64. |
| `USE_LETS_ENCRYPT_WILDCARD`                 | `no`      | multisite | no       | **Certificats Wildcard :** Si mis à `yes`, crée des certificats wildcard pour tous les domaines. Uniquement disponible avec les défis DNS.                                                                                                                                                                                   |
| `USE_LETS_ENCRYPT_STAGING`                  | `no`      | multisite | no       | **Utiliser Staging :** Si mis à `yes`, utilise l'environnement de staging de Let's Encrypt pour les tests. Les limites de débit y sont plus élevées mais les certificats ne sont pas fiables.                                                                                                                                |
| `LETS_ENCRYPT_CLEAR_OLD_CERTS`              | `no`      | global    | no       | **Effacer les anciens certificats :** Si mis à `yes`, supprime les anciens certificats inutiles lors du renouvellement.                                                                                                                                                                                                      |
| `LETS_ENCRYPT_CONCURRENT_REQUESTS`          | `no`      | global    | no       | **Requêtes concurrentes :** Si mis à `yes`, certbot-new effectue les demandes de certificats en parallèle. À utiliser avec prudence pour éviter les limites de débit.                                                                                                                                                        |
| `LETS_ENCRYPT_PROFILE`                      | `classic` | multisite | no       | **Profil de certificat :** Sélectionnez le profil à utiliser. Options : `classic` (général), `tlsserver` (optimisé TLS), ou `shortlived` (7 jours).                                                                                                                                                                          |
| `LETS_ENCRYPT_CUSTOM_PROFILE`               |           | multisite | no       | **Profil de certificat personnalisé :** Saisissez un profil personnalisé si votre serveur ACME le supporte. Remplace `LETS_ENCRYPT_PROFILE` s'il est défini.                                                                                                                                                                 |
| `LETS_ENCRYPT_MAX_RETRIES`                  | `3`       | multisite | no       | **Tentatives maximales :** Nombre de tentatives de génération de certificat en cas d'échec. `0` pour désactiver. Utile pour les problèmes réseau temporaires.                                                                                                                                                                |

!!! info "Information et comportement"
    - Le paramètre `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` est un paramètre multiple et peut être utilisé pour définir plusieurs éléments pour le fournisseur DNS. Les éléments seront enregistrés dans un fichier de cache, et Certbot lira les informations d'identification à partir de celui-ci.
    - Si aucun paramètre `LETS_ENCRYPT_DNS_PROPAGATION` n'est fourni, le temps de propagation par défaut du fournisseur est utilisé.
    - L'automatisation complète de Let's Encrypt avec le défi `http` fonctionne en mode stream tant que vous ouvrez le port `80/tcp` depuis l'extérieur. Utilisez le paramètre `LISTEN_STREAM_PORT_SSL` pour choisir votre port d'écoute SSL/TLS.
    - Si `LETS_ENCRYPT_PASSTHROUGH` est mis à `yes`, BunkerWeb ne gérera pas les requêtes de défi ACME lui-même mais les transmettra au serveur web backend. Ceci est utile dans les scénarios où BunkerWeb agit comme un reverse proxy devant un autre serveur configuré pour gérer les défis Let's Encrypt.

!!! tip "Défis HTTP vs. DNS"
    **Les défis HTTP** sont plus simples à configurer et fonctionnent bien pour la plupart des sites web :

    - Nécessite que votre site soit publiquement accessible sur le port 80
    - Configuré automatiquement par BunkerWeb
    - Ne peut pas être utilisé pour les certificats wildcard

    **Les défis DNS** offrent plus de flexibilité et sont requis pour les certificats wildcard :

    - Fonctionne même si votre site n'est pas publiquement accessible
    - Nécessite les identifiants de l'API de votre fournisseur DNS
    - Requis pour les certificats wildcard (ex. : *.example.com)
    - Utile lorsque le port 80 est bloqué ou indisponible

!!! warning "Certificats wildcard"
    Les certificats wildcard ne sont disponibles qu'avec les défis DNS. Si vous souhaitez les utiliser, vous devez mettre le paramètre `USE_LETS_ENCRYPT_WILDCARD` à `yes` et configurer correctement les identifiants de votre fournisseur DNS.

!!! warning "Limites de débit"
    Let's Encrypt impose des limites de débit sur l'émission de certificats. Lors du test de configurations, utilisez l'environnement de staging en mettant `USE_LETS_ENCRYPT_STAGING` à `yes` pour éviter d'atteindre les limites de production. Les certificats de staging ne sont pas reconnus par les navigateurs mais sont utiles pour valider votre configuration.

### Fournisseurs DNS supportés

Le plugin Let's Encrypt prend en charge un large éventail de fournisseurs DNS pour les défis DNS. Chaque fournisseur nécessite des informations d'identification spécifiques qui doivent être fournies via le paramètre `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`.

| Fournisseur       | Description      | Paramètres obligatoires                                                                                      | Paramètres optionnels                                                                                                                                                                                                                                                    | Documentation                                                                                         |
| ----------------- | ---------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `bunny`           | bunny.net        | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/mwt/certbot-dns-bunny/blob/main/README.rst)                        |
| `cloudflare`      | Cloudflare       | soit `api_token`<br>soit `email` et `api_key`                                                                |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)                             |
| `desec`           | deSEC            | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/desec-io/certbot-dns-desec/blob/main/README.md)                    |
| `digitalocean`    | DigitalOcean     | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)                           |
| `domainoffensive` | Domain-Offensive | `api_token`                                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/domainoffensive/certbot-dns-domainoffensive/blob/master/README.md) |
| `domeneshop`      | Domeneshop       | `token`<br>`secret`                                                                                          |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/domeneshop/certbot-dns-domeneshop/blob/master/README.rst)          |
| `dnsimple`        | DNSimple         | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)                               |
| `dnsmadeeasy`     | DNS Made Easy    | `api_key`<br>`secret_key`                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)                            |
| `duckdns`         | DuckDNS          | `duckdns_token`                                                                                              |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/infinityofspace/certbot_dns_duckdns/blob/main/Readme.md)           |
| `dynu`            | Dynu             | `auth_token`                                                                                                 |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/bikram990/certbot-dns-dynu/blob/main/README.md)                    |
| `gehirn`          | Gehirn DNS       | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                                 |
| `godaddy`         | GoDaddy          | `key`<br>`secret`                                                                                            | `ttl` (défaut : `600`)                                                                                                                                                                                                                                                   | [Documentation](https://github.com/miigotu/certbot-dns-godaddy/blob/main/README.md)                   |
| `google`          | Google Cloud     | `project_id`<br>`private_key_id`<br>`private_key`<br>`client_email`<br>`client_id`<br>`client_x509_cert_url` | `type` (défaut : `service_account`)<br>`auth_uri` (défaut : `https://accounts.google.com/o/oauth2/auth`)<br>`token_uri` (défaut : `https://accounts.google.com/o/oauth2/token`)<br>`auth_provider_x509_cert_url` (défaut : `https://www.googleapis.com/oauth2/v1/certs`) | [Documentation](https://certbot-dns-google.readthedocs.io/en/stable/)                                 |
| `infomaniak`      | Infomaniak       | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/infomaniak/certbot-dns-infomaniak/blob/main/README.rst)            |
| `ionos`           | IONOS            | `prefix`<br>`secret`                                                                                         | `endpoint` (défaut : `https://api.hosting.ionos.com`)                                                                                                                                                                                                                    | [Documentation](https://github.com/helgeerbe/certbot-dns-ionos/blob/master/README.md)                 |
| `linode`          | Linode           | `key`                                                                                                        |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-linode.readthedocs.io/en/stable/)                                 |
| `luadns`          | LuaDNS           | `email`<br>`token`                                                                                           |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-luadns.readthedocs.io/en/stable/)                                 |
| `njalla`          | Njalla           | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/chaptergy/certbot-dns-njalla/blob/main/README.md)                  |
| `nsone`           | NS1              | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-nsone.readthedocs.io/en/stable/)                                  |
| `ovh`             | OVH              | `application_key`<br>`application_secret`<br>`consumer_key`                                                  | `endpoint` (défaut : `ovh-eu`)                                                                                                                                                                                                                                           | [Documentation](https://certbot-dns-ovh.readthedocs.io/en/stable/)                                    |
| `pdns`            | PowerDNS         | `endpoint`<br>`api_key`<br>`server_id` (default: `localhost`)<br>`disable_notify` (default: `false`)         |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/kaechele/certbot-dns-pdns/blob/main/README.md)                     |
| `rfc2136`         | RFC 2136         | `server`<br>`name`<br>`secret`                                                                               | `port` (défaut : `53`)<br>`algorithm` (défaut : `HMAC-SHA512`)<br>`sign_query` (défaut : `false`)                                                                                                                                                                        | [Documentation](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                                |
| `route53`         | Amazon Route 53  | `access_key_id`<br>`secret_access_key`                                                                       |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-route53.readthedocs.io/en/stable/)                                |
| `sakuracloud`     | Sakura Cloud     | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)                            |
| `scaleway`        | Scaleway         | `application_token`                                                                                          |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst)                 |
| `transip`         | TransIP          | `key_file`<br>`username`                                                                                     |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-transip.readthedocs.io/en/stable/)                                |

### Exemples de configuration

=== "Défi HTTP de base"

    Configuration simple utilisant les défis HTTP pour un seul domaine :

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ```

=== "DNS Cloudflare avec Wildcard"

    Configuration pour les certificats wildcard utilisant le DNS de Cloudflare :

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "api_token VOTRE_JETON_API"
    USE_LETS_ENCRYPT_WILDCARD: "yes"
    ```

=== "Configuration AWS Route53"

    Configuration utilisant Amazon Route53 pour les défis DNS :

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "route53"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "aws_access_key_id VOTRE_CLE_ACCES"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "aws_secret_access_key VOTRE_CLE_SECRETE"
    ```

=== "Test avec l'environnement de Staging et tentatives"

    Configuration pour tester la configuration avec l'environnement de staging et des paramètres de tentatives améliorés :

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    USE_LETS_ENCRYPT_STAGING: "yes"
    LETS_ENCRYPT_MAX_RETRIES: "5"
    ```

=== "DigitalOcean avec temps de propagation personnalisé"

    Configuration utilisant le DNS de DigitalOcean avec un temps d'attente de propagation plus long :

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "digitalocean"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "token VOTRE_JETON_API"
    LETS_ENCRYPT_DNS_PROPAGATION: "120"
    ```

=== "Google Cloud DNS"

    Configuration utilisant Google Cloud DNS avec les informations d'identification d'un compte de service :

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "google"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "project_id votre-id-projet"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "private_key_id votre-id-cle-privee"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_3: "private_key votre-cle-privee"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_4: "client_email votre-email-compte-service"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_5: "client_id votre-id-client"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_6: "client_x509_cert_url votre-url-cert"
    ```
