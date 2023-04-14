# Integrations

## Docker

<figure markdown>
  ![Overwiew](assets/img/integration-docker.svg){ align=center }
  <figcaption>Docker integration</figcaption>
</figure>

Using BunkerWeb as a [Docker](https://www.docker.com/) container is a quick and easy way to test and use it as long as you are familiar with the Docker technology.

We provide ready-to-use prebuilt images for x64, x86 armv8 and armv7 architectures on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb) :

```shell
docker pull bunkerity/bunkerweb:1.4.6
```

Alternatively, you can build the Docker images directly from the [source](https://github.com/bunkerity/bunkerweb) (and get a coffee ☕ because it may take a long time depending on your hardware) :

```shell
git clone https://github.com/bunkerity/bunkerweb.git && \
cd bunkerweb && \
docker build -t my-bunkerweb .
```

BunkerWeb container's usage and configuration are based on :

- **Environment variables** to configure BunkerWeb and meet your use cases
- **Volume** to cache important data and mount custom configuration files
- **Networks** to expose ports for clients and connect to upstream web services

### Environment variables

Settings are passed to BunkerWeb using Docker environment variables. You can use the `-e` flag :

```shell
docker run \
	   ...
	   -e MY_SETTING=value \
	   -e "MY_OTHER_SETTING=value with spaces" \
	   ...
	   bunkerity/bunkerweb:1.4.6
```

Here is the docker-compose equivalent :

```yaml
...
services:
  mybunker:
    image: bunkerity/bunkerweb:1.4.6
    environment:
      - MY_SETTING=value
```

!!! info "Full list"
    For the complete list of environment variables, see the [settings section](/1.4/settings) of the documentation.

### Volume

A volume is used to share data with BunkerWeb and store persistent data like certificates, cached files, ...

The easiest way of managing the volume is by using a named one. You will first need to create it :

```shell
docker volume create bw_data
```

Once it's created, you will be able to mount it on `/data` when running the container :

```shell
docker run \
	   ...
	   -v bw_data:/data \
	   ...
	   bunkerity/bunkerweb:1.4.6
```

Here is the docker-compose equivalent :

```yaml
...
services:
  mybunker:
    image: bunkerity/bunkerweb:1.4.6
    volumes:
      - bw_data:/data
...
volumes:
  bw_data:
```

!!! warning "Using local folder for persistent data"

    BunkerWeb runs as an **unprivileged user with UID 101 and GID 101** inside the container. The reason behind this is security : in case a vulnerability is exploited, the attacker won't have full root (UID/GID 0) privileges.
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

### Networks

By default, BunkerWeb container is listening (inside the container) on **8080/tcp** for **HTTP** and **8443/tcp** for **HTTPS**.

!!! warning "Privileged ports in rootless mode or when using podman"
    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) and want to redirect privileged ports (< 1024) like 80 and 443 to BunkerWeb, please refer to the prerequisites [here](https://docs.docker.com/engine/security/rootless/#exposing-privileged-ports).
	
    If you are using [podman](https://podman.io/) you can lower the minimum number for unprivileged ports :
    ```shell
    sudo sysctl net.ipv4.ip_unprivileged_port_start=1
    ```

The easiest way to connect BunkerWeb to web applications is by using Docker networks.

First of all, you will need to create a network :

```shell
docker network create mynetwork
```

Once it's created, you will need to connect the container to that network :

```shell
docker run \
       ...
	   --network mynetwork \
	   ...
	   bunkerity/bunkerweb:1.4.6
```

You will also need to do the same with your web application(s). Please note that the other containers are accessible using their name as the hostname.

Here is the docker-compose equivalent :

```yaml
...
services:
  mybunker:
    image: bunkerity/bunkerweb:1.4.6
    networks:
      - bw-net
...
networks:
  bw-net:
```

## Docker autoconf

<figure markdown>
  ![Overwiew](assets/img/integration-autoconf.svg){ align=center }
  <figcaption>Docker autoconf integration</figcaption>
</figure>

!!! info "Docker integration"
    The Docker autoconf integration is an "evolution" of the Docker one. Please read the [Docker integration section](#docker) first if needed.

The downside of using environment variables is that the container needs to be recreated each time there is an update which is not very convenient. To counter that issue, you can use another image called **autoconf** which will listen for Docker events and automatically reconfigure BunkerWeb in real-time without recreating the container.

Instead of defining environment variables for the BunkerWeb container, you simply add **labels** to your web applications containers and the **autoconf** will "automagically" take care of the rest.

!!! info "Multisite mode"
    The Docker autoconf integration implies the use of **multisite mode**. Please refer to the [multisite section](/1.4/concepts/#multisite-mode) of the documentation for more information.

First of all, you will need to create the data volume :

```shell
docker volume create bw-data
```

Then, you can create two networks (replace 10.20.30.0/24 with an unused subnet of your choice) :

```shell
docker network create --subnet 10.20.30.0/24 bw-autoconf && \
docker network create bw-services
```

- One for communication between **BunkerWeb** and **autoconf**
- Another one for communication between **BunkerWeb** and **web applications**

You can now create the BunkerWeb container with the `AUTOCONF_MODE=yes` setting and the `bunkerweb.AUTOCONF` label (replace 10.20.30.0/24 with the subnet specified before) :

```shell
docker run \
       -d \
       --name mybunker \
	   --network bw-autoconf \
	   -p 80:8080 \
	   -p 443:8443 \
	   -e AUTOCONF_MODE=yes \
	   -e MULTISITE=yes \
	   -e SERVER_NAME= \
	   -e "API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24" \
	   -l bunkerweb.AUTOCONF \
	   bunkerity/bunkerweb:1.4.6 && \

docker network connect bw-services mybunker
```

!!! warning "Using Docker in rootless mode"
    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless), you will need to replace the mount of the docker socket with the following value : `$XDG_RUNTIME_DIR/docker.sock:/var/run/docker.sock:ro`.

And the autoconf one :

```shell
docker run \
       -d \
	   --name myautoconf \
	   --network bw-autoconf \
	   -v bw-data:/data \
	   -v /var/run/docker.sock:/var/run/docker.sock:ro \
	   bunkerity/bunkerweb-autoconf:1.4.6
```

Here is the docker-compose equivalent for the BunkerWeb autoconf stack :

```yaml
version: '3.5'

services:

  mybunker:
    image: bunkerity/bunkerweb:1.4.6
    ports:
      - 80:8080
	  - 443:8443
    environment:
	  - AUTOCONF_MODE=yes
	  - MULTISITE=yes
      - SERVER_NAME=
      - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
    labels:
      - "bunkerweb.AUTOCONF"
    networks:
      - bw-autoconf
	  - bw-services

  myautoconf:
    image: bunkerity/bunkerweb-autoconf:1.4.6
    volumes:
      - bw-data:/data
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - bw-autoconf

volumes:
  bw-data:

networks:
  bw-autoconf:
    ipam:
      driver: default
      config:
        - subnet: 10.20.30.0/24
  bw-services:
    name: bw-services
```

Once the stack is set up, you will be able to create the web application container and add the settings as labels using the "bunkerweb." prefix in order to automatically set up BunkerWeb :

```shell
docker run \
       -d \
       --name myapp \
	   --network bw-services \
	   -l bunkerweb.MY_SETTING_1=value1 \
	   -l bunkerweb.MY_SETTING_2=value2 \
       ...
	   mywebapp:4.2
```

Here is the docker-compose equivalent :

```yaml
...

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

...

networks:
  bw-services:
    external:
      name: bw-services

...
```

## Swarm

<figure markdown>
  ![Overwiew](assets/img/integration-swarm.svg){ align=center }
  <figcaption>Docker Swarm integration</figcaption>
</figure>

!!! info "Docker autoconf"
    The Docker autoconf integration is similar to the Docker autoconf one (but with services instead of containers). Please read the [Docker autoconf integration section](#docker-autoconf) first if needed.

To automatically configure BunkerWeb instances, a special service called **autoconf**, will be scheduled on a manager node. That service will listen for Docker Swarm events like service creation or deletion and automatically configure the **BunkerWeb instances** in real-time without downtime.

Like the [Docker autoconf integration](#docker-autoconf), configuration for web services is defined by using labels starting with the special **bunkerweb.** prefix.

The recommended setup is to schedule the **BunkerWeb service** as a **global service** on all worker nodes and the **autoconf service** as a **single replicated service** on a manager node.

First of all, you will need to create two networks (replace 10.20.30.0/24 with an unused subnet of your choice) :

```shell
docker network create -d overlay --attachable --subnet 10.20.30.0/24 bw-autoconf && \
docker network create -d overlay --attachable bw-services
```

- One for communication between **BunkerWeb** and **autoconf**
- Another one for communication between **BunkerWeb** and **web applications**

You can now create the BunkerWeb service (replace 10.20.30.0/24 with the subnet specified before) :

```shell
docker service create \
       --name mybunker \
	   --mode global \
	   --constraint node.role==worker \
	   --network bw-autoconf \
	   --network bw-services \
	   -p published=80,target=8080,mode=host \
	   -p published=443,target=8443,mode=host \
	   -e SWARM_MODE=yes \
	   -e SERVER_NAME= \
	   -e MULTISITE=yes \
	   -e "API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24" \
	   -l bunkerweb.AUTOCONF \
	   bunkerity/bunkerweb:1.4.6
```

And the autoconf one :

```shell
docker service \
       create \
	   --name myautoconf \
	   --constraint node.role==manager \
	   --network bw-autoconf \
	   --mount type=bind,source=/var/run/docker.sock,destination=/var/run/docker.sock,ro \
	   --mount type=volume,source=bw-data,destination=/data \
	   -e SWARM_MODE=yes \
	   bunkerity/bunkerweb-autoconf:1.4.6
```

Here is the docker-compose equivalent (using `docker stack deploy`) :

```yaml
version: '3.5'

services:

  mybunker:
    image: bunkerity/bunkerweb:1.4.6
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
      - SWARM_MODE=yes
      - SERVER_NAME=
      - MULTISITE=yes
      - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
    networks:
      - bw-autoconf
      - bw-services
    deploy:
      mode: global
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerweb.AUTOCONF"

  myautoconf:
    image: bunkerity/bunkerweb-autoconf:1.4.6
    environment:
      - SWARM_MODE=yes
    volumes:
      - bw-data:/data
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - bw-autoconf
    deploy:
      replicas: 1
      placement:
        constraints:
          - "node.role==manager"

networks:
  bw-autoconf:
    driver: overlay
    attachable: true
    name: bw-autoconf
	ipam:
	  config:
        - subnet: 10.20.30.0/24
  bw-services:
    driver: overlay
    attachable: true
    name: bw-services

volumes:
  bw-data:
```

Once the BunkerWeb Swarm stack is set up and running (see autoconf logs for more information), you will be able to deploy web applications in the cluster and use labels to dynamically configure BunkerWeb :

```shell
docker service \
       create \
       --name myapp \
       --network bw-services \
       -l bunkerweb.MY_SETTING_1=value1 \
       -l bunkerweb.MY_SETTING_2=value2 \
       ...
       mywebapp:4.2
```

Here is the docker-compose equivalent (using `docker stack deploy`) :

```yaml
...
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
...
networks:
  bw-services:
    external:
      name: bw-services
```

## Kubernetes

<figure markdown>
  ![Overwiew](assets/img/integration-kubernetes.svg){ align=center }
  <figcaption>Kubernetes integration</figcaption>
</figure>

The autoconf acts as an [Ingress controller](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/) and will configure the BunkerWeb instances according to the [Ingress resources](https://kubernetes.io/docs/concepts/services-networking/ingress/). It also monitors other Kubernetes objects like [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) for custom configurations.

The first step to install BunkerWeb on a Kubernetes cluster is to add a role and permissions on the cluster for the autoconf :

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
```

The recommended way of deploying BunkerWeb is using a [DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/) which means each node in the cluster will run an instance of BunkerWeb :

```yaml
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
        bunkerweb.io/AUTOCONF: "yes"
    spec:
      containers:
      - name: bunkerweb
        image: bunkerity/bunkerweb
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
apiVersion: v1
kind: Service
metadata:
  name: svc-bunkerweb
spec:
  clusterIP: None
  selector:
    app: bunkerweb
```

In order to store persistent data, you will need a [PersistentVolumeClaim](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) :

```yaml
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

Now, you can start the autoconf as a single replica [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) :

```yaml
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
      volumes:
      - name: vol-bunkerweb
        persistentVolumeClaim:
          claimName: pvc-bunkerweb
      containers:
      - name: bunkerweb-controller
        image: bunkerity/bunkerweb-autoconf
        imagePullPolicy: Always
        env:
        - name: KUBERNETES_MODE
          value: "yes"
        volumeMounts:
        - name: vol-bunkerweb
          mountPath: /data
```

Once the BunkerWeb Kubernetes stack is set up and running (see autoconf logs for more information), you will be able to deploy web applications in the cluster and declare your Ingress resource. Please note that [settings](/1.4/settings) need to be set as annotations for the Ingress resource with the special value **bunkerweb.io** for the domain part :

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ingress
  annotations:
	bunkerweb.io/MY_SETTING_1: "value1"
	bunkerweb.io/MY_SETTING_2: "value2"
spec:
  rules:
...
```

## Linux

<figure markdown>
  ![Overwiew](assets/img/integration-linux.svg){ align=center }
  <figcaption>Linux integration</figcaption>
</figure>

List of supported Linux distros :

- Debian 11 "Bullseye"
- Ubuntu 22.04 "Jammy"
- Fedora 36
- CentOS Stream 8

Please note that you will need to **install NGINX 1.20.2 before BunkerWeb**. For all distros, except Fedora, using prebuilt packages from [official NGINX repository](https://nginx.org/en/linux_packages.html) is mandatory. Compiling NGINX from source or using packages from different repositories won't work with the official prebuilt packages of BunkerWeb but you can build it from source.

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

    You should now be able to install NGINX 1.20.2 :
	```shell
	sudo apt update && \
	sudo apt install -y nginx=1.20.2-1~$(lsb_release -cs)
	```

	And finally install BunkerWeb 1.4.6 :
    ```shell
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.deb.sh | sudo bash && \
	sudo apt update && \
	sudo apt install -y bunkerweb=1.4.6
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

    You should now be able to install NGINX 1.20.2 :
	```shell
	sudo apt update && \
	sudo apt install -y nginx=1.20.2-1~jammy
	```

	And finally install BunkerWeb 1.4.6 :
    ```shell
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.deb.sh | sudo bash && \
	sudo apt update && \
	sudo apt install -y bunkerweb=1.4.6
    ```
	
	To prevent upgrading NGINX and/or BunkerWeb packages when executing `apt upgrade`, you can use the following command :
	```shell
	sudo apt-mark hold nginx bunkerweb
	```

=== "Fedora"

    Fedora already provides NGINX 1.20.2 that we support :
	```shell
	sudo dnf install -y nginx-1.20.2
	```

	And finally install BunkerWeb 1.4.6 :
  ```shell
  curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.rpm.sh | \
  sed 's/yum install -y pygpgme --disablerepo='\''bunkerity_bunkerweb'\''/yum install -y python-gnupg/g' | \
  sed 's/pypgpme_check=`rpm -qa | grep -qw pygpgme`/python-gnupg_check=`rpm -qa | grep -qw python-gnupg`/g' | sudo bash && \
  sudo dnf makecache && \
  sudo dnf install -y bunkerweb-1.4.6
  ```

	To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command :
  ```shell
  sudo dnf versionlock add nginx && \
  sudo dnf versionlock add bunkerweb
  ```

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

    You should now be able to install NGINX 1.20.2 :
	```shell
	sudo dnf install nginx-1.20.2
	```

	And finally install BunkerWeb 1.4.6 :
    ```shell
	dnf install -y epel-release && \
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo dnf install -y bunkerweb-1.4.6
    ```

	To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command :
	```shell
	sudo dnf versionlock add nginx && \
	sudo dnf versionlock add bunkerweb
	```

=== "Redhat"

    The first step is to add CentOS official repository. Create the following file at `/etc/yum.repos.d/centos.repo` :
    ```conf
    [centos]
    name=CentOS-$releasever - Base
    baseurl=http://mirror.centos.org/centos/$releasever/BaseOS/$basearch/os/
    gpgcheck=1
    enabled=1
    gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-centosofficial
	```

    The import the official GPG key of CentOS :
    ```shell
    rpm --import https://www.centos.org/keys/RPM-GPG-KEY-CentOS-Official
    ```

      Go to NGINX 1.20.2 by first adding the official NGINX repository. Create the following file at /etc/yum.repos.d/nginx.repo :
    ```conf
    [nginx-stable]
    name=nginx stable repo
    baseurl=http://nginx.org/packages/rhel/$releasever/$basearch/
    gpgcheck=1
    enabled=1
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true
	```

    You should now be able to install NGINX 1.20.2 :
	```shell
	sudo dnf install nginx-1.20.2-1.el8.ngx.x86_64
	```

	And finally install BunkerWeb 1.4.6 :
    ```shell
	dnf install -y epel-release && \
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo dnf install -y bunkerweb-1.4.6
    ```

	To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command :
	```shell
	sudo dnf versionlock add nginx && \
	sudo dnf versionlock add bunkerweb
	```

=== "From source"

    The first step is to install NGINX 1.20.2 using the repository of your choice or by [compiling it from source](https://docs.nginx.com/nginx/admin-guide/installing-nginx/installing-nginx-open-source/#compiling-and-installing-from-source).
	
	The target installation folder of BunkerWeb is located at `/usr/share/bunkerweb`, let's create it :
	```shell
	mkdir /usr/share/bunkerweb
	```
	
	You can now clone the BunkerWeb project to the `/tmp` folder :
	```shell
	https://github.com/bunkerity/bunkerweb.git /tmp/bunkerweb
	```
	
	BunkerWeb needs some dependencies to be compiled and installed to `/usr/share/bunkerweb/deps`, the easiest way to do it is by executing the [install.sh helper script](https://github.com/bunkerity/bunkerweb/blob/master/deps/install.sh) (please note that you will need to install additional packages which is not covered in this procedure and depends on your own system) :
	```
	mkdir /usr/share/bunkerweb/deps && \
	/tmp/bunkerweb/deps/install.sh
	```

	Additional Python dependencies needs to be installed into the `/usr/share/bunkerweb/deps/python` folder :
	```shell
	mkdir -p /usr/share/bunkerweb/deps/python && \
  cat src/scheduler/requirements.txt src/ui/requirements.txt src/common/gen/requirements.txt src/common/db/requirements.txt > /tmp/bunkerweb/deps/requirements.txt && \
	pip install --no-cache-dir --require-hashes --target /usr/share/bunkerweb/deps/python -r /tmp/bunkerweb/deps/requirements.txt && \
	```
	
	Once dependencies are installed, you will be able to copy the BunkerWeb sources to the target `/usr/share/bunkerweb` folder :
	```shell
	for src in api cli confs core gen helpers job lua misc utils ui settings.json VERSION linux/variables.env linux/ui.env linux/scripts ; do
		cp -r /tmp/bunkerweb/${src} /usr/share/bunkerweb
	done
	cp /usr/share/bunkerweb/helpers/bwcli /usr/bin
	```
	
	Additional folders also need to be created :
	```shell
  mkdir -p /etc/bunkerweb/configs && \
	mkdir -p /var/cache/bunkerweb && \
  mkdir -p /etc/bunkerweb/plugins && \
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
  ![Overwiew](assets/img/integration-ansible.svg){ align=center }
  <figcaption>Ansible integration</figcaption>
</figure>

List of supported Linux distros :

- Debian 11 "Bullseye"
- Ubuntu 22.04 "Jammy"
- Fedora 36
- CentOS Stream 8

[Ansible](https://docs.ansible.com/ansible/latest/index.html) is an IT automation tool. It can configure systems, deploy software, and orchestrate more advanced IT tasks such as continuous deployments or zero downtime rolling updates.

A specific BunkerWeb Ansible role is available on [Ansible Galaxy](https://galaxy.ansible.com/bunkerity/bunkerweb) (source code is available [here](https://github.com/bunkerity/bunkerweb-ansible)).

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
| `bunkerweb_version` | string | Version of BunkerWeb to install. | `1.4.6` |
| `nginx_version` | string | Version of NGINX to install. | `1.20.2` |
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

<figure markdown>
  ![Overwiew](assets/img/integration-vagrant.svg){ align=center }
  <figcaption>BunkerWeb integration with Vagrant</figcaption>
</figure>

List of supported providers :

- vmware_desktop 
- virtualbox 
- libvirt

**_Note on Supported Base Images_**  

Please be aware that the provided Vagrant boxes are based **exclusively on Ubuntu 22.04 "Jammy"**. While BunkerWeb supports other Linux distributions, the Vagrant setup currently only supports Ubuntu 22.04 as the base operating system. This ensures a consistent and reliable environment for users who want to deploy BunkerWeb using Vagrant.

Similar to other BunkerWeb integrations, the Vagrant setup uses **NGINX version 1.20.2**. This specific version is required to ensure compatibility and smooth functioning with BunkerWeb. Additionally, the Vagrant box includes **PHP** pre-installed, providing a ready-to-use environment for hosting PHP-based applications alongside BunkerWeb.

By using the provided Vagrant box based on Ubuntu 22.04 "Jammy", you benefit from a well-configured and integrated setup, allowing you to focus on developing and securing your applications with BunkerWeb without worrying about the underlying infrastructure.

Here are the steps to install BunkerWeb using Vagrant on Ubuntu with the supported virtualization providers (VirtualBox, VMware, and libvirt):


1. Make sure you have Vagrant and one of the supported virtualization providers (VirtualBox, VMware, or libvirt) installed on your system.
2. There are two ways to install the Vagrant box with BunkerWeb: either by using a provided Vagrantfile to configure your virtual machine or by creating a new box based on the existing BunkerWeb Vagrant box, offering you flexibility in how you set up your development environment.

=== "Vagrantfile"

    ```shell
    Vagrant.configure("2") do |config|
      config.vm.box = "bunkerity/bunkerity"
    end
    ```

    Depending on the virtualization provider you choose, you may need to install additional plugins:

    * For **VMware**, install the `vagrant-vmware-desktop` plugin. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).
    * For **libvirt**, install the `vagrant-libvirt plugin`. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).
    * For **VirtualBox**, install the `vagrant-vbguest` plugin. For more information, see the [Vagrant documentation](https://www.vagrantup.com/docs/providers).

=== "New Vagrant Box"

    ```shell
    vagrant init bunkerity/bunkerity
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
  config.vm.box = "bunkerity/bunkerity"

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