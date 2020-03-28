# bunkerized-nginx
nginx based Docker image secure by default.

## Main features
- HTTPS support with transparent Let's Encrypt automation
- State-of-the-art web security : HTTP headers, php.ini hardening, version leak, ...
- Integrated ModSecurity WAF with the OWASP Core Rule Set
- Based on alpine and compiled from source (< 100 MB image)
- Easy to configure with environment variables

## Quickstart guide

### Run HTTP server with default settings

```shell
docker run -p 80:80 -v /path/to/web/files:/www bunkerity/bunkerized-nginx
```

Web files are stored in the /www directory, so you need to mount the volume on it.

### Run HTTPS server with automated Let's Encrypt
```shell
docker run -p 80:80 -p 443:443 -v /path/to/web/files:/www -e SERVER_NAME=www.yourdomain.com -e AUTO_LETS_ENCRYPT=yes bunkerity/bunkerized-nginx
```

Let's Encrypt needs port 80 to be open to request and sign certificates but nginx will only listen on port 443.

## List of environment variables

### nginx
*SERVER_TOKENS*  
Values : on | off  
Default value : off  
If set to on, nginx will display server version in Server header and default error pages.

*HEADER_SERVER*  
Values : yes | no  
Default value : no  
If set to no, nginx will remove the Server header in HTTP responses.

*ALLOWED_METHODS*  
Values : allowed HTTP methods separated with | char  
Default value : GET|POST|HEAD  
Only the HTTP methods listed here will be accepted by nginx. If not listed, nginx will close the connection.

*DISABLE_DEFAULT_SERVER*  
Values : yes | no  
Default value : no  
If set to yes, nginx will only respond to HTTP request when the Host header match the SERVER_NAME. For example, it will close the connection if a bot access the site with direct ip.

*SERVE_FILES*  
Values : yes | no  
Default value : yes  
If set to yes, nginx will serve files from /www directory within the container.  
A use case to not serving files is when you setup bunkerized-nginx as a reverse proxy via a custom configuration.

*MAX_CLIENT_SIZE*  
Values : 0 | Xm  
Default value : 10m  
Sets the maximum body size before nginx returns a 413 error code.  
Setting to 0 means "infinite" body size.

*SERVER_NAME*  
Values : <first name> <second name> ...  
Default value : www.bunkerity.com  
Sets the host names of the webserver. This is the names used by your clients.  
Useful when used with AUTO_LETSENCRYPT=yes and/or DISABLE_DEFAULT_SERVER=yes.

### HTTPS
*AUTO_LETS_ENCRYPT*  
Values : yes | no  
Default value : no  
If set to yes, automatic certificate generation and renewal will be setup through Let's Encrypt. This will enable HTTPS on your website for free.  
You will need to redirect both 80 and 443 port to your container and also set the SERVER_NAME environment variable.

*HTTP2*  
Values : yes | no  
Default value : yes  
If set to yes, nginx will use HTTP2 protocol when HTTPS is enabled.

### ModSecurity
*USE_MODSECURITY*  
Values : yes | no  
Default value : yes  
If set to yes, the ModSecurity WAF will be enabled with the OWASP Core Rule Set.

### Security headers
*X_FRAME_OPTIONS*  
Values : DENY | SAMEORIGIN | ALLOW-FROM https://www.website.net | ALLOWALL  
Default value : DENY  
Policy to be used when the site is displayed through iframe. Can be used to mitigate clickjacking attacks. 
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options).

*X_XSS_PROTECTION*  
Values : 0 | 1 | 1; mode=block  
Default value : 1; mode=block  
Policy to be used when XSS is detected by the browser. Only works with Internet Explorer.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-XSS-Protection).  

*X_CONTENT_TYPE_OPTIONS*  
Values : nosniff  
Default value : nosniff  
Tells the browser to be strict about MIME type.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options).

*REFERRER_POLICY*  
Values : no-referrer | no-referrer-when-downgrade | origin | origin-when-cross-origin | same-origin | strict-origin | strict-origin-when-cross-origin | unsafe-url  
Default value : no-referrer  
Policy to be used for the Referer header.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy).

