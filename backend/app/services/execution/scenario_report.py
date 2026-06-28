"""
场景测试 HTML 报告生成器

将 ScenarioRun + ScenarioStepResult 渲染为单文件 HTML 报告。
"""

import html as html_module
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkdJeFRBPT06OWIzOWMzODg=

def _h(v: Any) -> str:
    """HTML escape helper."""
    if v is None:
        return ""
    return html_module.escape(str(v))


def _fmt_json(data: Any) -> str:
    """格式化 JSON，为空时返回提示文本。"""
    if not data:
        return '<span class="text-muted">无数据</span>'
    try:
        pretty = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        return f'<pre class="json">{_h(pretty)}</pre>'
    except Exception:
        return f'<pre class="json">{_h(str(data))}</pre>'
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkdJeFRBPT06OWIzOWMzODg=


def _status_badge(status: str) -> str:
    """状态徽章。"""
    cls = {
        "passed": "badge-pass",
        "failed": "badge-fail",
        "error": "badge-fail",
        "skipped": "badge-skip",
    }.get(status, "badge-neutral")
    label = {
        "passed": "通过",
        "failed": "失败",
        "error": "错误",
        "skipped": "跳过",
    }.get(status, status.upper())
    return f'<span class="badge {cls}">{label}</span>'


def _step_card(step: Dict[str, Any], index: int) -> str:
    """单步结果卡片 HTML。"""
    status = step.get("status", "unknown")
    name = step.get("step_name") or f"步骤 {step.get('step_order', index + 1)}"
    duration = step.get("duration_ms")
    duration_str = f"{duration} ms" if duration is not None else "—"
    error = step.get("error_message")
    request_data = step.get("request_data") or {}
    response_data = step.get("response_data") or {}
    extracted = step.get("extracted_data") or {}
    assertions = step.get("assertion_results") or []

    # 断言列表
    assertion_rows = ""
    if assertions:
        rows = ""
        for ass in assertions:
            passed = ass.get("passed", False)
            badge = '<span class="badge badge-pass">通过</span>' if passed else '<span class="badge badge-fail">失败</span>'
            actual = ass.get("actual")
            expected = ass.get("expected")
            rows += (
                f'<tr>'
                f'<td>{badge}</td>'
                f'<td>{_h(ass.get("assertion", {}).get("type", ""))}</td>'
                f'<td>{_h(json.dumps(expected, ensure_ascii=False, default=str))}</td>'
                f'<td>{_h(json.dumps(actual, ensure_ascii=False, default=str))}</td>'
                f'<td>{_h(ass.get("message", ""))}</td>'
                f'</tr>'
            )
        assertion_rows = (
            f'<table class="assertion-table">'
            f'<thead><tr><th>结果</th><th>类型</th><th>预期</th><th>实际</th><th>消息</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
        )
    else:
        assertion_rows = '<span class="text-muted">无断言</span>'

    # 提取数据
    extracted_block = _fmt_json(extracted) if extracted else '<span class="text-muted">无提取数据</span>'

    card_id = f"step-{index}"

    error_block = ""
    if error and status != "passed":
        error_block = f'<div class="error-box"><strong>错误信息：</strong><pre>{_h(error)}</pre></div>'
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkdJeFRBPT06OWIzOWMzODg=

    return f"""
    <div class="step-card {status}">
      <div class="step-header" onclick="toggleStep('{card_id}')">
        <div class="step-title">
          <span class="step-index">#{index + 1}</span>
          {_status_badge(status)}
          <span class="step-name">{_h(name)}</span>
        </div>
        <div class="step-meta">
          <span class="duration">{duration_str}</span>
          <span class="toggle-icon" id="icon-{card_id}">▼</span>
        </div>
      </div>
      <div class="step-body" id="body-{card_id}">
        {error_block}
        <div class="detail-grid">
          <div class="detail-block">
            <h4>请求</h4>
            {_fmt_json(request_data)}
          </div>
          <div class="detail-block">
            <h4>响应</h4>
            {_fmt_json(response_data)}
          </div>
          <div class="detail-block">
            <h4>提取变量</h4>
            {extracted_block}
          </div>
          <div class="detail-block">
            <h4>断言结果 ({len(assertions)})</h4>
            {assertion_rows}
          </div>
        </div>
      </div>
    </div>
    """


def generate_scenario_report(
    scenario_name: str,
    run_identifier: str,
    run_status: str,
    total_steps: int,
    passed_steps: int,
    failed_steps: int,
    skipped_steps: int,
    duration_ms: Optional[int],
    error_message: Optional[str],
    step_results: List[Dict[str, Any]],
    generated_at: Optional[datetime] = None,
) -> str:
    """
    生成场景测试 HTML 报告。

    Args:
        scenario_name: 场景名称
        run_identifier: 运行标识符，如 TSR-20240520-120000
        run_status: 运行状态
        total_steps: 总步骤数
        passed_steps: 通过数
        failed_steps: 失败数
        skipped_steps: 跳过数
        duration_ms: 耗时毫秒
        error_message: 整体错误信息
        step_results: 步骤结果列表，每项为 dict
        generated_at: 报告生成时间

    Returns:
        完整 HTML 字符串
    """
    if generated_at is None:
        generated_at = datetime.now()
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkdJeFRBPT06OWIzOWMzODg=

    duration_str = f"{duration_ms} ms" if duration_ms is not None else "—"
    status_badge = _status_badge(run_status)

    step_cards = "\n".join(
        _step_card(step, i) for i, step in enumerate(step_results)
    )

    error_banner = ""
    if error_message:
        error_banner = f'<div class="error-banner"><strong>整体错误：</strong>{_h(error_message)}</div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>场景测试报告 - {_h(scenario_name)}</title>
