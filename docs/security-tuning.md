# Security tuning

BunkerWeb offers many security features that you can configure with [settings](settings.md). Even if the default values of settings ensure a minimal "security by default", we strongly recommend you tune them. By doing so you will be able to ensure the security level of your choice but also manage false positives.

!!! tip "Other settings"
    This section only focuses on security tuning, see the [settings section](settings.md) of the documentation for other settings.

<figure markdown>
  ![Overview](assets/img/core-order.svg){ align=center }
  <figcaption>Overview and order of the core security plugins</figcaption>
</figure>

## HTTP protocol

### Deny status code

STREAM support :warning:

The first thing to define is the kind of action to do when a client access is denied. You can control the action with the `DENY_HTTP_STATUS` setting which allows the following values :

- `403` : send a "classical" Forbidden HTTP status code (a web page or custom content will be displayed)
- `444` : close the connection (no web page or custom content will be displayed)

The default value is `403` and we suggest you set it to `444` only if you already fixed a lot of false positive, you are familiar with BunkerWeb and want a higher level of security.

When using stream mode, value is ignored and always set to `444` with effect of closing the connection.

### Default server

STREAM support :x:

In the HTTP protocol, the Host header is used to determine which server the client wants to send the request to. That header is facultative and may be missing from the request or can be set as an unknown value. This is a common case, a lot of bots are scanning the Internet and are trying to exploit services or simply doing some fingerprinting.

You can disable any request containing undefined or unknown Host value by setting `DISABLE_DEFAULT_SERVER` to `yes` (default : `no`). Please note that clients won't even receive a response, the TCP connection will be closed (using the special 444 status code of NGINX).

### Allowed methods

STREAM support :x:

You can control the allowed HTTP methods by listing them (separated with "|") in the `ALLOWED_METHODS` setting (default : `GET|POST|HEAD`). Clients sending a method which is not listed will get a "405 - Method Not Allowed".

### Max sizes

STREAM support :x:

You can control the maximum body size with the `MAX_CLIENT_SIZE` setting (default : `10m`). See [here](https://nginx.org/en/docs/syntax.html) for accepted values. You can use the special value `0` to allow a body of infinite size (not recommended).

### Serve files

STREAM support :x:

To disable serving files from the www folder, you can set `SERVE_FILES` to `no` (default : `yes`). The value `no` is recommended if you use BunkerWeb as a reverse proxy.

### Headers

STREAM support :x:

Headers are very important when it comes to HTTP security. While some of them might be too verbose, others' verbosity will need to be increased, especially on the client-side.

#### Remove headers

STREAM support :x:

You can automatically remove verbose headers in the HTTP responses by using the `REMOVE_HEADERS` setting (default : `Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version`).

#### Cookies

STREAM support :x:

When it comes to cookies security, we can use the following flags :

- HttpOnly : disable any access to the cookie from Javascript using document.cookie
- SameSite : policy when requests come from third-party websites
- Secure : only send cookies on HTTPS request

Cookie flags can be overridden with values of your choice by using the `COOKIE_FLAGS` setting (default : `* HttpOnly SameSite=Lax`). See [here](https://github.com/AirisX/nginx_cookie_flag_module) for accepted values.

The Secure flag can be automatically added if HTTPS is used by using the `COOKIE_AUTO_SECURE_FLAG` setting (default : `yes`). The value `no` is not recommended unless you know what you're doing.

#### Security headers

STREAM support :x:

Various security headers are available and most of them can be set using BunkerWeb settings. Here is the list of headers, the corresponding setting and default value :

|           Header            | Setting                     |                                                                                                                                                                                                                                                                                                                                                            Default                                                                                                                                                                                                                                                                                                                                                            |
| :-------------------------: | :-------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: |
|  `Content-Security-Policy`  | `CONTENT_SECURITY_POLICY`   |                                                                                                                                                                                                                                                                                                             `object-src 'none'; frame-src 'self'; child-src 'self'; form-action 'self'; frame-ancestors 'self';`                                                                                                                                                                                                                                                                                                              |
| `Strict-Transport-Security` | `STRICT_TRANSPORT_SECURITY` |                                                                                                                                                                                                                                                                                                                                                      `max-age=31536000`                                                                                                                                                                                                                                                                                                                                                       |
|      `Referrer-Policy`      | `REFERRER_POLICY`           |                                                                                                                                                                                                                                                                                                                                               `strict-origin-when-cross-origin`                                                                                                                                                                                                                                                                                                                                               |
|    `Permissions-Policy`     | `PERMISSIONS_POLICY`        |                                                                                              `accelerometer=(), ambient-light-sensor=(), autoplay=(), battery=(), camera=(), cross-origin-isolated=(), display-capture=(), document-domain=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), geolocation=(), gyroscope=(), hid=(), idle-detection=(), magnetometer=(), microphone=(), midi=(), navigation-override=(), payment=(), picture-in-picture=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), usb=(), web-share=(), xr-spatial-tracking=()`                                                                                               |
|      `Feature-Policy`       | `FEATURE_POLICY`            | `accelerometer 'none'; ambient-light-sensor 'none'; autoplay 'none'; battery 'none'; camera 'none'; display-capture 'none'; document-domain 'none'; encrypted-media 'none'; execution-while-not-rendered 'none'; execution-while-out-of-viewport 'none'; fullscreen 'none'; 'none'; geolocation 'none'; gyroscope 'none'; layout-animation 'none'; legacy-image-formats 'none'; magnetometer 'none'; microphone 'none'; midi 'none'; navigation-override 'none'; payment 'none'; picture-in-picture 'none'; publickey-credentials-get 'none'; speaker-selection 'none'; sync-xhr 'none'; unoptimized-images 'none'; unsized-media 'none'; usb 'none'; screen-wake-lock 'none'; web-share 'none'; xr-spatial-tracking 'none';` |
|      `X-Frame-Options`      | `X_FRAME_OPTIONS`           |                                                                                                                                                                                                                                                                                                                                                         `SAMEORIGIN`                                                                                                                                                                                                                                                                                                                                                          |
|  `X-Content-Type-Options`   | `X_CONTENT_TYPE_OPTIONS`    |                                                                                                                                                                                                                                                                                                                                                           `nosniff`                                                                                                                                                                                                                                                                                                                                                           |
|     `X-XSS-Protection`      | `X_XSS_PROTECTION`          |                                                                                                                                                                                                                                                                                                                                                        `1; mode=block`                                                                                                                                                                                                                                                                                                                                                        |

#### CORS

STREAM support :x:

[Cross-Origin Resource Sharing](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS) lets you manage how your service can be contacted from different origins. Please note that you will have to allow the `OPTIONS` HTTP method using the `ALLOWED_METHODS` if you want to enable it (more info [here](#allowed-methods)). Here is the list of settings related to CORS :

|        Setting         |                                      Default                                       | Context |Multiple|                            Description                            |
|------------------------|------------------------------------------------------------------------------------|---------|--------|-------------------------------------------------------------------|
|`USE_CORS`              |`no`                                                                                |multisite|no      |Use CORS                                                           |
|`CORS_ALLOW_ORIGIN`     |`*`                                                                                 |multisite|no      |Allowed origins to make CORS requests : PCRE regex or *.           |
|`CORS_EXPOSE_HEADERS`   |`Content-Length,Content-Range`                                                      |multisite|no      |Value of the Access-Control-Expose-Headers header.                 |
|`CORS_MAX_AGE`          |`86400`                                                                             |multisite|no      |Value of the Access-Control-Max-Age header.                        |
|`CORS_ALLOW_CREDENTIALS`|`no`                                                                                |multisite|no      |Send the Access-Control-Allow-Credentials header.                  |
|`CORS_ALLOW_METHODS`    |`GET, POST, OPTIONS`                                                                |multisite|no      |Value of the Access-Control-Allow-Methods header.                  |
|`CORS_ALLOW_HEADERS`    |`DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range`|multisite|no      |Value of the Access-Control-Allow-Headers header.                  |
|`CORS_DENY_REQUEST`     |`yes`                                                                               |multisite|no      |Deny request and don't send it to backend if Origin is not allowed.|

Here is some examples of possible values for `CORS_ALLOW_ORIGIN` setting :

- `*` will allow all origin
- `^https://www\.example\.com$` will allow `https://www.example.com`
- `^https://.+\.example.com$` will allow any origins when domain ends with `.example.com`
- `^https://(www\.example1\.com|www\.example2\.com)$` will allow both `https://www.example1.com` and `https://www.example2.com`
- `^https?://www\.example\.com$` will allow both `https://www.example.com` and `http://www.example.com`

## HTTPS / SSL/TLS

Besides the HTTPS configuration, the following settings related to HTTPS can be set :

|            Setting            |      Default      | Description                                                                                                  |
| :---------------------------: | :---------------: | :----------------------------------------------------------------------------------------------------------- |
|   `REDIRECT_HTTP_TO_HTTPS`    |       `no`        | When set to `yes`, will redirect every HTTP request to HTTPS even if BunkerWeb is not configured with HTTPS. |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` |       `yes`       | When set to `yes`, will redirect every HTTP request to HTTPS only if BunkerWeb is configured with HTTPS.     |
|       `HTTPS_PROTOCOLS`       | `TLSv1.2 TLSv1.3` | List of supported SSL/TLS protocols when HTTPS is enabled.                                                   |
|            `HTTP2`            |       `yes`       | When set to `yes`, will enable HTTP2 protocol support when using HTTPS.                                      |
|         `LISTEN_HTTP`         |       `yes`       | When set to `no`, BunkerWeb will not listen for HTTP requests. Useful if you want HTTPS only for example.    |

When using stream, the `SSL_PROTOCOLS` can be used which takes the same value as the `HTTPS_PROTOCOLS` one.

### Let's Encrypt

STREAM support :white_check_mark:

BunkerWeb comes with automatic Let's Encrypt certificate generation and renewal. This is the easiest way of getting HTTPS working out of the box for public-facing web applications. Please note that you will need to set up proper DNS A record(s) for each of your domains pointing to your public IP(s) where BunkerWeb is accessible.

Here is the list of related settings :

|          Setting           |         Default          | Description                                                                                                                                                        |
| :------------------------: | :----------------------: | :----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|    `AUTO_LETS_ENCRYPT`     |           `no`           | When set to `yes`, HTTPS will be enabled with automatic certificate generation and renewal from Let's Encrypt.                                                     |
|    `EMAIL_LETS_ENCRYPT`    | `contact@{FIRST_SERVER}` | Email to use when generating certificates. Let's Encrypt will send notifications to that email like certificate expiration.                                        |
| `USE_LETS_ENCRYPT_STAGING` |           `no`           | When set to `yes`, the staging server of Let's Encrypt will be used instead of the production one. Useful when doing tests to avoid being "blocked" due to limits. |

Full Let's Encrypt automation is fully working with stream mode as long as you open the `80/tcp` port from the outside. Please note that you will need to use the `LISTEN_STREAM_PORT_SSL` setting in order to choose your listening SSL/TLS port.

### Custom certificate

STREAM support :white_check_mark:

If you want to use your own certificates, here is the list of related settings :

|       Setting       | Default | Description                                                                                                                                                                                                                             |
| :-----------------: | :-----: | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CUSTOM_SSL`  |  `no`   | When set to `yes`, HTTPS will be enabled with custom certificates.                                                                                                                                                                      |
| `CUSTOM_SSL_CERT` |         | Full path to the certificate. If you have one or more intermediate certificate(s) in your chain of trust, you will need to provide the bundle (more info [here](https://nginx.org/en/docs/http/configuring_https_servers.html#chains)). |
| `CUSTOM_SSL_KEY`  |         | Full path to the private key.                                                                                                                                                                                                           |

When `USE_CUSTOM_HTTPS` is set to `yes`, BunkerWeb will check every day if the custom certificate specified in `CUSTOM_HTTPS_CERT` is modified and will reload NGINX if that's the case.

When using stream mode, you will need to use the `LISTEN_STREAM_PORT_SSL` setting in order to choose your listening SSL/TLS port.

### Self-signed

STREAM support :white_check_mark:

If you want to quickly test HTTPS for staging/dev environment you can configure BunkerWeb to generate self-signed certificates, here is the list of related settings :

|          Setting           |        Default         | Description                                                                                                                |
| :------------------------: | :--------------------: | :------------------------------------------------------------------------------------------------------------------------- |
| `GENERATE_SELF_SIGNED_SSL` |          `no`          | When set to `yes`, HTTPS will be enabled with automatic self-signed certificate generation and renewal from Let's Encrypt. |
|  `SELF_SIGNED_SSL_EXPIRY`  |         `365`          | Number of days for the certificate expiration (**-days** value used with **openssl**).                                     |
|   `SELF_SIGNED_SSL_SUBJ`   | `/CN=www.example.com/` | Certificate subject to use (**-subj** value used with **openssl**).                                                        |

When using stream mode, you will need to use the `LISTEN_STREAM_PORT_SSL` setting in order to choose your listening SSL/TLS port.

## ModSecurity

STREAM support :x:

ModSecurity is integrated and enabled by default alongside the OWASP Core Rule Set within BunkerWeb. Here is the list of related settings :

|        Setting        | Default | Description                                                                                           |
| :-------------------: | :-----: | :---------------------------------------------------------------------------------------------------- |
|   `USE_MODSECURITY`   |  `yes`  | When set to `yes`, ModSecurity will be enabled.                                                       |
| `USE_MODSECURITY_CRS` |  `yes`  | When set to `yes` and `USE_MODSECURITY` is also set to `yes`, the OWASP Core Rule Set will be loaded. |

We strongly recommend keeping both ModSecurity and the OWASP Core Rule Set enabled. The only downsides are the false positives that may occur. But they can be fixed with some efforts and the CRS team maintains a list of exclusions for common applications (e.g., WordPress, Nextcloud, Drupal, Cpanel, ...).

Tuning ModSecurity and the CRS can be done using [custom configurations](quickstart-guide.md#custom-configurations) :

- modsec-crs : before the OWASP Core Rule Set is loaded
- modsec : after the OWASP Core Rule Set is loaded (also used if CRS is not loaded)

For example, you can add a custom configuration with type `modsec-crs` to add CRS exclusions :

```conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"
```

You can also add a custom configuration with type `modsec` to update loaded CRS rules :

```conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"
```

## Bad behavior

STREAM support :white_check_mark:

When attackers search for and/or exploit vulnerabilities they might generate some "suspicious" HTTP status codes that a "regular" user won’t generate within a period of time. If we detect that kind of behavior we can ban the offending IP address and force the attacker to come up with a new one.

That kind of security measure is implemented and enabled by default in BunkerWeb and is called "Bad behavior". Here is the list of the related settings :

|           Setting           |            Default            | Description                                                                  |
| :-------------------------: | :---------------------------: | :--------------------------------------------------------------------------- |
|     `USE_BAD_BEHAVIOR`      |             `yes`             | When set to `yes`, the Bad behavior feature will be enabled.                 |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | List of HTTP status codes considered as "suspicious".                        |
|   `BAD_BEHAVIOR_BAN_TIME`   |            `86400`            | The duration time (in seconds) of a ban when a client reached the threshold. |
|  `BAD_BEHAVIOR_THRESHOLD`   |             `10`              | Maximum number of "suspicious" HTTP status codes within the time period.     |
|  `BAD_BEHAVIOR_COUNT_TIME`  |             `60`              | Period of time during which we count "suspicious" HTTP status codes.                |

In other words, with the default values, if a client generates more than `10` status codes from the list `400 401 403 404 405 429 444` within `60` seconds their IP address will be banned for `86400` seconds.

When using stream mode, only the `444` status code will count as "bad".

## Antibot

STREAM support :x:

Attackers will certainly use automated tools to exploit/find some vulnerabilities in your web applications. One countermeasure is to challenge the users to detect if they look like a bot. If the challenge is solved, we consider the client as "legitimate" and they can access the web application.

That kind of security is implemented but not enabled by default in BunkerWeb and is called "Antibot". Here is the list of supported challenges :

- **Cookie** : send a cookie to the client, we expect to get the cookie back on other requests
- **Javascript** : force a client to solve a computation challenge using Javascript
- **Captcha** : force the client to solve a classical captcha (no external dependencies)
- **hCaptcha** : force the client to solve a captcha from hCaptcha
- **reCAPTCHA** : force the client to get a minimum score with Google reCAPTCHA

Here is the list of related settings :

|          Setting          |  Default   | Context |Multiple|                                                         Description                                                          |
|---------------------------|------------|---------|--------|------------------------------------------------------------------------------------------------------------------------------|
|`USE_ANTIBOT`              |`no`        |multisite|no      |Activate antibot feature.                                                                                                     |
|`ANTIBOT_URI`              |`/challenge`|multisite|no      |Unused URI that clients will be redirected to to solve the challenge.                                                         |
|`ANTIBOT_RECAPTCHA_SCORE`  |`0.7`       |multisite|no      |Minimum score required for reCAPTCHA challenge.                                                                               |
|`ANTIBOT_RECAPTCHA_SITEKEY`|            |multisite|no      |Sitekey for reCAPTCHA challenge.                                                                                              |
|`ANTIBOT_RECAPTCHA_SECRET` |            |multisite|no      |Secret for reCAPTCHA challenge.                                                                                               |
|`ANTIBOT_HCAPTCHA_SITEKEY` |            |multisite|no      |Sitekey for hCaptcha challenge.                                                                                               |
|`ANTIBOT_HCAPTCHA_SECRET`  |            |multisite|no      |Secret for hCaptcha challenge.                                                                                                |
|`ANTIBOT_TIME_RESOLVE`     |`60`        |multisite|no      |Maximum time (in seconds) clients have to resolve the challenge. Once this time has passed, a new challenge will be generated.|
|`ANTIBOT_TIME_VALID`       |`86400`     |multisite|no      |Maximum validity time of solved challenges. Once this time has passed, clients will need to resolve a new one.                |

Please note that antibot feature is using a cookie to maintain a session with clients. If you are using BunkerWeb in a clustered environment, you will need to set the `SESSIONS_SECRET` and `SESSIONS_NAME` settings to another value than the default one (which is `random`). You will find more info about sessions [here](settings.md#sessions).

## Blacklisting, whitelisting and greylisting

The blacklisting security feature is very easy to understand : if a specific criteria is met, the client will be banned. As for the whitelisting, it's the exact opposite : if a specific criteria is met, the client will be allowed and no additional security check will be done. Whereas for the greylisting :  if a specific criteria is met, the client will be allowed but additional security checks will be done.

You can configure blacklisting, whitelisting and greylisting at the same time. If that's the case, note that whitelisting is executed before blacklisting and greylisting : even if a criteria is true for all of them, the client will be whitelisted.

### Blacklisting

STREAM support :warning:

You can use the following settings to set up blacklisting :

|             Setting              |                                                           Default                                                            | Context |Multiple|                                          Description                                           |
|----------------------------------|------------------------------------------------------------------------------------------------------------------------------|---------|--------|------------------------------------------------------------------------------------------------|
|`USE_BLACKLIST`                   |`yes`                                                                                                                         |multisite|no      |Activate blacklist feature.                                                                     |
|`BLACKLIST_IP`                    |                                                                                                                              |multisite|no      |List of IP/network, separated with spaces, to block.                                            |
|`BLACKLIST_IP_URLS`               |`https://www.dan.me.uk/torlist/?exit`                                                                                         |global   |no      |List of URLs, separated with spaces, containing bad IP/network to block.                        |
|`BLACKLIST_RDNS_GLOBAL`           |`yes`                                                                                                                         |multisite|no      |Only perform RDNS blacklist checks on global IP addresses.                                      |
|`BLACKLIST_RDNS`                  |`.shodan.io .censys.io`                                                                                                       |multisite|no      |List of reverse DNS suffixes, separated with spaces, to block.                                  |
|`BLACKLIST_RDNS_URLS`             |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing reverse DNS suffixes to block.                  |
|`BLACKLIST_ASN`                   |                                                                                                                              |multisite|no      |List of ASN numbers, separated with spaces, to block.                                           |
|`BLACKLIST_ASN_URLS`              |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing ASN to block.                                   |
|`BLACKLIST_USER_AGENT`            |                                                                                                                              |multisite|no      |List of User-Agent (PCRE regex), separated with spaces, to block.                               |
|`BLACKLIST_USER_AGENT_URLS`       |`https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list`|global   |no      |List of URLs, separated with spaces, containing bad User-Agent to block.                        |
|`BLACKLIST_URI`                   |                                                                                                                              |multisite|no      |List of URI (PCRE regex), separated with spaces, to block.                                      |
|`BLACKLIST_URI_URLS`              |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing bad URI to block.                               |
|`BLACKLIST_IGNORE_IP`             |                                                                                                                              |multisite|no      |List of IP/network, separated with spaces, to ignore in the blacklist.                          |
|`BLACKLIST_IGNORE_IP_URLS`        |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing IP/network to ignore in the blacklist.          |
|`BLACKLIST_IGNORE_RDNS`           |                                                                                                                              |multisite|no      |List of reverse DNS suffixes, separated with spaces, to ignore in the blacklist.                |
|`BLACKLIST_IGNORE_RDNS_URLS`      |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing reverse DNS suffixes to ignore in the blacklist.|
|`BLACKLIST_IGNORE_ASN`            |                                                                                                                              |multisite|no      |List of ASN numbers, separated with spaces, to ignore in the blacklist.                         |
|`BLACKLIST_IGNORE_ASN_URLS`       |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing ASN to ignore in the blacklist.                 |
|`BLACKLIST_IGNORE_USER_AGENT`     |                                                                                                                              |multisite|no      |List of User-Agent (PCRE regex), separated with spaces, to ignore in the blacklist.             |
|`BLACKLIST_IGNORE_USER_AGENT_URLS`|                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing User-Agent to ignore in the blacklist.          |
|`BLACKLIST_IGNORE_URI`            |                                                                                                                              |multisite|no      |List of URI (PCRE regex), separated with spaces, to ignore in the blacklist.                    |
|`BLACKLIST_IGNORE_URI_URLS`       |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing URI to ignore in the blacklist.                 |

When using stream mode, only IP, RDNS and ASN checks will be done.

### Greylisting

STREAM support :warning:

You can use the following settings to set up greylisting :

|         Setting          |Default| Context |Multiple|                                         Description                                          |
|--------------------------|-------|---------|--------|----------------------------------------------------------------------------------------------|
|`USE_GREYLIST`            |`no`   |multisite|no      |Activate greylist feature.                                                                    |
|`GREYLIST_IP`             |       |multisite|no      |List of IP/network, separated with spaces, to put into the greylist.                          |
|`GREYLIST_IP_URLS`        |       |global   |no      |List of URLs, separated with spaces, containing good IP/network to put into the greylist.     |
|`GREYLIST_RDNS_GLOBAL`    |`yes`  |multisite|no      |Only perform RDNS greylist checks on global IP addresses.                                     |
|`GREYLIST_RDNS`           |       |multisite|no      |List of reverse DNS suffixes, separated with spaces, to put into the greylist.                |
|`GREYLIST_RDNS_URLS`      |       |global   |no      |List of URLs, separated with spaces, containing reverse DNS suffixes to put into the greylist.|
|`GREYLIST_ASN`            |       |multisite|no      |List of ASN numbers, separated with spaces, to put into the greylist.                         |
|`GREYLIST_ASN_URLS`       |       |global   |no      |List of URLs, separated with spaces, containing ASN to put into the greylist.                 |
|`GREYLIST_USER_AGENT`     |       |multisite|no      |List of User-Agent (PCRE regex), separated with spaces, to put into the greylist.             |
|`GREYLIST_USER_AGENT_URLS`|       |global   |no      |List of URLs, separated with spaces, containing good User-Agent to put into the greylist.     |
|`GREYLIST_URI`            |       |multisite|no      |List of URI (PCRE regex), separated with spaces, to put into the greylist.                    |
|`GREYLIST_URI_URLS`       |       |global   |no      |List of URLs, separated with spaces, containing bad URI to put into the greylist.             |

When using stream mode, only IP, RDNS and ASN checks will be done.

### Whitelisting

STREAM support :warning:

You can use the following settings to set up whitelisting :

|          Setting          |                                                                                          Default                                                                                           | Context |Multiple|                                   Description                                    |
|---------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|--------|----------------------------------------------------------------------------------|
|`USE_WHITELIST`            |`yes`                                                                                                                                                                                       |multisite|no      |Activate whitelist feature.                                                       |
|`WHITELIST_IP`             |`20.191.45.212 40.88.21.235 40.76.173.151 40.76.163.7 20.185.79.47 52.142.26.175 20.185.79.15 52.142.24.149 40.76.162.208 40.76.163.23 40.76.162.191 40.76.162.247 54.208.102.37 107.21.1.8`|multisite|no      |List of IP/network, separated with spaces, to put into the whitelist.             |
|`WHITELIST_IP_URLS`        |                                                                                                                                                                                            |global   |no      |List of URLs, separated with spaces, containing good IP/network to whitelist.     |
|`WHITELIST_RDNS_GLOBAL`    |`yes`                                                                                                                                                                                       |multisite|no      |Only perform RDNS whitelist checks on global IP addresses.                        |
|`WHITELIST_RDNS`           |`.google.com .googlebot.com .yandex.ru .yandex.net .yandex.com .search.msn.com .baidu.com .baidu.jp .crawl.yahoo.net .fwd.linkedin.com .twitter.com .twttr.com .discord.com`                |multisite|no      |List of reverse DNS suffixes, separated with spaces, to whitelist.                |
|`WHITELIST_RDNS_URLS`      |                                                                                                                                                                                            |global   |no      |List of URLs, separated with spaces, containing reverse DNS suffixes to whitelist.|
|`WHITELIST_ASN`            |`32934`                                                                                                                                                                                     |multisite|no      |List of ASN numbers, separated with spaces, to whitelist.                         |
|`WHITELIST_ASN_URLS`       |                                                                                                                                                                                            |global   |no      |List of URLs, separated with spaces, containing ASN to whitelist.                 |
|`WHITELIST_USER_AGENT`     |                                                                                                                                                                                            |multisite|no      |List of User-Agent (PCRE regex), separated with spaces, to whitelist.             |
|`WHITELIST_USER_AGENT_URLS`|                                                                                                                                                                                            |global   |no      |List of URLs, separated with spaces, containing good User-Agent to whitelist.     |
|`WHITELIST_URI`            |                                                                                                                                                                                            |multisite|no      |List of URI (PCRE regex), separated with spaces, to whitelist.                    |
|`WHITELIST_URI_URLS`       |                                                                                                                                                                                            |global   |no      |List of URLs, separated with spaces, containing bad URI to whitelist.             |

When using stream mode, only IP, RDNS and ASN checks will be done.

## Reverse scan

STREAM support :white_check_mark:

Reverse scan is a feature designed to detect open ports by establishing TCP connections with clients' IP addresses.
Consider adding this feature if you want to detect possible open proxies or connections from servers.

We provide a list of suspicious ports by default but it can be modified to fit your needs. Be mindful, adding too many ports to the list can significantly slow down clients' connections due to the network checks. If a listed port is open, the client's access will be denied.

Please be aware, this feature is new and further improvements will be added soon.

Here is the list of settings related to reverse scan :

|   Setting    |                                   Default                                    | Description                                    |
| :----------: | :--------------------------------------------------------------------------: | :--------------------------------------------- |
| `USE_REVERSE_SCAN`  |                                    `no`                                     | When set to `yes`, will enable ReverseScan. |
| `REVERSE_SCAN_PORTS` | `22 80 443 3128 8000 8080`                                                 | List of suspicious ports to scan.                  |
| `REVERSE_SCAN_TIMEOUT` | `500`                                                                    | Specify the maximum timeout (in ms) when scanning a port.                |

## BunkerNet

STREAM support :white_check_mark:

BunkerNet is a crowdsourced database of malicious requests shared between all BunkerWeb instances over the world.

If you enable BunkerNet, malicious requests will be sent to a remote server and will be analyzed by our systems. By doing so, we can extract malicious data from everyone's reports and give back the results to each BunkerWeb instances participating into BunkerNet.

At the moment, that feature should be considered in "beta". We only extract malicious IP and we are very strict about how we do it to avoid any "poisoning". We strongly recommend activating it (which is the default) because the more instances participate, the more data we have to improve the algorithm.

The setting used to enable or disable BunkerNet is `USE_BUNKERNET` (default : `yes`).

## DNSBL

STREAM support :white_check_mark:

DNSBL or "DNS BlackList" is an external list of malicious IPs that you query using the DNS protocol. Automatic querying of that kind of blacklist is supported by BunkerWeb. If a remote DNSBL server of your choice says that the IP address of the client is in the blacklist, it will be banned.

Here is the list of settings related to DNSBL :

|   Setting    |                                   Default                                    | Description                                    |
| :----------: | :--------------------------------------------------------------------------: | :--------------------------------------------- |
| `USE_DNSBL`  |                                    `yes`                                     | When set to `yes`, will enable DNSBL checking. |
| `DNSBL_LIST` | `bl.blocklist.de problems.dnsbl.sorbs.net sbl.spamhaus.org xbl.spamhaus.org` | List of DNSBL servers to ask.                  |

## Limiting

BunkerWeb supports applying a limit policy to :

- Number of connections per IP
- Number of requests per IP and URL within a time period

Please note that it should not be considered as an effective solution against DoS or DDoS but rather as an anti-bruteforce measure or rate limit policy for API.

In both cases (connections or requests) if the limit is reached, the client will receive the HTTP status "429 - Too Many Requests".

### Connections

STREAM support :white_check_mark:

The following settings are related to the Limiting connections feature :

|        Setting         | Default | Description                                                                                |
| :--------------------: | :-----: | :----------------------------------------------------------------------------------------- |
|    `USE_LIMIT_CONN`    |  `yes`  | When set to `yes`, will limit the maximum number of concurrent connections for a given IP. |
| `LIMIT_CONN_MAX_HTTP1` |  `10`   | Maximum number of concurrent connections when using HTTP1 protocol.                        |
| `LIMIT_CONN_MAX_HTTP2` |  `100`  | Maximum number of concurrent streams when using HTTP2 protocol.                            |
| `LIMIT_CONN_MAX_STREAM`|  `10`  | Maximum number of connections per IP when using stream.                                     |

### Requests

STREAM support :x:

The following settings are related to the Limiting requests feature :

|        Setting        |Default| Context |Multiple|                                         Description                                         |
|-----------------------|-------|---------|--------|---------------------------------------------------------------------------------------------|
|`USE_LIMIT_REQ`        |`yes`  |multisite|no      |Activate limit requests feature.                                                             |
|`LIMIT_REQ_URL`        |`/`    |multisite|yes     |URL (PCRE regex) where the limit request will be applied or special value / for all requests.|
|`LIMIT_REQ_RATE`       |`2r/s` |multisite|yes     |Rate to apply to the URL (s for second, m for minute, h for hour and d for day).             |
|`USE_LIMIT_CONN`       |`yes`  |multisite|no      |Activate limit connections feature.                                                          |
|`LIMIT_CONN_MAX_HTTP1` |`10`   |multisite|no      |Maximum number of connections per IP when using HTTP/1.X protocol.                           |
|`LIMIT_CONN_MAX_HTTP2` |`100`  |multisite|no      |Maximum number of streams per IP when using HTTP/2 protocol.                                 |
|`LIMIT_CONN_MAX_STREAM`|`10`   |multisite|no      |Maximum number of connections per IP when using stream.                                      |

Please note that you can add different rates for different URLs by adding a number as a suffix to the settings for example : `LIMIT_REQ_URL_1=^/url1$`, `LIMIT_REQ_RATE_1=5r/d`, `LIMIT_REQ_URL_2=^/url2/subdir/.*$`, `LIMIT_REQ_RATE_2=1r/m`, ...

Another important thing to note is that `LIMIT_REQ_URL` values are PCRE regex.

## Country

STREAM support :white_check_mark:

The country security feature allows you to apply policy based on the country of the IP address of clients :

- Deny any access if the country is in a blacklist
- Only allow access if the country is in a whitelist (other security checks will still be executed)

Here is the list of related settings :

|       Setting       | Default | Description                                  |
| :-----------------: | :-----: | :------------------------------------------- |
| `BLACKLIST_COUNTRY` |         | List of 2 letters country code to blacklist. |
| `WHITELIST_COUNTRY` |         | List of 2 letters country code to whitelist. |

Using both country blacklist and whitelist at the same time makes no sense. If you do, please note that only the whitelist will be executed.

## Authentication

### Auth basic

STREAM support :x:

You can quickly protect sensitive resources like the admin area for example, by requiring HTTP basic authentication. Here is the list of related settings :

|          Setting          |      Default      | Description                                                                                  |
| :-----------------------: | :---------------: | :------------------------------------------------------------------------------------------- |
|     `USE_AUTH_BASIC`      |       `no`        | When set to `yes` HTTP auth basic will be enabled.                                           |
|   `AUTH_BASIC_LOCATION`   |    `sitewide`     | Location (URL) of the sensitive resource. Use special value `sitewide` to enable everywhere. |
|   `AUTH_BASIC_USER`   |    `changeme`     | The username required.                                                                       |
| `AUTH_BASIC_PASSWORD` |    `changeme`     | The password required.                                                                       |
|   `AUTH_BASIC_TEXT`   | `Restricted area` | Text to display in the auth prompt.                                                          |

### Auth request

You can deploy complex authentication (e.g. SSO), by using the auth request settings (see [here](https://docs.nginx.com/nginx/admin-guide/security-controls/configuring-subrequest-authentication/) for more information on the feature). Please note that you will find [Authelia](https://www.authelia.com/) and [Authentik](https://goauthentik.io/) examples in the [repository](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/examples).

**Auth request settings are related to reverse proxy rules.**

|                Setting                |             Default              | Context |Multiple|                                                    Description                                                     |
|---------------------------------------|----------------------------------|---------|--------|--------------------------------------------------------------------------------------------------------------------|
|`REVERSE_PROXY_AUTH_REQUEST`           |                                  |multisite|yes     |Enable authentication using an external provider (value of auth_request directive).                                 |
|`REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL`|                                  |multisite|yes     |Redirect clients to sign-in URL when using REVERSE_PROXY_AUTH_REQUEST (used when auth_request call returned 401).    |
|`REVERSE_PROXY_AUTH_REQUEST_SET`       |                                  |multisite|yes     |List of variables to set from the authentication provider, separated with ; (values of auth_request_set directives).|
