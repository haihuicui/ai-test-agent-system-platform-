@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo ===========================================
echo  Starting LightRAG Server (Backend + WebUI)
echo  WebUI: http://localhost:9621
echo  API Docs: http://localhost:9621/docs
echo ===========================================
echo.

.venv\Scripts\lightrag-server.exe

endlocal
pause
