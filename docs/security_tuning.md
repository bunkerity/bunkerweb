# Security tuning

bunkerized-nginx comes with a set of predefined security settings that you can (and you should) tune to meet your own use case.

## Miscellaneous

Here is a list of miscellaneous environment variables related more or less to security :
- `MAX_CLIENT_SIZE=10m` : maximum size of client body
- `ALLOWED_METHODS=GET|POST|HEAD` : list of HTTP methos that clients are allowed to use
- `DISABLE_DEFAULT_SERVER=no` : enable/disable the default server (i.e. : should your server respond to unknown Host header ?)
- `SERVER_TOKENS=off` : enable/disable sending the version number of nginx

## HTTPS

### Settings

Here is a list of environment variables and the corresponding default value related to HTTPS :
- `LISTEN_HTTP=yes` : you can set it to `no` if you want to disable HTTP access
- `REDIRECT_HTTP_TO_HTTPS=no` : enable/disable HTTP to HTTPS redirection
- `HTTPS_PROTOCOLS=TLSv1.2 TLSv1.3` : list of TLS versions to use
- `HTTP2=yes` : enable/disable HTTP2 when HTTPS is enabled
- `COOKIE_AUTO_SECURE_FLAG=yes` : enable/disable adding Secure flag when HTTPS is enabled
- `STRICT_TRANSPORT_SECURITY=max-age=31536000` : force users to visit the website in HTTPS (more info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy))

### Let's Encrypt

Using Let's Encrypt with the `AUTO_LETS_ENCRYPT=yes` environment variable is the easiest way to add HTTPS supports to your web services if they are connected to internet and you have public DNS A record(s).

You can also set the `EMAIL_LETS_ENCRYPT` environment variable if you want to receive notifications from Let's Encrypt (e.g. : expiration).

### Custom certificate(s)

If you have security constraints (e.g : local network, custom PKI, ...) you can use custom certificates of your choice and tell bunkerized-nginx to use them with the following environment variables :
- `USE_CUSTOM_HTTPS=yes`
- `CUSTOM_HTTPS_CERT=/path/inside/container/to/cert.pem`
- `CUSTOM_HTTPS_KEY=/path/inside/container/to/key.pem`

Here is a an example on how to use custom certificates : 

```shell
$ ls /etc/ssl/my-web-app
cert.pem key.pem

$ docker run -p 80:8080 \
             -p 443:8443 \
             -v /etc/ssl/my-web-app:/certs:ro \
             -e USE_CUSTOM_HTTPS=yes \
             -e CUSTOM_HTTPS_CERT=/certs/cert.pem \
             -e CUSTOM_HTTPS_KEY=/certs/key.pem \
             ...
             bunkerity/bunkerized-nginx
```

