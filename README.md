<p align="center">
	<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/logo.png?raw=true" width="425" />
</p>

<p align="center">
        <img src="https://img.shields.io/badge/bunkerized--nginx-1.2.7-blue" />
        <img src="https://img.shields.io/badge/nginx-1.20.1-blue" />
        <img src="https://img.shields.io/github/last-commit/bunkerity/bunkerized-nginx" />
        <img src="https://img.shields.io/github/workflow/status/bunkerity/bunkerized-nginx/Automatic%20test?label=automatic%20test" />
        <img src="https://img.shields.io/github/workflow/status/bunkerity/bunkerized-nginx/Build%20and%20push%20bunkerized-nginx?label=docker%20build" />
        <img src="https://img.shields.io/readthedocs/bunkerized-nginx" />
</p>

<p align="center">
	<strong>
		<a href="https://bunkerized-nginx.readthedocs.io">Documentation</a>
		 &#124; 
		<a href="https://github.com/bunkerity/bunkerized-nginx/tree/master/examples">Examples</a>
		 &#124; 
		<a href="https://www.bunkerity.com/category/bunkerized-nginx/">Blog posts</a>
		 &#124; 
		<a href="https://coso.me/bunkerity-chat">Community chat</a>
		 &#124; 
		<a href="https://coso.me/bunkerity">Follow us</a>
	</strong>
</p>

> Make security by default great again !

bunkerized-nginx is a web server based on the notorious nginx and focused on security. It integrates into existing environments (Linux, Docker, Swarm, Kubernetes, ...) to make your web services "secured by default" without any hassle. The security best practices are automatically applied for you while keeping control of every settings to meet your own use case.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/overview.png?raw=true" />

Non-exhaustive list of features :
- HTTPS support with transparent Let's Encrypt automation
- State-of-the-art web security : HTTP security headers, prevent leaks, TLS hardening, ...
- Integrated ModSecurity WAF with the OWASP Core Rule Set
- Automatic ban of strange behaviors
- Antibot challenge through cookie, javascript, captcha or recaptcha v3
- Block TOR, proxies, bad user-agents, countries, ...
- Block known bad IP with DNSBL
- Prevent bruteforce attacks with rate limiting
- Plugins system for external security checks (ClamAV, CrowdSec, ...)
- Easy to configure with environment variables or web UI
- Seamless integration into existing environments : Linux, Docker, Swarm, Kubernetes, ...

Fooling automated tools/scanners :

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/demo.gif?raw=true" />

You can find a live demo at https://demo-nginx.bunkerity.com, feel free to do some security tests.

# Table of contents
<details>
	<summary>Click to show</summary>

