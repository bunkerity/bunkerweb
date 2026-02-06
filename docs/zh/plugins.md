# 插件

BunkerWeb 附带一个插件系统，可以轻松添加新功能。安装插件后，您可以使用插件定义的其他设置来管理它。

## 官方插件

以下是我们维护的“官方”插件列表（更多信息请参阅 [bunkerweb-plugins](https://github.com/bunkerity/bunkerweb-plugins) 仓库）：

|      名称      | 版本  | 描述                                                                     |                                                链接                                                 |
| :------------: | :---: | :----------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------: |
|   **ClamAV**   |  1.9  | 使用 ClamAV 杀毒引擎自动扫描上传的文件，并在检测到文件为恶意时拒绝请求。 |     [bunkerweb-plugins/clamav](https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav)     |
|   **Coraza**   |  1.9  | 使用 Coraza WAF（ModSecurity 的替代品）检查请求。                        |     [bunkerweb-plugins/coraza](https://github.com/bunkerity/bunkerweb-plugins/tree/main/coraza)     |
|  **Discord**   |  1.9  | 使用 Webhook 将安全通知发送到 Discord 频道。                             |    [bunkerweb-plugins/discord](https://github.com/bunkerity/bunkerweb-plugins/tree/main/discord)    |
|   **Slack**    |  1.9  | 使用 Webhook 将安全通知发送到 Slack 频道。                               |      [bunkerweb-plugins/slack](https://github.com/bunkerity/bunkerweb-plugins/tree/main/slack)      |
| **VirusTotal** |  1.9  | 使用 VirusTotal API 自动扫描上传的文件，并在检测到文件为恶意时拒绝请求。 | [bunkerweb-plugins/virustotal](https://github.com/bunkerity/bunkerweb-plugins/tree/main/virustotal) |
|  **WebHook**   |  1.9  | 使用 Webhook 将安全通知发送到自定义 HTTP 端点。                          |    [bunkerweb-plugins/webhook](https://github.com/bunkerity/bunkerweb-plugins/tree/main/webhook)    |

## 如何使用插件

### 自动

如果您想快速安装外部插件，可以使用 `EXTERNAL_PLUGIN_URLS` 设置。它接受一个以空格分隔的 URL 列表，每个 URL 指向一个包含一个或多个插件的压缩（zip 格式）存档。

如果您想自动安装官方插件，可以使用以下值：`EXTERNAL_PLUGIN_URLS=https://github.com/bunkerity/bunkerweb-plugins/archive/refs/tags/v1.9.zip`

### 手动

第一步是通过将其文件放置在相应的 `plugins` 数据文件夹中来安装插件。该过程取决于您的集成：

=== "Docker"

    当使用 [Docker 集成](integrations.md#docker)时，插件必须放置在调度器容器中挂载在 `/data/plugins` 的卷中。

    首先要做的是创建 plugins 文件夹：

    ```shell
    mkdir -p ./bw-data/plugins
    ```

    然后，您可以将您选择的插件放入该文件夹中：

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    ??? warning "为持久化数据使用本地文件夹"
        调度器在容器内以**UID 101 和 GID 101 的非特权用户**身份运行。这背后的原因是安全性：万一漏洞被利用，攻击者将不会拥有完全的 root (UID/GID 0) 权限。
        但有一个缺点：如果您为持久化数据使用**本地文件夹**，您将需要**设置正确的权限**，以便非特权用户可以向其中写入数据。类似这样的操作应该可以解决问题：

        ```shell
        mkdir bw-data && \
        chown root:101 bw-data && \
        chmod 770 bw-data
        ```

        或者，如果文件夹已经存在：

        ```shell
        chown -R root:101 bw-data && \
        chmod -R 770 bw-data
        ```

        如果您正在使用[无根模式的 Docker](https://docs.docker.com/engine/security/rootless) 或 [podman](https://podman.io/)，容器中的 UID 和 GID 将映射到主机上不同的 UID 和 GID。您首先需要检查您的初始 subuid 和 subgid：

        ```shell
        grep ^$(whoami): /etc/subuid && \
        grep ^$(whoami): /etc/subgid
        ```

        例如，如果您的值为 **100000**，则映射的 UID/GID 将为 **100100** (100000 + 100)：

        ```shell
        mkdir bw-data && \
        sudo chgrp 100100 bw-data && \
        chmod 770 bw-data
        ```

        或者如果文件夹已经存在：

        ```shell
        sudo chgrp -R 100100 bw-data && \
        sudo chmod -R 770 bw-data
        ```

    然后，您可以在启动 Docker 堆栈时挂载该卷：

    ```yaml
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        volumes:
          - ./bw-data:/data
    ...
    ```

=== "Docker autoconf"

    当使用 [Docker autoconf 集成](integrations.md#docker-autoconf)时，插件必须放置在调度器容器中挂载在 `/data/plugins` 的卷中。


    首先要做的是创建 plugins 文件夹：

    ```shell
    mkdir -p ./bw-data/plugins
    ```

    然后，您可以将您选择的插件放入该文件夹中：

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    因为调度器以 UID 和 GID 101 的非特权用户运行，您需要编辑权限：

    ```shell
    chown -R 101:101 ./bw-data
    ```

    然后您可以在启动 Docker 堆栈时挂载该卷：

    ```yaml
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        volumes:
          - ./bw-data:/data
    ...
    ```

=== "Swarm"

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

    当使用 [Swarm 集成](integrations.md#swarm)时，插件必须放置在调度器容器中挂载在 `/data/plugins` 的卷中。

    !!! info "Swarm 卷"
        本文档不涉及配置一个当调度器服务在不同节点上运行时将持久化的 Swarm 卷。我们将假设您在所有节点上都有一个挂载在 `/shared` 的共享文件夹。

    首先要做的是创建 plugins 文件夹：

    ```shell
    mkdir -p /shared/bw-plugins
    ```

    然后，您可以将您选择的插件放入该文件夹中：

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /shared/bw-plugins
    ```

    因为调度器以 UID 和 GID 101 的非特权用户运行，您需要编辑权限：

    ```shell
    chown -R 101:101 /shared/bw-plugins
    ```

    然后您可以在启动 Swarm 堆栈时挂载该卷：

    ```yaml
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        volumes:
          - /shared/bw-plugins:/data/plugins
    ...
    ```

=== "Kubernetes"

    当使用 [Kubernetes 集成](integrations.md#kubernetes)时，插件必须放置在调度器容器中挂载在 `/data/plugins` 的卷中。

    首先要做的是声明一个将包含我们插件数据的 [PersistentVolumeClaim](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)：

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

    您现在可以添加卷挂载和一个 init 容器来自动配置该卷：

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
              image: bunkerity/bunkerweb-scheduler:1.6.8
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

    当使用 [Linux 集成](integrations.md#linux)时，插件必须写入 `/etc/bunkerweb/plugins` 文件夹：

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /etc/bunkerweb/plugins && \
    chown -R nginx:nginx /etc/bunkerweb/plugins
    ```

## 编写插件

### 结构 {#structure}

!!! tip "现有插件"

    如果文档不够，您可以查看[官方插件](https://github.com/bunkerity/bunkerweb-plugins)和[核心插件](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/src/common/core)的现有源代码（已包含在 BunkerWeb 中，但从技术上讲它们是插件）。

插件结构如下所示：
```
plugin /
    confs / conf_type / conf_name.conf
    ui / actions.py
         hooks.py
         template.html
         blueprints / <blueprint_file(s)>
              templates / <blueprint_template(s)>
    jobs / my-job.py
    templates / my-template.json
          my-template / configs / conf_type / conf_name.conf
    plugin.lua
    plugin.json
```

- **conf_name.conf**：添加[自定义 NGINX 配置](advanced.md#custom-configurations)（作为 Jinja2 模板）。

- **actions.py**：在 Flask 服务器上执行的脚本。此脚本在 Flask 上下文中运行，使您可以访问 `jinja2` 和 `requests` 等库和实用程序。

- **hooks.py**：包含 flask 钩子的自定义 Python 文件，将在加载插件时执行。

- **template.html**：通过 UI 访问的自定义插件页面。

- **blueprints 文件夹（在 ui 内）**：
  此文件夹用于覆盖现有的 Flask 蓝图或创建新的蓝图。在内部，您可以包含蓝图文件和一个可选的 **templates** 子文件夹，用于蓝图特定的模板。

- **jobs py 文件**：由调度器作为作业执行的自定义 Python 文件。

- **my-template.json**：添加[自定义模板](concepts.md#templates)以覆盖设置的默认值并轻松应用自定义配置。

- **plugin.lua**：使用 [NGINX LUA 模块](https://github.com/openresty/lua-nginx-module)在 NGINX 上执行的代码。

- **plugin.json**：您的插件的元数据、设置和作业定义。

### 开始

第一步是创建一个将包含插件的文件夹：

```shell
mkdir myplugin && \
cd myplugin
```

### 元数据

一个名为 **plugin.json** 的文件，写在插件文件夹的根目录下，必须包含有关插件的元数据。这是一个示例：

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

以下是字段的详细信息：

|     字段      | 强制  |  类型  | 描述                                                                        |
| :-----------: | :---: | :----: | :-------------------------------------------------------------------------- |
|     `id`      |  是   | 字符串 | 插件的内部 ID：必须在其他插件（包括“核心”插件）中唯一，并且只包含小写字符。 |
|    `name`     |  是   | 字符串 | 您的插件的名称。                                                            |
| `description` |  是   | 字符串 | 您的插件的描述。                                                            |
|   `version`   |  是   | 字符串 | 您的插件的版本。                                                            |
|   `stream`    |  是   | 字符串 | 关于流支持的信息：`no`、`yes` 或 `partial`。                                |
|  `settings`   |  是   |  字典  | 您的插件的设置列表。                                                        |
|    `jobs`     |  否   |  列表  | 您的插件的作业列表。                                                        |
|    `bwcli`    |  否   |  字典  | 将 CLI 命令名称映射到存储在插件 'bwcli' 目录中的文件，以公开 CLI 插件。     |

每个设置都有以下字段（键是在配置中使用的设置的 ID）：

|    字段    | 强制  |  类型  | 描述                                                  |
| :--------: | :---: | :----: | :---------------------------------------------------- |
| `context`  |  是   | 字符串 | 设置的上下文：`multisite` 或 `global`。               |
| `default`  |  是   | 字符串 | 设置的默认值。                                        |
|   `help`   |  是   | 字符串 | 关于插件的帮助文本（在 Web UI 中显示）。              |
|    `id`    |  是   | 字符串 | Web UI 用于 HTML 元素的内部 ID。                      |
|  `label`   |  是   | 字符串 | Web UI 显示的标签。                                   |
|  `regex`   |  是   | 字符串 | 用于验证用户提供的值的正则表达式。                    |
|   `type`   |  是   | 字符串 | 字段的类型：`text`、`check`、`select` 或 `password`。 |
| `multiple` |  否   | 字符串 | 用于将多个带有数字后缀的设置分组的唯一 ID。           |
|  `select`  |  否   |  列表  | 当 `type` 为 `select` 时，可能的字符串值列表。        |

每个作业都有以下字段：

|  字段   | 强制  |  类型  | 描述                                                                                              |
| :-----: | :---: | :----: | :------------------------------------------------------------------------------------------------ |
| `name`  |  是   | 字符串 | 作业的名称。                                                                                      |
| `file`  |  是   | 字符串 | 作业文件夹内的文件名。                                                                            |
| `every` |  是   | 字符串 | 作业调度频率：`minute`、`hour`、`day`、`week` 或 `once`（无频率，仅在（重新）生成配置之前一次）。 |

### CLI 命令

插件可以使用在 `bwcli plugin <plugin_id> ...` 下运行的自定义命令扩展 `bwcli` 工具：

1. 在您的插件中添加一个 `bwcli` 目录，并为每个命令放置一个文件（例如 `bwcli/list.py`）。CLI 在执行文件之前将插件路径添加到 `sys.path`。
2. 在 `plugin.json` 的可选 `bwcli` 部分中声明命令，将每个命令名称映射到其可执行文件名。

```json
{
  "bwcli": {
    "list": "list.py",
    "save": "save.py"
  }
}
```

一旦安装了插件，调度程序就会自动公开声明的命令。核心插件（例如 `src/common/core/backup` 中的 `backup`）也遵循相同的模式。

### 配置

您可以通过添加一个名为 **confs** 的文件夹来添加自定义 NGINX 配置，其内容类似于[自定义配置](advanced.md#custom-configurations)。**confs** 内的每个子文件夹将包含 [jinja2](https://jinja.palletsprojects.com) 模板，这些模板将在相应的上下文（`http`、`server-http`、`default-server-http`、`stream`、`server-stream`、`modsec`、`modsec-crs`、`crs-plugins-before` 和 `crs-plugins-after`）下生成和加载。

这是一个名为 **example.conf** 的 **confs/server-http** 文件夹内的配置模板文件示例：

```nginx
location /setting {
  default_type 'text/plain';
    content_by_lua_block {
        ngx.say('{{ DUMMY_SETTING }}')
    }
}
```

`{{ DUMMY_SETTING }}` 将被插件用户选择的 `DUMMY_SETTING` 的值替换。

### 模板

有关更多信息，请查看[模板文档](concepts.md#templates)。

### LUA

#### 主脚本

在底层，BunkerWeb 使用 [NGINX LUA 模块](https://github.com/openresty/lua-nginx-module)在 NGINX 内部执行代码。需要执行代码的插件必须在插件文件夹的根目录下提供一个 lua 文件，使用 **plugin.json** 的 `id` 值作为其名称。这是一个名为 **myplugin.lua** 的示例：

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

声明的函数会在特定的上下文中自动调用。以下是每个函数的详细信息：

|     函数      |                                           上下文                                            | 描述                                                                                 | 返回值                                                                                                                                                                                                                                                                                                                             |
| :-----------: | :-----------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|    `init`     |          [init_by_lua](https://github.com/openresty/lua-nginx-module#init_by_lua)           | 当 NGINX 刚启动或收到重新加载命令时调用。典型的用例是准备插件将使用的任何数据。      | `ret`, `msg`<ul><li>`ret` (布尔值)：如果没有错误则为 true，否则为 false</li><li>`msg` (字符串)：成功或错误消息</li></ul>                                                                                                                                                                                                           |
|     `set`     |           [set_by_lua](https://github.com/openresty/lua-nginx-module#set_by_lua)            | 在服务器接收到每个请求之前调用。典型的用例是在访问阶段之前进行计算。                 | `ret`, `msg`<ul><li>`ret` (布尔值)：如果没有错误则为 true，否则为 false</li><li>`msg` (字符串)：成功或错误消息</li></ul>                                                                                                                                                                                                           |
|   `access`    |        [access_by_lua](https://github.com/openresty/lua-nginx-module#access_by_lua)         | 在服务器接收到每个请求时调用。典型的用例是在这里进行安全检查，并在需要时拒绝请求。   | `ret`, `msg`,`status`,`redirect`<ul><li>`ret` (布尔值)：如果没有错误则为 true，否则为 false</li><li>`msg` (字符串)：成功或错误消息</li><li>`status` (数字)：中断当前进程并返回 [HTTP 状态](https://github.com/openresty/lua-nginx-module#http-status-constants)</li><li>`redirect` (URL)：如果设置，将重定向到给定的 URL</li></ul> |
|     `log`     |           [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)            | 当请求完成时（在它被记录到访问日志之前）调用。典型的用例是例如进行统计或计算计数器。 | `ret`, `msg`<ul><li>`ret` (布尔值)：如果没有错误则为 true，否则为 false</li><li>`msg` (字符串)：成功或错误消息</li></ul>                                                                                                                                                                                                           |
| `log_default` |           [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)            | 与 `log` 相同，但仅在默认服务器上调用。                                              | `ret`, `msg`<ul><li>`ret` (布尔值)：如果没有错误则为 true，否则为 false</li><li>`msg` (字符串)：成功或错误消息</li></ul>                                                                                                                                                                                                           |
|   `preread`   | [preread_by_lua](https://github.com/openresty/stream-lua-nginx-module#preread_by_lua_block) | 与 `access` 函数类似，但用于流模式。                                                 | `ret`, `msg`,`status`<ul><li>`ret` (布尔值)：如果没有错误则为 true，否则为 false</li><li>`msg` (字符串)：成功或错误消息</li><li>`status` (数字)：中断当前进程并返回 [status](https://github.com/openresty/lua-nginx-module#http-status-constants)</li></ul>                                                                        |
| `log_stream`  |     [log_by_lua](https://github.com/openresty/stream-lua-nginx-module#log_by_lua_block)     | 与 `log` 函数类似，但用于流模式。                                                    | `ret`, `msg`<ul><li>`ret` (布尔值)：如果没有错误则为 true，否则为 false</li><li>`msg` (字符串)：成功或错误消息</li></ul>                                                                                                                                                                                                           |

#### 库

[NGINX LUA 模块](https://github.com/openresty/lua-nginx-module)和 [NGINX stream LUA 模块](https://github.com/openresty/stream-lua-nginx-module)的所有指令都可用。此外，您可以使用 BunkerWeb 中包含的 LUA 库：有关完整列表，请参见[此脚本](https://github.com/bunkerity/bunkerweb/blobsrc/deps/clone.sh)。

如果您需要其他库，可以将它们放在插件的根文件夹中，并通过在它们前面加上您的插件 ID 来访问它们。这是一个名为 **mylibrary.lua** 的示例文件：

```lua
local _M = {}

_M.dummy = function ()
	return "dummy"
end

return _M
```

这是您如何从 **myplugin.lua** 文件中使用它的方法：

```lua
local mylibrary = require "myplugin.mylibrary"

...

mylibrary.dummy()

...
```

#### 助手

一些助手模块提供了常见的有用助手：

- `self.variables`：允许访问和存储插件的属性
- `self.logger`：打印日志
- `bunkerweb.utils`：各种有用的函数
- `bunkerweb.datastore`：访问一个实例上的全局共享数据（键/值存储）
- `bunkerweb.clusterstore`：访问 BunkerWeb 实例之间共享的 Redis 数据存储（键/值存储）

要访问这些函数，您首先需要**引用**这些模块：

```lua
local utils       = require "bunkerweb.utils"
local datastore   = require "bunkerweb.datastore"
local clustestore = require "bunkerweb.clustertore"
```

检索一个设置值：

```lua
local myvar = self.variables["DUMMY_SETTING"]
if not myvar then
    self.logger:log(ngx.ERR, "can't retrieve setting DUMMY_SETTING")
else
    self.logger:log(ngx.NOTICE, "DUMMY_SETTING = " .. value)
end
```

在本地缓存中存储一些东西：

```lua
local ok, err = self.datastore:set("plugin_myplugin_something", "somevalue")
if not ok then
    self.logger:log(ngx.ERR, "can't save plugin_myplugin_something into datastore : " .. err)
else
    self.logger:log(ngx.NOTICE, "successfully saved plugin_myplugin_something into datastore")
end
```

检查一个 IP 地址是否是全局的：

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

!!! tip "更多示例"

    如果您想查看可用函数的完整列表，可以查看仓库的 [lua 目录](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/src/bw/lua/bunkerweb)中存在的文件。

### 作业

BunkerWeb 使用内部作业调度器来执行定期任务，例如使用 certbot 续订证书、下载黑名单、下载 MMDB 文件等。您可以通过将任务放入名为 **jobs** 的子文件夹中，并在 **plugin.json** 元数据文件中列出它们来添加您选择的任务。不要忘记为每个人添加执行权限，以避免用户克隆和安装您的插件时出现任何问题。

### 插件页面

与 Web UI 相关的所有内容都位于 **ui** 子文件夹中，正如我们在[之前的结构部分](#structure)中看到的那样。

#### 先决条件

当您想要创建一个插件页面时，您需要两个文件：

- **template.html**，可以通过 **GET /plugins/<*plugin_id*>** 访问。

- **actions.py**，您可以在其中添加一些脚本和逻辑，通过 **POST /plugins/<*plugin_id*>** 访问。请注意，此文件**需要一个与插件同名的函数**才能工作。即使该函数为空，也需要此文件。

#### 基本示例

!!! info "Jinja 2 模板"
    **template.html** 文件是一个 Jinja2 模板，如果需要，请参阅 [Jinja2 文档](https://jinja.palletsprojects.com)。

我们可以先不考虑 **actions.py** 文件，**只在 GET 情况下使用模板**。模板可以访问应用程序上下文和库，因此您可以使用 Jinja、请求或 flask 实用程序。

例如，您可以在模板中像这样获取请求参数：

```html
<p>请求参数 : {{ request.args.get() }}.</p>```

#### Actions.py

!!! warning "CSRF 令牌"

    请注意，每个表单提交都受到 CSRF 令牌的保护，您需要在您的表单中包含以下代码片段：
    ```html
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
    ```

当发送 **POST /plugins/<*plugin_id*>** 时，您可以使用 **actions.py** 文件为您的插件页面添加额外的脚本。

在 **actions.py** 中，您默认有两个函数：

**pre_render 函数**

这允许您在 **GET** 模板时检索数据，并使用 Jinja 中可用的 pre_render 变量来更动态地显示内容。

```python
def pre_render(**kwargs)
  return <pre_render_data>
```

BunkerWeb 会给您发送这种类型的响应：


```python
return jsonify({"status": "ok|ko", "code" : XXX, "data": <pre_render_data>}), 200
```

**<*plugin_id*> 函数**

这允许您在从模板端点进行 **POST** 时检索数据，该端点必须在 AJAX 中使用。

```python
def myplugin(**kwargs)
  return <plugin_id_data>
```

BunkerWeb 会给你发送这种类型的响应：

```python
return jsonify({"message": "ok", "data": <plugin_id_data>}), 200
```

**您可以从 action.py 访问什么**

以下是在 action.py 函数上传递和访问的参数：

```python
function(app=app, args=request.args.to_dict() or request.json or None)
```

!!! info "可用的 Python 库"

    BunkerWeb 的 Web UI 包含一组预安装的 Python 库，您可以在插件的 `actions.py` 或其他与 UI 相关的脚本中使用。这些库开箱即用，无需额外安装。

    以下是包含的库的完整列表：

    - **bcrypt** - 密码哈希库
    - **biscuit-python** - Biscuit 认证令牌
    - **certbot** - 用于 Let's Encrypt 的 ACME 客户端
    - **Flask** - Web 框架
    - **Flask-Login** - 用户会话管理
    - **Flask-Session[cachelib]** - 服务器端会话存储
    - **Flask-WTF** - 表单处理和 CSRF 保护
    - **gunicorn[gthread]** - WSGI HTTP 服务器
    - **pillow** - 图像处理
    - **psutil** - 系统和进程实用程序
    - **python_dateutil** - 日期和时间实用程序
    - **qrcode** - 二维码生成
    - **regex** - 高级正则表达式
    - **urllib3** - HTTP 客户端
    - **user_agents** - 用户代理解析

    !!! tip "在您的插件中使用库"
        要在您的 `actions.py` 文件中导入和使用这些库，只需使用标准的 Python `import` 语句。例如：

        ```python
        from flask import request
        import bcrypt
        ```

    ??? warning "外部库"
        如果您需要上面未列出的库，请将它们安装在您插件的 `ui` 文件夹中，并使用经典的 `import` 指令导入它们。请确保与现有环境兼容以避免冲突。

**一些例子**

- 检索表单提交的数据

```python
from flask import request

def myplugin(**kwargs) :
	my_form_value = request.form["my_form_input"]
  return my_form_value
```

- 访问应用程序配置

**action.py**
```python
from flask import request

def pre_render(**kwargs) :
	config = kwargs['app'].config["CONFIG"].get_config(methods=False)
  return config
```

**模板**
```html
<!-- 元数据 + 配置 -->
<div>{{ pre_render }}</div>
```

### Hooks.py

本文档概述了用于管理应用程序内请求不同阶段的生命周期钩子。每个钩子都与一个特定的阶段相关联。

=== "before_request"
    这些钩子在处理传入请求**之前**执行。它们通常用于预处理任务，例如身份验证、验证或日志记录。

    如果钩子返回一个响应对象，Flask 将跳过请求处理并直接返回该响应。这对于短路请求处理管道很有用。

    **示例：**

    ```python
    from flask import request, Response

    def before_request():
        print("Before-request: Validating request...", flush=True)
        # 在此处执行身份验证、验证或日志记录
        if not is_valid_request(request): # 我们在应用程序上下文中
            return Response("Invalid request!", status=400)

    def is_valid_request(request):
        # 虚拟验证逻辑
        return "user" in request
    ```
=== "after_request"
    这些钩子在请求处理**之后**运行。它们非常适合后处理任务，例如清理、额外的日志记录或在发送回响应之前对其进行修改。

    它们接收响应对象作为参数，并可以在返回之前对其进行修改。第一个返回响应的 after_request 钩子将用作最终响应。

    **示例：**

    ```python
    from flask import request

    def after_request(response):
        print("After-request: Logging response...", flush=True)
        # 在此处执行日志记录、清理或响应修改
        log_response(response)
        return response

    def log_response(response):
        # 虚拟日志记录逻辑
        print("Response logged:", response, flush=True)
    ```
=== "teardown_request"
    当请求上下文被拆除时，会调用这些钩子。这些钩子用于释放资源或处理请求生命周期中发生的错误。

    **示例：**

    ```python
    def teardown_request(error=None):
        print("Teardown-request: Cleaning up resources...", flush=True)
        # 在此处执行清理、释放资源或处理错误
        if error:
            handle_error(error)
        cleanup_resources()

    def handle_error(error):
        # 虚拟错误处理逻辑
        print("Error encountered:", error, flush=True)

    def cleanup_resources():
        # 虚拟资源清理逻辑
        print("Resources have been cleaned up.", flush=True)
    ```
=== "context_processor"
    这些钩子用于向模板或视图注入额外的上下文。它们通过将通用数据（如用户信息或配置设置）传递给模板来丰富运行时上下文。

    如果上下文处理器返回一个字典，则键和值将添加到所有模板的上下文中。这允许您在多个视图或模板之间共享数据。

    **示例：**

    ```python
    def context_processor() -> dict:
        print("Context-processor: Injecting context data...", flush=True)
        # 返回一个包含模板/视图上下文数据的字典
        return {
            "current_user": "John Doe",
            "app_version": "1.0.0",
            "feature_flags": {"new_ui": True}
        }
    ```

这种生命周期钩子设计为管理请求生命周期的各个方面提供了一种模块化和系统化的方法：

- **模块化：** 每个钩子都负责一个独特的阶段，确保了关注点的分离。
- **可维护性：** 开发人员可以轻松地添加、修改或删除钩子实现，而不会影响请求生命周期的其他部分。
- **可扩展性：** 该框架是灵活的，允许随着应用程序需求的发展添加额外的钩子或增强功能。

通过明确定义每个钩子的职责及其相关的日志记录前缀，系统确保了请求处理的每个阶段都是透明和可管理的。

### 蓝图

在 Flask 中，**蓝图**是一种模块化的方式，用于组织应用程序中的相关组件——例如视图、模板和静态文件。它们允许您逻辑地对功能进行分组，并可用于创建应用程序的新部分或覆盖现有部分。

#### 创建一个蓝图

要定义一个蓝图，您需要创建一个 `Blueprint` 类的实例，并指定其名称和导入路径。然后，您可以定义与此蓝图关联的路由和视图。

**示例：定义一个新的蓝图**

```python
from os.path import dirname
from flask import Blueprint, render_template

# 定义蓝图
my_blueprint = Blueprint('my_blueprint', __name__, template_folder=dirname(__file__) + '/templates') # 设置 template_folder 是为了避免与原始蓝图冲突

# 在蓝图内定义一个路由
@my_blueprint.route('/my_blueprint')
def my_blueprint_page():
    return render_template('my_blueprint.html')
```


在此示例中，创建了一个名为 `my_blueprint` 的蓝图，并在其中定义了一个路由 `/my_blueprint`。

#### 覆盖现有蓝图

蓝图也可以覆盖现有的蓝图以修改或扩展功能。为此，请确保新蓝图的名称与您要覆盖的蓝图相同，并在原始蓝图之后注册它。

**示例：覆盖现有蓝图**

```python
from os.path import dirname
from flask import Flask, Blueprint

# 原始蓝图
instances = Blueprint('instances', __name__, template_folder=dirname(__file__) + '/templates') # 设置 template_folder 是为了避免与原始蓝图冲突

@instances.route('/instances')
def override_instances():
    return "我的新实例页面"
```

在这种情况下，访问 URL `/instances` 将显示“我的新实例页面”，因为最后注册的 `instances` 蓝图覆盖了原始的 `instances` 蓝图。

!!! warning "关于覆盖"
    在覆盖现有蓝图时要小心，因为它可能会影响应用程序的行为。确保更改与应用程序的要求一致，并且不会引入意外的副作用。

    所有现有的路由都将从原始蓝图中移除，因此如果需要，您需要重新实现它们。

#### 命名约定

!!! danger "重要"
    确保蓝图的名称与蓝图变量名称匹配，否则它将不被视为有效的蓝图，也不会被注册。

为了保持一致性和清晰度，建议遵循以下命名约定：

- **蓝图名称**：使用简短的全小写名称。可以使用下划线来提高可读性，例如 `user_auth`。

- **文件名**：将文件名与蓝图名称匹配，确保其全小写并根据需要使用下划线，例如 `user_auth.py`。

这种做法与 Python 的模块命名约定一致，有助于维护清晰的项目结构。

**示例：蓝图和文件名命名**

```
plugin /
    ui / blueprints / user_auth.py
                      templates / user_auth.html
```

在这种结构中，`user_auth.py` 包含 `user_auth` 蓝图，而 `user_auth.html` 是相关的模板，遵循了推荐的命名约定。
