# Concepts

## Architecture

<figure markdown>
  ![Overview](assets/img/concepts.svg){ align=center, width="600" }
</figure>

Within your infrastructure, BunkerWeb acts as a reverse proxy in front of your web services. The typical architecture involves accessing BunkerWeb from the Internet, which then forwards requests to the appropriate application service on a secure network.

Using BunkerWeb in this way (classical reverse proxy architecture) with TLS offloading and centralized security policies enhances performance by reducing encryption overhead on backend servers while ensuring consistent access control, threat mitigation, and compliance enforcement across all services.

## Integrations

The first concept is the integration of BunkerWeb into the target environment. We prefer to use the word "integration" instead of "installation" because one of BunkerWeb's goals is to integrate seamlessly into existing environments.

The following integrations are officially supported:

- [Docker](integrations.md#docker)
- [Linux](integrations.md#linux)
- [Docker autoconf](integrations.md#docker-autoconf)
- [Kubernetes](integrations.md#kubernetes)
- [Swarm](integrations.md#swarm)

If you think a new integration should be supported, do not hesitate to open a [new issue](https://github.com/bunkerity/bunkerweb/issues) on the GitHub repository.

!!! info "Going further"

    The technical details of all BunkerWeb integrations are available in the [integrations section](integrations.md) of the documentation.

## Settings

!!! tip "BunkerWeb PRO settings"
    Some plugins are reserved for the **PRO version**. Want to quickly test BunkerWeb PRO for one month? Use the code `freetrial` when placing your order on the [BunkerWeb panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) or by clicking [here](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc) to directly to apply the promo code (will be effective at checkout).

Once BunkerWeb is integrated into your environment, you will need to configure it to serve and protect your web applications.

The configuration of BunkerWeb is done using what we call "settings" or "variables." Each setting is identified by a name such as `AUTO_LETS_ENCRYPT` or `USE_ANTIBOT`. You can assign values to these settings to configure BunkerWeb.

Here is a dummy example of a BunkerWeb configuration:

```conf
SERVER_NAME=www.example.com
AUTO_LETS_ENCRYPT=yes
USE_ANTIBOT=captcha
REFERRER_POLICY=no-referrer
USE_MODSECURITY=no
USE_GZIP=yes
USE_BROTLI=no
```

Please note that if you are using the web User Interface, the setting names are also displayed in addition to a "human-friendly" label:

<figure markdown>
  ![Overview](assets/img/settings-ui1.png){ align=center, width="800" }
  <figcaption>Settings name in the web UI</figcaption>
</figure>

You can also use the search bar and directly specify a setting name:

<figure markdown>
  ![Overview](assets/img/settings-ui2.png){ align=center, width="600" }
  <figcaption>Settings search in the web UI</figcaption>
</figure>

!!! info "Going further"

    The complete list of available settings with descriptions and possible values is available in the [feature section](features.md) of the documentation.

## Multisite mode {#multisite-mode}

Understanding the multisite mode is essential when utilizing BunkerWeb. As our primary focus is safeguarding web applications, our solution is intricately linked to the concept of "virtual hosts" or "vhosts" (more info [here](https://en.wikipedia.org/wiki/Virtual_hosting)). These virtual hosts enable the serving of multiple web applications from a single instance or cluster.

By default, BunkerWeb has the multisite mode disabled. This means that only one web application will be served, and all settings will be applied to it. This setup is ideal when you have a single application to protect, as you don't need to concern yourself with multisite configurations.

However, when the multisite mode is enabled, BunkerWeb becomes capable of serving and protecting multiple web applications. Each web application is identified by a unique server name and has its own set of settings. This mode proves beneficial when you have multiple applications to secure, and you prefer to utilize a single instance (or a cluster) of BunkerWeb.

The activation of the multisite mode is controlled by the `MULTISITE` setting, which can be set to `yes` to enable it or `no` to keep it disabled (the default value).

Each setting within BunkerWeb has a specific context that determines where it can be applied. If the context is set to "global," the setting can't be applied per server or site but is instead applied to the entire configuration as a whole. On the other hand, if the context is "multisite," the setting can be applied globally and per server. To define a multisite setting for a specific server, simply add the server name as a prefix to the setting name. For example, `app1.example.com_AUTO_LETS_ENCRYPT` or `app2.example.com_USE_ANTIBOT` are examples of setting names with server name prefixes. When a multisite setting is defined globally without a server prefix, all servers inherit that setting. However, individual servers can still override the setting if the same setting is defined with a server name prefix.

Understanding the intricacies of multisite mode and its associated settings allows you to tailor BunkerWeb's behavior to suit your specific requirements, ensuring optimal protection for your web applications.

Here's a dummy example of a multisite BunkerWeb configuration:

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

Please note that multisite mode is implicit when using the web User Interface. You have the option to apply configurations directly to your services or to set global settings that will be applied to all your services (you can still apply exceptions directly to specific services):

<figure markdown>
  ![Overview](assets/img/ui-multisite.png){ align=center, width="600" }
  <figcaption>Apply a setting to all services from the web UI</figcaption>
</figure>

!!! info "Going further"

    You will find concrete examples of multisite mode in the [advanced usages](advanced.md) of the documentation and the [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/examples) directory of the repository.

## Custom configurations {#custom-configurations}

To address unique challenges and cater to specific use cases, BunkerWeb offers the flexibility of custom configurations. While the provided settings and [external plugins](plugins.md) cover a wide range of scenarios, there may be situations that require additional customization.

BunkerWeb is built on the renowned NGINX web server, which provides a powerful configuration system. This means you can leverage NGINX's configuration capabilities to meet your specific needs. Custom NGINX configurations can be included in various [contexts](https://docs.nginx.com/nginx/admin-guide/basic-functionality/managing-configuration-files/#contexts) such as HTTP or server, allowing you to fine-tune the behavior of BunkerWeb according to your requirements. Whether you need to customize global settings or apply configurations to specific server blocks, BunkerWeb empowers you to optimize its behavior to align perfectly with your use case.

Another integral component of BunkerWeb is the ModSecurity Web Application Firewall. With custom configurations, you have the flexibility to address false positives or add custom rules to further enhance the protection provided by ModSecurity. These custom configurations allow you to fine-tune the behavior of the firewall and ensure that it aligns with the specific requirements of your web applications.

By leveraging custom configurations, you unlock a world of possibilities to tailor BunkerWeb's behavior and security measures precisely to your needs. Whether it's adjusting NGINX configurations or fine-tuning ModSecurity, BunkerWeb provides the flexibility to meet your unique challenges effectively.

Managing custom configurations from the web User Interface is done through the **Configs** menu:

<figure markdown>
  ![Overview](assets/img/configs-ui.png){ align=center, width="800" }
  <figcaption>Manage custom configurations from the web UI</figcaption>
</figure>

!!! info "Going further"

    You will find concrete examples of custom configurations in the [advanced usages](advanced.md#custom-configurations) of the documentation and the [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/examples) directory of the repository.

## Database

BunkerWeb securely stores its current configuration in a backend database, which contains essential data for smooth operation. The following information is stored in the database:

- **Settings for all services**: The database holds the defined settings for all the services provided by BunkerWeb. This ensures that your configurations and preferences are preserved and readily accessible.

- **Custom configurations**: Any custom configurations you create are also stored in the backend database. This includes personalized settings and modifications tailored to your specific requirements.

- **BunkerWeb instances**: Information about BunkerWeb instances, including their setup and relevant details, is stored in the database. This allows for easy management and monitoring of multiple instances if applicable.

- **Metadata about job execution**: The database stores metadata related to the execution of various jobs within BunkerWeb. This includes information about scheduled tasks, maintenance processes, and other automated activities.

- **Cached files**: BunkerWeb utilizes caching mechanisms for improved performance. The database holds cached files, ensuring efficient retrieval and delivery of frequently accessed resources.

Under the hood, whenever you edit a setting or add a new configuration, BunkerWeb automatically stores the changes in the database, ensuring data persistence and consistency. BunkerWeb supports multiple backend database options, including SQLite, MariaDB, MySQL, and PostgreSQL.

!!! tip
    When you rely on the web UI for day-to-day administration, we recommend switching to an external database engine (PostgreSQL or MySQL/MariaDB) instead of staying on SQLite. External engines handle concurrent requests and long-term growth more gracefully, especially in multi-user environments.

Configuring the database is straightforward using the `DATABASE_URI` setting, which follows the specified formats for each supported database:

!!! warning
    When using the Docker Integration, you must set the `DATABASE_URI` environment variable in all BunkerWeb containers (except the BunkerWeb container itself), to ensure that all components can access the database correctly. This is crucial for maintaining the integrity and functionality of the system.

    In all cases, ensure that `DATABASE_URI` is set before starting BunkerWeb, as it is required for proper operation.

- **SQLite**: `sqlite:///var/lib/bunkerweb/db.sqlite3`
- **MariaDB**: `mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db`
- **MySQL**: `mysql+pymysql://bunkerweb:changeme@bw-db:3306/db`
- **PostgreSQL**: `postgresql://bunkerweb:changeme@bw-db:5432/db`

By specifying the appropriate database URI in the configuration, you can seamlessly integrate BunkerWeb with your preferred database backend, ensuring efficient and reliable storage of your configuration data.

### Database compatibility matrix

| Integration        | PostgreSQL                                   | MariaDB             | MySQL              | SQLite      |
| :----------------- | :------------------------------------------- | :------------------ | :----------------- | :---------- |
| **Docker**         | ✅ `v18` and earlier (all-in-one: ✅ `v17`)   | ✅ `v11` and earlier | ✅ `v9` and earlier | ✅ Supported |
| **Kubernetes**     | ✅ `v18` and earlier                          | ✅ `v11` and earlier | ✅ `v9` and earlier | ✅ Supported |
| **Autoconf**       | ✅ `v18` and earlier                          | ✅ `v11` and earlier | ✅ `v9` and earlier | ✅ Supported |
| **Linux packages** | See notes below                              | See notes below     | See notes below    | ✅ Supported |

!!! info "Notes"
    - **PostgreSQL**: Alpine packages now ship with the `v18` client, so `v18` and earlier are supported out of the box; the all-in-one image still embeds `v17`, so `v18` is unsupported there.
    - **Linux**: Support depends on your distribution's packages. If needed, you can install database clients manually from vendor repositories (RHEL typically requires this).
    - **SQLite**: Ships with the packages and is ready to use.

Helpful external resources for installing database clients:

- [PostgreSQL download and repository guide](https://www.postgresql.org/download/)
- [MariaDB repository configuration tool](https://mariadb.org/download/?t=repo-config)
- [MySQL repository setup guide](https://dev.mysql.com/doc/mysql-yum-repo-quick-guide/en/)
- [SQLite download page](https://www.sqlite.org/download.html)

<figure markdown>
  ![Overview](assets/img/bunkerweb_db.svg){ align=center, width="800" }
  <figcaption>Database Schema</figcaption>
</figure>

## Scheduler {#scheduler}

For seamless coordination and automation, BunkerWeb employs a specialized service known as the scheduler. The scheduler plays a vital role in ensuring smooth operation by performing the following tasks:

- **Storing settings and custom configurations**: The scheduler is responsible for storing all the settings and custom configurations within the backend database. This centralizes the configuration data, making it easily accessible and manageable.

- **Executing various tasks (jobs)**: The scheduler handles the execution of various tasks, referred to as jobs. These jobs encompass a range of activities, such as periodic maintenance, scheduled updates, or any other automated tasks required by BunkerWeb.

- **Generating BunkerWeb configuration**: The scheduler generates a configuration that is readily understood by BunkerWeb. This configuration is derived from the stored settings and custom configurations, ensuring that the entire system operates cohesively.

- **Acting as an intermediary for other services**: The scheduler acts as an intermediary, facilitating communication and coordination between different components of BunkerWeb. It interfaces with services such as the web UI or autoconf, ensuring a seamless flow of information and data exchange.

In essence, the scheduler serves as the brain of BunkerWeb, orchestrating various operations and ensuring the smooth functioning of the system.

Depending on the integration approach, the execution environment of the scheduler may differ. In container-based integrations, the scheduler is executed within its dedicated container, providing isolation and flexibility. On the other hand, for Linux-based integrations, the scheduler is self-contained within the bunkerweb service, simplifying the deployment and management process.

By employing the scheduler, BunkerWeb streamlines the automation and coordination of essential tasks, enabling efficient and reliable operation of the entire system.

If you are using the web User Interface, you can manage scheduler jobs by clicking on **Jobs** from the menu:

<figure markdown>
  ![Overview](assets/img/jobs-ui.png){ align=center, width="800" }
  <figcaption>Manage jobs from the web UI</figcaption>
</figure>

### Instances health check

Since version 1.6.0, the scheduler possesses a built-in health check system that monitors the health of instances. If an instance becomes unhealthy, the scheduler will stop sending the configuration to it. If the instance becomes healthy again, the scheduler will resume sending the configuration.

The health check interval is set by the `HEALTHCHECK_INTERVAL` environment variable, with a default value of `30`, meaning the scheduler will check the health of the instances every 30 seconds.

## Templates {#templates}

BunkerWeb leverages the power of templates to simplify the configuration process and enhance flexibility. Templates provide a structured and standardized approach to defining settings and custom configurations, ensuring consistency and ease of use.

- **Predefined templates**: The community version offers three predefined templates that encapsulate common custom configurations and settings. These templates serve as a starting point for configuring BunkerWeb, enabling quick setup and deployment. The predefined templates are the following:
    - **low**: A basic template that provides essential settings for web application protection.
    - **medium**: A balanced template that offers a mix of security features and performance optimizations.
    - **high**: An advanced template that focuses on robust security measures and comprehensive protection.

- **Custom templates**: In addition to predefined templates, BunkerWeb allows users to create custom templates tailored to their specific requirements. Custom templates enable fine-tuning of settings and custom configurations, ensuring that BunkerWeb aligns perfectly with the user's needs.

With the web User Interface, templates are available through **easy mode** when you add or edit a service:

<figure markdown>
  ![Overview](assets/img/templates-ui.png){ align=center, width="800" }
  <figcaption>Templates usage from the web UI</figcaption>
</figure>

**Creating custom templates**

Creating a custom template is a straightforward process that involves defining the desired settings, custom configurations, and steps in a structured format.

* **Template structure**: A custom template consists of a name, a series of settings, custom configurations, and optional steps. The template structure is defined in a JSON file that adheres to the specified format. The key components of a custom template include:
    * **Settings**: A setting is defined with a name and corresponding value. This value will override the default value of the setting. **Only multisite settings are supported.**
    * **Configs**: A custom configuration is a path to an NGINX configuration file that will be included as a custom configuration. To know where to place the custom configuration file, refer to the example of a plugin's tree below. **Only multisite configuration types are supported.**
    * **Steps**: A step contains a title, subtitle, settings, and custom configurations. Each step represents a configuration step that the user can follow to set up BunkerWeb according to the custom template in the web UI.

!!! info "Specifications about steps"

    If steps are declared, **it is not mandatory to include all the settings and custom configurations in the settings and configs sections**. Keep in mind that when a setting or a custom configuration is declared in a step, the user will be allowed to make edits to it in the web UI.

* **Template file**: The custom template is defined in a JSON file in a `templates` folder inside the plugin directory that adheres to the specified structure. The template file contains a name, the settings, custom configurations, and steps required to configure BunkerWeb according to the user's preferences.

* **Selecting a template**: Once the custom template is defined, users can select it during the easy-mode configuration process of a service in the web UI. A template can also be selected with the `USE_TEMPLATE` setting in the configuration. The name of the template file (without the `.json` extension) should be specified as the value of the `USE_TEMPLATE` setting.

Example of a custom template file:
```json
{
    "name": "template name",
	// optional
    "settings": {
        "SETTING_1": "value",
        "SETTING_2": "value"
    },
	// optional
    "configs": [
        "modsec/false_positives.conf",
        "modsec/non_editable.conf",
		"modsec-crs/custom_rules.conf"
    ],
	// optional
    "steps": [
        {
            "title": "Title 1",
            "subtitle": "subtitle 1",
            "settings": [
                "SETTING_1"
            ],
            "configs": [
                "modsec-crs/custom_rules.conf"
            ]
        },
        {
            "title": "Title 2",
            "subtitle": "subtitle 2",
            "settings": [
                "SETTING_2"
            ],
            "configs": [
                "modsec/false_positives.conf"
            ]
        }
    ]
}
```

Example of a plugin's tree including custom templates:
```tree
.
├── plugin.json
└── templates
    ├── my_other_template.json
    ├── my_template
    │   └── configs
    │       ├── modsec
    │       │   ├── false_positives.conf
    │       │   └── non_editable.conf
    │       └── modsec-crs
    │           └── custom_rules.conf
    └── my_template.json
```