Please note that if you have one or more intermediate certificate(s) in your chain of trust, you will need to provide the bundle to `CUSTOM_HTTPS_CERT` (more info [here](https://nginx.org/en/docs/http/configuring_https_servers.html#chains)).

You can reload the certificate(s) (e.g. : in case of a renewal) by sending the SIGHUP/HUP signal to the container bunkerized-nginx will catch the signal and send a reload order to nginx :

```shell
docker kill --signal=SIGHUP my-container
```

### Self-signed certificate

This method is not recommended in production but can be used to quickly deploy HTTPS for testing purposes. Just use the `GENERATE_SELF_SIGNED_SSL=yes` environment variable and bunkerized-nginx will generate a self-signed certificate for you :
```shell
$ docker run -p 80:8080 \
             -p 443:8443 \
             -e GENERATE_SELF_SIGNED_SSL=yes \
             ...
             bunkerity/bunkerized-nginx
```

## Headers

Some important HTTP headers related to client security are sent with a default value. Sometimes it can break a web application or can be tuned to provide even more security. The complete list is available [here](https://bunkerized-nginx.readthedocs.io/en/latest/environment_variables.html#security-headers).

You can also remove headers (e.g. : too verbose ones) by using the `REMOVE_HEADERS` environment variable which takes a list of header name separated with space (default value = `Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version`).

## ModSecurity

ModSecurity is integrated and enabled by default alongside the OWASP Core Rule Set within bunkerized-nginx. To change this behaviour you can use the `USE_MODSECURITY=no` or `USE_MODSECURITY_CRS=no` environment variables.

We strongly recommend to keep both ModSecurity and the OWASP Core Rule Set enabled. The only downsides are the false positives that may occur. But they can be fixed easily and the CRS team maintains a list of exclusions for common application (e.g : wordpress, nextcloud, drupal, cpanel, ...).

Tuning the CRS with bunkerized-nginx is pretty simple : you can add configuration before (i.e. : exclusions) and after (i.e. : exceptions/tuning) the rules are loaded. You just need to mount your .conf files into the /modsec-crs-confs (before CRS is loaded) and /modsec-confs (after CRS is loaded).

Here is an example to illustrate it :

```shell
$ cat /data/exclusions-crs/wordpress.conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"

$ cat /data/tuning-crs/remove-false-positives.conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"

$ docker run -p 80:8080 \
             -p 443:8443 \
             -v /data/exclusions-crs:/modsec-crs-confs:ro \
             -v /data/tuning-crs:/modsec-confs:ro \
             ...
             bunkerity/bunkerized-nginx
```

## Bad behaviors detection

When attackers search for and/or exploit vulnerabilities they might generate some suspicious HTTP status codes that a "regular" user won't generate within a period of time. If we detect that kind of behavior we can ban the offending IP address and force the attacker to come with a new one.

That kind of security measure is implemented and enabled by default in bunkerized-nginx. Here is the list of the related environment variables and their default value :
- `USE_BAD_BEHAVIOR=yes` : enable/disable "bad behavior" detection and automatic ban of IP
- `BAD_BEHAVIOR_STATUS_CODES=400 401 403 404 405 429 444` : the list of HTTP status codes considered as "suspicious"
- `BAD_BEHAVIOR_THRESHOLD=10` : the number of "suspicious" HTTP status codes required before we ban the corresponding IP address
- `BAD_BEHAVIOR_BAN_TIME=86400` : the duration time (in seconds) of the ban
- `BAD_BEHAVIOR_COUNT_TIME=60` : the duration time (in seconds) to wait before resetting the counter of "suspicious" HTTP status codes for a given IP 

## Antibot challenge

Attackers will certainly use automated tools to exploit/find some vulnerabilities on your web service. One countermeasure is to challenge the users to detect if it looks like a bot. It might be effective against script kiddies or "lazy" attackers.

You can use the `USE_ANTIBOT` environment variable to add that kind of checks whenever a new client is connecting. The available challenges are : `cookie`, `javascript`, `captcha` and `recaptcha`. More info [here](https://bunkerized-nginx.readthedocs.io/en/latest/environment_variables.html#antibot).

## External blacklists

### DNSBL

Automatic checks on external DNS BlackLists are enabled by default with the `USE_DNSBL=yes` environment variable. The list of DNSBL zones is also configurable, you just need to edit the `DNSBL_LIST` environment variable which contains the following value by default `bl.blocklist.de problems.dnsbl.sorbs.net sbl.spamhaus.org xbl.spamhaus.org`.

### CrowdSec

CrowdSec is not enabled by default because it's more than an external blacklists and needs some extra work to get it working. But bunkerized-nginx is fully working with CrowdSec, here are the related environment variables :
- `USE_CROWDSEC=no` : enable/disable CrowdSec checks before we authorize a client
- `CROWDSEC_HOST=` : full URL to your CrowdSec instance API
- `CROWDSEC_KEY=` : bouncer key given from **cscli bouncer add MyBouncer**

You will also need to share the logs generated by bunkerized-nginx with your CrowdSec instance. One approach is to send the logs to a syslog server which is writing the logs to the file system and then CrowdSec can easily read the logs. If you want to give it a try, you have a concrete example on how to use CrowdSec with bunkerized-nginx [here](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/crowdsec).

### User-Agents

Sometimes script kiddies or lazy attackers don't put a "legitimate" value inside the **User-Agent** HTTP header so we can block them. This is controlled with the `BLOCK_USER_AGENT=yes` environment variable. The blacklist is composed of two files from [here](https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list) and [here](https://raw.githubusercontent.com/JayBizzle/Crawler-Detect/master/raw/Crawlers.txt).

If a legitimate User-Agent is blacklisted, you can use the `WHITELIST_USER_AGENT` while still keeping the `BLOCK_USER_AGENT=yes` (more info [here](https://bunkerized-nginx.readthedocs.io/en/latest/environment_variables.html#custom-whitelisting)).

### TOR exit nodes

Blocking TOR exit nodes might not be a good decision depending on your use case. We decided to enable it by default with the `BLOCK_TOR_EXIT_NODE=yes` environment variable. If privacy is a concern for you and/or your clients, you can override the default value (i.e : `BLOCK_TOR_EXIT_NODE=no`).

Please note that you have a concrete example on how to use bunkerized-nginx with a .onion hidden service [here](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/tor-hidden-service).

### Proxies

This list contains IP addresses and networks known to be open proxies (downloaded from [here](https://iplists.firehol.org/files/firehol_proxies.netset)). Unless privacy is important for you and/or your clients, you should keep the default environment variable `BLOCK_PROXIES=yes`.

### Abusers

This list contains IP addresses and networks known to be abusing (downloaded from [here](https://iplists.firehol.org/files/firehol_abusers_30d.netset)). You can control this feature with the `BLOCK_ABUSERS` environment variable (default : `yes`).

### Referrers

This list contains bad referrers domains known for spamming (downloaded from [here](https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-referrers.list)). If one value is found inside the **Referer** HTTP header, request will be blocked. You can control this feature with the `BLOCK_REFERRER` environment variable (default = `yes`).

## Limiting

### Requests

To limit bruteforce attacks we decided to use the [rate limiting feature in nginx](https://www.nginx.com/blog/rate-limiting-nginx/) so attackers will be limited to X request(s)/s for the same resource. That kind of protection might be useful against other attacks too (e.g. : blind SQL injection).

Here is the list of related environment variables and their default value :
- `USE_LIMIT_REQ=yes` : enable/disable request limiting
- `LIMIT_REQ_RATE=1r/s` : the rate to apply for the same resource
- `LIMIT_REQ_BURST=2` : the number of request tu put in a queue before effectively rejecting requests

### Connections

Opening too many connections from the same IP address might be considered as suspicious (unless it's a shared IP and everyone is sending requests to your web service). It can be a dos/ddos attempt too. Bunkerized-nginx levarages the [ngx_http_conn_module](http://nginx.org/en/docs/http/ngx_http_limit_conn_module.html) from nginx to prevent users opening too many connections. 

Here is the list of related environment variables and their default value :
- `USE_LIMIT_CONN=yes` : enable disable connection limiting
- `LIMIT_CONN_MAX=50` : maximum number of connections per IP

## Country

If the location of your clients is known, you may want to add another security layer by whitelisting or blacklisting some countries. You can use the `BLACKLIST_COUNTRY` or `WHITELIST_COUNTRY` environment variables depending on your approach. They both take a list of 2 letters country code separated with space.

## Authentication

You can quickly protect sensitive resources (e.g. : admin panels) by requiring HTTP authentication. Here is the list of related environment variables and their default value :
- `USE_AUTH_BASIC=no` : enable/disable auth basic
- `AUTH_BASIC_LOCATION=sitewide` : location of the sensitive resource (e.g. `/admin`) or `sitewide` to force authentication on the whole service
- `AUTH_BASIC_USER=changeme` : the username required
- `AUTH_BASIC_PASSWORD=changeme` : the password required
- `AUTH_BASIC_TEXT=Restricted area` : the text that will be displayed to the user

## Whitelisting

Adding extra security can sometimes trigger false positives. Also, it might be not useful to do the security checks for specific clients because we decided to trust them. Bunkerized-nginx supports two types of whitelist : by IP address and by reverse DNS.

Here is the list of related environment variables and their default value : 
- `USE_WHITELIST_IP=yes` : enable/disable whitelisting by IP address
- `WHITELIST_IP_LIST=23.21.227.69 40.88.21.235 50.16.241.113 50.16.241.114 50.16.241.117 50.16.247.234 52.204.97.54 52.5.190.19 54.197.234.188 54.208.100.253 54.208.102.37 107.21.1.8` : list of IP addresses and/or network CIDR blocks to whitelist (default contains the IP addresses of the [DuckDuckGo crawler](https://help.duckduckgo.com/duckduckgo-help-pages/results/duckduckbot/))
- `USE_WHITELIST_REVERSE=yes` : enable/disable whitelisting by reverse DNS
- `WHITELIST_REVERSE_LIST=.googlebot.com .google.com .search.msn.com .crawl.yahoot.net .crawl.baidu.jp .crawl.baidu.com .yandex.com .yandex.ru .yandex.net` : the list of reverse DNS suffixes to trust (default contains the list of major search engines crawlers)

## Blacklisting

Sometimes it isn't necessary to spend some resources for a particular client because we know for sure that he is malicious. Bunkerized-nginx nginx supports two types of blacklisting : by IP address and by reverse DNS.

Here is the list of related environment variables and their default value : 
- `USE_BLACKLIST_IP=yes` : enable/disable blacklisting by IP address
- `BLACKLIST_IP_LIST=` : list of IP addresses and/or network CIDR blocks to blacklist
- `USE_BLACKLIST_REVERSE=yes` : enable/disable blacklisting by reverse DNS
- `BLACKLIST_REVERSE_LIST=.shodan.io` : the list of reverse DNS suffixes to never trust

## Web UI

Mounting the docker socket in a container which is facing the network, like we do with the [web UI](https://bunkerized-nginx.readthedocs.io/en/latest/quickstart_guide.html#web-ui), is not a good security practice. In case of a vulnerability inside the application, attackers can freely use the Docker socket and the whole host can be compromised.

A possible workaround is to use the [tecnativa/docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy) image which acts as a reverse proxy between the application and the Docker socket. It can allow/deny the requests made to the Docker API.

Before starting the web UI, you need to fire up the docker-socket-proxy (we also need a network because of inter-container communication) :

```shell
docker network create mynet
```

```shell
docker run --name mysocketproxy \
           --network mynet \
           -v /var/run/docker.sock:/var/run/docker.sock:ro \
           -e POST=1 \
           -e CONTAINERS=1 \
           tecnativa/docker-socket-proxy
```

You can now start the web UI container and use the `DOCKER_HOST` environment variable to define the Docker API endpoint :

```shell
docker run --network mynet \
           -v autoconf:/etc/nginx \
           -e ABSOLUTE_URI=https://my.webapp.com/admin/ \
           -e DOCKER_HOST=tcp://mysocketproxy:2375 \
           bunkerity/bunkerized-nginx-ui
```

## Plugins

Some security features can be added through the plugins system (e.g. : ClamAV). You will find more info in the [plugins section](https://bunkerized-nginx.readthedocs.io/en/latest/plugins.html).

## Container hardening

You will find a ready to use docker-compose.yml file focused on container hardening [here](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/hardened).

### Drop capabilities
By default, *bunkerized-nginx* runs as non-root user inside the container and should not use any of the default [capabilities](https://docs.docker.com/engine/security/#linux-kernel-capabilities) allowed by Docker. You can safely remove all capabilities to harden the container :

```shell
docker run ... --drop-cap=all ... bunkerity/bunkerized-nginx
```

### No new privileges
Bunkerized-nginx should never tries to gain additional privileges through setuid/setgid executables. You can safely add the **no-new-privileges** [security configuration](https://docs.docker.com/engine/reference/run/#security-configuration) when creating the container :

```shell
docker run ... --security-opt no-new-privileges ... bunkerity/bunkerized-nginx
```

### Read-only
Since the locations where bunkerized-nginx needs to write are known, we can run the container with a read-only root file system and only allow writes to specific locations by adding volumes and a tmpfs mount :

```shell
docker run ... --read-only --tmpfs /tmp -v cache-vol:/cache -v conf-vol:/etc/nginx -v /path/to/web/files:/www:ro -v /where/to/store/certificates:/etc/letsencrypt bunkerity/bunkerized-nginx
```

### User namespace remap
Another hardening trick is [user namespace remapping](https://docs.docker.com/engine/security/userns-remap/) : it allows you to map the UID/GID of users inside a container to another UID/GID on the host. For example, you can map the user nginx with UID/GID 101 inside the container to a non-existent user with UID/GID 100101 on the host.

Let's assume you have the /etc/subuid and /etc/subgid files like this :  
```
user:100000:65536
```
It means that everything done inside the container will be remapped to UID/GID 100101 (100000 + 101) on the host.

Please note that you must set the rights on the volumes (e.g. : /etc/letsencrypt, /www, ...) according to the remapped UID/GID :  
```shell
$ chown root:100101 /path/to/letsencrypt
$ chmod 770 /path/to/letsencrypt
$ docker run ... -v /path/to/letsencrypt:/etc/letsencrypt ... bunkerity/bunkerized-nginx
```

