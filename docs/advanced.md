# Advanced usages

Many real-world use case examples are available in the [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.4/examples) folder of the GitHub repository.

We also provide numerous boilerplates, such as YAML files for various integrations and database types. These are available in the [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.4/misc/integrations) folder.

This section only focuses on advanced usages and security tuning, see the [settings section](features.md) of the documentation to see all the available settings.

## Use cases

!!! tip "Testing"
    To perform quick tests when multisite mode is enabled (and if you don't have the proper DNS entries set up for the domains) you can use curl with the HTTP Host header of your choice :
    ```shell
    curl -H "Host: app1.example.com" http://ip-or-fqdn-of-server
    ```

    If you are using HTTPS, you will need to play with SNI :
    ```shell
    curl -H "Host: app1.example.com" --resolve example.com:443:ip-of-server https://example.com
    ```

### Behind load balancer or reverse proxy

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

You will find more settings about real IP in the [settings section](features.md#real-ip) of the documentation.

=== "HTTP header"

    We will assume the following regarding the load balancers or reverse proxies (you will need to update the settings depending on your configuration) :

    - They use the `X-Forwarded-For` header to set the real IP
    - They have IPs in the `1.2.3.0/24` and `100.64.0.0/10` networks

    === "Web UI"

        Navigate to the **Global config** page, select the **Real IP** plugin and fill out the following settings :

        <figure markdown>![Real IP settings (header) using web UI](assets/img/advanced-proxy1.png){ align=center }<figcaption>Real IP settings (header) using web UI</figcaption></figure>

        Please note that it's recommended to restart BunkerWeb when you change settings related to real IP.

    === "Linux"

        You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

        ```conf
        ...
        USE_REAL_IP=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=X-Forwarded-For
        ...
        ```

        Please note that it's recommended to issue a restart instead of reload when configuring settings related to real IP :

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "All-in-one"

        You will need to add the settings to the environment variables when running the All-in-one container :

        ```bash
        docker run -d \
            --name bunkerweb-aio \
            -v bw-storage:/data \
            -e USE_REAL_IP="yes" \
            -e REAL_IP_FROM="1.2.3.0/24 100.64.0.0/10" \
            -e REAL_IP_HEADER="X-Forwarded-For" \
            -p 80:8080/tcp \
            -p 443:8443/tcp \
            -p 443:8443/udp \
            bunkerity/bunkerweb-all-in-one:1.6.4
        ```

        Please note that if your container is already created, you will need to delete it and recreate it so the new environment variables will be updated.

    === "Docker"

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler containers:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.4
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.4
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Please note that if your container is already created, you will need to delete it and recreate it so the new environment variables will be updated.

    === "Docker autoconf"

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler containers:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.4
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.4
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Please note that if your container is already created, you will need to delete it and recreate it so the new environment variables will be updated.

    === "Kubernetes"

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler pods.

        Here is the corresponding part of your `values.yaml` file that you can use :

        ```yaml
        bunkerweb:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "X-Forwarded-For"
        scheduler:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "X-Forwarded-For"
        ```

    === "Swarm"

        !!! warning "Deprecated"
            The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_2_2) instead.

            **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler services:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.4
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.4
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Please note that if your service is already created, you will need to delete it and recreate it so the new environment variables will be updated.

=== "Proxy protocol"

    !!! warning "Read carefully"

        Only use the PROXY protocol if you are sure that your load balancer or reverse proxy is sending it. **If you enable it and it's not used, you will get errors**.

    We will assume the following regarding the load balancers or reverse proxies (you will need to update the settings depending on your configuration) :

    - They use the `PROXY protocol` v1 or v2 to set the real IP
    - They have IPs in the `1.2.3.0/24` and `100.64.0.0/10` networks

    === "Web UI"

        Navigate to the **Global config** page, select the **Real IP** plugin and fill out the following settings :

        <figure markdown>![Real IP settings (PROXY protocol) using web UI](assets/img/advanced-proxy2.png){ align=center }<figcaption>Real IP settings (PROXY protocol) using web UI</figcaption></figure>

        Please note that it's recommended to restart BunkerWeb when you change settings related to real IP.

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
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "All-in-one"

        You will need to add the settings to the environment variables when running the All-in-one container :

        ```bash
        docker run -d \
            --name bunkerweb-aio \
            -v bw-storage:/data \
            -e USE_REAL_IP="yes" \
            -e USE_PROXY_PROTOCOL="yes" \
            -e REAL_IP_FROM="1.2.3.0/24 100.64.0.0/10" \
            -e REAL_IP_HEADER="X-Forwarded-For" \
            -p 80:8080/tcp \
            -p 443:8443/tcp \
            -p 443:8443/udp \
            bunkerity/bunkerweb-all-in-one:1.6.4
        ```

        Please note that if your container is already created, you will need to delete it and recreate it so the new environment variables will be updated.

    === "Docker"

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler containers:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.4
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.4
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Please note that if your container is already created, you will need to delete it and recreate it so the new environment variables will be updated.

    === "Docker autoconf"

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler containers:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.4
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.4
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Please note that if your container is already created, you will need to delete it and recreate it so the new environment variables will be updated.

    === "Kubernetes"

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler pods.

        Here is the corresponding part of your `values.yaml` file that you can use:

        ```yaml
        bunkerweb:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: USE_PROXY_PROTOCOL
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "proxy_protocol"
        scheduler:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: USE_PROXY_PROTOCOL
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "proxy_protocol"
        ```

    === "Swarm"

        !!! warning "Deprecated"
            The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_3_2) instead.

            **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler services.

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.4
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.4
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Please note that if your service is already created, you will need to delete it and recreate it so the new environment variables will be updated.

