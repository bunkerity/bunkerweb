# bunkerized-nginx
nginx based Docker image secure by default.

## Main features
- HTTPS support with transparent Let's Encrypt automation
- State-of-the-art web security : HTTP headers, php.ini hardening, version leak, ...
- Integrated ModSecurity WAF with the OWASP Core Rule Set
- Based on alpine and compiled from source (< 100 MB image)
- Easy to configure with environment variables

## TODO
- Documentation
- Reverse proxy mode
