# Integrations

## Docker

### Introduction

You can get official prebuilt Docker images of bunkerized-nginx for x86, x64, armv7 and aarch64/arm64 architectures on Docker Hub :
```shell
$ docker pull bunkerity/bunkerized-nginx
```

Or you can build it from source if you wish :
```shell
$ git clone https://github.com/bunkerity/bunkerized-nginx.git
$ cd bunkerized-nginx
$ docker build -t bunkerized-nginx .
```

To use bunkerized-nginx as a Docker container you have to pass specific environment variables, mount volumes and redirect ports to make it accessible from the outside.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/docker.png?raw=true" />

### Basic usage

To demonstrate the use of the Docker image, we will create a simple "Hello World" static file that will be served by bunkerized-nginx.

**One important thing to know is that the container runs as an unprivileged user with UID and GID 101. The reason behind this behavior is the security : in case a vulnerability is exploited the attacker won't have full privileges. But there is also a downside because bunkerized-nginx (heavily) make use of volumes, you will need to adjust the rights on the host.**

First create the environment on the host :
```shell
$ mkdir bunkerized-hello bunkerized-hello/www bunkerized-hello/certs
$ cd bunkerized-hello
$ chown root:101 www certs
$ chmod 750 www
$ chmod 770 certs
```

The www folder will contain our static files that will be served by bunkerized-nginx. Whereas the certs folder will store the automatically generated Let's Encrypt certificates.

Let's create a dummy static page into the www folder :
```shell
$ echo "Hello bunkerized World !" > www/index.html
$ chown root:101 www/index.html
$ chmod 740 www/index.html
```

It's time to run the container :
```shell
$ docker run \
         -p 80:8080 \
         -p 443:8443 \
         -v "${PWD}/www:/www:ro" \
         -v "${PWD}/certs:/etc/letsencrypt" \
         -e SERVER_NAME=www.example.com \
         -e AUTO_LETS_ENCRYPT=yes \
         bunkerity/bunkerized-nginx
```

Or if you prefer docker-compose :
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
```

Important things to note :
- Replace www.example.com with your own domain (it must points to your server IP address if you want Let's Encrypt to work)
- Automatic Let's Encrypt is enabled thanks to `AUTO_LETS_ENCRYPT=yes` (since the default is `AUTO_LETS_ENCRYPT=no` you can remove the environment variable to disable Let's Encrypt)
- The container is exposing TCP/8080 for HTTP and TCP/8443 for HTTPS
- The /www volume is used to deliver static files and can be mounted as read-only for security reason
- The /etc/letsencrypt volume is used to store certificates and must be mounted as read/write

Inspect the container logs until bunkerized-nginx is started then visit http(s)://www.example.com to confirm that everything is working as expected.

This example is really simple but, as you can see in the [list of environment variables](#TODO), you may get a lot of environment variables depending on your use case. To make things cleanier, you can write the environment variables to a file :
```shell
$ cat variables.env
SERVER_NAME=www.example.com
AUTO_LETS_ENCRYPT=yes
```

And load the file when creating the container :
```shell
$ docker run ... --env-file "${PWD}/variables.env" ... bunkerity/bunkerized-nginx
```

Or if you prefer docker-compose :
```yaml
...
services:
  mybunkerized:
    ...
    env_file:
      - ./variables.env
    ...
...
```

### Autoconf

The downside of using environment variables is that the container needs to be recreated each time there is an update which is not very convenient. To counter that issue, you can use another image called bunkerized-nginx-autoconf which will listen for Docker events and automatically configure bunkerized-nginx instance in real time without recreating the container. Instead of defining environment variables for the bunkerized-nginx container, you simply add labels to your web services and bunkerized-nginx-autoconf will "automagically" take care of the rest.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/autoconf-docker.png?raw=true" />

First of all, you will need a network so autoconf and bunkerized-nginx can communicate and another one to allow communication between bunkerized-nginx and your web services :
```shell
$ docker network create bunkerized-net
$ docker network create services-net
```

We will also make use of a named volume to share the configuration :
```shell
$ docker volume create bunkerized-vol
```

You can now create the bunkerized-nginx container, connect it to the web services network and start it :
```shell
$ docker run \
         --name mybunkerized \
         -l bunkerized-nginx.AUTOCONF \
         --network bunkerized-net \
         -p 80:8080 \
         -p 443:8443 \
         -v "${PWD}/www:/www:ro" \
         -v "${PWD}/certs:/etc/letsencrypt:ro" \
         -v bunkerized-vol:/etc/nginx:ro \
         -e MULTISITE=yes \
         -e SERVER_NAME= \
         -e AUTO_LETS_ENCRYPT=yes \
         bunkerity/bunkerized-nginx
