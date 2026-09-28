Le plugin Real IP garantit que BunkerWeb identifie correctement l’adresse IP du client même derrière des proxys. Indispensable pour appliquer les règles de sécurité, la limitation de débit et des logs fiables : sinon toutes les requêtes sembleraient venir de l’IP du proxy.

Comment ça marche :

1. Activé, BunkerWeb inspecte les en‑têtes (ex. [`X-Forwarded-For`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Forwarded-For)) contenant l’IP d’origine.
2. Il vérifie que l’IP source figure dans `REAL_IP_FROM` (liste de proxys de confiance) pour n’accepter que les proxys légitimes.
3. L’IP client est extraite de l’en‑tête `REAL_IP_HEADER` et utilisée pour l’évaluation sécurité et la journalisation.
4. En chaînes d’IPs, une recherche récursive peut déterminer l’IP d’origine.
5. Le support du [PROXY protocol](https://netnut.io/what-is-proxy-protocol-and-how-does-it-work/) peut être activé pour recevoir l’IP client directement depuis des proxys compatibles (ex. [HAProxy](https://www.haproxy.org/)).
6. Les listes d’IP de proxys de confiance peuvent être téléchargées automatiquement via des URLs.

### Comment l’utiliser

1. Activer : mettez le paramètre `USE_REAL_IP` à `yes`.
2. Proxys de confiance : renseignez IP/plages dans `REAL_IP_FROM`.
3. En‑tête : indiquez lequel porte l’IP réelle via `REAL_IP_HEADER`.
4. Récursif : activez `REAL_IP_RECURSIVE` si nécessaire.
5. Sources URL : utilisez `REAL_IP_FROM_URLS` pour télécharger des listes.
6. PROXY protocol : activez `USE_PROXY_PROTOCOL` si l’amont le supporte.

!!! danger "Avertissement PROXY protocol"
    Activer `USE_PROXY_PROTOCOL` sans un amont correctement configuré pour l’émettre cassera votre application. Assurez‑vous de l’avoir configuré avant activation.

### Paramètres

| Paramètre            | Défaut                                    | Contexte  | Multiple | Description                                                                      |
| -------------------- | ----------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------- |
| `USE_REAL_IP`        | `no`                                      | multisite | non      | Activer la récupération de l’IP réelle depuis les en‑têtes ou le PROXY protocol. |
| `REAL_IP_FROM`       | `192.168.0.0/16 172.16.0.0/12 10.0.0.0/8` | multisite | non      | Proxys de confiance : liste d’IP/réseaux séparés par des espaces.                |
| `REAL_IP_HEADER`     | `X-Forwarded-For`                         | multisite | non      | En‑tête porteur de l’IP réelle ou valeur spéciale `proxy_protocol`.              |
| `REAL_IP_RECURSIVE`  | `yes`                                     | multisite | non      | Recherche récursive dans un en‑tête contenant plusieurs IPs.                     |
| `REAL_IP_FROM_URLS`  |                                           | multisite | non      | URLs fournissant des IPs/réseaux de proxys de confiance (supporte `file://`).    |
| `USE_PROXY_PROTOCOL` | `no`                                      | global    | non      | Activer le support PROXY protocol pour la communication directe proxy→BunkerWeb. |

!!! tip "Fournisseurs cloud"
    Ajoutez les IP de vos load balancers (AWS/GCP/Azure…) à `REAL_IP_FROM` pour une identification correcte.

!!! danger "Considérations sécurité"
    N’ajoutez que des sources de confiance, sinon risque d’usurpation d’IP via en‑têtes manipulés.

!!! info "Multiples adresses"
    Avec `REAL_IP_RECURSIVE`, si l’en‑tête contient plusieurs IPs, la première non listée comme proxy de confiance est retenue comme IP client.

### Exemples

=== "Basique (derrière reverse proxy)"

    Configuration simple pour un site derrière un reverse proxy :

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24 10.0.0.5"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "Load balancer cloud"

    Configuration pour un site derrière un load balancer cloud :

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "PROXY Protocol"

    Configuration utilisant le PROXY protocol avec un load balancer compatible :

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24"
    REAL_IP_HEADER: "proxy_protocol"
    USE_PROXY_PROTOCOL: "yes"
    ```

=== "Sources de proxys multiples avec URL"

    Configuration avancée avec des listes d'IP de proxys mises à jour automatiquement :

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Real-IP"
    REAL_IP_RECURSIVE: "yes"
    REAL_IP_FROM_URLS: "https://example.com/proxy-ips.txt file:///etc/bunkerweb/custom-proxies.txt"
    ```

=== "Configuration CDN"

    Configuration pour un site web derrière un CDN :

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_FROM_URLS: "https://cdn-provider.com/ip-ranges.txt"
    REAL_IP_HEADER: "CF-Connecting-IP"  # Exemple pour Cloudflare
    REAL_IP_RECURSIVE: "no"  # Inutile avec les en-têtes à IP unique
    ```

=== "Derrière Cloudflare"

    Configuration pour un site web derrière Cloudflare :

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "" # Nous faisons uniquement confiance aux IP Cloudflare
    REAL_IP_FROM_URLS: "https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/" # Télécharge automatiquement les IP Cloudflare
    REAL_IP_HEADER: "CF-Connecting-IP"  # En-tête Cloudflare pour l'IP client
    REAL_IP_RECURSIVE: "yes"
    ```
