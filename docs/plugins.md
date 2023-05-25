# Plugins

BunkerWeb comes with a plugin system making it possible to easily add new features. Once a plugin is installed, you can manage it using additional settings defined by the plugin.

## Official plugins

Here is the list of "official" plugins that we maintain (see the [bunkerweb-plugins](https://github.com/bunkerity/bunkerweb-plugins) repository for more information) :

|      Name      | Version | Description                                                                                                                      |                                                 Link                                                  |
| :------------: | :-----: | :------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------: |
|   **ClamAV**   |   1.0   | Automatically scans uploaded files with the ClamAV antivirus engine and denies the request when a file is detected as malicious. |     [bunkerweb-plugins/clamav](https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav)     |
|  **CrowdSec**  |   1.0   | CrowdSec bouncer for BunkerWeb.                                                                                                  |   [bunkerweb-plugins/crowdsec](https://github.com/bunkerity/bunkerweb-plugins/tree/main/crowdsec)   |
| **Discord** | 1.0 | Send security notifications to a Discord channel using a Webhook. | [bunkerweb-plugins/discord](https://github.com/bunkerity/bunkerweb-plugins/tree/main/discord) |
| **Slack** | 1.0 | Send security notifications to a Slack channel using a Webhook. | [bunkerweb-plugins/slack](https://github.com/bunkerity/bunkerweb-plugins/tree/main/slack) |
| **VirusTotal** |   1.0   | Automatically scans uploaded files with the VirusTotal API and denies the request when a file is detected as malicious.          | [bunkerweb-plugins/virustotal](https://github.com/bunkerity/bunkerweb-plugins/tree/main/virustotal) |

## How to use a plugin

### Automatic

If you want to quickly install external plugins, you can use the `EXTERNAL_PLUGIN_URLS` setting. It takes a list of URLs, separated with space, pointing to compressed (zip format) archive containing one or more plugin(s).

You can use the following value if you want to automatically install the official plugins : `EXTERNAL_PLUGIN_URLS=https://github.com/bunkerity/bunkerweb-plugins/archive/refs/tags/v1.0.zip`

### Manual

The first step is to install the plugin by putting the plugin files inside the corresponding `plugins` data folder, the procedure depends on your integration :

=== "Docker"

    When using the [Docker integration](integrations.md#docker), plugins must be written to the volume mounted on `/data/plugins` into the scheduler container.

    The first thing to do is to create the plugins folder :

    ```shell
    mkdir -p ./bw-data/plugins
    ```

    Then, you can drop the plugins of your choice into that folder :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    Because the scheduler runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :

    ```shell
    chown -R 101:101 ./bw-data
    ```

    Then you can mount the volume when starting your Docker stack :

    ```yaml
    version: '3.5'
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.5.0
        volumes:
          - ./bw-data:/data
    ...
    ```

=== "Docker autoconf"

    When using the [Docker autoconf integration](integrations.md#docker-autoconf), plugins must be written to the volume mounted on `/data/plugins` into the scheduler container.


    The first thing to do is to create the plugins folder :

    ```shell
    mkdir -p ./bw-data/plugins
    ```

    Then, you can drop the plugins of your choice into that folder :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    Because the scheduler runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :

    ```shell
    chown -R 101:101 ./bw-data
    ```

    Then you can mount the volume when starting your Docker stack :

    ```yaml
    version: '3.5'
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.5.0
        volumes:
          - ./bw-data:/data
    ...
    ```

=== "Swarm"

    When using the [Swarm integration](integrations.md#swarm), plugins must be written to the volume mounted on `/data/plugins` into the scheduler container.

    !!! info "Swarm volume"
        Configuring a Swarm volume that will persist when the scheduler service is running on different nodes is not covered is in this documentation. We will assume that you have a shared folder mounted on `/shared` accross all nodes.

    The first thing to do is to create the plugins folder :

    ```shell
    mkdir -p /shared/bw-plugins
    ```

    Then, you can drop the plugins of your choice into that folder :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /shared/bw-plugins
    ```

    Because the scheduler runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :

    ```shell
    chown -R 101:101 /shared/bw-plugins
    ```

    Then you can mount the volume when starting your Swarm stack :

    ```yaml
    version: '3.5'
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.5.0
        volumes:
          - /shared/bw-plugins:/data/plugins
    ...
    ```

=== "Kubernetes"

    When using the [Kubernetes integration](integrations.md#kubernetes), plugins must be written to the volume mounted on `/data/plugins` into the scheduler container.

    The fist thing to do is to declare a [PersistentVolumeClaim](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) that will contain our plugins data :

    ```yaml
    apiVersion: v1
    kind: PersistentVolumeClaim
    metadata:
      name: pvc-bunkerweb-plugins
    spec:
      accessModes:
        - ReadWriteOnce
    resources:
      requests:
        storage: 5Gi
    ```

    You can now add the volume mount and an init containers to automatically provision the volume :

    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-scheduler
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-scheduler
      template:
        metadata:
          labels:
            app: bunkerweb-scheduler
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            - name: bunkerweb-scheduler
              image: bunkerity/bunkerweb-scheduler:1.5.0
              imagePullPolicy: Always
              env:
                - name: KUBERNETES_MODE
                  value: "yes"
                - name: "DATABASE_URI"
                  value: "mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db"
              volumeMounts:
                - mountPath: "/data/plugins"
                  name: vol-plugins
          initContainers:
            - name: bunkerweb-scheduler-init
              image: alpine/git
              command: ["/bin/sh", "-c"]
              args: ["git clone https://github.com/bunkerity/bunkerweb-plugins /data/plugins && chown -R 101:101 /data/plugins"]
              volumeMounts:
                - mountPath: "/data/plugins"
                  name: vol-plugins
          volumes:
            - name: vol-plugins
              persistentVolumeClaim:
                claimName: pvc-bunkerweb-plugins
    ```

=== "Linux"

    When using the [Linux integration](integrations.md#linux), plugins must be written to the `/etc/bunkerweb/plugins` folder :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /etc/bunkerweb/plugins && \
    chown -R nginx:nginx /etc/bunkerweb/plugins
    ```

=== "Ansible"

    When using the [Ansible integration](integrations.md#ansible), you can use the `plugins` variable to set a local folder containing your plugins that will be copied to your BunkerWeb instances.
	
    Let's assume that you have plugins inside the `bunkerweb-plugins` folder :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins
    ```

    In your Ansible inventory, you can use the `plugins` variable to set the path of plugins folder :

    ```ini
    [mybunkers]
    192.168.0.42 ... custom_plugins="{{ playbook_dir }}/bunkerweb-plugins"
    ```
	
    Or alternatively, in your playbook file :

    ```yaml
    - hosts: all
      become: true
      vars:
      - custom_plugins: "{{ playbook_dir }}/bunkerweb-plugins"
      roles:
      - bunkerity.bunkerweb
    ```

    Run the playbook :

    ```shell
    ansible-playbook -i inventory.yml playbook.yml
    ```

=== "Vagrant"

    When using the [Vagrant integration](integrations.md#vagrant), plugins must be written to the `/etc/bunkerweb/plugins` folder (you will need to do a `vagrant ssh` first) :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /etc/bunkerweb/plugins
    ```

## Writing a plugin

!!! tip "Existing plugins"

    If the documentation is not enough, you can have a look at the existing source code of [official plugins](https://github.com/bunkerity/bunkerweb-plugins) and the [core plugins](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/src/common/core) (already included in BunkerWeb but they are plugins, technically speaking).

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
  "name": "My Plugin",
  "description": "Just an example plugin.",
  "version": "1.0",
  "stream": "partial",
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
  },
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
|    `name`     |    yes    | string | Name of your plugin.                                                                                                                                                                               |
| `description` |    yes    | string | Description of your plugin.                                                                                                                                                                        |
|   `version`   |    yes    | string | Version of your plugin.                                                                                                                                                                            |
|   `stream`    |    yes    | string | Information about stream support : `no`, `yes` or `partial`.
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
|   `type`   |    yes    | string | The type of the field : `text`, `check`, `select` or `password`.         |
| `multiple` |    no     | string | Unique ID to group multiple settings with numbers as suffix. |
|  `select`  |    no     |  list  | List of possible string values when `type` is `select`.      |

Each job has the following fields :

|  Field  | Mandatory |  Type  | Description                                                                                                                             |
| :-----: | :-------: | :----: | :-------------------------------------------------------------------------------------------------------------------------------------- |
| `name`  |    yes    | string | Name of the job.                                                                                                                        |
| `file`  |    yes    | string | Name of the file inside the jobs folder.                                                                                                |
| `every` |    yes    | string | Job scheduling frequency : `minute`, `hour`, `day`, `week` or `once` (no frequency, only once before (re)generating the configuration). |

### Configurations

You can add custom NGINX configurations by adding a folder named **confs** with content similar to the [custom configurations](quickstart-guide.md#custom-configurations). Each subfolder inside the **confs** will contain [jinja2](https://jinja.palletsprojects.com) templates that will be generated and loaded at the corresponding context (`http`, `server-http`, `default-server-http`, `stream` and `server-stream`).

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
local class     = require "middleclass"
local plugin    = require "bunkerweb.plugin"
local utils     = require "bunkerweb.utils"


local myplugin = class("myplugin", plugin)


function myplugin:initialize()
    plugin.initialize(self, "myplugin")
    self.dummy = "dummy"
end

function myplugin:init()
    self.logger:log(ngx.NOTICE, "init called")
    return self:ret(true, "success")
end

function myplugin:set()
    self.logger:log(ngx.NOTICE, "set called")
    return self:ret(true, "success")
end

function myplugin:access()
    self.logger:log(ngx.NOTICE, "access called")
    return self:ret(true, "success")
end

function myplugin:log()
    self.logger:log(ngx.NOTICE, "log called")
    return self:ret(true, "success")
end

function myplugin:log_default()
    self.logger:log(ngx.NOTICE, "log_default called")
    return self:ret(true, "success")
end

function myplugin:preread()
    self.logger:log(ngx.NOTICE, "preread called")
    return self:ret(true, "success")
end

function myplugin:log_stream()
    self.logger:log(ngx.NOTICE, "log_stream called")
    return self:ret(true, "success")
end

return myplugin
```

The declared functions are automatically called during specific contexts. Here are the details of each function :

| Function |                                   Context                                    | Description                                                                                                                                               | Return value                                                                                                                                                                                                                                                                                                                            |
| :------: | :--------------------------------------------------------------------------: | :-------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|  `init`  |   [init_by_lua](https://github.com/openresty/lua-nginx-module#init_by_lua)   | Called when NGINX just started or received a reload order. the typical use case is to prepare any data that will be used by your plugin.                  | `ret`, `msg`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li></ul>|
|  `set`  |   [set_by_lua](https://github.com/openresty/lua-nginx-module#set_by_lua)   | Called before each request received by the server.The typical use case is for computing before access phase.                 | `ret`, `msg`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li></ul>|
| `access` | [access_by_lua](https://github.com/openresty/lua-nginx-module#access_by_lua) | Called on each request received by the server. The typical use case is to do the security checks here and deny the request if needed.                     | `ret`, `msg`,`status`,`redirect`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li><li>`status` (number) : interrupt current process and return [HTTP status](https://github.com/openresty/lua-nginx-module#http-status-constants)</li><li>`redirect` (URL) : if set will redirect to given URL</li></ul> |
|  `log`   |    [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)    | Called when a request has finished (and before it gets logged to the access logs). The typical use case is to make stats or compute counters for example. | `ret`, `msg`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li></ul>                                                                                                                                                                                                           |
|  `log_default`   |    [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)    | Same as `log` but only called on the default server. | `ret`, `msg`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li></ul>                                                                                                                                                                                                           |
| `preread` | [preread_by_lua](https://github.com/openresty/stream-lua-nginx-module#preread_by_lua_block) | Similar to the `access` function but for stream mode. | `ret`, `msg`,`status`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li><li>`status` (number) : interrupt current process and return [status](https://github.com/openresty/lua-nginx-module#http-status-constants)</li></ul> |
| `log_stream` | [log_by_lua](https://github.com/openresty/stream-lua-nginx-module#log_by_lua_block) | Similar to the `log` function but for stream mode. | `ret`, `msg`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li></ul> |

#### Libraries

All directives from [NGINX LUA module](https://github.com/openresty/lua-nginx-module) and are available and [NGINX stream LUA module](https://github.com/openresty/stream-lua-nginx-module). On top of that, you can use the LUA libraries included within BunkerWeb : see [this script](https://github.com/bunkerity/bunkerweb/blobsrc/deps/clone.sh) for the complete list.

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

Some helpers modules provide common helpful helpers :

- `self.variables` : allows to access and store plugins' attributes
- `self.logger` : print logs
- `bunkerweb.utils` : various useful functions
- `bunkerweb.datastore` : access the global shared data on one instance (key/value store)
- `bunkerweb.clusterstore` : access a Redis data store shared beetween BunkerWeb instances (key/value store)

To access the functions, you first need to **require** the modules :

```lua
local utils       = require "bunkerweb.utils"
local datastore   = require "bunkerweb.datastore"
local clustestore = require "bunkerweb.clustertore"
```

Retrieve a setting value :

```lua
local myvar = self.variables["DUMMY_SETTING"]
if not myvar then
    self.logger:log(ngx.ERR, "can't retrieve setting DUMMY_SETTING")
else
    self.logger:log(ngx.NOTICE, "DUMMY_SETTING = " .. value)
end
```

Store something in the local cache :

```lua
local ok, err = self.datastore:set("plugin_myplugin_something", "somevalue")
if not ok then
    self.logger:log(ngx.ERR, "can't save plugin_myplugin_something into datastore : " .. err)
else
    self.logger:log(ngx.NOTICE, "successfully saved plugin_myplugin_something into datastore")
end
```

Check if an IP address is global :

```lua
local ret, err = utils.ip_is_global(ngx.ctx.bw.remote_addr)
if ret == nil then
    self.logger:log(ngx.ERR, "error while checking if IP " .. ngx.ctx.bw.remote_addr .. " is global or not : " .. err)
elseif not ret then
    self.logger:log(ngx.NOTICE, "IP " .. ngx.ctx.bw.remote_addr .. " is not global")
else
    self.logger:log(ngx.NOTICE, "IP " .. ngx.ctx.bw.remote_addr .. " is global")
end
```

!!! tip "More examples"

    If you want to see the full list of available functions, you can have a look at the files present in the [lua directory](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/src/bw/lua/bunkerweb) of the repository.

### Jobs

BunkerWeb uses an internal job scheduler for periodic tasks like renewing certificates with certbot, downloading blacklists, downloading MMDB files, ... You can add tasks of your choice by putting them inside a subfolder named **jobs** and listing them in the **plugin.json** metadata file. Don't forget to add the execution permissions for everyone to avoid any problems when a user is cloning and installing your plugin.

### Plugin page

Plugin pages are used to display information about your plugin and interact with the user inside the plugins section of the [web UI](web-ui.md).

Everything related to the web UI is located inside a subfolder named **ui** at the root directory of your plugin. A template file named **template.html** and located inside the **ui** subfolder contains the client code and logic to display your page. Another file named **actions.py** and also located inside the **ui** subfolder contains code that will be executed when the user is interacting with your page (filling a form for example).

!!! info "Jinja 2 template"
    The **template.html** file is a Jinja2 template, please refer to the [Jinja2 documentation](https://jinja.palletsprojects.com) if needed.

A plugin page can have a form that is used to submit data to the plugin. To get the values of the form, you need to put a **actions.py** file in the **ui** folder. Inside the file, **you must define a function that has the same name as the plugin**. This function will be called when the form is submitted. You can then use the **request** object (from the [Flask library](https://flask.palletsprojects.com)) to get the values of the form. The form's action must finish with **/plugins/<*plugin_id*>**. The helper function `url_for` will generate for you the prefix of the URL : `{{ url_for('plugins') }}/plugin_id`.

If you want to display variables generated from your **actions.py** in your template file, you can return a dictionary with variables name as keys and variables value as values. Here is dummy example where we return a single variable :

```python
def myplugin() :
	return {"foo": "bar"}
```

And we display it in the **template.html** file :
```html
{% if foo %}
Content of foo is : {{ foo }}.
{% endif %}
```

Please note that every form submission is protected via a CSRF token, you will need to include the following snippet into your forms :
```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
```

Retrieving user submitted data is pretty simple, thanks to the request module provided by Flask :

```python
from flask import request

def myplugin() :
	my_form_value = request.form["my_form_input"]
```

!!! info "Python libraries"
    You can use Python libraries that are already available like :
    `Flask`, `Flask-Login`, `Flask-WTF`, `beautifulsoup4`, `docker`, `Jinja2`, `python-magic` and `requests`. To see the full list, you can have a look at the Web UI [requirements.txt](https://github.com/bunkerity/bunkerweb/blobsrc/ui/requirements.txt). If you need external libraries, you can install them inside the **ui** folder of your plugin and then use the classical **import** directive.