$ docker network connect services-net mybunkerized
$ docker start mybunkerized
```

The autoconf one can now be started :
```shell
$ docker run \
         --name myautoconf \
         --network bunkerized-net \
         --volumes-from mybunkerized:rw \
         -v /var/run/docker.sock:/var/run/docker.sock:ro \
         bunkerity/bunkerized-nginx-autoconf
```

Here is the docker-compose equivalent :
```yaml
version: '3'

services:

  mybunkerized:
    image: bunkerity/bunkerized-nginx
    restart: always
    ports:
      - 80:8080
      - 443:8443
    volumes:
      - ./certs:/etc/letsencrypt
      - ./www:/www:ro
      - bunkerized-vol:/etc/nginx
    environment:
      - SERVER_NAME=
      - MULTISITE=yes
      - AUTO_LETS_ENCRYPT=yes
    labels:
      - "bunkerized-nginx.AUTOCONF"
    networks:
      - bunkerized-net
      - services-net

  myautoconf:
    image: bunkerity/bunkerized-nginx-autoconf
    restart: always
    volumes_from:
      - mybunkerized
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      - mybunkerized
    networks:
      - bunkerized-net

volumes:
  autoconf:

networks:
  bunkerized-net:
    name: bunkerized-net
  services-net:
    name: services-net
```

Important things to note :
- autoconf needs to send reload orders to bunkerized-nginx, they need to be on the same network
- autoconf is generating config files and other artefacts for the bunkerized-nginx, they need to share the volumes
- autoconf must have access to the Docker socket in order to get events and access to labels
- bunkerized-nginx must have the bunkerized-nginx.AUTOCONF label
- bunkerized-nginx must be started in [multisite mode](#) with the `MULTISITE=yes` environment variable
- When setting the `SERVER_NAME` environment variable to an empty value, bunkerized-nginx won't generate any web service configuration at startup
- The `AUTO_LETS_ENCRYPT=yes` will be applied to all subsequent web service configuration, unless overriden by the web service labels

Check the logs of both autoconf and bunkerized-nginx to see if everything is working as expected.

You can now create a new web service and add environment variables as labels with the **"bunkerized-nginx." prefix** so the autoconf service will "automagically" do the configuration for you :
```shell
$ docker run \
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
version: "3"

services:

  myservice:
    image: tutum/hello-world
    networks:
      myservice:
        aliases:
          - myservice
    labels:
      - "bunkerized-nginx.SERVER_NAME=www.example.com"
      - "bunkerized-nginx.USE_REVERSE_PROXY=yes"
      - "bunkerized-nginx.REVERSE_PROXY_URL=/"
      - "bunkerized-nginx.REVERSE_PROXY_HOST=http://myservice"

networks:
  services-net:
    external:
      name: services-net
```

Please note that if you want to override the `AUTO_LETS_ENCRYPT=yes` previously defined in the bunkerized-nginx container, you simply need to add the `bunkerized-nginx.AUTO_LETS_ENCRYPT=no` label.

Look at the logs of both autoconf and bunkerized-nginx to check if the configuration has been generated and loaded by bunkerized-nginx. You should now be able to visit http(s)://www.example.com.

When your service is not needed anymore, you can delete it as usual. The autoconf should get the event and remove generate the configuration again.

## Docker Swarm

## Kubernetes

## Linux
