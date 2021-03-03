# bunkerized-nginx

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/logo.png?raw=true" width="425" />

<img src="https://img.shields.io/badge/bunkerized--nginx-1.2.2-blue" /> <img src="https://img.shields.io/badge/nginx-1.18.0-blue" /> <img src="https://img.shields.io/github/last-commit/bunkerity/bunkerized-nginx" /> <a href="https://matrix.to/#/#bunkerized-nginx:matrix.org"><img src="https://img.shields.io/badge/matrix%20chat-%23bunkerized--nginx%3Amatrix.org-blue" /></a> <img src="https://img.shields.io/github/workflow/status/bunkerity/bunkerized-nginx/Automatic%20test?label=automatic%20test" /> <img src="https://img.shields.io/docker/cloud/build/bunkerity/bunkerized-nginx" />

nginx Docker image secure by default.  

Avoid the hassle of following security best practices each time you need a web server or reverse proxy. Bunkerized-nginx provides generic security configs, settings and tools so you don't need to do it yourself.

Non-exhaustive list of features :
- HTTPS support with transparent Let's Encrypt automation
- State-of-the-art web security : HTTP security headers, prevent leaks, TLS hardening, ...
- Integrated ModSecurity WAF with the OWASP Core Rule Set
- Automatic ban of strange behaviors with fail2ban
- Antibot challenge through cookie, javascript, captcha or recaptcha v3
- Block TOR, proxies, bad user-agents, countries, ...
- Block known bad IP with DNSBL and CrowdSec
- Prevent bruteforce attacks with rate limiting
- Detect bad files with ClamAV
- Easy to configure with environment variables or web UI
- Automatic configuration with container labels

Fooling automated tools/scanners :

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/demo.gif?raw=true" />

