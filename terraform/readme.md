# Seguimiento 3: Terraform en Oracle Cloud

Infraestructura para la API v2 existente. Se conservan FastAPI, PostgreSQL,
las rutas V1/V2, Object Storage y las integraciones externas de la entrega 2.

## Recursos y alcance

| Servicio OCI | Archivo | Uso real |
| --- | --- | --- |
| Compute | `compute.tf` | Oracle Linux 9: API y PostgreSQL 16 con Docker |
| Networking / VCN | `network.tf` | Red, subred, salida a Internet y acceso restringido a API |
| Object Storage | `storage.tf` | JSON de `/api/v2/storage` en bucket privado |
| Vault | `vault.tf`, `database.tf` | Clave compartida y contraseña de PostgreSQL |

PostgreSQL es **autogestionado en Compute**, no OCI Database with PostgreSQL.
`database.tf` configura su secreto y `deploy/compose.oci.yml` instala la base.
Son cuatro servicios OCI diferentes, más la base de datos que utiliza la API.
No se cuentan dos contenedores o dos máquinas como dos servicios OCI distintos.
IAM y el compartimento dedicado limitan permisos; no se cuentan para alcanzar
los cuatro servicios. La interpretación académica final corresponde al profesor.

La VM usa 1 OCPU ARM, 6 GB RAM y 50 GB de disco; Vault es `DEFAULT`, con clave
`SOFTWARE`. No se crean balanceadores, NAT Gateway ni base administrada de pago.
La elegibilidad Always Free depende de **home region, cuotas globales y capacidad**.
Revisa también recursos en otros compartimentos. No cambies automáticamente de
shape por falta de capacidad. Si el titular autoriza una demo facturable,
`compute_shape = "VM.Standard.E5.Flex"` selecciona AMD y una imagen compatible;
mantiene 1 OCPU, 6 GB y 50 GB de disco. El pipeline debe recibir también
`OCI_COMPUTE_SHAPE=VM.Standard.E5.Flex` para no intentar volver a A1. E5 no es
Always Free: detener la instancia al terminar las pruebas y eliminar después
los recursos que ya no hagan falta; el almacenamiento puede seguir facturando.
Terraform plan no calcula costos. Los créditos
temporales de Free Trial no equivalen a gratuidad permanente.

## Requisitos

- Terraform 1.16.5, Git, Python 3.13 y uv. Bash para los scripts locales
  (Git Bash en Windows). Docker para validación local.
- Cuenta OCI con permisos para crear compartimento, VCN, VM, buckets, Vault,
  secretos, claves, dynamic group y políticas. IAM debe poder crearse en la
  tenancy; el usuario del pipeline necesita administrar
  `instance-agent-command-family` en el compartimento de despliegue.
- API key OCI registrada y archivo **fuera del repositorio**: `~/.oci/config`.
  Autenticarse en el navegador no configura este acceso.
- Commit disponible en el repositorio público `Alejom55/Inventario-U`.
  El servidor descarga un SHA exacto, no una rama mutable.

Ejemplo de configuración local (sin valores reales):

```ini
[DEFAULT]
user=ocid1.user.oc1..REPLACE
fingerprint=REPLACE
tenancy=ocid1.tenancy.oc1..REPLACE
region=sa-bogota-1
key_file=/ruta/fuera/del/repo/oci_api_key.pem
```

No subas PEM, `.env`, `.tfvars`, planes ni estados. Los estados contienen
secretos aunque Terraform los oculte con `sensitive`; el backend debe ser privado.
La aplicación recibe secretos desde Vault mediante Instance Principals y los
guarda en `/opt/inventario/runtime.env`, accesible solo por root.

## 1. Crear el bucket de estado una sola vez

Desde la raíz del repositorio, con Terraform autenticado:

```bash
terraform -chdir=terraform/bootstrap init
terraform -chdir=terraform/bootstrap plan -var='compartment_ocid=OCID_REAL' -out=bootstrap.tfplan
terraform -chdir=terraform/bootstrap apply bootstrap.tfplan
terraform -chdir=terraform/bootstrap output
```

