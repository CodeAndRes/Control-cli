---
id: 008
status: DONE
assigned_to: 99
created_at: 2026-03-22 19:01
---

# 🎯 Misión: Fase 3 de invocación del CLI en Windows

## 📝 Descripción
Resolver la colisión del comando `control` con `control.exe` de Windows proporcionando una vía estable y documentada para invocar el CLI del proyecto.

## ✅ Alcance de esta fase
- Añadir un entry point alternativo no ambiguo para el CLI.
- Ajustar documentación operativa para usar la invocación estable.
- Validar la ejecución real del CLI con el nuevo comando.

## 🛠️ Herramientas Sugeridas (Skills)
- [ ] sync_inboxes
- [ ] Toda automatizacion repetible debe mantenerse apta para convertirse en skill.

## 📋 Log de Operaciones (The Cone of Silence)
- [2026-03-22 19:01] [CONTROL]: Misión emitida. Esperando ejecución de 99.
- [2026-03-22 19:02] [99]: Rama incremental `feat/agent-cli-phase3` creada desde la fase anterior.
- [2026-03-22 19:02] [99]: Añadido el entry point estable `controlhq` para Windows.
- [2026-03-22 19:02] [99]: Documentación operativa mínima añadida en README y dossiers actualizados.
- [2026-03-22 19:02] [99]: Validada la ejecución real con `.\venv\Scripts\controlhq.exe --help` e `inbox-pending`.
- [2026-03-22 19:02] [99]: Misión completada.
