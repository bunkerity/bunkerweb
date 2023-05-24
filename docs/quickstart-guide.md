# Quickstart guide

!!! info "Prerequisites"
    We assume that you're already familiar with the [core concepts](concepts.md) and you have followed the [integrations instructions](integrations.md) for your environment.

!!! tip "Going further"
		To demonstrate the use of BunkerWeb, we will deploy a dummy "Hello World" web application as an example. See the [examples folder](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/examples) of the repository to get real-world examples.

## Protect HTTP applications

Protecting existing web applications already accessible with the HTTP(S) protocol is the main goal of BunkerWeb : it will act as a classical [reverse proxy](https://en.wikipedia.org/wiki/Reverse_proxy) with extra security features.

The following settings can be used :

- `USE_REVERSE_PROXY` : enable/disable reverse proxy mode
- `REVERSE_PROXY_URL` : the public path prefix
- `REVERSE_PROXY_HOST` : (internal) address of the proxied web application

You will find more settings about reverse proxy in the [settings section](settings.md#reverse-proxy) of the documentation.

### Single application

=== "Docker"

    When using Docker integration, the easiest way of protecting an existing application is to add the web service in the `bw-services` network :

    ```yaml
    version: "3.5"

    services:

      myapp:
        image: tutum/hello-world
        networks:
          - bw-services

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
          - USE_REVERSE_PROXY=yes
          - REVERSE_PROXY_URL=/
          - REVERSE_PROXY_HOST=http://myapp
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

=== "Docker autoconf"

    We will assume that you already have the [Docker autoconf integration](integrations.md#docker-autoconf) stack running on your machine and connected to a network called `bw-services` so you can connect your existing application and configure BunkerWeb with labels :

    ```yaml
    version: '3.5'

    services:
      myapp:
    	  image: tutum/hello-world
    	  networks:
    	    bw-services:
    		    aliases:
    		      - myapp
    	  labels:
    	    - "bunkerweb.SERVER_NAME=www.example.com"
    	    - "bunkerweb.USE_REVERSE_PROXY=yes"
    	    - "bunkerweb.REVERSE_PROXY_URL=/"
    	    - "bunkerweb.REVERSE_PROXY_HOST=http://myapp"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Swarm"

    We will assume that you already have the [Swarm integration](integrations.md#swarm) stack running on your cluster and connected to a network called `bw-services` so you can connect your existing application and configure BunkerWeb with labels :

    ```yaml
    version: "3"

    services:
      myapp:
        image: tutum/hello-world
        networks:
          bw-services:
              aliases:
                - myapp
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/"
          - "bunkerweb.REVERSE_PROXY_HOST=http://myapp"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    We will assume that you already have the [Kubernetes integration](integrations.md#kubernetes) stack running on your cluster.

    Let's assume that you have a typical Deployment with a Service to access the web application from within the cluster :

    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app
      labels:
    	app: app
    spec:
      replicas: 1
      selector:
    	matchLabels:
    	  app: app
      template:
    	metadata:
    	  labels:
    		app: app
    	spec:
    	  containers:
    	  - name: app
    		image: tutum/hello-world
    		ports:
    		- containerPort: 80
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app
    spec:
      selector:
    	app: app
      ports:
    	- protocol: TCP
    	  port: 80
    	  targetPort: 80
    ```

    Here is the corresponding Ingress definition to serve and protect the web application :

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      annotations:
        bunkerweb.io/DUMMY_SETTING: "value"
    spec:
      rules:
        - host: www.example.com
          http:
            paths:
              - path: /
                pathType: Prefix
                backend:
                  service:
                  name: svc-app
                  port:
                    number: 80
    ```

=== "Linux"

    We will assume that you already have the [Linux integration](integrations.md#linux) stack running on your machine.

    The following command will run a basic HTTP server on the port 8000 and deliver the files in the current directory :

    ```shell
    python3 -m http.server -b 127.0.0.1
    ```

    Configuration of BunkerWeb is done by editing the `/etc/bunkerweb/variables.env` file :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    SERVER_NAME=www.example.com
    USE_REVERSE_PROXY=yes
    REVERSE_PROXY_URL=/
    REVERSE_PROXY_HOST=http://127.0.0.1:8000
    ```

    Let's check the status of BunkerWeb :

    ```shell
    systemctl status bunkerweb
    ```

    If it's already running, we can restart it :

    ```shell
    systemctl restart bunkerweb
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb
    ```

=== "Ansible"

    We will assume that you already have a service running and you want to use BunkerWeb as a reverse-proxy.

    The following command will run a basic HTTP server on the port 8000 and deliver the files in the current directory :

    ```shell
    python3 -m http.server -b 127.0.0.1
    ```

    Content of the `my_variables.env` configuration file :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    SERVER_NAME=www.example.com
    USE_REVERSE_PROXY=yes
    REVERSE_PROXY_URL=/
    REVERSE_PROXY_HOST=http://127.0.0.1:8000
    ```

    In your Ansible inventory, you can use the `variables_env` variable to set the path of configuration file :

    ```yaml
    [mybunkers]
      192.168.0.42 variables_env="{{ playbook_dir }}/my_variables.env"
    ```
    
    Or alternatively, in your playbook file :

    ```yaml
    - hosts: all
      become: true
      vars:
        - variables_env: "{{ playbook_dir }}/my_variables.env"
      roles:
        - bunkerity.bunkerweb
    ```

    You can now run the playbook :

    ```shell
    ansible-playbook -i inventory.yml playbook.yml
    ```

=== "Vagrant"

    We will assume that you already have the [Vagrant integration](integrations.md#vagrant) stack running on your machine.

    The following command will run a basic HTTP server on the port 8000 and deliver the files in the current directory :

    ```shell
    python3 -m http.server -b 127.0.0.1
    ```

    Configuration of BunkerWeb is done by editing the `/etc/bunkerweb/variables.env` file.

	  Connect to your vagrant machine :

    ```shell
    vagrant ssh
    ```

	  And then you can edit the `variables.env` file in your host machine like this :

    ```conf
    SERVER_NAME=www.example.com
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    USE_REVERSE_PROXY=yes
    REVERSE_PROXY_URL=/
    REVERSE_PROXY_HOST=http://127.0.0.1:8000
    ```

    Let's check the status of BunkerWeb :

    ```shell
    systemctl status bunkerweb
    ```

    If it's already running we can restart it :

    ```shell
    systemctl restart bunkerweb
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb
    ```

### Multiple applications

!!! tip "Testing"

    To perform quick tests when multisite mode is enabled (and if you don't have the proper DNS entries set up for the domains) you can use curl with the HTTP Host header of your choice :

    ```shell
    curl -H "Host: app1.example.com" http://ip-or-fqdn-of-server
    ```
    
    If you are using HTTPS, you will need to play with SNI :

    ```shell
    curl -H "Host: app1.example.com" --resolve example.com:443:ip-of-server https://example.com
    ```

=== "Docker"

    When using Docker integration, the easiest way of protecting an existing application is to add the web service in the `bw-services network` :

    ```yaml
    version: "3.5"

    services:
      myapp1:
        image: tutum/hello-world
        networks:
          - bw-services

      myapp2:
        image: tutum/hello-world
        networks:
          - bw-services

      myapp3:
        image: tutum/hello-world
        networks:
          - bw-services

      bunkerweb:
        image: bunkerity/bunkerweb:1.5.0
        ports:
          - 80:8080
          - 443:8443
        labels:
          - "bunkerweb.INSTANCE"
        environment:
          - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
          - MULTISITE=yes
          - SERVER_NAME=app1.example.com app2.example.com app3.example.com
          - USE_REVERSE_PROXY=yes # Will be applied to all server config
          - REVERSE_PROXY_URL=/ # Will be applied to all server config
          - app1.example.com_REVERSE_PROXY_HOST=http://myapp1
          - app2.example.com_REVERSE_PROXY_HOST=http://myapp2
          - app3.example.com_REVERSE_PROXY_HOST=http://myapp3
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

=== "Docker autoconf"

    We will assume that you already have the [Docker autoconf integration](integrations.md#docker-autoconf) stack running on your machine and connected to a network called `bw-services` so you can connect your existing application and configure BunkerWeb with labels :

    ```yaml
    version: '3.5'

    services:
      myapp1:
    	  image: tutum/hello-world
    	  networks:
    	    bw-services:
    		    aliases:
    		      - myapp1
    	  labels:
    	    - "bunkerweb.SERVER_NAME=app1.example.com"
    	    - "bunkerweb.USE_REVERSE_PROXY=yes"
    	    - "bunkerweb.REVERSE_PROXY_URL=/"
    	    - "bunkerweb.REVERSE_PROXY_HOST=http://myapp1"

      myapp2:
    	  image: tutum/hello-world
    	  networks:
    	    bw-services:
    		    aliases:
    		      - myapp1
    	  labels:
    	    - "bunkerweb.SERVER_NAME=app2.example.com"
    	    - "bunkerweb.USE_REVERSE_PROXY=yes"
    	    - "bunkerweb.REVERSE_PROXY_URL=/"
    	    - "bunkerweb.REVERSE_PROXY_HOST=http://myapp2"

      myapp3:
    	  image: tutum/hello-world
    	  networks:
    	    bw-services:
    		    aliases:
    		      - myapp3
    	  labels:
    	    - "bunkerweb.SERVER_NAME=app3.example.com"
    	    - "bunkerweb.USE_REVERSE_PROXY=yes"
    	    - "bunkerweb.REVERSE_PROXY_URL=/"
    	    - "bunkerweb.REVERSE_PROXY_HOST=http://myapp3"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Swarm"

    We will assume that you already have the [Swarm integration](integrations.md#swarm) stack running on your cluster and connected to a network called `bw-services` so you can connect your existing application and configure BunkerWeb with labels :

    ```yaml
    version: "3"

    services:
      myapp1:
        image: tutum/hello-world
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
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/"
          - "bunkerweb.REVERSE_PROXY_HOST=http://myapp1"

      myapp2:
        image: tutum/hello-world
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
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/"
          - "bunkerweb.REVERSE_PROXY_HOST=http://myapp2"

      myapp3:
        image: tutum/hello-world
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
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/"
          - "bunkerweb.REVERSE_PROXY_HOST=http://myapp3"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    We will assume that you already have the [Kubernetes integration](integrations.md#kubernetes) stack running on your cluster.

    Let's assume that you have typical Deployments with a Service to access the web applications from within the cluster :

    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app1
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
    		image: tutum/hello-world
    		ports:
    		- containerPort: 80
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app1
    spec:
      selector:
    	app: app1
      ports:
    	- protocol: TCP
    	  port: 80
    	  targetPort: 80
    ```

    Here is the corresponding Ingress definition to serve and protect the web applications :

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      annotations:
        bunkerweb.io/DUMMY_SETTING: "value"
        bunkerweb.io/app1.example.com_DUMMY_SETTING: "value"
    spec:
      rules:
        - host: app1.example.com
          http:
            paths:
              - path: /
                pathType: Prefix
                backend:
                  service:
                  name: svc-app1
                  port:
                    number: 80
        - host: app2.example.com
          http:
            paths:
              - path: /
                pathType: Prefix
                backend:
                  service:
                  name: svc-app2
                  port:
                    number: 80
        - host: app3.example.com
          http:
            paths:
              - path: /
                pathType: Prefix
                backend:
                  service:
                  name: svc-app3
                  port:
                    number: 80
    ```

=== "Linux"

    We will assume that you already have the [Linux integration](integrations.md#linux) stack running on your machine.

    The following command will run a basic HTTP server on the port 8001 and deliver the files in the current directory (repeat it and change the port if you want to test BunkerWeb) :

    ```shell
    python3 -m http.server -b 127.0.0.1 8001
    ```

    Configuration of BunkerWeb is done by editing the `/etc/bunkerweb/variables.env` file :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    MULTISITE=yes
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    USE_REVERSE_PROXY=yes
    REVERSE_PROXY_URL=/
    app1.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8001
    app2.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8002
    app3.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8003
    ```

    Let's check the status of BunkerWeb :

    ```shell
    systemctl status bunkerweb
    ```

    If it's already running, we can restart it :

    ```shell
    systemctl restart bunkerweb
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb
    ```

=== "Ansible"

    We will assume that you already have a service running and you want to use BunkerWeb as a reverse-proxy.

    The following command will run a basic HTTP server on the port 8001 and deliver the files in the current directory (repeat it and change the port if you want to test BunkerWeb) :

    ```shell
    python3 -m http.server -b 127.0.0.1 8001
    ```

    Content of the `my_variables.env` configuration file :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    MULTISITE=yes
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    USE_REVERSE_PROXY=yes
    REVERSE_PROXY_URL=/
    app1.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8001
    app2.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8002
    app3.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8003
    ```

    In your Ansible inventory, you can use the `variables_env` variable to set the path of configuration file :

    ```yaml
    [mybunkers]
      192.168.0.42 variables_env="{{ playbook_dir }}/my_variables.env"
    ```
    
    Or alternatively, in your playbook file :

    ```yaml
    - hosts: all
      become: true
      vars:
        - variables_env: "{{ playbook_dir }}/my_variables.env"
      roles:
        - bunkerity.bunkerweb
    ```

    You can now run the playbook :

    ```shell
    ansible-playbook -i inventory.yml playbook.yml
    ```

=== "Vagrant"

    We will assume that you already have the [Vagrant integration](integrations.md#vagrant) stack running on your machine.

	  First of all, connect to your vagrant machine :

    ```shell
    vagrant ssh
    ```

    The following command will run a basic HTTP server on the port 8001 and deliver the files in the current directory (repeat it and change the port if you want to test BunkerWeb) :

    ```shell
    python3 -m http.server -b 127.0.0.1 8001
    ```

	  And then you can edit the `variables.env` file in your host machine like this :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    MULTISITE=yes
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    USE_REVERSE_PROXY=yes
    REVERSE_PROXY_URL=/
    app1.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8001
    app2.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8002
    app3.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8003
    ```

    Let's check the status of BunkerWeb :

    ```shell
    systemctl status bunkerweb
    ```

    If it's already running we can restart it :

    ```shell
    systemctl restart bunkerweb
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb
    ```

## Behind load balancer or reverse proxy

When BunkerWeb is itself behind a load balancer or a reverse proxy, you need to configure it so it can get the real IP address of the clients. If you don't, the security features will block the IP address of the load balancer or reverse proxy instead of the client's one.

BunkerWeb actually supports two methods to retrieve the real IP address of the client :

- Using the `PROXY protocol`
- Using a HTTP header like `X-Forwarded-For`

The following settings can be used :

- `USE_REAL_IP` : enable/disable real IP retrieval
- `USE_PROXY_PROTOCOL` : enable/disable PROXY protocol support
- `REAL_IP_FROM` : list of trusted IP/network address allowed to send us the "real IP"
- `REAL_IP_HEADER` : the HTTP header containing the real IP or special value `proxy_protocol` when using PROXY protocol

You will find more settings about real IP in the [settings section](settings.md#real-ip) of the documentation.

### HTTP header

We will assume the following regarding the load balancers or reverse proxies (you will need to update the settings depending on your configuration) :

- They use the `X-Forwarded-For` header to set the real IP
- They have IPs in the `1.2.3.0/24` and `100.64.0.0/10` networks

The following settings need to be set :

```conf
USE_REAL_IP=yes
REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
REAL_IP_HEADER=X-Forwarded-For
```

=== "Docker"

    When starting the BunkerWeb container, you will need to add the settings :

    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.5.0
      ...
      environment:
        - USE_REAL_IP=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/10
        - REAL_IP_HEADER=X-Forwarded-For
      ...
    ```

=== "Docker autoconf"

    Before running the [Docker autoconf integration](integrations.md#docker-autoconf) stack, you will need to add the settings for the BunkerWeb container :

    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.5.0
      ...
      environment:
        - USE_REAL_IP=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/10
        - REAL_IP_HEADER=X-Forwarded-For
      ...
    ```

=== "Swarm"

    Before running the [Swarm integration](integrations.md#swarm) stack, you will need to add the settings for the BunkerWeb service :

    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.5.0
      ...
      environment:
        - USE_REAL_IP=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/10
        - REAL_IP_HEADER=X-Forwarded-For
      ...
    ```

=== "Kubernetes"

    You will need to add the settings to the environment variables of the BunkerWeb containers (doing it using the ingress is not supported because you will get into trouble when using things like Let's Encrypt) :

    ```yaml
    apiVersion: apps/v1
    kind: DaemonSet
    metadata:
      name: bunkerweb
    spec:
        ...
        spec:
          containers:
            - name: bunkerweb
              ...
              env:
                - name: USE_REAL_IP
                  value: "yes"
                - name: REAL_IP_FROM
                  value: "1.2.3.0/24 100.64.0.0/10"
                - name: REAL_IP_HEADER
                  value: "X-Forwarded-For"
    ...
    ```

=== "Linux"

    You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

    ```conf
    ...
    USE_REAL_IP=yes
    REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
    REAL_IP_HEADER=X-Forwarded-For
    ...
    ```

    Don't forget to restart the BunkerWeb service once it's done.

=== "Ansible"

    You will need to add the settings to your `my_variables.env` configuration file :

    ```conf
    ...
    USE_REAL_IP=yes
    REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
    REAL_IP_HEADER=X-Forwarded-For
    ...
    ```

    In your Ansible inventory, you can use the `variables_env` variable to set the path of configuration file :

    ```yaml
    [mybunkers]
    192.168.0.42 variables_env="{{ playbook_dir }}/my_variables.env"
    ```

	  Or alternatively, in your playbook file :

    ```yaml
    - hosts: all
        become: true
        vars:
          - variables_env: "{{ playbook_dir }}/my_variables.env"
        roles:
          - bunkerity.bunkerweb
    ```

    Run the playbook :

    ```shell
    ansible-playbook -i inventory.yml playbook.yml
    ```

=== "Vagrant"

    You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

    ```conf
    ...
    USE_REAL_IP=yes
    REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
    REAL_IP_HEADER=X-Forwarded-For
    ...
    ```

    Don't forget to restart the BunkerWeb service once it's done.

### Proxy protocol

We will assume the following regarding the load balancers or reverse proxies (you will need to update the settings depending on your configuration) :

- They use the `PROXY protocol` v1 or v2 to set the real IP
- They have IPs in the `1.2.3.0/24` and `100.64.0.0/10` networks

The following settings need to be set :

```conf
USE_REAL_IP=yes
USE_PROXY_PROTOCOL=yes
REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
REAL_IP_HEADER=proxy_protocol
```

=== "Docker"

    When starting the BunkerWeb container, you will need to add the settings :

    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.5.0
      ...
      environment:
        - USE_REAL_IP=yes
        - USE_PROXY_PROTOCOL=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/10
        - REAL_IP_HEADER=proxy_protocol
      ...
    ```

=== "Docker autoconf"

    Before running the [Docker autoconf integration](integrations.md#docker-autoconf) stack, you will need to add the settings for the BunkerWeb container :

    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.5.0
      ...
      environment:
        - USE_REAL_IP=yes
        - USE_PROXY_PROTOCOL=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/10
        - REAL_IP_HEADER=proxy_protocol
      ...
    ```

=== "Swarm"

    Before running the [Swarm integration](integrations.md#swarm) stack, you will need to add the settings for the BunkerWeb service :

    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.5.0
      ...
      environment:
        - USE_REAL_IP=yes
        - USE_PROXY_PROTOCOL=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/10
        - REAL_IP_HEADER=proxy_protocol
      ...
    ```

=== "Kubernetes"

    You will need to add the settings to the environment variables of the BunkerWeb containers (doing it using the ingress is not supported because you will get into trouble when using things like Let's Encrypt) :

    ```yaml
    apiVersion: apps/v1
    kind: DaemonSet
    metadata:
      name: bunkerweb
    spec:
        ...
        spec:
          containers:
            - name: bunkerweb
              ...
              env:
                - name: USE_REAL_IP
                  value: "yes"
                - name: USE_PROXY_PROTOCOL
                  value: "yes"
                - name: REAL_IP_FROM
                  value: "1.2.3.0/24 100.64.0.0/10"
                - name: REAL_IP_HEADER
                  value: "proxy_protocol"
    ...
    ```

=== "Linux"

    You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

    ```conf
    ...
    USE_REAL_IP=yes
    USE_PROXY_PROTOCOL=yes
    REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
    REAL_IP_HEADER=proxy_protocol
    ...
    ```

    Don't forget to restart the BunkerWeb service once it's done.

=== "Ansible"

    You will need to add the settings to your `my_variables.env` configuration file :

    ```conf
    ...
    USE_REAL_IP=yes
    USE_PROXY_PROTOCOL=yes
    REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
    REAL_IP_HEADER=proxy_protocol
    ...
    ```

    In your Ansible inventory, you can use the `variables_env` variable to set the path of configuration file :

    ```yaml
    [mybunkers]
    192.168.0.42 variables_env="{{ playbook_dir }}/my_variables.env"
    ```

	  Or alternatively, in your playbook file :

    ```yaml
    - hosts: all
        become: true
        vars:
          - variables_env: "{{ playbook_dir }}/my_variables.env"
        roles:
          - bunkerity.bunkerweb
    ```

    Run the playbook :

    ```shell
    ansible-playbook -i inventory.yml playbook.yml
    ```

=== "Vagrant"

    You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

    ```conf
    ...
    USE_REAL_IP=yes
    USE_PROXY_PROTOCOL=yes
    REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
    REAL_IP_HEADER=proxy_protocol
    ...
    ```

    Don't forget to restart the BunkerWeb service once it's done.

## Protect UDP/TCP applications

!!! warning "Feature is in beta"
		This feature is not production-ready. Feel free to test it and report us any bug using [issues](https://github.com/bunkerity/bunkerweb/issues) in the GitHub repository.

BunkerWeb can also act as **generic UDP/TCP reverse proxy** : you can protect any network-based applications working at least on layer 4 of the OSI model. Behind the hood, it leverages the [stream module](https://nginx.org/en/docs/stream/ngx_stream_core_module.html) of NGINX instead of using the "classical" http one.

Please note that not all settings and security features are available when using the stream module. You will find more info about that in the [security tuning](security-tuning.md) and [settings](settings.md) sections of the documentation.

Configuration for a basic reverse proxy is very similar to the HTTP one because it uses the same `USE_REVERSE_PROXY=yes` and `REVERSE_PROXY_HOST=myapp:4242` settings. Even the settings used when BunkerWeb is [behind a Load Balancer](#behind-load-balancer-or-reverse-proxy) are the same (but for obvious reasons, only **PROXY protocol** is supported).

On top of that, the following specific settings are used :

- `SERVER_TYPE=stream` : activate `stream` mode (generic UDP/TCP) instead of `http` one (which is the default)
- `LISTEN_STREAM_PORT=4242` : the listening "plain" (without SSL/TLS) port that BunkerWeb will listen on
- `LISTEN_STREAM_PORT_SSL=4343` : the listening "ssl/tls" port that BunkerWeb will listen on
- `USE_UDP=no` : listen for and forward UDP packets instead of TCP

For complete list of settings regarding `stream` mode, please refer to the [settings](settings.md) section of the documentation.

=== "Docker"

    When using Docker integration, the easiest way of protecting existing network applications is to add the services in the `bw-services` network :

    ```yaml
    version: "3.5"

    services:

      myapp1:
        image: istio/tcp-echo-server:1.2
        command: [ "9000", "app1" ]
        networks:
          - bw-services

      myapp2:
        image: istio/tcp-echo-server:1.2
        command: [ "9000", "app2" ]
        networks:
          - bw-services

      bunkerweb:
        image: bunkerity/bunkerweb:1.5.0
        ports:
          - 80:8080 # Keep it if you want to use Let's Encrypt automation
          - 10000:10000 # app1
          - 20000:20000 # app2
        labels:
          - "bunkerweb.INSTANCE"
        environment:
          - SERVER_NAME=app1.example.com app2.example.com
          - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
          - MULTISITE=yes
          - USE_REVERSE_PROXY=yes # Will be applied to all services
          - SERVER_TYPE=stream # Will be applied to all services
          - app1.example.com_REVERSE_PROXY_HOST=myapp1:9000
          - app1.example.com_LISTEN_STREAM_PORT=10000
          - app2.example.com_REVERSE_PROXY_HOST=myapp2:9000
          - app2.example.com_LISTEN_STREAM_PORT=20000
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

=== "Docker autoconf"

    Before running the [Docker autoconf integration](integrations.md#docker-autoconf) stack on your machine, you will need to edit the ports :

    ```yaml
    version: "3.5"

    services:

      bunkerweb:
        image: bunkerity/bunkerweb:1.5.0
        ports:
          - 80:8080 # Keep it if you want to use Let's Encrypt automation
          - 10000:10000 # app1
          - 20000:20000 # app2
      
    ...
    ```

    Once the stack is running, you can connect your existing applications to the `bw-services` network and configure BunkerWeb with labels :

    ```yaml
    version: '3.5'

    services:
      myapp1:
        image: istio/tcp-echo-server:1.2
        command: [ "9000", "app1" ]
        networks:
          bw-services:
            aliases:
              - myapp1
        labels:
          - "bunkerweb.SERVER_NAME=app1.example.com"
          - "bunkerweb.SERVER_KIND=stream"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.2
        command: [ "9000", "app2" ]
        networks:
          bw-services:
            aliases:
              - myapp2
        labels:
          - "bunkerweb.SERVER_NAME=app2.example.com"
          - "bunkerweb.SERVER_KIND=stream"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Swarm"

    Before running the [Swarm integration](integrations.md#swarm) stack on your machine, you will need to edit the ports :

    ```yaml
    version: "3.5"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.5.0
        ports:
          # Keep it if you want to use Let's Encrypt automation
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
          - published: 10000
            target: 10000
            mode: host
            protocol: tcp
    ...
    ```

    Once the stack is running, you can connect your existing applications to the `bw-services` network and configure BunkerWeb with labels :

    ```yaml
    version: '3.5'

    services:

      myapp1:
        image: istio/tcp-echo-server:1.2
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.SERVER_KIND=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.2
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.SERVER_KIND=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    Protection TCP/UDP applications using the `stream` feature is not yet supported when using the [Kubernetes integration](integrations.md#kubernetes).

=== "Linux"

    You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

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

    Don't forget to restart the BunkerWeb service once it's done.

=== "Ansible"

    You will need to add the settings to your `my_variables.env` configuration file :

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

    In your Ansible inventory, you can use the `variables_env` variable to set the path of configuration file :

    ```yaml
    [mybunkers]
    192.168.0.42 variables_env="{{ playbook_dir }}/my_variables.env"
    ```

	  Or alternatively, in your playbook file :

    ```yaml
    - hosts: all
        become: true
        vars:
          - variables_env: "{{ playbook_dir }}/my_variables.env"
        roles:
          - bunkerity.bunkerweb
    ```

    Run the playbook :

    ```shell
    ansible-playbook -i inventory.yml playbook.yml
    ```

=== "Vagrant"

    You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

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

    Don't forget to restart the BunkerWeb service once it's done.

## Custom configurations

Because BunkerWeb is based on the NGINX web server, you can add custom NGINX configurations in different NGINX contexts. You can also apply custom configurations for the ModSecurity WAF which is a core component of BunkerWeb (more info [here](security-tuning.md#modsecurity)). Here is the list of custom configurations types :

- **http** : http level of NGINX
- **server-http** : http/server level of NGINX
- **default-server-http** : server level of NGINX (only apply to the "default server" when the name supplied by the client doesn't match any server name in `SERVER_NAME`)
- **modsec-crs** : before the OWASP Core Rule Set is loaded
- **modsec** : after the OWASP Core Rule Set is loaded (also used if CRS is not loaded)
- **stream** : stream level of NGINX
- **server-stream** : stream/server level of NGINX

Custom configurations can be applied globally or only for a specific server when applicable and if the multisite mode is enabled.

The howto depends on the integration used but under the hood, applying custom configurations is done by adding files ending with the .conf suffix in their name to specific folders. To apply a custom configuration for a specific server, the file is written to a subfolder which is named as the primary server name.

Some integrations offer a more convenient way of applying configurations such as using [Configs](https://docs.docker.com/engine/swarm/configs/) with Swarm or [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) with Kubernetes.

=== "Docker"

    When using the [Docker integration](integrations.md#docker), you have two choices for the addition of custom configurations :
    
    - Using specific settings `*_CUSTOM_CONF_*` as environment variables (recommended)
    - Writing .conf files to the volume mounted on /data of the scheduler
    
    **Using settings**
    
    The settings to use must follow the pattern `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` :
    
    - `<SITE>` : optional primary server name if multisite mode is enabled and the config must be applied to a specific service
    - `<TYPE>` : the type of config, accepted values are `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `STREAM` and `SERVER_STREAM`
    - `<NAME>` : the name of config without the .conf suffix

    Here is a dummy example using a docker-compose file :

    ```yaml
    ...
    mybunker:
      image: bunkerity/bunkerweb:1.5.0
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

    **Using files**

    The first thing to do is to create the folders :

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    You can now write your configurations :

    ```shell
    echo "location /hello {
    	default_type 'text/plain';
    	content_by_lua_block {
    		ngx.say('world')
    	}
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Because the scheduler runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    When starting the scheduler container, you will need to mount the folder on /data :

    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.5.0
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Docker autoconf"

    When using the [Docker autoconf integration](integrations.md#docker-autoconf), you have two choices for adding custom configurations :

    - Using specific settings `*_CUSTOM_CONF_*` as labels (easiest)
    - Writing .conf files to the volume mounted on /data of the scheduler

    **Using labels**

    !!! warning "Limitations using labels"
        When using labels with the Docker autoconf integration, you can only apply custom configurations for the corresponding web service. Applying **http**, **default-server-http**, **stream** or any global configurations (like **server-http** or **server-stream** for all services) is not possible : you will need to mount files for that purpose.

    The labels to use must follow the pattern `bunkerweb.CUSTOM_CONF_<TYPE>_<NAME>` :
    
    - `<TYPE>` : the type of config, accepted values are `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS` and `SERVER_STREAM`
    - `<NAME>` : the name of config without the .conf suffix 

    Here is a dummy example using a docker-compose file :

    ```yaml
    myapp:
      image: tutum/hello-world
      labels:
        - |
          bunkerweb.CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
                ngx.say('world')
    	  }
      ...
    ```

    **Using files**

    The first thing to do is to create the folders :
  
    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    You can now write your configurations :
  
    ```shell
    echo "location /hello {
    	default_type 'text/plain';
    	content_by_lua_block {
    		ngx.say('world')
    	}
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```
  
    Because the scheduler runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    When starting the scheduler container, you will need to mount the folder on /data :

    ```yaml
    myautoconf:
      image: bunkerity/bunkerweb-scheduler:1.5.0
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Swarm"

    When using the [Swarm integration](integrations.md#swarm), custom configurations are managed using [Docker Configs](https://docs.docker.com/engine/swarm/configs/).

    To keep it simple, you don't even need to attach the Config to a service : the autoconf service is listening for Config events and will update the custom configurations when needed.

    When creating a Config, you will need to add special labels :

    * **bunkerweb.CONFIG_TYPE** : must be set to a valid custom configuration type (http, server-http, default-server-http, modsec, modsec-crs, stream or server-stream)
    * **bunkerweb.CONFIG_SITE** : set to a server name to apply configuration to that specific server (optional, will be applied globally if unset)

    Here is the example :

    ```shell
    echo "location /hello {
    	default_type 'text/plain';
    	content_by_lua_block {
    		ngx.say('world')
    	}
    }" | docker config create -l bunkerweb.CONFIG_TYPE=server-http my-config -
    ```

    There is no update mechanism : the alternative is to remove an existing config using `docker config rm` and then recreate it.

=== "Kubernetes"

    When using the [Kubernetes integration](integrations.md#kubernetes), custom configurations are managed using [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/).

    To keep it simple, you don't even need to use the ConfigMap with a Pod (e.g. as environment variable or volume) : the autoconf Pod is listening for ConfigMap events and will update the custom configurations when needed.

    When creating a ConfigMap, you will need to add special labels :

    * **bunkerweb.io/CONFIG_TYPE** : must be set to a valid custom configuration type (http, server-http, default-server-http, modsec, modsec-crs, stream or server-stream)
    * **bunkerweb.io/CONFIG_SITE** : set to a server name to apply configuration to that specific server (optional, will be applied globally if unset)

    Here is the example :

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

=== "Linux"

    When using the [Linux integration](integrations.md#linux), custom configurations must be written to the /etc/bunkerweb/configs folder.

    Here is an example for server-http/hello-world.conf :

    ```conf
    location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }
    ```

    Because BunkerWeb runs as an unprivileged user (nginx:nginx), you will need to edit the permissions :

    ```shell
    chown -R root:nginx /etc/bunkerweb/configs && \
    chmod -R 770 /etc/bunkerweb/configs
    ```

    Don't forget to restart the BunkerWeb service once it's done.

=== "Ansible"

    The `custom_configs_path[]` variable is a dictionary with configuration types (`http`, `server-http`, `modsec`, `modsec-crs`, `stream` and `server-stream`) as keys and the corresponding values are path containing the configuration files.

    Here is an example for server-http/hello-world.conf :

    ```conf
    location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }
    ```

    And the corresponding `custom_configs_path[server-http]` variable used in your inventory :

    ```yaml
      [mybunkers]
      192.168.0.42 custom_configs_path={"server-http": "{{ playbook_dir }}/server-http"}
    ```

    Or alternatively, in your playbook file :

    ```yaml
    - hosts: all
      become: true
      vars:
        - custom_configs_path: {
            server-http: "{{ playbook_dir }}/server-http"
          }
      roles:
        - bunkerity.bunkerweb
    ```

    Run the playbook :

    ```shell
    ansible-playbook -i inventory.yml playbook.yml
    ```

=== "Vagrant"

    When using the [Vagrant integration](integrations.md#vagrant), custom configurations must be written to the `/etc/bunkerweb/configs` folder.

    Here is an example for server-http/hello-world.conf :

    ```conf
    location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }
    ```

    Because BunkerWeb runs as an unprivileged user (nginx:nginx), you will need to edit the permissions :

    ```shell
    chown -R root:nginx /etc/bunkerweb/configs && \
    chmod -R 770 /etc/bunkerweb/configs
    ```

    Don't forget to restart the BunkerWeb service once it's done.

## PHP

!!! warning "Support is in beta"
	At the moment, PHP support with BunkerWeb is still in beta and we recommend you use a reverse-proxy architecture if you can. By the way, PHP is not supported at all for some integrations like Kubernetes.

!!! tip "Testing"
	To perform quick tests when multisite mode is enabled (and if you don't have the proper DNS entries set up for the domains) you can use curl with the HTTP Host header of your choice :
	```shell
	curl -H "Host: app1.example.com" http://ip-or-fqdn-of-server
	```

	If you are using HTTPS, you will need to play with SNI :
	```shell
	curl -H "Host: app1.example.com" --resolve example.com:443:ip-of-server https://example.com
	```

BunkerWeb supports PHP using external or remote [PHP-FPM](https://www.php.net/manual/en/install.fpm.php) instances. We will assume that you are already familiar with managing that kind of services.

 The following settings can be used :

- `REMOTE_PHP` : Hostname of the remote PHP-FPM instance.
- `REMOTE_PHP_PATH` : Root folder containing files in the remote PHP-FPM instance.
- `LOCAL_PHP` : Path to the local socket file of PHP-FPM instance.
- `LOCAL_PHP_PATH` : Root folder containing files in the local PHP-FPM instance.

=== "Docker"

    When using the [Docker integration](integrations.md#docker), to support PHP applications, you will need to :

    - Mount your PHP files into the `/var/www/html` folder of BunkerWeb
    - Set up a PHP-FPM container for your application and mount the folder containing PHP files
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as environment variables when starting BunkerWeb

    If you enable the [multisite mode](concepts.md#integration), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    We will assume that your PHP apps are located into a folder named `www`. Please note that you will need to fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33 if you use the `php:fpm` image) is the owner of the files and folders :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    You can now run BunkerWeb, configure it for your PHP application and also run the PHP apps :

    ```yaml
    version: "3.5"

    services:

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

      bunkerweb:
        image: bunkerity/bunkerweb:1.5.0
        volumes:
          - ./www:/var/www/html
        ports:
          - 80:8080
          - 443:8443
        labels:
          - "bunkerweb.INSTANCE"
        environment:
          - SERVER_NAME=app1.example.com app2.example.com
          - MULTISITE=yes
          - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
          - app1.example.com_REMOTE_PHP=myapp1
          - app1.example.com_REMOTE_PHP_PATH=/app
          - app2.example.com_REMOTE_PHP=myapp2
          - app2.example.com_REMOTE_PHP_PATH=/app
          - app3.example.com_REMOTE_PHP=myapp3
          - app3.example.com_REMOTE_PHP_PATH=/app
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

=== "Docker autoconf"

    !!! info "Multisite mode enabled"
        The [Docker autoconf integration](integrations.md#docker-autoconf) integration implies the use of multisite mode : protecting one PHP application is the same as protecting multiple ones.

    When using the [Docker autoconf integration](integrations.md#docker-autoconf), to support PHP applications, you will need to :

    - Mount your PHP files into the `/var/www/html` folder of BunkerWeb
    - Set up a PHP-FPM containers for your applications and mount the folder containing PHP apps
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as labels for your PHP-FPM container

    Since the Docker autoconf implies using the [multisite mode](concepts.md#integration), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    Once the folders are created, copy your files and fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33 if you use the `php:fpm` image) is the owner of the files and folders :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```
	
    When you start the BunkerWeb autoconf stack, mount the `www` folder into `/var/www/html` for the BunkerWeb container :

    ```yaml
    version: '3.5'

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.5.0
        volumes:
          - ./www:/var/www/html
        labels:
          - "bunkerweb.INSTANCE"
        environment:
          - MULTISITE=yes
          - DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db # Remember to set a stronger password for the database
          - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
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

    You can now create your PHP-FPM containers, mount the correct subfolders and use labels to configure BunkerWeb :

    ```yaml
    version: '3.5'
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

=== "Swarm"

    !!! info "Multisite mode enabled"
        The [Swarm integration](integrations.md#docker-autoconf) integration implies the use of multisite mode : protecting one PHP application is the same as protecting multiple ones.

    !!! info "Shared volume"
        Using PHP with the Docker Swarm integration needs a shared volume between all BunkerWeb and PHP-FPM instances which is not covered in this documentation.

    When using the [Docker autoconf integration](integrations.md#docker-autoconf), to support PHP applications, you will need to :

    - Mount your PHP files into the `/var/www/html` folder of BunkerWeb
    - Set up a PHP-FPM containers for your applications and mount the folder containing PHP apps
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as labels for your PHP-FPM container

    Since the Swarm integration implies using the [multisite mode](concepts.md#integration), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    As an example, we will consider that you have a shared folder mounted on your worker nodes on the `/shared` endpoint.

    Once the folders are created, copy your files and fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33 if you use the `php:fpm` image) is the owner of the files and folders :

    ```shell
    chown -R 33:101 /shared/www && \
    find /shared/www -type f -exec chmod 0640 {} \; && \
    find /shared/www -type d -exec chmod 0750 {} \;
    ```
	
	  When you start the BunkerWeb stack, mount the `/shared/www` folder into `/var/www/html` for the BunkerWeb container :

    ```yaml
    version: "3.5"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.5.0
        volumes:
          - /shared/www:/var/www/html
    ...
    ```

    You can now create your PHP-FPM services, mount the correct subfolders and use labels to configure BunkerWeb :

    ```yaml
    version: '3.5'
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

=== "Kubernetes"

	!!! warning "PHP is not supported for Kubernetes"
		Kubernetes integration allows configuration through [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) and the BunkerWeb controller only supports HTTP applications at the moment.

=== "Linux"

    We will assume that you already have the [Linux integration](integrations.md#linux) stack running on your machine.

    By default, BunkerWeb will search for web files inside the `/var/www/html` folder. You can use it to store your PHP applications. Please note that you will need to configure your PHP-FPM service to get or set the user/group of the running processes and the UNIX socket file used to communicate with BunkerWeb.

    First of all, you will need to make sure that your PHP-FPM instance can access the files inside the `/var/www/html` folder and also that BunkerWeb can access the UNIX socket file in order to communicate with PHP-FPM. We recommend to set a different user like `www-data` for the PHP-FPM service and to give the nginx group access to the UNIX socket file. Here is corresponding PHP-FPM configuration :

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

    Don't forget to restart your PHP-FPM service :

    ```shell
    systemctl restart php-fpm
    ```

    If you enable the [multisite mode](concepts.md#integration), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    /var/www/html
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    Please note that you will need to fix the permissions so BunkerWeb (group `nginx`) can at least read files and list folders and PHP-FPM (user `www-data` but it might be different depending on your system) is the owner of the files and folders :

    ```shell
    chown -R www-data:nginx /var/www/html && \
    find /var/www/html -type f -exec chmod 0640 {} \; && \
    find /var/www/html -type d -exec chmod 0750 {} \;
    ```

    You can now edit the `/etc/bunkerweb/variable.env` file :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    MULTISITE=yes
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app1.example.com_LOCAL_PHP_PATH=/var/www/html/app1.example.com
    app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app2.example.com_LOCAL_PHP_PATH=/var/www/html/app2.example.com
    app3.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app3.example.com_LOCAL_PHP_PATH=/var/www/html/app3.example.com
    ```

    Let's check the status of BunkerWeb :

    ```shell
    systemctl status bunkerweb
    ```

    If it's already running we can restart it :

    ```shell
    systemctl restart bunkerweb
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb
    ```

=== "Ansible"

    !!! info "Linux"
        Please follow the instruction for Linux integration to create a local `www` folder (permissions are not needed, Ansible will do it for you).

    We will assume that you already have the [Ansible integration](integrations.md#ansible) setup on your machine.

    Content of the `my_variables.env` configuration file :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    MULTISITE=yes
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app1.example.com_LOCAL_PHP_PATH=/var/www/html/app1.example.com
    app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app2.example.com_LOCAL_PHP_PATH=/var/www/html/app2.example.com
    app3.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app3.example.com_LOCAL_PHP_PATH=/var/www/html/app3.example.com
    ```
	
    The `custom_site` variable can be used to specify a directory containing your application files (e.g : `www`) that will be copied to `/var/www/html` and the `custom_www_owner` variable contains the owner that should be set for the files and folders. Here is an example using the Ansible inventory (replace `www-data` with the user running the PHP-FPM service):

    ```ini
    [mybunkers]
    192.168.0.42 variables_env="{{ playbook_dir }}/my_variables.env" custom_www="{{ playbook_dir }}/my_app" custom_www_owner="www-data"
    ```
	
    Or alternatively, in your playbook file :

    ```yaml
    - hosts: all
      become: true
      vars:
      - variables_env: "{{ playbook_dir }}/my_variables.env"
      - custom_www: "{{ playbook_dir }}/www"
      - custom_www_owner: "www-data"
      roles:
      - bunkerity.bunkerweb
    ```

	You can now run the playbook :

	```shell
	ansible-playbook -i inventory.yml playbook.yml
	```

=== "Vagrant"

    !!! info "Linux"
        Please follow the instruction for Linux integration to create the `/var/www/html` folder.

    We will assume that you already have the [Vagrant integration](integrations.md#vagrant) stack running on your machine.

    Once PHP files are copied into the `/var/www/html`folder, you can now edit the `/etc/bunkerweb/variable.env` file :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    MULTISITE=yes
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app1.example.com_LOCAL_PHP_PATH=/var/www/html/app1.example.com
    app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app2.example.com_LOCAL_PHP_PATH=/var/www/html/app2.example.com
    app3.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app3.example.com_LOCAL_PHP_PATH=/var/www/html/app3.example.com
    ```

    Let's check the status of BunkerWeb :

    ```shell
    systemctl status bunkerweb
    ```

    If it's already running we can restart it :

    ```shell
    systemctl restart bunkerweb
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb
    ```

## IPv6

!!! warning "Feature is in beta"
		This feature is not production-ready. Feel free to test it and report us any bug using [issues](https://github.com/bunkerity/bunkerweb/issues) in the GitHub repository.

By default, BunkerWeb will only listen on IPv4 adresses and won't use IPv6 for network communications. If you want to enable IPv6 support, you need to set `USE_IPV6=yes`. Please note that IPv6 configuration of your network and environment is out-of-the-scope of this documentation.

=== "Docker"

    First of all, you will need to configure your Docker daemon to enable IPv6 support for containers and use ip6tables if needed. Here is sample configuration for your `/etc/docker/daemon.json` file :

    ```json
    {
      "experimental": true,
      "ipv6": true,
      "ip6tables": true,
      "fixed-cidr-v6": "fd00:dead:beef::/48"
    }
    ```

    You can now restart the Docker service to apply the changes :

    ```shell
    systemctl restart docker
    ```

    Once Docker is setup to support IPv6 you can add the `USE_IPV6` setting and configure the `bw-services` for IPv6 :

    ```yaml
    version: '3.5'

    services:

      bunkerweb:
        image: bunkerity/bunkerweb:1.5.0
        environment:
          - USE_IPv6=yes
    
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

=== "Docker autoconf"

    First of all, you will need to configure your Docker daemon to enable IPv6 support for containers and use ip6tables if needed. Here is sample configuration for your `/etc/docker/daemon.json` file :

    ```json
    {
      "experimental": true,
      "ipv6": true,
      "ip6tables": true,
      "fixed-cidr-v6": "fd00:dead:beef::/48"
    }
    ```

    You can now restart the Docker service to apply the changes :

    ```shell
    systemctl restart docker
    ```

    Once Docker is setup to support IPv6 you can add the `USE_IPV6` setting and configure the IPv6 for the `bw-services` network :

    ```yaml
    version: '3.5'

    services:

      bunkerweb:
        image: bunkerity/bunkerweb:1.5.0
        environment:
          - USE_IPv6=yes
    
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