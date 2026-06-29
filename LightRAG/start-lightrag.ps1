# LightRAG 一键启动脚本（PowerShell）
# 用法：右键 → 使用 PowerShell 运行，或在终端执行：.\start-lightrag.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"

Write-Host "===========================================" -ForegroundColor Cyan
Write-Host " Starting LightRAG Server (Backend + WebUI)" -ForegroundColor Cyan
Write-Host " WebUI:    http://localhost:9621" -ForegroundColor Yellow
Write-Host " API Docs: http://localhost:9621/docs" -ForegroundColor Yellow
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

& ".venv\Scripts\lightrag-server.exe"
