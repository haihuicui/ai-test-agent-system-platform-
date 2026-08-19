/**
 * E2E: WebUI workspace 切换器对本机 9621（补丁版实例）的端到端验证。
 * 运行: node scripts/e2e_webui_workspace_switcher.mjs  （cwd = ui/，用其 node_modules 的 playwright）
 */
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:9621'
let failures = 0
const check = (cond, label, extra = '') => {
  if (cond) {
    console.log(`PASS: ${label}`)
  } else {
    failures++
    console.log(`FAIL: ${label} ${extra}`)
  }
}

const browser = await chromium.launch()
const page = await browser.newPage()

const captured = []
page.on('request', (req) => {
  const url = req.url()
  if (/health|documents|graphs|query/.test(url)) {
    captured.push([url, req.headers()['lightrag-workspace'] ?? null])
  }
})

try {
  await page.goto(`${BASE}/webui`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)
  await page.screenshot({ path: 'scripts/e2e_ws_debug.png', fullPage: false })
  console.log('page title:', await page.title(), '| url:', page.url())

  // 1. 切换器存在（aria-label = Workspace/工作空间）且显示默认空间
  let trigger = page.getByRole('button', { name: /^(Workspace|工作空间)$/ })
  check(await trigger.count() > 0, '切换器存在')
  const triggerText = await trigger.first().innerText()
  check(/默认空间|Default workspace/.test(triggerText), '默认显示默认空间', `got "${triggerText}"`)

  // 2. 打开 Popover 输入 PR-1，出现消毒预览 PR_1
  await trigger.first().click()
  await page.waitForTimeout(400)
  const input = page.locator('[data-slot="popover-content"] input, .popover-content input, input').last()
  await input.fill('PR-1')
  await page.waitForTimeout(300)
  const bodyText = await page.innerText('body')
  check(/PR_1/.test(bodyText), '消毒预览显示 PR_1')

  // 3. 应用切换（Enter 键）
  await input.press('Enter')
  await page.waitForTimeout(800)
  const stored = await page.evaluate(
    () => JSON.parse(localStorage.getItem('settings-storage')).state.workspace
  )
  check(stored === 'PR_1', 'localStorage 持久化 workspace=PR_1', `got ${stored}`)

  // 4. 刷新后请求带头
  captured.length = 0
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForTimeout(2000)
  const healthWithWs = captured.filter(([u, h]) => u.includes('health') && h === 'PR_1')
  check(healthWithWs.length > 0, '刷新后 /health 携带 LIGHTRAG-WORKSPACE: PR_1',
    `captured=${JSON.stringify(captured.slice(0, 6))}`)

  // 5. 切回默认空间
  const trigger2 = page.getByRole('button', { name: /^(Workspace|工作空间)$/ })
  await trigger2.first().click()
  await page.waitForTimeout(400)
  const defaultItem = page.getByRole('option', { name: /默认空间|Default workspace/ })
  await defaultItem.first().click()
  await page.waitForTimeout(600)
  const stored2 = await page.evaluate(
    () => JSON.parse(localStorage.getItem('settings-storage')).state.workspace
  )
  check(stored2 === '', '切回默认空间 workspace=""', `got ${stored2}`)

  // 6. 切回后请求不再带头
  captured.length = 0
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForTimeout(2000)
  const leaked = captured.filter(([, h]) => h)
  check(leaked.length === 0, '切回后请求不再携带 workspace 头',
    `leaked=${JSON.stringify(leaked.slice(0, 3))}`)
} finally {
  await browser.close()
}

console.log(failures === 0 ? '\n=== ALL PASS ===' : `\n=== ${failures} FAIL ===`)
process.exit(failures === 0 ? 0 : 1)
