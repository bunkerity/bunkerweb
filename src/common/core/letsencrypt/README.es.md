El complemento de Let's Encrypt simplifica la gestión de certificados SSL/TLS al automatizar la creación, renovación y configuración de certificados gratuitos de Let's Encrypt. Esta función permite conexiones HTTPS seguras para sus sitios web sin la complejidad de la gestión manual de certificados, reduciendo tanto los costos como la sobrecarga administrativa.

**Cómo funciona:**

1.  Cuando está habilitado, BunkerWeb detecta automáticamente los dominios configurados para su sitio web.
2.  BunkerWeb solicita certificados SSL/TLS gratuitos a la autoridad de certificación de Let's Encrypt.
3.  La propiedad del dominio se verifica mediante desafíos HTTP (demostrando que usted controla el sitio web) o desafíos DNS (demostrando que usted controla el DNS de su dominio).
4.  Los certificados se instalan y configuran automáticamente para sus dominios.
5.  BunkerWeb se encarga de las renovaciones de certificados en segundo plano antes de su vencimiento, garantizando la disponibilidad continua de HTTPS.
6.  Todo el proceso está totalmente automatizado, requiriendo una intervención mínima después de la configuración inicial.

!!! info "Requisitos previos"
    Para utilizar esta función, asegúrese de que los **registros A** de DNS adecuados estén configurados para cada dominio, apuntando a la(s) IP(s) pública(s) donde BunkerWeb es accesible. Sin una configuración de DNS correcta, el proceso de verificación del dominio fallará.

### Cómo usar

Siga estos pasos para configurar y usar la función de Let's Encrypt:

1.  **Habilite la función:** Establezca el ajuste `AUTO_LETS_ENCRYPT` en `yes` para habilitar la emisión y renovación automática de certificados.
2.  **Proporcione un correo electrónico de contacto (recomendado):** Ingrese su dirección de correo electrónico con el ajuste `EMAIL_LETS_ENCRYPT` para que Let's Encrypt pueda avisarle antes de que caduque un certificado. Si lo deja vacío, BunkerWeb se registrará sin dirección (opción de Certbot `--register-unsafely-without-email`) y no recibirá recordatorios ni correos de recuperación.
3.  **Elija el tipo de desafío:** Seleccione la verificación `http` o `dns` con el ajuste `LETS_ENCRYPT_CHALLENGE`.
4.  **Configure el proveedor de DNS:** Si utiliza desafíos DNS, especifique su proveedor de DNS y sus credenciales.
5.  **Seleccione el perfil del certificado:** Elija su perfil de certificado preferido utilizando el ajuste `LETS_ENCRYPT_PROFILE` (classic, tlsserver o shortlived).
6.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, los certificados se emiten, instalan y renuevan automáticamente según sea necesario.

!!! tip "Perfiles de Certificado"
    Let's Encrypt proporciona diferentes perfiles de certificado para diferentes casos de uso:

    - **classic**: Certificados de propósito general con una validez de 90 días (predeterminado)
    - **tlsserver**: Optimizado para la autenticación de servidores TLS con una validez de 90 días y una carga útil más pequeña
    - **shortlived**: Seguridad mejorada con una validez de 7 días para entornos automatizados
    - **custom**: Si su servidor ACME admite un perfil diferente, configúrelo usando `LETS_ENCRYPT_CUSTOM_PROFILE`.

!!! info "Disponibilidad del Perfil"
    Tenga en cuenta que los perfiles `tlsserver` y `shortlived` pueden no estar disponibles en todos los entornos o con todos los clientes ACME en este momento. El perfil `classic` tiene la compatibilidad más amplia y se recomienda para la mayoría de los usuarios. Si un perfil seleccionado no está disponible, el sistema volverá automáticamente al perfil `classic`.

### Ajustes de Configuración

