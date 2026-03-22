# Technical Analysis - CONTROL CLI (Mission 001)

## Scope
Reviewed current project structure and CLI implementation in:
- pyproject.toml
- src/control/cli.py

## Current Snapshot
- CLI framework: Typer + Rich
- Commands implemented: init, recruit, run_skill, dispatch
- Packaging: setuptools backend, console script `control = control.cli:app`
- Storage model: local `.control/` workspace folders and markdown/yaml files

## Strengths
- Clear initial command set and simple onboarding flow.
- Good use of Typer for options/arguments and auto-help.
- Rich output improves operator feedback.
- Data layout in `.control/` is understandable.

## Technical Findings
1. Missing package init file
- `src/control/__init__.py` is not present in the visible structure.
- This can break packaging/import behavior in some environments.

2. Mission ID generation can collide
- `dispatch` uses `len(existing_missions) + 1`.
- If a mission file is deleted or numbering is non-sequential, IDs can be reused.

3. No validation for enum-like options
- `recruit` accepts free text for `c1`, `c2`, `c3` even though valid sets are implied.
- This can produce inconsistent dossiers.

4. Skill execution command is environment-dependent
- `run_skill` calls `python` directly, which may not map to expected interpreter.
- This is brittle across Windows/Linux and venv setups.

5. Missing error handling around filesystem writes
- `init`, `recruit`, and `dispatch` do not wrap file operations with clear error messages.
- Failures (permissions, missing dirs, encoding edge cases) are not classified.

6. CLI structure scaling risk
- All commands live in one file (`src/control/cli.py`), which will become harder to maintain.

7. Limited automated quality gates
- No test suite, linting, formatting, or CI checks are defined in project metadata.

## Recommended Improvements (Priority Order)
P0 - Reliability
1. Add `src/control/__init__.py`.
2. Change mission ID logic to parse max existing numeric suffix and increment safely.
3. Use `sys.executable` (or Typer/Click subprocess strategy) instead of hardcoded `python`.

P1 - Correctness and UX
4. Enforce option choices for `c1`, `c2`, `c3` using `typing.Literal` or Typer enums.
5. Add defensive checks and user-friendly errors for all file write/read operations.
6. Add a `--dry-run` mode for `dispatch` and `recruit`.

P2 - Maintainability
7. Split commands into modules:
   - `src/control/commands/init.py`
   - `src/control/commands/recruit.py`
   - `src/control/commands/dispatch.py`
   - `src/control/commands/skill.py`
8. Add shared services (`mission_service.py`, `fs_utils.py`) for reusable logic.

P3 - Engineering hygiene
9. Add tests (pytest) for:
   - mission ID generation
   - dossier generation
   - skill path resolution and error branches
10. Add tooling config (ruff + black + optional mypy) and CI workflow.

## Suggested Next Deliverables
- Iteration 1: P0 fixes only (safe and low-risk).
- Iteration 2: P1 + command modularization.
- Iteration 3: tests + lint + CI.
