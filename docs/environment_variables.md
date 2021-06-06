# List of environment variables

## nginx

### Misc

`MULTISITE`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*  
When set to *no*, only one server block will be generated. Otherwise one server per host defined in the `SERVER_NAME` environment variable will be generated.  
Any environment variable tagged as *multisite* context can be used for a specific server block with the following format : *host_VARIABLE=value*. If the variable is used without the host prefix it will be applied to all the server blocks (but still can be overriden).

`SERVER_NAME`  
Values : *&lt;first name&gt; &lt;second name&gt; ...*  
Default value : *www.bunkerity.com*  
Context : *global*, *multisite*  
Sets the host names of the webserver separated with spaces. This must match the Host header sent by clients.  
Useful when used with `MULTISITE=yes` and/or `AUTO_LETSENCRYPT=yes` and/or `DISABLE_DEFAULT_SERVER=yes`.

`MAX_CLIENT_SIZE`  
Values : *0* | *Xm*  
Default value : *10m*  
Context : *global*, *multisite*  
Sets the maximum body size before nginx returns a 413 error code.  
Setting to 0 means "infinite" body size.

`ALLOWED_METHODS`  
Values : *allowed HTTP methods separated with | char*  
Default value : *GET|POST|HEAD*  
Context : *global*, *multisite*  
Only the HTTP methods listed here will be accepted by nginx. If not listed, nginx will close the connection.

`DISABLE_DEFAULT_SERVER`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*  
If set to yes, nginx will only respond to HTTP request when the Host header match a FQDN specified in the `SERVER_NAME` environment variable.  
For example, it will close the connection if a bot access the site with direct ip.

`SERVE_FILES`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, nginx will serve files from /www directory within the container.  
A use case to not serving files is when you setup bunkerized-nginx as a reverse proxy.

`DNS_RESOLVERS`  
Values : *\<two IP addresses separated with a space\>*  
Default value : *127.0.0.11*  
Context : *global*  
The IP addresses of the DNS resolvers to use when performing DNS lookups.

`ROOT_FOLDER`  
Values : *\<any valid path to web files\>*  
Default value : */www*  
Context : *global*  
The default folder where nginx will search for web files. Don't change it unless you know what you are doing.

`ROOT_SITE_SUBFOLDER`  
Values : *\<any valid directory name\>*  
Default value :  
Context : *global*, *multisite*  
The subfolder where nginx will search for site web files.

