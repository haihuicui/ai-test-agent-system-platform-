# Midscene.js Android API 速查表

> 基于 https://midscenejs.com/zh 官方文档整理

## 导入

```typescript
import { AndroidAgent, AndroidDevice, getConnectedDevices, agentFromAdbDevice } from '@midscene/android';
import { AndroidDeviceOpt } from '@midscene/android';
import { PageAgentOpt } from '@midscene/core';
// 如需自定义动作
import { defineAction, getMidsceneLocationSchema } from '@midscene/core/device';
import { z } from '@midscene/core';
```

## AndroidDevice

```typescript
const device = new AndroidDevice(udid: string, opts?: AndroidDeviceOpt);
await device.connect();
await device.disconnect();
```

### AndroidDeviceOpt
```typescript
{
  keyboardDismissStrategy?: 'esc-first' | 'back-first' | 'disabled';  // 键盘隐藏策略
  appNameMapping?: Record<string, string>;  // 应用名称→包名映射
  scrcpyBinaryPath?: string;  // scrcpy 二进制定制路径
  scrcpyPortRange?: [number, number];  // scrcpy 端口范围
  scrcpyMode?: boolean;  // 是否使用 scrcpy 截图模式
}
```

## AndroidAgent

### 构造函数
```typescript
const agent = new AndroidAgent(device: AndroidDevice, opts?: PageAgentOpt & AndroidAgentOpt);
```

### AndroidAgentOpt（Android 特有）
```typescript
{
  aiActContext?: string;  // 传给 AI 的上文背景（弹窗策略等）
  customActions?: CustomAction[];  // 自定义手势动作
  appNameMapping?: Record<string, string>;  // 应用名称映射
}
```

### PageAgentOpt（通用）
```typescript
{
  generateReport?: boolean;           // 默认 true
  reportFileName?: string;            // 自定义报告名
  persistExecutionDump?: boolean;     // 额外输出 JSON dump
  autoPrintReportMsg?: boolean;       // 默认 true
  cache?: false | {
    id: string;
    strategy?: 'read-only' | 'read-write' | 'write-only';
  };
  outputFormat?: 'single-html' | 'html-and-external-assets';
  screenshotShrinkFactor?: number;    // 截图缩放比例，默认 1
  replanningCycleLimit?: number;      // aiAct 最大重规划次数，默认 20
  waitAfterAction?: number;           // 动作后等待(ms)，默认 300
  modelConfig?: Record<string, string | number>;  // 模型配置
  onTaskStartTip?: (tip: string) => void;  // 子任务开始回调
}
```

## 交互方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `agent.ai()` | `(prompt: string) => Promise<void>` | 自动规划（简写） |
| `agent.aiAct()` | `(prompt, opts?) => Promise<void>` | 自动规划（完整） |
| `agent.aiTap()` | `(locate: string) => Promise<void>` | 即时点击 |
| `agent.aiHover()` | `(locate: string) => Promise<void>` | 即时悬浮 |
| `agent.aiInput()` | `(locate: string, text: string) => Promise<void>` | 即时输入 |
| `agent.aiClearInput()` | `(locate: string) => Promise<void>` | 清空输入 |
| `agent.aiKeyboardPress()` | `(key: string) => Promise<void>` | 按键 |
| `agent.aiScroll()` | `(opts) => Promise<void>` | 滚动 |
| `agent.aiPinch()` | `(opts) => Promise<void>` | 捏合 |
| `agent.aiLongPress()` | `(locate: string) => Promise<void>` | 长按 |
| `agent.aiDoubleClick()` | `(locate: string) => Promise<void>` | 双击 |

## 数据提取

| 方法 | 签名 | 说明 |
|------|------|------|
| `agent.aiAsk()` | `(question: string) => Promise<string>` | 自然语言问答 |
| `agent.aiQuery()` | `(demand: string) => Promise<T>` | 结构化数据提取 |
| `agent.aiBoolean()` | `(question: string) => Promise<boolean>` | 是/否判断 |
| `agent.aiNumber()` | `(question: string) => Promise<number>` | 数字提取 |
| `agent.aiString()` | `(question: string) => Promise<string>` | 文字提取 |

## 断言/定位/等待

| 方法 | 签名 | 说明 |
|------|------|------|
| `agent.aiAssert()` | `(assertion: string) => Promise<void>` | 断言验证 |
| `agent.aiLocate()` | `(locate: string) => Promise<{rect,center}>` | 定位元素 |
| `agent.aiWaitFor()` | `(condition: string, opts?) => Promise<void>` | 等待条件满足 |

## Android 特有方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `agent.launch()` | `(target: string) => Promise<void>` | 启动应用/URL |
| `agent.runAdbShell()` | `(command: string, opts?) => Promise<string>` | 执行 adb shell |
| `agent.terminate()` | `(uri: string) => Promise<void>` | 强制停止应用 |
| `agent.back()` | `() => Promise<void>` | Android 返回键 |
| `agent.home()` | `() => Promise<void>` | 回到桌面 |
| `agent.recentApps()` | `() => Promise<void>` | 最近应用 |

## 辅助函数

```typescript
// 获取已连接设备列表
const devices = await getConnectedDevices();
// => [{ udid: string, state: string, port?: number }]

// 快捷创建 agent
const agent = await agentFromAdbDevice(deviceId?: string, opts?);
```

## aiAct/ai 高级选项

```typescript
await agent.aiAct('操作描述', {
  cacheable?: boolean;         // 是否允许缓存，默认 true
  deepThink?: 'unset' | true | false;  // 深度思考，规划/定位分离
  deepLocate?: boolean;        // 深度定位，默认 false
  fileChooserAccept?: string | string[];  // 文件选择器（仅 Web 端）
  abortSignal?: AbortSignal;   // 中断信号
});
```

## aiScroll 选项

```typescript
await agent.aiScroll({
  direction: 'up' | 'down' | 'left' | 'right';
  scrollType?: 'once' | 'untilVisible';
  value?: string;              // untilVisible 时的目标描述
  distance?: number;           // 滚动距离
});
```

## runYaml

```typescript
await agent.runYaml(yamlContent: string);
```