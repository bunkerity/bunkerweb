# Actualización

## Actualización desde 1.6.X

### Procedimiento

#### Docker

1.  **Hacer copia de seguridad de la base de datos**:

    - Antes de proceder con la actualización de la base de datos, asegúrate de realizar una copia de seguridad completa del estado actual de la base de datos.
    - Utiliza las herramientas adecuadas para hacer una copia de seguridad de toda la base de datos, incluyendo datos, esquemas y configuraciones.

    ```bash
    docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
    ```

    ```bash
    docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
    ```

2.  **Actualizar BunkerWeb**:
    - Actualiza BunkerWeb a la última versión.
        1.  **Actualiza el archivo Docker Compose**: Actualiza el archivo Docker Compose para usar la nueva versión de la imagen de BunkerWeb.
            ```yaml
            services:
                bunkerweb:
                    image: bunkerity/bunkerweb:1.6.7-rc1
                    ...
                bw-scheduler:
                    image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
                    ...
                bw-autoconf:
                    image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
                    ...
                bw-ui:
                    image: bunkerity/bunkerweb-ui:1.6.7-rc1
                    ...
            ```

        2.  **Reinicia los contenedores**: Reinicia los contenedores para aplicar los cambios.
            ```bash
            docker compose down
            docker compose up -d
            ```

3.  **Revisa los registros**: Revisa los registros del servicio del programador para asegurarte de que la migración fue exitosa.

    ```bash
    docker compose logs <scheduler_container>
    ```

4.  **Verifica la base de datos**: Verifica que la actualización de la base de datos fue exitosa revisando los datos y las configuraciones en el nuevo contenedor de la base de datos.

#### Linux