<style>
:root {{
  --color-bg: #f5f7fa;
  --color-card: #ffffff;
  --color-border: #e1e4e8;
  --color-text: #24292e;
  --color-muted: #6a737d;
  --color-pass: #28a745;
  --color-pass-bg: #d4edda;
  --color-fail: #dc3545;
  --color-fail-bg: #f8d7da;
  --color-skip: #6c757d;
  --color-skip-bg: #e2e3e5;
  --color-primary: #0366d6;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
  line-height: 1.6;
}}
.container {{
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}}
header {{
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 24px;
}}
header h1 {{ margin: 0 0 8px; font-size: 24px; }}
header .meta {{ color: var(--color-muted); font-size: 14px; }}
.summary-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}}
.summary-card {{
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}}
.summary-card .value {{
  font-size: 32px;
  font-weight: 700;
  margin: 8px 0;
}}
.summary-card.pass .value {{ color: var(--color-pass); }}
.summary-card.fail .value {{ color: var(--color-fail); }}
.summary-card.skip .value {{ color: var(--color-skip); }}
.summary-card.total .value {{ color: var(--color-primary); }}
.summary-card .label {{ font-size: 14px; color: var(--color-muted); }}
.badge {{
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  margin-right: 6px;
}}
.badge-pass {{ background: var(--color-pass-bg); color: var(--color-pass); }}
.badge-fail {{ background: var(--color-fail-bg); color: var(--color-fail); }}
.badge-skip {{ background: var(--color-skip-bg); color: var(--color-skip); }}
.badge-neutral {{ background: #e1e4e8; color: #24292e; }}
.step-card {{
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin-bottom: 16px;
  overflow: hidden;
}}
.step-card.passed {{ border-left: 4px solid var(--color-pass); }}
.step-card.failed {{ border-left: 4px solid var(--color-fail); }}
.step-card.error {{ border-left: 4px solid var(--color-fail); }}
.step-card.skipped {{ border-left: 4px solid var(--color-skip); }}
.step-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  cursor: pointer;
  user-select: none;
}}
.step-header:hover {{ background: #f6f8fa; }}
.step-title {{ display: flex; align-items: center; gap: 10px; }}
.step-index {{ color: var(--color-muted); font-weight: 600; min-width: 28px; }}
.step-name {{ font-weight: 600; }}
.step-meta {{ display: flex; align-items: center; gap: 12px; color: var(--color-muted); font-size: 14px; }}
.toggle-icon {{ transition: transform .2s; }}
.step-body {{
  display: none;
  padding: 0 18px 18px;
  border-top: 1px solid var(--color-border);
}}
.step-body.open {{ display: block; }}
.detail-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 16px;
}}
.detail-block h4 {{
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--color-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
pre.json {{
  background: #f6f8fa;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
}}
.assertion-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}}
.assertion-table th, .assertion-table td {{
  border: 1px solid var(--color-border);
  padding: 8px 10px;
  text-align: left;
}}
.assertion-table th {{
  background: #f6f8fa;
  font-weight: 600;
}}
.error-box, .error-banner {{
  background: var(--color-fail-bg);
  color: var(--color-fail);
  border: 1px solid #f5c6cb;
  border-radius: 6px;
  padding: 12px;
  margin: 12px 0;
}}
.error-banner {{
  margin-bottom: 24px;
}}
.text-muted {{ color: var(--color-muted); }}
@media (max-width: 768px) {{
  .detail-grid {{ grid-template-columns: 1fr; }}
  .summary-grid {{ grid-template-columns: repeat(2, 1fr); }}
}}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>场景测试报告</h1>
    <div class="meta">
      <strong>场景：</strong>{_h(scenario_name)} &nbsp;|&nbsp;
      <strong>运行 ID：</strong>{_h(run_identifier)} &nbsp;|&nbsp;
      <strong>状态：</strong>{status_badge} &nbsp;|&nbsp;
      <strong>耗时：</strong>{duration_str} &nbsp;|&nbsp;
      <strong>生成时间：</strong>{generated_at.strftime("%Y-%m-%d %H:%M:%S")}
    </div>
  </header>

  {error_banner}

  <div class="summary-grid">
    <div class="summary-card total">
      <div class="label">总步骤</div>
      <div class="value">{total_steps}</div>
    </div>
    <div class="summary-card pass">
      <div class="label">通过</div>
      <div class="value">{passed_steps}</div>
    </div>
    <div class="summary-card fail">
      <div class="label">失败</div>
      <div class="value">{failed_steps}</div>
    </div>
    <div class="summary-card skip">
      <div class="label">跳过</div>
      <div class="value">{skipped_steps}</div>
    </div>
  </div>

  <section>
    <h2 style="margin-bottom: 16px;">步骤详情</h2>
    {step_cards}
  </section>
</div>
<script>
function toggleStep(id) {{
  const body = document.getElementById('body-' + id);
  const icon = document.getElementById('icon-' + id);
  if (body.classList.contains('open')) {{
    body.classList.remove('open');
    icon.textContent = '▼';
  }} else {{
    body.classList.add('open');
    icon.textContent = '▲';
  }}
}}
// 默认展开失败和错误的步骤
document.querySelectorAll('.step-card.failed .step-header, .step-card.error .step-header').forEach(h => h.click());
</script>
</body>
</html>"""
    return html
