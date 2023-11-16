#!/bin/bash

helm delete redmine
kubectl delete pvc data-redmine-mariadb-0
kubectl delete pvc data-redmine-postgresql-0
