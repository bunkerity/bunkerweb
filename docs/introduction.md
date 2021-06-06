# Introduction

<p align="center">
	<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/logo.png?raw=true" width="425" />
</p>

nginx Docker image secure by default.  

Avoid the hassle of following security best practices "by hand" each time you need a web server or reverse proxy. Bunkerized-nginx provides generic security configs, settings and tools so you don't need to do it yourself.

Non-exhaustive list of features :
- HTTPS support with transparent Let's Encrypt automation
- State-of-the-art web security : HTTP security headers, prevent leaks, TLS hardening, ...
- Integrated ModSecurity WAF with the OWASP Core Rule Set
- Automatic ban of strange behaviors
- Antibot challenge through cookie, javascript, captcha or recaptcha v3
- Block TOR, proxies, bad user-agents, countries, ...
- Block known bad IP with DNSBL and CrowdSec
- Prevent bruteforce attacks with rate limiting
- Plugins system for external security checks (e.g. : ClamAV)
- Easy to configure with environment variables or web UI
- Automatic configuration with container labels
- Docker Swarm support

Fooling automated tools/scanners :

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/demo.gif?raw=true" />

You can find a live demo at <a href="https://demo-nginx.bunkerity.com" target="_blank">https://demo-nginx.bunkerity.com</a>, feel free to do some security tests.
