#!/bin/bash

helm delete wordpress
kubectl delete pvc data-wordpress-mariadb-0
