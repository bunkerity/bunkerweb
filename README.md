<p align="center">
	<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/logo.png?raw=true" width="425" />
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
		<span> | </span>
		<a href="https://github.com/bunkerity/bunkerized-nginx/tree/master/examples">Examples</a>
		<span> | </span>
		<a href="https://www.bunkerity.com/category/bunkerized-nginx/">Blog posts</a>
		<span> | </span>
		<a href="https://coso.me/bunkerity-chat">Community chat</a>
		<span> | </span>
		<a href="https://coso.me/bunkerity">Follow us</a>
	</strong>
</p>

nginx Docker image secure by default.  

Avoid the hassle of following security best practices "by hand" each time you need a web server or reverse proxy. Bunkerized-nginx provides generic security configs, settings and tools so you don't need to do it yourself.

Non-exhaustive list of features :
- HTTPS support with transparent Let's Encrypt automation
- State-of-the-art web security : HTTP security headers, prevent leaks, TLS hardening, ...
- Integrated ModSecurity WAF with the OWASP Core Rule Set
- Automatic ban of strange behaviors
- Antibot challenge through cookie, javascript, captcha or recaptcha v3
- Block TOR, proxies, bad user-agents, countries, ...
- Block known bad IP with DNSBL and CrowdSec
- Prevent bruteforce attacks with rate limiting
- Plugins system for external security checks (e.g. : ClamAV)
- Easy to configure with environment variables or web UI
- Automatic configuration with container labels
- Docker Swarm support

Fooling automated tools/scanners :

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/demo.gif?raw=true" />

You can find a live demo at https://demo-nginx.bunkerity.com, feel free to do some security tests.

# Table of contents
<details>
	<summary>Click to show</summary>

- [Table of contents](#table-of-contents)
- [Quickstart guide](#quickstart-guide)
  * [Run HTTP server with default settings](#run-http-server-with-default-settings)
  * [In combination with PHP](#in-combination-with-php)
  * [Run HTTPS server with automated Let's Encrypt](#run-https-server-with-automated-lets-encrypt)
  * [As a reverse proxy](#as-a-reverse-proxy)
  * [Behind a reverse proxy](#behind-a-reverse-proxy)
  * [Multisite](#multisite)
  * [Automatic configuration](#automatic-configuration)
  * [Swarm mode](#swarm-mode)
  * [Web UI](#web-ui)
- [Security tuning](#security-tuning)
- [Going further](#going-further)
- [License](#license)
- [Contributing](#contributing)
</details>

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

# Security tuning

bunkerized-nginx comes with a set of predefined security settings that you can (and you should) tune to meet your own use case. We recommend you to read the [security tuning](https://bunkerized-nginx.readthedocs.io/en/latest/security_tuning.html) section of the documentation.

# Going further

- [Official documentation](https://bunkerized-nginx.readthedocs.io/)
- [Full concrete examples](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples)
- [Tutorials in our blog](https://www.bunkerity.com/blog)

# License

This project is licensed under the terms of the [GNU Affero General Public License (AGPL) version 3](https://github.com/bunkerity/bunkerized-nginx/LICENSE.md).

# Contributing

If you would like to contribute to the project you can read the [contributing guidelines](https://github.com/bunkerity/bunkerized-nginx/CONTRIBUTING.md) to get started.
