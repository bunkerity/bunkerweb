#!/bin/sh

# first, you need to run the crowdsec service
echo "running crowdsec service ..."
docker-compose up -d mycrowdsec

# wait a little until it's up
sleep 10

# get the bouncer key
docker-compose exec mycrowdsec cscli bouncers add MyBouncer

# enter the key into the CROWDSEC_KEY setting
read -p "edit CROWDSEC_KEY env var in plugin.json file and press enter" edited

# start all services
docker-compose up -d

# wait a little until it's up
sleep 10

# restart crowdsec so it reads the log files
docker-compose restart mycrowdsec
