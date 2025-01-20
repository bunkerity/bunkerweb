# Quickstart guide

!!! info "Prerequisites"

    We assume that you're already familiar with the [core concepts](concepts.md) and you have followed the [integrations instructions](integrations.md) for your environment.

!!! tip "Going further"

	To demonstrate the use of BunkerWeb, we will deploy a basic stack using the setup wizard as an example. See the [examples folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.0-rc2/examples) of the repository to get real-world examples.

Protecting existing web applications already accessible with the HTTP(S) protocol is the main goal of BunkerWeb : it will act as a classical [reverse proxy](https://en.wikipedia.org/wiki/Reverse_proxy) with extra security features.

## Basic setup

=== "Docker"

    When using Docker integration, the easiest way of protecting an existing application is to add the web service in the `bw-services` network and then configure them in the web interface :

    ```yaml
    x-bw-env: &bw-env
      # We use an anchor to avoid repeating the same settings for both services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        # This is the name that will be used to identify the instance in the Scheduler
        image: bunkerity/bunkerweb:1.6.0-rc2
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        environment:
          <<: *bw-env # We use the anchor to avoid repeating the same settings for all services
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc2
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: ""
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # Change it if needed
        volumes:
          - bw-data:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.0-rc2
        environment:
          <<: *bw-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-db:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

    volumes:
      bw-data:
      bw-db:


    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker autoconf"

    We will assume that you already have the [Docker autoconf integration](integrations.md#docker-autoconf) stack running on your machine.

    🧙🪄 If you want an example using the web interface, you can follow the [Autoconf Wizard](web-ui.md#__tabbed_1_2) documentation (this is an optional step).

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_1_2) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    🧙🪄 If you want an example using the web interface, you can follow the [Swarm Wizard](web-ui.md#__tabbed_1_3) documentation (this is an optional step).

    We will assume that you already have the [Swarm integration](integrations.md#swarm) stack running on your cluster and connected to a network called `bw-services` so you can connect your existing application and configure BunkerWeb with labels (as explained in the [Creating a new service](#__tabbed_2_3) section).

=== "Kubernetes"

    We will assume that you already have the [Kubernetes integration](integrations.md#kubernetes) stack running on your cluster.

    🧙🪄 If you want an example using the web interface, you can follow the [Kubernetes Wizard](web-ui.md#__tabbed_1_4) documentation (this is an optional step).

=== "Linux"

    We will assume that you already have the [Linux integration](integrations.md#linux) stack running on your machine.

    🧙🪄 If you don't want to use the setup wizard, you will need to run the following command `export UI_WIZARD=no` before installing BunkerWeb as described in [integrations section](integrations.md#linux) of the documentation (this is an optional step).

    Let's check the status of BunkerWeb :

    ```shell
    systemctl status bunkerweb
    ```

    Now let's check the status of the Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    If they are already running, we can reload them :

    ```shell
    systemctl reload bunkerweb bunkerweb-scheduler
    ```

    Otherwise, we will need to start them :

    ```shell
    systemctl start bunkerweb bunkerweb-scheduler
    ```

## Accessing the setup wizard

!!! tip "Accessing the setup wizard"

    You can access the setup wizard by browsing the `https://your-ip-address/setup` URI of your server.

If you didn't run the setup wizard, you can ignore this step.

### Create an Administrator account

You should see a setup page just like this one :
<figure markdown>
  ![Setup Wizard landing page](assets/img/ui-wizard-step1.png){ align=center }
  <figcaption>Setup Wizard landing page</figcaption>
</figure>

Once you're on the setup page, you can enter the **administrator username, email, and password** and click on the "Next" button.

### Configure the Reverse Proxy and HTTPS

The next step will ask you to enter the **server name** that the web UI will use. You can also choose to enable **Let's Encrypt** or use a **custom certificate**.

<figure markdown>
  ![Setup Wizard step 2](assets/img/ui-wizard-step2.png){ align=center }
  <figcaption>Setup Wizard step 2</figcaption>
</figure>

### Overview of your settings

The last step will give you an overview of the settings you've entered. You can click on the "Setup" button to complete the setup.

<figure markdown>
  ![Setup Wizard final step](assets/img/ui-wizard-step3.png){ align=center }
  <figcaption>Setup Wizard final step</figcaption>
</figure>


## Accessing the web interface

You can now access the web interface by browsing to the domain you configured in the previous step and the URI if you changed it (default is `https://your-domain/`).

<figure markdown>
  ![Web interface login page](assets/img/ui-login.png){ align=center }
  <figcaption>Web interface login page</figcaption>
</figure>

You can now log in with the administrator account you created during the setup wizard.

<figure markdown>
  ![Web interface home](assets/img/ui-home.png){ align=center }
  <figcaption>Web interface home</figcaption>
</figure>

## Creating a new service

=== "Web UI"

    You can create a new service by navigating to the `Services` section of the web interface and clicking on the `➕ Create new service` button.

    Their are multiple ways of creating a service using the web interface :

    * The **Easy mode** will guide you through the process of creating a new service.
    * The **Advanced mode** will allow you to configure the service with more options.
    * The **Raw mode** will allow you to enter the configuration directly like editing the `variables.env` file.

    !!! tip "Draft service"

        You can create a draft service to save your progress and come back to it later. Just click on the `🌐 Online` button to toggle the service to draft mode.

    === "Easy mode"

        In this mode, you can choose among the available templates and fill in the required fields.

        <figure markdown>
          ![Web interface create service easy](assets/img/ui-create-service-easy.png){ align=center }
          <figcaption>Web interface create service easy</figcaption>
        </figure>

        * To navigate between the different plugins, you can use the dropdown menu on the top left corner of the page.
        * Once you've selected the template, you can fill in the required fields and follow the instructions to create the service.
        * Once you're done configuring the service, you can click on the `💾 Save` button to save the configuration.

    === "Advanced mode"

        In this mode, you can configure the service with more options while seeing all the available settings from all the different plugins.

        <figure markdown>
          ![Web interface create service advanced](assets/img/ui-create-service-advanced.png){ align=center }
          <figcaption>Web interface create service advanced</figcaption>
        </figure>

        * To navigate between the different plugins, you can use the dropdown menu on the top left corner of the page.
        * Each setting has a small piece of information that will help you understand what it does.
        * Once you're done configuring the service, you can click on the `💾 Save` button to save the configuration.

    === "Raw mode"

        In this mode, you can enter the configuration directly like editing the `variables.env` file.

        <figure markdown>
          ![Web interface create service RAW](assets/img/ui-create-service-raw.png){ align=center }
          <figcaption>Web interface create service RAW</figcaption>
        </figure>

        * Once you're done configuring the service, you can click on the `💾 Save` button to save the configuration.

    🚀 Once you've saved the configuration, you should see your new service in the list of services.

    <figure markdown>
      ![Web interface services page](assets/img/ui-services.png){ align=center }
      <figcaption>Web interface services page</figcaption>
    </figure>

    If you wish to edit the service, you can click on the service name or the `📝 Edit` button.

=== "Docker"

    We will assume that you followed the [Basic setup](#__tabbed_1_1) and you have the Docker integration running on your machine.

    You must then have a network called `bw-services` so you can connect your existing application and configure BunkerWeb:

    ```yaml
    services:
      myapp:
    	  image: nginxdemos/nginx-hello
    	  networks:
    	    - bw-services

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

    After that, you can create manually add the service in the docker compose file that you created in the previous step.

    ```yaml
    ...

    services:
      ...
      bw-scheduler:
        ...
        environment:
          ...
          SERVER_NAME: "www.example.com" # When using the Docker integration, you can set the configuration directly in the scheduler, make sure to set the correct domain name
          MULTISITE: "yes" # Enable multisite mode so you can add multiple services
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/"
          www.example.com_REVERSE_PROXY_HOST: "http://myapp:8080"
          ...
    ```

    You can then restart the `bw-scheduler` service to apply the changes.

    ```shell
    docker compose down bw-scheduler && docker compose up -d bw-scheduler
    ```

=== "Docker autoconf labels"

    We will assume that you followed the [Basic setup](#__tabbed_1_2) and you have the Docker autoconf integration running on your machine.

    You must then have a network called `bw-services` so you can connect your existing application and configure BunkerWeb with labels :

    ```yaml
    services:
      myapp:
    	  image: nginxdemos/nginx-hello
    	  networks:
    	    - bw-services
    	  labels:
    	    - "bunkerweb.SERVER_NAME=www.example.com"
    	    - "bunkerweb.USE_REVERSE_PROXY=yes"
    	    - "bunkerweb.REVERSE_PROXY_URL=/"
    	    - "bunkerweb.REVERSE_PROXY_HOST=http://myapp:8080"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

    Doing so will automatically create a new service with the provided labels as configuration.

=== "Swarm labels"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_2_2) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    We will assume that you followed the [Basic setup](#__tabbed_1_3) and you have the Swarm stack running on your cluster and connected to a network called `bw-services` so you can connect your existing application and configure BunkerWeb with labels :

    ```yaml
    services:
      myapp:
        image: nginxdemos/nginx-hello
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/"
          - "bunkerweb.REVERSE_PROXY_HOST=http://myapp:8080"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes annotations"

    We will assume that you followed the [Basic setup](#__tabbed_1_4) and you have the Kubernetes stack running on your cluster.

    Let's assume that you have a typical Deployment with a Service to access the web application from within the cluster :

    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app
      labels:
    	app: app
    spec:
      replicas: 1
      selector:
    	matchLabels:
    	  app: app
      template:
    	metadata:
    	  labels:
    		app: app
    	spec:
    	  containers:
    	  - name: app
    		image: nginxdemos/nginx-hello
    		ports:
    		- containerPort: 8080
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app
    spec:
      selector:
    	app: app
      ports:
    	- protocol: TCP
    	  port: 80
    	  targetPort: 8080
    ```

    Here is the corresponding Ingress definition to serve and protect the web application :

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      annotations:
        bunkerweb.io/DUMMY_SETTING: "value"
    spec:
      rules:
        - host: www.example.com
          http:
            paths:
              - path: /
                pathType: Prefix
                backend:
                  service:
                  name: svc-app
                  port:
                    number: 80
    ```

=== "Linux variables.env file"

    We will assume that you followed the [Basic setup](#__tabbed_1_5) and you have the Linux integration running on your machine.

    You can create a new service by editing the `variables.env` file located in the `/etc/bunkerweb/` directory.

    ```shell
    nano /etc/bunkerweb/variables.env
    ```

    You can then add the following configuration :

    ```shell
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/
    www.example.com_REVERSE_PROXY_HOST=http://myapp:8080
    ```

    You can then reload the `bunkerweb-scheduler` service to apply the changes.

    ```shell
    systemctl reload bunkerweb-scheduler
    ```
