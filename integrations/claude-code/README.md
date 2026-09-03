# Memory Curator в Claude Code

Три шага подключения:

1. **MCP-сервер** — скопируй `.mcp.json` (рядом с этим файлом) в корень
   проекта или в `~/.claude.json` (глобально). Поправь `command` —
   абсолютный путь к `curator-mcp-server` в твоём окружении
   (venv репозитория memory-curator) — и `CURATOR_BASE_DIR` — директория
   с .md-файлами базы знаний.

2. **Скилл** — скопируй скилл сохранения знаний:

   ```bash
   mkdir -p ~/.claude/skills
   cp -r ../../.agents/skills/curator-save ~/.claude/skills/
   ```

   Скилл описан в формате Claude Code (YAML frontmatter + инструкция) и
   включает проактивный триггер: агент сам предлагает сохранить проверенное
   знание по ходу сессии.

3. **Проверка** — в новой сессии Claude Code:

   ```
   сохрани знания из этой сессии
   ```

   Агент извлечёт кандидатов, покажет preview, после подтверждения
   сохранит через MCP (`curator_session_capture`), факт появится в
   `CURATOR_BASE_DIR/session/{type}.md`, дедубликацией и устареванием
   займётся improve-цикл.

Контракт кандидатов и правила формата — в скилле
(`.agents/skills/curator-save/SKILL.md`). Локальный запуск и CLI —
в `docs/getting-started.md`.
