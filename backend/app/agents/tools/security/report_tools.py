"""
渗透测试 - 报告生成工具模块

提供专业的渗透测试报告生成功能，支持 Markdown、JSON 格式，
并可通过 MCP Chart Server 生成数据可视化图表。
"""

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.utils.sync_executor import run_sync

from langchain_core.tools import tool

from app.config.settings import settings
from app.config.minio_client import MinIOClient

# Windows 下 subprocess 默认编码为 gbk，MCP server (npx) 输出可能包含非 ASCII 字符，
# 需强制使用 utf-8 以避免 UnicodeDecodeError。
if os.name == "nt":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjJsbFZRPT06NzdmZGIzZjU=

SECURITY_WORKSPACE = Path(settings.api_workspace_root).resolve().parent / "workspace" / "security"
SECURITY_WORKSPACE.mkdir(parents=True, exist_ok=True)

REPORT_TEMPLATE = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / ".claude" / "skills" / "security" / "templates" / "pentest_report_template.md"


def _safe_filename(name: str) -> str:
    """生成安全的文件名（只保留 ASCII 字母数字、下划线和连字符）"""
    safe = re.sub(r'[^\w\-]', '_', name)
    safe = re.sub(r'_+', '_', safe)
    return safe.strip('_')


def _upload_report_to_minio(content: str, object_name: str, content_type: str ="text/html") -> str:
    """将报告内容上传到 MinIO，返回 object_name"""
    data = content.encode("utf-8")
    MinIOClient.upload_bytes(
        object_name=object_name,
        data=data,
        content_type=content_type,
    )
    return object_name


# ============================================================================
# 报告生成
# ============================================================================

