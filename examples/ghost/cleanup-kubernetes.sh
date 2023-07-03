#!/bin/bash

helm delete ghost
kubectl delete pvc data-ghost-mysql-0
