El complemento PHP proporciona una integración perfecta con PHP-FPM para BunkerWeb, lo que permite el procesamiento dinámico de PHP para sus sitios web. Esta característica es compatible tanto con instancias locales de PHP-FPM que se ejecutan en la misma máquina como con servidores remotos de PHP-FPM, lo que le brinda flexibilidad en la forma en que configura su entorno PHP.

**Cómo funciona:**

1.  Cuando un cliente solicita un archivo PHP de su sitio web, BunkerWeb enruta la solicitud a la instancia de PHP-FPM configurada.
2.  Para PHP-FPM local, BunkerWeb se comunica con el intérprete de PHP a través de un archivo de socket de Unix.
3.  Para PHP-FPM remoto, BunkerWeb reenvía las solicitudes al host y puerto especificados utilizando el protocolo FastCGI.
4.  PHP-FPM procesa el script y devuelve el contenido generado a BunkerWeb, que luego lo entrega al cliente.
5.  La reescritura de URL se configura automáticamente para admitir los marcos de trabajo y aplicaciones PHP comunes que utilizan "URL amigables".

### Cómo usar

Siga estos pasos para configurar y usar la función PHP:

1.  **Elija su configuración de PHP-FPM:** Decida si utilizará una instancia de PHP-FPM local o remota.
2.  **Configure la conexión:** Para PHP local, especifique la ruta del socket; para PHP remoto, proporcione el nombre de host y el puerto.
3.  **Establezca la raíz del documento:** Configure la carpeta raíz que contiene sus archivos PHP utilizando la configuración de ruta adecuada.
4.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, BunkerWeb enruta automáticamente las solicitudes de PHP a su instancia de PHP-FPM.

### Ajustes de Configuración

| Ajuste            | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                           |
| ----------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
| `REMOTE_PHP`      |                   | multisite | no       | **Host PHP Remoto:** Nombre de host de la instancia remota de PHP-FPM. Deje en blanco para usar PHP local.            |
| `REMOTE_PHP_PATH` |                   | multisite | no       | **Ruta Remota:** Carpeta raíz que contiene los archivos en la instancia remota de PHP-FPM.                            |
| `REMOTE_PHP_PORT` | `9000`            | multisite | no       | **Puerto Remoto:** Puerto de la instancia remota de PHP-FPM.                                                          |
| `LOCAL_PHP`       |                   | multisite | no       | **Socket PHP Local:** Ruta al archivo de socket de PHP-FPM. Deje en blanco para usar una instancia remota de PHP-FPM. |
| `LOCAL_PHP_PATH`  |                   | multisite | no       | **Ruta Local:** Carpeta raíz que contiene los archivos en la instancia local de PHP-FPM.                              |

!!! tip "PHP-FPM Local vs. Remoto"
    Elija la configuración que mejor se adapte a su infraestructura:

    -   **PHP-FPM local** ofrece un mejor rendimiento debido a la comunicación basada en sockets y es ideal cuando PHP se ejecuta en la misma máquina que BunkerWeb.
    -   **PHP-FPM remoto** proporciona más flexibilidad y escalabilidad al permitir que el procesamiento de PHP se realice en servidores separados.

!!! warning "Configuración de la Ruta"
    La `REMOTE_PHP_PATH` o `LOCAL_PHP_PATH` debe coincidir con la ruta real del sistema de archivos donde se almacenan sus archivos PHP; de lo contrario, se producirá un error de "Archivo no encontrado".

!!! info "Reescritura de URL"
    El complemento PHP configura automáticamente la reescritura de URL para admitir aplicaciones PHP modernas. Las solicitudes de archivos inexistentes se dirigirán a `index.php` con el URI de la solicitud original disponible como parámetro de consulta.

### Configuraciones de Ejemplo

=== "Configuración de PHP-FPM Local"

    Configuración para usar una instancia de PHP-FPM local:

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html"
    ```

=== "Configuración de PHP-FPM Remoto"

    Configuración para usar una instancia de PHP-FPM remota:

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9000"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "Configuración de Puerto Personalizado"

    Configuración para usar PHP-FPM en un puerto no estándar:

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9001"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "Configuración de WordPress"

    Configuración optimizada para WordPress:

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html/wordpress"
    ```
