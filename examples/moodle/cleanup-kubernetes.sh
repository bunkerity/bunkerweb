#!/bin/bash

helm delete moodle
kubectl delete pvc data-moodle-mariadb-0
