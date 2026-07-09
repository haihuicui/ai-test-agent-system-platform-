---
name: android-midscene-execute
description: 执行 Midscene.js Android 测试脚本。检查设备连接、配置环境、运行脚本并实时监控执行状态。
category: mobile-automation
triggers:
  - 运行.*测试
  - 执行.*脚本
  - execute.*test
  - run.*midscene
---

# Midscene.js Android 测试脚本执行

## 概述

在真实 Android 设备上执行 Midscene.js 测试脚本，包含环境检查、设备管理、脚本执行和实时监控。

## 执行流程

### 第 0 步：环境预检

执行测试前必须检查以下条件：

```bash
# 1. Node.js 环境
node -v      # >= 18

# 2. adb 是否可用
which adb

# 3. 设备连接状态
adb devices  # 至少一台设备状态为 "device"

# 4. USB 调试权限
# 设备屏幕应弹出授权对话框，需手动点击"允许"

# 5. 检查包依赖
npm ls @midscene/android dotenv tsx 2>/dev/null || npm install
```

### 第 1 步：环境变量确认

检查 `.env` 文件中的 API 配置：

```bash
# 必须配置
MIDSCENE_MODEL_NAME=qwen3.7-plus
MIDSCENE_MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MIDSCENE_MODEL_API_KEY=sk-xxx
MIDSCENE_MODEL_FAMILY=qwen3
```

如果缺少配置，向用户询问 API Key 并写入 `.env`。

### 第 2 步：设备就绪确认

```bash
# 检查设备屏幕是否为亮屏
adb shell dumpsys power | grep "mWakefulness=Awake" || echo "WARNING: Screen may be off"

# 检查设备是否解锁
adb shell dumpsys window | grep "mDreamingLockscreen=false" || echo "WARNING: Device may be locked"

# 确保输入权限（重要！如果报 INJECT_EVENTS 错误则需检查）
adb shell settings list global | grep development_settings_enabled
```

**常见问题处理：**

| 问题 | 解决方案 |
|------|---------|
| `INJECT_EVENTS permission` 错误 | 在开发者选项中开启"USB 调试（安全设置）" |
| 设备 offline | `adb kill-server && adb start-server && adb devices` |
| 输入后内容被清空 | 设置 `keyboardDismissStrategy: 'back-first'` |
| 截图获取失败 | 检查 scrcpy（如果使用该截图模式） |

### 第 3 步：执行脚本

#### 单个脚本执行

```bash
# 前台执行（推荐，实时查看输出）
npx tsx tests/android/test_xxx_TC001.ts

# 指定 Midscene 运行目录（可选）
MIDSCENE_RUN_DIR=./midscene_output npx tsx tests/android/test_xxx_TC001.ts
```

#### 批量执行

```bash
# 使用批量脚本
bash tests/android/run_all.sh

# 或逐个执行
for f in tests/android/test_*.ts; do
  echo "=== Running: $f ==="
  npx tsx "$f" || echo "FAILED: $f"
done
```

#### YAML 脚本执行

```bash
# YAML 脚本需通过一个 TS 入口加载
npx tsx -e "
import 'dotenv/config';
import { agentFromAdbDevice } from '@midscene/android';
const agent = await agentFromAdbDevice();
await agent.runYaml(require('fs').readFileSync('test_suite.yaml','utf8'));
"
```

### 第 4 步：实时监控

执行期间关注以下信号：

| 信号 | 含义 | 处理方式 |
|------|------|---------|
| `Midscene - report file updated:` | 步骤完成，报告更新 | 正常运行 |
| AI 规划超时 | 模型响应慢或任务复杂 | 增加 `replanningCycleLimit` |
| 元素未找到 | 页面布局变化 | 检查截图，调整描述 |
| 多步操作卡住 | 弹窗拦截 | 更新 `aiActContext` |

### 第 5 步：结果收集

每个脚本执行后收集：
- 退出码（0=成功）
- 控制台输出日志
- 报告文件路径（`midscene_run/report/*.html`）
- 执行时间

```bash
# 记录执行结果
echo "$script: $exit_code ($(date))" >> test_results.log
```

## 高级执行模式

### 1. 报告文件独立命名

```typescript
const agent = new AndroidAgent(device, {
  reportFileName: 'test_login_TC001',  // 自定义报告文件名
});
```

### 2. 缓存加速重复执行

```typescript
const agent = new AndroidAgent(device, {
  cache: {
    id: 'test_login_cache',
    strategy: 'read-write',  // 首次写、后续读
  },
});
```

### 3. 截图缩放减少 Token

```typescript
const agent = new AndroidAgent(device, {
  screenshotShrinkFactor: 2,  // 宽高减半，面积1/4
});
```

## 故障排查清单

1. **设备未识别**: `adb kill-server && adb start-server && adb devices`
2. **触控无响应**: 检查开发者选项中"USB调试(安全设置)"是否开启
3. **输入法冲突**: 设备上切换到系统默认输入法
4. **App 未安装**: 使用 `adb install app.apk` 提前安装
5. **网络受限**: 确保设备和电脑在同一网络（无线调试模式）
6. **报告太大**: 使用 `outputFormat: 'html-and-external-assets'`

## 注意事项

- 执行前确保设备屏幕亮且已解锁
- 不要在执行时操作设备（会干扰 Midscene 的 adb 命令）
- 长时间执行建议插着充电器
- 每次执行后 Midscene 自动生成报告，路径在 stdout 中输出
- 执行失败时，先去 `midscene_run/report/` 查看 HTML 报告回放定位问题