=== "Actualización fácil usando el script de instalación"

    * **Inicio rápido**:

        Para empezar, descarga el script de instalación y su suma de verificación, luego verifica la integridad del script antes de ejecutarlo.

        ```bash
        LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | jq -r .tag_name)

        # Download the script and its checksum
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh.sha256

        # Verify the checksum
        sha256sum -c install-bunkerweb.sh.sha256

        # Si la verificación es exitosa, ejecuta el script
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh
        ```

        !!! danger "Aviso de seguridad"
            **Siempre verifica la integridad del script de instalación antes de ejecutarlo.**

            Descarga el archivo de suma de verificación y usa una herramienta como `sha256sum` para confirmar que el script no ha sido alterado o manipulado.

            Si la verificación de la suma de verificación falla, **no ejecutes el script**—puede no ser seguro.

    * **Cómo funciona**:

        El mismo script de instalación multipropósito utilizado para instalaciones nuevas también puede realizar una actualización in situ. Cuando detecta una instalación existente y una versión de destino diferente, cambia al modo de actualización y aplica el siguiente flujo de trabajo:

        1. Detección y validación
            * Detecta el SO/versión y confirma la matriz de soporte.
            * Lee la versión de BunkerWeb actualmente instalada desde `/usr/share/bunkerweb/VERSION`.
        2. Decisión del escenario de actualización
            * Si la versión solicitada es igual a la instalada, se aborta (a menos que lo vuelvas a ejecutar explícitamente para ver el estado).
            * Si las versiones difieren, marca una actualización.
        3. (Opcional) Copia de seguridad automática previa a la actualización
            * Si `bwcli` y el programador están disponibles y la copia de seguridad automática está habilitada, crea una copia de seguridad a través del plugin de copia de seguridad incorporado.
            * Destino: ya sea el directorio que proporcionaste con `--backup-dir` o una ruta generada como `/var/tmp/bunkerweb-backup-YYYYmmdd-HHMMSS`.
            * Puedes deshabilitar esto con `--no-auto-backup` (la copia de seguridad manual entonces se convierte en tu responsabilidad).
        4. Detención de servicios
            * Detiene `bunkerweb`, `bunkerweb-ui` y `bunkerweb-scheduler` para garantizar una actualización consistente (coincide con las recomendaciones del procedimiento manual).
        5. Eliminación de bloqueos de paquetes
            * Elimina temporalmente `apt-mark hold` / `dnf versionlock` en `bunkerweb` y `nginx` para que se pueda instalar la versión de destino.
        6. Ejecución de la actualización
            * Instala solo la nueva versión del paquete de BunkerWeb (NGINX no se reinstala en modo de actualización a menos que falte, esto evita tocar un NGINX correctamente anclado).
            * Vuelve a aplicar los bloqueos/versionlocks para congelar las versiones actualizadas.
        7. Finalización y estado
            * Muestra el estado de systemd para los servicios principales y los próximos pasos.
            * Deja tu configuración y base de datos intactas: solo se actualiza el código de la aplicación y los archivos gestionados.

        Comportamientos clave / notas:

        * El script NO modifica tu `/etc/bunkerweb/variables.env` ni el contenido de la base de datos.
        * Si la copia de seguridad automática falló (o se deshabilitó), aún puedes hacer una restauración manual usando la sección de Reversión a continuación.
        * El modo de actualización evita intencionadamente reinstalar o degradar NGINX fuera de la versión anclada compatible ya presente.
        * Los registros para la solución de problemas permanecen en `/var/log/bunkerweb/`.

    * **Comportamiento según el modo**:

        - El instalador reutiliza la misma lógica de selección durante la actualización: el modo manager mantiene el asistente deshabilitado, vincula la API a `0.0.0.0` y sigue exigiendo una IP para la lista blanca (proporciónala con `--manager-ip` en ejecuciones no interactivas), mientras que el modo worker continúa obligando a indicar las IP del manager.
        - Las actualizaciones del manager pueden decidir si se inicia el servicio Web UI, y el resumen indica explícitamente el estado del servicio API para que puedas controlarlo con `--api` / `--no-api`.
        - Las opciones de CrowdSec siguen limitadas a las actualizaciones full stack, y el script continúa validando el sistema operativo y la arquitectura de CPU antes de modificar paquetes; las combinaciones no soportadas siguen requiriendo `--force`.

        Resumen de la reversión:

        * Usa el directorio de copia de seguridad generado (o tu copia de seguridad manual) + los pasos en la sección de Reversión para restaurar la base de datos, luego reinstala la versión anterior de la imagen/paquete y vuelve a bloquear los paquetes.

    *  **Opciones de línea de comandos**:

        Puedes realizar actualizaciones desatendidas con los mismos indicadores utilizados para la instalación. Los más relevantes para las actualizaciones:

        | Opción                  | Propósito                                                                                                                                     |
        | :---------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------- |
        | `-v, --version <X.Y.Z>` | Versión de BunkerWeb de destino a la que actualizar.                                                                                          |
        | `-y, --yes`             | No interactivo (asume la confirmación de la actualización y habilita la copia de seguridad automática a menos que se use `--no-auto-backup`). |
        | `--backup-dir <RUTA>`   | Destino para la copia de seguridad automática previa a la actualización. Se crea si no existe.                                                |
        | `--no-auto-backup`      | Omitir la copia de seguridad automática (NO recomendado). Debes tener una copia de seguridad manual.                                          |
        | `-q, --quiet`           | Suprimir la salida (combinar con registro / monitoreo).                                                                                       |
        | `-f, --force`           | Continuar en una versión de SO no compatible.                                                                                                 |
        | `--dry-run`             | Mostrar el entorno detectado, las acciones previstas y luego salir sin cambiar nada.                                                          |

        Ejemplos:

        ```bash
        # Actualizar a 1.6.7~rc1 interactivamente (pedirá confirmación para la copia de seguridad)
        sudo ./install-bunkerweb.sh --version 1.6.7~rc1

        # Actualización no interactiva con copia de seguridad automática a un directorio personalizado
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 --backup-dir /var/backups/bw-2025-01 -y

        # Actualización desatendida silenciosa (salida suprimida) – depende de la copia de seguridad automática predeterminada
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 -y -q

        # Realizar una ejecución de prueba (plan) sin aplicar cambios
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 --dry-run

        # Actualizar omitiendo la copia de seguridad automática (NO recomendado)
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 --no-auto-backup -y
        ```

        !!! warning "Omitir copias de seguridad"
            Usar `--no-auto-backup` sin tener una copia de seguridad manual verificada puede resultar en una pérdida de datos irreversible si la actualización encuentra problemas. Siempre mantén al menos una copia de seguridad reciente y probada.

