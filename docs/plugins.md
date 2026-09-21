# Plugins

BunkerWeb comes with a plugin system making it possible to easily add new features. Once a plugin is installed, you can manage it using additional settings defined by the plugin.

## Official plugins

Here is the list of "official" plugins that we maintain (see the [bunkerweb-plugins](https://github.com/bunkerity/bunkerweb-plugins) repository for more information) :

|      Name      | Version | Description                                                                                                                      |                                                Link                                                 |
| :------------: | :-----: | :------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------: |
| **Authentik**  |  1.11   | Protect your web services with Authentik forward authentication (auth_request) for single sign-on.                               |  [bunkerweb-plugins/authentik](https://github.com/bunkerity/bunkerweb-plugins/tree/main/authentik)  |
|   **ClamAV**   |  1.11   | Automatically scans uploaded files with the ClamAV antivirus engine and denies the request when a file is detected as malicious. |     [bunkerweb-plugins/clamav](https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav)     |
| **Cloudflare** |  1.11   | Configure Cloudflare's trusted IPs, manage Origin CA certificates and sync BunkerWeb bans to a Cloudflare IP List.               | [bunkerweb-plugins/cloudflare](https://github.com/bunkerity/bunkerweb-plugins/tree/main/cloudflare) |
|   **Coraza**   |  1.11   | Inspect requests using the Coraza WAF (alternative of ModSecurity).                                                              |     [bunkerweb-plugins/coraza](https://github.com/bunkerity/bunkerweb-plugins/tree/main/coraza)     |
|  **Discord**   |  1.11   | Send security notifications to a Discord channel using a Webhook.                                                                |    [bunkerweb-plugins/discord](https://github.com/bunkerity/bunkerweb-plugins/tree/main/discord)    |
|   **Matrix**   |  1.11   | Send security notifications to a Matrix room using the Matrix API.                                                               |     [bunkerweb-plugins/matrix](https://github.com/bunkerity/bunkerweb-plugins/tree/main/matrix)     |
|   **Slack**    |  1.11   | Send security notifications to a Slack channel using a Webhook.                                                                  |      [bunkerweb-plugins/slack](https://github.com/bunkerity/bunkerweb-plugins/tree/main/slack)      |
| **VirusTotal** |  1.11   | Automatically scans uploaded files with the VirusTotal API and denies the request when a file is detected as malicious.          | [bunkerweb-plugins/virustotal](https://github.com/bunkerity/bunkerweb-plugins/tree/main/virustotal) |
|  **WebHook**   |  1.11   | Send security notifications to a custom HTTP endpoint using a Webhook.                                                           |    [bunkerweb-plugins/webhook](https://github.com/bunkerity/bunkerweb-plugins/tree/main/webhook)    |

## Web UI management and community catalogue

The **Plugins** page separates installation from activation:

- External, UI, and PRO plugins can be enabled or disabled without deleting their stored package. The scheduler omits disabled plugins from the materialized plugin directories, then restores them from the database when you enable them again.
- Core plugins are part of the BunkerWeb image and cannot be disabled at the installation layer. Use the plugin's global settings when it exposes an activation switch.
- A plugin can ship `icon.svg`, `icon.png`, `logo.svg`, or `logo.png` at the root of its folder. BunkerWeb detects these names in that order and serves at most 512 KiB through the authenticated icon endpoint. The Web UI falls back to a built-in icon when no supported file exists.

The community catalogue lists the latest releases from two fixed GitHub repositories: [`bunkerity/bunkerweb-plugins`](https://github.com/bunkerity/bunkerweb-plugins) and [`bunkerity/bunkerweb-templates`](https://github.com/bunkerity/bunkerweb-templates). The repositories themselves are the catalogue. There is no separate manifest or producer. BunkerWeb reads each item's `plugin.json` or `template.json` from the release archive, applies the plugin compatibility gate, and installs only the selected item through the existing upload path.

Set the Web UI environment variable `USE_PLUGIN_CATALOG=no` to disable catalogue requests, hide both catalogue sections, and refuse catalogue installs. `off`, `false`, and `0` also disable it. This switch does not remove anything already installed. A cached listing older than 24 hours remains visible but cannot install anything until a refresh succeeds.

!!! warning "Catalogue trust model"
    HTTPS to GitHub and an exact repository allowlist protect the download path. At refresh time BunkerWeb records the release archive's SHA-256 digest; at install time it fetches the pinned tag again and refuses the item if the digest changed. This check proves that the installed bytes match the bytes that were listed. It does not prove who authored them. Write access to the two `bunkerity` repositories is the trust root, and a hostile repository publisher remains trusted. Ed25519 signing is deliberately deferred.

## How to use a plugin

### Automatic

If you want to quickly install external plugins, you can use the `EXTERNAL_PLUGIN_URLS` setting. It takes a list of URLs separated by spaces, each pointing to a compressed (zip format) archive containing one or more plugins.

You can use the following value if you want to automatically install the official plugins : `EXTERNAL_PLUGIN_URLS=https://github.com/bunkerity/bunkerweb-plugins/archive/refs/tags/v1.11.zip`

### Manual

The first step is to install the plugin by placing its files inside the corresponding `plugins` data folder. The procedure depends on your integration :

=== "Docker"

    When using the [Docker integration](integrations.md#docker), plugins must be placed in the volume mounted on `/data/plugins` in the scheduler container.

    The first thing to do is to create the plugins folder :

    ```shell
    mkdir -p ./bw-data/plugins
    ```

    Then, you can drop the plugins of your choice into that folder :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    ??? warning "Using local folder for persistent data"
        The scheduler runs as an **unprivileged user with UID 101 and GID 101** inside the container. The reason behind this is security : in case a vulnerability is exploited, the attacker won't have full root (UID/GID 0) privileges.
        But there is a downside : if you use a **local folder for the persistent data**, you will need to **set the correct permissions** so the unprivileged user can write data to it. Something like that should do the trick :

        ```shell
        mkdir bw-data && \
        chown root:101 bw-data && \
        chmod 770 bw-data
        ```

        Alternatively, if the folder already exists :

        ```shell
        chown -R root:101 bw-data && \
        chmod -R 770 bw-data
        ```

        If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) or [podman](https://podman.io/), UIDs and GIDs in the container will be mapped to different ones in the host. You will first need to check your initial subuid and subgid :

        ```shell
        grep ^$(whoami): /etc/subuid && \
        grep ^$(whoami): /etc/subgid
        ```

        For example, if you have a value of **100000**, the mapped UID/GID will be **100100** (100000 + 100) :

        ```shell
        mkdir bw-data && \
        sudo chgrp 100100 bw-data && \
        chmod 770 bw-data
        ```

        Or if the folder already exists :

        ```shell
        sudo chgrp -R 100100 bw-data && \
        chmod -R 770 bw-data
        ```

    Then you can mount the volume when starting your Docker stack :

    ```yaml
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
        volumes:
          - ./bw-data:/data
    ...
    ```

=== "Docker autoconf"

    When using the [Docker autoconf integration](integrations.md#docker-autoconf), plugins must be placed in the volume mounted on `/data/plugins` in the scheduler container.


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
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
        volumes:
          - ./bw-data:/data
    ...
    ```

=== "Swarm"

    When using the [Swarm integration](integrations.md#swarm), plugins must be placed in the volume mounted on `/data/plugins` in the scheduler container.

    !!! info "Swarm volume"
        Configuring a Swarm volume that will persist when the scheduler service is running on different nodes is not covered is in this documentation. We will assume that you have a shared folder mounted on `/shared` across all nodes.

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
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
        volumes:
          - /shared/bw-plugins:/data/plugins
    ...
    ```

=== "Kubernetes"

    When using the [Kubernetes integration](integrations.md#kubernetes), plugins must be placed in the volume mounted on `/data/plugins` in the scheduler container.

    The first thing to do is to declare a [PersistentVolumeClaim](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) that will contain our plugins data :

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

    You can now add the volume mount and an init container to automatically provision the volume :

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
              image: bunkerity/bunkerweb-scheduler:1.7.0-beta
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

## Writing a plugin

### Structure

!!! tip "Existing plugins"

    If the documentation is not enough, you can have a look at the existing source code of [official plugins](https://github.com/bunkerity/bunkerweb-plugins) and the [core plugins](https://github.com/bunkerity/bunkerweb/tree/v1.7.0-beta/src/common/core) (already included in BunkerWeb but they are plugins, technically speaking).

What a plugin structure looks like:
```
plugin /
    confs / conf_type / conf_name.conf
    ui / actions.py
         hooks.py
         template.html
         blueprints / <blueprint_file(s)>
              templates / <blueprint_template(s)>
    jobs / my-job.py
    bwcli / my-command.py
    templates / my-template.json
          my-template / configs / conf_type / conf_name.conf
    plugin.lua
    plugin.json
```

- **conf_name.conf** : Add [custom NGINX configurations](advanced.md#custom-configurations) (as Jinja2 templates).

- **actions.py** : Script to execute on the Flask server. This script runs in a Flask context, giving you access to libraries and utilities like `jinja2` and `requests`.

- **hooks.py** : Custom Python file that contains flask's hooks and will be executed when the plugin is loaded.

- **template.html** : Custom plugin page accessed via the UI.

- **blueprints folder (within ui)**:
  This folder is used to override existing Flask blueprints or create new ones. Inside, you can include blueprint files and an optional **templates** subfolder for blueprint-specific templates.

- **jobs py file** : Custom Python files executed as jobs by the scheduler.

- **bwcli folder** : Python (or executable) files that extend the `bwcli` CLI through custom commands.

- **my-template.json** : Add [custom templates](concepts.md#templates) to override the default values of settings and apply custom configurations easily.

- **plugin.lua** : Code executed on NGINX using the [NGINX LUA module](https://github.com/openresty/lua-nginx-module).

- **plugin.json** : Metadata, settings, and job definitions for your plugin.

### Getting started

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

|     Field     | Mandatory |  Type  | Description                                                                                                               |
| :-----------: | :-------: | :----: | :------------------------------------------------------------------------------------------------------------------------ |
|     `id`      |    yes    | string | Internal ID for the plugin : must be unique among other plugins (including "core" ones) and contain only lowercase chars. |
|    `name`     |    yes    | string | Name of your plugin.                                                                                                      |
| `description` |    yes    | string | Description of your plugin.                                                                                               |
|   `version`   |    yes    | string | Version of your plugin.                                                                                                   |
|   `stream`    |    yes    | string | Information about stream support : `no`, `yes` or `partial`.                                                              |
|  `settings`   |    yes    |  dict  | List of the settings of your plugin.                                                                                      |
|    `jobs`     |    no     |  list  | List of the jobs of your plugin.                                                                                          |
|    `bwcli`    |    no     |  dict  | Map CLI command names to files stored in the plugin's `bwcli` directory to expose CLI plugins.                            |

### Execution order

A plugin may declare where it wants to sit inside a phase. The key is optional; everything below is a hint, not a guarantee.

```json
{
  "id": "myplugin",
  "order": {
    "ssl_certificate": { "after": ["certificates"] },
    "access": { "before": ["antibot"] }
  }
}
```

- Phase names are `init`, `init_worker`, `set`, `rewrite`, `access`, `content`, `ssl_client_hello_default`, `ssl_certificate`, `ssl_certificate_default`, `header`, `log`, `preread`, `log_stream`, `log_default`, `timer` and `init_workers`. `headers` is accepted as an alias of `header`, as in `order.json`.
- `before` / `after` are lists of plugin ids. An unavailable plugin, or one that does not implement the phase, is ignored with a warning in the BunkerWeb error log.
- Mutually contradictory declarations (a cycle) are dropped with a warning: the declarations of the plugins on the cycle are skipped and the order is recomputed with every other plugin's constraints still applied; only if that retry fails too is the default order kept. A malformed `order` block is also warned about and dropped; the plugin still loads.
- `before` / `after` may contain the wildcard `"*"`, meaning every other plugin implementing this phase that is not itself constrained relative to me. `"before": ["*"]` puts a plugin ahead of every plugin that does not pin itself and `"after": ["*"]` puts it last. Plugins with the same wildcard keep their default-list order; an explicit plugin id wins over another plugin's wildcard.

After initialization, the computed `plugins_order` is sealed: declare `order` in the manifest instead of trying to change it from plugin code.

**Precedence inside a phase**, strongest first:

1. the operator's `PLUGINS_ORDER_<PHASE>` setting (global or per service);
2. declared `order` constraints, resolved with a stable sort;
3. PRO plugins alphabetically, then external plugins alphabetically, then core plugins in `order.json` order, then remaining core plugins alphabetically.

Each setting has the following fields (the key is the ID of the settings used in a configuration) :

|   Field    | Mandatory |  Type  | Description                                                      |
| :--------: | :-------: | :----: | :--------------------------------------------------------------- |
| `context`  |    yes    | string | Context of the setting : `multisite` or `global`.                |
| `default`  |    yes    | string | The default value of the setting.                                |
|   `help`   |    yes    | string | Help text about the plugin (shown in web UI).                    |
|    `id`    |    yes    | string | Internal ID used by the web UI for HTML elements.                |
|  `label`   |    yes    | string | Label shown by the web UI.                                       |
|  `regex`   |    yes    | string | The regex used to validate the value provided by the user.       |
|   `type`   |    yes    | string | The type of the field : `text`, `check`, `select` or `password`. |
| `multiple` |    no     | string | Unique ID to group multiple settings with numbers as suffix.     |
|  `select`  |    no     |  list  | List of possible string values when `type` is `select`.          |

Each job has the following fields :

|  Field  | Mandatory |  Type  | Description                                                                                                                             |
| :-----: | :-------: | :----: | :-------------------------------------------------------------------------------------------------------------------------------------- |
| `name`  |    yes    | string | Name of the job.                                                                                                                        |
| `file`  |    yes    | string | Name of the file inside the jobs folder.                                                                                                |
| `every` |    yes    | string | Job scheduling frequency : `minute`, `hour`, `day`, `week` or `once` (no frequency, only once before (re)generating the configuration). |
| `reload` |    no    |  bool  | Whether a change from this job should trigger a reload of the BunkerWeb instances. Defaults to `false`.                                 |
| `async`  |    no    |  bool  | Whether the job is routed to the `heavy` worker queue. Both queues share the default worker pool; isolate them only with workers pinned through `WORKER_QUEUES=heavy` or `WORKER_QUEUES=default`. Defaults to `false`. |
| `regenerate` |  no  |  bool  | Whether a change from this job requires the NGINX configuration to be **rendered again**, not just shipped. Defaults to `false`.        |

Core heavy jobs are `backup-data`, `bunkernet-register`, `bunkernet-data`, `push-configs`, `certbot-new`, `certbot-renew`, `download-plugins`, `download-crs-plugins` and `download-pro-plugins`; routing follows the manifest's `async` flag, not the job name.

!!! info "A refused manifest is refused everywhere"

    A `plugin.json` that fails one of the caps below is refused by both the config generator
    (Python) and the NGINX runtime (Lua): it is dropped from the generated configuration and never
    loaded, ordered or executed. The refusal is logged as an `ERROR` naming the plugin id, file,
    failing field and cap.

    Length caps are measured in **UTF-8 bytes**, not characters. `id`, `version` and setting `id`
    are ASCII-only, so byte and character counts always agree for those fields.

    | Field | Cap |
    | :---: | :--- |
    | `id` | ASCII letters, digits, `.`, `_`, `-` only, 1-64 bytes |
    | `name` | max 128 bytes |
    | `description` | max 256 bytes |
    | `version` | must match `\d+\.\d+(\.\d+)?` (ASCII digits only) |
    | `stream` | one of `yes`, `no`, `partial` |
    | setting `id` | ASCII uppercase letters, digits, `_` only, 1-256 bytes |
    | setting `context` | one of `global`, `multisite` |
    | setting `default` | max 4096 bytes |
    | setting `help` | max 512 bytes |
    | setting `label` | max 256 bytes |
    | setting `regex` | max 1024 bytes |
    | setting `type` | one of `password`, `text`, `number`, `file`, `check`, `select`, `multiselect`, `multivalue`, `size`, `duration` |

    `extensions` is validated on the Python side only: the NGINX runtime never reads it. Job
    fields (`jobs[]`) are also Python-only because the Worker dispatches them.

### CLI commands

Plugins can extend the `bwcli` tool with custom commands that run under `bwcli plugin <plugin_id> ...`:

1. Add a `bwcli` directory in your plugin and drop one file per command (for example `bwcli/list.py`). The CLI adds the plugin path to `sys.path` before executing the file.
2. Declare the commands in the optional `bwcli` section of `plugin.json`, mapping each command name to its executable file name.

```json
{
  "bwcli": {
    "list": "list.py",
    "save": "save.py"
  }
}
```

The scheduler automatically exposes the declared commands once the plugin is installed. Core plugins, such as `backup` in `src/common/core/backup`, follow the same pattern.

### Configurations

You can add custom NGINX configurations by adding a folder named **confs** with content similar to the [custom configurations](advanced.md#custom-configurations). Each subfolder inside the **confs** will contain [jinja2](https://jinja.palletsprojects.com) templates that will be generated and loaded at the corresponding context (`http`, `server-http`, `default-server-http`, `stream`, `server-stream`, `modsec`, `modsec-crs`, `crs-plugins-before` and `crs-plugins-after`).

Here is an example for a configuration template file inside the **confs/server-http** folder named **example.conf** :

```nginx
location /setting {
  default_type 'text/plain';
    content_by_lua_block {
        ngx.say('{{ DUMMY_SETTING }}')
    }
}
```

`{{ DUMMY_SETTING }}` will be replaced by the value of the `DUMMY_SETTING` chosen by the user of the plugin.

### Templates

Check the [templates documentation](concepts.md#templates) for more information.

### LUA

#### Main script

Under the hood, BunkerWeb is using the [NGINX LUA module](https://github.com/openresty/lua-nginx-module) to execute code within NGINX. Plugins that need to execute code must provide a lua file at the root directory of the plugin folder using the `id` value of **plugin.json** as its name. Here is an example named **myplugin.lua** :

```lua
local class     = require "middleclass"
local plugin    = require "bunkerweb.plugin"
local utils     = require "bunkerweb.utils"


local myplugin = class("myplugin", plugin)


function myplugin:initialize(ctx)
    plugin.initialize(self, "myplugin", ctx)
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

|   Function    |                                           Context                                           | Description                                                                                                                                               | Return value                                                                                                                                                                                                                                                                                                                                                          |
| :-----------: | :-----------------------------------------------------------------------------------------: | :-------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|    `init`     |          [init_by_lua](https://github.com/openresty/lua-nginx-module#init_by_lua)           | Called when NGINX just started or received a reload order. the typical use case is to prepare any data that will be used by your plugin.                  | `ret`, `msg`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li></ul>                                                                                                                                                                                                                                      |
|     `set`     |           [set_by_lua](https://github.com/openresty/lua-nginx-module#set_by_lua)            | Called before each request received by the server.The typical use case is for computing before access phase.                                              | `ret`, `msg`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li></ul>                                                                                                                                                                                                                                      |
|   `access`    |        [access_by_lua](https://github.com/openresty/lua-nginx-module#access_by_lua)         | Called on each request received by the server. The typical use case is to do the security checks here and deny the request if needed.                     | `ret`, `msg`,`status`,`redirect`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li><li>`status` (number) : interrupt current process and return [HTTP status](https://github.com/openresty/lua-nginx-module#http-status-constants)</li><li>`redirect` (URL) : if set will redirect to given URL</li></ul> |
|     `log`     |           [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)            | Called when a request has finished (and before it gets logged to the access logs). The typical use case is to make stats or compute counters for example. | `ret`, `msg`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li></ul>                                                                                                                                                                                                                                      |
| `log_default` |           [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)            | Same as `log` but only called on the default server.                                                                                                      | `ret`, `msg`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li></ul>                                                                                                                                                                                                                                      |
|   `preread`   | [preread_by_lua](https://github.com/openresty/stream-lua-nginx-module#preread_by_lua_block) | Similar to the `access` function but for stream mode.                                                                                                     | `ret`, `msg`,`status`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li><li>`status` (number) : interrupt current process and return [status](https://github.com/openresty/lua-nginx-module#http-status-constants)</li></ul>                                                                              |
| `log_stream`  |     [log_by_lua](https://github.com/openresty/stream-lua-nginx-module#log_by_lua_block)     | Similar to the `log` function but for stream mode.                                                                                                        | `ret`, `msg`<ul><li>`ret` (boolean) : true if no error or else false</li><li>`msg` (string) : success or error message</li></ul>                                                                                                                                                                                                                                      |

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
- `bunkerweb.clusterstore` : access a Redis data store shared between BunkerWeb instances (key/value store)

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

    If you want to see the full list of available functions, you can have a look at the files present in the [lua directory](https://github.com/bunkerity/bunkerweb/tree/v1.7.0-beta/src/bw/lua/bunkerweb) of the repository.

### Jobs

BunkerWeb uses an internal job scheduler for periodic tasks like renewing certificates with certbot, downloading blacklists, downloading MMDB files, ... You can add tasks of your choice by putting them inside a subfolder named **jobs** and listing them in the **plugin.json** metadata file. Don't forget to add the execution permissions for everyone to avoid any problems when a user is cloning and installing your plugin.

The exit code of a job is a protocol: `sys.exit(1)` means "something changed", which ships the job's cache directory (`/var/cache/bunkerweb/<plugin_id>/`) to the instances and asks them to reload. `sys.exit(0)` means the job succeeded and changed nothing; any other code is a failure. Returning a value instead of exiting does nothing — return values are discarded and recorded as `0`.

Shipping the cache is enough as long as the instances read your files at **run time**. If one of your `confs/` templates *reads* what the job wrote — inlining a downloaded list, or probing a cached certificate with `is_file()` — then it is not enough: the configuration the instances reload is the one that was rendered before your job ran, and it does not mention the new material. Declare `"regenerate": true` on that job and BunkerWeb renders the configuration again, ships it and reloads. It costs a full render plus one extra dispatch of your plugin's jobs, so set it only when a template actually reads the cache, and make sure the job exits `0` when it has nothing new to write.

The flag fires on **every** exit `1`. If your job wants a render on a narrower condition than that — it exits `1` to have new files shipped, but only some of those runs change what a template would emit — leave the flag off and ask for the render yourself, under your own condition: `JOB.db.checked_changes(["config"], plugins_changes=["<your plugin id>"], value=True)`. Do not do both; declaring the flag *and* calling it by hand renders twice. The shipped `modsecurity/download-crs-plugins` job is the worked example.

!!! warning "Unknown keys are refused"
    Job entries accept `name`, `file`, `every`, `reload`, `async` and `regenerate` and nothing else. A misspelled key (`"regenrate"`) makes the whole plugin fail validation and be ignored, with the offending key named in the logs — deliberately, so a typo cannot silently disable a flag.

### Plugin page

Everything related to the web UI is located inside the subfolder **ui** as we seen in the [previous structure section.](#structure).

#### Prerequisites

When you want to create a plugin page, you need two files :

- **template.html** that will be accessible with a **GET /plugins/<*plugin_id*>**.

- **actions.py** where you can add some scripting and logic with a **POST /plugins/<*plugin_id*>**. Notice that this file **need a function with the same name as the plugin** to work. This file is needed even if the function is empty.

#### Basic example

!!! info "Jinja 2 template"
    The **template.html** file is a Jinja2 template, please refer to the [Jinja2 documentation](https://jinja.palletsprojects.com) if needed.

We can put aside the **actions.py** file and start **only using the template on a GET situation**. The template can access app context and libs, so you can use Jinja, request or flask utils.

For example, you can get the request arguments in your template like this :

```html
<p>request args : {{ request.args.get() }}.</p>
```

#### Actions.py

!!! warning "CSRF Token"

    Please note that every form submission is protected via a CSRF token, you will need to include the following snippet into your forms :
    ```html
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
    ```

You can power-up your plugin page with additional scripting with the **actions.py** file when sending a **POST /plugins/<*plugin_id*>**.

You have two functions by default in **actions.py** :

**pre_render function**

This allows you to retrieve data when you **GET** the template, and to use the data with the pre_render variable available in Jinja to display content more dynamically.

```python
def pre_render(**kwargs)
  return <pre_render_data>
```

BunkerWeb will send you this type of response :


```python
return jsonify({"status": "ok|ko", "code" : XXX, "data": <pre_render_data>}), 200
```

**<*plugin_id*> function**

This allows you to retrieve data when you make a **POST** from the template endpoint, which must be used in AJAX.

```python
def myplugin(**kwargs)
  return <plugin_id_data>
```

BunkerWeb will send you this type of response :

```python
return jsonify({"message": "ok", "data": <plugin_id_data>}), 200
```

**What you can access from action.py**

Here are the arguments that are passed and access on action.py functions:

```python
function(app=app, db=db, api_client=api_client, bw_instances_utils=bw_instances_utils, args=args, data=data)
```

`db` is the retired handle and raises `RetiredDBError` if used; use `api_client` instead.

!!! info "Available Python Libraries"

    BunkerWeb's Web UI includes a set of pre-installed Python libraries that you can use in your plugin's `actions.py` or other UI-related scripts. These are available out-of-the-box without needing additional installations.

    Here's the complete list of included libraries:

    - **bcrypt** - Password hashing library
    - **biscuit-python** - Biscuit authentication tokens
    - **certbot** - ACME client for Let's Encrypt
    - **Flask** - Web framework
    - **Flask-Login** - User session management
    - **Flask-Session[cachelib]** - Server-side session storage
    - **Flask-WTF** - Form handling and CSRF protection
    - **gunicorn[gthread]** - WSGI HTTP server
    - **pillow** - Image processing
    - **psutil** - System and process utilities
    - **python_dateutil** - Date and time utilities
    - **qrcode** - QR code generation
    - **regex** - Advanced regular expressions
    - **urllib3** - HTTP client
    - **user_agents** - User agent parsing

    !!! tip "Using Libraries in Your Plugin"
        To import and use these libraries in your `actions.py` file, simply use the standard Python `import` statement. For example:

        ```python
        from flask import request
        import bcrypt
        ```

    ??? warning "External Libraries"
        If you need libraries not listed above, install them inside the `ui` folder of your plugin and import them using the classical `import` directive. Ensure compatibility with the existing environment to avoid conflicts.

**Some examples**

- Retrieve form submitted data

```python
from flask import request

def myplugin(**kwargs) :
	my_form_value = request.form["my_form_input"]
  return my_form_value
```

- Access app config

**action.py**
```python
from flask import request

def pre_render(**kwargs) :
	config = kwargs['app'].config["CONFIG"].get_config(methods=False)
  return config
```

**template**
```html
<!-- metadata + config -->
<div>{{ pre_render }}</div>
```

### Hooks.py

This documentation outlines the lifecycle hooks used for managing different stages of a request within the application. Each hook is associated with a specific phase.

=== "before_request"
    These hooks are executed **before** processing an incoming request. They are typically used for pre-processing tasks such as authentication, validation, or logging.

    If the hook returns a response object, Flask will skip the request handling and return the response directly. This can be useful for short-circuiting the request processing pipeline.

    **Example:**

    ```python
    from flask import request, Response

    def before_request():
        print("Before-request: Validating request...", flush=True)
        # Perform authentication, validation, or logging here
        if not is_valid_request(request): # We are in the app context
            return Response("Invalid request!", status=400)

    def is_valid_request(request):
        # Dummy validation logic
        return "user" in request
    ```
=== "after_request"
    These hooks that run **after** the request has been processed. They are ideal for post-processing tasks such as cleanup, additional logging, or modifying the response before it is sent back.

    They receive the response object as an argument and can modify it before returning it. The first after_request hook to return a response will be used as the final response.

    **Example:**

    ```python
    from flask import request

    def after_request(response):
        print("After-request: Logging response...", flush=True)
        # Perform logging, cleanup, or response modifications here
        log_response(response)
        return response

    def log_response(response):
        # Dummy logging logic
        print("Response logged:", response, flush=True)
    ```
=== "teardown_request"
    These hooks are invoked when the request context is being torn down. These hooks are used for releasing resources or handling errors that occurred during the request lifecycle.

    **Example:**

    ```python
    def teardown_request(error=None):
        print("Teardown-request: Cleaning up resources...", flush=True)
        # Perform cleanup, release resources, or handle errors here
        if error:
            handle_error(error)
        cleanup_resources()

    def handle_error(error):
        # Dummy error handling logic
        print("Error encountered:", error, flush=True)

    def cleanup_resources():
        # Dummy resource cleanup logic
        print("Resources have been cleaned up.", flush=True)
    ```
=== "context_processor"
    These hooks are used to inject additional context into templates or views. They enrich the runtime context by passing common data (like user information or configuration settings) to the templates.

    If a context processor returns a dictionary, the keys and values will be added to the context for all templates. This allows you to share data across multiple views or templates.

    **Example:**

    ```python
    def context_processor() -> dict:
        print("Context-processor: Injecting context data...", flush=True)
        # Return a dictionary containing context data for templates/views
        return {
            "current_user": "John Doe",
            "app_version": "1.0.0",
            "feature_flags": {"new_ui": True}
        }
    ```

This lifecycle hook design provides a modular and systematic approach to managing various aspects of a request's lifecycle:

- **Modularity:** Each hook is responsible for a distinct phase, ensuring that concerns are separated.
- **Maintainability:** Developers can easily add, modify, or remove hook implementations without impacting other parts of the request lifecycle.
- **Extensibility:** The framework is flexible, allowing for additional hooks or enhancements as application requirements evolve.

By clearly defining the responsibilities of each hook and their associated logging prefixes, the system ensures that each stage of request processing is transparent and manageable.

### Blueprints

In Flask, **blueprints** serve as a modular way to organize related components—such as views, templates, and static files—within your application. They allow you to group functionality logically and can be used to create new sections of your app or override existing ones.

#### Creating a Blueprint

To define a blueprint, you create an instance of the `Blueprint` class, specifying its name and import path. You then define routes and views associated with this blueprint.

**Example: Defining a New Blueprint**

```python
from os.path import dirname
from flask import Blueprint, render_template

# Define the blueprint
my_blueprint = Blueprint('my_blueprint', __name__, template_folder=dirname(__file__) + '/templates') # The template_folder is set to avoid conflicts with the original blueprint

# Define a route within the blueprint
@my_blueprint.route('/my_blueprint')
def my_blueprint_page():
    return render_template('my_blueprint.html')
```


In this example, a blueprint named `my_blueprint` is created, and a route `/my_blueprint` is defined within it.

#### Overriding an Existing Blueprint

Blueprints can also override existing ones to modify or extend functionality. To do this, ensure that the new blueprint has the same name as the one you're overriding and register it after the original.

**Example: Overriding an Existing Blueprint**

```python
from os.path import dirname
from flask import Flask, Blueprint

# Original blueprint
instances = Blueprint('instances', __name__, template_folder=dirname(__file__) + '/templates') # The template_folder is set to avoid conflicts with the original blueprint

@instances.route('/instances')
def override_instances():
    return "My new instances page"
```

In this scenario, accessing the URL `/instances` will display "My new instances page" because the `instances` blueprint, registered last, overrides the original `instances` blueprint.

!!! warning "About overriding"
    Be cautious when overriding existing blueprints, as it can impact the behavior of the application. Ensure that the changes align with the application's requirements and do not introduce unexpected side effects.

    All existing routes will be removed from he original blueprint, so you will need to re-implement them if needed.

#### Naming Conventions

!!! danger "Important"
    Ensure the blueprint’s name matches the blueprint variable name, else it will not be considered as a valid blueprint and will not be registered.

For consistency and clarity, it's advisable to follow these naming conventions:

- **Blueprint Names**: Use short, all-lowercase names. Underscores can be used for readability, e.g., `user_auth`.

- **File Names**: Match the filename to the blueprint name, ensuring it's all lowercase with underscores as needed, e.g., `user_auth.py`.

This practice aligns with Python's module naming conventions and helps maintain a clear project structure.

**Example: Blueprint and File Naming**

```
plugin /
    ui / blueprints / user_auth.py
                      templates / user_auth.html
```

In this structure, `user_auth.py` contains the `user_auth` blueprint, and `user_auth.html` is the associated template, adhering to the recommended naming conventions.

### Plugin translations

A plugin can ship its own translation catalog and have it merged into the admin UI, both in the browser (`t()`) and server-side (`_()` in a Jinja template). No `plugin.json` declaration or build step is needed.

Two layouts are supported, in order:

1. `ui/blueprints/static/locales/<lang>.json` for a plugin with a Flask blueprint.
2. `ui/static/locales/<lang>.json` for a simple `ui/template.html` page.

`en.json` is the required fallback; every other language file is optional. Keep keys under your plugin id, such as `{"my_plugin": {"title": "..."}}`. A colliding leaf cannot override a core key or an already-loaded plugin key: its value is dropped with a warning. New leaves under an existing namespace merge normally.

Server-side `_()` cannot interpolate `{{var}}` placeholders as the browser's `t()` can. Use `t()` in the browser for strings requiring substitution.

### UI plugins: supported surface

The web UI holds no database connection. Plugin UI code reaches the central API through **`PLUGIN_API`**:

```python
from app.dependencies import PLUGIN_API


def my_page():
    return PLUGIN_API.get_services(with_drafts=True)
```

`ui/actions.py` receives it as `api_client`:

```python
def pre_render(**kwargs):
    return {"services": kwargs["api_client"].get_services(with_drafts=True)}
```

These methods are the compatibility promise between minor versions; other UI-client methods are internal. `PLUGIN_API` is not a security boundary: plugin code runs in the UI process, so install only plugins you trust.

| Method | What it returns |
| --- | --- |
| `get_global_settings(full=False, methods=False, with_drafts=False, filtered_settings=None, global_only=True)` | The configuration as a flat dict. |
| `get_plugins(type="all", with_data=False, only_enabled=False, with_settings=True)` | Installed plugins and settings schema. |
| `get_services(with_drafts=True)` / `get_service(service_id, full=False, methods=True, with_drafts=True)` | Services or one service configuration. |
| `get_configs(service=None, type=None, with_drafts=True, with_data=False)` / `get_config_item(service, type, name, with_data=True)` | Custom configs. |
| `create_config(**kwargs)` / `update_config(service, type, name, body=None, **kwargs)` / `delete_config(service, type, name)` | Custom config writes. |
| `get_cache_files(service=None, plugin=None, job_name=None, with_data=False)` / `get_cache_file(service, plugin, job, filename, download=False)` | Job cache entries. |
| `get_jobs()` / `get_last_job_run(name)` | Registered jobs and last run. |
| `readonly` | `True` when the database is read-only. |

Settings are not written through `PLUGIN_API`: use `BW_CONFIG.edit_global_conf()` or `BW_CONFIG.edit_service()`, which validate them first.

**Migrating from 1.6.** `app.dependencies.DB` is retired; using it raises a `RuntimeError` naming the plugin. Replace `DB.get_config(...)` with `PLUGIN_API.get_global_settings(...)` or `PLUGIN_API.get_service(...)`, custom-config calls with the matching `get_config*` / config-write methods, job-cache calls with `get_cache_files(..., with_data=True)`, and `kwargs["db"]` in `ui/actions.py` with `kwargs["api_client"]`. `DB._db_session()` has no replacement: the UI has no database session. `DB` is falsy, so replace `if DB is not None:` with `if DB:` before accessing it.
