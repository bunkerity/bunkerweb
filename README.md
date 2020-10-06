# bunkerized-nginx

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/logo.png?raw=true" width="425" />

nginx based Docker image secure by default.  

Non-exhaustive list of features :
- HTTPS support with transparent Let's Encrypt automation
- State-of-the-art web security : HTTP security headers, php.ini hardening, prevent leaks, ...
- Integrated ModSecurity WAF with the OWASP Core Rule Set
- Automatic ban of strange behaviors with fail2ban
- Block TOR, proxies, bad user-agents, countries, ...
- Perform automatic DNSBL checks to block known bad IP
- Prevent bruteforce attacks with rate limiting
- Detect bad files with ClamAV
- Easy to configure with environment variables

# Table of contents
- [bunkerized-nginx](#bunkerized-nginx)
- [Table of contents](#table-of-contents)
- [Live demo](#live-demo)
- [Quickstart guide](#quickstart-guide)
  * [Run HTTP server with default settings](#run-http-server-with-default-settings)
  * [Run HTTPS server with automated Let's Encrypt](#run-https-server-with-automated-let-s-encrypt)
  * [Reverse proxy](#reverse-proxy)
- [Tutorials](#tutorials)
- [List of environment variables](#list-of-environment-variables)
  * [nginx](#nginx)
  * [HTTPS](#https)
  * [ModSecurity](#modsecurity)
  * [Security headers](#security-headers)
  * [Blocking](#blocking)
  * [PHP](#php)
  * [Fail2ban](#fail2ban)
  * [ClamAV](#clamav)
  * [Misc](#misc)
- [Include custom configurations](#include-custom-configurations)
- [Create your own image](#create-your-own-image)
- [TODO](#todo)

# Live demo
You can find a live demo at https://demo-nginx.bunkerity.com.

# Quickstart guide

## Run HTTP server with default settings

```shell
docker run -p 80:80 -v /path/to/web/files:/www bunkerity/bunkerized-nginx
```

Web files are stored in the /www directory, the container will serve files from there.

## Run HTTPS server with automated Let's Encrypt
```shell
docker run -p 80:80 -p 443:443 -v /path/to/web/files:/www -v /where/to/save/certificates:/etc/letsencrypt -e SERVER_NAME=www.yourdomain.com -e AUTO_LETS_ENCRYPT=yes -e REDIRECT_HTTP_TO_HTTPS=yes bunkerity/bunkerized-nginx
```

Certificates are stored in the /etc/letsencrypt directory, you should save it on your local drive.  
If you don't want your webserver to listen on HTTP add the environment variable `LISTEN_HTTP` with a "no" value. But Let's Encrypt needs the port 80 to be opened so redirecting the port is mandatory.

Here you have three environment variables :
- `SERVER_NAME` : define the FQDN of your webserver, this is mandatory for Let's Encrypt (www.yourdomain.com should point to your IP address)
- `AUTO_LETS_ENCRYPT` : enable automatic Let's Encrypt creation and renewal of certificates
- `REDIRECT_HTTP_TO_HTTPS` : enable HTTP to HTTPS redirection

## Reverse proxy
You can setup a reverse proxy by adding your own custom configurations at server context.  
For example, this is a dummy reverse proxy configuration :  
```shell
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
docker run -p 80:80 -e SERVER_NAME="www.website1.com www.website2.com" -e SERVE_FILES=no -e DISABLE_DEFAULT_SERVER=yes -v /path/to/server/conf:/server-confs bunkerity/bunkerized-nginx
```

Here you have three environment variables :
- `SERVER_NAME` : list of valid Host headers sent by clients
- `SERVE_FILES` : nginx will not serve files from the /www directory
- `DISABLE_DEFAULT_SERVER` : nginx will not respond to requests if Host header is not in the SERVER_NAME list

# Tutorials
You will find some tutorials about bunkerized-nginx in our [blog](https://www.bunkerity.com/category/bunkerized-nginx/).  

# List of environment variables

## nginx
`SERVER_TOKENS`  
Values : *on* | *off*  
Default value : *off*  
If set to on, nginx will display server version in Server header and default error pages.

`HEADER_SERVER`  
Values : *yes* | *no*  
Default value : *no*  
If set to no, nginx will remove the Server header in HTTP responses.

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

`ROOT_FOLDER`  
Values : *\<any valid path to web files\>  
Default value : */www*  
The default folder where nginx will search for web files. Don't change it unless you want to make your own image.

`MAX_CLIENT_SIZE`  
Values : *0* | *Xm*  
Default value : *10m*  
Sets the maximum body size before nginx returns a 413 error code.  
Setting to 0 means "infinite" body size.

`SERVER_NAME`  
Values : *&lt;first name&gt; &lt;second name&gt; ...*  
Default value : *www.bunkerity.com*  
Sets the host names of the webserver separated with spaces. This must match the Host header sent by clients.  
Useful when used with `AUTO_LETSENCRYPT=yes` and/or `DISABLE_DEFAULT_SERVER=yes`.

`WRITE_ACCESS`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, nginx will be granted write access to the /www directory.  
Set it to yes if your website uses file upload or creates dynamic files for example.

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

`ERROR_XXX`  
Values : *\<relative path to the error page\>*  
Default value :  
Use this kind of environment variable to define custom error page depending on the HTTP error code. Replace XXX with HTTP code.  
For example : `ERROR_404=/404.html` means the /404.html page will be displayed when 404 code is generated. The path is relative to the root web folder.

`PROXY_REAL_IP`
Values : *yes* | *no*
Default value : *no*
Use this kind of environment variable to define whether you're using Nginx inside another proxy, this means you will see "X-Forwarded-For" instead of regular "Remote-Addr" IPs inside your logs. Modsecurity will also then work correctly.

## HTTPS
`AUTO_LETS_ENCRYPT`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, automatic certificate generation and renewal will be setup through Let's Encrypt. This will enable HTTPS on your website for free.  
You will need to redirect both 80 and 443 port to your container and also set the `SERVER_NAME` environment variable.

`LISTEN_HTTP`  
Values : *yes* | *no*  
Default value : *yes*  
If set to no, nginx will not in listen on HTTP (port 80).  
Useful if you only want HTTPS access to your website.

`REDIRECT_HTTP_TO_HTTPS`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, nginx will redirect all HTTP requests to HTTPS.  

`HTTP2`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, nginx will use HTTP2 protocol when HTTPS is enabled.  

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

`GENERATE_SELF_SIGNED_SSL`
Values : *yes* | *no*
Default value : *no*
If set to yes, HTTPS will be enabled with a container generated self signed SSL.

`SELF_SIGNED_SSL_EXPIRY`
Values : *integer*
Default value : *365* (1 year)
Needs "GENERATE_SELF_SIGNED_SSL" to work.
Sets the expiry date for the self generated certificate.

`SELF_SIGNED_SSL_COUNTRY`
Values : *text*
Default value : *Switzerland*
Needs "GENERATE_SELF_SIGNED_SSL" to work.
Sets the country for the self generated certificate.

`SELF_SIGNED_SSL_STATE`
Values : *text*
Default value : *Switzerland*
Needs "GENERATE_SELF_SIGNED_SSL" to work.
Sets the state for the self generated certificate.

`SELF_SIGNED_SSL_CITY`
Values : *text*
Default value : *Bern*
Needs "GENERATE_SELF_SIGNED_SSL" to work.
Sets the city for the self generated certificate.

`SELF_SIGNED_SSL_ORG`
Values : *text*
Default value : *AcmeInc*
Needs "GENERATE_SELF_SIGNED_SSL" to work.
Sets the organisation name for the self generated certificate.

`SELF_SIGNED_SSL_OU`
Values : *text*
Default value : *IT*
Needs "GENERATE_SELF_SIGNED_SSL" to work.
Sets the organisitional unit for the self generated certificate.

`SELF_SIGNED_SSL_CN`
Values : *text*
Default value : *bunkerity-nginx*
Needs "GENERATE_SELF_SIGNED_SSL" to work.
Sets the CN server name for the self generated certificate.

## ModSecurity
`USE_MODSECURITY`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, the ModSecurity WAF will be enabled.  
You can include custom rules by adding .conf files into the /modsec-confs/ directory inside the container (i.e : through a volume).  

`USE_MODSECURITY_CRS`  
Values: *yes* | *no*
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
Values : *\* HttpOnly* | *MyCookie secure SameSite* | *...*  
Default value : *\* HttpOnly*  
Adds some security to the cookies set by the server.  
Accepted value can be found [here](https://github.com/AirisX/nginx_cookie_flag_module).

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
`BLOCK_COUNTRY`  
Values : *\<country code 1\> \<country code 2\> ...*  
Default value :  
Block some countries from accessing your website. Use 2 letters country code separated with space.

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

`USE_DNSBL`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, DNSBL checks will be performed to the servers specified in the `DNSBL_LIST` environment variable.  

`DNSBL_LIST`  
Values : *\<list of DNS zones separated with spaces\>*  
Default value : *bl.blocklist.de problems.dnsbl.sorbs.net sbl.spamhaus.org xbl.spamhaus.org*  
The list of DNSBL zones to query when `USE_DNSBL` is set to *yes*.

`DNSBL_RESOLVERS`  
Values : *\<two IP addresses separated with a space\>*  
Default value : *8.8.8.8 8.8.4.4*  
The IP addresses of the DNS resolvers to use when `USE_DNSBL` is set to *yes*.

`DNSBL_CACHE`  
Values : *\<size with units k or m\>*  
Default value : *10m*  
The size of the cache used to keep DNSBL responses.

`USE_REQ_LIMIT`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, the amount of HTTP requests made by a user will be limited during a period of time.  
More info rate limiting [here](https://www.nginx.com/blog/rate-limiting-nginx/).

`REQ_LIMIT_RATE`  
Values : *Xr/s* | *Xr/m*  
Default value : *20r/s*  
The rate limit to apply when `USE_REQ_LIMIT` is set to *yes*. Default is 10 requests per second.

`REQ_LIMIT_BURST`  
Values : *<any valid integer\>*  
Default value : *40*  
The number of of requests to put in queue before rejecting requests.

`REQ_LIMIT_CACHE`  
Values : *Xm* | *Xk*    
Default value : *10m*  
The size of the cache to store information about request limiting.

## PHP
`REMOTE_PHP`  
Values : *\<any valid IP/hostname\>*  
Default value :  
Set the IP/hostname address of a remote PHP-FPM to execute .php files. See `USE_PHP` if you want to run a PHP-FPM instance on the same container as bunkerized-nginx.

`REMOTE_PHP_PATH`  
Values : *\<any valid absolute path\>*  
Default value : */app*  
The path where the PHP files are located inside the server specified in `REMOTE_PHP`.

`USE_PHP`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, a local PHP-FPM instance will be run inside the container to execute PHP files.

`PHP_DISPLAY_ERRORS`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, PHP errors will be shown to clients. Only meaningful if `USE_PHP` is set to *yes*.

`PHP_EXPOSE`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, the PHP version will be sent within the X-Powered-By header. Only meaningful if `USE_PHP` is set to *yes*.

`PHP_OPEN_BASEDIR`  
Values : *\<directories separated with : char\>*  
Default value : */www/:/tmp/*  
Limits access to files within the given directories. For example include() or fopen() calls outside the directory will fail. Only meaningful if `USE_PHP` is set to *yes*.

`PHP_ALLOW_URL_FOPEN`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, allows using url in fopen() calls (i.e. : ftp://, http://, ...). Only meaningful if `USE_PHP` is set to *yes*.

`PHP_ALLOW_URL_INCLUDE`  
Values : *yes* | *no*  
Default value : *no*  
If set to yes, allows using url in include() calls (i.e. : ftp://, http://, ...). Only meaningful if `USE_PHP` is set to *yes*.

`PHP_FILE_UPLOADS`  
Values : *yes* | *no*  
Default value : *yes*  
If set to yes, allows clients to upload files. Only meaningful if `USE_PHP` is set to *yes*.

`PHP_UPLOAD_MAX_FILESIZE`  
Values : *\<size in bytes\>* | *XM*  
Default value : *10M*  
Sets the maximum file size allowed when uploading files. Only meaningful if `USE_PHP` is set to *yes*.

`PHP_POST_MAX_SIZE`  
Values : *\<size in bytes\>* | *XM*  
Default value : *10M*  
Sets the maximum POST size allowed for clients. Only meaningful if `USE_PHP` is set to *yes*.

`PHP_DISABLE_FUNCTIONS`  
Values : *\<function 1\>, \<function 2\> ...*  
Default value : *system, exec, shell_exec, passthru, phpinfo, show_source, highlight_file, popen, proc_open, fopen_with_path, dbmopen, dbase_open, putenv, filepro, filepro_rowcount, filepro_retrieve, posix_mkfifo*  
List of PHP functions blacklisted separated with commas. They can't be used anywhere in PHP code. Only meaningful if `USE_PHP` is set to *yes*.

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
Default : value : *20*  
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
A use case is to use this to install PHP extensions (e.g. : php7-json php7-xml php7-curl ...).

`LOGROTATE_MINSIZE`  
Values : *x* | *xk* | *xM* | *xG*  
Default value : 10M  
The minimum size of a log file before being rotated (no letter = bytes, k = kilobytes, M = megabytes, G = gigabytes).

`LOGROTATE_MAXAGE`  
Values : *\<any integer\>*  
Default value : 7  
The number of days before rotated files are deleted.

# Create your own image

You can use bunkerity/bunkerized-nginx as a base image for your web application.  
Here is a Dockerfile example :  
```
FROM bunkerity/bunkerized-nginx

# Copy your web files to a folder
COPY ./web-files/ /opt/web-files

# Optional : add your own script to be executed on startup
COPY ./my-entrypoint.sh /entrypoint.d/my-entrypoint.sh
RUN chmod +x /entrypoint.d/my-entrypoint.sh

# Mandatory variables to make things working
ENV ROOT_FOLDER /opt/web-files
ENV PHP_OPEN_BASEDIR /opt/web-files/:/tmp/

# Optional variables
ENV MAX_CLIENT_SIZE 100m
ENV PHP_UPLOAD_MAX_FILESIZE 100M
ENV WRITE_ACCESS yes
ENV ADDITIONAL_MODULES php7-mysqli php7-json php7-session
```

You can have a look at (bunkerized-phpmyadmin)[https://github.com/bunkerity/bunkerized-phpmyadmin] which is a secure phpMyAdmin Docker image based on bunkerized-nginx.

# Include custom configurations
Custom configurations files (ending with .conf suffix) can be added in some directory inside the container :
  - /http-confs : http context
  - /server-confs : server context

You just need to use a volume like this :
```
docker run ... -v /path/to/http/confs:/http-confs ... bunkerity/bunkerized-nginx
```
