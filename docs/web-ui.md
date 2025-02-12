# Web UI

## Overview

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/tGS3pzquEjY" title="BunkerWeb web UI" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

The "Web UI" is a web application that helps you manage your BunkerWeb instance using a user-friendly interface instead of the command-line one.

Here is the list of features offered by the web UI :

- Get a comprehensive view of the blocked attacks
- Start, stop, restart and reload your BunkerWeb instance
- Add, edit and delete settings for your web applications
- Add, edit and delete custom configurations for NGINX and ModSecurity
- Install and uninstall external plugins
- Explore the cached files
- Monitor jobs execution and restart them when needed
- View the logs and search pattern

## Prerequisites

Because the web UI is a web application, the recommended architecture is to use BunkerWeb in front of it as a reverse proxy. The recommended installation procedure is to use the setup wizard, which will guide you step by step as described in the [quickstart guide](quickstart-guide.md) section of the documentation.

!!! warning "Security considerations"

    The security of the web UI is really important. If someone manages to gain access to the application, not only he will be able to edit your configurations but he could execute some code in the context of BunkerWeb (with a custom configuration containing LUA code for example). We highly recommend you to follow minimal security best practices like :

    * Choose a strong password for the login (**at least 8 chars with 1 lower case letter, 1 upper case letter, 1 digit and 1 special char is required**)
    * Put the web UI under a "hard to guess" URI
    * Enable two-factor authentication (2FA)
    * Do not open the web UI on the Internet without any further restrictions
    * Apply best practices listed in the [advanced usages section](advanced.md#security-tuning) of the documentation depending on your use case

## Upgrade to PRO

!!! info "What is BunkerWeb PRO ?"
    BunkerWeb PRO is an enhanced version of BunkerWeb open-source. Whether it's enhanced security, an enriched user experience, or technical monitoring, the BunkerWeb PRO version will allow you to fully benefit from BunkerWeb and respond to your professional needs. Do not hesitate to visit the [BunkerWeb panel](https://panel.bunkerweb.io/knowledgebase?utm_campaign=self&utm_source=doc) or [contact us](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) if you have any question regarding the PRO version.

Once you have your PRO license key from the [BunkerWeb panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc), you can paste it into the PRO page of the web UI.

<figure markdown>
  ![PRO upgrade](assets/img/pro-ui-upgrade.png){ align=center, width="700" }
  <figcaption>Upgrade to PRO from the web UI</figcaption>
</figure>

!!! warning "Upgrade time"
    The PRO version is downloaded in the background by the scheduler, it may take some time to upgrade.

When your BunkerWeb instance has upgraded to the PRO version, you will see your license expiration date and the maximum number of services you can protect.

<figure markdown>
  ![PRO upgrade](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>PRO license information</figcaption>
</figure>

<!-- ## Setup wizard

!!! info "Wizard"

    The setup wizard is a feature that helps you to **configure** and **install the web UI** using a **user-friendly interface**. You will need to set the `UI_HOST` setting (`http://hostname-of-web-ui:7000`) and browse the `/setup` URI of your server to access the setup wizard.

<figure markdown>
  ![Overview](assets/img/ui-wizard-account.webp){ align=center, width="350" }
  <figcaption>Account section of the setup wizard</figcaption>
</figure>

Choose your administrator username and password. Please note that password must have at least 8 chars with 1 lower case letter, 1 upper case letter, 1 digit and 1 special char.

<figure markdown>
  ![Overview](assets/img/ui-wizard-settings.webp){ align=center, width="350" }
  <figcaption>Settings section of the setup wizard</figcaption>
</figure>

Configure the following settings :

- `UI Host` : internal http endpoint of your web UI
- `UI URL` : the public path where your web UI will be accessible
- `Server name` : the public server name where your web UI will be accessible
- `Auto let's encrypt` : enable/disable HTTPS using automated let's encrypt

Please note that your server name must have a valid DNS entry pointing to your BunkerWeb instance (or load balancer if you use Swarm/Kubernetes). You can check the DNS validity by clicking the `Check` button.

Review your final BunkerWeb UI URL and then click on the `Setup` button. Once the setup is finished, you will be redirected to your web UI login page.

=== "Docker"

    If you want to use the setup wizard, you will need to set the `UI_HOST` setting to the HTTP endpoint of your web UI container. For example, if your web UI container is named `bw-ui` and is listening on the `7000` port, you will need to set the `UI_HOST` setting to `http://bw-ui:7000`.

    !!! tip "Accessing the setup wizard"

        You can access the setup wizard by browsing the `https://your-ip-address-or-fqdn/setup` URI of your server.


    Here is the docker-compose boilerplate that you can use (don't forget to edit the `changeme` data) :

    ```yaml
    x-ui-env: &bw-ui-env
      # We anchor the environment variables to avoid duplication
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc4
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        environment:
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc4
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: ""
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # We mirror the API_WHITELIST_IP from the bunkerweb service
          UI_HOST: "http://bw-ui:7000" # Change it if needed
        volumes:
          - bw-data:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.0-rc4
        environment:
          <<: *bw-ui-env
          TOTP_SECRETS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-db:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

    volumes:
      bw-data:
      bw-db:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker autoconf"

    If you want to use the setup wizard, you will need to set the `UI_HOST` setting to the HTTP endpoint of your web UI container. For example, if your web UI container is named `bw-ui` and is listening on the `7000` port, you will need to set the `UI_HOST` setting to `http://bw-ui:7000`.

    !!! tip "Accessing the setup wizard"

        You can access the setup wizard by browsing the `https://your-ip-address-or-fqdn/setup` URI of your server.

    Here is the docker-compose boilerplate that you can use (don't forget to edit the `changeme` data) :

    ```yaml
    x-ui-env: &bw-ui-env
      # We anchor the environment variables to avoid duplication
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc4
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        labels:
          - "bunkerweb.INSTANCE=yes" # We set the instance label to allow the autoconf to detect the instance
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc4
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # Change it if needed
        volumes:
          - bw-data:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.0-rc4
        depends_on:
          - bw-docker
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.0-rc4
        environment:
          <<: *bw-ui-env
          TOTP_SECRETS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-db:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

    volumes:
      bw-data:
      bw-db:

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
      bw-db:
        name: bw-db
    ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_1_2) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    If you want to use the setup wizard, you will need to set the `UI_HOST` setting to the HTTP endpoint of your web UI container. For example, if your web UI container is named `bw-ui` and is listening on the `7000` port, you will need to set the `UI_HOST` setting to `http://bw-ui:7000`.

    !!! tip "Accessing the setup wizard"

        You can access the setup wizard by browsing the `https://your-ip-address-or-fqdn/setup` URI of your server.

    Here is the stack boilerplate that you can use (don't forget to edit the `changeme` data) :

    ```yaml
    x-ui-env: &bw-ui-env
      # We anchor the environment variables to avoid duplication
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc4
        ports:
          - published: 80
            target: 8080
            mode: host
            protocol: tcp
          - published: 443
            target: 8443
            mode: host
            protocol: tcp
          - published: 443
            target: 8443
            mode: host
            protocol: udp # For QUIC / HTTP3 support
        environment:
          SWARM_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        deploy:
          mode: global
          placement:
            constraints:
              - "node.role == worker"
          labels:
            - "bunkerweb.INSTANCE=yes"

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc4
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "bw-redis"
          UI_HOST: "http://bw-ui:7000" # Change it if needed
        volumes:
          - bw-data:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.0-rc4
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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
          CONFIGS: "1"
          CONTAINERS: "1"
          SERVICES: "1"
          SWARM: "1"
          TASKS: "1"
          LOG_LEVEL: "warning"
        networks:
          - bw-docker
        deploy:
          placement:
            constraints:
              - "node.role == manager"

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.0-rc4
        environment:
          <<: *bw-ui-env
          TOTP_SECRETS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-db:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      bw-redis:
        image: redis:7-alpine
        networks:
          - bw-universe

    volumes:
      bw-db:
      bw-data:

    networks:
      bw-universe:
        name: bw-universe
        driver: overlay
        attachable: true
        ipam:
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
        driver: overlay
        attachable: true
      bw-docker:
        name: bw-docker
        driver: overlay
        attachable: true
      bw-db:
        name: bw-db
        driver: overlay
        attachable: true
    ```

=== "Kubernetes"

    If you want to use the setup wizard, you will need to set the `UI_HOST` setting to the HTTP endpoint of your web UI SERVICE. For example, if your web UI service is named `svc-bunkerweb-ui` and is listening on the `7000` port, you will need to set the `UI_HOST` setting to `http://svc-bunkerweb-ui.default.svc.cluster.local:7000` (don't forget to replace the namespace and the service name accordingly).

    !!! tip "Accessing the setup wizard"

        You can access the setup wizard by browsing the `https://your-ip-address-or-fqdn/setup` URI of your server.

    Here is the yaml boilerplate that you can use (don't forget to edit the `changeme` data) :

    ```yaml
    apiVersion: rbac.authorization.k8s.io/v1
    kind: ClusterRole
    metadata:
      name: cr-bunkerweb
    rules:
      - apiGroups: [""]
        resources: ["services", "pods", "configmaps", "secrets"]
        verbs: ["get", "watch", "list"]
      - apiGroups: ["networking.k8s.io"]
        resources: ["ingresses"]
        verbs: ["get", "watch", "list"]
    ---
    apiVersion: v1
    kind: ServiceAccount
    metadata:
      name: sa-bunkerweb
      namespace: default
    ---
    apiVersion: rbac.authorization.k8s.io/v1
    kind: ClusterRoleBinding
    metadata:
      name: crb-bunkerweb
    subjects:
      - kind: ServiceAccount
        name: sa-bunkerweb
        namespace: default
        apiGroup: ""
    roleRef:
      kind: ClusterRole
      name: cr-bunkerweb
      apiGroup: rbac.authorization.k8s.io
    ---
    apiVersion: apps/v1
    kind: DaemonSet
    metadata:
      name: bunkerweb
    spec:
      selector:
        matchLabels:
          app: bunkerweb
      template:
        metadata:
          labels:
            app: bunkerweb
          # mandatory annotation
          annotations:
            bunkerweb.io/INSTANCE: "yes"
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            # using bunkerweb as name is mandatory
            - name: bunkerweb
              image: bunkerity/bunkerweb:1.6.0-rc4
              imagePullPolicy: Always
              securityContext:
                runAsUser: 101
                runAsGroup: 101
                allowPrivilegeEscalation: false
                capabilities:
                  drop:
                    - ALL
              ports:
                - containerPort: 8080
                  hostPort: 80
                - containerPort: 8443
                  hostPort: 443
              env:
                - name: KUBERNETES_MODE
                  value: "yes"
                # replace with your DNS resolvers
                # e.g. : kube-dns.kube-system.svc.cluster.local
                - name: DNS_RESOLVERS
                  value: "coredns.kube-system.svc.cluster.local"
                # 10.0.0.0/8 is the cluster internal subnet
                - name: API_WHITELIST_IP
                  value: "127.0.0.0/8 10.0.0.0/8"
              livenessProbe:
                exec:
                  command:
                    - /usr/share/bunkerweb/helpers/healthcheck.sh
                initialDelaySeconds: 30
                periodSeconds: 5
                timeoutSeconds: 1
                failureThreshold: 3
              readinessProbe:
                exec:
                  command:
                    - /usr/share/bunkerweb/helpers/healthcheck.sh
                initialDelaySeconds: 30
                periodSeconds: 1
                timeoutSeconds: 1
                failureThreshold: 3
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-controller
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-controller
      template:
        metadata:
          labels:
            app: bunkerweb-controller
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            - name: bunkerweb-controller
              image: bunkerity/bunkerweb-autoconf:1.6.0-rc4
              imagePullPolicy: Always
              env:
                - name: KUBERNETES_MODE
                  value: "yes"
                - name: DATABASE_URI
                  value: "mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db" # Remember to set a stronger password for the database
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-scheduler
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-scheduler
      template:
        metadata:
          labels:
            app: bunkerweb-scheduler
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            - name: bunkerweb-scheduler
              image: bunkerity/bunkerweb-scheduler:1.6.0-rc4
              imagePullPolicy: Always
              env:
                - name: KUBERNETES_MODE
                  value: "yes"
                - name: DATABASE_URI
                  value: "mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db" # Remember to set a stronger password for the database
                # replace with your DNS resolvers
                # e.g. : kube-dns.kube-system.svc.cluster.local
                - name: DNS_RESOLVERS
                  value: "coredns.kube-system.svc.cluster.local"
                # 10.0.0.0/8 is the cluster internal subnet
                - name: API_WHITELIST_IP
                  value: "127.0.0.0/8 10.0.0.0/8"
                - name: BUNKERWEB_INSTANCES
                  value: ""
                - name: SERVER_NAME
                  value: ""
                - name: MULTISITE
                  value: "yes"
                - name: USE_REDIS
                  value: "yes"
                # replace with your Redis host
                - name: REDIS_HOST
                  value: "svc-bunkerweb-redis.default.svc.cluster.local"
                - name: UI_HOST
                  value: "http://svc-bunkerweb-ui.default.svc.cluster.local:7000" # Change it if needed
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-redis
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-redis
      template:
        metadata:
          labels:
            app: bunkerweb-redis
        spec:
          containers:
            - name: bunkerweb-redis
              image: redis:7-alpine
              imagePullPolicy: Always
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-db
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-db
      template:
        metadata:
          labels:
            app: bunkerweb-db
        spec:
          containers:
            - name: bunkerweb-db
              image: mariadb:11
              imagePullPolicy: Always
              env:
                - name: MYSQL_RANDOM_ROOT_PASSWORD
                  value: "yes"
                - name: MYSQL_DATABASE
                  value: "db"
                - name: MYSQL_USER
                  value: "bunkerweb"
                - name: MYSQL_PASSWORD
                  value: "changeme" # Remember to set a stronger password for the database
              volumeMounts:
                - mountPath: "/var/lib/mysql"
                  name: vol-db
          volumes:
            - name: vol-db
              persistentVolumeClaim:
                claimName: pvc-bunkerweb
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-ui
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-ui
      template:
        metadata:
          labels:
            app: bunkerweb-ui
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            - name: bunkerweb-ui
              image: bunkerity/bunkerweb-ui:1.6.0-rc4
              imagePullPolicy: Always
              env:
                - name: KUBERNETES_MODE
                  value: "yes"
                - name: DATABASE_URI
                  value: "mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db" # Remember to set a stronger password for the database
                - name: TOTP_SECRETS
                  value: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-bunkerweb
    spec:
      clusterIP: None
      selector:
        app: bunkerweb
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-bunkerweb-db
    spec:
      type: ClusterIP
      selector:
        app: bunkerweb-db
      ports:
        - name: sql
          protocol: TCP
          port: 3306
          targetPort: 3306
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-bunkerweb-redis
    spec:
      type: ClusterIP
      selector:
        app: bunkerweb-redis
      ports:
        - name: redis
          protocol: TCP
          port: 6379
          targetPort: 6379
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-bunkerweb-ui
    spec:
      type: ClusterIP
      selector:
        app: bunkerweb-ui
      ports:
        - name: http
          protocol: TCP
          port: 7000
          targetPort: 7000
    ---
    apiVersion: v1
    kind: PersistentVolumeClaim
    metadata:
      name: pvc-bunkerweb
    spec:
      accessModes:
        - ReadWriteOnce
      resources:
        requests:
          storage: 5Gi
    ```

=== "Linux"

    If you don't want to use the setup wizard, you will need to run the following command `export UI_WIZARD=no` before installing BunkerWeb as described in [integrations section](integrations.md#linux) of the documentation (this is an optional step).

    !!! tip "Accessing the setup wizard"

        You can access the setup wizard by browsing the `https://your-ip-address/setup` URI of your server. -->

## Accessing logs

Beginning with version `1.6`, the method of accessing logs has changed. This update specifically impacts container based integrations: the web UI will read the logs files from the `/var/log/bunkerweb` directory.

To keep the logs accessible from the web UI, we recommend you to use a syslog server such as `syslog-ng` to read the logs and creates the corresponding files in the `/var/log/bunkerweb` directory.

### Compose boilerplates

=== "Docker"

    To forward the logs correctly to the `/var/log/bunkerweb` directory on the Docker integration, you will need to stream the logs to a file using `syslog-ng`. Here is an example of how to do this :

    ```yaml
    x-bw-env: &bw-env
      # We anchor the environment variables to avoid duplication
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc4
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *bw-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog
          options:
            tag: "bunkerweb" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc4
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
          SERVE_FILES: "no"
          DISABLE_DEFAULT_SERVER: "yes"
          USE_CLIENT_CACHE: "yes"
          USE_GZIP: "yes"
          www.example.com_USE_UI: "yes"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Change it to a hard to guess URI
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
          www.example.com_INTERCEPTED_ERROR_CODES: "400 404 405 413 429 500 501 502 503 504"
          www.example.com_GENERATE_SELF_SIGNED_SSL: "yes"
          www.example.com_MAX_CLIENT_SIZE: "50m"
          www.example.com_ALLOWED_METHODS: "GET|POST|PUT|DELETE"
        volumes:
          - bw-data:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-scheduler" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.0-rc4
        environment:
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the admin user
          TOPT_SECRETS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-ui" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-db:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      bw-syslog:
        image: balabit/syslog-ng:4.7.1
        # image: lscr.io/linuxserver/syslog-ng:4.7.1-r1-ls116 # For aarch64 architecture
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # This is the syslog-ng configuration file
        networks:
          bw-universe:
            ipv4_address: 10.20.30.254 # Make sure to set the correct IP address

    volumes:
      bw-data:
      bw-db:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker Autoconf"

    To forward the logs correctly to the `/var/log/bunkerweb` directory on the Autoconf integration, you will need to stream the logs to a file using `syslog-ng`. Here is an example of how to do this :

    ```yaml
    x-ui-env: &bw-ui-env
      # We anchor the environment variables to avoid duplication
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc4
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog
          options:
            tag: "bunkerweb" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc4
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
          SERVER_NAME: "" # The server name will be filled with services labels
          MULTISITE: "yes" # Mandatory setting for autoconf / ui
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        volumes:
          - bw-data:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-scheduler" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.0-rc4
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375" # This is the Docker socket address
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-docker
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-autoconf" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.0-rc4
        environment:
          <<: *bw-ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the admin user
          TOPT_SECRETS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        volumes:
          - bw-logs:/var/log/bunkerweb
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_UI=yes"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme" # Change it to a hard to guess URI
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
          - "bunkerweb.INTERCEPTED_ERROR_CODES=400 404 405 413 429 500 501 502 503 504"
          - "bunkerweb.GENERATE_SELF_SIGNED_SSL=yes"
          - "bunkerweb.MAX_CLIENT_SIZE=50m"
          - "bunkerweb.ALLOWED_METHODS=GET|POST|PUT|DELETE"
        logging:
          driver: syslog
          options:
            tag: "bw-ui" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-db:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: "unless-stopped"
        networks:
          - bw-docker

      bw-syslog:
        image: balabit/syslog-ng:4.7.1
        # image: lscr.io/linuxserver/syslog-ng:4.7.1-r1-ls116 # For aarch64 architecture
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # This is the syslog-ng configuration file
        networks:
          bw-universe:
            ipv4_address: 10.20.30.254 # Make sure to set the correct IP address

    volumes:
      bw-data:
      bw-db:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
      bw-docker:
        name: bw-docker
    ```

### Syslog-ng configuration

Here is an example of a `syslog-ng.conf` file that you can use to forward the logs to a file :

```conf
@version: 4.7

# Source configuration to receive logs from Docker containers
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# Template to format log messages
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# Destination configuration to write logs to dynamically named files
destination d_dyna_file {
  file(
    "/var/log/bunkerweb/${PROGRAM}.log"
    template(t_imp)
    owner("101")
    group("101")
    dir_owner("root")
    dir_group("101")
    perm(0440)
    dir_perm(0770)
    create_dirs(yes)
  );
};

# Log path to direct logs to dynamically named files
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Account management

You can access the account management page by clicking on the profile image in the top right corner:

<figure markdown>
  ![Overview](assets/img/manage-account.png){ align=center, width="400" }
  <figcaption>Account page access from top right corner</figcaption>
</figure>

### Username / Password

!!! warning "Lost password/username"

    In case you forgot your UI credentials, you can reset them from the CLI following [the steps described in the troubleshooting section](troubleshooting.md#web-ui).

You can update your username or password by filling the dedicated forms in the **Security** tab. For security reason, you need to enter your current password even if you are connected.

Please note that when your username or password is updated, you will be logout from the web UI to log in again.

<figure markdown>
  ![Overview](assets/img/profile-username-password.png){ align=center, width="650" }
  <figcaption>Username / Password form</figcaption>
</figure>

### Two-Factor authentication

!!! warning "Lost secret key"

    In case you lost your secret key, two options are available :

    - You can recover your account using one of the provided recovery codes when you enabled 2FA (a recovery code can only be used once).
    - You can disable 2FA from the CLI following [the steps described in the troubleshooting section](troubleshooting.md#web-ui).

You can power-up your login security by adding **Two-Factor Authentication (2FA)** to your account. By doing so, an extra code will be needed in addition to your password.

The web UI uses [Time based One Time Password (TOTP)](https://en.wikipedia.org/wiki/Time-based_one-time_password) as 2FA implementation : using a **secret key**, the algorithm will generate **one time passwords only valid for a short period of time**.

Any TOTP client such as Google Authenticator, Authy, FreeOTP, ... can be used to store the secret key and generate the codes. Please note that once TOTP is enabled, **you won't be able to retrieve it from the web UI**.

The following steps are needed to enable the TOTP feature from the web UI :

- Copy the secret key or use the QR code on your authenticator app
- Enter the current TOTP code in the 2FA input
- Enter your current password

!!! info "Secret key refresh"
    A new secret key is **generated each time** you visit the page or submit the form. In case something went wrong (e.g. : expired TOTP code), you will need to copy the new secret key to your authenticator app until 2FA is successfully enabled.

!!! tip "Recovery codes"

    When you enable 2FA, you will be provided with **5 recovery codes**. These codes can be used to recover your account in case you have lost your TOTP secret key. Each code can only be used once. **These codes will only be shown once so make sure to store them in a safe place**.

    If you ever lose your recovery codes, **you can refresh them via the TOTP section of the account management page**. Please note that the old recovery codes will be invalidated.

You can enable or disable 2FA and also refresh recovery codes in the **Security** tab:

<figure markdown>
  ![Overview](assets/img/profile-totp.png){ align=center, width="800" }
  <figcaption>TOTP enable / disable / refresh recovery codes forms</figcaption>
</figure>

After a successful login/password combination, you will be prompted to enter your TOTP code:

<figure markdown>
  ![Overview](assets/img/profile-2fa.png){ align=center, width="400" }
  <figcaption>2FA on login page</figcaption>
</figure>

### Current sessions

In the **Session** tab, you will be able to list and revoke current sessions:

<figure markdown>
  ![Overview](assets/img/sessions.png){ align=center, width="800" }
  <figcaption>Manage sessions</figcaption>
</figure>


## Advanced installation

!!! tip "Overriding admin credentials from environment variables"

    If you want to override the admin credentials from environment variables, you can set the following variables :

    - `OVERRIDE_ADMIN_CREDS` : set it to `yes` to enable the override even if the admin credentials are already set (default is `no`)
    - `ADMIN_USERNAME` : username to access the web UI
    - `ADMIN_PASSWORD` : password to access the web UI

    The web UI will use these variables to authenticate you.

!!! tip "Web UI specific environment variables"

    The web UI uses the following environment variables :

    - `OVERRIDE_ADMIN_CREDS` : set it to `yes` to enable the override even if the admin credentials are already set (default is `no`).
    - `ADMIN_USERNAME` : username to access the web UI.
    - `ADMIN_PASSWORD` : password to access the web UI.
    - `FLASK_SECRET` : a secret key used to encrypt the session cookie (if not set, a random key will be generated).
    - `TOTP_SECRETS` : a list of TOTP secrets separated by spaces or a dictionary (e.g. : `{"1": "mysecretkey"}` or `mysecretkey` or `mysecretkey mysecretkey1`). **We strongly recommend you to set this variable if you want to use 2FA, as it will be used to encrypt the TOTP secret keys** (if not set, a random number of secret keys will be generated). Check out the [passlib documentation](https://passlib.readthedocs.io/en/stable/narr/totp-tutorial.html#application-secrets) for more information.
    - `LISTEN_ADDR` : the address where the web UI will listen (default is `0.0.0.0` in **Docker images** and `127.0.0.1` on **Linux installations**).
    - `LISTEN_PORT` : the port where the web UI will listen (default is `7000`).
    - `MAX_WORKERS` : the number of workers used by the web UI (default is the number of CPUs).
    - `MAX_THREADS` : the number of threads used by the web UI (default is `MAX_WORKERS` * 2).
    - `FORWARDED_ALLOW_IPS` : a list of IP addresses or networks that are allowed to be used in the `X-Forwarded-For` header (default is `*` in **Docker images** and `127.0.0.1` on **Linux installations**).
    - `CHECK_PRIVATE_IP` : set it to `yes` to not disconnect users that have their IP address changed during a session if they are in a private network (default is `yes`). (Non-private IP addresses are always checked).

    The web UI will use these variables to authenticate you and handle the 2FA feature.

!!! example "Generating recommended secrets"

    To generate a valid **ADMIN_PASSWORD**, we recommend you to **use a password manager** or a **password generator**.

    You can generate a valid **FLASK_SECRET** using the following command :

    ```shell
    python3 -c "import secrets; print(secrets.token_hex(64))"
    ```

    You can generate valid space-separated **TOTP_SECRETS** using the following command (you will need the `passlib` package) :

    ```shell
    python3 -c "from passlib import totp; print(' '.join(totp.generate_secret() for i in range(1, 6)))"
    ```

=== "Docker"

    The web UI can be deployed using a dedicated container which is available on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) :

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternatively, you can also build it yourself :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    !!! tip "Environment variables"

        Please read the [Prerequisites](#prerequisites) section to check out all the environment variables you can set to customize the web UI.

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md). We recommend you to connect BunkerWeb and web UI using a dedicated network (like `bw-universe` also used by the scheduler) so it won't be on the same network of your web services for obvious security reasons. Please note that the web UI container is listening on the `7000` port.

    !!! info "Database backend"

        If you want another Database backend than MariaDB please refer to the docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.0-rc4/misc/integrations) of the repository.

    Here is the docker-compose boilerplate that you can use (don't forget to edit the `changeme` data) :

    ```yaml
    x-ui-env: &ui-env
      # We anchor the environment variables to avoid duplication
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc4
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        environment:
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc4
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # We mirror the API_WHITELIST_IP from the bunkerweb service
          SERVE_FILES: "no"
          DISABLE_DEFAULT_SERVER: "yes"
          USE_CLIENT_CACHE: "yes"
          USE_GZIP: "yes"
          www.example.com_USE_UI: "yes"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Remember to set a stronger URI
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000" # The web UI container is listening on the 7000 port by default
          www.example.com_INTERCEPTED_ERROR_CODES: "400 404 405 413 429 500 501 502 503 504"
          www.example.com_GENERATE_SELF_SIGNED_SSL: "yes"
          www.example.com_MAX_CLIENT_SIZE: "50m"
          www.example.com_ALLOWED_METHODS: "GET|POST|PUT|DELETE"
        volumes:
          - bw-data:/data # This is used to persist the cache and other data like the backups
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.0-rc4
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the changeme user
          TOTP_SECRETS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-db:/var/lib/mysql
        networks:
          - bw-db

    volumes:
      bw-data:
      bw-db:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker autoconf"

    The web UI can be deployed using a dedicated container which is available on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) :

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternatively, you can also build it yourself :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    !!! tip "Environment variables"

        Please read the [Prerequisites](#prerequisites) section to check out all the environment variables you can set to customize the web UI.

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md). We recommend you to connect BunkerWeb and web UI using a dedicated network (like `bw-universe` also used by the scheduler and autoconf) so it won't be on the same network of your web services for obvious security reasons. Please note that the web UI container is listening on the `7000` port.

    !!! info "Database backend"

        If you want another Database backend than MariaDB please refer to the docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.0-rc4/misc/integrations) of the repository.

    Here is the docker-compose boilerplate that you can use (don't forget to edit the `changeme` data) :

    ```yaml
    x-ui-env: &ui-env
      # We anchor the environment variables to avoid duplication
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc4
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        labels:
          - "bunkerweb.INSTANCE=yes" # We set the instance label to allow the autoconf to detect the instance
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc4
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
        volumes:
          - bw-data:/data # This is used to persist the cache and other data like the backups
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.0-rc4
        depends_on:
          - bw-docker
        environment:
          <<: *ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-db:/var/lib/mysql
        networks:
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.0-rc4
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the changeme user
          TOTP_SECRETS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_UI=yes"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme"
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
          - "bunkerweb.INTERCEPTED_ERROR_CODES=400 404 405 413 429 500 501 502 503 504"
          - "bunkerweb.GENERATE_SELF_SIGNED_SSL=yes"
          - "bunkerweb.MAX_CLIENT_SIZE=50m"
          - "bunkerweb.ALLOWED_METHODS=GET|POST|PUT|DELETE"
        networks:
          - bw-universe
          - bw-db

    volumes:
      bw-data:
      bw-db:

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
      bw-db:
        name: bw-db
    ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_3_2) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    The web UI can be deployed using a dedicated container which is available on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) :

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternatively, you can also build it yourself :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    !!! tip "Environment variables"

        Please read the [Prerequisites](#prerequisites) section to check out all the environment variables you can set to customize the web UI.

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md). We recommend you to connect BunkerWeb and web UI using a dedicated network (like `bw-universe` also used by the scheduler and autoconf) so it won't be on the same network of your web services for obvious security reasons. Please note that the web UI container is listening on the `7000` port.

    !!! info "Database backend"

        If you want another Database backend than MariaDB please refer to the stack files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.0-rc4/misc/integrations) of the repository.

    Here is the stack boilerplate that you can use (don't forget to edit the `changeme` data) :

    ```yaml
    x-ui-env: &ui-env
      # We anchor the environment variables to avoid duplication
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc4
        ports:
          - published: 80
            target: 8080
            mode: host
            protocol: tcp
          - published: 443
            target: 8443
            mode: host
            protocol: tcp
          - published: 443
            target: 8443
            mode: host
            protocol: udp # For QUIC / HTTP3 support
        environment:
          SWARM_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        networks:
          - bw-universe
          - bw-services
        deploy:
          mode: global
          placement:
            constraints:
              - "node.role == worker"
          labels:
            - "bunkerweb.INSTANCE=yes"

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc4
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "bw-redis"
        volumes:
          - bw-data:/data # This is used to persist the cache and other data like the backups
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.0-rc4
        environment:
          <<: *ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          CONFIGS: "1"
          CONTAINERS: "1"
          SERVICES: "1"
          SWARM: "1"
          TASKS: "1"
          LOG_LEVEL: "warning"
        networks:
          - bw-docker
        deploy:
          placement:
            constraints:
              - "node.role == manager"

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-db:/var/lib/mysql
        networks:
          - bw-db

      bw-redis:
        image: redis:7-alpine
        networks:
          - bw-universe

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.0-rc4
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the changeme user
          TOTP_SECRETS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        networks:
          - bw-universe
          - bw-db
        deploy:
          labels:
            - "bunkerweb.SERVER_NAME=www.example.com"
            - "bunkerweb.USE_UI=yes"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_URL=/changeme"
            - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
            - "bunkerweb.REVERSE_PROXY_INTERCEPT_ERRORS=no"
            - "bunkerweb.INTERCEPTED_ERROR_CODES=400 404 405 413 429 500 501 502 503 504"
            - "bunkerweb.GENERATE_SELF_SIGNED_SSL=yes"
            - "bunkerweb.MAX_CLIENT_SIZE=50m"
            - "bunkerweb.ALLOWED_METHODS=GET|POST|PUT|DELETE"

    volumes:
      bw-db:
      bw-data:

    networks:
      bw-universe:
        name: bw-universe
        driver: overlay
        attachable: true
        ipam:
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
        driver: overlay
        attachable: true
      bw-docker:
        name: bw-docker
        driver: overlay
        attachable: true
      bw-db:
        name: bw-db
        driver: overlay
        attachable: true
    ```

=== "Kubernetes"

    The web UI can be deployed using a dedicated container which is available on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) as a standard [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).

    !!! tip "Environment variables"

        Please read the [Prerequisites](#prerequisites) section to check out all the environment variables you can set to customize the web UI.

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md). Network segmentation between web UI and web services is not covered in this documentation. Please note that the web UI container is listening on the `7000` port.

    !!! info "Database backend"

        If you want another Database backend than MariaDB please refer to the yaml files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.0-rc4/misc/integrations) of the repository.

    Here is the yaml boilerplate that you can use (don't forget to edit the `changeme` data) :

    ```yaml
    apiVersion: rbac.authorization.k8s.io/v1
    kind: ClusterRole
    metadata:
      name: cr-bunkerweb
    rules:
      - apiGroups: [""]
        resources: ["services", "pods", "configmaps", "secrets"]
        verbs: ["get", "watch", "list"]
      - apiGroups: ["networking.k8s.io"]
        resources: ["ingresses"]
        verbs: ["get", "watch", "list"]
    ---
    apiVersion: v1
    kind: ServiceAccount
    metadata:
      name: sa-bunkerweb
      namespace: default
    ---
    apiVersion: rbac.authorization.k8s.io/v1
    kind: ClusterRoleBinding
    metadata:
      name: crb-bunkerweb
    subjects:
      - kind: ServiceAccount
        name: sa-bunkerweb
        namespace: default
        apiGroup: ""
    roleRef:
      kind: ClusterRole
      name: cr-bunkerweb
      apiGroup: rbac.authorization.k8s.io
    ---
    apiVersion: apps/v1
    kind: DaemonSet
    metadata:
      name: bunkerweb
    spec:
      selector:
        matchLabels:
          app: bunkerweb
      template:
        metadata:
          labels:
            app: bunkerweb
          # mandatory annotation
          annotations:
            bunkerweb.io/INSTANCE: "yes"
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            # using bunkerweb as name is mandatory
            - name: bunkerweb
              image: bunkerity/bunkerweb:1.6.0-rc4
              imagePullPolicy: Always
              securityContext:
                runAsUser: 101
                runAsGroup: 101
                allowPrivilegeEscalation: false
                capabilities:
                  drop:
                    - ALL
              ports:
                - containerPort: 8080
                  hostPort: 80
                - containerPort: 8443
                  hostPort: 443
              env:
                - name: KUBERNETES_MODE
                  value: "yes"
                # replace with your DNS resolvers
                # e.g. : kube-dns.kube-system.svc.cluster.local
                - name: DNS_RESOLVERS
                  value: "coredns.kube-system.svc.cluster.local"
                # 10.0.0.0/8 is the cluster internal subnet
                - name: API_WHITELIST_IP
                  value: "127.0.0.0/8 10.0.0.0/8"
              livenessProbe:
                exec:
                  command:
                    - /usr/share/bunkerweb/helpers/healthcheck.sh
                initialDelaySeconds: 30
                periodSeconds: 5
                timeoutSeconds: 1
                failureThreshold: 3
              readinessProbe:
                exec:
                  command:
                    - /usr/share/bunkerweb/helpers/healthcheck.sh
                initialDelaySeconds: 30
                periodSeconds: 1
                timeoutSeconds: 1
                failureThreshold: 3
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-controller
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-controller
      template:
        metadata:
          labels:
            app: bunkerweb-controller
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            - name: bunkerweb-controller
              image: bunkerity/bunkerweb-autoconf:1.6.0-rc4
              imagePullPolicy: Always
              env:
                - name: KUBERNETES_MODE
                  value: "yes"
                - name: DATABASE_URI
                  value: "mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db" # Remember to set a stronger password for the database
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-scheduler
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-scheduler
      template:
        metadata:
          labels:
            app: bunkerweb-scheduler
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            - name: bunkerweb-scheduler
              image: bunkerity/bunkerweb-scheduler:1.6.0-rc4
              imagePullPolicy: Always
              env:
                - name: KUBERNETES_MODE
                  value: "yes"
                - name: DATABASE_URI
                  value: "mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db" # Remember to set a stronger password for the database
                # replace with your DNS resolvers
                # e.g. : kube-dns.kube-system.svc.cluster.local
                - name: DNS_RESOLVERS
                  value: "coredns.kube-system.svc.cluster.local"
                # 10.0.0.0/8 is the cluster internal subnet
                - name: API_WHITELIST_IP
                  value: "127.0.0.0/8 10.0.0.0/8"
                - name: BUNKERWEB_INSTANCES
                  value: ""
                - name: SERVER_NAME
                  value: ""
                - name: MULTISITE
                  value: "yes"
                - name: USE_REDIS
                  value: "yes"
                # replace with your Redis host
                - name: REDIS_HOST
                  value: "svc-bunkerweb-redis.default.svc.cluster.local"
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-redis
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-redis
      template:
        metadata:
          labels:
            app: bunkerweb-redis
        spec:
          containers:
            - name: bunkerweb-redis
              image: redis:7-alpine
              imagePullPolicy: Always
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-db
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-db
      template:
        metadata:
          labels:
            app: bunkerweb-db
        spec:
          containers:
            - name: bunkerweb-db
              image: mariadb:11
              imagePullPolicy: Always
              env:
                - name: MYSQL_RANDOM_ROOT_PASSWORD
                  value: "yes"
                - name: MYSQL_DATABASE
                  value: "db"
                - name: MYSQL_USER
                  value: "bunkerweb"
                - name: MYSQL_PASSWORD
                  value: "changeme" # Remember to set a stronger password for the database
              volumeMounts:
                - mountPath: "/var/lib/mysql"
                  name: vol-db
          volumes:
            - name: vol-db
              persistentVolumeClaim:
                claimName: pvc-bunkerweb
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-ui
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-ui
      template:
        metadata:
          labels:
            app: bunkerweb-ui
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            - name: bunkerweb-ui
              image: bunkerity/bunkerweb-ui:1.6.0-rc4
              imagePullPolicy: Always
              env:
                - name: KUBERNETES_MODE
                  value: "yes"
                - name: DATABASE_URI
                  value: "mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db" # Remember to set a stronger password for the database
                - name: ADMIN_USERNAME
                  value: changeme
                - name: ADMIN_PASSWORD
                  value: "changeme" # Remember to set a stronger password for the ui user
                - name: TOTP_SECRETS
                  value: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-bunkerweb
    spec:
      clusterIP: None
      selector:
        app: bunkerweb
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-bunkerweb-db
    spec:
      type: ClusterIP
      selector:
        app: bunkerweb-db
      ports:
        - name: sql
          protocol: TCP
          port: 3306
          targetPort: 3306
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-bunkerweb-redis
    spec:
      type: ClusterIP
      selector:
        app: bunkerweb-redis
      ports:
        - name: redis
          protocol: TCP
          port: 6379
          targetPort: 6379
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-bunkerweb-ui
    spec:
      type: ClusterIP
      selector:
        app: bunkerweb-ui
      ports:
        - name: http
          protocol: TCP
          port: 7000
          targetPort: 7000
    ---
    apiVersion: v1
    kind: PersistentVolumeClaim
    metadata:
      name: pvc-bunkerweb
    spec:
      accessModes:
        - ReadWriteOnce
      resources:
        requests:
          storage: 5Gi
    ---
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      annotations:
        bunkerweb.io/www.example.com_SERVE_FILES: "no"
        bunkerweb.io/www.example.com_USE_CLIENT_CACHE: "yes"
        bunkerweb.io/www.example.com_USE_GZIP: "yes"
        bunkerweb.io/www.example.com_USE_UI: "yes"
        bunkerweb.io/www.example.com_INTERCEPTED_ERROR_CODES: "400 404 405 413 429 500 501 502 503 504"
        bunkerweb.io/www.example.com_GENERATE_SELF_SIGNED_SSL: "yes"
        bunkerweb.io/www.example.com_MAX_CLIENT_SIZE: "50m"
        bunkerweb.io/www.example.com_ALLOWED_METHODS: "GET|POST|PUT|DELETE"
    spec:
      rules:
        - host: www.example.com
          http:
            paths:
              - path: /changeme
                pathType: Prefix
                backend:
                  service:
                    name: svc-bunkerweb-ui
                    port:
                      number: 7000
    ```

=== "Linux"

    The installation of the web UI using the [Linux integration](integrations.md#linux) is pretty straightforward because it is installed with BunkerWeb.

    The web UI comes as systemd service named `bunkerweb-ui` which is not enabled by default. If you want to start the web UI when on startup you can run the following command :

    ```shell
    systemctl enable bunkerweb-ui
    ```

    A dedicated environment file located at `/etc/bunkerweb/ui.env` is used to configure the web UI :

    ```conf
    ADMIN_USERNAME=changeme
    ADMIN_PASSWORD=changeme
    TOTP_SECRETS=mysecret
    ```

    Replace the `changeme` data with your own values.

    Remember to set a stronger secret key for the `TOTP_SECRETS` variable, check the [Prerequisites](#prerequisites) section for more information.

    Each time you edit the `/etc/bunkerweb/ui.env` file, you will need to restart the service :

    ```shell
    systemctl restart bunkerweb-ui
    ```

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md). Please note that the web UI is listening on the `7000` port and only on the loopback interface.

    Here is the `/etc/bunkerweb/variables.env` boilerplate you can use :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4
    API_LISTEN_IP=127.0.0.1
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_UI=yes
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/changeme
    www.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:7000
    www.example.com_INTERCEPTED_ERROR_CODES=400 404 405 413 429 500 501 502 503 504
    www.example.com_GENERATE_SELF_SIGNED_SSL=yes
    www.example.com_MAX_CLIENT_SIZE=50m
    www.example.com_ALLOWED_METHODS=GET|POST|PUT|DELETE
    ```

    Don't forget to reload the `bunkerweb` service :

    ```shell
    systemctl reload bunkerweb
    ```