@tool
async def generate_pentest_report(
    project_name: str,
    target: str,
    findings: List[Dict[str, Any]],
    tester_name: str = "AI 渗透测试智能体",
    output_format: str = "markdown",
    include_charts: bool = True,
    output_file: Optional[str] = None,
) -> str:
    """
    生成专业的渗透测试报告

    根据漏洞发现结果生成标准化的渗透测试报告，支持 Markdown 和 JSON 格式，
    并可生成风险分布图表。

    Args:
        project_name: 项目名称
        target: 测试目标（URL/IP）
        findings: 漏洞发现列表，每项应包含：
            - id: 漏洞编号（如 VL-001）
            - title: 漏洞标题
            - severity: 风险等级（Critical/High/Medium/Low/Info）
            - type: 漏洞类型
            - url: 受影响 URL
            - parameter: 受影响参数
            - description: 漏洞描述
            - reproduction: 复现步骤
            - evidence: 证据
            - remediation: 修复建议
        tester_name: 测试人员名称
        output_format: 输出格式，markdown 或 json
        include_charts: 是否包含图表（通过 MCP Chart Server 生成）
        output_file: MinIO 对象名称覆盖（可选，默认自动生成）

    Returns:
        JSON 格式的报告生成结果，包含以下字段：
        - success: 是否成功
        - object_name: MinIO 对象路径（如 "pentest/reports/20250604_120000_xxx.md"）
        - content: 报告完整内容
        - format: 报告格式
        - total_vulnerabilities: 漏洞总数
        - risk_score: 风险评分
        - severity_distribution: 风险等级分布统计

    **重要：** 返回结果中的 `object_name` 必须传给 `mgmt_save_pentest_report` 的 `file_path` 参数，
    才能在前端正确显示和下载报告。

    Example:
        >>> findings = [
        ...     {
        ...         "id": "VL-001",
        ...         "title": "SQL 注入漏洞",
        ...         "severity": "Critical",
        ...         "type": "SQL Injection",
        ...         "url": "https://example.com/search",
        ...         "parameter": "q",
        ...         "description": "搜索参数存在 SQL 注入",
        ...         "reproduction": "1. 访问 URL\n2. 输入 ' OR '1'='1",
        ...         "evidence": "页面返回所有数据",
        ...         "remediation": "使用参数化查询"
        ...     }
        ... ]
        >>> result = await generate_pentest_report(
        ...     project_name="客户系统安全评估",
        ...     target="https://example.com",
        ...     findings=findings
        ... )
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_time = datetime.now().strftime("%Y-%m-%d")

    # Calculate statistics
    severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    severity_scores = {"Critical": 9.5, "High": 8.0, "Medium": 5.5, "Low": 2.0, "Info": 0.0}

    for finding in findings:
        sev = finding.get("severity", "Info")
        if sev in severity_counts:
            severity_counts[sev] += 1

    total_vulns = sum(severity_counts.values())
    risk_score = sum(severity_counts[s] * severity_scores[s] for s in severity_counts) / max(total_vulns, 1)

    # Generate chart data for MCP Chart Server
    chart_files = []
    if include_charts:
        chart_files = await _generate_charts(severity_counts, project_name, timestamp)

    ext = "md" if output_format == "markdown" else "json"
    safe_name = _safe_filename(project_name)
    object_name = f"pentest/reports/{timestamp}_{safe_name}.{ext}"

    if output_format == "json":
        report_data = {
            "project_info": {
                "project_name": project_name,
                "target": target,
                "test_date": report_time,
                "tester": tester_name,
            },
            "summary": {
                "total_vulnerabilities": total_vulns,
                "risk_score": round(risk_score, 1),
                "severity_distribution": severity_counts,
            },
            "findings": findings,
            "charts": chart_files,
        }
        content = json.dumps(report_data, ensure_ascii=False, indent=2)
        content_type = "application/json"
    else:
        # Markdown format
        content = _generate_markdown_report(
            project_name=project_name,
            target=target,
            report_time=report_time,
            tester_name=tester_name,
            findings=findings,
            severity_counts=severity_counts,
            risk_score=risk_score,
            chart_files=chart_files,
        )
        content_type = "text/markdown"

    # Upload to MinIO
    await run_sync(_upload_report_to_minio, content, object_name, content_type)

    return json.dumps({
        "success": True,
        "project": project_name,
        "target": target,
        "total_vulnerabilities": total_vulns,
        "risk_score": round(risk_score, 1),
        "severity_distribution": severity_counts,
        "object_name": object_name,
        "content": content,
        "charts": chart_files,
        "format": output_format,
    }, ensure_ascii=False, indent=2)


async def _generate_charts(severity_counts: Dict[str, int], project_name: str, timestamp: str) -> List[str]:
    """
    通过 MCP Chart Server 生成图表

    生成风险分布饼图和柱状图，保存为图片文件。
    图表使用 AntV 规范，通过 MCP Server 渲染。
    """
    chart_files = []
    charts_dir = SECURITY_WORKSPACE / f"charts_{timestamp}"
    await run_sync(charts_dir.mkdir, parents=True, exist_ok=True)
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjJsbFZRPT06NzdmZGIzZjU=

    # Since MCP Chart Server integration requires async tool call,
    # we prepare chart spec files that can be rendered later.
    # The actual rendering will be done by the agent using MCP tools.

    # Pie chart spec (AntV G2Plot)
    pie_spec = {
        "type": "pie",
        "title": f"{project_name} - 风险等级分布",
        "data": [
            {"type": "严重", "value": severity_counts["Critical"]},
            {"type": "高危", "value": severity_counts["High"]},
            {"type": "中危", "value": severity_counts["Medium"]},
            {"type": "低危", "value": severity_counts["Low"]},
            {"type": "信息", "value": severity_counts["Info"]},
        ],
        "colorField": "type",
        "angleField": "value",
        "color": ["#ff4d4f", "#faad14", "#fa8c16", "#1890ff", "#d9d9d9"],
        "radius": 0.8,
        "label": {"type": "outer"},
        "legend": {"position": "bottom"},
    }

    pie_path = charts_dir / "severity_pie.json"
    await run_sync(
        pie_path.write_text,
        json.dumps(pie_spec, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    chart_files.append(str(pie_path))

    # Bar chart spec (AntV G2Plot)
    bar_spec = {
        "type": "column",
        "title": f"{project_name} - 漏洞数量统计",
        "data": [
            {"severity": "严重", "count": severity_counts["Critical"]},
            {"severity": "高危", "count": severity_counts["High"]},
            {"severity": "中危", "count": severity_counts["Medium"]},
            {"severity": "低危", "count": severity_counts["Low"]},
            {"severity": "信息", "count": severity_counts["Info"]},
        ],
        "xField": "severity",
        "yField": "count",
        "colorField": "severity",
        "color": ["#ff4d4f", "#faad14", "#fa8c16", "#1890ff", "#d9d9d9"],
        "label": {"position": "top"},
        "columnStyle": {"radius": [4, 4, 0, 0]},
    }

    bar_path = charts_dir / "severity_bar.json"
    await run_sync(
        bar_path.write_text,
        json.dumps(bar_spec, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    chart_files.append(str(bar_path))

    # CVSS score distribution (if available)
    line_spec = {
        "type": "line",
        "title": f"{project_name} - 漏洞趋势",
        "data": [
            {"phase": "信息收集", "count": sum(severity_counts.values())},
            {"phase": "漏洞扫描", "count": severity_counts["Critical"] + severity_counts["High"]},
            {"phase": "漏洞验证", "count": severity_counts["Critical"]},
        ],
        "xField": "phase",
        "yField": "count",
        "point": {"size": 5, "shape": "diamond"},
        "label": {},
    }

    line_path = charts_dir / "trend_line.json"
    await run_sync(
        line_path.write_text,
        json.dumps(line_spec, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    chart_files.append(str(line_path))

    return chart_files


def _generate_markdown_report(
    project_name: str,
    target: str,
    report_time: str,
    tester_name: str,
    findings: List[Dict[str, Any]],
    severity_counts: Dict[str, int],
    risk_score: float,
    chart_files: List[str],
) -> str:
    """生成 Markdown 格式的渗透测试报告"""

    md = f"""# 渗透测试报告：{project_name}

