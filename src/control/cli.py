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
PENDING_MARKER = "<!-- CONTROL:INBOX:PENDING -->"
HISTORY_MARKER = "<!-- CONTROL:INBOX:HISTORY -->"
HISTORY_HEADER = "## Historial"


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
{PENDING_MARKER}

## Historial
{HISTORY_MARKER}
"""


def _ensure_agent_inbox(agent: str) -> Path:
    inbox_dir = Path(".control/inboxes")
    inbox_dir.mkdir(parents=True, exist_ok=True)

    inbox_path = inbox_dir / f"{_agent_slug(agent)}.md"
    if not inbox_path.exists():
        inbox_path.write_text(_render_inbox(agent), encoding="utf-8")

    return inbox_path


def _prepend_pending_item(inbox_path: Path, entry: str) -> None:
    content = inbox_path.read_text(encoding="utf-8")

    if PENDING_MARKER not in content:
        raise RuntimeError(f"Inbox mal formado: falta marcador {PENDING_MARKER}")

    updated = content.replace(PENDING_MARKER, f"{PENDING_MARKER}\n{entry}", 1)
    inbox_path.write_text(updated, encoding="utf-8")


def _split_inbox_sections(content: str) -> tuple[str, str, str, str]:
    if PENDING_MARKER not in content or HISTORY_MARKER not in content or HISTORY_HEADER not in content:
        raise RuntimeError("Inbox mal formado: faltan marcadores de seccion")

    pending_start = content.index(PENDING_MARKER) + len(PENDING_MARKER)
    history_header_start = content.index(HISTORY_HEADER)
    history_content_start = content.index(HISTORY_MARKER) + len(HISTORY_MARKER)

    prefix = content[:pending_start]
    pending_section = content[pending_start:history_header_start]
    middle = content[history_header_start:history_content_start]
    history_section = content[history_content_start:]
    return prefix, pending_section, middle, history_section


def _parse_entries(section: str) -> list[str]:
    lines = section.strip("\n").splitlines()
    if not lines or all(not line.strip() for line in lines):
        return []

    entries: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        if line.startswith("- ["):
            if current:
                entries.append(current)
            current = [line]
            continue

        if current:
            current.append(line)

    if current:
        entries.append(current)

    return ["\n".join(entry).rstrip() for entry in entries]


def _render_entries(entries: list[str]) -> str:
    if not entries:
        return "\n"

    return "\n" + "\n\n".join(entries) + "\n"


def _load_inbox_entries(inbox_path: Path) -> tuple[str, list[str], str, list[str]]:
    content = inbox_path.read_text(encoding="utf-8")
    prefix, pending_section, middle, history_section = _split_inbox_sections(content)
    return prefix, _parse_entries(pending_section), middle, _parse_entries(history_section)


def _write_inbox_entries(
    inbox_path: Path,
    prefix: str,
    pending_entries: list[str],
    middle: str,
    history_entries: list[str],
) -> None:
    content = "".join(
        [
            prefix,
            _render_entries(pending_entries),
            middle,
            _render_entries(history_entries),
        ]
    )
    inbox_path.write_text(content, encoding="utf-8")


def _entry_status(entry: str) -> str:
    first_line = entry.splitlines()[0]
    if " [NEW] " in first_line:
        return "NEW"
    if " [ACK] " in first_line:
        return "ACK"
    if " [ARCHIVED] " in first_line:
        return "ARCHIVED"
    return "NEW"


def _replace_entry_status(entry: str, new_status: str) -> str:
    lines = entry.splitlines()
    first_line = lines[0]

    for current_status in ["NEW", "ACK", "ARCHIVED"]:
        marker = f" [{current_status}] "
        if marker in first_line:
            lines[0] = first_line.replace(marker, f" [{new_status}] ", 1)
            return "\n".join(lines)

    lines[0] = first_line.replace("] ", f"] [{new_status}] ", 4)
    return "\n".join(lines)


def _inbox_entry_summary(index: int, entry: str) -> str:
    return f"{index}. {entry.splitlines()[0]}"


def _normalize_mission_id(mission_id: str) -> str:
    normalized = mission_id.strip()
    if not normalized.isdigit():
        raise typer.BadParameter("El id de mision debe ser numerico")
    return f"{int(normalized):03d}"


def _mission_file_path(mission_id: str) -> Path:
    return Path(".control/briefings") / f"mission_{_normalize_mission_id(mission_id)}.md"


def _mission_context(mission_file: Path) -> tuple[str, str]:
    assigned_to = "99"
    title = mission_file.stem

    for line in mission_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("assigned_to: "):
            assigned_to = line.split(":", 1)[1].strip()
        elif line.startswith("# "):
            title = line.replace("# ", "", 1).strip()
            for prefix in ["🎯 Misión: ", "🎯 Mision: ", "Misión: ", "Mision: "]:
                if title.startswith(prefix):
                    title = title.replace(prefix, "", 1)
                    break

    return assigned_to, title


def _close_mission_briefing(mission_file: Path, actor: str, note: str) -> tuple[str, str]:
    content = mission_file.read_text(encoding="utf-8")
    assigned_to, title = _mission_context(mission_file)

    if "status: OPEN" in content:
        content = content.replace("status: OPEN", "status: DONE", 1)

    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    log_line = f"- [{date_str}] [{actor}]: Mision cerrada desde CLI."
    if note:
        log_line += f" {note}"

    if not content.endswith("\n"):
        content += "\n"
    content += log_line + "\n"
    mission_file.write_text(content, encoding="utf-8")
    return assigned_to, title


def _archive_inbox_entry_for_mission(agent: str, mission_file: Path, title: str) -> tuple[Path, bool]:
    inbox_path = _ensure_agent_inbox(agent)
    prefix, pending_entries, middle, history_entries = _load_inbox_entries(inbox_path)
    mission_ref = f"ref: {str(mission_file).replace(os.sep, '/')}"

    for index, entry in enumerate(pending_entries):
        if mission_ref in entry:
            archived_entry = _replace_entry_status(pending_entries.pop(index), "ARCHIVED")
            history_entries.insert(0, archived_entry)
            _write_inbox_entries(inbox_path, prefix, pending_entries, middle, history_entries)
            return inbox_path, True

    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    archived_entry = "\n".join([
        f"- [{date_str}] [MISSION] [HIGH] [CONTROL] [ARCHIVED] {title}",
        "  detalle: Mision archivada desde CLI sin entrada pendiente previa.",
        f"  ref: {str(mission_file).replace(os.sep, '/')}"
    ])
    history_entries.insert(0, archived_entry)
    _write_inbox_entries(inbox_path, prefix, pending_entries, middle, history_entries)
    return inbox_path, False


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

    entry_lines = [f"- [{date_str}] [{item_type}] [{priority}] [{origin}] [NEW] {title}"]
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


@app.command()
def inbox_pending(
    agent: str = typer.Option("", "--agent", "-a", help="Agente a consultar. Si se omite, lista todos los inboxes."),
):
    """Lista las entradas pendientes del inbox."""
    inbox_paths: list[Path]

    if agent:
        inbox_paths = [_ensure_agent_inbox(agent)]
    else:
        inbox_paths = [
            path
            for path in sorted(Path(".control/inboxes").glob("*.md"))
            if path.name.lower() != "readme.md"
        ]

    reports: list[str] = []
    for inbox_path in inbox_paths:
        prefix, pending_entries, _, _ = _load_inbox_entries(inbox_path)
        agent_line = next((line for line in prefix.splitlines() if line.startswith("agent: ")), f"agent: {inbox_path.stem}")
        agent_name = agent_line.split(":", 1)[1].strip()
        reports.append(f"Inbox {agent_name} ({len(pending_entries)} pendientes)")
        if pending_entries:
            reports.extend(_inbox_entry_summary(index, entry) for index, entry in enumerate(pending_entries, start=1))

    console.print(Panel("\n".join(reports), title="📥 Inbox Pending"))


@app.command()
def inbox_ack(
    agent: str = typer.Option(..., "--agent", "-a", help="Agente propietario del inbox"),
    item: int = typer.Option(..., "--item", "-i", help="Indice 1-based de la entrada pendiente"),
):
    """Marca una entrada pendiente del inbox como leida."""
    inbox_path = _ensure_agent_inbox(agent)
    prefix, pending_entries, middle, history_entries = _load_inbox_entries(inbox_path)

    if item < 1 or item > len(pending_entries):
        raise typer.BadParameter("Indice de inbox fuera de rango")

    updated_entry = _replace_entry_status(pending_entries[item - 1], "ACK")
    pending_entries[item - 1] = updated_entry
    _write_inbox_entries(inbox_path, prefix, pending_entries, middle, history_entries)

    console.print(Panel(updated_entry.splitlines()[0], title="✅ Inbox ACK"))


@app.command()
def inbox_archive(
    agent: str = typer.Option(..., "--agent", "-a", help="Agente propietario del inbox"),
    item: int = typer.Option(..., "--item", "-i", help="Indice 1-based de la entrada pendiente"),
):
    """Mueve una entrada pendiente al historial del inbox."""
    inbox_path = _ensure_agent_inbox(agent)
    prefix, pending_entries, middle, history_entries = _load_inbox_entries(inbox_path)

    if item < 1 or item > len(pending_entries):
        raise typer.BadParameter("Indice de inbox fuera de rango")

    archived_entry = _replace_entry_status(pending_entries.pop(item - 1), "ARCHIVED")
    history_entries.insert(0, archived_entry)
    _write_inbox_entries(inbox_path, prefix, pending_entries, middle, history_entries)

    console.print(Panel(archived_entry.splitlines()[0], title="🗃️ Inbox Archived"))


@app.command()
def mission_close(
    mission: str = typer.Option(..., "--mission", "-m", help="ID de la mision a cerrar"),
    actor: str = typer.Option("99", "--actor", help="Agente que realiza el cierre"),
    note: str = typer.Option("", "--note", "-n", help="Nota adicional para el log de cierre"),
):
    """Cierra una mision y sincroniza su inbox asociado."""
    mission_file = _mission_file_path(mission)
    if not mission_file.exists():
        raise typer.BadParameter("La mision indicada no existe")

    assigned_to, title = _close_mission_briefing(mission_file, actor, note)
    inbox_path, archived_existing_entry = _archive_inbox_entry_for_mission(assigned_to, mission_file, title)

    detail = "Entrada pendiente archivada." if archived_existing_entry else "Entrada archivada creada en historial."
    console.print(Panel(
        f"[bold green]Mision cerrada con exito.[/bold green]\n"
        f"Mision: {mission_file.name}\n"
        f"Agente: {assigned_to}\n"
        f"Inbox: {inbox_path}\n"
        f"Resultado inbox: {detail}",
        title="✅ Mission Closed"
    ))


###
if __name__ == "__main__":
    app()