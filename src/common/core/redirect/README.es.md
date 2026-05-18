El complemento de Redirección proporciona capacidades de redirección HTTP simples y eficientes para sus sitios web protegidos por BunkerWeb. Esta función le permite redirigir fácilmente a los visitantes de una URL a otra, admitiendo tanto redirecciones de dominio completo, redirecciones de ruta específicas como redirecciones que preservan la ruta.

**Cómo funciona:**

1.  Cuando un visitante accede a su sitio web, BunkerWeb verifica si hay una redirección configurada.
2.  Si está habilitado, BunkerWeb redirige al visitante a la URL de destino especificada.
3.  Puede configurar si desea preservar la ruta de la solicitud original (agregándola automáticamente a la URL de destino) o redirigir a la URL de destino exacta.
4.  El código de estado HTTP utilizado para la redirección se puede personalizar entre redirecciones permanentes (301) y temporales (302).
5.  Esta funcionalidad es ideal para migraciones de dominio, establecer dominios canónicos o redirigir URL obsoletas.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de Redirección:

1.  **Establezca la ruta de origen:** Configure la ruta desde la que se redirigirá utilizando el ajuste `REDIRECT_FROM` (por ejemplo, `/`, `/old-page`).
2.  **Establezca la URL de destino:** Configure la URL de destino a la que se redirigirá a los visitantes utilizando el ajuste `REDIRECT_TO`.
3.  **Elija el tipo de redirección:** Decida si desea preservar la ruta de la solicitud original con el ajuste `REDIRECT_TO_REQUEST_URI`.
4.  **Seleccione el código de estado:** Establezca el código de estado HTTP apropiado con el ajuste `REDIRECT_TO_STATUS_CODE` para indicar una redirección permanente o temporal.
5.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, todas las solicitudes al sitio se redirigirán automáticamente según su configuración.

### Ajustes de Configuración

| Ajuste                    | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                     |
| ------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_FROM`           | `/`               | multisite | yes      | **Ruta desde la que redirigir:** La ruta que se redirigirá.                                                                     |
| `REDIRECT_TO`             |                   | multisite | yes      | **URL de destino:** La URL de destino a la que se redirigirá a los visitantes. Deje en blanco para deshabilitar la redirección. |
| `REDIRECT_TO_REQUEST_URI` | `no`              | multisite | yes      | **Preservar ruta:** Cuando se establece en `yes`, agrega el URI de la solicitud original a la URL de destino.                   |
| `REDIRECT_TO_STATUS_CODE` | `301`             | multisite | yes      | **Código de estado HTTP:** El código de estado HTTP a utilizar. Opciones: `301`, `302`, `303`, `307` o `308`.                   |

!!! tip "Elegir el Código de Estado Correcto"
    - **`301` (Moved Permanently):** Redirección permanente, almacenada en caché por navegadores. Puede cambiar POST a GET. Ideal para migraciones de dominio.
    - **`302` (Found):** Redirección temporal. Puede cambiar POST a GET.
    - **`303` (See Other):** Siempre redirige usando el método GET. Útil después de envíos de formularios.
    - **`307` (Temporary Redirect):** Redirección temporal que preserva el método HTTP. Ideal para APIs.
    - **`308` (Permanent Redirect):** Redirección permanente que preserva el método HTTP. Para migraciones permanentes de API.

!!! info "Preservación de la Ruta"
    Cuando `REDIRECT_TO_REQUEST_URI` se establece en `yes`, BunkerWeb preserva la ruta de la solicitud original. Por ejemplo, si un usuario visita `https://dominio-antiguo.com/blog/post-1` y ha configurado una redirección a `https://dominio-nuevo.com`, será redirigido a `https://dominio-nuevo.com/blog/post-1`.

### Configuraciones de Ejemplo

=== "Redirección de Múltiples Rutas"

    Una configuración que redirige múltiples rutas a diferentes destinos:

    ```yaml
    # Redirigir /blog a un nuevo dominio de blog
    REDIRECT_FROM: "/blog/"
    REDIRECT_TO: "https://blog.example.com/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"

    # Redirigir /shop a otro dominio
    REDIRECT_FROM_2: "/shop/"
    REDIRECT_TO_2: "https://shop.example.com/"
    REDIRECT_TO_REQUEST_URI_2: "no"
    REDIRECT_TO_STATUS_CODE_2: "301"

    # Redirigir el resto del sitio
    REDIRECT_FROM_3: "/"
    REDIRECT_TO_3: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI_3: "no"
    REDIRECT_TO_STATUS_CODE_3: "301"
    ```

=== "Redirección de Dominio Simple"

    Una configuración que redirige a todos los visitantes a un nuevo dominio:

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Redirección con Preservación de Ruta"

    Una configuración que redirige a los visitantes a un nuevo dominio mientras preserva la ruta solicitada:

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Redirección Temporal"

    Una configuración para una redirección temporal a un sitio de mantenimiento:

    ```yaml
    REDIRECT_TO: "https://maintenance.example.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "302"
    ```

=== "Consolidación de Subdominios"

    Una configuración para redirigir un subdominio a una ruta específica en el dominio principal:

    ```yaml
    REDIRECT_TO: "https://example.com/support"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Migración de Endpoint de API"

    Una configuración para redirigir permanentemente un endpoint de API preservando el método HTTP:

    ```yaml
    REDIRECT_FROM: "/api/v1/"
    REDIRECT_TO: "https://api.example.com/v2/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "308"
    ```

=== "Redirección Post-Formulario"

    Una configuración para redirigir después del envío de un formulario usando el método GET:

    ```yaml
    REDIRECT_TO: "https://example.com/gracias"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "303"
    ```
