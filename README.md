<p align="center">
	<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/docs/img/logo.png?raw=true" width="425" />
</p>

<p align="center">
        <img src="https://img.shields.io/badge/bunkerized--nginx-1.3.0-blue" />
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

bunkerized-nginx is a web server based on the notorious nginx and focused on security. It integrates into existing environments (Linux, Docker, Swarm, Kubernetes, ...) to make your web services "secure by default" without any hassle. The security best practices are automatically applied for you while keeping control of every settings to meet your own use case.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/docs/img/overview.png?raw=true" />

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

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/docs/img/demo.gif?raw=true" />

You can find a live demo at [https://demo-nginx.bunkerity.com](https://demo-nginx.bunkerity.com), feel free to do some security tests.

# Table of contents
<details>
	<summary>Click to show</summary>

- [Table of contents](#table-of-contents)
- [Integrations](#integrations)
  * [Docker](#docker)
  * [Docker autoconf](#docker-autoconf)
  * [Swarm](#swarm)
  * [Kubernetes](#kubernetes)
  * [Linux](#linux)
- [Configuration](#configuration)
  * [Singlesite](#singlesite)
  * [Multisite](#multisite)
  * [Special folders](#special-folders)
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
$ git clone https://github.com/bunkerity/bunkerized-nginx.git
$ cd bunkerized-nginx
$ docker build -t bunkerized-nginx .
```

To use bunkerized-nginx as a Docker container you have to pass specific environment variables, mount volumes and redirect ports to make it accessible from the outside.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/docs/img/docker.png?raw=true" />

You will find more information about Docker integration in the [documentation](https://bunkerized-nginx.readthedocs.io/en/latest/integrations.html#docker).

## Docker autoconf

The downside of using environment variables is that the container needs to be recreated each time there is an update which is not very convenient. To counter that issue, you can use another image called bunkerized-nginx-autoconf which will listen for Docker events and automatically configure bunkerized-nginx instance in real time without recreating the container. Instead of defining environment variables for the bunkerized-nginx container, you simply add labels to your web services and bunkerized-nginx-autoconf will "automagically" take care of the rest.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/docs/img/autoconf-docker.png?raw=true" />

You will find more information about Docker autoconf feature in the [documentation](https://bunkerized-nginx.readthedocs.io/en/latest/integrations.html#docker-autoconf).

## Swarm

Using bunkerized-nginx in a Docker Swarm cluster requires a shared folder accessible from both managers and workers (anything like NFS, GlusterFS, CephFS or even SSHFS will work). The deployment and configuration is very similar to the "Docker autoconf" one but with services instead of containers. A service based on the bunkerized-nginx-autoconf image needs to be scheduled on a manager node (don't worry it doesn't expose any network port for obvious security reasons). This service will listen for Docker Swarm events like service creation or deletion and generate the configuration according to the labels of each service. Once configuration generation is done, the bunkerized-nginx-autoconf service will send a reload order to all the bunkerized-nginx tasks so they can load the new configuration.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/docs/img/swarm.png?raw=true" />

You will find more information about Docker Swarm integration in the [documentation](https://bunkerized-nginx.readthedocs.io/en/latest/integrations.html#docker-swarm).

## Kubernetes

**This integration is still in beta, please fill an issue if you find a bug or have an idea on how to improve it.**

Using bunkerized-nginx in a Kubernetes cluster requires a shared folder accessible from the nodes (anything like NFS, GlusterFS, CephFS or even SSHFS will work). The bunkerized-nginx-autoconf acts as an Ingress Controller and connects to the k8s API to get cluster events and generate a new configuration when it's needed. Once the configuration is generated, the Ingress Controller sends a reload order to the bunkerized-nginx instances running in the cluster.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/docs/img/kubernetes.png?raw=true" />

You will find more information about Kubernetes integration in the [documentation](https://bunkerized-nginx.readthedocs.io/en/latest/integrations.html#kubernetes).

## Linux

**This integration is still in beta, please fill an issue if you find a bug or have an idea on how to improve it.**

List of supported Linux distributions :
- Debian buster (10)
- Ubuntu focal (20.04)
- CentOS 7
- Fedora 34

Unlike containers, Linux integration can be tedious because bunkerized-nginx has a bunch of dependencies that need to be installed before we can use it. Fortunately, we provide a [helper script](https://github.com/bunkerity/bunkerized-nginx/blob/master/helpers/install.sh) to make the process easier and automatic. Once installed, the configuration is really simple, all you have to do is to edit the `/opt/bunkerized-nginx/variables.env` configuration file and run the `bunkerized-nginx` command to apply it.

You will find more information about Linux integration in the [documentation](https://bunkerized-nginx.readthedocs.io/en/latest/integrations.html#linux).

# Configuration

The configuration is made through what we call "environment variables" as a form of key/value pairs. You will find the [quickstart guide](https://bunkerized-nginx.readthedocs.io/en/latest/quickstart_guide.html) and the complete [list of environment variables](https://bunkerized-nginx.readthedocs.io/en/latest/environment_variables.html) in the documentation.

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

You will find more information about the special folders in the [documentation](https://bunkerized-nginx.readthedocs.io/en/latest/special_folders.html).

# Web UI

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/docs/img/web-ui.gif?raw=true" />

You will find more information about the web UI in the [documentation](https://bunkerized-nginx.readthedocs.io/en/latest/web_ui.html).

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
