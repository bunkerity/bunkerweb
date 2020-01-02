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

### nginx security
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

## TODO
- File permissions hardening
- Custom nginx configuration
- Custom TLS certificates
- Documentation
- Reverse proxy mode
