import typer
import os
import sys
import yaml
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
import subprocess  
import datetime

app = typer.Typer(help="🕵️ CONTROL: Cuartel General de Agentes (Agnóstico)")
console = Console()


def _next_mission_id(briefing_dir: Path) -> str:
    highest_id = 0

    for mission_path in briefing_dir.glob("mission_*.md"):
        try:
            mission_number = int(mission_path.stem.split("_")[1])
        except (IndexError, ValueError):
            continue

        highest_id = max(highest_id, mission_number)

    return f"{highest_id + 1:03d}"


def _agent_slug(agent: str) -> str:
    return agent.strip().lower().replace(" ", "_")


def _render_inbox(agent: str) -> str:
    agent_id = _agent_slug(agent)
    return f"""---
agent: {agent}
agent_id: {agent_id}
read_required_on_start: true
---

# 📬 Inbox: {agent}

## Reglas
- Leer este inbox al iniciar cualquier intervención.
- Las misiones accionables se desarrollan en `.control/briefings`.
- Este inbox centraliza notificaciones, contexto y referencias para el agente.

## Pendientes
<!-- CONTROL:INBOX:PENDING -->

## Historial
<!-- CONTROL:INBOX:HISTORY -->
"""


def _ensure_agent_inbox(agent: str) -> Path:
    inbox_dir = Path(".control/inboxes")
    inbox_dir.mkdir(parents=True, exist_ok=True)

    inbox_path = inbox_dir / f"{_agent_slug(agent)}.md"
    if not inbox_path.exists():
        inbox_path.write_text(_render_inbox(agent), encoding="utf-8")

    return inbox_path


def _prepend_pending_item(inbox_path: Path, entry: str) -> None:
    marker = "<!-- CONTROL:INBOX:PENDING -->"
    content = inbox_path.read_text(encoding="utf-8")

    if marker not in content:
        raise RuntimeError(f"Inbox mal formado: falta marcador {marker}")

    updated = content.replace(marker, f"{marker}\n{entry}", 1)
    inbox_path.write_text(updated, encoding="utf-8")


def _deliver_inbox_item(
    agent: str,
    item_type: str,
    title: str,
    body: str,
    origin: str = "CONTROL",
    reference: str | None = None,
    priority: str = "NORMAL",
) -> Path:
    inbox_path = _ensure_agent_inbox(agent)
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    entry_lines = [f"- [{date_str}] [{item_type}] [{priority}] [{origin}] {title}"]
    if body:
        entry_lines.append(f"  detalle: {body}")
    if reference:
        entry_lines.append(f"  ref: {reference.replace(os.sep, '/')}")

    _prepend_pending_item(inbox_path, "\n".join(entry_lines) + "\n")
    return inbox_path

