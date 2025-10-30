El complemento de Certificado Autofirmado genera y gestiona automáticamente certificados SSL/TLS directamente dentro de BunkerWeb, lo que permite conexiones HTTPS seguras sin necesidad de una autoridad de certificación externa. Esta función es particularmente útil en entornos de desarrollo, redes internas o siempre que necesite implementar HTTPS rápidamente sin configurar certificados externos.

**Cómo funciona:**

1.  Cuando está habilitado, BunkerWeb genera automáticamente un certificado SSL/TLS autofirmado para sus dominios configurados.
2.  El certificado incluye todos los nombres de servidor definidos en su configuración, lo que garantiza una validación SSL adecuada para cada dominio.
3.  Los certificados se almacenan de forma segura y se utilizan para cifrar todo el tráfico HTTPS a sus sitios web.
4.  El certificado se renueva automáticamente antes de su vencimiento, lo que garantiza la disponibilidad continua de HTTPS.

!!! warning "Advertencias de Seguridad del Navegador"
    Los navegadores mostrarán advertencias de seguridad cuando los usuarios visiten sitios que utilizan certificados autofirmados, ya que estos certificados no están validados por una autoridad de certificación de confianza. Para entornos de producción, considere usar [Let's Encrypt](#lets-encrypt) en su lugar.

### Cómo usar

Siga estos pasos para configurar y usar la función de Certificado Autofirmado:

1.  **Habilite la función:** Establezca el ajuste `GENERATE_SELF_SIGNED_SSL` en `yes` para habilitar la generación de certificados autofirmados.
2.  **Elija el algoritmo criptográfico:** Seleccione su algoritmo preferido utilizando el ajuste `SELF_SIGNED_SSL_ALGORITHM`.
3.  **Configure el período de validez:** Opcionalmente, establezca cuánto tiempo debe ser válido el certificado utilizando el ajuste `SELF_SIGNED_SSL_EXPIRY`.
4.  **Establezca el sujeto del certificado:** Configure el sujeto del certificado utilizando el ajuste `SELF_SIGNED_SSL_SUBJ`.
5.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, los certificados se generan y aplican automáticamente a sus dominios.

!!! tip "Configuración en Modo Stream"
    Para el modo stream, configure el ajuste `LISTEN_STREAM_PORT_SSL` para especificar el puerto de escucha SSL/TLS. Este paso es esencial para el correcto funcionamiento en modo stream.

### Ajustes de Configuración

| Ajuste                      | Valor por defecto      | Contexto  | Múltiple | Descripción                                                                                                                                      |
| --------------------------- | ---------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GENERATE_SELF_SIGNED_SSL`  | `no`                   | multisite | no       | **Habilitar autofirmado:** Establezca en `yes` para habilitar la generación automática de certificados autofirmados.                             |
| `SELF_SIGNED_SSL_ALGORITHM` | `ec-prime256v1`        | multisite | no       | **Algoritmo del certificado:** Algoritmo utilizado para la generación de certificados: `ec-prime256v1`, `ec-secp384r1`, `rsa-2048` o `rsa-4096`. |
| `SELF_SIGNED_SSL_EXPIRY`    | `365`                  | multisite | no       | **Validez del certificado:** Número de días que el certificado autofirmado debe ser válido (predeterminado: 1 año).                              |
| `SELF_SIGNED_SSL_SUBJ`      | `/CN=www.example.com/` | multisite | no       | **Sujeto del certificado:** Campo de sujeto para el certificado que identifica el dominio.                                                       |

!!! tip "Entornos de Desarrollo"
    Los certificados autofirmados son ideales para entornos de desarrollo y prueba donde se necesita HTTPS pero no se requieren certificados de confianza para los navegadores públicos.

!!! info "Información del Certificado"
    Los certificados autofirmados generados utilizan el algoritmo especificado (por defecto, criptografía de curva elíptica con la curva prime256v1) e incluyen el sujeto configurado, lo que garantiza la funcionalidad adecuada para sus dominios.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple que utiliza certificados autofirmados con los ajustes predeterminados:

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=mysite.local/"
    ```

=== "Certificados de Corta Duración"

    Configuración con certificados que expiran con más frecuencia (útil para probar regularmente los procesos de renovación de certificados):

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "90"
    SELF_SIGNED_SSL_SUBJ: "/CN=dev.example.com/"
    ```

=== "Pruebas con Certificados RSA"

    Configuración para un entorno de prueba donde un dominio utiliza certificados RSA autofirmados:

    ```yaml
    SERVER_NAME: "test.example.com"
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "rsa-4096"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=test.example.com/"
    ```
