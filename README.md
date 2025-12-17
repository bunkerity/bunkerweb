<p align="center">
	<img alt="BunkerWeb logo" src="https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/misc/logo.png" height=100 width=350 />
</p>

<p align="center">
	<img src="https://img.shields.io/github/v/release/bunkerity/bunkerweb?label=stable" />
	<img src="https://img.shields.io/github/v/release/bunkerity/bunkerweb?include_prereleases&label=latest" />
	<br />
	<img src="https://img.shields.io/github/last-commit/bunkerity/bunkerweb" />
	<img src="https://img.shields.io/github/issues/bunkerity/bunkerweb">
	<img src="https://img.shields.io/github/issues-pr/bunkerity/bunkerweb">
	<br />
	<img src="https://img.shields.io/github/actions/workflow/status/bunkerity/bunkerweb/dev.yml?branch=dev&label=CI%2FCD%20dev" />
	<img src="https://img.shields.io/github/actions/workflow/status/bunkerity/bunkerweb/staging.yml?branch=staging&label=CI%2FCD%20staging" />
	<a href="https://www.bestpractices.dev/projects/8001">
		<img src="https://www.bestpractices.dev/projects/8001/badge">
	</a>
</p>

<p align="center">
	🌐 <a href="https://www.bunkerweb.io/?utm_campaign=self&utm_source=github">Website</a>
	 &#124;
	🤝 <a href="https://panel.bunkerweb.io/?utm_campaign=self&utm_source=github">Panel</a>
	 &#124;
	📓 <a href="https://docs.bunkerweb.io/?utm_campaign=self&utm_source=github">Documentation</a>
	 &#124;
	👨‍💻 <a href="https://demo.bunkerweb.io/?utm_campaign=self&utm_source=github">Demo</a>
	 &#124;
	📱 <a href="https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=github">Demo UI</a>
	 &#124;
	🧩 <a href="https://github.com/bunkerity/bunkerweb-templates">Templates</a>
	 &#124;
	🛡️ <a href="https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/examples">Examples</a>
	<br/>
	💬 <a href="https://discord.com/invite/fTf46FmtyD">Chat</a>
	 &#124;
	📝 <a href="https://github.com/bunkerity/bunkerweb/discussions">Forum</a>
	 &#124;
	🗺️ <a href="https://www.bunkerweb.io/threatmap/?utm_campaign=self&utm_source=github">Threatmap</a>
	&#124;
	📊 <a href="https://status.bunkerweb.io/?utm_campaign=self&utm_source=github">Status</a>
	&#124;
	🔎 <a href="https://forms.gle/e3VgymAteYPnwM1j9">Feedback</a>
</p>

> 🛡️ Make security by default great again!

# BunkerWeb

<p align="center">
	<img alt="Overview banner" src="https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/docs/assets/img/intro-overview.svg" />
</p>

BunkerWeb is a next-generation, open-source Web Application Firewall (WAF).

