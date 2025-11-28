# Introduction

## Overview

<figure markdown>
  ![Overview](assets/img/intro-overview.svg){ align=center, width="800" }
  <figcaption>Make your web services secure by default!</figcaption>
</figure>

BunkerWeb is a next-generation, open-source Web Application Firewall (WAF).

As a full-featured web server (based on [NGINX](https://nginx.org/) under the hood), it protects your web services to make them "secure by default." BunkerWeb integrates seamlessly into your existing environments ([Linux](integrations.md#linux), [Docker](integrations.md#docker), [Swarm](integrations.md#swarm), [Kubernetes](integrations.md#kubernetes), …) as a reverse proxy and is fully configurable (don't panic, there is an [awesome web UI](web-ui.md) if you don't like the CLI) to meet your specific use cases. In other words, cybersecurity is no longer a hassle.

BunkerWeb includes primary [security features](advanced.md#security-tuning) as part of the core but can be easily extended with additional ones thanks to a [plugin system](plugins.md).

## Why BunkerWeb?

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/oybLtyhWJIo" title="BunkerWeb overview" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

- **Easy integration into existing environments**: Seamlessly integrate BunkerWeb into various environments such as Linux, Docker, Swarm, Kubernetes, and more. Enjoy a smooth transition and hassle-free implementation.

- **Highly customizable**: Tailor BunkerWeb to your specific requirements with ease. Enable, disable, and configure features effortlessly, allowing you to customize the security settings according to your unique use case.

- **Secure by default**: BunkerWeb provides out-of-the-box, hassle-free minimal security for your web services. Experience peace of mind and enhanced protection right from the start.

- **Awesome web UI**: Take control of BunkerWeb more efficiently with the exceptional web user interface (UI). Navigate settings and configurations effortlessly through a user-friendly graphical interface, eliminating the need for the command-line interface (CLI).

- **Plugin system**: Extend the capabilities of BunkerWeb to meet your own use cases. Seamlessly integrate additional security measures and customize the functionality of BunkerWeb according to your specific requirements.

- **Free as in "freedom"**: BunkerWeb is licensed under the free [AGPLv3 license](https://www.gnu.org/licenses/agpl-3.0.en.html), embracing the principles of freedom and openness. Enjoy the freedom to use, modify, and distribute the software, backed by a supportive community.

- **Professional services**: Get technical support, tailored consulting, and custom development directly from the maintainers of BunkerWeb. Visit the [BunkerWeb Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc) for more information.

## Security features

Explore the impressive array of security features offered by BunkerWeb. While not exhaustive, here are some notable highlights:

- **HTTPS** support with transparent **Let's Encrypt** automation: Easily secure your web services with automated Let's Encrypt integration, ensuring encrypted communication between clients and your server.

- **State-of-the-art web security**: Benefit from cutting-edge web security measures, including comprehensive HTTP security headers, prevention of data leaks, and TLS hardening techniques.

- Integrated **ModSecurity WAF** with the **OWASP Core Rule Set**: Enjoy enhanced protection against web application attacks with the integration of ModSecurity, fortified by the renowned OWASP Core Rule Set.

- **Automatic ban** of strange behaviors based on HTTP status codes: BunkerWeb intelligently identifies and blocks suspicious activities by automatically banning behaviors that trigger abnormal HTTP status codes.

- Apply **connection and request limits** for clients: Set limits on the number of connections and requests from clients, preventing resource exhaustion and ensuring fair usage of server resources.

- **Block bots** with **challenge-based verification**: Keep malicious bots at bay by challenging them to solve puzzles such as cookies, JavaScript tests, captchas, hCaptcha, reCAPTCHA, or Turnstile, effectively blocking unauthorized access.

- **Block known bad IPs** with external blacklists and **DNSBL**: Utilize external blacklists and DNS-based blackhole lists (DNSBL) to proactively block known malicious IP addresses, bolstering your defense against potential threats.

- **And much more...**: BunkerWeb is packed with a plethora of additional security features that go beyond this list, providing you with comprehensive protection and peace of mind.

To delve deeper into the core security features, we invite you to explore the [security tuning](advanced.md#security-tuning) section of the documentation. Discover how BunkerWeb empowers you to fine-tune and optimize security measures according to your specific needs.

## Demo

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/ZhYV-QELzA4" title="Fooling automated tools and scanners" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

A demo website protected with BunkerWeb is available at [demo.bunkerweb.io](https://demo.bunkerweb.io/?utm_campaign=self&utm_source=doc). Feel free to visit it and perform some security tests.

## Web UI

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/tGS3pzquEjY" title="BunkerWeb web UI" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

BunkerWeb offers an optional [user interface](web-ui.md) to manage your instances and their configurations. An online read-only demo is available at [demo-ui.bunkerweb.io](https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=doc). Feel free to test it yourself.

## BunkerWeb Cloud

<figure markdown>
  ![Overview](assets/img/bunkerweb-cloud.png){ align=center, width="600" }
  <figcaption>BunkerWeb Cloud</figcaption>
</figure>

Don't want to self-host and manage your own BunkerWeb instance(s)? You might be interested in BunkerWeb Cloud, our fully managed SaaS offering for BunkerWeb.

Order your [BunkerWeb Cloud instance](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=doc) and get access to:

- A fully managed BunkerWeb instance hosted in our cloud
- All BunkerWeb features, including PRO ones
- A monitoring platform with dashboards and alerts
- Technical support to assist you with configuration

If you are interested in the BunkerWeb Cloud offering, don't hesitate to [contact us](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) so we can discuss your needs.

## PRO version

!!! tip "BunkerWeb PRO free trial"
    Want to quickly test BunkerWeb PRO for one month? Use the code `freetrial` when placing your order on the [BunkerWeb Panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) or by clicking [here](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc) to directly to apply the promo code (will be effective at checkout).

When using BunkerWeb, you have the choice of the version you want to use: open-source or PRO.

Whether it's enhanced security, an enriched user experience, or technical monitoring, the BunkerWeb PRO version allows you to fully benefit from BunkerWeb and meet your professional needs.

In the documentation or the user interface, PRO features are annotated with a crown <img src="assets/img/pro-icon.svg" alt="crown pro icon" height="32px" width="32px"> to distinguish them from those integrated into the open-source version.

You can upgrade from the open-source version to the PRO one easily and at any time. The process is straightforward:

- Claim your [free trial on the BunkerWeb panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) by using the `freetrial` promo code at checkout
- Once connected to the client area, copy your PRO license key
- Paste your private key into BunkerWeb using the [web UI](web-ui.md#upgrade-to-pro) or [specific setting](features.md#pro)

Do not hesitate to visit the [BunkerWeb panel](https://panel.bunkerweb.io/knowledgebase?utm_campaign=self&utm_source=doc) or [contact us](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) if you have any questions regarding the PRO version.

## Professional services

Get the most out of BunkerWeb by accessing professional services directly from the maintainers of the project. From technical support to tailored consulting and development, we are here to assist you in securing your web services.

You will find more information by visiting the [BunkerWeb Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc), our dedicated platform for professional services.

Don't hesitate to [contact us](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) if you have any questions. We will be more than happy to respond to your needs.

## Ecosystem, community, and resources

Official websites, tools, and resources about BunkerWeb:

- [**Website**](https://www.bunkerweb.io/?utm_campaign=self&utm_source=doc): Get more information, news, and articles about BunkerWeb.
- [**Panel**](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc): A dedicated platform to order and manage professional services (e.g., technical support) around BunkerWeb.
- [**Documentation**](https://docs.bunkerweb.io): Technical documentation of the BunkerWeb solution.
- [**Demo**](https://demo.bunkerweb.io/?utm_campaign=self&utm_source=doc): Demonstration website of BunkerWeb. Don't hesitate to attempt attacks to test the robustness of the solution.
- [**Web UI**](https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=doc): Online read-only demo of the web UI of BunkerWeb.
- [**Threatmap**](https://www.bunkerweb.io/threatmap/?utm_campaign=self&utm_source=doc): Live cyberattacks blocked by BunkerWeb instances all around the world.
- [**Status**](https://status.bunkerweb.io/?utm_campaign=self&utm_source=doc): Live health and availability updates for BunkerWeb services.

Community and social networks:

- [**Discord**](https://discord.com/invite/fTf46FmtyD)
- [**LinkedIn**](https://www.linkedin.com/company/bunkerity/)
- [**X (Formerly Twitter)**](https://x.com/bunkerity)
- [**Reddit**](https://www.reddit.com/r/BunkerWeb/)
