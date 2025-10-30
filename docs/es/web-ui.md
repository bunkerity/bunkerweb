# Interfaz de usuario web

## Descripción general

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/tGS3pzquEjY" title="Interfaz de usuario web de BunkerWeb" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

La "Interfaz de usuario web" es una aplicación web que te ayuda a gestionar tu instancia de BunkerWeb utilizando una interfaz fácil de usar en lugar de depender únicamente de la línea de comandos.

Aquí tienes una lista de las características que ofrece la interfaz de usuario web:

- Obtén una vista completa de los ataques bloqueados
- Inicia, detén, reinicia y recarga tu instancia de BunkerWeb
- Añade, edita y elimina configuraciones para tus aplicaciones web
- Añade, edita y elimina configuraciones personalizadas para NGINX y ModSecurity
- Instala y desinstala plugins externos
- Explora los archivos en caché
- Supervisa la ejecución de los trabajos y reinícialos según sea necesario
- Visualiza los registros y busca patrones

## Requisitos previos {#prerequisites}

Dado que la interfaz de usuario web es una aplicación web, la arquitectura recomendada es ejecutar BunkerWeb delante de ella como un proxy inverso. El procedimiento de instalación recomendado es utilizar el asistente de configuración, que te guiará paso a paso como se describe en la [guía de inicio rápido](quickstart-guide.md).

