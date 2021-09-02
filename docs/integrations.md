# Integrations

## Docker

You can get official prebuilt Docker images of bunkerized-nginx for x86, x64, armv7 and aarch64/arm64 architectures on Docker Hub :
```shell
$ docker pull bunkerity/bunkerized-nginx
```

Or you can build it from source if you wish :
```shell
$ git clone https://github.com/bunkerity/bunkerized-nginx.git
$ cd bunkerized-nginx
$ docker build -t bunkerized-nginx .
```

To use bunkerized-nginx as a Docker container you have to pass specific environment variables, mount volumes and redirect ports to make it accessible from the outside.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/docs/img/docker.png?raw=true" />

To demonstrate the use of the Docker image, we will create a simple "Hello World" static file that will be served by bunkerized-nginx.

**One important thing to know is that the container runs as an unprivileged user with UID and GID 101. The reason behind this behavior is the security : in case a vulnerability is exploited the attacker won't have full privileges inside the container. But there is also a downside because bunkerized-nginx (heavily) make use of volumes, you will need to adjust the rights on the host.**

First create the environment on the host :
```shell
$ mkdir bunkerized-hello bunkerized-hello/www bunkerized-hello/certs
$ cd bunkerized-hello
$ chown root:101 www certs
$ chmod 750 www
$ chmod 770 certs
```

The www folder will contain our static files that will be served by bunkerized-nginx. Whereas the certs folder will store the automatically generated Let's Encrypt certificates.

Let's create a dummy static page into the www folder :
```shell
$ echo "Hello bunkerized World !" > www/index.html
$ chown root:101 www/index.html
$ chmod 740 www/index.html
```

It's time to run the container :
```shell
$ docker run \
         -p 80:8080 \
         -p 443:8443 \
         -v "${PWD}/www:/www:ro" \
         -v "${PWD}/certs:/etc/letsencrypt" \
         -e SERVER_NAME=www.example.com \
         -e AUTO_LETS_ENCRYPT=yes \
         bunkerity/bunkerized-nginx
```

Or if you prefer docker-compose :
```yaml
version: '3'
services:
  mybunkerized:
    image: bunkerity/bunkerized-nginx
    ports:
      - 80:8080
      - 443:8443
    volumes:
      - ./www:/www:ro
      - ./certs:/etc/letsencrypt
    environment:
      - SERVER_NAME=www.example.com
      - AUTO_LETS_ENCRYPT=yes
```

Important things to note :
- Replace www.example.com with your own domain (it must points to your server IP address if you want Let's Encrypt to work)
- Automatic Let's Encrypt is enabled thanks to `AUTO_LETS_ENCRYPT=yes` (since the default is `AUTO_LETS_ENCRYPT=no` you can remove the environment variable to disable Let's Encrypt)
- The container is exposing TCP/8080 for HTTP and TCP/8443 for HTTPS
- The /www volume is used to deliver static files and can be mounted as read-only for security reason
- The /etc/letsencrypt volume is used to store certificates and must be mounted as read/write

Inspect the container logs until bunkerized-nginx is started then visit http(s)://www.example.com to confirm that everything is working as expected.

