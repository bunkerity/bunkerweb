# Security tuning

bunkerized-nginx comes with a set of predefined security settings that you can (and you should) tune to meet your own use case.

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

Here is a dummy example on how to use custom certificates : 

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

Some important HTTP headers related to client security are sent with a default value. Sometimes it can break a web application or can be tuned to provide even more security. The complete list is available [here](#TODO).

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

TODO

## Antibot challenge

Attackers will certainly use automated tools to exploit/find some vulnerabilities on your web service. One countermeasure is to challenge the users to detect if it looks like a bot. It might be effective against script kiddies or "lazy" attackers.

You can use the `USE_ANTIBOT` environment variable to add that kind of checks whenever a new client is connecting. The available challenges are : `cookie`, `javascript`, `captcha` and `recaptcha`. More info [here](#TODO).

## External blacklists

## Container hardening

### Drop capabilities
By default, *bunkerized-nginx* runs as non-root user inside the container and should not use any of the default [capabilities](https://docs.docker.com/engine/security/#linux-kernel-capabilities) allowed by Docker. You can safely remove all capabilities to harden the container :

```shell
docker run ... --drop-cap=all ... bunkerity/bunkerized-nginx
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
