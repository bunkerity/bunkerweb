#!/bin/bash

echo $CERTBOT_VALIDATION > /opt/bunkerized-nginx/acme-challenge/.well-known/acme-challenge/$CERTBOT_TOKEN
