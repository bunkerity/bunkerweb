# Quickstart guide

## Reverse proxy

The following environment variables can be used to deploy bunkerized-nginx as a reverse proxy in front of your web services :
- `USE_REVERSE_PROXY` : activate/deactivate the reverse proxy mode
- `REVERSE_PROXY_URL` : public path prefix
- `REVERSE_PROXY_HOST` : full address of the proxied service

Here is a basic example :
```conf
SERVER_NAME=www.example.com
USE_REVERSE_PROXY=yes
REVERSE_PROXY_URL=/
REVERSE_PROXY_HOST=http://my-service.example.local:8080
```

If you have multiple web services you can configure multiple reverse proxy rules by appending a number to the environment variables names :
```conf
SERVER_NAME=www.example.com
USE_REVERSE_PROXY=yes
REVERSE_PROXY_URL_1=/app1
REVERSE_PROXY_HOST_1=http://app1.example.local:8080
REVERSE_PROXY_URL_2=/app2
REVERSE_PROXY_HOST_2=http://app2.example.local:8080
```

### Docker

When using Docker, the recommended way is to create a network so bunkerized-nginx can communicate with the web service using the container name :
```shell
$ docker network create services-net
$ docker run -d \
         --name myservice \
         --network services-net \
         tutum/hello-world
$ docker run -d \
         --network services-net \
         -p 80:8080 \
         -p 443:8443 \
         -v "${PWD}/certs:/etc/letsencrypt" \
         -e SERVER_NAME=www.example.com \
         -e AUTO_LETS_ENCRYPT=yes \
         -e USE_REVERSE_PROXY=yes \
         -e REVERSE_PROXY_URL=/ \
         -e REVERSE_PROXY_HOST=http://myservice \
         bunkerity/bunkerized-nginx
```

docker-compose equivalent :
```yaml
version: '3'

services:

  mybunkerized:
    image: bunkerity/bunkerized-nginx
    ports:
      - 80:8080
      - 443:8443
    volumes:
      - ./certs:/etc/letsencrypt
    environment:
      - SERVER_NAME=www.example.com
      - AUTO_LETS_ENCRYPT=yes
      - USE_REVERSE_PROXY=yes
      - REVERSE_PROXY_URL=/
      - REVERSE_PROXY_HOST=http://myservice
    networks:
      - services-net
    depends_on:
      - myservice

  myservice:
    image: tutum/hello-world
    networks:
      - services-net

networks:
  services-net:
```

### Docker autoconf

When the Docker autoconf stack is running, you simply need to start the container hosting your web service and add the environment variables as labels :
```shell
$ docker run -d \
         --name myservice \
         --network services-net \
         -l bunkerized-nginx.SERVER_NAME=www.example.com \
         -l bunkerized-nginx.USE_REVERSE_PROXY=yes \
         -l bunkerized-nginx.REVERSE_PROXY_URL=/ \
         -l bunkerized-nginx.REVERSE_PROXY_HOST=http://myservice \
         tutum/hello-world
```

docker-compose equivalent :
```yaml
version: '3'

services:

  myservice:
    image: tutum/hello-world
    networks:
      services-net:
        aliases:
          - myservice
    labels:
      - bunkerized-nginx.SERVER_NAME=www.example.com
      - bunkerized-nginx.USE_REVERSE_PROXY=yes
      - bunkerized-nginx.REVERSE_PROXY_URL=/
      - bunkerized-nginx.REVERSE_PROXY_HOST=http://myservice

networks:
  services-net:
    external:
      name: services-net
```

### Docker Swarm

When the Docker Swarm stack is running, you simply need to start the Swarm service hosting your web service and add the environment variables as labels :
```shell
$ docker service create \
         --name myservice \
         --network services-net \
         --constraint node.role==worker \
         -l bunkerized-nginx.SERVER_NAME=www.example.com \
         -l bunkerized-nginx.USE_REVERSE_PROXY=yes \
         -l bunkerized-nginx.REVERSE_PROXY_URL=/ \
         -l bunkerized-nginx.REVERSE_PROXY_HOST=http://myservice \
         tutum/hello-world
```