| 项目信息 | 内容 |
| :--- | :--- |
| **测试目标** | {target} |
| **测试时间** | {report_time} |
| **测试人员** | {tester_name} |
| **报告日期** | {report_time} |

---

## 执行摘要 (Executive Summary)

本次渗透测试共发现 **{sum(severity_counts.values())}** 个安全漏洞，综合风险评分为 **{risk_score:.1f}/10**。

| 风险等级 | 数量 | 状态 |
| :--- | :--- | :--- |
| 🔴 **严重 (Critical)** | {severity_counts["Critical"]} | 需立即修复 |
| 🟠 **高危 (High)** | {severity_counts["High"]} | 需尽快修复 |
| 🟡 **中危 (Medium)** | {severity_counts["Medium"]} | 建议修复 |
| 🔵 **低危 (Low)** | {severity_counts["Low"]} | 接受风险/建议修复 |
| ⚪ **信息 (Info)** | {severity_counts["Info"]} | 关注 |

"""

    # Add chart references
    if chart_files:
        md += "\n### 风险分布图表\n\n"
        for chart in chart_files:
            md += f"- 图表文件: `{chart}`\n"
        md += "\n> 图表可通过 AntV MCP Chart Server 渲染为可视化图片。\n"

    md += """
---

## 漏洞发现清单 (Vulnerability Summary)

| ID | 漏洞标题 | 风险等级 | 类型 | 状态 |
| :--- | :--- | :--- | :--- | :--- |
"""

    severity_icons = {
        "Critical": "🔴 严重",
        "High": "🟠 高危",
        "Medium": "🟡 中危",
        "Low": "🔵 低危",
        "Info": "⚪ 信息",
    }

    for finding in findings:
        sev = finding.get("severity", "Info")
        md += f"| **{finding.get('id', 'N/A')}** | {finding.get('title', 'N/A')} | {severity_icons.get(sev, sev)} | {finding.get('type', 'N/A')} | 未修复 |\n"

    md += """
---

## 漏洞详情 (Detailed Findings)

"""

    for finding in findings:
        sev = finding.get("severity", "Info")
        md += f"""### [{finding.get('id', 'N/A')}] {finding.get('title', 'N/A')}

| 属性 | 详情 |
| :--- | :--- |
| **风险等级** | {severity_icons.get(sev, sev)} |
| **CVSS 评分** | {finding.get('cvss', '待评估')} |
| **漏洞类型** | {finding.get('type', 'N/A')} |
| **受影响 URL** | `{finding.get('url', 'N/A')}` |
| **参数** | `{finding.get('parameter', 'N/A')}` |

#### 漏洞描述
{finding.get('description', '暂无描述')}

#### 复现步骤 (Proof of Concept)
{finding.get('reproduction', '暂无复现步骤')}

#### 证据
```
{finding.get('evidence', '暂无证据')}
```

#### 修复建议
{finding.get('remediation', '暂无修复建议')}

---

"""

    md += """## 附录 (Appendix)

### 风险等级定义

| 等级 | CVSS 范围 | 描述 |
| :--- | :--- | :--- |
| 🔴 **严重** | 9.0 - 10.0 | 可直接获取服务器权限、核心数据泄露，或导致核心业务中断。需立即修复。 |
| 🟠 **高危** | 7.0 - 8.9 | 可获取敏感数据、越权操作，利用难度较低。需尽快修复。 |
| 🟡 **中危** | 4.0 - 6.9 | 需特定交互或条件方可利用，造成局部影响。建议修复。 |
| 🔵 **低危** | 0.1 - 3.9 | 利用难度极高或影响轻微，建议修复以增强纵深防御。 |
| ⚪ **信息** | 0.0 | 信息泄露问题，不影响系统安全，但需关注。 |

### 测试工具参考

| 工具 | 用途 |
| :--- | :--- |
| nmap | 端口扫描与服务识别 |
| subfinder | 子域名枚举 |
| ffuf | 目录扫描与模糊测试 |
| sqlmap | SQL 注入检测 |
| dalfox | XSS 漏洞检测 |
| httpx | Web 指纹识别 |
| wafw00f | WAF 检测 |

---

## 免责声明

本报告仅用于授权的安全测试和内部安全改进目的。未经授权使用本报告中的技术进行攻击是非法的。

---

