# Test Plan: SauceDemo 购物结账主流程

## Prerequisites
- **Authentication**: UI login required (project storageState does not persist session for this application)
- **User Role**: Standard user (`standard_user`)
- **Data Requirements**: Product inventory must be available
- **Initial State**: User must not be logged in; cart must be empty
- **TestIdAttribute**: `data-test`

## Test Data
- **Source**: Extracted from page content during exploration
- **Credentials**: `standard_user` / `secret_sauce` (displayed on login page)
- **Test Accounts**:
  | Username | Type | Status |
  |----------|------|--------|
  | standard_user | 标准用户 | 可用 |
  | locked_out_user | 锁定用户 | 不可用 |
  | problem_user | 问题用户 | 可登录但有已知 bug |
- **Default Password**: `secret_sauce` (适用于所有用户)
- **Checkout User Info**: First Name = "John", Last Name = "Doe", Zip/Postal Code = "12345"
- **Test Product**: Sauce Labs Backpack ($29.99)

## Page Coverage
| Page | URL | Status |
|------|-----|--------|
| 登录页 | `https://www.saucedemo.com/` | ✅ Explored |
| 库存页 | `https://www.saucedemo.com/inventory.html` | ✅ Explored |
| 购物车页 | `https://www.saucedemo.com/cart.html` | ✅ Explored |
| 结账信息页 | `https://www.saucedemo.com/checkout-step-one.html` | ✅ Explored |
| 结账概览页 | `https://www.saucedemo.com/checkout-step-two.html` | ✅ Explored |
| 结账完成页 | `https://www.saucedemo.com/checkout-complete.html` | ✅ Explored |

## Test Scenarios

### Scenario 1: 正常购物结账完整流程

**Prerequisites:**
- 用户必须尚未登录
- 库存中至少有一件商品（Sauce Labs Backpack）

**Setup Steps:**
1. 导航到登录页
   - URL: `https://www.saucedemo.com/`
   - **Locator**: N/A
   - **Verified**: ✅
2. 输入用户名
   - **Element**: 用户名输入框
   - **Locator**: `[data-test="username"]`
   - **Data**: `standard_user`
   - **Verified**: ✅
3. 输入密码
   - **Element**: 密码输入框
   - **Locator**: `[data-test="password"]`
   - **Data**: `secret_sauce`
   - **Verified**: ✅
4. 点击登录按钮
   - **Element**: 登录按钮
   - **Locator**: `[data-test="login-button"]`
   - **Verified**: ✅
5. 等待库存页加载完成
   - **Verification**: 页面 URL 变为 `/inventory.html`

**Test Steps:**

1. 导航到登录页
   - URL: `https://www.saucedemo.com/`
   - **Locator**: N/A
   - **Verified**: ✅

2. 输入用户名
   - **Element**: 用户名输入框
   - **Locator**: `[data-test="username"]`
   - **Data**: `standard_user`
   - **Verified**: ✅

3. 输入密码
   - **Element**: 密码输入框
   - **Locator**: `[data-test="password"]`
   - **Data**: `secret_sauce`
   - **Verified**: ✅

4. 点击登录按钮
   - **Element**: 登录按钮
   - **Locator**: `[data-test="login-button"]`
   - **Verified**: ✅

5. 验证登录成功，进入库存页
   - **Element**: 页面标题/URL
   - **Verification**: URL 应为 `https://www.saucedemo.com/inventory.html`
   - **Verified**: ✅

6. 点击"Sauce Labs Backpack"的添加到购物车按钮
   - **Element**: Sauce Labs Backpack 的添加到购物车按钮
   - **Locator**: `[data-test="add-to-cart-sauce-labs-backpack"]`
   - **Verified**: ✅

7. 验证购物车徽章显示数量 1
   - **Element**: 购物车徽章
   - **Locator**: `[data-test="shopping-cart-badge"]`
   - **Expected**: 显示文本 "1"
   - **Verified**: ✅

8. 点击购物车链接
   - **Element**: 购物车链接
   - **Locator**: `a[data-test="shopping-cart-link"]`
   - **Verified**: ✅

9. 验证购物车页面
   - URL: `https://www.saucedemo.com/cart.html`
   - **Verification**: 页面标题为 "Your Cart"，商品 Sauce Labs Backpack 显示在列表中

10. 点击 Checkout 按钮
    - **Element**: 结账按钮
    - **Locator**: `[data-test="checkout"]`
    - **Verified**: ✅

11. 填写名字
    - **Element**: 名字输入框
    - **Locator**: `[data-test="firstName"]`
    - **Data**: `John`
    - **Verified**: ✅

12. 填写姓氏
    - **Element**: 姓氏输入框
    - **Locator**: `[data-test="lastName"]`
    - **Data**: `Doe`
    - **Verified**: ✅

13. 填写邮编
    - **Element**: 邮编输入框
    - **Locator**: `[data-test="postalCode"]`
    - **Data**: `12345`
    - **Verified**: ✅

14. 点击 Continue 按钮
    - **Element**: 继续按钮
    - **Locator**: `[data-test="continue"]`
    - **Verified**: ✅

15. 验证结账概览页面
    - URL: `https://www.saucedemo.com/checkout-step-two.html`
    - **Verification**: 显示商品 Sauce Labs Backpack，价格 $29.99
    - 支付信息: SauceCard #31337
    - 运费: Free Pony Express Delivery!
    - 总计: $32.39（含税 $2.40）

16. 点击 Finish 按钮
    - **Element**: 完成按钮
    - **Locator**: `[data-test="finish"]`
    - **Verified**: ✅

