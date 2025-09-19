El complemento de Escaneo Inverso protege de manera robusta contra los intentos de evasión de proxy al escanear los puertos de los clientes para detectar si están ejecutando servidores proxy u otros servicios de red. Esta función ayuda a identificar y bloquear posibles amenazas de clientes que puedan estar intentando ocultar su verdadera identidad u origen, mejorando así la postura de seguridad de su sitio web.

**Cómo funciona:**

1.  Cuando un cliente se conecta a su servidor, BunkerWeb intenta escanear puertos específicos en la dirección IP del cliente.
2.  El complemento comprueba si alguno de los puertos de proxy comunes (como 80, 443, 8080, etc.) está abierto en el lado del cliente.
3.  Si se detectan puertos abiertos, lo que indica que el cliente puede estar ejecutando un servidor proxy, se deniega la conexión.
4.  Esto agrega una capa adicional de seguridad contra herramientas automatizadas, bots y usuarios maliciosos que intentan enmascarar su identidad.

!!! success "Beneficios clave"

      1. **Seguridad Mejorada:** Identifica a los clientes que potencialmente ejecutan servidores proxy que podrían ser utilizados con fines maliciosos.
      2. **Detección de Proxy:** Ayuda a detectar y bloquear a los clientes que intentan ocultar su verdadera identidad.
      3. **Ajustes Configurables:** Personalice qué puertos escanear según sus requisitos de seguridad específicos.
      4. **Optimizado para el Rendimiento:** Escaneo inteligente con tiempos de espera configurables para minimizar el impacto en los usuarios legítimos.
      5. **Integración Perfecta:** Funciona de forma transparente con sus capas de seguridad existentes.

### Cómo usar

Siga estos pasos para configurar y usar la función de Escaneo Inverso:

1.  **Habilite la función:** Establezca el ajuste `USE_REVERSE_SCAN` en `yes` para habilitar el escaneo de puertos del cliente.
2.  **Configure los puertos a escanear:** Personalice el ajuste `REVERSE_SCAN_PORTS` para especificar qué puertos del cliente deben ser verificados.
3.  **Establezca el tiempo de espera del escaneo:** Ajuste el `REVERSE_SCAN_TIMEOUT` para equilibrar un escaneo exhaustivo con el rendimiento.
4.  **Supervise la actividad de escaneo:** Verifique los registros y la [interfaz de usuario web](web-ui.md) para revisar los resultados del escaneo y los posibles incidentes de seguridad.

### Ajustes de Configuración

| Ajuste                 | Valor por defecto          | Contexto  | Múltiple | Descripción                                                                                                  |
| ---------------------- | -------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| `USE_REVERSE_SCAN`     | `no`                       | multisite | no       | **Habilitar Escaneo Inverso:** Establezca en `yes` para habilitar el escaneo de los puertos de los clientes. |
| `REVERSE_SCAN_PORTS`   | `22 80 443 3128 8000 8080` | multisite | no       | **Puertos a Escanear:** Lista de puertos separados por espacios para verificar en el lado del cliente.       |
| `REVERSE_SCAN_TIMEOUT` | `500`                      | multisite | no       | **Tiempo de Espera del Escaneo:** Tiempo máximo en milisegundos permitido para escanear un puerto.           |

!!! warning "Consideraciones de Rendimiento"
Escanear múltiples puertos puede agregar latencia a las conexiones de los clientes. Use un valor de tiempo de espera apropiado y limite el número de puertos escaneados para mantener un buen rendimiento.

!!! info "Puertos de Proxy Comunes"
La configuración predeterminada incluye puertos comunes utilizados por los servidores proxy (80, 443, 8080, 3128) y SSH (22). Es posible que desee personalizar esta lista según su modelo de amenaza.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple para habilitar el escaneo de puertos del cliente:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "500"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Escaneo Exhaustivo"

    Una configuración más completa que verifica puertos adicionales:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1000"
    REVERSE_SCAN_PORTS: "22 80 443 3128 8080 8000 8888 1080 3333 8081"
    ```

=== "Configuración Optimizada para el Rendimiento"

    Configuración ajustada para un mejor rendimiento al verificar menos puertos con un tiempo de espera más bajo:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "250"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Configuración de Alta Seguridad"

    Configuración enfocada en la máxima seguridad con un escaneo extendido:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1500"
    REVERSE_SCAN_PORTS: "22 25 80 443 1080 3128 3333 4444 5555 6588 6666 7777 8000 8080 8081 8800 8888 9999"
    ```