# Table of contents
- [bunkerized-nginx](#bunkerized-nginx)
- [Table of contents](#table-of-contents)
- [Live demo](#live-demo)
- [Quickstart guide](#quickstart-guide)
  * [Run HTTP server with default settings](#run-http-server-with-default-settings)
  * [In combination with PHP](#in-combination-with-php)
  * [Run HTTPS server with automated Let's Encrypt](#run-https-server-with-automated-lets-encrypt)
  * [As a reverse proxy](#as-a-reverse-proxy)
  * [Behind a reverse proxy](#behind-a-reverse-proxy)
  * [Multisite](#multisite)
  * [Automatic configuration](#automatic-configuration)
  * [Web UI](#web-ui)
  * [Antibot challenge](#antibot-challenge)
- [Tutorials and examples](#tutorials-and-examples)
- [List of environment variables](#list-of-environment-variables)
  * [nginx](#nginx)
    + [Misc](#misc)
    + [Information leak](#information-leak)
    + [Custom error pages](#custom-error-pages)
    + [HTTP basic authentication](#http-basic-authentication)
    + [Reverse proxy](#reverse-proxy)
    + [Compression](#compression)
    + [Cache](#cache)
  * [HTTPS](#https)
    + [Let's Encrypt](#lets-encrypt)
    + [HTTP](#http)
    + [Custom certificate](#custom-certificate)
    + [Self-signed certificate](#self-signed-certificate)
    + [Misc](#misc-1)
  * [ModSecurity](#modsecurity)
  * [Security headers](#security-headers)
  * [Blocking](#blocking)
    + [Antibot](#antibot)
    + [External blacklists](#external-blacklists)
    + [DNSBL](#dnsbl)
    + [CrowdSec](#crowdsec)
    + [Custom whitelisting](#custom-whitelisting)
    + [Custom blacklisting](#custom-blacklisting)
    + [Requests limiting](#requests-limiting)
    + [Countries](#countries)
  * [PHP](#php)
  * [Fail2ban](#fail2ban)
  * [ClamAV](#clamav)
  * [Misc](#misc-2)
- [Include custom configurations](#include-custom-configurations)
- [Cache data](#cache-data)
- [Create your own image](#create-your-own-image)

# Live demo
You can find a live demo at https://demo-nginx.bunkerity.com.

# Quickstart guide

## Run HTTP server with default settings

```shell
docker run -p 80:8080 -v /path/to/web/files:/www:ro bunkerity/bunkerized-nginx
```

Web files are stored in the /www directory, the container will serve files from there.

## In combination with PHP

```shell
docker network create mynet
docker run --network mynet \
           -p 80:8080 \
           -v /path/to/web/files:/www:ro \
           -e REMOTE_PHP=myphp \
           -e REMOTE_PHP_PATH=/app \
           bunkerity/bunkerized-nginx
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

Certificates are stored in the /etc/letsencrypt directory, you should save it on your local drive.  
If you don't want your webserver to listen on HTTP add the environment variable `LISTEN_HTTP` with a *no* value. But Let's Encrypt needs the port 80 to be opened so redirecting the port is mandatory.

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

See [this section](#reverse-proxy) if you need to tweak some values (trusted ip/network, header, ...).

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
│   └── index.php
│   └── ...
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
           -l bunkerized-nginx.REVERSE_PROXY_HOST=http://anotherapp
           tutum/hello-world
```

## Web UI

**This feature exposes, for now, a security risk because you need to mount the docker socket inside a container exposing a web application. You can test it but you should not use it in servers facing the internet.**  

A dedicated image, *bunkerized-nginx-ui*, lets you manage bunkerized-nginx instances and services configurations through a web user interface. This feature is still in beta, feel free to open a new issue if you find a bug and/or you have an idea to improve it. 

First we need a volume that will store the configurations :

```shell
docker volume create nginx_conf
```

Then, we can create the bunkerized-nginx instance with the `bunkerized-nginx.UI` label and a reverse proxy configuration for our web UI :

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

The `AUTH_BASIC` environment variables let you define a login/password that must be provided before accessing to the web UI. At the moment, there is no authentication mechanism integrated into bunkerized-nginx-ui.

We can now create the bunkerized-nginx-ui container that will host the web UI behind bunkerized-nginx :

```shell
docker run --network mynet \
           -v /var/run/docker.sock:/var/run/docker.sock:ro \
           -v nginx_conf:/etc/nginx \
           -e ABSOLUTE_URI=https://admin.domain.com/webui/ \
           bunkerity/bunkerized-nginx-ui
```

After that, the web UI should be accessible from https://admin.domain.com/webui/.

## Antibot challenge

```shell
docker run -p 80:8080 -v /path/to/web/files:/www -e USE_ANTIBOT=captcha bunkerity/bunkerized-nginx
```

When `USE_ANTIBOT` is set to *captcha*, every users visiting your website must complete a captcha before accessing the pages. Others challenges are also available : *cookie*, *javascript* or *recaptcha* (more info [here](#antibot)).

# Tutorials and examples

You will find some docker-compose.yml examples in the [examples directory](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples).  

# List of environment variables

## nginx

### Misc

`MULTISITE`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*  
When set to *no*, only one server block will be generated. Otherwise one server per host defined in the `SERVER_NAME` environment variable will be generated.  
Any environment variable tagged as *multisite* context can be used for a specific server block with the following format : *host_VARIABLE=value*. If the variable is used without the host prefix it will be applied to all the server blocks (but still can be overriden).

`SERVER_NAME`  
Values : *&lt;first name&gt; &lt;second name&gt; ...*  
Default value : *www.bunkerity.com*  
Context : *global*  
Sets the host names of the webserver separated with spaces. This must match the Host header sent by clients.  
Useful when used with `MULTISITE=yes` and/or `AUTO_LETSENCRYPT=yes` and/or `DISABLE_DEFAULT_SERVER=yes`.

`MAX_CLIENT_SIZE`  
Values : *0* | *Xm*  
Default value : *10m*  
Context : *global*, *multisite*  
Sets the maximum body size before nginx returns a 413 error code.  
Setting to 0 means "infinite" body size.

`ALLOWED_METHODS`  
Values : *allowed HTTP methods separated with | char*  
Default value : *GET|POST|HEAD*  
Context : *global*, *multisite*  
Only the HTTP methods listed here will be accepted by nginx. If not listed, nginx will close the connection.

`DISABLE_DEFAULT_SERVER`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
If set to yes, nginx will only respond to HTTP request when the Host header match a FQDN specified in the `SERVER_NAME` environment variable.  
For example, it will close the connection if a bot access the site with direct ip.

`SERVE_FILES`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, nginx will serve files from /www directory within the container.  
A use case to not serving files is when you setup bunkerized-nginx as a reverse proxy.

`DNS_RESOLVERS`  
Values : *\<two IP addresses separated with a space\>*  
Default value : *127.0.0.11*  
Context : *global*  
The IP addresses of the DNS resolvers to use when performing DNS lookups.

`ROOT_FOLDER`  
Values : *\<any valid path to web files\>  
Default value : */www*  
Context : *global*  
The default folder where nginx will search for web files. Don't change it unless you want to make your own image.

`LOG_FORMAT`  
Values : *\<any values accepted by the log_format directive\>*  
Default value : *$host $remote_addr - $remote_user \[$time_local\] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"*  
Context : *global*  
The log format used by nginx to generate logs. More info [here](http://nginx.org/en/docs/http/ngx_http_log_module.html#log_format).

`HTTP_PORT`  
Values : *\<any valid port greater than 1024\>*  
Default value : *8080*  
Context : *global*  
The HTTP port number used by nginx and certbot inside the container.

`HTTPS_PORT`  
Values : *\<any valid port greater than 1024\>*  
Default value : *8443*  
Context : *global*  
The HTTPS port number used by nginx inside the container.

### Information leak

`SERVER_TOKENS`  
Values : *on* | *off*  
Default value : *off*  
Context : *global*  
If set to on, nginx will display server version in Server header and default error pages.

`REMOVE_HEADERS`  
Values : \<*list of headers separated with space*\>  
Default value : *Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version*  
Context : *global*, *multisite*  
List of header to remove when sending responses to clients.

### Custom error pages

`ERROR_XXX`  
Values : *\<relative path to the error page\>*  
Default value :  
Context : *global*, *multisite*  
Use this kind of environment variable to define custom error page depending on the HTTP error code. Replace XXX with HTTP code.  
For example : `ERROR_404=/404.html` means the /404.html page will be displayed when 404 code is generated. The path is relative to the root web folder.

### HTTP basic authentication

`USE_AUTH_BASIC`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
If set to yes, enables HTTP basic authentication at the location `AUTH_BASIC_LOCATION` with user `AUTH_BASIC_USER` and password `AUTH_BASIC_PASSWORD`.

`AUTH_BASIC_LOCATION`  
Values : *sitewide* | */somedir* | *\<any valid location\>*  
Default value : *sitewide*  
Context : *global*, *multisite*  
The location to restrict when `USE_AUTH_BASIC` is set to *yes*. If the special value *sitewide* is used then auth basic will be set at server level outside any location context.

`AUTH_BASIC_USER`  
Values : *\<any valid username\>*  
Default value : *changeme*  
Context : *global*, *multisite*  
The username allowed to access `AUTH_BASIC_LOCATION` when `USE_AUTH_BASIC` is set to yes.

`AUTH_BASIC_PASSWORD`  
Values : *\<any valid password\>*  
Default value : *changeme*  
Context : *global*, *multisite*  
The password of `AUTH_BASIC_USER` when `USE_AUTH_BASIC` is set to yes.

`AUTH_BASIC_TEXT`  
Values : *\<any valid text\>*  
Default value : *Restricted area*  
Context : *global*, *multisite*  
The text displayed inside the login prompt when `USE_AUTH_BASIC` is set to yes.

### Reverse proxy

`USE_REVERSE_PROXY`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
Set this environment variable to *yes* if you want to use bunkerized-nginx as a reverse proxy.

`REVERSE_PROXY_URL`  
Values : \<*any valid location path*\>  
Default value :  
Context : *global*, *multisite*  
Only valid when `USE_REVERSE_PROXY` is set to *yes*. Let's you define the location path to match when acting as a reverse proxy.  
You can set multiple url/host by adding a suffix number to the variable name like this : `REVERSE_PROXY_URL_1`, `REVERSE_PROXY_URL_2`, `REVERSE_PROXY_URL_3`, ...

`REVERSE_PROXY_HOST`  
Values : \<*any valid proxy_pass value*\>  
Default value :  
Context : *global*, *multisite*  
Only valid when `USE_REVERSE_PROXY` is set to *yes*. Let's you define the proxy_pass destination to use when acting as a reverse proxy.  
You can set multiple url/host by adding a suffix number to the variable name like this : `REVERSE_PROXY_HOST_1`, `REVERSE_PROXY_HOST_2`, `REVERSE_PROXY_HOST_3`, ...

`REVERSE_PROXY_WS`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
Only valid when `USE_REVERSE_PROXY` is set to *yes*. Set it to *yes* when the corresponding `REVERSE_PROXY_HOST` is a WebSocket server.  
You can set multiple url/host by adding a suffix number to the variable name like this : `REVERSE_PROXY_WS_1`, `REVERSE_PROXY_WS_2`, `REVERSE_PROXY_WS_3`, ...

`PROXY_REAL_IP`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
Set this environment variable to *yes* if you're using bunkerized-nginx behind a reverse proxy. This means you will see the real client address instead of the proxy one inside your logs. Modsecurity, fail2ban and others security tools will also then work correctly.

`PROXY_REAL_IP_FROM`  
Values : *\<list of trusted IP addresses and/or networks separated with spaces\>*  
Default value : *192.168.0.0/16 172.16.0.0/12 10.0.0.0/8*  
Context : *global*, *multisite*  
When `PROXY_REAL_IP` is set to *yes*, lets you define the trusted IPs/networks allowed to send the correct client address.

`PROXY_REAL_IP_HEADER`  
Values : *X-Forwarded-For* | *X-Real-IP* | *custom header*  
Default value : *X-Forwarded-For*  
Context : *global*, *multisite*  
When `PROXY_REAL_IP` is set to *yes*, lets you define the header that contains the real client IP address.

`PROXY_REAL_IP_RECURSIVE`  
Values : *on* | *off*  
Default value : *on*  
Context : *global*, *multisite*  
When `PROXY_REAL_IP` is set to *yes*, setting this to *on* avoid spoofing attacks using the header defined in `PROXY_REAL_IP_HEADER`.

### Compression

`USE_GZIP`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
When set to *yes*, nginx will use the gzip algorithm to compress responses sent to clients.

`GZIP_COMP_LEVEL`  
Values : \<*any integer between 1 and 9*\>  
Default value : *5*  
Context : *global*, *multisite*  
The gzip compression level to use when `USE_GZIP` is set to *yes*.

`GZIP_MIN_LENGTH`  
Values : \<*any positive integer*\>  
Default value : *1000*  
Context : *global*, *multisite*  
The minimum size (in bytes) of a response required to compress when `USE_GZIP` is set to *yes*.

`GZIP_TYPES`  
Values : \<*list of mime types separated with space*\>  
Default value : *application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml*  
Context : *global*, *multisite*  
List of response MIME type required to compress when `USE_GZIP` is set to *yes*.

`USE_BROTLI`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
When set to *yes*, nginx will use the brotli algorithm to compress responses sent to clients.

`BROTLI_COMP_LEVEL`  
Values : \<*any integer between 1 and 9*\>  
Default value : *5*  
Context : *global*, *multisite*  
The brotli compression level to use when `USE_BROTLI` is set to *yes*.

`BROTLI_MIN_LENGTH`  
Values : \<*any positive integer*\>  
Default value : *1000*  
Context : *global*, *multisite*  
The minimum size (in bytes) of a response required to compress when `USE_BROTLI` is set to *yes*.

`BROTLI_TYPES`  
Values : \<*list of mime types separated with space*\>  
Default value : *application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml*  
Context : *global*, *multisite*  
List of response MIME type required to compress when `USE_BROTLI` is set to *yes*.

### Cache

`USE_CLIENT_CACHE`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
When set to *yes*, clients will be told to cache some files locally.

`CLIENT_CACHE_EXTENSIONS`  
Values : \<*list of extensions separated with |*\>  
Default value : *jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2*  
Context : *global*, *multisite*  
List of file extensions that clients should cache when `USE_CLIENT_CACHE` is set to *yes*.

`CLIENT_CACHE_CONTROL`  
Values : \<*Cache-Control header value*\>  
Default value : *public, max-age=15552000*  
Context : *global*, *multisite*  
Content of the [Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control) header to send when `USE_CLIENT_CACHE` is set to *yes*.

`CLIENT_CACHE_ETAG`  
Values : *on* | *off*  
Default value : *on*  
Context : *global*, *multisite*  
Whether or not nginx will send the [ETag](https://en.wikipedia.org/wiki/HTTP_ETag) header when `USE_CLIENT_CACHE` is set to *yes*.

`USE_OPEN_FILE_CACHE`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
When set to *yes*, nginx will cache open fd, existence of directories, ... See [open_file_cache](http://nginx.org/en/docs/http/ngx_http_core_module.html#open_file_cache).

`OPEN_FILE_CACHE`  
Values : \<*any valid open_file_cache parameters*\>  
Default value : *max=1000 inactive=20s*  
Context : *global*, *multisite*  
Parameters to use with open_file_cache when `USE_OPEN_FILE_CACHE` is set to *yes*.

`OPEN_FILE_CACHE_ERRORS`  
Values : *on* | *off*  
Default value : *on*  
Context : *global*, *multisite*  
Whether or not nginx should cache file lookup errors when `USE_OPEN_FILE_CACHE` is set to *yes*.

`OPEN_FILE_CACHE_MIN_USES`  
Values : \<*any valid integer *\>  
Default value : *2*  
Context : *global*, *multisite*  
The minimum number of file accesses required to cache the fd when `USE_OPEN_FILE_CACHE` is set to *yes*.

`OPEN_FILE_CACHE_VALID`  
Values : \<*any time value like Xs, Xm, Xh, ...*\>  
Default value : *30s*  
Context : *global*, *multisite*  
The time after which cached elements should be validated when `USE_OPEN_FILE_CACHE` is set to *yes*.

`USE_PROXY_CACHE`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
When set to *yes*, nginx will cache responses from proxied applications. See [proxy_cache](http://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_cache).

`PROXY_CACHE_PATH_ZONE_SIZE`  
Values : \<*any valid size like Xk, Xm, Xg, ...*\>  
Default value : *10m*  
Context : *global*, *multisite*  
Maximum size of cached metadata when `USE_PROXY_CACHE` is set to *yes*.
 
`PROXY_CACHE_PATH_PARAMS`  
Values : \<*any valid parameters to proxy_cache_path directive*\>  
Default value : *max_size=100m*  
Context : *global*, *multisite*  
Parameters to use for [proxy_cache_path](http://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_cache_path) directive when `USE_PROXY_CACHE` is set to *yes*.

`PROXY_CACHE_METHODS`  
Values : \<*list of HTTP methods separated with space*\>  
Default value : *GET HEAD*  
Context : *global*, *multisite*  
The HTTP methods that should trigger a cache operation when `USE_PROXY_CACHE` is set to *yes*.
 
`PROXY_CACHE_MIN_USES`  
Values : \<*any positive integer*\>  
Default value : *2*  
Context : *global*, *multisite*  
The minimum number of requests before the response is cached when `USE_PROXY_CACHE` is set to *yes*.

`PROXY_CACHE_KEY`  
Values : \<*list of variables*\>  
Default value : *$scheme$host$request_uri*  
Context : *global*, *multisite*  
The key used to uniquely identify a cached response when `USE_PROXY_CACHE` is set to *yes*.

`PROXY_CACHE_VALID`  
Values : \<*status=time list separated with space*\>  
Default value : *200=10m 301=10m 302=1h*  
Context : *global*, *multisite*  
Define the caching time depending on the HTTP status code (list of status=time separated with space) when `USE_PROXY_CACHE` is set to *yes*.

`PROXY_NO_CACHE`  
Values : \<*list of variables*\>  
Default value : *$http_authorization*  
Context : *global*, *multisite*  
Conditions that must be met to disable caching of the response when `USE_PROXY_CACHE` is set to *yes*.

`PROXY_CACHE_BYPASS`  
Values : \<*list of variables*\>
Default value : *$http_authorization*  
Context : *global*, *multisite* 
Conditions that must be met to bypass the cache when `USE_PROXY_CACHE` is set to *yes*.

## HTTPS

### Let's Encrypt

`AUTO_LETS_ENCRYPT`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
If set to yes, automatic certificate generation and renewal will be setup through Let's Encrypt. This will enable HTTPS on your website for free.  
You will need to redirect the 80 port to 8080 port inside container and also set the `SERVER_NAME` environment variable.

`AUTO_LETS_ENCRYPT_CRON`  
Values : *\<cron expression\>*   
Default value : 0 2 * * *  
Context : *global*  
Cron expression of how often lets encrypt is asking for being renewed.

`EMAIL_LETS_ENCRYPT`  
Values : *contact@yourdomain.com*  
Default value : *contact@yourdomain.com*  
Context : *global*, *multisite*  
Define the contact email address declare in the certificate.

### HTTP

`LISTEN_HTTP`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to no, nginx will not in listen on HTTP (port 80).  
Useful if you only want HTTPS access to your website.

`REDIRECT_HTTP_TO_HTTPS`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
If set to yes, nginx will redirect all HTTP requests to HTTPS.  

### Custom certificate

`USE_CUSTOM_HTTPS`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*  
If set to yes, HTTPS will be enabled with certificate/key of your choice.  

`CUSTOM_HTTPS_CERT`  
Values : *\<any valid path inside the container\>*  
Default value :  
Context : *global*  
Full path of the certificate file to use when `USE_CUSTOM_HTTPS` is set to yes.  

`CUSTOM_HTTPS_KEY`  
Values : *\<any valid path inside the container\>*  
Default value :  
Context : *global*  
Full path of the key file to use when `USE_CUSTOM_HTTPS` is set to yes.  

### Self-signed certificate

`GENERATE_SELF_SIGNED_SSL`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*  
If set to yes, HTTPS will be enabled with a container generated self-signed certificate.

`SELF_SIGNED_SSL_EXPIRY`  
Values : *integer*  
Default value : *365* (1 year)  
Context : *global*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the expiry date for the self generated certificate.

`SELF_SIGNED_SSL_COUNTRY`  
Values : *text*  
Default value : *Switzerland*  
Context : *global*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the country for the self generated certificate.

`SELF_SIGNED_SSL_STATE`  
Values : *text*  
Default value : *Switzerland*  
Context : *global*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the state for the self generated certificate.

`SELF_SIGNED_SSL_CITY`  
Values : *text*  
Default value : *Bern*  
Context : *global*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the city for the self generated certificate.

`SELF_SIGNED_SSL_ORG`  
Values : *text*  
Default value : *AcmeInc*  
Context : *global*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the organisation name for the self generated certificate.

`SELF_SIGNED_SSL_OU`  
Values : *text*  
Default value : *IT*  
Context : *global*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the organisitional unit for the self generated certificate.

`SELF_SIGNED_SSL_CN`  
Values : *text*  
Default value : *bunkerity-nginx*  
Context : *global*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the CN server name for the self generated certificate.

### Misc

`HTTP2`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, nginx will use HTTP2 protocol when HTTPS is enabled.  

`HTTPS_PROTOCOLS`  
Values : *TLSv1.2* | *TLSv1.3* | *TLSv1.2 TLSv1.3*  
Default value : *TLSv1.2 TLSv1.3*  
Context : *global*, *multisite*  
The supported version of TLS. We recommend the default value *TLSv1.2 TLSv1.3* for compatibility reasons.

## ModSecurity

`USE_MODSECURITY`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, the ModSecurity WAF will be enabled.  
You can include custom rules by adding .conf files into the /modsec-confs/ directory inside the container (i.e : through a volume).  

`USE_MODSECURITY_CRS`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, the [OWASP ModSecurity Core Rule Set](https://coreruleset.org/) will be used. It provides generic rules to detect common web attacks.  
You can customize the CRS (i.e. : add WordPress exclusions) by adding custom .conf files into the /modsec-crs-confs/ directory inside the container (i.e : through a volume). Files inside this directory are included before the CRS rules. If you need to tweak (i.e. : SecRuleUpdateTargetById) put .conf files inside the /modsec-confs/ which is included after the CRS rules.

## Security headers

`X_FRAME_OPTIONS`  
Values : *DENY* | *SAMEORIGIN* | *ALLOW-FROM https://www.website.net* | *ALLOWALL*  
Default value : *DENY*  
Context : *global*, *multisite*  
Policy to be used when the site is displayed through iframe. Can be used to mitigate clickjacking attacks. 
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options).

`X_XSS_PROTECTION`  
Values : *0* | *1* | *1; mode=block*  
Default value : *1; mode=block*  
Context : *global*, *multisite*  
Policy to be used when XSS is detected by the browser. Only works with Internet Explorer.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-XSS-Protection).  

`X_CONTENT_TYPE_OPTIONS`  
Values : *nosniff*  
Default value : *nosniff*  
Context : *global*, *multisite*  
Tells the browser to be strict about MIME type.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options).

`REFERRER_POLICY`  
Values : *no-referrer* | *no-referrer-when-downgrade* | *origin* | *origin-when-cross-origin* | *same-origin* | *strict-origin* | *strict-origin-when-cross-origin* | *unsafe-url*  
Default value : *no-referrer*  
Context : *global*, *multisite*  
Policy to be used for the Referer header.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy).

`FEATURE_POLICY`  
Values : *&lt;directive&gt; &lt;allow list&gt;*  
Default value : *accelerometer 'none'; ambient-light-sensor 'none'; autoplay 'none'; camera 'none'; display-capture 'none'; document-domain 'none'; encrypted-media 'none'; fullscreen 'none'; geolocation 'none'; gyroscope 'none'; magnetometer 'none'; microphone 'none'; midi 'none'; payment 'none'; picture-in-picture 'none'; speaker 'none'; sync-xhr 'none'; usb 'none'; vibrate 'none'; vr 'none'*  
Context : *global*, *multisite*  
Tells the browser which features can be used on the website.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Feature-Policy).

`PERMISSIONS_POLICY`  
Values : *feature=(allow list)*  
Default value : accelerometer=(), ambient-light-sensor=(), autoplay=(), camera=(), display-capture=(), document-domain=(), encrypted-media=(), fullscreen=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), midi=(), payment=(), picture-in-picture=(), speaker=(), sync-xhr=(), usb=(), vibrate=(), vr=()  
Context : *global*, *multisite*  
Tells the browser which features can be used on the website.  
More info [here](https://www.w3.org/TR/permissions-policy-1/).

`COOKIE_FLAGS`  
Values : *\* HttpOnly* | *MyCookie secure SameSite=Lax* | *...*  
Default value : *\* HttpOnly SameSite=Lax*  
Context : *global*, *multisite*  
Adds some security to the cookies set by the server.  
Accepted value can be found [here](https://github.com/AirisX/nginx_cookie_flag_module).

`COOKIE_AUTO_SECURE_FLAG`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
When set to *yes*, the *secure* will be automatically added to cookies when using HTTPS.

`STRICT_TRANSPORT_SECURITY`  
Values : *max-age=expireTime [; includeSubDomains] [; preload]*  
Default value : *max-age=31536000*  
Context : *global*, *multisite*  
Tells the browser to use exclusively HTTPS instead of HTTP when communicating with the server.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security).

`CONTENT_SECURITY_POLICY`  
Values : *\<directive 1\>; \<directive 2\>; ...*  
Default value : *object-src 'none'; frame-ancestors 'self'; form-action 'self'; block-all-mixed-content; sandbox allow-forms allow-same-origin allow-scripts allow-popups; base-uri 'self';*  
Context : *global*, *multisite*  
Policy to be used when loading resources (scripts, forms, frames, ...).  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy).

## Blocking

### Antibot

`USE_ANTIBOT`  
Values : *no* | *cookie* | *javascript* | *captcha* | *recaptcha*  
Default value : *no*  
Context : *global*, *multisite*  
If set to another allowed value than *no*, users must complete a "challenge" before accessing the pages on your website :
- *cookie* : asks the users to set a cookie
- *javascript* : users must execute a javascript code
- *captcha* : a text captcha must be resolved by the users
- *recaptcha* : use [Google reCAPTCHA v3](https://developers.google.com/recaptcha/intro) score to allow/deny users 

`ANTIBOT_URI`  
Values : *\<any valid uri\>*  
Default value : */challenge*  
Context : *global*, *multisite*  
A valid and unused URI to redirect users when `USE_ANTIBOT` is used. Be sure that it doesn't exist on your website.

`ANTIBOT_SESSION_SECRET`  
Values : *random* | *\<32 chars of your choice\>*  
Default value : *random*  
Context : *global*, *multisite*  
A secret used to generate sessions when `USE_ANTIBOT` is set. Using the special *random* value will generate a random one. Be sure to use the same value when you are in a multi-server environment (so sessions are valid in all the servers).

`ANTIBOT_RECAPTCHA_SCORE`  
Values : *\<0.0 to 1.0\>*  
Default value : *0.7*  
Context : *global*, *multisite*  
The minimum score required when `USE_ANTIBOT` is set to *recaptcha*.

`ANTIBOT_RECAPTCHA_SITEKEY`  
Values : *\<public key given by Google\>*  
Default value :  
Context : *global*  
The sitekey given by Google when `USE_ANTIBOT` is set to *recaptcha*.

`ANTIBOT_RECAPTCHA_SECRET`  
Values : *\<private key given by Google\>*  
Default value :  
Context : *global*  
The secret given by Google when `USE_ANTIBOT` is set to *recaptcha*.

### External blacklists

`BLOCK_USER_AGENT`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, block clients with "bad" user agent.  
Blacklist can be found [here](https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list) and [here](https://raw.githubusercontent.com/JayBizzle/Crawler-Detect/master/raw/Crawlers.txt).

`BLOCK_USER_AGENT_CRON`  
Values : *\<cron expression\>*   
Default value : 5 0 * * * *  
Context : *global*  
Cron expression of how often blocklist user agent is updated.

`BLOCK_TOR_EXIT_NODE`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
Is set to yes, will block known TOR exit nodes.  
Blacklist can be found [here](https://iplists.firehol.org/?ipset=tor_exits).

`BLOCK_TOR_EXIT_NODE_CRON`  
Values : *\<cron expression\>*   
Default value : 15 0 * * * *  
Context : *global*  
Cron expression of how often blocklist tor exit node is updated.

`BLOCK_PROXIES`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
Is set to yes, will block known proxies.  
Blacklist can be found [here](https://iplists.firehol.org/?ipset=firehol_proxies).

`BLOCK_PROXIES_CRON`  
Values : *\<cron expression\>*   
Default value : 20 0 * * * *  
Context : *global*  
Cron expression of how often blocklist proxies is updated.

`BLOCK_ABUSERS`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
Is set to yes, will block known abusers.  
Blacklist can be found [here](https://iplists.firehol.org/?ipset=firehol_abusers_30d).

`BLOCK_ABUSERS_CRON`  
Values : *\<cron expression\>*   
Default value : 30 0 * * * *  
Context : *global*  
Cron expression of how often blocklist abusers is updated.

`BLOCK_REFERRER`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
Is set to yes, will block known bad referrer header.  
Blacklist can be found [here](https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-referrers.list).

`BLOCK_REFERRER_CRON`  
Values : *\<cron expression\>*   
Default value : 10 0 * * * *  
Context : *global*  
Cron expression of how often blocklist referrer is updated.

### DNSBL

`USE_DNSBL`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to *yes*, DNSBL checks will be performed to the servers specified in the `DNSBL_LIST` environment variable.  

`DNSBL_LIST`  
Values : *\<list of DNS zones separated with spaces\>*  
Default value : *bl.blocklist.de problems.dnsbl.sorbs.net sbl.spamhaus.org xbl.spamhaus.org*  
Context : *global*  
The list of DNSBL zones to query when `USE_DNSBL` is set to *yes*.

### CrowdSec

`USE_CROWDSEC`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
If set to *yes*, [CrowdSec](https://github.com/crowdsecurity/crowdsec) will be enabled. Please note that you need a CrowdSec instance running see example [here](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/crowdsec).

`CROWDSEC_HOST`  
Values : *\<full URL to the CrowdSec instance API\>*  
Default value :  
Context : *global*  
The full URL to the CrowdSec API.

`CROWDSEC_KEY`  
Values : *\<CrowdSec bouncer key\>*  
Default value :  
Context : *global*  
The CrowdSec key given by *cscli bouncer add BouncerName*.

### Custom whitelisting

`USE_WHITELIST_IP`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to *yes*, lets you define custom IP addresses to be whitelisted through the `WHITELIST_IP_LIST` environment variable.

`WHITELIST_IP_LIST`  
Values : *\<list of IP addresses separated with spaces\>*  
Default value : *23.21.227.69 40.88.21.235 50.16.241.113 50.16.241.114 50.16.241.117 50.16.247.234 52.204.97.54 52.5.190.19 54.197.234.188 54.208.100.253 54.208.102.37 107.21.1.8*  
Context : *global*  
The list of IP addresses to whitelist when `USE_WHITELIST_IP` is set to *yes*. The default list contains IP addresses of the [DuckDuckGo crawler](https://help.duckduckgo.com/duckduckgo-help-pages/results/duckduckbot/).

`USE_WHITELIST_REVERSE`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to *yes*, lets you define custom reverse DNS suffixes to be whitelisted through the `WHITELIST_REVERSE_LIST` environment variable.

`WHITELIST_REVERSE_LIST`  
Values : *\<list of reverse DNS suffixes separated with spaces\>*  
Default value : *.googlebot.com .google.com .search.msn.com .crawl.yahoot.net .crawl.baidu.jp .crawl.baidu.com .yandex.com .yandex.ru .yandex.net*  
Context : *global*  
The list of reverse DNS suffixes to whitelist when `USE_WHITELIST_REVERSE` is set to *yes*. The default list contains suffixes of major search engines.

### Custom blacklisting

`USE_BLACKLIST_IP`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to *yes*, lets you define custom IP addresses to be blacklisted through the `BLACKLIST_IP_LIST` environment variable.

`BLACKLIST_IP_LIST`  
Values : *\<list of IP addresses separated with spaces\>*  
Default value :  
Context : *global*  
The list of IP addresses to blacklist when `USE_BLACKLIST_IP` is set to *yes*.

`USE_BLACKLIST_REVERSE`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to *yes*, lets you define custom reverse DNS suffixes to be blacklisted through the `BLACKLIST_REVERSE_LIST` environment variable.

`BLACKLIST_REVERSE_LIST`  
Values : *\<list of reverse DNS suffixes separated with spaces\>*  
Default value : *.shodan.io*  
Context : *global*  
The list of reverse DNS suffixes to blacklist when `USE_BLACKLIST_REVERSE` is set to *yes*.

### Requests limiting

`USE_LIMIT_REQ`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, the amount of HTTP requests made by a user will be limited during a period of time.  
More info rate limiting [here](https://www.nginx.com/blog/rate-limiting-nginx/).

`LIMIT_REQ_RATE`  
Values : *Xr/s* | *Xr/m*  
Default value : *20r/s*  
Context : *global*, *multisite*  
The rate limit to apply when `USE_LIMIT_REQ` is set to *yes*. Default is 10 requests per second.

`LIMIT_REQ_BURST`  
Values : *<any valid integer\>*  
Default value : *40*  
Context : *global*, *multisite*  
The number of of requests to put in queue before rejecting requests.

`LIMIT_REQ_CACHE`  
Values : *Xm* | *Xk*    
Default value : *10m*  
Context : *global*  
The size of the cache to store information about request limiting.

### Countries

`BLACKLIST_COUNTRY`  
Values : *\<country code 1\> \<country code 2\> ...*  
Default value :  
Context : *global*, *multisite*  
Block some countries from accessing your website. Use 2 letters country code separated with space.

`WHITELIST_COUNTRY`  
Values : *\<country code 1\> \<country code 2\> ...*  
Default value :  
Context : *global*, *multisite*  
Only allow specific countries accessing your website. Use 2 letters country code separated with space.

`GEOIP_CRON`  
Values : *\<cron expression\>*   
Default value : 30 2 2 * *
Context : *global*  
Cron expression of how often geoip will update its database.

## PHP

`REMOTE_PHP`  
Values : *\<any valid IP/hostname\>*  
Default value :  
Context : *global*, *multisite*  
Set the IP/hostname address of a remote PHP-FPM to execute .php files. See `USE_PHP` if you want to run a PHP-FPM instance on the same container as bunkerized-nginx.

`REMOTE_PHP_PATH`  
Values : *\<any valid absolute path\>*  
Default value : */app*  
Context : *global*, *multisite*  
The path where the PHP files are located inside the server specified in `REMOTE_PHP`.

## Fail2ban

`USE_FAIL2BAN`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, fail2ban will be used to block users getting too much "strange" HTTP codes in a period of time.  
Instead of using iptables which is not possible inside a container, fail2ban will dynamically update nginx to ban/unban IP addresses.  
If a number (`FAIL2BAN_MAXRETRY`) of "strange" HTTP codes (`FAIL2BAN_STATUS_CODES`) is found between a time interval (`FAIL2BAN_FINDTIME`) then the originating IP address will be ban for a specific period of time (`FAIL2BAN_BANTIME`).

`FAIL2BAN_STATUS_CODES`   
Values : *\<HTTP status codes separated with | char\>*  
Default value : *400|401|403|404|405|444*  
Context : *global*  
List of "strange" error codes that fail2ban will search for.  

`FAIL2BAN_BANTIME`  
Values : *<number of seconds>*  
Default value : *3600*  
Context : *global*  
The duration time, in seconds, of a ban.  

`FAIL2BAN_FINDTIME`  
Values : *<number of seconds>*  
Default : value : *60*  
Context : *global*  
The time interval, in seconds, to search for "strange" HTTP status codes.  

`FAIL2BAN_MAXRETRY`  
Values : *\<any positive integer\>*  
Default : value : *15*  
Context : *global*  
The number of "strange" HTTP status codes to find between the time interval.

`FAIL2BAN_IGNOREIP`  
Values : *\<list of IP addresses or subnet separated with spaces\>*  
Default value : 127.0.0.1/8 192.168.0.0/16 172.16.0.0/12 10.0.0.0/8  
Context : *global*  
IPs or subnet which should never be ban by fail2ban.

## ClamAV

`USE_CLAMAV_UPLOAD`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, ClamAV will scan every file uploads and block the upload if the file is detected.

`USE_CLAMAV_SCAN`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*  
If set to yes, ClamAV will scan all the files inside the container every day.  

`USE_CLAMAV_SCAN_CRON`  
Values : *\<cron expression\>*   
Default value : 40 */1 * * * 
Context : *global*  
Cron expression of how often ClamAV will scan all the files inside the container.  

`CLAMAV_SCAN_REMOVE`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*  
If set to yes, ClamAV will automatically remove the detected files.  

`CLAMAV_UPDATE_CRON`  
Values : *\<cron expression\>*   
Default value : 0 3 * * *
Context : *global*  
Cron expression of how often ClamAV will update its database.

## Misc

`ADDITIONAL_MODULES`  
Values : *\<list of packages separated with space\>*  
Default value :  
Context : *global*  
You can specify additional modules to install. All [alpine packages](https://pkgs.alpinelinux.org/packages) are valid.  

`LOGROTATE_MINSIZE`  
Values : *x* | *xk* | *xM* | *xG*  
Default value : 10M  
Context : *global*  
The minimum size of a log file before being rotated (no letter = bytes, k = kilobytes, M = megabytes, G = gigabytes).

`LOGROTATE_MAXAGE`  
Values : *\<any integer\>*  
Default value : 7  
Context : *global*  
The number of days before rotated files are deleted.

`LOGROTATE_CRON`  
Values : *\<cron expression\>*   
Default value : 0 4 * * *
Context : *global*  
Cron expression of how often Logrotate will rotate files.

# Include custom configurations
Custom configurations files (ending with .conf suffix) can be added in some directory inside the container :
  - /http-confs : http context
  - /server-confs : server context

You just need to use a volume like this :
```shell
docker run ... -v /path/to/http/confs:/http-confs:ro ... -v /path/to/server/confs:/server-confs:ro ... bunkerity/bunkerized-nginx
```

When `MULTISITE` is set to *yes*, .conf files inside the /server-confs directory are loaded by all the server blocks. You can also set custom configuration for a specific server block by adding files in a subdirectory named as the host defined in the `SERVER_NAME` environment variable. Here is an example :

```shell
docker run ... -v /path/to/server/confs:/server-confs:ro ... -e MULTISITE=yes -e "SERVER_NAME=app1.domain.com app2.domain.com" ... bunkerity/bunkerized-nginx
```

The */path/to/server/confs* directory should have a structure like this :
```
/path/to/server/confs
├── app1.domain.com
│   └── custom.conf
│   └── ...
└── app2.domain.com
    └── custom.conf
    └── ...
```

# Cache data

You can store cached data (blacklists, geoip DB, ...) to avoid downloading them again after a container deletion by mounting a volume on the /cache directory :

```shell
docker run ... -v /path/to/cache:/cache ... bunkerity/bunkerized-nginx
```