Being a full-featured web server (based on [NGINX](https://nginx.org/) under the hood), it will protect your web services to make them "secure by default." BunkerWeb integrates seamlessly into your existing environments ([Linux](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#linux), [Docker](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#docker), [Swarm](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#swarm), [Kubernetes](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#kubernetes), …) as a reverse proxy and is fully configurable (don't panic, there is an [awesome web UI](https://docs.bunkerweb.io/1.6.7~rc1/web-ui/?utm_campaign=self&utm_source=github) if you don't like the CLI) to meet your own use cases. In other words, cybersecurity is no longer a hassle.

BunkerWeb contains primary [security features](https://docs.bunkerweb.io/1.6.7~rc1/advanced/?utm_campaign=self&utm_source=github#security-tuning) as part of the core but can be easily extended with additional ones thanks to a [plugin system](https://docs.bunkerweb.io/1.6.7~rc1/plugins/?utm_campaign=self&utm_source=github).

## Why BunkerWeb?

https://github.com/user-attachments/assets/c3fed740-28d8-4335-ab05-113a9e815b4f

- **Easy integration into existing environments**: Seamlessly integrate BunkerWeb into various environments such as Linux, Docker, Swarm, Kubernetes, and more. Enjoy a smooth transition and hassle-free implementation.
- **Highly customizable**: Tailor BunkerWeb to your specific requirements with ease. Enable, disable, and configure features effortlessly, allowing you to customize the security settings according to your unique use case.
- **Secure by default**: BunkerWeb provides out-of-the-box, hassle-free minimal security for your web services. Experience peace of mind and enhanced protection right from the start.
- **Awesome web UI**: Take control of BunkerWeb more efficiently with the exceptional web user interface (UI). Navigate settings and configurations effortlessly through a user-friendly graphical interface, eliminating the need for the command-line interface (CLI).
- **Plugin system**: Extend the capabilities of BunkerWeb to meet your own use cases. Seamlessly integrate additional security measures and customize the functionality of BunkerWeb according to your specific requirements.
- **Free as in "freedom"**: BunkerWeb is licensed under the free [AGPLv3 license](https://www.gnu.org/licenses/agpl-3.0.en.html), embracing the principles of freedom and openness. Enjoy the freedom to use, modify, and distribute the software, backed by a supportive community.
- **Professional services**: Get technical support, tailored consulting, and custom development directly from the maintainers of BunkerWeb. Visit the [Bunker Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=github) for more information.

## Security features

A non-exhaustive list of security features:

- **HTTPS** support with transparent **Let's Encrypt** automation
- **State-of-the-art web security**: HTTP security headers, prevent leaks, TLS hardening, ...
- Integrated **ModSecurity WAF** with the **OWASP Core Rule Set**
- **Automatic ban** of strange behaviors based on HTTP status codes
- Apply **connection and request limits** for clients
- **Block bots** by asking them to solve a **challenge** (e.g., cookie, JavaScript, captcha, hCaptcha, or reCAPTCHA)
- **Block known bad IPs** with external blacklists and DNSBL
- And much more...

Learn more about the core security features in the [security tuning](https://docs.bunkerweb.io/1.6.7~rc1/advanced/?utm_campaign=self&utm_source=github#security-tuning) section of the documentation.

## Demo

https://github.com/user-attachments/assets/6fc0e3c1-d353-4a84-bad0-15bf9b6623a5

A demo website protected with BunkerWeb is available at [demo.bunkerweb.io](https://demo.bunkerweb.io/?utm_campaign=self&utm_source=github). Feel free to visit it and perform some security tests.

## Web UI

https://github.com/user-attachments/assets/a3ed56f8-c124-4ca9-b8b3-4be0913b3078

BunkerWeb offers an optional [user interface](web-ui.md) to manage your instances and their configurations. An online read-only demo is available at [demo-ui.bunkerweb.io](https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=doc), feel free to test it yourself.

## BunkerWeb Cloud

Don't want to self-host and manage your own BunkerWeb instance(s)? You might be interested in BunkerWeb Cloud, our fully managed SaaS offering for BunkerWeb.

Order your [BunkerWeb Cloud instance](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=doc) and get access to:

- A fully managed BunkerWeb instance hosted in our cloud
- All BunkerWeb features, including PRO ones
- A monitoring platform with dashboards and alerts
- Technical support to assist you with configuration

If you are interested in the BunkerWeb Cloud offering, don't hesitate to [contact us](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) so we can discuss your needs.

## PRO version

Want to quickly test BunkerWeb PRO for one month? Use the code `freetrial` when placing your order on the [BunkerWeb panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) or by clicking [here](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc) to directly to apply the promo code (will be effective at checkout).

When using BunkerWeb, you have the choice of the version you want to use: open-source or PRO.

Whether it's enhanced security, an enriched user experience, or technical monitoring, the BunkerWeb PRO version allows you to fully benefit from BunkerWeb and meet your professional needs.

In the documentation or the user interface, PRO features are annotated with a crown <img src="https://docs.bunkerweb.io/1.6.7~rc1/assets/img/pro-icon.svg" alt="crown pro icon" height="32px" width="32px"> to distinguish them from those integrated into the open-source version.

You can upgrade from the open-source version to the PRO one easily and at any time. The process is straightforward:

- Claim your [free trial on the BunkerWeb panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) by using the `freetrial` promo code at checkout
- Once connected to the client area, copy your PRO license key
- Paste your license key into BunkerWeb using the [web UI](https://docs.bunkerweb.io/1.6.7~rc1/web-ui/#upgrade-to-pro) or a [specific setting](https://docs.bunkerweb.io/1.6.7~rc1/features/#pro)

Do not hesitate to visit the [BunkerWeb panel](https://panel.bunkerweb.io/knowledgebase?utm_campaign=self&utm_source=doc) or [contact us](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) if you have any questions regarding the PRO version.

## Professional services

Get the most out of BunkerWeb by getting professional services directly from the maintainers of the project. From technical support to tailored consulting and development, we are here to assist you in the security of your web services.

You will find more information by visiting the [BunkerWeb Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc), our dedicated platform for professional services.

Don't hesitate to [contact us](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) if you have any questions; we will be more than happy to respond to your needs.

## Ecosystem, community, and resources

Official websites, tools, and resources about BunkerWeb:

- [**Website**](https://www.bunkerweb.io/?utm_campaign=self&utm_source=doc): get more information, news, and articles about BunkerWeb
- [**Panel**](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc): dedicated platform to order and manage professional services (e.g., technical support) around BunkerWeb
- [**Documentation**](https://docs.bunkerweb.io): technical documentation of the BunkerWeb solution
- [**Demo**](https://demo.bunkerweb.io/?utm_campaign=self&utm_source=doc): demonstration website of BunkerWeb, don't hesitate to attempt attacks to test the robustness of the solution
- [**Web UI**](https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=doc): online read-only demo of the web UI of BunkerWeb
- [**Threatmap**](https://www.bunkerweb.io/threatmap/?utm_campaign=self&utm_source=doc): live cyber attack blocked by BunkerWeb instances all around the world

Community and social networks:

- [**Discord**](https://discord.com/invite/fTf46FmtyD)
- [**LinkedIn**](https://www.linkedin.com/company/bunkerity/)
- [**Twitter**](https://twitter.com/bunkerity)
- [**Reddit**](https://www.reddit.com/r/BunkerWeb/)

# Concepts

<p align="center">
	<img alt="Concepts banner" src="https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/docs/assets/img/concepts.svg" />
</p>

You will find more information about the key concepts of BunkerWeb in the [documentation](https://docs.bunkerweb.io/1.6.7~rc1/concepts/?utm_campaign=self&utm_source=github).

## Integrations

The first concept is the integration of BunkerWeb into the target environment. We prefer to use the word "integration" instead of "installation" because one of the goals of BunkerWeb is to integrate seamlessly into existing environments.

The following integrations are officially supported:

- [Docker](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#docker)
- [Linux](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#linux)
- [Docker autoconf](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#docker-autoconf)
- [Kubernetes](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#kubernetes)
- [Swarm](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#swarm)
- [Microsoft Azure](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#microsoft-azure)

## Settings

Once BunkerWeb is integrated into your environment, you will need to configure it to serve and protect your web applications.

The configuration of BunkerWeb is done by using what we call the "settings" or "variables." Each setting is identified by a name such as `AUTO_LETS_ENCRYPT` or `USE_ANTIBOT`. You can assign values to the settings to configure BunkerWeb.

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

## Multisite mode

The multisite mode is a crucial concept to understand when using BunkerWeb. Because the goal is to protect web applications, we intrinsically inherit the concept of "virtual host" or "vhost" (more info [here](https://en.wikipedia.org/wiki/Virtual_hosting)) which makes it possible to serve multiple web applications from a single (or a cluster of) instance.

By default, the multisite mode of BunkerWeb is disabled, which means that only one web application will be served and all the settings will be applied to it. The typical use case is when you have a single application to protect: you don't have to worry about the multisite, and the default behavior should be the right one for you.

When multisite mode is enabled, BunkerWeb will serve and protect multiple web applications. Each web application is identified by a unique server name and has its own set of settings. The typical use case is when you have multiple applications to protect and you want to use a single (or a cluster depending on the integration) instance of BunkerWeb.

## Custom configurations

Because meeting all the use cases only using the settings is not an option (even with [external plugins](https://docs.bunkerweb.io/1.6.7~rc1/plugins/?utm_campaign=self&utm_source=github)), you can use custom configurations to solve your specific challenges.

Under the hood, BunkerWeb uses the notorious NGINX web server, that's why you can leverage its configuration system for your specific needs. Custom NGINX configurations can be included in different [contexts](https://docs.nginx.com/nginx/admin-guide/basic-functionality/managing-configuration-files/#contexts) like HTTP or server (all servers and/or specific server block).

Another core component of BunkerWeb is the ModSecurity Web Application Firewall: you can also use custom configurations to fix some false positives or add custom rules, for example.

## Database

<p align="center">
	<img alt="Database model" src="https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/docs/assets/img/bunkerweb_db.svg" />
</p>

The state of the current configuration of BunkerWeb is stored in a backend database which contains the following data:

- Settings defined for all the services
- Custom configurations
- BunkerWeb instances
- Metadata about job execution
- Cached files

The following backend databases are supported: SQLite, MariaDB, MySQL, and PostgreSQL.

## Scheduler

To make things automagically work together, a dedicated service called the scheduler is in charge of:

- Storing the settings and custom configurations inside the database
- Executing various tasks (called jobs)
- Generating a configuration which is understood by BunkerWeb
- Being the intermediary for other services (like web UI or autoconf)

In other words, the scheduler is the brain of BunkerWeb.

# Setup

<!--## BunkerWeb Cloud

<p align="center">
	<img alt="Docker banner" src="https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/docs/assets/img/bunkerweb-cloud.webp" />
</p>

BunkerWeb Cloud is the easiest way to get started with BunkerWeb. It offers you a fully managed BunkerWeb service with no hassle. Think of it like a BunkerWeb-as-a-Service!

You will find more information about BunkerWeb Cloud beta [here](https://www.bunkerweb.io/cloud?utm_campaign=self&utm_source=docs) and you can apply for free [in the BunkerWeb panel](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=docs).
-->
## Linux

<p align="center">
	<img alt="Linux banner" src="https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/docs/assets/img/integration-linux.svg" />
</p>

List of supported Linux distros:

- Debian 12 "Bookworm"
- Debian 13 "Trixie"
- Ubuntu 22.04 "Jammy"
- Ubuntu 24.04 "Noble"
- Fedora 41
- Fedora 42
- RHEL 8.10
- RHEL 9.6
- RHEL 10.0

You will find more information in the [Linux section](https://docs.bunkerweb.io/1.5.10/integrations/?utm_campaign=self&utm_source=github#linux) of the documentation.

## Docker

<p align="center">
	<img alt="Docker banner" src="https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/docs/assets/img/integration-docker.svg" />
</p>

We provide ready-to-use prebuilt images for x64, x86, armv7, and arm64 platforms on [Docker Hub](https://hub.docker.com/u/bunkerity).

Docker integration key concepts are:

- **Environment variables** to configure BunkerWeb
- **Scheduler** container to store configuration and execute jobs
- **Networks** to expose ports for clients and connect to upstream web services

You will find more information in the [Docker integration section](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#docker) of the documentation.

## Docker autoconf

<p align="center">
	<img alt="Docker autoconf banner" src="https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/docs/assets/img/integration-autoconf.svg" />
</p>

The downside of using environment variables is that the container needs to be recreated each time there is an update, which is not very convenient. To counter that issue, you can use another image called **autoconf** which will listen for Docker events and automatically reconfigure BunkerWeb in real-time without recreating the container.

Instead of defining environment variables for the BunkerWeb container, you simply add **labels** to your web applications containers and the **autoconf** will "automagically" take care of the rest.

You will find more information in the [Docker autoconf section](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#docker-autoconf) of the documentation.

## Kubernetes

<p align="center">
	<img alt="Kubernetes banner" src="https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/docs/assets/img/integration-kubernetes.svg" />
</p>

The autoconf acts as an [Ingress controller](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/) and will configure the BunkerWeb instances according to the [Ingress resources](https://kubernetes.io/docs/concepts/services-networking/ingress/). It also monitors other Kubernetes objects like [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) for custom configurations.

The official [Helm chart](https://helm.sh/) for BunkerWeb is available in the [bunkerity/bunkerweb-helm repository](https://github.com/bunkerity/bunkerweb-helm).

You will find more information in the [Kubernetes section](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#kubernetes) of the documentation.

## Microsoft Azure

<p align="center">
	<img alt="Azure banner" src="https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/docs/assets/img/integration-azure.webp" />
</p>

BunkerWeb is referenced in the [Azure Marketplace](https://azuremarketplace.microsoft.com/fr-fr/marketplace/apps/bunkerity.bunkerweb?tab=Overview) and an ARM template is available in the [misc folder](https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/misc/integrations/azure-arm-template.json).

You will find more information in the [Microsoft Azure section](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#microsoft-azure) of the documentation.

## Swarm

<p align="center">
	<img alt="Swarm banner" src="https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/docs/assets/img/integration-swarm.svg" />
</p>

To automatically configure BunkerWeb instances, a special service, called **autoconf** will listen for Docker Swarm events like service creation or deletion and automatically configure the **BunkerWeb instances** in real-time without downtime.

Like the [Docker autoconf integration](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#docker-autoconf), configuration for web services is defined using labels starting with the special **bunkerweb.** prefix.

You will find more information in the [Swarm section](https://docs.bunkerweb.io/1.6.7~rc1/integrations/?utm_campaign=self&utm_source=github#swarm) of the documentation.

# Quickstart guide

Once you have set up BunkerWeb with the integration of your choice, you can follow the [quickstart guide](https://docs.bunkerweb.io/1.6.7~rc1/quickstart-guide/?utm_campaign=self&utm_source=github) that will cover the installation and first configuration to protect a web service.

# Security tuning

BunkerWeb offers many security features that you can configure with [features](https://docs.bunkerweb.io/1.6.7~rc1/features/?utm_campaign=self&utm_source=github). Even if the default values of settings ensure a minimal "security by default," we strongly recommend you to tune them. By doing so, you will be able to ensure a security level of your choice but also manage false positives.

You will find more information in the [security tuning section](https://docs.bunkerweb.io/1.6.7~rc1/advanced/?utm_campaign=self&utm_source=github#security-tuning) of the documentation.

# Settings

As a general rule, when multisite mode is enabled, if you want to apply settings with multisite context to a specific server, you will need to add the primary (first) server name as a prefix like `www.example.com_USE_ANTIBOT=captcha` or `myapp.example.com_USE_GZIP=yes`, for example.

When settings are considered as "multiple," it means that you can have multiple groups of settings for the same feature by adding numbers as suffixes like `REVERSE_PROXY_URL_1=/subdir`, `REVERSE_PROXY_HOST_1=http://myhost1`, `REVERSE_PROXY_URL_2=/anotherdir`, `REVERSE_PROXY_HOST_2=http://myhost2`, ... for example.

Check the [features section](https://docs.bunkerweb.io/1.6.7~rc1/features/?utm_campaign=self&utm_source=github) of the documentation to get the full list.

# Web UI

https://github.com/user-attachments/assets/a3ed56f8-c124-4ca9-b8b3-4be0913b3078

The "Web UI" is a web application that helps you manage your BunkerWeb instance using a user-friendly interface instead of the command-line one.

Here is the list of features offered by the web UI:

- Get a comprehensive view of the blocked attacks
- Start, stop, restart, and reload your BunkerWeb instance
- Add, edit, and delete settings for your web applications
- Add, edit, and delete custom configurations for NGINX and ModSecurity
- Install and uninstall external plugins
- Explore the cached files
- Monitor job execution and restart them when needed
- View the logs and search patterns

You will find more information in the [Web UI section](https://docs.bunkerweb.io/1.6.7~rc1/web-ui/?utm_campaign=self&utm_source=github) of the documentation.

# Plugins

BunkerWeb comes with a plugin system to make it possible to easily add new features. Once a plugin is installed, you can manage it using additional settings defined by the plugin.

Here is the list of "official" plugins that we maintain (see the [bunkerweb-plugins](https://github.com/bunkerity/bunkerweb-plugins/?utm_campaign=self&utm_source=github) repository for more information):

|      Name      | Version | Description                                                                                                                      |                                                Link                                                 |
| :------------: | :-----: | :------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------: |
|   **ClamAV**   |   1.9   | Automatically scans uploaded files with the ClamAV antivirus engine and denies the request when a file is detected as malicious. |     [bunkerweb-plugins/clamav](https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav)     |
|   **Coraza**   |   1.9   | Inspect requests using the Coraza WAF (alternative of ModSecurity).                                                              |     [bunkerweb-plugins/coraza](https://github.com/bunkerity/bunkerweb-plugins/tree/main/coraza)     |
|  **Discord**   |   1.9   | Send security notifications to a Discord channel using a Webhook.                                                                |    [bunkerweb-plugins/discord](https://github.com/bunkerity/bunkerweb-plugins/tree/main/discord)    |
|   **Slack**    |   1.9   | Send security notifications to a Slack channel using a Webhook.                                                                  |      [bunkerweb-plugins/slack](https://github.com/bunkerity/bunkerweb-plugins/tree/main/slack)      |
| **VirusTotal** |   1.9   | Automatically scans uploaded files with the VirusTotal API and denies the request when a file is detected as malicious.          | [bunkerweb-plugins/virustotal](https://github.com/bunkerity/bunkerweb-plugins/tree/main/virustotal) |
|  **WebHook**   |   1.9   | Send security notifications to a custom HTTP endpoint using a Webhook.                                                           |    [bunkerweb-plugins/webhook](https://github.com/bunkerity/bunkerweb-plugins/tree/main/webhook)    |

You will find more information in the [plugins section](https://docs.bunkerweb.io/1.6.7~rc1/plugins/?utm_campaign=self&utm_source=github) of the documentation.

# Language Support & Localization

BunkerWeb UI supports multiple languages. Translations are managed in the `src/ui/app/static/locales` directory. The following languages are currently available:

- English (en)
- French (fr)
- Arabic (ar)
- Bengali (bn)
- Spanish (es)
- Hindi (hi)
- Portuguese (pt)
- Russian (ru)
- Urdu (ur)
- Chinese (zh)
- German (de)
- Italian (it)
- Turkish (tr)

See the [locales/README.md](https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/src/ui/app/static/locales/README.md) for details on translation provenance and review status.

## Contributing Translations

We welcome contributions to improve or add new locale files!

**How to contribute a translation:**

1. Edit the `src/ui/app/lang_config.py` file to add your language (code, name, flag, english_name).
2. Copy `en.json` as a template in `src/ui/app/static/locales/`, rename it to your language code (e.g., `de.json` for German).
3. Translate the values in your new file.
4. Update the table in `locales/README.md` to add your language and indicate who created/reviewed it.
5. Submit a pull request.

For updates, edit the relevant file and update the provenance table as needed.

See the [locales/README.md](https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/src/ui/app/static/locales/README.md) for full guidelines.

# Support

## Professional

Get technical support directly from the BunkerWeb maintainers. You will find more information by visiting the [BunkerWeb Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=github), our dedicated platform for professional services.

Don't hesitate to [contact us](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=github) if you have any questions; we will be more than happy to respond to your needs.

## Community

To get free community support, you can use the following media:

- The #help channel of BunkerWeb in the [Discord server](https://discord.com/invite/fTf46FmtyD)
- The help category of [GitHub discussions](https://github.com/bunkerity/bunkerweb/discussions)
- The [/r/BunkerWeb](https://www.reddit.com/r/BunkerWeb) subreddit
- The [Server Fault](https://serverfault.com/) and [Super User](https://superuser.com/) forums

Please don't use [GitHub issues](https://github.com/bunkerity/bunkerweb/issues) to ask for help; use it only for bug reports and feature requests.

# License

This project is licensed under the terms of the [GNU Affero General Public License (AGPL) version 3](https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/LICENSE.md).

# Contribute

If you would like to contribute to the plugins, you can read the [contributing guidelines](https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/CONTRIBUTING.md) to get started.

# Security policy

We take security bugs as serious issues and encourage responsible disclosure; see our [security policy](https://github.com/bunkerity/bunkerweb/raw/v1.6.7-rc1/SECURITY.md) for more information.

# Star History

<a href="https://star-history.com/#bunkerity/bunkerweb&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=bunkerity/bunkerweb&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=bunkerity/bunkerweb&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=bunkerity/bunkerweb&type=Date" />
 </picture>
</a>
