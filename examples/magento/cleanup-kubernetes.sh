#!/bin/bash

helm delete magento
kubectl delete pvc data-magento-elasticsearch-data-0
kubectl delete pvc data-magento-elasticsearch-master-0
kubectl delete pvc data-magento-mariadb-0
