# Plugins

BunkerWeb comes with a plugin system to make it possible to easily add new features. Once a plugin is installed, you can manage it using additional settings defined by the plugin.

## Official plugins

Here is the list of "official" plugins that we maintain (see the [bunkerweb-plugins](https://github.com/bunkerity/bunkerweb-plugins) repository for more information) :

|      Name      | Version | Description                                                                                                                      |                                                 Link                                                  |
| :------------: | :-----: | :------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------: |
|   **ClamAV**   |   0.1   | Automatically scans uploaded files with the ClamAV antivirus engine and denies the request when a file is detected as malicious. |     [bunkerweb-plugins/clamav](https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav)     |
|  **CrowdSec**  |   0.1   | CrowdSec bouncer for BunkerWeb.                                                                                                  |   [bunkerweb-plugins/crowdsec](https://github.com/bunkerity/bunkerweb-plugins/tree/main/crowdsec)   |
| **Discord** | 0.1 | Send security notifications to a Discord channel using a Webhook. | [bunkerweb-plugins/discord](https://github.com/bunkerity/bunkerweb-plugins/tree/main/discord) |
| **Slack** | 0.1 | Send security notifications to a Slack channel using a Webhook. | [bunkerweb-plugins/slack](https://github.com/bunkerity/bunkerweb-plugins/tree/main/slack) |
| **VirusTotal** |   0.1   | Automatically scans uploaded files with the VirusTotal API and denies the request when a file is detected as malicious.          | [bunkerweb-plugins/virustotal](https://github.com/bunkerity/bunkerweb-plugins/tree/main/virustotal) |

## How to use a plugin

### Automatic

If you want to quickly install external plugins, you can use the `EXTERNAL_PLUGIN_URLS` setting. It takes a list of URLs, separated with space, pointing to compressed (zip format) archive containing one or more plugin(s).

You can use the following value if you want to automatically install the official plugins : `EXTERNAL_PLUGIN_URLS=https://github.com/bunkerity/bunkerweb-plugins/archive/refs/tags/v0.2.zip`

### Manual

The first step is to install the plugin by putting the plugin files inside the corresponding `plugins` data folder, the procedure depends on your integration :

=== "Docker"

    When using the [Docker integration](/1.4/integrations/#docker), plugins must be written to the volume mounted on `/data`.

    The first thing to do is to create the plugins folder :
    ```shell
    mkdir -p ./bw-data/plugins
    ```

    Then you can drop the plugins of your choice into that folder :
    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    Because BunkerWeb runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :
    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    When starting the BunkerWeb container, you will need to mount the folder on `/data` :
    ```shell
    docker run \
    	   ...
    	   -v "${PWD}/bw-data:/data" \
    	   ...
    	   bunkerity/bunkerweb:1.4.2
    ```

    Here is the docker-compose equivalent :
    ```yaml
    mybunker:
      image: bunkerity/bunkerweb:1.4.2
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Docker autoconf"

    When using the [Docker autoconf integration](/1.4/integrations/#docker-autoconf), plugins must be written to the volume mounted on `/data`.

    The easiest way to do it is by starting the Docker autoconf stack with a folder mounted on `/data` (instead of a named volume). Once the stack is started, you can copy the plugins of your choice to the `plugins` folder from your host :
    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    Because BunkerWeb runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :
    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

=== "Swarm"

    When using the [Swarm integration](/1.4/integrations/#swarm), the easiest way of installing plugins is by using `docker exec` and downloading the plugins from the container.

    Execute a shell inside the autoconf container (use `docker ps` to get the name) :
    ```shell
    docker exec -it myautoconf /bin/bash
    ```

    Once you have a shell inside the container, you can drop the plugins of your choice inside the `/data/plugins` folder :
    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /data/plugins
    ```

=== "Kubernetes"

    When using the [Kubernetes integration](/1.4/integrations/#kubernetes), the easiest way of installing plugins is by using `kubectl exec` and downloading the plugins from the container.

    Execute a shell inside the autoconf container (use `kubectl get pods` to get the name) :
    ```shell
    kubectl exec -it myautoconf -- /bin/bash
    ```

    Once you have a shell inside the container, you can drop the plugins of your choice inside the `/data/plugins` folder :
    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /data/plugins
    ```

=== "Linux"

    When using the [Linux integration](/1.4/integrations/#linux), plugins must be written to the `/opt/bunkerweb/plugins` folder :
    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /data/plugins
    ```

=== "Ansible"
    When using the [Ansible integration](/1.4/integrations/#ansible), you can use the `plugins` variable to set a local folder containing your plugins that will be copied to your BunkerWeb instances.
	
	Let's assume that you have plugins inside the `bunkerweb-plugins` folder :
	```shell
	git clone https://github.com/bunkerity/bunkerweb-plugins
	```

	In your Ansible inventory, you can use the `plugins` variable to set the path of plugins folder : 
    ```ini
	[mybunkers]
	192.168.0.42 ... plugins="{{ playbook_dir }}/bunkerweb-plugins"
    ```
	
	Or alternatively, in your playbook file :
	```yaml
	- hosts: all
	  become: true
	  vars:
		- variables_env: "{{ playbook_dir }}/my_variables.env"
	  roles:
		- bunkerweb
	```

	Run the playbook :
	```shell
	ansible-playbook -i inventory.yml playbook.yml
	```

## Writing a plugin

!!! tip "Existing plugins"

    If the documentation is not enough you can have a look at the existing source code of [official plugins](https://github.com/bunkerity/bunkerweb-plugins) and the [core plugins](https://github.com/bunkerity/bunkerweb/tree/master/core) (already included in BunkerWeb but they are plugins technically speaking).

The first step is to create a folder that will contain the plugin :

```shell
mkdir myplugin && \
cd myplugin
```

### Metadata

A file named **plugin.json** and written at the root of the plugin folder must contain metadata about the plugin. Here is an example :

```json
{
	"id": "myplugin",
	"order": 42,
	"name": "My Plugin",
	"description": "Just an example plugin.",
	"version": "1.0",
	"settings": {
		"DUMMY_SETTING": {
			"context": "multisite",
			"default": "1234",
			"help": "Here is the help of the setting.",
			"id": "dummy-id",
			"label": "Dummy setting",
			"regex": "^.*$",
			"type": "text"
		}
	}
	"jobs": [
		{
			"name": "my-job",
			"file": "my-job.py",
			"every": "hour"
		}
	]
}
```

Here are the details of the fields :

|     Field     | Mandatory |  Type  | Description                                                                                                                                                                                        |
| :-----------: | :-------: | :----: | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|     `id`      |    yes    | string | Internal ID for the plugin : must be unique among other plugins (including "core" ones) and contain only lowercase chars.                                                                          |
|    `order`    |    yes    |  int   | When the plugin should be executed during the access phase : `1` for whitelisting, `2` for blacklisting, `3` for "standard security feature" or `999` if your settings don't use the access phase. |
|    `name`     |    yes    | string | Name of your plugin.                                                                                                                                                                               |
| `description` |    yes    | string | Description of your plugin.                                                                                                                                                                        |
|   `version`   |    yes    | string | Version of your plugin.                                                                                                                                                                            |
|  `settings`   |    yes    |  dict  | List of the settings of your plugin.                                                                                                                                                               |
|    `jobs`     |    no     |  list  | List of the jobs of your plugin.                                                                                                                                                                   |

Each setting has the following fields (the key is the ID of the settings used in a configuration) :

|   Field    | Mandatory |  Type  | Description                                                  |
| :--------: | :-------: | :----: | :----------------------------------------------------------- |
| `context`  |    yes    | string | Context of the setting : `multisite` or `global`.            |
| `default`  |    yes    | string | The default value of the setting.                            |
|   `help`   |    yes    | string | Help text about the plugin (shown in web UI).                |
|    `id`    |    yes    | string | Internal ID used by the web UI for HTML elements.            |
|  `label`   |    yes    | string | Label shown by the web UI.                                   |
|  `regex`   |    yes    | string | The regex used to validate the value provided by the user.   |
|   `type`   |    yes    | string | The type of the field : `text`, `check` or `select`.         |
| `multiple` |    no     | string | Unique ID to group multiple settings with numbers as suffix. |
|  `select`  |    no     |  list  | List of possible string values when `type` is `select`.      |

Each job has the following fields :

|  Field  | Mandatory |  Type  | Description                                                                                                                             |
| :-----: | :-------: | :----: | :-------------------------------------------------------------------------------------------------------------------------------------- |
| `name`  |    yes    | string | Name of the job.                                                                                                                        |
| `file`  |    yes    | string | Name of the file inside the jobs folder.                                                                                                |
| `every` |    yes    | string | Job scheduling frequency : `minute`, `hour`, `day`, `week` or `once` (no frequency, only once before (re)generating the configuration). |

### Configurations

You can add custom NGINX configurations by adding a folder named **confs** with content similar to the [custom configurations](/1.4/quickstart-guide/#custom-configurations). Each subfolder inside the **confs** will contain [jinja2](https://jinja.palletsprojects.com) templates that will be generated and loaded at the corresponding context (`http`, `server-http` and `default-server-http`).

Here is an example for a configuration template file inside the **confs/server-http** folder named **example.conf** :

```conf
location /setting {
	default_type 'text/plain';
    content_by_lua_block {
        ngx.say('{{ DUMMY_SETTING }}')
    }
}
```

`{{ DUMMY_SETTING }}` will be replaced by the value of the `DUMMY_SETTING` chosen by the user of the plugin.

### LUA

#### Main script

Under the hood, BunkerWeb is using the [NGINX LUA module](https://github.com/openresty/lua-nginx-module) to execute code within NGINX. Plugins that need to execute code must provide a lua file at the root directory of the plugin folder using the `id` value of **plugin.json** as its name. Here is an example named **myplugin.lua** :

```lua
local _M		= {}
_M.__index		= _M

local utils		= require "utils"
local datastore	= require "datastore"
local logger	= require "logger"

function _M.new()
	local self = setmetatable({}, _M)
	self.dummy = "dummy"
	return self, nil
end

function _M:init()
	logger.log(ngx.NOTICE, "MYPLUGIN", "init called")
	return true, "success"
end

function _M:access()
	logger.log(ngx.NOTICE, "MYPLUGIN", "access called")
	return true, "success", nil, nil
end

function _M:log()
	logger.log(ngx.NOTICE, "MYPLUGIN", "log called")
	return true, "success"
end

function _M:log_default()
	logger.log(ngx.NOTICE, "MYPLUGIN", "log_default called")
	return true, "success"
end

return _M
```

The declared functions are automatically called during specific contexts. Here are the details of each function :

| Function |                                   Context                                    | Description                                                                                                                                               | Return value                                                                                                                                                                                                                                                                                                                            |
| :------: | :--------------------------------------------------------------------------: | :-------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|  `init`  |   [init_by_lua](https://github.com/openresty/lua-nginx-module#init_by_lua)   | Called when NGINX just started or received a reload order. the typical use case is to prepare any data that will be used by your plugin.                  | `ret`, `err`<ul><li>`ret` (boolean) : true if no error else false</li><li>`err` (string) : success or error message</li></ul>                                                                                                                                                                                                           |
| `access` | [access_by_lua](https://github.com/openresty/lua-nginx-module#access_by_lua) | Called on each request received by the server. The typical use case is to do the security checks here and deny the request if needed.                     | `ret`, `err`, `return`, `status`<ul><li>`ret` (boolean) : true if no error else false</li><li>`err` (string) : success or error message</li><li>`return` (boolean) : true if you want to stop the access phase and send a status to the client</li><li>`status` (number) : the return value to set if `return` is set to true</li></ul> |
|  `log`   |    [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)    | Called when a request has finished (and before it gets logged to the access logs). The typical use case is to make stats or compute counters for example. | `ret`, `err`<ul><li>`ret` (boolean) : true if no error else false</li><li>`err` (string) : success or error message</li></ul>                                                                                                                                                                                                           |
|  `log_default`   |    [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)    | Same as `log` but only called on the default server. | `ret`, `err`<ul><li>`ret` (boolean) : true if no error else false</li><li>`err` (string) : success or error message</li></ul>                                                                                                                                                                                                           |

#### Libraries

All directives from [NGINX LUA module](https://github.com/openresty/lua-nginx-module) are available. On top of that, you can use the LUA libraries included within BunkerWeb : see [this script](https://github.com/bunkerity/bunkerweb/blob/master/deps/clone.sh) for the complete list.

If you need additional libraries, you can put them in the root folder of the plugin and access them by prefixing them with your plugin ID. Here is an example file named **mylibrary.lua** :

```lua
local _M = {}

_M.dummy = function ()
	return "dummy"
end

return _M
```

And here is how you can use it from the **myplugin.lua** file :

```lua
local mylibrary = require "myplugin.mylibrary"

...

mylibrary.dummy()

...
```

#### Helpers

Some helpers modules provide common helpful functions :

- **datastore** : access the global shared data (key/value store)
- **logger** : generate logs
- **utils** : various useful functions

To access the functions, you first need to **require** the module :

```lua
...

local utils		= require "utils"
local datastore	= require "datastore"
local logger	= require "logger"

...
```

Retrieve a setting value :

```lua
local value, err = utils:get_variable("DUMMY_SETTING")
if not value then
	logger.log(ngx.ERR, "MYPLUGIN", "can't retrieve setting DUMMY_SETTING : " .. err)
else
	logger.log(ngx.NOTICE, "MYPLUGIN", "DUMMY_SETTING = " .. value)
end
```

Store something in the cache :

```lua
local ok, err = datastore:set("plugin_myplugin_something", "somevalue")
if not value then
	logger.log(ngx.ERR, "MYPLUGIN", "can't save plugin_myplugin_something into datastore : " .. err)
else
	logger.log(ngx.NOTICE, "MYPLUGIN", "successfully saved plugin_myplugin_something into datastore into datastore")
end
```

Check if an IP address is global :

```lua
local ret, err = utils.ip_is_global(ngx.var.remote_addr)
if ret == nil then
	logger.log(ngx.ERR, "MYPLUGIN", "error while checking if IP " .. ngx.var.remote_addr .. " is global or not : " .. err)
elseif not ret then
	logger.log(ngx.NOTICE, "MYPLUGIN", "IP " .. ngx.var.remote_addr .. " is not global")
else
	logger.log(ngx.NOTICE, "MYPLUGIN", "IP " .. ngx.var.remote_addr .. " is global")
end
```

!!! tip "More examples"

    If you want to see the full list of available functions, you can have a look at the files present in the [lua directory](https://github.com/bunkerity/bunkerweb/tree/master/lua) of the repository.

### Jobs

BunkerWeb uses an internal job scheduler for periodic tasks like renewing certificates with certbot, downloading blacklists, downloading MMDB files, ... You can add tasks of your choice by putting them inside a subfolder named **jobs** and listing them in the **plugin.json** metadata file. Don't forget to add the execution permissions for everyone to avoid any problems when a user is cloning and installing your plugin.

### Plugin page

Plugin pages are used to display information about your plugin. You can create a page by creating a subfolder named **ui** next to the file **plugin.json** and putting a **template.html** file inside it. The template file will be used to display the page.

A plugin page can have a form that is used to submit data to the plugin. To get the values of the form, you need to put a **actions.py** file in the **ui** folder. Inside the file, **you must define a function that has the same name as the plugin**. This function will be called when the form is submitted. You can then use the **request** object (from the library flask) to get the values of the form. The form's action must finish with **/plugins/<*plugin_id*>**. We recommend to use the url_for function to generate the action URL to avoid any problems. Like this : **{{ url_for('plugins') }}/<*plugin_id*>**.

!!! info "Template variables"

    Your template file can use template variables to display the content of your plugin. Like *Jinja2*, the template variables can be accessed by using the `{{` and `}}` delimiters. To use template variables, your custom function must return a dictionary with the template variables. The dictionary keys are the template variables names and the values are the values to display. Example :
    ```json
    {
        "foo": "bar"
    }
    ```
    ```html
    <html>
        <body>
            <p>{{ foo }}</p>
        </body>
    </html>
    ```
    Will display : `bar`

If you want to submit your form through a POST request, you need to add the following line to your form :

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
```

Otherwise, the form will not be submitted because of the CSRF token protection.

!!! tip "Plugins pages"

    Plugins pages are displayed in the **Plugins** section of the Web UI.

!!! info "Useful information"

    You can use Python libraries in your **actions.py** file. You just have to **import** them. Here are the main list of available libraries :
    `Flask`, `Flask-Login`, `Flask-WTF`, `beautifulsoup4`, `docker`, `Jinja2`, `python-magic` and `requests`. To see the full list, you can have a look at the Web UI [requirements.txt](https://github.com/bunkerity/bunkerweb/blob/master/ui/requirements.txt)

    In your **template.html** file, you can use the following functions :
    `csrf_token` and `url_for`

For example, I have a plugin called **myplugin** and I want to create a custom page. I just have to create a subfolder called **ui** and put a **template.html** file inside it. I want my plugin to display a form that will submit the data to the plugin. I can then use the **request** object (from the library flask) to get the values of the form. For that I create a **actions.py** file in the same **ui** folder as my **template.html** file. I define a function called **myplugin** that returns a dictionary with the template variables I want to display.

```html
<html>
    <body>
        <p>{{ foo }}</p>
        <form action="{{ url_for('plugins') }}/myplugin" method="POST">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
            <input type="text" name="foo" />
            <input type="submit" value="Submit" />
        </form>
    </body>
</html>
```

```python
from flask import request

def myplugin():
    return {
        "foo": request.form["foo"]
    }
```