- [Table of contents](#table-of-contents)
- [Integrations](#integrations)
  * [Docker](#docker)
  * [Swarm](#swarm)
  * [Kubernetes][#kubernetes] 
  * [Linux](#linux)
- [Use-cases](#use-cases)
  * [Static pages](#static-pages)
  * [PHP applications](#php-application)
  * [Reverse proxy](#reverse-proxy)
  * [Custom configurations](#custom-configurations)
- [Web UI](#web-ui)
- [Security tuning](#security-tuning)
- [Going further](#going-further)
- [License](#license)
- [Contributing](#contributing)
- [Security policy](#security-policy)
</details>

# Integrations

## Docker

You can get official prebuilt Docker images of bunkerized-nginx for x86, x64, armv7 and aarch64/arm64 architectures on Docker Hub :
```shell
$ docker pull bunkerity/bunkerized-nginx
```

Or you can build it from source if you wish :
```shell
$ docker build -t bunkerized-nginx .
```

To use bunkerized-nginx as a Docker container you have to pass specific environment variables, mount volumes and redirect ports to make it accessible from the outside.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/docker.png?raw=true" />

The downside of using environment variables is that the container needs to be recreated each time there is an update which is not very convenient. To counter that issue, you can use another image called bunkerized-nginx-autoconf which will listen for Docker events and automatically configure bunkerized-nginx instance in real time without recreating the container. Instead of defining environment variables for the bunkerized-nginx container, you simply add labels to your web services and bunkerized-nginx-autoconf will "automagically" take care of the rest.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/autoconf-docker.png?raw=true" />

You will find more information about Docker integration and Docker autoconf feature in the [documentation](#TODO).

## Swarm

Using bunkerized-nginx in a Docker Swarm cluster requires a shared folder accessible from both managers and workers (anything like NFS, GlusterFS, CephFS or even SSHFS will work). The deployment and configuration is very similar to the "Docker autoconf" one but with services instead of containers. A service based on the bunkerized-nginx-autoconf image needs to be scheduled on a manager node (don't worry it doesn't expose any network port for obvious security reasons). This service will listen for Docker Swarm events like service creation or deletion and generate the configuration according to the labels of each service. Once configuration generation is done, the bunkerized-nginx-autoconf service will send a reload order to all the bunkerized-nginx tasks so they can load the new configuration.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/swarm.png?raw=true" />

You will find more information about Docker Swarm integration in the [documentation](#TODO).

## Kubernetes

**This integration is still in beta, please fill an issue if you find a bug or have an idea on how to improve it.**

Using bunkerized-nginx in a Kubernetes cluster requires a shared folder accessible from the nodes (anything like NFS, GlusterFS, CephFS or even SSHFS will work). The bunkerized-nginx-autoconf acts as an Ingress Controller and connects to the k8s API to get cluster events and generate a new configuration when it's needed. Once the configuration is generated, the Ingress Controller sends a reload order to the bunkerized-nginx instances running in the cluster.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/kubernetes.png?raw=true" />

You will find more information about Kubernetes integration in the [documentation](#TODO).

## Linux

**This integration is still in beta, please fill an issue if you find a bug or have an idea on how to improve it.**

List of supported Linux distributions :
- Debian buster (10)
- Ubuntu focal (20.04)
- CentOS 7
- Fedora 34

Unlike containers, Linux integration can be tedious because bunkerized-nginx has a bunch of dependencies that need to be installed before we can use it. Fortunately, we provide a [helper script](#TODO) to make the process easier and automatic. Once installed, the configuration is really simple, all you have to do is to edit the `/opt/bunkerized-nginx/variables.env` configuration file and run the `bunkerized-nginx` command to apply it.

You will find more information about Linux integration in the [documentation](#TODO).

# Configuration

The configuration is made through what we call "environment variables" as a form of key/value pairs. You will find the complete list in the [documentation](#TODO).

## Singlesite

By default, bunkerized-nginx will only create one server block in the nginx configuration. This cover the simplest use-case where you want to protect one service easily and quickly.

Here is a dummy configuration as an example :
```conf
SERVER_NAME=example.com www.example.com
AUTO_LETS_ENCRYPT=yes
DISABLE_DEFAULT_SERVER=yes
USE_REVERSE_PROXY=yes
REVERSE_PROXY_URL=/
REVERSE_PROXY_HOST=http://internal-service.example.local:8080
# Uncomment the HTTP_PORT and HTTPS_PORTS variables when using Linux configuration
#HTTP_PORT=80
#HTTPS_PORT=443
```

## Multisite

If you have multiple services to protect, the easiest way to do it is by enabling the "multisite" mode. When using multisite, bunkerized-nginx will create one server block per server defined in the `SERVER_NAME` environment variable. You can configure each servers independently by adding the server name as a prefix.

Here is a dummy configuration as an example :
```conf
SERVER_NAME=app1.example.com app2.example.com
# Without prefix the variables are applied globally but can still be overriden
AUTO_LETS_ENCRYPT=yes
DISABLE_DEFAULT_SERVER=yes
# Specific configurations for first service
app1.example.com_USE_REVERSE_PROXY=yes
app1.example.com_REVERSE_PROXY_URL=/
app1.example.com_REVERSE_PROXY_HOST=http://internal-service.example.local:8080
# Specific configuration for second service
app2.example.com_REMOTE_PHP=my-fpm
app2.example.com_REMOTE_PHP_PATH=/var/www/html
# Uncomment the HTTP_PORT and HTTPS_PORTS variables when using Linux configuration
#HTTP_PORT=80
#HTTPS_PORT=443
```

## Special folders

|       Name       |                                     Location                                     |                                 Purpose                                 | Multisite |
|:----------------:|:--------------------------------------------------------------------------------:|:-----------------------------------------------------------------------:|:---------:|
| www              | /www (container)<br> /opt/bunkerized-nginx/www (Linux)                           | Static files that need to be delivered by bunkerized-nginx.             | Yes       |
| http-confs       | /http-confs (container)<br> /opt/bunkerized-nginx/http-confs (Linux)             | Custom nginx configuration files loaded at http context.                | No        |
| server-confs     | /server-confs (container)<br> /opt/bunkerized-nginx/server-confs (Linux)         | Custom nginx configuration files loaded at server context.              | Yes       |
| modsec-confs     | /modsec-confs (container)<br> /opt/bunkerized-nginx/modsec-confs (Linux)         | Custom ModSecurity configuration files loaded before the Core Rule Set. | Yes       |
| modsec-crs-confs | /modsec-crs-confs (container)<br> /opt/bunkerized-nginx/modsec-crs-confs (Linux) | Custom ModSecurity configuration files loaded after the Core Rule Set.  | Yes       |
| plugins          | /plugins (container)<br> /opt/bunkerized-nginx/plugins (Linux)                   | Location of bunkerized-nginx plugins.                                   | No        |
| cache            | /cache (container)<br> /opt/bunkerized-nginx/plugins (Linux)                     | Placeholder for caching data like external blacklists.                  | No        |
| acme-challenge   | /acme-challenge (container)<br> /opt/bunkerized-nginx/acme-challenge (Linux)     | Placeholder for Let's Encrypt challenges.                               | No        |

You will find more information about the special folders in the [documentation](#TODO).

# Web UI

TODO

# Security tuning

bunkerized-nginx comes with a set of predefined security settings that you can (and you should) tune to meet your own use case. We recommend you to read the [security tuning](https://bunkerized-nginx.readthedocs.io/en/latest/security_tuning.html) section of the documentation.

# Going further

- [Official documentation](https://bunkerized-nginx.readthedocs.io/)
- [Full concrete examples](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples)
- [Tutorials in our blog](https://www.bunkerity.com/blog)

# License

This project is licensed under the terms of the [GNU Affero General Public License (AGPL) version 3](https://github.com/bunkerity/bunkerized-nginx/blob/master/LICENSE.md).

# Contributing

If you would like to contribute to the project you can read the [contributing guidelines](https://github.com/bunkerity/bunkerized-nginx/blob/master/CONTRIBUTING.md) to get started.

# Security policy

We take security bugs as serious issues and encourage responsible disclosure, see our [security policy](https://github.com/bunkerity/bunkerized-nginx/blob/master/SECURITY.md) for more information.

# OLD README

# Quickstart guide

## Run HTTP server with default settings

```shell
docker run -p 80:8080 -v /path/to/web/files:/www:ro bunkerity/bunkerized-nginx
```

Web files are stored in the /www directory, the container will serve files from there. Please note that *bunkerized-nginx* doesn't run as root but as an unprivileged user with UID/GID 101 therefore you should set the rights of */path/to/web/files* accordingly.

## In combination with PHP

```shell
docker network create mynet
```

```shell
docker run --network mynet \
           -p 80:8080 \
           -v /path/to/web/files:/www:ro \
           -e REMOTE_PHP=myphp \
           -e REMOTE_PHP_PATH=/app \
           bunkerity/bunkerized-nginx
```

```shell
docker run --network mynet \
           --name myphp \
           -v /path/to/web/files:/app \
           php:fpm
```

The `REMOTE_PHP` environment variable lets you define the address of a remote PHP-FPM instance that will execute the .php files. `REMOTE_PHP_PATH` must be set to the directory where the PHP container will find the files.

## Run HTTPS server with automated Let's Encrypt

```shell
docker run -p 80:8080 \
           -p 443:8443 \
           -v /path/to/web/files:/www:ro \
           -v /where/to/save/certificates:/etc/letsencrypt \
           -e SERVER_NAME=www.yourdomain.com \
           -e AUTO_LETS_ENCRYPT=yes \
           -e REDIRECT_HTTP_TO_HTTPS=yes \
           bunkerity/bunkerized-nginx
```

Certificates are stored in the /etc/letsencrypt directory, you should save it on your local drive. Please note that *bunkerized-nginx* doesn't run as root but as an unprivileged user with UID/GID 101 therefore you should set the rights of */where/to/save/certificates* accordingly.

If you don't want your webserver to listen on HTTP add the environment variable `LISTEN_HTTP` with a *no* value (e.g. HTTPS only). But Let's Encrypt needs the port 80 to be opened so redirecting the port is mandatory.

Here you have three environment variables :
- `SERVER_NAME` : define the FQDN of your webserver, this is mandatory for Let's Encrypt (www.yourdomain.com should point to your IP address)
- `AUTO_LETS_ENCRYPT` : enable automatic Let's Encrypt creation and renewal of certificates
- `REDIRECT_HTTP_TO_HTTPS` : enable HTTP to HTTPS redirection

## As a reverse proxy

```shell
docker run -p 80:8080 \
           -e USE_REVERSE_PROXY=yes \
           -e REVERSE_PROXY_URL=/ \
           -e REVERSE_PROXY_HOST=http://myserver:8080 \
           bunkerity/bunkerized-nginx
```

This is a simple reverse proxy to a unique application. If you have more than one application you can add more REVERSE_PROXY_URL/REVERSE_PROXY_HOST by appending a suffix number like this :

```shell
docker run -p 80:8080 \
           -e USE_REVERSE_PROXY=yes \
           -e REVERSE_PROXY_URL_1=/app1/ \
           -e REVERSE_PROXY_HOST_1=http://myapp1:3000/ \
           -e REVERSE_PROXY_URL_2=/app2/ \
           -e REVERSE_PROXY_HOST_2=http://myapp2:3000/ \
           bunkerity/bunkerized-nginx
```

## Behind a reverse proxy

```shell
docker run -p 80:8080 \
           -v /path/to/web/files:/www \
           -e PROXY_REAL_IP=yes \
           bunkerity/bunkerized-nginx
```

The `PROXY_REAL_IP` environment variable, when set to *yes*, activates the [ngx_http_realip_module](https://nginx.org/en/docs/http/ngx_http_realip_module.html) to get the real client IP from the reverse proxy.

See [this section](https://bunkerized-nginx.readthedocs.io/en/latest/environment_variables.html#reverse-proxy) if you need to tweak some values (trusted ip/network, header, ...).

## Multisite

By default, bunkerized-nginx will only create one server block. When setting the `MULTISITE` environment variable to *yes*, one server block will be created for each host defined in the `SERVER_NAME` environment variable.  
You can set/override values for a specific server by prefixing the environment variable with one of the server name previously defined.

```shell
docker run -p 80:8080 \
           -p 443:8443 \
           -v /where/to/save/certificates:/etc/letsencrypt \
           -e SERVER_NAME=app1.domain.com app2.domain.com \
           -e MULTISITE=yes \
           -e AUTO_LETS_ENCRYPT=yes \
           -e REDIRECT_HTTP_TO_HTTPS=yes \
           -e USE_REVERSE_PROXY=yes \
           -e app1.domain.com_REVERSE_PROXY_URL=/ \
           -e app1.domain.com_REVERSE_PROXY_HOST=http://myapp1:8000 \
           -e app2.domain.com_REVERSE_PROXY_URL=/ \
           -e app2.domain.com_REVERSE_PROXY_HOST=http://myapp2:8000 \
           bunkerity/bunkerized-nginx
```

The `USE_REVERSE_PROXY` is a *global* variable that will be applied to each server block. Whereas the `app1.domain.com_*` and `app2.domain.com_*` will only be applied to the app1.domain.com and app2.domain.com server block respectively.

When serving files, the web root directory should contains subdirectories named as the servers defined in the `SERVER_NAME` environment variable. Here is an example :

```shell

docker run -p 80:8080 \
           -p 443:8443 \
           -v /where/to/save/certificates:/etc/letsencrypt \
           -v /where/are/web/files:/www:ro \
           -e SERVER_NAME=app1.domain.com app2.domain.com \
           -e MULTISITE=yes \
           -e AUTO_LETS_ENCRYPT=yes \
           -e REDIRECT_HTTP_TO_HTTPS=yes \
           -e app1.domain.com_REMOTE_PHP=php1 \
           -e app1.domain.com_REMOTE_PHP_PATH=/app \
           -e app2.domain.com_REMOTE_PHP=php2 \
           -e app2.domain.com_REMOTE_PHP_PATH=/app \
           bunkerity/bunkerized-nginx
```

The */where/are/web/files* directory should have a structure like this :
```shell
/where/are/web/files
├── app1.domain.com
│   └── index.php
│   └── ...
└── app2.domain.com
    └── index.php
    └── ...
```

## Automatic configuration

The downside of using environment variables is that you need to recreate a new container each time you want to add or remove a web service. An alternative is to use the *bunkerized-nginx-autoconf* image which listens for Docker events and "automagically" generates the configuration.

First we need a volume that will store the configurations :

```shell
docker volume create nginx_conf
```

Then we run bunkerized-nginx with the `bunkerized-nginx.AUTOCONF` label, mount the created volume at /etc/nginx and set some default configurations for our services (e.g. : automatic Let's Encrypt and HTTP to HTTPS redirect) : 

```shell
docker network create mynet

docker run -p 80:8080 \
           -p 443:8443 \
           --network mynet \
           -v /where/to/save/certificates:/etc/letsencrypt \
           -v /where/are/web/files:/www:ro \
           -v nginx_conf:/etc/nginx \
           -e SERVER_NAME= \
           -e MULTISITE=yes \
           -e AUTO_LETS_ENCRYPT=yes \
           -e REDIRECT_HTTP_TO_HTTPS=yes \
           -l bunkerized.nginx.AUTOCONF \
           bunkerity/bunkerized-nginx
```

When setting `SERVER_NAME` to nothing bunkerized-nginx won't create any server block (in case we only want automatic configuration). 

Once bunkerized-nginx is created, let's setup the autoconf container :

```shell
docker run -v /var/run/docker.sock:/var/run/docker.sock:ro \
           -v nginx_conf:/etc/nginx \
           bunkerity/bunkerized-nginx-autoconf
```

We can now create a new container and use labels to dynamically configure bunkerized-nginx. Labels for automatic configuration are the same as environment variables but with the "bunkerized-nginx." prefix.

Here is a PHP example :

```shell
docker run --network mynet \
           --name myapp \
           -v /where/are/web/files/app.domain.com:/app \
           -l bunkerized-nginx.SERVER_NAME=app.domain.com \
           -l bunkerized-nginx.REMOTE_PHP=myapp \
           -l bunkerized-nginx.REMOTE_PHP_PATH=/app \
           php:fpm
```

And a reverse proxy example :

```shell
docker run --network mynet \
           --name anotherapp \
           -l bunkerized-nginx.SERVER_NAME=app2.domain.com \
           -l bunkerized-nginx.USE_REVERSE_PROXY=yes \
           -l bunkerized-nginx.REVERSE_PROXY_URL=/ \
           -l bunkerized-nginx.REVERSE_PROXY_HOST=http://anotherapp \
           tutum/hello-world
```

## Swarm mode

Automatic configuration through labels is also supported in swarm mode. The *bunkerized-nginx-autoconf* is used to listen for Swarm events (e.g. service create/rm) and "automagically" edit configurations files and reload nginx.

As a use case we will assume the following :
- Some managers are also workers (they will only run the *autoconf* container for obvious security reasons)
- The bunkerized-nginx service will be deployed on all workers (global mode) so clients can connect to each of them (e.g. load balancing, CDN, edge proxy, ...)
- There is a shared folder mounted on managers and workers (e.g. NFS, GlusterFS, CephFS, ...)

Let's start by creating the network to allow communications between our services :
```shell
docker network create -d overlay mynet
```

We can now create the *autoconf* service that will listen to swarm events :
```shell
docker service create --name autoconf \
                      --network mynet \
                      --mount type=bind,source=/var/run/docker.sock,destination=/var/run/docker.sock,ro \
                      --mount type=bind,source=/shared/confs,destination=/etc/nginx \
                      --mount type=bind,source=/shared/letsencrypt,destination=/etc/letsencrypt \
                      --mount type=bind,source=/shared/acme-challenge,destination=/acme-challenge \
                      -e SWARM_MODE=yes \
                      -e API_URI=/ChangeMeToSomethingHardToGuess \
                      --replicas 1 \
                      --constraint node.role==manager \
                      bunkerity/bunkerized-nginx-autoconf
```

**You need to change `API_URI` to something hard to guess since there is no other security mechanism to protect the API at the moment.**

When *autoconf* is created, it's time for the *bunkerized-nginx* service to be up :

```shell
docker service create --name nginx \
                      --network mynet \
                      -p published=80,target=8080,mode=host \
                      -p published=443,target=8443,mode=host \
                      --mount type=bind,source=/shared/confs,destination=/etc/nginx \
                      --mount type=bind,source=/shared/letsencrypt,destination=/etc/letsencrypt,ro \
                      --mount type=bind,source=/shared/acme-challenge,destination=/acme-challenge,ro \
                      --mount type=bind,source=/shared/www,destination=/www,ro \
                      -e SWARM_MODE=yes \
                      -e USE_API=yes \
                      -e API_URI=/ChangeMeToSomethingHardToGuess \
                      -e MULTISITE=yes \
                      -e SERVER_NAME= \
                      -e AUTO_LETS_ENCRYPT=yes \
                      -e REDIRECT_HTTP_TO_HTTPS=yes \
                      -l bunkerized-nginx.AUTOCONF \
                      --mode global \
                      --constraint node.role==worker \
                      bunkerity/bunkerized-nginx
```

The `API_URI` value must be the same as the one specified for the *autoconf* service.

We can now create a new service and use labels to dynamically configure bunkerized-nginx. Labels for automatic configuration are the same as environment variables but with the "bunkerized-nginx." prefix.

Here is a PHP example :

```shell
docker service create --name myapp \
                      --network mynet \
                      --mount type=bind,source=/shared/www/app.domain.com,destination=/app \
                      -l bunkerized-nginx.SERVER_NAME=app.domain.com \
                      -l bunkerized-nginx.REMOTE_PHP=myapp \
                      -l bunkerized-nginx.REMOTE_PHP_PATH=/app \
                      --constraint node.role==worker \
                      php:fpm
```

And a reverse proxy example :

```shell
docker service create --name anotherapp \
                      --network mynet \
                      -l bunkerized-nginx.SERVER_NAME=app2.domain.com \
                      -l bunkerized-nginx.USE_REVERSE_PROXY=yes \
                      -l bunkerized-nginx.REVERSE_PROXY_URL=/ \
                      -l bunkerized-nginx.REVERSE_PROXY_HOST=http://anotherapp \
                      --constraint node.role==worker \
                      tutum/hello-world
```

## Web UI

A dedicated image, *bunkerized-nginx-ui*, lets you manage bunkerized-nginx instances and services configurations through a web user interface. This feature is still in beta, feel free to open a new issue if you find a bug and/or you have an idea to improve it. 

First we need a volume that will store the configurations and a network because bunkerized-nginx will be used as a reverse proxy for the web UI :

```shell
docker volume create nginx_conf
docker network create mynet
```

Let's create the bunkerized-nginx-ui container that will host the web UI behind bunkerized-nginx :

```shell
docker run --network mynet \
           --name myui \
           -v /var/run/docker.sock:/var/run/docker.sock:ro \
           -v nginx_conf:/etc/nginx \
           -e ABSOLUTE_URI=https://admin.domain.com/webui/ \
           bunkerity/bunkerized-nginx-ui
```

You will need to edit the `ABSOLUTE_URI` environment variable to reflect your actual URI of the web UI.

We can now setup the bunkerized-nginx instance with the `bunkerized-nginx.UI` label and a reverse proxy configuration for our web UI :

```shell
docker network create mynet

docker run -p 80:8080 \
           -p 443:8443 \
           --network mynet \
           -v nginx_conf:/etc/nginx \
           -v /where/are/web/files:/www:ro \
           -v /where/to/save/certificates:/etc/letsencrypt \
           -e SERVER_NAME=admin.domain.com \
           -e MULTISITE=yes \
           -e AUTO_LETS_ENCRYPT=yes \
           -e REDIRECT_HTTP_TO_HTTPS=yes \
           -e DISABLE_DEFAULT_SERVER=yes \
           -e admin.domain.com_USE_MODSECURITY=no \
           -e admin.domain.com_SERVE_FILES=no \
           -e admin.domain.com_USE_AUTH_BASIC=yes \
           -e admin.domain.com_AUTH_BASIC_USER=admin \
           -e admin.domain.com_AUTH_BASIC_PASSWORD=password \
           -e admin.domain.com_USE_REVERSE_PROXY=yes \
           -e admin.domain.com_REVERSE_PROXY_URL=/webui/ \
           -e admin.domain.com_REVERSE_PROXY_HOST=http://myui:5000/ \
           -l bunkerized-nginx.UI \
           bunkerity/bunkerized-nginx
```

The `AUTH_BASIC` environment variables let you define a login/password that must be provided before accessing to the web UI. At the moment, there is no authentication mechanism integrated into bunkerized-nginx-ui so **using auth basic with a strong password coupled with a "hard to guess" URI is strongly recommended**.

Web UI should now be accessible from https://admin.domain.com/webui/.