| Ajuste                                      | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AUTO_LETS_ENCRYPT`                         | `no`              | multisite | no       | **Habilitar Let's Encrypt:** Establezca en `yes` para habilitar la emisión y renovación automática de certificados.                                                                                                                                                                                                                                                         |
| `LETS_ENCRYPT_PASSTHROUGH`                  | `no`              | multisite | no       | **Pasar a través de Let's Encrypt:** Establezca en `yes` para pasar las solicitudes de Let's Encrypt al servidor web. Esto es útil cuando BunkerWeb está detrás de otro proxy inverso que maneja SSL.                                                                                                                                                                       |
| `EMAIL_LETS_ENCRYPT`                        | `-`               | multisite | no       | **Correo electrónico de contacto:** Dirección utilizada para los avisos de caducidad de Let's Encrypt. Déjelo en blanco solo si acepta no recibir alertas ni correos de recuperación (Certbot se registra con `--register-unsafely-without-email`).                                                                                                                         |
| `LETS_ENCRYPT_CHALLENGE`                    | `http`            | multisite | no       | **Tipo de desafío:** Método utilizado para verificar la propiedad del dominio. Opciones: `http` o `dns`.                                                                                                                                                                                                                                                                    |
| `LETS_ENCRYPT_DNS_PROVIDER`                 |                   | multisite | no       | **Proveedor de DNS:** Cuando se utilizan desafíos DNS, el proveedor de DNS a utilizar (por ejemplo, cloudflare, route53, digitalocean).                                                                                                                                                                                                                                     |
| `LETS_ENCRYPT_DNS_PROPAGATION`              | `default`         | multisite | no       | **Propagación de DNS:** El tiempo de espera para la propagación de DNS en segundos. Si no se proporciona ningún valor, se utiliza el tiempo de propagación predeterminado del proveedor.                                                                                                                                                                                    |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`          |                   | multisite | yes      | **Elemento de credencial:** Elementos de configuración para la autenticación del proveedor de DNS (por ejemplo, `cloudflare_api_token 123456`). Los valores pueden ser texto sin formato, codificados en base64 o un objeto JSON.                                                                                                                                           |
| `LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64` | `yes`             | multisite | no       | **Decodificar credenciales DNS en Base64:** Decodifica automáticamente las credenciales del proveedor DNS codificadas en base64 cuando se establece en `yes`. Cuando está habilitado, los valores que coinciden con el formato base64 se decodifican antes de su uso (excepto para el proveedor `rfc2136`). Desactive si sus credenciales están intencionalmente en base64. |
| `USE_LETS_ENCRYPT_WILDCARD`                 | `no`              | multisite | no       | **Certificados comodín:** Cuando se establece en `yes`, crea certificados comodín para todos los dominios. Solo disponible con desafíos DNS.                                                                                                                                                                                                                                |
| `USE_LETS_ENCRYPT_STAGING`                  | `no`              | multisite | no       | **Usar entorno de prueba:** Cuando se establece en `yes`, utiliza el entorno de prueba de Let's Encrypt para realizar pruebas. El entorno de prueba tiene límites de velocidad más altos pero produce certificados que no son de confianza para los navegadores.                                                                                                            |
| `LETS_ENCRYPT_CLEAR_OLD_CERTS`              | `no`              | global    | no       | **Limpiar certificados antiguos:** Cuando se establece en `yes`, elimina los certificados antiguos que ya no son necesarios durante la renovación.                                                                                                                                                                                                                          |
| `LETS_ENCRYPT_CONCURRENT_REQUESTS`          | `no`              | global    | no       | **Solicitudes concurrentes:** Cuando se establece en `yes`, certbot-new emite solicitudes de certificados de forma concurrente. Úselo con precaución para evitar límites de tasa.                                                                                                                                                                                           |
| `LETS_ENCRYPT_PROFILE`                      | `classic`         | multisite | no       | **Perfil de certificado:** Seleccione el perfil de certificado a utilizar. Opciones: `classic` (propósito general), `tlsserver` (optimizado para servidores TLS) o `shortlived` (certificados de 7 días).                                                                                                                                                                   |
| `LETS_ENCRYPT_CUSTOM_PROFILE`               |                   | multisite | no       | **Perfil de certificado personalizado:** Ingrese un perfil de certificado personalizado si su servidor ACME admite perfiles no estándar. Esto anula `LETS_ENCRYPT_PROFILE` si está configurado.                                                                                                                                                                             |
| `LETS_ENCRYPT_MAX_RETRIES`                  | `3`               | multisite | no       | **Máximo de reintentos:** Número de veces que se reintentará la generación de certificados en caso de fallo. Establezca en `0` para deshabilitar los reintentos. Útil para manejar problemas de red temporales o límites de velocidad de la API.                                                                                                                            |

