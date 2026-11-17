# Práctica temporal en DigitalOcean

Autorización: infraestructura de hasta USD 1 y duración máxima de dos horas.
La cuenta está creada; la verificación del método de pago aún está pendiente.
No hay un Droplet desplegado ni un temporizador activo por el hecho de existir estos archivos.

## Control de coste y eliminación

DigitalOcean sigue cobrando un Droplet apagado. Esta práctica debe **eliminar**
su servidor desechable, después de descargar evidencias; no basta con detenerlo.
No crear backups, snapshots, volúmenes adicionales, balanceadores ni servicios administrados.

`guard.py` usa solamente la biblioteca estándar de Python. Su estado privado debe
contener el ID, nombre y etiqueta exclusivos del nuevo servidor, el `created_at`
real obtenido de DigitalOcean, la tarifa horaria verificada y el instante UTC de eliminación.
Se propone eliminar a los 110 minutos, dejando margen de reintentos dentro de dos horas.

El guard valida la identidad antes de borrar, no sigue redirecciones con credenciales
y solo termina satisfactoriamente cuando la API confirma que ese ID ya no existe.
El token se lee de un archivo privado ignorado por Git; nunca se imprime.
Antes del despliegue se deben instalar y verificar tanto el guard externo como
la ejecución programada dentro de la VM. Si no se puede garantizar su preparación,
eliminar inmediatamente el Droplet recién creado.

```powershell
uv run --frozen python -m pytest tests/digitalocean -q --no-cov
```

Estos tests no acceden a DigitalOcean, no crean recursos y no prueban todavía
una eliminación real en la nube. La activación y validación remota quedan pendientes.

El máximo autorizado se refiere a uso de infraestructura. El proveedor o banco
pueden exigir una verificación o retención independiente al registrar el método de pago.
No continuar con un depósito o cargo inicial fuera del límite sin que el usuario lo revise.

Referencias: [precios](https://www.digitalocean.com/pricing/droplets),
[eliminación de Droplets](https://docs.digitalocean.com/products/droplets/how-to/destroy/).
