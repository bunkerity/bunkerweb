# Security tuning

BunkerWeb offers many security features that you can configure with [settings](/settings). Even if the default values of settings ensure a minimal "security by default", we strongly recommend you to tune them. By doing so you will be able to ensure a security level of your choice but also manage false positives.

!!! tip "Other settings"
    This section only focuses on security tuning, see the [settings section](/settings) of the documentation for other settings.

## HTTP protocol

### Default server

In the HTTP protocol, the Host header is used to determine which server the client wants to send the request to. That header is facultative and may be missing from the request or can be set as an unknown value. This is a common case, a lot of bots are scanning the Internet and are trying to exploit services or simply doing some fingerprinting.

You can disable any request containing undefined or unknown Host value by setting `DISABLE_DEFAULT_SERVER` to `yes` (default : `no`). Please note that clients won't even receive a response, the TCP connection will be closed (using the special 444 status code of NGINX).

### Allowed methods

You can control the allowed HTTP methods by listing them (separated with "|") in the `ALLOWED_METHODS` setting (default : `GET|POST|HEAD`). Clients sending a method which is not listed will get a "405 - Method Not Allowed".

### Max sizes

You can control the maximum body size with the `MAX_CLIENT_SIZE` setting (default : `10m`). See [here](https://nginx.org/en/docs/syntax.html) for accepted values. You can use the special value `0` to allow a body of infinite size (not recommended).

### Serve files

To disable serving files from the www folder, you can set `SERVE_FILES` to `no` (default : `yes`). The value `no` is recommended if you use BunkerWeb as a reverse proxy.

### Headers

Headers are very important when it comes to HTTP security. Not only some of them are too verbose but others can add some security, especially on the client-side.

#### Remove headers

You can automatically remove verbose headers in the HTTP responses by using the `REMOVE_HEADERS` setting (default : `Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version`).

#### Cookies

When it comes to cookies security, we can use the following flags :

- HttpOnly : disable any access to the cookie from Javascript using document.cookie
- SameSite : policy when requests come from third-party websites
- Secure : only send cookies on HTTPS request

Cookie flags can be overridden with values of your choice by using the `COOKIE_FLAGS` setting (default : `* HttpOnly SameSite=Lax`). See [here](https://github.com/AirisX/nginx_cookie_flag_module) for accepted values.

The Secure flag can be automatically added if HTTPS is used by using the `COOKIE_AUTO_SECURE_FLAG` setting (default : `yes`). The value `no` is not recommended unless you know what you're doing.

#### Security headers

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

## HTTPS

Besides the HTTPS configuration, the following settings related to HTTPS can be set :

|            Setting            |      Default      | Description                                                                                                  |
| :---------------------------: | :---------------: | :----------------------------------------------------------------------------------------------------------- |
|   `REDIRECT_HTTP_TO_HTTPS`    |       `no`        | When set to `yes`, will redirect every HTTP request to HTTPS even if BunkerWeb is not configured with HTTPS. |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` |       `yes`       | When set to `yes`, will redirect every HTTP request to HTTPS only if BunkerWeb is configured with HTTPS.     |
|       `HTTPS_PROTOCOLS`       | `TLSv1.2 TLSv1.3` | List of supported SSL/TLS protocols when HTTPS is enabled.                                                   |
|            `HTTP2`            |       `yes`       | When set to `yes`, will enable HTTP2 protocol support when using HTTPS.                                      |
|         `LISTEN_HTTP`         |       `yes`       | When set to `no`, BunkerWeb will not listen for HTTP requests. Useful if you want HTTPS only for example.    |

### Let's Encrypt

BunkerWeb comes with automatic Let's Encrypt certificate generation and renewal. This is the easiest way of getting HTTPS working out of the box for public-facing web applications. Please note that you will need to set up proper DNS A record(s) for each of your domains pointing to your public IP(s) where BunkerWeb is accessible.

Here is the list of related settings :

|          Setting           |         Default          | Description                                                                                                                                                        |
| :------------------------: | :----------------------: | :----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|    `AUTO_LETS_ENCRYPT`     |           `no`           | When set to `yes`, HTTPS will be enabled with automatic certificate generation and renewal from Let's Encrypt.                                                     |
|    `EMAIL_LETS_ENCRYPT`    | `contact@{FIRST_SERVER}` | Email to use when generating certificates. Let's Encrypt will send notifications to that email like certificate expiration.                                        |
| `USE_LETS_ENCRYPT_STAGING` |           `no`           | When set to `yes`, the staging server of Let's Encrypt will be used instead of the production one. Useful when doing tests to avoid being "blocked" due to limits. |

### Custom certificate

If you want to use your own certificates, here is the list of related settings :

|       Setting       | Default | Description                                                                                                                                                                                                                             |
| :-----------------: | :-----: | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CUSTOM_HTTPS`  |  `no`   | When set to `yes`, HTTPS will be enabled with custom certificates.                                                                                                                                                                      |
| `CUSTOM_HTTPS_CERT` |         | Full path to the certificate. If you have one or more intermediate certificate(s) in your chain of trust, you will need to provide the bundle (more info [here](https://nginx.org/en/docs/http/configuring_https_servers.html#chains)). |
| `CUSTOM_HTTPS_KEY`  |         | Full path to the private key.                                                                                                                                                                                                           |

When `USE_CUSTOM_HTTPS` is set to `yes`, BunkerWeb will check every day if the custom certificate specified in `CUSTOM_HTTPS_CERT` is modified and will reload NGINX if that's the case.

### Self-signed

If you want to quickly test HTTPS for staging/dev environment you can configure BunkerWeb to generate self-signed certificates, here is the list of related

|          Setting           |        Default         | Description                                                                                                                |
| :------------------------: | :--------------------: | :------------------------------------------------------------------------------------------------------------------------- |
| `GENERATE_SELF_SIGNED_SSL` |          `no`          | When set to `yes`, HTTPS will be enabled with automatic self-signed certificate generation and renewal from Let's Encrypt. |
|  `SELF_SIGNED_SSL_EXPIRY`  |         `365`          | Number of days for the certificate expiration (**-days** value used with **openssl**).                                     |
|   `SELF_SIGNED_SSL_SUBJ`   | `/CN=www.example.com/` | Certificate subject to use (**-subj** value used with **openssl**).                                                        |

## ModSecurity

ModSecurity is integrated and enabled by default alongside the OWASP Core Rule Set within BunkerWeb. Here is the list of related settings :

|        Setting        | Default | Description                                                                                           |
| :-------------------: | :-----: | :---------------------------------------------------------------------------------------------------- |
|   `USE_MODSECURITY`   |  `yes`  | When set to `yes`, ModSecurity will be enabled.                                                       |
| `USE_MODSECURITY_CRS` |  `yes`  | When set to `yes` and `USE_MODSECURITY` is also set to `yes`, the OWASP Core Rule Set will be loaded. |

We strongly recommend keeping both ModSecurity and the OWASP Core Rule Set enabled. The only downsides are the false positives that may occur. But they can be fixed with some efforts and the CRS team maintains a list of exclusions for common applications (e.g., WordPress, Nextcloud, Drupal, Cpanel, ...).

Tuning ModSecurity and the CRS can be done using [custom configurations](/quickstart-guide/#custom-configurations) :

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

When attackers search for and/or exploit vulnerabilities they might generate some "suspicious" HTTP status codes that a "regular" user won’t generate within a period of time. If we detect that kind of behavior we can ban the offending IP address and force the attacker to come up with a new one.

That kind of security measure is implemented and enabled by default in BunkerWeb and is called "Bad behavior". Here is the list of the related settings :

|           Setting           |            Default            | Description                                                                  |
| :-------------------------: | :---------------------------: | :--------------------------------------------------------------------------- |
|     `USE_BAD_BEHAVIOR`      |             `yes`             | When set to `yes`, the Bad behavior feature will be enabled.                 |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | List of HTTP status codes considered as "suspicious".                        |
|   `BAD_BEHAVIOR_BAN_TIME`   |            `86400`            | The duration time (in seconds) of a ban when a client reached the threshold. |
|  `BAD_BEHAVIOR_THRESHOLD`   |             `10`              | Maximum number of "suspicious" HTTP status codes within the time period.     |
|  `BAD_BEHAVIOR_COUNT_TIME`  |             `60`              | Period of time where we count "suspicious" HTTP status codes.                |

In other words, with the default values, if a client generates more than `10` status codes from the list `400 401 403 404 405 429 444` within `60` seconds his IP address will be banned for `86400` seconds.

## Antibot

Attackers will certainly use automated tools to exploit/find some vulnerabilities in your web applications. One countermeasure is to challenge the users to detect if they look like a bot. If the challenge is solved, we consider the client as "legitimate" and he can access the web application.

That kind of security is implemented but not enabled by default in BunkerWeb and is called "Antibot". Here is the list of supported challenges :

- **Cookie** : send a cookie to the client, we expect to get the cookie back on other requests
- **Javascript** : force a client to solve a computation challenge using Javascript
- **Captcha** : force the client to solve a classical captcha (no external dependencies)
- **hCaptcha** : force the client to solve a captcha from hCaptcha
- **reCAPTCHA** : force the client to get a minimum score with Google reCAPTCHA

Here is the list of related settings :

|                          Setting                           |   Default    | Description                                                                                                                                                                     |
| :--------------------------------------------------------: | :----------: | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
|                       `USE_ANTIBOT`                        |     `no`     | Accepted values to enable Antibot feature : `cookie`, `javascript`, `captcha`, `hcaptcha` and `recaptcha`.                                                                      |
|                       `ANTIBOT_URI`                        | `/challenge` | URI that clients will be redirected to in order to solve the challenge. Be sure that it isn't used in your web application.                                                     |
|                  `ANTIBOT_SESSION_SECRET`                  |   `random`   | The secret used to encrypt cookies when using Antibot. The special value `random` will generate one for you. Be sure to set it when you use a clustered integration (32 chars). |
| `ANTIBOT_HCAPTCHA_SITEKEY` and `ANTIBOT_RECAPTCHA_SITEKEY` |              | The Sitekey value to use when `USE_ANTIBOT` is set to `hcaptcha` or `recaptcha`.                                                                                                |
|  `ANTIBOT_HCAPTCHA_SECRET` and `ANTIBOT_RECAPTCHA_SECRET`  |              | The Secret value to use when `USE_ANTIBOT` is set to `hcaptcha` or `recaptcha`.                                                                                                 |
|                 `ANTIBOT_RECAPTCHA_SCORE`                  |    `0.7`     | The minimum score that clients must have when `USE_ANTIBOT` is set to `recaptcha`.                                                                                              |

## Blacklisting and whitelisting

The blacklisting security feature is very easy to understand : if a specific criteria is met, the client will be banned. As for the whitelisting, it's the exact opposite : if a specific criteria is met, the client will be allowed and no additional security check will be done.

You can configure blacklisting and whitelisting at the same time. If that's the case, note that whitelisting is executed before blacklisting : if a criteria is true for both, the client will be whitelisted.

### Blacklisting

You can use the following settings to setup blacklisting :

|           Setting           |                                                            Default                                                             | Description                                                                                   |
| :-------------------------: | :----------------------------------------------------------------------------------------------------------------------------: | :-------------------------------------------------------------------------------------------- |
|       `USE_BLACKLIST`       |                                                             `yes`                                                              | When set to `yes`, will enable blacklisting based on various criteria.                        |
|       `BLACKLIST_IP`        |                                                                                                                                | List of IPs and networks to blacklist.                                                        |
|     `BLACKLIST_IP_URLS`     |                                             `https://www.dan.me.uk/torlist/?exit`                                              | List of URL containing IP and network to blacklist. The default list contains TOR exit nodes. |
|      `BLACKLIST_RDNS`       |                                                    `.shodan.io .censys.io`                                                     | List of reverse DNS to blacklist.                                                             |
|    `BLACKLIST_RDNS_URLS`    |                                                                                                                                | List of URLs containing reverse DNS to blacklist.                                             |
|       `BLACKLIST_ASN`       |                                                                                                                                | List of ASN to blacklist.                                                                     |
|    `BLACKLIST_ASN_URLS`     |                                                                                                                                | List of URLs containing ASN to blacklist.                                                     |
|   `BLACKLIST_USER_AGENT`    |                                                                                                                                | List of User-Agents to blacklist.                                                             |
| `BLACKLIST_USER_AGENT_URLS` | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` | List of URLs containing User-Agent(s) to blacklist.                                           |
|       `BLACKLIST_URI`       |                                                                                                                                | List of requests URI to blacklist.                                                            |
|    `BLACKLIST_URI_URLS`     |                                                                                                                                | List of URLs containing request URI to blacklist.                                             |

### Whitelisting

You can use the following settings to setup whitelisting :

|           Setting           |                                                                                           Default                                                                                            | Description                                                                                                              |
| :-------------------------: | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------------------------------------------- |
|       `USE_WHITELIST`       |                                                                                            `yes`                                                                                             | When set to `yes`, will enable blacklisting based on various criteria.                                                   |
|       `WHITELIST_IP`        | `20.191.45.212 40.88.21.235 40.76.173.151 40.76.163.7 20.185.79.47 52.142.26.175 20.185.79.15 52.142.24.149 40.76.162.208 40.76.163.23 40.76.162.191 40.76.162.247 54.208.102.37 107.21.1.8` | List of IP and network to whitelist. The default list contains IP from DuckDuckGo crawler.                               |
|     `WHITELIST_IP_URLS`     |                                                                                              ``                                                                                              | List of URLs containing IP and network to whitelist.                                                                     |
|      `WHITELIST_RDNS`       |         `.google.com .googlebot.com .yandex.ru .yandex.net .yandex.com .search.msn.com .baidu.com .baidu.jp .crawl.yahoo.net .fwd.linkedin.com .twitter.com .twttr.com .discord.com`         | List of reverse DNS to whitelist. Default list contains various reverse DNS of search engines and social media crawlers. |
|    `WHITELIST_RDNS_URLS`    |                                                                                                                                                                                              | List of URLs containing reverse DNS to whitelist.                                                                        |
|       `WHITELIST_ASN`       |                                                                                           `32934`                                                                                            | List of ASN to whitelist. The default list contains the ASN of Facebook.                                                 |
|    `WHITELIST_ASN_URLS`     |                                                                                                                                                                                              | List of URL containing ASN to whitelist.                                                                                 |
|   `WHITELIST_USER_AGENT`    |                                                                                                                                                                                              | List of User-Agent to whitelist.                                                                                         |
| `WHITELIST_USER_AGENT_URLS` |                                                                                                                                                                                              | List of URLs containing User-Agent to whitelist.                                                                         |
|       `WHITELIST_URI`       |                                                                                                                                                                                              | List of requests URI to whitelist.                                                                                       |
|    `WHITELIST_URI_URLS`     |                                                                                                                                                                                              | List of URLs containing request(s) URI to whitelist.                                                                     |

## BunkerNet

BunkerNet is a crowdsourced database of malicious requests shared between all BunkerWeb instances over the world.

If you enable BunkerNet, malicious requests will be sent to a remote server and will be analyzed by our systems. By doing so, we can extract malicious data from everyone's reports and give back the results to each BunkerWeb instances participating into BunkerNet.

At the moment, that feature should be considered in "beta". We only extract malicious IP and we are very strict about how we do it to avoid any "poisoning". We strongly recommend activating it (which is the default) because the more instances participate, the more data we have to improve the algorithm.

The setting used to enable or disable BunkerNet is `USE_BUNKERNET` (default : `yes`).

## DNSBL

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

Please note that it should not be considered as an effective solution against DoS or DDoS but rather an anti-bruteforce measure or rate limit policy for API.

In both cases (connections or requests) if the limit is reached, the client will receive the HTTP status "429 - Too Many Requests".

### Connections

The following settings are related to the Limiting connections feature :

|        Setting         | Default | Description                                                                                |
| :--------------------: | :-----: | :----------------------------------------------------------------------------------------- |
|    `USE_LIMIT_CONN`    |  `yes`  | When set to `yes`, will limit the maximum number of concurrent connections for a given IP. |
| `LIMIT_CONN_MAX_HTTP1` |  `10`   | Maximum number of concurrent connections when using HTTP1 protocol.                        |
| `LIMIT_CONN_MAX_HTTP2` |  `100`  | Maximum number of concurrent streams when using HTTP2 protocol.                            |

### Requests

The following settings are related to the Limiting requests feature :

|     Setting      | Default | Description                                                                                                                                                                                |
| :--------------: | :-----: | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_LIMIT_REQ`  |  `yes`  | When set to `yes`, will limit the number of requests for a given IP on each URL with a period of time.                                                                                     |
| `LIMIT_REQ_URL`  |   `/`   | The URL that will be limited. The special URL `/` will define a default limit for all URLs.                                                                                                |
| `LIMIT_REQ_RATE` | `2r/s`  | The limit to apply to the corresponding URL. Syntax is `Xr/Y` where **X** is the number of request(s) and **Y** the period of time (s for second, m for minute, h for hour and d for day). |

Please note that you can add different rate for different URLs by adding a number to suffix to the settings for example : `LIMIT_REQ_URL_1=/url1`, `LIMIT_REQ_RATE_1=5r/d`, `LIMIT_REQ_URL_2=/url2`, `LIMIT_REQ_RATE_2=1r/m`, ...

Another important thing to note is that `LIMIT_REQ_URL` accepts LUA patterns.

## Country

The country security feature allows you to apply policy based on the country of the IP address of clients :

- Deny any access if the country is in a blacklist
- Only allow access if the country is in a whitelist (other security checks will still be executed)

Here is the list of related settings :

|       Setting       | Default | Description                                  |
| :-----------------: | :-----: | :------------------------------------------- |
| `BLACKLIST_COUNTRY` |         | List of 2 letters country code to blacklist. |
| `WHITELIST_COUNTRY` |         | List of 2 letters country code to whitelist. |

Using both country blacklist and whitelist at the same time makes no sense. If you do please note that only the whitelist will be executed.

## Authentication

You can quickly protect sensitive resources like the admin area for example by requiring HTTP basic authentication. Here is the list of related settings :

|          Setting          |      Default      | Description                                                                                  |
| :-----------------------: | :---------------: | :------------------------------------------------------------------------------------------- |
|     `USE_AUTH_BASIC`      |       `no`        | When set to `yes` HTTP auth basic will be enabled.                                           |
|   `AUTH_BASIC_LOCATION`   |    `sitewide`     | Location (URL) of the sensitive resource. Use special value `sitewide` to enable everywhere. |
|   `USE_AUTH_BASIC_USER`   |    `changeme`     | The username required.                                                                       |
| `USE_AUTH_BASIC_PASSWORD` |    `changeme`     | The password required.                                                                       |
|   `USE_AUTH_BASIC_TEXT`   | `Restricted area` | Text to display in the auth prompt.                                                          |
