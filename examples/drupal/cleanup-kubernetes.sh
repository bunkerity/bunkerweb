#!/bin/bash

helm delete drupal
kubectl delete pvc data-drupal-mariadb-0
