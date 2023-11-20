#!/bin/bash

helm delete prestashop
kubectl delete pvc data-prestashop-mariadb-0