Se crea `inventario-u-tfstate`, privado y versionado, en el compartimento padre.
Conserva el estado local de `terraform/bootstrap/` de forma segura. Este módulo
no depende del backend que está creando. Si el bucket ya existe, impórtalo o usa
su nombre en el backend; no intentes apropiarte de un bucket ajeno.

## 2. Configurar variables y backend

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
cp terraform/backend.hcl.example terraform/backend.hcl
```

Edita ambos archivos: tenancy, compartimento padre, región y namespace real.
`api_allowed_cidr` debe ser tu IP pública con `/32` o red de demostración `/24`
o más restringida. La dirección `203.0.113.10/32` es un ejemplo que no funciona.
El código bloquea `0.0.0.0/0`. Solo se abre TCP 8000; no se abren 22 ni 5432.

Si tus compañeros ya acordaron una clave, define `TF_VAR_team_api_key` en el
entorno (24-128 caracteres alfanuméricos, guion o guion bajo). En caso contrario,
se genera una clave en Vault. No compartas su valor en commits, logs ni capturas.
Configura las dos URLs HTTPS cuando existan. Si quedan vacías, las funciones
locales operan pero `/api/v2/integracion` no puede consultar a los compañeros.

## 3. Validar sin crear recursos

```bash
uv sync --frozen --group dev
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
terraform -chdir=terraform test
```

`terraform test` usa proveedores simulados: valida forma, restricciones y
seguridad; no comprueba credenciales, capacidad ni políticas IAM reales.
El workflow `Validacion OCI` ejecuta además la suite con PostgreSQL aislado,
cobertura mínima de 85%, sintaxis Bash, build Docker y validación de Compose.

## 4. Desplegar desde tu equipo

```bash
terraform -chdir=terraform init -reconfigure -backend-config=backend.hcl
terraform -chdir=terraform plan
bash scripts/deploy_oci.sh
```

El script muestra y aplica el plan tras escribir `DESPLEGAR`, y después instala
el SHA actual mediante OCI Run Command. Debe estar previamente publicado con
`git push`. Cloud-init instala Docker y prepara el comando permitido a `ocarun`;
no se concede `NOPASSWD:ALL` ni se abre SSH.

El despliegue espera a Docker y comprueba: health, autenticación obligatoria,
consulta real a PostgreSQL, escritura/lectura/listado de un JSON en OCI. Ese JSON
pequeño queda como evidencia hasta eliminar la demo. No consulta APIs de terceros
sin IDs de prueba acordados.

La API se prueba por HTTP en el CIDR restringido. **Usa solo datos y claves de
demostración**: HTTP no cifra tráfico. Antes de uso real, configura dominio y
HTTPS; no se incluye un dominio inventado ni un certificado sin verificar.

## 5. Pipeline nuevo en GitHub

Workflow: `.github/workflows/despliegue-oci.yml`, ejecución manual.
El workflow debe estar en la rama predeterminada para aparecer en Actions;
si recibiste esta entrega en `codex/terraform-oci`, intégrala primero mediante PR.
No se modifican los pipelines anteriores de Railway/Render.

Crea el environment `oci-demo` y configura:

| Tipo | Nombre | Valor |
| --- | --- | --- |
| Secret | `OCI_TENANCY_OCID` | OCID tenancy |
| Secret | `OCI_USER_OCID` | Usuario de la API key |
| Secret | `OCI_FINGERPRINT` | Fingerprint de esa key |
| Secret | `OCI_PRIVATE_KEY` | PEM completo, con saltos de línea reales |
| Secret opcional | `OCI_PARENT_COMPARTMENT_OCID` | Usa tenancy si se omite |
| Secret opcional | `TEAM_API_KEY` | Clave compartida existente |
| Variable | `OCI_NAMESPACE` | Namespace mostrado por bootstrap |
| Variable | `OCI_API_ALLOWED_CIDR` | IP/red permitida |
| Variable opcional | `OCI_REGION` | Por defecto `sa-bogota-1` |
| Variable opcional | `OCI_COMPUTE_SHAPE` | Por defecto A1; E5 solo con presupuesto autorizado |
| Variable opcional | `OCI_STATE_BUCKET` | Por defecto `inventario-u-tfstate` |
| Variables opcionales | `DEPORTBACK_API_URL`, `FASTIFY_API_URL` | URLs HTTPS |

Usa primero `action=plan`, revisa recursos y cuotas. Después `action=deploy`.
El pipeline ejecuta pruebas, aplica Terraform y despliega el SHA del workflow.
Espera el resultado remoto: una VM creada no equivale a una API funcionando.
Protege el environment con revisores si tu plan de GitHub lo permite. El estado
remoto tiene bloqueo y el workflow no cancela una operación Terraform en curso.

## Datos, actualizaciones y recuperación

El nombre fijo del proyecto Compose mantiene `postgres_data` entre releases.
No se ejecuta `docker compose down -v` durante despliegue. La nueva imagen se
construye antes de reemplazar la API. Un fallo del smoke check marca el pipeline
como fallido; **no hay rollback automático**. Reejecuta el SHA anterior si es
compatible con el esquema, o corrige y vuelve a desplegar.

No regeneres el secreto PostgreSQL de una base ya inicializada sin rotar también
su contraseña dentro de PostgreSQL. Un volumen existente no cambia de contraseña
porque cambie `POSTGRES_PASSWORD` en Compose.

Las actualizaciones del catálogo de imágenes no reemplazan la VM automáticamente.
Cloud-init solo se ejecuta al crear la VM: cambios de bootstrap requieren una
migración explícita. Reemplazar o destruir la VM **borra PostgreSQL**; exporta los
datos antes. El bootstrap SDK queda fijado a la versión usada en `uv.lock`.

## 6. Eliminar al terminar la sustentación

Haz copia de los datos que quieras conservar. Luego:

```bash
bash scripts/destroy_oci.sh
```

El script muestra el plan de destrucción y exige `ELIMINAR`. Detiene la VM para
evitar nuevas escrituras, verifica que el bucket sea el de este compartimento,
lo vacía y aplica el plan. Desde GitHub: `action=destroy`, `confirmation=ELIMINAR`.
Ambas vías eliminan la base, el bucket y la infraestructura del proyecto.

Vault y sus claves/secretos pueden quedar en **eliminación programada**, según los
plazos mínimos de OCI; revisa la consola hasta completar el proceso. Si una
dependencia en borrado diferido impide eliminar el compartimento, reejecuta
`terraform destroy` cuando termine el plazo. No borres el estado antes.

El bucket de estado queda fuera de la demo para permitir recuperación. Al cerrar
definitivamente: guarda evidencia necesaria, elimina todas sus versiones/objetos,
retira deliberadamente `prevent_destroy` del módulo bootstrap y aplica su plan
de destrucción. No reutilices el script de limpieza de JSON para borrar estados.

## Sustentación

Muestra los cuatro servicios y el compartimento, el pipeline exitoso, `/docs`,
`/api/v2/health`, una operación de inventario y un JSON guardado/recuperado.
Explica `init`, `plan`, `apply`, estado remoto, dependencias, Instance Principals,
secreto PostgreSQL, volumen persistente y eliminación. Para integración entre
nubes necesitas URLs, IDs existentes y la clave acordada con tus compañeros.

La entrega también pide commits GitMoji y release nuevo. Tras validar el
despliegue real, publica un release con la etiqueta `v2.1.0` si está disponible y
describe el alcance comprobado, sin presentar pruebas simuladas como despliegue.

## Referencias

- [Always Free y límites globales](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Proveedor OCI](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/)
- [Backend OCI y bloqueo](https://developer.hashicorp.com/terraform/language/backend/oci)
- [Run Command e imágenes soportadas](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/runningcommands.htm)
- [Permisos Run Command](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/instances.htm#Required_IAM_Policy_for_Working_with_Instances)