`LOG_FORMAT`  
Values : *\<any values accepted by the log_format directive\>*  
Default value : *$host $remote_addr - $remote_user \[$time_local\] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"*  
Context : *global*  
The log format used by nginx to generate logs. More info [here](http://nginx.org/en/docs/http/ngx_http_log_module.html#log_format).

`LOG_LEVEL`  
Values : *debug, info, notice, warn, error, crit, alert, or emerg*  
Default value : *info*  
Context : *global*  
The level of logging : *debug* means more logs and *emerg* means less logs. More info [here](https://nginx.org/en/docs/ngx_core_module.html#error_log).

`HTTP_PORT`  
Values : *\<any valid port greater than 1024\>*  
Default value : *8080*  
Context : *global*  
The HTTP port number used by nginx inside the container.

`HTTPS_PORT`  
Values : *\<any valid port greater than 1024\>*  
Default value : *8443*  
Context : *global*  
The HTTPS port number used by nginx inside the container.

`WORKER_CONNECTIONS`
Values : *\<any positive integer\>*  
Default value : 1024  
Context : *global*  
Sets the value of the [worker_connections](https://nginx.org/en/docs/ngx_core_module.html#worker_connections) directive.

`WORKER_RLIMIT_NOFILE`
Values : *\<any positive integer\>*  
Default value : 2048  
Context : *global*  
Sets the value of the [worker_rlimit_nofile](https://nginx.org/en/docs/ngx_core_module.html#worker_rlimit_nofile) directive.

### Information leak

`SERVER_TOKENS`  
Values : *on* | *off*  
Default value : *off*  
Context : *global*  
If set to on, nginx will display server version in Server header and default error pages.

`REMOVE_HEADERS`  
Values : \<*list of headers separated with space*\>  
Default value : *Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version*  
Context : *global*, *multisite*  
List of header to remove when sending responses to clients.

### Custom error pages

`ERRORS`  
Values : *\<error1=/page1 error2=/page2\>*  
Default value :  
Context : *global*, *multisite*  
Use this kind of environment variable to define custom error page depending on the HTTP error code. Replace errorX with HTTP code.  
Example : `ERRORS=404=/404.html 403=/403.html` the /404.html page will be displayed when 404 code is generated (same for 403 and /403.html page). The path is relative to the root web folder.

### HTTP basic authentication

`USE_AUTH_BASIC`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
If set to yes, enables HTTP basic authentication at the location `AUTH_BASIC_LOCATION` with user `AUTH_BASIC_USER` and password `AUTH_BASIC_PASSWORD`.

`AUTH_BASIC_LOCATION`  
Values : *sitewide* | */somedir* | *\<any valid location\>*  
Default value : *sitewide*  
Context : *global*, *multisite*  
The location to restrict when `USE_AUTH_BASIC` is set to *yes*. If the special value *sitewide* is used then auth basic will be set at server level outside any location context.

`AUTH_BASIC_USER`  
Values : *\<any valid username\>*  
Default value : *changeme*  
Context : *global*, *multisite*  
The username allowed to access `AUTH_BASIC_LOCATION` when `USE_AUTH_BASIC` is set to yes.

`AUTH_BASIC_PASSWORD`  
Values : *\<any valid password\>*  
Default value : *changeme*  
Context : *global*, *multisite*  
The password of `AUTH_BASIC_USER` when `USE_AUTH_BASIC` is set to yes.

`AUTH_BASIC_TEXT`  
Values : *\<any valid text\>*  
Default value : *Restricted area*  
Context : *global*, *multisite*  
The text displayed inside the login prompt when `USE_AUTH_BASIC` is set to yes.

### Reverse proxy

`USE_REVERSE_PROXY`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
Set this environment variable to *yes* if you want to use bunkerized-nginx as a reverse proxy.

`REVERSE_PROXY_URL`  
Values : \<*any valid location path*\>  
Default value :  
Context : *global*, *multisite*  
Only valid when `USE_REVERSE_PROXY` is set to *yes*. Let's you define the location path to match when acting as a reverse proxy.  
You can set multiple url/host by adding a suffix number to the variable name like this : `REVERSE_PROXY_URL_1`, `REVERSE_PROXY_URL_2`, `REVERSE_PROXY_URL_3`, ...

`REVERSE_PROXY_HOST`  
Values : \<*any valid proxy_pass value*\>  
Default value :  
Context : *global*, *multisite*  
Only valid when `USE_REVERSE_PROXY` is set to *yes*. Let's you define the proxy_pass destination to use when acting as a reverse proxy.  
You can set multiple url/host by adding a suffix number to the variable name like this : `REVERSE_PROXY_HOST_1`, `REVERSE_PROXY_HOST_2`, `REVERSE_PROXY_HOST_3`, ...

`REVERSE_PROXY_WS`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
Only valid when `USE_REVERSE_PROXY` is set to *yes*. Set it to *yes* when the corresponding `REVERSE_PROXY_HOST` is a WebSocket server.  
You can set multiple url/host by adding a suffix number to the variable name like this : `REVERSE_PROXY_WS_1`, `REVERSE_PROXY_WS_2`, `REVERSE_PROXY_WS_3`, ...

`REVERSE_PROXY_HEADERS`  
Values : *\<list of custom headers separated with a semicolon like this : header1 value1;header2 value2...\>* 
Default value :  
Context : *global*, *multisite*  
Only valid when `USE_REVERSE_PROXY` is set to *yes*.  
You can set multiple url/host by adding a suffix number to the variable name like this : `REVERSE_PROXY_HEADERS_1`, `REVERSE_PROXY_HEADERS_2`, `REVERSE_PROXY_HEADERS_3`, ...

`PROXY_REAL_IP`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
Set this environment variable to *yes* if you're using bunkerized-nginx behind a reverse proxy. This means you will see the real client address instead of the proxy one inside your logs. Ssecurity tools will also then work correctly.

`PROXY_REAL_IP_FROM`  
Values : *\<list of trusted IP addresses and/or networks separated with spaces\>*  
Default value : *192.168.0.0/16 172.16.0.0/12 10.0.0.0/8*  
Context : *global*, *multisite*  
When `PROXY_REAL_IP` is set to *yes*, lets you define the trusted IPs/networks allowed to send the correct client address.

`PROXY_REAL_IP_HEADER`  
Values : *X-Forwarded-For* | *X-Real-IP* | *custom header*  
Default value : *X-Forwarded-For*  
Context : *global*, *multisite*  
When `PROXY_REAL_IP` is set to *yes*, lets you define the header that contains the real client IP address.

`PROXY_REAL_IP_RECURSIVE`  
Values : *on* | *off*  
Default value : *on*  
Context : *global*, *multisite*  
When `PROXY_REAL_IP` is set to *yes*, setting this to *on* avoid spoofing attacks using the header defined in `PROXY_REAL_IP_HEADER`.

### Compression

`USE_GZIP`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
When set to *yes*, nginx will use the gzip algorithm to compress responses sent to clients.

`GZIP_COMP_LEVEL`  
Values : \<*any integer between 1 and 9*\>  
Default value : *5*  
Context : *global*, *multisite*  
The gzip compression level to use when `USE_GZIP` is set to *yes*.

`GZIP_MIN_LENGTH`  
Values : \<*any positive integer*\>  
Default value : *1000*  
Context : *global*, *multisite*  
The minimum size (in bytes) of a response required to compress when `USE_GZIP` is set to *yes*.

`GZIP_TYPES`  
Values : \<*list of mime types separated with space*\>  
Default value : *application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml*  
Context : *global*, *multisite*  
List of response MIME type required to compress when `USE_GZIP` is set to *yes*.

`USE_BROTLI`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
When set to *yes*, nginx will use the brotli algorithm to compress responses sent to clients.

`BROTLI_COMP_LEVEL`  
Values : \<*any integer between 1 and 9*\>  
Default value : *5*  
Context : *global*, *multisite*  
The brotli compression level to use when `USE_BROTLI` is set to *yes*.

`BROTLI_MIN_LENGTH`  
Values : \<*any positive integer*\>  
Default value : *1000*  
Context : *global*, *multisite*  
The minimum size (in bytes) of a response required to compress when `USE_BROTLI` is set to *yes*.

`BROTLI_TYPES`  
Values : \<*list of mime types separated with space*\>  
Default value : *application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml*  
Context : *global*, *multisite*  
List of response MIME type required to compress when `USE_BROTLI` is set to *yes*.

### Cache

`USE_CLIENT_CACHE`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
When set to *yes*, clients will be told to cache some files locally.

`CLIENT_CACHE_EXTENSIONS`  
Values : \<*list of extensions separated with |*\>  
Default value : *jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2*  
Context : *global*, *multisite*  
List of file extensions that clients should cache when `USE_CLIENT_CACHE` is set to *yes*.

`CLIENT_CACHE_CONTROL`  
Values : \<*Cache-Control header value*\>  
Default value : *public, max-age=15552000*  
Context : *global*, *multisite*  
Content of the [Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control) header to send when `USE_CLIENT_CACHE` is set to *yes*.

`CLIENT_CACHE_ETAG`  
Values : *on* | *off*  
Default value : *on*  
Context : *global*, *multisite*  
Whether or not nginx will send the [ETag](https://en.wikipedia.org/wiki/HTTP_ETag) header when `USE_CLIENT_CACHE` is set to *yes*.

`USE_OPEN_FILE_CACHE`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
When set to *yes*, nginx will cache open fd, existence of directories, ... See [open_file_cache](http://nginx.org/en/docs/http/ngx_http_core_module.html#open_file_cache).

`OPEN_FILE_CACHE`  
Values : \<*any valid open_file_cache parameters*\>  
Default value : *max=1000 inactive=20s*  
Context : *global*, *multisite*  
Parameters to use with open_file_cache when `USE_OPEN_FILE_CACHE` is set to *yes*.

`OPEN_FILE_CACHE_ERRORS`  
Values : *on* | *off*  
Default value : *on*  
Context : *global*, *multisite*  
Whether or not nginx should cache file lookup errors when `USE_OPEN_FILE_CACHE` is set to *yes*.

`OPEN_FILE_CACHE_MIN_USES`  
Values : \<*any valid integer *\>  
Default value : *2*  
Context : *global*, *multisite*  
The minimum number of file accesses required to cache the fd when `USE_OPEN_FILE_CACHE` is set to *yes*.

`OPEN_FILE_CACHE_VALID`  
Values : \<*any time value like Xs, Xm, Xh, ...*\>  
Default value : *30s*  
Context : *global*, *multisite*  
The time after which cached elements should be validated when `USE_OPEN_FILE_CACHE` is set to *yes*.

`USE_PROXY_CACHE`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
When set to *yes*, nginx will cache responses from proxied applications. See [proxy_cache](http://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_cache).

`PROXY_CACHE_PATH_ZONE_SIZE`  
Values : \<*any valid size like Xk, Xm, Xg, ...*\>  
Default value : *10m*  
Context : *global*, *multisite*  
Maximum size of cached metadata when `USE_PROXY_CACHE` is set to *yes*.
 
`PROXY_CACHE_PATH_PARAMS`  
Values : \<*any valid parameters to proxy_cache_path directive*\>  
Default value : *max_size=100m*  
Context : *global*, *multisite*  
Parameters to use for [proxy_cache_path](http://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_cache_path) directive when `USE_PROXY_CACHE` is set to *yes*.

`PROXY_CACHE_METHODS`  
Values : \<*list of HTTP methods separated with space*\>  
Default value : *GET HEAD*  
Context : *global*, *multisite*  
The HTTP methods that should trigger a cache operation when `USE_PROXY_CACHE` is set to *yes*.
 
`PROXY_CACHE_MIN_USES`  
Values : \<*any positive integer*\>  
Default value : *2*  
Context : *global*, *multisite*  
The minimum number of requests before the response is cached when `USE_PROXY_CACHE` is set to *yes*.

`PROXY_CACHE_KEY`  
Values : \<*list of variables*\>  
Default value : *$scheme$host$request_uri*  
Context : *global*, *multisite*  
The key used to uniquely identify a cached response when `USE_PROXY_CACHE` is set to *yes*.

`PROXY_CACHE_VALID`  
Values : \<*status=time list separated with space*\>  
Default value : *200=10m 301=10m 302=1h*  
Context : *global*, *multisite*  
Define the caching time depending on the HTTP status code (list of status=time separated with space) when `USE_PROXY_CACHE` is set to *yes*.

`PROXY_NO_CACHE`  
Values : \<*list of variables*\>  
Default value : *$http_authorization*  
Context : *global*, *multisite*  
Conditions that must be met to disable caching of the response when `USE_PROXY_CACHE` is set to *yes*.

`PROXY_CACHE_BYPASS`  
Values : \<*list of variables*\>
Default value : *$http_authorization*  
Context : *global*, *multisite* 
Conditions that must be met to bypass the cache when `USE_PROXY_CACHE` is set to *yes*.

## HTTPS

### Let's Encrypt

`AUTO_LETS_ENCRYPT`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
If set to yes, automatic certificate generation and renewal will be setup through Let's Encrypt. This will enable HTTPS on your website for free.  
You will need to redirect the 80 port to 8080 port inside container and also set the `SERVER_NAME` environment variable.

`EMAIL_LETS_ENCRYPT`  
Values : *contact@yourdomain.com*  
Default value : *contact@first-domain-in-server-name*  
Context : *global*, *multisite*  
Define the contact email address declare in the certificate.

### HTTP

`LISTEN_HTTP`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to no, nginx will not in listen on HTTP (port 80).  
Useful if you only want HTTPS access to your website.

`REDIRECT_HTTP_TO_HTTPS`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
If set to yes, nginx will redirect all HTTP requests to HTTPS.  

### Custom certificate

`USE_CUSTOM_HTTPS`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
If set to yes, HTTPS will be enabled with certificate/key of your choice.  

`CUSTOM_HTTPS_CERT`  
Values : *\<any valid path inside the container\>*  
Default value :  
Context : *global*, *multisite*  
Full path of the certificate or bundle file to use when `USE_CUSTOM_HTTPS` is set to yes. If your chain of trust contains one or more intermediate certificate(s), you will need to bundle them into a single file (more info [here](https://nginx.org/en/docs/http/configuring_https_servers.html#chains)).  

`CUSTOM_HTTPS_KEY`  
Values : *\<any valid path inside the container\>*  
Default value :  
Context : *global*, *multisite*  
Full path of the key file to use when `USE_CUSTOM_HTTPS` is set to yes.  

### Self-signed certificate

`GENERATE_SELF_SIGNED_SSL`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
If set to yes, HTTPS will be enabled with a container generated self-signed certificate.

`SELF_SIGNED_SSL_EXPIRY`  
Values : *integer*  
Default value : *365* (1 year)  
Context : *global*, *multisite*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the expiry date for the self generated certificate.

`SELF_SIGNED_SSL_COUNTRY`  
Values : *text*  
Default value : *Switzerland*  
Context : *global*, *multisite*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the country for the self generated certificate.

`SELF_SIGNED_SSL_STATE`  
Values : *text*, *multisite*  
Default value : *Switzerland*  
Context : *global*, *multisite*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the state for the self generated certificate.

`SELF_SIGNED_SSL_CITY`  
Values : *text*  
Default value : *Bern*  
Context : *global*, *multisite*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the city for the self generated certificate.

`SELF_SIGNED_SSL_ORG`  
Values : *text*  
Default value : *AcmeInc*  
Context : *global*, *multisite*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the organisation name for the self generated certificate.

`SELF_SIGNED_SSL_OU`  
Values : *text*  
Default value : *IT*  
Context : *global*, *multisite*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the organisitional unit for the self generated certificate.

`SELF_SIGNED_SSL_CN`  
Values : *text*  
Default value : *bunkerity-nginx*  
Context : *global*, *multisite*  
Needs `GENERATE_SELF_SIGNED_SSL` to work.
Sets the CN server name for the self generated certificate.

### Misc

`HTTP2`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, nginx will use HTTP2 protocol when HTTPS is enabled.  

`HTTPS_PROTOCOLS`  
Values : *TLSv1.2* | *TLSv1.3* | *TLSv1.2 TLSv1.3*  
Default value : *TLSv1.2 TLSv1.3*  
Context : *global*, *multisite*  
The supported version of TLS. We recommend the default value *TLSv1.2 TLSv1.3* for compatibility reasons.

## ModSecurity

`USE_MODSECURITY`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, the ModSecurity WAF will be enabled.  
You can include custom rules by adding .conf files into the /modsec-confs/ directory inside the container (i.e : through a volume).  

`USE_MODSECURITY_CRS`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, the [OWASP ModSecurity Core Rule Set](https://coreruleset.org/) will be used. It provides generic rules to detect common web attacks.  
You can customize the CRS (i.e. : add WordPress exclusions) by adding custom .conf files into the /modsec-crs-confs/ directory inside the container (i.e : through a volume). Files inside this directory are included before the CRS rules. If you need to tweak (i.e. : SecRuleUpdateTargetById) put .conf files inside the /modsec-confs/ which is included after the CRS rules.

`MODSECURITY_SEC_AUDIT_ENGINE`  
Values : *On* | *Off* | *RelevantOnly*  
Default value : *RelevantOnly*  
Context : *global*, *multisite*  
Sets the value of the [SecAuditEngine directive](https://github.com/SpiderLabs/ModSecurity/wiki/Reference-Manual-%28v2.x%29#SecAuditEngine) of ModSecurity.

## Security headers

`X_FRAME_OPTIONS`  
Values : *DENY* | *SAMEORIGIN* | *ALLOW-FROM https://www.website.net*
Default value : *DENY*  
Context : *global*, *multisite*  
Policy to be used when the site is displayed through iframe. Can be used to mitigate clickjacking attacks. 
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options).

`X_XSS_PROTECTION`  
Values : *0* | *1* | *1; mode=block*  
Default value : *1; mode=block*  
Context : *global*, *multisite*  
Policy to be used when XSS is detected by the browser. Only works with Internet Explorer.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-XSS-Protection).  

`X_CONTENT_TYPE_OPTIONS`  
Values : *nosniff*  
Default value : *nosniff*  
Context : *global*, *multisite*  
Tells the browser to be strict about MIME type.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options).

`REFERRER_POLICY`  
Values : *no-referrer* | *no-referrer-when-downgrade* | *origin* | *origin-when-cross-origin* | *same-origin* | *strict-origin* | *strict-origin-when-cross-origin* | *unsafe-url*  
Default value : *no-referrer*  
Context : *global*, *multisite*  
Policy to be used for the Referer header.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy).

`FEATURE_POLICY`  
Values : *&lt;directive&gt; &lt;allow list&gt;*  
Default value : *accelerometer 'none'; ambient-light-sensor 'none'; autoplay 'none'; camera 'none'; display-capture 'none'; document-domain 'none'; encrypted-media 'none'; fullscreen 'none'; geolocation 'none'; gyroscope 'none'; magnetometer 'none'; microphone 'none'; midi 'none'; payment 'none'; picture-in-picture 'none'; speaker 'none'; sync-xhr 'none'; usb 'none'; vibrate 'none'; vr 'none'*  
Context : *global*, *multisite*  
Tells the browser which features can be used on the website.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Feature-Policy).

`PERMISSIONS_POLICY`  
Values : *feature=(allow list)*  
Default value : accelerometer=(), ambient-light-sensor=(), autoplay=(), camera=(), display-capture=(), document-domain=(), encrypted-media=(), fullscreen=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), midi=(), payment=(), picture-in-picture=(), speaker=(), sync-xhr=(), usb=(), vibrate=(), vr=()  
Context : *global*, *multisite*  
Tells the browser which features can be used on the website.  
More info [here](https://www.w3.org/TR/permissions-policy-1/).

`COOKIE_FLAGS`  
Values : *\* HttpOnly* | *MyCookie secure SameSite=Lax* | *...*  
Default value : *\* HttpOnly SameSite=Lax*  
Context : *global*, *multisite*  
Adds some security to the cookies set by the server.  
Accepted value can be found [here](https://github.com/AirisX/nginx_cookie_flag_module).

`COOKIE_AUTO_SECURE_FLAG`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
When set to *yes*, the *secure* will be automatically added to cookies when using HTTPS.

`STRICT_TRANSPORT_SECURITY`  
Values : *max-age=expireTime [; includeSubDomains] [; preload]*  
Default value : *max-age=31536000*  
Context : *global*, *multisite*  
Tells the browser to use exclusively HTTPS instead of HTTP when communicating with the server.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security).

`CONTENT_SECURITY_POLICY`  
Values : *\<directive 1\>; \<directive 2\>; ...*  
Default value : *object-src 'none'; frame-ancestors 'self'; form-action 'self'; block-all-mixed-content; sandbox allow-forms allow-same-origin allow-scripts allow-popups allow-downloads; base-uri 'self';*  
Context : *global*, *multisite*  
Policy to be used when loading resources (scripts, forms, frames, ...).  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy).

## Blocking

### Antibot

`USE_ANTIBOT`  
Values : *no* | *cookie* | *javascript* | *captcha* | *recaptcha*  
Default value : *no*  
Context : *global*, *multisite*  
If set to another allowed value than *no*, users must complete a "challenge" before accessing the pages on your website :
- *cookie* : asks the users to set a cookie
- *javascript* : users must execute a javascript code
- *captcha* : a text captcha must be resolved by the users
- *recaptcha* : use [Google reCAPTCHA v3](https://developers.google.com/recaptcha/intro) score to allow/deny users 

`ANTIBOT_URI`  
Values : *\<any valid uri\>*  
Default value : */challenge*  
Context : *global*, *multisite*  
A valid and unused URI to redirect users when `USE_ANTIBOT` is used. Be sure that it doesn't exist on your website.

`ANTIBOT_SESSION_SECRET`  
Values : *random* | *\<32 chars of your choice\>*  
Default value : *random*  
Context : *global*, *multisite*  
A secret used to generate sessions when `USE_ANTIBOT` is set. Using the special *random* value will generate a random one. Be sure to use the same value when you are in a multi-server environment (so sessions are valid in all the servers).

`ANTIBOT_RECAPTCHA_SCORE`  
Values : *\<0.0 to 1.0\>*  
Default value : *0.7*  
Context : *global*, *multisite*  
The minimum score required when `USE_ANTIBOT` is set to *recaptcha*.

`ANTIBOT_RECAPTCHA_SITEKEY`  
Values : *\<public key given by Google\>*  
Default value :  
Context : *global*, *multisite*  
The sitekey given by Google when `USE_ANTIBOT` is set to *recaptcha*.

`ANTIBOT_RECAPTCHA_SECRET`  
Values : *\<private key given by Google\>*  
Default value :  
Context : *global*, *multisite*  
The secret given by Google when `USE_ANTIBOT` is set to *recaptcha*.

### External blacklists

`BLOCK_USER_AGENT`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, block clients with "bad" user agent.  
Blacklist can be found [here](https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list) and [here](https://raw.githubusercontent.com/JayBizzle/Crawler-Detect/master/raw/Crawlers.txt).

`BLOCK_TOR_EXIT_NODE`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
Is set to yes, will block known TOR exit nodes.  
Blacklist can be found [here](https://iplists.firehol.org/?ipset=tor_exits).

`BLOCK_PROXIES`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
Is set to yes, will block known proxies.  
Blacklist can be found [here](https://iplists.firehol.org/?ipset=firehol_proxies).

`BLOCK_ABUSERS`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
Is set to yes, will block known abusers.  
Blacklist can be found [here](https://iplists.firehol.org/?ipset=firehol_abusers_30d).

`BLOCK_REFERRER`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
Is set to yes, will block known bad referrer header.  
Blacklist can be found [here](https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-referrers.list).

### DNSBL

`USE_DNSBL`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to *yes*, DNSBL checks will be performed to the servers specified in the `DNSBL_LIST` environment variable.  

`DNSBL_LIST`  
Values : *\<list of DNS zones separated with spaces\>*  
Default value : *bl.blocklist.de problems.dnsbl.sorbs.net sbl.spamhaus.org xbl.spamhaus.org*  
Context : *global*, *multisite*  
The list of DNSBL zones to query when `USE_DNSBL` is set to *yes*.

### CrowdSec

`USE_CROWDSEC`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*, *multisite*  
If set to *yes*, [CrowdSec](https://github.com/crowdsecurity/crowdsec) will be enabled. Please note that you need a CrowdSec instance running see example [here](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/crowdsec).

`CROWDSEC_HOST`  
Values : *\<full URL to the CrowdSec instance API\>*  
Default value :  
Context : *global*  
The full URL to the CrowdSec API.

`CROWDSEC_KEY`  
Values : *\<CrowdSec bouncer key\>*  
Default value :  
Context : *global*  
The CrowdSec key given by *cscli bouncer add BouncerName*.

### Custom whitelisting

`USE_WHITELIST_IP`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to *yes*, lets you define custom IP addresses to be whitelisted through the `WHITELIST_IP_LIST` environment variable.

`WHITELIST_IP_LIST`  
Values : *\<list of IP addresses and/or network CIDR blocks separated with spaces\>*  
Default value : *23.21.227.69 40.88.21.235 50.16.241.113 50.16.241.114 50.16.241.117 50.16.247.234 52.204.97.54 52.5.190.19 54.197.234.188 54.208.100.253 54.208.102.37 107.21.1.8*  
Context : *global*, *multisite*  
The list of IP addresses and/or network CIDR blocks to whitelist when `USE_WHITELIST_IP` is set to *yes*. The default list contains IP addresses of the [DuckDuckGo crawler](https://help.duckduckgo.com/duckduckgo-help-pages/results/duckduckbot/).

`USE_WHITELIST_REVERSE`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to *yes*, lets you define custom reverse DNS suffixes to be whitelisted through the `WHITELIST_REVERSE_LIST` environment variable.

`WHITELIST_REVERSE_LIST`  
Values : *\<list of reverse DNS suffixes separated with spaces\>*  
Default value : *.googlebot.com .google.com .search.msn.com .crawl.yahoot.net .crawl.baidu.jp .crawl.baidu.com .yandex.com .yandex.ru .yandex.net*  
Context : *global*, *multisite*  
The list of reverse DNS suffixes to whitelist when `USE_WHITELIST_REVERSE` is set to *yes*. The default list contains suffixes of major search engines.

`WHITELIST_USER_AGENT`  
Values : *\<list of regexes separated with spaces\>*  
Default value :  
Context : *global*, *multisite*  
Whitelist user agent from being blocked by `BLOCK_USER_AGENT`.

`WHITELIST_URI`  
Values : *\<list of URI separated with spaces\>*  
Default value :  
Context : *global*, *multisite*  
URI listed here have security checks like bad user-agents, bad IP, ... disabled. Useful when using callbacks for example.

### Custom blacklisting

`USE_BLACKLIST_IP`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to *yes*, lets you define custom IP addresses to be blacklisted through the `BLACKLIST_IP_LIST` environment variable.

`BLACKLIST_IP_LIST`  
Values : *\<list of IP addresses and/or network CIDR blocks separated with spaces\>*  
Default value :  
Context : *global*, *multisite*  
The list of IP addresses and/or network CIDR blocks to blacklist when `USE_BLACKLIST_IP` is set to *yes*.

`USE_BLACKLIST_REVERSE`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to *yes*, lets you define custom reverse DNS suffixes to be blacklisted through the `BLACKLIST_REVERSE_LIST` environment variable.

`BLACKLIST_REVERSE_LIST`  
Values : *\<list of reverse DNS suffixes separated with spaces\>*  
Default value : *.shodan.io*  
Context : *global*, *multisite*  
The list of reverse DNS suffixes to blacklist when `USE_BLACKLIST_REVERSE` is set to *yes*.

### Requests limiting

`USE_LIMIT_REQ`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, the amount of HTTP requests made by a user for a given resource will be limited during a period of time.  
More info rate limiting [here](https://www.nginx.com/blog/rate-limiting-nginx/) (the key used is $binary_remote_addr$uri).

`LIMIT_REQ_RATE`  
Values : *Xr/s* | *Xr/m*  
Default value : *1r/s*  
Context : *global*, *multisite*  
The rate limit to apply when `USE_LIMIT_REQ` is set to *yes*. Default is 1 request to the same URI and from the same IP per second.

`LIMIT_REQ_BURST`  
Values : *<any valid integer\>*  
Default value : *2*  
Context : *global*, *multisite*  
The number of requests to put in queue before rejecting requests.

`LIMIT_REQ_CACHE`  
Values : *Xm* | *Xk*    
Default value : *10m*  
Context : *global*  
The size of the cache to store information about request limiting.

### Connections limiting

`USE_LIMIT_CONN`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, the number of connections made by an ip will be limited during a period of time. (ie. very small/weak ddos protection)  
More info connections limiting [here](http://nginx.org/en/docs/http/ngx_http_limit_conn_module.html).

`LIMIT_CONN_MAX`  
Values : *<any valid integer\>*  
Default value : *50*  
Context : *global*, *multisite*  
The maximum number of connections per ip to put in queue before rejecting requests.

`LIMIT_CONN_CACHE`  
Values : *Xm* | *Xk*    
Default value : *10m*  
Context : *global*  
The size of the cache to store information about connection limiting.

### Countries

`BLACKLIST_COUNTRY`  
Values : *\<country code 1\> \<country code 2\> ...*  
Default value :  
Context : *global*, *multisite*  
Block some countries from accessing your website. Use 2 letters country code separated with space.

`WHITELIST_COUNTRY`  
Values : *\<country code 1\> \<country code 2\> ...*  
Default value :  
Context : *global*, *multisite*  
Only allow specific countries accessing your website. Use 2 letters country code separated with space.

## PHP

`REMOTE_PHP`  
Values : *\<any valid IP/hostname\>*  
Default value :  
Context : *global*, *multisite*  
Set the IP/hostname address of a remote PHP-FPM to execute .php files.

`REMOTE_PHP_PATH`  
Values : *\<any valid absolute path\>*  
Default value : */app*  
Context : *global*, *multisite*  
The path where the PHP files are located inside the server specified in `REMOTE_PHP`.

## Bad behavior

`USE_BAD_BEHAVIOR`  
Values : *yes* | *no*  
Default value : *yes*  
Context : *global*, *multisite*  
If set to yes, bunkerized-nginx will block users getting too much "suspicious" HTTP codes in a period of time.  

`BAD_BEHAVIOR_STATUS_CODES`   
Values : *\<HTTP status codes separated with space\>*  
Default value : *400 401 403 404 405 429 444*  
Context : *global*, *multisite*  
List of HTTP status codes considered as "suspicious".   

`BAD_BEHAVIOR_THRESHOLD`  
Values : *<any positive integer>*  
Default value : *10*  
Context : *global*, *multisite*  
The number of "suspicious" HTTP status code before the corresponding IP is banned.

`BAD_BEHAVIOR_BAN_TIME`  
Values : *<any positive integer>*  
Default value : *86400*  
Context : *global*, *multisite*  
The duration time (in seconds) of a ban when the corresponding IP has reached the `BAD_BEHAVIOR_THRESHOLD`.

`BAD_BEHAVIOR_COUNT_TIME`  
Values : *<any positive integer>*  
Default value : *60*  
Context : *global*, *multisite*  
The duration time (in seconds) before the counter of "suspicious" HTTP is reset.

## misc

`SWARM_MODE`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*  
Only set to *yes* when you use *bunkerized-nginx* with *autoconf* feature in swarm mode. More info [here](#swarm-mode).

`USE_API`  
Values : *yes* | *no*  
Default value : *no*  
Context : *global*  
Only set to *yes* when you use *bunkerized-nginx* with *autoconf* feature in swarm mode. More info [here](#swarm-mode).

`API_URI`  
Values : *random* | *\<any valid URI path\>*  
Default value : *random*  
Context : *global*  
Set it to a random path when you use *bunkerized-nginx* with *autoconf* feature in swarm mode. More info [here](#swarm-mode).

`API_WHITELIST_IP`  
Values : *\<list of IP/CIDR separated with space\>*  
Default value : *192.168.0.0/16 172.16.0.0/12 10.0.0.0/8*  
Context : *global*  
List of IP/CIDR block allowed to send API order using the `API_URI` uri.
