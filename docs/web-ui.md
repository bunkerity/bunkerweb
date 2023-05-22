# Web UI

## Overview

<p align="center">
	<iframe style="display: block;" width="560" height="315" src="https://www.youtube-nocookie.com/embed/Ao20SfvQyr4" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

The "Web UI" is a web application that helps you manage your BunkerWeb instance using a user-friendly interface instead of the command-line one.

## Features

- Start, stop, restart and reload your BunkerWeb instance
- Add, edit and delete settings for your web applications
- Add, edit and delete custom configurations for NGINX and ModSecurity
- Install and uninstall external plugins
- Explore the cached files
- Monitor jobs execution
- View the logs and search pattern

## Installation

Because the web UI is a web application, the recommended installation procedure is to use BunkerWeb in front of it as a reverse proxy.

!!! warning "Security considerations"

    The security of the web UI is really important. If someone manages to gain access to the application, not only he will be able to edit your configurations but he could execute some code in the context of BunkerWeb (with a custom configuration containing LUA code for example). We highly recommend you to follow minimal security best practices like :

    * Choose a strong password for the login (**at least 8 chars with 1 lower case letter, 1 upper case letter, 1 digit and 1 special char is required**)
    * Put the web UI under a "hard to guess" URI
    * Do not open the web UI on the Internet without any further restrictions
    * Apply settings listed in the [security tuning section](security-tuning.md) of the documentation

