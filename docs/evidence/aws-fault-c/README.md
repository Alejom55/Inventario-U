# Procedencia

Archivos originales descargados del artefacto del run AWS `44209628616`, sin modificar sus mediciones ni sus decisiones históricas. El manifiesto registra las rutas originales y el SHA256 de cada archivo. Se comprobó que no contienen las claves de negocio, administración ni métricas conservadas en los archivos privados de la práctica, incluyendo la clave de negocio anterior a la rotación.

Los `*-toolkit.log` y journals son del ejecutor Chaos Toolkit; no se presentan como logs internos del servidor. Cada archivo de ronda contiene las 600 peticiones y sus trazas, incluidas las 300 muestras de la ventana de fallo. No hay aquí nueva ejecución, datos E1 ni capturas de Grafana.

La corrida histórica aprobó éxito R1 >=99 % y además un guardarraíl de latencia. El gate actualizado en `scripts/aws_evidence_gate.py` mantiene éxito >=99 % como única métrica numérica de decisión y deja la latencia como diagnóstico. Conserva las comprobaciones de perfil, procedencia y reversión. No se reescriben los archivos históricos para atribuirles esa modificación posterior.
