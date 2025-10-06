El complemento de Caché del Cliente optimiza el rendimiento del sitio web al controlar cómo los navegadores almacenan en caché el contenido estático. Reduce el uso de ancho de banda, disminuye la carga del servidor y mejora los tiempos de carga de la página al indicar a los navegadores que almacenen y reutilicen activos estáticos —como imágenes, archivos CSS y JavaScript— localmente en lugar de solicitarlos en cada visita a la página.

**Cómo funciona:**

1.  Cuando está habilitado, BunkerWeb agrega encabezados `Cache-Control` a las respuestas para archivos estáticos.
2.  Estos encabezados le dicen a los navegadores por cuánto tiempo deben almacenar el contenido en caché localmente.
3.  Para los archivos con extensiones específicas (como imágenes, CSS, JavaScript), BunkerWeb aplica la política de almacenamiento en caché configurada.
4.  El soporte opcional de ETag proporciona un mecanismo de validación adicional para determinar si el contenido en caché todavía está actualizado.
5.  Cuando los visitantes regresan a su sitio, sus navegadores pueden usar los archivos almacenados en caché localmente en lugar de descargarlos nuevamente, lo que resulta en tiempos de carga de página más rápidos.

### Cómo usar

Siga estos pasos para configurar y usar la función de Caché del Cliente:

1.  **Habilite la función:** La función de Caché del Cliente está deshabilitada por defecto; establezca la configuración `USE_CLIENT_CACHE` en `yes` para habilitarla.
2.  **Configure las extensiones de archivo:** Especifique qué tipos de archivo deben almacenarse en caché utilizando la configuración `CLIENT_CACHE_EXTENSIONS`.
3.  **Establezca las directivas de control de caché:** Personalice cómo los clientes deben almacenar el contenido en caché utilizando la configuración `CLIENT_CACHE_CONTROL`.
4.  **Configure el soporte de ETag:** Decida si habilitar los ETags para validar la frescura de la caché con la configuración `CLIENT_CACHE_ETAG`.
5.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, los encabezados de caché se aplican automáticamente a las respuestas elegibles.

### Ajustes de Configuración

| Ajuste                    | Valor por defecto                                                         | Contexto  | Múltiple | Descripción                                                                                                                                     |
| ------------------------- | ------------------------------------------------------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CLIENT_CACHE`        | `no`                                                                      | multisite | no       | **Habilitar Caché del Cliente:** Establezca en `yes` para habilitar el almacenamiento en caché del lado del cliente de los archivos estáticos.  |
| `CLIENT_CACHE_EXTENSIONS` | `jpg\|jpeg\|png\|bmp\|ico\|svg\|tif\|css\|js\|otf\|ttf\|eot\|woff\|woff2` | global    | no       | **Extensiones Cacheadas:** Lista de extensiones de archivo (separadas por barras verticales) que deben ser almacenadas en caché por el cliente. |
| `CLIENT_CACHE_CONTROL`    | `public, max-age=15552000`                                                | multisite | no       | **Encabezado Cache-Control:** Valor para el encabezado HTTP Cache-Control para controlar el comportamiento del almacenamiento en caché.         |
| `CLIENT_CACHE_ETAG`       | `yes`                                                                     | multisite | no       | **Habilitar ETags:** Establezca en `yes` para enviar el encabezado HTTP ETag para los recursos estáticos.                                       |

!!! tip "Optimizando los Ajustes de Caché"
    Para contenido que se actualiza con frecuencia, considere usar valores de `max-age` más cortos. Para contenido que cambia raramente (como bibliotecas de JavaScript versionadas o logotipos), use tiempos de caché más largos. El valor por defecto de 15552000 segundos (180 días) es apropiado para la mayoría de los activos estáticos.

!!! info "Comportamiento del Navegador"
    Diferentes navegadores implementan el almacenamiento en caché de manera ligeramente diferente, pero todos los navegadores modernos respetan las directivas estándar de `Cache-Control`. Los ETags proporcionan un mecanismo de validación adicional que ayuda a los navegadores a determinar si el contenido en caché sigue siendo válido.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple que habilita el almacenamiento en caché para activos estáticos comunes:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|gif|css|js|svg|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=86400"  # 1 día
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Almacenamiento en Caché Agresivo"

    Configuración optimizada para un almacenamiento en caché máximo, adecuada para sitios con contenido estático que se actualiza con poca frecuencia:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2|pdf|xml|txt"
    CLIENT_CACHE_CONTROL: "public, max-age=31536000, immutable"  # 1 año
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Estrategia de Contenido Mixto"

    Para sitios con una mezcla de contenido actualizado con frecuencia y con poca frecuencia, considere usar el versionado de archivos en su aplicación y una configuración como esta:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=604800"  # 1 semana
    CLIENT_CACHE_ETAG: "yes"
    ```
