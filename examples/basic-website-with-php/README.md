# Basic website with PHP

This is a basic example for a typical PHP website/app.

## Docker

```shell
$ mkdir letsencrypt
$ chown root:101 letsencrypt
$ chmod 770 letsencrypt
$ chmod 755 web-files
$ chmod -R 744 web-files/*
$ docker-compose up
```

## Linux

```shell
$ cp variables.env /opt/bunkerized-nginx/variables.env
$ cp web-files/* /opt/bunkerized-nginx/www
$ chown -R www-data:www-data /opt/bunkerized-nginx/www/*
$ chmod -R 774 /opt/bunkerized-nginx/www/*
$ bunkerized-nginx
```
