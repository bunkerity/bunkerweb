# Volumes list

Please note that bunkerized-nginx run as an unprivileged user inside the container (UID/GID = 101) and you should set the rights on the host accordingly (e.g. : chmod 101:101 ...) to the files and folders on your host.

## Web files

Mountpoint : `/www`

Description :  
If `MULTISITE=no`, the web files are directly stored inside the `/www` folder. When `MULTISITE=yes`, you need to create subdirectories named as the servers defined in the `SERVER_NAME` environment variable.

Examples : [basic](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/basic-website-with-php) and [multisite](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/multisite-basic)

Read-only : yes

## Let's Encrypt

Mountpoint : `/etc/letsencrypt`

Description :  
When `AUTO_LETS_ENCRYPT=yes`, certbot will save configurations, certificates and keys inside the `/etc/letsencrypt` folder. It's a common practise to save it so you can remount it in case of a container restart and certbot won't generate new certificate(s).

Examples : [here](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/basic-website-with-php)

Read-only : no

## Custom nginx configurations

### http context

Mountpoint : `/http-confs`

Description :  
If you need to add custom configurations at http context, you can create **.conf** files and mount them to the `/http-confs` folder.

Examples : [load balancer](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/load-balancer)

Read-only : yes

### server context

Mountpoint : `/server-confs`

Description :  
If `MULTISITE=no`, you can create **.conf** files and mount them to the `/server-confs` folder. When `MULTISITE=yes`, you need to create subdirectories named as the servers defined in the `SERVER_NAME` environment variable.

Examples : [nextcloud](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/nextcloud) and [multisite](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/multisite-custom-server-confs)

Read-only : yes

## ModSecurity

### Rules and before CRS

Mountpoint : `/modsec-confs`

Description :  
Use this volume if you need to add custom ModSecurity rules and/or OWASP Core Rule Set configurations before the rules are loaded (e.g. : exclusions).  
If `MULTISITE=no` you can create **.conf** files and mount them to the `/modsec-confs` folder. When `MULTISITE=yes`, you need to create subdirectories named as the servers defined in the `SERVER_NAME` environment variable. You can also apply global configuration to all servers by putting **.conf** files directly on the root folder.

Examples : [wordpress](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/wordpress) and [multisite](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/multisite-custom-server-confs)

Read-only : yes

### After CRS

Mountpoint : `/modsec-crs-confs`

Description :  
Use this volume to tweak OWASP Core Rule Set (e.g. : tweak rules to avoid false positives). Your files are loaded after the rules.
If `MULTISITE=no` you can create **.conf** files and mount them to the `/modsec-crs-confs` folder. When `MULTISITE=yes`, you need to create subdirectories named as the servers defined in the `SERVER_NAME` environment variable. You can also apply global configuration to all servers by putting **.conf** files directly on the root folder.

Examples : [wordpress](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/wordpress) and [multisite](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/multisite-custom-server-confs)

Read-only : yes

## Cache

Mountpoint : `/cache`

Description :  
Depending of the settings you use, bunkerized-nginx may download external content (e.g. : blacklists, GeoIP DB, ...). To avoid downloading it again in case of a container restart, you can save the data on the host.

Read-only : no

## Plugins

Mountpoint : `/plugins`

Description :  
This volume is used to extend bunkerized-nginx with [additional plugins](https://bunkerized-nginx.readthedocs.io/en/latest/plugins.html). Please note that you will need to have a subdirectory for each plugin you want to enable.

Read-only : yes