**报告结束**
"""

    return md

# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjJsbFZRPT06NzdmZGIzZjU=

@tool
async def generate_executive_summary(
    project_name: str,
    target: str,
    findings: List[Dict[str, Any]],
    output_file: Optional[str] = None,
) -> str:
    """
    生成执行摘要（Executive Summary）

    为管理层生成简洁的风险概览，包含关键指标和建议。

    Args:
        project_name: 项目名称
        target: 测试目标
        findings: 漏洞发现列表
        output_file: 输出文件路径（可选）

    Returns:
        JSON 格式的执行摘要，包含以下字段：
        - project: 项目名称
        - target: 测试目标
        - overall_risk: 整体风险等级
        - risk_score: 风险评分
        - key_numbers: 关键统计数据
        - priority_actions: 优先修复建议
        - top_vulnerabilities:  Top 漏洞列表
        - object_name: MinIO 对象路径（当提供了 output_file 时）

    **重要：** 若返回中包含 `object_name`，必须将其传给 `mgmt_save_pentest_report` 的 `file_path` 参数。
    """
    severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    severity_scores = {"Critical": 9.5, "High": 8.0, "Medium": 5.5, "Low": 2.0, "Info": 0.0}

    for finding in findings:
        sev = finding.get("severity", "Info")
        if sev in severity_counts:
            severity_counts[sev] += 1

    total = sum(severity_counts.values())
    risk_score = sum(severity_counts[s] * severity_scores[s] for s in severity_counts) / max(total, 1)

    # Priority actions
    priority_actions = []
    if severity_counts["Critical"] > 0:
        priority_actions.append(f"立即修复 {severity_counts['Critical']} 个严重漏洞")
    if severity_counts["High"] > 0:
        priority_actions.append(f"尽快修复 {severity_counts['High']} 个高危漏洞")
    if severity_counts["Medium"] > 0:
        priority_actions.append(f"计划修复 {severity_counts['Medium']} 个中危漏洞")

    summary = {
        "project": project_name,
        "target": target,
        "overall_risk": "极高" if risk_score >= 9 else "高" if risk_score >= 7 else "中" if risk_score >= 4 else "低",
        "risk_score": round(risk_score, 1),
        "key_numbers": {
            "total_vulnerabilities": total,
            "critical": severity_counts["Critical"],
            "high": severity_counts["High"],
            "medium": severity_counts["Medium"],
            "low": severity_counts["Low"],
        },
        "priority_actions": priority_actions,
        "top_vulnerabilities": [
            {
                "id": f["id"],
                "title": f["title"],
                "severity": f["severity"],
            }
            for f in findings[:5]
        ],
    }

    content = json.dumps(summary, ensure_ascii=False, indent=2)

    if output_file:
        safe_name = _safe_filename(project_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        object_name = f"pentest/reports/{timestamp}_{safe_name}_summary.json"
        await run_sync(_upload_report_to_minio, content, object_name, "application/json")
        summary["object_name"] = object_name

    return json.dumps(summary, ensure_ascii=False, indent=2)


# ============================================================================
# HTML 报告生成（含 MCP 图表）
# ============================================================================

async def _render_charts_via_mcp(
    severity_counts: Dict[str, int], project_name: str
) -> Dict[str, str]:
    """
    通过 MCP Chart Server 渲染图表，返回 {chart_name: base64_image_data}。

    若 MCP 不可用或调用失败，返回空字典，由调用方回退到 CSS 图表。
    整个过程有 20 秒超时，避免 npx 启动卡住导致系统无响应。
    """
    import asyncio

    charts: Dict[str, str] = {}

    async def _do_render() -> Dict[str, str]:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        async with MultiServerMCPClient(
            {
                "chart": {
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@antv/mcp-server-chart"],
                },
            }
        ) as client:
            tools = await client.get_tools()
            tool_map = {t.name: t for t in tools}

            # 颜色配置
            colors = ["#ff4d4f", "#faad14", "#fa8c16", "#1890ff", "#d9d9d9"]
            severity_labels = ["严重", "高危", "中危", "低危", "信息"]
            severity_keys = ["Critical", "High", "Medium", "Low", "Info"]
            result: Dict[str, str] = {}

            # Pie chart
            pie_data = [
                {"type": label, "value": severity_counts[key]}
                for label, key in zip(severity_labels, severity_keys)
            ]
            pie_spec = {
                "type": "pie",
                "title": f"{project_name} - 风险等级分布",
                "data": pie_data,
                "colorField": "type",
                "angleField": "value",
                "color": colors,
                "radius": 0.8,
                "label": {"type": "outer"},
                "legend": {"position": "bottom"},
            }
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjJsbFZRPT06NzdmZGIzZjU=

            pie_result = None
            for tool_name in ["render_chart", "generate_chart", "chart", "pie"]:
                if tool_name in tool_map:
                    try:
                        pie_result = await asyncio.wait_for(
                            tool_map[tool_name].ainvoke({"type": "pie", "spec": pie_spec}),
                            timeout=8,
                        )
                        break
                    except Exception:
                        continue

            if pie_result:
                result["pie"] = _extract_image_data(pie_result)

            # Bar/Column chart
            bar_data = [
                {"severity": label, "count": severity_counts[key]}
                for label, key in zip(severity_labels, severity_keys)
            ]
            bar_spec = {
                "type": "column",
                "title": f"{project_name} - 漏洞数量统计",
                "data": bar_data,
                "xField": "severity",
                "yField": "count",
                "colorField": "severity",
                "color": colors,
                "label": {"position": "top"},
                "columnStyle": {"radius": [4, 4, 0, 0]},
            }

            bar_result = None
            for tool_name in ["render_chart", "generate_chart", "chart", "column", "bar"]:
                if tool_name in tool_map:
                    try:
                        bar_result = await asyncio.wait_for(
                            tool_map[tool_name].ainvoke({"type": "column", "spec": bar_spec}),
                            timeout=8,
                        )
                        break
                    except Exception:
                        continue

            if bar_result:
                result["bar"] = _extract_image_data(bar_result)

            return result

    try:
        charts = await asyncio.wait_for(_do_render(), timeout=20)
    except asyncio.TimeoutError:
        print("[report_tools] MCP chart rendering timed out, falling back to CSS charts")
        charts = {}
    except Exception as e:
        print(f"[report_tools] MCP chart rendering skipped: {e}")
        charts = {}

    return charts


def _extract_image_data(result: Any) -> str:
    """从 MCP 工具返回结果中提取图片数据（支持 base64、SVG、文件路径）。"""
    if isinstance(result, str):
        # 可能是 base64 字符串、SVG、文件路径或 JSON 字符串
        result = result.strip()
        if result.startswith("data:image"):
            return result
        if result.startswith("<") and "svg" in result.lower():
            # SVG 字符串，转成 base64 data URL
            import base64
            b64 = base64.b64encode(result.encode("utf-8")).decode("utf-8")
            return f"data:image/svg+xml;base64,{b64}"
        if result.startswith("{"):
            try:
                data = json.loads(result)
                return _extract_image_data(data)
            except json.JSONDecodeError:
                pass
        # 可能是文件路径
        p = Path(result)
        if p.exists():
            import base64
            suffix = p.suffix.lower()
            mime = "image/png" if suffix == ".png" else "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/svg+xml" if suffix == ".svg" else "image/png"
            b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
            return f"data:{mime};base64,{b64}"
        # 尝试直接作为 base64
        if len(result) > 100 and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in result[:100]):
            return f"data:image/png;base64,{result}"
        return result

    if isinstance(result, dict):
        # 尝试常见的字段名
        for key in ("image", "data", "base64", "content", "result", "svg", "png", "url"):
            if key in result:
                return _extract_image_data(result[key])
    return ""


def _generate_css_pie_chart(severity_counts: Dict[str, int]) -> str:
    """生成纯 CSS 饼图（MCP 不可用时回退）。"""
    total = sum(severity_counts.values())
    if total == 0:
        return '<div style="text-align:center;padding:20px;color:#999">暂无数据</div>'

    colors = {"Critical": "#ff4d4f", "High": "#faad14", "Medium": "#fa8c16", "Low": "#1890ff", "Info": "#d9d9d9"}
    labels = {"Critical": "严重", "High": "高危", "Medium": "中危", "Low": "低危", "Info": "信息"}

    items_html = ""
    for key in ["Critical", "High", "Medium", "Low", "Info"]:
        count = severity_counts[key]
        if count > 0:
            pct = count / total * 100
            items_html += f'<div style="display:flex;align-items:center;margin:4px 0;font-size:13px"><span style="width:12px;height:12px;border-radius:2px;background:{colors[key]};margin-right:8px;display:inline-block"></span><span style="flex:1">{labels[key]}</span><span style="font-weight:600">{count}</span><span style="color:#999;margin-left:4px">({pct:.1f}%)</span></div>'

    return f'<div style="padding:16px">{items_html}</div>'


def _generate_css_bar_chart(severity_counts: Dict[str, int]) -> str:
    """生成纯 CSS 柱状图（MCP 不可用时回退）。"""
    total = sum(severity_counts.values())
    if total == 0:
        return '<div style="text-align:center;padding:20px;color:#999">暂无数据</div>'

    colors = {"Critical": "#ff4d4f", "High": "#faad14", "Medium": "#fa8c16", "Low": "#1890ff", "Info": "#d9d9d9"}
    labels = {"Critical": "严重", "High": "高危", "Medium": "中危", "Low": "低危", "Info": "信息"}
    max_count = max(severity_counts.values()) or 1

    bars_html = ""
    for key in ["Critical", "High", "Medium", "Low", "Info"]:
        count = severity_counts[key]
        width = (count / max_count) * 100
        bars_html += f'''<div style="display:flex;align-items:center;margin:6px 0">
            <div style="width:50px;font-size:13px;text-align:right;padding-right:10px">{labels[key]}</div>
            <div style="flex:1;background:#f0f0f0;border-radius:4px;height:24px;overflow:hidden">
                <div style="width:{width:.1f}%;height:100%;background:{colors[key]};border-radius:4px;display:flex;align-items:center;justify-content:flex-end;padding-right:8px;color:#fff;font-size:12px;font-weight:600">{count}</div>
            </div>
        </div>'''

    return f'<div style="padding:16px">{bars_html}</div>'


def _generate_html_report_content(
    project_name: str,
    target: str,
    report_time: str,
    tester_name: str,
    findings: List[Dict[str, Any]],
    severity_counts: Dict[str, int],
    risk_score: float,
    chart_images: Dict[str, str],
) -> str:
    """生成完整 HTML 报告内容。"""
    total = sum(severity_counts.values())
    colors = {"Critical": "#ff4d4f", "High": "#faad14", "Medium": "#fa8c16", "Low": "#1890ff", "Info": "#d9d9d9"}
    labels = {"Critical": "严重", "High": "高危", "Medium": "中危", "Low": "低危", "Info": "信息"}
    severity_icons = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🔵", "Info": "⚪"}
    risk_level = "极高" if risk_score >= 9 else "高" if risk_score >= 7 else "中" if risk_score >= 4 else "低"
    risk_color = "#ff4d4f" if risk_score >= 9 else "#faad14" if risk_score >= 7 else "#fa8c16" if risk_score >= 4 else "#1890ff"

    # 图表区域
    pie_chart_html = ""
    if chart_images.get("pie"):
        pie_chart_html = f'<img src="{chart_images["pie"]}" style="max-width:100%;height:auto" alt="风险等级分布" />'
    else:
        pie_chart_html = _generate_css_pie_chart(severity_counts)

    bar_chart_html = ""
    if chart_images.get("bar"):
        bar_chart_html = f'<img src="{chart_images["bar"]}" style="max-width:100%;height:auto" alt="漏洞数量统计" />'
    else:
        bar_chart_html = _generate_css_bar_chart(severity_counts)

    # 漏洞汇总行
    vuln_rows = ""
    for finding in findings:
        sev = finding.get("severity", "Info")
        vuln_rows += f'''<tr>
            <td style="padding:10px;border-bottom:1px solid #e8e8e8;font-weight:600">{finding.get("id", "N/A")}</td>
            <td style="padding:10px;border-bottom:1px solid #e8e8e8">{finding.get("title", "N/A")}</td>
            <td style="padding:10px;border-bottom:1px solid #e8e8e8"><span style="color:{colors.get(sev, "#999")};font-weight:600">{severity_icons.get(sev, "")} {labels.get(sev, sev)}</span></td>
            <td style="padding:10px;border-bottom:1px solid #e8e8e8">{finding.get("type", "N/A")}</td>
            <td style="padding:10px;border-bottom:1px solid #e8e8e8"><span style="display:inline-block;padding:2px 8px;border-radius:12px;background:{colors.get(sev, "#999")}20;color:{colors.get(sev, "#999")};font-size:12px">未修复</span></td>
        </tr>'''

    # 漏洞详情卡片
    vuln_cards = ""
    for finding in findings:
        sev = finding.get("severity", "Info")
        cvss = finding.get("cvss", "待评估")
        vuln_cards += f'''<div style="margin-bottom:24px;padding:20px;background:#fff;border-radius:8px;border:1px solid #e8e8e8">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
                <span style="display:inline-block;padding:4px 12px;border-radius:4px;background:{colors.get(sev, "#999")};color:#fff;font-size:12px;font-weight:600">{finding.get("id", "N/A")}</span>
                <h3 style="margin:0;font-size:18px">{finding.get("title", "N/A")}</h3>
            </div>
            <table style="width:100%;border-collapse:collapse;margin-bottom:16px;font-size:14px">
                <tr><td style="padding:6px 0;color:#666;width:100px">风险等级</td><td style="padding:6px 0;font-weight:600;color:{colors.get(sev, "#999")}">{severity_icons.get(sev, "")} {labels.get(sev, sev)}</td></tr>
                <tr><td style="padding:6px 0;color:#666">CVSS 评分</td><td style="padding:6px 0">{cvss}</td></tr>
                <tr><td style="padding:6px 0;color:#666">漏洞类型</td><td style="padding:6px 0">{finding.get("type", "N/A")}</td></tr>
                <tr><td style="padding:6px 0;color:#666">受影响 URL</td><td style="padding:6px 0;font-family:monospace;font-size:13px;word-break:break-all">{finding.get("url", "N/A")}</td></tr>
                <tr><td style="padding:6px 0;color:#666">参数</td><td style="padding:6px 0;font-family:monospace;font-size:13px">{finding.get("parameter", "N/A")}</td></tr>
            </table>
            <div style="margin-bottom:16px">
                <div style="font-weight:600;color:#333;margin-bottom:6px;font-size:14px">漏洞描述</div>
                <div style="color:#555;line-height:1.6;font-size:14px">{finding.get("description", "暂无描述")}</div>
            </div>
            <div style="margin-bottom:16px">
                <div style="font-weight:600;color:#333;margin-bottom:6px;font-size:14px">复现步骤 (PoC)</div>
                <div style="background:#f6f8fa;padding:12px;border-radius:6px;font-size:13px;line-height:1.6;white-space:pre-wrap;word-break:break-all">{finding.get("reproduction", "暂无复现步骤")}</div>
            </div>
            <div style="margin-bottom:16px">
                <div style="font-weight:600;color:#333;margin-bottom:6px;font-size:14px">证据</div>
                <pre style="background:#f6f8fa;padding:12px;border-radius:6px;font-size:13px;overflow:auto;max-height:300px;margin:0">{finding.get("evidence", "暂无证据")}</pre>
            </div>
            <div>
                <div style="font-weight:600;color:#333;margin-bottom:6px;font-size:14px">修复建议</div>
                <div style="background:#e6f7ff;padding:12px;border-radius:6px;border-left:4px solid #1890ff;font-size:14px;line-height:1.6">{finding.get("remediation", "暂无修复建议")}</div>
            </div>
        </div>'''

    # 统计卡片
    stat_cards = ""
    for key in ["Critical", "High", "Medium", "Low", "Info"]:
        stat_cards += f'''<div style="flex:1;min-width:100px;text-align:center;padding:16px;background:#fff;border-radius:8px;border:1px solid #e8e8e8">
            <div style="font-size:28px;font-weight:700;color:{colors[key]}">{severity_counts[key]}</div>
            <div style="font-size:13px;color:#666;margin-top:4px">{labels[key]}</div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>渗透测试报告 - {project_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; color: #333; line-height: 1.6; }}
        .container {{ max-width: 960px; margin: 0 auto; padding: 24px; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; padding: 40px 24px; border-radius: 12px; margin-bottom: 24px; }}
        .header h1 {{ margin: 0 0 8px 0; font-size: 28px; }}
        .header .meta {{ color: #a0a0a0; font-size: 14px; }}
        .header .meta span {{ margin-right: 20px; }}
        .card {{ background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 24px; border: 1px solid #e8e8e8; }}
        .card h2 {{ margin: 0 0 16px 0; font-size: 20px; color: #1a1a2e; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px; }}
        .risk-badge {{ display: inline-block; padding: 6px 16px; border-radius: 20px; font-size: 14px; font-weight: 600; color: #fff; background: {risk_color}; }}
        .stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }}
        .chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
        @media (max-width: 768px) {{ .chart-grid {{ grid-template-columns: 1fr; }} }}
        table.summary {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        table.summary th {{ text-align: left; padding: 10px; background: #f6f8fa; font-weight: 600; border-bottom: 2px solid #e8e8e8; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; padding: 24px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>渗透测试报告</h1>
            <div class="meta">
                <span>项目: {project_name}</span>
                <span>目标: {target}</span>
                <span>日期: {report_time}</span>
                <span>测试人员: {tester_name}</span>
            </div>
        </div>

        <div class="card">
            <h2>执行摘要</h2>
            <p style="font-size:15px;color:#555;margin-bottom:16px">
                本次渗透测试共发现 <strong style="color:#ff4d4f">{total}</strong> 个安全漏洞，
                综合风险评分为 <strong>{risk_score:.1f}/10</strong>，
                风险等级为 <span class="risk-badge">{risk_level}</span>。
            </p>
            <div class="stats">{stat_cards}</div>
        </div>

        <div class="card">
            <h2>风险分布图表</h2>
            <div class="chart-grid">
                <div>
                    <div style="font-weight:600;margin-bottom:8px;font-size:14px;color:#666;text-align:center">风险等级分布</div>
                    {pie_chart_html}
                </div>
                <div>
                    <div style="font-weight:600;margin-bottom:8px;font-size:14px;color:#666;text-align:center">漏洞数量统计</div>
                    {bar_chart_html}
                </div>
            </div>
        </div>

        <div class="card">
            <h2>漏洞发现清单</h2>
            <table class="summary">
                <tr>
                    <th>ID</th>
                    <th>漏洞标题</th>
                    <th>风险等级</th>
                    <th>类型</th>
                    <th>状态</th>
                </tr>
                {vuln_rows}
            </table>
        </div>

        <div class="card">
            <h2>漏洞详情</h2>
            {vuln_cards}
        </div>

        <div class="card">
            <h2>附录</h2>
            <h3 style="font-size:16px;margin:16px 0 8px">风险等级定义</h3>
            <table class="summary">
                <tr><th style="width:80px">等级</th><th style="width:100px">CVSS 范围</th><th>描述</th></tr>
                <tr><td style="padding:8px"><span style="color:#ff4d4f;font-weight:600">严重</span></td><td style="padding:8px">9.0 - 10.0</td><td style="padding:8px">可直接获取服务器权限、核心数据泄露，或导致核心业务中断。需立即修复。</td></tr>
                <tr><td style="padding:8px"><span style="color:#faad14;font-weight:600">高危</span></td><td style="padding:8px">7.0 - 8.9</td><td style="padding:8px">可获取敏感数据、越权操作，利用难度较低。需尽快修复。</td></tr>
                <tr><td style="padding:8px"><span style="color:#fa8c16;font-weight:600">中危</span></td><td style="padding:8px">4.0 - 6.9</td><td style="padding:8px">需特定交互或条件方可利用，造成局部影响。建议修复。</td></tr>
                <tr><td style="padding:8px"><span style="color:#1890ff;font-weight:600">低危</span></td><td style="padding:8px">0.1 - 3.9</td><td style="padding:8px">利用难度极高或影响轻微，建议修复以增强纵深防御。</td></tr>
                <tr><td style="padding:8px"><span style="color:#999;font-weight:600">信息</span></td><td style="padding:8px">0.0</td><td style="padding:8px">信息泄露问题，不影响系统安全，但需关注。</td></tr>
            </table>
            <h3 style="font-size:16px;margin:16px 0 8px">测试工具参考</h3>
            <table class="summary">
                <tr><th style="width:120px">工具</th><th>用途</th></tr>
                <tr><td style="padding:8px">nmap</td><td style="padding:8px">端口扫描与服务识别</td></tr>
                <tr><td style="padding:8px">subfinder</td><td style="padding:8px">子域名枚举</td></tr>
                <tr><td style="padding:8px">ffuf</td><td style="padding:8px">目录扫描与模糊测试</td></tr>
                <tr><td style="padding:8px">sqlmap</td><td style="padding:8px">SQL 注入检测</td></tr>
                <tr><td style="padding:8px">dalfox</td><td style="padding:8px">XSS 漏洞检测</td></tr>
                <tr><td style="padding:8px">httpx</td><td style="padding:8px">Web 指纹识别</td></tr>
                <tr><td style="padding:8px">wafw00f</td><td style="padding:8px">WAF 检测</td></tr>
            </table>
        </div>

        <div class="footer">
            <p>本报告仅用于授权的安全测试和内部安全改进目的。未经授权使用本报告中的技术进行攻击是非法的。</p>
            <p>报告生成时间: {report_time} | AI 渗透测试智能体</p>
        </div>
    </div>
</body>
</html>'''
    return html


@tool
async def generate_html_pentest_report(
    project_name: str,
    target: str,
    findings: List[Dict[str, Any]],
    tester_name: str = "AI 渗透测试智能体",
    output_file: Optional[str] = None,
) -> str:
    """
    生成图文并茂的 HTML 渗透测试报告

    自动调用 MCP Chart Server 渲染风险分布图表，生成内嵌图表的完整 HTML 报告。
    若 MCP 不可用，会自动回退到纯 CSS 图表。

    Args:
        project_name: 项目名称
        target: 测试目标（URL/IP）
        findings: 漏洞发现列表，每项应包含：
            - id: 漏洞编号
            - title: 漏洞标题
            - severity: 风险等级（Critical/High/Medium/Low/Info）
            - type: 漏洞类型
            - url: 受影响 URL
            - parameter: 受影响参数
            - description: 漏洞描述
            - reproduction: 复现步骤
            - evidence: 证据
            - remediation: 修复建议
        tester_name: 测试人员名称
        output_file: MinIO 对象名称（可选，默认自动生成）

    Returns:
        JSON 格式的报告生成结果，包含以下字段：
        - success: 是否成功
        - object_name: MinIO 对象路径（如 "pentest/reports/20250604_120000_xxx.html"）
        - content: HTML 报告完整内容
        - format: "html"
        - total_vulnerabilities: 漏洞总数
        - risk_score: 风险评分
        - charts_embedded: 是否内嵌图表

    **重要：** 返回结果中的 `object_name` 必须传给 `mgmt_save_pentest_report` 的 `file_path` 参数，
    `content` 必须传给 `content` 参数，`format` 必须设为 `"html"`，才能在前端正确显示和下载报告。
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    safe_name = _safe_filename(project_name)
    object_name = output_file or f"pentest/reports/{timestamp}_{safe_name}.html"

    # 统计数据
    severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    severity_scores = {"Critical": 9.5, "High": 8.0, "Medium": 5.5, "Low": 2.0, "Info": 0.0}

    for finding in findings:
        sev = finding.get("severity", "Info")
        if sev in severity_counts:
            severity_counts[sev] += 1

    total_vulns = sum(severity_counts.values())
    risk_score = sum(severity_counts[s] * severity_scores[s] for s in severity_counts) / max(total_vulns, 1)

    # 通过 MCP 渲染图表
    chart_images = await _render_charts_via_mcp(severity_counts, project_name)

    # 生成 HTML
    html_content = _generate_html_report_content(
        project_name=project_name,
        target=target,
        report_time=report_time,
        tester_name=tester_name,
        findings=findings,
        severity_counts=severity_counts,
        risk_score=risk_score,
        chart_images=chart_images,
    )

    # 上传到 MinIO
    await run_sync(_upload_report_to_minio, html_content, object_name, "text/html")

    return json.dumps({
        "success": True,
        "project": project_name,
        "target": target,
        "total_vulnerabilities": total_vulns,
        "risk_score": round(risk_score, 1),
        "severity_distribution": severity_counts,
        "object_name": object_name,
        "content": html_content,
        "format": "html",
        "charts_embedded": bool(chart_images),
    }, ensure_ascii=False, indent=2)
