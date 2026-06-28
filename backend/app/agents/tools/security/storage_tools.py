"""
渗透测试 - 结果存储工具模块

提供 SQLite 持久化存储功能，用于保存漏洞发现、扫描结果和生成报告。
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from langchain_core.tools import tool

from app.utils.sync_executor import run_sync
from app.config.settings import settings

SECURITY_WORKSPACE = Path(settings.api_workspace_root).resolve().parent / "workspace" / "security"
SECURITY_WORKSPACE.mkdir(parents=True, exist_ok=True)

DB_PATH = SECURITY_WORKSPACE / "pentest_results.db"


# ============================================================================
# 数据库初始化
# ============================================================================

def _init_db():
    """初始化 SQLite 数据库表结构"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Projects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            target TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Hosts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            hostname TEXT,
            ip_address TEXT,
            os_type TEXT,
            ports TEXT,
            technologies TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    # Vulnerabilities table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vulnerabilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            host_id INTEGER,
            vuln_id TEXT NOT NULL,
            title TEXT NOT NULL,
            severity TEXT NOT NULL,
            vuln_type TEXT,
            affected_url TEXT,
            parameter TEXT,
            description TEXT,
            reproduction TEXT,
            evidence TEXT,
            remediation TEXT,
            cvss_score REAL,
            status TEXT DEFAULT 'open',
            discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (host_id) REFERENCES hosts(id)
        )
    """)

    # Scan results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            scan_type TEXT NOT NULL,
            target TEXT NOT NULL,
            tool TEXT,
            result_json TEXT,
            raw_output TEXT,
            scan_time TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    # Reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            report_type TEXT,
            format TEXT,
            file_path TEXT,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    conn.commit()
    conn.close()


_init_db()


# ============================================================================
# 同步辅助函数
# ============================================================================

def _storage_create_project(name: str, target: str, description: Optional[str]) -> dict:
    """同步：创建渗透测试项目"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO projects (name, target, description) VALUES (?, ?, ?)",
        (name, target, description),
    )
    project_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "success": True,
        "project_id": project_id,
        "name": name,
        "target": target,
        "message": f"项目 '{name}' 创建成功",
    }


def _storage_list_projects() -> dict:
    """同步：列出所有渗透测试项目"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, target, status, created_at FROM projects ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()

    projects = []
    for row in rows:
        projects.append({
            "id": row[0],
            "name": row[1],
            "target": row[2],
            "status": row[3],
            "created_at": row[4],
        })

    return {
        "success": True,
        "total": len(projects),
        "projects": projects,
    }


def _storage_add_vulnerability(
    project_id: int,
    vuln_id: str,
    title: str,
    severity: str,
    vuln_type: Optional[str] = None,
    affected_url: Optional[str] = None,
    parameter: Optional[str] = None,
    description: Optional[str] = None,
    reproduction: Optional[str] = None,
    evidence: Optional[str] = None,
    remediation: Optional[str] = None,
    cvss_score: Optional[float] = None,
) -> dict:
    """同步：添加漏洞发现记录"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO vulnerabilities
        (project_id, vuln_id, title, severity, vuln_type, affected_url, parameter,
         description, reproduction, evidence, remediation, cvss_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, vuln_id, title, severity, vuln_type, affected_url, parameter,
         description, reproduction, evidence, remediation, cvss_score),
    )
    vuln_db_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "success": True,
        "vuln_db_id": vuln_db_id,
        "project_id": project_id,
        "vuln_id": vuln_id,
        "title": title,
        "severity": severity,
    }


