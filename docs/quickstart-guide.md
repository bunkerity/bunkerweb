# Quickstart guide

!!! info "Prerequisites"
    We assume that you're already familiar with the [core concepts](/1.4/concepts) and you have followed the [integrations instructions](/1.4/integrations) for your environment.

!!! tip "Going further"
		To demonstrate the use of BunkerWeb, we will deploy a dummy "Hello World" web application as an example. See the [examples folder](https://github.com/bunkerity/bunkerweb/tree/master/examples) of the repository to get real-world examples.

## Protect HTTP applications

Protecting existing web applications already accessible with the HTTP(S) protocol is the main goal of BunkerWeb : it will act as a classical [reverse proxy](https://en.wikipedia.org/wiki/Reverse_proxy) with extra security features.

The following settings can be used :

- `USE_REVERSE_PROXY` : enable/disable reverse proxy mode
- `REVERSE_PROXY_URL` : the public path prefix
- `REVERSE_PROXY_HOST` : (internal) address of the proxied web application

You will find more settings about reverse proxy in the [settings section](/1.4/settings/#reverse-proxy) of the documentation.

### Single application

=== "Docker"

    When using Docker integration, the easiest way of protecting an existing application is to create a network so BunkerWeb can send requests using the container name.

    Create the Docker network if it's not already created :
    ```shell
    docker network create bw-net
    ```

    Then instantiate your app :
    ```shell
    docker run -d \
           --name myapp \
    	   --network bw-net \
    	   nginxdemos/hello:plain-text
    ```

    Create the BunkerWeb volume if it's not already created :
    ```shell
    docker volume create bw-data
    ```

    You can now run BunkerWeb and configure it for your app :
    ```shell
    docker run -d \
           --name mybunker \
    	   --network bw-net \
    	   -p 80:8080 \
    	   -p 443:8443 \
    	   -v bw-data:/data \
    	   -e SERVER_NAME=www.example.com \
    	   -e USE_REVERSE_PROXY=yes \
    	   -e REVERSE_PROXY_URL=/ \
    	   -e REVERSE_PROXY_HOST=http://myapp \
    	   bunkerity/bunkerweb:1.4.2
    ```

    Here is the docker-compose equivalent :
    ```yaml
    version: '3'

    services:

      mybunker:
    	image: bunkerity/bunkerweb:1.4.2
    	ports:
    	  - 80:8080
    	  - 443:8443
    	volumes:
    	  - bw-data:/data
    	environment:
    	  - USE_REVERSE_PROXY=yes
    	  - REVERSE_PROXY_URL=/
    	  - REVERSE_PROXY_HOST=http://myapp
    	networks:
    	  - bw-net

      myapp:
    	image: nginxdemos/hello:plain-text
    	networks:
    	  - bw-net

    volumes:
      bw-data:

    networks:
      bw-net:
    	name: bw-net
    ```

=== "Docker autoconf"

    We will assume that you already have the [Docker autoconf integration](/1.4/integrations/#docker-autoconf) stack running on your machine and connected to a network called bw-services.

    You can instantiate your container and pass the settings as labels :
    ```shell
    docker run -d \
           --name myapp \
    	   --network bw-services \
    	   -l bunkerweb.SERVER_NAME=www.example.com \
    	   -l bunkerweb.USE_REVERSE_PROXY=yes \
    	   -l bunkerweb.USE_REVERSE_URL=/ \
    	   -l bunkerweb.REVERSE_PROXY_HOST=http://myapp \
    	   nginxdemos/hello:plain-text
    ```

    Here is the docker-compose equivalent :
    ```yaml
    version: '3'

    services:

      myapp:
    	image: nginxdemos/hello:plain-text
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
    	external:
    	  name: bw-services
    ```

=== "Swarm"

    We will assume that you already have the [Swarm integration](/1.4/integrations/#swarm) stack running on your cluster.

    You can instantiate your service and pass the settings as labels :
    ```shell
    docker service \
       create \
       --name myapp \
       --network bw-services \
       -l bunkerweb.SERVER_NAME=www.example.com \
       -l bunkerweb.USE_REVERSE_PROXY=yes \
       -l bunkerweb.REVERSE_PROXY_HOST=http://myapp \
       -l bunkerweb.REVERSE_PROXY_URL=/ \
       nginxdemos/hello:plain-text
    ```

    Here is the docker-compose equivalent (using `docker stack deploy`) :
    ```yaml
    version: "3"

    services:

      myapp:
    	image: nginxdemos/hello:plain-text
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
    	external:
    	  name: bw-services
    ```

=== "Kubernetes"

    We will assume that you already have the [Kubernetes integration](/1.4/integrations/#kubernetes) stack running on your cluster.

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
    		image: nginxdemos/hello:plain-text
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
    	bunkerweb.io/AUTOCONF: "yes"
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

    We will assume that you already have the [Linux integration](/1.4/integrations/#linux) stack running on your machine.

    The following command will run a basic HTTP server on the port 8000 and deliver the files in the current directory :
    ```shell
    python3 -m http.server -b 127.0.0.1
    ```

    Configuration of BunkerWeb is done by editing the `/opt/bunkerweb/variables.env` file :
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

    If it's already running we can just reload it :
    ```shell
    systemctl reload bunkerweb
    ```

    Otherwise, we will need to start it :
    ```shell
    systemctl start bunkerweb
    ```

=== "Ansible"

    We will assume that you already have a service running and you want to use bunkerweb as a reverse-proxy.

    The following command will run a basic HTTP server on the port 8000 and deliver the files in the current directory :
    ```shell
    python3 -m http.server -b 127.0.0.1
    ```

    Configuration of the `variables.env` file :
    ```conf
    SERVER_NAME=www.example.com
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    USE_REVERSE_PROXY=yes
    REVERSE_PROXY_URL=/
    REVERSE_PROXY_HOST=http://127.0.0.1:8000
    ```

    In your Ansible inventory, you can use the `variables_env` variable to configure BunkerWeb :
	```yaml
	all:
  	  children:
        Groups:
          hosts: 
            "Your_IP_Address":
          vars:
            variables_env: ../variables.env
	```

	Or in INI format :
	```ini
	[all]
	host

	[all:vars]
	variables_env = ../variables.env
	```

	Run the playbook :
	```shell
	ansible-playbook -i inventory.yml playbook.yml
	```

### Multiple applications

!!! tip "Testing"
		To perform quick tests when multisite mode is enabled (and if you don't have the proper DNS entries set up for the domains) you can use curl with the HTTP Host header of your choice :
		`shell curl -H "Host: app1.example.com" http://ip-or-fqdn-of-server `

=== "Docker"

    When using Docker integration, the easiest way of protecting multiple existing applications is to create a network so BunkerWeb can send requests using the container names.

    Create the Docker network if it's not already created :
    ```shell
    docker network create bw-net
    ```

    Then instantiate your apps :
    === "App #1"
    	```shell
    	docker run -d \
    		   --name myapp1 \
    		   --network bw-net \
    		   nginxdemos/hello:plain-text
    	```
    === "App #2"
    	```shell
    	docker run -d \
    		   --name myapp2 \
    		   --network bw-net \
    		   nginxdemos/hello:plain-text
    	```
    === "App #3"
    	```shell
    	docker run -d \
    		   --name myapp3 \
    		   --network bw-net \
    		   nginxdemos/hello:plain-text
    	```

    Create the BunkerWeb volume if it's not already created :
    ```shell
    docker volume create bw-data
    ```

    You can now run BunkerWeb and configure it for your apps :
    ```shell
    docker run -d \
           --name mybunker \
    	   --network bw-net \
    	   -p 80:8080 \
    	   -p 443:8443 \
    	   -v bw-data:/data \
    	   -e MULTISITE=yes
    	   -e "SERVER_NAME=app1.example.com app2.example.com app3.example.com" \
    	   -e USE_REVERSE_PROXY=yes \
    	   -e REVERSE_PROXY_URL=/ \
    	   -e app1.example.com_REVERSE_PROXY_HOST=http://myapp1 \
    	   -e app2.example.com_REVERSE_PROXY_HOST=http://myapp2 \
    	   -e app3.example.com_REVERSE_PROXY_HOST=http://myapp3 \
    	   bunkerity/bunkerweb:1.4.2
    ```

    Here is the docker-compose equivalent :
    ```yaml
    version: '3'

    services:

      mybunker:
    	image: bunkerity/bunkerweb:1.4.2
    	ports:
    	  - 80:8080
    	  - 443:8443
    	volumes:
    	  - bw-data:/data
    	environment:
    	  - MULTISITE=yes
    	  - SERVER_NAME=app1.example.com app2.example.com app3.example.com
    	  - USE_REVERSE_PROXY=yes
    	  - REVERSE_PROXY_URL=/
    	  - app1.example.com_REVERSE_PROXY_HOST=http://myapp1
    	  - app2.example.com_REVERSE_PROXY_HOST=http://myapp2
    	  - app3.example.com_REVERSE_PROXY_HOST=http://myapp3
    	networks:
    	  - bw-net

      myapp1:
    	image: nginxdemos/hello:plain-text
    	networks:
    	  - bw-net

      myapp2:
    	image: nginxdemos/hello:plain-text
    	networks:
    	  - bw-net

      myapp3:
    	image: nginxdemos/hello:plain-text
    	networks:
    	  - bw-net

    volumes:
      bw-data:

    networks:
      bw-net:
    	name: bw-net
    ```

=== "Docker autoconf"

    We will assume that you already have the [Docker autoconf integration](/1.4/integrations/#docker-autoconf) stack running on your machine and connected to a network called bw-services.

    You can instantiate your containers and pass the settings as labels :
    === "App #1"
    	```shell
    	docker run -d \
           --name myapp1 \
    	   --network bw-services \
    	   -l bunkerweb.SERVER_NAME=app1.example.com \
    	   -l bunkerweb.USE_REVERSE_PROXY=yes \
    	   -l bunkerweb.USE_REVERSE_URL=/ \
    	   -l bunkerweb.REVERSE_PROXY_HOST=http://myapp1 \
    	   nginxdemos/hello:plain-text
    	```

    	Here is the docker-compose equivalent :
    	```yaml
    	version: '3'

    	services:

    	  myapp1:
    		image: nginxdemos/hello:plain-text
    		networks:
    		  bw-services:
    			aliases:
    			  - myapp1
    		labels:
    		  - "bunkerweb.SERVER_NAME=app1.example.com"
    		  - "bunkerweb.USE_REVERSE_PROXY=yes"
    		  - "bunkerweb.REVERSE_PROXY_URL=/"
    		  - "bunkerweb.REVERSE_PROXY_HOST=http://myapp1"

    	networks:
    	  bw-services:
    		external:
    		  name: bw-services
    	```

    === "App #2"
    	```shell
    	docker run -d \
           --name myapp2 \
    	   --network bw-services \
    	   -l bunkerweb.SERVER_NAME=app2.example.com \
    	   -l bunkerweb.USE_REVERSE_PROXY=yes \
    	   -l bunkerweb.USE_REVERSE_URL=/ \
    	   -l bunkerweb.REVERSE_PROXY_HOST=http://myapp2 \
    	   nginxdemos/hello:plain-text
    	```

    	Here is the docker-compose equivalent :
    	```yaml
    	version: '3'

    	services:

    	  myapp2:
    		image: nginxdemos/hello:plain-text
    		networks:
    		  bw-services:
    			aliases:
    			  - myapp2
    		labels:
    		  - "bunkerweb.SERVER_NAME=app2.example.com"
    		  - "bunkerweb.USE_REVERSE_PROXY=yes"
    		  - "bunkerweb.REVERSE_PROXY_URL=/"
    		  - "bunkerweb.REVERSE_PROXY_HOST=http://myapp2"

    	networks:
    	  bw-services:
    		external:
    		  name: bw-services
    	```
    === "App #3"
    	```shell
    	docker run -d \
           --name myapp3 \
    	   --network bw-services \
    	   -l bunkerweb.SERVER_NAME=app3.example.com \
    	   -l bunkerweb.USE_REVERSE_PROXY=yes \
    	   -l bunkerweb.USE_REVERSE_URL=/ \
    	   -l bunkerweb.REVERSE_PROXY_HOST=http://myapp3 \
    	   nginxdemos/hello:plain-text
    	```

    	Here is the docker-compose equivalent :
    	```yaml
    	version: '3'

    	services:

    	  myapp3:
    		image: nginxdemos/hello:plain-text
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
    		external:
    		  name: bw-services
    	```

=== "Swarm"

    We will assume that you already have the [Swarm integration](/1.4/integrations/#swarm) stack running on your cluster.

    You can instantiate your services and pass the settings as labels :
    === "App #1"
    	```shell
    	docker service \
    	   create \
    	   --name myapp1 \
    	   --network bw-services \
    	   -l bunkerweb.SERVER_NAME=app1.example.com \
    	   -l bunkerweb.USE_REVERSE_PROXY=yes \
    	   -l bunkerweb.REVERSE_PROXY_HOST=http://myapp1 \
    	   -l bunkerweb.REVERSE_PROXY_URL=/ \
    	   nginxdemos/hello:plain-text
    	```

    	Here is the docker-compose equivalent (using `docker stack deploy`) :
    	```yaml
    	version: "3"

    	services:

    	  myapp1:
    		image: nginxdemos/hello:plain-text
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

    	networks:
    	  bw-services:
    		external:
    		  name: bw-services
    	```

    === "App #2"
    	```shell
    	docker service \
    	   create \
    	   --name myapp2 \
    	   --network bw-services \
    	   -l bunkerweb.SERVER_NAME=app2.example.com \
    	   -l bunkerweb.USE_REVERSE_PROXY=yes \
    	   -l bunkerweb.REVERSE_PROXY_HOST=http://myapp2 \
    	   -l bunkerweb.REVERSE_PROXY_URL=/ \
    	   nginxdemos/hello:plain-text
    	```

    	Here is the docker-compose equivalent (using `docker stack deploy`) :
    	```yaml
    	version: "3"

    	services:

    	  myapp2:
    		image: nginxdemos/hello:plain-text
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

    	networks:
    	  bw-services:
    		external:
    		  name: bw-services
    	```

    === "App #3"
    	```shell
    	docker service \
    	   create \
    	   --name myapp3 \
    	   --network bw-services \
    	   -l bunkerweb.SERVER_NAME=app3.example.com \
    	   -l bunkerweb.USE_REVERSE_PROXY=yes \
    	   -l bunkerweb.REVERSE_PROXY_HOST=http://myapp3 \
    	   -l bunkerweb.REVERSE_PROXY_URL=/ \
    	   nginxdemos/hello:plain-text
    	```

    	Here is the docker-compose equivalent (using `docker stack deploy`) :
    	```yaml
    	version: "3"

    	services:

    	  myapp3:
    		image: nginxdemos/hello:plain-text
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
    		external:
    		  name: bw-services
    	```

=== "Kubernetes"

    We will assume that you already have the [Kubernetes integration](/1.4/integrations/#kubernetes) stack running on your cluster.

    Let's also assume that you have some typical Deployments with Services to access the web applications from within the cluster :

    === "App #1"
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
    			image: nginxdemos/hello:plain-text
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

    === "App #2"
    	```yaml
    	apiVersion: apps/v1
    	kind: Deployment
    	metadata:
    	  name: app2
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
    			image: nginxdemos/hello:plain-text
    			ports:
    			- containerPort: 80
    	---
    	apiVersion: v1
    	kind: Service
    	metadata:
    	  name: svc-app2
    	spec:
    	  selector:
    		app: app2
    	  ports:
    		- protocol: TCP
    		  port: 80
    		  targetPort: 80
    	```

    === "App #3"
    	```yaml
    	apiVersion: apps/v1
    	kind: Deployment
    	metadata:
    	  name: app3
    	  labels:
    		app: app3
    	spec:
    	  replicas: 1
    	  selector:
    		matchLabels:
    		  app: app3
    	  template:
    		metadata:
    		  labels:
    			app: app3
    		spec:
    		  containers:
    		  - name: app1
    			image: nginxdemos/hello:plain-text
    			ports:
    			- containerPort: 80
    	---
    	apiVersion: v1
    	kind: Service
    	metadata:
    	  name: svc-app3
    	spec:
    	  selector:
    		app: app3
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
    	bunkerweb.io/AUTOCONF: "yes"
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

    We will assume that you already have the [Linux integration](/1.4/integrations/#linux) stack running on your machine.

    Let's assume that you have some web applications running on the same machine as BunkerWeb :

    === "App #1"
    	The following command will run a basic HTTP server on the port 8001 and deliver the files in the current directory :
    	```shell
    	python3 -m http.server -b 127.0.0.1 8001
    	```

    === "App #2"
    	The following command will run a basic HTTP server on the port 8002 and deliver the files in the current directory :
    	```shell
    	python3 -m http.server -b 127.0.0.1 8002
    	```

    === "App #3"
    	The following command will run a basic HTTP server on the port 8003 and deliver the files in the current directory :
    	```shell
    	python3 -m http.server -b 127.0.0.1 8003
    	```

    Configuration of BunkerWeb is done by editing the `/opt/bunkerweb/variables.env` file :
    ```conf
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
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

    If it's already running we can just reload it :
    ```shell
    systemctl reload bunkerweb
    ```

    Otherwise, we will need to start it :
    ```shell
    systemctl start bunkerweb
    ```

=== "Ansible"

    Let's assume that you have some web applications running on the same machine as BunkerWeb :

    === "App #1"
    	The following command will run a basic HTTP server on the port 8001 and deliver the files in the current directory :
    	```shell
    	python3 -m http.server -b 127.0.0.1 8001
    	```

    === "App #2"
    	The following command will run a basic HTTP server on the port 8002 and deliver the files in the current directory :
    	```shell
    	python3 -m http.server -b 127.0.0.1 8002
    	```

    === "App #3"
    	The following command will run a basic HTTP server on the port 8003 and deliver the files in the current directory :
    	```shell
    	python3 -m http.server -b 127.0.0.1 8003
    	```

    Configuration of the `variables.env` file :
    ```conf
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    USE_REVERSE_PROXY=yes
    REVERSE_PROXY_URL=/
    app1.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8001
    app2.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8002
    app3.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8003
    ```

	In your Ansible inventory, you can use the `variables_env` variable to configure BunkerWeb :
	```yaml
	all:
  	  children:
        host1:
          hosts: 
            "Your_IP_Address":
		  vars:
        	variables_env: ../variables.env
		host2:
          hosts: 
            "Your_IP_Address":
		  vars:
        	variables_env = variables.env
			enable_ui=true
		host3:
          hosts: 
            "Your_IP_Address":
		  vars:
        	variables_env = ../variables.env
			custom_site=../site
			plugins=../plugins
	```

	Or in INI format :
	```ini
	[all]
	host1
	host2
	host3
	
	[host1:vars]
	variables_env = ../variables.env

	[host2:vars]
	variables_env = variables.env
	enable_ui=true

	[host3:vars]
	variables_env = ../variables.env
	custom_site=../site
	plugins=../plugins
	```

	Run the playbook :
	```shell
	ansible-playbook -i inventory.yml playbook.yml
	```

## Behind load balancer or reverse proxy

When BunkerWeb is itself behind a load balancer or a reverse proxy, you will need to configure it so it can get the real IP address of the clients. If you don't do it, the security features will block the IP address of the load balancer or reverse proxy instead of the client one.

BunkerWeb actually supports two methods to retrieve the real IP address of the client :

- Using the PROXY protocol
- Using a HTTP header like X-Forwarded-For

The following settings can be used :

- `USE_REAL_IP` : enable/disable real IP retrieval
- `USE_PROXY_PROTOCOL` : enable/disable PROXY protocol support
- `REAL_IP_FROM` : list of trusted IP/network address allowed to send us the "real IP"
- `REAL_IP_HEADER` : the HTTP header containing the real IP or special value "proxy_protocol" when using PROXY protocol

You will find more settings about real IP in the [settings section](/1.4/settings/#real-ip) of the documentation.

### HTTP header

We will assume the following regarding the load balancers or reverse proxies (you will need to update the settings depending on your configuration) :

- They use the X-Forwarded-For header to set the real IP
- They have IPs in the 1.2.3.0/24 and 100.64.0.0/16 networks

The following settings need to be set :

```conf
USE_REAL_IP=yes
REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
REAL_IP_HEADER=X-Forwarded-For
```

=== "Docker"

    When starting the BunkerWeb container, you will need to add the settings :
    ```shell
    docker run \
    	   ...
    	   -e USE_REAL_IP=yes \
    	   -e "REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16" \
    	   -e REAL_IP_HEADER=X-Forwarded-For \
    	   ...
    	   bunkerity/bunkerweb:1.4.2
    ```

    Here is the docker-compose equivalent :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.2
      ...
      environment:
        - USE_REAL_IP=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        - REAL_IP_HEADER=X-Forwarded-For
      ...
    ```

=== "Docker autoconf"

    Before running the [Docker autoconf integration](/1.4/integrations/#docker-autoconf) stack, you will need to add the settings for the BunkerWeb container :
    ```shell
    docker run \
           ...
           -e USE_REAL_IP=yes \
           -e "REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16" \
           -e REAL_IP_HEADER=X-Forwarded-For \
           ...
           bunkerity/bunkerweb:1.4.2
    ```

    Here is the docker-compose equivalent :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.2
      ...
      environment:
        - USE_REAL_IP=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        - REAL_IP_HEADER=X-Forwarded-For
      ...
    ```

=== "Swarm"

    Before running the [Swarm integration](/1.4/integrations/#swarm) stack, you will need to add the settings for the BunkerWeb service :
    ```shell
    docker service create \
           ...
           -e USE_REAL_IP=yes \
           -e "REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16" \
           -e REAL_IP_HEADER=X-Forwarded-For \
           ...
           bunkerity/bunkerweb:1.4.2
    ```

    Here is the docker-compose equivalent (using `docker stack deploy`) :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.2
      ...
      environment:
        - USE_REAL_IP=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        - REAL_IP_HEADER=X-Forwarded-For
      ...
    ```

=== "Kubernetes"

    You will need to add the settings to the environment variables of the bunkerweb containers (doing it using the ingress is not supported because you will get into trouble when using things like Let's Encrypt) :
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
		spec:
		  containers:
		  - name: bunkerweb
			image: bunkerity/bunkerweb:1.4.2
			...
			env:
			- name: USE_REAL_IP
			  value: "yes"
			- name: REAL_IP_HEADER
			  value: "X-Forwarded-For"
			- name: REAL_IP_FROM
			  value: "1.2.3.0/24 100.64.0.0/16"
    ...
    ```

=== "Linux"

    You will need to add the settings to the `/opt/bunkerweb/variables.env` file :
    ```conf
	...
	USE_REAL_IP=yes
	REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
	REAL_IP_HEADER=X-Forwarded-For
	...
	```

    Don't forget to reload the bunkerweb service once it's done.

=== "Ansible"

    You will need to add the settings to your `variables.env` file :
    ```conf
	...
	USE_REAL_IP=yes
	REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
	REAL_IP_HEADER=X-Forwarded-For
	...
	```

	In your Ansible inventory, you can use the `variables_env` variable to configure BunkerWeb :
	```yaml
	all:
  	  children:
        Groups:
          hosts: 
            "Your_IP_Address":
          vars:
            variables_env: ../variables.env
	```

	Or in INI format :
	```ini
	[all]
	host
	
	[all:vars]
	variables_env = ../variables.env
	```

	Run the playbook :
	```shell
	ansible-playbook -i inventory.yml playbook.yml
	```

### Proxy protocol

We will assume the following regarding the load balancers or reverse proxies (you will need to update the settings depending on your configuration) :

- They use the PROXY protocol v1 or v2 to set the real IP
- They have IPs in the 1.2.3.0/24 and 100.64.0.0/16 networks

The following settings need to be set :

```conf
USE_REAL_IP=yes
USE_PROXY_PROTOCOL=yes
REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
REAL_IP_HEADER=proxy_protocol
```

=== "Docker"

    When starting the BunkerWeb container, you will need to add the settings :
    ```shell
    docker run \
    	   ...
    	   -e USE_REAL_IP=yes \
    	   -e USE_PROXY_PROTOCOL=yes \
    	   -e "REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16" \
    	   -e REAL_IP_HEADER=proxy_protocol \
    	   ...
    	   bunkerity/bunkerweb:1.4.2
    ```

    Here is the docker-compose equivalent :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.2
      ...
      environment:
        - USE_REAL_IP=yes
    	- USE_PROXY_PROTOCOL=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        - REAL_IP_HEADER=proxy_protocol
      ...
    ```

=== "Docker autoconf"

    Before running the [Docker autoconf integration](/1.4/integrations/#docker-autoconf) stack, you will need to add the settings for the BunkerWeb container :
    ```shell
    docker run \
           ...
           -e USE_REAL_IP=yes \
    	   -e USE_PROXY_PROTOCOL=yes \
           -e "REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16" \
           -e REAL_IP_HEADER=proxy_protocol \
           ...
           bunkerity/bunkerweb:1.4.2
    ```

    Here is the docker-compose equivalent :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.2
      ...
      environment:
        - USE_REAL_IP=yes
    	- USE_PROXY_PROTOCOL=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        - REAL_IP_HEADER=proxy_protocol
      ...
    ```

=== "Swarm"

    Before running the [Swarm integration](/1.4/integrations/#swarm) stack, you will need to add the settings for the BunkerWeb service :
    ```shell
    docker service create \
           ...
           -e USE_REAL_IP=yes \
    	   -e USE_PROXY_PROTOCOL=yes \
           -e "REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16" \
           -e REAL_IP_HEADER=proxy_protocol \
           ...
           bunkerity/bunkerweb:1.4.2
    ```

    Here is the docker-compose equivalent (using `docker stack deploy`) :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.2
      ...
      environment:
        - USE_REAL_IP=yes
    	- USE_PROXY_PROTOCOL=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        - REAL_IP_HEADER=proxy_protocol
      ...
    ```

=== "Kubernetes"

    You will need to add the settings to the environment variables of the bunkerweb containers (doing it using the ingress is not supported because you will get into trouble when using things like Let's Encrypt) :
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
		spec:
		  containers:
		  - name: bunkerweb
			image: bunkerity/bunkerweb:1.4.2
			...
			env:
			- name: USE_REAL_IP
			  value: "yes"
			- name: USE_PROXY_PROTOCOL
			  value: "yes"
			- name: REAL_IP_HEADER
			  value: "proxy_protocol"
			- name: REAL_IP_FROM
			  value: "1.2.3.0/24 100.64.0.0/16"
    ...
    ```

=== "Linux"

    You will need to add the settings to the `/opt/bunkerweb/variables.env` file :
    ```conf
	...
	USE_REAL_IP=yes
	USE_PROXY_PROTOCOL=yes
	REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
	REAL_IP_HEADER=proxy_protocol
	...
	```

    Don't forget to reload the bunkerweb service once it's done.

=== "Ansible"

    You will need to add the settings to your `variables.env` file :
    ```conf
	...
	USE_REAL_IP=yes
	USE_PROXY_PROTOCOL=yes
	REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
	REAL_IP_HEADER=proxy_protocol
	...
	```

	In your Ansible inventory, you can use the `variables_env` variable to configure BunkerWeb :
	```yaml
	all:
  	  children:
        Groups:
          hosts: 
            "Your_IP_Address":
          vars:
            variables_env: ../variables.env
	```

	Or in INI format :
	```ini
	[all]
	host
	
	[all:vars]
	variables_env = ../variables.env
	```

	Run the playbook :
	```shell
	ansible-playbook -i inventory.yml playbook.yml
	```

## Custom configurations

Because BunkerWeb is based on the NGINX web server, you can add custom NGINX configurations in different NGINX contexts. You can also apply custom configurations for the ModSecurity WAF which is a core component of BunkerWeb (more info [here](/1.4/security-tuning/#modsecurity)). Here is the list of custom configurations types :

- **http** : http level of NGINX
- **server-http** : server level of NGINX
- **default-server-http** : server level of NGINX (only apply to the "default server" when the name supplied by the client doesn't match any server name in `SERVER_NAME`)
- **modsec-crs** : before the OWASP Core Rule Set is loaded
- **modsec** : after the OWASP Core Rule Set is loaded (also used if CRS is not loaded)

Custom configurations can be applied globally or only for a specific server when applicable and if multisite mode is enabled.

The howto depends on the integration used but under the hood, applying custom configurations is done by adding files ending with the .conf suffix in their name to specific folders. To apply a custom configuration for a specific server, the file is written to a subfolder which is named as the primary server name.

Some integrations offer a more convenient way of applying configurations for example using [Configs](https://docs.docker.com/engine/swarm/configs/) with Swarm or [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) with Kubernetes.

=== "Docker"

    When using the [Docker integration](/1.4/integrations/#docker), you have two choices for adding custom configurations :
    
    - Using specific settings `*_CUSTOM_CONF_*` as environment variables (easiest)
    - Writing .conf files to the volume mounted on /data
    
    **Using settings**
    
    The settings to use must follow the pattern `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` :
    
    - `<SITE>` : optional primary server name if multisite mode is enabled and the config must be applied to a specific service
    - `<TYPE>` : the type of config, accepted values are `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP`, `MODSEC` and `MODSEC_CRS`
    - `<NAME>` : the name of config without the .conf suffix

    Here is a dummy example using a docker-compose file :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.2
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

    Because BunkerWeb runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :
    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    When starting the BunkerWeb container, you will need to mount the folder on /data :
    ```shell
    docker run \
    	   ...
    	   -v "${PWD}/bw-data:/data" \
    	   ...
    	   bunkerity/bunkerweb:1.4.2
    ```

    Here is the docker-compose equivalent :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.2
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Docker autoconf"

    When using the [Docker autoconf integration](/1.4/integrations/#docker-autoconf), you have two choices for adding custom configurations :

    - Using specific settings `*_CUSTOM_CONF_*` as labels (easiest)
    - Writing .conf files to the volume mounted on /data

    **Using labels**

    !!! warning "Limitations using labels"
        When using labels with the Docker autoconf integration, you can only apply custom configurations for the corresponding web service. Applying **http**, **default-server-http** or any global configurations (like **server-http** for all services) is not possible : you will need to mount files for that purpose.

    The labels to use must follow the pattern `bunkerweb.CUSTOM_CONF_<TYPE>_<NAME>` :
    
    - `<TYPE>` : the type of config, accepted values are `SERVER_HTTP`, `MODSEC` and `MODSEC_CRS`
    - `<NAME>` : the name of config without the .conf suffix

    Here is a dummy example using a docker-compose file :
    ```yaml
    myapp:
      image: nginxdemos/hello:plain-text
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

    When starting the BunkerWeb autoconf container, you will need to mount the folder on /data :
    ```shell
    docker run \
    	   ...
    	   -v "${PWD}/bw-data:/data" \
    	   ...
    	   bunkerity/bunkerweb-autoconf:1.4.2
    ```

    Here is the docker-compose equivalent :
    ```yaml
    myautoconf:
      image: bunkerity/bunkerweb-autoconf:1.4.2
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Swarm"

    When using the [Swarm integration](/1.4/integrations/#swarm), custom configurations are managed using [Docker Configs](https://docs.docker.com/engine/swarm/configs/).

    To keep it simple, you don't even need to attach the Config to a service : the autoconf service is listening for Config events and will update the custom configurations when needed.

    When creating a Config you will need to add special labels :

    * **bunkerweb.CONFIG_TYPE** : must be set to a valid custom configuration type (http, server-http, default-server-http, modsec or modsec-crs)
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

    When using the [Kubernetes integration](/1.4/integrations/#kubernetes), custom configurations are managed using [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/).

    To keep it simple, you don't even need to use the ConfigMap with a Pod (e.g. as environment variable or volume) : the autoconf Pod is listening for ConfigMap events and will update the custom configurations when needed.

    When creating a ConfigMap you will need to add special labels :

    * **bunkerweb.io/CONFIG_TYPE** : must be set to a valid custom configuration type (http, server-http, default-server-http, modsec or modsec-crs)
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

    When using the [Linux integration](/1.4/integrations/#linux), custom configurations must be written to the /opt/bunkerweb/configs folder.

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
    chown -R root:nginx /opt/bunkerweb/configs && \
    chmod -R 770 /opt/bunkerweb/configs
    ```

    Don't forget to reload the bunkerweb service once it's done.

=== "Ansible"

    When the variable `custom_configs` is set to "true" , you could use the 
	`custom_configs_path[]` variable to write the configs to the /opt/bunkerweb/configs folder.

    Here is an example for server-http/hello-world.conf :
    ```conf
	location /hello {
		default_type 'text/plain';
		content_by_lua_block {
			ngx.say('world')
		}
	}
	```

	In your Ansible inventory, you can use the `variables_env` variable to configure BunkerWeb :
	```yaml
	all:
  	  children:
        Groups:
          hosts: 
            "Your_IP_Address":
          vars:
        	custom_configs: true
        	custom_configs_path: {
          	server-http: ../hello-world.conf,
          	#http: ../http.conf,
          	#default-server-http: ../default-server-http.conf,
          	#modsec-crs: ../modsec-crs,
          	#modsec: ../modsec
          }
	```

	Or in INI format :
	```ini
	[all]
	host
	
	[all:vars]
	custom_configs=true
	custom_configs_path={'server-http': '../hello-world.conf', 'http': '../http.conf', 'default-server-http': '../default-server-http.conf', 'modsec-crs': '../modsec-crs', 'modsec': '../modsec'}
	```

	Run the playbook :
	```shell
	ansible-playbook -i inventory.yml playbook.yml
	```

## FPM

Using PHP with Nginx is a bit tricky. 

The following settings can be used :

- `REMOTE_PHP` : Hostname of the remote PHP-FPM instance.
- `REMOTE_PHP_PATH` : Root folder containing files in the remote PHP-FPM instance.
- `DISABLE_DEFAULT_SERVER` : Close connection if the request vhost is unknown.

### Single application

=== "Docker"

    When using the [Docker integration](/1.4/integrations/#docker), you have two steps for adding custom configurations :
    
    - Using specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as environment variables
    - Writing yours files in yours folder and mounte the volume on /data
    
    Create the Docker network if it's not already created :
    ```shell
    docker network create bw-net
    ```

	Then instance the PHP-FPM container :
    ```shell
    docker run -d \
       	--name myphp \
       	--network bw-net \
       	-v AbsolutePath/bw-data/www:/app \
       	php:fpm
    ```

    You can now run BunkerWeb and configure it for your app :
    ```shell
    docker run -d \
           --name mybunker \
    	   --network bw-net \
    	   -p 80:8080 \
    	   -p 443:8443 \
    	   -v AbsolutePath/bw-data:/data \
    	   -e SERVER_NAME=www.example.com \
		   -e AUTO_LETS_ENCRYPT=yes \
		   -e DISABLE_DEFAULT_SERVER=yes \
		   -e USE_CLIENT_CACHE=yes \
		   -e USE_GZIP=yes \
		   -e REMOTE_PHP=myphp \
		   -e REMOTE_PHP_PATH=/app \
    	   bunkerity/bunkerweb:1.4.2
    ```

	Here is the docker-compose equivalent :
    ```yaml
    version: '3'

    services:

      mybunker:
    	image: bunkerity/bunkerweb:1.4.2
    	ports:
    	  - 80:8080
    	  - 443:8443
    	volumes:
    	  - ./bw-data:/data
    	environment:
    	  - SERVER_NAME=www.example.com # replace with your domain
      	  - AUTO_LETS_ENCRYPT=yes
      	  - DISABLE_DEFAULT_SERVER=yes
      	  - USE_CLIENT_CACHE=yes
      	  - USE_GZIP=yes
      	  - REMOTE_PHP=myphp
      	  - REMOTE_PHP_PATH=/app
    	networks:
    	  - bw-net

      myphp:
    	image: php:fpm
		volumes:
		  - ./bw-data:/data
    	networks:
    	  - bw-net

    networks:
      bw-net:
    ```

=== "Docker autoconf"

    We will assume that you already have the Docker autoconf integration stack running on your machine and connected to a network called bw-services.

	You can instantiate your container and pass the settings as labels :
    ```shell
    docker run -d \
        --name mybunker \
    	--network bw-autoconf \
		-v ./www:/www \
	   -p 80:8080 \
	   -p 443:8443 \
    	-e AUTOCONF_MODE=yes \
       -e MULTISITE=yes \
       -e "API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24" \
        -e SERVER_NAME= \
       -l bunkerweb.AUTOCONF \
        bunkerity/bunkerweb:1.4.2
    ```

    === "App #1"
    	```shell
    	docker run -d \
       		--name myphp1 \
       		--network bw-services \
       		-v ./www/app1.example.com:/app \
       		-l bunkerweb.DISABLE_DEFAULT_SERVER=yes \
       		-l bunkerweb.SERVER_NAME=app1.example.com \
       		-l bunkerweb.USE_CLIENT_CACHE=yes \
       		-l bunkerweb.USE_GZIP=yes \
       		-l bunkerweb.REMOTE_PHP=myphp1 \
       		-l bunkerweb.REMOTE_PHP_PATH=/app \
       		-l bunkerweb.ROOT_FOLDER=/www/app1.example.com \
       		php:fpm
    	```

    === "App #2"
    	```shell
    	docker run -d \
       		--name myphp2 \
       		--network bw-services \
       		-v ./www/app2.example.com:/app \
       		-l bunkerweb.DISABLE_DEFAULT_SERVER=yes \
       		-l bunkerweb.SERVER_NAME=app2.example.com \
       		-l bunkerweb.USE_CLIENT_CACHE=yes \
       		-l bunkerweb.USE_GZIP=yes \
       		-l bunkerweb.REMOTE_PHP=myphp2 \
       		-l bunkerweb.REMOTE_PHP_PATH=/app \
       		-l bunkerweb.ROOT_FOLDER=/www/app2.example.com \
       		php:fpm
    	```

	Here is the docker-compose equivalent :
	```yaml
	version: '3'

	services:

  	  mybunker:
    	image: bunkerity/bunkerweb:1.4.2
    	volumes: 
      	  - ./www:/www
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
    	image: bunkerity/bunkerweb-autoconf:1.4.2
    	volumes:
      	  - bw-data:/data
      	  - /var/run/docker.sock:/var/run/docker.sock:ro
    	networks:
      	  - bw-autoconf

  	  myphp1:
    	image: php:fpm
    	volumes:
      	  - ./www/app1.example.com:/app
    	networks:
      	  bw-services:
        	aliases:
            	- myphp1
    	labels:
      	  - "bunkerweb.DISABLE_DEFAULT_SERVER=yes"
      	  - "bunkerweb.SERVER_NAME=app1.example.com"
      	  - "bunkerweb.USE_CLIENT_CACHE=yes"
      	  - "bunkerweb.USE_GZIP=yes"
      	  - "bunkerweb.REMOTE_PHP=myphp1"
      	  - "bunkerweb.REMOTE_PHP_PATH=/app"
      	  - "bunkerweb.ROOT_FOLDER=/www/app1.example.com"

  	  myphp2:
    	image: php:fpm
    	volumes:
      	  - ./www/app2.example.com:/app
    	networks:
      	  bw-services:
        	aliases:
            	- myphp2
    	labels:
      	  - "bunkerweb.DISABLE_DEFAULT_SERVER=yes"
      	  - "bunkerweb.SERVER_NAME=app2.example.com"
      	  - "bunkerweb.USE_CLIENT_CACHE=yes"
      	  - "bunkerweb.USE_GZIP=yes"
      	  - "bunkerweb.REMOTE_PHP=myphp2"
      	  - "bunkerweb.REMOTE_PHP_PATH=/app"
      	  - "bunkerweb.ROOT_FOLDER=/www/app2.example.com"

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

=== "Linux"

    We will assume that you already have the [Linux integration](/1.4/integrations/#linux) stack running on your machine.

    Configuration of BunkerWeb is done by editing your local `variables.env` file :

	Depanding of your system, you may need to change `LOCAL_PHP_PATH`.

	=== "Ubuntu"
    	```conf
    	SERVER_NAME=www.example.com
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		LOCAL_PHP=/run/php/php-fpm.sock
		LOCAL_PHP_PATH=/opt/bunkerweb/www/	
    	```

	=== "Debian"
    	```conf
    	SERVER_NAME=www.example.com
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		LOCAL_PHP=/run/php/php-fpm.sock
		LOCAL_PHP_PATH=/opt/bunkerweb/www/	
    	```

	=== "CentOs"
    	```conf
    	SERVER_NAME=www.example.com
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		LOCAL_PHP=/run/php-fpm/www.sock
		LOCAL_PHP_PATH=/opt/bunkerweb/www/	
    	```

	=== "Fedora"
    	```conf
    	SERVER_NAME=www.example.com
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		LOCAL_PHP=/run/php-fpm/www.sock
		LOCAL_PHP_PATH=/opt/bunkerweb/www/	
    	```

    Let's check the status of BunkerWeb :
    ```shell
    systemctl status bunkerweb
    ```
    If it's already running we can just reload it :
    ```shell
    systemctl reload bunkerweb
    ```

	Then you will have to install php-fpm 
    ```shell
    apt install php-fpm
    ```

	Depending on your system, the configuration of the php-fpm service may change:
	=== "Ubuntu"
		By default, the user and the group of the php-fpm service is "www-data", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

	=== "Debian"
		By default, the user and the group of the php-fpm service is "www-data", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

	=== "CentOs"
		By default, the user and the group of the php-fpm service is "apache", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

	=== "Fedora"
		By default, the user and the group of the php-fpm service is "apache", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

    Reload the php-fpm service :
	```shell
	systemctl reload php-fpm
	```

=== "Ansible"

    You will need to add the settings to your `variables.env` file accordingly to your system :

    === "Ubuntu"
    	```conf
    	SERVER_NAME=www.example.com
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		LOCAL_PHP=/run/php/php-fpm.sock
		LOCAL_PHP_PATH=/opt/bunkerweb/www/	
    	```

	=== "Debian"
    	```conf
    	SERVER_NAME=www.example.com
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		LOCAL_PHP=/run/php/php-fpm.sock
		LOCAL_PHP_PATH=/opt/bunkerweb/www/	
    	```

	=== "CentOs"
    	```conf
    	SERVER_NAME=www.example.com
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		LOCAL_PHP=/run/php-fpm/www.sock
		LOCAL_PHP_PATH=/opt/bunkerweb/www/	
    	```

	=== "Fedora"
    	```conf
    	SERVER_NAME=www.example.com
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		LOCAL_PHP=/run/php-fpm/www.sock
		LOCAL_PHP_PATH=/opt/bunkerweb/www/	
    	```

	In your Ansible inventory, you can use the `variables_env` variable to configure BunkerWeb and `custom_site` to add your own site configuration :
	```yaml
	all:
  	  children:
        Groups:
          hosts: 
            "Your_IP_Address":
          vars:
            variables_env: ../variables.env,
			custom_site= ../site
	```

	Or in INI format :
	```ini
	[all]
	host
	
	[all:vars]
	variables_env = ../variables.env
	custom_site = ../site
	```

	Run the playbook :
	```shell
	ansible-playbook -i inventory.yml playbook.yml
	```

	Then you will have to install php-fpm 
    ```shell
    apt install php-fpm
    ```

	Depending on your system, the configuration of the php-fpm service may change:
	=== "Ubuntu"
		By default, the user and the group of the php-fpm service is "www-data", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

	=== "Debian"
		By default, the user and the group of the php-fpm service is "www-data", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

	=== "CentOs"
		By default, the user and the group of the php-fpm service is "apache", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

	=== "Fedora"
		By default, the user and the group of the php-fpm service is "apache", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

    Reload the php-fpm service :
	```shell
	systemctl reload php-fpm
	```

### Multiple applications

=== "Docker"

    When using the [Docker integration](/1.4/integrations/#docker), you have two steps for adding custom configurations :
    
    - Using specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as environment variables
    - Writing yours files in yours folder and mount the volume on /data
    
    Create the Docker networks if it's not already created :
    ```shell
    docker network create net_app1
	docker network create net_app2
    ```

    Then instantiate your apps :
    === "App #1"
    	```shell
    	docker run -d \
    		   --name myphp1 \
    		   --network net_app1 \
			   -v bw-data/www/app1.example.com:/app
    		   php:fpm
    	```
    === "App #2"
    	```shell
    	docker run -d \
    		   --name myphp2 \
    		   --network net_app2 \
			   -v bw-data/www/app2.example.com:/app
    		   php:fpm
    	```

    You can now run BunkerWeb and configure it for your app :
    ```shell
    docker run -d \
           --name mybunker \
    	   --network net_app1 \
    	   --network net_app2 \
    	   -p 80:8080 \
    	   -p 443:8443 \
    	   -v ./bw-data:/data \
    	   -e SERVER_NAME=app1.example.com app2.exemple.com \
		   -e MULTISITE=yes \
		   -e AUTO_LETS_ENCRYPT=yes \
		   -e DISABLE_DEFAULT_SERVER=yes \
		   -e USE_CLIENT_CACHE=yes \
		   -e USE_GZIP=yes \
		   -e app1.exemple.com_REMOTE_PHP=myphp1 \
		   -e app1.exemple.com_REMOTE_PHP_PATH=/app \
		   -e app2.exemple.com_REMOTE_PHP=myphp2 \
		   -e app2.exemple.com_REMOTE_PHP_PATH=/app \
    	   bunkerity/bunkerweb:1.4.2
    ```

	Here is the docker-compose equivalent :
    ```yaml
    version: '3'

    services:

      mybunker:
    	image: bunkerity/bunkerweb:1.4.2
    	ports:
    	  - 80:8080
    	  - 443:8443
    	volumes:
    	  - ./bw-data:/data
    	environment:
    	  - SERVER_NAME=www.example.com # replace with your domain
      	  - AUTO_LETS_ENCRYPT=yes
      	  - DISABLE_DEFAULT_SERVER=yes
      	  - USE_CLIENT_CACHE=yes
      	  - USE_GZIP=yes
      	  - REMOTE_PHP=myphp
      	  - REMOTE_PHP_PATH=/app
    	networks:
    	  - bw-net

      myphp:
    	image: php:fpm
		volumes:
		  - ./bw-data:/data
    	networks:
    	  - bw-net

    networks:
      bw-net:
    ```

=== "Docker autoconf"

    We will assume that you already have the Docker autoconf integration stack running on your machine and connected to a network called bw-services.

	You can instantiate your container and pass the settings as labels :
    ```shell
    docker run -d \
        --name mybunker \
    	--network bw-autoconf \
		-v ./www:/www \
	   -p 80:8080 \
	   -p 443:8443 \
    	-e AUTOCONF_MODE=yes \
       -e MULTISITE=yes \
       -e "API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24" \
        -e SERVER_NAME= \
       -l bunkerweb.AUTOCONF \
        bunkerity/bunkerweb:1.4.2
    ```

    === "App #1"
    	```shell
    	docker run -d \
       		--name myphp1 \
       		--network bw-services \
       		-v ./www/app1.example.com:/app \
       		-l bunkerweb.DISABLE_DEFAULT_SERVER=yes \
       		-l bunkerweb.SERVER_NAME=app1.example.com \
       		-l bunkerweb.USE_CLIENT_CACHE=yes \
       		-l bunkerweb.USE_GZIP=yes \
       		-l bunkerweb.REMOTE_PHP=myphp1 \
       		-l bunkerweb.REMOTE_PHP_PATH=/app \
       		-l bunkerweb.ROOT_FOLDER=/www/app1.example.com \
       		php:fpm
    	```

    === "App #2"
    	```shell
    	docker run -d \
       		--name myphp2 \
       		--network bw-services \
       		-v ./www/app2.example.com:/app \
       		-l bunkerweb.DISABLE_DEFAULT_SERVER=yes \
       		-l bunkerweb.SERVER_NAME=app2.example.com \
       		-l bunkerweb.USE_CLIENT_CACHE=yes \
       		-l bunkerweb.USE_GZIP=yes \
       		-l bunkerweb.REMOTE_PHP=myphp2 \
       		-l bunkerweb.REMOTE_PHP_PATH=/app \
       		-l bunkerweb.ROOT_FOLDER=/www/app2.example.com \
       		php:fpm
    	```

	Here is the docker-compose equivalent :
	```yaml
	version: '3'

	services:

  	  mybunker:
    	image: bunkerity/bunkerweb:1.4.2
    	volumes: 
      	  - ./www:/www
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
    	image: bunkerity/bunkerweb-autoconf:1.4.2
    	volumes:
      	  - bw-data:/data
      	  - /var/run/docker.sock:/var/run/docker.sock:ro
    	networks:
      	  - bw-autoconf

  	  myphp1:
    	image: php:fpm
    	volumes:
      	  - ./www/app1.example.com:/app
    	networks:
      	  bw-services:
        	aliases:
            	- myphp1
    	labels:
      	  - "bunkerweb.DISABLE_DEFAULT_SERVER=yes"
      	  - "bunkerweb.SERVER_NAME=app1.example.com"
      	  - "bunkerweb.USE_CLIENT_CACHE=yes"
      	  - "bunkerweb.USE_GZIP=yes"
      	  - "bunkerweb.REMOTE_PHP=myphp1"
      	  - "bunkerweb.REMOTE_PHP_PATH=/app"
      	  - "bunkerweb.ROOT_FOLDER=/www/app1.example.com"

  	  myphp2:
    	image: php:fpm
    	volumes:
      	  - ./www/app2.example.com:/app
    	networks:
      	  bw-services:
        	aliases:
            	- myphp2
    	labels:
      	  - "bunkerweb.DISABLE_DEFAULT_SERVER=yes"
      	  - "bunkerweb.SERVER_NAME=app2.example.com"
      	  - "bunkerweb.USE_CLIENT_CACHE=yes"
      	  - "bunkerweb.USE_GZIP=yes"
      	  - "bunkerweb.REMOTE_PHP=myphp2"
      	  - "bunkerweb.REMOTE_PHP_PATH=/app"
      	  - "bunkerweb.ROOT_FOLDER=/www/app2.example.com"

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

=== "Linux"

    We will assume that you already have the [Linux integration](/1.4/integrations/#linux) stack running on your machine.

    If you have multiple services to protect, the easiest way to do it is by enabling the `“multisite”` mode. When using multisite, bunkerized-nginx will create one server block per server defined in the `SERVER_NAME` environment variable. You can configure each servers independently by adding the server name as a prefix.

	=== "Ubuntu"
    	```conf
    	SERVER_NAME=app1.example.com app2.example.com
		MULTISITE=yes
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
		app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
		app1.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app1.example.com
		app2.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app2.example.com
    	```

	=== "Debian"
    	```conf
    	SERVER_NAME=app1.example.com app2.example.com
		MULTISITE=yes
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
		app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
		app1.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app1.example.com
		app2.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app2.example.com
    	```

	=== "CentOs"
    	```conf
    	SERVER_NAME=app1.example.com app2.example.com
		MULTISITE=yes
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		app1.example.com_LOCAL_PHP=/run/php-fpm/www.sock
		app2.example.com_LOCAL_PHP=/run/php-fpm/www.sock
		app1.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app1.example.com
		app2.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app2.example.com	
    	```

	=== "Fedora"
    	```conf
    	SERVER_NAME=app1.example.com app2.example.com
		MULTISITE=yes
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		app1.example.com_LOCAL_PHP=/run/php-fpm/www.sock
		app2.example.com_LOCAL_PHP=/run/php-fpm/www.sock
		app1.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app1.example.com
		app2.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app2.example.com	
    	```

	When using the multisite mode, some special folders must have a specific structure with subfolders named the same as the servers defined in the `SERVER_NAME` environment variable. Let’s take the app2.example.com as an example : if some static files need to be served by nginx, you need to place them under www/app2.example.com.

    Let's check the status of BunkerWeb :
    ```shell
    systemctl status bunkerweb
    ```
    If it's already running we can just reload it :
    ```shell
    systemctl reload bunkerweb
    ```

	Then you will have to install php-fpm 
    ```shell
    apt install php-fpm
    ```

	Depending on your system, the configuration of the php-fpm service may change:
	=== "Ubuntu"
		By default, the user and the group of the php-fpm service is "www-data", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

	=== "Debian"
		By default, the user and the group of the php-fpm service is "www-data", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

	=== "CentOs"
		By default, the user and the group of the php-fpm service is "apache", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

	=== "Fedora"
		By default, the user and the group of the php-fpm service is "apache", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

    Reload the php-fpm service :
	```shell
	systemctl reload php-fpm
	```

=== "Ansible"

    You will need to add the settings to your `variables.env` file accordingly to your system :

    === "Ubuntu"
    	```conf
    	SERVER_NAME=app1.example.com app2.example.com
		MULTISITE=yes
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
		app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
		app1.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app1.example.com
		app2.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app2.example.com
    	```

	=== "Debian"
    	```conf
    	SERVER_NAME=app1.example.com app2.example.com
		MULTISITE=yes
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
		app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
		app1.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app1.example.com
		app2.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app2.example.com
    	```

	=== "CentOs"
    	```conf
    	SERVER_NAME=app1.example.com app2.example.com
		MULTISITE=yes
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		app1.example.com_LOCAL_PHP=/run/php-fpm/www.sock
		app2.example.com_LOCAL_PHP=/run/php-fpm/www.sock
		app1.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app1.example.com
		app2.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app2.example.com	
    	```

	=== "Fedora"
    	```conf
    	SERVER_NAME=app1.example.com app2.example.com
		MULTISITE=yes
		HTTP_PORT=80
		HTTPS_PORT=443
		DNS_RESOLVERS=8.8.8.8 8.8.4.4
		DISABLE_DEFAULT_SERVER=no
		USE_CLIENT_CACHE=yes
		USE_GZIP=yes
		app1.example.com_LOCAL_PHP=/run/php-fpm/www.sock
		app2.example.com_LOCAL_PHP=/run/php-fpm/www.sock
		app1.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app1.example.com
		app2.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app2.example.com	
    	```

	When using the multisite mode, some special folders must have a specific structure with subfolders named the same as the servers defined in the `SERVER_NAME` environment variable. Let’s take the app2.example.com as an example : if some static files need to be served by nginx, you need to place them under www/app2.example.com.

	In your Ansible inventory, you can use the `variables_env` variable to configure BunkerWeb and `custom_site` to add your own site configuration :
	```yaml
	all:
  	  children:
        Groups:
          hosts: 
            "Your_IP_Address":
          vars:
            variables_env: ../variables.env,
			custom_site=../site
	```

	Or in INI format :
	```ini
	[all]
	host
	
	[all:vars]
	variables_env = ../variables.env
	custom_site = ../site
	```

	Run the playbook :
	```shell
	ansible-playbook -i inventory.yml playbook.yml
	```

	Then you will have to install php-fpm 
    ```shell
    apt install php-fpm
    ```

	Depending on your system, the configuration of the php-fpm service may change:
	=== "Ubuntu"
		By default, the user and the group of the php-fpm service is "www-data", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

	=== "Debian"
		By default, the user and the group of the php-fpm service is "www-data", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

	=== "CentOs"
		By default, the user and the group of the php-fpm service is "apache", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

	=== "Fedora"
		By default, the user and the group of the php-fpm service is "apache", so change it to your user.
    	```conf
		[www]
		user = nginx
		group = nginx
		listen.owner = nginx
		listen.group = nginx
    	```

    Reload the php-fpm service :
	```shell
	systemctl reload php-fpm
	```