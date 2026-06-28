"""
渗透测试 - 信息收集工具模块

提供子域名枚举、端口扫描、目录扫描、指纹识别等信息收集功能。
所有工具通过子进程调用安全测试命令行工具执行。
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from app.utils.sync_executor import run_sync

from langchain_core.tools import tool
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1VOeVNBPT06Nzc1MTcxYzc=

from app.config.settings import settings


# ============================================================================
# 工作区配置
# ============================================================================

SECURITY_WORKSPACE = Path(settings.api_workspace_root).resolve().parent / "workspace" / "security"
SECURITY_WORKSPACE.mkdir(parents=True, exist_ok=True)


def _run_command(cmd: list[str], timeout: int = 300, cwd: Optional[str] = None) -> dict:
    """通用命令执行辅助函数"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd or str(SECURITY_WORKSPACE),
        )
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"命令执行超时（{timeout}秒）"}
    except FileNotFoundError as e:
        return {"success": False, "error": f"命令未找到: {str(e)}. 请确保已安装相应工具。"}
    except Exception as e:
        return {"success": False, "error": f"命令执行失败: {str(e)}"}


# ============================================================================
# 子域名枚举
# ============================================================================

async def _recon_subdomains_impl(
    domain: str,
    mode: str = "passive",
    wordlist: Optional[str] = None,
    output_file: Optional[str] = None,
) -> str:
    """子域名枚举核心实现"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = output_file or f"subdomains_{domain}_{timestamp}.txt"
    out_path = SECURITY_WORKSPACE / out_file

    discovered = []

    # Passive enumeration
    if mode in ("passive", "comprehensive"):
        # subfinder
        sf_result = await run_sync(
            _run_command,
            ["subfinder", "-d", domain, "-all", "-silent"],
            timeout=120
        )
        if sf_result["success"]:
            for line in sf_result["stdout"].strip().split("\n"):
                if line and line not in discovered:
                    discovered.append(line)

        # assetfinder
        af_result = await run_sync(
            _run_command,
            ["assetfinder", "--subs-only", domain],
            timeout=120
        )
        if af_result["success"]:
            for line in af_result["stdout"].strip().split("\n"):
                if line and line not in discovered:
                    discovered.append(line)

    # Active brute force
    if mode in ("active", "comprehensive"):
        wordlist_path = wordlist or "/usr/share/wordlists/seclists/Discovery/DNS/subdomains-top1million-5000.txt"
        # dnsx brute force
        bf_result = await run_sync(
            _run_command,
            ["dnsx", "-d", domain, "-w", wordlist_path, "-silent"],
            timeout=180
        )
        if bf_result["success"]:
            for line in bf_result["stdout"].strip().split("\n"):
                if line and line not in discovered:
                    discovered.append(line)

    # DNS resolution
    resolved = []
    if discovered:
        # Write to temp file for dnsx
        temp_subs = SECURITY_WORKSPACE / f"temp_subs_{timestamp}.txt"
        await run_sync(temp_subs.write_text, "\n".join(discovered), encoding="utf-8")
        dns_result = await run_sync(
            _run_command,
            ["dnsx", "-l", str(temp_subs), "-a", "-resp", "-silent"],
            timeout=120
        )
        await run_sync(temp_subs.unlink, missing_ok=True)
        if dns_result["success"]:
            for line in dns_result["stdout"].strip().split("\n"):
                if line:
                    resolved.append(line)

    # Save results
    if discovered:
        await run_sync(out_path.write_text, "\n".join(discovered), encoding="utf-8")

    return json.dumps({
        "success": True,
        "domain": domain,
        "mode": mode,
        "total_discovered": len(discovered),
        "total_resolved": len(resolved),
        "subdomains": discovered[:200],  # Limit output
        "resolved_details": resolved[:100],
        "output_file": str(out_path) if discovered else None,
        "timestamp": datetime.now().isoformat(),
    }, ensure_ascii=False, indent=2)


@tool
async def recon_subdomains(
    domain: str,
    mode: str = "passive",
    wordlist: Optional[str] = None,
    output_file: Optional[str] = None,
) -> str:
    """
    子域名枚举与 DNS 侦察

    使用 subfinder、assetfinder 等工具发现目标域名的子域名。

    Args:
        domain: 目标域名，如 example.com
        mode: 扫描模式，可选 passive（被动）/ active（主动）/ comprehensive（综合）
        wordlist: 自定义字典路径（可选）
        output_file: 输出文件路径（可选，默认保存到 workspace）

    Returns:
        JSON 格式的子域名列表和统计信息

    Example:
        >>> result = await recon_subdomains(domain="example.com", mode="comprehensive")
    """
    return await _recon_subdomains_impl(domain, mode, wordlist, output_file)

# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1VOeVNBPT06Nzc1MTcxYzc=

# ============================================================================
# 端口扫描
# ============================================================================

async def _recon_port_scan_impl(
    target: str,
    ports: str = "top1000",
    scan_type: str = "syn",
    service_detection: bool = True,
    os_detection: bool = False,
    output_file: Optional[str] = None,
) -> str:
    """端口扫描核心实现"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = output_file or f"portscan_{target.replace('.', '_')}_{timestamp}.xml"
    out_path = SECURITY_WORKSPACE / out_file

    # Build port specification
    port_map = {
        "top100": "--top-ports 100",
        "top1000": "--top-ports 1000",
        "full": "-p-",
    }
    port_arg = port_map.get(ports, f"-p {ports}")

    # Build scan type
    scan_map = {
        "syn": "-sS",
        "connect": "-sT",
        "udp": "-sU",
        "aggressive": "-sS -sV -sC -O",
    }
    scan_arg = scan_map.get(scan_type, "-sS")

    # Build nmap command
    cmd_parts = ["nmap", scan_arg, port_arg, "-T4"]
    if service_detection:
        cmd_parts.append("-sV")
    if os_detection:
        cmd_parts.append("-O")
    cmd_parts.extend(["-oX", str(out_path), target])

    result = await run_sync(_run_command, cmd_parts, timeout=600)

    if not result["success"]:
        # Fallback to rustscan for faster scanning
        rust_result = await run_sync(
            _run_command,
            ["rustscan", "-a", target, "--", "-sV"],
            timeout=300
        )
        if rust_result["success"]:
            result = rust_result
            # Save output
            await run_sync(
                out_path.with_suffix(".txt").write_text,
                result["stdout"],
                encoding="utf-8"
            )

    # Parse simple results
    open_ports = []
    lines = result.get("stdout", "").split("\n")
    for line in lines:
        if "/tcp" in line and "open" in line:
            parts = line.split()
            if len(parts) >= 3:
                open_ports.append({
                    "port": parts[0],
                    "state": parts[1],
                    "service": parts[2],
                })

    return json.dumps({
        "success": result.get("success", False),
        "target": target,
        "ports": ports,
        "scan_type": scan_type,
        "open_ports": open_ports,
        "total_open": len(open_ports),
        "raw_output": result.get("stdout", "")[:5000],
        "output_file": str(out_path) if out_path.exists() else None,
        "timestamp": datetime.now().isoformat(),
    }, ensure_ascii=False, indent=2)