!!! warning "Consideraciones de seguridad"

    La seguridad de la interfaz de usuario web es extremadamente importante. Si una persona no autorizada obtiene acceso a la aplicación, no solo podrá editar tus configuraciones, sino que también podría ejecutar código en el contexto de BunkerWeb (por ejemplo, a través de una configuración personalizada que contenga código LUA). Te recomendamos encarecidamente que sigas las mejores prácticas de seguridad mínimas, como:

    * Elige una contraseña segura para el inicio de sesión (**al menos 8 caracteres, incluyendo 1 letra minúscula, 1 letra mayúscula, 1 dígito y 1 carácter especial**)
    * Coloca la interfaz de usuario web bajo una URI "difícil de adivinar"
    * Habilita la autenticación de dos factores (2FA)
    * No expongas la interfaz de usuario web a Internet sin restricciones adicionales
    * Aplica las mejores prácticas enumeradas en la [sección de usos avanzados](advanced.md#security-tuning) de la documentación según tu caso de uso

## Actualizar a PRO {#upgrade-to-pro}

!!! tip "Prueba gratuita de BunkerWeb PRO"
    ¿Quieres probar rápidamente BunkerWeb PRO durante un mes? Usa el código `freetrial` al realizar tu pedido en el [panel de BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) o haciendo clic [aquí](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc) para aplicar directamente el código de promoción (se hará efectivo al finalizar la compra).

Una vez que tengas tu clave de licencia PRO del [panel de BunkerWeb](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc), puedes pegarla en la página PRO de la interfaz de usuario web.

<figure markdown>
  ![Actualización PRO](assets/img/pro-ui-upgrade.png){ align=center, width="700" }
  <figcaption>Actualizar a PRO desde la interfaz de usuario web</figcaption>
</figure>

!!! warning "Tiempo de actualización"
    La versión PRO se descarga en segundo plano por el programador, puede tardar un tiempo en actualizarse.

Cuando tu instancia de BunkerWeb se haya actualizado a la versión PRO, verás la fecha de caducidad de tu licencia y el número máximo de servicios que puedes proteger.

<figure markdown>
  ![Actualización PRO](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>Información de la licencia PRO</figcaption>
</figure>

## Acceso a los registros

A partir de la versión `1.6`, el método de acceso a los registros ha cambiado. Esta actualización afecta específicamente a las integraciones basadas en contenedores: la interfaz de usuario web ahora leerá los archivos de registro del directorio `/var/log/bunkerweb`.

Para mantener los registros accesibles desde la interfaz de usuario web, te recomendamos que utilices un servidor de syslog, como `syslog-ng`, para leer los registros y crear los archivos correspondientes en el directorio `/var/log/bunkerweb`.

!!! warning "Uso de una carpeta local para los registros"
    La interfaz de usuario web se ejecuta como un **usuario sin privilegios con UID 101 y GID 101** dentro del contenedor por razones de seguridad: en caso de que se explote una vulnerabilidad, el atacante no tendrá privilegios completos de root (UID/GID 0).

    Sin embargo, hay una desventaja: si utilizas una **carpeta local para los registros**, debes **establecer los permisos correctos** para que el usuario sin privilegios pueda leer los archivos de registro. Por ejemplo:

    ```shell
    mkdir bw-logs && \
    chown root:101 bw-logs && \
    chmod 770 bw-logs
    ```

    Alternativamente, si la carpeta ya existe:

    ```shell
    chown -R root:101 bw-logs && \
    chmod -R 770 bw-logs
    ```

    Si estás utilizando [Docker en modo sin raíz](https://docs.docker.com/engine/security/rootless) o [podman](https://podman.io/), los UID y GID en el contenedor se mapearán a diferentes en el host. Primero necesitarás verificar tu subuid y subgid iniciales:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    Por ejemplo, si tienes un valor de **100000**, el UID/GID mapeado será **100100** (100000 + 100):

    ```shell
    mkdir bw-logs && \
    sudo chgrp 100100 bw-logs && \
    chmod 770 bw-logs
    ```

    O si la carpeta ya existe:

    ```shell
    sudo chgrp -R 100100 bw-logs && \
    sudo chmod -R 770 bw-logs
    ```

### Plantillas de Compose

=== "Docker"

    Para reenviar los registros correctamente al directorio `/var/log/bunkerweb` en la integración de Docker, necesitarás transmitir los registros a un archivo usando `syslog-ng`. Aquí hay un ejemplo de cómo hacerlo:

    ```yaml
    x-bw-env: &bw-env
      # Anclamos las variables de entorno para evitar la duplicación
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
      # Token de API opcional al asegurar el acceso a la API
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *bw-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog
          options:
            tag: "bunkerweb" # Esta será la etiqueta utilizada por syslog-ng para crear el archivo de registro
            syslog-address: "udp://10.20.30.254:514" # Esta es la dirección del contenedor de syslog-ng

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Asegúrate de establecer el nombre de instancia correcto
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos
          SERVE_FILES: "no"
          DISABLE_DEFAULT_SERVER: "yes"
          USE_CLIENT_CACHE: "yes"
          USE_GZIP: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Cámbialo a una URI difícil de adivinar
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
        volumes:
          - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-scheduler" # Esta será la etiqueta utilizada por syslog-ng para crear el archivo de registro
            syslog-address: "udp://10.20.30.254:514" # Esta es la dirección del contenedor de syslog-ng

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6-rc1
        environment:
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para el usuario administrador
          TOTP_ENCRYPTION_KEYS: "mysecret" # Recuerda establecer una clave secreta más segura (consulta la sección de Requisitos previos)
        volumes:
          - bw-logs:/var/log/bunkerweb # Este es el volumen utilizado para almacenar los registros
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-ui" # Esta será la etiqueta utilizada por syslog-ng para crear el archivo de registro
            syslog-address: "udp://10.20.30.254:514" # Esta es la dirección del contenedor de syslog-ng

      bw-db:
        image: mariadb:11
        # Establecemos el tamaño máximo de paquete permitido para evitar problemas con consultas grandes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para la base de datos
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      bw-syslog:
        image: balabit/syslog-ng:4.9.0
        cap_add:
          - NET_BIND_SERVICE  # Enlazar a puertos bajos
          - NET_BROADCAST  # Enviar broadcasts
          - NET_RAW  # Usar sockets raw
          - DAC_READ_SEARCH  # Leer archivos omitiendo permisos
          - DAC_OVERRIDE  # Omitir permisos de archivo
          - CHOWN  # Cambiar propietario
          - SYSLOG  # Escribir en los registros del sistema
        volumes:
          - bw-logs:/var/log/bunkerweb # Este es el volumen utilizado para almacenar los registros
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # Este es el archivo de configuración de syslog-ng
        networks:
          bw-universe:
            ipv4_address: 10.20.30.254 # Asegúrate de establecer la dirección IP correcta

    volumes:
      bw-data:
      bw-storage:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker Autoconf"

    Para reenviar los registros correctamente al directorio `/var/log/bunkerweb` en la integración de Autoconf, necesitarás transmitir los registros a un archivo usando `syslog-ng`. Aquí hay un ejemplo de cómo hacerlo:

    ```yaml
    x-ui-env: &bw-ui-env
      # Anclamos las variables de entorno para evitar la duplicación
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog
          options:
            tag: "bunkerweb" # Esta será la etiqueta utilizada por syslog-ng para crear el archivo de registro
            syslog-address: "udp://10.20.30.254:514" # Esta es la dirección del contenedor de syslog-ng

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: "" # No necesitamos especificar la instancia de BunkerWeb aquí, ya que son detectadas automáticamente por el servicio de autoconfiguración
          SERVER_NAME: "" # El nombre del servidor se rellenará con las etiquetas de los servicios
          MULTISITE: "yes" # Configuración obligatoria para autoconfiguración / ui
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        volumes:
          - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-scheduler" # Esta será la etiqueta utilizada por syslog-ng para crear el archivo de registro
            syslog-address: "udp://10.20.30.254:514" # Esta es la dirección del contenedor de syslog-ng

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc1
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375" # Esta es la dirección del socket de Docker
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-docker
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-autoconf" # Esta será la etiqueta utilizada por syslog-ng para crear el archivo de registro
            syslog-address: "udp://10.20.30.254:514" # Esta es la dirección del contenedor de syslog-ng

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6-rc1
        environment:
          <<: *bw-ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para el usuario administrador
          TOTP_ENCRYPTION_KEYS: "mysecret" # Recuerda establecer una clave secreta más segura (consulta la sección de Requisitos previos)
        volumes:
          - bw-logs:/var/log/bunkerweb
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_TEMPLATE=ui"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme" # Cámbialo a una URI difícil de adivinar
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
        logging:
          driver: syslog
          options:
            tag: "bw-ui" # Esta será la etiqueta utilizada por syslog-ng para crear el archivo de registro
            syslog-address: "udp://10.20.30.254:514" # Esta es la dirección del contenedor de syslog-ng

      bw-db:
        image: mariadb:11
        # Establecemos el tamaño máximo de paquete permitido para evitar problemas con consultas grandes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para la base de datos
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: "unless-stopped"
        networks:
          - bw-docker

      bw-syslog:
        image: balabit/syslog-ng:4.9.0
        cap_add:
          - NET_BIND_SERVICE  # Enlazar a puertos bajos
          - NET_BROADCAST  # Enviar broadcasts
          - NET_RAW  # Usar sockets raw
          - DAC_READ_SEARCH  # Leer archivos omitiendo permisos
          - DAC_OVERRIDE  # Omitir permisos de archivo
          - CHOWN  # Cambiar propietario
          - SYSLOG  # Escribir en los registros del sistema
        volumes:
          - bw-logs:/var/log/bunkerweb # Este es el volumen utilizado para almacenar los registros
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # Este es el archivo de configuración de syslog-ng
        networks:
          bw-universe:
            ipv4_address: 10.20.30.254 # Asegúrate de establecer la dirección IP correcta

    volumes:
      bw-data:
      bw-storage:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
      bw-docker:
        name: bw-docker
    ```

### Configuración de Syslog-ng

Aquí hay un ejemplo de un archivo `syslog-ng.conf` que puedes usar para reenviar los registros a un archivo:

```conf
@version: 4.8

# Configuración de origen para recibir registros de contenedores de Docker
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# Plantilla para formatear mensajes de registro
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# Configuración de destino para escribir registros en archivos con nombres dinámicos
destination d_dyna_file {
  file(
    "/var/log/bunkerweb/${PROGRAM}.log"
    template(t_imp)
    owner("101")
    group("101")
    dir_owner("root")
    dir_group("101")
    perm(0440)
    dir_perm(0770)
    create_dirs(yes)
  );
};

# Ruta de registro para dirigir los registros a archivos con nombres dinámicos
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Gestión de la cuenta

Puedes acceder a la página de gestión de la cuenta haciendo clic en la imagen de perfil en la esquina superior derecha:

<figure markdown>
  ![Descripción general](assets/img/manage-account.png){ align=center, width="400" }
  <figcaption>Acceso a la página de la cuenta desde la esquina superior derecha</figcaption>
</figure>

### Nombre de usuario / Contraseña

!!! warning "Contraseña/nombre de usuario perdido"

    En caso de que hayas olvidado tus credenciales de la interfaz de usuario, puedes restablecerlas desde la CLI siguiendo [los pasos descritos en la sección de solución de problemas](troubleshooting.md#web-ui).

Puedes actualizar tu nombre de usuario o contraseña rellenando los formularios dedicados en la pestaña **Seguridad**. Por razones de seguridad, debes introducir tu contraseña actual incluso si estás conectado.

Ten en cuenta que cuando tu nombre de usuario o contraseña se actualice, se cerrará la sesión de la interfaz de usuario web para que vuelvas a iniciarla.

<figure markdown>
  ![Descripción general](assets/img/profile-username-password.png){ align=center }
  <figcaption>Formulario de nombre de usuario / contraseña</figcaption>
</figure>

### Autenticación de dos factores

!!! tip "Claves de cifrado obligatorias"

    Al habilitar la 2FA, debes proporcionar al menos una clave de cifrado. Esta clave se utilizará para cifrar tus secretos TOTP.

    La forma recomendada de generar una clave válida es usar el paquete `passlib`:

    ```shell
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    Establece la clave generada en la variable de entorno `TOTP_ENCRYPTION_KEYS` de la interfaz de usuario web. También puedes establecer varias claves separadas por espacios o como un diccionario (por compatibilidad con versiones anteriores).

!!! warning "Clave secreta perdida"

    En caso de que hayas perdido tu clave secreta, hay dos opciones disponibles:

    - Puedes recuperar tu cuenta usando uno de los códigos de recuperación proporcionados cuando habilitaste la 2FA (un código de recuperación solo se puede usar una vez).
    - Puedes deshabilitar la 2FA desde la CLI siguiendo [los pasos descritos en la sección de solución de problemas](troubleshooting.md#web-ui).

Puedes potenciar la seguridad de tu inicio de sesión añadiendo la **Autenticación de Dos Factores (2FA)** a tu cuenta. Al hacerlo, se necesitará un código extra además de tu contraseña.

La interfaz de usuario web utiliza la [Contraseña de un Solo Uso Basada en el Tiempo (TOTP)](https://es.wikipedia.org/wiki/Contrase%C3%B1a_de_un_solo_uso_basada_en_tiempo) como implementación de 2FA: usando una **clave secreta**, el algoritmo generará **contraseñas de un solo uso solo válidas por un corto período de tiempo**.

Cualquier cliente TOTP como Google Authenticator, Authy, FreeOTP, ... puede ser utilizado para almacenar la clave secreta y generar los códigos. Ten en cuenta que una vez que se habilita TOTP, **no podrás recuperarla desde la interfaz de usuario web**.

Los siguientes pasos son necesarios para habilitar la función TOTP desde la interfaz de usuario web:

- Copia la clave secreta o usa el código QR en tu aplicación de autenticación
- Introduce el código TOTP actual en la entrada de 2FA
- Introduce tu contraseña actual

!!! info "Actualización de la clave secreta"
    Se genera una nueva clave secreta **cada vez** que visitas la página o envías el formulario. En caso de que algo haya salido mal (p. ej.: código TOTP caducado), necesitarás copiar la nueva clave secreta en tu aplicación de autenticación hasta que la 2FA se habilite con éxito.

!!! tip "Códigos de recuperación"

    Cuando habilites la 2FA, se te proporcionarán **5 códigos de recuperación**. Estos códigos se pueden utilizar para recuperar tu cuenta en caso de que hayas perdido tu clave secreta TOTP. Cada código solo se puede usar una vez. **Estos códigos solo se mostrarán una vez, así que asegúrate de guardarlos en un lugar seguro**.

    Si alguna vez pierdes tus códigos de recuperación, **puedes actualizarlos a través de la sección TOTP de la página de gestión de la cuenta**. Ten en cuenta que los antiguos códigos de recuperación se invalidarán.

Puedes habilitar o deshabilitar la 2FA y también actualizar los códigos de recuperación en la pestaña **Seguridad**:

<figure markdown>
  ![Descripción general](assets/img/profile-totp.png){ align=center }
  <figcaption>Formularios para habilitar / deshabilitar / actualizar los códigos de recuperación de TOTP</figcaption>
</figure>

Después de una combinación exitosa de inicio de sesión/contraseña, se te pedirá que introduzcas tu código TOTP:

<figure markdown>
  ![Descripción general](assets/img/profile-2fa.png){ align=center, width="400" }
  <figcaption>2FA en la página de inicio de sesión</figcaption>
</figure>

### Sesiones actuales

En la pestaña **Sesión**, podrás listar y revocar las sesiones actuales:

<figure markdown>
  ![Descripción general](assets/img/sessions.png){ align=center }
  <figcaption>Gestionar sesiones</figcaption>
</figure>

## Instalación avanzada

La interfaz de usuario web se puede desplegar y configurar sin pasar por el proceso del asistente de configuración: la configuración se realiza a través de variables de entorno, que se pueden añadir directamente a los contenedores o en el archivo `/etc/bunkerweb/ui.env` en el caso de una integración con Linux.

!!! tip "Variables de entorno específicas de la interfaz de usuario web"

    La interfaz de usuario web utiliza las siguientes variables de entorno:

    - `OVERRIDE_ADMIN_CREDS`: establécelo en `yes` para habilitar la anulación incluso si las credenciales de administrador ya están configuradas (el valor predeterminado es `no`).
    - `ADMIN_USERNAME`: nombre de usuario para acceder a la interfaz de usuario web.
    - `ADMIN_PASSWORD`: contraseña para acceder a la interfaz de usuario web.
    - `FLASK_SECRET`: una clave secreta utilizada para cifrar la cookie de sesión (si no se establece, se generará una clave aleatoria).
    - `TOTP_ENCRYPTION_KEYS` (o `TOTP_SECRETS`): una lista de claves de cifrado TOTP separadas por espacios o un diccionario (p. ej.: `{"1": "miclavesecreta"}` o `miclavesecreta` o `miclavesecreta miclavesecreta1`). **Te recomendamos encarecidamente que establezcas esta variable si quieres usar 2FA, ya que se utilizará para cifrar las claves secretas de TOTP** (si no se establece, se generará un número aleatorio de claves secretas). Consulta la [documentación de passlib](https://passlib.readthedocs.io/en/stable/narr/totp-tutorial.html#application-secrets) para obtener más información.
    - `UI_LISTEN_ADDR` (preferido): la dirección en la que escuchará la interfaz de usuario web (el valor predeterminado es `0.0.0.0` en **imágenes de Docker** y `127.0.0.1` en **instalaciones de Linux**). Vuelve a `LISTEN_ADDR` si no se establece.
    - `UI_LISTEN_PORT` (preferido): el puerto en el que escuchará la interfaz de usuario web (el valor predeterminado es `7000`). Vuelve a `LISTEN_PORT` si no se establece.
    - `MAX_WORKERS`: el número de trabajadores utilizados por la interfaz de usuario web (el valor predeterminado es el número de CPU).
    - `MAX_THREADS`: el número de hilos utilizados por la interfaz de usuario web (el valor predeterminado es `MAX_WORKERS` * 2).
    - `FORWARDED_ALLOW_IPS`: una lista de direcciones IP o redes que se pueden usar en la cabecera `X-Forwarded-For` (el valor predeterminado es `*` en **imágenes de Docker** y `127.0.0.1` en **instalaciones de Linux**).
    - `CHECK_PRIVATE_IP`: establécelo en `yes` para no desconectar a los usuarios que hayan cambiado su dirección IP durante una sesión si están en una red privada (el valor predeterminado es `yes`). (Las direcciones IP no privadas siempre se comprueban).
    - `ENABLE_HEALTHCHECK`: establécelo en `yes` para habilitar el punto final `/healthcheck` que devuelve una respuesta JSON simple con información de estado (el valor predeterminado es `no`).

    La interfaz de usuario web utilizará estas variables para autenticarte y gestionar la función 2FA.

!!! example "Generación de secretos recomendados"

    Para generar una **ADMIN_PASSWORD** válida, te recomendamos que **utilices un gestor de contraseñas** o un **generador de contraseñas**.

    Puedes generar una **FLASK_SECRET** válida usando el siguiente comando:

    ```shell
    python3 -c "import secrets; print(secrets.token_hex(64))"
    ```

    Puedes generar **TOTP_ENCRYPTION_KEYS** válidas separadas por espacios usando el siguiente comando (necesitarás el paquete `passlib`):

    ```shell
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

=== "Linux"

    La instalación de la interfaz de usuario web utilizando la [integración de Linux](integrations.md#linux) es bastante sencilla porque se instala con BunkerWeb.

    La interfaz de usuario web viene como un servicio systemd llamado `bunkerweb-ui`, asegúrate de que esté habilitado:

    ```shell
    sudo systemctl enable bunkerweb-ui && \
    sudo systemctl status bunkerweb-ui
    ```

    Un archivo de entorno dedicado ubicado en `/etc/bunkerweb/ui.env` se utiliza para configurar la interfaz de usuario web:

    ```conf
    ADMIN_USERNAME=changeme
    ADMIN_PASSWORD=changeme
    TOTP_ENCRYPTION_KEYS=mysecret
    ```

    Reemplaza los datos de `changeme` con tus propios valores.

    Recuerda establecer una clave secreta más segura para `TOTP_ENCRYPTION_KEYS`.

    Cada vez que edites el archivo `/etc/bunkerweb/ui.env`, necesitarás reiniciar el servicio:

    ```shell
    systemctl restart bunkerweb-ui
    ```

    Acceder a la interfaz de usuario web a través de BunkerWeb es una [configuración de proxy inverso](quickstart-guide.md) clásica. Ten en cuenta que la interfaz de usuario web está escuchando en el puerto `7000` y solo en la interfaz de bucle invertido.

    Aquí está la plantilla de `/etc/bunkerweb/variables.env` que puedes usar:

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4
    API_LISTEN_IP=127.0.0.1
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_TEMPLATE=ui
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/changeme
    www.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:7000
    ```

    No olvides recargar el servicio `bunkerweb`:

    ```shell
    systemctl reload bunkerweb
    ```

=== "Docker"

    La interfaz de usuario web se puede desplegar utilizando un contenedor dedicado que está disponible en [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui):

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternativamente, también puedes construirla tú mismo:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    Acceder a la interfaz de usuario web a través de BunkerWeb es una [configuración de proxy inverso](quickstart-guide.md) clásica. Te recomendamos que conectes BunkerWeb y la interfaz de usuario web utilizando una red dedicada (como `bw-universe`, también utilizada por el programador) para que no esté en la misma red que tus servicios web por razones de seguridad obvias. Ten en cuenta que el contenedor de la interfaz de usuario web está escuchando en el puerto `7000`.

    !!! info "Backend de la base de datos"

        Si quieres otro backend de base de datos que no sea MariaDB, consulta los archivos docker-compose en la [carpeta misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc1/misc/integrations) del repositorio.

    Aquí está la plantilla de docker-compose que puedes usar (no olvides editar los datos de `changeme`):

    ```yaml
    x-ui-env: &ui-env
      # Anclamos las variables de entorno para evitar la duplicación
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Para soporte de QUIC / HTTP3
        environment:
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Asegúrate de establecer el rango de IP correcto para que el programador pueda enviar la configuración a la instancia
          API_TOKEN: "" # Refleja el API_TOKEN si lo usas
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Asegúrate de establecer el nombre de instancia correcto
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Reflejamos el API_WHITELIST_IP del servicio bunkerweb
          API_TOKEN: "" # Refleja el API_TOKEN si lo usas
          SERVE_FILES: "no"
          DISABLE_DEFAULT_SERVER: "yes"
          USE_CLIENT_CACHE: "yes"
          USE_GZIP: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Recuerda establecer una URI más segura
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000" # El contenedor de la interfaz de usuario web escucha en el puerto 7000 por defecto
        volumes:
          - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6-rc1
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para el usuario changeme
          TOTP_ENCRYPTION_KEYS: "mysecret" # Recuerda establecer una clave secreta más segura (consulta la sección de Requisitos previos)
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Establecemos el tamaño máximo de paquete permitido para evitar problemas con consultas grandes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para la base de datos
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-db

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
      bw-db:
        name: bw-db
    ```

=== "Docker autoconf"

    La interfaz de usuario web se puede desplegar utilizando un contenedor dedicado que está disponible en [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui):

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternativamente, también puedes construirla tú mismo:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    !!! tip "Variables de entorno"

        Por favor, lee la sección de [Requisitos previos](#prerequisites) para ver todas las variables de entorno que puedes establecer para personalizar la interfaz de usuario web.

    Acceder a la interfaz de usuario web a través de BunkerWeb es una [configuración de proxy inverso](quickstart-guide.md) clásica. Te recomendamos que conectes BunkerWeb y la interfaz de usuario web utilizando una red dedicada (como `bw-universe`, también utilizada por el programador y la autoconfiguración) para que no esté en la misma red que tus servicios web por razones de seguridad obvias. Ten en cuenta que el contenedor de la interfaz de usuario web está escuchando en el puerto `7000`.

    !!! info "Backend de la base de datos"

        Si quieres otro backend de base de datos que no sea MariaDB, consulta los archivos docker-compose en la [carpeta misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc1/misc/integrations) del repositorio.

    Aquí está la plantilla de docker-compose que puedes usar (no olvides editar los datos de `changeme`):

    ```yaml
    x-ui-env: &ui-env
      # Anclamos las variables de entorno para evitar la duplicación
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Para soporte de QUIC / HTTP3
        labels:
          - "bunkerweb.INSTANCE=yes" # Establecemos la etiqueta de la instancia para permitir que la autoconfiguración detecte la instancia
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
        volumes:
          - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc1
        depends_on:
          - bw-docker
        environment:
          <<: *ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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
        # Establecemos el tamaño máximo de paquete permitido para evitar problemas con consultas grandes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para la base de datos
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6-rc1
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para el usuario changeme
          TOTP_ENCRYPTION_KEYS: "mysecret" # Recuerda establecer una clave secreta más segura (consulta la sección de Requisitos previos)
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_TEMPLATE=ui"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme"
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
        networks:
          - bw-universe
          - bw-db

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
      bw-db:
        name: bw-db
    ```

=== "Kubernetes"

    La interfaz de usuario web se puede desplegar utilizando un contenedor dedicado que está disponible en [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) y se puede desplegar como un [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) estándar.

    Acceder a la interfaz de usuario web a través de BunkerWeb es una [configuración de proxy inverso](quickstart-guide.md) clásica. La segmentación de la red entre la interfaz de usuario web y los servicios web no se cubre en esta documentación. Ten en cuenta que el contenedor de la interfaz de usuario web está escuchando en el puerto `7000`.

    !!! info "Backend de la base de datos"

        Si quieres otro backend de base de datos que no sea MariaDB, consulta los archivos yaml en la [carpeta misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc1/misc/integrations) del repositorio.

    Aquí está la parte correspondiente de tu archivo values.yaml que puedes usar:

    ```yaml
    settings:
      # Usa un secreto existente llamado bunkerweb y que contenga los siguientes valores:
      # - admin-username
      # - admin-password
      # - flask-secret
      # - totp-secrets
      existingSecret: "secret-bunkerweb"
    ui:
      wizard: false
      ingress:
        enabled: true
        serverName: "www.example.com"
        serverPath: "/admin"
      overrideAdminCreds: "yes"
    ```

=== "Swarm"

    !!! warning "Obsoleto"
        La integración de Swarm está obsoleta y se eliminará en una futura versión. Por favor, considera usar la [integración de Kubernetes](integrations.md#kubernetes) en su lugar.

        **Se puede encontrar más información en la [documentación de la integración de Swarm](integrations.md#swarm).**

    La interfaz de usuario web se puede desplegar utilizando un contenedor dedicado que está disponible en [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui):

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternativamente, también puedes construirla tú mismo:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    Acceder a la interfaz de usuario web a través de BunkerWeb es una [configuración de proxy inverso](quickstart-guide.md) clásica. Te recomendamos que conectes BunkerWeb y la interfaz de usuario web utilizando una red dedicada (como `bw-universe`, también utilizada por el programador y la autoconfiguración) para que no esté en la misma red que tus servicios web por razones de seguridad obvias. Ten en cuenta que el contenedor de la interfaz de usuario web está escuchando en el puerto `7000`.

    !!! info "Backend de la base de datos"

        Si quieres otro backend de base de datos que no sea MariaDB, consulta los archivos de la pila en la [carpeta misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc1/misc/integrations) del repositorio.

    Aquí está la plantilla de la pila que puedes usar (no olvides editar los datos de `changeme`):

    ```yaml
    x-ui-env: &ui-env
      # Anclamos las variables de entorno para evitar la duplicación
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc1
        ports:
          - published: 80
            target: 8080
            mode: host
            protocol: tcp
          - published: 443
            target: 8443
            mode: host
            protocol: tcp
          - published: 443
            target: 8443
            mode: host
            protocol: udp # Para soporte de QUIC / HTTP3
        environment:
          SWARM_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        networks:
          - bw-universe
          - bw-services
        deploy:
          mode: global
          placement:
            constraints:
              - "node.role == worker"
          labels:
            - "bunkerweb.INSTANCE=yes"

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "bw-redis"
          UI_HOST: "http://bw-ui:7000" # Cámbialo si es necesario
        volumes:
          - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc1
        environment:
          <<: *ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          CONFIGS: "1"
          CONTAINERS: "1"
          SERVICES: "1"
          SWARM: "1"
          TASKS: "1"
          LOG_LEVEL: "warning"
        networks:
          - bw-docker
        deploy:
          placement:
            constraints:
              - "node.role == manager"

      bw-db:
        image: mariadb:11
        # Establecemos el tamaño máximo de paquete permitido para evitar problemas con consultas grandes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para la base de datos
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-db

      bw-redis:
        image: redis:7-alpine
        networks:
          - bw-universe

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6-rc1
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para el usuario changeme
          TOTP_ENCRYPTION_KEYS: "mysecret" # Recuerda establecer una clave secreta más segura (consulta la sección de Requisitos previos)
        networks:
          - bw-universe
          - bw-db
        deploy:
          labels:
            - "bunkerweb.SERVER_NAME=www.example.com"
            - "bunkerweb.USE_TEMPLATE=ui"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_URL=/changeme"
            - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"

    volumes:
      bw-data:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        driver: overlay
        attachable: true
        ipam:
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
        driver: overlay
        attachable: true
      bw-docker:
        name: bw-docker
        driver: overlay
        attachable: true
      bw-db:
        name: bw-db
        driver: overlay
        attachable: true
    ```

## Soporte de idiomas y localización

La interfaz de usuario de BunkerWeb admite varios idiomas. Las traducciones se gestionan en el directorio `src/ui/app/static/locales`. Actualmente están disponibles los siguientes idiomas:

- Inglés (en)
- Francés (fr)
- Árabe (ar)
- Bengalí (bn)
- Español (es)
- Hindi (hi)
- Portugués (pt)
- Ruso (ru)
- Urdu (ur)
- Chino (zh)
- Alemán (de)
- Italiano (it)

Consulta el [locales/README.md](https://github.com/bunkerity/bunkerweb/raw/v1.6.6-rc1/src/ui/app/static/locales/README.md) para obtener detalles sobre la procedencia de la traducción y el estado de la revisión.

### Contribuir con traducciones

¡Agradecemos las contribuciones para mejorar o añadir nuevos archivos de localización!

**Cómo contribuir con una traducción:**

1. Edita el archivo `src/ui/app/lang_config.py` para añadir tu idioma (código, nombre, bandera, nombre en inglés).
2. Copia `en.json` como plantilla en `src/ui/app/static/locales/`, renómbralo con el código de tu idioma (p. ej., `de.json` para alemán).
3. Traduce los valores de tu nuevo archivo.
4. Actualiza la tabla en `locales/README.md` para añadir tu idioma e indicar quién lo creó/revisó.
5. Envía una solicitud de extracción.

Para las actualizaciones, edita el archivo correspondiente y actualiza la tabla de procedencia según sea necesario.

Consulta el [locales/README.md](https://github.com/bunkerity/bunkerweb/raw/v1.6.6-rc1/src/ui/app/static/locales/README.md) para obtener las directrices completas.
Genera una traducción limpia de este archivo
