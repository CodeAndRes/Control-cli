# 📬 Inboxes de CONTROL

Los inboxes viven en `.control/inboxes` y son la bandeja operativa de cada agente.

## Reglas
- Cada agente debe leer su inbox al iniciar cualquier intervención.
- `MISSION` notifica trabajo accionable y referencia su briefing en `.control/briefings`.
- `MESSAGE` transmite contexto, instrucciones o avisos no accionables.
- Las entradas nuevas se insertan en `Pendientes`.

## Convención de nombres
- Un inbox por agente.
- El nombre del archivo usa el identificador operativo del agente en minúsculas.
- Ejemplos: `99.md`, `max86.md`.

## Formato
- Cabecera YAML con `agent`, `agent_id` y `read_required_on_start`.
- Sección `Pendientes` para nuevas entradas.
- Sección `Historial` reservada para futuras acciones de archivo.

## Automatización
- La emisión de misiones debe notificar al inbox del agente.
- Los envíos informativos deben usar `MESSAGE`.
- Las acciones repetibles de sincronización o bootstrap deben vivir como skills.