docker-compose equivalent :
```yaml
version: '3'

services:

  myservice:
    image: tutum/hello-world
    networks:
      services-net:
        aliases:
          - myservice
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - bunkerized-nginx.SERVER_NAME=www.example.com
        - bunkerized-nginx.USE_REVERSE_PROXY=yes
        - bunkerized-nginx.REVERSE_PROXY_URL=/
        - bunkerized-nginx.REVERSE_PROXY_HOST=http://myservice

networks:
  services-net:
    external:
      name: services-net
```

### Kubernetes

Example deployment and service declaration :
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myservice
  labels:
    app: myservice
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myservice
  template:
    metadata:
      labels:
        app: myservice
    spec:
      containers:
      - name: myservice
        image: tutum/hello-world
---
apiVersion: v1
kind: Service
metadata:
  name: myservice
spec:
  type: ClusterIP
  selector:
    app: myservice
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
```

The most straightforward way to add a reverse proxy in the Kubernetes cluster is to declare it in the Ingress resource :
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bunkerized-nginx-ingress
  # this label is mandatory
  labels:
    bunkerized-nginx: "yes"
spec:
  tls:
  - hosts:
    - www.example.com
  rules:
  - host: "www.example.com"
    http:
      paths:
      - pathType: Prefix
        path: "/"
        backend:
          service:
            name: myservice
            port:
              number: 80
```

An alternative "hackish" way is to use environment variables as annotations prefixed with "bunkerized-nginx." inside the Service resource of your web service :
```yaml
apiVersion: v1
kind: Service
metadata:
  name: myservice
  # this label is mandatory
  labels:
    bunkerized-nginx: "yes"
  annotations:
    bunkerized-nginx.SERVER_NAME: "www.example.com"
    bunkerized-nginx.AUTO_LETS_ENCRYPT: "yes"
    bunkerized-nginx.USE_REVERSE_PROXY: "yes"
    bunkerized-nginx.REVERSE_PROXY_URL: "/"
    bunkerized-nginx.REVERSE_PROXY_HOST: "http://myservice.default.svc.cluster.local"
spec:
  type: ClusterIP
  selector:
    app: myservice
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
```

### Linux

Example of a basic configuration file :
```conf
HTTP_PORT=80
HTTPS_PORT=443
DNS_RESOLVERS=8.8.8.8 8.8.4.4
SERVER_NAME=www.example.com
AUTO_LETS_ENCRYPT=yes
USE_REVERSE_PROXY=yes
REVERSE_PROXY_URL=/
# Local proxied application
REVERSE_PROXY_HOST=http://127.0.0.1:8080
# Remote proxied application
#REVERSE_PROXY_HOST=http://service.example.local:8080
```

## PHP applications

The following environment variables can be used to configure bunkerized-nginx in front of PHP-FPM web applications :
- `REMOTE_PHP` : host/ip of a remote PHP-FPM instance
- `REMOTE_PHP_PATH` : absolute path containing the PHP files (from the remote instance perspective) 
- `LOCAL_PHP` : absolute path of the local unix socket used by a local PHP-FPM instance
- `LOCAL_PHP_PATH` : absolute path containing the PHP files (when using local instance)

Here is a basic example with a remote instance :
```conf
SERVER_NAME=www.example.com
REMOTE_PHP=my-php.example.local
REMOTE_PHP_PATH=/var/www/html
```

And another example with a local instance :
```conf
SERVER_NAME=www.example.com
LOCAL_PHP=/var/run/php7-fpm.sock
LOCAL_PHP_PATH=/opt/bunkerized-nginx/www
```

### Docker

When using Docker, the recommended way is to create a network so bunkerized-nginx can communicate with the PHP-FPM instance using the container name :
```shell
$ docker network create services-net
$ docker run -d \
         --name myservice \
         --network services-net \
         -v "${PWD}/www:/app" \
         php:fpm
$ docker run -d \
         --network services-net \
         -p 80:8080 \
         -p 443:8443 \
         -v "${PWD}/www:/www:ro" \
         -v "${PWD}/certs:/etc/letsencrypt" \
         -e SERVER_NAME=www.example.com \
         -e AUTO_LETS_ENCRYPT=yes \
         -e REMOTE_PHP=myservice \
         -e REMOTE_PHP_PATH=/app \
         bunkerity/bunkerized-nginx
```