def _storage_list_vulnerabilities(
    project_id: Optional[int] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """同步：查询漏洞发现记录"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    query = "SELECT * FROM vulnerabilities WHERE 1=1"
    params = []

    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY discovered_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    vulnerabilities = []
    for row in rows:
        vulnerabilities.append({
            "id": row[0],
            "project_id": row[1],
            "host_id": row[2],
            "vuln_id": row[3],
            "title": row[4],
            "severity": row[5],
            "vuln_type": row[6],
            "affected_url": row[7],
            "parameter": row[8],
            "description": row[9],
            "reproduction": row[10],
            "evidence": row[11],
            "remediation": row[12],
            "cvss_score": row[13],
            "status": row[14],
            "discovered_at": row[15],
        })

    return {
        "success": True,
        "total": len(vulnerabilities),
        "vulnerabilities": vulnerabilities,
    }


def _storage_update_vulnerability_status(vuln_id: str, status: str) -> dict:
    """同步：更新漏洞状态"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE vulnerabilities SET status = ? WHERE vuln_id = ?",
        (status, vuln_id),
    )
    conn.commit()
    updated = cursor.rowcount
    conn.close()

    return {
        "success": updated > 0,
        "vuln_id": vuln_id,
        "new_status": status,
        "updated_rows": updated,
    }


def _storage_save_scan_result(
    project_id: int,
    scan_type: str,
    target: str,
    tool: str,
    result_json: str,
    raw_output: Optional[str] = None,
) -> dict:
    """同步：保存扫描结果"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO scan_results (project_id, scan_type, target, tool, result_json, raw_output)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (project_id, scan_type, target, tool, result_json, raw_output),
    )
    scan_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "success": True,
        "scan_id": scan_id,
        "project_id": project_id,
        "scan_type": scan_type,
    }


def _storage_get_scan_results(
    project_id: Optional[int] = None,
    scan_type: Optional[str] = None,
) -> dict:
    """同步：获取扫描结果"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    query = "SELECT id, project_id, scan_type, target, tool, result_json, scan_time FROM scan_results WHERE 1=1"
    params = []

    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)
    if scan_type:
        query += " AND scan_type = ?"
        params.append(scan_type)

    query += " ORDER BY scan_time DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        try:
            parsed = json.loads(row[5])
        except Exception:
            parsed = row[5]

        results.append({
            "id": row[0],
            "project_id": row[1],
            "scan_type": row[2],
            "target": row[3],
            "tool": row[4],
            "result": parsed,
            "scan_time": row[6],
        })

    return {
        "success": True,
        "total": len(results),
        "scan_results": results,
    }


def _storage_save_report(
    project_id: int,
    report_type: str,
    format: str,
    file_path: str,
) -> dict:
    """同步：保存报告记录"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO reports (project_id, report_type, format, file_path) VALUES (?, ?, ?, ?)",
        (project_id, report_type, format, file_path),
    )
    report_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "success": True,
        "report_id": report_id,
        "project_id": project_id,
        "file_path": file_path,
    }


def _storage_get_statistics(project_id: int) -> dict:
    """同步：获取项目统计信息"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Vulnerability counts by severity
    cursor.execute(
        "SELECT severity, COUNT(*) FROM vulnerabilities WHERE project_id = ? GROUP BY severity",
        (project_id,),
    )
    severity_counts = {row[0]: row[1] for row in cursor.fetchall()}

    # Total scans
    cursor.execute(
        "SELECT COUNT(*) FROM scan_results WHERE project_id = ?",
        (project_id,),
    )
    total_scans = cursor.fetchone()[0]

    # Total reports
    cursor.execute(
        "SELECT COUNT(*) FROM reports WHERE project_id = ?",
        (project_id,),
    )
    total_reports = cursor.fetchone()[0]

    conn.close()

    return {
        "success": True,
        "project_id": project_id,
        "vulnerability_counts": severity_counts,
        "total_vulnerabilities": sum(severity_counts.values()),
        "total_scans": total_scans,
        "total_reports": total_reports,
    }


# ============================================================================
# 项目管理
# ============================================================================

@tool
async def storage_create_project(
    name: str,
    target: str,
    description: Optional[str] = None,
) -> str:
    """
    创建渗透测试项目

    Args:
        name: 项目名称
        target: 测试目标
        description: 项目描述（可选）

    Returns:
        JSON 格式的项目信息
    """
    result = await run_sync(_storage_create_project, name, target, description)
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
async def storage_list_projects() -> str:
    """
    列出所有渗透测试项目

    Returns:
        JSON 格式的项目列表
    """
    result = await run_sync(_storage_list_projects)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ============================================================================
