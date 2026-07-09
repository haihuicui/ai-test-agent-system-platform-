// templates/test_template.ts
// Midscene.js Android 测试脚本模板
// 替换所有 <...> 占位符后即可运行
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YmpOVlF3PT06YzRlNWRlOWE=

import 'dotenv/config';
import {
  AndroidAgent,
  AndroidDevice,
  getConnectedDevices,
} from '@midscene/android';
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YmpOVlF3PT06YzRlNWRlOWE=

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YmpOVlF3PT06YzRlNWRlOWE=

async function main() {
  console.log('=== Test: <用例标题> ===\n');

  // 1. 设备连接
  const devices = await getConnectedDevices();
  if (devices.length === 0) {
    throw new Error('No Android device connected. Run: adb devices');
  }
  console.log(`Device: ${devices[0].udid} (${devices[0].state})`);

  const device = new AndroidDevice(devices[0].udid, {
    // keyboardDismissStrategy: 'back-first',
  });

  const agent = new AndroidAgent(device, {
    aiActContext:
      '如果出现任何权限弹窗、用户协议，点击同意。如果出现登录页，点击关闭。如果出现广告弹窗，点击关闭。',
    // reportFileName: '<自定义报告名>',
    // screenshotShrinkFactor: 2,
  });

  await device.connect();
  console.log('Device connected\n');

  try {
    // ============================================================
    // 2. 前置条件
    // ============================================================
    // await agent.launch('<包名或Activity>');
    // await agent.aiWaitFor('<首页加载完成>');

    // ============================================================
    // 3. 测试步骤
    // ============================================================

    // === Step 1 ===
    console.log('Step 1: <步骤描述>');
    // await agent.aiTap('<元素描述>');

    // === Step 2 ===
    console.log('Step 2: <步骤描述>');
    // await agent.aiInput('<输入框描述>', '<输入内容>');

    // === Step 3 ===
    console.log('Step 3: <步骤描述>');
    // await agent.aiScroll({ direction: 'down', scrollType: 'untilVisible', value: '<目标>' });

    // ============================================================
    // 4. 断言验证
    // ============================================================
    console.log('\n--- Assertions ---');
    // await agent.aiAssert('<验证点>');
    // const data = await agent.aiQuery('{title: string, count: Number}[]');

    console.log('\n✅ Test passed: <用例标题>');
    return 0;
  } catch (error) {
    console.error('\n❌ Test failed: <用例标题>');
    console.error(error);
    return 1;
  } finally {
    // ============================================================
    // 5. 清理
    // ============================================================
    console.log('\n>>> Cleaning up...');
    // await agent.terminate('<包名>');
    await agent.home();
  }
}
// @ts-expect-error  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YmpOVlF3PT06YzRlNWRlOWE=

main().then((code) => process.exit(code));