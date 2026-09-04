@echo off
rem Установка Memory Curator — просто запусти, без вопросов:
rem сам найдёт opencode / Claude Code и поставит всё (MCP, команды, скиллы, worker).
rem Флаги опциональны (для скриптов): --opencode ^| --claude ^| --base-dir ПУТЬ
cd /d "%~dp0core"

python -m venv .venv
if errorlevel 1 goto :error
.venv\Scripts\pip install --quiet -e .
if errorlevel 1 goto :error
.venv\Scripts\curator install %*
exit /b %errorlevel%

:error
echo Не получилось. Проверь, что Python установлен и доступен как "python".
exit /b 1
