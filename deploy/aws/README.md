# Práctica temporal de Inventario-U en AWS

Ejecutar `python3 deploy/aws/launch.py plan` desde AWS CloudShell en Ohio.
El plan consulta el precio vigente de una única t3.small Linux, valida el SHA
inmutable y reserva margen dentro de USD 1 en créditos para una ventana de dos horas.
`apply` vuelve a comprobar precio, cuenta, revisión y red antes de crear recursos.
Los resultados y la clave SSH se guardan en `deploy/aws/runtime/`, fuera de Git.

Cuando el usuario autorice expresamente una ventana mayor, `plan --until-utc
2026-11-18T23:00:00Z` permite fijar ese vencimiento exacto (18:00 COL). El máximo
es 24 horas, con reserva calculada de hasta USD 0,95, dentro de USD 1 en créditos.
`apply` conserva el vencimiento revisado y consulta otra vez precio, cuenta y red;
no extiende el plazo desde la hora de ejecución. Sin opción explícita siguen
siendo dos horas. La vigencia del plan FREE debe cubrir toda la ventana.

La restricción del usuario es ahora **USD 0 de bolsillo**, solo créditos gratis.
Antes de cualquier creación, el script consulta `GetAccountPlanState` y exige
plan `FREE`, estado `ACTIVE`, al menos USD 1 en créditos y más de dos horas hasta
su vencimiento. También verifica `FreeTierEligible` para t3.small. Una cuenta
`PAID` se rechaza incluso si conserva créditos; el script nunca cambia el plan.
El consumo previsto de la práctica se mantiene por debajo de USD 1 en créditos.

La VM usa un disco gp3 cifrado de 8 GiB con eliminación al terminar, CPU en modo
standard sin cobros por créditos excedentes, una IPv4 pública y Docker Compose.
PostgreSQL y Prometheus no publican puertos. Solo HTTPS autenticado es accesible
para el equipo; HTTP permite emitir el certificado y redirige a HTTPS. SSH se
restringe a la IPv4 de esta sesión CloudShell. No crea NAT Gateway, RDS, balanceador
ni claves permanentes de la cuenta AWS.

El bootstrap instala primero un temporizador systemd con vencimiento UTC. Además,
AWS Scheduler termina esa instancia al vencer la ventana, con un rol cuyo único
permiso es `ec2:TerminateInstances` sobre su ARN exacto. El horario se elimina al
ejecutarse. Si no puede crear esta protección externa, el script solicita terminar
inmediatamente la VM. Scheduler tiene precisión de un minuto, no de segundos.

La terminación elimina la base sintética del disco. Exportar resultados y logs
antes del vencimiento. El hostname `IP.sslip.io` dura lo mismo que esa IPv4; no es
una dirección permanente para otro lanzamiento. No se reutilizan claves de Render.
Los roles, clave pública SSH y grupo de seguridad se deben limpiar al terminar;
no generan cargos por hora. El temporizador y Scheduler son protecciones de tiempo,
no un tope monetario por recurso: la protección de USD 0 de bolsillo corresponde
al plan de cuenta FREE, que el script exige antes de cualquier creación. No usar
este procedimiento para cuentas PAID. El precio y consumo de créditos siguen
siendo verificables en Billing.

## Validación y entrega

La ejecución [44209628616](https://github.com/Alejom55/Inventario-U/actions/runs/44209628616)
se inició desde el botón **Run workflow**, rama `feat/aws-chaos`. Sus tres rondas
se ejecutaron contra la misma aplicación e instancia EC2. El artefacto contiene
las 600 observaciones por ronda, journals de Chaos Toolkit y sus registros.
El objetivo durante el fallo pasó de 0% en R0 a 100% en R1; p95 de R1: 82,624 ms.

`uv run --frozen python -m scripts.verify_aws` verificó por HTTPS CRUD sintético,
GET/QUERY, trazas, autenticación y consultas reales de todos los paneles.
`python3 -m deploy.aws.verify_control`, ejecutado en CloudShell, contrastó el
plan FREE y las protecciones contra las API de EC2, IAM y Scheduler. Las pruebas
offline de resiliencia y configuración suman 178 aprobadas.

Guía pública: `docs/aws-guide.md`; colección: `docs/aws-postman.json`;
tablero importable: `docs/aws-dashboard.json`. Claves y entorno Postman privado:
`deploy/aws/runtime/`. Las claves AWS son distintas de las de Render.

Render queda separado. La evidencia anterior continúa identificada como Render;
este despliegue no acredita automáticamente las rondas ni la integración del grupo.