!!! info "Información y comportamiento"
    - El ajuste `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` es un ajuste múltiple y se puede utilizar para establecer varios elementos para el proveedor de DNS. Los elementos se guardarán como un archivo de caché, y Certbot leerá las credenciales de él.
    - Si no se proporciona ningún ajuste `LETS_ENCRYPT_DNS_PROPAGATION`, se utiliza el tiempo de propagación predeterminado del proveedor.
    - La automatización completa de Let's Encrypt utilizando el desafío `http` funciona en modo de flujo (stream) siempre que abra el puerto `80/tcp` desde el exterior. Utilice el ajuste `LISTEN_STREAM_PORT_SSL` para elegir su puerto de escucha SSL/TLS.
    - Si `LETS_ENCRYPT_PASSTHROUGH` se establece en `yes`, BunkerWeb no manejará las solicitudes de desafío ACME por sí mismo, sino que las pasará al servidor web de backend. Esto es útil en escenarios donde BunkerWeb actúa como un proxy inverso frente a otro servidor que está configurado para manejar los desafíos de Let's Encrypt.

!!! tip "Desafíos HTTP vs. DNS"
    **Los desafíos HTTP** son más fáciles de configurar y funcionan bien para la mayoría de los sitios web:

    - Requiere que su sitio web sea accesible públicamente en el puerto 80
    - Configurado automáticamente por BunkerWeb
    - No se puede utilizar para certificados comodín

    **Los desafíos DNS** ofrecen más flexibilidad y son necesarios para los certificados comodín:

    - Funciona incluso cuando su sitio web no es accesible públicamente
    - Requiere credenciales de la API del proveedor de DNS
    - Requerido para certificados comodín (por ejemplo, *.example.com)
    - Útil cuando el puerto 80 está bloqueado o no está disponible

!!! warning "Certificados comodín"
    Los certificados comodín solo están disponibles con desafíos DNS. Si desea utilizarlos, debe establecer el ajuste `USE_LETS_ENCRYPT_WILDCARD` en `yes` y configurar correctamente las credenciales de su proveedor de DNS.

!!! warning "Límites de velocidad"
    Let's Encrypt impone límites de velocidad en la emisión de certificados. Al probar las configuraciones, utilice el entorno de prueba estableciendo `USE_LETS_ENCRYPT_STAGING` en `yes` para evitar alcanzar los límites de velocidad de producción. Los certificados de prueba no son de confianza para los navegadores, pero son útiles para validar su configuración.

### Proveedores de DNS compatibles

El complemento de Let's Encrypt admite una amplia gama de proveedores de DNS para los desafíos de DNS. Cada proveedor requiere credenciales específicas que deben proporcionarse utilizando el ajuste `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`.

