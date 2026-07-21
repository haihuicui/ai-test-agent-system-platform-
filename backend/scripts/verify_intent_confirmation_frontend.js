// 前端意图确认面板端到端验证脚本
const { chromium } = require("playwright");
const path = require("path");

const BASE_URL = "http://localhost:3000";
const PROJECT_ID = "PR-1";
const USER_MESSAGE =
  "为 SauceDemo 网站创建完整的 Web 功能测试，覆盖登录、加购、购物车、结账流程。";

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  try {
    // 1. 打开 Web 测试页面
    console.log("打开 Web 测试页面...");
    await page.goto(`${BASE_URL}/projects/${PROJECT_ID}/web-tests`, {
      waitUntil: "networkidle",
    });
    await page.screenshot({ path: "e2e-01-web-tests-page.png" });

    // 2. 点击 AI 助手按钮
    console.log("点击 AI 助手按钮...");
    await page.getByRole("button", { name: /AI 助手/ }).click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "e2e-02-ai-chat-opened.png" });

    // 2.5 新建对话，避免加载历史线程的旧中断状态
    console.log("新建对话...");
    const newThreadBtn = page.getByRole("button", { name: /新建对话/ }).first();
    if (await newThreadBtn.isVisible().catch(() => false)) {
      await newThreadBtn.click();
      await page.waitForTimeout(1500);
    }

    // 3. 输入需求并发送
    console.log("输入需求...");
    const textarea = page.locator('textarea[placeholder*="输入您的消息"]').first();
    await textarea.fill(USER_MESSAGE);
    await page.getByRole("button", { name: /发送/ }).click();

    // 4. 等待意图确认面板出现（最多 180 秒，因为涉及多次 LLM 调用）
    console.log("等待意图确认面板...");
    const expandBtn = page.getByRole("button", { name: /扩展已有功能/ }).first();
    await expandBtn.waitFor({ state: "visible", timeout: 180000 });

    await page.screenshot({ path: "e2e-03-intent-confirmation-panel.png" });
    console.log("✅ 意图确认面板已渲染");

    // 5. 验证面板内容
    const reason = await page
      .locator("text=WF-1008")
      .first()
      .isVisible()
      .catch(() => false);
    console.log("推荐原因包含 WF-1008:", reason);

    const newBtn = page.getByRole("button", { name: /新建功能/ }).first();
    const viewBtn = page.getByRole("button", { name: /先查看详情/ }).first();

    console.log("扩展按钮可见:", await expandBtn.isVisible().catch(() => false));
    console.log("新建按钮可见:", await newBtn.isVisible().catch(() => false));
    console.log("查看详情按钮可见:", await viewBtn.isVisible().catch(() => false));

    // 6. 点击扩展按钮
    console.log("点击扩展已有功能...");
    await expandBtn.click();

    // 7. 等待面板消失或进入加载状态
    await page.waitForTimeout(3000);
    await page.screenshot({ path: "e2e-04-after-expand-click.png" });

    // 8. 等待 Agent 继续输出（最多 180 秒）
    console.log("等待 Agent 继续执行...");
    await page
      .locator("text=WF-1008")
      .last()
      .waitFor({ state: "visible", timeout: 180000 });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "e2e-05-continuation.png" });

    console.log("✅ 前端端到端验证通过");
  } catch (error) {
    console.error("❌ 前端验证失败:", error.message);
    await page.screenshot({ path: "e2e-error.png" });
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
