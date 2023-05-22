# Concepts

<figure markdown>
  ![Overwiew](assets/img/concepts.svg){ align=center }
</figure>

## Integrations

The first concept is the integration of BunkerWeb into the target environment. We prefer to use the word "integration" instead of "installation" because one of the goals of BunkerWeb is to integrate seamlessly into existing environments.

The following integrations are officially supported :

- [Docker](integrations.md#docker)
- [Docker autoconf](integrations.md#docker-autoconf)
- [Swarm](integrations.md#swarm)
- [Kubernetes](integrations.md#kubernetes)
- [Linux](integrations.md#linux)
- [Ansible](integrations.md#ansible)
- [Vagrant](integrations.md#vagrant)

If you think that a new integration should be supported, do not hesitate to open a [new issue](https://github.com/bunkerity/bunkerweb/issues) on the GitHub repository.

!!! info "Going further"

    The technical details of all BunkerWeb integrations are available in the [integrations section](integrations.md) of the documentation.

## Settings

Once BunkerWeb is integrated into your environment, you will need to configure it to serve and protect your web applications.

The configuration of BunkerWeb is done by using what we call the "settings" or "variables". Each setting is identified by a name such as `AUTO_LETS_ENCRYPT` or `USE_ANTIBOT`. You can assign values to the settings to configure BunkerWeb.

Here is a dummy example of a BunkerWeb configuration :

```conf
SERVER_NAME=www.example.com
AUTO_LETS_ENCRYPT=yes
USE_ANTIBOT=captcha
REFERRER_POLICY=no-referrer
USE_MODSECURITY=no
USE_GZIP=yes
USE_BROTLI=no
```

!!! info "Going further"

    The complete list of available settings with descriptions and possible values is available in the [settings section](settings.md) of the documentation.

!!! info "Settings generator tool"

    To help you tune BunkerWeb, we offer an easy-to-use settings generator tool available at [config.bunkerweb.io](https://config.bunkerweb.io).

## Multisite mode

The multisite mode is a crucial concept to understand when using BunkerWeb. Because the goal is to protect web applications, our solution is intrinsically linked to the concept of "virtual host" or "vhost" (more info [here](https://en.wikipedia.org/wiki/Virtual_hosting)) which makes it possible to serve multiple web applications from a single (or a cluster of) instance.

By default, the multisite mode of BunkerWeb is disabled which means that only one web application will be served and all the settings will be applied to it. The typical use case is having a single application to protect : you don't have to worry about the multisite and the default behavior should be the right one for you.

When multisite mode is enabled, BunkerWeb serves and protects multiple web applications. Each web application is identified by a unique server name and have its own set of settings. The typical use case is having multiple applications to protect and you want to use a single (or a cluster depending of the integration) instance of BunkerWeb.

The multisite mode is controlled by the `MULTISITE` setting which can be set to `yes` (enabled) or `no` (disabled, which is the default).

Each setting has a context that defines "where" it can be applied. If the context is global then the setting can't be set per server (or "per site", "per app") but only to the whole configuration. Otherwise, if the context is multisite, the setting can be set globally and per server. Defining a multisite setting to a specific server is done by adding the server name as a prefix of the setting name like `app1.example.com_AUTO_LETS_ENCRYPT` or `app2.example.com_USE_ANTIBOT` for example. When a multisite setting is defined globally (without any server prefix), all the servers will inherit that setting (but can still be overridden if we set the same setting with the server name prefix).

Here is a dummy example of a multisite BunkerWeb configuration :

```conf
MULTISITE=yes
SERVER_NAME=app1.example.com app2.example.com app3.example.com
AUTO_LETS_ENCRYPT=yes
USE_GZIP=yes
USE_BROTLI=yes
app1.example.com_USE_ANTIBOT=javascript
app1.example.com_USE_MODSECURITY=no
app2.example.com_USE_ANTIBOT=cookie
app2.example.com_WHITELIST_COUNTRY=FR
app3.example.com_USE_BAD_BEHAVIOR=no
```

!!! info "Going further"

    You will find concrete examples of multisite mode in the [quickstart guide](quickstart-guide.md) of the documentation and the [examples](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/examples) directory of the repository.

## Custom configurations

Because meeting all the use cases only using the settings is not an option (even with [external plugins](plugins.md)), you can use custom configurations to solve your specific challenges.

Under the hood, BunkerWeb uses the notorious NGINX web server, that's why you can leverage its configuration system for your specific needs. Custom NGINX configurations can be included in different [contexts](https://docs.nginx.com/nginx/admin-guide/basic-functionality/managing-configuration-files/#contexts) like HTTP or server (all servers and/or specific server block).

Another core component of BunkerWeb is the ModSecurity Web Application Firewall : you can also use custom configurations to fix some false positives or add custom rules for example.

!!! info "Going further"

    You will find concrete examples of custom configurations in the [quickstart guide](quickstart-guide.md) of the documentation and the [examples](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/examples) directory of the repository.

## Database

State of the current configuration of BunkerWeb is stored in a backend database which contains the following data :

- Settings defined for all the services
- Custom configurations 
- BunkerWeb instances
- Metadata about jobs execution
- Cached files

Under the hood, when you edit a setting or add a new configuration, everything is stored in the database. We actually support SQLite, MariaDB, MySQL and PostgreSQL as backends.

Database configuration is done by using the `DATABASE_URI` setting which respects the following formats :

- SQLite : `sqlite:///var/lib/bunkerweb/db.sqlite3`
- MariaDB : `mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db`
- MySQL : `mysql+pymysql://bunkerweb:changeme@bw-db:3306/db`
- PostgreSQL : `postgresql://bunkerweb:changeme@bw-db:5432/db`

## Scheduler

To make things automagically work together, a dedicated service called the scheduler is in charge of :

- Storing the settings and custom configurations inside the database
- Executing various tasks (called jobs)
- Generating a configuration which is understood by BunkerWeb
- Being the intermediary for other services (like web UI or autoconf)

In other words, the scheduler is the brain of BunkerWeb.

When using container-based integrations, the scheduler is executed in its own container. Whereas, for linux-based integrations scheduler is self-contained in the `bunkerweb` service.