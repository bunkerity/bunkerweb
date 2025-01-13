# Advanced usage

BunkerWeb offers many security features that you can configure with [settings](settings.md). Even if the default values of settings ensure a minimal "security by default", we strongly recommend you tune them. By doing so you will be able to ensure the security level of your choice but also manage false positives.

!!! tip "Other settings"
    This section only focuses on advanced usages, see the [settings section](settings.md) of the documentation to see all the available settings.

!!! tip "Testing"
    To perform quick tests when multisite mode is enabled (and if you don't have the proper DNS entries set up for the domains) you can use curl with the HTTP Host header of your choice :
    ```shell
    curl -H "Host: app1.example.com" http://ip-or-fqdn-of-server
    ```

    If you are using HTTPS, you will need to play with SNI :
    ```shell
    curl -H "Host: app1.example.com" --resolve example.com:443:ip-of-server https://example.com
    ```

## Behind load balancer or reverse proxy

!!! info "Real IP"

    When BunkerWeb is itself behind a load balancer or a reverse proxy, you need to configure it so it can get the real IP address of the clients. **If you don't, the security features will block the IP address of the load balancer or reverse proxy instead of the client's one**.

BunkerWeb actually supports two methods to retrieve the real IP address of the client :

- Using the `PROXY protocol`
- Using a HTTP header like `X-Forwarded-For`

The following settings can be used :

- `USE_REAL_IP` : enable/disable real IP retrieval
- `USE_PROXY_PROTOCOL` : enable/disable PROXY protocol support.
- `REAL_IP_FROM` : list of trusted IP/network address allowed to send us the "real IP"
- `REAL_IP_HEADER` : the HTTP header containing the real IP or special value `proxy_protocol` when using PROXY protocol

You will find more settings about real IP in the [settings section](settings.md#real-ip) of the documentation.

=== "HTTP header"

    We will assume the following regarding the load balancers or reverse proxies (you will need to update the settings depending on your configuration) :

    - They use the `X-Forwarded-For` header to set the real IP
    - They have IPs in the `1.2.3.0/24` and `100.64.0.0/10` networks

    === "Docker"

        When starting the **Scheduler** container, you will need to add the settings :

        ```yaml
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

    === "Docker autoconf"

        Before running the [Docker autoconf integration](integrations.md#docker-autoconf) stack, you will need to add the settings for the **Scheduler** container :

        ```yaml
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

    === "Swarm"

        !!! warning "Deprecated"
            The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_2_2) instead.

            **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

        Before running the [Swarm integration](integrations.md#swarm) stack, you will need to add the settings for the **Scheduler** service :

        ```yaml
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

    === "Kubernetes"

        You will need to add the settings to the environment variables of the Scheduler container (doing it using the ingress is not supported because you will get into trouble when using things like Let's Encrypt) :

        ```yaml
        apiVersion: apps/v1
        kind: DaemonSet
        metadata:
          name: bunkerweb-scheduler
        spec:
            ...
            spec:
              containers:
                - name: bunkerweb-scheduler
                  ...
                  env:
                    - name: USE_REAL_IP
                      value: "yes"
                    - name: REAL_IP_FROM
                      value: "1.2.3.0/24 100.64.0.0/10"
                    - name: REAL_IP_HEADER
                      value: "X-Forwarded-For"
        ...
        ```

    === "Linux"

        You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

        ```conf
        ...
        USE_REAL_IP=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=X-Forwarded-For
        ...
        ```

        Please note that it's recommended to issue a restart instead of reload when configuring settings related to proxy protocols :

        ```shell
        systemctl restart bunkerweb bunkerweb-scheduler
        ```

=== "Proxy protocol"

    !!! warning "Read carefully"

        Only use the PROXY protocol if you are sure that your load balancer or reverse proxy is sending it. **If you enable it and it's not used, you will get errors**.

    We will assume the following regarding the load balancers or reverse proxies (you will need to update the settings depending on your configuration) :

    - They use the `PROXY protocol` v1 or v2 to set the real IP
    - They have IPs in the `1.2.3.0/24` and `100.64.0.0/10` networks

    === "Docker"

        When starting the **Scheduler** container, you will need to add the settings :

        ```yaml
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

    === "Docker autoconf"

        Before running the [Docker autoconf integration](integrations.md#docker-autoconf) stack, you will need to add the settings for the **Scheduler** container :

        ```yaml
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

    === "Swarm"

        !!! warning "Deprecated"
            The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_3_2) instead.

            **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

        Before running the [Swarm integration](integrations.md#swarm) stack, you will need to add the settings for the **Scheduler** service :

        ```yaml
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

    === "Kubernetes"

        You will need to add the settings to the environment variables of the **Scheduler** containers (doing it using the ingress is not supported because you will get into trouble when using things like Let's Encrypt) :

        ```yaml
        apiVersion: apps/v1
        kind: DaemonSet
        metadata:
          name: bunkerweb-scheduler
        spec:
            ...
            spec:
              containers:
                - name: bunkerweb-scheduler
                  ...
                  env:
                    - name: USE_REAL_IP
                      value: "yes"
                    - name: USE_PROXY_PROTOCOL
                      value: "yes"
                    - name: REAL_IP_FROM
                      value: "1.2.3.0/24 100.64.0.0/10"
                    - name: REAL_IP_HEADER
                      value: "proxy_protocol"
        ...
        ```

    === "Linux"

        You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

        ```conf
        ...
        USE_REAL_IP=yes
        USE_PROXY_PROTOCOL=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=proxy_protocol
        ...
        ```

        Please note that it's recommended to issue a restart instead of reload when configuring settings related to proxy protocols :

        ```shell
        systemctl restart bunkerweb bunkerweb-scheduler
        ```

## Protect UDP/TCP applications

!!! example "Experimental feature"

	This feature is not production-ready. Feel free to test it and report us any bug using [issues](https://github.com/bunkerity/bunkerweb/issues) in the GitHub repository.

BunkerWeb offers the capability to function as a **generic UDP/TCP reverse proxy**, allowing you to protect any network-based applications operating at least on layer 4 of the OSI model. Instead of utilizing the "classical" HTTP module, BunkerWeb leverages the [stream module](https://nginx.org/en/docs/stream/ngx_stream_core_module.html) of NGINX.

It's important to note that **not all settings and security features are available when using the stream module**. Additional information on this can be found in the [settings](settings.md) sections of the documentation.

Configuring a basic reverse proxy is quite similar to the HTTP setup, as it involves using the same settings: `USE_REVERSE_PROXY=yes` and `REVERSE_PROXY_HOST=myapp:4242`. Even when BunkerWeb is positioned behind a Load Balancer, the settings remain the same (with **PROXY protocol** being the supported option due to evident reasons).

On top of that, the following specific settings are used :

- `SERVER_TYPE=stream` : activate `stream` mode (generic UDP/TCP) instead of `http` one (which is the default)
- `LISTEN_STREAM_PORT=4242` : the listening "plain" (without SSL/TLS) port that BunkerWeb will listen on
- `LISTEN_STREAM_PORT_SSL=4343` : the listening "ssl/tls" port that BunkerWeb will listen on
- `USE_UDP=no` : listen for and forward UDP packets instead of TCP

For complete list of settings regarding `stream` mode, please refer to the [settings](settings.md) section of the documentation.

=== "Docker"

    When using Docker integration, the easiest way of protecting existing network applications is to add the services in the `bw-services` network :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc1
        ports:
          - "80:8080" # Keep it if you want to use Let's Encrypt automation
          - "10000:10000" # app1
          - "20000:20000" # app2
        labels:
          - "bunkerweb.INSTANCE=yes"
        environment:
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
        volumes:
          - bw-data:/data
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          USE_REVERSE_PROXY: "yes" # Will be applied to all services
          SERVER_TYPE: "stream" # Will be applied to all services
          app1.example.com_REVERSE_PROXY_HOST: "myapp1:9000"
          app1.example.com_LISTEN_STREAM_PORT: "10000"
          app2.example.com_REVERSE_PROXY_HOST: "myapp2:9000"
          app2.example.com_LISTEN_STREAM_PORT: "20000"
        restart: "unless-stopped"
        networks:
          - bw-universe

      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services

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
    ```

=== "Docker autoconf"

    Before running the [Docker autoconf integration](integrations.md#docker-autoconf) stack on your machine, you will need to edit the ports and the Scheduler environment variables :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc1
        ports:
          - "80:8080" # Keep it if you want to use Let's Encrypt automation
          - "10000:10000" # app1
          - "20000:20000" # app2
      ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
        ...
        environment:
          SERVER_TYPE: "stream"
    ...
    ```

    Once the stack is running, you can connect your existing applications to the `bw-services` network and configure BunkerWeb with labels :

    ```yaml
    services:
      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        labels:
          - "bunkerweb.SERVER_NAME=app1.example.com"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        labels:
          - "bunkerweb.SERVER_NAME=app2.example.com"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_4_2) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    Before running the [Swarm integration](integrations.md#swarm) stack on your machine, you will need to edit the ports and the Scheduler environment variables :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc1
        ports:
          # Keep it if you want to use Let's Encrypt automation
          - published: 80
            target: 8080
            mode: host
            protocol: tcp
          # app1
          - published: 10000
            target: 10000
            mode: host
            protocol: tcp
          # app2
          - published: 10000
            target: 10000
            mode: host
            protocol: tcp
      ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
        ...
        environment:
          SERVER_TYPE: "stream"
    ...
    ```

    Once the stack is running, you can connect your existing applications to the `bw-services` network and configure BunkerWeb with labels :

    ```yaml
    services:

      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    Protection TCP/UDP applications using the `stream` feature is not yet supported when using the [Kubernetes integration](integrations.md#kubernetes).

=== "Linux"

    You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

    ```conf
    ...
    SERVER_NAME=app1.example.com app2.example.com
    MULTISITE=yes
    USE_REVERSE_PROXY=yes
    SERVER_TYPE=stream
    app1.example.com_REVERSE_PROXY_HOST=myapp1.domain.or.ip:9000
    app1.example.com_LISTEN_STREAM_PORT=10000
    app2.example.com_REVERSE_PROXY_HOST=myapp2.domain.or.ip:9000
    app2.example.com_LISTEN_STREAM_PORT=20000
    ...
    ```

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

## Custom configurations

To customize and add custom configurations to BunkerWeb, you can take advantage of its NGINX foundation. Custom NGINX configurations can be added in different NGINX contexts, including configurations for the ModSecurity Web Application Firewall (WAF), which is a core component of BunkerWeb. More details about ModSecurity configurations can be found [here](security-tuning.md#modsecurity).

Here are the available types of custom configurations:

- **http**: Configurations at the HTTP level of NGINX.
- **server-http**: Configurations at the HTTP/Server level of NGINX.
- **default-server-http**: Configurations at the Server level of NGINX, specifically for the "default server" when the supplied client name doesn't match any server name in `SERVER_NAME`.
- **modsec-crs**: Configurations applied before the OWASP Core Rule Set is loaded.
- **modsec**: Configurations applied after the OWASP Core Rule Set is loaded, or used when the Core Rule Set is not loaded.
- **stream**: Configurations at the Stream level of NGINX.
- **server-stream**: Configurations at the Stream/Server level of NGINX.

Custom configurations can be applied globally or specifically for a particular server, depending on the applicable context and whether the [multisite mode](concepts.md#multisite-mode) is enabled.

The method for applying custom configurations depends on the integration being used. However, the underlying process involves adding files with the `.conf` suffix to specific folders. To apply a custom configuration for a specific server, the file should be placed in a subfolder named after the primary server name.

Some integrations provide more convenient ways to apply configurations, such as using [Configs](https://docs.docker.com/engine/swarm/configs/) in Docker Swarm or [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) in Kubernetes. These options offer simpler approaches for managing and applying configurations.

=== "Docker"

    When using the [Docker integration](integrations.md#docker), you have two choices for the addition of custom configurations :

    - Using specific settings `*_CUSTOM_CONF_*` as environment variables (recommended)
    - Writing .conf files to the volume mounted on /data of the scheduler

    **Using settings**

    The settings to use must follow the pattern `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` :

    - `<SITE>` : optional primary server name if multisite mode is enabled and the config must be applied to a specific service
    - `<TYPE>` : the type of config, accepted values are `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `STREAM` and `SERVER_STREAM`
    - `<NAME>` : the name of config without the .conf suffix

    Here is a dummy example using a docker-compose file :

    ```yaml
    ...
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
      environment:
        - |
          CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
              ngx.say('world')
    	      }
          }
      ...
    ```

    **Using files**

    The first thing to do is to create the folders :

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    You can now write your configurations :

    ```shell
    echo "location /hello {
    	default_type 'text/plain';
    	content_by_lua_block {
    		ngx.say('world')
    	}
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Because the scheduler runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    When starting the scheduler container, you will need to mount the folder on /data :

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Docker autoconf"

    When using the [Docker autoconf integration](integrations.md#docker-autoconf), you have two choices for adding custom configurations :

    - Using specific settings `*_CUSTOM_CONF_*` as labels (easiest)
    - Writing .conf files to the volume mounted on /data of the scheduler

    **Using labels**

    !!! warning "Limitations using labels"
        When using labels with the Docker autoconf integration, you can only apply custom configurations for the corresponding web service. Applying **http**, **default-server-http**, **stream** or any global configurations (like **server-http** or **server-stream** for all services) is not possible : you will need to mount files for that purpose.

    The labels to use must follow the pattern `bunkerweb.CUSTOM_CONF_<TYPE>_<NAME>` :

    - `<TYPE>` : the type of config, accepted values are `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS` and `SERVER_STREAM`
    - `<NAME>` : the name of config without the .conf suffix

    Here is a dummy example using a docker-compose file :

    ```yaml
    myapp:
      image: nginxdemos/nginx-hello
      labels:
        - |
          bunkerweb.CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
                ngx.say('world')
            }
    	    }
      ...
    ```

    **Using files**

    The first thing to do is to create the folders :

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    You can now write your configurations :

    ```shell
    echo "location /hello {
    	default_type 'text/plain';
    	content_by_lua_block {
    		ngx.say('world')
    	}
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Because the scheduler runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    When starting the scheduler container, you will need to mount the folder on /data :

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_5_2) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    When using the [Swarm integration](integrations.md#swarm), custom configurations are managed using [Docker Configs](https://docs.docker.com/engine/swarm/configs/).

    To keep it simple, you don't even need to attach the Config to a service : the autoconf service is listening for Config events and will update the custom configurations when needed.

    When creating a Config, you will need to add special labels :

    * **bunkerweb.CONFIG_TYPE** : must be set to a valid custom configuration type (http, server-http, default-server-http, modsec, modsec-crs, stream or server-stream)
    * **bunkerweb.CONFIG_SITE** : set to a server name to apply configuration to that specific server (optional, will be applied globally if unset)

    Here is the example :

    ```shell
    echo "location /hello {
    	default_type 'text/plain';
    	content_by_lua_block {
    		ngx.say('world')
    	}
    }" | docker config create -l bunkerweb.CONFIG_TYPE=server-http my-config -
    ```

    There is no update mechanism : the alternative is to remove an existing config using `docker config rm` and then recreate it.

=== "Kubernetes"

    When using the [Kubernetes integration](integrations.md#kubernetes), custom configurations are managed using [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/).

    To keep it simple, you don't even need to use the ConfigMap with a Pod (e.g. as environment variable or volume) : the autoconf Pod is listening for ConfigMap events and will update the custom configurations when needed.

    When creating a ConfigMap, you will need to add special labels :

    * **bunkerweb.io/CONFIG_TYPE** : must be set to a valid custom configuration type (http, server-http, default-server-http, modsec, modsec-crs, stream or server-stream)
    * **bunkerweb.io/CONFIG_SITE** : set to a server name to apply configuration to that specific server (optional, will be applied globally if unset)

    Here is the example :

    ```yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: cfg-bunkerweb-all-server-http
      annotations:
    	bunkerweb.io/CONFIG_TYPE: "server-http"
    data:
      myconf: |
    	location /hello {
    		default_type 'text/plain';
    		content_by_lua_block {
    			ngx.say('world')
    		}
    	}
    ```

=== "Linux"

    When using the [Linux integration](integrations.md#linux), custom configurations must be written to the /etc/bunkerweb/configs folder.

    Here is an example for server-http/hello-world.conf :

    ```conf
    location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }
    ```

    Because BunkerWeb runs as an unprivileged user (nginx:nginx), you will need to edit the permissions :

    ```shell
    chown -R root:nginx /etc/bunkerweb/configs && \
    chmod -R 770 /etc/bunkerweb/configs
    ```

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

## PHP

!!! example "Experimental feature"
	At the moment, PHP support with BunkerWeb is still in beta and we recommend you use a reverse-proxy architecture if you can. By the way, PHP is not supported at all for some integrations like Kubernetes.

BunkerWeb supports PHP using external or remote [PHP-FPM](https://www.php.net/manual/en/install.fpm.php) instances. We will assume that you are already familiar with managing that kind of services.

 The following settings can be used :

- `REMOTE_PHP` : Hostname of the remote PHP-FPM instance.
- `REMOTE_PHP_PATH` : Root folder containing files in the remote PHP-FPM instance.
- `REMOTE_PHP_PORT` : Port of the remote PHP-FPM instance (*default is 9000*).
- `LOCAL_PHP` : Path to the local socket file of PHP-FPM instance.
- `LOCAL_PHP_PATH` : Root folder containing files in the local PHP-FPM instance.

=== "Docker"

    When using the [Docker integration](integrations.md#docker), to support PHP applications, you will need to :

    - Mount your PHP files into the `/var/www/html` folder of BunkerWeb
    - Set up a PHP-FPM container for your application and mount the folder containing PHP files
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as environment variables when starting BunkerWeb

    If you enable the [multisite mode](concepts.md#multisite-mode), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    We will assume that your PHP apps are located into a folder named `www`. Please note that you will need to fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33 if you use the `php:fpm` image) is the owner of the files and folders :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    You can now run BunkerWeb, configure it for your PHP application and also run the PHP apps :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *bw-api-env
        volumes:
          - ./www:/var/www/html
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          REMOTE_PHP_PATH: "/app" # Will be applied to all services thanks to the MULTISITE setting
          app1.example.com_REMOTE_PHP: "myapp1"
          app2.example.com_REMOTE_PHP: "myapp2"
          app3.example.com_REMOTE_PHP: "myapp3"
        volumes:
          - bw-data:/data
        restart: "unless-stopped"
        networks:
          - bw-universe

      myapp1:
        image: php:fpm
        volumes:
          - ./www/app1.example.com:/app
        networks:
          - bw-services

      myapp2:
        image: php:fpm
        volumes:
          - ./www/app2.example.com:/app
        networks:
          - bw-services

      myapp3:
        image: php:fpm
        volumes:
          - ./www/app3.example.com:/app
        networks:
          - bw-services

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
    ```

=== "Docker autoconf"

    !!! info "Multisite mode enabled"
        The [Docker autoconf integration](integrations.md#docker-autoconf) integration implies the use of multisite mode : protecting one PHP application is the same as protecting multiple ones.

    When using the [Docker autoconf integration](integrations.md#docker-autoconf), to support PHP applications, you will need to :

    - Mount your PHP files into the `/var/www/html` folder of BunkerWeb
    - Set up a PHP-FPM containers for your applications and mount the folder containing PHP apps
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as labels for your PHP-FPM container

    Since the Docker autoconf implies using the [multisite mode](concepts.md#multisite-mode), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    Once the folders are created, copy your files and fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33 if you use the `php:fpm` image) is the owner of the files and folders :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    When you start the BunkerWeb autoconf stack, mount the `www` folder into `/var/www/html` for the **Scheduler** container :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      AUTOCONF_MODE: "yes"
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc1
        labels:
          - "bunkerweb.INSTANCE=yes"
        environment:
          <<: *bw-api-env
        volumes:
          - ./www:/var/www/html
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
          SERVER_NAME: "" # The server name will be filled with services labels
          MULTISITE: "yes" # Mandatory setting for autoconf
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/data # This is used to persist data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.0-rc1
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          AUTOCONF_MODE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
          DOCKER_HOST: "tcp://bw-docker:2375" # The Docker socket
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        networks:
          - bw-docker

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-db:/var/lib/mysql
        networks:
          - bw-docker

    volumes:
      bw-data:
      bw-db:

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

    You can now create your PHP-FPM containers, mount the correct subfolders and use labels to configure BunkerWeb :

    ```yaml
    services:
      myapp1:
          image: php:fpm
          volumes:
            - ./www/app1.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp1
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.REMOTE_PHP=myapp1"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp2:
          image: php:fpm
          volumes:
            - ./www/app2.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp2
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.REMOTE_PHP=myapp2"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp3:
          image: php:fpm
          volumes:
            - ./www/app3.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp3
          labels:
            - "bunkerweb.SERVER_NAME=app3.example.com"
            - "bunkerweb.REMOTE_PHP=myapp3"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_6_2) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    !!! info "Multisite mode enabled"
        The [Swarm integration](integrations.md#docker-autoconf) integration implies the use of multisite mode : protecting one PHP application is the same as protecting multiple ones.

    !!! info "Shared volume"
        Using PHP with the Docker Swarm integration needs a shared volume between all BunkerWeb and PHP-FPM instances which is not covered in this documentation.

    When using the [Docker autoconf integration](integrations.md#docker-autoconf), to support PHP applications, you will need to :

    - Mount your PHP files into the `/var/www/html` folder of BunkerWeb
    - Set up a PHP-FPM containers for your applications and mount the folder containing PHP apps
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as labels for your PHP-FPM container

    Since the Swarm integration implies using the [multisite mode](concepts.md#multisite-mode), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    As an example, we will consider that you have a shared folder mounted on your worker nodes on the `/shared` endpoint.

    Once the folders are created, copy your files and fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33 if you use the `php:fpm` image) is the owner of the files and folders :

    ```shell
    chown -R 33:101 /shared/www && \
    find /shared/www -type f -exec chmod 0640 {} \; && \
    find /shared/www -type d -exec chmod 0750 {} \;
    ```

	  When you start the BunkerWeb stack, mount the `/shared/www` folder into `/var/www/html` for the **Scheduler** container :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-rc1
        volumes:
          - /shared/www:/var/www/html
    ...
    ```

    You can now create your PHP-FPM services, mount the correct subfolders and use labels to configure BunkerWeb :

    ```yaml
    services:
      myapp1:
          image: php:fpm
          volumes:
            - ./www/app1.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp1
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app1.example.com"
              - "bunkerweb.REMOTE_PHP=myapp1"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp2:
          image: php:fpm
          volumes:
            - ./www/app2.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp2
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app2.example.com"
              - "bunkerweb.REMOTE_PHP=myapp2"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp3:
          image: php:fpm
          volumes:
            - ./www/app3.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp3
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app3.example.com"
              - "bunkerweb.REMOTE_PHP=myapp3"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

	!!! warning "PHP is not supported for Kubernetes"
		Kubernetes integration allows configuration through [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) and the BunkerWeb controller only supports HTTP applications at the moment.

=== "Linux"

    We will assume that you already have the [Linux integration](integrations.md#linux) stack running on your machine.

    By default, BunkerWeb will search for web files inside the `/var/www/html` folder. You can use it to store your PHP applications. Please note that you will need to configure your PHP-FPM service to get or set the user/group of the running processes and the UNIX socket file used to communicate with BunkerWeb.

    First of all, you will need to make sure that your PHP-FPM instance can access the files inside the `/var/www/html` folder and also that BunkerWeb can access the UNIX socket file in order to communicate with PHP-FPM. We recommend to set a different user like `www-data` for the PHP-FPM service and to give the nginx group access to the UNIX socket file. Here is corresponding PHP-FPM configuration :

    ```ini
    ...
    [www]
    user = www-data
    group = www-data
    listen = /run/php/php-fpm.sock
    listen.owner = www-data
    listen.group = nginx
    listen.mode = 0660
    ...
    ```

    Don't forget to restart your PHP-FPM service :

    ```shell
    systemctl restart php-fpm
    ```

    If you enable the [multisite mode](concepts.md#multisite-mode), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    /var/www/html
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    Please note that you will need to fix the permissions so BunkerWeb (group `nginx`) can at least read files and list folders and PHP-FPM (user `www-data` but it might be different depending on your system) is the owner of the files and folders :

    ```shell
    chown -R www-data:nginx /var/www/html && \
    find /var/www/html -type f -exec chmod 0640 {} \; && \
    find /var/www/html -type d -exec chmod 0750 {} \;
    ```

    You can now edit the `/etc/bunkerweb/variable.env` file :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4
    API_LISTEN_IP=127.0.0.1
    MULTISITE=yes
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app1.example.com_LOCAL_PHP_PATH=/var/www/html/app1.example.com
    app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app2.example.com_LOCAL_PHP_PATH=/var/www/html/app2.example.com
    app3.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app3.example.com_LOCAL_PHP_PATH=/var/www/html/app3.example.com
    ```

    Let's check the status of BunkerWeb :

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

## IPv6

!!! warning "Experimental feature"

    This feature is not production-ready. Feel free to test it and report us any bug using [issues](https://github.com/bunkerity/bunkerweb/issues) in the GitHub repository.

By default, BunkerWeb will only listen on IPv4 addresses and won't use IPv6 for network communications. If you want to enable IPv6 support, you need to set `USE_IPV6=yes`. Please note that IPv6 configuration of your network and environment is out-of-the-scope of this documentation.

=== "Docker / Autoconf / Swarm"

    First of all, you will need to configure your Docker daemon to enable IPv6 support for containers and use ip6tables if needed. Here is sample configuration for your `/etc/docker/daemon.json` file :

    ```json
    {
      "experimental": true,
      "ipv6": true,
      "ip6tables": true,
      "fixed-cidr-v6": "fd00:dead:beef::/48"
    }
    ```

    You can now restart the Docker service to apply the changes :

    ```shell
    systemctl restart docker
    ```

    Once Docker is setup to support IPv6 you can add the `USE_IPV6` setting and configure the `bw-services` for IPv6 :

    ```yaml
    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
        environment:
          USE_IPv6: "yes"

    ...

    networks:
      bw-services:
        name: bw-services
        enable_ipv6: true
        ipam:
          config:
            - subnet: fd00:13:37::/48
              gateway: fd00:13:37::1

    ...
    ```

=== "Linux"

    You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

    ```conf
    ...
    USE_IPV6=yes
    ...
    ```

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

## HTTP protocol

### Deny status code

STREAM support :warning:

The first thing to define is the kind of action to do when a client access is denied. You can control the action with the `DENY_HTTP_STATUS` setting which allows the following values :

- `403` : send a "classical" Forbidden HTTP status code (a web page or custom content will be displayed)
- `444` : close the connection (no web page or custom content will be displayed)

The default value is `403` and we suggest you set it to `444` only if you already fixed a lot of false positive, you are familiar with BunkerWeb and want a higher level of security.

When using stream mode, value is ignored and always set to `444` with effect of closing the connection.

### Default server

STREAM support :x:

In the HTTP protocol, the Host header is used to determine which server the client wants to send the request to. That header is facultative and may be missing from the request or can be set as an unknown value. This is a common case, a lot of bots are scanning the Internet and are trying to exploit services or simply doing some fingerprinting.

You can disable any request containing undefined or unknown Host value by setting `DISABLE_DEFAULT_SERVER` to `yes` (default : `no`). Please note that clients won't even receive a response, the TCP connection will be closed (using the special 444 status code of NGINX).

If you want to close SSL/TLS connection if [Server Name Indication (SNI)](https://en.wikipedia.org/wiki/Server_Name_Indication) is undefined or unknown, you can set `DISABLE_DEFAULT_SERVER_STRICT_SNI` to `yes` (default : `no`). On the one hand, you can block attackers as soon as possible at SSL/TLS level but, in the other hand, you may have issues if your BunkerWeb instance is behind a reverse proxy configured to send HTTPS requests without SNI.

### Allowed methods

STREAM support :x:

You can control the allowed HTTP methods by listing them (separated with "|") in the `ALLOWED_METHODS` setting (default : `GET|POST|HEAD`). Clients sending a method which is not listed will get a "405 - Method Not Allowed".

!!! note Using POST

    If `POST` is required, then `OPTIONS` should also be specified to allow for the CORS pre-flight request.

### Max sizes

STREAM support :x:

You can control the maximum body size with the `MAX_CLIENT_SIZE` setting (default : `10m`). See [here](https://nginx.org/en/docs/syntax.html) for accepted values. You can use the special value `0` to allow a body of infinite size (not recommended).

### Serve files

STREAM support :x:

To disable serving files from the www folder, you can set `SERVE_FILES` to `no` (default : `yes`). The value `no` is recommended if you use BunkerWeb as a reverse proxy.

### Headers

STREAM support :x:

Headers are very important when it comes to HTTP security. While some of them might be too verbose, others' verbosity will need to be increased, especially on the client-side.

#### Remove headers

STREAM support :x:

You can automatically remove verbose headers in the HTTP responses by using the `REMOVE_HEADERS` setting (default : `Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version`).

#### Keep upstream headers

STREAM support :x:

You can use the `KEEP_UPSTREAM_HEADERS` setting to preserve specific headers from upstream servers, preventing BunkerWeb from overriding them in HTTP responses.

* By default, this setting includes `Content-Security-Policy`, `Permissions-Policy`, and `X-Frame-Options`.
* To retain all headers from the upstream server, use the special value `*`.

Headers to be preserved should be listed and separated by spaces.

#### Cookies

STREAM support :x:

When it comes to cookies security, we can use the following flags :

- **HttpOnly** : disable any access to the cookie from Javascript using document.cookie
- **SameSite** : policy when requests come from third-party websites
- **Secure** : only send cookies on HTTPS request

Cookie flags can be overridden with values of your choice by using the `COOKIE_FLAGS` setting (default : `* HttpOnly SameSite=Lax`). See [here](https://github.com/AirisX/nginx_cookie_flag_module) for accepted values.

The Secure flag can be automatically added if HTTPS is used by using the `COOKIE_AUTO_SECURE_FLAG` setting (default : `yes`). The value `no` is not recommended unless you know what you're doing.

#### Security headers

STREAM support :x:

Various security headers are available and most of them can be set using BunkerWeb settings. Here is the list of headers, the corresponding setting and default value :

|           Header            | Setting                     |                                                                                                                                                                                                                                                                                                                                                                    Default                                                                                                                                                                                                                                                                                                                                                                     |
| :-------------------------: | :-------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: |
|  `Content-Security-Policy`  | `CONTENT_SECURITY_POLICY`   |                                                                                                                                                                                                                                                                                                                                        `object-src 'none'; form-action 'self'; frame-ancestors 'self';`                                                                                                                                                                                                                                                                                                                                        |
| `Strict-Transport-Security` | `STRICT_TRANSPORT_SECURITY` |                                                                                                                                                                                                                                                                                                                                                 `max-age=31536000; includeSubDomains; preload`                                                                                                                                                                                                                                                                                                                                                 |
|      `Referrer-Policy`      | `REFERRER_POLICY`           |                                                                                                                                                                                                                                                                                                                                                       `strict-origin-when-cross-origin`                                                                                                                                                                                                                                                                                                                                                        |
|    `Permissions-Policy`     | `PERMISSIONS_POLICY`        | `accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), compute-pressure=(), display-capture=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), local-fonts=(), magnetometer=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), publickey-credentials-create=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), speaker-selection=(), storage-access=(), usb=(), web-share=(), window-management=(), xr-spatial-tracking=(), interest-cohort=()` |
|      `X-Frame-Options`      | `X_FRAME_OPTIONS`           |                                                                                                                                                                                                                                                                                                                                                                  `SAMEORIGIN`                                                                                                                                                                                                                                                                                                                                                                  |
|  `X-Content-Type-Options`   | `X_CONTENT_TYPE_OPTIONS`    |                                                                                                                                                                                                                                                                                                                                                                   `nosniff`                                                                                                                                                                                                                                                                                                                                                                    |
|  `X-DNS-Prefetch-Control`   | `X_DNS_PREFETCH_CONTROL`    |                                                                                                                                                                                                                                                                                                                                                                     `off`                                                                                                                                                                                                                                                                                                                                                                      |

#### CORS

STREAM support :x:

[Cross-Origin Resource Sharing (CORS)](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS) allows you to control how your service can be accessed from different origins. To enable CORS, ensure the `OPTIONS` HTTP method is included in the `ALLOWED_METHODS` setting (more details [here](#allowed-methods)). Below is a list of settings related to CORS:

| Setting                        | Default                                                                              | Context   | Multiple | Description                                                                            |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | -------- | -------------------------------------------------------------------------------------- |
| `USE_CORS`                     | `no`                                                                                 | multisite | no       | Use CORS                                                                               |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | no       | Allowed origins to make CORS requests : PCRE regex or * or self (for the same origin). |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | no       | Value of the Access-Control-Allow-Methods header.                                      |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | no       | Value of the Access-Control-Allow-Headers header.                                      |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | no       | Send the Access-Control-Allow-Credentials header.                                      |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | no       | Value of the Access-Control-Expose-Headers header.                                     |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | no       | Value for the Cross-Origin-Opener-Policy header.                                       |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | no       | Value for the Cross-Origin-Embedder-Policy header.                                     |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | no       | Value for the Cross-Origin-Resource-Policy header.                                     |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | no       | Value of the Access-Control-Max-Age header.                                            |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | no       | Deny request and don't send it to backend if Origin is not allowed.                    |

Here is some examples of possible values for `CORS_ALLOW_ORIGIN` setting :

- `*` will allow all origin
- `^https://www\.example\.com$` will allow `https://www.example.com`
- `^https://.+\.example.com$` will allow any origins when domain ends with `.example.com`
- `^https://(www\.example1\.com|www\.example2\.com)$` will allow both `https://www.example1.com` and `https://www.example2.com`
- `^https?://www\.example\.com$` will allow both `https://www.example.com` and `http://www.example.com`

Here are some links to help you set the correct values for the CORS settings :

* Cross-Origin-Opener-Policy: [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Opener-Policy)
* Cross-Origin-Embedder-Policy: [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Embedder-Policy)
* Cross-Origin-Resource-Policy: [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Resource-Policy)

## HTTPS / SSL/TLS

Besides the HTTPS / SSL/TLS configuration, the following settings related to HTTPS / SSL/TLS can be set :

|            Setting            |      Default      | Description                                                                                                  |
| :---------------------------: | :---------------: | :----------------------------------------------------------------------------------------------------------- |
|   `REDIRECT_HTTP_TO_HTTPS`    |       `no`        | When set to `yes`, will redirect every HTTP request to HTTPS even if BunkerWeb is not configured with HTTPS. |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` |       `yes`       | When set to `yes`, will redirect every HTTP request to HTTPS only if BunkerWeb is configured with HTTPS.     |
|        `SSL_PROTOCOLS`        | `TLSv1.2 TLSv1.3` | List of supported SSL/TLS protocols when SSL is enabled.                                                     |
|            `HTTP2`            |       `yes`       | When set to `yes`, will enable HTTP2 protocol support when using HTTPS.                                      |
|            `HTTP3`            |       `no`        | When set to `yes`, will enable HTTP3 protocol support when using HTTPS.                                      |
|     `HTTP3_ALT_SVC_PORT`      |       `443`       | HTTP3 alternate service port. This value will be used as part of the Alt-Svc header.                         |
|         `LISTEN_HTTP`         |       `yes`       | When set to `no`, BunkerWeb will not listen for HTTP requests. Useful if you want HTTPS only for example.    |

!!! example "About HTTP3"
    HTTP/3 is the next version of the HTTP protocol. It is based on Google's QUIC protocol which is a transport layer protocol that provides security and reliability features. HTTP/3 is designed to improve the performance of websites and web applications.

    **Remember that NGINX's support for HTTP/3 is still experimental and may not be suitable for all use cases.**

### Let's Encrypt

STREAM support :white_check_mark:

BunkerWeb comes with automatic Let's Encrypt certificate generation and renewal. This is the easiest way of getting HTTPS / SSL/TLS working out of the box for public-facing web applications. Please note that you will need to set up proper DNS A record(s) for each of your domains pointing to your public IP(s) where BunkerWeb is accessible.

Here is the list of related settings :

|              Setting               |         Default          | Description                                                                                                                                                                   |
| :--------------------------------: | :----------------------: | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|        `AUTO_LETS_ENCRYPT`         |           `no`           | When set to `yes`, HTTPS / SSL/TLS will be enabled with automatic certificate generation and renewal from Let's Encrypt.                                                      |
|        `EMAIL_LETS_ENCRYPT`        | `contact@{FIRST_SERVER}` | Email to use when generating certificates. Let's Encrypt will send notifications to that email like certificate expiration.                                                   |
|      `LETS_ENCRYPT_CHALLENGE`      |          `http`          | The challenge type to use for Let's Encrypt (http or dns).                                                                                                                    |
|    `LETS_ENCRYPT_DNS_PROVIDER`     |                          | The DNS provider to use for DNS challenges.                                                                                                                                   |
|   `LETS_ENCRYPT_DNS_PROPAGATION`   |        `default`         | The time to wait for DNS propagation in seconds for DNS challenges.                                                                                                           |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` |                          | Configuration item that will be added to the credentials.ini file for the DNS provider (e.g. 'cloudflare_api_token 123456') for DNS challenges.                               |
|    `USE_LETS_ENCRYPT_WILDCARD`     |           `no`           | Create wildcard certificates for all domains. This allows a single certificate to secure multiple subdomains. (Only available with DNS challenges)                            |
|     `USE_LETS_ENCRYPT_STAGING`     |           `no`           | Use the staging environment for Let’s Encrypt certificate generation. Useful when you are testing your deployments to avoid being rate limited in the production environment. |
|   `LETS_ENCRYPT_CLEAR_OLD_CERTS`   |           `no`           | Clear old certificates when renewing.                                                                                                                                         |

!!! info "Information and behavior"
    - The `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` setting is a multiple setting and can be used to set multiple items for the DNS provider. The items will be saved as a cache file and Certbot will read the credentials from it.

    - If no `LETS_ENCRYPT_DNS_PROPAGATION` setting is set, the provider's default propagation time will be used.

!!! warning "Wildcard certificates"
    Wildcard certificates are only available with DNS challenges. If you want to use them, you will need to set the `USE_LETS_ENCRYPT_WILDCARD` setting to `yes`.

**Available DNS Providers**

| Provider       | Description     | Mandatory Settings                                                                                           | Optional Settings                                                                                                                                                                                                                                                        | Link(s)                                                                               |
| -------------- | --------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| `cloudflare`   | Cloudflare      | `api_token`                                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)             |
| `digitalocean` | DigitalOcean    | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)           |
| `dnsimple`     | DNSimple        | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)               |
| `dnsmadeeasy`  | DNS Made Easy   | `api_key`<br>`secret_key`                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)            |
| `gehirn`       | Gehirn DNS      | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                 |
| `google`       | Google Cloud    | `project_id`<br>`private_key_id`<br>`private_key`<br>`client_email`<br>`client_id`<br>`client_x509_cert_url` | `type` (default: `service_account`)<br>`auth_uri` (default: `https://accounts.google.com/o/oauth2/auth`)<br>`token_uri` (default: `https://accounts.google.com/o/oauth2/token`)<br>`auth_provider_x509_cert_url` (default: `https://www.googleapis.com/oauth2/v1/certs`) | [Documentation](https://certbot-dns-google.readthedocs.io/en/stable/)                 |
| `linode`       | Linode          | `key`                                                                                                        | `version` (default: `4`)                                                                                                                                                                                                                                                 | [Documentation](https://certbot-dns-linode.readthedocs.io/en/stable/)                 |
| `luadns`       | LuaDNS          | `email`<br>`token`                                                                                           |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-luadns.readthedocs.io/en/stable/)                 |
| `nsone`        | NS1             | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-nsone.readthedocs.io/en/stable/)                  |
| `ovh`          | OVH             | `application_key`<br>`application_secret`<br>`consumer_key`                                                  | `endpoint` (default: `ovh-eu`)                                                                                                                                                                                                                                           | [Documentation](https://certbot-dns-ovh.readthedocs.io/en/stable/)                    |
| `rfc2136`      | RFC 2136        | `server`<br>`name`<br>`secret`                                                                               | `port` (default: `53`)<br>`algorithm` (default: `HMAC-SHA512`)<br>`sign_query` (default: `false`)                                                                                                                                                                        | [Documentation](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                |
| `route53`      | Amazon Route 53 | `access_key_id`<br>`secret_access_key`                                                                       |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-route53.readthedocs.io/en/stable/)                |
| `sakuracloud`  | Sakura Cloud    | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)            |
| `scaleway`     | Scaleway        | `application_token`                                                                                          |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst) |

Full Let's Encrypt automation using the `http` challenge is fully working with stream mode as long as you open the `80/tcp` port from the outside. Please note that you will need to use the `LISTEN_STREAM_PORT_SSL` setting in order to choose your listening SSL/TLS port.

### Custom certificate

STREAM support :white_check_mark:

If you want to use your own certificates, here is the list of related settings :

| Setting                | Default | Context   | Multiple | Description                                                                      |
| ---------------------- | ------- | --------- | -------- | -------------------------------------------------------------------------------- |
| `USE_CUSTOM_SSL`       | `no`    | multisite | no       | Use custom HTTPS / SSL/TLS certificate.                                          |
| `CUSTOM_SSL_CERT`      |         | multisite | no       | Full path of the certificate or bundle file (must be readable by the scheduler). |
| `CUSTOM_SSL_KEY`       |         | multisite | no       | Full path of the key file (must be readable by the scheduler).                   |
| `CUSTOM_SSL_CERT_DATA` |         | multisite | no       | Certificate data encoded in base64.                                              |
| `CUSTOM_SSL_KEY_DATA`  |         | multisite | no       | Key data encoded in base64.                                                      |

When `USE_CUSTOM_SSL` is set to `yes`, BunkerWeb will check every day if the custom certificate specified in `CUSTOM_SSL_CERT` is modified and will reload NGINX if that's the case.

When using stream mode, you will need to use the `LISTEN_STREAM_PORT_SSL` setting in order to choose your listening SSL/TLS port.

### Self-signed

STREAM support :white_check_mark:

If you want to quickly test HTTPS / SSL/TLS for staging/dev environment you can configure BunkerWeb to generate self-signed certificates, here is the list of related settings :

|          Setting           |        Default         | Description                                                                                                                          |
| :------------------------: | :--------------------: | :----------------------------------------------------------------------------------------------------------------------------------- |
| `GENERATE_SELF_SIGNED_SSL` |          `no`          | When set to `yes`, HTTPS / SSL/TLS will be enabled with automatic self-signed certificate generation and renewal from Let's Encrypt. |
|  `SELF_SIGNED_SSL_EXPIRY`  |         `365`          | Number of days for the certificate expiration (**-days** value used with **openssl**).                                               |
|   `SELF_SIGNED_SSL_SUBJ`   | `/CN=www.example.com/` | Certificate subject to use (**-subj** value used with **openssl**).                                                                  |

When using stream mode, you will need to use the `LISTEN_STREAM_PORT_SSL` setting in order to choose your listening SSL/TLS port.

## ModSecurity

STREAM support :x:

ModSecurity is integrated and enabled by default alongside the OWASP Core Rule Set within BunkerWeb. Here is the list of related settings :

| Setting                               | Default        | Description                                                                                                                                                        |
| ------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_MODSECURITY`                     | `yes`          | Enable ModSecurity WAF.                                                                                                                                            |
| `USE_MODSECURITY_CRS`                 | `yes`          | Enable OWASP Core Rule Set.                                                                                                                                        |
| `USE_MODSECURITY_CRS_PLUGINS`         | `yes`          | Enable OWASP Core Rule Set plugins.                                                                                                                                |
| `MODSECURITY_CRS_VERSION`             | `4`            | Version of the OWASP Core Rule Set to use with ModSecurity (3, 4 or nightly).                                                                                      |
| `MODSECURITY_CRS_PLUGIN_URLS`         |                | List of OWASP CRS plugins URLs (direct download to .zip or .tar file) to download and install (URLs are separated with space). (Not compatible with CRS version 3) |
| `MODSECURITY_SEC_AUDIT_ENGINE`        | `RelevantOnly` | SecAuditEngine directive of ModSecurity.                                                                                                                           |
| `MODSECURITY_SEC_RULE_ENGINE`         | `On`           | SecRuleEngine directive of ModSecurity.                                                                                                                            |
| `MODSECURITY_SEC_AUDIT_LOG_PARTS`     | `ABCFHZ`       | SecAuditLogParts directive of ModSecurity.                                                                                                                         |
| `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` | `131072`       | SecRequestBodyNoFilesLimit directive of ModSecurity.                                                                                                               |

!!! warning "ModSecurity and the OWASP Core Rule Set"
    **We strongly recommend keeping both ModSecurity and the OWASP Core Rule Set enabled**. The only downsides are the false positives that may occur. But they can be fixed with some efforts and the CRS team maintains a list of exclusions for common applications (e.g., WordPress, Nextcloud, Drupal, Cpanel, ...).

You can choose between the following versions of the OWASP Core Rule Set :

- **3** : The version [v3.3.7](https://github.com/coreruleset/coreruleset/releases/tag/v3.3.7) of the OWASP Core Rule Set
- **4** : The version [v4.10.0](https://github.com/coreruleset/coreruleset/releases/tag/v4.10.0) of the OWASP Core Rule Set (***default***)
- **nightly** : The latest [nightly](https://github.com/coreruleset/coreruleset/releases/tag/nightly) build of the OWASP Core Rule Set which is updated every day

!!! example "OWASP Core Rule Set's nightly build"
    The nightly build of the OWASP Core Rule Set is updated every day and contains the latest rules. It is recommended to use it in a staging environment before using it in production.

### Custom configurations

Tuning ModSecurity and the CRS can be done using [custom configurations](quickstart-guide.md#custom-configurations) :

- modsec-crs : before the OWASP Core Rule Set is loaded
- modsec : after the OWASP Core Rule Set is loaded (also used if CRS is not loaded)
- crs-plugins-before : before the CRS plugins are loaded
- crs-plugins-after : after the CRS plugins are loaded

For example, you can add a custom configuration with type `modsec-crs` to add CRS exclusions :

```conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"
```

You can also add a custom configuration with type `modsec` to update loaded CRS rules :

```conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"
```

!!! info "Order of execution"
    ModSecurity order of execution is as follows :

    1. *OWASP* CRS configuration
    2. Custom plugins configuration (`crs-plugins-before`)
    3. Custom plugins rules **before CRS rules** (`crs-plugins-before`)
    4. Downloaded plugins configuration
    5. Downloaded plugins rules **before CRS rules**
    6. Custom CRS rules (`modsec-crs`)
    6. *OWASP* CRS rules
    7. Custom plugins rules **after CRS rules** (`crs-plugins-after`)
    8. Downloaded plugins rules **after CRS rules**
    9. Custom rules (`modsec`)

!!! tip "OWASP Core Rule Set's plugins"
    The OWASP Core Rule Set plugins can be found [here](https://github.com/coreruleset/plugin-registry)

<!-- ## CrowdSec

STREAM support :x:

<figure markdown>
  ![Overview](assets/img/crowdsec.svg){ align=center, width="600" }
</figure>

This BunkerWeb plugin acts as a [CrowdSec](https://crowdsec.net/) bouncer. It will deny requests based on the decision of your CrowdSec API. Not only you will benefinit from the crowdsourced blacklist, you can also configure [scenarios](https://docs.crowdsec.net/docs/concepts#scenarios) to automatically ban IPs based on suspicious behaviors.

### Setup

=== "Docker"
    **Acquisition file**

    You will need to run CrowdSec instance and configure it to parse BunkerWeb logs. Because BunkerWeb is based on NGINX, you can use the `nginx` value for the `type` parameter in your acquisition file (assuming that BunkerWeb logs are stored "as is" without additional data) :

    ```yaml
    filenames:
       - /var/log/bunkerweb.log
    labels:
        type: nginx
    ```

    **Syslog**

    For container-based integrations, we recommend you to redirect the logs of the BunkerWeb container to a syslog service that will store the logs so CrowdSec can access it easily. Here is an example configuration for syslog-ng that will store raw logs coming from BunkerWeb to a local `/var/log/bunkerweb.log` file :

    ```syslog
    @version: 4.7

    source s_net {
        udp(
            ip("0.0.0.0")
        );
    };

    template t_imp {
        template("$MSG\n");
        template_escape(no);
    };

    destination d_file {
        file("/var/log/bunkerweb.log" template(t_imp));
    };

    log {
        source(s_net);
        destination(d_file);
    };
    ```

    **Optional : Application Security Component**

    CrowdSec also provides an [Application Security Component](https://docs.crowdsec.net/docs/appsec/intro) that can be used to protect your application from attacks. You can configure the plugin to send requests to the AppSec Component for further analysis. If you want to use it, you will need to create another acquisition file for the AppSec Component :

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
        type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    **Docker Compose**

    Here is the docker-compose boilerplate that you can use (**don't forget to edit the bouncer key**) :

    ```yaml
    services:
        bunkerweb:
            image: bunkerity/bunkerweb:1.6.0-rc1
            ports:
              - "80:8080"
              - "443:8443"
            environment:
                API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
            restart: "unless-stopped"
            networks:
              - bw-universe
              - bw-services
              - bw-plugins
            logging:
                driver: syslog
                options:
                    syslog-address: "udp://10.10.10.254:514"

        bw-scheduler:
            image: bunkerity/bunkerweb-scheduler:1.6.0-rc1
            depends_on:
              - bunkerweb
            environment:
                BUNKERWEB_INSTANCES: "bunkerweb"
                SERVER_NAME: "www.example.com"
                API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
                USE_CROWDSEC: "yes"
                CROWDSEC_API: "http://crowdsec:8080" # This is the API URL of the CrowdSec instance
                CROWDSEC_APPSEC_URL: "http://crowdsec:7422" # This is the AppSec Component URL of the CrowdSec instance, comment if you don't want to use it
                CROWDSEC_API_KEY: "s3cr3tb0unc3rk3y" # This is the API key of the Bouncer, we recommend have a more complex key
            restart: "unless-stopped"
            networks:
              - bw-universe

        crowdsec:
            image: crowdsecurity/crowdsec:v1.6.2
            volumes:
              - cs-data:/var/lib/crowdsec/data
              - ./acquis.yaml:/etc/crowdsec/acquis.yaml # This is the acquisition file for CrowdSec created above
              - ./appsec.yaml:/etc/crowdsec/acquis.d/appsec.yaml # Comment if you don't want to use the AppSec Component
              - bw-logs:/var/log:ro
            environment:
                BOUNCER_KEY_bunkerweb: "s3cr3tb0unc3rk3y" # This is the API key of the Bouncer, we recommend have a more complex key (it must match the one configured)
                COLLECTIONS: "crowdsecurity/nginx crowdsecurity/appsec-virtual-patching crowdsecurity/appsec-generic-rules"
                #   COLLECTIONS: "crowdsecurity/nginx" # If you don't want to use the AppSec Component use this line instead
            networks:
              - bw-plugins

        syslog:
            image: balabit/syslog-ng:4.7.1 # For x86_64 architecture
            # image: lscr.io/linuxserver/syslog-ng:4.7.1-r1-ls116 # For aarch64 architecture
            volumes:
              - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # This is the syslog-ng configuration file created above
              - bw-logs:/var/log
            networks:
                bw-plugins:
                    ipv4_address: 10.10.10.254

    networks:
        bw-services:
            name: bw-services
        bw-universe:
            name: bw-universe
            ipam:
            driver: default
            config:
                - subnet: 10.20.30.0/24
        bw-plugins:
            ipam:
            driver: default
            config:
                - subnet: 10.10.10.0/24

    volumes:
        bw-data:
        bw-logs:
        cs-data:
    ```

=== "Linux"

    You'll need to install CrowdSec and configure it to parse BunkerWeb logs. To do so, you can follow the [official documentation](https://doc.crowdsec.net/docs/getting_started/install_crowdsec).

    For CrowdSec to parse BunkerWeb logs, you have to add the following lines to your acquisition file located in `/etc/crowdsec/acquis.yaml` :

    ```yaml
    filenames:
      - /var/log/bunkerweb/access.log
      - /var/log/bunkerweb/error.log
      - /var/log/bunkerweb/modsec_audit.log
    labels:
        type: nginx
    ```

    Now we have to add our custom bouncer to the CrowdSec API. To do so, you can use the `cscli` tool :

    ```shell
    sudo cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6
    ```

    !!! warning "API key"
        Keep the key generated by the `cscli` command, you will need it later.

    Now restart the CrowdSec service :

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Optional : Application Security Component with Linux**

    If you want to use the AppSec Component, you will need to create another acquisition file for it located in `/etc/crowdsec/acquis.d/appsec.yaml` :

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
        type: appsec
    listen_addr: 127.0.0.1:7422
    source: appsec
    ```

    And you will need to install the AppSec Component's collections :

    ```shell
    sudo cscli collections install crowdsecurity/appsec-virtual-patching
    sudo cscli collections install crowdsecurity/appsec-generic-rules
    ```

    Now you just have to restart the CrowdSec service :

    ```shell
    sudo systemctl restart crowdsec
    ```

    If you need more information about the AppSec Component, you can refer to the [official documentation](https://docs.crowdsec.net/docs/appsec/intro).

    **Settings**

    Now you can configure the plugin by adding the following settings to your BunkerWeb configuration file :

    ```env
    USE_CROWDSEC=yes
    CROWDSEC_API=http://127.0.0.1:8080
    CROWDSEC_API_KEY=<The key provided by cscli>
    CROWDSEC_APPSEC_URL=http://127.0.0.1:7422 # Comment if you don't want to use the AppSec Component
    ```

    And finally reload the BunkerWeb service :

    ```shell
    sudo systemctl reload bunkerweb
    ``` -->

## Bad behavior

STREAM support :white_check_mark:

When attackers search for and/or exploit vulnerabilities they might generate some "suspicious" HTTP status codes that a "regular" user won’t generate within a period of time. If we detect that kind of behavior we can ban the offending IP address and force the attacker to come up with a new one.

That kind of security measure is implemented and enabled by default in BunkerWeb and is called "Bad behavior". Here is the list of the related settings :

|           Setting           |            Default            | Description                                                                  |
| :-------------------------: | :---------------------------: | :--------------------------------------------------------------------------- |
|     `USE_BAD_BEHAVIOR`      |             `yes`             | When set to `yes`, the Bad behavior feature will be enabled.                 |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | List of HTTP status codes considered as "suspicious".                        |
|  `BAD_BEHAVIOR_THRESHOLD`   |             `10`              | Maximum number of "suspicious" HTTP status codes within the time period.     |
|  `BAD_BEHAVIOR_COUNT_TIME`  |             `60`              | Period of time during which we count "suspicious" HTTP status codes.         |
|   `BAD_BEHAVIOR_BAN_TIME`   |            `86400`            | The duration time (in seconds) of a ban when a client reached the threshold. |

In other words, with the default values, if a client generates more than `10` status codes from the list `400 401 403 404 405 429 444` within `60` seconds their IP address will be banned for `86400` seconds.

When using stream mode, only the `444` status code will count as "bad".

## Antibot

STREAM support :x:

Attackers often use automated tools to exploit vulnerabilities in web applications. A common countermeasure is to challenge users to determine whether they are bots. If the challenge is successfully completed, the client is deemed "legitimate" and granted access to the web application.

BunkerWeb includes a built-in "Antibot" feature to implement this type of security, though it is not enabled by default. Below are the supported challenge mechanisms:

- **Cookie**: Sends a cookie to the client and expects it to be returned on subsequent requests.
- **JavaScript**: Requires the client to solve a computational challenge using JavaScript.
- **Captcha**: Presents a traditional CAPTCHA challenge (no external dependencies).
- **hCaptcha**: Challenges the client with a CAPTCHA provided by hCaptcha.
- **reCAPTCHA**: Uses Google reCAPTCHA to ensure the client achieves a minimum score.
- **Turnstile**: Enforces rate limiting and access control using Cloudflare Turnstile, leveraging various mechanisms.

Here is the list of related settings :

| Setting                     | Default      | Context   | Multiple | Description                                                                                                                    |
| --------------------------- | ------------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `USE_ANTIBOT`               | `no`         | multisite | no       | Activate antibot feature.                                                                                                      |
| `ANTIBOT_URI`               | `/challenge` | multisite | no       | Unused URI that clients will be redirected to to solve the challenge.                                                          |
| `ANTIBOT_TIME_RESOLVE`      | `60`         | multisite | no       | Maximum time (in seconds) clients have to resolve the challenge. Once this time has passed, a new challenge will be generated. |
| `ANTIBOT_TIME_VALID`        | `86400`      | multisite | no       | Maximum validity time of solved challenges. Once this time has passed, clients will need to resolve a new one.                 |
| `ANTIBOT_RECAPTCHA_SCORE`   | `0.7`        | multisite | no       | Minimum score required for reCAPTCHA challenge (Only compatible with reCAPTCHA v3).                                            |
| `ANTIBOT_RECAPTCHA_SITEKEY` |              | multisite | no       | Sitekey for reCAPTCHA challenge.                                                                                               |
| `ANTIBOT_RECAPTCHA_SECRET`  |              | multisite | no       | Secret for reCAPTCHA challenge.                                                                                                |
| `ANTIBOT_HCAPTCHA_SITEKEY`  |              | multisite | no       | Sitekey for hCaptcha challenge.                                                                                                |
| `ANTIBOT_HCAPTCHA_SECRET`   |              | multisite | no       | Secret for hCaptcha challenge.                                                                                                 |
| `ANTIBOT_TURNSTILE_SITEKEY` |              | multisite | no       | Sitekey for Turnstile challenge.                                                                                               |
| `ANTIBOT_TURNSTILE_SECRET`  |              | multisite | no       | Secret for Turnstile challenge.                                                                                                |

Please note that antibot feature is using a cookie to maintain a session with clients. If you are using BunkerWeb in a clustered environment, you will need to set the `SESSIONS_SECRET` and `SESSIONS_NAME` settings to another value than the default one (which is `random`). You will find more info about sessions [here](settings.md#sessions).

## Blacklisting, whitelisting and greylisting

The security features for blacklisting, whitelisting, and greylisting are straightforward to understand:

- **Blacklisting**: If a specific criterion is met, the client will be blocked.
- **Whitelisting**: If a specific criterion is met, the client will be allowed, bypassing all additional security checks.
- **Greylisting**: If a specific criterion is met, the client will be allowed but subjected to additional security checks else the client will be blocked.

These mechanisms can be configured simultaneously. If all three are enabled and a client meets criteria for multiple lists, **whitelisting takes precedence**, followed by blacklisting, and finally greylisting. In such cases, a whitelisted client will bypass both blacklisting and greylisting, regardless of overlapping criteria.

### Blacklisting

STREAM support :warning:

You can use the following settings to set up blacklisting :

| Setting                            | Default                                                                                                                        | Context   | Description                                                                                                                                                                       |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BLACKLIST`                    | `yes`                                                                                                                          | multisite | Activate blacklist feature.                                                                                                                                                       |
| `BLACKLIST_IP`                     |                                                                                                                                | multisite | List of IP/network, separated with spaces, to block.                                                                                                                              |
| `BLACKLIST_RDNS`                   | `.shodan.io .censys.io`                                                                                                        | multisite | List of reverse DNS suffixes, separated with spaces, to block.                                                                                                                    |
| `BLACKLIST_RDNS_GLOBAL`            | `yes`                                                                                                                          | multisite | Only perform RDNS blacklist checks on global IP addresses.                                                                                                                        |
| `BLACKLIST_ASN`                    |                                                                                                                                | multisite | List of ASN numbers, separated with spaces, to block.                                                                                                                             |
| `BLACKLIST_USER_AGENT`             |                                                                                                                                | multisite | List of User-Agent (PCRE regex), separated with spaces, to block.                                                                                                                 |
| `BLACKLIST_URI`                    |                                                                                                                                | multisite | List of URI (PCRE regex), separated with spaces, to block.                                                                                                                        |
| `BLACKLIST_IGNORE_IP`              |                                                                                                                                | multisite | List of IP/network, separated with spaces, to ignore in the blacklist.                                                                                                            |
| `BLACKLIST_IGNORE_RDNS`            |                                                                                                                                | multisite | List of reverse DNS suffixes, separated with spaces, to ignore in the blacklist.                                                                                                  |
| `BLACKLIST_IGNORE_ASN`             |                                                                                                                                | multisite | List of ASN numbers, separated with spaces, to ignore in the blacklist.                                                                                                           |
| `BLACKLIST_IGNORE_USER_AGENT`      |                                                                                                                                | multisite | List of User-Agent (PCRE regex), separated with spaces, to ignore in the blacklist.                                                                                               |
| `BLACKLIST_IGNORE_URI`             |                                                                                                                                | multisite | List of URI (PCRE regex), separated with spaces, to ignore in the blacklist.                                                                                                      |
| `BLACKLIST_IP_URLS`                | `https://www.dan.me.uk/torlist/?exit`                                                                                          | multisite | List of URLs, separated with spaces, containing bad IP/network to block. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                         |
| `BLACKLIST_RDNS_URLS`              |                                                                                                                                | multisite | List of URLs, separated with spaces, containing reverse DNS suffixes to block. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                   |
| `BLACKLIST_ASN_URLS`               |                                                                                                                                | multisite | List of URLs, separated with spaces, containing ASN to block. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                                    |
| `BLACKLIST_USER_AGENT_URLS`        | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` | multisite | List of URLs, separated with spaces, containing bad User-Agent to block. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                         |
| `BLACKLIST_URI_URLS`               |                                                                                                                                | multisite | List of URLs, separated with spaces, containing bad URI to block. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                                |
| `BLACKLIST_IGNORE_IP_URLS`         |                                                                                                                                | multisite | List of URLs, separated with spaces, containing IP/network to ignore in the blacklist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.           |
| `BLACKLIST_IGNORE_RDNS_URLS`       |                                                                                                                                | multisite | List of URLs, separated with spaces, containing reverse DNS suffixes to ignore in the blacklist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme. |
| `BLACKLIST_IGNORE_ASN_URLS`        |                                                                                                                                | multisite | List of URLs, separated with spaces, containing ASN to ignore in the blacklist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                  |
| `BLACKLIST_IGNORE_USER_AGENT_URLS` |                                                                                                                                | multisite | List of URLs, separated with spaces, containing User-Agent to ignore in the blacklist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.           |
| `BLACKLIST_IGNORE_URI_URLS`        |                                                                                                                                | multisite | List of URLs, separated with spaces, containing URI to ignore in the blacklist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                  |

!!! info "stream mode"
    When using stream mode, only IP, RDNS and ASN checks will be done.

!!! tip "Ignore lists"
    The ignore lists are useful when you want to block a specific criterion but want to exclude some IPs, RDNS, ASN, User-Agent, or URI from the blacklist.

### Greylisting

STREAM support :warning:

You can use the following settings to set up greylisting :

| Setting                    | Default | Context   | Description                                                                                                                                                                     |
| -------------------------- | ------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GREYLIST`             | `no`    | multisite | Activate greylist feature.                                                                                                                                                      |
| `GREYLIST_IP`              |         | multisite | List of IP/network, separated with spaces, to put into the greylist.                                                                                                            |
| `GREYLIST_RDNS`            |         | multisite | List of reverse DNS suffixes, separated with spaces, to put into the greylist.                                                                                                  |
| `GREYLIST_RDNS_GLOBAL`     | `yes`   | multisite | Only perform RDNS greylist checks on global IP addresses.                                                                                                                       |
| `GREYLIST_ASN`             |         | multisite | List of ASN numbers, separated with spaces, to put into the greylist.                                                                                                           |
| `GREYLIST_USER_AGENT`      |         | multisite | List of User-Agent (PCRE regex), separated with spaces, to put into the greylist.                                                                                               |
| `GREYLIST_URI`             |         | multisite | List of URI (PCRE regex), separated with spaces, to put into the greylist.                                                                                                      |
| `GREYLIST_IP_URLS`         |         | multisite | List of URLs, separated with spaces, containing good IP/network to put into the greylist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.      |
| `GREYLIST_RDNS_URLS`       |         | multisite | List of URLs, separated with spaces, containing reverse DNS suffixes to put into the greylist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme. |
| `GREYLIST_ASN_URLS`        |         | multisite | List of URLs, separated with spaces, containing ASN to put into the greylist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                  |
| `GREYLIST_USER_AGENT_URLS` |         | multisite | List of URLs, separated with spaces, containing good User-Agent to put into the greylist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.      |
| `GREYLIST_URI_URLS`        |         | multisite | List of URLs, separated with spaces, containing bad URI to put into the greylist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.              |

!!! info "stream mode"
    When using stream mode, only IP, RDNS and ASN checks will be done.

### Whitelisting

STREAM support :warning:

You can use the following settings to set up whitelisting :

| Setting                     | Default                                                                                                                                                                      | Context   | Multiple | Description                                                                                                                                                         |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_WHITELIST`             | `yes`                                                                                                                                                                        | multisite | no       | Activate whitelist feature.                                                                                                                                         |
| `WHITELIST_IP`              | ``                                                                                                                                                                           | multisite | no       | List of IP/network, separated with spaces, to put into the whitelist.                                                                                               |
| `WHITELIST_RDNS`            | `.google.com .googlebot.com .yandex.ru .yandex.net .yandex.com .search.msn.com .baidu.com .baidu.jp .crawl.yahoo.net .fwd.linkedin.com .twitter.com .twttr.com .discord.com` | multisite | no       | List of reverse DNS suffixes, separated with spaces, to whitelist.                                                                                                  |
| `WHITELIST_RDNS_GLOBAL`     | `yes`                                                                                                                                                                        | multisite | no       | Only perform RDNS whitelist checks on global IP addresses.                                                                                                          |
| `WHITELIST_ASN`             | `32934`                                                                                                                                                                      | multisite | no       | List of ASN numbers, separated with spaces, to whitelist.                                                                                                           |
| `WHITELIST_USER_AGENT`      |                                                                                                                                                                              | multisite | no       | List of User-Agent (PCRE regex), separated with spaces, to whitelist.                                                                                               |
| `WHITELIST_URI`             |                                                                                                                                                                              | multisite | no       | List of URI (PCRE regex), separated with spaces, to whitelist.                                                                                                      |
| `WHITELIST_IP_URLS`         |                                                                                                                                                                              | multisite | no       | List of URLs, separated with spaces, containing good IP/network to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.      |
| `WHITELIST_RDNS_URLS`       |                                                                                                                                                                              | multisite | no       | List of URLs, separated with spaces, containing reverse DNS suffixes to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme. |
| `WHITELIST_ASN_URLS`        |                                                                                                                                                                              | multisite | no       | List of URLs, separated with spaces, containing ASN to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                  |
| `WHITELIST_USER_AGENT_URLS` |                                                                                                                                                                              | multisite | no       | List of URLs, separated with spaces, containing good User-Agent to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.      |
| `WHITELIST_URI_URLS`        |                                                                                                                                                                              | multisite | no       | List of URLs, separated with spaces, containing bad URI to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.              |

!!! info "stream mode"
    When using stream mode, only IP, RDNS and ASN checks will be done.

## Reverse scan

STREAM support :white_check_mark:

The reverse scan feature is designed to identify open ports by attempting to establish TCP connections with clients' IP addresses. This is particularly useful for detecting potential open proxies or connections originating from servers.

By default, we provide a list of suspicious ports, which you can customize to suit your specific needs. However, keep in mind that adding too many ports to the list may slow down client connections due to the additional network checks. If an open port from the list is detected, the client's access will be denied.

Here is the list of settings related to reverse scan :

|        Setting         |          Default           | Description                                               |
| :--------------------: | :------------------------: | :-------------------------------------------------------- |
|   `USE_REVERSE_SCAN`   |            `no`            | When set to `yes`, will enable ReverseScan.               |
|  `REVERSE_SCAN_PORTS`  | `22 80 443 3128 8000 8080` | List of suspicious ports to scan.                         |
| `REVERSE_SCAN_TIMEOUT` |           `500`            | Specify the maximum timeout (in ms) when scanning a port. |

## BunkerNet

STREAM support :white_check_mark:

**BunkerNet** is a global, crowdsourced database of malicious requests, collaboratively shared among all BunkerWeb instances worldwide.

When you enable BunkerNet, malicious requests detected by your instance are sent to a remote server, where they are analyzed by our advanced systems. This process allows us to aggregate and extract malicious patterns from reports across all participating instances. The resulting insights are then redistributed to bolster the security of every BunkerWeb instance connected to BunkerNet.

Beyond the enhanced security that comes from leveraging this collective intelligence, enabling BunkerNet unlocks additional features, such as seamless integration with the **CrowdSec Console**, providing further tools to monitor and manage threats effectively.

The setting used to enable or disable BunkerNet is `USE_BUNKERNET` (default : `yes`).

### CrowdSec Console integration

If you're not already familiar with it, [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) is an open-source cybersecurity solution that leverages crowdsourced intelligence to combat cyber threats. Think of it as the "Waze of cybersecurity"—when one server is attacked, other systems worldwide are alerted and protected from the same attackers. You can learn more about it [here](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

Through our partnership with CrowdSec, you can enroll your BunkerWeb instances into your [CrowdSec Console](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration). This means that attacks blocked by BunkerWeb will be visible in your CrowdSec Console alongside attacks blocked by CrowdSec Security Engines, giving you a unified view of threats.

Importantly, CrowdSec does not need to be installed for this integration (though we highly recommend trying it out with the [CrowdSec plugin for BunkerWeb](https://github.com/bunkerity/bunkerweb-plugins/tree/main/crowdsec) to further enhance the security of your web services). Additionally, you can enroll your CrowdSec Security Engines into the same Console account for even greater synergy.

**Step #1 : create your CrowdSec Console account**

Go to the [CrowdSec Console](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration) and register your account if you don't already have one. Once it's done, write down your enroll key by going to "Security Engines", then "Engines" and click on "Add Security Engine" :

<figure markdown>
  ![Overview](assets/img/crowdity1.png){ align=center }
  <figcaption>Get your Crowdsec Console enroll key</figcaption>
</figure>

**Step #2 : get your BunkerNet ID**

Activating the BunkerNet feature (which is the case by default) is mandatory if you want to enroll your BunkerWeb instance(s) into your CrowdSec console. You can do it by setting `USE_BUNKERNET` to `yes`.

Get your BunkerNet ID on Docker :

```shell
docker exec my-bw-scheduler cat /var/cache/bunkerweb/bunkernet/instance.id
```

Get your BunkerNet ID on Linux :

```shell
cat /var/cache/bunkerweb/bunkernet/instance.id
```

**Step #3 : enroll your instance using the Panel**

Once you have noted your BunkerNet ID and CrowdSec Console enroll key, you can [order the free product "BunkerNet / CrowdSec" on the Panel](https://panel.bunkerweb.io/order/bunkernet/11?utm_campaign=self&utm_source=doc). Please note that you will need to create an account if you don't already have one.

You can now select the "BunkerNet / CrowdSec" service and fill out the form by pasting your BunkerNet ID and CrowdSec Console enroll key :

<figure markdown>
  ![Overview](assets/img/crowdity2.png){ align=center }
  <figcaption>Enroll your BunkerWeb instance into the CrowdSec Console</figcaption>
</figure>

**Step #4 : accept new security engine on the Console**

Last but not least, you need to go back to your CrowdSec Console and accept the new Security Engine :

<figure markdown>
  ![Overview](assets/img/crowdity3.png){ align=center }
  <figcaption>Accept enroll into the CrowdSec Console</figcaption>
</figure>

**Congratulations, your BunkerWeb instance is now enrolled into your CrowdSec Console !**

Pro tip : when viewing your alerts, click on "columns" and tick the "context" checkbox to get access to BunkerWeb specific data.

<figure markdown>
  ![Overview](assets/img/crowdity4.png){ align=center }
  <figcaption>BunkerWeb data shown in the context column</figcaption>
</figure>

## DNSBL

STREAM support :white_check_mark:

**DNSBL** (Domain Name System Blacklist) is an external database of malicious IP addresses that can be queried using the DNS protocol. BunkerWeb supports automatic querying of such blacklists, providing an additional layer of security.

When a client connects, BunkerWeb can query the DNSBL server of your choice. If the server confirms that the client's IP address is listed as malicious, BunkerWeb will automatically ban the client, preventing any potential threats from reaching your application. This streamlined integration enhances your ability to block known malicious actors in real time.

Here is the list of settings related to DNSBL :

|   Setting    |                       Default                       | Description                                    |
| :----------: | :-------------------------------------------------: | :--------------------------------------------- |
| `USE_DNSBL`  |                        `yes`                        | When set to `yes`, will enable DNSBL checking. |
| `DNSBL_LIST` | `bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org` | List of DNSBL servers to ask.                  |

## Limiting

BunkerWeb allows you to enforce limit policies on the following:

- **Number of connections per IP**
- **Number of requests per IP and URL within a specific time period**

While these policies are not designed to effectively mitigate DoS or DDoS attacks, they serve as powerful tools for preventing brute-force attempts or implementing rate limiting for APIs.

In both cases—whether the limit applies to connections or requests—clients exceeding the defined limits will receive an HTTP status code **"429 - Too Many Requests"**, ensuring fair usage and protecting your resources.

### Connections

STREAM support :white_check_mark:

The following settings are related to the Limiting connections feature :

|         Setting         | Default | Description                                                                                |
| :---------------------: | :-----: | :----------------------------------------------------------------------------------------- |
|    `USE_LIMIT_CONN`     |  `yes`  | When set to `yes`, will limit the maximum number of concurrent connections for a given IP. |
| `LIMIT_CONN_MAX_HTTP1`  |  `10`   | Maximum number of concurrent connections when using HTTP1 protocol.                        |
| `LIMIT_CONN_MAX_HTTP2`  |  `100`  | Maximum number of concurrent streams when using HTTP2 protocol.                            |
| `LIMIT_CONN_MAX_HTTP3`  |  `100`  | Maximum number of concurrent streams when using HTTP3 protocol.                            |
| `LIMIT_CONN_MAX_STREAM` |  `10`   | Maximum number of connections per IP when using stream.                                    |

### Requests

STREAM support :x:

The following settings are related to the Limiting requests feature :

| Setting          | Default | Context   | Multiple | Description                                                                                   |
| ---------------- | ------- | --------- | -------- | --------------------------------------------------------------------------------------------- |
| `USE_LIMIT_REQ`  | `yes`   | multisite | no       | Activate limit requests feature.                                                              |
| `LIMIT_REQ_URL`  | `/`     | multisite | yes      | URL (PCRE regex) where the limit request will be applied or special value / for all requests. |
| `LIMIT_REQ_RATE` | `2r/s`  | multisite | yes      | Rate to apply to the URL (s for second, m for minute, h for hour and d for day).              |

You can configure different rate limits for specific URLs by appending a numeric suffix to the relevant settings. This allows fine-grained control over traffic to various endpoints. For example:

- `LIMIT_REQ_URL_1=^/url1$` and `LIMIT_REQ_RATE_1=5r/d` will apply a limit of 5 requests per day to `/url1`.
- `LIMIT_REQ_URL_2=^/url2/subdir/.*$` and `LIMIT_REQ_RATE_2=1r/m` will apply a stricter limit of 1 request per minute to any URL under `/url2/subdir/`.

This flexibility ensures that different endpoints can have tailored rate limits based on their usage patterns or sensitivity.

!!! info "Key considerations"
    - The `LIMIT_REQ_URL` values are **PCRE regex (Perl Compatible Regular Expressions)**. This means you can use advanced regular expression patterns to match specific URLs or URL structures precisely.
    - Proper regex usage allows for complex matching scenarios, such as limiting requests to nested paths, parameterized URLs, or specific file types.

By leveraging these settings, you can effectively manage traffic across your application, ensuring fair resource usage while protecting against misuse or abuse.

## Country

STREAM support :white_check_mark:

The **Country Security** feature enables you to enforce policies based on the geographic location of a client's IP address. This provides an additional layer of control and security for your application. You can configure it to:

- **Blacklist**: Deny access to clients if their country is included in a blacklist. These clients will be entirely blocked from reaching your application.
- **Whitelist**: Allow access only to clients whose country is included in a whitelist. Clients from other countries will be denied access, but those allowed will still undergo other configured security checks.

This feature is particularly useful for restricting access to certain regions, protecting sensitive resources, or reducing exposure to potential threats originating from specific areas.

Here is the list of related settings :

| Setting             | Default | Context   | Multiple | Description                                                                                                    |
| ------------------- | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------- |
| `BLACKLIST_COUNTRY` |         | multisite | no       | Deny access if the country of the client is in the list (ISO 3166-1 alpha-2 format separated with spaces).     |
| `WHITELIST_COUNTRY` |         | multisite | no       | Deny access if the country of the client is not in the list (ISO 3166-1 alpha-2 format separated with spaces). |

Using both a country blacklist and a whitelist simultaneously is logically redundant and not recommended. If both are configured, the **whitelist takes precedence**, meaning only the whitelist will be applied, and the blacklist will be ignored.

To avoid confusion and ensure clear policy enforcement, use either a blacklist or a whitelist based on your specific security requirements, but not both at the same time.

## Authentication

### Auth basic

STREAM support :x:

To safeguard sensitive resources, such as an admin area, you can enable **HTTP Basic Authentication**. This simple yet effective mechanism requires users to provide valid credentials before accessing the protected resource, adding an extra layer of security with minimal configuration.

Here is the list of related settings :

|        Setting        |      Default      | Multiple                            | Description                                                                                  |
| :-------------------: | :---------------: | :---------------------------------- | :------------------------------------------------------------------------------------------- |
|   `USE_AUTH_BASIC`    |       `no`        | no                                  | When set to `yes` HTTP auth basic will be enabled.                                           |
| `AUTH_BASIC_LOCATION` |    `sitewide`     | no                                  | Location (URL) of the sensitive resource. Use special value `sitewide` to enable everywhere. |
|   `AUTH_BASIC_USER`   |    `changeme`     | yes                                 | The username required.                                                                       |
| `AUTH_BASIC_PASSWORD` |    `changeme`     | yes                                 | The password required.                                                                       |
|   `AUTH_BASIC_TEXT`   | `Restricted area` | Text to display in the auth prompt. |

!!! tip "multi users"
    You can set multiple users by using the following format : `AUTH_BASIC_USER_1`, `AUTH_BASIC_PASSWORD_1`, `AUTH_BASIC_USER_2`, `AUTH_BASIC_PASSWORD_2`, etc.

### Auth request

For more advanced authentication methods, such as Single Sign-On (SSO), you can leverage the **auth request settings**. This allows integration with external authentication systems by using subrequest-based authentication. For detailed information about this feature, refer to the [NGINX documentation](https://docs.nginx.com/nginx/admin-guide/security-controls/configuring-subrequest-authentication/).

To help you get started, the [BunkerWeb repository](https://github.com/bunkerity/bunkerweb/tree/v1.6.0-rc1/examples) includes examples for popular authentication solutions like [Authelia](https://www.authelia.com/) and [Authentik](https://goauthentik.io/). These examples demonstrate how to integrate these tools seamlessly with your deployment.

**Auth request settings are related to reverse proxy rules.**

| Setting                                 | Default | Context   | Multiple | Description                                                                                                          |
| --------------------------------------- | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------- |
| `REVERSE_PROXY_AUTH_REQUEST`            |         | multisite | yes      | Enable authentication using an external provider (value of auth_request directive).                                  |
| `REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` |         | multisite | yes      | Redirect clients to sign-in URL when using REVERSE_PROXY_AUTH_REQUEST (used when auth_request call returned 401).    |
| `REVERSE_PROXY_AUTH_REQUEST_SET`        |         | multisite | yes      | List of variables to set from the authentication provider, separated with ; (values of auth_request_set directives). |

## Monitoring and reporting

### Monitoring <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :x:

The monitoring plugin lets you collect and retrieve metrics about BunkerWeb. By enabling it, your instance(s) will start collecting various data related to attacks, requests and performance. You can then retrieve them by calling the `/monitoring` API endpoint on regular basis or by using other plugins like the Prometheus exporter one.

**List of features**

- Enable collection of various BunkerWeb metrics
- Retrieve metrics from the API
- Use in combination with other plugins (e.g. Prometheus exporter)
- Dedicate UI page to monitor your instance(s)

**List of settings**

| Setting                        | Default | Context | Multiple | Description                                   |
| ------------------------------ | ------- | ------- | -------- | --------------------------------------------- |
| `USE_MONITORING`               | `yes`   | global  | no       | Enable monitoring of BunkerWeb.               |
| `MONITORING_METRICS_DICT_SIZE` | `10M`   | global  | no       | Size of the dict to store monitoring metrics. |

### Prometheus exporter <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :x:

The Prometheus exporter plugin adds a [Prometheus exporter](https://prometheus.io/docs/instrumenting/exporters/) on your BunkerWeb instance(s). When enabled, you can configure your Prometheus instance(s) to scrape a specific endpoint on Bunkerweb and gather internal metrics.

We also provide a [Grafana dashboard](https://grafana.com/grafana/dashboards/20755-bunkerweb/) that you can import into your own instance and connect to your own Prometheus datasource.

**Please note that the use of Prometheus exporter plugin requires to enable the Monitoring plugin (`USE_MONITORING=yes`)**

**List of features**

- Prometheus exporter providing internal BunkerWeb metrics
- Dedicated and configurable port, listen IP and URL
- Whitelist IP/network for maximum security

**List of settings**

| Setting                        | Default                                               | Context | Multiple | Description                                                              |
| ------------------------------ | ----------------------------------------------------- | ------- | -------- | ------------------------------------------------------------------------ |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | global  | no       | Enable the Prometheus export.                                            |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | global  | no       | Listening IP of the Prometheus exporter.                                 |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | global  | no       | Listening port of the Prometheus exporter.                               |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | global  | no       | HTTP URL of the Prometheus exporter.                                     |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | global  | no       | List of IP/networks allowed to contact the Prometheus exporter endpoint. |

### Reporting <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :x:

!!! warning "Monitoring plugin needed"
    This plugins requires the Monitoring Pro plugin to be installed and enabled with the `USE_MONITORING` setting set to `yes`.

The Reporting plugin provides a comprehensive solution for regular reporting of important data from BunkerWeb, including global statistics, attacks, bans, requests, reasons, and AS information. It offers a wide range of features, including automatic report creation, customization options, and seamless integration with monitoring pro plugin. With the Reporting plugin, you can easily generate and manage reports to monitor the performance and security of your application.

**List of features**

- Regular reporting of important data from BunkerWeb, including global statistics, attacks, bans, requests, reasons, and AS information.
- Integration with Monitoring Pro plugin for seamless integration and enhanced reporting capabilities.
- Support for webhooks (classic, Discord, and Slack) for real-time notifications.
- Support for SMTP for email notifications.
- Configuration options for customization and flexibility.

**List of settings**

| Setting                        | Default            | Context | Description                                                                                                                        |
| ------------------------------ | ------------------ | ------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | global  | Enable sending the report via email.                                                                                               |
| `USE_REPORTING_WEBHOOK`        | `no`               | global  | Enable sending the report via webhook.                                                                                             |
| `REPORTING_SCHEDULE`           | `weekly`           | global  | The frequency at which reports are sent.                                                                                           |
| `REPORTING_WEBHOOK_URLS`       |                    | global  | List of webhook URLs to receive the report in Markdown (separated by spaces).                                                      |
| `REPORTING_SMTP_EMAILS`        |                    | global  | List of email addresses to receive the report in HTML format (separated by spaces).                                                |
| `REPORTING_SMTP_HOST`          |                    | global  | The host server used for SMTP sending.                                                                                             |
| `REPORTING_SMTP_PORT`          | `465`              | global  | The port used for SMTP. Please note that there are different standards depending on the type of connection (SSL = 465, TLS = 587). |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | global  | The email address used as the sender. Note that 2FA must be disabled for this email address.                                       |
| `REPORTING_SMTP_FROM_USER`     |                    | global  | The user authentication value for sending via the from email address.                                                              |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | global  | The password authentication value for sending via the from email address.                                                          |
| `REPORTING_SMTP_SSL`           | `SSL`              | global  | Determine whether or not to use a secure connection for SMTP.                                                                      |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | global  | The subject line of the email.                                                                                                     |

!!! info "Information and behavior"
    - case `USE_REPORTING_SMTP` is set to `yes`, the setting `REPORTING_SMTP_EMAILS` must be set.
    - case `USE_REPORTING_WEBHOOK` is set to `yes`, the setting `REPORTING_WEBHOOK_URLS` must be set.
    - Accepted values for `REPORTING_SCHEDULE` are `daily`, `weekly`and `monthly`.
    - case no `REPORTING_SMTP_FROM_USER` and `REPORTING_SMTP_FROM_PASSWORD` are set, the plugin will try to send the email without authentication.
    - case `REPORTING_SMTP_FROM_USER` isn't set but `REPORTING_SMTP_FROM_PASSWORD` is set, the plugin will use the `REPORTING_SMTP_FROM_EMAIL` as the username.
    - case the job fails, the plugin will retry sending the report in the next execution.

## Backup and restore

### Backup

STREAM support :white_check_mark:

#### Automated backup

!!! warning "Information for Red Hat Enterprise Linux (RHEL) 8.9 users"
    If you are using **RHEL 8.9** and plan on using an **external database**, you will need to install the `mysql-community-client` package to ensure the `mysqldump` command is available. You can install the package by executing the following commands:

    === "MySQL/MariaDB"

        1. **Install the MySQL repository configuration package**

            ```bash
            sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
            ```

        2. **Enable the MySQL repository**

            ```bash
            sudo dnf config-manager --enable mysql80-community
            ```

        3. **Install the MySQL client**

            ```bash
            sudo dnf install mysql-community-client
            ```

    === "PostgreSQL"

        1. **Install the PostgreSQL repository configuration package**

            ```bash
            dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
            ```

        2. **Install the PostgreSQL client**

            ```bash
            dnf install postgresql<version>
            ```


Data is invaluable, especially in digital environments where it's susceptible to loss due to various factors such as hardware failures, software errors, or human mistakes. To mitigate such risks and ensure the safety and availability of your important files, it's crucial to establish a robust backup system. This section outlines the backup functionality provided by BunkerWeb, allowing you to securely store your data in a custom location through regular backups.

!!! info "Information and behavior"

    The importance of backups cannot be overstated. They serve as a safety net against data loss scenarios, providing a means to restore your system to a previous state in case of unexpected events. Regular backups not only safeguard your data but also offer peace of mind, knowing that you have a reliable mechanism in place to recover from any mishaps.


| Setting            | Default                      | Context | Multiple | Description                                   |
| ------------------ | ---------------------------- | ------- | -------- | --------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global  | no       | Enable or disable the backup feature          |
| `BACKUP_SCHEDULE`  | `daily`                      | global  | no       | The frequency of the backup                   |
| `BACKUP_ROTATION`  | `7`                          | global  | no       | The number of backups to keep                 |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global  | no       | The directory where the backup will be stored |

#### Manual backup

To manually initiate a backup, execute the following command:

=== "Linux"

    ```bash
    bwcli plugin backup save
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup save
    ```

This command will create a backup of your database and store it in the backup directory specified in the `BACKUP_DIRECTORY` setting.

You can also specify a custom directory for the backup by providing the `BACKUP_DIRECTORY` environment variable when executing the command:

=== "Linux"

    ```bash
    BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
    ```

=== "Docker"

    ```bash
    docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
    ```

    ```bash
    docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
    ```

!!! note "Specifications for MariaDB/MySQL"

    In case you are using MariaDB/MySQL, you may encounter the following error when trying to backup your database:

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    To resolve this issue, you can execute the following command to change the authentication plugin to `mysql_native_password`:

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    If you're using the Docker integration, you can add the following command to the `docker-compose.yml` file to automatically change the authentication plugin:

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

#### Manual restore

To manually initiate a restore, execute the following command:

=== "Linux"

    ```bash
    bwcli plugin backup restore
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup restore
    ```

This command will create a temporary backup of your database in `/var/tmp/bunkerweb/backups` and restore your database to the latest backup available in the backup directory specified in the `BACKUP_DIRECTORY` setting.

You can also specify a custom backup file for the restore by providing the path to it as an argument when executing the command:

=== "Linux"

    ```bash
    bwcli plugin backup restore /path/to/backup/file
    ```

=== "Docker"

    ```bash
    docker cp /path/to/backup/file <scheduler_container>:/path/to/backup/file
    ```

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup restore /path/to/backup/file
    ```

!!! example "In case of failure"

    Don't worry if the restore fails, you can always restore your database to the previous state by executing the command again but with the `BACKUP_DIRECTORY` setting set to `/var/tmp/bunkerweb/backups`:

    === "Linux"

        ```bash
        BACKUP_DIRECTORY=/var/tmp/bunkerweb/backups bwcli plugin backup restore
        ```

    === "Docker"

        ```bash
        docker cp <scheduler_container>:/var/tmp/bunkerweb/backups /var/tmp/bunkerweb/backups
        ```

        ```bash
        docker exec -it -e BACKUP_DIRECTORY=/var/tmp/bunkerweb/backups <scheduler_container> bwcli plugin backup restore
        ```

### Backup S3 <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :white_check_mark:

The Backup S3 tool seamlessly automates data protection, similar to the community backup plugin. However, it stands out by securely storing backups directly in an S3 bucket.

By activating this feature, you're proactively safeguarding your **data's integrity**. Storing backups **remotely** shields crucial information from threats like **hardware failures**, **cyberattacks**, or **natural disasters**. This ensures both **security** and **availability**, enabling swift recovery during **unexpected events**, preserving **operational continuity**, and ensuring **peace of mind**.

!!! warning "Information for Red Hat Enterprise Linux (RHEL) 8.9 users"
    If you are using **RHEL 8.9** and plan on using an **external database**, you will need to install the `mysql-community-client` package to ensure the `mysqldump` command is available. You can install the package by executing the following commands:

    === "MySQL/MariaDB"

        1. **Install the MySQL repository configuration package**

            ```bash
            sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
            ```

        2. **Enable the MySQL repository**

            ```bash
            sudo dnf config-manager --enable mysql80-community
            ```

        3. **Install the MySQL client**

            ```bash
            sudo dnf install mysql-community-client
            ```

    === "PostgreSQL"

        1. **Install the PostgreSQL repository configuration package**

            ```bash
            dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
            ```

        2. **Install the PostgreSQL client**

            ```bash
            dnf install postgresql<version>
            ```

**List of features**

- Automatic data backup to an S3 bucket
- Flexible scheduling options: daily, weekly, or monthly
- Rotation management for controlling the number of backups to keep
- Customizable compression level for backup files

**List of settings**

| Setting                       | Default | Context | Description                                  |
| ----------------------------- | ------- | ------- | -------------------------------------------- |
| `USE_BACKUP_S3`               | `no`    | global  | Enable or disable the S3 backup feature      |
| `BACKUP_S3_SCHEDULE`          | `daily` | global  | The frequency of the backup                  |
| `BACKUP_S3_ROTATION`          | `7`     | global  | The number of backups to keep                |
| `BACKUP_S3_ENDPOINT`          |         | global  | The S3 endpoint                              |
| `BACKUP_S3_BUCKET`            |         | global  | The S3 bucket                                |
| `BACKUP_S3_DIR`               |         | global  | The S3 directory                             |
| `BACKUP_S3_REGION`            |         | global  | The S3 region                                |
| `BACKUP_S3_ACCESS_KEY_ID`     |         | global  | The S3 access key ID                         |
| `BACKUP_S3_ACCESS_KEY_SECRET` |         | global  | The S3 access key secret                     |
| `BACKUP_S3_COMP_LEVEL`        | `6`     | global  | The compression level of the backup zip file |

#### Manual backup

To manually initiate a backup, execute the following command:

=== "Linux"

    ```bash
    bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 save
    ```

This command will create a backup of your database and store it in the S3 bucket specified in the `BACKUP_S3_BUCKET` setting.

You can also specify a custom S3 bucket for the backup by providing the `BACKUP_S3_BUCKET` environment variable when executing the command:

=== "Linux"

    ```bash
    BACKUP_S3_BUCKET=your-bucket-name bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it -e BACKUP_S3_BUCKET=your-bucket-name <scheduler_container> bwcli plugin backup_s3 save
    ```

!!! note "Specifications for MariaDB/MySQL"

    In case you are using MariaDB/MySQL, you may encounter the following error when trying to backup your database:

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    To resolve this issue, you can execute the following command to change the authentication plugin to `mysql_native_password`:

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    If you're using the Docker integration, you can add the following command to the `docker-compose.yml` file to automatically change the authentication plugin:

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

#### Manual restore

To manually initiate a restore, execute the following command:

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
    ```

This command will create a temporary backup of your database in the S3 bucket specified in the `BACKUP_S3_BUCKET` setting and restore your database to the latest backup available in the bucket.

You can also specify a custom backup file for the restore by providing the path to it as an argument when executing the command:

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore s3_backup_file.zip
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup restore s3_backup_file.zip
    ```

!!! example "In case of failure"

    Don't worry if the restore fails, you can always restore your database to the previous state by executing the command again as a backup is created before the restore:

    === "Linux"

        ```bash
        bwcli plugin backup_s3 restore
        ```

    === "Docker"

        ```bash
        docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
        ```

## Migration <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :white_check_mark:

The Migration plugin **revolutionizes** BunkerWeb configuration transfers between instances with its **user-friendly web interface**, simplifying the entire migration journey. Whether you're upgrading systems, scaling infrastructure, or transitioning environments, this tool empowers you to effortlessly transfer **settings, preferences, and data** with unmatched ease and confidence. Say goodbye to cumbersome manual processes and hello to a **seamless, hassle-free migration experience**.

**List of features**

- **Effortless Migration:** Easily transfer BunkerWeb configurations between instances without the complexities of manual procedures.

- **Intuitive Web Interface:** Navigate through the migration process effortlessly with a user-friendly web interface designed for intuitive operation.

- **Cross-Database Compatibility:** Enjoy seamless migration across various database platforms, including SQLite, MySQL, MariaDB, and PostgreSQL, ensuring compatibility with your preferred database environment.

### Create a migration file

To manually create a migration file, execute the following command:

=== "Linux"

    ```bash
    bwcli plugin migration create /path/to/migration/file
    ```

=== "Docker"

    1. Create a migration file:

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration create /path/to/migration/file
        ```

    2. Copy the migration file to your local machine:

        ```bash
        docker cp <scheduler_container>:/path/to/migration/file /path/to/migration/file
        ```

This command will create a backup of your database and store it in the backup directory specified in the command.

!!! note "Specifications for MariaDB/MySQL"

    In case you are using MariaDB/MySQL, you may encounter the following error when trying to backup your database:

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    To resolve this issue, you can execute the following command to change the authentication plugin to `mysql_native_password`:

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    If you're using the Docker integration, you can add the following command to the `docker-compose.yml` file to automatically change the authentication plugin:

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

### Initialize a migration

To manually initialize a migration, execute the following command:

=== "Linux"

    ```bash
    bwcli plugin migration migrate /path/to/migration/file
    ```

=== "Docker"

    1. Copy the migration file to the container:

        ```bash
        docker cp /path/to/migration/file <scheduler_container>:/path/to/migration/file
        ```

    2. Initialize the migration:

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration migrate /path/to/migration/file
        ```

This command seamlessly migrates your BunkerWeb data to precisely match the configuration outlined in the migration file.

## Security.txt

STREAM support :white_check_mark:

The Security.txt plugin allows you to easily create a `security.txt` file for your website, providing a standardized method for security researchers and others to report security vulnerabilities. By enabling this feature, you can enhance your site's security posture and streamline the reporting process for potential security issues.

**List of features**

- **Streamlined and Standardized Reporting:** Implement a standardized and user-friendly method for security researchers to report vulnerabilities, ensuring clear communication and timely responses.
- **Enhanced Security Posture and Transparency:** Strengthen your site's security by providing clear guidelines for reporting security issues, fostering transparency and trust within the security community.
- **Customizable and User-Friendly Configuration:** Customize the `security.txt` file to include specific contact information and security policies, and manage it easily through a user-friendly web interface.
- **Compliance with Best Practices:** Align with industry best practices by implementing a `security.txt` file, demonstrating your commitment to security and fostering a collaborative security culture.

!!! warning "Settings required"
    To enable the Security.txt plugin, you need to at least set the `SECURITYTXT_CONTACT` setting to a valid value to specify the contact information for reporting security vulnerabilities. If this setting is not configured, the `security.txt` file won't be served.

**List of settings**

| Setting                        | Default                     | Context   | Multiple | Description                                                                                                                                                                                                                                                              |
| ------------------------------ | --------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_SECURITYTXT`              | `no`                        | multisite | no       | Enable security.txt file.                                                                                                                                                                                                                                                |
| `SECURITYTXT_URI`              | `/.well-known/security.txt` | multisite | no       | Indicates the URI where the "security.txt" file will be accessible from.                                                                                                                                                                                                 |
| `SECURITYTXT_CONTACT`          |                             | multisite | yes      | Indicates a method that researchers should use for reporting security vulnerabilities such as an email address, a phone number, and/or a web page with contact information. (If the value is empty, the security.txt file will not be created as it is a required field) |
| `SECURITYTXT_EXPIRES`          |                             | multisite | no       | Indicates the date and time after which the data contained in the "security.txt" file is considered stale and should not be used (If the value is empty, the value will always be the current date and time + 1 year).                                                   |
| `SECURITYTXT_ENCRYPTION`       |                             | multisite | yes      | Indicates an encryption key that security researchers should use for encrypted communication.                                                                                                                                                                            |
| `SECURITYTXT_ACKNOWLEDGEMENTS` |                             | multisite | yes      | Indicates a link to a page where security researchers are recognized for their reports.                                                                                                                                                                                  |
| `SECURITYTXT_PREFERRED_LANG`   | `en`                        | multisite | no       | Can be used to indicate a set of natural languages that are preferred when submitting security reports.                                                                                                                                                                  |
| `SECURITYTXT_CANONICAL`        |                             | multisite | yes      | Indicates the canonical URIs where the "security.txt" file is located, which is usually something like "https://example.com/.well-known/security.txt". (If the value is empty, the default value will be automatically generated from the site URL + SECURITYTXT_URI)    |
| `SECURITYTXT_POLICY`           |                             | multisite | yes      | Indicates a link to where the vulnerability disclosure policy is located.                                                                                                                                                                                                |
| `SECURITYTXT_HIRING`           |                             | multisite | yes      | Used for linking to the vendor's security-related job positions.                                                                                                                                                                                                         |
| `SECURITYTXT_CSAF`             |                             | multisite | yes      | A link to the provider-metadata.json of your CSAF (Common Security Advisory Framework) provider.                                                                                                                                                                         |

!!! info "Autogenerated values"
    - The `SECURITYTXT_CANONICAL` setting is automatically generated from the site URL and the `SECURITYTXT_URI` setting (if the value is empty).
    - The `SECURITYTXT_EXPIRES` setting is automatically generated to be the current date and time + 1 year if the value is empty.
