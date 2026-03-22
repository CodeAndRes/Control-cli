import os
import re
import subprocess
import sys
from pathlib import Path


def _agent_slug(agent_name: str) -> str:
    return agent_name.strip().lower().replace(" ", "_")


def _read_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _find_dossier_path(agent_name: str) -> Path:
    dossier_dir = Path(".control/dossiers")
    direct_match = dossier_dir / f"{_agent_slug(agent_name)}.md"
    if direct_match.exists():
        return direct_match

    normalized_agent = agent_name.strip().lower()
    for dossier_path in sorted(dossier_dir.glob("*.md")):
        content = _read_if_exists(dossier_path)
        title_match = re.search(r"^# .*Agente\s+(.+?)\s*$", content, flags=re.MULTILINE)
        if title_match and title_match.group(1).strip().lower() == normalized_agent:
            return dossier_path
        if normalized_agent in content.lower():
            return dossier_path

    return direct_match


def _briefings_for_agent(agent_name: str) -> list[Path]:
    briefing_dir = Path(".control/briefings")
    matches = []
    for mission_path in sorted(briefing_dir.glob("mission_*.md")):
        content = _read_if_exists(mission_path)
        if f"assigned_to: {agent_name}" in content:
            matches.append(mission_path)
    return matches


def _briefing_meta(mission_path: Path) -> dict[str, str]:
    content = _read_if_exists(mission_path)
    status = "UNKNOWN"
    created_at = "unknown"
    title = mission_path.stem

    for line in content.splitlines():
        if line.startswith("status: "):
            status = line.split(":", 1)[1].strip()
        elif line.startswith("created_at: "):
            created_at = line.split(":", 1)[1].strip()
        elif line.startswith("# "):
            title = line.replace("# ", "", 1).strip()
            for prefix in ["🎯 Misión: ", "🎯 Mision: ", "Misión: ", "Mision: "]:
                if title.startswith(prefix):
                    title = title.replace(prefix, "", 1)
                    break

    mission_id_match = re.search(r"mission_(\d+)", mission_path.stem)
    mission_id = mission_id_match.group(1) if mission_id_match else "000"

    return {
        "id": mission_id,
        "status": status,
        "created_at": created_at,
        "title": title,
        "path": mission_path.as_posix(),
    }


def _pending_and_history(inbox_content: str) -> tuple[list[str], list[str]]:
    pending_marker = "<!-- CONTROL:INBOX:PENDING -->"
    history_marker = "<!-- CONTROL:INBOX:HISTORY -->"
    history_header = "## Historial"

    if pending_marker not in inbox_content or history_marker not in inbox_content or history_header not in inbox_content:
        return [], []

    pending_start = inbox_content.index(pending_marker) + len(pending_marker)
    history_header_start = inbox_content.index(history_header)
    history_start = inbox_content.index(history_marker) + len(history_marker)

    pending_section = inbox_content[pending_start:history_header_start].strip()
    history_section = inbox_content[history_start:].strip()

    def parse(section: str) -> list[str]:
        if not section:
            return []
        entries = []
        current = []
        for line in section.splitlines():
            if line.startswith("- ["):
                if current:
                    entries.append("\n".join(current))
                current = [line]
            elif current:
                current.append(line)
        if current:
            entries.append("\n".join(current))
        return entries

    return parse(pending_section), parse(history_section)


def _git_lines(command: list[str]) -> list[str]:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _extract_consciousness_section(content: str) -> str:
    match = re.search(r"^## Clone Consciousness Dump\s*$", content, flags=re.MULTILINE)
    if not match:
        return ""

    start = match.end()
    next_header = content.find("\n## ", start)
    return content[start:] if next_header == -1 else content[start:next_header]


