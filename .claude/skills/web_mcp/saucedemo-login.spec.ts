import { test, expect } from '@playwright/test';

// SauceDemo 使用 data-test 而非默认的 data-testid
test.use({ testIdAttribute: 'data-test' });

test.describe('用户登录', () => {

  // 场景 1：使用有效凭证成功登录
  test('登录成功 - 标准用户有效凭证', async ({ page }) => {
    // 1. 导航到 SauceDemo 登录页面
    await page.goto('https://www.saucedemo.com');
    await page.waitForLoadState('networkidle');

    // 2. 填写用户名
    await page.getByTestId('username').fill('standard_user');

    // 3. 填写密码
    await page.getByTestId('password').fill('secret_sauce');

    // 4. 点击登录按钮
    await page.getByTestId('login-button').click();
    await page.waitForLoadState('networkidle');

    // 验证：URL 跳转到 inventory.html
    await expect(page).toHaveURL(/.*inventory\.html/);

    // 验证：商品列表容器可见
    await expect(page.getByTestId('inventory-container')).toBeVisible();
  });

  // 场景 2：使用无效凭证登录失败
  test('登录失败 - 无效凭证', async ({ page }) => {
    // 1. 导航到 SauceDemo 登录页面
    await page.goto('https://www.saucedemo.com');
    await page.waitForLoadState('networkidle');

    // 2. 填写无效用户名
    await page.getByTestId('username').fill('invalid_user');

    // 3. 填写错误密码
    await page.getByTestId('password').fill('wrong_password');

    // 4. 点击登录按钮
    await page.getByTestId('login-button').click();

    // 验证：URL 不变仍在登录页
    await expect(page).toHaveURL('https://www.saucedemo.com/');

    // 验证：错误消息可见
    await expect(page.getByTestId('error')).toBeVisible();
  });

  // 场景 3：使用锁定用户登录被拒
  test('登录被拒 - 锁定用户', async ({ page }) => {
    // 1. 导航到 SauceDemo 登录页面
    await page.goto('https://www.saucedemo.com');
    await page.waitForLoadState('networkidle');

    // 2. 填写锁定用户用户名
    await page.getByTestId('username').fill('locked_out_user');

    // 3. 填写密码
    await page.getByTestId('password').fill('secret_sauce');

    // 4. 点击登录按钮
    await page.getByTestId('login-button').click();

    // 验证：URL 不变仍在登录页
    await expect(page).toHaveURL('https://www.saucedemo.com/');

    // 验证：错误消息可见
    await expect(page.getByTestId('error')).toBeVisible();
  });

});
