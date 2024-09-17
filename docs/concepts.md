# Concepts

<figure markdown>
  ![Overview](assets/img/concepts.svg){ align=center, width="600" }
</figure>

## Integrations

The first concept is the integration of BunkerWeb into the target environment. We prefer to use the word "integration" instead of "installation" because one of the goals of BunkerWeb is to integrate seamlessly into existing environments.

The following integrations are officially supported :

- [Docker](integrations.md#docker)
- [Linux](integrations.md#linux)
- [Docker autoconf](integrations.md#docker-autoconf)
- [Kubernetes](integrations.md#kubernetes)
- [Swarm](integrations.md#swarm)

If you think that a new integration should be supported, do not hesitate to open a [new issue](https://github.com/bunkerity/bunkerweb/issues) on the GitHub repository.

!!! info "Going further"

    The technical details of all BunkerWeb integrations are available in the [integrations section](integrations.md) of the documentation.

## Settings

!!! tip "Pro settings"

    Some plugins are reserved for the **pro version**. [Find out more about the pro version here.](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc#pro)

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

    To help you tune BunkerWeb, we offer an easy-to-use settings generator tool available at [config.bunkerweb.io](https://config.bunkerweb.io/?utm_campaign=self&utm_source=doc).

## Multisite mode

Understanding the multisite mode is essential when utilizing BunkerWeb. As our primary focus is safeguarding web applications, our solution is intricately linked to the concept of "virtual hosts" or "vhosts" (more info [here](https://en.wikipedia.org/wiki/Virtual_hosting)). These virtual hosts enable the serving of multiple web applications from a single instance or cluster.

By default, BunkerWeb has the multisite mode disabled. This means that only one web application will be served, and all settings will be applied to it. This setup is ideal when you have a single application to protect, as you don't need to concern yourself with multisite configurations.

However, when the multisite mode is enabled, BunkerWeb becomes capable of serving and protecting multiple web applications. Each web application is identified by a unique server name and has its own set of settings. This mode proves beneficial when you have multiple applications to secure, and you prefer to utilize a single instance (or a cluster) of BunkerWeb.

The activation of the multisite mode is controlled by the `MULTISITE` setting, which can be set to `yes` to enable it or `no` to keep it disabled (which is the default value).

Each setting within BunkerWeb has a specific context that determines where it can be applied. If the context is set to "global," the setting can't be applied per server or site but is instead applied to the entire configuration as a whole. On the other hand, if the context is "multisite," the setting can be applied globally and per server. To define a multisite setting for a specific server, simply add the server name as a prefix to the setting name. For example, `app1.example.com_AUTO_LETS_ENCRYPT` or `app2.example.com_USE_ANTIBOT` are examples of setting names with server name prefixes. When a multisite setting is defined globally without a server prefix, all servers inherit that setting. However, individual servers can still override the setting if the same setting is defined with a server name prefix.

Understanding the intricacies of multisite mode and its associated settings allows you to tailor BunkerWeb's behavior to suit your specific requirements, ensuring optimal protection for your web applications.

Here's a dummy example of a multisite BunkerWeb configuration :

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

    You will find concrete examples of multisite mode in the [quickstart guide](quickstart-guide.md) of the documentation and the [examples](https://github.com/bunkerity/bunkerweb/tree/v1.5.10/examples) directory of the repository.

## Custom configurations

To address unique challenges and cater to specific use cases, BunkerWeb offers the flexibility of custom configurations. While the provided settings and [external plugins](plugins.md) cover a wide range of scenarios, there may be situations that require additional customization.

BunkerWeb is built on the renowned NGINX web server, which provides a powerful configuration system. This means you can leverage NGINX's configuration capabilities to meet your specific needs. Custom NGINX configurations can be included in various [contexts](https://docs.nginx.com/nginx/admin-guide/basic-functionality/managing-configuration-files/#contexts) such as HTTP or server, allowing you to fine-tune the behavior of BunkerWeb according to your requirements. Whether you need to customize global settings or apply configurations to specific server blocks, BunkerWeb empowers you to optimize its behavior to align perfectly with your use case.

Another integral component of BunkerWeb is the ModSecurity Web Application Firewall. With custom configurations, you have the flexibility to address false positives or add custom rules to further enhance the protection provided by ModSecurity. These custom configurations allow you to fine-tune the behavior of the firewall and ensure that it aligns with the specific requirements of your web applications.

By leveraging custom configurations, you unlock a world of possibilities to tailor BunkerWeb's behavior and security measures precisely to your needs. Whether it's adjusting NGINX configurations or fine-tuning ModSecurity, BunkerWeb provides the flexibility to meet your unique challenges effectively.

!!! info "Going further"

    You will find concrete examples of custom configurations in the [quickstart guide](quickstart-guide.md) of the documentation and the [examples](https://github.com/bunkerity/bunkerweb/tree/v1.5.10/examples) directory of the repository.

## Database

BunkerWeb securely stores its current configuration in a backend database, which contains essential data for smooth operation. The following information is stored in the database:

- **Settings for all services**: The database holds the defined settings for all the services provided by BunkerWeb. This ensures that your configurations and preferences are preserved and readily accessible.

- **Custom configurations**: Any custom configurations you create are also stored in the backend database. This includes personalized settings and modifications tailored to your specific requirements.

- **BunkerWeb instances**: Information about BunkerWeb instances, including their setup and relevant details, is stored in the database. This allows for easy management and monitoring of multiple instances if applicable.

- **Metadata about job execution**: The database stores metadata related to the execution of various jobs within BunkerWeb. This includes information about scheduled tasks, maintenance processes, and other automated activities.

- **Cached files**: BunkerWeb utilizes caching mechanisms for improved performance. The database holds cached files, ensuring efficient retrieval and delivery of frequently accessed resources.

Under the hood, whenever you edit a setting or add a new configuration, BunkerWeb automatically stores the changes in the database, ensuring data persistence and consistency. BunkerWeb supports multiple backend database options, including SQLite, MariaDB, MySQL, and PostgreSQL.

Configuring the database is straightforward using the `DATABASE_URI` setting, which follows the specified formats for each supported database:

- **SQLite**: `sqlite:///var/lib/bunkerweb/db.sqlite3`
- **MariaDB**: `mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db`
- **MySQL**: `mysql+pymysql://bunkerweb:changeme@bw-db:3306/db`
- **PostgreSQL**: `postgresql://bunkerweb:changeme@bw-db:5432/db`

By specifying the appropriate database URI in the configuration, you can seamlessly integrate BunkerWeb with your preferred database backend, ensuring efficient and reliable storage of your configuration data.

<figure markdown>
  ![Overview](assets/img/bunkerweb_db.svg){ align=center, width="800" }
  <figcaption>Database Schema</figcaption>
</figure>

## Scheduler

For seamless coordination and automation, BunkerWeb employs a specialized service known as the scheduler. The scheduler plays a vital role in ensuring smooth operation by performing the following tasks:

- **Storing settings and custom configurations**: The scheduler is responsible for storing all the settings and custom configurations within the backend database. This centralizes the configuration data, making it easily accessible and manageable.

- **Executing various tasks (jobs)**: The scheduler handles the execution of various tasks, referred to as jobs. These jobs encompass a range of activities, such as periodic maintenance, scheduled updates, or any other automated tasks required by BunkerWeb.

- **Generating BunkerWeb configuration**: The scheduler generates a configuration that is readily understood by BunkerWeb. This configuration is derived from the stored settings and custom configurations, ensuring that the entire system operates cohesively.

- **Acting as an intermediary for other services**: The scheduler acts as an intermediary, facilitating communication and coordination between different components of BunkerWeb. It interfaces with services such as the web UI or autoconf, ensuring a seamless flow of information and data exchange.

In essence, the scheduler serves as the brain of BunkerWeb, orchestrating various operations and ensuring the smooth functioning of the system.

Depending on the integration approach, the execution environment of the scheduler may differ. In container-based integrations, the scheduler is executed within its dedicated container, providing isolation and flexibility. On the other hand, for Linux-based integrations, the scheduler is self-contained within the bunkerweb service, simplifying the deployment and management process.

By employing the scheduler, BunkerWeb streamlines the automation and coordination of essential tasks, enabling efficient and reliable operation of the entire system.