@app.command()
def init():
    """Inicializa la Sede de la Agencia (.control) en el repo actual."""
    base_path = Path(".control")
    folders = ["dossiers", "briefings", "skills", "outputs", "inboxes"]
    
    for folder in folders:
        (base_path / folder).mkdir(parents=True, exist_ok=True)
    
    config = {
        "agency_name": "CONTROL_HQ",
        "created_at": "2026-03-22",
        "system": "Agnostic Agentic Scaffolding"
    }
    
    with open(base_path / "agency.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
        
    console.print(Panel("[bold green]✅ AGENCIA ACTIVADA[/bold green]\nEstructura .control/ creada con éxito.", title="Sede Central"))

@app.command()
def recruit(
    name: str = typer.Argument(..., help="Nombre del agente"),
    c1: str = typer.Option("Local", "--c1", help="Entorno: Local, CLI, Cloud"),
    c2: str = typer.Option("Permanente", "--c2", help="Vida: Efimero, Permanente, Semi"),
    c3: str = typer.Option("Ejecutor", "--c3", help="Rango: Orquestador, Ejecutor")
):
    """Recluta un nuevo agente bajo las 3 capas de CONTROL."""
    agent_id = _agent_slug(name)
    dossier_path = Path(f".control/dossiers/{agent_id}.md")
    inbox_path = _ensure_agent_inbox(name)
    
    content = f"""# 🕵️ Dossier: Agente {name.upper()}

## 🗂️ Clasificación (3 Capas)
- **Capa 1 (Entorno):** {c1}
- **Capa 2 (Ciclo de Vida):** {c2}
- **Capa 3 (Rango):** {c3}

## 🎯 Instrucciones (System Prompt)
Eres el Agente {name}. Tu misión en este repositorio es...
(Define aquí su comportamiento para que Copilot lo asuma)

## 📬 Inbox Operativo
- **Ruta:** `{inbox_path.as_posix()}`
- **Regla:** Leer este inbox al inicio de cada intervención.

## 🛠️ Maletín de Skills
- [ ] Listar skills aquí...

---
*Documento propiedad de CONTROL. Clasificado.*
"""
    dossier_path.write_text(content, encoding="utf-8")
    console.print(f"[bold blue]👤 Agente {name} reclutado.[/bold blue] Dossier listo en: {dossier_path}")

@app.command()
def run_skill(
    name: str = typer.Argument(..., help="Nombre de la skill a ejecutar")):
    skill_path = Path(f".control/skills/{name}/logic.py")
    
    if not skill_path.exists():
        console.print(f"[bold red]❌ Error:[/bold red] La skill '{name}' no existe.")
        raise typer.Exit(code=1)
    
    console.print(f"[bold yellow]⚙️ Ejecutando skill:[/bold yellow] {name}...")
    
    try:
        # Forzamos a Python a usar UTF-8 para la entrada/salida de este subproceso
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [sys.executable, str(skill_path)], 
            capture_output=True, 
            text=True, 
            encoding="utf-8", # IMPORTANTE: Lee la salida como UTF-8
            env=env           # IMPORTANTE: Le dice al hijo que escriba en UTF-8
        )
        
        if result.returncode == 0:
            # Usamos console.print de Rich para que los emojis del hijo salgan bien
            console.print(f"[bold green]✅ Skill finalizada:[/bold green]\n{result.stdout}")
        else:
            console.print(f"[bold red]❌ Fallo en la skill:[/bold red]\n{result.stderr}")
            
    except Exception as e:
        console.print(f"[bold red]💥 Error inesperado:[/bold red] {e}")

@app.command()
def dispatch(
    target: str = typer.Option(..., "--task", "-t", help="Descripción de la misión"),
    agent: str = typer.Option("Max", "--agent", "-a", help="Agente asignado")
):
    """Emite una orden oficial de CONTROL (Crea un Briefing de misión)."""
    briefing_dir = Path(".control/briefings")
    briefing_dir.mkdir(parents=True, exist_ok=True)
    
    # Genera el siguiente ID libre usando el numero mas alto existente.
    mission_id = _next_mission_id(briefing_dir)
    mission_file = briefing_dir / f"mission_{mission_id}.md"
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    content = f"""---
id: {mission_id}
status: OPEN
assigned_to: {agent}
created_at: {date_str}
---

# 🎯 Misión: {target}

## 📝 Descripción
{target}

## 🛠️ Herramientas Sugeridas (Skills)
- [ ] analyze_project
- [ ] (Añadir más según necesidad)

## 📋 Log de Operaciones (The Cone of Silence)
- [{date_str}] [CONTROL]: Misión emitida. Esperando ejecución de {agent}.
"""
    
    mission_file.write_text(content, encoding="utf-8")
    inbox_path = _deliver_inbox_item(
        agent=agent,
        item_type="MISSION",
        title=target,
        body=f"Nueva misión asignada a {agent}.",
        reference=str(mission_file),
        priority="HIGH",
    )
    console.print(Panel(
        f"[bold cyan]Misión {mission_id} emitida con éxito.[/bold cyan]\n"
        f"Archivo: {mission_file}\n"
        f"Agente: {agent}\n"
        f"Inbox: {inbox_path}",
        title="🛰️ Despacho de CONTROL"
    ))


@app.command()
def message(
    agent: str = typer.Option(..., "--agent", "-a", help="Agente destinatario"),
    subject: str = typer.Option(..., "--subject", "-s", help="Asunto del mensaje"),
    body: str = typer.Option("", "--body", "-b", help="Detalle adicional para el inbox"),
):
    """Envía un mensaje informativo al inbox de un agente."""
    inbox_path = _deliver_inbox_item(
        agent=agent,
        item_type="MESSAGE",
        title=subject,
        body=body,
        priority="NORMAL",
    )

    console.print(Panel(
        f"[bold green]Mensaje entregado con éxito.[/bold green]\n"
        f"Agente: {agent}\n"
        f"Inbox: {inbox_path}",
        title="📬 CONTROL Message"
    ))


###
if __name__ == "__main__":
    app()