#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Truncate the bloated CapabilityAccessManager.db-wal file.
.DESCRIPTION
    Windows 的 Capability Access Manager 服务 (camsvc) 的 SQLite WAL 日志文件
    (C:\ProgramData\Microsoft\Windows\CapabilityAccessManager\CapabilityAccessManager.db-wal)
    可能异常膨胀到数十 GB。此脚本停止服务、删除 WAL 文件并重启服务，
    让系统重建一个干净的 WAL。
#>

$LogFile = "d:\project\ai-test-agent\cleanup-log-20260706-admin.txt"
$Log = @()
$Log += "=== CapabilityAccessManager WAL cleanup started at $(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss') ==="

try {
    $ServiceName = "camsvc"
    $WalPath = "C:\ProgramData\Microsoft\Windows\CapabilityAccessManager\CapabilityAccessManager.db-wal"

    $Log += "Stopping service: $ServiceName"
    Stop-Service -Name $ServiceName -Force -ErrorAction Stop
    $Log += "Service stopped successfully."

    Start-Sleep -Seconds 2

    if (Test-Path $WalPath) {
        $Size = (Get-Item $WalPath).Length
        $SizeGB = [math]::Round($Size / 1GB, 2)
        $Log += "Found WAL file: $WalPath ($SizeGB GB)"
        Remove-Item $WalPath -Force -ErrorAction Stop
        $Log += "DELETED WAL file."
    } else {
        $Log += "WAL file not found at $WalPath"
    }

    $Log += "Starting service: $ServiceName"
    Start-Service -Name $ServiceName -ErrorAction Stop
    $Log += "Service started successfully."

    $Log += "=== Cleanup completed at $(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss') ==="
} catch {
    $Log += "ERROR: $_"
}

$Log | Out-File -FilePath $LogFile -Encoding utf8
$Log | ForEach-Object { Write-Output $_ }

Write-Output "`n日志已保存到: $LogFile"
Write-Output "按 Enter 键退出..."
Read-Host
