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

If you have multiple web services you configure multiple reverse proxy rules by appending a number to the environment variables names :
```conf
SERVER_NAME=www.example.com
USE_REVERSE_PROXY=yes
REVERSE_PROXY_URL_1=/app1
REVERSE_PROXY_HOST_1=http://app1.example.local:8080
REVERSE_PROXY_URL_2=/app2
REVERSE_PROXY_HOST_2=http://app2.example.local:8080
```

### Docker

When using Docker, the recommended way is to create a network so bunkerized-nginx can communicate with the web service using its container name :
```shell
$ docker network create services-net
$ docker run -d \
         --name myservice \
         --network services-net \
         tutum/hello-world
$ docker run -d \
         --network services-net
         -p 80:8080 \
         -p 443:8443 \
         -v "${PWD}/www:/www:ro" \
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
      - ./www:/www:ro
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
      myservice:
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
      myservice:
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
    bunkerized-nginx.USE_REVERSE_PROXY: "yes"
    bunkerized-nginx.REVERSE_PROXY_URL: "/"
    bunkerized-nginx.REVERSE_PROXY_HOST: "http://myservice"
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

TODO

### Docker autoconf

TODO

### Docker Swarm

TODO

### Kubernetes

TODO

## Multisite

If you have multiple services to protect, the easiest way to do it is by enabling the "multisite" mode. When using multisite, bunkerized-nginx will create one server block per server defined in the SERVER_NAME environment variable. You can configure each servers independently by adding the server name as a prefix.

Here is an example :
```conf
SERVER_NAME=app1.example.com app2.example.com
app1.example.com_USE_REVERSE_PROXY=yes
app1.example.com_REVERSE_PROXY_URL=/
app1.example.com_REVERSE_PROXY_HOST=http://app1.example.local:8080
app2.example.com_REMOTE_PHP=app2.example.local
app2.example.com_REMOTE_PHP_PATH=/var/www/html
```

### Docker

TODO

### Docker autoconf

TODO

### Docker Swarm

TODO

### Kubernetes

TODO
