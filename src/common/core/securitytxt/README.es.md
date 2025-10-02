El complemento Security.txt implementa el estándar [Security.txt](https://securitytxt.org/) ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116)) para su sitio web. Esta función ayuda a los investigadores de seguridad a acceder a sus políticas de seguridad y proporciona una forma estandarizada para que informen sobre las vulnerabilidades de seguridad que descubran en sus sistemas.

**Cómo funciona:**

1.  Cuando está habilitado, BunkerWeb crea un archivo `/.well-known/security.txt` en la raíz de su sitio web.
2.  Este archivo contiene información sobre sus políticas de seguridad, contactos y otros detalles relevantes.
3.  Los investigadores de seguridad y las herramientas automatizadas pueden encontrar fácilmente este archivo en la ubicación estándar.
4.  El contenido se configura mediante ajustes simples que le permiten especificar información de contacto, claves de cifrado, políticas y agradecimientos.
5.  BunkerWeb formatea automáticamente el archivo de acuerdo con la RFC 9116.

### Cómo usar

Siga estos pasos para configurar y usar la función Security.txt:

1.  **Habilite la función:** Establezca el ajuste `USE_SECURITYTXT` en `yes` para habilitar el archivo security.txt.
2.  **Configure la información de contacto:** Especifique al menos un método de contacto utilizando el ajuste `SECURITYTXT_CONTACT`.
3.  **Establezca información adicional:** Configure campos opcionales como la fecha de vencimiento, el cifrado, los agradecimientos y las URL de las políticas.
4.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, BunkerWeb creará y servirá automáticamente el archivo security.txt en la ubicación estándar.

### Ajustes de Configuración

| Ajuste                         | Valor por defecto           | Contexto  | Múltiple | Descripción                                                                                                                        |
| ------------------------------ | --------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_SECURITYTXT`              | `no`                        | multisite | no       | **Habilitar Security.txt:** Establezca en `yes` para habilitar el archivo security.txt.                                            |
| `SECURITYTXT_URI`              | `/.well-known/security.txt` | multisite | no       | **URI de Security.txt:** Indica la URI donde estará accesible el archivo security.txt.                                             |
| `SECURITYTXT_CONTACT`          |                             | multisite | sí       | **Información de contacto:** Cómo pueden contactarlo los investigadores de seguridad (p. ej., `mailto:security@example.com`).      |
| `SECURITYTXT_EXPIRES`          |                             | multisite | no       | **Fecha de vencimiento:** Cuándo debe considerarse que este archivo security.txt ha expirado (formato ISO 8601).                   |
| `SECURITYTXT_ENCRYPTION`       |                             | multisite | sí       | **Cifrado:** URL que apunta a las claves de cifrado que se utilizarán para la comunicación segura.                                 |
| `SECURITYTXT_ACKNOWLEDGEMENTS` |                             | multisite | sí       | **Agradecimientos:** URL donde se reconoce a los investigadores de seguridad por sus informes.                                     |
| `SECURITYTXT_POLICY`           |                             | multisite | sí       | **Política de seguridad:** URL que apunta a la política de seguridad que describe cómo informar vulnerabilidades.                  |
| `SECURITYTXT_HIRING`           |                             | multisite | sí       | **Empleos de seguridad:** URL que apunta a las ofertas de trabajo relacionadas con la seguridad.                                   |
| `SECURITYTXT_CANONICAL`        |                             | multisite | sí       | **URL canónica:** La(s) URI(s) canónica(s) para este archivo security.txt.                                                         |
| `SECURITYTXT_PREFERRED_LANG`   | `en`                        | multisite | no       | **Idioma(s) preferido(s):** El(los) idioma(s) utilizado(s) en las comunicaciones. Especificado como un código de idioma ISO 639-1. |
| `SECURITYTXT_CSAF`             |                             | multisite | sí       | **CSAF:** Enlace al `provider-metadata.json` de su proveedor de Common Security Advisory Framework.                                |

!!! warning "Se requiere fecha de vencimiento"
Según la RFC 9116, el campo `Expires` es obligatorio. Si no proporciona un valor para `SECURITYTXT_EXPIRES`, BunkerWeb establece automáticamente la fecha de vencimiento en un año a partir de la fecha actual.

!!! info "La información de contacto es esencial"
El campo `Contact` es la parte más importante del archivo security.txt. Debe proporcionar al menos una forma para que los investigadores de seguridad se pongan en contacto con usted. Puede ser una dirección de correo electrónico, un formulario web, un número de teléfono o cualquier otro método que funcione para su organización.

!!! warning "Las URL deben usar HTTPS"
Según la RFC 9116, todas las URL del archivo security.txt (excepto los enlaces `mailto:` y `tel:`) DEBEN usar HTTPS. BunkerWeb convertirá automáticamente las URL que no sean HTTPS a HTTPS para garantizar el cumplimiento de la norma.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración mínima con solo información de contacto:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    ```

=== "Configuración Completa"

    Una configuración más completa con todos los campos:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "https://example.com/security-contact-form"
    SECURITYTXT_EXPIRES: "2023-12-31T23:59:59+00:00"
    SECURITYTXT_ENCRYPTION: "https://example.com/pgp-key.txt"
    SECURITYTXT_ACKNOWLEDGEMENTS: "https://example.com/hall-of-fame"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_HIRING: "https://example.com/jobs/security"
    SECURITYTXT_CANONICAL: "https://example.com/.well-known/security.txt"
    SECURITYTXT_PREFERRED_LANG: "en"
    SECURITYTXT_CSAF: "https://example.com/provider-metadata.json"
    ```

=== "Configuración de Múltiples Contactos"

    Configuración con múltiples métodos de contacto:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "tel:+1-201-555-0123"
    SECURITYTXT_CONTACT_3: "https://example.com/security-form"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_EXPIRES: "2024-06-30T23:59:59+00:00"
    ```