### Using custom DNS resolution mechanisms

BunkerWeb's NGINX configuration can be customized to use different DNS resolvers depending on your needs. This can be particularly useful in various scenarios:

1. To respect entries in your local `/etc/hosts` file
2. When you need to use custom DNS servers for certain domains
3. To integrate with local DNS caching solutions

#### Using systemd-resolved

Many modern Linux systems use `systemd-resolved` for DNS resolution. If you want BunkerWeb to respect the content of your `/etc/hosts` file and use the system's DNS resolution mechanism, you can configure it to use the local systemd-resolved DNS service.

To verify that systemd-resolved is running on your system, you can use:

```bash
systemctl status systemd-resolved
```

To enable systemd-resolved as your DNS resolver in BunkerWeb, set the `DNS_RESOLVERS` setting to `127.0.0.53`, which is the default listening address for systemd-resolved:

=== "Web UI"

    Navigate to the **Global config** page and set the DNS resolvers to `127.0.0.53`

=== "Linux"

    You will need to modify the `/etc/bunkerweb/variables.env` file:

    ```conf
    ...
    DNS_RESOLVERS=127.0.0.53
    ...
    ```

    After making this change, reload BunkerWeb to apply the configuration:

    ```shell
    sudo systemctl reload bunkerweb-scheduler
    ```

#### Using dnsmasq

