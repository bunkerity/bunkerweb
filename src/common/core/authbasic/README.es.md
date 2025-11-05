El plugin Auth Basic proporciona autenticación básica HTTP para proteger su sitio web o recursos específicos. Esta función añade una capa extra de seguridad al requerir que los usuarios introduzcan un nombre de usuario y una contraseña antes de acceder al contenido protegido. Este tipo de autenticación es fácil de implementar y es ampliamente compatible con los navegadores.

**Cómo funciona:**

1.  Cuando un usuario intenta acceder a un área protegida de su sitio web, el servidor envía un desafío de autenticación.
2.  El navegador muestra un cuadro de diálogo de inicio de sesión pidiendo al usuario un nombre de usuario y una contraseña.
3.  El usuario introduce sus credenciales, que se envían al servidor.
4.  Si las credenciales son válidas, se le concede al usuario acceso al contenido solicitado.
5.  Si las credenciales no son válidas, se le muestra al usuario un mensaje de error con el código de estado 401 No autorizado.

### Cómo usar

Siga estos pasos para habilitar y configurar la autenticación básica:

1.  **Habilite la función:** Establezca el ajuste `USE_AUTH_BASIC` en `yes` en su configuración de BunkerWeb.
2.  **Elija el ámbito de protección:** Decida si proteger todo su sitio o solo URL específicas configurando el ajuste `AUTH_BASIC_LOCATION`.
3.  **Defina las credenciales:** Configure al menos un par de nombre de usuario y contraseña utilizando los ajustes `AUTH_BASIC_USER` y `AUTH_BASIC_PASSWORD`.
4.  **Personalice el mensaje:** Opcionalmente, cambie el `AUTH_BASIC_TEXT` para mostrar un mensaje personalizado en la solicitud de inicio de sesión.
5.  **Ajuste el coste del hash (opcional):** Modifique `AUTH_BASIC_ROUNDS` (1000-999999999) para equilibrar el rendimiento del inicio de sesión y la robustez del hashing de contraseñas.

### Ajustes de configuración

| Ajuste                | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                                                                       |
| --------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_AUTH_BASIC`      | `no`              | multisite | no       | **Habilitar autenticación básica:** Establezca en `yes` para habilitar la autenticación básica.                                                                                                   |
| `AUTH_BASIC_LOCATION` | `sitewide`        | multisite | no       | **Ámbito de protección:** Establezca en `sitewide` para proteger todo el sitio, o especifique una ruta de URL (p. ej., `/admin`) para proteger solo áreas específicas.                            |
| `AUTH_BASIC_USER`     | `changeme`        | multisite | yes      | **Nombre de usuario:** El nombre de usuario requerido para la autenticación. Puede definir múltiples pares de nombre de usuario/contraseña.                                                       |
| `AUTH_BASIC_PASSWORD` | `changeme`        | multisite | yes      | **Contraseña:** La contraseña requerida para la autenticación. Cada contraseña corresponde a un nombre de usuario.                                                                                |
| `AUTH_BASIC_ROUNDS`   | `656000`          | multisite | yes      | **Rondas de hash:** Número de rondas SHA-512 aplicadas al generar el archivo htpasswd (debe mantenerse entre 1000 y 999999999). Valores más bajos aceleran el acceso pero reducen la resistencia. |
| `AUTH_BASIC_TEXT`     | `Restricted area` | multisite | no       | **Texto de la solicitud:** El mensaje que se muestra en la solicitud de autenticación mostrada a los usuarios.                                                                                    |

!!! warning "Consideraciones de seguridad"
    La autenticación básica HTTP transmite las credenciales codificadas (no cifradas) en Base64. Aunque esto es aceptable cuando se utiliza sobre HTTPS, no debe considerarse seguro sobre HTTP plano. Habilite siempre SSL/TLS cuando utilice la autenticación básica.

!!! tip "Uso de múltiples credenciales"
    Puede configurar múltiples pares de nombre de usuario/contraseña para el acceso. Cada ajuste `AUTH_BASIC_USER` debe tener un ajuste `AUTH_BASIC_PASSWORD` correspondiente.

### Configuraciones de ejemplo

=== "Protección de todo el sitio"

    Para proteger todo su sitio web con un único conjunto de credenciales:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Protección de áreas específicas"

    Para proteger solo una ruta específica, como un panel de administración:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "/admin/"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Múltiples usuarios"

    Para configurar múltiples usuarios con diferentes credenciales:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_TEXT: "Staff Area"

    # Primer usuario
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "admin_password"

    # Segundo usuario
    AUTH_BASIC_USER_2: "editor"
    AUTH_BASIC_PASSWORD_2: "editor_password"

    # Tercer usuario
    AUTH_BASIC_USER_3: "viewer"
    AUTH_BASIC_PASSWORD_3: "viewer_password"
    ```
