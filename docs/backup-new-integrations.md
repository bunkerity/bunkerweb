****** INTEGRATIONS ******
=== "RHEL"

    The first step is to add NGINX official repository. Create the following file at `/etc/yum.repos.d/nginx.repo` :
    ```conf
    [nginx-stable]
    name=nginx stable repo
    baseurl=http://nginx.org/packages/centos/$releasever/$basearch/
    gpgcheck=1
    enabled=1
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true
	```

  You should now be able to install NGINX 1.20.2 :
	```shell
	sudo dnf install nginx-1.20.2
	```

	And finally install BunkerWeb 1.4.8 :
  ```shell
	wget https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm && \
  rpm -Uvh epel-release*rpm && \
  curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.rpm.sh | sudo bash && \
  sudo dnf check-update && \
  sudo dnf install -y bunkerweb-1.4.8
  ```

	To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command :
	```shell
	sudo dnf versionlock add nginx && \
	sudo dnf versionlock add bunkerweb
	```

## Vagrant

<figure markdown>
  ![Overwiew](assets/img/integration-ansible.svg){ align=center }
  <figcaption>Vagrant integration</figcaption>
</figure>

List of supported Linux distros :

- Ubuntu 22.04 "Jammy"

[Vagrant](https://www.vagrantup.com/docs) is a tool for building and managing virtual machine environments in a single workflow. With an easy-to-use workflow and focus on automation, Vagrant lowers development environment setup time, increases production parity, and makes the "works on my machine" excuse a relic of the past.

A specific BunkerWeb box is available on vagrantup.

First of all download the box from vagrantup : ```shell vagrant box add bunkerity/bunkerity```

Then an list of boxes should appear, select the one whith your provider (virtualbox, vmware, libvirt).

This will download the box named bunkerity/bunkerity from [HashiCorp's Vagrant Cloud box catalog](https://vagrantcloud.com/boxes/search), where you can find and host boxes.

Now you've added a box to Vagrant either by initializing or adding it explicitly, you need to configure your project to use it as a base. 
For initializing a new Vagrant project, you can use the `vagrant init bunkerity/bunkerity` command. This will create a Vagrantfile in the current directory.

Open the Vagrantfile and replace the contents with the following.

  ```shell
  Vagrant.configure("2") do |config|
    config.vm.box = "bunkerity/bunkerity"
  end
  ```

Vagrant will automatically download the box in his latest version and add it to your Vagrant environment. If you want to use a specific version of the box, you can use the `config.vm.box_version` option.

For exemple:

  ```shell
  Vagrant.configure("2") do |config|
    config.vm.box = "bunkerity/bunkerity"
    config.vm.box_version = "1.4.2"
  end
  ```

Now you can start the box :
```shell
vagrant up
```

And then connect to it :
```shell
vagrant ssh
```

****** QUICKSTART ******

=== "Vagrant"

    We will assume that you already have the [Vagrant integration](/1.4/integrations/#vagrant) stack running on your machine.

    The following command will run a basic HTTP server on the port 8000 and deliver the files in the current directory :
		```shell
		python3 -m http.server -b 127.0.0.1
		```

    Configuration of BunkerWeb is done by editing the `/opt/bunkerweb/variables.env` file.

	Connect to your vagrant machine :
	```shell
	vagrant ssh
	```

	And then you can edit the `variables.env` file in your host machine like this :

	```conf
	SERVER_NAME=www.example.com
	HTTP_PORT=80
	HTTPS_PORT=443
	DNS_RESOLVERS=8.8.8.8 8.8.4.4
	USE_REVERSE_PROXY=yes
	REVERSE_PROXY_URL=/
	REVERSE_PROXY_HOST=http://127.0.0.1:8000
	```

    If it's already running we can restart it :
    ```shell
    systemctl restart bunkerweb
    ```

    Otherwise, we will need to start it :
    ```shell
    systemctl start bunkerweb
    ```

    Let's check the status of BunkerWeb :
    ```shell
    systemctl status bunkerweb
    ```

=== "Vagrant"

    We will assume that you already have the [Vagrant integration](/1.4/integrations/#Vagrant) stack running on your machine with some web applications running on the same machine as BunkerWeb.

	Let's assume that you have some web applications running on the same machine as BunkerWeb :

    === "App #1"
    	The following command will run a basic HTTP server on the port 8001 and deliver the files in the current directory :
		```shell
		python3 -m http.server -b 127.0.0.1 8001
		```

    === "App #2"
    	The following command will run a basic HTTP server on the port 8002 and deliver the files in the current directory :
    	```shell
    	python3 -m http.server -b 127.0.0.1 8002
    	```

    === "App #3"
    	The following command will run a basic HTTP server on the port 8003 and deliver the files in the current directory :
    	```shell
    	python3 -m http.server -b 127.0.0.1 8003
    	```

	Connect to your vagrant machine :
	```shell
	vagrant ssh
	```

    Configuration of BunkerWeb is done by editing the /opt/bunkerweb/variables.env file :
	```conf
	SERVER_NAME=app1.example.com app2.example.com app3.example.com
	HTTP_PORT=80
	HTTPS_PORT=443
	MULTISITE=yes
	DNS_RESOLVERS=8.8.8.8 8.8.4.4
	USE_REVERSE_PROXY=yes
	REVERSE_PROXY_URL=/
	app1.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8001
	app2.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8002
	app3.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:8003
	```

    If it's already running we can restart it :
    ```shell
    systemctl restart bunkerweb
    ```

    Otherwise, we will need to start it :
    ```shell
    systemctl start bunkerweb
    ```

    Let's check the status of BunkerWeb :
    ```shell
    systemctl status bunkerweb
    ```

=== "Vagrant"

    You will need to add the settings to the `/opt/bunkerweb/variables.env` file :

	```conf
	...
	USE_REAL_IP=yes
	REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
	REAL_IP_HEADER=X-Forwarded-For
	...
	```

    Don't forget to restart the BunkerWeb service once it's done.

=== "Vagrant"

    You will need to add the settings to the `/opt/bunkerweb/variables.env` file :

	```conf
	...
	USE_REAL_IP=yes
	USE_PROXY_PROTOCOL=yes
	REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
	REAL_IP_HEADER=proxy_protocol
	...
	```

    Don't forget to restart the BunkerWeb service once it's done.

=== "Vagrant"

    When using the [Vagrant integration](/1.4/integrations/#vagrant), custom configurations must be written to the `/opt/bunkerweb/configs` folder.

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
    chown -R root:nginx /opt/bunkerweb/configs && \
    chmod -R 770 /opt/bunkerweb/configs
    ```

    Don't forget to restart the BunkerWeb service once it's done.

=== "Vagrant"

    We will assume that you already have the [Vagrant integration](/1.4/integrations/#vagrant) stack running on your machine.

    By default, BunkerWeb will search for web files inside the `/opt/bunkerweb/www` folder. You can use it to store your PHP application. Please note that you will need to configure your PHP-FPM service to get or set the user/group of the running processes and the UNIX socket file used to communicate with BunkerWeb.

	First of all, you will need to make sure that your PHP-FPM instance can access the files inside the `/opt/bunkerweb/www` folder and also that BunkerWeb can access the UNIX socket file in order to communicate with PHP-FPM. We recommend to set a different user like `www-data` for the PHP-FPM service and to give the nginx group access to the UNIX socket file. Here is corresponding PHP-FPM configuration :
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
	systemctl restart php8.1-fpm
	```

	Once your application is copied to the `/opt/bunkerweb/www` folder, you will need to fix the permissions so BunkerWeb (user/group nginx) can at least read files and list folders and PHP-FPM (user/group www-data) is the owner of the files and folders : 
	```shell
	chown -R www-data:nginx /opt/bunkerweb/www && \
	find /opt/bunkerweb/www -type f -exec chmod 0640 {} \; && \
	find /opt/bunkerweb/www -type d -exec chmod 0750 {} \;
	```

	You can now edit the `/opt/bunkerweb/variable.env` file :
	```env
	HTTP_PORT=80
	HTTPS_PORT=443
	DNS_RESOLVERS=8.8.8.8 8.8.4.4
	SERVER_NAME=www.example.com
	AUTO_LETS_ENCRYPT=yes
	LOCAL_PHP=/run/php/php-fpm.sock
	LOCAL_PHP_PATH=/opt/bunkerweb/www/	
	```

    Let's check the status of BunkerWeb :
    ```shell
    systemctl status bunkerweb
    ```
    If it's already running we can restart it :
    ```shell
    systemctl restart bunkerweb
    ```

	Otherwise, we will need to start it : 
    ```shell
    systemctl start bunkerweb
    ```

    === "Vagrant"

	We will assume that you already have the [Vagrant integration](/1.4/integrations/#vagrant) stack running on your machine.

    By default, BunkerWeb will search for web files inside the `/opt/bunkerweb/www` folder. You can use it to store your PHP applications : each application will be in its own subfolder named the same as the primary server name. Please note that you will need to configure your PHP-FPM service to get or set the user/group of the running processes and the UNIX socket file used to communicate with BunkerWeb.

	First of all, you will need to make sure that your PHP-FPM instance can access the files inside the `/opt/bunkerweb/www` folder and also that BunkerWeb can access the UNIX socket file in order to communicate with PHP-FPM. We recommend to set a different user like `www-data` for the PHP-FPM service and to give the nginx group access to the UNIX socket file. Here is corresponding PHP-FPM configuration :
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
	systemctl restart php8.1-fpm
	```

	Once your application is copied to the `/opt/bunkerweb/www` folder, you will need to fix the permissions so BunkerWeb (user/group nginx) can at least read files and list folders and PHP-FPM (user/group www-data) is the owner of the files and folders : 
	```shell
	chown -R www-data:nginx /opt/bunkerweb/www && \
	find /opt/bunkerweb/www -type f -exec chmod 0640 {} \; && \
	find /opt/bunkerweb/www -type d -exec chmod 0750 {} \;
	```

	You can now edit the `/opt/bunkerweb/variable.env` file :
	```env
	HTTP_PORT=80
	HTTPS_PORT=443
	DNS_RESOLVERS=8.8.8.8 8.8.4.4
	SERVER_NAME=app1.example.com app2.example.com app3.example.com
	MULTISITE=yes
	AUTO_LETS_ENCRYPT=yes
	app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
	app1.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app1.example.com
	app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
	app2.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app2.example.com
	app3.example.com_LOCAL_PHP=/run/php/php-fpm.sock
	app3.example.com_LOCAL_PHP_PATH=/opt/bunkerweb/www/app3.example.com
	```

    Let's check the status of BunkerWeb :
    ```shell
    systemctl status bunkerweb
    ```
    If it's already running we can restart it :
    ```shell
    systemctl restart bunkerweb
    ```

	Otherwise, we will need to start it : 
    ```shell
    systemctl start bunkerweb
    ```

****** PLUGINS ****** 

=== "Vagrant"

    When using the [Linux integration](/1.4/integrations/#linux), plugins must be written to the `/opt/bunkerweb/plugins` folder :
    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /data/plugins
    ```

****** UI ****** 

=== "Vagrant"

    The installation of the web UI using the [Vagrant integration](/1.4/integrations/#vagrant) is pretty straightforward because it is installed with BunkerWeb.

    The first thing to do is to edit the BunkerWeb configuration located at **/opt/bunkerweb/variables.env** to add settings related to the web UI :
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

    You can edit the **/opt/bunkerweb/ui.env** file containing the settings of the web UI :
    ```conf
    ADMIN_USERNAME=admin
    ADMIN_PASSWORD=changeme
    ABSOLUTE_URI=http(s)://bwadm.example.com/changeme/
    ```

    Important things to note :

    * `http(s)://bwadmin.example.com/changeme/` is the full base URL of the web UI (must match the sub(domain) and /changeme URL used in **/opt/bunkerweb/variables.env**)
    * replace the username `admin` and password `changeme` with strong ones

    Restart the BunkerWeb UI service and you are now ready to access it :
	```shell
	systemctl restart bunkerweb-ui
	```

****** TROUBLE ******

=== "Vagrant"

    For errors related to BunkerWeb services (e.g. not starting), you can use `journalctl` :
    ```shell
    journalctl -u bunkerweb --no-pager
    ```

    Common logs are located inside the `/var/log/nginx` directory :
    ```shell
    cat /var/log/nginx/error.log
    cat /var/log/nginx/access.log
    ```

=== "Vagrant"

    You can use the `bwcli` command (as root) :
    ```shell
    sudo bwcli unban 1.2.3.4
    ```