def _consciousness_validation_errors(output_path: Path) -> list[str]:
    content = _read_if_exists(output_path)
    if not content:
        return []

    section = _extract_consciousness_section(content)
    if not section:
        return ["No existe la seccion `Clone Consciousness Dump` en el resumen previo."]

    errors: list[str] = []

    if "PENDIENTE" in section:
        errors.append("La seccion contiene campos en `PENDIENTE`.")

    required_fields = [
        "Timestamp",
        "Clone identity",
        "Mission focus now",
        "What I understand from dossier/inbox",
        "Decisions I am taking now",
        "Next 3 concrete actions",
        "Risks or blockers",
    ]

    for field in required_fields:
        line_match = re.search(rf"^-\s+{re.escape(field)}:\s*(.*)$", section, flags=re.MULTILINE)
        if not line_match:
            errors.append(f"Falta el campo obligatorio `{field}`.")
            continue

        value = line_match.group(1).strip()
        if not value:
            errors.append(f"El campo `{field}` esta vacio.")

    timeline_header = re.search(r"^-\s+Git timeline evidence:\s*$", section, flags=re.MULTILINE)
    if not timeline_header:
        errors.append("Falta el bloque `Git timeline evidence`.")
    else:
        timeline_start = timeline_header.end()
        timeline_tail = section[timeline_start:]
        timeline_items = re.findall(r"^\s+-\s+(.+)$", timeline_tail, flags=re.MULTILINE)
        timeline_items = [item.strip() for item in timeline_items if item.strip()]
        valid_items = [item for item in timeline_items if "No git timeline available" not in item]
        if not valid_items:
            errors.append("Se requiere al menos 1 evidencia valida en `Git timeline evidence`.")

    return errors


