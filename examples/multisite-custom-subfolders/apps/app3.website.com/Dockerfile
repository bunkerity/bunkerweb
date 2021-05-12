FROM php:fpm

COPY docker-php-entrypoint /usr/local/bin/
RUN  chmod +x /usr/local/bin/docker-php-entrypoint

ENTRYPOINT ["/usr/local/bin/docker-php-entrypoint"]

EXPOSE 9000
CMD ["php-fpm"]