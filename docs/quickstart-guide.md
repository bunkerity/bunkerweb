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

    Then, instantiate your app :
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
    	   bunkerity/bunkerweb:1.4.6
    ```

    Here is the docker-compose equivalent :
    ```yaml
    version: '3'

    services:

      mybunker:
    	image: bunkerity/bunkerweb:1.4.6
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

    Configuration of BunkerWeb is done by editing the `/etc/bunkerweb/variables.env` file :
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
    SERVER_NAME=www.example.com
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
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

    We will assume that you already have the [Vagrant integration](/1.4/integrations/#vagrant) stack running on your machine.

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

    If it's already running we can restart it :
    ```shell
    systemctl restart bunkerweb
    ```

    Otherwise, we will need to start it :
    ```shell
    systemctl start bunkerweb
    ```

    Let's check the status of BunkerWeb :
    ```shell
    systemctl status bunkerweb
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
    	   -e MULTISITE=yes \
    	   -e "SERVER_NAME=app1.example.com app2.example.com app3.example.com" \
    	   -e USE_REVERSE_PROXY=yes \
    	   -e REVERSE_PROXY_URL=/ \
    	   -e app1.example.com_REVERSE_PROXY_HOST=http://myapp1 \
    	   -e app2.example.com_REVERSE_PROXY_HOST=http://myapp2 \
    	   -e app3.example.com_REVERSE_PROXY_HOST=http://myapp3 \
    	   bunkerity/bunkerweb:1.4.6
    ```

    Here is the docker-compose equivalent :
    ```yaml
    version: '3'

    services:

      mybunker:
    	image: bunkerity/bunkerweb:1.4.6
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

    Configuration of BunkerWeb is done by editing the `/etc/bunkerweb/variables.env` file :
    ```conf
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    HTTP_PORT=80
    HTTPS_PORT=443
    MULTISITE=yes
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

    If it's already running, we can restart it :
    ```shell
    systemctl restart bunkerweb
    ```

    Otherwise, we will need to start it :
    ```shell
    systemctl start bunkerweb
    ```
	
=== "Vagrant"

	We will assume that you already have the [Vagrant integration](/1.4/integrations/#Vagrant) stack running on your machine with some web applications running on the same machine as BunkerWeb.

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

	Connect to your vagrant machine :
	```shell
	vagrant ssh
	```

	Configuration of BunkerWeb is done by editing the /etc/bunkerweb/variables.env file :
	```conf
	SERVER_NAME=app1.example.com app2.example.com app3.example.com
	HTTP_PORT=80
	HTTPS_PORT=443
	MULTISITE=yes
	DNS_RESOLVERS=8.8.8.8 8.8.4.4
	USE_REVERSE_PROXY=yes
	REVERSE_PROXY_URL=/
	app1.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8001
	app2.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8002
	app3.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8003
	```

	If it's already running we can restart it :
	```shell
	systemctl restart bunkerweb
	```

	Otherwise, we will need to start it :
	```shell
	systemctl start bunkerweb
	```

	Let's check the status of BunkerWeb :
	```shell
	systemctl status bunkerweb
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

   Content of the `my_variables.env` configuration file : 
    ```conf
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    HTTP_PORT=80
    HTTPS_PORT=443
    MULTISITE=yes
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    USE_REVERSE_PROXY=yes
    REVERSE_PROXY_URL=/
    app1.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8001
    app2.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8002
    app3.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8003
    ```
	[]()
	In your Ansible inventory, you can use the `variables_env` variable to set the path of configuration file :
	```yaml
	[mybunkers]
    192.168.0.42 variables_env="{{ playbook_dir }}/my_variables.env"
	```
	[]()
	Or alternatively, in your playbook file : 
	```yaml
    - hosts: all
      become: true
      vars:
        - variables_env: "{{ playbook_dir }}/my_variables.env"
      roles:
        - bunkerity.bunkerweb
	```
	[]()
	Run the playbook :
	```shell
	ansible-playbook -i inventory.yml playbook.yml
	```

## Behind load balancer or reverse proxy

When BunkerWeb is itself behind a load balancer or a reverse proxy, you need to configure it so it can get the real IP address of the clients. If you don't, the security features will block the IP address of the load balancer or reverse proxy instead of the client's one.

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
    	   bunkerity/bunkerweb:1.4.6
    ```

    Here is the docker-compose equivalent :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.6
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
           bunkerity/bunkerweb:1.4.6
    ```

    Here is the docker-compose equivalent :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.6
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
           bunkerity/bunkerweb:1.4.6
    ```

    Here is the docker-compose equivalent (using `docker stack deploy`) :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.6
      ...
      environment:
        - USE_REAL_IP=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
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
	  selector:
		matchLabels:
		  app: bunkerweb
	  template:
		spec:
		  containers:
		  - name: bunkerweb
			image: bunkerity/bunkerweb:1.4.6
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
    	   bunkerity/bunkerweb:1.4.6
    ```

    Here is the docker-compose equivalent :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.6
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
           bunkerity/bunkerweb:1.4.6
    ```

    Here is the docker-compose equivalent :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.6
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
           bunkerity/bunkerweb:1.4.6
    ```

    Here is the docker-compose equivalent (using `docker stack deploy`) :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.6
      ...
      environment:
        - USE_REAL_IP=yes
    	- USE_PROXY_PROTOCOL=yes
        - REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
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
	  selector:
		matchLabels:
		  app: bunkerweb
	  template:
		spec:
		  containers:
		  - name: bunkerweb
			image: bunkerity/bunkerweb:1.4.6
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

## Custom configurations

Because BunkerWeb is based on the NGINX web server, you can add custom NGINX configurations in different NGINX contexts. You can also apply custom configurations for the ModSecurity WAF which is a core component of BunkerWeb (more info [here](/1.4/security-tuning/#modsecurity)). Here is the list of custom configurations types :

- **http** : http level of NGINX
- **server-http** : server level of NGINX
- **default-server-http** : server level of NGINX (only apply to the "default server" when the name supplied by the client doesn't match any server name in `SERVER_NAME`)
- **modsec-crs** : before the OWASP Core Rule Set is loaded
- **modsec** : after the OWASP Core Rule Set is loaded (also used if CRS is not loaded)

Custom configurations can be applied globally or only for a specific server when applicable and if the multisite mode is enabled.

The howto depends on the integration used but under the hood, applying custom configurations is done by adding files ending with the .conf suffix in their name to specific folders. To apply a custom configuration for a specific server, the file is written to a subfolder which is named as the primary server name.

Some integrations offer a more convenient way of applying configurations such as using [Configs](https://docs.docker.com/engine/swarm/configs/) with Swarm or [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) with Kubernetes.

=== "Docker"

    When using the [Docker integration](/1.4/integrations/#docker), you have two choices for the addition of custom configurations :
    
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
      image: bunkerity/bunkerweb:1.4.6
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
    	   bunkerity/bunkerweb:1.4.6
    ```

    Here is the docker-compose equivalent :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.6
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
    	   bunkerity/bunkerweb-autoconf:1.4.6
    ```

    Here is the docker-compose equivalent :
    ```yaml
    myautoconf:
      image: bunkerity/bunkerweb-autoconf:1.4.6
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Swarm"

    When using the [Swarm integration](/1.4/integrations/#swarm), custom configurations are managed using [Docker Configs](https://docs.docker.com/engine/swarm/configs/).

    To keep it simple, you don't even need to attach the Config to a service : the autoconf service is listening for Config events and will update the custom configurations when needed.

    When creating a Config, you will need to add special labels :

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

    When creating a ConfigMap, you will need to add special labels :

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

    When using the [Linux integration](/1.4/integrations/#linux), custom configurations must be written to the /etc/bunkerweb/configs folder.

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

    The `custom_configs_path[]` variable is a dictionary with configuration types (`http`, `server-http`, `modsec`, `modsec-crs`) as keys and the corresponding values are path containing the configuration files.

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

    When using the [Vagrant integration](/1.4/integrations/#vagrant), custom configurations must be written to the `/etc/bunkerweb/configs` folder.

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

BunkerWeb supports PHP using external or remote [PHP-FPM](https://www.php.net/manual/en/install.fpm.php) instances. We will assume that you are already familiar with managing that kind of services.

 The following settings can be used :

- `REMOTE_PHP` : Hostname of the remote PHP-FPM instance.
- `REMOTE_PHP_PATH` : Root folder containing files in the remote PHP-FPM instance.
- `LOCAL_PHP` : Path to the local socket file of PHP-FPM instance.
- `LOCAL_PHP_PATH` : Root folder containing files in the local PHP-FPM instance.

### Single application

=== "Docker"

    When using the [Docker integration](/1.4/integrations/#docker), to support PHP applications, you will need to :
    
	- Copy your application files into the `www` subfolder of the `bw-data` volume of BunkerWeb
	- Set up a PHP-FPM container for your application and mount the `bw-data/www` folder
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as environment variables when starting BunkerWeb

	Create the `bw-data/www` folder :
	```shell
	mkdir -p bw-data/www
	```

    You can create a Docker network if it's not already created :
    ```shell
    docker network create bw-net
    ```

	Now you can copy your application files to the `bw-data/www` folder. Please note that you will need to fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33) is the owner of the files and folders :
	```shell
	chown -R 101:101 ./bw-data && \
	chown -R 33:101 ./bw-data/www && \
    find ./bw-data/www -type f -exec chmod 0640 {} \; && \
    find ./bw-data/www -type d -exec chmod 0750 {} \;
	```

	Let's create the PHP-FPM container, give it a name, connect it to the network and mount the application files :
    ```shell
    docker run -d \
       	   --name myphp \
       	   --network bw-net \
       	   -v "${PWD}/bw-data/www:/app" \
       	   php:fpm
    ```

    You can now run BunkerWeb and configure it for your PHP application :
    ```shell
    docker run -d \
           --name mybunker \
    	   --network bw-net \
    	   -p 80:8080 \
    	   -p 443:8443 \
    	   -v "${PWD}/bw-data:/data" \
    	   -e SERVER_NAME=www.example.com \
		   -e AUTO_LETS_ENCRYPT=yes \
		   -e REMOTE_PHP=myphp \
		   -e REMOTE_PHP_PATH=/app \
    	   bunkerity/bunkerweb:1.4.6
    ```

	Here is the docker-compose equivalent :
    ```yaml
    version: '3'

    services:

      mybunker:
    	image: bunkerity/bunkerweb:1.4.6
    	ports:
    	  - 80:8080
    	  - 443:8443
    	volumes:
    	  - ./bw-data:/data
    	environment:
    	  - SERVER_NAME=www.example.com
      	  - AUTO_LETS_ENCRYPT=yes
      	  - REMOTE_PHP=myphp
      	  - REMOTE_PHP_PATH=/app
    	networks:
    	  - bw-net

      myphp:
    	image: php:fpm
		volumes:
		  - ./bw-data/www:/app
    	networks:
    	  - bw-net

    networks:
      bw-net:
    ```

=== "Docker autoconf"

    When using the [Docker autoconf integration](/integrations/#docker-autoconf), your PHP files must not be mounted into the `bw-data/www` folder. Instead, you will need to create a specific folder containing your PHP application and mount it both on the BunkerWeb container (outside the `/data` endpoint) and your PHP-FPM container.

    First of all, create the application folder (e.g. `myapp`), copy your files and fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33) is the owner of the files and folders :
    ```shell
	chown -R 33:101 ./myapp && \
    find ./myapp -type f -exec chmod 0640 {} \; && \
    find ./myapp -type d -exec chmod 0750 {} \;
	```
	
	When you create the BunkerWeb container, simply mount the folder containing your PHP application to a specific endpoint like `/app` :
	```shell
	docker run -d \
	       ...
		   -v "${PWD}/myapp:/app" \
		   ...
		   bunkerity/bunkerweb:1.4.6
	```
	
	Once BunkerWeb and autoconf are ready, you will be able to create the PHP-FPM container, mount the application folder inside the container and configure it using specific labels :
	```shell
	docker run -d \
	       --name myphp \
	       --network bw-services \
	       -v "${PWD}/myapp:/app" \
	       -l bunkerweb.SERVER_NAME=www.example.com \
	       -l bunkerweb.AUTO_LETS_ENCRYPT=yes \
		   -l bunkerweb.ROOT_FOLDER=/app \
	       -l bunkerweb.REMOTE_PHP=myphp \
	       -l bunkerweb.REMOTE_PHP_PATH=/app \
	       php:fpm
	```

	Here is the docker-compose equivalent :
	```yaml
	version: '3'

	services:

  	  myphp:
    	image: php:fpm
    	volumes:
      	  - ./myapp:/app
    	networks:
      	  bw-services:
        	aliases:
            	- myphp
    	labels:
      	  - bunkerweb.SERVER_NAME=www.example.com
		  - bunkerweb.AUTO_LETS_ENCRYPT=yes
		  - bunkerweb.ROOT_FOLDER=/app
      	  - bunkerweb.REMOTE_PHP=myphp
      	  - bunkerweb.REMOTE_PHP_PATH=/app

	networks:
	  bw-services:
	    external:
	      name: bw-services
	```

=== "Swarm"

	!!! info "Shared volume"
		Using PHP with the Docker Swarm integration needs a shared volume between all BunkerWeb and PHP-FPM instances.

    When using the [Docker Swarm integration](/integrations/#swarm), your PHP files must not be mounted into the `bw-data/www` folder. Instead, you will need to create a specific folder containing your PHP application and mount it both on the BunkerWeb container (outside the `/data` endpoint) and your PHP-FPM container. As an example, we will consider that you have a shared folder mounted on your worker nodes on the `/shared` endpoint.

    First of all, create the application folder (e.g. `/shared/myapp`), copy your files and fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33) is the owner of the files and folders :
    ```shell
	chown -R 33:101 /shared/myapp && \
    find /shared/myapp -type f -exec chmod 0640 {} \; && \
    find /shared/myapp -type d -exec chmod 0750 {} \;
	```
	
	When you create the BunkerWeb service, simply mount the folder containing your PHP application to a specific endpoint like `/app` :
	```shell
	docker service create \
	       ...
		   -v "/shared/myapp:/app" \
		   ...
		   bunkerity/bunkerweb:1.4.6
	```

	Once BunkerWeb and autoconf are ready, you will be able to create the PHP-FPM service, mount the application folder inside the container and configure it using specific labels :
	```shell
	docker service create \
	       --name myphp \
	       --network bw-services \
	       -v "/shared/myapp:/app" \
	       -l bunkerweb.SERVER_NAME=www.example.com \
	       -l bunkerweb.AUTO_LETS_ENCRYPT=yes \
		   -l bunkerweb.ROOT_FOLDER=/app \
	       -l bunkerweb.REMOTE_PHP=myphp \
	       -l bunkerweb.REMOTE_PHP_PATH=/app \
	       php:fpm
	```

	Here is the docker-compose equivalent (using `docker stack deploy`) :
	```yaml
	version: '3'

	services:

  	  myphp:
    	image: php:fpm
    	volumes:
      	  - ./myapp:/app
    	networks:
      	  - bw-services
	    deploy:
	      placement:
	        constraints:
	          - "node.role==worker"
          labels:
      	    - bunkerweb.SERVER_NAME=www.example.com
	        - bunkerweb.AUTO_LETS_ENCRYPT=yes
			- bunkerweb.ROOT_FOLDER=/app
      	    - bunkerweb.REMOTE_PHP=myphp
      	    - bunkerweb.REMOTE_PHP_PATH=/app

	networks:
	  bw-services:
	    external:
	      name: bw-services
	```

=== "Kubernetes"

	!!! warning "PHP is not supported for Kubernetes"
		Kubernetes integration allows configuration through [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) and the BunkerWeb controller only supports HTTP applications at the moment.

=== "Linux"

    We will assume that you already have the [Linux integration](/1.4/integrations/#linux) stack running on your machine.

    By default, BunkerWeb will search for web files inside the `/var/www/html` folder. You can use it to store your PHP application. Please note that you will need to configure your PHP-FPM service to get or set the user/group of the running processes and the UNIX socket file used to communicate with BunkerWeb.

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

	Once your application is copied to the `/var/www/html` folder, you will need to fix the permissions so BunkerWeb (user/group nginx) can at least read files and list folders and PHP-FPM (user/group www-data) is the owner of the files and folders : 
	```shell
	chown -R www-data:nginx /var/www/html && \
	find /var/www/html -type f -exec chmod 0640 {} \; && \
	find /var/www/html -type d -exec chmod 0750 {} \;
	```

	You can now edit the `/etc/bunkerweb/variable.env` file :
	```env
	HTTP_PORT=80
	HTTPS_PORT=443
	DNS_RESOLVERS=8.8.8.8 8.8.4.4
	SERVER_NAME=www.example.com
	AUTO_LETS_ENCRYPT=yes
	LOCAL_PHP=/run/php/php-fpm.sock
	LOCAL_PHP_PATH=/var/www/html/	
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

	By default, BunkerWeb will search for web files inside the `/var/www/html` folder. You can use it to store your PHP application. Please note that you will need to configure your PHP-FPM service to get or set the user/group of the running processes and the UNIX socket file used to communicate with BunkerWeb.

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

	!!! info "PHP-FPM with Ansible"
		The PHP-FPM configuration part using Ansible is out of the scope of this documentation.
	
	Content of the `my_variables.env` configuration file :
	```env
	HTTP_PORT=80
	HTTPS_PORT=443
	DNS_RESOLVERS=8.8.8.8 8.8.4.4
	SERVER_NAME=www.example.com
	AUTO_LETS_ENCRYPT=yes
	LOCAL_PHP=/run/php/php-fpm.sock
	LOCAL_PHP_PATH=/var/www/html/	
	```
	
	The `custom_site` variable can be used to specify a directory containing your application files (e.g : `my_app`) that will be copied to `/var/www/html` and the `custom_www_owner` variable contains the owner that should be set for the files and folders. Here is an example using the Ansible inventory :
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
		- custom_www: "{{ playbook_dir }}/my_app"
		- custom_www_owner: "www-data"
	  roles:
		- bunkerity.bunkerweb
	```

	You can now run the playbook :
	```shell
	ansible-playbook -i inventory.yml playbook.yml
	```

=== "Vagrant"

    We will assume that you already have the [Vagrant integration](/1.4/integrations/#vagrant) stack running on your machine.

    By default, BunkerWeb will search for web files inside the `/var/www/html` folder. You can use it to store your PHP application. Please note that you will need to configure your PHP-FPM service to get or set the user/group of the running processes and the UNIX socket file used to communicate with BunkerWeb.

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
	systemctl restart php8.1-fpm
	```

	Once your application is copied to the `/var/www/html` folder, you will need to fix the permissions so BunkerWeb (user/group nginx) can at least read files and list folders and PHP-FPM (user/group www-data) is the owner of the files and folders : 
	```shell
	chown -R www-data:nginx /var/www/html && \
	find /var/www/html -type f -exec chmod 0640 {} \; && \
	find /var/www/html -type d -exec chmod 0750 {} \;
	```

	You can now edit the `/etc/bunkerweb/variable.env` file :
	```env
	HTTP_PORT=80
	HTTPS_PORT=443
	DNS_RESOLVERS=8.8.8.8 8.8.4.4
	SERVER_NAME=www.example.com
	AUTO_LETS_ENCRYPT=yes
	LOCAL_PHP=/run/php/php-fpm.sock
	LOCAL_PHP_PATH=/var/www/html/	
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

	When using the [Docker integration](/1.4/integrations/#docker), to support PHP applications, you will need to :
    
	- Copy your application files into the `www` subfolder of the `bw-data` volume of BunkerWeb (each application will be in its own subfolder named the same as the primary server name)
	- Setup a PHP-FPM container for your application and mount the `bw-data/www/subfolder` folder
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as environment variables when starting BunkerWeb

	Create the `bw-data/www` subfolders :
	```shell
	mkdir -p bw-data/www/{app1.example.com,app2.example.com,app3.example.com}
	```

    You can create a Docker network if it's not already created :
    ```shell
    docker network create bw-net
    ```

	Now you can copy your application files to the `bw-data/www` subfolders. Please note that you will need to fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33) is the owner of the files and folders :
	```shell
	chown -R 101:101 ./bw-data && \
	chown -R 33:101 ./bw-data/www && \
    find ./bw-data/www -type f -exec chmod 0640 {} \; && \
    find ./bw-data/www -type d -exec chmod 0750 {} \;
	```

	Let's create the PHP-FPM containers, give them a name, connect them to the network and mount the application files :
	
	=== "App #1"
		```shell
		docker run -d \
       	       --name myphp1 \
       	       --network bw-net \
       	       -v "${PWD}/bw-data/www/app1.example.com:/app" \
       	       php:fpm
		```

	=== "App #2"
		```shell
		docker run -d \
       	       --name myphp2 \
       	       --network bw-net \
       	       -v "${PWD}/bw-data/www/app2.example.com:/app" \
       	       php:fpm
		```

	=== "App #3"
		```shell
		docker run -d \
       	       --name myphp3 \
       	       --network bw-net \
       	       -v "${PWD}/bw-data/www/app3.example.com:/app" \
       	       php:fpm
		```

    You can now run BunkerWeb and configure it for your PHP applications :
    ```shell
    docker run -d \
           --name mybunker \
           --network bw-net \
           -p 80:8080 \
           -p 443:8443 \
           -v "${PWD}/bw-data:/data" \
	       -e MULTISITE=yes \
           -e "SERVER_NAME=app1.example.com app2.example.com app3.example.com" \
	       -e AUTO_LETS_ENCRYPT=yes \
	       -e app1.example.com_REMOTE_PHP=myphp1 \
	       -e app1.example.com_REMOTE_PHP_PATH=/app \
	       -e app2.example.com_REMOTE_PHP=myphp2 \
	       -e app2.example.com_REMOTE_PHP_PATH=/app \
	       -e app3.example.com_REMOTE_PHP=myphp3 \
	       -e app3.example.com_REMOTE_PHP_PATH=/app \
    	   bunkerity/bunkerweb:1.4.6
    ```

	Here is the docker-compose equivalent :
    ```yaml
    version: '3'

    services:

      mybunker:
    	image: bunkerity/bunkerweb:1.4.6
    	ports:
    	  - 80:8080
    	  - 443:8443
    	volumes:
    	  - ./bw-data:/data
    	environment:
    	  - SERVER_NAME=app1.example.com app2.example.com app3.example.com
	      - MULTISITE=yes
      	  - AUTO_LETS_ENCRYPT=yes
      	  - app1.example.com_REMOTE_PHP=myphp1
      	  - app1.example.com_REMOTE_PHP_PATH=/app
      	  - app2.example.com_REMOTE_PHP=myphp2
      	  - app2.example.com_REMOTE_PHP_PATH=/app
      	  - app3.example.com_REMOTE_PHP=myphp3
      	  - app3.example.com_REMOTE_PHP_PATH=/app
    	networks:
    	  - bw-net

      myphp1:
        image: php:fpm
		volumes:
		  - ./bw-data/www/app1.example.com:/app
    	networks:
    	  - bw-net

      myphp2:
        image: php:fpm
		volumes:
		  - ./bw-data/www/app2.example.com:/app
    	networks:
    	  - bw-net

      myphp3:
        image: php:fpm
		volumes:
		  - ./bw-data/www/app3.example.com:/app
    	networks:
    	  - bw-net

    networks:
      bw-net:
    ```

=== "Docker autoconf"

    When using the [Docker autoconf integration](/integrations/#docker-autoconf), your PHP files must not be mounted into the `bw-data/www` folder. Instead, you will need to create a specific folder containing your PHP applications and mount it both on the BunkerWeb container (outside the `/data` endpoint) and your PHP-FPM containers.

    First of all create the applications folder (e.g. `myapp`), the subfolders for each application (e.g, `app1`, `app2` and `app3`), copy your web files and fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33) is the owner of the files and folders :
    ```shell
	chown -R 33:101 ./myapps && \
    find ./myapps -type f -exec chmod 0640 {} \; && \
    find ./myapps -type d -exec chmod 0750 {} \;
	```
	
	When you create the BunkerWeb container, simply mount the folder containing your PHP applications to a specific endpoint like `/apps` :
	```shell
	docker run -d \
	       ...
		   -v "${PWD}/myapps:/apps" \
		   ...
		   bunkerity/bunkerweb:1.4.6
	```
	
	Once BunkerWeb and autoconf are ready, you will be able to create the PHP-FPM containers, mount the right application folder inside each container and configure them using specific labels :
	
	=== "App #1"
		```shell
		docker run -d \
			   --name myphp1 \
			   --network bw-services \
			   -v "${PWD}/myapps/app1:/app" \
			   -l bunkerweb.SERVER_NAME=app1.example.com \
			   -l bunkerweb.AUTO_LETS_ENCRYPT=yes \
			   -l bunkerweb.REMOTE_PHP=myphp1 \
			   -l bunkerweb.REMOTE_PHP_PATH=/app \
			   -l bunkerweb.ROOT_FOLDER=/apps/app1 \
			   php:fpm
		```

	=== "App #2"
		```shell
		docker run -d \
			   --name myphp2 \
			   --network bw-services \
			   -v "${PWD}/myapps/app2:/app" \
			   -l bunkerweb.SERVER_NAME=app2.example.com \
			   -l bunkerweb.AUTO_LETS_ENCRYPT=yes \
			   -l bunkerweb.REMOTE_PHP=myphp2 \
			   -l bunkerweb.REMOTE_PHP_PATH=/app \
			   -l bunkerweb.ROOT_FOLDER=/apps/app2 \
			   php:fpm
		```

	=== "App #3"
		```shell
		docker run -d \
			   --name myphp3 \
			   --network bw-services \
			   -v "${PWD}/myapps/app3:/app" \
			   -l bunkerweb.SERVER_NAME=app3.example.com \
			   -l bunkerweb.AUTO_LETS_ENCRYPT=yes \
			   -l bunkerweb.REMOTE_PHP=myphp3 \
			   -l bunkerweb.REMOTE_PHP_PATH=/app \
			   -l bunkerweb.ROOT_FOLDER=/apps/app3 \
			   php:fpm
		```

	Here is the docker-compose equivalent :
	```yaml
	version: '3'

	services:

  	  myphp1:
    	image: php:fpm
    	volumes:
      	  - ./myapps/app1:/app
    	networks:
      	  bw-services:
        	aliases:
              - myphp1
    	labels:
      	  - bunkerweb.SERVER_NAME=app1.example.com
		  - bunkerweb.AUTO_LETS_ENCRYPT=yes
      	  - bunkerweb.REMOTE_PHP=myphp1
      	  - bunkerweb.REMOTE_PHP_PATH=/app
      	  - bunkerweb.ROOT_FOLDER=/apps/app1

  	  myphp2:
    	image: php:fpm
    	volumes:
      	  - ./myapps/app2:/app
    	networks:
      	  bw-services:
        	aliases:
              - myphp2
    	labels:
      	  - bunkerweb.SERVER_NAME=app2.example.com
		  - bunkerweb.AUTO_LETS_ENCRYPT=yes
      	  - bunkerweb.REMOTE_PHP=myphp2
      	  - bunkerweb.REMOTE_PHP_PATH=/app
      	  - bunkerweb.ROOT_FOLDER=/apps/app2

  	  myphp3:
    	image: php:fpm
    	volumes:
      	  - ./myapps/app3:/app
    	networks:
      	  bw-services:
        	aliases:
              - myphp3
    	labels:
      	  - bunkerweb.SERVER_NAME=app3.example.com
		  - bunkerweb.AUTO_LETS_ENCRYPT=yes
      	  - bunkerweb.REMOTE_PHP=myphp3
      	  - bunkerweb.REMOTE_PHP_PATH=/app
      	  - bunkerweb.ROOT_FOLDER=/apps/app3

	networks:
	  bw-services:
	    external:
	      name: bw-services
	```

=== "Swarm"

	!!! info "Shared volume"
		Using PHP with the Docker Swarm integration needs a shared volume between all BunkerWeb and PHP-FPM instances.

    When using the [Docker Swarm integration](/integrations/#swarm), your PHP files must not be mounted into the `bw-data/www` folder. Instead, you will need to create a specific folder containing your PHP applications and mount it both on the BunkerWeb container (outside the `/data` endpoint) and your PHP-FPM containers. As an example, we will consider that you have a shared folder mounted on your worker nodes on the `/shared` endpoint.

    First of all, create the applications folder (e.g. `myapp`), the subfolders for each application (e.g, `app1`, `app2` and `app3`), copy your files and fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33) is the owner of the files and folders :
    ```shell
	chown -R 33:101 /shared/myapps && \
    find /shared/myapps -type f -exec chmod 0640 {} \; && \
    find /shared/myapps -type d -exec chmod 0750 {} \;
	```
	
	When you create the BunkerWeb service, simply mount the folder containing your PHP applications to a specific endpoint like `/apps` :
	```shell
	docker service create \
	       ...
		   -v "/shared/myapps:/apps" \
		   ...
		   bunkerity/bunkerweb:1.4.6
	```

	Once BunkerWeb and autoconf are ready, you will be able to create the PHP-FPM service, mount the application folder inside the container and configure it using specific labels :
	
	=== "App #1"
		```shell
		docker service create \
			   --name myphp1 \
			   --network bw-services \
			   -v /shared/myapps/app1:/app \
			   -l bunkerweb.SERVER_NAME=app1.example.com \
			   -l bunkerweb.AUTO_LETS_ENCRYPT=yes \
			   -l bunkerweb.REMOTE_PHP=myphp1 \
			   -l bunkerweb.REMOTE_PHP_PATH=/app \
			   -l bunkerweb.ROOT_FOLDER=/apps/app1 \
			   php:fpm
		```

	=== "App #2"
		```shell
		docker service create \
			   --name myphp2 \
			   --network bw-services \
			   -v /shared/myapps/app2:/app \
			   -l bunkerweb.SERVER_NAME=app2.example.com \
			   -l bunkerweb.AUTO_LETS_ENCRYPT=yes \
			   -l bunkerweb.REMOTE_PHP=myphp2 \
			   -l bunkerweb.REMOTE_PHP_PATH=/app \
			   -l bunkerweb.ROOT_FOLDER=/apps/app2 \
			   php:fpm
		```

	=== "App #2"
		```shell
		docker service create \
			   --name myphp3 \
			   --network bw-services \
			   -v /shared/myapps/app3:/app \
			   -l bunkerweb.SERVER_NAME=app3.example.com \
			   -l bunkerweb.AUTO_LETS_ENCRYPT=yes \
			   -l bunkerweb.REMOTE_PHP=myphp3 \
			   -l bunkerweb.REMOTE_PHP_PATH=/app \
			   -l bunkerweb.ROOT_FOLDER=/apps/app3 \
			   php:fpm
		```

	Here is the docker-compose equivalent (using `docker stack deploy`) :
	```yaml
	version: '3'

	services:

  	  myphp1:
    	image: php:fpm
    	volumes:
      	  - /shared/myapps/app1:/app
    	networks:
      	  - bw-services
	    deploy:
	      placement:
	        constraints:
	          - "node.role==worker"
          labels:
      	    - bunkerweb.SERVER_NAME=app1.example.com
	        - bunkerweb.AUTO_LETS_ENCRYPT=yes
      	    - bunkerweb.REMOTE_PHP=myphp1
      	    - bunkerweb.REMOTE_PHP_PATH=/app
      	    - bunkerweb.ROOT_FOLDER=/apps/app1

  	  myphp2:
    	image: php:fpm
    	volumes:
      	  - /shared/myapps/app2:/app
    	networks:
      	  - bw-services
	    deploy:
	      placement:
	        constraints:
	          - "node.role==worker"
          labels:
      	    - bunkerweb.SERVER_NAME=app2.example.com
	        - bunkerweb.AUTO_LETS_ENCRYPT=yes
      	    - bunkerweb.REMOTE_PHP=myphp2
      	    - bunkerweb.REMOTE_PHP_PATH=/app
      	    - bunkerweb.ROOT_FOLDER=/apps/app2

  	  myphp3:
    	image: php:fpm
    	volumes:
      	  - /shared/myapps/app3:/app
    	networks:
      	  - bw-services
	    deploy:
	      placement:
	        constraints:
	          - "node.role==worker"
          labels:
      	    - bunkerweb.SERVER_NAME=app3.example.com
	        - bunkerweb.AUTO_LETS_ENCRYPT=yes
      	    - bunkerweb.REMOTE_PHP=myphp3
      	    - bunkerweb.REMOTE_PHP_PATH=/app
      	    - bunkerweb.ROOT_FOLDER=/apps/app3

	networks:
	  bw-services:
	    external:
	      name: bw-services
	```

=== "Kubernetes"

	!!! warning "PHP is not supported for Kubernetes"
		Kubernetes integration allows configuration through [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) and the BunkerWeb controller only supports HTTP applications at the moment.

=== "Linux"

	We will assume that you already have the [Linux integration](/1.4/integrations/#linux) stack running on your machine.

    By default, BunkerWeb will search for web files inside the `/var/www/html` folder. You can use it to store your PHP applications : each application will be in its own subfolder named the same as the primary server name. Please note that you will need to configure your PHP-FPM service to get or set the user/group of the running processes and the UNIX socket file used to communicate with BunkerWeb.

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

	Once your application is copied to the `/var/www/html` folder, you will need to fix the permissions so BunkerWeb (user/group nginx) can at least read files and list folders and PHP-FPM (user/group www-data) is the owner of the files and folders : 
	```shell
	chown -R www-data:nginx /var/www/html && \
	find /var/www/html -type f -exec chmod 0640 {} \; && \
	find /var/www/html -type d -exec chmod 0750 {} \;
	```

	You can now edit the `/etc/bunkerweb/variable.env` file :
	```env
	HTTP_PORT=80
	HTTPS_PORT=443
	DNS_RESOLVERS=8.8.8.8 8.8.4.4
	SERVER_NAME=app1.example.com app2.example.com app3.example.com
	MULTISITE=yes
	AUTO_LETS_ENCRYPT=yes
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

	By default, BunkerWeb will search for web files inside the `/var/www/html` folder. You can use it to store your PHP application : each application will be in its own subfolder named the same as the primary server name. Please note that you will need to configure your PHP-FPM service to get or set the user/group of the running processes and the UNIX socket file used to communicate with BunkerWeb.

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

	!!! info "PHP-FPM with Ansible"
		The PHP-FPM configuration part using Ansible is out of the scope of this documentation.

	Content of the `my_variables.env` configuration file :
	```env
	HTTP_PORT=80
	HTTPS_PORT=443
	DNS_RESOLVERS=8.8.8.8 8.8.4.4
	SERVER_NAME=app1.example.com app2.example.com app3.example.com
	MULTISITE=yes
	AUTO_LETS_ENCRYPT=yes
	app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
	app1.example.com_LOCAL_PHP_PATH=/var/www/html/app1.example.com
	app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
	app2.example.com_LOCAL_PHP_PATH=/var/www/html/app2.example.com
	app3.example.com_LOCAL_PHP=/run/php/php-fpm.sock
	app3.example.com_LOCAL_PHP_PATH=/var/www/html/app3.example.com
	```

	The `custom_site` variable can be used to specify a directory containing your application files (e.g : `my_app`) that will be copied to `/var/www/html` and the `custom_www_owner` variable contains the owner that should be set for the files and folders. Here is an example using the Ansible inventory :
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
		- custom_www: "{{ playbook_dir }}/my_app"
		- custom_www_owner: "www-data"
	  roles:
		- bunkerity.bunkerweb
	```

	You can now run the playbook :
	```shell
	ansible-playbook -i inventory.yml playbook.yml
	```

=== "Vagrant"

	We will assume that you already have the [Vagrant integration](/1.4/integrations/#vagrant) stack running on your machine.

    By default, BunkerWeb will search for web files inside the `/var/www/html` folder. You can use it to store your PHP applications : each application will be in its own subfolder named the same as the primary server name. Please note that you will need to configure your PHP-FPM service to get or set the user/group of the running processes and the UNIX socket file used to communicate with BunkerWeb.

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
	systemctl restart php8.1-fpm
	```

	Once your application is copied to the `/var/www/html` folder, you will need to fix the permissions so BunkerWeb (user/group nginx) can at least read files and list folders and PHP-FPM (user/group www-data) is the owner of the files and folders : 
	```shell
	chown -R www-data:nginx /var/www/html && \
	find /var/www/html -type f -exec chmod 0640 {} \; && \
	find /var/www/html -type d -exec chmod 0750 {} \;
	```

	You can now edit the `/etc/bunkerweb/variable.env` file :
	```env
	HTTP_PORT=80
	HTTPS_PORT=443
	DNS_RESOLVERS=8.8.8.8 8.8.4.4
	SERVER_NAME=app1.example.com app2.example.com app3.example.com
	MULTISITE=yes
	AUTO_LETS_ENCRYPT=yes
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