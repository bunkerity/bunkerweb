# bunkerized-nginx

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/logo.png?raw=true" width="425" />

<img src="https://img.shields.io/badge/nginx-1.18.0-blue" /> <img src="https://img.shields.io/docker/cloud/build/bunkerity/bunkerized-nginx" /> <img src="https://img.shields.io/github/last-commit/bunkerity/bunkerized-nginx" />

nginx Docker image secure by default.  

Avoid the hassle of following security best practices each time you need a web server or reverse proxy. Bunkerized-nginx provides generic security configs, settings and tools so you don't need to do it yourself.

Non-exhaustive list of features :
- HTTPS support with transparent Let's Encrypt automation
- State-of-the-art web security : HTTP security headers, prevent leaks, TLS hardening, ...
- Integrated ModSecurity WAF with the OWASP Core Rule Set
- Automatic ban of strange behaviors with fail2ban
- Antibot challenge through cookie, javascript, captcha or recaptcha v3
- Block TOR, proxies, bad user-agents, countries, ...
- Perform automatic DNSBL checks to block known bad IP
- Prevent bruteforce attacks with rate limiting
- Detect bad files with ClamAV
- Easy to configure with environment variables

Fooling automated tools/scanners :

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/demo.gif?raw=true" />

# Table of contents
- [bunkerized-nginx](#bunkerized-nginx)
- [Table of contents](#table-of-contents)
- [Live demo](#live-demo)
- [Quickstart guide](#quickstart-guide)
  * [Run HTTP server with default settings](#run-http-server-with-default-settings)
  * [In combination with PHP](#in-combination-with-php)
  * [Run HTTPS server with automated Let's Encrypt](#run-https-server-with-automated-lets-encrypt)
  * [Behind a reverse proxy](#behind-a-reverse-proxy)
  * [As a reverse proxy](#as-a-reverse-proxy)
  * [Antibot challenge](#antibot-challenge)
- [Tutorials and examples](#tutorials-and-examples)
- [List of environment variables](#list-of-environment-variables)
  * [nginx](#nginx)
    + [Misc](#misc)
    + [Information leak](#information-leak)
    + [Custom error pages](#custom-error-pages)
    + [HTTP basic authentication](#http-basic-authentication)
    + [Reverse proxy](#reverse-proxy)
  * [HTTPS](#https)
    + [Let's Encrypt](#let-s-encrypt)
    + [HTTP](#http)
    + [Custom certificate](#custom-certificate)
    + [Self-signed certificate](#self-signed-certificate)
    + [Misc](#misc)
  * [ModSecurity](#modsecurity)
  * [Security headers](#security-headers)
  * [Blocking](#blocking)
    + [Antibot](#antibot)
    + [External blacklist](#external-blacklist)
    + [DNSBL](#dnsbl)
    + [Custom whitelisting](#custom-whitelisting)
    + [Custom blacklisting](#custom-blacklisting)
    + [Requests limiting](#requests-limiting)
    + [Countries](#countries)
  * [PHP](#php)
  * [Fail2ban](#fail2ban)
  * [ClamAV](#clamav)
  * [Misc](#misc-2)
- [Create your own image](#create-your-own-image)
- [Include custom configurations](#include-custom-configurations)

# Live demo
You can find a live demo at https://demo-nginx.bunkerity.com.

# Quickstart guide

## Run HTTP server with default settings

```shell
docker run -p 80:8080 -v /path/to/web/files:/www bunkerity/bunkerized-nginx
```

Web files are stored in the /www directory, the container will serve files from there.

## In combination with PHP

```shell
docker network create mynet
docker run --network mynet -p 80:8080 -v /path/to/web/files:/www -e REMOTE_PHP=myphp -e REMOTE_PHP_PATH=/app bunkerity/bunkerized-nginx
docker run --network mynet --name=myphp -v /path/to/web/files:/app php:fpm
```

The `REMOTE_PHP` environment variable lets you define the address of a remote PHP-FPM instance that will execute the .php files. `REMOTE_PHP_PATH` must be set to the directory where the PHP container will find the files.

## Run HTTPS server with automated Let's Encrypt
```shell
docker run -p 80:8080 -p 443:8443 -v /path/to/web/files:/www -v /where/to/save/certificates:/etc/letsencrypt -e SERVER_NAME=www.yourdomain.com -e AUTO_LETS_ENCRYPT=yes -e REDIRECT_HTTP_TO_HTTPS=yes bunkerity/bunkerized-nginx
```

Certificates are stored in the /etc/letsencrypt directory, you should save it on your local drive.  
If you don't want your webserver to listen on HTTP add the environment variable `LISTEN_HTTP` with a *no* value. But Let's Encrypt needs the port 80 to be opened so redirecting the port is mandatory.

Here you have three environment variables :
- `SERVER_NAME` : define the FQDN of your webserver, this is mandatory for Let's Encrypt (www.yourdomain.com should point to your IP address)
- `AUTO_LETS_ENCRYPT` : enable automatic Let's Encrypt creation and renewal of certificates
- `REDIRECT_HTTP_TO_HTTPS` : enable HTTP to HTTPS redirection

## Behind a reverse proxy
```shell
docker run -p 80:8080 -v /path/to/web/files:/www -e PROXY_REAL_IP=yes bunkerity/bunkerized-nginx
```

The `PROXY_REAL_IP` environment variable, when set to *yes*, activates the [ngx_http_realip_module](https://nginx.org/en/docs/http/ngx_http_realip_module.html) to get the real client IP from the reverse proxy.

See [this section](#reverse-proxy) if you need to tweak some values (trusted ip/network, header, ...).

## As a reverse proxy
You can setup a reverse proxy by adding your own custom configurations at server context.  
For example, this is a dummy reverse proxy configuration :  
```shell
proxy_set_header Host $host;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
location / {
	if ($host = www.website1.com) {
		proxy_pass http://192.168.42.10$request_uri;
	}

	if ($host = www.website2.com) {
		proxy_pass http://192.168.42.11$request_uri;
	}
}
```
All files (ending with .conf) in /server-confs inside the container will be included at server context. You can simply mount a volume where your config files are located :  
```shell
docker run -p 80:8080 -e SERVER_NAME="www.website1.com www.website2.com" -e SERVE_FILES=no -e DISABLE_DEFAULT_SERVER=yes -v /path/to/server/conf:/server-confs bunkerity/bunkerized-nginx
```

Here you have three environment variables :
- `SERVER_NAME` : list of valid Host headers sent by clients
- `SERVE_FILES` : nginx will not serve files from the /www directory
- `DISABLE_DEFAULT_SERVER` : nginx will not respond to requests if Host header is not in the SERVER_NAME list

## Antibot challenge
```shell
docker run -p 80:8080 -v /path/to/web/files:/www -e USE_ANTIBOT=captcha bunkerity/bunkerized-nginx
```

When `USE_ANTIBOT` is set to *captcha*, every users visiting your website must complete a captcha before accessing the pages. Others challenges are also available : *cookie*, *javascript* or *recaptcha* (more info [here](#antibot)).

# Tutorials and examples

You will find some docker-compose.yml examples in the [examples directory](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples) and tutorials about bunkerized-nginx in our [blog](https://www.bunkerity.com/category/bunkerized-nginx/).  

# List of environment variables

## nginx

### Misc

`SERVER_NAME`  
Values : *&lt;first name&gt; &lt;second name&gt; ...*  
Default value : *www.bunkerity.com*  
Sets the host names of the webserver separated with spaces. This must match the Host header sent by clients.  
Useful when used with `AUTO_LETSENCRYPT=yes` and/or `DISABLE_DEFAULT_SERVER=yes`.

`MAX_CLIENT_SIZE`  
Values : *0* | *Xm*  
Default value : *10m*  
Sets the maximum body size before nginx returns a 413 error code.  
Setting to 0 means "infinite" body size.

`ALLOWED_METHODS`  
Values : *allowed HTTP methods separated with | char*  
Default value : *GET|POST|HEAD*  
Only the HTTP methods listed here will be accepted by nginx. If not listed, nginx will close the connection.

`DISABLE_DEFAULT_SERVER`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, nginx will only respond to HTTP request when the Host header match a FQDN specified in the `SERVER_NAME` environment variable.  
For example, it will close the connection if a bot access the site with direct ip.

`SERVE_FILES`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, nginx will serve files from /www directory within the container.  
A use case to not serving files is when you setup bunkerized-nginx as a reverse proxy via a custom configuration.

`DNS_RESOLVERS`  
Values : *\<two IP addresses separated with a space\>*  
Default value : *127.0.0.11 8.8.8.8*  
The IP addresses of the DNS resolvers to use when performing DNS lookups.

`WRITE_ACCESS`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, nginx will be granted write access to the /www directory.  
Set it to yes if your website uses file upload or creates dynamic files for example.

`ROOT_FOLDER`  
Values : *\<any valid path to web files\>  
Default value : */www*  
The default folder where nginx will search for web files. Don't change it unless you want to make your own image.

### Information leak

`SERVER_TOKENS`  
Values : *on* | *off*  
Default value : *off*  
If set to on, nginx will display server version in Server header and default error pages.

`HEADER_SERVER`  
Values : *yes* | *no*  
Default value : *no*  
If set to no, nginx will remove the Server header in HTTP responses.

### Custom error pages

`ERROR_XXX`  
Values : *\<relative path to the error page\>*  
Default value :  
Use this kind of environment variable to define custom error page depending on the HTTP error code. Replace XXX with HTTP code.  
For example : `ERROR_404=/404.html` means the /404.html page will be displayed when 404 code is generated. The path is relative to the root web folder.

### HTTP basic authentication

`USE_AUTH_BASIC`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, enables HTTP basic authentication at the location `AUTH_BASIC_LOCATION` with user `AUTH_BASIC_USER` and password `AUTH_BASIC_PASSWORD`.

`AUTH_BASIC_LOCATION`  
Values : *sitewide* | */somedir* | *\<any valid location\>*  
Default value : *sitewide*  
The location to restrict when `USE_AUTH_BASIC` is set to *yes*. If the special value *sitewide* is used then auth basic will be set at server level outside any location context.

`AUTH_BASIC_USER`  
Values : *\<any valid username\>*  
Default value : *changeme*  
The username allowed to access `AUTH_BASIC_LOCATION` when `USE_AUTH_BASIC` is set to yes.

`AUTH_BASIC_PASSWORD`  
Values : *\<any valid password\>*  
Default value : *changeme*  
The password of `AUTH_BASIC_USER` when `USE_AUTH_BASIC` is set to yes.

`AUTH_BASIC_TEXT`  
Values : *\<any valid text\>*  
Default value : *Restricted area*  
The text displayed inside the login prompt when `USE_AUTH_BASIC` is set to yes.

### Reverse proxy

`PROXY_REAL_IP`  
Values : *yes* | *no*  
Default value : *no*  
Set this environment variable to *yes* if you're using bunkerized-nginx behind a reverse proxy. This means you will see the real client address instead of the proxy one inside your logs. Modsecurity, fail2ban and others security tools will also then work correctly.

`PROXY_REAL_IP_FROM`  
Values : *\<list of trusted IP addresses and/or networks separated with spaces\>*  
Default value : *192.168.0.0/16 172.16.0.0/12 10.0.0.0/8*  
When `PROXY_REAL_IP` is set to *yes*, lets you define the trusted IPs/networks allowed to send the correct client address.

`PROXY_REAL_IP_HEADER`  
Values : *X-Forwarded-For* | *X-Real-IP* | *custom header*  
Default value : *X-Forwarded-For*  
When `PROXY_REAL_IP` is set to *yes*, lets you define the header that contains the real client IP address.

`PROXY_REAL_IP_RECURSIVE`  
Values : *on* | *off*  
Default value : *on*  
When `PROXY_REAL_IP` is set to *yes*, setting this to *on* avoid spoofing attacks using the header defined in `PROXY_REAL_IP_HEADER`.

## HTTPS

### Let's Encrypt

`AUTO_LETS_ENCRYPT`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, automatic certificate generation and renewal will be setup through Let's Encrypt. This will enable HTTPS on your website for free.  
You will need to redirect both 80 and 443 port to your container and also set the `SERVER_NAME` environment variable.

### HTTP

`LISTEN_HTTP`  
Values : *yes* | *no*  
Default value : *yes*  
If set to no, nginx will not in listen on HTTP (port 80).  
Useful if you only want HTTPS access to your website.

`REDIRECT_HTTP_TO_HTTPS`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, nginx will redirect all HTTP requests to HTTPS.  

### Custom certificate

`USE_CUSTOM_HTTPS`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, HTTPS will be enabled with certificate/key of your choice.  

`CUSTOM_HTTPS_CERT`  
Values : *\<any valid path inside the container\>*  
Default value :  
Full path of the certificate file to use when `USE_CUSTOM_HTTPS` is set to yes.  

`CUSTOM_HTTPS_KEY`  
Values : *\<any valid path inside the container\>*  
Default value :  
Full path of the key file to use when `USE_CUSTOM_HTTPS` is set to yes.  

### Self-signed certificate

`GENERATE_SELF_SIGNED_SSL`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, HTTPS will be enabled with a container generated self-signed certificate.

`SELF_SIGNED_SSL_EXPIRY`  
Values : *integer*  
Default value : *365* (1 year)  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the expiry date for the self generated certificate.

`SELF_SIGNED_SSL_COUNTRY`  
Values : *text*  
Default value : *Switzerland*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the country for the self generated certificate.

`SELF_SIGNED_SSL_STATE`  
Values : *text*  
Default value : *Switzerland*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the state for the self generated certificate.

`SELF_SIGNED_SSL_CITY`  
Values : *text*  
Default value : *Bern*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the city for the self generated certificate.

`SELF_SIGNED_SSL_ORG`  
Values : *text*  
Default value : *AcmeInc*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the organisation name for the self generated certificate.

`SELF_SIGNED_SSL_OU`  
Values : *text*  
Default value : *IT*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the organisitional unit for the self generated certificate.

`SELF_SIGNED_SSL_CN`  
Values : *text*  
Default value : *bunkerity-nginx*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the CN server name for the self generated certificate.

### Misc

`HTTP2`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, nginx will use HTTP2 protocol when HTTPS is enabled.  

`HTTPS_PROTOCOLS`  
Values : *TLSv1.2* | *TLSv1.3* | *TLSv1.2 TLSv1.3*  
Default value : *TLSv1.2 TLSv1.3*  
The supported version of TLS. We recommend the default value *TLSv1.2 TLSv1.3* for compatibility reasons.

## ModSecurity

`USE_MODSECURITY`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, the ModSecurity WAF will be enabled.  
You can include custom rules by adding .conf files into the /modsec-confs/ directory inside the container (i.e : through a volume).  

`USE_MODSECURITY_CRS`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, the [OWASP ModSecurity Core Rule Set](https://coreruleset.org/) will be used. It provides generic rules to detect common web attacks.  
You can customize the CRS (i.e. : add WordPress exclusions) by adding custom .conf files into the /modsec-crs-confs/ directory inside the container (i.e : through a volume). Files inside this directory are included before the CRS rules. If you need to tweak (i.e. : SecRuleUpdateTargetById) put .conf files inside the /modsec-confs/ which is included after the CRS rules.

## Security headers

`X_FRAME_OPTIONS`  
Values : *DENY* | *SAMEORIGIN* | *ALLOW-FROM https://www.website.net* | *ALLOWALL*  
Default value : *DENY*  
Policy to be used when the site is displayed through iframe. Can be used to mitigate clickjacking attacks. 
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options).

`X_XSS_PROTECTION`  
Values : *0* | *1* | *1; mode=block*  
Default value : *1; mode=block*  
Policy to be used when XSS is detected by the browser. Only works with Internet Explorer.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-XSS-Protection).  

`X_CONTENT_TYPE_OPTIONS`  
Values : *nosniff*  
Default value : *nosniff*  
Tells the browser to be strict about MIME type.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options).

`REFERRER_POLICY`  
Values : *no-referrer* | *no-referrer-when-downgrade* | *origin* | *origin-when-cross-origin* | *same-origin* | *strict-origin* | *strict-origin-when-cross-origin* | *unsafe-url*  
Default value : *no-referrer*  
Policy to be used for the Referer header.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy).

`FEATURE_POLICY`  
Values : *&lt;directive&gt; &lt;allow list&gt;*  
Default value : *accelerometer 'none'; ambient-light-sensor 'none'; autoplay 'none'; camera 'none'; display-capture 'none'; document-domain 'none'; encrypted-media 'none'; fullscreen 'none'; geolocation 'none'; gyroscope 'none'; magnetometer 'none'; microphone 'none'; midi 'none'; payment 'none'; picture-in-picture 'none'; speaker 'none'; sync-xhr 'none'; usb 'none'; vibrate 'none'; vr 'none'*  
Tells the browser which features can be used on the website.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Feature-Policy).

`COOKIE_FLAGS`  
Values : *\* HttpOnly* | *MyCookie secure SameSite=Lax* | *...*  
Default value : *\* HttpOnly SameSite=Lax*  
Adds some security to the cookies set by the server.  
Accepted value can be found [here](https://github.com/AirisX/nginx_cookie_flag_module).

`COOKIE_AUTO_SECURE_FLAG`  
Values : *yes* | *no*  
Default value : *yes*  
When set to *yes*, the *secure* will be automatically added to cookies when using HTTPS.

`STRICT_TRANSPORT_POLICY`  
Values : *max-age=expireTime [; includeSubDomains] [; preload]*  
Default value : *max-age=31536000*  
Tells the browser to use exclusively HTTPS instead of HTTP when communicating with the server.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security).

`CONTENT_SECURITY_POLICY`  
Values : *\<directive 1\>; \<directive 2\>; ...*  
Default value : *default-src 'self'; frame-ancestors 'self'; form-action 'self'; block-all-mixed-content; sandbox allow-forms allow-same-origin allow-scripts; reflected-xss block; base-uri 'self'; referrer no-referrer*  
Policy to be used when loading resources (scripts, forms, frames, ...).  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy).

## Blocking

### Antibot

`USE_ANTIBOT`  
Values : *no* | *cookie* | *javascript* | *captcha* | *recaptcha*  
Default value : *no*  
If set to another allowed value than *no*, users must complete a "challenge" before accessing the pages on your website :
- *cookie* : asks the users to set a cookie
- *javascript* : users must execute a javascript code
- *captcha* : a text captcha must be resolved by the users
- *recaptcha* : use [Google reCAPTCHA v3](https://developers.google.com/recaptcha/intro) score to allow/deny users 

`ANTIBOT_URI`  
Values : *\<any valid uri\>*  
Default value : */challenge*  
A valid and unused URI to redirect users when `USE_ANTIBOT` is used. Be sure that it doesn't exist on your website.

`ANTIBOT_SESSION_SECRET`  
Values : *random* | *\<32 chars of your choice\>*  
Default value : *random*  
A secret used to generate sessions when `USE_ANTIBOT` is set. Using the special *random* value will generate a random one. Be sure to use the same value when you are in a multi-server environment (so sessions are valid in all the servers).

`ANTIBOT_RECAPTCHA_SCORE`  
Values : *\<0.0 to 1.0\>*  
Default value : *0.7*  
The minimum score required when `USE_ANTIBOT` is set to *recaptcha*.

`ANTIBOT_RECAPTCHA_SITEKEY`  
Values : *\<public key given by Google\>*  
Default value :  
The sitekey given by Google when `USE_ANTIBOT` is set to *recaptcha*.

`ANTIBOT_RECAPTCHA_SECRET`  
Values : *\<private key given by Google\>*  
Default value :  
The secret given by Google when `USE_ANTIBOT` is set to *recaptcha*.

### External blacklist

`BLOCK_USER_AGENT`  
Values : *yes* | *no*  
Default value : *yes*
If set to yes, block clients with "bad" user agent.  
Blacklist can be found [here](https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list).

`BLOCK_TOR_EXIT_NODE`  
Values : *yes* | *no*  
Default value : *yes*  
Is set to yes, will block known TOR exit nodes.  
Blacklist can be found [here](https://iplists.firehol.org/?ipset=tor_exits).

`BLOCK_PROXIES`  
Values : *yes* | *no*  
Default value : *yes*  
Is set to yes, will block known proxies.  
Blacklist can be found [here](https://iplists.firehol.org/?ipset=firehol_proxies).

`BLOCK_ABUSERS`  
Values : *yes* | *no*  
Default value : *yes*  
Is set to yes, will block known abusers.  
Blacklist can be found [here](https://iplists.firehol.org/?ipset=firehol_abusers_30d).

### DNSBL

`USE_DNSBL`  
Values : *yes* | *no*  
Default value : *yes*  
If set to *yes*, DNSBL checks will be performed to the servers specified in the `DNSBL_LIST` environment variable.  

`DNSBL_LIST`  
Values : *\<list of DNS zones separated with spaces\>*  
Default value : *bl.blocklist.de problems.dnsbl.sorbs.net sbl.spamhaus.org xbl.spamhaus.org*  
The list of DNSBL zones to query when `USE_DNSBL` is set to *yes*.

### Custom whitelisting

`USE_WHITELIST_IP`  
Values : *yes* | *no*  
Default value : *yes*  
If set to *yes*, lets you define custom IP addresses to be whitelisted through the `WHITELIST_IP_LIST` environment variable.

`WHITELIST_IP_LIST`  
Values : *\<list of IP addresses separated with spaces\>*  
Default value : *23.21.227.69 40.88.21.235 50.16.241.113 50.16.241.114 50.16.241.117 50.16.247.234 52.204.97.54 52.5.190.19 54.197.234.188 54.208.100.253 54.208.102.37 107.21.1.8*  
The list of IP addresses to whitelist when `USE_WHITELIST_IP` is set to *yes*. The default list contains IP addresses of the [DuckDuckGo crawler](https://help.duckduckgo.com/duckduckgo-help-pages/results/duckduckbot/).

`USE_WHITELIST_REVERSE`  
Values : *yes* | *no*  
Default value : *yes*  
If set to *yes*, lets you define custom reverse DNS suffixes to be whitelisted through the `WHITELIST_REVERSE_LIST` environment variable.

`WHITELIST_REVERSE_LIST`  
Values : *\<list of reverse DNS suffixes separated with spaces\>*  
Default value : *.googlebot.com .google.com .search.msn.com .crawl.yahoot.net .crawl.baidu.jp .crawl.baidu.com .yandex.com .yandex.ru .yandex.net*  
The list of reverse DNS suffixes to whitelist when `USE_WHITELIST_REVERSE` is set to *yes*. The default list contains suffixes of major search engines.

### Custom blacklisting

`USE_BLACKLIST_IP`  
Values : *yes* | *no*  
Default value : *yes*  
If set to *yes*, lets you define custom IP addresses to be blacklisted through the `BLACKLIST_IP_LIST` environment variable.

`BLACKLIST_IP_LIST`  
Values : *\<list of IP addresses separated with spaces\>*  
Default value :  
The list of IP addresses to blacklist when `USE_BLACKLIST_IP` is set to *yes*.

`USE_BLACKLIST_REVERSE`  
Values : *yes* | *no*  
Default value : *yes*  
If set to *yes*, lets you define custom reverse DNS suffixes to be blacklisted through the `BLACKLIST_REVERSE_LIST` environment variable.

`BLACKLIST_REVERSE_LIST`  
Values : *\<list of reverse DNS suffixes separated with spaces\>*  
Default value : *.shodan.io*  
The list of reverse DNS suffixes to blacklist when `USE_BLACKLIST_REVERSE` is set to *yes*.

### Requests limiting

`USE_LIMIT_REQ`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, the amount of HTTP requests made by a user will be limited during a period of time.  
More info rate limiting [here](https://www.nginx.com/blog/rate-limiting-nginx/).

`LIMIT_REQ_RATE`  
Values : *Xr/s* | *Xr/m*  
Default value : *20r/s*  
The rate limit to apply when `USE_LIMIT_REQ` is set to *yes*. Default is 10 requests per second.

`LIMIT_REQ_BURST`  
Values : *<any valid integer\>*  
Default value : *40*  
The number of of requests to put in queue before rejecting requests.

`LIMIT_REQ_CACHE`  
Values : *Xm* | *Xk*    
Default value : *10m*  
The size of the cache to store information about request limiting.

### Countries

`BLOCK_COUNTRY`  
Values : *\<country code 1\> \<country code 2\> ...*  
Default value :  
Block some countries from accessing your website. Use 2 letters country code separated with space.

## PHP

`REMOTE_PHP`  
Values : *\<any valid IP/hostname\>*  
Default value :  
Set the IP/hostname address of a remote PHP-FPM to execute .php files. See `USE_PHP` if you want to run a PHP-FPM instance on the same container as bunkerized-nginx.

`REMOTE_PHP_PATH`  
Values : *\<any valid absolute path\>*  
Default value : */app*  
The path where the PHP files are located inside the server specified in `REMOTE_PHP`.

## Fail2ban

`USE_FAIL2BAN`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, fail2ban will be used to block users getting too much "strange" HTTP codes in a period of time.  
Instead of using iptables which is not possible inside a container, fail2ban will dynamically update nginx to ban/unban IP addresses.  
If a number (`FAIL2BAN_MAXRETRY`) of "strange" HTTP codes (`FAIL2BAN_STATUS_CODES`) is found between a time interval (`FAIL2BAN_FINDTIME`) then the originating IP address will be ban for a specific period of time (`FAIL2BAN_BANTIME`).

`FAIL2BAN_STATUS_CODES`   
Values : *\<HTTP status codes separated with | char\>*  
Default value : *400|401|403|404|405|444*  
List of "strange" error codes that fail2ban will search for.  

`FAIL2BAN_BANTIME`  
Values : *<number of seconds>*  
Default value : *3600*  
The duration time, in seconds, of a ban.  

`FAIL2BAN_FINDTIME`  
Values : *<number of seconds>*  
Default : value : *60*  
The time interval, in seconds, to search for "strange" HTTP status codes.  

`FAIL2BAN_MAXRETRY`  
Values : *\<any positive integer\>*  
Default : value : *15*  
The number of "strange" HTTP status codes to find between the time interval.

## ClamAV

`USE_CLAMAV_UPLOAD`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, ClamAV will scan every file uploads and block the upload if the file is detected.  

`USE_CLAMAV_SCAN`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, ClamAV will scan all the files inside the container every day.  

`CLAMAV_SCAN_REMOVE`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, ClamAV will automatically remove the detected files.  

## Misc

`ADDITIONAL_MODULES`  
Values : *\<list of packages separated with space\>*  
Default value :  
You can specify additional modules to install. All [alpine packages](https://pkgs.alpinelinux.org/packages) are valid.  

`LOGROTATE_MINSIZE`  
Values : *x* | *xk* | *xM* | *xG*  
Default value : 10M  
The minimum size of a log file before being rotated (no letter = bytes, k = kilobytes, M = megabytes, G = gigabytes).

`LOGROTATE_MAXAGE`  
Values : *\<any integer\>*  
Default value : 7  
The number of days before rotated files are deleted.

# Create your own image

You can use bunkerity/bunkerized-nginx as a base image for your web application. Here is a Dockerfile example :  
```
FROM bunkerity/bunkerized-nginx

# Add your own script to be executed on startup
COPY ./my-entrypoint.sh /entrypoint.d/my-entrypoint.sh
RUN chmod +x /entrypoint.d/my-entrypoint.sh

# Edit default settings
ENV MAX_CLIENT_SIZE 100m
ENV BLOCK_TOR_EXIT_NODE no
ENV USE_ANTIBOT captcha
```

# Include custom configurations
Custom configurations files (ending with .conf suffix) can be added in some directory inside the container :
  - /http-confs : http context
  - /server-confs : server context

You just need to use a volume like this :
```
docker run ... -v /path/to/http/confs:/http-confs ... -v /path/to/server/confs:/server-confs ... bunkerity/bunkerized-nginx
```