docker-compose equivalent :
```yaml
version: '3'

services:

  mybunkerized:
    image: bunkerity/bunkerized-nginx
    ports:
      - 80:8080
      - 443:8443
    volumes:
      - ./www:/www:ro
      - ./certs:/etc/letsencrypt
    environment:
      - SERVER_NAME=www.example.com
      - AUTO_LETS_ENCRYPT=yes
      - REMOTE_PHP=myservice
      - REMOTE_PHP_PATH=/app
    networks:
      - services-net
    depends_on:
      - myservice

  myservice:
    image: php:fpm
    networks:
      - services-net
    volumes:
      - ./www:/app

networks:
  services-net:
```

### Docker autoconf

When the Docker autoconf stack is running, you simply need to start the container hosting your PHP-FPM instance and add the environment variables as labels :

```shell
$ docker run -d \
         --name myservice \
         --network services-net \
         -v "${PWD}/www/www.example.com:/app" \
         -l bunkerized-nginx.SERVER_NAME=www.example.com \
         -l bunkerized-nginx.REMOTE_PHP=myservice \
         -l bunkerized-nginx.REMOTE_PHP_PATH=/app \
         php:fpm
```

```yaml
version: '3'

services:

  myservice:
    image: php:fpm
    volumes:
      - ./www/www.example.com:/app
    networks:
      services-net:
        aliases:
          - myservice
    labels:
      - bunkerized-nginx.SERVER_NAME=www.example.com
      - bunkerized-nginx.REMOTE_PHP=myservice
      - bunkerized-nginx.REMOTE_PHP_PATH=/app

networks:
  services-net:
    external:
      name: services-net
```

### Docker Swarm

When the Docker Swarm stack is running, you simply need to start the Swarm service hosting your PHP-FPM instance and add the environment variables as labels :
```shell
$ docker service create \
         --name myservice \
         --constraint node.role==worker \
         --network services-net \
         --mount type=bind,source=/shared/www/www.example.com,destination=/app \
         -l bunkerized-nginx.SERVER_NAME=www.example.com \
         -l bunkerized-nginx.REMOTE_PHP=myservice \
         -l bunkerized-nginx.REMOTE_PHP_PATH=/app \
         php:fpm
```

docker-compose equivalent :
```yaml
version: "3"

services:

  myservice:
    image: php:fpm
    networks:
      services-net:
        aliases:
          - myservice
    volumes:
      - /shared/www/www.example.com:/app
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerized-nginx.SERVER_NAME=www.example.com"
        - "bunkerized-nginx.REMOTE_PHP=myservice"
        - "bunkerized-nginx.REMOTE_PHP_PATH=/app"

networks:
  services-net:
    external:
      name: services-net
```

### Kubernetes

You need to use environment variables as annotations prefixed with `bunkerized-nginx.` inside the Service resource of your PHP-FPM instance :

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myservice
  labels:
    app: myservice
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myservice
  template:
    metadata:
      labels:
        app: myservice
    spec:
      containers:
      - name: myservice
        image: php:fpm
        volumeMounts:
        - name: php-files
          mountPath: /app
      volumes:
      - name: php-files
        hostPath:
          path: /shared/www/www.example.com
          type: Directory
---
apiVersion: v1
kind: Service
metadata:
  name: myservice
  # this label is mandatory
  labels:
    bunkerized-nginx: "yes"
  annotations:
    bunkerized-nginx.SERVER_NAME: "www.example.com"
    bunkerized-nginx.AUTO_LETS_ENCRYPT: "yes"
    bunkerized-nginx.REMOTE_PHP: "myservice.default.svc.cluster.local"
    bunkerized-nginx.REMOTE_PHP_PATH: "/app"
spec:
  type: ClusterIP
  selector:
    app: myservice
  ports:
    - protocol: TCP
      port: 9000
      targetPort: 9000
