# Plugins

BunkerWeb verfügt über ein Pluginsystem, das es ermöglicht, neue Funktionen einfach hinzuzufügen. Sobald ein Plugin installiert ist, können Sie es über zusätzliche, vom Plugin definierte Einstellungen verwalten.

## Offizielle Plugins

Hier ist die Liste der "offiziellen" Plugins, die wir pflegen (weitere Informationen finden Sie im Repository [bunkerweb-plugins](https://github.com/bunkerity/bunkerweb-plugins)):

|      Name      | Version | Beschreibung                                                                                                                                 |                                                Link                                                 |
| :------------: | :-----: | :------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------: |
|   **ClamAV**   |   1.9   | Scannt hochgeladene Dateien automatisch mit der ClamAV-Antiviren-Engine und lehnt die Anfrage ab, wenn eine Datei als bösartig erkannt wird. |     [bunkerweb-plugins/clamav](https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav)     |
|   **Coraza**   |   1.9   | Überprüft Anfragen mit der Coraza WAF (Alternative zu ModSecurity).                                                                          |     [bunkerweb-plugins/coraza](https://github.com/bunkerity/bunkerweb-plugins/tree/main/coraza)     |
|  **Discord**   |   1.9   | Sendet Sicherheitsbenachrichtigungen über einen Webhook an einen Discord-Kanal.                                                              |    [bunkerweb-plugins/discord](https://github.com/bunkerity/bunkerweb-plugins/tree/main/discord)    |
|   **Slack**    |   1.9   | Sendet Sicherheitsbenachrichtigungen über einen Webhook an einen Slack-Kanal.                                                                |      [bunkerweb-plugins/slack](https://github.com/bunkerity/bunkerweb-plugins/tree/main/slack)      |
| **VirusTotal** |   1.9   | Scannt hochgeladene Dateien automatisch mit der VirusTotal-API und lehnt die Anfrage ab, wenn eine Datei als bösartig erkannt wird.          | [bunkerweb-plugins/virustotal](https://github.com/bunkerity/bunkerweb-plugins/tree/main/virustotal) |
|  **WebHook**   |   1.9   | Sendet Sicherheitsbenachrichtigungen über einen Webhook an einen benutzerdefinierten HTTP-Endpunkt.                                          |    [bunkerweb-plugins/webhook](https://github.com/bunkerity/bunkerweb-plugins/tree/main/webhook)    |

## Wie man ein Plugin verwendet

### Automatisch

Wenn Sie externe Plugins schnell installieren möchten, können Sie die Einstellung `EXTERNAL_PLUGIN_URLS` verwenden. Sie akzeptiert eine durch Leerzeichen getrennte Liste von URLs, die jeweils auf ein komprimiertes (zip-Format) Archiv mit einem oder mehreren Plugins verweisen.

Sie können den folgenden Wert verwenden, wenn Sie die offiziellen Plugins automatisch installieren möchten: `EXTERNAL_PLUGIN_URLS=https://github.com/bunkerity/bunkerweb-plugins/archive/refs/tags/v1.9.zip`

### Manuell

Der erste Schritt besteht darin, das Plugin zu installieren, indem Sie seine Dateien in den entsprechenden Datenordner `plugins` legen. Das Verfahren hängt von Ihrer Integration ab:

=== "Docker"

    Bei Verwendung der [Docker-Integration](integrations.md#docker) müssen Plugins in das Volume gemountet werden, das auf `/data/plugins` im Scheduler-Container verweist.

    Als Erstes müssen Sie den Plugins-Ordner erstellen:

    ```shell
    mkdir -p ./bw-data/plugins
    ```

    Dann können Sie die Plugins Ihrer Wahl in diesen Ordner legen:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    ??? warning "Verwendung eines lokalen Ordners für persistente Daten"
        Der Scheduler läuft als **unprivilegierter Benutzer mit UID 101 und GID 101** im Container. Der Grund dafür ist die Sicherheit: Im Falle einer ausgenutzten Schwachstelle hat der Angreifer keine vollen Root-Rechte (UID/GID 0).
        Aber es gibt einen Nachteil: Wenn Sie einen **lokalen Ordner für die persistenten Daten** verwenden, müssen Sie **die richtigen Berechtigungen festlegen**, damit der unprivilegierte Benutzer Daten darin schreiben kann. Etwas wie das Folgende sollte ausreichen:

        ```shell
        mkdir bw-data && \
        chown root:101 bw-data && \
        chmod 770 bw-data
        ```

        Alternativ, wenn der Ordner bereits existiert:

        ```shell
        chown -R root:101 bw-data && \
        chmod -R 770 bw-data
        ```

        Wenn Sie [Docker im rootless-Modus](https://docs.docker.com/engine/security/rootless) oder [podman](https://podman.io/) verwenden, werden UIDs und GIDs im Container auf andere auf dem Host abgebildet. Sie müssen zuerst Ihre anfängliche subuid und subgid überprüfen:

        ```shell
        grep ^$(whoami): /etc/subuid && \
        grep ^$(whoami): /etc/subgid
        ```

        Wenn Sie beispielsweise einen Wert von **100000** haben, ist die abgebildete UID/GID **100100** (100000 + 100):

        ```shell
        mkdir bw-data && \
        sudo chgrp 100100 bw-data && \
        chmod 770 bw-data
        ```

        Oder wenn der Ordner bereits existiert:

        ```shell
        sudo chgrp -R 100100 bw-data && \
        chmod -R 770 bw-data
        ```

    Dann können Sie das Volume beim Starten Ihres Docker-Stacks mounten:

    ```yaml
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        volumes:
          - ./bw-data:/data
    ...
    ```

=== "Docker autoconf"

    Bei Verwendung der [Docker-Autoconf-Integration](integrations.md#docker-autoconf) müssen Plugins in das Volume gemountet werden, das auf `/data/plugins` im Scheduler-Container verweist.

    Als Erstes müssen Sie den Plugins-Ordner erstellen:

    ```shell
    mkdir -p ./bw-data/plugins
    ```

    Dann können Sie die Plugins Ihrer Wahl in diesen Ordner legen:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    Da der Scheduler als unprivilegierter Benutzer mit UID und GID 101 läuft, müssen Sie die Berechtigungen bearbeiten:

    ```shell
    chown -R 101:101 ./bw-data
    ```

    Dann können Sie das Volume beim Starten Ihres Docker-Stacks mounten:

    ```yaml
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        volumes:
          - ./bw-data:/data
    ...
    ```

=== "Swarm"

    !!! warning "Veraltet"
        Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](integrations.md#kubernetes).

        **Weitere Informationen finden Sie in der [Swarm-Integrationsdokumentation](integrations.md#swarm).**

    Bei Verwendung der [Swarm-Integration](integrations.md#swarm) müssen Plugins in das Volume gemountet werden, das auf `/data/plugins` im Scheduler-Container verweist.

    !!! info "Swarm-Volume"
        Die Konfiguration eines Swarm-Volumes, das bestehen bleibt, wenn der Scheduler-Dienst auf verschiedenen Knoten ausgeführt wird, wird in dieser Dokumentation nicht behandelt. Wir gehen davon aus, dass Sie einen freigegebenen Ordner auf `/shared` auf allen Knoten gemountet haben.

    Als Erstes müssen Sie den Plugins-Ordner erstellen:

    ```shell
    mkdir -p /shared/bw-plugins
    ```

    Dann können Sie die Plugins Ihrer Wahl in diesen Ordner legen:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /shared/bw-plugins
    ```

    Da der Scheduler als unprivilegierter Benutzer mit UID und GID 101 läuft, müssen Sie die Berechtigungen bearbeiten:

    ```shell
    chown -R 101:101 /shared/bw-plugins
    ```

    Dann können Sie das Volume beim Starten Ihres Swarm-Stacks mounten:

    ```yaml
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        volumes:
          - /shared/bw-plugins:/data/plugins
    ...
    ```

=== "Kubernetes"

    Bei Verwendung der [Kubernetes-Integration](integrations.md#kubernetes) müssen Plugins in das Volume gemountet werden, das auf `/data/plugins` im Scheduler-Container verweist.

    Als Erstes müssen Sie einen [PersistentVolumeClaim](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) deklarieren, der unsere Plugin-Daten enthalten wird:

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

    Sie können nun den Volume-Mount und einen Init-Container hinzufügen, um das Volume automatisch bereitzustellen:

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
              image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
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

    Bei Verwendung der [Linux-Integration](integrations.md#linux) müssen Plugins in den Ordner `/etc/bunkerweb/plugins` geschrieben werden:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /etc/bunkerweb/plugins && \
    chown -R nginx:nginx /etc/bunkerweb/plugins
    ```

## Ein Plugin schreiben

### Struktur

!!! tip "Bestehende Plugins"

    Wenn die Dokumentation nicht ausreicht, können Sie sich den bestehenden Quellcode der [offiziellen Plugins](https://github.com/bunkerity/bunkerweb-plugins) und der [Kern-Plugins](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/src/common/core) ansehen (bereits in BunkerWeb enthalten, aber technisch gesehen sind es Plugins).

Wie eine Plugin-Struktur aussieht:
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

- **conf_name.conf** : Fügen Sie [benutzerdefinierte NGINX-Konfigurationen](advanced.md#custom-configurations) (als Jinja2-Vorlagen) hinzu.

- **actions.py** : Skript, das auf dem Flask-Server ausgeführt wird. Dieses Skript wird in einem Flask-Kontext ausgeführt und gibt Ihnen Zugriff auf Bibliotheken und Dienstprogramme wie `jinja2` und `requests`.

- **hooks.py** : Benutzerdefinierte Python-Datei, die Flask-Hooks enthält und beim Laden des Plugins ausgeführt wird.

- **template.html** : Benutzerdefinierte Plugin-Seite, die über die Benutzeroberfläche aufgerufen wird.

- **blueprints-Ordner (innerhalb von ui)**:
  Dieser Ordner wird verwendet, um bestehende Flask-Blueprints zu überschreiben oder neue zu erstellen. Darin können Sie Blueprint-Dateien und einen optionalen **templates**-Unterordner für Blueprint-spezifische Vorlagen einschließen.

- **jobs py-Datei** : Benutzerdefinierte Python-Dateien, die als Jobs vom Scheduler ausgeführt werden.

- **my-template.json** : Fügen Sie [benutzerdefinierte Vorlagen](concepts.md#templates) hinzu, um die Standardwerte von Einstellungen zu überschreiben und benutzerdefinierte Konfigurationen einfach anzuwenden.

- **plugin.lua** : Code, der auf NGINX mit dem [NGINX LUA-Modul](https://github.com/openresty/lua-nginx-module) ausgeführt wird.

- **plugin.json** : Metadaten, Einstellungen und Jobdefinitionen für Ihr Plugin.

### Erste Schritte

Der erste Schritt ist die Erstellung eines Ordners, der das Plugin enthalten wird:

```shell
mkdir myplugin && \
cd myplugin
```

### Metadaten

Eine Datei namens **plugin.json**, die im Stammverzeichnis des Plugin-Ordners geschrieben wird, muss Metadaten über das Plugin enthalten. Hier ist ein Beispiel:

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

Hier sind die Details der Felder:

|     Feld      | Obligatorisch | Typ    | Beschreibung                                                                                                                                 |
| :-----------: | :-----------: | :----- | :------------------------------------------------------------------------------------------------------------------------------------------- |
|     `id`      |      ja       | string | Interne ID für das Plugin: muss unter anderen Plugins (einschließlich "Kern"-Plugins) eindeutig sein und darf nur Kleinbuchstaben enthalten. |
|    `name`     |      ja       | string | Name Ihres Plugins.                                                                                                                          |
| `description` |      ja       | string | Beschreibung Ihres Plugins.                                                                                                                  |
|   `version`   |      ja       | string | Version Ihres Plugins.                                                                                                                       |
|   `stream`    |      ja       | string | Informationen zur Stream-Unterstützung: `no`, `yes` oder `partial`.                                                                          |
|  `settings`   |      ja       | dict   | Liste der Einstellungen Ihres Plugins.                                                                                                       |
|    `jobs`     |     nein      | list   | Liste der Jobs Ihres Plugins.                                                                                                                |
|    `bwcli`    |     nein      |  dict  | Ordnet CLI-Befehlsnamen den in dem 'bwcli'-Verzeichnis des Plugins gespeicherten Dateien zu, um CLI-Plugins verfügbar zu machen.      |

Jede Einstellung hat die folgenden Felder (der Schlüssel ist die ID der in einer Konfiguration verwendeten Einstellungen):

|    Feld    | Obligatorisch | Typ    | Beschreibung                                                                      |
| :--------: | :-----------: | :----- | :-------------------------------------------------------------------------------- |
| `context`  |      ja       | string | Kontext der Einstellung: `multisite` oder `global`.                               |
| `default`  |      ja       | string | Der Standardwert der Einstellung.                                                 |
|   `help`   |      ja       | string | Hilfetext zum Plugin (wird in der Web-UI angezeigt).                              |
|    `id`    |      ja       | string | Interne ID, die von der Web-UI für HTML-Elemente verwendet wird.                  |
|  `label`   |      ja       | string | Label, das von der Web-UI angezeigt wird.                                         |
|  `regex`   |      ja       | string | Der Regex, der zur Validierung des vom Benutzer angegebenen Werts verwendet wird. |
|   `type`   |      ja       | string | Der Typ des Feldes: `text`, `check`, `select` oder `password`.                    |
| `multiple` |     nein      | string | Eindeutige ID zur Gruppierung mehrerer Einstellungen mit Zahlen als Suffix.       |
|  `select`  |     nein      | list   | Liste der möglichen Zeichenfolgenwerte, wenn `type` `select` ist.                 |

Jeder Job hat die folgenden Felder:

|  Feld   | Obligatorisch | Typ    | Beschreibung                                                                                                                                        |
| :-----: | :-----------: | :----- | :-------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`  |      ja       | string | Name des Jobs.                                                                                                                                      |
| `file`  |      ja       | string | Name der Datei im Jobs-Ordner.                                                                                                                      |
| `every` |      ja       | string | Häufigkeit der Job-Planung: `minute`, `hour`, `day`, `week` oder `once` (keine Häufigkeit, nur einmal vor der (Neu-)Generierung der Konfiguration). |

### CLI-Befehle

Plugins können das 'bwcli'-Tool mit benutzerdefinierten Befehlen erweitern, die unter 'bwcli plugin <plugin_id> ...' ausgeführt werden:

1. Fügen Sie ein 'bwcli'-Verzeichnis in Ihrem Plugin hinzu und legen Sie eine Datei pro Befehl ab (zum Beispiel 'bwcli/list.py'). Die CLI fügt den Plugin-Pfad zu 'sys.path' hinzu, bevor die Datei ausgeführt wird.
2. Deklarieren Sie die Befehle im optionalen 'bwcli'-Abschnitt von 'plugin.json', indem Sie jeden Befehlsnamen seinem ausführbaren Dateinamen zuordnen.

```json
{
  "bwcli": {
    "list": "list.py",
    "save": "save.py"
  }
}
```

Der Scheduler stellt die deklarierten Befehle automatisch bereit, sobald das Plugin installiert ist. Core-Plugins wie 'backup' in 'src/common/core/backup' folgen demselben Muster.

### Konfigurationen

Sie können benutzerdefinierte NGINX-Konfigurationen hinzufügen, indem Sie einen Ordner namens **confs** mit Inhalt ähnlich den [benutzerdefinierten Konfigurationen](advanced.md#custom-configurations) hinzufügen. Jeder Unterordner in **confs** enthält [jinja2](https://jinja.palletsprojects.com)-Vorlagen, die generiert und im entsprechenden Kontext (`http`, `server-http`, `default-server-http`, `stream`, `server-stream`, `modsec`, `modsec-crs`, `crs-plugins-before` und `crs-plugins-after`) geladen werden.

Hier ist ein Beispiel für eine Konfigurationsvorlagendatei im Ordner **confs/server-http** namens **example.conf**:

```nginx
location /setting {
  default_type 'text/plain';
    content_by_lua_block {
        ngx.say('{{ DUMMY_SETTING }}')
    }
}
```

`{{ DUMMY_SETTING }}` wird durch den Wert von `DUMMY_SETTING` ersetzt, der vom Benutzer des Plugins ausgewählt wurde.

### Vorlagen

Weitere Informationen finden Sie in der [Vorlagendokumentation](concepts.md#templates).

### LUA

#### Hauptskript

Im Hintergrund verwendet BunkerWeb das [NGINX LUA-Modul](https://github.com/openresty/lua-nginx-module), um Code innerhalb von NGINX auszuführen. Plugins, die Code ausführen müssen, müssen eine Lua-Datei im Stammverzeichnis des Plugin-Ordners bereitstellen, die den `id`-Wert von **plugin.json** als Namen verwendet. Hier ist ein Beispiel namens **myplugin.lua**:

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

Die deklarierten Funktionen werden automatisch in bestimmten Kontexten aufgerufen. Hier sind die Details zu jeder Funktion:

|   Funktion    |                                           Kontext                                           | Beschreibung                                                                                                                                                                                                                  | Rückgabewert                                                                                                                                                                                                                                                                                                                                                                                                  |
| :-----------: | :-----------------------------------------------------------------------------------------: | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
|    `init`     |          [init_by_lua](https://github.com/openresty/lua-nginx-module#init_by_lua)           | Wird aufgerufen, wenn NGINX gerade gestartet wurde oder einen Neuladebefehl erhalten hat. Der typische Anwendungsfall besteht darin, Daten vorzubereiten, die von Ihrem Plugin verwendet werden.                              | `ret`, `msg`<ul><li>`ret` (boolean): true, wenn kein Fehler, sonst false</li><li>`msg` (string): Erfolgs- oder Fehlermeldung</li></ul>                                                                                                                                                                                                                                                                        |
|     `set`     |           [set_by_lua](https://github.com/openresty/lua-nginx-module#set_by_lua)            | Wird vor jeder vom Server empfangenen Anfrage aufgerufen. Der typische Anwendungsfall ist die Berechnung vor der Zugriffsphase.                                                                                               | `ret`, `msg`<ul><li>`ret` (boolean): true, wenn kein Fehler, sonst false</li><li>`msg` (string): Erfolgs- oder Fehlermeldung</li></ul>                                                                                                                                                                                                                                                                        |
|   `access`    |        [access_by_lua](https://github.com/openresty/lua-nginx-module#access_by_lua)         | Wird bei jeder vom Server empfangenen Anfrage aufgerufen. Der typische Anwendungsfall besteht darin, hier die Sicherheitsüberprüfungen durchzuführen und die Anfrage bei Bedarf abzulehnen.                                   | `ret`, `msg`,`status`,`redirect`<ul><li>`ret` (boolean): true, wenn kein Fehler, sonst false</li><li>`msg` (string): Erfolgs- oder Fehlermeldung</li><li>`status` (number): unterbricht den aktuellen Prozess und gibt den [HTTP-Status](https://github.com/openresty/lua-nginx-module#http-status-constants) zurück</li><li>`redirect` (URL): wenn gesetzt, wird auf die angegebene URL umgeleitet</li></ul> |
|     `log`     |           [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)            | Wird aufgerufen, wenn eine Anfrage abgeschlossen ist (und bevor sie in die Zugriffsprotokolle geschrieben wird). Der typische Anwendungsfall besteht darin, beispielsweise Statistiken zu erstellen oder Zähler zu berechnen. | `ret`, `msg`<ul><li>`ret` (boolean): true, wenn kein Fehler, sonst false</li><li>`msg` (string): Erfolgs- oder Fehlermeldung</li></ul>                                                                                                                                                                                                                                                                        |
| `log_default` |           [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)            | Dasselbe wie `log`, wird aber nur auf dem Standardserver aufgerufen.                                                                                                                                                          | `ret`, `msg`<ul><li>`ret` (boolean): true, wenn kein Fehler, sonst false</li><li>`msg` (string): Erfolgs- oder Fehlermeldung</li></ul>                                                                                                                                                                                                                                                                        |
|   `preread`   | [preread_by_lua](https://github.com/openresty/stream-lua-nginx-module#preread_by_lua_block) | Ähnlich der `access`-Funktion, aber für den Stream-Modus.                                                                                                                                                                     | `ret`, `msg`,`status`<ul><li>`ret` (boolean): true, wenn kein Fehler, sonst false</li><li>`msg` (string): Erfolgs- oder Fehlermeldung</li><li>`status` (number): unterbricht den aktuellen Prozess und gibt den [Status](https://github.com/openresty/lua-nginx-module#http-status-constants) zurück</li></ul>                                                                                                |
| `log_stream`  |     [log_by_lua](https://github.com/openresty/stream-lua-nginx-module#log_by_lua_block)     | Ähnlich der `log`-Funktion, aber für den Stream-Modus.                                                                                                                                                                        | `ret`, `msg`<ul><li>`ret` (boolean): true, wenn kein Fehler, sonst false</li><li>`msg` (string): Erfolgs- oder Fehlermeldung</li></ul>                                                                                                                                                                                                                                                                        |

#### Bibliotheken

Alle Direktiven aus dem [NGINX LUA-Modul](https://github.com/openresty/lua-nginx-module) und dem [NGINX Stream LUA-Modul](https://github.com/openresty/stream-lua-nginx-module) sind verfügbar. Darüber hinaus können Sie die in BunkerWeb enthaltenen LUA-Bibliotheken verwenden: siehe [dieses Skript](https://github.com/bunkerity/bunkerweb/blob/v1.6.8-rc3/src/deps/clone.sh) für die vollständige Liste.

Wenn Sie zusätzliche Bibliotheken benötigen, können Sie diese in den Stammordner des Plugins legen und darauf zugreifen, indem Sie ihnen Ihre Plugin-ID voranstellen. Hier ist ein Beispiel für eine Datei namens **mylibrary.lua**:

```lua
local _M = {}

_M.dummy = function ()
	return "dummy"
end

return _M
```

Und hier ist, wie Sie sie aus der Datei **myplugin.lua** verwenden können:

```lua
local mylibrary = require "myplugin.mylibrary"

...

mylibrary.dummy()

...
```

#### Helfer

Einige Helfermodule bieten allgemeine nützliche Helfer:

-   `self.variables`: ermöglicht den Zugriff auf und die Speicherung von Plugin-Attributen
-   `self.logger`: druckt Protokolle
-   `bunkerweb.utils`: verschiedene nützliche Funktionen
-   `bunkerweb.datastore`: greift auf die globalen gemeinsamen Daten auf einer Instanz zu (Schlüssel-Wert-Speicher)
-   `bunkerweb.clusterstore`: greift auf einen Redis-Datenspeicher zu, der zwischen BunkerWeb-Instanzen geteilt wird (Schlüssel-Wert-Speicher)

Um auf die Funktionen zuzugreifen, müssen Sie zuerst die Module **erfordern**:

```lua
local utils       = require "bunkerweb.utils"
local datastore   = require "bunkerweb.datastore"
local clustestore = require "bunkerweb.clustertore"
```

Einen Einstellungswert abrufen:

```lua
local myvar = self.variables["DUMMY_SETTING"]
if not myvar then
    self.logger:log(ngx.ERR, "kann Einstellung DUMMY_SETTING nicht abrufen")
else
    self.logger:log(ngx.NOTICE, "DUMMY_SETTING = " .. value)
end
```

Etwas im lokalen Cache speichern:

```lua
local ok, err = self.datastore:set("plugin_myplugin_something", "somevalue")
if not ok then
    self.logger:log(ngx.ERR, "kann plugin_myplugin_something nicht im Datenspeicher speichern: " .. err)
else
    self.logger:log(ngx.NOTICE, "plugin_myplugin_something erfolgreich im Datenspeicher gespeichert")
end
```

Überprüfen, ob eine IP-Adresse global ist:

```lua
local ret, err = utils.ip_is_global(ngx.ctx.bw.remote_addr)
if ret == nil then
    self.logger:log(ngx.ERR, "Fehler beim Überprüfen, ob die IP " .. ngx.ctx.bw.remote_addr .. " global ist oder nicht: " .. err)
elseif not ret then
    self.logger:log(ngx.NOTICE, "IP " .. ngx.ctx.bw.remote_addr .. " ist nicht global")
else
    self.logger:log(ngx.NOTICE, "IP " .. ngx.ctx.bw.remote_addr .. " ist global")
end
```

!!! tip "Weitere Beispiele"

    Wenn Sie die vollständige Liste der verfügbaren Funktionen sehen möchten, können Sie sich die Dateien im [lua-Verzeichnis](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/src/bw/lua/bunkerweb) des Repositorys ansehen.

### Jobs

BunkerWeb verwendet einen internen Job-Scheduler für periodische Aufgaben wie die Erneuerung von Zertifikaten mit Certbot, das Herunterladen von Blacklists, das Herunterladen von MMDB-Dateien usw. Sie können Aufgaben Ihrer Wahl hinzufügen, indem Sie sie in einen Unterordner namens **jobs** legen und sie in der Metadatendatei **plugin.json** auflisten. Vergessen Sie nicht, die Ausführungsberechtigungen für alle hinzuzufügen, um Probleme zu vermeiden, wenn ein Benutzer Ihr Plugin klont und installiert.

### Plugin-Seite

Alles, was mit der Web-UI zu tun hat, befindet sich im Unterordner **ui**, wie wir im [vorherigen Strukturabschnitt](#struktur) gesehen haben.

#### Voraussetzungen

Wenn Sie eine Plugin-Seite erstellen möchten, benötigen Sie zwei Dateien:

- **template.html**, das mit einem **GET /plugins/<*plugin_id*>** erreichbar ist.

- **actions.py**, wo Sie Skripte und Logik mit einem **POST /plugins/<*plugin_id*>** hinzufügen können. Beachten Sie, dass diese Datei **eine Funktion mit demselben Namen wie das Plugin benötigt**, um zu funktionieren. Diese Datei wird auch dann benötigt, wenn die Funktion leer ist.

#### Grundlegendes Beispiel

!!! info "Jinja 2-Vorlage"
    Die Datei **template.html** ist eine Jinja2-Vorlage. Weitere Informationen finden Sie in der [Jinja2-Dokumentation](https://jinja.palletsprojects.com).

Wir können die Datei **actions.py** beiseite legen und **nur die Vorlage in einer GET-Situation verwenden**. Die Vorlage kann auf den App-Kontext und Bibliotheken zugreifen, sodass Sie Jinja-, Request- oder Flask-Dienstprogramme verwenden können.

Sie können beispielsweise die Anforderungsargumente in Ihrer Vorlage wie folgt abrufen:

```html
<p>Anforderungsargumente: {{ request.args.get() }}.</p>
```

#### Actions.py

!!! warning "CSRF-Token"

    Bitte beachten Sie, dass jede Formularübermittlung durch ein CSRF-Token geschützt ist. Sie müssen das folgende Snippet in Ihre Formulare einfügen:
    ```html
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
    ```

Sie können Ihre Plugin-Seite mit zusätzlichen Skripten mit der Datei **actions.py** erweitern, wenn Sie einen **POST /plugins/<*plugin_id*>** senden.

Sie haben standardmäßig zwei Funktionen in **actions.py**:

**pre_render-Funktion**

Dies ermöglicht es Ihnen, Daten abzurufen, wenn Sie die Vorlage **GET**en, und die Daten mit der in Jinja verfügbaren `pre_render`-Variable zu verwenden, um Inhalte dynamischer anzuzeigen.

```python
def pre_render(**kwargs)
  return <pre_render_data>
```

BunkerWeb sendet Ihnen diese Art von Antwort:

```python
return jsonify({"status": "ok|ko", "code" : XXX, "data": <pre_render_data>}), 200
```

**<*plugin_id*>-Funktion**

Dies ermöglicht es Ihnen, Daten abzurufen, wenn Sie einen **POST** vom Vorlagenendpunkt ausführen, der in AJAX verwendet werden muss.

```python
def myplugin(**kwargs)
  return <plugin_id_data>
```

BunkerWeb sendet Ihnen diese Art von Antwort:

```python
return jsonify({"message": "ok", "data": <plugin_id_data>}), 200
```

**Was Sie von action.py aus zugreifen können**

Hier sind die Argumente, die an die Funktionen von `action.py` übergeben und darauf zugegriffen werden:

```python
function(app=app, args=request.args.to_dict() or request.json or None)
```

!!! info "Verfügbare Python-Bibliotheken"

    Die Web-UI von BunkerWeb enthält eine Reihe vorinstallierter Python-Bibliotheken, die Sie in der `actions.py`-Datei Ihres Plugins oder anderen UI-bezogenen Skripten verwenden können. Diese sind sofort verfügbar und erfordern keine zusätzlichen Installationen.

    Hier ist die vollständige Liste der enthaltenen Bibliotheken:

    -   **bcrypt** - Passwort-Hashing-Bibliothek
    -   **biscuit-python** - Biscuit-Authentifizierungstoken
    -   **certbot** - ACME-Client für Let's Encrypt
    -   **Flask** - Web-Framework
    -   **Flask-Login** - Benutzersitzungsverwaltung
    -   **Flask-Session[cachelib]** - Serverseitige Sitzungsspeicherung
    -   **Flask-WTF** - Formularbehandlung und CSRF-Schutz
    -   **gunicorn[gthread]** - WSGI-HTTP-Server
    -   **pillow** - Bildverarbeitung
    -   **psutil** - System- und Prozess-Dienstprogramme
    -   **python_dateutil** - Datums- und Uhrzeit-Dienstprogramme
    -   **qrcode** - QR-Code-Generierung
    -   **regex** - Erweiterte reguläre Ausdrücke
    -   **urllib3** - HTTP-Client
    -   **user_agents** - User-Agent-Parsing

    !!! tip "Verwendung von Bibliotheken in Ihrem Plugin"
        Um diese Bibliotheken in Ihrer `actions.py`-Datei zu importieren und zu verwenden, verwenden Sie einfach die standardmäßige Python-`import`-Anweisung. Zum Beispiel:

        ```python
        from flask import request
        import bcrypt
        ```

    ??? warning "Externe Bibliotheken"
        Wenn Sie Bibliotheken benötigen, die nicht oben aufgeführt sind, installieren Sie sie im `ui`-Ordner Ihres Plugins und importieren Sie sie mit der klassischen `import`-Anweisung. Stellen Sie die Kompatibilität mit der vorhandenen Umgebung sicher, um Konflikte zu vermeiden.

**Einige Beispiele**

-   Abrufen von übermittelten Formulardaten

```python
from flask import request

def myplugin(**kwargs) :
	my_form_value = request.form["my_form_input"]
  return my_form_value
```

-   Zugriff auf die App-Konfiguration

**action.py**
```python
from flask import request

def pre_render(**kwargs) :
	config = kwargs['app'].config["CONFIG"].get_config(methods=False)
  return config
```

**Vorlage**
```html
<!-- Metadaten + Konfiguration -->
<div>{{ pre_render }}</div>
```

### Hooks.py

Diese Dokumentation beschreibt die Lebenszyklus-Hooks, die zur Verwaltung verschiedener Phasen einer Anfrage innerhalb der Anwendung verwendet werden. Jeder Hook ist mit einer bestimmten Phase verbunden.

=== "before_request"
    Diese Hooks werden **vor** der Verarbeitung einer eingehenden Anfrage ausgeführt. Sie werden normalerweise für Vorverarbeitungsaufgaben wie Authentifizierung, Validierung oder Protokollierung verwendet.

    Wenn der Hook ein Antwortobjekt zurückgibt, überspringt Flask die Anforderungsbehandlung und gibt die Antwort direkt zurück. Dies kann nützlich sein, um die Anforderungsverarbeitungspipeline kurzzuschließen.

    **Beispiel:**

    ```python
    from flask import request, Response

    def before_request():
        print("Before-request: Validating request...", flush=True)
        # Hier Authentifizierung, Validierung oder Protokollierung durchführen
        if not is_valid_request(request): # Wir befinden uns im App-Kontext
            return Response("Invalid request!", status=400)

    def is_valid_request(request):
        # Dummy-Validierungslogik
        return "user" in request
    ```
=== "after_request"
    Diese Hooks werden **nach** der Verarbeitung der Anfrage ausgeführt. Sie sind ideal für Nachverarbeitungsaufgaben wie Bereinigung, zusätzliche Protokollierung oder das Ändern der Antwort, bevor sie zurückgesendet wird.

    Sie erhalten das Antwortobjekt als Argument und können es ändern, bevor sie es zurückgeben. Der erste `after_request`-Hook, der eine Antwort zurückgibt, wird als endgültige Antwort verwendet.

    **Beispiel:**

    ```python
    from flask import request

    def after_request(response):
        print("After-request: Logging response...", flush=True)
        # Hier Protokollierung, Bereinigung oder Antwortänderungen durchführen
        log_response(response)
        return response

    def log_response(response):
        # Dummy-Protokollierungslogik
        print("Response logged:", response, flush=True)
    ```
=== "teardown_request"
    Diese Hooks werden aufgerufen, wenn der Anforderungskontext abgebaut wird. Diese Hooks werden verwendet, um Ressourcen freizugeben oder Fehler zu behandeln, die während des Lebenszyklus der Anfrage aufgetreten sind.

    **Beispiel:**

    ```python
    def teardown_request(error=None):
        print("Teardown-request: Cleaning up resources...", flush=True)
        # Hier Bereinigung, Ressourcenfreigabe oder Fehlerbehandlung durchführen
        if error:
            handle_error(error)
        cleanup_resources()

    def handle_error(error):
        # Dummy-Fehlerbehandlungslogik
        print("Error encountered:", error, flush=True)

    def cleanup_resources():
        # Dummy-Ressourcenbereinigungslogik
        print("Resources have been cleaned up.", flush=True)
    ```
=== "context_processor"
    Diese Hooks werden verwendet, um zusätzlichen Kontext in Vorlagen oder Ansichten einzufügen. Sie bereichern den Laufzeitkontext, indem sie allgemeine Daten (wie Benutzerinformationen oder Konfigurationseinstellungen) an die Vorlagen übergeben.

    Wenn ein Kontextprozessor ein Wörterbuch zurückgibt, werden die Schlüssel und Werte dem Kontext für alle Vorlagen hinzugefügt. Dies ermöglicht es Ihnen, Daten über mehrere Ansichten oder Vorlagen hinweg zu teilen.

    **Beispiel:**

    ```python
    def context_processor() -> dict:
        print("Context-processor: Injecting context data...", flush=True)
        # Ein Wörterbuch mit Kontextdaten für Vorlagen/Ansichten zurückgeben
        return {
            "current_user": "John Doe",
            "app_version": "1.0.0",
            "feature_flags": {"new_ui": True}
        }
    ```

Dieses Lebenszyklus-Hook-Design bietet einen modularen und systematischen Ansatz zur Verwaltung verschiedener Aspekte des Lebenszyklus einer Anfrage:

-   **Modularität:** Jeder Hook ist für eine bestimmte Phase verantwortlich, wodurch sichergestellt wird, dass die Belange getrennt sind.
-   **Wartbarkeit:** Entwickler können Hook-Implementierungen einfach hinzufügen, ändern oder entfernen, ohne andere Teile des Lebenszyklus der Anfrage zu beeinträchtigen.
-   **Erweiterbarkeit:** Das Framework ist flexibel und ermöglicht zusätzliche Hooks oder Erweiterungen, wenn sich die Anwendungsanforderungen ändern.

Durch die klare Definition der Verantwortlichkeiten jedes Hooks und der zugehörigen Protokollierungspräfixe stellt das System sicher, dass jede Phase der Anforderungsverarbeitung transparent und verwaltbar ist.

### Blueprints

In Flask dienen **Blueprints** als modularer Weg, um verwandte Komponenten – wie Ansichten, Vorlagen und statische Dateien – innerhalb Ihrer Anwendung zu organisieren. Sie ermöglichen es Ihnen, Funktionen logisch zu gruppieren und können verwendet werden, um neue Abschnitte Ihrer App zu erstellen oder bestehende zu überschreiben.

#### Erstellen eines Blueprints

Um einen Blueprint zu definieren, erstellen Sie eine Instanz der `Blueprint`-Klasse und geben dabei dessen Namen und Importpfad an. Anschließend definieren Sie Routen und Ansichten, die mit diesem Blueprint verbunden sind.

**Beispiel: Definieren eines neuen Blueprints**

```python
from os.path import dirname
from flask import Blueprint, render_template

# Den Blueprint definieren
my_blueprint = Blueprint('my_blueprint', __name__, template_folder=dirname(__file__) + '/templates') # Der template_folder wird gesetzt, um Konflikte mit dem ursprünglichen Blueprint zu vermeiden

# Eine Route innerhalb des Blueprints definieren
@my_blueprint.route('/my_blueprint')
def my_blueprint_page():
    return render_template('my_blueprint.html')
```

In diesem Beispiel wird ein Blueprint namens `my_blueprint` erstellt und eine Route `/my_blueprint` darin definiert.

#### Überschreiben eines bestehenden Blueprints

Blueprints können auch bestehende überschreiben, um Funktionalität zu ändern oder zu erweitern. Stellen Sie dazu sicher, dass der neue Blueprint denselben Namen hat wie der, den Sie überschreiben, und registrieren Sie ihn nach dem Original.

**Beispiel: Überschreiben eines bestehenden Blueprints**

```python
from os.path import dirname
from flask import Flask, Blueprint

# Ursprünglicher Blueprint
instances = Blueprint('instances', __name__, template_folder=dirname(__file__) + '/templates') # Der template_folder wird gesetzt, um Konflikte mit dem ursprünglichen Blueprint zu vermeiden

@instances.route('/instances')
def override_instances():
    return "Meine neue Instanzen-Seite"
```

In diesem Szenario wird beim Aufrufen der URL `/instances` "Meine neue Instanzen-Seite" angezeigt, da der zuletzt registrierte `instances`-Blueprint den ursprünglichen `instances`-Blueprint überschreibt.

!!! warning "Zum Überschreiben"
    Seien Sie vorsichtig beim Überschreiben bestehender Blueprints, da dies das Verhalten der Anwendung beeinträchtigen kann. Stellen Sie sicher, dass die Änderungen den Anforderungen der Anwendung entsprechen und keine unerwarteten Nebenwirkungen verursachen.

    Alle bestehenden Routen werden aus dem ursprünglichen Blueprint entfernt, sodass Sie sie bei Bedarf neu implementieren müssen.

#### Namenskonventionen

!!! danger "Wichtig"
    Stellen Sie sicher, dass der Name des Blueprints mit dem Namen der Blueprint-Variable übereinstimmt, andernfalls wird er nicht als gültiger Blueprint betrachtet und nicht registriert.

Für Konsistenz und Klarheit ist es ratsam, die folgenden Namenskonventionen zu befolgen:

-   **Blueprint-Namen**: Verwenden Sie kurze, nur aus Kleinbuchstaben bestehende Namen. Unterstriche können zur Lesbarkeit verwendet werden, z. B. `user_auth`.

-   **Dateinamen**: Passen Sie den Dateinamen an den Blueprint-Namen an und stellen Sie sicher, dass er nur aus Kleinbuchstaben mit Unterstrichen besteht, z. B. `user_auth.py`.

Diese Praxis steht im Einklang mit den Namenskonventionen für Python-Module und hilft, eine klare Projektstruktur beizubehalten.

**Beispiel: Blueprint- und Dateibenennung**

```
plugin /
    ui / blueprints / user_auth.py
                      templates / user_auth.html
```

In dieser Struktur enthält `user_auth.py` den `user_auth`-Blueprint und `user_auth.html` ist die zugehörige Vorlage, die den empfohlenen Namenskonventionen entspricht.
