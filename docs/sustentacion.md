# Guía de sustentación: Seguimiento 3

## Qué se entrega

El proyecto de la entrega 2 se despliega en Oracle Cloud con Terraform. La API
FastAPI conserva sus rutas V1/V2 y utiliza PostgreSQL para inventario y Object
Storage para documentos JSON. El pipeline nuevo crea la infraestructura y
despliega un commit exacto de Git.

## Arquitectura y servicios

| Servicio | Responsabilidad | Código |
| --- | --- | --- |
| Compute | VM Oracle Linux con API y PostgreSQL en Docker (demo E5 x86; A1 ARM por defecto) | `terraform/compute.tf` |
| Networking / VCN | Red, subred, rutas y acceso TCP 8000 limitado por IP | `terraform/network.tf` |
| Object Storage | Bucket privado de JSON usado por la API | `terraform/storage.tf` |
| Vault | Clave de cifrado y secretos de API y PostgreSQL | `terraform/vault.tf`, `terraform/database.tf` |

PostgreSQL 16 es autogestionado dentro de Compute. No se presenta como un
servicio de base de datos administrada de OCI. Se instala con
`deploy/compose.oci.yml` y persiste en un volumen Docker.

Un bucket privado adicional, creado por `terraform/bootstrap/`, conserva el
estado remoto de Terraform con versiones. No se cuenta como un quinto servicio.

## Antes de la defensa

La ejecución real pasó el 14 de octubre y la VM se detuvo después por presupuesto.
Consultar `evidencias/apagado.json`. La API no estará disponible mientras esté detenida.
La consola advierte que terminó Free Trial y que puede retirar recursos no gratuitos;
verificar elegibilidad y capacidad antes de intentar reactivar E5. No asumir que
la instancia se conservará. La reactivación supone nuevo consumo facturable.

Si la cuenta permite reactivarla y hay presupuesto, usar **Start** en Compute,
esperar RUNNING y comprobar health. Si la red de la universidad tiene otra IP,
actualizar el CIDR autorizado en Terraform y `OCI_API_ALLOWED_CIDR` antes de probar.
No abrir la API a todo Internet. Recuperar la clave de API desde Vault en privado;
no mostrarla en la grabación. Si no se puede iniciar, usar las evidencias guardadas
y preparar un redespliegue en una cuenta/región con capacidad y autorización.

## Recorrido para la demostración

1. Mostrar los archivos `.tf` y explicar qué recurso describe cada uno.
2. Mostrar el release de esta entrega y los commits GitMoji.
3. Abrir GitHub Actions y mostrar la ejecución del pipeline de infraestructura.
4. Mostrar en OCI la VM, VCN, bucket de JSON y Vault del compartimento de la demo.
5. Abrir `/docs` y `/api/v2/health` desde la red autorizada.
6. Crear un SKU de prueba, un almacén y un movimiento de entrada; consultar el
   inventario resultante. Las rutas funcionales requieren `X-Api-Key`.
7. Guardar un JSON con `POST /api/v2/storage`, recuperarlo por `trace_id` y mostrar
   el objeto en el bucket privado.
8. Explicar el procedimiento de eliminación. Ejecutarlo solamente al terminar
   la sustentación y después de guardar la evidencia y los datos necesarios.

No mostrar contraseñas, claves privadas, valores de Vault, estados ni planes
binarios en capturas. El reporte de ejecución debe distinguir validación local,
pruebas simuladas y comprobaciones contra la nube real.

## Preguntas que debes poder responder

**¿Qué aporta infraestructura como código?**
Describe recursos y relaciones en archivos versionados. Permite revisar cambios
antes de aplicarlos y repetir el despliegue con parámetros explícitos.

**¿Qué hacen `init`, `plan` y `apply`?**
`init` prepara proveedores y backend. `plan` compara configuración y estado para
proponer cambios. `apply` ejecuta el plan. Un plan exitoso no prueba que la API
esté funcionando: eso se verifica con las comprobaciones posteriores.

**¿Por qué separar archivos?**
Facilita identificar cada servicio y cumple el enunciado. Terraform carga los
`.tf` del directorio como un mismo módulo y resuelve dependencias por referencias;
el orden alfabético de los archivos no determina el orden de creación.

**¿Para qué sirve el estado?**
Relaciona los recursos declarados con sus identificadores reales. Puede contener
secretos, por lo que se guarda en un bucket privado y nunca en Git. Las versiones
ayudan a recuperar cambios accidentales; el bloqueo evita escrituras simultáneas.

**¿Cómo obtiene credenciales la VM?**
Usa Instance Principals. Un dynamic group identifica las instancias del
compartimento de la demo y una política limita acceso al bucket y a los dos
secretos. No se copia la clave privada del usuario a la VM.

**¿Qué hace el pipeline nuevo?**
Permite `plan`, `deploy` y `destroy`. Para desplegar, ejecuta controles, aplica
Terraform y usa OCI Run Command para instalar el SHA exacto del workflow.
Comprueba health, autenticación, consulta a PostgreSQL y escritura/lectura/listado
de Object Storage. No utiliza SSH abierto a Internet.

**¿Qué ocurre con los datos al actualizar?**
Docker Compose conserva el volumen de PostgreSQL entre releases. Destruir o
reemplazar la VM elimina sus datos; un volumen Docker no es una copia de seguridad.

**¿Cómo se elimina la infraestructura?**
`bash scripts/destroy_oci.sh` presenta el plan y exige `ELIMINAR`. Detiene la VM,
vacía el bucket de la demo y aplica la destrucción. También existe `destroy` en
el pipeline. Vault puede requerir esperar la eliminación programada. El bucket
de estado se conserva y se retira por separado cuando ya no haga falta recuperar.

**¿Qué límites tiene esta demo?**
Usa HTTP restringido por IP y datos de prueba. Un entorno de producción requiere
HTTPS y copias de seguridad, entre otros controles. Las integraciones con APIs de
compañeros necesitan sus URLs, identificadores y clave acordada. Una prueba con
proveedores simulados no valida capacidad disponible, IAM ni conectividad real.

## Entrega en UVirtual

Subir el proyecto y las evidencias de ejecución siguiendo el plazo de la actividad.
El ZIP no debe contener `.git`, `.venv`, `.terraform`, `.env`, claves PEM,
`terraform.tfvars`, `backend.hcl`, estados ni planes Terraform. Incluir el enlace
al repositorio y al release. La sustentación es individual: practicar el recorrido
y explicar cada decisión con el código abierto.