```

### Linux

Example of a basic configuration file :
```conf
HTTP_PORT=80
HTTPS_PORT=443
DNS_RESOLVERS=8.8.8.8 8.8.4.4
SERVER_NAME=www.example.com
AUTO_LETS_ENCRYPT=yes
# Case 1 : the PHP-FPM instance is on the same machine
# you just need to adjust the socket path
LOCAL_PHP=/run/php/php7.3-fpm.sock
LOCAL_PHP_PATH=/opt/bunkerized-nginx/www
# Case 2 : the PHP-FPM instance is on another machine
#REMOTE_PHP=myapp.example.local
#REMOTE_PHP_PATH=/app
```

Don't forget that bunkerized-nginx runs as an unprivileged user/group both named `nginx`. When using a local PHP-FPM instance, you will need to take care of the rights and permissions of the socket and web files.

For example, if your PHP-FPM is running as the `www-data` user, you can create a new group called `web-users` and add `nginx` and `www-data` into it :
```shell
$ groupadd web-users
$ usermod -a -G web-users nginx
$ usermod -a -G web-users www-data
```

Once it's done, you will need to tweak your PHP-FPM configuration file (e.g., `/etc/php/7.3/fpm/pool.d/www.conf`) to edit the default group of the processes and the permissions of the socket file :
```conf
[www]
...
user = www-data
group = web-users
...
listen = /run/php/php7.3-fpm.sock
listen.owner = www-data
listen.group = web-users
listen.mode = 0660
...
```

Last but not least, you will need to edit the permissions of `/opt/bunkerized-nginx/www` to make sure that nginx can read and PHP-FPM can write (in case your PHP app needs it) :
```shell
$ chown root:web-users /opt/bunkerized-nginx/www
$ chmod 750 /opt/bunkerized-nginx/www
$ find /opt/bunkerized-nginx/www/* -exec chown www-data:nginx {} \;
$ find /opt/bunkerized-nginx/www/* -type f -exec chmod 740 {} \;
$ find /opt/bunkerized-nginx/www/* -type d -exec chmod 750 {} \;
```

## Multisite

If you have multiple services to protect, the easiest way to do it is by enabling the "multisite" mode. When using multisite, bunkerized-nginx will create one server block per server defined in the `SERVER_NAME` environment variable. You can configure each servers independently by adding the server name as a prefix.

Here is an example :
```conf
SERVER_NAME=app1.example.com app2.example.com
MULTISITE=yes
app1.example.com_USE_REVERSE_PROXY=yes
app1.example.com_REVERSE_PROXY_URL=/
app1.example.com_REVERSE_PROXY_HOST=http://app1.example.local:8080
app2.example.com_REMOTE_PHP=app2.example.local
app2.example.com_REMOTE_PHP_PATH=/var/www/html
```

When using the multisite mode, some [special folders](https://bunkerized-nginx.readthedocs.io/en/latest/special_folders.html) must have a specific structure with subfolders named the same as the servers defined in the `SERVER_NAME` environment variable. Let's take the **app2.example.com** as an example : if some static files need to be served by nginx, you need to place them under **www/app2.example.com**.

### Docker

When using Docker, the recommended way is to create a network so bunkerized-nginx can communicate with the web services using the container name :
```shell
$ docker network create services-net
$ docker run -d \
         --name myapp1 \
         --network services-net \
         tutum/hello-world
$ docker run -d \
         --name myapp2 \
         --network services-net \
         -v "${PWD}/www/app2.example.com:/app" \
         php:fpm
$ docker run -d \
         --network services-net \
         -p 80:8080 \
         -p 443:8443 \
         -v "${PWD}/www:/www:ro" \
         -v "${PWD}/certs:/etc/letsencrypt" \
         -e "SERVER_NAME=app1.example.com app2.example.com" \
         -e MULTISITE=yes \
         -e AUTO_LETS_ENCRYPT=yes \
         -e app1.example.com_USE_REVERSE_PROXY=yes \
         -e app1.example.com_REVERSE_PROXY_URL=/ \
         -e app1.example.com_REVERSE_PROXY_HOST=http://myapp1 \
         -e app2.example.com_REMOTE_PHP=myapp2 \
         -e app2.example.com_REMOTE_PHP_PATH=/app \
         bunkerity/bunkerized-nginx
```

docker-compose equivalent :
```yaml
version: '3'

services:

  mybunkerized:
    image: bunkerity/bunkerized-nginx
    ports:
      - 80:8080
      - 443:8443
    volumes:
      - ./www:/www:ro
      - ./certs:/etc/letsencrypt
    environment:
      - SERVER_NAME=app1.example.com app2.example.com
      - MULTISITE=yes
      - AUTO_LETS_ENCRYPT=yes
      - app1.example.com_USE_REVERSE_PROXY=yes
      - app1.example.com_REVERSE_PROXY_URL=/
      - app1.example.com_REVERSE_PROXY_HOST=http://myapp1
      - app2.example.com_REMOTE_PHP=myapp2
      - app2.example.com_REMOTE_PHP_PATH=/app
    networks:
      - services-net
    depends_on:
      - myapp1
      - myapp2

  myapp1:
    image: tutum/hello-world
    networks:
      - services-net

  myapp2:
    image: php:fpm
    volumes:
      - ./www/app2.example.com:/app
    networks:
      - services-net

networks:
  services-net:
```

### Docker autoconf

**The multisite feature must be activated when using the Docker autoconf integration.**

When the Docker autoconf stack is running, you simply need to start the containers hosting your web services and add the environment variables as labels :
```shell
$ docker run -d \
         --name myapp1 \
         --network services-net \
         -l bunkerized-nginx.SERVER_NAME=app1.example.com \
         -l bunkerized-nginx.USE_REVERSE_PROXY=yes \
         -l bunkerized-nginx.REVERSE_PROXY_URL=/ \
         -l bunkerized-nginx.REVERSE_PROXY_HOST=http://myapp1 \
         tutum/hello-world
$ docker run -d \
         --name myapp2 \
         --network services-net \
         -v "${PWD}/www/app2.example.com:/app" \
         -l bunkerized-nginx.SERVER_NAME=app2.example.com \
         -l bunkerized-nginx.REMOTE_PHP=myapp2 \
         -l bunkerized-nginx.REMOTE_PHP_PATH=/app \
         php:fpm
```

docker-compose equivalent :
```yaml
version: '3'

services:

  myapp1:
    image: tutum/hello-world
    networks:
      services-net:
        aliases:
          - myapp1
    labels:
      - bunkerized-nginx.SERVER_NAME=app1.example.com
      - bunkerized-nginx.USE_REVERSE_PROXY=yes
      - bunkerized-nginx.REVERSE_PROXY_URL=/
      - bunkerized-nginx.REVERSE_PROXY_HOST=http://myapp1

  myapp2:
    image: php:fpm
    networks:
      services-net:
        aliases:
          - myapp2
    volumes:
      - ./www/app2.example.com:/app
    labels:
      - bunkerized-nginx.SERVER_NAME=app2.example.com
      - bunkerized-nginx.REMOTE_PHP=myapp2
      - bunkerized-nginx.REMOTE_PHP_PATH=/app

networks:
  services-net:
    external:
      name: services-net
```

### Docker Swarm

**The multisite feature must be activated when using the Docker Swarm integration.**

When the Docker Swarm stack is running, you simply need to start the Swarm service hosting your web services and add the environment variables as labels :
```shell
$ docker service create \
         --name myapp1 \
         --network services-net \
         --constraint node.role==worker \
         -l bunkerized-nginx.SERVER_NAME=app1.example.com \
         -l bunkerized-nginx.USE_REVERSE_PROXY=yes \
         -l bunkerized-nginx.REVERSE_PROXY_URL=/ \
         -l bunkerized-nginx.REVERSE_PROXY_HOST=http://myapp1 \
         tutum/hello-world
$ docker service create \
         --name myapp2 \
         --constraint node.role==worker \
         --network services-net \
         --mount type=bind,source=/shared/www/app2.example.com,destination=/app \
         -l bunkerized-nginx.SERVER_NAME=app2.example.com \
         -l bunkerized-nginx.REMOTE_PHP=myapp2 \
         -l bunkerized-nginx.REMOTE_PHP_PATH=/app \
         php:fpm
```

docker-compose equivalent :
```yaml
version: "3"

services:

  myapp1:
    image: tutum/hello-world
    networks:
      services-net:
        aliases:
          - myapp1
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - bunkerized-nginx.SERVER_NAME=app1.example.com
        - bunkerized-nginx.USE_REVERSE_PROXY=yes
        - bunkerized-nginx.REVERSE_PROXY_URL=/
        - bunkerized-nginx.REVERSE_PROXY_HOST=http://myapp1

  myapp2:
    image: php:fpm
    networks:
      services-net:
        aliases:
          - myapp2
    volumes:
      - /shared/www/app2.example.com:/app
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerized-nginx.SERVER_NAME=app2.example.com"
        - "bunkerized-nginx.REMOTE_PHP=myapp2"
        - "bunkerized-nginx.REMOTE_PHP_PATH=/app"

networks:
  services-net:
    external:
      name: services-net
```

### Kubernetes

**The multisite feature must be activated when using the Kubernetes integration.**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp1
  labels:
    app: myapp1
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myapp1
  template:
    metadata:
      labels:
        app: myapp1
    spec:
      containers:
      - name: myapp1
        image: tutum/hello-world
---
apiVersion: v1
kind: Service
metadata:
  name: myapp1
  # this label is mandatory
  labels:
    bunkerized-nginx: "yes"
  annotations:
    bunkerized-nginx.SERVER_NAME: "app1.example.com"
    bunkerized-nginx.AUTO_LETS_ENCRYPT: "yes"
    bunkerized-nginx.USE_REVERSE_PROXY: "yes"
    bunkerized-nginx.REVERSE_PROXY_URL: "/"
    bunkerized-nginx.REVERSE_PROXY_HOST: "http://myapp1.default.svc.cluster.local"
spec:
  type: ClusterIP
  selector:
    app: myapp1
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp2
  labels:
    app: myapp2
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myapp2
  template:
    metadata:
      labels:
        app: myapp2
    spec:
      containers:
      - name: myapp2
        image: php:fpm
        volumeMounts:
        - name: php-files
          mountPath: /app
      volumes:
      - name: php-files
        hostPath:
          path: /shared/www/app2.example.com
          type: Directory
---
apiVersion: v1
kind: Service
metadata:
  name: myapp2
  # this label is mandatory
  labels:
    bunkerized-nginx: "yes"
  annotations:
    bunkerized-nginx.SERVER_NAME: "app2.example.com"
    bunkerized-nginx.AUTO_LETS_ENCRYPT: "yes"
    bunkerized-nginx.REMOTE_PHP: "myapp2.default.svc.cluster.local"
    bunkerized-nginx.REMOTE_PHP_PATH: "/app"
spec:
  type: ClusterIP
  selector:
    app: myapp2
  ports:
    - protocol: TCP
      port: 9000
      targetPort: 9000
```

### Linux

Example of a basic configuration file :
```conf
HTTP_PORT=80
HTTPS_PORT=443
DNS_RESOLVERS=8.8.8.8 8.8.4.4
SERVER_NAME=app1.example.com app2.example.com
MULTISITE=yes
AUTO_LETS_ENCRYPT=yes
app1.example.com_USE_REVERSE_PROXY=yes
app1.example.com_REVERSE_PROXY_URL=/
# Local proxied application
app1.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8080
# Remote proxied application
#app1.example.com_REVERSE_PROXY_HOST=http://service.example.local:8080
# If the PHP-FPM instance is on the same machine
# you just need to adjust the socket path
app2.example.com_LOCAL_PHP=/run/php/php7.3-fpm.sock
app2.example.com_LOCAL_PHP_PATH=/opt/bunkerized-nginx/www/app2.example.com
# Else if the PHP-FPM instance is on another machine
#app2.example.com_REMOTE_PHP=myapp.example.local
#app2.example.com_REMOTE_PHP_PATH=/app
```

Don't forget that bunkerized-nginx runs as an unprivileged user/group both named `nginx`. When using a local PHP-FPM instance, you will need to take care of the rights and permissions of the socket and web files.

See the [Linux section of PHP application](#id5) for more information.