17. 验证结账完成页面
    - URL: `https://www.saucedemo.com/checkout-complete.html`
    - **Verification**: 显示 "Thank you for your order!" 标题
    - 显示完成确认信息

18. 点击 Back Home 按钮返回库存页
    - **Element**: 回到首页按钮
    - **Locator**: `[data-test="back-to-products"]`
    - **Verified**: ✅

19. 验证返回库存页
    - URL: `https://www.saucedemo.com/inventory.html`

**Expected Results:**
- 用户成功登录并进入库存页面
- 商品成功添加到购物车
- 购物车徽章显示正确的商品数量
- 结账时正确输入用户信息
- 结账概览显示正确的商品、价格、税费和总计
- 结账完成页面显示成功确认信息
- 点击 Back Home 后成功返回库存页
- 购物车徽章应消失（结账后购物车已清空）

**Cleanup:**
- 不需要额外清理（每次测试使用 `standard_user`，从干净的会话开始）

---

### Scenario 2: 登录失败 - 锁定用户

**Prerequisites:**
- 用户尚未登录

**Test Steps:**

1. 导航到登录页
   - URL: `https://www.saucedemo.com/`
   - **Locator**: N/A

2. 输入用户名
   - **Element**: 用户名输入框
   - **Locator**: `[data-test="username"]`
   - **Data**: `locked_out_user`

3. 输入密码
   - **Element**: 密码输入框
   - **Locator**: `[data-test="password"]`
   - **Data**: `secret_sauce`

4. 点击登录按钮
   - **Element**: 登录按钮
   - **Locator**: `[data-test="login-button"]`

5. 验证错误消息
   - **Element**: 错误提示框
   - **Locator**: `[data-test="error"]`
   - **Expected**: "Epic sadface: Sorry, this user has been locked out."

**Expected Results:**
- 显示锁定用户的错误消息
- 用户无法进入库存页面

---

### Scenario 3: 登录验证 - 空用户名

**Prerequisites:**
- 用户尚未登录

**Test Steps:**

1. 导航到登录页
   - URL: `https://www.saucedemo.com/`

2. 输入密码（不输入用户名）
   - **Element**: 密码输入框
   - **Locator**: `[data-test="password"]`
   - **Data**: `secret_sauce`

3. 点击登录按钮
   - **Element**: 登录按钮
   - **Locator**: `[data-test="login-button"]`

4. 验证错误消息
   - **Element**: 错误提示框
   - **Locator**: `[data-test="error"]`
   - **Expected**: "Epic sadface: Username is required"

**Expected Results:**
- 显示必填字段错误消息

---

### Scenario 4: 结账验证 - 空必填字段

**Prerequisites:**
- 用户已登录
- 购物车中至少有一件商品

**Setup Steps:**
1-5: 同 Scenario 1 的登录步骤
6: 添加 Sauce Labs Backpack 到购物车
7: 导航到购物车
8: 点击 Checkout

**Test Steps:**

1. 点击 Continue 按钮（不填写任何字段）
   - **Element**: 继续按钮
   - **Locator**: `[data-test="continue"]`

2. 验证错误消息
   - **Element**: 错误提示框
   - **Locator**: `[data-test="error"]`
   - **Expected**: "Error: First Name is required"

**Expected Results:**
- 显示"First Name is required"错误消息
- 用户无法进入下一页面

---

### Scenario 5: 从购物车移除商品

**Prerequisites:**
- 用户已登录
- 购物车中至少有一件商品

**Setup Steps:**
1-6: 同 Scenario 1 的登录并添加到购物车
7: 导航到购物车页面

**Test Steps:**

1. 点击 Remove 按钮
   - **Element**: 移除按钮
   - **Locator**: `[data-test="remove-sauce-labs-backpack"]`

2. 验证购物车为空
   - **Verification**: 购物车中不再显示该商品
   - 购物车徽章应消失或显示 "0"

**Expected Results:**
- 商品从购物车中成功移除

## Locator Summary

| Element | Playwright Locator | Page |
|---------|-------------------|------|
| Username | `[data-test="username"]` | 登录页 |
| Password | `[data-test="password"]` | 登录页 |
| Login Button | `[data-test="login-button"]` | 登录页 |
| Error Container | `[data-test="error"]` | 所有页面 |
| Add to Cart (Backpack) | `[data-test="add-to-cart-sauce-labs-backpack"]` | 库存页 |
| Shopping Cart Badge | `[data-test="shopping-cart-badge"]` | 所有页（顶栏） |
| Shopping Cart Link | `a[data-test="shopping-cart-link"]` | 所有页（顶栏） |
| Checkout Button | `[data-test="checkout"]` | 购物车页 |
| Remove (Backpack) | `[data-test="remove-sauce-labs-backpack"]` | 购物车页 |
| First Name | `[data-test="firstName"]` | 结账信息页 |
| Last Name | `[data-test="lastName"]` | 结账信息页 |
| Zip/Postal Code | `[data-test="postalCode"]` | 结账信息页 |
| Continue Button | `[data-test="continue"]` | 结账信息页 |
| Cancel Button | `[data-test="cancel"]` | 结账信息/概览页 |
| Finish Button | `[data-test="finish"]` | 结账概览页 |
| Back Home | `[data-test="back-to-products"]` | 结账完成页 |

## Authentication
- **认证方式**：需 UI 登录（项目 storageState 对该应用不生效）
- **Setup Steps**:
  1. Navigate to `https://www.saucedemo.com/`
  2. Fill `[data-test="username"]` with `standard_user`
  3. Fill `[data-test="password"]` with `secret_sauce`
  4. Click `[data-test="login-button"]`
