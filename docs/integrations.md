# Integrations

## Docker

<figure markdown>
  ![Overview](assets/img/integration-docker.svg){ align=center, width="600" }
  <figcaption>Docker integration</figcaption>
</figure>

Utilizing BunkerWeb as a [Docker](https://www.docker.com/) container offers a convenient and straightforward approach for testing and utilizing the solution, particularly if you are already familiar with Docker technology.

To facilitate your Docker deployment, we provide readily available prebuilt images on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb), supporting multiple architectures. These prebuilt images are optimized and prepared for use on the following architectures:

- x64 (64-bit)
- x86
- armv8 (ARM 64-bit)
- armv7 (ARM 32-bit)

By accessing these prebuilt images from Docker Hub, you can quickly pull and run BunkerWeb within your Docker environment, eliminating the need for extensive configuration or setup processes. This streamlined approach allows you to focus on leveraging the capabilities of BunkerWeb without unnecessary complexities.

Whether you're conducting tests, developing applications, or deploying BunkerWeb in production, the Docker containerization option provides flexibility and ease of use. Embracing this method empowers you to take full advantage of BunkerWeb's features while leveraging the benefits of Docker technology.

```shell
docker pull bunkerity/bunkerweb:1.5.7
```

Docker images are also available on [GitHub packages](https://github.com/orgs/bunkerity/packages?repo_name=bunkerweb) and can be downloaded using the `ghcr.io` repository address :

```shell
docker pull ghcr.io/bunkerity/bunkerweb:1.5.7
```

Alternatively, if you prefer a more hands-on approach, you have the option to build the Docker image directly from the [source](https://github.com/bunkerity/bunkerweb). Building the image from source gives you greater control and customization over the deployment process. However, please note that this method may take some time to complete, depending on your hardware configuration.

While the image is being built, you can take a moment to relax and enjoy a cup of coffee ☕, as the process may require some patience. Once the image is successfully built, you can proceed to deploy and utilize BunkerWeb within your Docker environment. This method allows you to tailor the image to your specific requirements and ensures a more personalized deployment of BunkerWeb.

So, whether you choose to use the ready-to-use prebuilt images or embark on the journey of building the image from source, BunkerWeb in Docker provides you with the flexibility and options to seamlessly integrate it into your environment.

```shell
git clone https://github.com/bunkerity/bunkerweb.git && \
cd bunkerweb && \
docker build -t my-bunkerweb -f src/bunkerweb/Dockerfile .
```

Docker integration key concepts are :

- **Environment variables** to configure BunkerWeb
- **Scheduler** container to store configuration and execute jobs
- **Networks** to expose ports for clients and connect to upstream web services

When integrating BunkerWeb with Docker, there are key concepts to keep in mind, ensuring a smooth and efficient deployment:

- **Environment variables**: BunkerWeb can be easily configured using environment variables. These variables allow you to customize various aspects of BunkerWeb's behavior, such as network settings, security options, and other parameters.

- **Scheduler container**: To effectively manage the configuration and execution of jobs, BunkerWeb utilizes a dedicated container called the [scheduler](concepts.md#scheduler).

- **Networks**: Docker networks play a vital role in the integration of BunkerWeb. These networks serve two main purposes: exposing ports to clients and connecting to upstream web services. By exposing ports, BunkerWeb can accept incoming requests from clients, allowing them to access the protected web services. Additionally, by connecting to upstream web services, BunkerWeb can efficiently route and manage the traffic, providing enhanced security and performance.

!!! info "Database backend"
    Please be aware that our instructions assume you are using SQLite as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.7/misc/integrations) folder of the repository for more information.

### Environment variables

Settings are passed to BunkerWeb using Docker environment variables :

```yaml
...
services:
  mybunker:
    image: bunkerity/bunkerweb:1.5.7
    labels:
      - "bunkerweb.INSTANCE=yes"
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
docker pull bunkerity/bunkerweb-scheduler:1.5.7
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
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.5.7
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
    Due to Docker's limitations in supporting fine-grained authorizations, it's important to be aware of the potential security risks associated with accessing the API directly. Accessing the Docker API can pose a threat, as an attacker with API access can potentially obtain root privileges on the host machine. For more detailed information on this topic, we encourage you to refer to the provided link ([here](https://blog.quarkslab.com/why-is-exposing-the-docker-socket-a-really-bad-idea.html)).

    To mitigate these risks, we strongly advise against directly mounting the socket file located at `/var/run/docker.sock` within the BunkerWeb container. Instead, we recommend employing an alternative approach that enhances security. One such approach involves using a "proxy" container, such as `tecnativa/docker-socket-proxy`, which acts as an intermediary and allows only necessary API calls.

    By adopting this proxy container strategy, you can establish a more secure communication channel with the Docker API, minimizing the potential attack surface and enhancing overall system security.

You will need to create the Docker API proxy container, mount the socket and set the `DOCKER_HOST` environment variable to use the Docker API proxy :

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.5.7
    env:
      - DOCKER_HOST=tcp://bw-docker:2375
...
  bw-docker:
    image: tecnativa/docker-socket-proxy:nightly
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - CONTAINERS=1
      - LOG_LEVEL=warning
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

To secure the communication between the scheduler and BunkerWeb API, it is important to authorize API calls. You can use the `API_WHITELIST_IP` setting to specify allowed IP addresses and subnets. It is strongly recommended to use a static subnet for the `bw-universe` network to enhance security. By implementing these measures, you can ensure that only authorized sources can access the BunkerWeb API, reducing the risk of unauthorized access or malicious activities:

```yaml
...
services:
  mybunker:
    image: bunkerity/bunkerweb:1.5.7
    ports:
      - 80:8080
      - 443:8443
    networks:
      - bw-services
      - bw-universe
...
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.5.7
    networks:
      - bw-universe
      - bw-docker
...
  bw-docker:
    image: tecnativa/docker-socket-proxy:nightly
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
    image: bunkerity/bunkerweb:1.5.7
    ports:
      - 80:8080
      - 443:8443
    labels:
      - "bunkerweb.INSTANCE=yes"
    environment:
      - SERVER_NAME=www.example.com
      - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.5.7
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
    image: tecnativa/docker-socket-proxy:nightly
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - CONTAINERS=1
      - LOG_LEVEL=warning
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

An alternative approach is available to address the inconvenience of recreating the container every time there is an update. By utilizing another image called **autoconf**, you can automate the real-time reconfiguration of BunkerWeb without the need for container recreation.

To leverage this functionality, instead of defining environment variables for the BunkerWeb container, you can add **labels** to your web application containers. The **autoconf** image will then listen for Docker events and seamlessly handle the configuration updates for BunkerWeb.

This "automagical" process simplifies the management of BunkerWeb configurations. By adding labels to your web application containers, you can delegate the reconfiguration tasks to **autoconf** without the manual intervention of container recreation. This streamlines the update process and enhances convenience.

By adopting this approach, you can enjoy real-time reconfiguration of BunkerWeb without the hassle of container recreation, making it more efficient and user-friendly.

!!! info "Multisite mode"
    The Docker autoconf integration implies the use of **multisite mode**. Please refer to the [multisite section](concepts.md#multisite-mode) of the documentation for more information.

!!! info "Database backend"
    Please be aware that our instructions assume you are using MariaDB as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.7/misc/integrations) folder of the repository for more information.

To enable automated configuration updates, include an additional container called `bw-autoconf` in the stack. This container hosts the autoconf service, which manages dynamic configuration changes for BunkerWeb. To support this functionality, use a dedicated "real" database backend (e.g., MariaDB, MySQL, or PostgreSQL) for synchronized configuration storage. By integrating `bw-autoconf` and a suitable database backend, you establish the infrastructure for seamless automated configuration management in BunkerWeb.

```yaml
version: "3.5"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.5.7
    ports:
      - 80:8080
      - 443:8443
    labels:
      - "bunkerweb.INSTANCE=yes"
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
    image: bunkerity/bunkerweb-autoconf:1.5.7
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
    image: bunkerity/bunkerweb-scheduler:1.5.7
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
    image: tecnativa/docker-socket-proxy:nightly
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - CONTAINERS=1
      - LOG_LEVEL=warning
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

!!! info "Database in the `bw-docker` network"
    The database container is intentionally not included in the `bw-universe` network. It is used by the `bw-autoconf` and `bw-scheduler` containers rather than directly by BunkerWeb. Therefore, the database container is part of the `bw-docker` network, which enhances security by making external access to the database more challenging. This deliberate design choice helps safeguard the database and strengthens the overall security perspective of the system.

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

To enable automatic configuration of BunkerWeb instances, the **autoconf** service requires access to the Docker API. This service listens for Docker Swarm events, such as service creation or deletion, and seamlessly configures the **BunkerWeb instances** in real-time without any downtime. It also monitors other Swarm objects, such as [configs](https://docs.docker.com/engine/swarm/configs/), for custom configurations.

Similar to the [Docker autoconf integration](#docker-autoconf), configuration for web services is defined using labels that start with the **bunkerweb**  prefix.

For an optimal setup, it is recommended to schedule the **BunkerWeb service** as a ***global service*** on all nodes, while the **autoconf, scheduler, and Docker API proxy services** should be scheduled as ***single replicated services***. Please note that the Docker API proxy service needs to be scheduled on a manager node unless you configure it to use a remote API (which is not covered in the documentation).

Since multiple instances of BunkerWeb are running, a shared data store implemented as a [Redis](https://redis.io/) service must be created. These instances will utilize the Redis service to cache and share data. Further details regarding the Redis settings can be found [here](settings.md#redis).

As for the database volume, the documentation does not specify a specific approach. Choosing either a shared folder or a specific driver for the database volume is dependent on your unique use-case and is left as an exercise for the reader.

!!! info "Database backend"
    Please be aware that our instructions assume you are using MariaDB as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.7/misc/integrations) folder of the repository for more information.

    Clustered database backends setup are out-of-the-scope of this documentation.

Here is the stack boilerplate that you can deploy using `docker stack deploy` :

```yaml
version: "3.5"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.5.7
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
        - "bunkerweb.INSTANCE=yes"

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.5.7
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
    image: tecnativa/docker-socket-proxy:nightly
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - CONFIGS=1
      - CONTAINERS=1
      - SERVICES=1
      - SWARM=1
      - TASKS=1
      - LOG_LEVEL=warning
    networks:
      - bw-docker
    deploy:
      placement:
        constraints:
          - "node.role == manager"

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.5.7
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

!!! info "Swarm mandatory setting"
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

To automate the configuration of BunkerWeb instances in a Kubernetes environment, the autoconf service serves as an [Ingress controller](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/). It configures the BunkerWeb instances based on [Ingress resources](https://kubernetes.io/docs/concepts/services-networking/ingress/) and also monitors other Kubernetes objects, such as [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/), for custom configurations.

For an optimal setup, it is recommended to define BunkerWeb as a **[DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)**, which ensures that a pod is created on all nodes, while the **autoconf and scheduler** are defined as **single replicated [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)**.

Given the presence of multiple BunkerWeb instances, it is necessary to establish a shared data store implemented as a [Redis](https://redis.io/) service. This Redis service will be utilized by the instances to cache and share data among themselves. Further information about the Redis settings can be found [here](settings.md#redis).

!!! info "Database backend"
    Please be aware that our instructions assume you are using MariaDB as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.7/misc/integrations) folder of the repository for more information.

    Clustered database backends setup are out-of-the-scope of this documentation.

Please ensure that both the scheduler and autoconf services have access to the Kubernetes API. It is recommended to utilize [RBAC authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) for this purpose.

Additionally, it is crucial to set the `KUBERNETES_MODE` environment variable to `yes` when utilizing the Kubernetes integration. This variable is mandatory for proper functionality.

To assist you, here is a YAML boilerplate that can serve as a foundation for your configuration:

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
          image: bunkerity/bunkerweb:1.5.7
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
          image: bunkerity/bunkerweb-autoconf:1.5.7
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
          image: bunkerity/bunkerweb-scheduler:1.5.7
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

Once the BunkerWeb Kubernetes stack is successfully set up and operational (refer to the autoconf logs for detailed information), you can proceed with deploying web applications within the cluster and declaring your Ingress resource.

It is important to note that the BunkerWeb settings need to be specified as annotations for the Ingress resource. For the domain part, please use the special value "**bunkerweb.io**". By including the appropriate annotations, you can configure BunkerWeb accordingly for the Ingress resource.

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

Supported Linux distributions for BunkerWeb (amd64/x86_64 and arm64/aarch64 architectures) include:

- Debian 12 "Bookworm"
- Ubuntu 22.04 "Jammy"
- Ubuntu 24.04 "Noble"
- Fedora 39
- Red Hat Enterprise Linux (RHEL) 8.9
- Red Hat Enterprise Linux (RHEL) 9.3

Please ensure that you have **NGINX 1.24.0 installed before installing BunkerWeb**. For all distributions, except Fedora, it is mandatory to use prebuilt packages from the [official NGINX repository](https://nginx.org/en/linux_packages.html). Compiling NGINX from source or using packages from different repositories will not work with the official prebuilt packages of BunkerWeb. However, you have the option to build BunkerWeb from source.

To simplify the installation process, Linux package repositories for BunkerWeb are available on [PackageCloud](https://packagecloud.io/bunkerity/bunkerweb). They provide a bash script that automatically adds and trusts the repository. You can follow the provided script for automatic setup, or opt for [manual installation](https://packagecloud.io/bunkerity/bunkerweb/install) instructions if you prefer.

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

    !!! warning "Testing/dev version"
        If you use the `testing` or `dev` version, you will need to add the `force-bad-version` directive to your `/etc/dpkg/dpkg.cfg` file before installing BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    Optional step : if you want to automatically enable the [setup wizard](web-ui.md#setup-wizard) when BunkerWeb is installed, export the following variable :

    ```shell
    export UI_WIZARD=1
    ```

    And finally install BunkerWeb 1.5.7 :

    ```shell
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y bunkerweb=1.5.7
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `apt upgrade`, you can use the following command :

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Ubuntu"

    !!! example "Specifications for Ubuntu 24.04"
        As of Ubuntu 24.04, the `nginx` package is not available in the official repository. You will need to use the `jammy` repository to install NGINX 1.24.0.

        Also we do not yet run automated tests on Ubuntu 24.04, so please consider this version as experimental.

    The first step is to add NGINX official repository :

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu jammy nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    You should now be able to install NGINX 1.24.0 :

    ```shell
    sudo apt update && \
    sudo apt install -y nginx=1.24.0-1~jammy
    ```

    !!! warning "Testing/dev version"
        If you use the `testing` or `dev` version, you will need to add the `force-bad-version` directive to your `/etc/dpkg/dpkg.cfg` file before installing BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    Optional step : if you want to automatically enable the [setup wizard](web-ui.md#setup-wizard) when BunkerWeb is installed, export the following variable :

    ```shell
    export UI_WIZARD=1
    ```

    And finally install BunkerWeb 1.5.7 :

    ```shell
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y bunkerweb=1.5.7
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

    Optional step : if you want to automatically enable the [setup wizard](web-ui.md#setup-wizard) when BunkerWeb is installed, export the following variable :

    ```shell
    export UI_WIZARD=1
    ```

    And finally install BunkerWeb 1.5.7 :

    ```shell
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.rpm.sh | \
  	sed 's/yum install -y pygpgme --disablerepo='\''bunkerity_bunkerweb'\''/yum install -y python-gnupg/g' | \
  	sed 's/pypgpme_check=`rpm -qa | grep -qw pygpgme`/python-gnupg_check=`rpm -qa | grep -qw python-gnupg`/g' | sudo bash && \
  	sudo dnf makecache && \
  	sudo -E dnf install -y bunkerweb-1.5.7
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

    Optional step : if you want to automatically enable the [setup wizard](web-ui.md#setup-wizard) when BunkerWeb is installed, export the following variable :

    ```shell
    export UI_WIZARD=1
    ```

    And finally install BunkerWeb 1.5.7 :

    ```shell
	  sudo dnf install -y epel-release && \
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo -E dnf install -y bunkerweb-1.5.7
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command :

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

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

Supported Linux distributions for BunkerWeb (amd64/x86_64 and arm64/aarch64 architectures) include:

- Debian 12 "Bookworm"
- Ubuntu 22.04 "Jammy"
- Ubuntu 24.04 "Noble"
- Fedora 39
- Red Hat Enterprise Linux (RHEL) 8.9
- Red Hat Enterprise Linux (RHEL) 9.3

To simplify the deployment and configuration process, [Ansible](https://docs.ansible.com/ansible/latest/index.html) can be used as an IT automation tool. Ansible enables you to configure systems, deploy software, and perform advanced IT tasks such as continuous deployments or zero downtime rolling updates.

For BunkerWeb, there is a dedicated Ansible role available on [Ansible Galaxy](https://galaxy.ansible.com/bunkerity/bunkerweb).

To proceed with the BunkerWeb Ansible role setup, follow these steps:

1. Begin by creating an inventory file that lists the IP addresses or FQDNs of the remote systems you want to manage. You can either add this information to the `/etc/ansible/hosts` file or create a separate inventory file such as `inventory.yml`. Here's an example using a TOML format:

    ```toml
    [mybunkers]
    192.0.2.50
    192.0.2.51
    192.0.2.52
    ```

2. Next, establish SSH connections to the managed nodes by adding your public SSH keys to the `authorized_keys` file on each remote system. Verify that you can successfully connect to the nodes using SSH.

3. Create a playbook file, such as `playbook.yml`, which will define the desired configuration using the BunkerWeb Ansible role. Here's an example playbook configuration:

    ```yaml
    ---
    - hosts: all
      become: true
      roles:
        - bunkerity.bunkerweb
    ```

4. Execute the playbook using the `ansible-playbook` command, providing the inventory file and the playbook file as arguments. For example:

    ```shell
    ansible-playbook -i inventory.yml playbook.yml
    ```

By running the playbook, Ansible will apply the BunkerWeb role to all the hosts specified in the inventory, setting up the desired configuration.

the configuration of BunkerWeb is done by using specific role variables :

|         Name          |    Type    | Description                                                                                                                                                                        | Default value         |
| :-------------------: | :--------: | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
|  `bunkerweb_version`  |   string   | Version of BunkerWeb to install.                                                                                                                                                   | `1.5.7`               |
|    `nginx_version`    |   string   | Version of NGINX to install.                                                                                                                                                       | `1.24.0`              |
|   `freeze_versions`   |  boolean   | Prevent upgrade of BunkerWeb and NGINX when performing packages upgrades.                                                                                                          | `true`                |
|    `variables_env`    |   string   | Path of the variables.env file to configure BunkerWeb.                                                                                                                             | `files/variables.env` |
|      `enable_ui`      |  boolean   | Activate the web UI.                                                                                                                                                               | `false`               |
|      `custom_ui`      |   string   | Path of the ui.env file to configure the web UI.                                                                                                                                   | `files/ui.env`        |
| `custom_configs_path` | Dictionary | Each entry is a path of the folder containing custom configurations. Keys are the type of custom configs : `http`, `server-http`, `modsec`, `modsec-crs` and `default-server-http` | empty values          |
|     `custom_www`      |   string   | Path of the www directory to upload.                                                                                                                                               | empty value           |
|   `custom_plugins`    |   string   | Path of the plugins directory to upload.                                                                                                                                           | empty value           |
|  `custom_www_owner`   |   string   | Default owner for www files and folders.                                                                                                                                           | `nginx`               |
|  `custom_www_group`   |   string   | Default group for www files and folders.                                                                                                                                           | `nginx`               |

## Vagrant

<!-- TODO
<figure markdown>
  ![Overview](assets/img/integration-vagrant.svg){ align=center }
  <figcaption>BunkerWeb integration with Vagrant</figcaption>
</figure>
-->

List of supported providers :

- virtualbox
- libvirt

!!! note "Supported Base Images"
    Please be aware that the provided Vagrant boxes are based **exclusively on Ubuntu 22.04 "Jammy"**. While BunkerWeb supports other Linux distributions, the Vagrant setup currently only supports Ubuntu 22.04 as the base operating system. This ensures a consistent and reliable environment for users who want to deploy BunkerWeb using Vagrant.

Similar to other BunkerWeb integrations, the Vagrant setup uses **NGINX version 1.24.0**. This specific version is required to ensure compatibility and smooth functioning with BunkerWeb. Additionally, the Vagrant box includes **PHP** pre-installed, providing a ready-to-use environment for hosting PHP-based applications alongside BunkerWeb.

By using the provided Vagrant box based on Ubuntu 22.04 "Jammy", you benefit from a well-configured and integrated setup, allowing you to focus on developing and securing your applications with BunkerWeb without worrying about the underlying infrastructure.

Here are the steps to install BunkerWeb using Vagrant on Ubuntu with the supported virtualization providers (VirtualBox, and libvirt):

1. Make sure you have Vagrant and one of the supported virtualization providers (VirtualBox or libvirt) installed on your system.
2. There are two ways to install the Vagrant box with BunkerWeb: either by using a provided Vagrantfile to configure your virtual machine or by creating a new box based on the existing BunkerWeb Vagrant box, offering you flexibility in how you set up your development environment.

=== "Vagrantfile"

    ```shell
    Vagrant.configure("2") do |config|
      config.vm.box = "bunkerity/bunkerweb"
    end
    ```

    Depending on the virtualization provider you choose, you may need to install additional plugins:

    * For **libvirt**, install the `vagrant-libvirt plugin`. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).
    * For **VirtualBox**, install the `vagrant-vbguest` plugin. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).

=== "New Vagrant Box"

    ```shell
    vagrant init bunkerity/bunkerweb
    ```

    Depending on the virtualization provider you choose, you may need to install additional plugins:

    * For **libvirt**, install the `vagrant-libvirt plugin`. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).
    * For **VirtualBox**, install the `vagrant-vbguest` plugin. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).

After installing the necessary plugins for your chosen virtualization provider, run the following command to start the virtual machine and install BunkerWeb:

```shell
vagrant up --provider=virtualbox # or --provider=libvirt
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
  # For libvirt
  # config.vm.provider "libvirt"
end
```