=== "Manual"

    1. **Hacer copia de seguridad de la base de datos**:

        - Antes de proceder con la actualización de la base de datos, asegúrate de realizar una copia de seguridad completa del estado actual de la base de datos.
        - Utiliza las herramientas adecuadas para hacer una copia de seguridad de toda la base de datos, incluyendo datos, esquemas y configuraciones.

        ??? warning "Información para usuarios de Red Hat Enterprise Linux (RHEL) 8.10"
            Si estás usando **RHEL 8.10** y planeas usar una **base de datos externa**, necesitarás instalar el paquete `mysql-community-client` para asegurar que el comando `mysqldump` esté disponible. Puedes instalar el paquete ejecutando los siguientes comandos:

            === "MySQL/MariaDB"

                1. **Instalar el paquete de configuración del repositorio de MySQL**

                    ```bash
                    sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
                    ```

                2. **Habilitar el repositorio de MySQL**

                    ```bash
                    sudo dnf config-manager --enable mysql80-community
                    ```

                3. **Instalar el cliente de MySQL**

                    ```bash
                    sudo dnf install mysql-community-client
                    ```

            === "PostgreSQL"

                4. **Instalar el paquete de configuración del repositorio de PostgreSQL**

                    ```bash
                    dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                    ```

                5. **Instalar el cliente de PostgreSQL**

                    ```bash
                    dnf install postgresql<version>
                    ```

        ```bash
        BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
        ```

    1. **Actualizar BunkerWeb**:
        - Actualiza BunkerWeb a la última versión.

            1. **Detener los servicios**:
                ```bash
                sudo systemctl stop bunkerweb
                sudo systemctl stop bunkerweb-ui
                sudo systemctl stop bunkerweb-scheduler
                ```

            2. **Actualizar BunkerWeb**:

                === "Debian/Ubuntu"

                    Primero, si has mantenido previamente el paquete de BunkerWeb, desmárcalo:

                    Puedes imprimir una lista de paquetes mantenidos con `apt-mark showhold`

                    ```shell
                    sudo apt-mark unhold bunkerweb nginx
                    ```

                    Luego, puedes actualizar el paquete de BunkerWeb:

                    ```shell
                    sudo apt update && \
                    sudo apt install -y --allow-downgrades bunkerweb=1.6.7~rc1
                    ```

                    Para evitar que el paquete de BunkerWeb se actualice al ejecutar `apt upgrade`, puedes usar el siguiente comando:

                    ```shell
                    sudo apt-mark hold bunkerweb nginx
                    ```

                    Más detalles en la [página de integración con Linux](integrations.md#__tabbed_1_1).

                === "Fedora/RedHat"

                    Primero, si has mantenido previamente el paquete de BunkerWeb, desmárcalo:

                    Puedes imprimir una lista de paquetes mantenidos con `dnf versionlock list`

                    ```shell
                    sudo dnf versionlock delete package bunkerweb && \
                    sudo dnf versionlock delete package nginx
                    ```

                    Luego, puedes actualizar el paquete de BunkerWeb:

                    ```shell
                    sudo dnf makecache && \
                    sudo dnf install -y --allowerasing bunkerweb-1.6.7~rc1
                    ```

                    Para evitar que el paquete de BunkerWeb se actualice al ejecutar `dnf upgrade`, puedes usar el siguiente comando:

                    ```shell
                    sudo dnf versionlock add bunkerweb && \
                    sudo dnf versionlock add nginx
                    ```

                    Más detalles en la [página de integración con Linux](integrations.md#__tabbed_1_3).

            3. **Iniciar los servicios**:
                    ```bash
                    sudo systemctl start bunkerweb
                    sudo systemctl start bunkerweb-ui
                    sudo systemctl start bunkerweb-scheduler
                    ```
                    O reinicia el sistema:
                    ```bash
                    sudo reboot
                    ```


    3. **Revisa los registros**: Revisa los registros del servicio del programador para asegurarte de que la migración fue exitosa.

        ```bash
        journalctl -u bunkerweb --no-pager
        ```

    4. **Verifica la base de datos**: Verifica que la actualización de la base de datos fue exitosa revisando los datos y las configuraciones en el nuevo contenedor de la base de datos.

### Reversión

!!! failure "En caso de problemas"

    Si encuentras algún problema durante la actualización, puedes volver a la versión anterior de la base de datos restaurando la copia de seguridad tomada en el [paso 1](#__tabbed_1_1).

    Obtén soporte y más información:

    - [Solicitar soporte profesional](https://panel.bunkerweb.io/?utm_source=doc&utm_campaign=self)
    - [Crear un issue en GitHub](https://github.com/bunkerity/bunkerweb/issues)
    - [Unirse al servidor de Discord de BunkerWeb](https://discord.bunkerity.com)

=== "Docker"

    1. **Extrae la copia de seguridad si está comprimida**.

        Primero extrae el archivo zip de la copia de seguridad:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Restaura la copia de seguridad**.

        === "SQLite"

            1. **Elimina el archivo de la base de datos existente.**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2. **Restaura la copia de seguridad.**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                ```

            3. **Corrige los permisos.**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4. **Detén la pila.**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1. **Restaura la copia de seguridad.**

                ```bash
                docker exec -e MYSQL_PWD=<your_password> -i <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                ```

            2. **Detén la pila.**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1. **Elimina la base de datos existente.**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2. **Vuelve a crear la base de datos.**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3. **Restaura la copia de seguridad.**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

            4. **Detén la pila.**

                ```bash
                docker compose down
                ```

    3. **Retrocede la versión de BunkerWeb**.

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<old_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<old_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<old_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<old_version>
                ...
        ```

    4. **Inicia los contenedores**.

        ```bash
        docker compose up -d
        ```

=== "Linux"

    4. **Extrae la copia de seguridad si está comprimida**.

        Primero extrae el archivo zip de la copia de seguridad:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    5. **Detén los servicios**.

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    6. **Restaura la copia de seguridad**.

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /path/to/backup/directory/backup.sql
            ```

        === "PostgreSQL"

            1. **Elimina la base de datos existente.**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2. **Vuelve a crear la base de datos.**

                ```bash
                createdb -U <username> <database_name>
                ```

            3. **Restaura la copia de seguridad.**

                ```bash
                psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

    7. **Inicia los servicios**.

        ```bash
        sudo systemctl start bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    8. **Retrocede la versión de BunkerWeb**.
        - Retrocede BunkerWeb a la versión anterior siguiendo los mismos pasos que al actualizar BunkerWeb en la [página de integración con Linux](integrations.md#linux)

## Actualización desde 1.5.X

### ¿Qué ha cambiado?

#### Programador

A diferencia de las versiones 1.5.X, el servicio del Programador **ya no utiliza el *proxy del socket de Docker* para obtener las instancias de BunkerWeb**. En su lugar, utiliza la nueva variable de entorno `BUNKERWEB_INSTANCES`.

!!! info "Sobre la variable de entorno `BUNKERWEB_INSTANCES`"

    Esta nueva variable es una lista de instancias de BunkerWeb separadas por espacios en este formato: `http://bunkerweb:5000 bunkerweb1:5000 bunkerweb2:5000 ...`. El programador utilizará entonces esta lista para obtener la configuración de las instancias y enviarles la configuración.

    * El prefijo `http://` es opcional.
    * El puerto es opcional y por defecto es el valor de la variable de entorno `API_HTTP_PORT`.
    * El valor predeterminado de la variable de entorno `BUNKERWEB_INSTANCES` es `127.0.0.1`.

En otras palabras, el nuevo sistema es totalmente agnóstico y genérico: el programador se encarga de gestionar una lista de instancias de BunkerWeb y no necesita preocuparse por el entorno.

!!! tip "Integraciones Autoconf/Kubernetes/Swarm"

    Si estás utilizando las integraciones `Autoconf`, `Kubernetes` o `Swarm`, puedes establecer la variable de entorno `BUNKERWEB_INSTANCES` en una cadena vacía (para que no intente enviar la configuración a la predeterminada que es `127.0.0.1`).

    **Las instancias serán obtenidas automáticamente por el controlador**. También puedes añadir instancias personalizadas a la lista que pueden no ser recogidas por el controlador.

Desde la versión `1.6`, el Programador también tiene un nuevo [sistema de comprobación de estado integrado](concepts.md), que comprobará la salud de las instancias. Si una instancia deja de estar saludable, el programador dejará de enviarle la configuración. Si la instancia vuelve a estar saludable, el programador comenzará a enviarle la configuración de nuevo.

#### Contenedor de BunkerWeb

Otro cambio importante es que las **configuraciones** que antes se declaraban en el contenedor de BunkerWeb **ahora se declaran en el programador**. Esto significa que tendrás que mover tus configuraciones del contenedor de BunkerWeb al contenedor del Programador.

Aunque las configuraciones se declaran ahora en el contenedor del Programador, **todavía necesitarás declarar las configuraciones obligatorias relacionadas con la API en el contenedor de BunkerWeb**, como la configuración `API_WHITELIST_IP`, que se utiliza para incluir en la lista blanca la dirección IP del Programador, para que pueda enviar la configuración a la instancia. Si usas `API_TOKEN`, también debes establecerlo en el contenedor de BunkerWeb (y reflejarlo en el Programador) para permitir las llamadas a la API autenticadas.

!!! warning "Configuraciones del contenedor de BunkerWeb"

    Cada configuración relacionada con la API que declares en el contenedor de BunkerWeb **tiene que ser reflejada en el contenedor del Programador** para que siga funcionando, ya que la configuración será sobrescrita por la configuración generada por el Programador.

#### Valores predeterminados y nuevas configuraciones

Hicimos nuestro mejor esfuerzo para no cambiar el valor predeterminado, pero hemos añadido muchas otras configuraciones. Se recomienda encarecidamente leer las secciones de [ajuste de seguridad](advanced.md#security-tuning) y [configuraciones](features.md) de la documentación.

#### Plantillas

Hemos añadido una nueva característica llamada **plantillas**. Las plantillas proporcionan un enfoque estructurado y estandarizado para definir configuraciones y configuraciones personalizadas, consulta la sección [conceptos/plantillas](concepts.md#templates) para obtener más información.

#### Espacios de nombres de Autoconf

Hemos añadido una característica de **espacio de nombres** a las integraciones de autoconfiguración. Los espacios de nombres te permiten agrupar tus instancias y aplicarles configuraciones solo a ellas. Consulta las siguientes secciones según tu Integración para obtener más información:

- [Autoconf/espacios de nombres](integrations.md#namespaces)
- [Kubernetes/espacios de nombres](integrations.md#namespaces_1)
- [Swarm/espacios de nombres](integrations.md#namespaces_2)

### Procedimiento

1.  **Hacer copia de seguridad de la base de datos**:
      - Antes de proceder con la actualización de la base de datos, asegúrate de realizar una copia de seguridad completa del estado actual de la base de datos.
      - Utiliza las herramientas adecuadas para hacer una copia de seguridad de toda la base de datos, incluyendo datos, esquemas y configuraciones.

    === "1.5.7 y posteriores"

        === "Docker"

            ```bash
            docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
            ```

            ```bash
            docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
            ```

        === "Linux"

            ??? warning "Información para usuarios de Red Hat Enterprise Linux (RHEL) 8.10"
                Si estás usando **RHEL 8.10** y planeas usar una **base de datos externa**, necesitarás instalar el paquete `mysql-community-client` para asegurar que el comando `mysqldump` esté disponible. Puedes instalar el paquete ejecutando los siguientes comandos:

                === "MySQL/MariaDB"

                    1. **Instalar el paquete de configuración del repositorio de MySQL**

                        ```bash
                        sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
                        ```

                    2. **Habilitar el repositorio de MySQL**

                        ```bash
                        sudo dnf config-manager --enable mysql80-community
                        ```

                    3. **Instalar el cliente de MySQL**

                        ```bash
                        sudo dnf install mysql-community-client
                        ```

                === "PostgreSQL"

                    4. **Instalar el paquete de configuración del repositorio de PostgreSQL**

                        ```bash
                        dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                        ```

                    5. **Instalar el cliente de PostgreSQL**

                        ```bash
                        dnf install postgresql<version>
                        ```

            ```bash
            BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
            ```

    === "1.5.6 y anteriores"

        === "SQLite"

            === "Docker"

                Primero necesitamos instalar el paquete `sqlite` en el contenedor.

                ```bash
                docker exec -u 0 -it <scheduler_container> apk add sqlite
                ```

                Luego, haz una copia de seguridad de la base de datos.

                ```bash
                docker exec -it <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /path/to/backup/directory/backup.sql
                ```

        === "MariaDB"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mariadb-dump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mariadb-dump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "MySQL"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mysqldump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mysqldump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "PostgreSQL"

            === "Docker"

                ```bash
                docker exec -it -e PGPASSWORD=<database_password> <database_container> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                PGPASSWORD=<database_password> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

2.  **Actualizar BunkerWeb**:
      - Actualiza BunkerWeb a la última versión.

        === "Docker"

            1.  **Actualiza el archivo Docker Compose**: Actualiza el archivo Docker Compose para usar la nueva versión de la imagen de BunkerWeb.
                ```yaml
                services:
                    bunkerweb:
                        image: bunkerity/bunkerweb:1.6.7-rc1
                        ...
                    bw-scheduler:
                        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
                        ...
                    bw-autoconf:
                        image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
                        ...
                    bw-ui:
                        image: bunkerity/bunkerweb-ui:1.6.7-rc1
                        ...
                ```

            2.  **Reinicia los contenedores**: Reinicia los contenedores para aplicar los cambios.
                ```bash
                docker compose down
                docker compose up -d
                ```

        === "Linux"

            3.  **Detén los servicios**:
                ```bash
                sudo systemctl stop bunkerweb
                sudo systemctl stop bunkerweb-ui
                sudo systemctl stop bunkerweb-scheduler
                ```

            4.  **Actualiza BunkerWeb**:

                === "Debian/Ubuntu"

                    Primero, si has mantenido previamente el paquete de BunkerWeb, desmárcalo:

                    Puedes imprimir una lista de paquetes mantenidos con `apt-mark showhold`

                    ```shell
                    sudo apt-mark unhold bunkerweb nginx
                    ```

                    Luego, puedes actualizar el paquete de BunkerWeb:

                    ```shell
                    sudo apt update && \
                    sudo apt install -y --allow-downgrades bunkerweb=1.6.7~rc1
                    ```

                    Para evitar que el paquete de BunkerWeb se actualice al ejecutar `apt upgrade`, puedes usar el siguiente comando:

                    ```shell
                    sudo apt-mark hold bunkerweb nginx
                    ```

                    Más detalles en la [página de integración con Linux](integrations.md#__tabbed_1_1).

                === "Fedora/RedHat"

                    Primero, si has mantenido previamente el paquete de BunkerWeb, desmárcalo:

                    Puedes imprimir una lista de paquetes mantenidos con `dnf versionlock list`

                    ```shell
                    sudo dnf versionlock delete package bunkerweb && \
                    sudo dnf versionlock delete package nginx
                    ```

                    Luego, puedes actualizar el paquete de BunkerWeb:

                    ```shell
                    sudo dnf makecache && \
                    sudo dnf install -y --allowerasing bunkerweb-1.6.7~rc1
                    ```

                    Para evitar que el paquete de BunkerWeb se actualice al ejecutar `dnf upgrade`, puedes usar el siguiente comando:

                    ```shell
                    sudo dnf versionlock add bunkerweb && \
                    sudo dnf versionlock add nginx
                    ```

                    Más detalles en la [página de integración con Linux](integrations.md#__tabbed_1_3).

            5.  **Inicia los servicios**:
                    ```bash
                    sudo systemctl start bunkerweb
                    sudo systemctl start bunkerweb-ui
                    sudo systemctl start bunkerweb-scheduler
                    ```
                    O reinicia el sistema:
                    ```bash
                    sudo reboot
                    ```


3.  **Revisa los registros**: Revisa los registros del servicio del programador para asegurarte de que la migración fue exitosa.

    === "Docker"

        ```bash
        docker compose logs <scheduler_container>
        ```

    === "Linux"

        ```bash
        journalctl -u bunkerweb --no-pager
        ```

4.  **Verifica la base de datos**: Verifica que la actualización de la base de datos fue exitosa revisando los datos y las configuraciones en el nuevo contenedor de la base de datos.

### Reversión

!!! failure "En caso de problemas"

    Si encuentras algún problema durante la actualización, puedes volver a la versión anterior de la base de datos restaurando la copia de seguridad tomada en el [paso 1](#__tabbed_1_1).

    Obtén soporte y más información:

    - [Solicitar soporte profesional](https://panel.bunkerweb.io/?utm_source=doc&utm_campaign=self)
    - [Crear un issue en GitHub](https://github.com/bunkerity/bunkerweb/issues)
    - [Unirse al servidor de Discord de BunkerWeb](https://discord.bunkerity.com)

=== "Docker"

    1. **Extrae la copia de seguridad si está comprimida**.

        Primero extrae el archivo zip de la copia de seguridad:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Restaura la copia de seguridad**.

        === "SQLite"

            1. **Elimina el archivo de la base de datos existente.**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2. **Restaura la copia de seguridad.**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                ```

            3. **Corrige los permisos.**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4. **Detén la pila.**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1. **Restaura la copia de seguridad.**

                ```bash
                docker exec -e MYSQL_PWD=<your_password> -i <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                ```

            2. **Detén la pila.**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1. **Elimina la base de datos existente.**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2. **Vuelve a crear la base de datos.**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3. **Restaura la copia de seguridad.**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

            4. **Detén la pila.**

                ```bash
                docker compose down
                ```

    3. **Retrocede la versión de BunkerWeb**.

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<old_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<old_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<old_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<old_version>
                ...
        ```

    4. **Inicia los contenedores**.

        ```bash
        docker compose up -d
        ```

=== "Linux"

    4. **Extrae la copia de seguridad si está comprimida**.

        Primero extrae el archivo zip de la copia de seguridad:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    5. **Detén los servicios**.

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    6. **Restaura la copia de seguridad**.

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /path/to/backup/directory/backup.sql
            ```

        === "PostgreSQL"

            1. **Elimina la base de datos existente.**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2. **Vuelve a crear la base de datos.**

                ```bash
                createdb -U <username> <database_name>
                ```

            3. **Restaura la copia de seguridad.**

                ```bash
                psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

    7. **Inicia los servicios**.

        ```bash
        sudo systemctl start bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    8. **Retrocede la versión de BunkerWeb**.
        - Retrocede BunkerWeb a la versión anterior siguiendo los mismos pasos que al actualizar BunkerWeb en la [página de integración con Linux](integrations.md#linux)
