# Special folders

Please note that bunkerized-nginx runs as an unprivileged user (UID/GID 101 when using the Docker image) and you should set the rights on the host accordingly to the files and folders on your host.

## Multisite

When the special folder "supports" the multisite mode, you can create subfolders named as the server names used in the configuration. When doing it only the subfolder files will be "used" by the corresponding web service.

## Web files

This special folder is used by bunkerized-nginx to deliver static files. The typical use case is when you have a PHP application that also contains static assets like CSS, JS and images.

Location (container) : `/www`  
Location (Linux) : `/opt/bunkerized-nginx/www`  
Multisite : `yes`  
Read-only : `yes`  

Examples :
- [Basic website with PHP](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/basic-website-with-php)
- [Multisite basic](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/multisite-basic)

## http configurations

This special folder contains .conf files that will be loaded by nginx at http context. The typical use case is when you need to add custom directives into the `http { }` block of nginx.

Location (container) : `/http-confs`  
Location (Linux) : `/opt/bunkerized-nginx/http-confs`  
Multisite : `no`  
Read-only : `yes`  

Examples :
- [Load balancer](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/load-balancer)

## server configurations

This special folder contains .conf files that will be loaded by nginx at server context. The typical use case is when you need to add custom directives into the `server { }` block of nginx.

Location (container) : `/server-confs`  
Location (Linux) : `/opt/bunkerized-nginx/server-confs`  
Multisite : `yes`  
Read-only : `yes`  

Examples :
- [Wordpress](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/wordpress)
- [Multisite custom confs](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/multisite-custom-confs)

## ModSecurity configurations

This special folder contains .conf files that will be loaded by ModSecurity after the OWASP Core Rule Set is loaded. The typical use case is to edit loaded CRS rules to avoid false positives.

Location (container) : `/modsec-confs`  
Location (Linux) : `/opt/bunkerized-nginx/modsec-confs`  
Multisite : `yes`  
Read-only : `yes`  

Examples :
- [Wordpress](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/wordpress)
- [Multisite custom confs](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/multisite-custom-confs)

## CRS configurations

This special folder contains .conf file that will be loaded by ModSecurity before the OWASP Core Rule Set is loaded. The typical use case is when you want to specify exclusions for the CRS.

Location (container) : `/modsec-crs-confs`  
Location (Linux) : `/opt/bunkerized-nginx/modsec-crs-confs`  
Multisite : `yes`  
Read-only : `yes`  

Examples :
- [Wordpress](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/wordpress)
- [Multisite custom confs](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/multisite-custom-confs)

## Cache

This special folder is used to cache some data like blacklists and avoid downloading them again if it is not necessary. The typical use case is to avoid the overhead when you are testing bunkerized-nginx in a container and you have to recreate it multiple times.

Location (container) : `/cache`  
Location (Linux) : `/opt/bunkerized-nginx/cache`  
Multisite : `no`  
Read-only : `no`  

## Plugins

This special folder is the placeholder for the plugins loaded by bunkerized-nginx. See the [plugins section](https://bunkerized-nginx.readthedocs.io/en/latest/plugins.html) for more information.

Location (container) : `/plugins`  
Location (Linux) : `/opt/bunkerized-nginx/plugins`  
Multisite : `no`  
Read-only : `no`  

## ACME challenge

This special folder is used as the web root for Let's Encrypt challenges. The typical use case is to share the same folder when you are using bunkerized-nginx in a clustered environment like Docker Swarm or Kubernetes.

Location (container) : `/acme-challenge`  
Location (Linux) : `/opt/bunkerized-nginx/acme-challenge`  
Multisite : `no`  
Read-only : `no`  