This example is really simple but, as you can see in the [list of environment variables](https://bunkerized-nginx.readthedocs.io/en/latest/environment_variables.html), you may get a lot of environment variables depending on your use case. To make things cleanier, you can write the environment variables to a file :
```shell
$ cat variables.env
SERVER_NAME=www.example.com
AUTO_LETS_ENCRYPT=yes
```

And load the file when creating the container :
```shell
$ docker run ... --env-file "${PWD}/variables.env" ... bunkerity/bunkerized-nginx
```

Or if you prefer docker-compose :
```yaml
...
services:
  mybunkerized:
    ...
    env_file:
      - ./variables.env
    ...
...
```

## Docker autoconf

The downside of using environment variables is that the container needs to be recreated each time there is an update which is not very convenient. To counter that issue, you can use another image called bunkerized-nginx-autoconf which will listen for Docker events and automatically configure bunkerized-nginx instance in real time without recreating the container. Instead of defining environment variables for the bunkerized-nginx container, you simply add labels to your web services and bunkerized-nginx-autoconf will "automagically" take care of the rest.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/docs/img/autoconf-docker.png?raw=true" />

First of all, you will need a network to allow communication between bunkerized-nginx and your web services :
```shell
$ docker network create services-net
```

We will also make use of a named volume to share the configuration between autoconf and bunkerized-nginx :
```shell
$ docker volume create bunkerized-vol
```

You can now create the bunkerized-nginx container :
```shell
$ docker run \
         --name mybunkerized \
         -l bunkerized-nginx.AUTOCONF \
         --network services-net \
         -p 80:8080 \
         -p 443:8443 \
         -v "${PWD}/www:/www:ro" \
         -v "${PWD}/certs:/etc/letsencrypt" \
         -v bunkerized-vol:/etc/nginx \
         -e MULTISITE=yes \
         -e SERVER_NAME= \
         -e AUTO_LETS_ENCRYPT=yes \
         bunkerity/bunkerized-nginx
```

The autoconf one can now be started :
```shell
$ docker run \
         --name myautoconf \
         --volumes-from mybunkerized:rw \
         -v /var/run/docker.sock:/var/run/docker.sock:ro \
         bunkerity/bunkerized-nginx-autoconf
```

Here is the docker-compose equivalent :
```yaml
version: '3'

services:

  mybunkerized:
    image: bunkerity/bunkerized-nginx
    restart: always
    ports:
      - 80:8080
      - 443:8443
    volumes:
      - ./certs:/etc/letsencrypt
      - ./www:/www:ro
      - bunkerized-vol:/etc/nginx
    environment:
      - SERVER_NAME=
      - MULTISITE=yes
      - AUTO_LETS_ENCRYPT=yes
    labels:
      - "bunkerized-nginx.AUTOCONF"
    networks:
      - services-net

  myautoconf:
    image: bunkerity/bunkerized-nginx-autoconf
    restart: always
    volumes_from:
      - mybunkerized
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      - mybunkerized

volumes:
  bunkerized-vol:

networks:
  services-net:
    name: services-net
```

Important things to note :
- autoconf is generating config files and other artefacts for the bunkerized-nginx, they need to share the same volumes
- autoconf must have access to the Docker socket in order to get events, access to labels and send SIGHUP signal (reload order) to bunkerized-nginx
- bunkerized-nginx must have the bunkerized-nginx.AUTOCONF label
- bunkerized-nginx must be started in [multisite mode](https://bunkerized-nginx.readthedocs.io/en/latest/quickstart_guide.html#multisite) with the `MULTISITE=yes` environment variable
- When setting the `SERVER_NAME` environment variable to an empty value, bunkerized-nginx won't generate any web service configuration at startup
- The `AUTO_LETS_ENCRYPT=yes` will be applied to all subsequent web service configuration, unless overriden by the web service labels

Check the logs of both autoconf and bunkerized-nginx to see if everything is working as expected.

You can now create a new web service and add environment variables as labels with the `bunkerized-nginx.` prefix to let the autoconf service "automagically" do the configuration for you :
```shell
$ docker run \
         --name myservice \
         --network services-net \
         -l bunkerized-nginx.SERVER_NAME=www.example.com \
         -l bunkerized-nginx.USE_REVERSE_PROXY=yes \
         -l bunkerized-nginx.REVERSE_PROXY_URL=/ \
         -l bunkerized-nginx.REVERSE_PROXY_HOST=http://myservice \
         tutum/hello-world
```

docker-compose equivalent :
```yaml
version: "3"

services:

  myservice:
    image: tutum/hello-world
    networks:
      services-net:
        aliases:
          - myservice
    labels:
      - "bunkerized-nginx.SERVER_NAME=www.example.com"
      - "bunkerized-nginx.USE_REVERSE_PROXY=yes"
      - "bunkerized-nginx.REVERSE_PROXY_URL=/"
      - "bunkerized-nginx.REVERSE_PROXY_HOST=http://myservice"

networks:
  services-net:
    external:
      name: services-net
```

Please note that if you want to override the `AUTO_LETS_ENCRYPT=yes` previously defined in the bunkerized-nginx container, you simply need to add the `bunkerized-nginx.AUTO_LETS_ENCRYPT=no` label.

Look at the logs of both autoconf and bunkerized-nginx to check if the configuration has been generated and loaded by bunkerized-nginx. You should now be able to visit http(s)://www.example.com.

When your container is not needed anymore, you can delete it as usual. The autoconf should get the event and generate the configuration again.

## Docker Swarm

Using bunkerized-nginx in a Docker Swarm cluster requires a shared folder accessible from both managers and workers (anything like NFS, GlusterFS, CephFS or even SSHFS will work). The deployment and configuration is very similar to the "Docker autoconf" one but with services instead of containers. A service based on the bunkerized-nginx-autoconf image needs to be scheduled on a manager node (don't worry it doesn't expose any network port for obvious security reasons). This service will listen for Docker Swarm events like service creation or deletion and generate the configuration according to the labels of each service. Once configuration generation is done, the bunkerized-nginx-autoconf service will send a reload order to all the bunkerized-nginx tasks so they can load the new configuration.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/docs/img/swarm.png?raw=true" />

**We will assume that a shared directory is mounted at the /shared location on both your managers and workers. Keep in mind that bunkerized-nginx and autoconf are running as unprivileged users with UID and GID 101. You must set the rights and permissions of the subfolders in /shared accordingly.**

In this setup we will deploy bunkerized-nginx in global mode on all workers and autoconf as a single replica on a manager.

First of all, you will need to setup the shared folders :
```shell
$ cd /shared
$ mkdir www confs letsencrypt acme-challenge
$ chown root:101 www confs letsencrypt acme-challenge
$ chmod 770 www confs letsencrypt acme-challenge
```

Then you will need to create 2 networks, one for the communication between bunkerized-nginx and autoconf and the other one for the communication between bunkerized-nginx and the web services :
```shell
$ docker network create -d overlay --attachable bunkerized-net
$ docker network create -d overlay --attachable services-net
```

We can now start the bunkerized-nginx as a service :
```shell
$ docker service create \
         --name mybunkerized \
         --mode global \
         --constraint node.role==worker \
         -l bunkerized-nginx.AUTOCONF \
         --network bunkerized-net \
         -p published=80,target=8080,mode=host \
         -p published=443,target=8443,mode=host \
         --mount type=bind,source=/shared/confs,destination=/etc/nginx,ro \
         --mount type=bind,source=/shared/www,destination=/www,ro \
         --mount type=bind,source=/shared/letsencrypt,destination=/etc/letsencrypt,ro \
         --mount type=bind,source=/shared/acme-challenge,destination=/acme-challenge,ro \
         -e SWARM_MODE=yes \
         -e USE_API=yes \
         -e API_URI=/ChangeMeToSomethingHardToGuess \
         -e SERVER_NAME= \
         -e MULTISITE=yes \
         -e AUTO_LETS_ENCRYPT=yes \
         bunkerity/bunkerized-nginx
$ docker service update \
         --network-add services-net \
         mybunkerized
```

Once bunkerized-nginx has been started you can start the autoconf as a service :
```shell
$ docker service create \
         --name myautoconf \
         --replicas 1 \
         --constraint node.role==manager \
         --network bunkerized-net \
         --mount type=bind,source=/var/run/docker.sock,destination=/var/run/docker.sock,ro \
         --mount type=bind,source=/shared/confs,destination=/etc/nginx \
         --mount type=bind,source=/shared/letsencrypt,destination=/etc/letsencrypt \
         --mount type=bind,source=/shared/acme-challenge,destination=/acme-challenge \
         -e SWARM_MODE=yes \
         -e API_URI=/ChangeMeToSomethingHardToGuess \
         bunkerity/bunkerized-nginx-autoconf
```

Or do the same with docker-compose if you wish :
```yaml
version: '3.8'

services:

  nginx:
    image: bunkerity/bunkerized-nginx
    ports:
      - published: 80
        target: 8080
        mode: host
        protocol: tcp
      - published: 443
        target: 8443
        mode: host
        protocol: tcp
    volumes:
      - /shared/confs:/etc/nginx:ro
      - /shared/www:/www:ro
      - /shared/letsencrypt:/etc/letsencrypt:ro
      - /shared/acme-challenge:/acme-challenge:ro
    environment:
      - SWARM_MODE=yes
      - USE_API=yes
      - API_URI=/ChangeMeToSomethingHardToGuess # must match API_URI from autoconf
      - MULTISITE=yes
      - SERVER_NAME=
      - AUTO_LETS_ENCRYPT=yes
    networks:
      - bunkerized-net
      - services-net
    deploy:
      mode: global
      placement:
        constraints:
          - "node.role==worker"
      # mandatory label
      labels:
        - "bunkerized-nginx.AUTOCONF"

  autoconf:
    image: bunkerity/bunkerized-nginx-autoconf
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /shared/confs:/etc/nginx
      - /shared/letsencrypt:/etc/letsencrypt
      - /shared/acme-challenge:/acme-challenge
    environment:
      - SWARM_MODE=yes
      - API_URI=/ChangeMeToSomethingHardToGuess # must match API_URI from nginx
    networks:
      - bunkerized-net
    deploy:
      replicas: 1
      placement:
        constraints:
          - "node.role==manager"

# This will create the networks for you
networks:
  bunkerized-net:
    driver: overlay
    attachable: true
    name: bunkerized-net
  services-net:
    driver: overlay
    attachable: true
    name: services-net
```

Check the logs of both autoconf and bunkerized-nginx services to see if everything is working as expected.

You can now create a new service and add environment variables as labels with the `bunkerized-nginx.` prefix to let the autoconf service "automagically" do the configuration for you :
```shell
$ docker service create \
         --name myservice \
         --constraint node.role==worker \
         --network services-net \
         -l bunkerized-nginx.SERVER_NAME=www.example.com \
         -l bunkerized-nginx.USE_REVERSE_PROXY=yes \
         -l bunkerized-nginx.REVERSE_PROXY_URL=/ \
         -l bunkerized-nginx.REVERSE_PROXY_HOST=http://myservice \
         tutum/hello-world
```

docker-compose equivalent :
```yaml
version: "3"

services:

  myservice:
    image: tutum/hello-world
    networks:
      - services-net
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerized-nginx.SERVER_NAME=www.example.com"
        - "bunkerized-nginx.USE_REVERSE_PROXY=yes"
        - "bunkerized-nginx.REVERSE_PROXY_URL=/"
        - "bunkerized-nginx.REVERSE_PROXY_HOST=http://myservice"

networks:
  services-net:
    external:
      name: services-net
```

Please note that if you want to override the `AUTO_LETS_ENCRYPT=yes` previously defined in the bunkerized-nginx service, you simply need to add the `bunkerized-nginx.AUTO_LETS_ENCRYPT=no` label.

Look at the logs of both autoconf and bunkerized-nginx to check if the configuration has been generated and loaded by bunkerized-nginx. You should now be able to visit http(s)://www.example.com.

When your service is not needed anymore, you can delete it as usual. The autoconf should get the event and generate the configuration again.

## Kubernetes

**This integration is still in beta, please fill an issue if you find a bug or have an idea on how to improve it.**

Using bunkerized-nginx in a Kubernetes cluster requires a shared folder accessible from the nodes (anything like NFS, GlusterFS, CephFS or even SSHFS will work). The bunkerized-nginx-autoconf acts as an Ingress Controller and connects to the k8s API to get cluster events and generate a new configuration when it's needed. Once the configuration is generated, the Ingress Controller sends a reload order to the bunkerized-nginx instances running in the cluster.

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/docs/img/kubernetes.png?raw=true" />

**We will assume that a shared directory is mounted at the /shared location on your nodes. Keep in mind that bunkerized-nginx and autoconf are running as unprivileged users with UID and GID 101. You must set the rights and permissions of the subfolders in /shared accordingly.**

First of all, you will need to setup the shared folders :
```shell
$ cd /shared
$ mkdir www confs letsencrypt acme-challenge
$ chown root:nginx www confs letsencrypt acme-challenge
$ chmod 770 www confs letsencrypt acme-challenge
```

The first step to do is to declare the RBAC authorization that will be used by the Ingress Controller to access the Kubernetes API. A ready-to-use declaration is available here :
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: bunkerized-nginx-ingress-controller
rules:
- apiGroups: [""]
  resources: ["services", "pods"]
  verbs: ["get", "watch", "list"]
- apiGroups: ["extensions"]
  resources: ["ingresses"]
  verbs: ["get", "watch", "list"]
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: bunkerized-nginx-ingress-controller
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: bunkerized-nginx-ingress-controller
subjects:
- kind: ServiceAccount
  name: bunkerized-nginx-ingress-controller
  namespace: default
  apiGroup: ""
roleRef:
  kind: ClusterRole
  name: bunkerized-nginx-ingress-controller
  apiGroup: rbac.authorization.k8s.io
```

Next, you can deploy bunkerized-nginx as a DaemonSet :
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: bunkerized-nginx
  labels:
    app: bunkerized-nginx
spec:
  selector:
    matchLabels:
      name: bunkerized-nginx
  template:
    metadata:
      labels:
        name: bunkerized-nginx
        # this label is mandatory
        bunkerized-nginx: "yes"
    spec:
      containers:
      - name: bunkerized-nginx
        image: bunkerity/bunkerized-nginx
        ports:
        - containerPort: 8080
          hostPort: 80
        - containerPort: 8443
          hostPort: 443
        env:
        - name: KUBERNETES_MODE
          value: "yes"
        - name: DNS_RESOLVERS
          value: "kube-dns.kube-system.svc.cluster.local"
        - name: USE_API
          value: "yes"
        - name: API_URI
          value: "/ChangeMeToSomethingHardToGuess"
        - name: SERVER_NAME
          value: ""
        - name: MULTISITE
          value: "yes"
        volumeMounts:
        - name: confs
          mountPath: /etc/nginx
          readOnly: true
        - name: letsencrypt
          mountPath: /etc/letsencrypt
          readOnly: true
        - name: acme-challenge
          mountPath: /acme-challenge
          readOnly: true
        - name: www
          mountPath: /www
          readOnly: true
      volumes:
      - name: confs
        hostPath:
          path: /shared/confs
          type: Directory
      - name: letsencrypt
        hostPath:
          path: /shared/letsencrypt
          type: Directory
      - name: acme-challenge
        hostPath:
          path: /shared/acme-challenge
          type: Directory
      - name: www
        hostPath:
          path: /shared/www
          type: Directory
---
apiVersion: v1
kind: Service
metadata:
  name: bunkerized-nginx-service
  # this label is mandatory
  labels:
    bunkerized-nginx: "yes"
  # this annotation is mandatory
  annotations:
    bunkerized-nginx.AUTOCONF: "yes"
spec:
  clusterIP: None
  selector:
    name: bunkerized-nginx
```

Important thing to note, labels and annotations defined are mandatory for autoconf to work.

You can now deploy the autoconf which will act as the ingress controller :
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bunkerized-nginx-ingress-controller
  labels:
    app: bunkerized-nginx-autoconf
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bunkerized-nginx-autoconf
  template:
    metadata:
      labels:
        app: bunkerized-nginx-autoconf
    spec:
      serviceAccountName: bunkerized-nginx-ingress-controller
      containers:
      - name: bunkerized-nginx-autoconf
        image: bunkerity/bunkerized-nginx-autoconf
        env:
        - name: KUBERNETES_MODE
          value: "yes"
        - name: API_URI
          value: "/ChangeMeToSomethingHardToGuess"
        volumeMounts:
        - name: confs
          mountPath: /etc/nginx
        - name: letsencrypt
          mountPath: /etc/letsencrypt
        - name: acme-challenge
          mountPath: /acme-challenge
      volumes:
      - name: confs
        hostPath:
          path: /shared/confs
          type: Directory
      - name: letsencrypt
        hostPath:
          path: /shared/letsencrypt
          type: Directory
      - name: acme-challenge
        hostPath:
          path: /shared/acme-challenge
          type: Directory
```

Check the logs of both bunkerized-nginx and autoconf deployments to see if everything is working as expected.

You can now deploy your web service and make it accessible from within the cluster :
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  labels:
    app: myapp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: myapp
        image: containous/whoami
---
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  type: ClusterIP
  selector:
    app: myapp
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
```

Last but not least, it's time to define your Ingress resource to make your web service publicly available :
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bunkerized-nginx-ingress
  # this label is mandatory
  labels:
    bunkerized-nginx: "yes"
  annotations:
    # add any global and default environment variables here as annotations with the "bunkerized-nginx." prefix
    # examples :
    #bunkerized-nginx.AUTO_LETS_ENCRYPT: "yes"
    #bunkerized-nginx.USE_ANTIBOT: "javascript"
    #bunkerized-nginx.REDIRECT_HTTP_TO_HTTPS: "yes"
    #bunkerized-nginx.www.example.com_REVERSE_PROXY_WS: "yes"
    #bunkerized-nginx.www.example.com_USE_MODSECURITY: "no"
spec:
  tls:
  - hosts:
    - www.example.com
  rules:
  - host: "www.example.com"
    http:
      paths:
      - pathType: Prefix
        path: "/"
        backend:
          service:
            name: myapp
            port:
              number: 80
```

Check the logs to see if the configuration has been generated and bunkerized-nginx reloaded. You should be able to visit http(s)://www.example.com.

Note that an alternative would be to add annotations directly to your services (a common use-case is for [PHP applications](https://bunkerized-nginx.readthedocs.io/en/latest/quickstart_guide.html#php-applications) because the Ingress resource is only for reverse proxy) without editing the Ingress resource :
```yaml
apiVersion: v1
kind: Service
metadata:
  name: myapp
  # this label is mandatory
  labels:
    bunkerized-nginx: "yes"
  annotations:
    bunkerized-nginx.SERVER_NAME: "www.example.com"
    bunkerized-nginx.AUTO_LETS_ENCRYPT: "yes"
    bunkerized-nginx.USE_REVERSE_PROXY: "yes"
    bunkerized-nginx.REVERSE_PROXY_URL: "/"
    bunkerized-nginx.REVERSE_PROXY_HOST: "http://myapp.default.svc.cluster.local"
spec:
  type: ClusterIP
  selector:
    app: myapp
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
```

## Linux

**This integration is still in beta, please fill an issue if you find a bug or have an idea on how to improve it.**

List of supported Linux distributions :
- Debian buster (10)
- Ubuntu focal (20.04)
- CentOS 7
- Fedora 34

Unlike containers, Linux integration can be tedious because bunkerized-nginx has a bunch of dependencies that need to be installed before we can use it. Fortunately, we provide a helper script to make the process easier and automatic. Once installed, the configuration is really simple, all you have to do is to edit the `/opt/bunkerized-nginx/variables.env` configuration file and run the `bunkerized-nginx` command to apply it.

First of all you will need to install bunkerized-nginx. The recommended way is to use the official installer script :
```shell
$ curl -fsSL https://github.com/bunkerity/bunkerized-nginx/releases/download/v1.3.1/linux-install.sh -o /tmp/bunkerized-nginx.sh
```

Before executing it, you should also check the signature :
```shell
$ curl -fsSL https://github.com/bunkerity/bunkerized-nginx/releases/download/v1.3.1/linux-install.sh.asc -o /tmp/bunkerized-nginx.sh.asc
$ gpg --auto-key-locate hkps://keys.openpgp.org --locate-keys contact@bunkerity.com
$ gpg --verify /tmp/bunkerized-nginx.sh.asc /tmp/bunkerized-nginx.sh
```

You can now install bunkerized-nginx (and take a coffee because it may take a while) :
```shell
$ chmod +x /tmp/bunkerized-nginx.sh
$ /tmp/bunkerized-nginx.sh
```

To demonstrate the configuration on Linux, we will create a simple “Hello World” static file that will be served by bunkerized-nginx.

Static files are stored inside the `/opt/bunkerized-nginx/www` folder and the unprivileged nginx user must have read access on it :
```shell
$ echo "Hello bunkerized World !" > /opt/bunkerized-nginx/www/index.html
$ chown root:nginx /opt/bunkerized-nginx/www/index.html
$ chmod 740 /opt/bunkerized-nginx/www/index.html
```

Here is the example configuration file that needs to be written at `/opt/bunkerized-nginx/variables.env` :
```conf
HTTP_PORT=80
HTTPS_PORT=443
DNS_RESOLVERS=8.8.8.8 8.8.4.4
SERVER_NAME=www.example.com
AUTO_LETS_ENCRYPT=yes
```

Important things to note :
- Replace www.example.com with your own domain (it must points to your server IP address if you want Let’s Encrypt to work)
- Automatic Let’s Encrypt is enabled thanks to `AUTO_LETS_ENCRYPT=yes` (since the default is `AUTO_LETS_ENCRYPT=no` you can remove the environment variable to disable Let’s Encrypt)
- The default values for `HTTP_PORT` and `HTTPS_PORT` are `8080` and `8443` hence the explicit declaration with standard ports values
- Replace the `DNS_RESOLVERS` value with your own DNS resolver(s) if you need nginx to resolve internal DNS requests (e.g., reverse proxy to an internal service)

You can now apply the configuration by running the **bunkerized-nginx** command :
```shell
$ bunkerized-nginx
```

Visit http(s)://www.example.com to confirm that everything is working as expected.
