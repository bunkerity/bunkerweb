# Introduction

## Overview

<figure markdown>
  ![Overview](assets/img/intro-overview.svg){ align=center, width="800" }
  <figcaption>Make your web services secure by default !</figcaption>
</figure>

BunkerWeb is a next-generation and open-source Web Application Firewall (WAF).

Being a full-featured web server (based on [NGINX](https://nginx.org/) under the hood), it will protect your web services to make them "secure by default". BunkerWeb integrates seamlessly into your existing environments ([Linux](integrations.md#linux), [Docker](integrations.md#docker), [Swarm](integrations.md#swarm), [Kubernetes](integrations.md#kubernetes), …) and is fully configurable (don't panic, there is an [awesome web UI](web-ui.md) if you don't like the CLI) to meet your own use-cases . In other words, cybersecurity is no more a hassle.

BunkerWeb contains primary [security features](security-tuning.md) as part of the core but can be easily extended with additional ones thanks to a [plugin system](plugins.md)).

## Why BunkerWeb ?

- **Easy integration into existing environments** : support for Linux, Docker, Swarm, Kubernetes, Ansible, Vagrant, ...
- **Highly customizable** : enable, disable and configure features easily to meet your use case
- **Secure by default** : offers out-of-the-box and hassle-free minimal security for your web services
- **Awesome web UI** : keep control of everything more efficiently without the need of the CLI
- **Plugin system** : extend BunkerWeb to meet your own use-cases
- **Free as in "freedom"** : licensed under the free [AGPLv3 license](https://www.gnu.org/licenses/agpl-3.0.en.html)

## Security features

A non-exhaustive list of security features :

- **HTTPS** support with transparent **Let's Encrypt** automation
- **State-of-the-art web security** : HTTP security headers, prevent leaks, TLS hardening, ...
- Integrated **ModSecurity WAF** with the **OWASP Core Rule Set**
- **Automatic ban** of strange behaviors based on HTTP status code
- Apply **connections and requests limit** for clients
- **Block bots** by asking them to solve a **challenge** (e.g. : cookie, javascript, captcha, hCaptcha or reCAPTCHA)
- **Block known bad IPs** with external blacklists and DNSBL
- And much more ...

Learn more about the core security features in the [security tuning](security-tuning.md) section of the documentation.

## Demo

<p align="center">
	<iframe style="display: block;" width="560" height="315" src="https://www.youtube-nocookie.com/embed/ZhYV-QELzA4" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

A demo website protected with BunkerWeb is available at [demo.bunkerweb.io](https://demo.bunkerweb.io). Feel free to visit it and perform some security tests.
