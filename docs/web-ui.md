# Web UI

## Overview

<p align="center">
	<iframe style="display: block;" width="560" height="315" src="https://www.youtube-nocookie.com/embed/2n4EarhW7-Y" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

The "Web UI" is a web application that helps you manage your BunkerWeb instance using a user-friendly interface instead of the command-line one.

## Features

- Start, stop, restart and reload your BunkerWeb instance
- Add, edit and delete settings for your web applications
- Add, edit and delete custom configurations for NGINX and ModSecurity
- Install and uninstall external plugins
- View the logs and search pattern

## Installation

Because the web UI is a web application, the recommended installation procedure is to use BunkerWeb in front of it as a reverse proxy.

!!! warning "Security considerations"

    The security of the web UI is really important. If someone manages to gain access to the application, not only he will be able to edit your configurations but he could execute some code in the context of BunkerWeb (with a custom configuration containing LUA code for example). We highly recommend you to follow minimal security best practices like :

    * Choose a strong password for the login
    * Put the web UI under a "hard to guess" URI
    * Do not open the web UI on the Internet without any further restrictions
    * Apply settings listed in the [security tuning section](/1.4/security-tuning/) of the documentation

!!! info "Multisite mode"

    The installation of the web UI implies enabling the [multisite mode](/1.4/concepts/#multisite-mode).

!!! info "UI specific env variables"

    * Don't forget to add `USE_UI` environnement variable as it adds the security rules needed for `Modsecurity` to work with the UI.
    * Also it is advised to tweak the `INTERCEPTED_ERROR_CODES` setting to stop Bunkerweb from intercepting certain HTTP errors.

=== "Docker"

    When using the [Docker integration](/1.4/integrations/#docker), we recommend you to connect BunkerWeb and web UI using a dedicated network like with the scheduler and use another dedicated network for the communications between BunkerWeb and your web applications. The web UI can be deployed using a dedicated container based on the [bunkerweb-ui image](https://hub.docker.com/r/bunkerity/bunkerweb-ui).

    Let's start by creating the networks (replace 10.20.30.0/24 with an unused network of your choice) :
    ```shell
    docker network create --subnet 10.20.30.0/24 bw-universe && \
    docker network create bw-services
    ```

    You will also need the data volume, which where BunkerWeb's data will be stored :
    ```shell
    docker volume create bw-data
    ```

    You can now create the BunkerWeb container with specific settings related to the web UI, please note the special `bunkerweb.INSTANCE` label which is mandatory for the scheduler as well as the web UI to work properly :
    ```shell
    docker run -d \
       --name bunkerweb \
       --network bw-services \
       -p 80:8080 \
       -p 443:8443 \
       -e SERVER_NAME=bwadm.example.com \
       -e MULTISITE=yes \
       -e "API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24" \
       -e bwadm.example.com_USE_UI=yes \
       -e bwadm.example.com_USE_REVERSE_PROXY=yes \
       -e bwadm.example.com_REVERSE_PROXY_URL=/changeme/ \
       -e bwadm.example.com_REVERSE_PROXY_HOST=http://bw-ui:7000 \
       -e "bwadm.example.com_REVERSE_PROXY_HEADERS=X-Script-Name /changeme" \
       -e bwadm.example.com_INTERCEPTED_ERROR_CODES="400 401 405 413 429 500 501 502 503 504" \
       -l bunkerweb.INSTANCE \
       bunkerity/bunkerweb:1.4.6 && \
    docker network connect bw-universe bunkerweb
    ```

    Important things to note :

    * `bwadm.example.com` is the dedicated (sub)domain for accessing the web UI
    * replace `10.20.30.0/24` with the same network address used for the `bw-universe` network
    * replace the `/changeme` URL with a custom one of your choice
    * the `bunkerweb.INSTANCE` label is mandatory

    The web UI will need to access the Docker API in order to get metadata about the running containers. It can be done easily by mounting the **docker.sock** file into the container. But there is a security risk : if the web UI is exploited, all your container(s) and the host will be impacted because, at the moment, Docker doesn't provide any restriction feature. We highly recommend using something like a [docker socket proxy](https://github.com/Tecnativa/docker-socket-proxy) to mitigate that risk (only a subset of read-only API endpoints will be available to the web UI container).

    To connect the docker socket proxy and the web UI, you will need another network :
    ```shell
    docker network create bw-docker
    ```

    Once the network is created, you can now create the docker socket proxy container :
    ```shell
    docker run -d \
           --name bw-docker \
           --network bw-docker \
           -v /var/run/docker.sock:/var/run/docker.sock:ro \
           -e CONTAINERS=1 \
           tecnativa/docker-socket-proxy
    ```

    You can then create the scheduler container with the bw-data volume and the docker socket proxy network :
    ```shell
    docker run -d \
           --name bw-scheduler \
           --network bw-universe \
           -v bw-data:/data \
           -e DOCKER_HOST=tcp://bw-docker:2375 \
           bunkerity/bunkerweb-scheduler:1.4.6 && \
    docker network connect bw-docker bw-scheduler
    ```

    We can finally create the web UI container :
    ```shell
    docker run -d \
           --name bw-ui \
           --network bw-universe \
           -v bw-data:/data \
           -e DOCKER_HOST=tcp://bw-docker:2375 \
           -e ADMIN_USERNAME=admin \
           -e ADMIN_PASSWORD=changeme \
           -e ABSOLUTE_URI=http(s)://bwadm.example.com/changeme/ \
           bunkerity/bunkerweb-ui:1.4.6 && \
    docker network connect bw-docker bw-ui
    ```

    Important things to note :

    * `http(s)://bwadmin.example.com/changeme/` is the full base URL of the web UI (must match the sub(domain) and /changeme URL used when creating the BunkerWeb container)
    * Replace the username `admin` and password `changeme` with strong ones

    Here is the docker-compose equivalent :
    ```yaml
    version: "3"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.4.6
        ports:
          - "80:8080"
          - "443:8443"
        environment:
          - SERVER_NAME=bwadm.example.com
          - MULTISITE=yes
          - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
          - bwadm.example.com_USE_UI=yes
          - bwadm.example.com_USE_REVERSE_PROXY=yes
          - bwadm.example.com_REVERSE_PROXY_URL=/changeme/
          - bwadm.example.com_REVERSE_PROXY_HOST=http://bw-ui:7000
          - bwadm.example.com_REVERSE_PROXY_HEADERS=X-Script-Name /changeme
          - bwadm.example.com_REVERSE_PROXY_INTERCEPT_ERRORS=no
        labels:
          - "bunkerweb.INSTANCE"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.4.6
        volumes:
          - bw-data:/data
        environment:
          - DOCKER_HOST=tcp://bw-docker:2375
        networks:
          - bw-universe
          - bw-docker

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.4.6
        volumes:
          - bw-data:/data
        environment:
          - DOCKER_HOST=tcp://bw-docker:2375
          - ADMIN_USERNAME=admin
          - ADMIN_PASSWORD=changeme
          - ABSOLUTE_URI=http(s)://bwadm.example.com/changeme/
        networks:
          - bw-docker
          - bw-universe

      bw-docker:
        image: tecnativa/docker-socket-proxy
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          - CONTAINERS=1
        networks:
          - bw-docker

    volumes:
      bw-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
      bw-docker:
    ```

=== "Docker autoconf"

    When using the [Docker autoconf integration](/1.4/integrations/#docker-autoconf), we recommend you to connect the Autoconf and web UI containers using a dedicated network like with the scheduler and use another dedicated network for the communications between BunkerWeb and your web applications. The web UI can be deployed using a dedicated container based on the [bunkerweb-ui image](https://hub.docker.com/r/bunkerity/bunkerweb-ui).

    Let's start by creating the networks (replace 10.20.30.0/24 with an unused network of your choice) :
    ```shell
    docker network create --subnet 10.20.30.0/24 bw-universe && \
    docker network create bw-services
    ```

    You will also need the data volume, which where BunkerWeb's data will be stored :
    ```shell
    docker volume create bw-data
    ```

    You can now create the BunkerWeb container, please note the special `bunkerweb.INSTANCE` label which is mandatory for the scheduler as well as the web UI to work properly :
    ```shell
    docker run -d \
       --name bunkerweb \
       --network bw-universe \
       -p 80:8080 \
       -p 443:8443 \
       -e SERVER_NAME= \
       -e MULTISITE=yes \
       -e "API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24" \
       -l bunkerweb.INSTANCE \
       bunkerity/bunkerweb:1.4.6
    ```

    Important things to note :

    * replace `10.20.30.0/24` with the same network address used for the `bw-universe` network
    * the `bunkerweb.INSTANCE` label is mandatory

    The Autoconf and web UI will need to access the Docker API in order to get metadata about the running containers. It can be done easily by mounting the **docker.sock** file into the container. But there is a security risk : if the web UI is exploited, all your container(s) and the host will be impacted because, at the moment, Docker doesn't provide any restriction feature. We highly recommend using something like a [docker socket proxy](https://github.com/Tecnativa/docker-socket-proxy) to mitigate that risk (only a subset of read-only API endpoints will be available to the web UI container).

    To connect the docker socket proxy and the web UI, you will need another network :
    ```shell
    docker network create bw-docker
    ```

    Once the network is created, you can now create the docker socket proxy container :
    ```shell
    docker run -d \
           --name bw-docker \
           --network bw-docker \
           -v /var/run/docker.sock:/var/run/docker.sock:ro \
           -e CONTAINERS=1 \
           tecnativa/docker-socket-proxy
    ```

    You can then create the autoconf container connected to the docker socket proxy network :
    ```shell
    docker run -d \
           --name bw-autoconf \
           --network bw-universe \
           -v bw-data:/data \
           -e DOCKER_HOST=tcp://bw-docker:2375 \
           bunkerity/bunkerweb-autoconf:1.4.6 && \
    docker network connect bw-docker bw-autoconf
    ```

    You can then create the scheduler container with the bw-data volume and the docker socket proxy network :
    ```shell
    docker run -d \
           --name bw-scheduler \
           --network bw-universe \
           -v bw-data:/data \
           -e DOCKER_HOST=tcp://bw-docker:2375 \
           bunkerity/bunkerweb-scheduler:1.4.6 && \
    docker network connect bw-docker bw-scheduler
    ```

    We can finally create the web UI container :
    ```shell
    docker run -d \
           --name bw-ui \
           --network bw-universe \
           -v bw-data:/data \
           -e DOCKER_HOST=tcp://bw-docker:2375 \
           -e ADMIN_USERNAME=admin \
           -e ADMIN_PASSWORD=changeme \
           -e ABSOLUTE_URI=http(s)://bwadm.example.com/changeme/ \
           -l "bunkerweb.SERVER_NAME=bwadm.example.com" \
           -l "bunkerweb.USE_UI=yes" \
           -l "bunkerweb.USE_REVERSE_PROXY=yes" \
           -l "bunkerweb.REVERSE_PROXY_URL=/changeme" \
           -l "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000" \
           -l "bunkerweb.REVERSE_PROXY_HEADERS=X-Script-Name /changeme" \
           -l "bunkerweb.INTERCEPTED_ERROR_CODES=400 401 404 405 413 429 500 501 502 503 504" \
           bunkerity/bunkerweb-ui:1.4.6 && \
    docker network connect bw-docker bw-ui
    ```

    Important things to note :

    * `bwadm.example.com` is the dedicated (sub)domain for accessing the web UI
    * replace the `/changeme` URL with a custom one of your choice
    * `http(s)://bwadmin.example.com/changeme/` is the full base URL of the web UI (must match the sub(domain) and /changeme URL used when creating the BunkerWeb container)
    * Replace the username `admin` and password `changeme` with strong ones

    Here is the docker-compose equivalent :
    ```yaml
    version: "3.5"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.4.6
        ports:
          - 80:8080
          - 443:8443
        labels:
          - "bunkerweb.INSTANCE"
        environment:
          - SERVER_NAME=
          - MULTISITE=yes
          - API_WHITELIST_IP=127.0.0.0/8 10.20.30.0/24
          - AUTOCONF_MODE=yes
        networks:
          - bw-universe
          - bw-services

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.4.6
        volumes:
          - bw-data:/data
        environment:
          - DOCKER_HOST=tcp://bw-docker:2375
        networks:
          - bw-universe
          - bw-docker

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.4.6
        volumes:
          - bw-data:/data
        environment:
          - DOCKER_HOST=tcp://bw-docker:2375
          - AUTOCONF_MODE=yes
        networks:
          - bw-universe
          - bw-docker

      bw-docker:
        image: tecnativa/docker-socket-proxy
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          - CONTAINERS=1
        networks:
          - bw-docker
          
      bw-ui:
        image: bunkerity/bunkerweb-ui:1.4.6
        networks:
          bw-docker:
          bw-universe:
            aliases:
              - bw-ui
        volumes:
          - bw-data:/data
        environment:
          - DOCKER_HOST=tcp://bw-docker:2375
          - AUTOCONF_MODE=yes
          - ADMIN_USERNAME=admin
          - ADMIN_PASSWORD=changeme
          - ABSOLUTE_URI=http://bwadm.example.com/changeme/
        labels:
          - "bunkerweb.SERVER_NAME=bwadm.example.com"
          - "bunkerweb.USE_UI=yes"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme"
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
          - "bunkerweb.REVERSE_PROXY_HEADERS=X-Script-Name /changeme"
          - "bunkerweb.INTERCEPTED_ERROR_CODES=400 401 404 405 413 429 500 501 502 503 504"

    volumes:
      bw-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-docker:
        name: bw-docker

    ```

=== "Swarm"

=== "Kubernetes"

=== "Linux"

    The installation of the web UI using the [Linux integration](/1.4/integrations/#linux) is pretty straightforward because it is installed with BunkerWeb.

    The first thing to do is to edit the BunkerWeb configuration located at **/etc/bunkerweb/variables.env** to add settings related to the web UI :
    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    ...
    SERVER_NAME=bwadm.example.com
    MULTISITE=yes
    USE_API=yes
    API_WHITELIST_IP=127.0.0.0/8
    bwadm.example.com_USE_UI=yes
    bwadm.example.com_USE_REVERSE_PROXY=yes
    bwadm.example.com_REVERSE_PROXY_URL=/changeme/
    bwadm.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:7000
    bwadm.example.com_REVERSE_PROXY_HEADERS=X-Script-Name /changeme
    bwadm.example.com_REVERSE_PROXY_INTERCEPT_ERRORS=no
    ...
    ```

    Important things to note :

    * `bwadm.example.com` is the dedicated (sub)domain for accessing the web UI
    * replace the `/changeme` URLs with a custom one of your choice

    Once the configuration file is edited, you will need to restart BunkerWeb :
    ```shell
    systemctl restart bunkerweb
    ```

    You can edit the **/etc/bunkerweb/ui.env** file containing the settings of the web UI :
    ```conf
    ADMIN_USERNAME=admin
    ADMIN_PASSWORD=changeme
    ABSOLUTE_URI=http(s)://bwadm.example.com/changeme/
    ```

    Important things to note :

    * `http(s)://bwadmin.example.com/changeme/` is the full base URL of the web UI (must match the sub(domain) and /changeme URL used in **/etc/bunkerweb/variables.env**)
    * replace the username `admin` and password `changeme` with strong ones

    Restart the BunkerWeb UI service and you are now ready to access it :
	```shell
	systemctl restart bunkerweb-ui
	```

=== "Ansible"

    The installation of the web UI using the [Ansible integration](/1.4/integrations/#ansible) is pretty straightforward because it is already installed with BunkerWeb, the variable `enable_ui` can be set to `true` in order to activate the web UI service and the variable `custom_ui` can be used to specify the configuration file for the web UI.

    The first thing to do is to edit your local BunkerWeb configuration and add settings related to the web UI :
    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    ...
    SERVER_NAME=bwadm.example.com
    MULTISITE=yes
    USE_API=yes
    API_WHITELIST_IP=127.0.0.0/8
    bwadm.example.com_USE_UI=yes
    bwadm.example.com_USE_REVERSE_PROXY=yes
    bwadm.example.com_REVERSE_PROXY_URL=/changeme/
    bwadm.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:7000
    bwadm.example.com_REVERSE_PROXY_HEADERS=X-Script-Name /changeme
    bwadm.example.com_REVERSE_PROXY_INTERCEPT_ERRORS=no
    ...
    ```

    Important things to note :

    * `bwadm.example.com` is the dedicated (sub)domain for accessing the web UI
    * replace the `/changeme` URLs with a custom one of your choice

	You can now create a local `my_ui.env` file containing the settings of the web UI :
	```env
	ADMIN_USERNAME=admin
	ADMIN_PASSWORD=changeme
	ABSOLUTE_URI=http(s)://bwadm.example.com/changeme/
	```

    Important things to note :

    * `http(s)://bwadmin.example.com/changeme/` is the full base URL of the web UI (must match the sub(domain) and /changeme URL used when creating the BunkerWeb container)
    * Replace the username `admin` and password `changeme` with strong ones

	In your Ansible inventory, you can use the `enable_ui` variable to enable the web UI service and the `custom_ui`variable to specify the configuration file for the web UI :
	```yaml
	[mybunkers]
	192.168.0.42 variables_env="{{ playbook_dir }}/my_variables.env" enable_ui=true custom_ui="{{ playbook_dir }}/my_ui.env"
	```

	Or alternatively, in your playbook file :
	```yaml
	- hosts: all
	  become: true
	  vars:
		- variables_env: "{{ playbook_dir }}/my_variables.env"
		- enable_ui: true
		- custom_ui: "{{ playbook_dir }}/my_ui.env"
	  roles:
		- bunkerity.bunkerweb
	```

    You can now run the playbook and be able to access the web UI :
    ```shell
    ansible-playbook -i inventory.yml playbook.yml
    ```

=== "Vagrant"

    The installation of the web UI using the [Vagrant integration](/1.4/integrations/#vagrant) is pretty straightforward because it is installed with BunkerWeb.

    The first thing to do is to edit the BunkerWeb configuration located at **/etc/bunkerweb/variables.env** to add settings related to the web UI :
    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=8.8.8.8 8.8.4.4
    ...
    SERVER_NAME=bwadm.example.com
    MULTISITE=yes
    USE_API=yes
    API_WHITELIST_IP=127.0.0.0/8
    bwadm.example.com_USE_UI=yes
    bwadm.example.com_USE_REVERSE_PROXY=yes
    bwadm.example.com_REVERSE_PROXY_URL=/changeme/
    bwadm.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:7000
    bwadm.example.com_REVERSE_PROXY_HEADERS=X-Script-Name /changeme
    bwadm.example.com_REVERSE_PROXY_INTERCEPT_ERRORS=no
    ...
    ```

    Important things to note :

    * `bwadm.example.com` is the dedicated (sub)domain for accessing the web UI
    * replace the `/changeme` URLs with a custom one of your choice

    Once the configuration file is edited, you will need to restart BunkerWeb :
    ```shell
    systemctl restart bunkerweb
    ```

    You can edit the **/etc/bunkerweb/ui.env** file containing the settings of the web UI :
    ```conf
    ADMIN_USERNAME=admin
    ADMIN_PASSWORD=changeme
    ABSOLUTE_URI=http(s)://bwadm.example.com/changeme/
    ```

    Important things to note :

    * `http(s)://bwadmin.example.com/changeme/` is the full base URL of the web UI (must match the sub(domain) and /changeme URL used in **/etc/bunkerweb/variables.env**)
    * replace the username `admin` and password `changeme` with strong ones

    Restart the BunkerWeb UI service and you are now ready to access it :
	```shell
	systemctl restart bunkerweb-ui
	```