# Utilisations avancées

De nombreux exemples de cas d'utilisation concrets sont disponibles dans le dossier [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc1/examples) du dépôt GitHub.

Nous fournissons également de nombreux modèles standard, tels que des fichiers YAML pour diverses intégrations et types de bases de données. Ceux-ci sont disponibles dans le dossier [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc1/misc/integrations).

Cette section se concentre uniquement sur les utilisations avancées et le réglage de la sécurité, consultez la [section fonctionnalités](features.md) de la documentation pour voir tous les paramètres disponibles.

## Cas d'utilisation

!!! tip "Tester"
    Pour effectuer des tests rapides lorsque le mode multisite est activé (et si vous n'avez pas les bonnes entrées DNS configurées pour les domaines), vous pouvez utiliser curl avec l'en-tête HTTP Host de votre choix :
    ```shell
    curl -H "Host: app1.example.com" http://ip-or-fqdn-of-server
    ```

    Si vous utilisez HTTPS, vous devrez configurer le SNI :
    ```shell
    curl -H "Host: app1.example.com" --resolve example.com:443:ip-of-server https://example.com
    ```

### Derrière l'équilibreur de charge ou le proxy inverse

!!! info "Real IP"

    Lorsque BunkerWeb se trouve lui‑même derrière un équilibreur de charge ou un proxy inverse, vous devez le configurer afin qu'il puisse récupérer la véritable adresse IP des clients. **Si vous ne le faites pas, les fonctionnalités de sécurité bloqueront l'adresse IP de l'équilibreur de charge ou du proxy inverse au lieu de celle du client.**

BunkerWeb prend en fait en charge deux méthodes pour récupérer l'adresse IP réelle du client :

- À l'aide de l'icône `PROXY protocol`
- À l'aide d'un en-tête HTTP tel que `X-Forwarded-For`

Les paramètres suivants peuvent être utilisés :

- `USE_REAL_IP` : activer/désactiver la récupération d'IP réelle
- `USE_PROXY_PROTOCOL` : activer/désactiver la prise en charge du protocole PROXY.
- `REAL_IP_FROM` : liste d'adresses IP/réseau de confiance autorisées pour nous envoyer la "vraie IP"
- `REAL_IP_HEADER` : l'en-tête HTTP contenant l'IP réelle ou la valeur spéciale `proxy_protocol` lors de l'utilisation du protocole PROXY

Vous trouverez plus de paramètres sur l'IP réelle dans la [section des fonctionnalités](features.md#real-ip) de la documentation.

=== "En-tête HTTP"

    Nous supposerons ce qui suit concernant les équilibreurs de charge ou les proxies inverses (vous devrez mettre à jour les paramètres en fonction de votre configuration) :

    - Ils utilisent l' `X-Forwarded-For` en-tête pour définir l'adresse IP réelle
    - Ils ont des adresses IP dans les `1.2.3.0/24` réseaux`100.64.0.0/10` et

    === "Interface utilisateur Web"

        Accédez à la page **Config Globale**, sélectionnez le plugin **Real IP** et renseignez les paramètres suivants :

        <figure markdown>![Paramètres Real IP (en-tête) via l'interface Web](assets/img/advanced-proxy1.png){ align=center }<figcaption>Paramètres Real IP (en-tête) via l'interface Web</figcaption></figure>

        Veuillez noter qu'il est recommandé de redémarrer BunkerWeb lorsque vous modifiez des paramètres liés à la récupération de la vraie adresse IP.

    === "Linux"

        Vous devrez ajouter ces paramètres au fichier /etc/bunkerweb/variables.env :

        ```conf
        ...
        USE_REAL_IP=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=X-Forwarded-For
        ...
        ```

        Veuillez noter qu'il est recommandé de redémarrer plutôt que de recharger le service lorsque vous modifiez les paramètres liés à la récupération de la vraie adresse IP :

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "Tout-en-un"

        Vous devrez ajouter ces paramètres aux variables d'environnement lors de l'exécution du conteneur All-in-one :

        ```bash
        docker run -d \
            --name bunkerweb-aio \
            -v bw-storage:/data \
            -e USE_REAL_IP="yes" \
            -e REAL_IP_FROM="1.2.3.0/24 100.64.0.0/10" \
            -e REAL_IP_HEADER="X-Forwarded-For" \
            -p 80:8080/tcp \
            -p 443:8443/tcp \
            -p 443:8443/udp \
            bunkerity/bunkerweb-all-in-one:1.6.5-rc1
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    === "Docker"

        Vous devrez ajouter ces paramètres aux variables d'environnement des conteneurs BunkerWeb et du Scheduler :

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    === "Docker autoconf"

        Vous devrez ajouter ces paramètres aux variables d'environnement des conteneurs BunkerWeb et du Scheduler :

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    === "Kubernetes"

        Vous devrez ajouter ces paramètres aux variables d'environnement des pods BunkerWeb et du Scheduler.

        Voici la partie correspondante de votre fichier `values.yaml` que vous pouvez utiliser :

        ```yaml
        bunkerweb:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "X-Forwarded-For"
        scheduler:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "X-Forwarded-For"
        ```

    === "Swarm"

        !!! warning "Obsolète"
            L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

            **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

        Vous devrez ajouter ces paramètres aux variables d'environnement des services BunkerWeb et scheduler :

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

=== "Protocole proxy"

    !!! warning "Lire attentivement"

      N'utilisez le protocole `PROXY protocol` que si vous êtes certain que votre équilibreur de charge ou proxy inverse l'envoie. **Si vous l'activez et qu'il n'est pas utilisé, vous obtiendrez des erreurs**.

    Nous supposerons ce qui suit concernant les équilibreurs de charge ou les proxies inverses (vous devrez adapter les paramètres en fonction de votre configuration) :

    - Ils utilisent le `PROXY protocol` v1 ou v2 pour définir l'adresse IP réelle
    - Ils ont des adresses IP dans les réseaux `1.2.3.0/24` et `100.64.0.0/10`

    === "Interface utilisateur Web"

        Accédez à la page **Config Globale**, sélectionnez le plugin **Real IP** et renseignez les paramètres suivants :

        <figure markdown>![Paramètres Real IP (protocole PROXY) via l'interface Web](assets/img/advanced-proxy2.png){ align=center }<figcaption>Paramètres Real IP (protocole PROXY) via l'interface Web</figcaption></figure>

        Veuillez noter qu'il est recommandé de redémarrer BunkerWeb lorsque vous modifiez des paramètres liés à la récupération de la vraie adresse IP.

    === "Linux"

        Vous devrez ajouter ces paramètres au fichier /etc/bunkerweb/variables.env :

        ```conf
        ...
        USE_REAL_IP=yes
        USE_PROXY_PROTOCOL=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=proxy_protocol
        ...
        ```

        Veuillez noter qu'il est recommandé de redémarrer plutôt que de recharger le service lors de la configuration des paramètres liés au protocole PROXY :

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "Tout-en-un"

        Vous devrez ajouter ces paramètres aux variables d'environnement lors de l'exécution du conteneur All-in-one :

        ```bash
        docker run -d \
            --name bunkerweb-aio \
            -v bw-storage:/data \
            -e USE_REAL_IP="yes" \
            -e USE_PROXY_PROTOCOL="yes" \
            -e REAL_IP_FROM="1.2.3.0/24 100.64.0.0/10" \
            -e REAL_IP_HEADER="X-Forwarded-For" \
            -p 80:8080/tcp \
            -p 443:8443/tcp \
            -p 443:8443/udp \
            bunkerity/bunkerweb-all-in-one:1.6.5-rc1
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    === "Docker"

        Vous devrez ajouter ces paramètres aux variables d'environnement des conteneurs BunkerWeb et du Scheduler :

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    === "Docker autoconf"

        Vous devrez ajouter ces paramètres aux variables d'environnement des conteneurs BunkerWeb et du Scheduler :

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    === "Kubernetes"

        Vous devrez ajouter ces paramètres aux variables d'environnement des pods BunkerWeb et du Scheduler.

        Voici la partie correspondante de votre fichier `values.yaml` que vous pouvez utiliser :

        ```yaml
        bunkerweb:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: USE_PROXY_PROTOCOL
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "proxy_protocol"
        scheduler:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: USE_PROXY_PROTOCOL
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "proxy_protocol"
        ```

    === "Swarm"

        !!! warning "Obsolète"
            L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

            **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

        Vous devrez ajouter ces paramètres aux variables d'environnement des services BunkerWeb et scheduler :

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

### Utilisation de mécanismes de résolution DNS personnalisés

La configuration NGINX de BunkerWeb peut être personnalisée pour utiliser différents résolveurs DNS en fonction de vos besoins. Cela peut être particulièrement utile dans divers scénarios :

1. Pour respecter les entrées de votre `/etc/hosts` fichier local
2. Lorsque vous devez utiliser des serveurs DNS personnalisés pour certains domaines
3. Pour s'intégrer à des solutions de mise en cache DNS locales

#### Utilisation de systemd-resolved

De nombreux systèmes Linux modernes utilisent `systemd-resolved` la résolution DNS. Si vous souhaitez que BunkerWeb respecte le contenu de votre `/etc/hosts` fichier et utilise le mécanisme de résolution DNS du système, vous pouvez le configurer pour utiliser le service DNS local résolu par systemd.

Pour vérifier que systemd-resolved est en cours d'exécution sur votre système, vous pouvez utiliser :

```bash
systemctl status systemd-resolved
```

Pour activer systemd-resolved comme résolveur DNS dans BunkerWeb, définissez le `DNS_RESOLVERS` paramètre sur `127.0.0.53`, qui est l'adresse d'écoute par défaut pour systemd-resolved :

=== "Interface utilisateur Web"

    Accédez à la page **Config Globale** et définissez les résolveurs DNS sur `127.0.0.53`

    <figure markdown>![Paramètres des résolveurs DNS via l'interface Web](assets/img/advanced-dns-resolvers.png){ align=center }<figcaption>Paramètres des résolveurs DNS via l'interface Web</figcaption></figure>

=== "Linux"

    Vous devrez modifier le fichier /etc/bunkerweb/variables.env :

    ```conf
    ...
    DNS_RESOLVERS=127.0.0.53
    ...
    ```

    Après avoir effectué cette modification, rechargez le Scheduler pour appliquer la configuration :

    ```shell
    sudo systemctl reload bunkerweb-scheduler
    ```

#### Utilisation de dnsmasq

[dnsmasq](http://www.thekelleys.org.uk/dnsmasq/doc.html) est un serveur DNS, DHCP et TFTP léger qui est couramment utilisé pour la mise en cache et la personnalisation du DNS local. C'est particulièrement utile lorsque vous avez besoin de plus de contrôle sur votre résolution DNS que celui fourni par systemd-resolved.

=== "Linux"

    Tout d'abord, installez et configurez dnsmasq sur votre système Linux :

    === "Debian/Ubuntu"

        ```bash
        # Install dnsmasq
        sudo apt-get update && sudo apt-get install dnsmasq

        # Configure dnsmasq to listen only on localhost
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # Add custom DNS entries if needed
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # Restart dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    === "RHEL/Fedora"

        ```bash
        # Install dnsmasq
        sudo dnf install dnsmasq

        # Configure dnsmasq to listen only on localhost
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # Add custom DNS entries if needed
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # Restart dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    Ensuite, configurez BunkerWeb pour utiliser dnsmasq en définissant `DNS_RESOLVERS` sur `127.0.0.1` :

    === "Web UI"

        Accédez à la page **Config Globale** et sélectionnez le plugin **NGINX**, puis définissez les résolveurs DNS sur `127.0.0.1`.

        <figure markdown>![Paramètres des résolveurs DNS via l'interface Web](assets/img/advanced-dns-resolvers2.png){ align=center }<figcaption>Paramètres des résolveurs DNS via l'interface Web</figcaption></figure>

    === "Linux"

        Vous devrez modifier le fichier `/etc/bunkerweb/variables.env` :

        ```conf
        ...
        DNS_RESOLVERS=127.0.0.1
        ...
        ```

        Après avoir effectué cette modification, rechargez le Scheduler pour appliquer la configuration :

        ```shell
        sudo systemctl reload bunkerweb-scheduler
        ```

=== "Tout-en-un"

    Lorsque vous utilisez l'image All-in-one, exécutez dnsmasq dans un conteneur séparé et configurez BunkerWeb pour l'utiliser :

    ```bash
    # Create a custom network for DNS communication
    docker network create bw-dns

    # Run dnsmasq container using dockurr/dnsmasq with Quad9 DNS
    # Quad9 provides security-focused DNS resolution with malware blocking
    docker run -d \
        --name dnsmasq \
        --network bw-dns \
        -e DNS1="9.9.9.9" \
        -e DNS2="149.112.112.112" \
        -p 53:53/udp \
        -p 53:53/tcp \
        --cap-add=NET_ADMIN \
        --restart=always \
        dockurr/dnsmasq

    # Run BunkerWeb All-in-one with dnsmasq DNS resolver
    docker run -d \
        --name bunkerweb-aio \
        --network bw-dns \
        -v bw-storage:/data \
        -e DNS_RESOLVERS="dnsmasq" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.5-rc1
    ```

=== "Docker"

    Ajoutez un service dnsmasq à votre fichier docker-compose et configurez BunkerWeb pour l'utiliser :

    ```yaml
    services:
      dnsmasq:
        image: dockurr/dnsmasq
        container_name: dnsmasq
        environment:
          # Using Quad9 DNS servers for enhanced security and privacy
          # Primary: 9.9.9.9 (Quad9 with malware blocking)
          # Secondary: 149.112.112.112 (Quad9 backup server)
          DNS1: "9.9.9.9"
          DNS2: "149.112.112.112"
        ports:
          - 53:53/udp
          - 53:53/tcp
        cap_add:
          - NET_ADMIN
        restart: always
        networks:
          - bw-dns

      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc1
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-services
          - bw-dns

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-dns

    networks:
      # ...existing networks...
      bw-dns:
        name: bw-dns
    ```

### Configurations personnalisées

Pour personnaliser et ajouter des configurations personnalisées à BunkerWeb, vous pouvez profiter de sa base NGINX. Des configurations NGINX personnalisées peuvent être ajoutées dans différents contextes NGINX, y compris des configurations pour le pare-feu d'applications Web (WAF) ModSecurity, qui est un composant central de BunkerWeb. Vous trouverez plus de détails sur les configurations de ModSecurity [ici](features.md#custom-configurations).

Voici les types de configurations personnalisées disponibles :

- **http** : Configurations au niveau HTTP de NGINX.
- **server-http** : configurations au niveau HTTP/Server de NGINX.
- **default-server-http**: configurations au niveau du serveur de NGINX, en particulier pour le "serveur par défaut" lorsque le nom de client fourni ne correspond à aucun nom de serveur dans `SERVER_NAME`.
- **modsec-crs**: Configurations appliquées avant le chargement de l'ensemble de règles de base OWASP.
- **modsec**: configurations appliquées après le chargement de l'ensemble de règles de base OWASP ou utilisées lorsque l'ensemble de règles de base n'est pas chargé.
- **crs-plugins-before**: Configurations pour les plugins CRS, appliquées avant le chargement des plugins CRS.
- **crs-plugins-after**: Configurations pour les plugins CRS, appliquées après le chargement des plugins CRS.
- **stream** : Configurations au niveau du flux de NGINX.
- **server-stream** : Configurations au niveau Stream/Server de NGINX.

Les configurations personnalisées peuvent être appliquées globalement ou spécifiquement pour un serveur particulier, en fonction du contexte applicable et de l'activation ou non du [mode multisite](concepts.md#multisite-mode) .

La méthode d'application des configurations personnalisées dépend de l'intégration utilisée. Cependant, le processus sous-jacent implique l'ajout de fichiers avec le `.conf` suffixe à des dossiers spécifiques. Pour appliquer une configuration personnalisée à un serveur spécifique, le fichier doit être placé dans un sous-dossier nommé d'après le nom du serveur principal.

Certaines intégrations offrent des moyens plus pratiques d'appliquer des configurations, par exemple à l'aide de [Configs](https://docs.docker.com/engine/swarm/configs/) dans Docker Swarm ou de [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) dans Kubernetes. Ces options offrent des approches plus simples pour la gestion et l'application des configurations.

=== "Interface utilisateur Web"

    Accédez à la page **Configs**, cliquez sur **Create new custom config**, puis choisissez s'il s'agit d'une configuration globale ou spécifique à un service, le type de configuration et le nom de la configuration :

    <figure markdown>![Configurations personnalisées via l'interface Web](assets/img/advanced-config.png){ align=center }<figcaption>Configurations personnalisées via l'interface Web</figcaption></figure>

    N'oubliez pas de cliquer sur le bouton `💾 Enregistrer`.

=== "Linux"

    Lorsque vous utilisez l'intégration [Linux](integrations.md#linux), les configurations personnalisées doivent être écrites dans le dossier `/etc/bunkerweb/configs`.

    Voici un exemple pour server-http/hello-world.conf :

    ```nginx
    location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }
    ```

    Comme BunkerWeb s'exécute en tant qu'utilisateur non privilégié (nginx:nginx), vous devrez modifier les permissions :

    ```shell
    chown -R root:nginx /etc/bunkerweb/configs && \
    chmod -R 770 /etc/bunkerweb/configs
    ```

    Vérifions maintenant l'état du Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    S'ils sont déjà en cours d'exécution, nous pouvons le recharger :

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Sinon, nous devrons le démarrer :

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Tout-en-un"

    Lorsque vous utilisez l'image [Tout-en-un](integrations.md#all-in-one-aio-image), vous avez deux options pour ajouter des configurations personnalisées :

    - Utilisation de paramètres spécifiques `*_CUSTOM_CONF_*` comme variables d'environnement lors de l'exécution du conteneur (recommandé).
    - Écriture `.conf` de fichiers dans le `/data/configs/` répertoire du volume monté sur `/data`.

    **Utilisation des paramètres (variables d'environnement)**

    Les paramètres à utiliser doivent suivre le schéma `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>`:

    - `<SITE>` : Nom du serveur primaire facultatif si le mode multisite est activé et que la configuration doit être appliquée à un service spécifique.
    - `<TYPE>` : Le type de configuration, les valeurs acceptées sont `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP` `MODSEC` `MODSEC_CRS` `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER` `STREAM` , et `SERVER_STREAM`.
    - `<NAME>` : Le nom de la configuration sans le `.conf` suffixe.

    Voici un exemple fictif lors de l'exécution du conteneur All-in-one :

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -e "CUSTOM_CONF_SERVER_HTTP_hello-world=location /hello { \
            default_type 'text/plain'; \
            content_by_lua_block { \
              ngx.say('world'); \
            } \
          }" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        bunkerity/bunkerweb-all-in-one:1.6.5-rc1
    ```

    Veuillez noter que si votre conteneur est déjà créé, vous devrez le supprimer et le recréer pour que les nouvelles variables d'environnement soient appliquées.

    **Utilisation de fichiers**

    La première chose à faire est de créer les dossiers :

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    Vous pouvez maintenant écrire vos configurations :

    ```shell
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Étant donné que le Scheduler s'exécute en tant qu'utilisateur non privilégié avec UID et GID 101, vous devrez modifier les autorisations :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Au démarrage du conteneur de l'ordonnanceur, vous devrez monter le dossier sur /data :

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v ./bw-data:/data \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.5-rc1
    ```

=== "Docker"

    Lorsque vous utilisez l'intégration [Docker](integrations.md#docker), vous avez deux options pour ajouter des configurations personnalisées :

    - Utilisation de paramètres spécifiques `*_CUSTOM_CONF_*` comme variables d'environnement (recommandé)
    - Écriture des fichiers .conf sur le volume monté sur /data de l'ordonnanceur

    **Utilisation des paramètres**

    Les paramètres à utiliser doivent suivre le schéma `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` :

    - `<SITE>` : nom de serveur primaire facultatif si le mode multisite est activé et que la configuration doit être appliquée à un service spécifique
    - `<TYPE>` : le type de configuration, les valeurs acceptées sont `HTTP`, `DEFAULT_SERVER_HTTP` `SERVER_HTTP` `MODSEC` `MODSEC_CRS` `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER`, `STREAM` , et `SERVER_STREAM`
    - `<NAME>` : le nom de config sans le suffixe .conf

    Voici un exemple factice utilisant un fichier docker-compose :

    ```yaml
    ...
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
      environment:
        - |
          CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
              ngx.say('world')
            }
          }
      ...
    ```

    **Utilisation de fichiers**

    La première chose à faire est de créer les dossiers :

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    Vous pouvez maintenant écrire vos configurations :

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Étant donné que le Scheduler s'exécute en tant qu'utilisateur non privilégié avec UID et GID 101, vous devrez modifier les autorisations :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Au démarrage du conteneur de l'ordonnanceur, vous devrez monter le dossier sur /data :

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Docker autoconf"

    Lorsque vous utilisez l'intégration [Docker autoconf](integrations.md#docker-autoconf), vous avez deux options pour ajouter des configurations personnalisées :

    - Utilisation de paramètres spécifiques `*_CUSTOM_CONF_*` comme étiquettes (le plus simple)
    - Écriture des fichiers .conf sur le volume monté sur /data de l'ordonnanceur

    **Utilisation des étiquettes**

    !!! warning "Limitations de l'utilisation des étiquettes"
        Lorsque vous utilisez des étiquettes avec l'intégration Docker autoconf, vous ne pouvez appliquer des configurations personnalisées que pour le service web correspondant. L'application de **http**, **default-server-http**, **stream** ou de toute configuration globale (comme **server-http** ou **server-stream** pour tous les services) n'est pas possible : vous devrez monter des fichiers à cet effet.

    Les étiquettes à utiliser doivent suivre le modèle `bunkerweb.CUSTOM_CONF_<TYPE>_<NAME>` :

    - `<TYPE>` : le type de configuration, les valeurs acceptées sont `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE` `CRS_PLUGINS_AFTER` et `SERVER_STREAM`
    - `<NAME>` : le nom de config sans le suffixe .conf

    Voici un exemple factice utilisant un fichier docker-compose :

    ```yaml
    myapp:
      image: nginxdemos/nginx-hello
      labels:
        - |
          bunkerweb.CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
                ngx.say('world')
            }
          }
      ...
    ```

    **Utilisation de fichiers**

    La première chose à faire est de créer les dossiers :

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    Vous pouvez maintenant écrire vos configurations :

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Étant donné que le Scheduler s'exécute en tant qu'utilisateur non privilégié avec UID et GID 101, vous devrez modifier les autorisations :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Au démarrage du conteneur de l'ordonnanceur, vous devrez monter le dossier sur /data :

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Kubernetes"

    Lors de l'utilisation de l'[intégration Kubernetes](integrations.md#kubernetes), les configurations personnalisées sont gérées à l'aide de [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/).

    Pour simplifier, vous n'avez même pas besoin d'attacher le ConfigMap à un Pod (par ex. comme variable d'environnement ou volume) : le Pod d'autoconf écoute les événements ConfigMap et mettra à jour les configurations personnalisées lorsque nécessaire.

    Lors de la création d'un ConfigMap, vous devrez ajouter des labels spéciaux :

    * **bunkerweb.io/CONFIG_TYPE** : doit être défini sur un type de configuration personnalisé valide (http, server-http, default-server-http, modsec, modsec-crs, crs-plugins-before, crs-plugins-after, stream ou server-stream)
    * **bunkerweb.io/CONFIG_SITE** : défini sur un nom de serveur pour appliquer la configuration à ce serveur spécifique (facultatif, sera appliqué globalement s'il n'est pas défini)

    Voici l'exemple :

    ```yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: cfg-bunkerweb-all-server-http
      annotations:
        bunkerweb.io/CONFIG_TYPE: "server-http"
    data:
      myconf: |
      location /hello {
        default_type 'text/plain';
        content_by_lua_block {
          ngx.say('world')
        }
      }
    ```

    !!! tip "Custom Extra Config"
        Depuis la version `1.6.0`, vous pouvez ajouter/remplacer des paramètres à l'aide de l'annotation `bunkerweb.io/CONFIG_TYPE=settings`. En voici un exemple :

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: cfg-bunkerweb-extra-settings
          annotations:
            bunkerweb.io/CONFIG_TYPE: "settings"
        data:
          USE_ANTIBOT: "captcha" # multisite setting that will be applied to all services that do not override it
          USE_REDIS: "yes" # global setting that will be applied globally
          ...
        ```

=== "Swarm"

    !!! warning "Obsolète"
        L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

    Lorsque vous utilisez l'[Swarm integration](integrations.md#swarm), les configurations personnalisées sont gérées à l'aide des [Docker Configs](https://docs.docker.com/engine/swarm/configs/).

    Pour simplifier, vous n'avez même pas besoin d'attacher le Config à un service : le service d'autoconf écoute les événements Config et mettra à jour les configurations personnalisées lorsque nécessaire.

    Lors de la création d'un Config, vous devrez ajouter des labels spéciaux :

    * **bunkerweb.CONFIG_TYPE** : doit être défini sur un type de configuration personnalisé valide (http, server-http, default-server-http, modsec, modsec-crs, crs-plugins-before, crs-plugins-after, stream ou server-stream)
    * **bunkerweb.CONFIG_SITE** : défini sur un nom de serveur pour appliquer la configuration à ce serveur spécifique (facultatif, sera appliqué globalement s'il n'est pas défini)

    Voici l'exemple :

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" | docker config create -l bunkerweb.CONFIG_TYPE=server-http my-config -
    ```

    Il n'y a pas de mécanisme de mise à jour : l'alternative est de supprimer une configuration existante à l'aide puis de `docker config rm` la recréer.

### Exécution de nombreux services en production

#### CRS mondial

!!! warning "Plugins CRS"
    Lorsque le SCR est chargé globalement, les **plug-ins SCR ne sont pas pris en charge**. Si vous avez besoin de les utiliser, vous devrez charger le SCR par service.

Si vous utilisez BunkerWeb en production avec un grand nombre de services, et que vous activez la **fonctionnalité ModSecurity globalement** avec des règles CRS, le temps nécessaire pour charger les configurations BunkerWeb peut devenir trop long, ce qui peut entraîner un délai d'expiration.

La solution de contournement consiste à charger les règles CRS globalement plutôt que par service. Ce comportement n'est pas activé par défaut pour des raisons de compatibilité descendante et parce qu'il présente un inconvénient : si vous activez le chargement des règles CRS globales, **il ne sera plus possible de définir des règles modsec-crs** (exécutées avant les règles CRS) par service. Cependant, cette limitation peut être contournée en écrivant des règles d'exclusion globales `modsec-crs` comme suit :

```
SecRule REQUEST_FILENAME "@rx ^/somewhere$" "nolog,phase:4,allow,id:1010,chain"
SecRule REQUEST_HEADERS:Host "@rx ^app1\.example\.com$" "nolog"
```

Vous pouvez activer le chargement global du SCR en définissant `USE_MODSECURITY_GLOBAL_CRS` la valeur . `yes`

#### Ajuster max_allowed_packet pour MariaDB/MySQL

Il semble que la valeur par défaut du `max_allowed_packet` paramètre dans les serveurs de bases de données MariaDB et MySQL ne soit pas suffisante lors de l'utilisation de BunkerWeb avec un grand nombre de services.

Si vous rencontrez des erreurs comme celle-ci, en particulier sur le Scheduler :

```
[Warning] Aborted connection 5 to db: 'db' user: 'bunkerweb' host: '172.20.0.4' (Got a packet bigger than 'max_allowed_packet' bytes)
```

Vous devrez augmenter le `max_allowed_packet` sur votre serveur de base de données.

### Persistance des interdictions et des signalements

Par défaut, BunkerWeb stocke les bannissements et les rapports dans un magasin de données Lua local. Bien que simple et efficace, cette configuration signifie que des données sont perdues lors du redémarrage de l'instance. Pour vous assurer que les bannissements et les rapports persistent lors des redémarrages, vous pouvez configurer BunkerWeb pour utiliser un [ serveur Redis](https://redis.io/) ou [Valkey](https://valkey.io/) distant  .

**Pourquoi utiliser Redis/Valkey ?**

Redis et Valkey sont de puissants magasins de données en mémoire couramment utilisés comme bases de données, caches et courtiers de messages. Ils sont hautement évolutifs et prennent en charge une variété de structures de données, notamment :

- **Chaînes**: paires clé-valeur de base.
- **Hachages**: paires champ-valeur au sein d'une seule clé.
- **Listes**: collections ordonnées de chaînes.
- **Ensembles**: collections non ordonnées de chaînes uniques.
- **Ensembles triés**: Collections ordonnées avec partitions.

En tirant parti de Redis ou de Valkey, BunkerWeb peut stocker de manière persistante les bannissements, les rapports et les données de cache, garantissant ainsi la durabilité et l'évolutivité.

**Activation de la prise en charge Redis/Valkey**

Pour activer la prise en charge de Redis ou Valkey, configurez les paramètres suivants dans votre fichier de configuration BunkerWeb :

```conf
# Enable Redis/Valkey support
USE_REDIS=yes

# Redis/Valkey server hostname or IP address
REDIS_HOST=<hostname>

# Redis/Valkey server port number (default: 6379)
REDIS_PORT=6379

# Redis/Valkey database number (default: 0)
REDIS_DATABASE=0
```

- **`USE_REDIS`**: Réglez sur `yes` pour activer l'intégration Redis/Valkey.
- **`REDIS_HOST`**: Spécifiez le nom d'hôte ou l'adresse IP du serveur Redis/Valkey.
- **`REDIS_PORT`**: Spécifiez le numéro de port pour le serveur Redis/Valkey. La valeur par défaut est `6379`.
- **`REDIS_DATABASE`**: Indiquez le numéro de base de données Redis/Valkey à utiliser. La valeur par défaut est `0`.

Si vous avez besoin de paramètres plus avancés, tels que l'authentification, la prise en charge SSL/TLS ou le mode Sentinel, reportez-vous à la documentation sur les paramètres du [plug-in Redis](features.md#redis) pour obtenir des conseils détaillés.

### Protéger les applications UDP/TCP

!!! example "Fonctionnalité expérimentale"

	  This feature is not production-ready. Feel free to test it and report us any bug using [issues](https://github.com/bunkerity/bunkerweb/issues) in the GitHub repository.

BunkerWeb offre la possibilité de fonctionner comme un **proxy inverse UDP/TCP générique**, ce qui vous permet de protéger toutes les applications basées sur le réseau fonctionnant au moins sur la couche 4 du modèle OSI. Au lieu d'utiliser le module HTTP "classique", BunkerWeb exploite le [module de flux](https://nginx.org/en/docs/stream/ngx_stream_core_module.html) de NGINX.

Il est important de noter que **tous les paramètres et fonctionnalités de sécurité ne sont pas disponibles lors de l'utilisation du module de flux**. Vous trouverez de plus amples informations à ce sujet dans les sections des [fonctionnalités](features.md) de la documentation.

La configuration d'un proxy inverse de base est assez similaire à la configuration HTTP, car elle implique l'utilisation des mêmes paramètres : `USE_REVERSE_PROXY=yes` et `REVERSE_PROXY_HOST=myapp:9000`. Même lorsque BunkerWeb est positionné derrière un équilibreur de charge, les paramètres restent les mêmes (le **protocole PROXY** étant l'option prise en charge pour des raisons évidentes).

En plus de cela, les paramètres spécifiques suivants sont utilisés :

- `SERVER_TYPE=stream` : activer  le `stream` mode (UDP/TCP générique) au lieu d' `http` un (qui est la valeur par défaut)
- `LISTEN_STREAM_PORT=4242` : le port d'écoute "simple" (sans SSL/TLS) sur lequel BunkerWeb écoutera
- `LISTEN_STREAM_PORT_SSL=4343` : le port d'écoute "ssl/tls" sur lequel BunkerWeb écoutera
- `USE_UDP=no` : écouter et transférer les paquets UDP au lieu de TCP

Pour la liste complète des paramètres concernant `stream` le  mode, veuillez vous référer à la sections des [fonctionnalités](features.md) de la documentation.

!!! tip "Plusieurs ports d'écoute"

    Depuis la version `1.6.0`, BunkerWeb prend en charge plusieurs ports d'écoute pour le mode `stream`. Vous pouvez les spécifier à l'aide des paramètres `LISTEN_STREAM_PORT` et `LISTEN_STREAM_PORT_SSL`.

    Voici un exemple :

    ```conf
    ...
    LISTEN_STREAM_PORT=4242
    LISTEN_STREAM_PORT_SSL=4343
    LISTEN_STREAM_PORT_1=4244
    LISTEN_STREAM_PORT_SSL_1=4344
    ...
    ```

=== "Tout-en-un"

    Vous devrez ajouter ces paramètres aux variables d'environnement lors de l'exécution du conteneur All-in-one. Vous devrez également exposer les ports de stream.

    Cet exemple configure BunkerWeb pour agir comme proxy inverse pour deux applications basées sur le mode stream : `app1.example.com` et `app2.example.com`.

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -e SERVICE_UI="no" \
        -e SERVER_NAME="app1.example.com app2.example.com" \
        -e MULTISITE="yes" \
        -e USE_REVERSE_PROXY="yes" \
        -e SERVER_TYPE="stream" \
        -e app1.example.com_REVERSE_PROXY_HOST="myapp1:9000" \
        -e app1.example.com_LISTEN_STREAM_PORT="10000" \
        -e app2.example.com_REVERSE_PROXY_HOST="myapp2:9000" \
        -e app2.example.com_LISTEN_STREAM_PORT="20000" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        -p 10000:10000/tcp \
        -p 20000:20000/tcp \
        bunkerity/bunkerweb-all-in-one:1.6.5-rc1
    ```

    Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    Vos applications (`myapp1`, `myapp2`) doivent s'exécuter dans des conteneurs séparés (ou être autrement accessibles) et leurs noms d'hôte/adresses IP (par ex. `myapp1`, `myapp2` utilisés dans `_REVERSE_PROXY_HOST`) doivent être résolubles et atteignables depuis le conteneur `bunkerweb-aio`. Cela implique généralement de les connecter à un réseau Docker partagé.

    !!! note "Désactiver le service UI"
        Il est recommandé de désactiver le service d'interface Web (par exemple en définissant la variable d'environnement `SERVICE_UI=no`) car l'interface Web n'est pas compatible avec `SERVER_TYPE=stream`.

=== "Docker"

    Lors de l'utilisation de l'intégration Docker, la manière la plus simple de protéger des applications réseau existantes est d'ajouter les services au réseau `bw-services` :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc1
        ports:
          - "80:8080" # Keep it if you want to use Let's Encrypt automation when using http challenge type
          - "10000:10000" # app1
          - "20000:20000" # app2
        labels:
          - "bunkerweb.INSTANCE=yes"
        environment:
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          USE_REVERSE_PROXY: "yes" # Will be applied to all services
          SERVER_TYPE: "stream" # Will be applied to all services
          app1.example.com_REVERSE_PROXY_HOST: "myapp1:9000"
          app1.example.com_LISTEN_STREAM_PORT: "10000"
          app2.example.com_REVERSE_PROXY_HOST: "myapp2:9000"
          app2.example.com_LISTEN_STREAM_PORT: "20000"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe

      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services

    volumes:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
    ```

=== "Docker autoconf"

    Avant d'exécuter la pile de l'intégration [Docker autoconf](integrations.md#docker-autoconf) sur votre machine, vous devrez modifier les ports :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc1
        ports:
          - "80:8080" # Keep it if you want to use Let's Encrypt automation when using http challenge type
          - "10000:10000" # app1
          - "20000:20000" # app2
    ...
    ```

    Une fois la pile en cours d'exécution, vous pouvez connecter vos applications existantes au réseau `bw-services` et configurer BunkerWeb avec des `labels` :

    ```yaml
    services:
      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        labels:
          - "bunkerweb.SERVER_NAME=app1.example.com"
          - "bunkerweb.SERVER_TYPE=stream"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        labels:
          - "bunkerweb.SERVER_NAME=app2.example.com"
          - "bunkerweb.SERVER_TYPE=stream"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    !!! example "Fonctionnalité expérimentale"

        Actuellement, les [Ingresses](https://kubernetes.io/docs/concepts/services-networking/ingress/) ne prennent pas en charge le mode `stream`. **Ce que nous proposons ici est une solution de contournement pour le faire fonctionner.**

        N'hésitez pas à le tester et à nous signaler tout bug en ouvrant une issue via [issues](https://github.com/bunkerity/bunkerweb/issues) du dépôt GitHub.

    Avant d'exécuter la pile de l'[intégration Kubernetes](integrations.md#kubernetes) sur votre machine, vous devrez ouvrir les ports sur votre équilibreur de charge :

    ```yaml
    apiVersion: v1
    kind: Service
    metadata:
      name: lb
    spec:
      type: LoadBalancer
      ports:
        - name: http # Keep it if you want to use Let's Encrypt automation when using http challenge type
          port: 80
          targetPort: 8080
        - name: app1
          port: 10000
          targetPort: 10000
        - name: app2
          port: 20000
          targetPort: 20000
      selector:
        app: bunkerweb
    ```

    Une fois la pile en cours d'exécution, vous pouvez créer vos ressources Ingress :

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      namespace: services
      annotations:
        bunkerweb.io/SERVER_TYPE: "stream" # Will be applied to all services
        bunkerweb.io/app1.example.com_LISTEN_STREAM_PORT: "10000"
        bunkerweb.io/app2.example.com_LISTEN_STREAM_PORT: "20000"
    spec:
      rules:
        - host: app1.example.com
          http:
            paths:
              - path: / # This isn't used in stream mode but is required
                pathType: Prefix
                backend:
                  service:
                    name: svc-app1
                    port:
                      number: 9000
        - host: app2.example.com
          http:
            paths:
              - path: / # This isn't used in stream mode but is required
                pathType: Prefix
                backend:
                  service:
                    name: svc-app2
                    port:
                      number: 9000
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app1
      namespace: services
      labels:
        app: app1
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: app1
      template:
        metadata:
          labels:
            app: app1
        spec:
          containers:
            - name: app1
              image: istio/tcp-echo-server:1.3
              args: ["9000", "app1"]
              ports:
                - containerPort: 9000
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app1
      namespace: services
    spec:
      selector:
        app: app1
      ports:
        - protocol: TCP
          port: 9000
          targetPort: 9000
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app2
      namespace: services
      labels:
        app: app2
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: app2
      template:
        metadata:
          labels:
            app: app2
        spec:
          containers:
            - name: app2
              image: istio/tcp-echo-server:1.3
              args: ["9000", "app2"]
              ports:
                - containerPort: 9000
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app2
      namespace: services
    spec:
      selector:
        app: app2
      ports:
        - protocol: TCP
          port: 9000
          targetPort: 9000
    ```

=== "Linux"

    Vous devrez ajouter ces paramètres au fichier /etc/bunkerweb/variables.env :

    ```conf
    ...
    SERVER_NAME=app1.example.com app2.example.com
    MULTISITE=yes
    USE_REVERSE_PROXY=yes
    SERVER_TYPE=stream
    app1.example.com_REVERSE_PROXY_HOST=myapp1.domain.or.ip:9000
    app1.example.com_LISTEN_STREAM_PORT=10000
    app2.example.com_REVERSE_PROXY_HOST=myapp2.domain.or.ip:9000
    app2.example.com_LISTEN_STREAM_PORT=20000
    ...
    ```

    Vérifions maintenant l'état du Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    S'ils sont déjà en cours d'exécution, nous pouvons le recharger :

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Sinon, nous devrons le démarrer :

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "Obsolète"
        L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

    Avant d'exécuter la pile de l'intégration [Swarm](integrations.md#swarm) sur votre machine, vous devrez modifier les ports :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc1
        ports:
          # Keep it if you want to use Let's Encrypt automation when using http challenge type
          - published: 80
            target: 8080
            mode: host
            protocol: tcp
          # app1
          - published: 10000
            target: 10000
            mode: host
            protocol: tcp
          # app2
          - published: 20000
            target: 20000
            mode: host
            protocol: tcp
    ...
    ```

    Une fois la pile en cours d'exécution, vous pouvez connecter vos applications existantes au réseau `bw-services` et configurer BunkerWeb à l'aide d'étiquettes :

    ```yaml
    services:

      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.SERVER_TYPE=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.SERVER_TYPE=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

### Le PHP

!!! example "Fonctionnalité expérimentale"
	  Pour le moment, le support PHP avec BunkerWeb est encore en version bêta et nous vous recommandons d'utiliser une architecture de proxy inverse si vous le pouvez. D'ailleurs, PHP n'est pas du tout pris en charge pour certaines intégrations comme Kubernetes.

BunkerWeb prend en charge PHP en utilisant des  instances [PHP-FPM externes ou ](https://www.php.net/manual/en/install.fpm.php) distantes. Nous supposerons que vous êtes déjà familiarisé avec la gestion de ce type de services.

 Les paramètres suivants peuvent être utilisés :

- `REMOTE_PHP` : Nom d'hôte de l'instance PHP-FPM distante.
- `REMOTE_PHP_PATH` : Dossier racine contenant les fichiers dans l'instance PHP-FPM distante.
- `REMOTE_PHP_PORT` : Port de l'instance PHP-FPM distante (*9000 par défaut*).
- `LOCAL_PHP` : Chemin d'accès au fichier socket local de l'instance PHP-FPM.
- `LOCAL_PHP_PATH` : Dossier racine contenant les fichiers dans l'instance locale PHP-FPM.

=== "Tout-en-un"

    Lorsque vous utilisez l'image [Tout-en-un](integrations.md#all-in-one-aio-image), pour prendre en charge les applications PHP, vous devrez :

    - Montez vos fichiers PHP dans le `/var/www/html` dossier de BunkerWeb.
    - Configurez un conteneur PHP-FPM pour votre application et montez le dossier contenant les fichiers PHP.
    - Utilisez les paramètres spécifiques `REMOTE_PHP` et `REMOTE_PHP_PATH` comme variables d'environnement lors de l'exécution de BunkerWeb.

    Si vous activez le [mode multisite](concepts.md#multisite-mode), vous devrez créer des répertoires distincts pour chacune de vos applications. Chaque sous-répertoire doit être nommé à l'aide de la première valeur de `SERVER_NAME`. Voici un exemple fictif :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    └── app2.example.com
        └── index.php

    2 directories, 2 files
    ```

    Nous supposerons que vos applications PHP se trouvent dans un dossier nommé `www`. Veuillez noter que vous devrez corriger les permissions pour que BunkerWeb (UID/GID 101) puisse au moins lire les fichiers et lister les dossiers et PHP-FPM (UID/GID 33 si vous utilisez l' `php:fpm` image) soit le propriétaire des fichiers et dossiers :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    Vous pouvez maintenant exécuter BunkerWeb, le configurer pour votre application PHP et également exécuter les applications PHP. Vous devrez créer un réseau Docker personnalisé pour permettre à BunkerWeb de communiquer avec vos conteneurs PHP-FPM.

    ```bash
    # Create a custom network
    docker network create php-network

    # Run PHP-FPM containers
    docker run -d --name myapp1-php --network php-network -v ./www/app1.example.com:/app php:fpm
    docker run -d --name myapp2-php --network php-network -v ./www/app2.example.com:/app php:fpm

    # Run BunkerWeb All-in-one
    docker run -d \
        --name bunkerweb-aio \
        --network php-network \
        -v ./www:/var/www/html \
        -v bw-storage:/data \
        -e SERVER_NAME="app1.example.com app2.example.com" \
        -e MULTISITE="yes" \
        -e REMOTE_PHP_PATH="/app" \
        -e app1.example.com_REMOTE_PHP="myapp1-php" \
        -e app2.example.com_REMOTE_PHP="myapp2-php" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.5-rc1
    ```

    Veuillez noter que si votre conteneur est déjà créé, vous devrez le supprimer et le recréer pour que les nouvelles variables d'environnement soient appliquées.

=== "Docker"

    Lors de l'utilisation de l'intégration [Docker](integrations.md#docker), pour prendre en charge les applications PHP, vous devrez :

    - Montez vos fichiers PHP dans le `/var/www/html` dossier de BunkerWeb
    - Configurez un conteneur PHP-FPM pour votre application et montez le dossier contenant les fichiers PHP
    - Utilisez les paramètres spécifiques `REMOTE_PHP` et `REMOTE_PHP_PATH` comme variables d'environnement lors du démarrage de BunkerWeb

    Si vous activez le [mode multisite](concepts.md#multisite-mode), vous devrez créer des répertoires distincts pour chacune de vos applications. Chaque sous-répertoire doit être nommé à l'aide de la première valeur de `SERVER_NAME`. Voici un exemple fictif :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    Nous supposerons que vos applications PHP se trouvent dans un dossier nommé `www`. Veuillez noter que vous devrez corriger les permissions pour que BunkerWeb (UID/GID 101) puisse au moins lire les fichiers et lister les dossiers et PHP-FPM (UID/GID 33 si vous utilisez l' `php:fpm` image) soit le propriétaire des fichiers et dossiers :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    Vous pouvez maintenant exécuter BunkerWeb, le configurer pour votre application PHP et également exécuter les applications PHP :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *bw-api-env
        volumes:
          - ./www:/var/www/html
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          REMOTE_PHP_PATH: "/app" # Will be applied to all services thanks to the MULTISITE setting
          app1.example.com_REMOTE_PHP: "myapp1"
          app2.example.com_REMOTE_PHP: "myapp2"
          app3.example.com_REMOTE_PHP: "myapp3"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe

      myapp1:
        image: php:fpm
        volumes:
          - ./www/app1.example.com:/app
        networks:
          - bw-services

      myapp2:
        image: php:fpm
        volumes:
          - ./www/app2.example.com:/app
        networks:
          - bw-services

      myapp3:
        image: php:fpm
        volumes:
          - ./www/app3.example.com:/app
        networks:
          - bw-services

    volumes:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
    ```

=== "Docker autoconf"

    !!! info "Mode multisite activé"
        L'intégration [Docker autoconf](integrations.md#docker-autoconf) implique l'utilisation du mode multisite : protéger une application PHP équivaut à protéger plusieurs.

    Lors de l'utilisation de l'intégration [Docker autoconf](integrations.md#docker-autoconf), pour prendre en charge les applications PHP, vous devrez :

    - Montez vos fichiers PHP dans le `/var/www/html` dossier de BunkerWeb
    - Configurez un conteneur PHP-FPM pour vos applications et montez le dossier contenant les applications PHP
    - Utilisez les paramètres spécifiques `REMOTE_PHP` et `REMOTE_PHP_PATH` comme étiquettes pour votre conteneur PHP-FPM

    Comme l'autoconf de Docker implique d'utiliser le [mode multisite](concepts.md#multisite-mode), vous devrez créer des répertoires distincts pour chacune de vos applications. Chaque sous-répertoire doit être nommé à l'aide de la première valeur de `SERVER_NAME`. Voici un exemple fictif :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    Une fois les dossiers créés, copiez vos fichiers et corrigez les permissions afin que BunkerWeb (UID/GID 101) puisse au moins lire les fichiers et lister les dossiers et PHP-FPM (UID/GID 33 si vous utilisez l' `php:fpm` image) soit le propriétaire des fichiers et dossiers :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    Lorsque vous démarrez la pile autoconf de BunkerWeb, montez le `www` dossier dans `/var/www/html` le  conteneur **Scheduler** :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      AUTOCONF_MODE: "yes"
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc1
        labels:
          - "bunkerweb.INSTANCE=yes"
        environment:
          <<: *bw-api-env
        volumes:
          - ./www:/var/www/html
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
          SERVER_NAME: "" # The server name will be filled with services labels
          MULTISITE: "yes" # Mandatory setting for autoconf
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.5-rc1
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          AUTOCONF_MODE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
          DOCKER_HOST: "tcp://bw-docker:2375" # The Docker socket
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        networks:
          - bw-docker

      bw-db:
        image: mariadb:11
        # We set the max allowed packet size to avoid issues with large queries
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-docker

    volumes:
      bw-data:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-docker:
        name: bw-docker
    ```

    Vous pouvez maintenant créer vos conteneurs PHP-FPM, monter les bons sous-dossiers et utiliser des libellés pour configurer BunkerWeb :

    ```yaml
    services:
      myapp1:
          image: php:fpm
          volumes:
            - ./www/app1.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp1
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.REMOTE_PHP=myapp1"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp2:
          image: php:fpm
          volumes:
            - ./www/app2.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp2
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.REMOTE_PHP=myapp2"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp3:
          image: php:fpm
          volumes:
            - ./www/app3.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp3
          labels:
            - "bunkerweb.SERVER_NAME=app3.example.com"
            - "bunkerweb.REMOTE_PHP=myapp3"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    !!! warning "PHP n'est pas pris en charge pour Kubernetes"
      L'intégration Kubernetes permet la configuration via [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) et le contrôleur BunkerWeb ne prend actuellement en charge que les applications HTTP.

=== "Linux"

    Nous supposerons que vous avez déjà la pile d'intégration [Linux integration](integrations.md#linux) en cours d'exécution sur votre machine.

    Par défaut, BunkerWeb recherchera les fichiers web dans le dossier /var/www/html. Vous pouvez l'utiliser pour stocker vos applications PHP. Veuillez noter que vous devrez configurer votre service PHP-FPM pour définir l'utilisateur/groupe des processus en cours et le fichier de socket UNIX utilisé pour communiquer avec BunkerWeb.

    Tout d'abord, assurez-vous que votre instance PHP-FPM peut accéder aux fichiers situés dans /var/www/html et que BunkerWeb peut accéder au fichier de socket UNIX afin de communiquer avec PHP-FPM. Il est recommandé d'utiliser un utilisateur distinct tel que www-data pour le service PHP-FPM et d'autoriser le groupe nginx à accéder au fichier de socket UNIX. Voici la configuration PHP-FPM correspondante :

    ```ini
    ...
    [www]
    user = www-data
    group = www-data
    listen = /run/php/php-fpm.sock
    listen.owner = www-data
    listen.group = nginx
    listen.mode = 0660
    ...
    ```

    N'oubliez pas de redémarrer votre service PHP-FPM :

    ```shell
    systemctl restart php-fpm
    ```

    Si vous activez le [mode multisite](concepts.md#multisite-mode), vous devrez créer des répertoires distincts pour chacune de vos applications. Chaque sous-répertoire doit être nommé en utilisant la première valeur de `SERVER_NAME`. Voici un exemple fictif :

    ```
    /var/www/html
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    Veuillez noter que vous devrez corriger les permissions afin que BunkerWeb (groupe `nginx`) puisse au moins lire les fichiers et lister les dossiers, et que PHP-FPM (utilisateur `www-data`, qui peut varier selon votre système) soit le propriétaire des fichiers et dossiers :

    ```shell
    chown -R www-data:nginx /var/www/html && \
    find /var/www/html -type f -exec chmod 0640 {} \; && \
    find /var/www/html -type d -exec chmod 0750 {} \;
    ```

    Vous pouvez maintenant éditer le fichier `/etc/bunkerweb/variable.env` :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4
    API_LISTEN_IP=127.0.0.1
    MULTISITE=yes
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app1.example.com_LOCAL_PHP_PATH=/var/www/html/app1.example.com
    app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app2.example.com_LOCAL_PHP_PATH=/var/www/html/app2.example.com
    app3.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app3.example.com_LOCAL_PHP_PATH=/var/www/html/app3.example.com
    ```

    Vérifions maintenant l'état du Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    S'il est déjà en cours d'exécution, nous pouvons le recharger :

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Sinon, nous devrons le démarrer :

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "Obsolète"
        L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

    !!! info "Mode multisite activé"
        L'intégration [Swarm](integrations.md#docker-autoconf) implique l'utilisation du mode multisite : protéger une application PHP équivaut à protéger plusieurs applications.

    !!! info "Volume partagé"
        L'utilisation de PHP avec l'intégration Docker Swarm nécessite un volume partagé entre toutes les instances BunkerWeb et PHP-FPM, ce qui n'est pas couvert dans cette documentation.

    Lors de l'utilisation de l'intégration [Swarm](integrations.md#swarm), pour prendre en charge les applications PHP, vous devrez :

    - Montez vos fichiers PHP dans le `/var/www/html` dossier de BunkerWeb
    - Configurez un conteneur PHP-FPM pour vos applications et montez le dossier contenant les applications PHP
    - Utilisez les paramètres spécifiques `REMOTE_PHP` et `REMOTE_PHP_PATH` comme étiquettes pour votre conteneur PHP-FPM

    Étant donné que l'intégration de Swarm implique l'utilisation du [mode multisite](concepts.md#multisite-mode), vous devrez créer des répertoires distincts pour chacune de vos applications. Chaque sous-répertoire doit être nommé à l'aide de la première valeur de `SERVER_NAME`. Voici un exemple fictif :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    À titre d'exemple, nous considérerons que vous avez un dossier partagé monté sur vos nœuds de travail sur le point de `/shared` terminaison.

    Une fois les dossiers créés, copiez vos fichiers et corrigez les permissions afin que BunkerWeb (UID/GID 101) puisse au moins lire les fichiers et lister les dossiers et PHP-FPM (UID/GID 33 si vous utilisez l' `php:fpm` image) soit le propriétaire des fichiers et dossiers :

    ```shell
    chown -R 33:101 /shared/www && \
    find /shared/www -type f -exec chmod 0640 {} \; && \
    find /shared/www -type d -exec chmod 0750 {} \;
    ```

    Lorsque vous démarrez la pile BunkerWeb, montez le dossier /shared/www sur /var/www/html dans le conteneur **Scheduler** :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc1
        volumes:
          - /shared/www:/var/www/html
    ...
    ```

    Vous pouvez maintenant créer vos services PHP-FPM, monter les sous-dossiers appropriés et utiliser des labels pour configurer BunkerWeb :

    ```yaml
    services:
      myapp1:
          image: php:fpm
          volumes:
            - ./www/app1.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp1
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app1.example.com"
              - "bunkerweb.REMOTE_PHP=myapp1"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp2:
          image: php:fpm
          volumes:
            - ./www/app2.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp2
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app2.example.com"
              - "bunkerweb.REMOTE_PHP=myapp2"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp3:
          image: php:fpm
          volumes:
            - ./www/app3.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp3
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app3.example.com"
              - "bunkerweb.REMOTE_PHP=myapp3"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

### IPv6

!!! example "Fonctionnalité expérimentale"

    Cette fonctionnalité n'est pas prête pour la production. N'hésitez pas à la tester et à nous signaler tout bug via les [issues](https://github.com/bunkerity/bunkerweb/issues) du dépôt GitHub.

Par défaut, BunkerWeb n'écoutera que les adresses IPv4 et n'utilisera pas IPv6 pour les communications réseau. Si vous souhaitez activer la prise en charge d'IPv6, vous devez définir `USE_IPV6=yes`. Veuillez noter que la configuration IPv6 de votre réseau et de votre environnement n'entre pas dans le champ d'application de cette documentation.

=== "Docker / Autoconf / Swarm"

    Tout d'abord, vous devrez configurer le démon Docker pour activer la prise en charge d'IPv6 pour les conteneurs et utiliser ip6tables si nécessaire. Voici une configuration d'exemple pour votre fichier /etc/docker/daemon.json :

    ```json
    {
      "experimental": true,
      "ipv6": true,
      "ip6tables": true,
      "fixed-cidr-v6": "fd00:dead:beef::/48"
    }
    ```

    Vous pouvez maintenant redémarrer le service Docker pour appliquer les modifications :

    ```shell
    systemctl restart docker
    ```

    Une fois Docker configuré pour prendre en charge IPv6, vous pouvez ajouter le paramètre `USE_IPV6` et configurer le réseau bw-services pour IPv6 :

    ```yaml
    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc1
        environment:
          USE_IPv6: "yes"

    ...

    networks:
      bw-services:
        name: bw-services
        enable_ipv6: true
        ipam:
          config:
            - subnet: fd00:13:37::/48
              gateway: fd00:13:37::1

    ...
    ```

=== "Linux"

    Vous devrez ajouter ces paramètres au fichier /etc/bunkerweb/variables.env :

    ```conf
    ...
    USE_IPV6=yes
    ...
    ```

    Vérifions maintenant l'état de BunkerWeb :

    ```shell
    systemctl status bunkerweb
    ```

    S'il est déjà en cours d'exécution, nous pouvons le redémarrer :

    ```shell
    systemctl restart bunkerweb
    ```

    Sinon, nous devrons le démarrer :

    ```shell
    systemctl start bunkerweb
    ```

## Réglage de la sécurité

BunkerWeb offre de nombreuses fonctionnalités de sécurité que vous pouvez configurer avec les [fonctionnalités](features.md). Même si les valeurs par défaut des paramètres assurent une "sécurité par défaut" minimale, nous vous recommandons vivement de les régler. Ce faisant, vous serez en mesure de vous assurer du niveau de sécurité de votre choix, mais aussi de gérer les faux positifs.

!!! tip "Autres fonctionnalités"
    Cette section se concentre uniquement sur le réglage de la sécurité, voir la section [fonctionnalités](features.md) de la documentation pour d'autres paramètres.

<figure markdown>
  ![Vue d'ensemble](assets/img/core-order.svg){ align=center }
  <figcaption>Vue d'ensemble et ordre des plugins de sécurité de base</figcaption>
</figure>

## Intégration de la console CrowdSec

Si vous n'êtes pas déjà familier avec l'intégration de la console CrowdSec, [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) exploite l'intelligence participative pour lutter contre les cybermenaces. Considérez-le comme le "Waze de la cybersécurité" : lorsqu'un serveur est attaqué, les autres systèmes du monde entier sont alertés et protégés contre les mêmes attaquants. Vous pouvez en savoir plus à ce sujet [ici](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

**Félicitations, votre instance BunkerWeb est maintenant inscrite dans votre console CrowdSec !**

Conseil professionnel : Lorsque vous consultez vos alertes, cliquez sur l'option "colonnes" et cochez la case "contexte" pour accéder aux données spécifiques à BunkerWeb.

<figure markdown>
  ![Vue d'ensemble](assets/img/crowdity4.png){ align=center }
  <figcaption>Données BunkerWeb affichées dans la colonne de contexte</figcaption>
</figure>

## Surveillance et rapports

#### Monitoring <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge de STREAM :x:

Le plugin de surveillance vous permet de collecter et de récupérer des métriques sur BunkerWeb. En l'activant, votre ou vos instances commenceront à collecter diverses données liées aux attaques, aux requêtes et aux performances. Vous pouvez ensuite les récupérer en appelant régulièrement le point de terminaison de l' `/monitoring` API ou en utilisant d'autres plugins comme celui de l'exportateur Prometheus.

**Liste des fonctionnalités**

- Permettre la collecte de diverses métriques BunkerWeb
- Récupérer des métriques à partir de l'API
- Utilisation en combinaison avec d'autres plugins (par exemple Prometheus exporter)
- Dédiée à la page d'interface utilisateur pour surveiller vos instances

**Liste des paramètres**

| Réglage                        | Défaut | Contexte | Multiple | Description                                                        |
| ------------------------------ | ------ | -------- | -------- | ------------------------------------------------------------------ |
| `USE_MONITORING`               | `yes`  | global   | Non      | Activez la surveillance de BunkerWeb.                              |
| `MONITORING_METRICS_DICT_SIZE` | `10M`  | global   | Non      | Taille du dictionnaire pour stocker les métriques de surveillance. |

#### Prometheus exporter <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge de STREAM :x:

Le plugin d'exportation Prometheus ajoute un [exportateur Prometheus](https://prometheus.io/docs/instrumenting/exporters/) sur votre ou vos instances BunkerWeb. Lorsqu'elle est activée, vous pouvez configurer votre ou vos instances Prometheus pour récupérer un point de terminaison spécifique sur Bunkerweb et collecter des métriques internes.

Nous fournissons également un [tableau de bord Grafana](https://grafana.com/grafana/dashboards/20755-bunkerweb/) que vous pouvez importer dans votre propre instance et connecter à votre propre source de données Prometheus.

**Veuillez noter que l'utilisation du plugin d'exportation Prometheus nécessite d'activer le plugin de surveillance (`USE_MONITORING=yes`)**

**Liste des fonctionnalités**

- L'exportateur Prometheus fournit des métriques internes à BunkerWeb
- Port dédié et configurable, IP et URL d'écoute
- Liste blanche IP/réseau pour une sécurité maximale

**Liste des paramètres**

| Réglage                        | Ddéfaut                                               | Contexte | Multiple | Description                                                                                              |
| ------------------------------ | ----------------------------------------------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------- |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | global   | Non      | Activez l'exportation Prometheus.                                                                        |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | global   | Non      | IP d'écoute de l'exportateur Prometheus.                                                                 |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | global   | Non      | Port d'écoute de l'exportateur Prometheus.                                                               |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | global   | Non      | URL HTTP de l'exportateur Prometheus.                                                                    |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | global   | Non      | Liste des adresses IP/réseaux autorisés à contacter le point de terminaison de l'exportateur Prometheus. |

#### Reporting <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge de STREAM :x:

!!! warning "Plugin de surveillance nécessaire"
    Ce plug-in nécessite l'installation et l'activation du plug-in Monitoring Pro avec le `USE_MONITORING` paramètre défini sur `yes`.

Le plugin Reporting fournit une solution complète pour la communication régulière de données importantes de BunkerWeb, y compris les statistiques mondiales, les attaques, les bannissements, les demandes, les raisons et les informations AS. Il offre un large éventail de fonctionnalités, notamment la création automatique de rapports, des options de personnalisation et une intégration transparente avec le plugin monitoring pro. Avec le plugin Reporting, vous pouvez facilement générer et gérer des rapports pour surveiller les performances et la sécurité de votre application.

**Liste des fonctionnalités**

- Rapports réguliers sur les données importantes de BunkerWeb, y compris les statistiques mondiales, les attaques, les bannissements, les demandes, les raisons et les informations sur les SA.
- Intégration avec le plug-in Monitoring Pro pour une intégration transparente et des capacités de reporting améliorées.
- Prise en charge des webhooks (classique, Discord et Slack) pour les notifications en temps réel.
- Prise en charge de SMTP pour les notifications par e-mail.
- Options de configuration pour plus de personnalisation et de flexibilité.

**Liste des paramètres**

| Réglage                        | Faire défaut       | Contexte | Description                                                                                                                     |
| ------------------------------ | ------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | global   | Activez l'envoi du rapport par e-mail.                                                                                          |
| `USE_REPORTING_WEBHOOK`        | `no`               | global   | Activez l'envoi du rapport via le webhook.                                                                                      |
| `REPORTING_SCHEDULE`           | `weekly`           | global   | La fréquence à laquelle les rapports sont envoyés.                                                                              |
| `REPORTING_WEBHOOK_URLS`       |                    | global   | Liste des URL de webhook pour recevoir le rapport en Markdown (séparées par des espaces).                                       |
| `REPORTING_SMTP_EMAILS`        |                    | global   | Liste des adresses e-mail pour recevoir le rapport au format HTML (séparées par des espaces).                                   |
| `REPORTING_SMTP_HOST`          |                    | global   | Serveur hôte utilisé pour l'envoi SMTP.                                                                                         |
| `REPORTING_SMTP_PORT`          | `465`              | global   | Port utilisé pour SMTP. Veuillez noter qu'il existe différentes normes en fonction du type de connexion (SSL = 465, TLS = 587). |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | global   | L'adresse e-mail utilisée comme expéditeur. Notez que 2FA doit être désactivé pour cette adresse e-mail.                        |
| `REPORTING_SMTP_FROM_USER`     |                    | global   | Valeur d'authentification de l'utilisateur pour l'envoi via l'adresse e-mail de l'expéditeur.                                   |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | global   | La valeur d'authentification par mot de passe pour l'envoi via l'adresse e-mail de l'expéditeur.                                |
| `REPORTING_SMTP_SSL`           | `SSL`              | global   | Déterminez s'il faut ou non utiliser une connexion sécurisée pour SMTP.                                                         |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | global   | La ligne d'objet de l'e-mail.                                                                                                   |

!!! info "Information et comportement"
    - cas `USE_REPORTING_SMTP` est défini sur `yes`, le paramètre `REPORTING_SMTP_EMAILS` doit être défini.
    - cas `USE_REPORTING_WEBHOOK` est défini sur `yes`, le paramètre `REPORTING_WEBHOOK_URLS` doit être défini.
    - Les valeurs acceptées pour `REPORTING_SCHEDULE` sont `daily`, `weekly` et `monthly`.
    - cas aucun `REPORTING_SMTP_FROM_USER` et `REPORTING_SMTP_FROM_PASSWORD` ne sont définis, le plugin essaiera d'envoyer l'e-mail sans authentification.
    - cas `REPORTING_SMTP_FROM_USER` n'est pas défini mais `REPORTING_SMTP_FROM_PASSWORD` est défini, le plugin utilisera le `REPORTING_SMTP_FROM_EMAIL` comme nom d'utilisateur.
    - En cas d'échec du travail, le plug-in réessaiera d'envoyer le rapport lors de la prochaine exécution.

### Sauvegarde et restauration

#### Backup S3 <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge STREAM :white_check_mark:

L'outil Backup S3 automatise de manière transparente la protection des données, à l'instar du plug-in de sauvegarde communautaire. Cependant, il se distingue par le stockage sécurisé des sauvegardes directement dans un compartiment S3.

En activant cette fonctionnalité, vous protégez de manière proactive **l'intégrité de vos données**. Le stockage à **distance** des sauvegardes protège les informations cruciales contre les menaces telles que ** les pannes matérielles**, **les cyberattaques** ou **les catastrophes naturelles**. Cela garantit à la fois **la sécurité** et **la disponibilité**, ce qui permet une récupération rapide en cas ** d'événements inattendus**, préservant la **continuité opérationnelle** et garantissant **la tranquillité d'esprit**.

??? warning "Informations pour les utilisateurs de Red Hat Enterprise Linux (RHEL) 8.9"
    Si vous utilisez **RHEL 8.9** et que vous prévoyez d'utiliser une **base de données externe**, vous devez installer le `mysql-community-client` package pour vous assurer que la `mysqldump` commande est disponible. Vous pouvez installer le package en exécutant les commandes suivantes :

    === "MySQL/MariaDB"

        1. **Installez le paquet de configuration du dépôt MySQL**

          ```bash
          sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
          ```

        2. **Activez le dépôt MySQL**

          ```bash
          sudo dnf config-manager --enable mysql80-community
          ```

        3. **Installez le client MySQL**

          ```bash
          sudo dnf install mysql-community-client
          ```

    === "PostgreSQL"

        1. **Installez le paquet de configuration du dépôt PostgreSQL**

          ```bash
          dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
          ```

        2. **Installez le client PostgreSQL**

          ```bash
          dnf install postgresql<version>
          ```

**Liste des fonctionnalités**

- Sauvegarde automatique des données dans un compartiment S3
- Options de planification flexibles : quotidienne, hebdomadaire ou mensuelle
- Gestion de la rotation pour contrôler le nombre de sauvegardes à conserver
- Niveau de compression personnalisable pour les fichiers de sauvegarde

**Liste des paramètres**

| Réglage                       | Faire défaut | Contexte | Description                                           |
| ----------------------------- | ------------ | -------- | ----------------------------------------------------- |
| `USE_BACKUP_S3`               | `no`         | global   | Activer ou désactiver la fonction de sauvegarde S3    |
| `BACKUP_S3_SCHEDULE`          | `daily`      | global   | La fréquence de la sauvegarde                         |
| `BACKUP_S3_ROTATION`          | `7`          | global   | Le nombre de sauvegardes à conserver                  |
| `BACKUP_S3_ENDPOINT`          |              | global   | Le point de terminaison S3                            |
| `BACKUP_S3_BUCKET`            |              | global   | Le godet S3                                           |
| `BACKUP_S3_DIR`               |              | global   | L'annuaire S3                                         |
| `BACKUP_S3_REGION`            |              | global   | La région S3                                          |
| `BACKUP_S3_ACCESS_KEY_ID`     |              | global   | L'ID de la clé d'accès S3                             |
| `BACKUP_S3_ACCESS_KEY_SECRET` |              | global   | Le secret de la clé d'accès S3                        |
| `BACKUP_S3_COMP_LEVEL`        | `6`          | global   | Le niveau de compression du fichier zip de sauvegarde |

##### Sauvegarde manuelle

Pour lancer manuellement une sauvegarde, exécutez la commande suivante :

=== "Linux"

    ```bash
    bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 save
    ```

Cette commande crée une sauvegarde de votre base de données et la stocke dans le compartiment S3 spécifié dans le `BACKUP_S3_BUCKET` paramètre.

Vous pouvez également spécifier un compartiment S3 personnalisé pour la sauvegarde en fournissant la variable d' `BACKUP_S3_BUCKET` environnement lors de l'exécution de la commande :

=== "Linux"

    ```bash
    BACKUP_S3_BUCKET=your-bucket-name bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it -e BACKUP_S3_BUCKET=your-bucket-name <scheduler_container> bwcli plugin backup_s3 save
    ```

!!! note "Spécifications pour MariaDB/MySQL"

    Si vous utilisez MariaDB/MySQL, vous pouvez rencontrer l'erreur suivante lors de la sauvegarde de votre base de données :

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    Pour résoudre ce problème, vous pouvez exécuter la commande suivante pour changer le plugin d'authentification en `mysql_native_password` :

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    Si vous utilisez l'intégration Docker, vous pouvez ajouter la commande suivante au fichier `docker-compose.yml` pour changer automatiquement le plugin d'authentification :

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

##### Restauration manuelle

Pour lancer manuellement une restauration, exécutez la commande suivante :

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
    ```

Cette commande crée une sauvegarde temporaire de votre base de données dans le compartiment S3 spécifié dans le `BACKUP_S3_BUCKET` paramètre et restaure votre base de données à la dernière sauvegarde disponible dans le compartiment.

Vous pouvez également spécifier un fichier de sauvegarde personnalisé pour la restauration en fournissant le chemin d'accès à celui-ci en tant qu'argument lors de l'exécution de la commande :

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore s3_backup_file.zip
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup restore s3_backup_file.zip
    ```

!!! example "En cas de panne"

    Don't worry if the restore fails, you can always restore your database to the previous state by executing the command again as a backup is created before the restore:

    === "Linux"

        ```bash
        bwcli plugin backup_s3 restore
        ```

    === "Docker"

        ```bash
        docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
        ```

### Migration <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge STREAM :white_check_mark:

Le plug-in de migration **révolutionne les transferts de** configuration BunkerWeb entre les instances grâce à son **interface Web conviviale**, simplifiant ainsi l'ensemble du parcours de migration. Que vous mettiez à niveau des systèmes, que vous fassiez évoluer une infrastructure ou que vous transformiez d'environnement, cet outil vous permet de transférer sans effort les **paramètres, les préférences et les données** avec une facilité et une confiance inégalées. Dites adieu aux processus manuels fastidieux et bonjour à une expérience de **migration transparente et sans tracas**.

**Liste des fonctionnalités**

- **Migration sans effort :** Transférez facilement les configurations BunkerWeb entre les instances sans les complexités des procédures manuelles.

- **Interface Web intuitive :** Naviguez sans effort dans le processus de migration grâce à une interface Web conviviale conçue pour un fonctionnement intuitif.

- **Compatibilité entre bases de données :** profitez d'une migration transparente sur diverses plates-formes de bases de données, notamment SQLite, MySQL, MariaDB et PostgreSQL, garantissant la compatibilité avec votre environnement de base de données préféré.

#### Créer un fichier de migration

Pour créer manuellement un fichier de migration, exécutez la commande suivante :

=== "Linux"

    ```bash
    bwcli plugin migration create /path/to/migration/file
    ```

=== "Docker"

    1. Créez un fichier de migration :

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration create /path/to/migration/file
        ```

    2. Copiez le fichier de migration sur votre ordinateur local :

        ```bash
        docker cp <scheduler_container>:/path/to/migration/file /path/to/migration/file
        ```

Cette commande créera une sauvegarde de votre base de données et la stockera dans le répertoire de sauvegarde spécifié dans la commande.

!!! note "Spécifications pour MariaDB/MySQL"

    Si vous utilisez MariaDB/MySQL, vous pouvez rencontrer l'erreur suivante lors de la sauvegarde de votre base de données :

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    Pour résoudre ce problème, vous pouvez exécuter la commande suivante pour changer le plugin d'authentification en `mysql_native_password` :

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    Si vous utilisez l'intégration Docker, vous pouvez ajouter la commande suivante au fichier `docker-compose.yml` pour changer automatiquement le plugin d'authentification :

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

#### Initialiser une migration

Pour initialiser manuellement une migration, exécutez la commande suivante :

=== "Linux"

    ```bash
    bwcli plugin migration migrate /path/to/migration/file
    ```

=== "Docker"

    1. Copiez le fichier de migration dans le conteneur :

        ```bash
        docker cp /path/to/migration/file <scheduler_container>:/path/to/migration/file
        ```

    2. Initialisez la migration :

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration migrate /path/to/migration/file
        ```

=== "Tout-en-un"

    1. Copiez le fichier de migration dans le conteneur :

        ```bash
        docker cp /path/to/migration/file bunkerweb-aio:/path/to/migration/file
        ```

    2. Initialisez la migration :

        ```bash
        docker exec -it bunkerweb-aio bwcli plugin migration migrate /path/to/migration/file
        ```

Cette commande migre de manière transparente vos données BunkerWeb pour qu'elles correspondent précisément à la configuration décrite dans le fichier de migration.

## Anti DDoS <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge de STREAM :x:

Le  plug-in **anti-DDoS** offre une protection avancée contre les attaques par déni de service distribué (DDoS) en surveillant, analysant et filtrant le trafic suspect en temps réel.

En utilisant un mécanisme de **fenêtre glissante**, le plugin maintient un dictionnaire en mémoire des horodatages des requêtes pour détecter les pics de trafic anormaux à partir d'adresses IP individuelles. En fonction du mode de sécurité configuré, il peut soit bloquer les connexions incriminées, soit consigner l'activité suspecte pour un examen plus approfondi.

#### Fonctionnalités

- **Analyse du trafic en temps réel :** surveille en permanence les demandes entrantes pour détecter les attaques DDoS potentielles.
- **Mécanisme de fenêtre glissante :** suit l'activité récente des demandes dans une fenêtre de temps configurable.
- **Seuils configurables :** vous permet de définir le nombre maximum de requêtes suspectes par IP.
- **Logique de blocage avancée :** évalue à la fois le nombre de requêtes par IP et le nombre d'adresses IP distinctes dépassant le seuil.
- **Modes de sécurité flexibles :** choisissez entre le blocage immédiat de la connexion ou le mode de détection uniquement (journalisation).
- **Magasin de données en mémoire optimisé :** Garantit des recherches à grande vitesse et un suivi efficace des métriques.
- **Entretien ménager automatique :** efface périodiquement les données obsolètes pour maintenir des performances optimales.

#### Configuration

Personnalisez le comportement du plug-in à l'aide des paramètres suivants :

| Réglage                      | Faire défaut  | Contexte | Multiple | Description                                                                                                 |
| ---------------------------- | ------------- | -------- | -------- | ----------------------------------------------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`          | global   | Non      | Activez ou désactivez la protection anti-DDoS. Réglez sur `"yes"` pour activer le plugin.                   |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`         | global   | Non      | Taille de la banque de données en mémoire pour le suivi des métriques DDoS (par exemple, `10M`, `500k`).    |
| `ANTIDDOS_THRESHOLD`         | `100`         | global   | Non      | Nombre maximum de requêtes suspectes autorisées par IP dans la fenêtre de temps définie.                    |
| `ANTIDDOS_WINDOW_TIME`       | `10`          | global   | Non      | Fenêtre de temps en secondes pendant laquelle les demandes suspectes sont comptabilisées.                   |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444` | global   | Non      | Codes d'état HTTP considérés comme suspects et utilisés pour déclencher des actions anti-DDoS.              |
| `ANTIDDOS_DISTINCT_IP`       | `5`           | global   | Non      | Nombre minimum d'adresses IP distinctes qui doivent dépasser le seuil avant d'appliquer le mode de blocage. |

#### Bonnes pratiques

- **Réglage du seuil :** ajustez `ANTIDDOS_THRESHOLD` et `ANTIDDOS_WINDOW_TIME` en fonction de vos modèles de trafic typiques.
- **Révision du code d'état :** mettez régulièrement à jour `ANTIDDOS_STATUS_CODES` pour capturer les comportements suspects nouveaux ou en évolution.
- **Surveillance :** analysez régulièrement les journaux et les métriques pour affiner les paramètres et améliorer la protection globale.

## Gestionnaire d'utilisateurs <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Le plug-in de gestion des utilisateurs offre une interface robuste pour l'administration des comptes d'utilisateurs au sein de votre système.

Avec ce plugin, les administrateurs peuvent sans effort créer, mettre à jour et désactiver des comptes utilisateurs, gérer les rôles des utilisateurs, basculer l'authentification à deux facteurs (2FA) et afficher des informations détaillées sur les utilisateurs telles que les horodatages de la dernière connexion et les statuts des comptes (actif ou inactif). Conçu dans un souci de sécurité et de facilité d'utilisation, ce plug-in simplifie les tâches de gestion des utilisateurs tout en garantissant la conformité et l'auditabilité.

#### Fonctionnalités

- **Opérations de compte d'utilisateur :** importez au format CSV/XSLX, créez, modifiez et supprimez des comptes d'utilisateur en toute simplicité.
- **Contrôle d'accès basé sur les rôles :** Attribuez et modifiez les rôles d'utilisateur pour gérer les autorisations et les niveaux d'accès.
- **Gestion 2FA :** désactivez l'authentification à deux facteurs en fonction des décisions administratives.
- **Informations complètes sur les utilisateurs :** surveillez les données clés des utilisateurs, notamment les heures de dernière connexion, les dates de création de compte et le statut actif/inactif.
- **Journalisation des audits :** conservez une piste d'audit pour toutes les actions de gestion des utilisateurs afin d'améliorer la sécurité et la conformité.

<figure markdown>
  ![Vue d'ensemble](assets/img/user-manager.png){ align=center }
  <figcaption>Page Gestionnaire d'utilisateurs</figcaption>
</figure>

<figure markdown>
  ![Créer un formulaire utilisateur](assets/img/user-manager-create.png){ align=center }
  <figcaption>Gestionnaire d'utilisateurs - Créer un formulaire d'utilisateur</figcaption>
</figure>

<figure markdown>
  ![Page d'activités](assets/img/user-manager-activities.png){ align=center }
  <figcaption>Gestionnaire d'utilisateurs - Page Activités</figcaption>
</figure>
