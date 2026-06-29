@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

:: 国内 HuggingFace 镜像，否则模型下载会失败
set HF_ENDPOINT=https://hf-mirror.com

:: 启动时不预加载模型，第一次解析 PDF 时再加载，避免启动过慢
set DOCLING_SERVE_LOAD_MODELS_AT_BOOT=false

echo ===========================================
echo  Starting Docling Parse Service
echo  Endpoint: http://localhost:5001
echo ===========================================
echo.

.venv-docling\Scripts\python.exe -m docling_serve run --host 0.0.0.0 --port 5001

endlocal
pause
