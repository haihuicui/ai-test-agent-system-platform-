---
name: android-midscene-report
description: 收集 Midscene.js 测试报告，合并多个脚本结果，生成包含执行统计、失败分析、可视化回放的汇总测试报告。
category: mobile-automation
triggers:
  - 测试报告
  - test.*report
  - 报告.*输出
  - report.*output
---

# Midscene.js Android 测试报告输出

## 概述

Midscene 在每次执行后自动生成 HTML 可视化报告（`midscene_run/report/*.html`），包含每步操作的截图、AI 规划过程、断言结果。本 skill 负责收集、合并、汇总这些报告。

## Midscene 报告能力

每个 HTML 报告包含：
- **操作时间线**：每步操作的截图 + AI 分析
- **规划/定位/断言详情**：AI 思考过程、元素定位坐标、断言结果
- **操作状态标记**：✅ 成功 / ❌ 失败
- **原始截图**：每步前后的屏幕截图

## 报告收集

### 1. 定位报告文件

```bash
# 默认报告目录
ls -la midscene_run/report/

# 查找所有报告
find . -path "*/midscene_run/report/*.html" -type f
```

### 2. 报告汇总脚本

创建 `scripts/collect_reports.ts` 用于收集多个脚本的执行结果：

```typescript
// scripts/collect_reports.ts
import { readdirSync, statSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';

interface TestResult {
  name: string;
  status: 'pass' | 'fail';
  reportPath: string;
  duration: string;
  error?: string;
}

async function collectReports(logFile: string): Promise<TestResult[]> {
  const results: TestResult[] = [];
  const log = readFileSync(logFile, 'utf-8').split('\n');
  
  for (const line of log) {
    if (!line.trim()) continue;
    const parts = line.split(': ');
    const name = parts[0];
    const code = parseInt(parts[1]);
    const timestamp = parts[2];
    
    // 查找对应的 HTML 报告
    const reportPath = findReport(name);
    
    results.push({
      name,
      status: code === 0 ? 'pass' : 'fail',
      reportPath,
      duration: timestamp,
    });
  }
  
  return results;
}
```

### 3. 使用 ReportMergingTool 合并报告

Midscene 提供原生的报告合并工具：

```typescript
import { ReportMergingTool } from '@midscene/core';

const reportMergingTool = new ReportMergingTool();

// 追加多个报告
await reportMergingTool.append('test_login_report.html');
await reportMergingTool.append('test_search_report.html');

// 合并为一个报告
await reportMergingTool.mergeReports('merged_android_test_report.html');

// 清理
reportMergingTool.clear();
```

## 自定义汇总报告生成

### Markdown 汇总报告

```markdown
# Android 自动化测试报告

## 执行概览

| 项目 | 值 |
|------|-----|
| 执行时间 | 2026-06-10 14:30:00 |
| 设备 | Pixel 6 (Android 14) |
| AI 模型 | qwen3.7-plus |
| 总用例数 | 12 |
| 通过 | 10 ✅ |
| 失败 | 2 ❌ |
| 通过率 | 83.3% |
| 总耗时 | 8分32秒 |

## 用例执行详情

| ID | 标题 | 状态 | 耗时 | 报告 |
|----|------|------|------|------|
| TC-001 | 用户登录 | ✅ | 45s | [查看](report/test_login_TC001.html) |
| TC-002 | 商品搜索 | ✅ | 52s | [查看](report/test_search_TC002.html) |
| TC-003 | 加入购物车 | ❌ | 38s | [查看](report/test_cart_TC003.html) |
| ... | ... | ... | ... | ... |

## 失败用例分析

### TC-003: 加入购物车 ❌

**错误信息：**
```
Error: Element not found after 3 attempts
```

**失败截图：** ![失败截图](midscene_run/report/test_cart_TC003_screenshot.png)

**可能原因：**
1. 购物车按钮被广告弹窗遮挡
2. 页面加载未完成

**建议：**
1. 在 aiActContext 中添加"关闭广告弹窗"策略
2. 增加 aiWaitFor 等待步骤
3. 使用 aiLocate 确认元素位置

## 报告文件索引

| 文件 | 说明 | 路径 |
|------|------|------|
| merged_report.html | 合并报告（全部用例） | `midscene_run/report/merged_report.html` |
| test_login_TC001.html | TC-001 单独报告 | `midscene_run/report/test_login_TC001.html` |
| test_search_TC002.html | TC-002 单独报告 | `midscene_run/report/test_search_TC002.html` |
| test_cart_TC003.html | TC-003 单独报告 | `midscene_run/report/test_cart_TC003.html` |

## 可视化回放

在浏览器中打开 HTML 报告即可查看：
- 每步操作的截图对比
- AI 规划/定位的详细过程
- 断言执行的状态

```bash
# 本地查看报告
open midscene_run/report/merged_report.html    # macOS
xdg-open midscene_run/report/merged_report.html # Linux
start midscene_run/report/merged_report.html    # Windows

# 或启动本地服务器
npx serve midscene_run/report/
```
```

## 报告生成流程

```
① 各脚本执行 → 自动生成 HTML 报告
       ↓
② 收集 .html 报告路径列表
       ↓
③ 可选：ReportMergingTool.mergeReports() 合并
       ↓
④ 生成 Markdown 汇总报告
       ↓
⑤ 输出报告文件索引
```

## 报告格式选项

| 格式 | 适用场景 | 参数 |
|------|---------|------|
| `single-html`（默认） | 报告 < 10MB，单文件方便分享 | `outputFormat: 'single-html'` |
| `html-and-external-assets` | 大报告，截图存为独立 PNG | `outputFormat: 'html-and-external-assets'` |

**注意**：`html-and-external-assets` 格式无法用 `file://` 打开，需通过 HTTP 服务器：`npx serve midscene_run/report/`

## 失败用例深度分析

当用例失败时，执行以下分析：

1. **打开报告 HTML**：查看具体哪一步失败
2. **检查 AI 截图**：观察失败时的屏幕状态
3. **检查 AI 规划**：看模型是否正确理解了指令
4. **调整策略**：
   - 弹窗拦截 → 更新 `aiActContext`
   - 元素未找到 → 增加 `aiWaitFor` 或调整描述
   - 操作超时 → 增加 `replanningCycleLimit`
   - 截图模糊 → 减小 `screenshotShrinkFactor`

## 注意事项

- 报告在脚本执行时自动生成，无需额外调用 API
- 合并报告前确保所有子报告都已生成
- `html-and-external-assets` 格式需通过 HTTP 访问
- 报告包含截图 base64 数据，可能较大（10-50MB）
- 如需持久保存报告，建议复制到项目 `reports/` 目录