| Proveedor         | Descripción      | Ajustes obligatorios                                                                                         | Ajustes opcionales                                                                                                                                                                                                                                                                                   | Documentación                                                                                         |
| ----------------- | ---------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `bunny`           | bunny.net        | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/mwt/certbot-dns-bunny/blob/main/README.rst)                        |
| `cloudflare`      | Cloudflare       | ya sea `api_token`<br>o `email` y `api_key`                                                                  |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)                             |
| `desec`           | deSEC            | `token`                                                                                                      |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/desec-io/certbot-dns-desec/blob/main/README.md)                    |
| `digitalocean`    | DigitalOcean     | `token`                                                                                                      |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)                           |
| `domainoffensive` | Domain-Offensive | `api_token`                                                                                                  |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/domainoffensive/certbot-dns-domainoffensive/blob/master/README.md) |
| `domeneshop`      | Domeneshop       | `token`<br>`secret`                                                                                          |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/domeneshop/certbot-dns-domeneshop/blob/master/README.rst)          |
| `dnsimple`        | DNSimple         | `token`                                                                                                      |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)                               |
| `dnsmadeeasy`     | DNS Made Easy    | `api_key`<br>`secret_key`                                                                                    |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)                            |
| `duckdns`         | DuckDNS          | `duckdns_token`                                                                                              |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/infinityofspace/certbot_dns_duckdns/blob/main/Readme.md)           |
| `dynu`            | Dynu             | `auth_token`                                                                                                 |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/bikram990/certbot-dns-dynu/blob/main/README.md)                    |
| `gehirn`          | Gehirn DNS       | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                                 |
| `godaddy`         | GoDaddy          | `key`<br>`secret`                                                                                            | `ttl` (predeterminado: `600`)                                                                                                                                                                                                                                                                        | [Documentación](https://github.com/miigotu/certbot-dns-godaddy/blob/main/README.md)                   |
| `google`          | Google Cloud     | `project_id`<br>`private_key_id`<br>`private_key`<br>`client_email`<br>`client_id`<br>`client_x509_cert_url` | `type` (predeterminado: `service_account`)<br>`auth_uri` (predeterminado: `https://accounts.google.com/o/oauth2/auth`)<br>`token_uri` (predeterminado: `https://accounts.google.com/o/oauth2/token`)<br>`auth_provider_x509_cert_url` (predeterminado: `https://www.googleapis.com/oauth2/v1/certs`) | [Documentación](https://certbot-dns-google.readthedocs.io/en/stable/)                                 |
| `infomaniak`      | Infomaniak       | `token`                                                                                                      |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/infomaniak/certbot-dns-infomaniak/blob/main/README.rst)            |
| `ionos`           | IONOS            | `prefix`<br>`secret`                                                                                         | `endpoint` (predeterminado: `https://api.hosting.ionos.com`)                                                                                                                                                                                                                                         | [Documentación](https://github.com/helgeerbe/certbot-dns-ionos/blob/master/README.md)                 |
| `linode`          | Linode           | `key`                                                                                                        |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-linode.readthedocs.io/en/stable/)                                 |
| `luadns`          | LuaDNS           | `email`<br>`token`                                                                                           |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-luadns.readthedocs.io/en/stable/)                                 |
| `njalla`          | Njalla           | `token`                                                                                                      |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/chaptergy/certbot-dns-njalla/blob/main/README.md)                  |
| `nsone`           | NS1              | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-nsone.readthedocs.io/en/stable/)                                  |
| `ovh`             | OVH              | `application_key`<br>`application_secret`<br>`consumer_key`                                                  | `endpoint` (predeterminado: `ovh-eu`)                                                                                                                                                                                                                                                                | [Documentación](https://certbot-dns-ovh.readthedocs.io/en/stable/)                                    |
| `pdns`            | PowerDNS         | `endpoint`<br>`api_key`<br>`server_id` (default: `localhost`)<br>`disable_notify` (default: `false`)         |                                                                                                                                                                                                                                                                                                      | [Documentation](https://github.com/kaechele/certbot-dns-pdns/blob/main/README.md)                     |
| `rfc2136`         | RFC 2136         | `server`<br>`name`<br>`secret`                                                                               | `port` (predeterminado: `53`)<br>`algorithm` (predeterminado: `HMAC-SHA512`)<br>`sign_query` (predeterminado: `false`)                                                                                                                                                                               | [Documentación](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                                |
| `route53`         | Amazon Route 53  | `access_key_id`<br>`secret_access_key`                                                                       |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-route53.readthedocs.io/en/stable/)                                |
| `sakuracloud`     | Sakura Cloud     | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)                            |
| `scaleway`        | Scaleway         | `application_token`                                                                                          |                                                                                                                                                                                                                                                                                                      | [Documentación](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst)                 |
| `transip`         | TransIP          | `key_file`<br>`username`                                                                                     |                                                                                                                                                                                                                                                                                                      | [Documentación](https://certbot-dns-transip.readthedocs.io/en/stable/)                                |

### Configuraciones de Ejemplo

=== "Desafío HTTP Básico"

    Configuración simple que utiliza desafíos HTTP para un solo dominio:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ```

=== "DNS de Cloudflare con Comodín"

    Configuración para certificados comodín utilizando el DNS de Cloudflare:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "api_token SU_TOKEN_DE_API"
    USE_LETS_ENCRYPT_WILDCARD: "yes"
    ```

=== "Configuración de AWS Route53"

    Configuración que utiliza Amazon Route53 para los desafíos de DNS:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "route53"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "aws_access_key_id SU_CLAVE_DE_ACCESO"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "aws_secret_access_key SU_CLAVE_SECRETA"
    ```

=== "Pruebas con el Entorno de Prueba y Reintentos"

    Configuración para probar la configuración con el entorno de prueba y ajustes de reintento mejorados:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    USE_LETS_ENCRYPT_STAGING: "yes"
    LETS_ENCRYPT_MAX_RETRIES: "5"
    ```

=== "DigitalOcean con Tiempo de Propagación Personalizado"

    Configuración que utiliza el DNS de DigitalOcean con un tiempo de espera de propagación más largo:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "digitalocean"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "token SU_TOKEN_DE_API"
    LETS_ENCRYPT_DNS_PROPAGATION: "120"
    ```

=== "DNS de Google Cloud"

    Configuración que utiliza el DNS de Google Cloud con credenciales de cuenta de servicio:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "google"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "project_id su-id-de-proyecto"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "private_key_id su-id-de-clave-privada"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_3: "private_key su-clave-privada"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_4: "client_email su-correo-de-cuenta-de-servicio"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_5: "client_id su-id-de-cliente"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_6: "client_x509_cert_url su-url-de-certificado"
    ```
