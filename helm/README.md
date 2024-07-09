# bunkerweb

![Version: 0.1.0](https://img.shields.io/badge/Version-0.1.0-informational?style=flat-square) ![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square) ![AppVersion: 0.1.0](https://img.shields.io/badge/AppVersion-0.1.0-informational?style=flat-square)

# Description

A Helm chart for Kubernetes

# Sections

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| bunkerweb | object | `{"containerSecurityContext":{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"runAsGroup":101,"runAsUser":101},"env":{"API_WHITELIST_IP":"127.0.0.0/8 10.0.0.0/8","DNS_RESOLVERS":"coredns.kube-system.svc.cluster.local","KUBERNETES_MODE":"yes","MULTISITE":"yes","REDIS_HOST":"svc-bunkerweb-redis.default.svc.cluster.local","SERVER_NAME":"","USE_API":"yes","USE_REDIS":"yes"},"envFrom":{},"image":{"imagePullPolicy":"Always","repository":"bunkerity/bunkerweb","tag":"1.5.7"},"nodeSelector":{},"podSecurityContext":{},"resources":{},"service":{"annotations":{},"clusterIP":"None","ports":[{"name":"http","port":80,"protocol":"TCP","targetPort":"http"},{"name":"https","port":443,"protocol":"TCP","targetPort":"https"}]}}` | bunkerweb daemonset pod |
| bunkerweb.containerSecurityContext | object | `{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"runAsGroup":101,"runAsUser":101}` | containerSecurityContext |
| bunkerweb.env | object | `{"API_WHITELIST_IP":"127.0.0.0/8 10.0.0.0/8","DNS_RESOLVERS":"coredns.kube-system.svc.cluster.local","KUBERNETES_MODE":"yes","MULTISITE":"yes","REDIS_HOST":"svc-bunkerweb-redis.default.svc.cluster.local","SERVER_NAME":"","USE_API":"yes","USE_REDIS":"yes"}` | environnement variable |
| bunkerweb.envFrom | object | `{}` | envFrom for mount secret or configmap |
| bunkerweb.image | object | `{"imagePullPolicy":"Always","repository":"bunkerity/bunkerweb","tag":"1.5.7"}` | image configuration |
| bunkerweb.nodeSelector | object | `{}` | nodeSelector for choose node on deploy this pod |
| bunkerweb.podSecurityContext | object | `{}` | podSecurityContext |
| bunkerweb.resources | object | `{}` | cpu and memory resources |
| bunkerweb.service | object | `{"annotations":{},"clusterIP":"None","ports":[{"name":"http","port":80,"protocol":"TCP","targetPort":"http"},{"name":"https","port":443,"protocol":"TCP","targetPort":"https"}]}` | service configuration |
| controller | object | `{"containerSecurityContext":{},"env":{"DATABASE_URI":"mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db","KUBERNETES_MODE":"yes"},"envFrom":{},"image":{"imagePullPolicy":"Always","repository":"bunkerity/bunkerweb-autoconf","tag":"1.5.7"},"nodeSelector":{},"podSecurityContext":{},"replicas":1,"resources":{}}` | bunkerweb controller |
| controller.containerSecurityContext | object | `{}` | containerSecurityContext |
| controller.env | object | `{"DATABASE_URI":"mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db","KUBERNETES_MODE":"yes"}` | environnement variable |
| controller.envFrom | object | `{}` | envFrom |
| controller.image | object | `{"imagePullPolicy":"Always","repository":"bunkerity/bunkerweb-autoconf","tag":"1.5.7"}` | image settings |
| controller.nodeSelector | object | `{}` | nodeSelector for choose node on deploy this pod |
| controller.podSecurityContext | object | `{}` | podSecurityContext |
| controller.replicas | int | `1` | replica |
| controller.resources | object | `{}` | resources cpu/memory |
| db | object | `{"containerSecurityContext":{},"enabled":true,"env":{"MYSQL_DATABASE":"db","MYSQL_PASSWORD":"changeme","MYSQL_RANDOM_ROOT_PASSWORD":"yes","MYSQL_USER":"bunkerweb"},"envFrom":{},"image":{"imagePullPolicy":"Always","repository":"mariadb","tag":"10.10"},"nodeSelector":{},"persistence":{"enabled":true,"storageClassName":"","storageRequest":"5Gi"},"podSecurityContext":{},"replicas":1,"resources":{},"service":{"ports":[{"name":"sql","port":3306,"protocol":"TCP","targetPort":3306}],"type":"ClusterIP"}}` | mysql database configuration |
| db.containerSecurityContext | object | `{}` | containerSecurityContext |
| db.enabled | bool | `true` | deploy database |
| db.env | object | `{"MYSQL_DATABASE":"db","MYSQL_PASSWORD":"changeme","MYSQL_RANDOM_ROOT_PASSWORD":"yes","MYSQL_USER":"bunkerweb"}` | environnement variable |
| db.envFrom | object | `{}` | envFrom |
| db.image | object | `{"imagePullPolicy":"Always","repository":"mariadb","tag":"10.10"}` | image settings |
| db.nodeSelector | object | `{}` | nodeSelector for choose node on deploy this pod |
| db.persistence | object | `{"enabled":true,"storageClassName":"","storageRequest":"5Gi"}` | enable storage |
| db.podSecurityContext | object | `{}` | podSecurityContext |
| db.replicas | int | `1` | number of replicas |
| db.resources | object | `{}` | resources |
| db.service | object | `{"ports":[{"name":"sql","port":3306,"protocol":"TCP","targetPort":3306}],"type":"ClusterIP"}` | services configuration |
| kubernetesClusterDomain | string | `"cluster.local"` | kubernetes cluster domain |
| redis | object | `{"containerSecurityContext":{},"enabled":true,"envFrom":{},"image":{"imagePullPolicy":"Always","repository":"redis","tag":"7-alpine"},"nodeSelector":{},"podSecurityContext":{},"replicas":1,"resources":{},"service":{"ports":[{"name":"redis","port":6379,"protocol":"TCP","targetPort":6379}],"type":"ClusterIP"}}` | redis configuration |
| redis.containerSecurityContext | object | `{}` | containerSecurityContext |
| redis.enabled | bool | `true` | enabled redis deployment |
| redis.envFrom | object | `{}` | enFrom |
| redis.image | object | `{"imagePullPolicy":"Always","repository":"redis","tag":"7-alpine"}` | image settings |
| redis.nodeSelector | object | `{}` | nodeSelector for choose node on deploy this pod |
| redis.podSecurityContext | object | `{}` | podSecurityContext |
| redis.replicas | int | `1` | number of replicas |
| redis.resources | object | `{}` | resources cpu/mem |
| redis.service | object | `{"ports":[{"name":"redis","port":6379,"protocol":"TCP","targetPort":6379}],"type":"ClusterIP"}` | service configuration |
| saBunkerweb | object | `{"serviceAccount":{"annotations":{}}}` | service Account for scheduler and controller |
| scheduler | object | `{"containerSecurityContext":{},"env":{"DATABASE_URI":"mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db","KUBERNETES_MODE":"yes"},"envFrom":{},"image":{"imagePullPolicy":"Always","repository":"bunkerity/bunkerweb-scheduler","tag":"1.5.7"},"nodeSelector":{},"podSecurityContext":{},"replicas":1,"resources":{}}` | bunkerweb scheduler  |
| scheduler.containerSecurityContext | object | `{}` | containerSecurityContext |
| scheduler.env | object | `{"DATABASE_URI":"mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db","KUBERNETES_MODE":"yes"}` | environnement variable |
| scheduler.envFrom | object | `{}` | envFrom |
| scheduler.image | object | `{"imagePullPolicy":"Always","repository":"bunkerity/bunkerweb-scheduler","tag":"1.5.7"}` | image settings |
| scheduler.nodeSelector | object | `{}` | nodeSelector for choose node on deploy this pod |
| scheduler.podSecurityContext | object | `{}` | podSecurityContext |
| scheduler.replicas | int | `1` | replicas |
| scheduler.resources | object | `{}` | resources |
| ui | object | `{"containerSecurityContext":{},"enabled":true,"env":{"ABSOLUTE_URI":"https://bunkerweb-build.service.ovh/","ADMIN_PASSWORD":"ChangeIT","ADMIN_USERNAME":"bunkerAdmin","DATABASE_URI":"mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db","KUBERNETES_MODE":"yes"},"envFrom":{},"image":{"imagePullPolicy":"Always","repository":"bunkerity/bunkerweb-ui:1.5.7","tag":"1.5.7"},"ingress":{"annotations":{},"enabled":true,"host":"bunkerweb.tld.local","ingressClassName":"","path":"/","secretName":"mysecret"},"nodeSelector":{},"podSecurityContext":{},"replicas":1,"resources":{},"service":{"annotations":{},"ports":[{"name":"http","port":7000,"protocol":"TCP","targetPort":7000}],"type":"ClusterIP"}}` | bunkerweb ui |
| ui.containerSecurityContext | object | `{}` | containerSecurityContext |
| ui.enabled | bool | `true` | enabled deployement of ui |
| ui.env | object | `{"ABSOLUTE_URI":"https://bunkerweb-build.service.ovh/","ADMIN_PASSWORD":"ChangeIT","ADMIN_USERNAME":"bunkerAdmin","DATABASE_URI":"mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db","KUBERNETES_MODE":"yes"}` | environnement variable |
| ui.envFrom | object | `{}` | envFrom |
| ui.image | object | `{"imagePullPolicy":"Always","repository":"bunkerity/bunkerweb-ui:1.5.7","tag":"1.5.7"}` | image settings |
| ui.ingress | object | `{"annotations":{},"enabled":true,"host":"bunkerweb.tld.local","ingressClassName":"","path":"/","secretName":"mysecret"}` | ingress configuration |
| ui.ingress.enabled | bool | `true` | enable ingress for ui |
| ui.nodeSelector | object | `{}` | nodeSelector for choose node on deploy this pod |
| ui.podSecurityContext | object | `{}` | podSecurityContext |
| ui.replicas | int | `1` | replica |
| ui.resources | object | `{}` | resources cpu/memory |
| ui.service | object | `{"annotations":{},"ports":[{"name":"http","port":7000,"protocol":"TCP","targetPort":7000}],"type":"ClusterIP"}` | service configuration |