[dnsmasq](http://www.thekelleys.org.uk/dnsmasq/doc.html) is a lightweight DNS, DHCP, and TFTP server that's commonly used for local DNS caching and customization. It's particularly useful when you need more control over your DNS resolution than systemd-resolved provides.

=== "Linux"

    First, install and configure dnsmasq on your Linux system:

    === "Debian/Ubuntu"

        ```bash
        # Install dnsmasq
        sudo apt-get update && sudo apt-get install dnsmasq

        # Configure dnsmasq to listen only on localhost
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # Add custom DNS entries if needed
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # Restart dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    === "RHEL/Fedora"

        ```bash
        # Install dnsmasq
        sudo dnf install dnsmasq

        # Configure dnsmasq to listen only on localhost
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # Add custom DNS entries if needed
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # Restart dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    Then configure BunkerWeb to use dnsmasq by setting `DNS_RESOLVERS` to `127.0.0.1`:

    === "Web UI"

        Navigate to the **Global config** page, select the **NGINX** plugin and set the DNS resolvers to `127.0.0.1`.

    === "Linux"

        You will need to modify the `/etc/bunkerweb/variables.env` file:

        ```conf
        ...
        DNS_RESOLVERS=127.0.0.1
        ...
        ```

        After making this change, reload BunkerWeb:

        ```shell
        sudo systemctl reload bunkerweb-scheduler
        ```

=== "All-in-one"

    When using the All-in-one container, run dnsmasq in a separate container and configure BunkerWeb to use it:

    ```bash
    # Create a custom network for DNS communication
    docker network create bw-dns

    # Run dnsmasq container using dockurr/dnsmasq with Quad9 DNS
    # Quad9 provides security-focused DNS resolution with malware blocking
    docker run -d \
        --name dnsmasq \
        --network bw-dns \
        -e DNS1="9.9.9.9" \
        -e DNS2="149.112.112.112" \
        -p 53:53/udp \
        -p 53:53/tcp \
        --cap-add=NET_ADMIN \
        --restart=always \
        dockurr/dnsmasq

    # Run BunkerWeb All-in-one with dnsmasq DNS resolver
    docker run -d \
        --name bunkerweb-aio \
        --network bw-dns \
        -v bw-storage:/data \
        -e DNS_RESOLVERS="dnsmasq" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.4
    ```

=== "Docker"

    Add a dnsmasq service to your docker-compose file and configure BunkerWeb to use it:

    ```yaml
    services:
      dnsmasq:
        image: dockurr/dnsmasq
        container_name: dnsmasq
        environment:
          # Using Quad9 DNS servers for enhanced security and privacy
          # Primary: 9.9.9.9 (Quad9 with malware blocking)
          # Secondary: 149.112.112.112 (Quad9 backup server)
          DNS1: "9.9.9.9"
          DNS2: "149.112.112.112"
        ports:
          - 53:53/udp
          - 53:53/tcp
        cap_add:
          - NET_ADMIN
        restart: always
        networks:
          - bw-dns

      bunkerweb:
        image: bunkerity/bunkerweb:1.6.4
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-services
          - bw-dns

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.4
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-dns

    networks:
      # ...existing networks...
      bw-dns:
        name: bw-dns
    ```

### Custom configurations

To customize and add custom configurations to BunkerWeb, you can take advantage of its NGINX foundation. Custom NGINX configurations can be added in different NGINX contexts, including configurations for the ModSecurity Web Application Firewall (WAF), which is a core component of BunkerWeb. More details about ModSecurity configurations can be found [here](features.md#custom-configurations).

Here are the available types of custom configurations:

- **http**: Configurations at the HTTP level of NGINX.
- **server-http**: Configurations at the HTTP/Server level of NGINX.
- **default-server-http**: Configurations at the Server level of NGINX, specifically for the "default server" when the supplied client name doesn't match any server name in `SERVER_NAME`.
- **modsec-crs**: Configurations applied before the OWASP Core Rule Set is loaded.
- **modsec**: Configurations applied after the OWASP Core Rule Set is loaded, or used when the Core Rule Set is not loaded.
- **crs-plugins-before**: Configurations for the CRS plugins, applied before the CRS plugins are loaded.
- **crs-plugins-after**: Configurations for the CRS plugins, applied after the CRS plugins are loaded.
- **stream**: Configurations at the Stream level of NGINX.
- **server-stream**: Configurations at the Stream/Server level of NGINX.

Custom configurations can be applied globally or specifically for a particular server, depending on the applicable context and whether the [multisite mode](concepts.md#multisite-mode) is enabled.

The method for applying custom configurations depends on the integration being used. However, the underlying process involves adding files with the `.conf` suffix to specific folders. To apply a custom configuration for a specific server, the file should be placed in a subfolder named after the primary server name.

Some integrations provide more convenient ways to apply configurations, such as using [Configs](https://docs.docker.com/engine/swarm/configs/) in Docker Swarm or [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) in Kubernetes. These options offer simpler approaches for managing and applying configurations.

=== "Web UI"

    Navigate to the **Configs** page, click on **Create new custom config**, you can then choose if it's a global one or specific to a service, the configuration type and the configuration name :

    <figure markdown>![Custom configurations using web UI](assets/img/advanced-config.png){ align=center }<figcaption>Custom configurations using web UI</figcaption></figure>

    Don't forget to click on the save button.

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

    Now let's check the status of the Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    If they are already running, we can reload it :

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "All-in-one"

    When using the [All-in-one image](integrations.md#all-in-one-aio-image), you have two choices for adding custom configurations:

    - Using specific settings `*_CUSTOM_CONF_*` as environment variables when running the container (recommended).
    - Writing `.conf` files to the `/data/configs/` directory within the volume mounted to `/data`.

    **Using settings (Environment Variables)**

    The settings to use must follow the pattern `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>`:

    - `<SITE>` : Optional primary server name if multisite mode is enabled and the config must be applied to a specific service.
    - `<TYPE>` : The type of config, accepted values are `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER`, `STREAM` and `SERVER_STREAM`.
    - `<NAME>` : The name of config without the `.conf` suffix.

    Here is a dummy example when running the All-in-one container:

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -e "CUSTOM_CONF_SERVER_HTTP_hello-world=location /hello { \
            default_type 'text/plain'; \
            content_by_lua_block { \
              ngx.say('world'); \
            } \
          }" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        bunkerity/bunkerweb-all-in-one:1.6.4
    ```

    Please note that if your container is already created, you will need to delete it and recreate it for the new environment variables to be applied.

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

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v ./bw-data:/data \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.4
    ```

=== "Docker"

    When using the [Docker integration](integrations.md#docker), you have two choices for the addition of custom configurations :

    - Using specific settings `*_CUSTOM_CONF_*` as environment variables (recommended)
    - Writing .conf files to the volume mounted on /data of the scheduler

    **Using settings**

    The settings to use must follow the pattern `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` :

    - `<SITE>` : optional primary server name if multisite mode is enabled and the config must be applied to a specific service
    - `<TYPE>` : the type of config, accepted values are `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER`, `STREAM` and `SERVER_STREAM`
    - `<NAME>` : the name of config without the .conf suffix

    Here is a dummy example using a docker-compose file :

    ```yaml
    ...
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.4
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
      image: bunkerity/bunkerweb-scheduler:1.6.4
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

    - `<TYPE>` : the type of config, accepted values are `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER` and `SERVER_STREAM`
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
      image: bunkerity/bunkerweb-scheduler:1.6.4
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Kubernetes"

    When using the [Kubernetes integration](integrations.md#kubernetes), custom configurations are managed using [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/).

    To keep it simple, you don't even need to use the ConfigMap with a Pod (e.g. as environment variable or volume) : the autoconf Pod is listening for ConfigMap events and will update the custom configurations when needed.

    When creating a ConfigMap, you will need to add special labels :

    * **bunkerweb.io/CONFIG_TYPE** : must be set to a valid custom configuration type (http, server-http, default-server-http, modsec, modsec-crs, crs-plugins-before, crs-plugins-after, stream or server-stream)
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

    !!! tip "Custom Extra Config"
        Since the `1.6.0-rc3` version, you can add/override settings using the `bunkerweb.io/CONFIG_TYPE=settings` annotation. Here is an example :

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: cfg-bunkerweb-extra-settings
          annotations:
            bunkerweb.io/CONFIG_TYPE: "settings"
        data:
          USE_ANTIBOT: "captcha" # multisite setting that will be applied to all services that do not override it
          USE_REDIS: "yes" # global setting that will be applied globally
          ...
        ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_5_2) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    When using the [Swarm integration](integrations.md#swarm), custom configurations are managed using [Docker Configs](https://docs.docker.com/engine/swarm/configs/).

    To keep it simple, you don't even need to attach the Config to a service : the autoconf service is listening for Config events and will update the custom configurations when needed.

    When creating a Config, you will need to add special labels :

    * **bunkerweb.CONFIG_TYPE** : must be set to a valid custom configuration type (http, server-http, default-server-http, modsec, modsec-crs, crs-plugins-before, crs-plugins-after, stream or server-stream)
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

### Running many services in production

#### Global CRS

!!! warning "CRS plugins"
    When the CRS is loaded globally, **CRS plugins are not supported**. If you need to use them, you will need to load the CRS per service.

If you use BunkerWeb in production with a large number of services, and you enable the ModSecurity feature globally with CRS rules, the time required to load BunkerWeb configurations may become too long, potentially resulting in a timeout.

The workaround is to load the CRS rules globally rather than per service. This behavior is not enabled by default for backward compatibility reasons and because it has a drawback: if you enable global CRS rule loading, it will no longer be possible to define modsec-crs rules (executed before the CRS rules) on a per-service basis. However, this limitation can be bypassed by writing global `modsec-crs` exclusion rules like this:

```
SecRule REQUEST_FILENAME "@rx ^/somewhere$" "nolog,phase:4,allow,id:1010,chain"
SecRule REQUEST_HEADERS:Host "@rx ^app1\.example\.com$" "nolog"
```

You can enable the global CRS loading by setting `USE_MODSECURITY_GLOBAL_CRS` to `yes`.

#### Adjust max_allowed_packet for MariaDB/MySQL

It appears that the default value for the `max_allowed_packet` parameter in MariaDB and MySQL database servers is not sufficient when using BunkerWeb with a large number of services.

If you encounter errors like this, especially on the scheduler:

```
[Warning] Aborted connection 5 to db: 'db' user: 'bunkerweb' host: '172.20.0.4' (Got a packet bigger than 'max_allowed_packet' bytes)
```

You will need to increase the `max_allowed_packet` on your database server.

### Persistence of bans and reports

By default, BunkerWeb stores bans and reports in a local Lua datastore. While simple and efficient, this setup means that data is lost when the instance is restarted. To ensure that bans and reports persist across restarts, you can configure BunkerWeb to use a remote [Redis](https://redis.io/) or [Valkey](https://valkey.io/) server.

**Why Use Redis/Valkey?**

Redis and Valkey are powerful, in-memory data stores commonly used as databases, caches, and message brokers. They are highly scalable and support a variety of data structures, including:

- **Strings**: Basic key-value pairs.
- **Hashes**: Field-value pairs within a single key.
- **Lists**: Ordered collections of strings.
- **Sets**: Unordered collections of unique strings.
- **Sorted Sets**: Ordered collections with scores.

By leveraging Redis or Valkey, BunkerWeb can persistently store bans, reports, and cache data, ensuring durability and scalability.

**Enabling Redis/Valkey Support**

To enable Redis or Valkey support, configure the following settings in your BunkerWeb configuration file:

```conf
# Enable Redis/Valkey support
USE_REDIS=yes

# Redis/Valkey server hostname or IP address
REDIS_HOST=<hostname>

# Redis/Valkey server port number (default: 6379)
REDIS_PORT=6379

# Redis/Valkey database number (default: 0)
REDIS_DATABASE=0
```

- **`USE_REDIS`**: Set to `yes` to enable Redis/Valkey integration.
- **`REDIS_HOST`**: Specify the hostname or IP address of the Redis/Valkey server.
- **`REDIS_PORT`**: Specify the port number for the Redis/Valkey server. Defaults to `6379`.
- **`REDIS_DATABASE`**: Specify the Redis/Valkey database number to use. Defaults to `0`.

If you require more advanced settings, such as authentication, SSL/TLS support, or Sentinel mode, refer to the [Redis plugin settings documentation](features.md#redis) for detailed guidance.

### Protect UDP/TCP applications

!!! example "Experimental feature"

	This feature is not production-ready. Feel free to test it and report us any bug using [issues](https://github.com/bunkerity/bunkerweb/issues) in the GitHub repository.

BunkerWeb offers the capability to function as a **generic UDP/TCP reverse proxy**, allowing you to protect any network-based applications operating at least on layer 4 of the OSI model. Instead of utilizing the "classical" HTTP module, BunkerWeb leverages the [stream module](https://nginx.org/en/docs/stream/ngx_stream_core_module.html) of NGINX.

It's important to note that **not all settings and security features are available when using the stream module**. Additional information on this can be found in the [settings](features.md) sections of the documentation.

Configuring a basic reverse proxy is quite similar to the HTTP setup, as it involves using the same settings: `USE_REVERSE_PROXY=yes` and `REVERSE_PROXY_HOST=myapp:9000`. Even when BunkerWeb is positioned behind a Load Balancer, the settings remain the same (with **PROXY protocol** being the supported option due to evident reasons).

On top of that, the following specific settings are used :

- `SERVER_TYPE=stream` : activate `stream` mode (generic UDP/TCP) instead of `http` one (which is the default)
- `LISTEN_STREAM_PORT=4242` : the listening "plain" (without SSL/TLS) port that BunkerWeb will listen on
- `LISTEN_STREAM_PORT_SSL=4343` : the listening "ssl/tls" port that BunkerWeb will listen on
- `USE_UDP=no` : listen for and forward UDP packets instead of TCP

For complete list of settings regarding `stream` mode, please refer to the [settings](features.md) section of the documentation.

!!! tip "multiple listening ports"

    Since the `1.6.0-rc2` version, BunkerWeb supports multiple listening ports for the `stream` mode. You can specify them using the `LISTEN_STREAM_PORT` and `LISTEN_STREAM_PORT_SSL` settings.

    Here is an example :

    ```conf
    ...
    LISTEN_STREAM_PORT=4242
    LISTEN_STREAM_PORT_SSL=4343
    LISTEN_STREAM_PORT_1=4244
    LISTEN_STREAM_PORT_SSL_1=4344
    ...
    ```

=== "All-in-one"

    You will need to add the settings to the environment variables when running the All-in-one container. You will also need to expose the stream ports.

    This example configures BunkerWeb to proxy two stream-based applications, `app1.example.com` and `app2.example.com`.

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -e SERVICE_UI="no" \
        -e SERVER_NAME="app1.example.com app2.example.com" \
        -e MULTISITE="yes" \
        -e USE_REVERSE_PROXY="yes" \
        -e SERVER_TYPE="stream" \
        -e app1.example.com_REVERSE_PROXY_HOST="myapp1:9000" \
        -e app1.example.com_LISTEN_STREAM_PORT="10000" \
        -e app2.example.com_REVERSE_PROXY_HOST="myapp2:9000" \
        -e app2.example.com_LISTEN_STREAM_PORT="20000" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        -p 10000:10000/tcp \
        -p 20000:20000/tcp \
        bunkerity/bunkerweb-all-in-one:1.6.4
    ```

    Please note that if your container is already created, you will need to delete it and recreate it for the new environment variables to be applied.

    Your applications (`myapp1`, `myapp2`) should be running in separate containers (or be otherwise accessible) and their hostnames/IPs (e.g., `myapp1`, `myapp2` used in `_REVERSE_PROXY_HOST`) must be resolvable and reachable from the `bunkerweb-aio` container. This typically involves connecting them to a shared Docker network.

    !!! note "Deactivate UI Service"
        Deactivating the UI service (e.g., by setting `SERVICE_UI=no` as an environment variable) is recommended as the Web UI is not compatible with `SERVER_TYPE=stream`.

=== "Docker"

    When using Docker integration, the easiest way of protecting existing network applications is to add the services in the `bw-services` network :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.4
        ports:
          - "80:8080" # Keep it if you want to use Let's Encrypt automation when using http challenge type
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
        image: bunkerity/bunkerweb-scheduler:1.6.4
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
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
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
      bw-storage:

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

    Before running the [Docker autoconf integration](integrations.md#docker-autoconf) stack on your machine, you will need to edit the ports :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.4
        ports:
          - "80:8080" # Keep it if you want to use Let's Encrypt automation when using http challenge type
          - "10000:10000" # app1
          - "20000:20000" # app2
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
          - "bunkerweb.SERVER_TYPE=stream"
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
          - "bunkerweb.SERVER_TYPE=stream"
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

    Before running the [Swarm integration](integrations.md#swarm) stack on your machine, you will need to edit the ports :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.4
        ports:
          # Keep it if you want to use Let's Encrypt automation when using http challenge type
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
          - published: 20000
            target: 20000
            mode: host
            protocol: tcp
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
            - "bunkerweb.SERVER_TYPE=stream"
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
            - "bunkerweb.SERVER_TYPE=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    !!! example "Experimental feature"

        At the moment, [Ingresses](https://kubernetes.io/docs/concepts/services-networking/ingress/) does not support the `stream` mode. **What we are doing here is a workaround to make it work.**

        Feel free to test it and report us any bug using [issues](https://github.com/bunkerity/bunkerweb/issues) in the GitHub repository.

    Before running the [Kubernetes integration](integrations.md#kubernetes) stack on your machine, you will need to open the ports on your load balancer :

    ```yaml
    apiVersion: v1
    kind: Service
    metadata:
      name: lb
    spec:
      type: LoadBalancer
      ports:
        - name: http # Keep it if you want to use Let's Encrypt automation when using http challenge type
          port: 80
          targetPort: 8080
        - name: app1
          port: 10000
          targetPort: 10000
        - name: app2
          port: 20000
          targetPort: 20000
      selector:
        app: bunkerweb
    ```

    Once the stack is running, you can create your ingress resources :

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      namespace: services
      annotations:
        bunkerweb.io/SERVER_TYPE: "stream" # Will be applied to all services
        bunkerweb.io/app1.example.com_LISTEN_STREAM_PORT: "10000"
        bunkerweb.io/app2.example.com_LISTEN_STREAM_PORT: "20000"
    spec:
      rules:
        - host: app1.example.com
          http:
            paths:
              - path: / # This isn't used in stream mode but is required
                pathType: Prefix
                backend:
                  service:
                    name: svc-app1
                    port:
                      number: 9000
        - host: app2.example.com
          http:
            paths:
              - path: / # This isn't used in stream mode but is required
                pathType: Prefix
                backend:
                  service:
                    name: svc-app2
                    port:
                      number: 9000
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app1
      namespace: services
      labels:
        app: app1
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: app1
      template:
        metadata:
          labels:
            app: app1
        spec:
          containers:
            - name: app1
              image: istio/tcp-echo-server:1.3
              args: ["9000", "app1"]
              ports:
                - containerPort: 9000
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app1
      namespace: services
    spec:
      selector:
        app: app1
      ports:
        - protocol: TCP
          port: 9000
          targetPort: 9000
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app2
      namespace: services
      labels:
        app: app2
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: app2
      template:
        metadata:
          labels:
            app: app2
        spec:
          containers:
            - name: app2
              image: istio/tcp-echo-server:1.3
              args: ["9000", "app2"]
              ports:
                - containerPort: 9000
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app2
      namespace: services
    spec:
      selector:
        app: app2
      ports:
        - protocol: TCP
          port: 9000
          targetPort: 9000
    ```

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

    Now let's check the status of the Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    If they are already running, we can reload it :

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb-scheduler
    ```

### PHP

!!! example "Experimental feature"
	At the moment, PHP support with BunkerWeb is still in beta and we recommend you use a reverse-proxy architecture if you can. By the way, PHP is not supported at all for some integrations like Kubernetes.

BunkerWeb supports PHP using external or remote [PHP-FPM](https://www.php.net/manual/en/install.fpm.php) instances. We will assume that you are already familiar with managing that kind of services.

 The following settings can be used :

- `REMOTE_PHP` : Hostname of the remote PHP-FPM instance.
- `REMOTE_PHP_PATH` : Root folder containing files in the remote PHP-FPM instance.
- `REMOTE_PHP_PORT` : Port of the remote PHP-FPM instance (*default is 9000*).
- `LOCAL_PHP` : Path to the local socket file of PHP-FPM instance.
- `LOCAL_PHP_PATH` : Root folder containing files in the local PHP-FPM instance.

=== "All-in-one"

    When using the [All-in-one image](integrations.md#all-in-one-aio-image), to support PHP applications, you will need to :

    - Mount your PHP files into the `/var/www/html` folder of BunkerWeb.
    - Set up a PHP-FPM container for your application and mount the folder containing PHP files.
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as environment variables when running BunkerWeb.

    If you enable the [multisite mode](concepts.md#multisite-mode), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    └── app2.example.com
        └── index.php

    2 directories, 2 files
    ```

    We will assume that your PHP apps are located into a folder named `www`. Please note that you will need to fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33 if you use the `php:fpm` image) is the owner of the files and folders :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    You can now run BunkerWeb, configure it for your PHP application and also run the PHP apps. You will need to create a custom Docker network to allow BunkerWeb to communicate with your PHP-FPM containers.

    ```bash
    # Create a custom network
    docker network create php-network

    # Run PHP-FPM containers
    docker run -d --name myapp1-php --network php-network -v ./www/app1.example.com:/app php:fpm
    docker run -d --name myapp2-php --network php-network -v ./www/app2.example.com:/app php:fpm

    # Run BunkerWeb All-in-one
    docker run -d \
        --name bunkerweb-aio \
        --network php-network \
        -v ./www:/var/www/html \
        -v bw-storage:/data \
        -e SERVER_NAME="app1.example.com app2.example.com" \
        -e MULTISITE="yes" \
        -e REMOTE_PHP_PATH="/app" \
        -e app1.example.com_REMOTE_PHP="myapp1-php" \
        -e app2.example.com_REMOTE_PHP="myapp2-php" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.4
    ```

    Please note that if your container is already created, you will need to delete it and recreate it for the new environment variables to be applied.

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
        image: bunkerity/bunkerweb:1.6.4
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
        image: bunkerity/bunkerweb-scheduler:1.6.4
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
          - bw-storage:/data # This is used to persist the cache and other data like the backups
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
      bw-storage:

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
        image: bunkerity/bunkerweb:1.6.4
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
        image: bunkerity/bunkerweb-scheduler:1.6.4
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
          SERVER_NAME: "" # The server name will be filled with services labels
          MULTISITE: "yes" # Mandatory setting for autoconf
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.4
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
        # We set the max allowed packet size to avoid issues with large queries
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-docker

    volumes:
      bw-data:
      bw-storage:

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
        image: bunkerity/bunkerweb:1.6.4
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

    Now let's check the status of the Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    If they are already running, we can reload it :

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb-scheduler
    ```

### IPv6

!!! example "Experimental feature"

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
        image: bunkerity/bunkerweb-scheduler:1.6.4
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

    If they are already running, we can restart it :

    ```shell
    systemctl restart bunkerweb
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb
    ```

## Security tuning

BunkerWeb offers many security features that you can configure with [settings](features.md). Even if the default values of settings ensure a minimal "security by default", we strongly recommend you tune them. By doing so you will be able to ensure the security level of your choice but also manage false positives.

!!! tip "Other settings"
    This section only focuses on security tuning, see the [settings section](features.md) of the documentation for other settings.

<figure markdown>
  ![Overview](assets/img/core-order.svg){ align=center }
  <figcaption>Overview and order of the core security plugins</figcaption>
</figure>

## CrowdSec Console integration

If you aren’t already familiar with CrowdSec Console integration, [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) leverages crowdsourced intelligence to combat cyber threats. Think of it as the "Waze of cybersecurity"—when one server is attacked, other systems worldwide are alerted and protected from the same attackers. You can learn more about it [here](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

**Congratulations, your BunkerWeb instance is now enrolled in your CrowdSec Console!**

Pro tip: When viewing your alerts, click the "columns" option and check the "context" checkbox to access BunkerWeb-specific data.

<figure markdown>
  ![Overview](assets/img/crowdity4.png){ align=center }
  <figcaption>BunkerWeb data shown in the context column</figcaption>
</figure>

## Monitoring and reporting

#### Monitoring <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

#### Prometheus exporter <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

#### Reporting <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

### Backup and restore

#### Backup S3 <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

##### Manual backup

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

##### Manual restore

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

### Migration <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :white_check_mark:

The Migration plugin **revolutionizes** BunkerWeb configuration transfers between instances with its **user-friendly web interface**, simplifying the entire migration journey. Whether you're upgrading systems, scaling infrastructure, or transitioning environments, this tool empowers you to effortlessly transfer **settings, preferences, and data** with unmatched ease and confidence. Say goodbye to cumbersome manual processes and hello to a **seamless, hassle-free migration experience**.

**List of features**

- **Effortless Migration:** Easily transfer BunkerWeb configurations between instances without the complexities of manual procedures.

- **Intuitive Web Interface:** Navigate through the migration process effortlessly with a user-friendly web interface designed for intuitive operation.

- **Cross-Database Compatibility:** Enjoy seamless migration across various database platforms, including SQLite, MySQL, MariaDB, and PostgreSQL, ensuring compatibility with your preferred database environment.

#### Create a migration file

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

#### Initialize a migration

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

=== "All-in-one"

    1. Copy the migration file to the container:

        ```bash
        docker cp /path/to/migration/file bunkerweb-aio:/path/to/migration/file
        ```

    2. Initialize the migration:

        ```bash
        docker exec -it bunkerweb-aio bwcli plugin migration migrate /path/to/migration/file
        ```

This command seamlessly migrates your BunkerWeb data to precisely match the configuration outlined in the migration file.

## Anti DDoS <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :x:

The **Anti DDoS** Plugin provides advanced protection against Distributed Denial of Service (DDoS) attacks by monitoring, analyzing, and filtering suspicious traffic in real-time.

By employing a **sliding window mechanism**, the plugin maintains an in-memory dictionary of request timestamps to detect abnormal traffic spikes from individual IP addresses. Based on the configured security mode, it can either block offending connections or log the suspicious activity for further review.

#### Features

- **Real-Time Traffic Analysis:** Continuously monitors incoming requests to detect potential DDoS attacks.
- **Sliding Window Mechanism:** Tracks recent request activity within a configurable time window.
- **Configurable Thresholds:** Allows you to define the maximum number of suspicious requests per IP.
- **Advanced Blocking Logic:** Evaluates both per-IP request counts and the number of distinct IPs exceeding the threshold.
- **Flexible Security Modes:** Choose between immediate connection blocking or detection-only (logging) mode.
- **Optimized In-Memory Datastore:** Ensures high-speed lookups and efficient metric tracking.
- **Automatic Housekeeping:** Periodically clears outdated data to maintain optimal performance.

#### Configuration

Customize the plugin behavior using the following settings:

| Setting                      | Default       | Context | Multiple | Description                                                                                    |
| ---------------------------- | ------------- | ------- | -------- | ---------------------------------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`          | global  | no       | Enable or disable the Anti DDoS protection. Set to `"yes"` to activate the plugin.             |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`         | global  | no       | Size of the in-memory datastore for tracking DDoS metrics (e.g., `10M`, `500k`).               |
| `ANTIDDOS_THRESHOLD`         | `100`         | global  | no       | Maximum number of suspicious requests allowed per IP within the defined time window.           |
| `ANTIDDOS_WINDOW_TIME`       | `10`          | global  | no       | Time window in seconds during which suspicious requests are tallied.                           |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444` | global  | no       | HTTP status codes considered suspicious and used to trigger anti-DDoS actions.                 |
| `ANTIDDOS_DISTINCT_IP`       | `5`           | global  | no       | Minimum number of distinct IPs that must exceed the threshold before enforcing the block mode. |

#### Best Practices

- **Threshold Tuning:** Adjust `ANTIDDOS_THRESHOLD` and `ANTIDDOS_WINDOW_TIME` based on your typical traffic patterns.
- **Status Code Review:** Regularly update `ANTIDDOS_STATUS_CODES` to capture new or evolving suspicious behaviors.
- **Monitoring:** Analyze logs and metrics periodically to fine-tune settings and improve overall protection.

## User Manager <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

The User Management Plugin offers a robust interface for administering user accounts within your system.

With this plugin, administrators can effortlessly create, update, and disable user accounts, manage user roles, toggle two-factor authentication (2FA), and view detailed user information such as last login timestamps and account statuses (active or inactive). Designed with security and ease-of-use in mind, this plugin simplifies routine user management tasks while ensuring compliance and auditability.

#### Features

- **User Account Operations:** Import in CSV/XSLX format, Create, edit, and delete user accounts with ease.
- **Role-Based Access Control:** Assign and modify user roles to manage permissions and access levels.
- **2FA Management:** Disable two-factor authentication based on administrative decisions.
- **Comprehensive User Insights:** Monitor key user data including last login times, account creation dates, and active/inactive status.
- **Audit Logging:** Maintain an audit trail for all user management actions for enhanced security and compliance.

<figure markdown>
  ![Overview](assets/img/user-manager.png){ align=center }
  <figcaption>User Manager page</figcaption>
</figure>

<figure markdown>
  ![Create user form](assets/img/user-manager-create.png){ align=center }
  <figcaption>User Manager - Create user form</figcaption>
</figure>

<figure markdown>
  ![Activities page](assets/img/user-manager-activities.png){ align=center }
  <figcaption>User Manager - Activities page</figcaption>
</figure>
