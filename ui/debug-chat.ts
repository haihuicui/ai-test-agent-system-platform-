import { chromium, Browser, Page, Response } from 'playwright';
import fs from 'fs';

(async () => {
  const browser: Browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page: Page = await context.newPage();

  const logs: string[] = [];
  const log = (s: string) => {
    logs.push(s);
    console.log(s);
  };

  page.on('response', async (res: Response) => {
    const url = res.url();
    if (url.includes('/history') || url.includes('/threads/')) {
      const status = res.status();
      let bodyPreview = '';
      try {
        const text = await res.text();
        bodyPreview = text.slice(0, 400);
      } catch {
        bodyPreview = '<body unavailable>';
      }
      log(`RESPONSE ${status} ${url}`);
      log(`  BODY head: ${bodyPreview.replace(/\n/g, ' ')}`);
    }
  });

  page.on('console', (msg) => log(`CONSOLE ${msg.type()}: ${msg.text()}`));
  page.on('pageerror', (err) => log(`PAGEERROR: ${err.message}\n${err.stack || ''}`));

  try {
    // Adjust project id and folder id as needed. PR-1 is used here as example.
    const projectId = process.env.PROJECT_ID || 'PR-1';
    const folderId = process.env.FOLDER_ID || 'a82ad253-7c33-41db-a672-01da83d718d4';
    const chatUrl = `http://localhost:3000/projects/${projectId}/test-cases`;
    log(`Navigating to ${chatUrl}`);
    await page.goto(chatUrl, { waitUntil: 'networkidle', timeout: 30000 });

    // Wait for AI chat trigger button and click it.
    // Heuristic: look for a button containing "AI" or a robot icon in the test-cases page.
    const aiButton = page.locator('button').filter({ hasText: /AI|智能|生成/ }).first();
    if (await aiButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      log('Clicking AI chat button');
      await aiButton.click();
    } else {
      log('AI chat button not found by text heuristic');
    }

    // Wait a bit for history request to fire.
    await page.waitForTimeout(8000);

    // Try to find scrollable chat history container and scroll it multiple times.
    const scrollable = page.locator('[data-slot="dialog-content"], [role="dialog"] .overflow-y-auto, [class*="overflow"]')
      .filter({ has: page.locator('div') })
      .first();

    if (await scrollable.isVisible({ timeout: 3000 }).catch(() => false)) {
      log('Scrolling chat history container');
      for (let i = 0; i < 5; i++) {
        await scrollable.evaluate((el: Element) => el.scrollTop = 0); // scroll to top to trigger older history load
        await page.waitForTimeout(1500);
      }
    } else {
      log('No obvious scrollable chat container found');
      // Fallback: scroll the whole dialog.
      const dialog = page.locator('[role="dialog"]').first();
      if (await dialog.isVisible().catch(() => false)) {
        for (let i = 0; i < 5; i++) {
          await dialog.evaluate((el: Element) => { el.scrollTop = 0; });
          await page.waitForTimeout(1500);
        }
      }
    }

    await page.waitForTimeout(3000);
  } catch (e: any) {
    log(`ERROR: ${e.message}\n${e.stack || ''}`);
  } finally {
    const html = await page.content();
    fs.writeFileSync('debug-chat.html', html);
    fs.writeFileSync('debug-chat-log.txt', logs.join('\n'));
    await browser.close();
    log('Saved debug-chat.html and debug-chat-log.txt');
  }
})();
