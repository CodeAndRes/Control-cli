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

@app.command()
def init():
    """Inicializa la Sede de la Agencia (.control) en el repo actual."""
    base_path = Path(".control")
    folders = ["dossiers", "briefings", "skills", "outputs"]
    
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
    dossier_path = Path(f".control/dossiers/{name.lower()}.md")
    
    content = f"""# 🕵️ Dossier: Agente {name.upper()}

## 🗂️ Clasificación (3 Capas)
- **Capa 1 (Entorno):** {c1}
- **Capa 2 (Ciclo de Vida):** {c2}
- **Capa 3 (Rango):** {c3}

## 🎯 Instrucciones (System Prompt)
Eres el Agente {name}. Tu misión en este repositorio es...
(Define aquí su comportamiento para que Copilot lo asuma)

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
    console.print(Panel(
        f"[bold cyan]Misión {mission_id} emitida con éxito.[/bold cyan]\n"
        f"Archivo: {mission_file}\n"
        f"Agente: {agent}",
        title="🛰️ Despacho de CONTROL"
    ))


###
if __name__ == "__main__":
    app()