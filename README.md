# control-cli

CLI de CONTROL para coordinar agentes, misiones, inboxes y skills dentro de un repositorio.

## Windows

En Windows, no uses `control` como comando principal porque colisiona con `control.exe` del sistema.
La invocacion estable del proyecto es:

```powershell
controlhq --help
```

Si necesitas ejecutar el modulo directamente desde el codigo fuente:

```powershell
$env:PYTHONPATH='src'
.\venv\Scripts\python.exe -m control.cli --help
```

## Flujo operativo

- `dispatch`: crea briefings de misión y notifica el inbox del agente.
- `message`: envia mensajes informativos al inbox.
- `inbox-pending`: lista entradas pendientes.
- `inbox-ack`: marca una entrada como leida.
- `inbox-archive`: mueve una entrada al historial.
- `mission-close`: cierra una mision y sincroniza briefing e inbox.
- `run-skill`: ejecuta una skill local de `.control/skills`.

## Estructura relevante

- `.control/briefings`: misiones formales.
- `.control/inboxes`: bandeja operativa por agente.
- `.control/dossiers`: instrucciones y contexto de cada agente.
- `.control/skills`: automatizaciones repetibles.

## Desarrollo local

```powershell
.\venv\Scripts\python.exe -m pip install -e .
controlhq --help
```