@tool
async def recon_port_scan(
    target: str,
    ports: str = "top1000",
    scan_type: str = "syn",
    service_detection: bool = True,
    os_detection: bool = False,
    output_file: Optional[str] = None,
) -> str:
    """
    端口扫描与服务识别

    使用 nmap、rustscan 等工具扫描目标主机的开放端口和运行服务。

    Args:
        target: 目标 IP 或域名
        ports: 端口范围，可选 top100 / top1000 / full / 自定义如 "80,443,8080"
        scan_type: 扫描类型，syn / connect / udp / aggressive
        service_detection: 是否进行服务版本检测
        os_detection: 是否进行操作系统检测（需要 root）
        output_file: 输出文件路径（可选）

    Returns:
        JSON 格式的端口扫描结果

    Example:
        >>> result = await recon_port_scan(target="192.168.1.1", ports="top1000", scan_type="syn")
    """
    return await _recon_port_scan_impl(target, ports, scan_type, service_detection, os_detection, output_file)


# ============================================================================
# 目录扫描
# ============================================================================

async def _recon_directory_scan_impl(
    target_url: str,
    wordlist: Optional[str] = None,
    extensions: Optional[str] = None,
    recursive: bool = False,
    threads: int = 50,
    output_file: Optional[str] = None,
) -> str:
    """目录扫描核心实现"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = output_file or f"dirscan_{timestamp}.json"
    out_path = SECURITY_WORKSPACE / out_file

    wordlist_path = wordlist or "/usr/share/wordlists/seclists/Discovery/Web-Content/common.txt"
    ext_arg = f"-e {extensions}" if extensions else ""

    discovered = []

    # Try ffuf first
    ffuf_cmd = [
        "ffuf",
        "-u", f"{target_url}/FUZZ",
        "-w", wordlist_path,
        "-t", str(threads),
        "-mc", "200,201,204,301,302,307,308,401,403,405,500",
        "-o", str(out_path),
        "-of", "json",
    ]
    if ext_arg:
        ffuf_cmd.extend(ext_arg.split())
    if recursive:
        ffuf_cmd.append("-recursion")
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1VOeVNBPT06Nzc1MTcxYzc=

    result = await run_sync(_run_command, ffuf_cmd, timeout=300)

    # Parse ffuf JSON output
    if await run_sync(out_path.exists):
        try:
            import json as _json
            data = await run_sync(
                lambda p: _json.loads(p.read_text(encoding="utf-8")),
                out_path
            )
            for item in data.get("results", []):
                discovered.append({
                    "url": item.get("url", ""),
                    "status": item.get("status", 0),
                    "size": item.get("length", 0),
                    "words": item.get("words", 0),
                })
        except Exception:
            pass

    # Fallback parsing from stdout
    if not discovered and result.get("stdout"):
        for line in result["stdout"].split("\n"):
            if any(s in line for s in ["200", "301", "302", "403", "401", "500"]):
                discovered.append({"raw": line.strip()})

    return json.dumps({
        "success": True,
        "target": target_url,
        "total_discovered": len(discovered),
        "discovered_paths": discovered[:200],
        "output_file": str(out_path) if out_path.exists() else None,
        "timestamp": datetime.now().isoformat(),
    }, ensure_ascii=False, indent=2)


@tool
async def recon_directory_scan(
    target_url: str,
    wordlist: Optional[str] = None,
    extensions: Optional[str] = None,
    recursive: bool = False,
    threads: int = 50,
    output_file: Optional[str] = None,
) -> str:
    """
    目录和文件枚举扫描

    使用 ffuf、gobuster、feroxbuster 等工具发现隐藏目录和文件。

    Args:
        target_url: 目标 URL，如 https://example.com
        wordlist: 自定义字典路径（可选）
        extensions: 文件扩展名，如 "php,txt,bak,zip"（可选）
        recursive: 是否递归扫描子目录
        threads: 并发线程数
        output_file: 输出文件路径（可选）

    Returns:
        JSON 格式的扫描结果

    Example:
        >>> result = await recon_directory_scan(target_url="https://example.com", extensions="php,txt,bak")
    """
    return await _recon_directory_scan_impl(target_url, wordlist, extensions, recursive, threads, output_file)


# ============================================================================
# 指纹识别
# ============================================================================

async def _recon_fingerprint_impl(
    target_url: str,
    detect_waf: bool = True,
    detect_tech: bool = True,
    output_file: Optional[str] = None,
) -> str:
    """Web 指纹识别核心实现"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {
        "target": target_url,
        "technologies": [],
        "waf": None,
        "headers": {},
        "server": None,
    }

    # httpx for quick tech detection
    httpx_result = await run_sync(
        _run_command,
        ["httpx", "-u", target_url, "-tech-detect", "-json", "-silent"],
        timeout=60
    )
    if httpx_result["success"] and httpx_result["stdout"]:
        try:
            for line in httpx_result["stdout"].strip().split("\n"):
                if line:
                    data = json.loads(line)
                    results["technologies"] = data.get("tech", [])
                    results["server"] = data.get("webserver", "")
                    results["headers"] = {
                        k: v for k, v in data.items()
                        if k.startswith("header_")
                    }
        except Exception:
            pass

    # whatweb for detailed fingerprinting
    if detect_tech:
        ww_result = await run_sync(
            _run_command,
            ["whatweb", "-a", "3", target_url],
            timeout=120
        )
        if ww_result["success"]:
            results["whatweb_raw"] = ww_result["stdout"][:2000]

    # wafw00f for WAF detection
    if detect_waf:
        waf_result = await run_sync(
            _run_command,
            ["wafw00f", "-a", target_url],
            timeout=120
        )
        if waf_result["success"]:
            waf_lines = waf_result["stdout"].split("\n")
            for line in waf_lines:
                if "is behind" in line.lower():
                    results["waf"] = line.strip()
                    break
            if not results["waf"]:
                results["waf"] = "No WAF detected or detection failed"
            results["waf_raw"] = waf_result["stdout"][:2000]

    # Save results
    out_file = output_file or f"fingerprint_{timestamp}.json"
    out_path = SECURITY_WORKSPACE / out_file
    await run_sync(
        out_path.write_text,
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return json.dumps({
        "success": True,
        "target": target_url,
        "technologies": results["technologies"],
        "server": results["server"],
        "waf": results["waf"],
        "headers_summary": results["headers"],
        "output_file": str(out_path),
        "timestamp": datetime.now().isoformat(),
    }, ensure_ascii=False, indent=2)


@tool
async def recon_fingerprint(
    target_url: str,
    detect_waf: bool = True,
    detect_tech: bool = True,
    output_file: Optional[str] = None,
) -> str:
    """
    Web 指纹识别与 WAF 检测

    使用 whatweb、wafw00f、httpx、nuclei 等工具识别目标技术栈和防护设备。

    Args:
        target_url: 目标 URL
        detect_waf: 是否检测 WAF
        detect_tech: 是否检测技术栈
        output_file: 输出文件路径（可选）

    Returns:
        JSON 格式的指纹识别结果

    Example:
        >>> result = await recon_fingerprint(target_url="https://example.com")
    """
    return await _recon_fingerprint_impl(target_url, detect_waf, detect_tech, output_file)


# ============================================================================
# 综合信息收集
# ============================================================================

@tool
async def recon_full_scan(
    target: str,
    project_name: str = "pentest",
) -> str:
    """
    执行完整的信息收集扫描（综合侦察）

    依次执行：子域名枚举 → 端口扫描 → 目录扫描 → 指纹识别

    Args:
        target: 目标域名或 IP
        project_name: 项目名称（用于保存结果）

    Returns:
        JSON 格式的综合扫描结果摘要

    Example:
        >>> result = await recon_full_scan(target="example.com", project_name="client_audit")
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir = SECURITY_WORKSPACE / f"{project_name}_{timestamp}"
    await run_sync(project_dir.mkdir, parents=True, exist_ok=True)

    scan_results = {
        "project": project_name,
        "target": target,
        "timestamp": timestamp,
        "phases": [],
    }
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1VOeVNBPT06Nzc1MTcxYzc=

    # Phase 1: Subdomain enumeration (if target is a domain)
    if not target.replace(".", "").isdigit():
        sub_result_raw = await _recon_subdomains_impl(
            domain=target,
            mode="passive",
            output_file=str(project_dir / "subdomains.txt"),
        )
        sub_result = json.loads(sub_result_raw)
        scan_results["phases"].append({
            "name": "子域名枚举",
            "success": sub_result.get("success", False),
            "total_discovered": sub_result.get("total_discovered", 0),
        })

    # Phase 2: Port scan
    port_result_raw = await _recon_port_scan_impl(
        target=target,
        ports="top1000",
        scan_type="syn",
        output_file=str(project_dir / "portscan.xml"),
    )
    port_result = json.loads(port_result_raw)
    scan_results["phases"].append({
        "name": "端口扫描",
        "success": port_result.get("success", False),
        "total_open_ports": port_result.get("total_open", 0),
        "open_ports": port_result.get("open_ports", []),
    })

    # Phase 3: Directory scan (if HTTP service detected)
    target_url = f"https://{target}" if not target.startswith("http") else target
    dir_result_raw = await _recon_directory_scan_impl(
        target_url=target_url,
        output_file=str(project_dir / "dirscan.json"),
    )
    dir_result = json.loads(dir_result_raw)
    scan_results["phases"].append({
        "name": "目录扫描",
        "success": dir_result.get("success", False),
        "total_discovered": dir_result.get("total_discovered", 0),
    })

    # Phase 4: Fingerprint
    fp_result_raw = await _recon_fingerprint_impl(
        target_url=target_url,
        output_file=str(project_dir / "fingerprint.json"),
    )
    fp_result = json.loads(fp_result_raw)
    scan_results["phases"].append({
        "name": "指纹识别",
        "success": fp_result.get("success", False),
        "technologies": fp_result.get("technologies", []),
        "waf": fp_result.get("waf"),
    })

    # Save summary
    summary_path = project_dir / "recon_summary.json"
    await run_sync(
        summary_path.write_text,
        json.dumps(scan_results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    scan_results["project_dir"] = str(project_dir)
    return json.dumps(scan_results, ensure_ascii=False, indent=2)
