# Quickstart guide

## Reverse proxy

The following environment variables can be used to deploy bunkerized-nginx as a reverse proxy in front of your web services :
- `USE_REVERSE_PROXY` : activate/deactivate the reverse proxy mode
- `REVERSE_PROXY_URL` : public path prefix
- `REVERSE_PROXY_HOST` : full address of the proxied service

Here is a basic example :
```conf
SERVER_NAME=www.example.com
USE_REVERSE_PROXY=yes
REVERSE_PROXY_URL=/
REVERSE_PROXY_HOST=http://my-service.example.local:8080
```

If you have multiple web services you configure multiple reverse proxy rules by appending a number to the environment variables names :
```conf
SERVER_NAME=www.example.com
USE_REVERSE_PROXY=yes
REVERSE_PROXY_URL_1=/app1
REVERSE_PROXY_HOST_1=http://app1.example.local:8080
REVERSE_PROXY_URL_2=/app2
REVERSE_PROXY_HOST_2=http://app2.example.local:8080
```

### Docker

TODO

### Docker autoconf

TODO

### Docker Swarm

TODO

### Kubernetes

TODO

### Linux

TODO

## PHP applications

The following environment variables can be used to configure bunkerized-nginx in front of PHP-FPM web applications :
- `REMOTE_PHP` : host/ip of a remote PHP-FPM instance
- `REMOTE_PHP_PATH` : absolute path containing the PHP files (from the remote instance perspective) 
- `LOCAL_PHP` : absolute path of the local unix socket used by a local PHP-FPM instance
- `LOCAL_PHP_PATH` : absolute path containing the PHP files (when using local instance)

Here is a basic example with a remote instance :
```conf
SERVER_NAME=www.example.com
REMOTE_PHP=my-php.example.local
REMOTE_PHP_PATH=/var/www/html
```

And another example with a local instance :
```conf
SERVER_NAME=www.example.com
LOCAL_PHP=/var/run/php7-fpm.sock
LOCAL_PHP_PATH=/opt/bunkerized-nginx/www
```

### Docker

### Docker autoconf

### Docker Swarm

### Kubernetes

## Multisite

If you have multiple services to protect, the easiest way to do it is by enabling the "multisite" mode. When using multisite, bunkerized-nginx will create one server block per server defined in the SERVER_NAME environment variable. You can configure each servers independently by adding the server name as a prefix.

Here is an example :
```conf
SERVER_NAME=app1.example.com app2.example.com
app1.example.com_USE_REVERSE_PROXY=yes
app1.example.com_REVERSE_PROXY_URL=/
app1.example.com_REVERSE_PROXY_HOST=http://app1.example.local:8080
app2.example.com_REMOTE_PHP=app2.example.local
app2.example.com_REMOTE_PHP_PATH=/var/www/html
```

### Docker

### Docker autoconf

### Docker Swarm

### Kubernetes