# 漏洞管理
# ============================================================================

@tool
async def storage_add_vulnerability(
    project_id: int,
    vuln_id: str,
    title: str,
    severity: str,
    vuln_type: Optional[str] = None,
    affected_url: Optional[str] = None,
    parameter: Optional[str] = None,
    description: Optional[str] = None,
    reproduction: Optional[str] = None,
    evidence: Optional[str] = None,
    remediation: Optional[str] = None,
    cvss_score: Optional[float] = None,
) -> str:
    """
    添加漏洞发现记录

    Args:
        project_id: 项目 ID
        vuln_id: 漏洞编号（如 VL-001）
        title: 漏洞标题
        severity: 风险等级（Critical/High/Medium/Low/Info）
        vuln_type: 漏洞类型
        affected_url: 受影响 URL
        parameter: 受影响参数
        description: 漏洞描述
        reproduction: 复现步骤
        evidence: 证据
        remediation: 修复建议
        cvss_score: CVSS 评分

    Returns:
        JSON 格式的保存结果
    """
    result = await run_sync(
        _storage_add_vulnerability,
        project_id, vuln_id, title, severity,
        vuln_type, affected_url, parameter, description,
        reproduction, evidence, remediation, cvss_score,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
async def storage_list_vulnerabilities(
    project_id: Optional[int] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
) -> str:
    """
    查询漏洞发现记录

    Args:
        project_id: 项目 ID（可选）
        severity: 按风险等级过滤（可选）
        status: 按状态过滤（可选）

    Returns:
        JSON 格式的漏洞列表
    """
    result = await run_sync(_storage_list_vulnerabilities, project_id, severity, status)
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
async def storage_update_vulnerability_status(
    vuln_id: str,
    status: str,
) -> str:
    """
    更新漏洞状态

    Args:
        vuln_id: 漏洞编号（如 VL-001）
        status: 新状态（open/fixed/accepted/false_positive）

    Returns:
        JSON 格式的更新结果
    """
    result = await run_sync(_storage_update_vulnerability_status, vuln_id, status)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ============================================================================
# 扫描结果管理
# ============================================================================

@tool
async def storage_save_scan_result(
    project_id: int,
    scan_type: str,
    target: str,
    tool: str,
    result_json: str,
    raw_output: Optional[str] = None,
) -> str:
    """
    保存扫描结果

    Args:
        project_id: 项目 ID
        scan_type: 扫描类型（portscan/subdomain/dirscan/etc）
        target: 扫描目标
        tool: 使用的工具
        result_json: JSON 格式的扫描结果
        raw_output: 原始输出（可选）

    Returns:
        JSON 格式的保存结果
    """
    result = await run_sync(
        _storage_save_scan_result,
        project_id, scan_type, target, tool, result_json, raw_output,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
async def storage_get_scan_results(
    project_id: Optional[int] = None,
    scan_type: Optional[str] = None,
) -> str:
    """
    获取扫描结果

    Args:
        project_id: 项目 ID（可选）
        scan_type: 扫描类型过滤（可选）

    Returns:
        JSON 格式的扫描结果列表
    """
    result = await run_sync(_storage_get_scan_results, project_id, scan_type)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ============================================================================
# 报告管理
# ============================================================================

@tool
async def storage_save_report(
    project_id: int,
    report_type: str,
    format: str,
    file_path: str,
) -> str:
    """
    保存报告记录

    Args:
        project_id: 项目 ID
        report_type: 报告类型（full/executive/technical）
        format: 格式（markdown/json/pdf）
        file_path: 报告文件路径

    Returns:
        JSON 格式的保存结果
    """
    result = await run_sync(_storage_save_report, project_id, report_type, format, file_path)
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
async def storage_get_statistics(project_id: int) -> str:
    """
    获取项目统计信息

    Args:
        project_id: 项目 ID

    Returns:
        JSON 格式的统计信息
    """
    result = await run_sync(_storage_get_statistics, project_id)
    return json.dumps(result, ensure_ascii=False, indent=2)
