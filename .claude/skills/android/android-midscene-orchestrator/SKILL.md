---
name: android-midscene-orchestrator
description: Midscene.js Android 全流程自动化测试管道编排器。根据用户测试需求，串联 计划设计→用例设计→脚本生成→脚本执行→报告输出 五大阶段。加载本 skill 后自动判断当前阶段并调用对应子 skill。
triggers:
  - android.*测试
  - midscene.*android
  - android.*自动化
  - 手机.*自动化测试
---

# Midscene.js Android 全流程自动化测试管道

## 概述

基于 [Midscene.js](https://midscenejs.com/zh/android-getting-started.html) 视觉驱动 UI 自动化框架，实现 Android 端到端测试的五大阶段全流程：

```
用户需求 → ①计划设计 → ②用例设计 → ③脚本生成 → ④脚本执行 → ⑤报告输出
```

## 执行策略

### 阶段判断

根据用户输入判断当前所处阶段：

| 用户输入特征 | 执行阶段 | 产出物 |
|---|---|---|
| "测试这个场景"、"帮我规划测试" | 阶段①②③ | 测试计划 + 用例 + 脚本 |
| "有这个测试计划/用例，生成脚本" | 阶段③ | 脚本文件 |
| "运行这个脚本"、"执行测试" | 阶段④⑤ | 执行结果 + 报告 |
| 无明确指向 | 全流程 (①→⑤) | 全部产出物 |

### 阶段串联

每个阶段产出物必须有用户确认（clarify）才能进入下一阶段，避免盲目执行。

## 全流程执行步骤

### 阶段 ①：测试计划设计 → 加载 `android-midscene-plan`

1. 理解用户的测试需求/场景描述
2. 分析被测 App 的功能模块
3. 设计测试策略（覆盖范围、优先级、风险点）
4. 输出测试计划文档（Markdown）

**产出物检查**：计划应包含测试范围、策略、优先级、环境要求、风险点。

### 阶段 ②：测试用例设计 → 加载 `android-midscene-case`

1. 基于测试计划拆解测试用例
2. 每个用例含：ID、标题、前置条件、操作步骤、预期结果、优先级
3. 覆盖正向/负向/边界场景
4. 输出测试用例文档（Markdown 表格）

**产出物检查**：用例应含用例ID、前置条件、步骤、预期结果，且步骤描述应可直接转化为 Midscene 脚本。

### 阶段 ③：脚本生成 → 加载 `android-midscene-script`

1. 将测试用例转化为 Midscene.js TypeScript 或 YAML 脚本
2. 每个用例一个独立脚本文件
3. 包含 setup/teardown 逻辑
4. 输出到 `tests/android/` 目录

**产出物检查**：脚本可独立运行，包含必要的 import、设备连接、清理逻辑。

### 阶段 ④：脚本执行 → 加载 `android-midscene-execute`

1. 检查 adb 设备连接状态
2. 配置 API Key（从 .env 读取）
3. 逐脚本执行测试
4. 记录执行日志和截图

**产出物检查**：确认设备在线、API Key 有效、执行无阻塞错误。

### 阶段 ⑤：报告输出 → 加载 `android-midscene-report`

1. 收集 Midscene 生成的 HTML 报告
2. 合并多脚本报告（如需要）
3. 生成汇总测试报告
4. 标注通过/失败统计

**产出物检查**：报告包含执行统计、失败详情、可视化回放链接。

## 前置依赖

```bash
# Node.js 项目初始化
npm init -y
npm install @midscene/android dotenv
npm install -D tsx typescript @types/node

# 确保 adb 可用
which adb && adb devices
```

## 配置文件

在项目根目录创建 `.env`：
```env
# 模型配置（必需）
MIDSCENE_MODEL_NAME=qwen3.7-plus
MIDSCENE_MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MIDSCENE_MODEL_API_KEY=sk-your-api-key
MIDSCENE_MODEL_FAMILY=qwen3
```

## 子 Skill 依赖

本 skill 需要以下子 skill 配合使用，按需加载：
- `android-midscene-plan` — 测试计划设计
- `android-midscene-case` — 测试用例设计
- `android-midscene-script` — 脚本生成
- `android-midscene-execute` — 脚本执行
- `android-midscene-report` — 报告输出

## 注意事项

- 每个阶段完成后必须展示产出物给用户确认
- 阶段①②可不依赖真实设备，阶段④必须设备在线
- API Key 通过 .env 管理，永不硬编码在脚本中
- 生成的脚本必须支持独立运行（`npx tsx test_xxx.ts`）
- 报告 HTML 可浏览器直接打开回放每一步操作