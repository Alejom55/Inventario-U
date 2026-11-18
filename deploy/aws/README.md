# Práctica temporal de Inventario-U en AWS

Ejecutar `python3 deploy/aws/launch.py plan` desde AWS CloudShell en Ohio.
El plan consulta el precio vigente de una única t3.small Linux, valida el SHA
inmutable y reserva margen dentro de USD 1 para una ventana de dos horas.
`apply` vuelve a comprobar precio, cuenta, revisión y red antes de crear recursos.
Los resultados y la clave SSH se guardan en `deploy/aws/runtime/`, fuera de Git.

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
no un tope monetario nativo: el precio y el consumo se deben verificar en Billing.

Render queda separado. La evidencia anterior continúa identificada como Render;
este despliegue no acredita automáticamente las rondas ni la integración del grupo.