!!! info "Multisite mode"

    The usage of the web UI implies enabling the [multisite mode](concepts.md#multisite-mode).

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

    The following environment variables are used to configure the web UI container :

    - `ADMIN_USERNAME` : username to access the web UI
    - `ADMIN_PASSWORD` : password to access the web UI
    - `ABSOLUTE_URI` : full URI of your web UI instance (like `http://www.example.com/foo/`)

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md#protect-http-applications). We recommend you to connect BunkerWeb and web UI using a dedicated network (like `bw-universe` also used by the scheduler) so it won't be on the same network of your web services for obvious security reasons. Please note that the web UI container is listening on the `7000` port.

    !!! info "Database backend"

        If you want another Database backend than MariaDB please refer to the docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/misc/integrations) of the repository.

    Here is the docker-compose boilerplate that you can use (don't forget to edit the `changeme` data) :

    ```yaml
    version: "3.5"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.5.0
        ports:
          - 80:8080
          - 443:8443
        labels:
          - "bunkerweb.INSTANCE"
        environment:
          - SERVER_NAME=www.example.com
          - MULTISITE=yes
          - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db # Remember to set a stronger password for the database
          - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
          - DISABLE_DEFAULT_SERVER=yes
          - USE_CLIENT_CACHE=yes
          - USE_GZIP=yes
          - www.example.com_USE_UI=yes
          - www.example.com_USE_REVERSE_PROXY=yes
          - www.example.com_REVERSE_PROXY_URL=/changeme/
          - www.example.com_REVERSE_PROXY_HOST=http://bw-ui:7000
          - www.example.com_REVERSE_PROXY_HEADERS=X-Script-Name /changeme
          - www.example.com_INTERCEPTED_ERROR_CODES=400 404 405 413 429 500 501 502 503 504
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.5.0
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db # Remember to set a stronger password for the database
          - DOCKER_HOST=tcp://bw-docker:2375
        networks:
          - bw-universe
          - bw-docker

      bw-docker:
        image: tecnativa/docker-socket-proxy
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          - CONTAINERS=1
        networks:
          - bw-docker

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.5.0
        depends_on:
          - bw-docker
        environment:
          - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db # Remember to set a stronger password for the database
          - DOCKER_HOST=tcp://bw-docker:2375
          - ADMIN_USERNAME=changeme
          - ADMIN_PASSWORD=changeme # Remember to set a stronger password for the changeme user
          - ABSOLUTE_URI=http://www.example.com/changeme/
        networks:
          - bw-universe
          - bw-docker

      bw-db:
        image: mariadb:10.10
        environment:
          - MYSQL_RANDOM_ROOT_PASSWORD=yes
          - MYSQL_DATABASE=db
          - MYSQL_USER=bunkerweb
          - MYSQL_PASSWORD=changeme # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-docker

    volumes:
      bw-data:

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

    The following environment variables are used to configure the web UI container :

    - `ADMIN_USERNAME` : username to access the web UI
    - `ADMIN_PASSWORD` : password to access the web UI
    - `ABSOLUTE_URI` : full URI of your web UI instance (like `http://www.example.com/foo/`)

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md#protect-http-applications). We recommend you to connect BunkerWeb and web UI using a dedicated network (like `bw-universe` also used by the scheduler and autoconf) so it won't be on the same network of your web services for obvious security reasons. Please note that the web UI container is listening on the `7000` port.

    !!! info "Database backend"

        If you want another Database backend than MariaDB please refer to the docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/misc/integrations) of the repository.

    Here is the docker-compose boilerplate that you can use (don't forget to edit the `changeme` data) :

    ```yaml
    version: "3.5"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.5.0
        ports:
          - 80:8080
          - 443:8443
        labels:
          - "bunkerweb.INSTANCE"
        environment:
          - SERVER_NAME=
          - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db
          - AUTOCONF_MODE=yes
          - MULTISITE=yes
          - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
        networks:
          - bw-universe
          - bw-services

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.5.0
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db
          - AUTOCONF_MODE=yes
          - DOCKER_HOST=tcp://bw-docker:2375
        networks:
          - bw-universe
          - bw-docker

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.5.0
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db
          - DOCKER_HOST=tcp://bw-docker:2375
          - AUTOCONF_MODE=yes
        networks:
          - bw-universe
          - bw-docker

      bw-docker:
        image: tecnativa/docker-socket-proxy
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          - CONTAINERS=1
        networks:
          - bw-docker

      bw-db:
        image: mariadb:10.10
        environment:
          - MYSQL_RANDOM_ROOT_PASSWORD=yes
          - MYSQL_DATABASE=db
          - MYSQL_USER=bunkerweb
          - MYSQL_PASSWORD=changeme
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-docker

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.5.0
        networks:
          bw-docker:
          bw-universe:
            aliases:
              - bw-ui
        environment:
          - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db
          - DOCKER_HOST=tcp://bw-docker:2375
          - AUTOCONF_MODE=yes
          - ADMIN_USERNAME=admin
          - ADMIN_PASSWORD=changeme
          - ABSOLUTE_URI=http://www.example.com/changeme/
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_UI=yes"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme/"
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
          - "bunkerweb.REVERSE_PROXY_HEADERS=X-Script-Name /changeme"
          - "bunkerweb.INTERCEPTED_ERROR_CODES=400 404 405 413 429 500 501 502 503 504"

    volumes:
      bw-data:

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

=== "Swarm"

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

    The following environment variables are used to configure the web UI container :

    - `ADMIN_USERNAME` : username to access the web UI
    - `ADMIN_PASSWORD` : password to access the web UI
    - `ABSOLUTE_URI` : full URI of your web UI instance (like `http://www.example.com/foo/`)

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md#protect-http-applications). We recommend you to connect BunkerWeb and web UI using a dedicated network (like `bw-universe` also used by the scheduler and autoconf) so it won't be on the same network of your web services for obvious security reasons. Please note that the web UI container is listening on the `7000` port.

    !!! info "Database backend"

        If you want another Database backend than MariaDB please refer to the stack files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/misc/integrations) of the repository.

    Here is the stack boilerplate that you can use (don't forget to edit the `changeme` data) :

    ```yaml
    version: "3.5"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.5.0
        ports:
          - published: 80
            target: 8080
            mode: host
            protocol: tcp
          - published: 443
            target: 8443
            mode: host
            protocol: tcp
        environment:
          - SERVER_NAME=
          - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db
          - SWARM_MODE=yes
          - MULTISITE=yes
          - USE_REDIS=yes
          - REDIS_HOST=bw-redis
          - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
        networks:
          - bw-universe
          - bw-services
        deploy:
          mode: global
          placement:
            constraints:
              - "node.role == worker"
          labels:
            - "bunkerweb.INSTANCE"

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.5.0
        environment:
          - SWARM_MODE=yes
          - DOCKER_HOST=tcp://bw-docker:2375
          - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db
        networks:
          - bw-universe
          - bw-docker

      bw-docker:
        image: tecnativa/docker-socket-proxy
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          - CONFIGS=1
          - CONTAINERS=1
          - SERVICES=1
          - SWARM=1
          - TASKS=1
        networks:
          - bw-docker
        deploy:
          placement:
            constraints:
              - "node.role == manager"

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.5.0
        environment:
          - SWARM_MODE=yes
          - DOCKER_HOST=tcp://bw-docker:2375
          - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db
        networks:
          - bw-universe
          - bw-docker

      bw-db:
        image: mariadb:10.10
        environment:
          - MYSQL_RANDOM_ROOT_PASSWORD=yes
          - MYSQL_DATABASE=db
          - MYSQL_USER=bunkerweb
          - MYSQL_PASSWORD=changeme
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-docker

      bw-redis:
        image: redis:7-alpine
        networks:
          - bw-universe

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.5.0
        environment:
          - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db # Remember to set a stronger password for the database
          - DOCKER_HOST=tcp://bw-docker:2375
          - ADMIN_USERNAME=changeme
          - ADMIN_PASSWORD=changeme # Remember to set a stronger password for the changeme user
          - ABSOLUTE_URI=http://www.example.com/changeme/
        networks:
          - bw-universe
          - bw-docker
        deploy:
          labels:
            - "bunkerweb.SERVER_NAME=www.example.com"
            - "bunkerweb.USE_UI=yes"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_URL=/changeme/"
            - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
            - "bunkerweb.REVERSE_PROXY_HEADERS=X-Script-Name /changeme"
            - "bunkerweb.REVERSE_PROXY_INTERCEPT_ERRORS=no"
            - "INTERCEPTED_ERROR_CODES=400 404 405 413 429 500 501 502 503 504"

    volumes:
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
    ```

=== "Kubernetes"

    The web UI can be deployed using a dedicated container which is available on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) as a standard [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).

    The following environment variables are used to configure the web UI container :

    - `ADMIN_USERNAME` : username to access the web UI
    - `ADMIN_PASSWORD` : password to access the web UI
    - `ABSOLUTE_URI` : full URI of your web UI instance (like `http://www.example.com/foo/`)

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md#protect-http-applications). Network segmentation between web UI and web services is not covered in this documentation. Please note that the web UI container is listening on the `7000` port.

    !!! info "Database backend"

        If you want another Database backend than MariaDB please refer to the yaml files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/misc/integrations) of the repository.

    Here is the yaml boilerplate that you can use (don't forget to edit the `changeme` data) :

    ```yaml
    apiVersion: rbac.authorization.k8s.io/v1
    kind: ClusterRole
    metadata:
      name: cr-bunkerweb
    rules:
      - apiGroups: [""]
        resources: ["services", "pods", "configmaps"]
        verbs: ["get", "watch", "list"]
      - apiGroups: ["networking.k8s.io"]
        resources: ["ingresses"]
        verbs: ["get", "watch", "list"]
    ---
    apiVersion: v1
    kind: ServiceAccount
    metadata:
      name: sa-bunkerweb
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
          containers:
            # using bunkerweb as name is mandatory
            - name: bunkerweb
              image: bunkerity/bunkerweb:1.5.0
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
                - name: USE_API
                  value: "yes"
                # 10.0.0.0/8 is the cluster internal subnet
                - name: API_WHITELIST_IP
                  value: "127.0.0.0/8 10.0.0.0/8"
                - name: SERVER_NAME
                  value: ""
                - name: MULTISITE
                  value: "yes"
                - name: USE_REDIS
                  value: "yes"
                - name: REDIS_HOST
                  value: "svc-bunkerweb-redis.default.svc.cluster.local"
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
              image: bunkerity/bunkerweb-autoconf:1.5.0
              imagePullPolicy: Always
              env:
                - name: KUBERNETES_MODE
                  value: "yes"
                - name: "DATABASE_URI"
                  value: "mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db"
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
              image: bunkerity/bunkerweb-scheduler:1.5.0
              imagePullPolicy: Always
              env:
                - name: KUBERNETES_MODE
                  value: "yes"
                - name: "DATABASE_URI"
                  value: "mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db"
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
              image: mariadb:10.10
              imagePullPolicy: Always
              env:
                - name: MYSQL_RANDOM_ROOT_PASSWORD
                  value: "yes"
                - name: "MYSQL_DATABASE"
                  value: "db"
                - name: "MYSQL_USER"
                  value: "bunkerweb"
                - name: "MYSQL_PASSWORD"
                  value: "changeme"
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
          containers:
            - name: bunkerweb-ui
              image: bunkerity/bunkerweb-ui:1.5.0
              imagePullPolicy: Always
              env:
                - name: ADMIN_USERNAME
                  value: "changeme"
                - name: "ADMIN_PASSWORD"
                  value: "changeme"
                - name: "ABSOLUTE_URI"
                  value: "http://www.example.com/changeme/"
                - name: KUBERNETES_MODE
                  value: "YES"
                - name: "DATABASE_URI"
                  value: "mariadb+pymysql://bunkerweb:testor@svc-bunkerweb-db:3306/db"
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
      volumeName: pv-bunkerweb
    ---
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      annotations:
        bunkerweb.io/www.example.com_USE_UI: "yes"
        bunkerweb.io/www.example.com_REVERSE_PROXY_HEADERS_1: "X-Script-Name /changeme"
        bunkerweb.io/www.example.com_REVERSE_PROXY_INTERCEPT_ERRORS: "no"
    spec:
      rules:
        - host: www.example.com
          http:
            paths:
              - path: /changeme/
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
    systemctl enable bunkerweb
    ```

    A dedicated environment file located at `/etc/bunkerweb/ui.env` is used to configure the web UI :

    ```conf
    ADMIN_USERNAME=changeme
    ADMIN_PASSWORD=changeme
    ABSOLUTE_URI=http://www.example.com/changeme/
    ```

    Each time you edit the `/etc/bunkerweb/ui.env` file, you will need to restart the service :

    ```shell
    systemctl restart bunkerweb-ui
    ```

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md#protect-http-applications). Please note that the web UI is listening on the `7000` port and only on the loopback interface.

    Here is the `/etc/bunkerweb/variables.env` boilerplate you can use :

    ```conf
    API_LISTEN_IP=127.0.0.1
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_UI=yes
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/changeme/
    www.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:7000
    www.example.com_REVERSE_PROXY_HEADERS=X-Script-Name /changeme
    www.example.com_INTERCEPTED_ERROR_CODES=400 404 405 413 429 500 501 502 503 504
    ```

    Don't forget to restart the `bunkerweb` service :

    ```shell
    systemctl restart bunkerweb
    ```

=== "Ansible"

    The installation of the web UI using the [Vagrant integration](integrations.md#linux) is pretty straightforward because it is installed with BunkerWeb.

    Create a `my_ui.env` filed used to configure the web UI :

    ```conf
    ADMIN_USERNAME=changeme
    ADMIN_PASSWORD=changeme
    ABSOLUTE_URI=http://www.example.com/changeme/
    ```

    Here is the `my_variables.env` boilerplate you can use :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_UI=yes
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/changeme/
    www.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:7000
    www.example.com_REVERSE_PROXY_HEADERS=X-Script-Name /changeme
    www.example.com_INTERCEPTED_ERROR_CODES=400 404 405 413 429 500 501 502 503 504
    ```

    The variable `enable_ui` can be set to `true` in order to activate the web UI service and the variable `custom_ui` can be used to specify the configuration file for the web UI :

    ```ini
    [mybunkers]
    192.168.0.42 variables_env="{{ playbook_dir }}/my_variables.env" enable_ui=true custom_ui="{{ playbook_dir }}/my_ui.env"
    ```

    Or alternatively, in your playbook file :

    ```yaml
    - hosts: all
      become: true
      vars:
      - variables_env: "{{ playbook_dir }}/my_variables.env"
      - enable_ui: true
      - custom_ui: "{{ playbook_dir }}/my_ui.env"
      roles:
      - bunkerity.bunkerweb
    ```


    You can now run the playbook and be able to access the web UI :

    ```shell
    ansible-playbook -i inventory.yml playbook.yml
    ```

=== "Vagrant"

    The installation of the web UI using the [Vagrant integration](integrations.md#vagrant) is pretty straightforward because it is installed with BunkerWeb.

    First of all, you will need to get a shell on your Vagrant box :

    ```shell
    vagrant ssh
    ```

    The web UI comes as systemd service named `bunkerweb-ui` which is not enabled by default. If you want to start the web UI when on startup you can run the following command :

    ```shell
    systemctl enable bunkerweb
    ```

    A dedicated environment file located at `/etc/bunkerweb/ui.env` is used to configure the web UI :

    ```conf
    ADMIN_USERNAME=changeme
    ADMIN_PASSWORD=changeme
    ABSOLUTE_URI=http://www.example.com/changeme/
    ```

    Each time you edit the `/etc/bunkerweb/ui.env` file, you will need to restart the service :

    ```shell
    systemctl restart bunkerweb-ui
    ```

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md#protect-http-applications). Please note that the web UI is listening on the `7000` port and only on the loopback interface.

    Here is the `/etc/bunkerweb/variables.env` boilerplate you can use :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_UI=yes
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/changeme/
    www.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:7000
    www.example.com_REVERSE_PROXY_HEADERS=X-Script-Name /changeme
    www.example.com_INTERCEPTED_ERROR_CODES=400 404 405 413 429 500 501 502 503 504
    ```

    Don't forget to restart the `bunkerweb` service :

    ```shell
    systemctl restart bunkerweb
    ```