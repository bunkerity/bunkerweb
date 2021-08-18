# Web UI

## Overview

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/web-ui.gif?raw=true" />

## Usage

The web UI has its own set of environment variables to configure it :
- `ADMIN_USERNAME` and `ADMIN_PASSWORD` : credentials for accessing the web UI
- `ABSOLUTE_URI` : the full public URI that points to the web UI
- `API_URI` : path of the bunkerized-nginx API (must match the corresponding `API_URI` of the bunkerized-nginx instance)
- `DOCKER_HOST` : Docker API endpoint address (default = `unix:///var/run/docker.sock`)

Since the web UI is a web service itself, we can use bunkerized-nginx as a reverse proxy in front of it.

**Using the web UI in a Docker environment exposes a security risk because you need to mount the Docker API socket into the web UI container. It's highly recommended to use a middleware like [tecnativa/docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy) to reduce the risk as much as possible.**

**You need to apply the security best practices because the web UI contains code and that code might be vulnerable : complex admin password, hard to guess public URI, network isolation from others services, HTTPS only, ...**

### Docker

First of all, we will need to setup two networks one for ui communication and the other one for the services :
```shell
$ docker network create ui-net
$ docker network create services-net
```

We also need a volume to shared the generated configuration from the web UI to the bunkerized-nginx instances :
```shell
$ docker volume create bunkerized-vol
```

Next we will create the "Docker API proxy" container that will be in the front of the Docker socket and deny access to sensitive things :
```shell
$ docker run -d \
         --name my-docker-proxy \
         --network ui-net \
         -v /var/run/docker.sock:/var/run/docker.sock:ro \
         -e CONTAINERS=1 \
         -e SWARM=1 \
         -e SERVICES=1 \
         tecnativa/docker-socket-proxy
```

We can now create the web UI container based on bunkerized-nginx-ui image :
```shell
$ docker run -d \
         --name my-bunkerized-ui \
         --network ui-net \
         -v bunkerized-vol:/etc/nginx \
         -e ABSOLUTE_URI=https://admin.example.com/admin-changeme/ \
         -e DOCKER_HOST=tcp://my-docker-proxy:2375 \
         -e API_URI=/ChangeMeToSomethingHardToGuess \
         -e ADMIN_USERNAME=admin \
         -e ADMIN_PASSWORD=changeme \
         bunkerity/bunkerized-nginx-ui
```

Last but not least, you need to start the bunkerized-nginx and configure it as a reverse proxy for the web UI web service :
```shell
$ docker create \
         --name my-bunkerized \
         --network ui-net \
         -p 80:8080 \
         -p 443:8443 \
         -v bunkerized-vol:/etc/nginx \
         -v "${PWD}/certs:/etc/letsencrypt" \
         -e SERVER_NAME=admin.example.com \
         -e MULTISITE=yes \
         -e USE_API=yes \
         -e API_URI=/ChangeMeToSomethingHardToGuess \
         -e AUTO_LETS_ENCRYPT=yes \
         -e REDIRECT_HTTP_TO_HTTPS=yes \
         -e admin.example.com_USE_REVERSE_PROXY=yes \
         -e admin.example.com_REVERSE_PROXY_URL=/admin-changeme/ \
         -e admin.example.com_REVERSE_PROXY_HOST=http://my-bunkerized-ui:5000 \
         -e "admin.example.com_REVERSE_PROXY_HEADERS=X-Script-Name /admin-changeme" \
         -e admin.example.com_USE_MODSECURITY=no \
         -l bunkerized-nginx.UI \
         bunkerity/bunkerized-nginx
$ docker network connect services-net my-bunkerized
$ docker start my-bunkerized
```

The web UI should now be accessible at https://admin.example.com/admin-changeme/.

docker-compose equivalent :
```yaml
version: '3'

services:

  my-bunkerized:
    image: bunkerity/bunkerized-nginx
    restart: always
    depends_on:
      - my-bunkerized-ui
    networks:
      - services-net
      - ui-net
    ports:
      - 80:8080
      - 443:8443
    volumes:
      - ./letsencrypt:/etc/letsencrypt
      - bunkerized-vol:/etc/nginx
    environment:
      - SERVER_NAME=admin.example.com                                         # replace with your domain
      - MULTISITE=yes
      - USE_API=yes
      - API_URI=/ChangeMeToSomethingHardToGuess                               # change it to something hard to guess + must match API_URI from myui service
      - AUTO_LETS_ENCRYPT=yes
      - REDIRECT_HTTP_TO_HTTPS=yes
      - admin.example.com_USE_REVERSE_PROXY=yes
      - admin.example.com_REVERSE_PROXY_URL=/admin-changeme/                  # change it to something hard to guess
      - admin.example.com_REVERSE_PROXY_HOST=http://my-bunkerized-ui:5000
      - admin.example.com_REVERSE_PROXY_HEADERS=X-Script-Name /admin-changeme # must match REVERSE_PROXY_URL
      - admin.example.com_USE_MODSECURITY=no
    labels:
      - "bunkerized-nginx.UI"

  my-bunkerized-ui:
    image: bunkerity/bunkerized-nginx-ui
    restart: always
    depends_on:
      - my-docker-proxy
    networks:
      - ui-net
    volumes:
      - bunkerized-vol:/etc/nginx
    environment:
      - ABSOLUTE_URI=https://admin.example.com/admin-changeme/ # change it to your full URI
      - DOCKER_HOST=tcp://my-docker-proxy:2375
      - API_URI=/ChangeMeToSomethingHardToGuess                # must match API_URI from bunkerized-nginx
      - ADMIN_USERNAME=admin                                   # change it to something hard to guess
      - ADMIN_PASSWORD=changeme                                # change it to a good password

  my-docker-proxy:
    image: tecnativa/docker-socket-proxy
    restart: always
    networks:
      - ui-net
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - CONTAINERS=1
      - SWARM=1
      - SERVICES=1

networks:
  ui-net:
  services-net:
    name: services-net

volumes:
  bunkerized-vol:
```

### Linux

First of all, you need to edit the web UI configuration file located at `/opt/bunkerized-nginx/ui/variables.env` :
```conf
ABSOLUTE_URI=https://admin.example.com/admin-changeme/
DOCKER_HOST=
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme
```

Make sure that the web UI service is automatically started on boot :
```shell
$ systemctl enable bunkerized-nginx-ui
```

Now you can start the web UI service :
```shell
$ systemctl start bunkerized-nginx-ui
```

Edit the bunkerized-nginx configurations located at `/opt/bunkerized-nginx/variables.env` :
```conf
HTTP_PORT=80
HTTPS_PORT=443
DNS_RESOLVERS=8.8.8.8 8.8.4.4
SERVER_NAME=admin.example.com
MULTISITE=yes
AUTO_LETS_ENCRYPT=yes
REDIRECT_HTTP_TO_HTTPS=yes
admin.example.com_USE_REVERSE_PROXY=yes
admin.example.com_REVERSE_PROXY_URL=/admin-changeme/
# Local bunkerized-nginx-ui
admin.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:5000
# Remote bunkerized-nginx-ui
#REVERSE_PROXY_HOST=http://service.example.local:5000
admin.example.com_REVERSE_PROXY_HEADERS=X-Script-Name /admin-changeme
admin.example.com_USE_MODSECURITY=no
```

And run the `bunkerized-nginx` command to apply changes :
```shell
$ bunkerized-nginx
```

The web UI should now be accessible at https://admin.example.com/admin-changeme/.
