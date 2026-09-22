# Plugins

BunkerWeb viene con un sistema de plugins que permite añadir fácilmente nuevas características. Una vez que un plugin está instalado, puedes gestionarlo usando configuraciones adicionales definidas por el plugin.

## Plugins oficiales

Aquí está la lista de plugins "oficiales" que mantenemos (consulta el repositorio [bunkerweb-plugins](https://github.com/bunkerity/bunkerweb-plugins) para más información):

|     Nombre     | Versión | Descripción                                                                                                                                              |                                               Enlace                                                |
| :------------: | :-----: | :------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------: |
| **Authentik**  |  1.11   | Proteja sus servicios web con la autenticación delegada de Authentik (auth_request) para el inicio de sesión único (SSO).                                |  [bunkerweb-plugins/authentik](https://github.com/bunkerity/bunkerweb-plugins/tree/main/authentik)  |
|   **ClamAV**   |  1.11   | Escanea automáticamente los archivos subidos con el motor antivirus ClamAV y deniega la solicitud cuando un archivo es detectado como malicioso.         |     [bunkerweb-plugins/clamav](https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav)     |
| **Cloudflare** |  1.11   | Configure las IP de confianza de Cloudflare, gestione los certificados Origin CA y sincronice los baneos de BunkerWeb con una lista de IP de Cloudflare. | [bunkerweb-plugins/cloudflare](https://github.com/bunkerity/bunkerweb-plugins/tree/main/cloudflare) |
|   **Coraza**   |  1.11   | Inspecciona las solicitudes usando el WAF de Coraza (alternativa a ModSecurity).                                                                         |     [bunkerweb-plugins/coraza](https://github.com/bunkerity/bunkerweb-plugins/tree/main/coraza)     |
|  **Discord**   |  1.11   | Envía notificaciones de seguridad a un canal de Discord usando un Webhook.                                                                               |    [bunkerweb-plugins/discord](https://github.com/bunkerity/bunkerweb-plugins/tree/main/discord)    |
|   **Matrix**   |  1.11   | Envía notificaciones de seguridad a una sala de Matrix usando la API de Matrix.                                                                          |     [bunkerweb-plugins/matrix](https://github.com/bunkerity/bunkerweb-plugins/tree/main/matrix)     |
|   **Slack**    |  1.11   | Envía notificaciones de seguridad a un canal de Slack usando un Webhook.                                                                                 |      [bunkerweb-plugins/slack](https://github.com/bunkerity/bunkerweb-plugins/tree/main/slack)      |
| **VirusTotal** |  1.11   | Escanea automáticamente los archivos subidos con la API de VirusTotal y deniega la solicitud cuando un archivo es detectado como malicioso.              | [bunkerweb-plugins/virustotal](https://github.com/bunkerity/bunkerweb-plugins/tree/main/virustotal) |
|  **WebHook**   |  1.11   | Envía notificaciones de seguridad a un punto final HTTP personalizado usando un Webhook.                                                                 |    [bunkerweb-plugins/webhook](https://github.com/bunkerity/bunkerweb-plugins/tree/main/webhook)    |

## Gestión desde la UI web y catálogo comunitario

La página **Plugins** separa la instalación de la activación:

- Los plugins externos, de UI y PRO pueden activarse o desactivarse sin eliminar su paquete almacenado. El programador omite los plugins desactivados de los directorios de plugins materializados y los restaura desde la base de datos cuando vuelves a activarlos.
- Los plugins principales forman parte de la imagen de BunkerWeb y no pueden desactivarse en la capa de instalación. Usa los ajustes globales del plugin cuando exponga un interruptor de activación.
- Un plugin puede incluir `icon.svg`, `icon.png`, `logo.svg` o `logo.png` en la raíz de su carpeta. BunkerWeb detecta estos nombres en ese orden y sirve como máximo 512 KiB a través del endpoint de icono autenticado. La UI web recurre a un icono integrado cuando no existe ningún archivo compatible.

El catálogo comunitario lista los últimos lanzamientos de dos repositorios fijos de GitHub: [`bunkerity/bunkerweb-plugins`](https://github.com/bunkerity/bunkerweb-plugins) y [`bunkerity/bunkerweb-templates`](https://github.com/bunkerity/bunkerweb-templates). Los propios repositorios son el catálogo. No existe un manifiesto ni un productor separado. BunkerWeb lee el `plugin.json` o `template.json` de cada elemento desde el archivo del release, aplica la comprobación de compatibilidad del plugin e instala solo el elemento seleccionado a través de la ruta de subida existente.

Establece la variable de entorno de la UI web `USE_PLUGIN_CATALOG=no` para deshabilitar las solicitudes al catálogo, ocultar ambas secciones del catálogo y rechazar las instalaciones desde el catálogo. `off`, `false` y `0` también lo deshabilitan. Este interruptor no elimina nada ya instalado. Un listado en caché de más de 24 horas sigue siendo visible pero no puede instalar nada hasta que una actualización tenga éxito.

!!! warning "Modelo de confianza del catálogo"
    HTTPS hacia GitHub y una lista blanca exacta de repositorios protegen la ruta de descarga. En el momento de la actualización, BunkerWeb registra el digest SHA-256 del archivo del release; en el momento de la instalación, vuelve a obtener la etiqueta fijada y rechaza el elemento si el digest ha cambiado. Esta comprobación demuestra que los bytes instalados coinciden con los bytes que se listaron. No demuestra quién los creó. El acceso de escritura a los dos repositorios `bunkerity` es la raíz de confianza, y un publicador de repositorio hostil sigue siendo de confianza. La firma Ed25519 se ha aplazado deliberadamente.

## Cómo usar un plugin

### Automático

Si quieres instalar rápidamente plugins externos, puedes usar la configuración `EXTERNAL_PLUGIN_URLS`. Acepta una lista de URLs separadas por espacios, cada una apuntando a un archivo comprimido (formato zip) que contiene uno o más plugins.

Puedes usar el siguiente valor si quieres instalar automáticamente los plugins oficiales: `EXTERNAL_PLUGIN_URLS=https://github.com/bunkerity/bunkerweb-plugins/archive/refs/tags/v1.11.zip`

### Manual

El primer paso es instalar el plugin colocando sus archivos dentro de la carpeta de datos `plugins` correspondiente. El procedimiento depende de tu integración:

=== "Docker"

    Cuando se utiliza la [integración de Docker](integrations.md#docker), los plugins deben colocarse en el volumen montado en `/data/plugins` en el contenedor del programador.

    Lo primero que hay que hacer es crear la carpeta de plugins:

    ```shell
    mkdir -p ./bw-data/plugins
    ```

    Luego, puedes colocar los plugins de tu elección en esa carpeta:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    ??? warning "Usar una carpeta local para datos persistentes"
        El programador se ejecuta como un **usuario sin privilegios con UID 101 y GID 101** dentro del contenedor. La razón detrás de esto es la seguridad: en caso de que se explote una vulnerabilidad, el atacante no tendrá privilegios completos de root (UID/GID 0).
        Pero hay una desventaja: si usas una **carpeta local para los datos persistentes**, necesitarás **establecer los permisos correctos** para que el usuario sin privilegios pueda escribir datos en ella. Algo como esto debería funcionar:

        ```shell
        mkdir bw-data && \
        chown root:101 bw-data && \
        chmod 770 bw-data
        ```

        Alternativamente, si la carpeta ya existe:

        ```shell
        chown -R root:101 bw-data && \
        chmod -R 770 bw-data
        ```

        Si estás utilizando [Docker en modo sin raíz](https://docs.docker.com/engine/security/rootless) o [podman](https://podman.io/), los UID y GID en el contenedor se mapearán a diferentes en el host. Primero necesitarás verificar tu subuid y subgid iniciales:

        ```shell
        grep ^$(whoami): /etc/subuid && \
        grep ^$(whoami): /etc/subgid
        ```

        Por ejemplo, si tienes un valor de **100000**, el UID/GID mapeado será **100100** (100000 + 100):

        ```shell
        mkdir bw-data && \
        sudo chgrp 100100 bw-data && \
        chmod 770 bw-data
        ```

        O si la carpeta ya existe:

        ```shell
        sudo chgrp -R 100100 bw-data && \
        sudo chmod -R 770 bw-data
        ```

    Luego puedes montar el volumen al iniciar tu pila de Docker:

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

    Cuando se utiliza la [integración de Docker autoconf](integrations.md#docker-autoconf), los plugins deben colocarse en el volumen montado en `/data/plugins` en el contenedor del programador.


    Lo primero que hay que hacer es crear la carpeta de plugins:

    ```shell
    mkdir -p ./bw-data/plugins
    ```

    Luego, puedes colocar los plugins de tu elección en esa carpeta:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    Debido a que el programador se ejecuta como un usuario sin privilegios con UID y GID 101, necesitarás editar los permisos:

    ```shell
    chown -R 101:101 ./bw-data
    ```

    Luego puedes montar el volumen al iniciar tu pila de Docker:

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

    Cuando se utiliza la [integración de Swarm](integrations.md#swarm), los plugins deben colocarse en el volumen montado en `/data/plugins` en el contenedor del programador.

    !!! info "Volumen de Swarm"
        La configuración de un volumen de Swarm que persistirá cuando el servicio del programador se ejecute en diferentes nodos no se cubre en esta documentación. Asumiremos que tienes una carpeta compartida montada en `/shared` en todos los nodos.

    Lo primero que hay que hacer es crear la carpeta de plugins:

    ```shell
    mkdir -p /shared/bw-plugins
    ```

    Luego, puedes colocar los plugins de tu elección en esa carpeta:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /shared/bw-plugins
    ```

    Debido a que el programador se ejecuta como un usuario sin privilegios con UID y GID 101, necesitarás editar los permisos:

    ```shell
    chown -R 101:101 /shared/bw-plugins
    ```

    Luego puedes montar el volumen al iniciar tu pila de Swarm:

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

    Cuando se utiliza la [integración de Kubernetes](integrations.md#kubernetes), los plugins deben colocarse en el volumen montado en `/data/plugins` en el contenedor del programador.

    Lo primero que hay que hacer es declarar una [PersistentVolumeClaim](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) que contendrá los datos de nuestros plugins:

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

    Ahora puedes añadir el montaje del volumen y un contenedor de inicialización para aprovisionar automáticamente el volumen:

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

    Cuando se utiliza la [integración de Linux](integrations.md#linux), los plugins deben escribirse en la carpeta `/etc/bunkerweb/plugins`:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /etc/bunkerweb/plugins && \
    chown -R nginx:nginx /etc/bunkerweb/plugins
    ```

## Escribir un plugin

### Estructura

!!! tip "Plugins existentes"

    Si la documentación no es suficiente, puedes echar un vistazo al código fuente existente de los [plugins oficiales](https://github.com/bunkerity/bunkerweb-plugins) y los [plugins del núcleo](https://github.com/bunkerity/bunkerweb/tree/v1.7.0-beta/src/common/core) (ya incluidos en BunkerWeb, pero técnicamente son plugins).

Así es como se ve la estructura de un plugin:
```
plugin /
    confs / tipo_conf / nombre_conf.conf
    ui / actions.py
         hooks.py
         template.html
         blueprints / <archivo(s)_blueprint>
              templates / <plantilla(s)_blueprint>
    jobs / mi-trabajo.py
    templates / mi-plantilla.json
          mi-plantilla / configs / tipo_conf / nombre_conf.conf
    plugin.lua
    plugin.json
```

- **nombre_conf.conf**: Añade [configuraciones personalizadas de NGINX](advanced.md#custom-configurations) (como plantillas de Jinja2).

- **actions.py**: Script para ejecutar en el servidor Flask. Este script se ejecuta en un contexto de Flask, dándote acceso a librerías y utilidades como `jinja2` y `requests`.

- **hooks.py**: Archivo Python personalizado que contiene los hooks de Flask y que se ejecutará cuando se cargue el plugin.

- **template.html**: Página del plugin personalizada a la que se accede a través de la UI.

- **carpeta blueprints (dentro de ui)**:
  Esta carpeta se utiliza para sobrescribir los blueprints de Flask existentes o crear nuevos. Dentro, puedes incluir archivos de blueprint y una subcarpeta opcional **templates** para las plantillas específicas del blueprint.

- **archivo py de trabajos**: Archivos Python personalizados ejecutados como trabajos por el programador.

- **mi-plantilla.json**: Añade [plantillas personalizadas](concepts.md#templates) para sobrescribir los valores predeterminados de las configuraciones y aplicar configuraciones personalizadas fácilmente.

- **plugin.lua**: Código ejecutado en NGINX usando el [módulo LUA de NGINX](https://github.com/openresty/lua-nginx-module).

- **plugin.json**: Metadatos, configuraciones y definiciones de trabajos para tu plugin.

### Empezando

El primer paso es crear una carpeta que contendrá el plugin:

```shell
mkdir miplugin && \
cd miplugin
```

### Metadatos

Un archivo llamado **plugin.json** y escrito en la raíz de la carpeta del plugin debe contener metadatos sobre el plugin. Aquí hay un ejemplo:

```json
{
  "id": "miplugin",
  "name": "Mi Plugin",
  "description": "Solo un plugin de ejemplo.",
  "version": "1.0",
  "stream": "partial",
  "settings": {
    "DUMMY_SETTING": {
      "context": "multisite",
      "default": "1234",
      "help": "Aquí está la ayuda de la configuración.",
      "id": "dummy-id",
      "label": "Configuración de ejemplo",
      "regex": "^.*$",
      "type": "text"
    }
  },
  "jobs": [
    {
      "name": "mi-trabajo",
      "file": "mi-trabajo.py",
      "every": "hour"
    }
  ]
}
```

Aquí están los detalles de los campos:

|     Campo     | Obligatorio |  Tipo  | Descripción                                                                                                                                    |
| :-----------: | :---------: | :----: | :--------------------------------------------------------------------------------------------------------------------------------------------- |
|     `id`      |     sí      | cadena | ID interno para el plugin: debe ser único entre otros plugins (incluidos los del "núcleo") y contener solo caracteres en minúscula.            |
|    `name`     |     sí      | cadena | Nombre de tu plugin.                                                                                                                           |
| `description` |     sí      | cadena | Descripción de tu plugin.                                                                                                                      |
|   `version`   |     sí      | cadena | Versión de tu plugin.                                                                                                                          |
|   `stream`    |     sí      | cadena | Información sobre el soporte de stream: `no`, `yes` o `partial`.                                                                               |
|  `settings`   |     sí      |  dict  | Lista de las configuraciones de tu plugin.                                                                                                     |
|    `jobs`     |     no      | lista  | Lista de los trabajos de tu plugin.                                                                                                            |
|    `bwcli`    |     no      |  dict  | Mapea los nombres de los comandos de la CLI a los archivos almacenados en el directorio 'bwcli' del plugin para exponer los plugins de la CLI. |

### Orden de ejecución

Un plugin puede declarar dónde quiere situarse dentro de una fase. La clave es opcional; todo lo que sigue es una indicación, no una garantía.

```json
{
  "id": "myplugin",
  "order": {
    "ssl_certificate": { "after": ["certificates"] },
    "access": { "before": ["antibot"] }
  }
}
```

- Los nombres de fase son `init`, `init_worker`, `set`, `rewrite`, `access`, `content`, `ssl_client_hello_default`, `ssl_certificate`, `ssl_certificate_default`, `header`, `log`, `preread`, `log_stream`, `log_default`, `timer` e `init_workers`. `headers` se acepta como alias de `header`, igual que en `order.json`.
- `before` / `after` son listas de ids de plugin. Un plugin no disponible, o que no implementa la fase, se ignora con una advertencia en el log de errores de BunkerWeb. Se nombran como máximo cinco de esos ids por plugin y por fase; el resto se resume en una única línea `… more unknown order id(s) for phase <phase>`, de modo que una lista larga no pueda inundar el log.
- Las declaraciones mutuamente contradictorias (un ciclo) se descartan con una advertencia: las declaraciones de los plugins del ciclo se omiten y el orden se recalcula teniendo en cuenta las restricciones de todos los demás plugins; solo si ese reintento también falla se conserva el orden predeterminado. Un bloque `order` malformado también se advierte y se descarta; el plugin sigue cargándose. La comprobación es todo-o-nada e idéntica en el generador de configuración y en el runtime: una sola entrada inválida — un valor que no es una cadena, un id que no coincide con `[A-Za-z0-9_.-]{1,64}` o `"*"`, un nombre de fase desconocido, una clave desconocida junto a `before`/`after`, un `before`/`after` que no es una lista — descarta **toda la clave `order`**, incluidas las fases que estaban bien formadas. Corrige la entrada indicada y el resto de la declaración vuelve a aplicarse. Una lista `before`/`after` vacía, un objeto de fase vacío y un `order` vacío se aceptan todos y significan "sin restricción".
- `before` / `after` pueden contener el comodín `"*"`, que designa a cualquier otro plugin que implemente esta fase y que no esté él mismo restringido respecto a mí. `"before": ["*"]` coloca un plugin por delante de cualquier plugin que no se fije a sí mismo, y `"after": ["*"]` lo coloca al final. Los plugins que comparten el mismo comodín conservan su orden de lista predeterminado; un id de plugin explícito prevalece sobre el comodín de otro plugin.

Tras la inicialización, el `plugins_order` calculado queda sellado: declare `order` en el manifiesto en lugar de intentar cambiarlo desde el código del plugin.

**Prioridad dentro de una fase**, de mayor a menor:

1. la configuración `PLUGINS_ORDER_<PHASE>` del operador (global o por servicio);
2. las restricciones `order` declaradas, resueltas mediante una ordenación estable;
3. los plugins PRO alfabéticamente, luego los plugins externos alfabéticamente, luego los plugins principales según `order.json`, y por último los plugins principales restantes alfabéticamente.

Cada configuración tiene los siguientes campos (la clave es el ID de las configuraciones utilizadas en una configuración):

|   Campo    | Obligatorio |  Tipo  | Descripción                                                                        |
| :--------: | :---------: | :----: | :--------------------------------------------------------------------------------- |
| `context`  |     sí      | cadena | Contexto de la configuración: `multisite` o `global`.                              |
| `default`  |     sí      | cadena | El valor predeterminado de la configuración.                                       |
|   `help`   |     sí      | cadena | Texto de ayuda sobre el plugin (mostrado en la interfaz de usuario web).           |
|    `id`    |     sí      | cadena | ID interno utilizado por la interfaz de usuario web para los elementos HTML.       |
|  `label`   |     sí      | cadena | Etiqueta mostrada por la interfaz de usuario web.                                  |
|  `regex`   |     sí      | cadena | La expresión regular utilizada para validar el valor proporcionado por el usuario. |
|   `type`   |     sí      | cadena | El tipo del campo: `text`, `check`, `select` o `password`.                         |
| `multiple` |     no      | cadena | ID único para agrupar múltiples configuraciones con números como sufijo.           |
|  `select`  |     no      | lista  | Lista de posibles valores de cadena cuando `type` es `select`.                     |

Cada trabajo tiene los siguientes campos:

|  Campo  | Obligatorio |  Tipo  | Descripción                                                                                                                                            |
| :-----: | :---------: | :----: | :----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`  |     sí      | cadena | Nombre del trabajo.                                                                                                                                    |
| `file`  |     sí      | cadena | Nombre del archivo dentro de la carpeta de trabajos.                                                                                                   |
| `every` |     sí      | cadena | Frecuencia de programación del trabajo: `minute`, `hour`, `day`, `week` u `once` (sin frecuencia, solo una vez antes de (re)generar la configuración). |
| `reload` | no | bool | Si un cambio de este job debe activar un reload de las instancias de BunkerWeb. Por defecto `false`. |
| `async` | no | bool | El job se dirige a la cola `heavy`; ambas colas comparten el grupo de workers predeterminado. Aíslelas con `WORKER_QUEUES=heavy` o `WORKER_QUEUES=default`. Por defecto `false`. |
| `regenerate` | no | bool | Si un cambio de este job requiere que la configuración de NGINX se **renderice de nuevo**, no solo se envíe. Por defecto `false`. |

Los trabajos pesados principales son `backup-data`, `bunkernet-register`, `bunkernet-data`, `push-configs`, `certbot-new`, `certbot-renew`, `download-plugins`, `download-crs-plugins` y `download-pro-plugins`; el enrutamiento sigue el indicador `async` del manifiesto, no el nombre del trabajo.

!!! info "Un manifiesto rechazado se rechaza en todas partes"

    Un `plugin.json` que incumple alguno de los límites siguientes es rechazado tanto por el
    generador de configuración (Python) como por el runtime de NGINX (Lua): se elimina de la
    configuración generada y nunca se carga, ordena ni ejecuta. El rechazo se registra como un
    `ERROR` que nombra el id del plugin, el archivo, el campo que falla y el límite.

    Los límites de longitud se miden en **bytes UTF-8**, no en caracteres. `id`, `version` y el
    `id` de la configuración son exclusivamente ASCII, por lo que el recuento de bytes y de
    caracteres siempre coincide para esos campos.

    | Campo | Límite |
    | :---: | :--- |
    | `id` | solo letras ASCII, dígitos, `.`, `_`, `-`, 1-64 bytes |
    | `name` | máx. 128 bytes |
    | `description` | máx. 256 bytes |
    | `version` | debe coincidir con `\d+\.\d+(\.\d+)?` (solo dígitos ASCII) |
    | `stream` | uno de `yes`, `no`, `partial` |
    | `id` de la configuración | solo letras ASCII mayúsculas, dígitos, `_`, 1-256 bytes |
    | `context` de la configuración | uno de `global`, `multisite` |
    | `default` de la configuración | máx. 4096 bytes |
    | `help` de la configuración | máx. 512 bytes |
    | `label` de la configuración | máx. 256 bytes |
    | `regex` de la configuración | máx. 1024 bytes |
    | `type` de la configuración | uno de `password`, `text`, `number`, `file`, `check`, `select`, `multiselect`, `multivalue`, `size`, `duration` |

    `extensions` se valida solo en el lado de Python: el runtime de NGINX nunca lo lee. Los campos
    de trabajo (`jobs[]`) también son exclusivos de Python porque es el Worker quien los despacha.

### Comandos de CLI

Los plugins pueden extender la herramienta 'bwcli' con comandos personalizados que se ejecutan bajo 'bwcli plugin <plugin_id> ...':

1. Agregue un directorio 'bwcli' en su plugin y coloque un archivo por comando (por ejemplo, 'bwcli/list.py'). La CLI agrega la ruta del plugin a 'sys.path' antes de ejecutar el archivo.
2. Declare los comandos en la sección opcional 'bwcli' de 'plugin.json', mapeando cada nombre de comando a su nombre de archivo ejecutable.

```json
{
  "bwcli": {
    "list": "list.py",
    "save": "save.py"
  }
}
```

El planificador expone automáticamente los comandos declarados una vez que se instala el plugin. Los plugins principales, como 'backup' en 'src/common/core/backup', siguen el mismo patrón.

### Configuraciones

Puedes añadir configuraciones personalizadas de NGINX añadiendo una carpeta llamada **confs** con contenido similar a las [configuraciones personalizadas](advanced.md#custom-configurations). Cada subcarpeta dentro de **confs** contendrá plantillas de [jinja2](https://jinja.palletsprojects.com) que se generarán y cargarán en el contexto correspondiente (`http`, `server-http`, `default-server-http`, `stream`, `server-stream`, `modsec`, `modsec-crs`, `crs-plugins-before` y `crs-plugins-after`).

Aquí hay un ejemplo para un archivo de plantilla de configuración dentro de la carpeta **confs/server-http** llamado **example.conf**:

```nginx
location /setting {
  default_type 'text/plain';
    content_by_lua_block {
        ngx.say('{{ DUMMY_SETTING }}')
    }
}
```

`{{ DUMMY_SETTING }}` será reemplazado por el valor de `DUMMY_SETTING` elegido por el usuario del plugin.

### Plantillas

Consulta la [documentación de plantillas](concepts.md#templates) para obtener más información.

### LUA

#### Script principal

Internamente, BunkerWeb utiliza el [módulo LUA de NGINX](https://github.com/openresty/lua-nginx-module) para ejecutar código dentro de NGINX. Los plugins que necesiten ejecutar código deben proporcionar un archivo lua en el directorio raíz de la carpeta del plugin utilizando el valor `id` de **plugin.json** como su nombre. Aquí hay un ejemplo llamado **miplugin.lua**:

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

Las funciones declaradas se llaman automáticamente durante contextos específicos. Aquí están los detalles de cada función:

|    Función    |                                          Contexto                                           | Descripción                                                                                                                                                                         | Valor de retorno                                                                                                                                                                                                                                                                                                                                                                              |
| :-----------: | :-----------------------------------------------------------------------------------------: | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|    `init`     |          [init_by_lua](https://github.com/openresty/lua-nginx-module#init_by_lua)           | Se llama cuando NGINX acaba de iniciarse o recibió una orden de recarga. El caso de uso típico es preparar cualquier dato que será utilizado por tu plugin.                         | `ret`, `msg`<ul><li>`ret` (booleano): true si no hay error, de lo contrario false</li><li>`msg` (cadena): mensaje de éxito o error</li></ul>                                                                                                                                                                                                                                                  |
|     `set`     |           [set_by_lua](https://github.com/openresty/lua-nginx-module#set_by_lua)            | Se llama antes de cada solicitud recibida por el servidor. El caso de uso típico es para computar antes de la fase de acceso.                                                       | `ret`, `msg`<ul><li>`ret` (booleano): true si no hay error, de lo contrario false</li><li>`msg` (cadena): mensaje de éxito o error</li></ul>                                                                                                                                                                                                                                                  |
|   `access`    |        [access_by_lua](https://github.com/openresty/lua-nginx-module#access_by_lua)         | Se llama en cada solicitud recibida por el servidor. El caso de uso típico es hacer las comprobaciones de seguridad aquí y denegar la solicitud si es necesario.                    | `ret`, `msg`,`status`,`redirect`<ul><li>`ret` (booleano): true si no hay error, de lo contrario false</li><li>`msg` (cadena): mensaje de éxito o error</li><li>`status` (número): interrumpe el proceso actual y devuelve el [estado HTTP](https://github.com/openresty/lua-nginx-module#http-status-constants)</li><li>`redirect` (URL): si se establece, redirigirá a la URL dada</li></ul> |
|     `log`     |           [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)            | Se llama cuando una solicitud ha terminado (y antes de que se registre en los registros de acceso). El caso de uso típico es hacer estadísticas o calcular contadores, por ejemplo. | `ret`, `msg`<ul><li>`ret` (booleano): true si no hay error, de lo contrario false</li><li>`msg` (cadena): mensaje de éxito o error</li></ul>                                                                                                                                                                                                                                                  |
| `log_default` |           [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)            | Igual que `log` pero solo se llama en el servidor predeterminado.                                                                                                                   | `ret`, `msg`<ul><li>`ret` (booleano): true si no hay error, de lo contrario false</li><li>`msg` (cadena): mensaje de éxito o error</li></ul>                                                                                                                                                                                                                                                  |
|   `preread`   | [preread_by_lua](https://github.com/openresty/stream-lua-nginx-module#preread_by_lua_block) | Similar a la función `access` pero para el modo stream.                                                                                                                             | `ret`, `msg`,`status`<ul><li>`ret` (booleano): true si no hay error, de lo contrario false</li><li>`msg` (cadena): mensaje de éxito o error</li><li>`status` (número): interrumpe el proceso actual y devuelve el [estado](https://github.com/openresty/lua-nginx-module#http-status-constants)</li></ul>                                                                                     |
| `log_stream`  |     [log_by_lua](https://github.com/openresty/stream-lua-nginx-module#log_by_lua_block)     | Similar a la función `log` pero para el modo stream.                                                                                                                                | `ret`, `msg`<ul><li>`ret` (booleano): true si no hay error, de lo contrario false</li><li>`msg` (cadena): mensaje de éxito o error</li></ul>                                                                                                                                                                                                                                                  |

#### Librerías

Todas las directivas del [módulo LUA de NGINX](https://github.com/openresty/lua-nginx-module) y del [módulo LUA de stream de NGINX](https://github.com/openresty/stream-lua-nginx-module) están disponibles. Además de eso, puedes usar las librerías LUA incluidas en BunkerWeb: consulta [este script](https://github.com/bunkerity/bunkerweb/blobsrc/deps/clone.sh) para la lista completa.

Si necesitas librerías adicionales, puedes ponerlas en la carpeta raíz del plugin y acceder a ellas prefijándolas con el ID de tu plugin. Aquí hay un ejemplo de archivo llamado **mialibreria.lua**:

```lua
local _M = {}

_M.dummy = function ()
	return "dummy"
end

return _M
```

Y aquí está cómo puedes usarla desde el archivo **miplugin.lua**:

```lua
local mialibreria = require "miplugin.mialibreria"

...

mialibreria.dummy()

...
```

#### Ayudantes

Algunos módulos de ayudantes proporcionan ayudantes comunes y útiles:

- `self.variables`: permite acceder y almacenar los atributos de los plugins
- `self.logger`: imprime registros
- `bunkerweb.utils`: varias funciones útiles
- `bunkerweb.datastore`: accede a los datos compartidos globales en una instancia (almacén de clave/valor)
- `bunkerweb.clusterstore`: accede a un almacén de datos Redis compartido entre las instancias de BunkerWeb (almacén de clave/valor)

Para acceder a las funciones, primero necesitas **requerir** los módulos:

```lua
local utils       = require "bunkerweb.utils"
local datastore   = require "bunkerweb.datastore"
local clustestore = require "bunkerweb.clustertore"
```

Recuperar el valor de una configuración:

```lua
local myvar = self.variables["DUMMY_SETTING"]
if not myvar then
    self.logger:log(ngx.ERR, "no se puede recuperar la configuración DUMMY_SETTING")
else
    self.logger:log(ngx.NOTICE, "DUMMY_SETTING = " .. value)
end
```

Almacenar algo en la caché local:

```lua
local ok, err = self.datastore:set("plugin_myplugin_something", "somevalue")
if not ok then
    self.logger:log(ngx.ERR, "no se puede guardar plugin_myplugin_something en el datastore: " .. err)
else
    self.logger:log(ngx.NOTICE, "se guardó correctamente plugin_myplugin_something en el datastore")
end
```

Comprobar si una dirección IP es global:

```lua
local ret, err = utils.ip_is_global(ngx.ctx.bw.remote_addr)
if ret == nil then
    self.logger:log(ngx.ERR, "error al comprobar si la IP " .. ngx.ctx.bw.remote_addr .. " es global o no: " .. err)
elseif not ret then
    self.logger:log(ngx.NOTICE, "la IP " .. ngx.ctx.bw.remote_addr .. " no es global")
else
    self.logger:log(ngx.NOTICE, "la IP " .. ngx.ctx.bw.remote_addr .. " es global")
end
```

!!! tip "Más ejemplos"

    Si quieres ver la lista completa de funciones disponibles, puedes echar un vistazo a los archivos presentes en el [directorio lua](https://github.com/bunkerity/bunkerweb/tree/v1.7.0-beta/src/bw/lua/bunkerweb) del repositorio.

### Trabajos

BunkerWeb utiliza un programador de trabajos interno para tareas periódicas como renovar certificados con certbot, descargar listas negras, descargar archivos MMDB, ... Puedes añadir tareas de tu elección colocándolas dentro de una subcarpeta llamada **jobs** y listándolas en el archivo de metadatos **plugin.json**. No olvides añadir los permisos de ejecución para todos para evitar cualquier problema cuando un usuario clone e instale tu plugin.

El código de salida de un job es un protocolo: `sys.exit(1)` significa "algo cambió", lo que envía el directorio de caché del job (`/var/cache/bunkerweb/<plugin_id>/`) a las instancias y les pide que recarguen. `sys.exit(0)` significa que el job tuvo éxito y no cambió nada; cualquier otro código es un fallo. Devolver un valor en lugar de salir no hace nada — los valores de retorno se descartan y se registran como `0`.

Enviar la caché es suficiente mientras las instancias lean sus archivos en **tiempo de ejecución**. Si una de sus plantillas `confs/` *lee* lo que el job escribió — incrustando una lista descargada, o comprobando un certificado en caché con `is_file()` — entonces no basta: la configuración que las instancias recargan es la que se renderizó antes de que su job se ejecutara, y no menciona el nuevo material. Declare `"regenerate": true` en ese job y BunkerWeb renderiza la configuración de nuevo, la envía y recarga. Cuesta un renderizado completo más un despacho extra de los jobs de su plugin, así que actívelo solo cuando una plantilla realmente lea la caché, y asegúrese de que el job salga con `0` cuando no tenga nada nuevo que escribir.

!!! warning "Las claves desconocidas se rechazan"
    Las entradas de job aceptan `name`, `file`, `every`, `reload`, `async` y `regenerate`, y nada más. Una clave mal escrita (`"regenrate"`) hace que todo el plugin falle la validación y sea ignorado, nombrando la clave incorrecta en los registros — deliberadamente, para que una errata no pueda desactivar silenciosamente un flag.

### Página del plugin

Todo lo relacionado con la interfaz de usuario web se encuentra dentro de la subcarpeta **ui**, como vimos en la [sección de estructura anterior.](#estructura).

#### Requisitos previos

Cuando quieras crear una página de plugin, necesitas dos archivos:

- **template.html** que será accesible con un **GET /plugins/<*id_plugin*>**.

- **actions.py** donde puedes añadir algo de scripting y lógica con un **POST /plugins/<*id_plugin*>**. Ten en cuenta que este archivo **necesita una función con el mismo nombre que el plugin** para funcionar. Este archivo es necesario incluso si la función está vacía.

#### Ejemplo básico

!!! info "Plantilla de Jinja 2"
    El archivo **template.html** es una plantilla de Jinja2, por favor consulta la [documentación de Jinja2](https://jinja.palletsprojects.com) si es necesario.

Podemos dejar de lado el archivo **actions.py** y empezar a **usar solo la plantilla en una situación GET**. La plantilla puede acceder al contexto y las librerías de la aplicación, por lo que puedes usar Jinja, request o las utilidades de Flask.

Por ejemplo, puedes obtener los argumentos de la solicitud en tu plantilla de esta manera:

```html
<p>argumentos de la solicitud: {{ request.args.get() }}.</p>
```

#### Actions.py

!!! warning "Token CSRF"

    Ten en cuenta que cada envío de formulario está protegido mediante un token CSRF, necesitarás incluir el siguiente fragmento en tus formularios:
    ```html
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
    ```

Puedes potenciar tu página de plugin con scripting adicional con el archivo **actions.py** al enviar un **POST /plugins/<*id_plugin*>**.

Tienes dos funciones por defecto en **actions.py**:

**Función pre_render**

Esto te permite recuperar datos cuando haces un **GET** de la plantilla, y usar los datos con la variable pre_render disponible en Jinja para mostrar contenido de forma más dinámica.

```python
def pre_render(**kwargs)
  return <datos_pre_render>
```

BunkerWeb te enviará este tipo de respuesta:


```python
return jsonify({"status": "ok|ko", "code" : XXX, "data": <datos_pre_render>}), 200
```

**Función <*id_plugin*>**

Esto te permite recuperar datos cuando haces un **POST** desde el punto final de la plantilla, que debe usarse en AJAX.

```python
def miplugin(**kwargs)
  return <datos_id_plugin>
```

BunkerWeb te enviará este tipo de respuesta:

```python
return jsonify({"message": "ok", "data": <datos_id_plugin>}), 200
```

**A qué puedes acceder desde action.py**

Aquí están los argumentos que se pasan y a los que se accede en las funciones de action.py:

```python
function(app=app, db=db, api_client=api_client, bw_instances_utils=bw_instances_utils, args=args, data=data)
```

`db` es el manejador retirado y lanza `RetiredDBError` si se usa; utilice `api_client` en su lugar.

!!! info "Librerías de Python disponibles"

    La interfaz de usuario web de BunkerWeb incluye un conjunto de librerías de Python preinstaladas que puedes usar en el archivo `actions.py` de tu plugin u otros scripts relacionados con la interfaz de usuario. Estas están disponibles de serie sin necesidad de instalaciones adicionales.

    Aquí está la lista completa de librerías incluidas:

    - **bcrypt** - Librería para el hashing de contraseñas
    - **biscuit-python** - Tokens de autenticación Biscuit
    - **certbot** - Cliente ACME para Let's Encrypt
    - **Flask** - Framework web
    - **Flask-Login** - Gestión de sesiones de usuario
    - **Flask-Session[cachelib]** - Almacenamiento de sesiones del lado del servidor
    - **Flask-WTF** - Manejo de formularios y protección CSRF
    - **gunicorn[gthread]** - Servidor HTTP WSGI
    - **pillow** - Procesamiento de imágenes
    - **psutil** - Utilidades del sistema y de procesos
    - **python_dateutil** - Utilidades de fecha y hora
    - **qrcode** - Generación de códigos QR
    - **regex** - Expresiones regulares avanzadas
    - **urllib3** - Cliente HTTP
    - **user_agents** - Análisis de agentes de usuario

    !!! tip "Uso de librerías en tu plugin"
        Para importar y usar estas librerías en tu archivo `actions.py`, simplemente usa la declaración estándar de `import` de Python. Por ejemplo:

        ```python
        from flask import request
        import bcrypt
        ```

    ??? warning "Librerías externas"
        Si necesitas librerías que no están en la lista anterior, instálalas dentro de la carpeta `ui` de tu plugin e impórtalas usando la directiva clásica de `import`. Asegúrate de la compatibilidad con el entorno existente para evitar conflictos.

**Algunos ejemplos**

- Recuperar datos enviados de un formulario

```python
from flask import request

def miplugin(**kwargs) :
	mi_valor_formulario = request.form["mi_entrada_formulario"]
  return mi_valor_formulario
```

- Acceder a la configuración de la aplicación

**action.py**
```python
from flask import request

def pre_render(**kwargs) :
	config = kwargs['app'].config["CONFIG"].get_config(methods=False)
  return config
```

**plantilla**
```html
<!-- metadatos + configuración -->
<div>{{ pre_render }}</div>
```

### Hooks.py

Esta documentación describe los ganchos de ciclo de vida utilizados para gestionar diferentes etapas de una solicitud dentro de la aplicación. Cada gancho está asociado a una fase específica.

=== "before_request"
    Estos ganchos se ejecutan **antes** de procesar una solicitud entrante. Se utilizan normalmente para tareas de preprocesamiento como autenticación, validación o registro.

    Si el gancho devuelve un objeto de respuesta, Flask omitirá el manejo de la solicitud y devolverá la respuesta directamente. Esto puede ser útil para cortocircuitar el pipeline de procesamiento de la solicitud.

    **Ejemplo:**

    ```python
    from flask import request, Response

    def before_request():
        print("Antes de la solicitud: validando la solicitud...", flush=True)
        # Realizar autenticación, validación o registro aquí
        if not is_valid_request(request): # Estamos en el contexto de la aplicación
            return Response("¡Solicitud inválida!", status=400)

    def is_valid_request(request):
        # Lógica de validación ficticia
        return "user" in request
    ```
=== "after_request"
    Estos ganchos se ejecutan **después** de que la solicitud ha sido procesada. Son ideales para tareas de postprocesamiento como limpieza, registro adicional o modificación de la respuesta antes de que se envíe de vuelta.

    Reciben el objeto de respuesta como argumento y pueden modificarlo antes de devolverlo. El primer gancho after_request que devuelva una respuesta se utilizará como la respuesta final.

    **Ejemplo:**

    ```python
    from flask import request

    def after_request(response):
        print("Después de la solicitud: registrando la respuesta...", flush=True)
        # Realizar registro, limpieza o modificaciones de la respuesta aquí
        log_response(response)
        return response

    def log_response(response):
        # Lógica de registro ficticia
        print("Respuesta registrada:", response, flush=True)
    ```
=== "teardown_request"
    Estos ganchos se invocan cuando el contexto de la solicitud se está desmontando. Estos ganchos se utilizan para liberar recursos o manejar errores que ocurrieron durante el ciclo de vida de la solicitud.

    **Ejemplo:**

    ```python
    def teardown_request(error=None):
        print("Desmontaje de la solicitud: limpiando recursos...", flush=True)
        # Realizar limpieza, liberar recursos o manejar errores aquí
        if error:
            handle_error(error)
        cleanup_resources()

    def handle_error(error):
        # Lógica de manejo de errores ficticia
        print("Error encontrado:", error, flush=True)

    def cleanup_resources():
        # Lógica de limpieza de recursos ficticia
        print("Los recursos han sido limpiados.", flush=True)
    ```
=== "context_processor"
    Estos ganchos se utilizan para inyectar contexto adicional en las plantillas o vistas. Enriquecen el contexto de tiempo de ejecución pasando datos comunes (como información del usuario o configuraciones) a las plantillas.

    Si un procesador de contexto devuelve un diccionario, las claves y los valores se añadirán al contexto para todas las plantillas. Esto te permite compartir datos entre múltiples vistas o plantillas.

    **Ejemplo:**

    ```python
    def context_processor() -> dict:
        print("Procesador de contexto: inyectando datos de contexto...", flush=True)
        # Devolver un diccionario que contenga datos de contexto para las plantillas/vistas
        return {
            "current_user": "John Doe",
            "app_version": "1.0.0",
            "feature_flags": {"new_ui": True}
        }
    ```

Este diseño de ganchos de ciclo de vida proporciona un enfoque modular y sistemático para gestionar diversos aspectos del ciclo de vida de una solicitud:

- **Modularidad:** Cada gancho es responsable de una fase distinta, asegurando que las responsabilidades estén separadas.
- **Mantenibilidad:** Los desarrolladores pueden añadir, modificar o eliminar fácilmente implementaciones de ganchos sin afectar otras partes del ciclo de vida de la solicitud.
- **Extensibilidad:** El marco es flexible, lo que permite añadir ganchos adicionales o mejoras a medida que evolucionan los requisitos de la aplicación.

Al definir claramente las responsabilidades de cada gancho y sus prefijos de registro asociados, el sistema asegura que cada etapa del procesamiento de la solicitud sea transparente y manejable.

### Blueprints

En Flask, los **blueprints** sirven como una forma modular de organizar componentes relacionados —como vistas, plantillas y archivos estáticos— dentro de tu aplicación. Te permiten agrupar la funcionalidad de manera lógica y se pueden usar para crear nuevas secciones de tu aplicación o sobrescribir las existentes.

#### Crear un Blueprint

Para definir un blueprint, creas una instancia de la clase `Blueprint`, especificando su nombre y la ruta de importación. Luego, defines las rutas y vistas asociadas a este blueprint.

**Ejemplo: Definir un nuevo Blueprint**

```python
from os.path import dirname
from flask import Blueprint, render_template

# Definir el blueprint
mi_blueprint = Blueprint('mi_blueprint', __name__, template_folder=dirname(__file__) + '/templates') # La carpeta de plantillas se establece para evitar conflictos con el blueprint original

# Definir una ruta dentro del blueprint
@mi_blueprint.route('/mi_blueprint')
def mi_pagina_blueprint():
    return render_template('mi_blueprint.html')
```


En este ejemplo, se crea un blueprint llamado `mi_blueprint` y se define una ruta `/mi_blueprint` dentro de él.

#### Sobrescribir un Blueprint existente

Los blueprints también pueden sobrescribir los existentes para modificar o ampliar la funcionalidad. Para hacer esto, asegúrate de que el nuevo blueprint tenga el mismo nombre que el que estás sobrescribiendo y regístralo después del original.

**Ejemplo: Sobrescribir un Blueprint existente**

```python
from os.path import dirname
from flask import Flask, Blueprint

# Blueprint original
instances = Blueprint('instances', __name__, template_folder=dirname(__file__) + '/templates') # La carpeta de plantillas se establece para evitar conflictos con el blueprint original

@instances.route('/instances')
def override_instances():
    return "Mi nueva página de instancias"
```

En este escenario, al acceder a la URL `/instances` se mostrará "Mi nueva página de instancias" porque el blueprint `instances`, registrado en último lugar, sobrescribe el blueprint `instances` original.

!!! warning "Sobre la sobrescritura"
    Ten cuidado al sobrescribir los blueprints existentes, ya que puede afectar el comportamiento de la aplicación. Asegúrate de que los cambios se alineen con los requisitos de la aplicación y no introduzcan efectos secundarios inesperados.

    Todas las rutas existentes se eliminarán del blueprint original, por lo que necesitarás volver a implementarlas si es necesario.

#### Convenciones de nomenclatura

!!! danger "Importante"
    Asegúrate de que el nombre del blueprint coincida con el nombre de la variable del blueprint, de lo contrario no se considerará un blueprint válido y no se registrará.

Para la coherencia y la claridad, es aconsejable seguir estas convenciones de nomenclatura:

- **Nombres de Blueprint**: Usa nombres cortos, todo en minúsculas. Se pueden usar guiones bajos para mejorar la legibilidad, por ejemplo, `user_auth`.

- **Nombres de archivo**: Haz que el nombre del archivo coincida con el nombre del blueprint, asegurándote de que esté todo en minúsculas con guiones bajos según sea necesario, por ejemplo, `user_auth.py`.

Esta práctica se alinea con las convenciones de nomenclatura de módulos de Python y ayuda a mantener una estructura de proyecto clara.

**Ejemplo: Nomenclatura de Blueprint y archivo**

```
plugin /
    ui / blueprints / user_auth.py
                      templates / user_auth.html
```

En esta estructura, `user_auth.py` contiene el blueprint `user_auth`, y `user_auth.html` es la plantilla asociada, cumpliendo con las convenciones de nomenclatura recomendadas.

### Traducciones de plugins

Un plugin puede incluir su propio catálogo de traducción y hacer que se combine en la UI de administración, tanto en el navegador (`t()`) como en el servidor (`_()` en una plantilla Jinja). No se necesita ninguna declaración en `plugin.json` ni ningún paso de build. La URL del catálogo servida al navegador lleva una huella de archivo, de modo que las cachés del navegador se actualizan automáticamente cada vez que cambia el catálogo de un plugin instalado.

Se admiten dos disposiciones, en este orden:

1. `ui/blueprints/static/locales/<lang>.json` para un plugin con un blueprint de Flask.
2. `ui/static/locales/<lang>.json` para una página simple `ui/template.html`.

`en.json` es el fallback obligatorio; cualquier otro archivo de idioma es opcional. Toda clave de nivel superior de tu catálogo DEBE ser tu id de plugin, por ejemplo `{"my_plugin": {"title": "..."}}`. Cualquier otra clave de nivel superior se rechaza por completo — no se fusiona, no solo la hoja en colisión — con una única advertencia que nombra tu plugin y la(s) clave(s) implicada(s); esto es lo que impide que el catálogo de un plugin reclame o eclipse el espacio de nombres de otro plugin (o del núcleo). Dentro de tu propio espacio de nombres, una hoja que colisiona con un valor existente (del núcleo, o de un plugin cargado antes con exactamente tu mismo id de plugin) se descarta con una advertencia; una hoja nueva bajo tu propio espacio de nombres siempre se fusiona. Un id de plugin que contiene un `.` no puede tener un catálogo alcanzable (tanto `_()` como `t()` dividen la clave de búsqueda por `.`) y se rechaza por completo, con una advertencia.

El `_()` del servidor no puede interpolar marcadores `{{var}}` como sí hace el `t()` del navegador. Use `t()` en el navegador para cadenas que requieran sustitución.

### Superficie compatible de plugins UI

La UI web no tiene ninguna conexión a la base de datos. El código UI de un plugin accede a la API central mediante **`PLUGIN_API`**:

```python
from app.dependencies import PLUGIN_API


def my_page():
    return PLUGIN_API.get_services(with_drafts=True)
```

`ui/actions.py` la recibe como `api_client`:

```python
def pre_render(**kwargs):
    return {"services": kwargs["api_client"].get_services(with_drafts=True)}
```

Estos métodos son la promesa de compatibilidad entre versiones menores; el resto de métodos del cliente UI son internos. `PLUGIN_API` no es un límite de seguridad: el código del plugin se ejecuta en el proceso de la UI, así que instale solo plugins de confianza.

| Método | Qué devuelve |
| --- | --- |
| `get_global_settings(full=False, methods=False, with_drafts=False, filtered_settings=None, global_only=True)` | La configuración como un dict plano. |
| `get_plugins(type="all", with_data=False, only_enabled=False, with_settings=True)` | Los plugins instalados y su esquema de ajustes. |
| `get_services(with_drafts=True)` / `get_service(service_id, full=False, methods=True, with_drafts=True)` | Los servicios o la configuración de un servicio. |
| `get_configs(service=None, type=None, with_drafts=True, with_data=False)` / `get_config_item(service, type, name, with_data=True)` | Las configuraciones personalizadas. |
| `create_config(**kwargs)` / `update_config(service, type, name, body=None, **kwargs)` / `delete_config(service, type, name)` | Las escrituras de configuraciones personalizadas. |
| `get_cache_files(service=None, plugin=None, job_name=None, with_data=False)` / `get_cache_file(service, plugin, job, filename, download=False)` | Las entradas de caché de los trabajos. |
| `get_jobs()` / `get_last_job_run(name)` | Los trabajos registrados y su última ejecución. |
| `readonly` | `True` cuando la base de datos está en solo lectura. |

Los ajustes no se escriben a través de `PLUGIN_API`: use `BW_CONFIG.edit_global_conf()` o `BW_CONFIG.edit_service()`, que los validan primero.

**Migración desde la 1.6.** `app.dependencies.DB` está retirado; usarlo lanza un `RuntimeError` que nombra al plugin. Reemplace `DB.get_config(...)` por `PLUGIN_API.get_global_settings(...)` o `PLUGIN_API.get_service(...)`, las llamadas de configuración personalizada por los métodos `get_config*` / de escritura de configuración correspondientes, las llamadas de caché de trabajos por `get_cache_files(..., with_data=True)`, y `kwargs["db"]` en `ui/actions.py` por `kwargs["api_client"]`. `DB._db_session()` no tiene reemplazo: la UI no tiene sesión de base de datos. `DB` es falsy, así que reemplace `if DB is not None:` por `if DB:` antes de acceder a él.
