# Volumes list

Please note that bunkerized-nginx is ran as an unprivileged user inside the container (UID/GID = 101) and you should set the rights on the host accordingly (e.g. : chmod 101:101 ...).

## Web files

Mountpoint : `/www`  
Description :  
If `MULTISITE=no`, the web files are directly stored inside the `/www` folder. When `MULTISITE=yes`, you need to create subdirectories named as the servers defined in the `SERVER_NAME` environment variable.
Examples : [basic](#) and [multisite](#)  
Read-only : yes

## Custom nginx configurations

### http context

Mountpoint : `/http-confs`  
Description :  
If you need to add custom configurations at http context, you can create **.conf** files and mount them to the `/http-confs` folder. See the [load balancer example](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/load-balancer) for more information.
Read-only : yes

### server context

Mountpoint : `/server-confs`  
Description :  
If `MULTISITE=no`, you can create **.conf** files and mount them to the `/server-confs` folder. When `MULTISITE=yes`, you need to create subdirectories named as the servers defined in the `SERVER_NAME` environment variable.
Examples : [basic](#) and [multisite](#)  
Read-only : yes

## ModSecurity

### Rules and before CRS

### After CRS