*FEATURE_POLICY*  
Values : <directive> <allow list>  
Default value : accelerometer 'none'; ambient-light-sensor 'none'; autoplay 'none'; camera 'none'; display-capture 'none'; document-domain 'none'; encrypted-media 'none'; fullscreen 'none'; geolocation 'none'; gyroscope 'none'; magnetometer 'none'; microphone 'none'; midi 'none'; payment 'none'; picture-in-picture 'none'; speaker 'none'; sync-xhr 'none'; usb 'none'; vibrate 'none'; vr 'none'  
Tells the browser which features can be used on the website.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Feature-Policy).

*COOKIE_FLAGS*  
Values : * HttpOnly | MyCookie secure SameSite | ...  
Default value : * HttpOnly  
Adds some security to the cookies set by the server.  
Accepted value can be found [here](https://github.com/AirisX/nginx_cookie_flag_module).

*STRICT_TRANSPORT_POLICY*  
Values : max-age=expireTime [; includeSubDomains] [; preload]
Default value : max-age=31536000  
Tells the browser to use exclusively HTTPS instead of HTTP when communicating with the server.  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security).

*CONTENT_SECURITY_POLICY*  
Values : <directive 1>; <directive 2>; ...
Default value : default-src 'self'; frame-ancestors 'none'; form-action 'self'; upgrade-insecure-requests; block-all-mixed-content; sandbox allow-forms allow-same-origin allow-scripts; reflected-xss block; base-uri 'self'; referrer no-referrer  
Policy to be used when loading resources (scripts, forms, frames, ...).  
More info [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy).

### Blocking
*BLOCK_COUNTRY*  
Values : <country code 1> <country code 2> ...  
Default value :  
Block some countries from accessing your website. Use 2 letters country code separated with space.

*BLOCK_USER_AGENT*  
Values : yes | no
Default value : yes
If set to yes, block clients with "bad" user agent.  
Blacklist can be found [here](https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list).

*BLOCK_TOR_EXIT_NODE*  
Values : yes | no  
Default value : no  
Is set to yes, will block TOR clients.

### PHP
*USE_PHP*  
Values : yes | no  
Default value : yes  
If set to yes, PHP files will be executed by the server.

*PHP_DISPLAY_ERRORS*  
Values : yes | no  
Default value : no  
If set to yes, PHP errors will be shown to clients.

*PHP_EXPOSE*  
Values : yes | no  
Default value : no  
If set to yes, the PHP version will be sent within the X-Powered-By header.

*PHP_OPEN_BASEDIR*  
Values : <directory>  
Default value : /www/  
Limits access to files within the given directory. For example include() or fopen() calls outside the directory will fail.

*PHP_ALLOW_URL_FOPEN*  
Values : yes | no
Default value : no
If set to yes, allows using url in fopen() calls (i.e. : ftp://, http://, ...). 

*PHP_ALLOW_URL_INCLUDE*  
Values : yes | no
Default value : no
If set to yes, allows using url in include() calls (i.e. : ftp://, http://, ...). 

*PHP_FILE_UPLOADS*  
Values : yes | no
Default value : yes
If set to yes, allows clients to upload files.

*PHP_UPLOAD_MAX_FILESIZE*  
Values : <size in bytes> | XM
Default value : 10M  
Sets the maximum file size allowed when uploading files.

*PHP_DISABLE_FUNCTIONS*  
Values : <function 1>, <function 2> ...  
Default value : system, exec, shell_exec, passthru, phpinfo, show_source, highlight_file, popen, proc_open, fopen_with_path, dbmopen, dbase_open, putenv, chdir, mkdir, rmdir, chmod, rename, filepro, filepro_rowcount, filepro_retrieve, posix_mkfifo  
List of PHP functions blacklisted. They can't be used anywhere in PHP code.

## TODO
- Edit CONTENT_SECURITY_POLICY default value
- Custom TLS certificates
- Documentation
- Certificate Transparency
