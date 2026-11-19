# Inventario-U v4.0.0 — Ingeniería del Caos y laboratorio E1

Esta versión fija el código y las evidencias de la entrega académica. El código
fuente se descarga desde el tag `v4.0.0`; publicar este release no modifica el
despliegue existente ni inicia recursos de nube. Las rutas de negocio v1/v2/v3
conservan sus nombres: la versión del paquete no cambia el track de Canary.

## DevOps: fallo (c), agotamiento de concurrencia en AWS

- Ejecución real: [Actions 44209628616](https://github.com/Alejom55/Inventario-U/actions/runs/44209628616).
- Perfil idéntico: 5 solicitudes/s durante 120 s; ventana evaluada de 60 s,
  entre t=30 y t=90; 300 muestras por ventana y timeout de 2 s.
- Métrica única de decisión: éxito en R1 >=99 %. La latencia es diagnóstica.
- Patrones: bulkhead y control de admisión; R0 admite seis tareas de fondo,
  mientras R1 admite cuatro y rechaza dos sin cola.

| Medición | Éxito | p95 |
|---|---:|---:|
| Estado estable | 100 % | 82.779 ms |
| R0 | 0 % | 2128.845 ms |
| R1 | 100 % | 82.624 ms |

R1 cumple el umbral. La recuperación es de 100 puntos porcentuales; no se
calcula una variación relativa del éxito desde cero. La reversión se verificó
en las tres mediciones. Son resultados de una API en una VM AWS anterior;
no demuestran por sí solos resiliencia extremo a extremo de las tres APIs.

- [Resultados](evidence/aws-cloud-results.json), [originales y manifiesto](evidence/aws-fault-c/).
- [Guía AWS](aws-guide.md), [Postman](aws-postman.json), [tablero importable](aws-dashboard.json).
- [Grafana DevOps](https://niftyivy3144.grafana.net/d/inventario-aws-evidence).
- Informe grupal de seis páginas: [release de deportBack v4.0.0](https://github.com/redundante3452/deportBack/releases/tag/v4.0.0).

## Ciber E1: evidencia separada

Laboratorio aislado en AWS autorizado por el propietario. No equivale a firmas
grupales ni a una aceptación de reglas de compromiso por otros integrantes.

- R0 acepta 10/10 escrituras adversarias; no observa detección durante 30.828 s.
  MTTD y MTTC no están observados: no se reportan como cero.
- R1 rechaza 10/10 escrituras adversarias: MTTD 5.484 s y MTTC 0.500 s.
  Las diez lecturas legítimas responden correctamente; estos resultados
  describen una muestra pequeña, no una garantía de producción.
- [Ficha y alcance](../security/entrega-e1.md), [evidencias](evidence/ciber-e1-aws/).
- [Gate de evidencia 44247381296](https://github.com/Alejom55/Inventario-U/actions/runs/44247381296):
  valida mediciones archivadas; este run no inyecta el experimento.
- [Grafana Ciber](https://niftyivy3144.grafana.net/d/inventario-security-e1-aws).

## Archivos adjuntos

- `Inventario-U-informe-analisis-Grafana.pdf`: análisis de DevOps.
- `Inventario-U-solo-capturas-Grafana.zip`: capturas de Grafana DevOps.
- `Inventario-U-Ciber-E1-AWS-resultados-reales.pdf`: resultados y análisis E1.
- `Inventario-U-Ciber-E1-AWS-capturas-Grafana.zip`: tres capturas E1.

Los adjuntos son documentos y capturas públicos; no incluyen credenciales ni
archivos de runtime. El archivo automático de código fuente de GitHub corresponde
al tag. Las credenciales y la operación de nube se gestionan por separado.

## Verificación reproducible sin carga cloud

```powershell
uv lock --check
uv run --frozen python -m scripts.aws_evidence_gate
uv run --frozen python -m security.verify_aws_evidence
uv run --frozen pytest tests/local_team/test_aws_evidence_gate.py tests/security --no-cov
```

Se conservan los experimentos y evidencias anteriores de Canary, OCI, Render y
operación local con su procedencia. No deben presentarse como rondas nuevas AWS.
La sustentación requiere además verificar en vivo el flujo, la inyección, los
patrones, el tablero y la recuperación en las nubes del equipo.
