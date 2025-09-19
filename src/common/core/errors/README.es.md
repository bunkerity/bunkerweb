El complemento de Errores proporciona un manejo de errores personalizable para su sitio web, permitiéndole configurar cómo aparecen las respuestas de error HTTP a los usuarios. Esta característica le ayuda a presentar páginas de error amigables y con su marca que mejoran la experiencia del usuario durante escenarios de error, en lugar de mostrar las páginas de error predeterminadas del servidor, que pueden parecer técnicas y confusas para los visitantes.

**Cómo funciona:**

1.  Cuando un cliente encuentra un error HTTP (por ejemplo, 400, 404 o 500), BunkerWeb intercepta la respuesta de error.
2.  En lugar de mostrar la página de error predeterminada, BunkerWeb muestra una página de error personalizada y diseñada profesionalmente.
3.  Las páginas de error son totalmente personalizables a través de su configuración, permitiéndole especificar páginas personalizadas para códigos de error específicos. **Los archivos de las páginas de error personalizadas deben colocarse en el directorio definido por el ajuste `ROOT_FOLDER` (consulte la documentación del complemento Varios).**
    - Por defecto, `ROOT_FOLDER` es `/var/www/html/{server_name}` (donde `{server_name}` se reemplaza por el nombre real del servidor).
    - En el modo multisitio, cada sitio puede tener su propio `ROOT_FOLDER`, por lo que las páginas de error personalizadas deben colocarse en el directorio correspondiente para cada sitio.
4.  Las páginas de error predeterminadas proporcionan explicaciones claras, ayudando a los usuarios a entender qué salió mal y qué pueden hacer a continuación.

### Cómo usar

Siga estos pasos para configurar y usar la función de Errores:

1.  **Defina las páginas de error personalizadas:** Especifique qué códigos de error HTTP deben usar páginas de error personalizadas utilizando el ajuste `ERRORS`. Los archivos de las páginas de error personalizadas deben estar ubicados en la carpeta especificada por el ajuste `ROOT_FOLDER` para el sitio. En el modo multisitio, esto significa que cada sitio/servidor puede tener su propia carpeta para las páginas de error personalizadas.
2.  **Configure sus páginas de error:** Para cada código de error, puede usar la página de error predeterminada de BunkerWeb o proporcionar su propia página HTML personalizada (colocada en el `ROOT_FOLDER` apropiado).
3.  **Establezca los códigos de error interceptados:** Seleccione qué códigos de error siempre deben ser manejados por BunkerWeb con el ajuste `INTERCEPTED_ERROR_CODES`.
4.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, el manejo de errores ocurre automáticamente para todos los códigos de error especificados.

### Ajustes de Configuración

| Ajuste                    | Valor por defecto                                 | Contexto  | Múltiple | Descripción                                                                                                                                                                  |
| ------------------------- | ------------------------------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ERRORS`                  |                                                   | multisite | no       | **Páginas de Error Personalizadas:** Asigne códigos de error específicos a archivos HTML personalizados usando el formato `CODIGO_DE_ERROR=/ruta/al/archivo.html`.           |
| `INTERCEPTED_ERROR_CODES` | `400 401 403 404 405 413 429 500 501 502 503 504` | multisite | no       | **Errores Interceptados:** Lista de códigos de error HTTP que BunkerWeb debe manejar con su página de error predeterminada cuando no se especifica una página personalizada. |

!!! tip "Diseño de la Página de Error"
Las páginas de error predeterminadas de BunkerWeb están diseñadas para ser informativas, amigables y de apariencia profesional. Incluyen:

    -   Descripciones claras del error
    -   Información sobre qué pudo haber causado el error
    -   Acciones sugeridas para que los usuarios resuelvan el problema
    -   Indicadores visuales que ayudan a los usuarios a comprender si el problema está del lado del cliente o del servidor

!!! info "Tipos de Error"
Los códigos de error se clasifican por tipo:

    -   **Errores 4xx (del lado del cliente):** Indican problemas con la solicitud del cliente, como intentar acceder a páginas inexistentes o carecer de la autenticación adecuada.
    -   **Errores 5xx (del lado del servidor):** Indican problemas con la capacidad del servidor para cumplir una solicitud válida, como errores internos del servidor o indisponibilidad temporal.

### Configuraciones de Ejemplo

=== "Manejo de Errores Predeterminado"

    Deje que BunkerWeb maneje los códigos de error comunes con sus páginas de error predeterminadas:

    ```yaml
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Páginas de Error Personalizadas"

    Use páginas de error personalizadas para códigos de error específicos:

    ```yaml
    ERRORS: "404=/custom/404.html 500=/custom/500.html"
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Manejo de Errores Selectivo"

    Solo maneje códigos de error específicos con BunkerWeb:

    ```yaml
    INTERCEPTED_ERROR_CODES: "404 500"
    ```
