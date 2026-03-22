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


def build_summary(agent_name: str, clone_name: str = "") -> tuple[Path, str]:
    agent_slug = _agent_slug(agent_name)
    clone_label = clone_name.strip() or f"{agent_name}-fresh"
    dossier_path = _find_dossier_path(agent_name)
    inbox_path = Path(f".control/inboxes/{agent_slug}.md")
    output_path = Path(f".control/outputs/agent_{agent_slug}_clone_summary.md")

    dossier_content = _read_if_exists(dossier_path)
    inbox_content = _read_if_exists(inbox_path)
    pending_entries, history_entries = _pending_and_history(inbox_content)
    agent_briefings = _briefings_for_agent(agent_name)

    branch_line = _git_lines(["git", "branch", "--show-current"])
    status_line = _git_lines(["git", "status", "--short", "--branch"])
    recent_commits = _git_lines(["git", "log", "--oneline", "-n", "5"])

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
        "## What This Agent Already Has",
    ]

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
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return output_path, clone_label


def run_skill() -> None:
    agent_name = os.environ.get("CONTROL_AGENT", "99").strip() or "99"
    clone_name = os.environ.get("CONTROL_CLONE_NAME", "").strip()
    if len(sys.argv) > 1 and sys.argv[1].strip():
        agent_name = sys.argv[1].strip()
    if len(sys.argv) > 2 and sys.argv[2].strip():
        clone_name = sys.argv[2].strip()

    output_path, clone_label = build_summary(agent_name, clone_name)
    print(f"Clone summary generated for {agent_name} -> {clone_label}")
    print(f"Output: {output_path.as_posix()}")


if __name__ == "__main__":
    run_skill()