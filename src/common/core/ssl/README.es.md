El complemento SSL proporciona capacidades robustas de cifrado SSL/TLS para sus sitios web protegidos por BunkerWeb. Este componente principal permite conexiones HTTPS seguras al configurar y optimizar protocolos criptográficos, cifrados y ajustes de seguridad relacionados para proteger los datos en tránsito entre los clientes y sus servicios web.

**Cómo funciona:**

1.  Cuando un cliente inicia una conexión HTTPS a su sitio web, BunkerWeb gestiona el handshake SSL/TLS utilizando su configuración.
2.  El complemento impone protocolos de cifrado modernos y conjuntos de cifrado sólidos, al tiempo que deshabilita las opciones vulnerables conocidas.
3.  Los parámetros de sesión SSL optimizados mejoran el rendimiento de la conexión sin sacrificar la seguridad.
4.  La presentación de certificados se configura de acuerdo con las mejores prácticas para garantizar la compatibilidad y la seguridad.

!!! success "Beneficios de Seguridad" - **Protección de Datos:** Cifra los datos en tránsito, previniendo la interceptación y los ataques de intermediario (man-in-the-middle). - **Autenticación:** Verifica la identidad de su servidor a los clientes. - **Integridad:** Asegura que los datos no han sido manipulados durante la transmisión. - **Estándares Modernos:** Configurado para cumplir con las mejores prácticas y los estándares de seguridad de la industria.

### Cómo usar

Siga estos pasos para configurar y usar la función SSL:

1.  **Configure los protocolos:** Elija qué versiones de protocolo SSL/TLS admitir utilizando el ajuste `SSL_PROTOCOLS`.
2.  **Seleccione los conjuntos de cifrado:** Especifique la fuerza del cifrado utilizando el ajuste `SSL_CIPHERS_LEVEL` o proporcione cifrados personalizados con `SSL_CIPHERS_CUSTOM`.
3.  **Configure la redirección de HTTP a HTTPS:** Configure la redirección automática utilizando los ajustes `AUTO_REDIRECT_HTTP_TO_HTTPS` o `REDIRECT_HTTP_TO_HTTPS`.

### Ajustes de Configuración

| Ajuste                        | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                         |
| ----------------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_HTTP_TO_HTTPS`      | `no`              | multisite | no       | **Redirigir HTTP a HTTPS:** Cuando se establece en `yes`, todas las solicitudes HTTP se redirigen a HTTPS.                                          |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` | `yes`             | multisite | no       | **Redirección Automática de HTTP a HTTPS:** Cuando se establece en `yes`, redirige automáticamente de HTTP a HTTPS si se detecta HTTPS.             |
| `SSL_PROTOCOLS`               | `TLSv1.2 TLSv1.3` | multisite | no       | **Protocolos SSL:** Lista de protocolos SSL/TLS a admitir, separados por espacios.                                                                  |
| `SSL_CIPHERS_LEVEL`           | `modern`          | multisite | no       | **Nivel de Cifrados SSL:** Nivel de seguridad preestablecido para los conjuntos de cifrado (`modern`, `intermediate` o `old`).                      |
| `SSL_CIPHERS_CUSTOM`          |                   | multisite | no       | **Cifrados SSL Personalizados:** Lista de conjuntos de cifrado separados por dos puntos para usar en las conexiones SSL/TLS (sobrescribe el nivel). |

!!! tip "Pruebas de SSL Labs"
Después de configurar sus ajustes de SSL, utilice la [Prueba de Servidor de SSL Labs de Qualys](https://www.ssllabs.com/ssltest/) para verificar su configuración y buscar posibles problemas de seguridad. Una configuración de SSL adecuada de BunkerWeb debería obtener una calificación A+.

!!! warning "Selección de Protocolo"
El soporte para protocolos más antiguos como SSLv3, TLSv1.0 y TLSv1.1 está deshabilitado intencionadamente por defecto debido a vulnerabilidades conocidas. Solo habilite estos protocolos si es absolutamente necesario para admitir clientes heredados y comprende las implicaciones de seguridad de hacerlo.

### Configuraciones de Ejemplo

=== "Seguridad Moderna (Predeterminada)"

    La configuración predeterminada que proporciona una seguridad sólida mientras mantiene la compatibilidad con los navegadores modernos:

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Máxima Seguridad"

    Configuración enfocada en la máxima seguridad, potencialmente con compatibilidad reducida para clientes más antiguos:

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

=== "Compatibilidad Heredada"

    Configuración con mayor compatibilidad para clientes más antiguos (úsela solo si es necesario):

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "old"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Cifrados Personalizados"

    Configuración que utiliza una especificación de cifrado personalizada:

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_CUSTOM: "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    ```
