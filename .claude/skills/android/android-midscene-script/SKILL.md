---
name: android-midscene-script
description: 将测试用例转化为可执行的 Midscene.js TypeScript/YAML 脚本。生成包含设备连接、初始化、用例执行、清理的完整脚本文件。
category: mobile-automation
triggers:
  - 生成脚本
  - 编写.*脚本
  - generate.*script
  - midscene.*script
---

# Midscene.js Android 测试脚本生成

## 概述

根据测试用例生成可直接执行的 Midscene.js TypeScript 脚本。每个用例对应一个独立脚本文件，包含完整的生命周期管理。

## 脚本模板

### TypeScript 脚本（推荐）

```typescript
// test_<模块>_<用例ID>.ts
// 描述：<用例标题>
// 优先级：P0/P1/P2
// 依赖：需要 adb 连接设备

import 'dotenv/config';
import {
  AndroidAgent,
  AndroidDevice,
  getConnectedDevices,
} from '@midscene/android';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function main() {
  console.log('=== Test: <用例标题> ===\n');

  // 1. 设备连接
  const devices = await getConnectedDevices();
  if (devices.length === 0) {
    throw new Error('No Android device connected');
  }
  console.log(`Device: ${devices[0].udid} (${devices[0].state})`);

  const device = new AndroidDevice(devices[0].udid, {
    // keyboardDismissStrategy: 'back-first', // 如果输入后内容被清空，取消此行注释
  });

  const agent = new AndroidAgent(device, {
    aiActContext:
      '如果出现任何权限、用户协议弹窗，点击同意。如果出现登录页面，点击关闭。',
    // generateReport: true,         // (默认 true) 生成报告
    // reportFileName: '<自定义名称>',
    // outputFormat: 'html-and-external-assets', // 大报告场景
  });

  await device.connect();
  console.log('Device connected\n');

  try {
    // 2. 前置条件
    // [按需：启动 App、登录、数据准备]

    // 3. 测试步骤
    // === 步骤 1: <描述> ===
    console.log('Step 1: <描述>');
    // [Midscene API 调用]

    // === 步骤 2: <描述> ===
    console.log('Step 2: <描述>');
    // [Midscene API 调用]

    // 4. 断言验证
    console.log('\n--- Assertions ---');
    // [aiAssert 调用]

    console.log('\n✅ Test passed: <用例标题>');
    return 0;
  } catch (error) {
    console.error('\n❌ Test failed:');
    console.error(error);
    return 1;
  } finally {
    // 5. 清理
    console.log('\n>>> Cleaning up...');
    // [按需：agent.terminate(), agent.home()]
    await agent.home();
    // await device.disconnect(); // 如需要
  }
}

main().then((code) => process.exit(code));
```

### YAML 脚本（批量场景）

```yaml
# test_suite.yaml
# 使用 agent.runYaml() 加载执行

web: # 不适用时可为空
  url: ""

android:
  deviceId: ""         # 留空 = 第一个设备
  # keyboardDismissStrategy: "back-first"

ios: # 不适用时可为空

computer: # 不适用时可为空

tasks:
  - name: "<用例标题>"
    flow:
      - aiAct: "<操作描述>"
      - sleep: 2000
      - aiAssert: "<断言描述>"

  - name: "<另一个用例>"
    flow:
      - aiTap: "<操作>"
      - aiWaitFor: "<等待条件>"
```

## 生成规则

### 1. 文件命名规范
```
tests/android/test_{module}_{tc_id}.ts
tests/android/test_suite.yaml
```

### 2. API 映射

| 用例步骤描述 | 生成代码 |
|---|---|
| "启动xxx应用" | `await agent.launch('包名');` |
| "点击xxx" | `await agent.aiTap('xxx');` |
| "在xxx输入yyy" | `await agent.aiInput('xxx', 'yyy');` |
| "验证xxx存在" | `await agent.aiAssert('xxx');` |
| "等待xxx出现" | `await agent.aiWaitFor('xxx');` |
| "向下滚动到xxx" | `await agent.aiScroll({direction: 'down', scrollType: 'untilVisible', value: 'xxx'});` |
| "提取xxx列表" | `const data = await agent.aiQuery('{...}');` |
| "多步操作：..." | `await agent.aiAct('...');` |
| "返回上一页" | `await agent.back();` |
| "关闭xxx应用" | `await agent.terminate('包名');` |
| "等待N秒" | `await sleep(N * 1000);` |

### 3. aiAct prompt 编写规范

Midscene 的 `aiAct()` 通过自然语言自动规划步骤，prompt 要求：
- 一句话一个意图："点击登录按钮，输入账号 test@example.com，输入密码 123456，点击确认"
- 顺序明确：按操作先后顺序写
- 目标具体："滑动到页面底部" ✅ vs "往下滑" ❌

### 4. aiActContext 配置

根据测试场景设置默认行为：
```typescript
const agent = new AndroidAgent(device, {
  aiActContext: [
    '如果出现任何权限、用户协议弹窗，点击同意。',
    '如果出现登录页面，点击关闭，使用游客模式。',
    '如果出现广告弹窗，点击关闭按钮。',
  ].join(' '),
});
```

### 5. 错误处理

每个脚本必须包含 try-catch，失败时：
- 捕获错误信息到日志
- 执行清理操作（home/terminate）
- 返回非零退出码

## 批量脚本生成

如果测试用例数量多（>5个），生成一个 `run_all.sh` 统一入口：

```bash
#!/bin/bash
# run_all.sh — 执行全部 Android 测试脚本
set -e
SCRIPTS=(
  "tests/android/test_login_TC001.ts"
  "tests/android/test_search_TC002.ts"
  "tests/android/test_cart_TC003.ts"
)
PASS=0
FAIL=0
for script in "${SCRIPTS[@]}"; do
  echo "========================================="
  echo "Running: $script"
  echo "========================================="
  if npx tsx "$script"; then
    ((PASS++))
  else
    ((FAIL++))
  fi
  echo ""
done
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="
```

## 注意事项

- 每个脚本独立可运行，不依赖执行顺序
- API Key 从 `.env` 读取，不硬编码
- 脚本文件放到 `tests/android/` 目录
- 生成后检查 TypeScript 语法是否正确
- YAML 适用于简单线性流程，TypeScript 适用于复杂逻辑