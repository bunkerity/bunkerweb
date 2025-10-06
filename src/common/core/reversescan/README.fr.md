Le plugin Reverse Scan protège contre les tentatives de contournement via proxy en scannant certains ports côté client pour détecter des proxys/serveurs ouverts. Il aide à identifier et bloquer les clients qui tentent de masquer leur identité ou leur origine.

Comment ça marche :

1. À la connexion d’un client, BunkerWeb tente de scanner des ports spécifiques sur l’IP du client.
2. Les ports de proxy courants (80, 443, 8080, etc.) sont vérifiés.
3. Si des ports ouverts sont détectés (signe d’un proxy), la connexion est refusée.
4. Cela ajoute une couche contre bots/outils automatisés et utilisateurs malveillants.

### Comment l’utiliser

1. Activer : `USE_REVERSE_SCAN: yes`.
2. Ports : personnalisez `REVERSE_SCAN_PORTS`.
3. Timeout : ajustez `REVERSE_SCAN_TIMEOUT` pour l’équilibre sécurité/performance.
4. Suivi : consultez les logs et la [web UI](web-ui.md).

### Paramètres

| Paramètre              | Défaut                     | Contexte  | Multiple | Description                                 |
| ---------------------- | -------------------------- | --------- | -------- | ------------------------------------------- |
| `USE_REVERSE_SCAN`     | `no`                       | multisite | non      | Activer l’analyse des ports côté client.    |
| `REVERSE_SCAN_PORTS`   | `22 80 443 3128 8000 8080` | multisite | non      | Ports à vérifier (séparés par des espaces). |
| `REVERSE_SCAN_TIMEOUT` | `500`                      | multisite | non      | Délai max par port en millisecondes.        |

!!! warning "Performance"
    Scanner de nombreux ports ajoute de la latence. Limitez la liste et adaptez le timeout.

!!! info "Ports de proxy courants"
    La configuration par défaut inclut 80, 443, 8080, 3128 et SSH (22). Adaptez selon votre modèle de menace.

### Exemples

=== "Basique"

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "500"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Approfondi"

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1000"
    REVERSE_SCAN_PORTS: "22 80 443 3128 8080 8000 8888 1080 3333 8081"
    ```

=== "Optimisé performance"

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "250"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Haute sécurité"

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1500"
    REVERSE_SCAN_PORTS: "22 25 80 443 1080 3128 3333 4444 5555 6588 6666 7777 8000 8080 8081 8800 8888 9999"
    ```
