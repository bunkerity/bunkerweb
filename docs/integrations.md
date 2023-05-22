# Integrations

## Docker

<figure markdown>
  ![Overview](assets/img/integration-docker.svg){ align=center, width="600" }
  <figcaption>Docker integration</figcaption>
</figure>

Using BunkerWeb as a [Docker](https://www.docker.com/) container is a quick and easy way to test and use it as long as you are familiar with the Docker technology.

We provide ready-to-use prebuilt images for x64, x86 armv8 and armv7 architectures on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb) :

```shell
docker pull bunkerity/bunkerweb:1.5.0
```

Alternatively, you can build the Docker image directly from the [source](https://github.com/bunkerity/bunkerweb) (and get a coffee ☕ because it may take a long time depending on your hardware) :

```shell
git clone https://github.com/bunkerity/bunkerweb.git && \
cd bunkerweb && \
docker build -t my-bunkerweb -f src/bunkerweb/Dockerfile .
```

Docker integration key concepts are :

- **Environment variables** to configure BunkerWeb
- **Scheduler** container to store configuration and execute jobs
- **Networks** to expose ports for clients and connect to upstream web services

!!! info "Database backend"
    Please note that we assume you are using SQLite as database backend (which is the default for the `DATABASE_URI` setting). Other backends for this integration are still possible if you want to : see docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/misc/integrations) folder of the repostiory for more information.

### Environment variables

Settings are passed to BunkerWeb using Docker environment variables :

```yaml
...
services:
  mybunker:
    image: bunkerity/bunkerweb:1.5.0
    labels:
      - "bunkerweb.INSTANCE"
    environment:
      - MY_SETTING=value
      - ANOTHER_SETTING=another value
...
```

Please note that the `bunkerweb.INSTANCE` is mandatory to make sure the scheduler can detect BunkerWeb instance(s).

!!! info "Full list"
    For the complete list of environment variables, see the [settings section](settings.md) of the documentation.

### Scheduler