def build_summary(agent_name: str, clone_name: str = "", force: bool = False) -> tuple[Path, str]:
    agent_slug = _agent_slug(agent_name)
    clone_label = clone_name.strip() or f"{agent_name}-fresh"
    dossier_path = _find_dossier_path(agent_name)
    inbox_path = Path(f".control/inboxes/{agent_slug}.md")
    output_path = Path(f".control/outputs/agent_{agent_slug}_clone_summary.md")

    if output_path.exists() and not force:
        validation_errors = _consciousness_validation_errors(output_path)
        if validation_errors:
            detail = " ".join(f"- {error}" for error in validation_errors)
            raise RuntimeError(
                "Bloqueado: el `Clone Consciousness Dump` del resumen previo no cumple la validacion minima. "
                "Completa el volcado o reintenta con modo forzado. "
                f"Detalles: {detail}"
            )

    dossier_content = _read_if_exists(dossier_path)
    inbox_content = _read_if_exists(inbox_path)
    pending_entries, history_entries = _pending_and_history(inbox_content)
    agent_briefings = _briefings_for_agent(agent_name)
    briefing_metas = [_briefing_meta(path) for path in agent_briefings]
    briefing_metas.sort(key=lambda item: item["id"], reverse=True)
    open_missions = [meta for meta in briefing_metas if meta["status"] == "OPEN"]
    done_missions = [meta for meta in briefing_metas if meta["status"] == "DONE"]

    branch_line = _git_lines(["git", "branch", "--show-current"])
    status_line = _git_lines(["git", "status", "--short", "--branch"])
    recent_commits = _git_lines(["git", "log", "--oneline", "-n", "5"])
    timeline_commits = _git_lines(["git", "log", "--oneline", "-n", "10"])

    summary_lines = [
        f"# Agent Clone Summary: {agent_name}",
        "",
        f"Clone target: {clone_label}",
        f"Agent slug: {agent_slug}",
        "",
        "## Repo State",
        f"Current branch: {branch_line[0] if branch_line else 'unknown'}",
        f"Git status: {status_line[0] if status_line else 'unknown'}",
        "",
        "## Current Agent Assets",
        f"Dossier: {dossier_path.as_posix()} {'OK' if dossier_path.exists() else 'MISSING'}",
        f"Inbox: {inbox_path.as_posix()} {'OK' if inbox_path.exists() else 'MISSING'}",
        f"Assigned briefings: {len(agent_briefings)}",
        f"Inbox pending: {len(pending_entries)}",
        "",
        "## Source Agent Context",
        f"Assigned missions total: {len(briefing_metas)}",
        f"Assigned missions OPEN: {len(open_missions)}",
        f"Assigned missions DONE: {len(done_missions)}",
        f"Latest archived entries: {len(history_entries)}",
        "",
        "### Latest Assigned Missions",
    ]

    if briefing_metas:
        for meta in briefing_metas[:5]:
            summary_lines.append(
                f"- mission_{meta['id']} [{meta['status']}] {meta['title']} ({meta['created_at']})"
            )
    else:
        summary_lines.append("- No missions assigned to this agent.")

    summary_lines.extend([
        "",
        "### Continuity Signal",
    ])
    if pending_entries:
        summary_lines.append("- Hay trabajo pendiente en inbox: priorizar `inbox-pending` y resolver en orden.")
    elif open_missions:
        summary_lines.append("- No hay inbox pendiente, pero existen misiones OPEN asignadas por retomar.")
    else:
        summary_lines.append("- Estado estable: sin pendientes inmediatos ni misiones OPEN asignadas.")

    summary_lines.extend([
        "",
        "## What This Agent Already Has",
    ])

    if dossier_content:
        summary_lines.append("- Dossier operativo disponible.")
    if inbox_content:
        summary_lines.append("- Inbox operativo disponible.")
    if recent_commits:
        summary_lines.append("- Fases recientes publicadas en Git.")

    summary_lines.extend([
        "",
        "## Recent Commits",
    ])
    summary_lines.extend(f"- {line}" for line in recent_commits[:5])

    summary_lines.extend([
        "",
        "## Latest Archived Inbox Entries",
    ])
    if history_entries:
        summary_lines.extend(f"- {entry.splitlines()[0][2:]}" for entry in history_entries[:5])
    else:
        summary_lines.append("- No archived entries yet.")

    summary_lines.extend([
        "",
        "## Pending Inbox Entries",
    ])
    if pending_entries:
        summary_lines.extend(f"- {entry.splitlines()[0][2:]}" for entry in pending_entries[:5])
    else:
        summary_lines.append("- No pending entries.")

    summary_lines.extend([
        "",
        "## Suggested Bootstrap For New Clone",
        f"- Leer {dossier_path.as_posix()}.",
        f"- Leer {inbox_path.as_posix()}.",
        f"- Ejecutar `controlhq inbox-pending --agent {agent_name}`.",
        "- Continuar desde la rama actual si no se define otra instruccion.",
        "",
        "## Clone Consciousness Dump Instructions",
        "- Objetivo: al iniciar, el clon debe dejar su propio estado mental operativo en este mismo archivo.",
        "- Ubicacion: completar la seccion `## Clone Consciousness Dump` al final de este documento.",
        "- Frecuencia: al iniciar y despues de cada bloque relevante de trabajo.",
        "- Evidencia minima: usar estado Git y commits recientes para justificar decisiones.",
        "- Comandos sugeridos:",
        "  - `git status --short --branch`",
        "  - `git log --oneline -n 10`",
        "- Regla: no escribir solo intenciones; registrar hechos, decisiones y siguiente accion concreta.",
        "",
        "## Clone Consciousness Dump",
        "- Timestamp: PENDIENTE",
        "- Clone identity: PENDIENTE",
        "- Mission focus now: PENDIENTE",
        "- What I understand from dossier/inbox: PENDIENTE",
        "- Decisions I am taking now: PENDIENTE",
        "- Next 3 concrete actions: PENDIENTE",
        "- Risks or blockers: PENDIENTE",
        "- Git branch snapshot: " + (branch_line[0] if branch_line else "unknown"),
        "- Git status snapshot: " + (status_line[0] if status_line else "unknown"),
        "- Git timeline evidence:",
    ])

    if timeline_commits:
        summary_lines.extend(f"  - {line}" for line in timeline_commits[:10])
    else:
        summary_lines.append("  - No git timeline available.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return output_path, clone_label


def run_skill() -> None:
    agent_name = os.environ.get("CONTROL_AGENT", "99").strip() or "99"
    clone_name = os.environ.get("CONTROL_CLONE_NAME", "").strip()
    force = os.environ.get("CONTROL_FORCE_CONSCIOUSNESS", "0").strip() in {"1", "true", "yes"}
    if len(sys.argv) > 1 and sys.argv[1].strip():
        agent_name = sys.argv[1].strip()
    if len(sys.argv) > 2 and sys.argv[2].strip():
        clone_name = sys.argv[2].strip()
    if len(sys.argv) > 3 and sys.argv[3].strip().lower() in {"1", "true", "yes", "force"}:
        force = True

    try:
        output_path, clone_label = build_summary(agent_name, clone_name, force=force)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)

    print(f"Clone summary generated for {agent_name} -> {clone_label}")
    print(f"Output: {output_path.as_posix()}")


if __name__ == "__main__":
    run_skill()