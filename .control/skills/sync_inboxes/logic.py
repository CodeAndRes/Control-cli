import re
from pathlib import Path


def _agent_name_from_dossier(dossier_path: Path) -> str:
    content = dossier_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        match = re.match(r"^# .*Agente\s+(.+?)(?:\s*\(|$)", line.strip())
        if match:
            return match.group(1).strip()
    return dossier_path.stem


def _agent_slug(agent_name: str) -> str:
    return agent_name.strip().lower().replace(" ", "_")


def _render_inbox(agent_name: str) -> str:
    agent_id = _agent_slug(agent_name)
    return f"""---
agent: {agent_name}
agent_id: {agent_id}
read_required_on_start: true
---

# 📬 Inbox: {agent_name}

## Reglas
- Leer este inbox al iniciar cualquier intervención.
- Las misiones accionables se desarrollan en `.control/briefings`.
- Este inbox centraliza notificaciones, contexto y referencias para el agente.

## Pendientes
<!-- CONTROL:INBOX:PENDING -->

## Historial
<!-- CONTROL:INBOX:HISTORY -->
"""


def run_skill() -> None:
    dossier_dir = Path(".control/dossiers")
    inbox_dir = Path(".control/inboxes")
    inbox_dir.mkdir(parents=True, exist_ok=True)

    created = []
    existing = []

    for dossier_path in sorted(dossier_dir.glob("*.md")):
        agent_name = _agent_name_from_dossier(dossier_path)
        inbox_path = inbox_dir / f"{_agent_slug(agent_name)}.md"

        if inbox_path.exists():
            existing.append(inbox_path.name)
            continue

        inbox_path.write_text(_render_inbox(agent_name), encoding="utf-8")
        created.append(inbox_path.name)

    print("✅ sync_inboxes completada")
    print(f"Creados: {', '.join(created) if created else 'ninguno'}")
    print(f"Existentes: {', '.join(existing) if existing else 'ninguno'}")


if __name__ == "__main__":
    run_skill()