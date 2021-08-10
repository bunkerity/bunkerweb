# Introduction

<p align="center">
	<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/logo.png?raw=true" width="425" />
</p>

> Make security by default great again !

bunkerized-nginx is a web server based on the notorious nginx and focused on security. It integrates into existing environments (Linux, Docker, Swarm, Kubernetes, ...) to make your web services "secured by default" without any hassle. The security best practices are automatically applied for you while keeping control of every settings to meet your own use case.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/overview.png?raw=true" />

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

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/docs/img/demo.gif?raw=true" />

You can find a live demo at https://demo-nginx.bunkerity.com, feel free to do some security tests.