The [scheduler](concepts.md#scheduler) is executed in its own container which is also available on Docker Hub :

```shell
docker pull bunkerity/bunkerweb-scheduler:1.5.0
```

Alternatively, you can build the Docker image directly from the [source](https://github.com/bunkerity/bunkerweb) (less coffee ☕ needed than BunkerWeb image) :

```shell
git clone https://github.com/bunkerity/bunkerweb.git && \
cd bunkerweb && \
docker build -t my-scheduler -f src/scheduler/Dockerfile .
```

A volume is needed to store the SQLite database that will be used by the scheduler :

```yaml
...
services:
  mybunker:
    image: bunkerity/bunkerweb-scheduler:1.5.0
    volumes:
      - bw-data:/data
...
volumes:
  bw-data:
```

!!! warning "Using local folder for persistent data"

    The scheduler runs as an **unprivileged user with UID 101 and GID 101** inside the container. The reason behind this is security : in case a vulnerability is exploited, the attacker won't have full root (UID/GID 0) privileges.
    But there is a downside : if you use a **local folder for the persistent data**, you will need to **set the correct permissions** so the unprivileged user can write data to it. Something like that should do the trick :

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    Alternatively, if the folder already exists :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) or [podman](https://podman.io/), UIDs and GIDs in the container will be mapped to different ones in the host. You will first need to check your initial subuid and subgid :

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    For example, if you have a value of **100000**, the mapped UID/GID will be **100100** (100000 + 100) :
  
    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```
	
	  Or if the folder already exists :
  
	  ```shell
    sudo chgrp -R 100100 bw-data && \
    chmod -R 770 bw-data
    ```

When using Docker-based integrations, the scheduler will need to access the Docker API to get things working which is defined using the `DOCKER_HOST` environment variable.

!!! warning "Docker API access and security"

    Since Docker doesn't support fine-grained authorizations, accessing the API poses a security risk. An attacker with access to the API can easily gain root privileges on the host machine (more info [here](https://blog.quarkslab.com/why-is-exposing-the-docker-socket-a-really-bad-idea.html)).

    We strongly recommend not to mount the socket file usually located at `/var/run/docker.sock` directly in the container. An alternative, which is described here, is to use a "proxy" container like [tecnativa/docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy) that will allow only the necessary API calls.

You will need to create the Docker API proxy container, mount the socket and set the `DOCKER_HOST` environment variable to use the Docker API proxy :

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.5.0
    env:
      - DOCKER_HOST=tcp://bw-docker:2375
...
  bw-docker:
    image: tecnativa/docker-socket-proxy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - CONTAINERS=1
...
```

!!! warning "Docker socket in rootless mode"
    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless), you will need to replace the mount of the docker socket with the following value : `$XDG_RUNTIME_DIR/docker.sock:/var/run/docker.sock:ro`.

### Networks

By default, BunkerWeb container is listening (inside the container) on **8080/tcp** for **HTTP** and **8443/tcp** for **HTTPS**.

!!! warning "Privileged ports in rootless mode or when using podman"
    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) and want to redirect privileged ports (< 1024) like 80 and 443 to BunkerWeb, please refer to the prerequisites [here](https://docs.docker.com/engine/security/rootless/#exposing-privileged-ports).
	
    If you are using [podman](https://podman.io/) you can lower the minimum number for unprivileged ports :
    ```shell
    sudo sysctl net.ipv4.ip_unprivileged_port_start=1
    ```

The typical BunkerWeb stack when using the Docker integration contains the following containers :

- BunkerWeb
- Scheduler
- Docker socket proxy
- Your services

For defense in depth purposes, we strongly recommend to create at least three different Docker networks :

- `bw-services` : for BunkerWeb and your web services
- `bw-universe` : for BunkerWeb and scheduler
- `bw-docker` : for scheduler and the Docker API proxy

The scheduler needs to contact the API of BunkerWeb and for obvious security reason BunkerWeb needs to check if the caller is authorized to make API calls. The `API_WHITELIST_IP` setting lets you choose allowed IP addresses and subnets, usage of a static subnet for the `bw-universe` is strongly advised :

```yaml
...
services:
  mybunker:
    image: bunkerity/bunkerweb:1.5.0
    ports:
      - 80:8080
      - 443:8443
    networks:
      - bw-services
      - bw-universe
...
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.5.0
    networks:
      - bw-universe
      - bw-docker
...
  bw-docker:
    image: tecnativa/docker-socket-proxy
    networks:
      - bw-docker
...
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

### Full compose file

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
      - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.5.0
    depends_on:
      - bunkerweb
      - bw-docker
    volumes:
      - bw-data:/data
    environment:
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

## Docker autoconf

<figure markdown>
  ![Overview](assets/img/integration-autoconf.svg){ align=center, width="600" }
  <figcaption>Docker autoconf integration</figcaption>
</figure>

!!! info "Docker integration"
    The Docker autoconf integration is an "evolution" of the Docker one. Please read the [Docker integration section](#docker) first if needed.

The downside of using environment variables is that the container needs to be recreated each time there is an update which is not very convenient. To counter that issue, you can use another image called **autoconf** which will listen for Docker events and automatically reconfigure BunkerWeb in real-time without recreating the container.

Instead of defining environment variables for the BunkerWeb container, you simply add **labels** to your web applications containers and the **autoconf** will "automagically" take care of the rest.

!!! info "Multisite mode"
    The Docker autoconf integration implies the use of **multisite mode**. Please refer to the [multisite section](concepts.md#multisite-mode) of the documentation for more information.

!!! info "Database backend"
    Please note that we assume you are using MariaDB as database backend (which is defined using the `DATABASE_URI` setting). Other backends for this integration are still possible if you want : see docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/misc/integrations) folder of the repostiory for more information.

Another container, named `bw-autoconf` for example, containing the autoconf service must be added to the stack. Since two services will generate the configuration for BunkerWeb, a "real" database backend (in other words, not SQLite) also needs to be added :

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

!!! warning "Using Docker in rootless mode"
    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless), you will need to replace the mount of the docker socket with the following value : `$XDG_RUNTIME_DIR/docker.sock:/var/run/docker.sock:ro`.

Once the stack is set up, you will be able to create the web application container and add the settings as labels using the "bunkerweb." prefix in order to automatically set up BunkerWeb :

```yaml
version: "3.5"

services:
  myapp:
    image: mywebapp:4.2
    networks:
      bw-services:
        aliases:
          - myapp
    labels:
      - "bunkerweb.MY_SETTING_1=value1"
      - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

## Swarm

<figure markdown>
  ![Overview](assets/img/integration-swarm.svg){ align=center, width="600" }
  <figcaption>Docker Swarm integration</figcaption>
</figure>

!!! info "Docker autoconf"
    The Swarm integration is similar to the Docker autoconf one (but with services instead of containers). Please read the [Docker autoconf integration section](#docker-autoconf) first if needed.

To automatically configure BunkerWeb instances, a special service called **autoconf** needs to have access to the Docker API. That service will listen for Docker Swarm events like service creation or deletion and automatically configure the **BunkerWeb instances** in real-time without downtime. It also monitors other Swarm objects like [configs](https://docs.docker.com/engine/swarm/configs/) for custom configurations.

Like the [Docker autoconf integration](#docker-autoconf), configuration for web services is defined by using labels starting with the special **bunkerweb.** prefix.

The recommended setup is to schedule the **BunkerWeb service** as a **global service** on all nodes and the **autoconf, scheduler and Docker API proxy services** as **single replicated services**. Please note that the **Docker API proxy service** needs to be scheduled on a manager node unless you configure it to use a remote API (which is not covered in the documentation).

Since we have multiple instances of BunkerWeb running, a shared data store implemented as a [Redis](https://redis.io/) service must be created : the instances will use it to cache and share data. You will find more information about the Redis settings [here](settings.md#redis)

Using a shared folder or a specific driver for the database volume is left as an exercise for the reader (and depends on your own use-case).

!!! info "Database backend"
    Please note that we assume you are using MariaDB as database backend (which is defined using the `DATABASE_URI` setting). Other backends for this integration are still possible if you want : see docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/misc/integrations) folder of the repostiory for more information. Clustered database backends setup are out-of-the-scope of this documentation.

Here is the stack boilerplate that you can deploy using `docker stack deploy` :

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
      - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db # Remember to set a stronger password for the database
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
      - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db # Remember to set a stronger password for the database
    networks:
      - bw-universe
      - bw-docker
    deploy:
      placement:
        constraints:
          - "node.role == worker"

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
    deploy:
      placement:
        constraints:
          - "node.role == worker"

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
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-redis:
    image: redis:7-alpine
    networks:
      - bw-universe
    deploy:
      placement:
        constraints:
          - "node.role == worker"

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

Please note that the `SWARM_MODE=yes` environment variable is mandatory when using the Swarm integration.

Once the BunkerWeb Swarm stack is set up and running (see autoconf and scheduler logs for more information), you will be able to deploy web applications in the cluster and use labels to dynamically configure BunkerWeb :

```yaml
version: "3.5"

services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerweb.MY_SETTING_1=value1"
        - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

## Kubernetes

<figure markdown>
  ![Overview](assets/img/integration-kubernetes.svg){ align=center, width="600" }
  <figcaption>Kubernetes integration</figcaption>
</figure>

The autoconf acts as an [Ingress controller](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/) and will configure the BunkerWeb instances according to the [Ingress resources](https://kubernetes.io/docs/concepts/services-networking/ingress/). It also monitors other Kubernetes objects like [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) for custom configurations.

The recommended setup is to define **BunkerWeb** as a **[DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)** which will create a pod on all nodes and the **autoconf and scheduler** as **single replicated [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)**.

Since we have multiple instances of BunkerWeb running, a shared data store implemented as a [Redis](https://redis.io/) service must be created : the instances will use it to cache and share data. You will find more information about the Redis settings [here](settings.md#redis)

!!! info "Database backend"
    Please note that we assume you are using MariaDB as database backend (which is defined using the `DATABASE_URI` setting). Other backends for this integration are still possible if you want : see yaml files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/misc/integrations) folder of the repostiory for more information. Clustered database backends setup are out-of-the-scope of this documentation.

Please note that both scheduler and autoconf services needs to access the Kubernetes API. The recommended way of doing it is using [RBAC authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/).

Another important thing is the `KUBERNETES_MODE=yes` environment variable which is mandatory when using the Kubernetes integration.

Here is the yaml boilerplate you can use as a base :

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

Once the BunkerWeb Kubernetes stack is set up and running (see autoconf logs for more information), you will be able to deploy web applications in the cluster and declare your Ingress resource. Please note that [settings](settings.md) need to be set as annotations for the Ingress resource with the special value **bunkerweb.io** for the domain part :

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    bunkerweb.io/MY_SETTING: "value"
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  rules:
    - host: www.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: svc-my-app
                port:
                  number: 8000
...
```

## Linux

<figure markdown>
  ![Overview](assets/img/integration-linux.svg){ align=center, width="600" }
  <figcaption>Linux integration</figcaption>
</figure>

List of supported Linux distros (amd64/x86_64 and arm64/aarch64 architectures) :

- Debian 11 "Bullseye"
- Ubuntu 22.04 "Jammy"
- Fedora 38
- RedHat Enterprise Linux (RHEL) 8.7

Please note that you will need to **install NGINX 1.24.0 before BunkerWeb**. For all distros, except Fedora, using prebuilt packages from [official NGINX repository](https://nginx.org/en/linux_packages.html) is mandatory. Compiling NGINX from source or using packages from different repositories won't work with the official prebuilt packages of BunkerWeb but you can build it from source.

Repositories of Linux packages for BunkerWeb are available on [PackageCloud](https://packagecloud.io/bunkerity/bunkerweb). They provide a bash script to add and trust the repository automatically (but you can also follow the [manual installation](https://packagecloud.io/bunkerity/bunkerweb/install) instructions if you prefer).

=== "Debian"

    The first step is to add NGINX official repository :

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release debian-archive-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/debian `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    You should now be able to install NGINX 1.24.0 :

    ```shell
    sudo apt update && \
    sudo apt install -y nginx=1.24.0-1~$(lsb_release -cs)
    ```

    And finally install BunkerWeb 1.5.0 :

    ```shell
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo apt install -y bunkerweb=1.5.0
    ```
	
    To prevent upgrading NGINX and/or BunkerWeb packages when executing `apt upgrade`, you can use the following command :

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Ubuntu"

    The first step is to add NGINX official repository :

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    You should now be able to install NGINX 1.24.0 :

    ```shell
    sudo apt update && \
    sudo apt install -y nginx=1.24.0-1~jammy
    ```

    And finally install BunkerWeb 1.5.0 :

    ```shell
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo apt install -y bunkerweb=1.5.0
    ```
	
    To prevent upgrading NGINX and/or BunkerWeb packages when executing `apt upgrade`, you can use the following command :

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Fedora"

    Fedora already provides NGINX 1.24.0 that we support :

    ```shell
    sudo dnf install -y nginx-1.24.0
    ```

    And finally install BunkerWeb 1.5.0 :

    ```shell
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.rpm.sh | \
  	sed 's/yum install -y pygpgme --disablerepo='\''bunkerity_bunkerweb'\''/yum install -y python-gnupg/g' | \
  	sed 's/pypgpme_check=`rpm -qa | grep -qw pygpgme`/python-gnupg_check=`rpm -qa | grep -qw python-gnupg`/g' | sudo bash && \
  	sudo dnf makecache && \
  	sudo dnf install -y bunkerweb-1.5.0
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command :

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

=== "RedHat"

    The first step is to add NGINX official repository. Create the following file at `/etc/yum.repos.d/nginx.repo` :

    ```conf
    [nginx-stable]
    name=nginx stable repo
    baseurl=http://nginx.org/packages/centos/$releasever/$basearch/
    gpgcheck=1
    enabled=1
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true

    [nginx-mainline]
    name=nginx mainline repo
    baseurl=http://nginx.org/packages/mainline/centos/$releasever/$basearch/
    gpgcheck=1
    enabled=0
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true
    ```

    You should now be able to install NGINX 1.24.0 :

    ```shell
    sudo dnf install nginx-1.24.0
    ```
    And finally install BunkerWeb 1.5.0 :

    ```shell
	  dnf install -y epel-release && \
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo dnf install -y bunkerweb-1.5.0
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command :

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

<!---
=== "CentOS Stream"

    The first step is to add NGINX official repository. Create the following file at `/etc/yum.repos.d/nginx.repo` :
    ```conf
    [nginx-stable]
    name=nginx stable repo
    baseurl=http://nginx.org/packages/centos/$releasever/$basearch/
    gpgcheck=1
    enabled=1
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true
	```

    You should now be able to install NGINX 1.24.0 :
	```shell
	sudo dnf install nginx-1.24.0
	```

	And finally install BunkerWeb 1.5.0 :
    ```shell
	  dnf install -y epel-release && \
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo dnf install -y bunkerweb-1.5.0
    ```

	To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command :
	```shell
	sudo dnf versionlock add nginx && \
	sudo dnf versionlock add bunkerweb
	```


=== "From source"

    The first step is to install NGINX 1.24.0 using the repository of your choice or by [compiling it from source](https://docs.nginx.com/nginx/admin-guide/installing-nginx/installing-nginx-open-source/#compiling-and-installing-from-source).
	
	The target installation folder of BunkerWeb is located at `/usr/share/bunkerweb`, let's create it :
	```shell
	mkdir /usr/share/bunkerweb
	```
	
	You can now clone the BunkerWeb project to the `/tmp` folder :
	```shell
	https://github.com/bunkerity/bunkerweb.git /tmp/bunkerweb
	```
	
	BunkerWeb needs some dependencies to be compiled and installed to `/usr/share/bunkerweb/deps`, the easiest way to do it is by executing the [install.sh helper script](https://github.com/bunkerity/bunkerweb/blobdeps/install.sh) (please note that you will need to install additional packages which is not covered in this procedure and depends on your own system) :
	```
	mkdir /usr/share/bunkerweb/deps && \
	/tmp/bunkerweb/src/deps/install.sh
	```
	
	Additional Python dependencies needs to be installed into the `/usr/share/bunkerweb/deps/python` folder :
	```shell
	mkdir /usr/share/bunkerweb/src/deps/python && \
	pip install --no-cache-dir --require-hashes --target /usr/share/bunkerweb/deps/python -r /tmp/bunkerweb/deps/requirements.txt && \
	pip install --no-cache-dir --target /usr/share/bunkerweb/deps/python -r /tmp/bunkerweb/src/ui/requirements.txt
	```
	
	Once dependencies are installed, you will be able to copy the BunkerWeb sources to the target `/usr/share/bunkerweb` folder :
	```shell
	for src in api cli confs core gen helpers job lua misc utils ui settings.json VERSION linux/variables.env linux/ui.env linux/scripts ; do
		cp -r /tmp/bunkerweb/${src} /usr/share/bunkerweb
	done
	cp /usr/share/bunkerweb/helpers/bwcli /usr/local/bin
	```
	
	Additional folders also need to be created :
	```shell
	mkdir -p /etc/bunkerweb/{configs,plugins} && \
	mkdir -p /var/cache/bunkerweb && \
	mkdir -p /var/tmp/bunkerweb
	```
	
	Permissions needs to be fixed :
	```shell
	find /usr/share/bunkerweb -path /usr/share/bunkerweb/deps -prune -o -type f -exec chmod 0740 {} \; && \
	find /usr/share/bunkerweb -path /usr/share/bunkerweb/deps -prune -o -type d -exec chmod 0750 {} \; && \
	find /usr/share/bunkerweb/core/*/jobs/* -type f -exec chmod 750 {} \; && \
	chmod 770 /var/cache/bunkerweb /var/tmp/bunkerweb && \
	chmod 750 /usr/share/bunkerweb/gen/main.py /usr/share/bunkerweb/scheduler/main.py /usr/share/bunkerweb/cli/main.py /usr/share/bunkerweb/helpers/*.sh /usr/share/bunkerweb/scripts/*.sh /usr/bin/bwcli /usr/share/bunkerweb/ui/main.py && \
	chown -R root:nginx /usr/share/bunkerweb
	```
	
	Last but not least, you will need to set up systemd unit files :
	```shell
	cp /tmp/bunkerweb/linux/*.service /etc/systemd/system && \
	systemctl daemon-reload && \
	systemctl stop nginx && \
	systemctl disable nginx && \
	systemctl enable bunkerweb && \
	systemctl enable bunkerweb-ui
	```
--->

The configuration of BunkerWeb is done by editing the `/etc/bunkerweb/variables.env` file :

```conf
MY_SETTING_1=value1
MY_SETTING_2=value2
...
```

BunkerWeb is managed using systemctl :

- Check BunkerWeb status : `systemctl status bunkerweb`
- Start it if it's stopped : `systemctl start bunkerweb`
- Stop it if it's started : `systemctl stop bunkerweb`
- And restart : `systemctl restart bunkerweb`

## Ansible

<figure markdown>
  ![Overview](assets/img/integration-ansible.svg){ align=center, width="600" }
  <figcaption>Ansible integration</figcaption>
</figure>

List of supported Linux distros (amd64/x86_64 and arm64/aarch64 architectures) :

- Debian 11 "Bullseye"
- Ubuntu 22.04 "Jammy"
- Fedora 38
- RedHat Enterprise Linux (RHEL) 8.7

[Ansible](https://docs.ansible.com/ansible/latest/index.html) is an IT automation tool. It can configure systems, deploy software, and orchestrate more advanced IT tasks such as continuous deployments or zero downtime rolling updates.

A specific BunkerWeb Ansible role is available on [Ansible Galaxy](https://galaxy.ansible.com/bunkerity/bunkerweb).

First of all, download the role from ansible-galaxy :
```shell
ansible-galaxy install bunkerity.bunkerweb
```

Next, create an inventory by adding the IP adress or FQDN of one or more remote systems, either in `/etc/ansible/hosts` or in your own playbook `inventory.yml` :
```toml
[mybunkers]
192.0.2.50
192.0.2.51
192.0.2.52
```

The next step we're going to set up is the SSH connection so Ansible can connect to the managed nodes. Add your public SSH keys to the `authorized_keys` file on each remote system and ensure you can successfully connect. 

In order to use the role, we will create the playbook file named `playbook.yml` for example :
```yaml
---
- hosts: all
  become: true
  roles:
    - bunkerity.bunkerweb
```

Run the playbook :
```shell
ansible-playbook -i inventory.yml playbook.yml
```

Configuration of BunkerWeb is done by using specific role variables :

| Name  | Type  | Description  | Default value  |
|:-----:|:-----:|--------------|----------------|
| `bunkerweb_version` | string | Version of BunkerWeb to install. | `1.5.0` |
| `nginx_version` | string | Version of NGINX to install. | `1.24.0` |
| `freeze_versions` | boolean | Prevent upgrade of BunkerWeb and NGINX when performing packages upgrades. | `true` |
| `variables_env` | string | Path of the variables.env file to configure BunkerWeb. | `files/variables.env` |
| `enable_ui` | boolean | Activate the web UI. | `false` |
| `custom_ui` | string | Path of the ui.env file to configure the web UI. | `files/ui.env` |
| `custom_configs_path` | Dictionary | Each entry is a path of the folder containing custom configurations. Keys are the type of custom configs : `http`, `server-http`, `modsec`, `modsec-crs` and `default-server-http` | empty values |
| `custom_www` | string | Path of the www directory to upload. | empty value |
| `custom_plugins` | string | Path of the plugins directory to upload. | empty value |
| `custom_www_owner` | string | Default owner for www files and folders. | `nginx` |
| `custom_www_group` | string | Default group for www files and folders. | `nginx` |

## Vagrant

<!-- TODO
<figure markdown>
  ![Overview](assets/img/integration-vagrant.svg){ align=center }
  <figcaption>BunkerWeb integration with Vagrant</figcaption>
</figure>
-->
List of supported providers :

- vmware_desktop 
- virtualbox 
- libvirt

**_Note on Supported Base Images_**  

Please be aware that the provided Vagrant boxes are based **exclusively on Ubuntu 22.04 "Jammy"**. While BunkerWeb supports other Linux distributions, the Vagrant setup currently only supports Ubuntu 22.04 as the base operating system. This ensures a consistent and reliable environment for users who want to deploy BunkerWeb using Vagrant.

Similar to other BunkerWeb integrations, the Vagrant setup uses **NGINX version 1.24.0**. This specific version is required to ensure compatibility and smooth functioning with BunkerWeb. Additionally, the Vagrant box includes **PHP** pre-installed, providing a ready-to-use environment for hosting PHP-based applications alongside BunkerWeb.

By using the provided Vagrant box based on Ubuntu 22.04 "Jammy", you benefit from a well-configured and integrated setup, allowing you to focus on developing and securing your applications with BunkerWeb without worrying about the underlying infrastructure.

Here are the steps to install BunkerWeb using Vagrant on Ubuntu with the supported virtualization providers (VirtualBox, VMware, and libvirt):


1. Make sure you have Vagrant and one of the supported virtualization providers (VirtualBox, VMware, or libvirt) installed on your system.
2. There are two ways to install the Vagrant box with BunkerWeb: either by using a provided Vagrantfile to configure your virtual machine or by creating a new box based on the existing BunkerWeb Vagrant box, offering you flexibility in how you set up your development environment.

=== "Vagrantfile"

    ```shell
    Vagrant.configure("2") do |config|
      config.vm.box = "bunkerity/bunkerweb"
    end
    ```

    Depending on the virtualization provider you choose, you may need to install additional plugins:

    * For **VMware**, install the `vagrant-vmware-desktop` plugin. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).
    * For **libvirt**, install the `vagrant-libvirt plugin`. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).
    * For **VirtualBox**, install the `vagrant-vbguest` plugin. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).

=== "New Vagrant Box"

    ```shell
    vagrant init bunkerity/bunkerweb
    ```

    Depending on the virtualization provider you choose, you may need to install additional plugins:

    * For **VMware**, install the `vagrant-vmware-desktop` plugin. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).
    * For **libvirt**, install the `vagrant-libvirt plugin`. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).
    * For **VirtualBox**, install the `vagrant-vbguest` plugin. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).

After installing the necessary plugins for your chosen virtualization provider, run the following command to start the virtual machine and install BunkerWeb:

```shell
vagrant up --provider=virtualbox # or --provider=vmware_desktop or --provider=libvirt
```

Finally, to access the virtual machine using SSH, execute the following command:

```shell
vagrant ssh
```

**Example Vagrantfile**

  Here is an example `Vagrantfile` for installing BunkerWeb on Ubuntu 22.04 "Jammy" using the different supported virtualization providers:

```shell
Vagrant.configure("2") do |config|
  # Ubuntu 22.04 "Jammy"
  config.vm.box = "bunkerity/bunkerweb"
  # Uncomment the desired virtualization provider
  # For VirtualBox (default)
  config.vm.provider "virtualbox"
  # For VMware
  # config.vm.provider "vmware_desktop" # Windows
  # config.vm.provider "vmware_workstation" # Linux
  # For libvirt
  # config.vm.provider "libvirt"
end
```