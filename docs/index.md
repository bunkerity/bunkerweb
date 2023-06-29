# Introduction

## Overview

<figure markdown>
  ![Overview](assets/img/intro-overview.svg){ align=center, width="800" }
  <figcaption>Make your web services secure by default !</figcaption>
</figure>

Introducing BunkerWeb, the **cutting-edge** and **open-source Web Application Firewall** (WAF) that will revolutionize your web security experience.

With BunkerWeb, your web services are safeguarded by default, providing you with peace of mind and enhanced protection. Powered by [NGINX](https://nginx.org/), this comprehensive web server combines advanced features seamlessly, ensuring your online assets remain secure.

BunkerWeb effortlessly integrates into your existing environments, whether it's [Linux](integrations.md#linux), [Docker](integrations.md#docker), [Swarm](integrations.md#swarm), [Kubernetes](integrations.md#kubernetes), or more. Its versatility allows for easy configuration to suit your specific requirements. Don't worry if you prefer a user-friendly interface—BunkerWeb offers an exceptional [web UI](web-ui.md) alongside the command-line interface (CLI), ensuring accessibility for all users.

Experience the transformation in cybersecurity, where complexities and obstacles are a thing of the past. With BunkerWeb, fortifying your digital assets has never been more delightful and hassle-free.

Furthermore, BunkerWeb boasts a comprehensive set of primary [security features](security-tuning.md) at its core. However, what sets it apart is its remarkable flexibility through an intuitive [plugin system](plugins.md). This ingenious design empowers you to effortlessly enhance BunkerWeb with additional security measures, ensuring a tailored and robust defense for your web applications.

By seamlessly integrating new plugins into BunkerWeb, you can customize and expand its capabilities to address specific security requirements unique to your environment. Whether you need to strengthen authentication protocols, bolster threat detection, or implement specialized security measures, BunkerWeb's [plugin system](plugins.md) grants you the freedom to fortify your web infrastructure with ease.

With BunkerWeb's dynamic [plugin system](plugins.md), security becomes an enjoyable journey of exploration and empowerment. Discover the endless possibilities and create a fortified web environment that perfectly aligns with your needs.


## Why BunkerWeb ?

- **Easy integration into existing environments** : Seamlessly integrate BunkerWeb into various environments such as Linux, Docker, Swarm, Kubernetes, Ansible, Vagrant, and more. Enjoy a smooth transition and hassle-free implementation.

- **Highly customizable** : Tailor BunkerWeb to your specific requirements with ease. Enable, disable, and configure features effortlessly, allowing you to customize the security settings according to your unique use case.

- **Secure by default** : BunkerWeb provides out-of-the-box, hassle-free minimal security for your web services. Experience peace of mind and enhanced protection right from the start.

- **Awesome web UI** : Take control of BunkerWeb more efficiently with the exceptional web user interface (UI). Navigate settings and configurations effortlessly through a user-friendly graphical interface, eliminating the need for the command-line interface (CLI).

- **Plugin system** : Extend the capabilities of BunkerWeb to meet your own use cases. Seamlessly integrate additional security measures and customize the functionality of BunkerWeb according to your specific requirements.

- **Free as in "freedom"** : BunkerWeb is licensed under the free [AGPLv3 license](https://www.gnu.org/licenses/agpl-3.0.en.html), embracing the principles of freedom and openness. Enjoy the freedom to use, modify, and distribute the software, backed by a supportive community.

## Security features

Explore the impressive array of security features offered by BunkerWeb. While not exhaustive, here are some notable highlights:

- **HTTPS** support with transparent **Let's Encrypt** automation : Easily secure your web services with automated Let's Encrypt integration, ensuring encrypted communication between clients and your server.

- **State-of-the-art web security** : Benefit from cutting-edge web security measures, including comprehensive HTTP security headers, prevention of data leaks, and TLS hardening techniques.

- Integrated **ModSecurity WAF** with the **OWASP Core Rule Set** : Enjoy enhanced protection against web application attacks with the integration of ModSecurity, fortified by the renowned OWASP Core Rule Set.

- **Automatic ban** of strange behaviors based on HTTP status code : BunkerWeb intelligently identifies and blocks suspicious activities by automatically banning behaviors that trigger abnormal HTTP status codes.

- Apply **connections and requests limit** for clients : Set limits on the number of connections and requests from clients, preventing resource exhaustion and ensuring fair usage of server resources.

- **Block bots** with **challenge-based verification** : Keep malicious bots at bay by challenging them to solve puzzles such as cookies, JavaScript tests, captcha, hCaptcha, reCAPTCHA or Turnstile, effectively blocking unauthorized access.

- **Block known bad IPs** with external blacklists and DNSBL : Utilize external blacklists and DNS-based blackhole lists (DNSBL) to proactively block known malicious IP addresses, bolstering your defense against potential threats.

- **And much more...** : BunkerWeb is packed with a plethora of additional security features that go beyond this list, providing you with comprehensive protection and peace of mind.

To delve deeper into the core security features, we invite you to explore the [security tuning](security-tuning.md) section of the documentation. Discover how BunkerWeb empowers you to fine-tune and optimize security measures according to your specific needs.

## Demo

<p align="center">
	<iframe style="display: block;" width="560" height="315" src="https://www.youtube-nocookie.com/embed/ZhYV-QELzA4" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

A demo website protected with BunkerWeb is available at [demo.bunkerweb.io](https://demo.bunkerweb.io). Feel free to visit it and perform some security tests.
