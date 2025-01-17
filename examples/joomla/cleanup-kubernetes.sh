#!/bin/bash

helm delete joomla
kubectl delete pvc data-joomla-mariadb-0
